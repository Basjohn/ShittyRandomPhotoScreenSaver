"""Expanded Visualizer: the takeover coordinator (plan 01 §0.3, milestone M2).

The one owner of the takeover's effective state. It sits beside the Visualizer host binding: the display manager
that keeps the binding's "which unit" record creates it lazily (only when a capable mode or a saved intent needs
it, so an incapable Visualizer imports and constructs nothing new) and retires it with that record. It is a plain
object: no QObject, no signal, no timer, no thread. It is called only on events (an owner admission, the glyph, a
mode request and its completion, Edit, the owner's retirement), never per frame.

Every event goes through the pure reducer (``core.expanded_visualizer_takeover.reduce``); this module only
translates the facts in and performs the actions it returns through the existing owners:

* the display-wide viewport through ``QuickDisplayVisualizerOwner.set_expanded_display`` (a presentation route;
  nothing is written to the ordinary geometry, CUSTOM, presets or Settings);
* the intent through one narrow Settings write (``widgets.spotify_visualizer.expanded_display_requested``);
* a mode request through the canonical path, held until a collapse commits when the target is incapable;
* the glyph's availability and direction through the owning scene.

Fences (§0.5): the takeover generation is this coordinator's own admission serial, advanced at every owner
admission (a Settings return or topology change replaces the display manager, and with it this object). The
engine's generation is not used: it advances with every preset and mode activation. Glyph presses carry the
activation the glyph was published for and the owning display's key; completions carry the reducer's
transaction id.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from core.expanded_visualizer_takeover import (
    BeginEnter,
    BeginExit,
    BeginTransfer,
    CancelEnter,
    EditEntered,
    EditExited,
    EditResolutionDeclined,
    EnterCommitted,
    EnterFailed,
    EnterPrepared,
    ExitCommitted,
    ExitReason,
    ForwardModeRequest,
    GenerationReady,
    GlyphPressed,
    ModeActivated,
    ModeCycleRequested,
    ModeRejected,
    ModeRequested,
    OwnerRetired,
    PersistIntent,
    Phase,
    RejectModeRequest,
    RejectTransfer,
    RequestEditResolution,
    RetireTakeover,
    RollbackTransfer,
    RunEnter,
    TakeoverState,
    TransferCommitted,
    TransferFailed,
    TransferRequested,
    initial_state,
    reduce,
)
from core.logging.logger import get_logger

logger = get_logger(__name__)

#: Phases in which the view is (or is becoming) display-wide: the glyph offers the collapse.
_EXPANDED_FACING = frozenset({Phase.ENTER_PENDING, Phase.ENTERING, Phase.EXPANDED})
#: Phases in which ordinary layout gestures (move, scale, transfer, hover edit glyphs) must wait.
_LAYOUT_BLOCKING = frozenset({Phase.ENTER_PENDING, Phase.ENTERING, Phase.EXPANDED, Phase.EXITING,
                              Phase.TRANSFER_PENDING})


@dataclass(frozen=True)
class ExpandedDisplayServices:
    """What the coordinator reads and calls, as callables read at call time (reach the caller weakly)."""

    admitted_owner: Callable[[], Any]
    admitted_unit: Callable[[], Any]
    #: The persisted intent (normalized bool).
    requested: Callable[[], bool]
    persist_requested: Callable[[bool], None]
    #: ``resolve_expanded_display_capable`` for this mode under the current mode activation.
    mode_capable: Callable[[str], bool]
    #: Any CUSTOM session (Edit or a direct Alt gesture) is active.
    edit_active: Callable[[], bool]
    #: Project the glyph on one unit: (unit, available, expanded).
    publish_glyph: Callable[[Any, bool, bool], None]
    #: The card's ordinary edge margin (logical px): the display-wide card is inset by it (operator, 7 Nov).
    edge_margin: Callable[[], float] = lambda: 0.0


def display_key(unit: Any) -> str | None:
    """The physical display identity a takeover event names."""

    if unit is None:
        return None
    try:
        identity = unit.runtime.display_identity
        return f"{int(unit.screen_index)}:{identity.screen_key}"
    except Exception:
        return None


def _owner_activation(owner: Any) -> int | None:
    engine = getattr(getattr(owner, "controller", None), "engine", None)
    getter = getattr(engine, "get_activation_id", None)
    if not callable(getter):
        return 0
    try:
        return int(getter())
    except Exception:
        return None


class ExpandedDisplayCoordinator:
    """Feed takeover events to the reducer and perform its actions; one per display manager."""

    def __init__(self, services: ExpandedDisplayServices) -> None:
        self._services = services
        self._state: TakeoverState = initial_state()
        self._generation = 0
        self._press_serial = 0
        self._request_serial = 0
        self._forwards: dict[int, Callable[[str], bool]] = {}
        self._rejected: set[int] = set()
        self._events: deque[Any] = deque()
        self._dispatching = False
        self._glyph_unit: Any = None
        self._glyph_activation: int | None = None
        self._transfer_done = False
        self._retired = False

    # ---------------------------------------------------------------------------------------------- facts

    @property
    def state(self) -> TakeoverState:
        return self._state

    @property
    def phase(self) -> Phase:
        return self._state.phase

    @property
    def blocks_ordinary_layout(self) -> bool:
        """True while the view is, or is becoming, display-wide: ordinary layout gestures wait."""

        return self._state.phase in _LAYOUT_BLOCKING

    # --------------------------------------------------------------------------------------------- events

    def generation_ready(self) -> None:
        """An owner was admitted (startup, Settings return, reload, topology): evaluate the intent once.

        Called right after admission, before the generation is revealed, so a restored expansion is never first
        shown as an ordinary card. With Edit active the restore's preflight fails (Edit never shows an expanded
        state) and Edit's exit re-applies it.
        """

        if self._retired:
            return
        owner = self._services.admitted_owner()
        unit = self._services.admitted_unit()
        self._generation += 1
        live = owner is not None and unit is not None and not bool(getattr(owner, "is_retired", True))
        mode_id = str(owner.controller.mode_id) if live else None
        self._feed(GenerationReady(
            self._generation,
            _owner_activation(owner) if live else None,
            display_key(unit) if live else None,
            mode_id,
            bool(live and self._services.mode_capable(mode_id)),
            bool(self._services.requested()),
        ))
        if live and self._services.edit_active():
            self._feed(EditEntered(self._generation))

    def glyph_pressed(self, unit: Any, expand: bool) -> bool:
        """The visible glyph on ``unit`` was pressed. Returns True when the reducer admitted it."""

        if self._retired or self._glyph_activation is None:
            return False
        self._press_serial += 1
        step_outcomes = self._feed(GlyphPressed(
            self._generation, self._glyph_activation, display_key(unit), self._press_serial, bool(expand)
        ))
        return bool(step_outcomes) and step_outcomes[0] == "applied"

    def mode_requested(self, mode_id: str, forward: Callable[[], bool]) -> bool:
        """Route one canonical mode request. Returns False when it was refused (now or by the canonical path).

        ``forward`` performs the canonical request; it runs now, or after the collapse commits when the current
        view is expanded and the target is incapable (its ``True`` then only means the request is in flight).
        """

        if self._retired:
            return bool(forward())
        return self._route_request(
            lambda request_id: ModeRequested(self._generation, request_id, str(mode_id),
                                             bool(self._services.mode_capable(str(mode_id)))),
            lambda _target: bool(forward()),
            stale=lambda: bool(forward()),
        )

    def mode_cycle_requested(self, order: tuple[str, ...], request: Callable[[str], bool]) -> bool:
        """The double-click's next mode. ``order`` is every other enabled mode in cycle order after the current one
        (wrapping); ``request(mode)`` performs the canonical request. While expanded the cycle skips incapable modes
        and stays expanded, and with no other capable mode stays put (operator, 7 Nov); a collapsed view takes the
        next mode. Returns False when nothing was requested."""

        candidates = tuple((str(mode), bool(self._services.mode_capable(str(mode)))) for mode in order)
        if self._retired:
            return bool(candidates) and bool(request(candidates[0][0]))
        return self._route_request(
            lambda request_id: ModeCycleRequested(self._generation, request_id, candidates),
            request,
            stale=lambda: bool(candidates) and bool(request(candidates[0][0])),
        )

    def _route_request(self, make_event: Callable[[int], Any], forward: Callable[[str], bool], *,
                       stale: Callable[[], bool]) -> bool:
        self._request_serial += 1
        request_id = self._request_serial
        self._forwards[request_id] = forward
        outcomes = self._feed(make_event(request_id))
        if outcomes and outcomes[0] == "stale":
            # No current takeover generation (none admitted yet, or it is retiring): it has no say.
            self._forwards.pop(request_id, None)
            return stale()
        if request_id in self._rejected:
            self._forwards.pop(request_id, None)
            return False
        return True

    def mode_activated(self) -> None:
        """A canonical mode or preset activation completed (its activation id is the engine's newest)."""

        if self._retired:
            return
        owner = self._services.admitted_owner()
        unit = self._services.admitted_unit()
        if owner is None or unit is None or bool(getattr(owner, "is_retired", True)):
            return
        activation = _owner_activation(owner)
        if activation is None:
            return
        mode_id = str(owner.controller.mode_id)
        self._feed(ModeActivated(self._generation, activation, display_key(unit), mode_id,
                                 bool(self._services.mode_capable(mode_id))))

    def display_transferred(self) -> None:
        """The ordinary Visualizer moved to another display (the CUSTOM transaction already committed the move
        through the host binding; the display manager refuses one while the view is not ordinary)."""

        if self._retired or self._state.activation is None:
            return
        self._request_serial += 1
        self._transfer_done = True
        try:
            self._feed(TransferRequested(self._generation, self._state.activation, self._request_serial,
                                         display_key(self._services.admitted_unit()), True))
        finally:
            self._transfer_done = False

    def edit_entered(self) -> None:
        """Before an Edit session (or a direct Alt gesture) starts: an expanded view collapses first, at once."""

        if not self._retired and not self._state.edit_active:
            self._feed(EditEntered(self._generation))

    def edit_exited(self, *, saved: bool) -> None:
        if not self._retired and self._state.edit_active:
            self._feed(EditExited(self._generation, bool(saved)))

    def owner_retired(self, reason: str = "owner") -> None:
        """The admitted owner went (Settings, reload, Visualizer off, topology, shutdown): the state dies, the
        intent persists, the glyph is withdrawn."""

        if self._state.generation is None or self._state.phase is Phase.RETIRING:
            self._withdraw_glyph()
            return
        self._feed(OwnerRetired(self._generation, str(reason)))

    def retire(self) -> None:
        """The display manager retires: drop everything; nothing is called afterwards."""

        self.owner_retired("manager")
        self._retired = True
        self._forwards.clear()
        self._events.clear()

    # ------------------------------------------------------------------------------------------- dispatch

    def _feed(self, event: Any) -> list[str]:
        """Reduce ``event`` (after anything already queued) and perform the actions, in order.

        Completions an action reports synchronously (a non-animated route swap) are queued behind the current
        step's remaining actions, never reduced inside them. Returns the outcomes of the events this call drained
        (the first is ``event``'s when nothing was already dispatching).
        """

        self._events.append(event)
        if self._dispatching:
            return []
        outcomes: list[str] = []
        self._dispatching = True
        try:
            while self._events:
                current = self._events.popleft()
                step = reduce(self._state, current)
                self._state = step.state
                outcomes.append(step.outcome.value)
                for action in step.actions:
                    self._perform(action)
        finally:
            self._dispatching = False
        self._publish_glyph()
        return outcomes

    def _complete(self, event: Any) -> None:
        self._feed(event)

    def _perform(self, action: Any) -> None:
        generation = self._state.generation
        owner = self._services.admitted_owner()
        if isinstance(action, BeginEnter):
            self._events.append(
                EnterPrepared(generation, action.txn) if self._preflight(owner)
                else EnterFailed(generation, action.txn, "preflight")
            )
        elif isinstance(action, RunEnter):
            started = owner is not None and owner.set_expanded_display(
                True,
                animate=bool(action.animate),
                edge_margin=float(self._services.edge_margin()),
                on_complete=lambda txn=action.txn, gen=generation: self._complete(EnterCommitted(gen, txn)),
            )
            if not started:
                self._events.append(EnterFailed(generation, action.txn, "owner"))
        elif isinstance(action, CancelEnter):
            if owner is not None and (owner.expanded_display or owner.expanded_display_transition_active):
                owner.set_expanded_display(False, animate=False)
        elif isinstance(action, BeginExit):
            # Edit never shows an expanded state: its collapse is immediate, before the session draws.
            animate = bool(action.animate) and action.reason is not ExitReason.EDIT
            done = owner is not None and owner.set_expanded_display(
                False,
                animate=animate,
                on_complete=lambda txn=action.txn, gen=generation: self._complete(ExitCommitted(gen, txn)),
            )
            if not done:
                # No owner to draw it: the collapse is trivially complete.
                self._events.append(ExitCommitted(generation, action.txn))
        elif isinstance(action, PersistIntent):
            self._services.persist_requested(bool(action.requested))
        elif isinstance(action, ForwardModeRequest):
            forward = self._forwards.pop(action.request_id, None)
            accepted = False
            if forward is not None:
                try:
                    accepted = bool(forward(action.mode_id))
                except Exception:
                    logger.exception("[EXPANDED_VIS] Canonical mode request failed")
            if not accepted:
                self._rejected.add(action.request_id)
                self._events.append(ModeRejected(generation, action.request_id))
        elif isinstance(action, RejectModeRequest):
            self._forwards.pop(action.request_id, None)
            self._rejected.add(action.request_id)
            logger.info("[EXPANDED_VIS] Mode request refused: %s", action.reason)
        elif isinstance(action, RequestEditResolution):
            # The glyph is withdrawn under Edit, so this arises only from a stale press: never discard a draft
            # implicitly; the session keeps its draft and Edit.
            self._events.append(EditResolutionDeclined(generation))
        elif isinstance(action, BeginTransfer):
            # Only an ordinary move that already committed is reported. An expanded transfer is M5 (one
            # source-collapse + transfer + target-expand transaction); until then the routes refuse it.
            done = self._transfer_done and not action.expanded
            self._events.append(TransferCommitted(generation, action.txn) if done
                                else TransferFailed(generation, action.txn))
        elif isinstance(action, (RollbackTransfer, RejectTransfer)):
            pass
        elif isinstance(action, RetireTakeover):
            for request_id in tuple(self._forwards):
                self._rejected.add(request_id)
            self._forwards.clear()
            if owner is not None and not bool(getattr(owner, "is_retired", True)):
                owner.set_expanded_display(False, animate=False)
        else:  # pragma: no cover - the reducer's action set is closed
            raise TypeError(f"unknown takeover action: {action!r}")

    def _preflight(self, owner: Any) -> bool:
        """D1 steps 1-5: a live, started owner on a live display, no Edit session, a positive display rect."""

        unit = self._services.admitted_unit()
        if owner is None or unit is None or bool(getattr(owner, "is_retired", True)):
            return False
        if bool(getattr(unit, "is_retired", False)) or self._services.edit_active():
            return False
        if display_key(unit) != self._state.display:
            return False
        try:
            _x, _y, width, height = unit.runtime.display_identity.geometry
        except Exception:
            return False
        return float(width) > 0.0 and float(height) > 0.0

    # ---------------------------------------------------------------------------------------------- glyph

    def _withdraw_glyph(self) -> None:
        unit = self._glyph_unit
        self._glyph_unit = None
        self._glyph_activation = None
        if unit is not None and not bool(getattr(unit, "is_retired", True)):
            try:
                self._services.publish_glyph(unit, False, False)
            except RuntimeError:
                pass

    def _publish_glyph(self) -> None:
        state = self._state
        unit = self._services.admitted_unit()
        if state.phase is Phase.RETIRING or self._retired or unit is None:
            self._withdraw_glyph()
            return
        if self._glyph_unit is not None and self._glyph_unit is not unit:
            self._withdraw_glyph()
        available = bool(state.mode_capable and not state.edit_active
                         and state.phase is not Phase.TRANSFER_PENDING)
        self._glyph_unit = unit
        self._glyph_activation = state.activation if available else None
        self._services.publish_glyph(unit, available, state.phase in _EXPANDED_FACING)


__all__ = ["ExpandedDisplayCoordinator", "ExpandedDisplayServices", "display_key"]
