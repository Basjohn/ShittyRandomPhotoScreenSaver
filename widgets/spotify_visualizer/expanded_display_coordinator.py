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
* the glyph's availability and direction through the owning scene;
* the ordinary widgets on the owning display (M3, §F): one display-local transient visual policy on the retained
  scene (``set_ordinary_widgets_covered``), covered as the enter runs (D1.6) and uncovered as a collapse, a failed
  or cancelled enter, or a retirement begins (D2.2). It hides the cards and their shadows, never retires them:
  every family, model, provider and display lease (Media, Gmail, Feeds, Steam...) stays exactly as it was, so the
  Visualizer's Media truth and every shared backend keep their consumers, and collapsing returns each widget exactly
  as it was. The OSD's foreground lane is outside the cover. Other displays are never touched.
* Fullscreen Edit (M3c): Edit entered on a resting expanded view keeps it expanded (no collapse transaction); the
  display manager then opens the Edit session on the full-display overlays only (``fullscreen_edit``). A collapse
  press under it is answered through the Edit session (declined: its draft and Edit stay); the one forced end
  (an incapable mode became the Visualizer's) ends the session through ``end_fullscreen_edit``.
* An Edit beside the view (plan 1B.1): Edit entered on another display while the view rests expanded edits that
  display's ordinary layout (``edit_elsewhere``); the view stays expanded and running outside the session, with
  Fullscreen Edit's holds.

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
    EndFullscreenEdit,
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
    #: Cover (True) or uncover the ordinary widget lanes on one unit: (unit, covered, fade seconds; 0 snaps).
    cover_widgets: Callable[[Any, bool, float], None] = lambda _unit, _covered, _fade_s: None
    #: End a Fullscreen Edit session whose expanded view cannot stay (its draft is not saved).
    end_fullscreen_edit: Callable[[], None] = lambda: None
    #: Move the collapsed Visualizer onto the display a takeover event names (plan 1B.12): the CUSTOM display hop and
    #: its Save, with no Edit chrome. True once committed; False (or a raise) leaves the source exactly as it was.
    move_to_display: Callable[[str], bool] = lambda _display: False
    #: The live display unit a takeover event's display key names (None: none), for the move's target runtime.
    display_unit: Callable[[str], Any] = lambda _display: None


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
        #: The unit whose ordinary widgets are covered (None: none), and the owner's fade half last seen.
        self._cover_unit: Any = None
        self._fade_half_s = 0.0
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
    def covered_unit(self) -> Any:
        """The unit whose display the Expanded Visualizer covers (None: none): covered as the enter starts, uncovered
        as a collapse, a failed or cancelled enter, or a retirement starts (the M3 widget cover's own edges). The
        display manager leaves it out of image batches while it already shows an image (plan 01 E0, M4)."""

        return self._cover_unit

    @property
    def fullscreen_edit(self) -> bool:
        """Edit is open on the expanded view (M3c): it edits the full-display overlays, never the ordinary layout."""

        return bool(self._state.edit_fullscreen)

    @property
    def edit_elsewhere(self) -> bool:
        """Edit is open on another display while the view stays expanded (plan 1B.1): an ordinary Edit of the other
        displays; the view's display is not in the session."""

        return bool(self._state.edit_elsewhere)

    @property
    def transfer_in_flight(self) -> bool:
        """The takeover's own display transfer is running (its move reaches the host binding while layout waits)."""

        return self._state.phase is Phase.TRANSFER_PENDING and not self._transfer_done

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

    def expand_on_display(self, unit: Any, target: Any) -> bool:
        """A display glyph on ``unit`` (the card's display) asked for the view display-wide on ``target``'s display
        (plan 1B.12). On the view's own display it is that display's glyph press (expand, or collapse while
        expanded there); on another display it is one transfer transaction of the reducer: a collapsed view moves
        and then expands there, an expanded one moves expanded. Returns True when the reducer admitted it."""

        if self._retired or self._glyph_activation is None or target is None:
            return False
        state = self._state
        if display_key(unit) != state.display:
            return False
        if display_key(target) == state.display:
            return self.glyph_pressed(unit, state.phase not in _EXPANDED_FACING)
        self._request_serial += 1
        outcomes = self._feed(TransferRequested(self._generation, self._glyph_activation, self._request_serial,
                                                display_key(target), True, True))
        return bool(outcomes) and outcomes[0] == "applied"

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

    def edit_entered(self, *, on_view_display: bool = True) -> None:
        """Before an Edit session (or a direct Alt gesture) starts. A resting expanded view stays expanded: Edit
        entered on its display becomes Fullscreen Edit (``fullscreen_edit``), Edit entered on another display an
        ordinary Edit of the other displays (``edit_elsewhere``). A view still entering or moving collapses at its
        commit edge, as before (an ordinary Edit)."""

        if not self._retired and not self._state.edit_active:
            self._feed(EditEntered(self._generation, bool(on_view_display)))

    def edit_exited(self, *, saved: bool) -> None:
        if not self._retired and self._state.edit_active:
            self._feed(EditExited(self._generation, bool(saved)))

    def owner_retired(self, reason: str = "owner") -> None:
        """The admitted owner went (Settings, reload, Visualizer off, topology, shutdown): the state dies, the
        intent persists, the glyph is withdrawn."""

        if self._state.generation is None or self._state.phase is Phase.RETIRING:
            self._withdraw_glyph()
            self._cover_widgets(False, animate=True)
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
            # D1.6 before D1.7: the widgets fade out with the card's first half (a restore before reveal snaps).
            self._cover_widgets(True, animate=bool(action.animate))
            started = owner is not None and owner.set_expanded_display(
                True,
                animate=bool(action.animate),
                on_complete=lambda txn=action.txn, gen=generation: self._complete(EnterCommitted(gen, txn)),
            )
            if not started:
                self._events.append(EnterFailed(generation, action.txn, "owner"))
        elif isinstance(action, CancelEnter):
            # Whatever had begun to fade comes back with a fade (fade, never vanish or pop).
            self._cover_widgets(False, animate=True)
            if owner is not None and (owner.expanded_display or owner.expanded_display_transition_active):
                owner.set_expanded_display(False, animate=False)
        elif isinstance(action, BeginExit):
            # Edit never shows an expanded state: its collapse is immediate, before the session draws.
            animate = bool(action.animate) and action.reason is not ExitReason.EDIT
            # D2.2 before D2.4: the widgets fade back in while the display-wide card fades out.
            self._cover_widgets(False, animate=animate)
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
            # The glyph is withdrawn under Edit (Fullscreen Edit too), so this arises only from a stale press: never
            # discard or save a draft implicitly; the session keeps its draft and Edit (Save or Cancel first).
            self._events.append(EditResolutionDeclined(generation))
        elif isinstance(action, EndFullscreenEdit):
            logger.warning("[EXPANDED_VIS] Fullscreen Edit ends with its view (the mode is no longer capable)")
            self._services.end_fullscreen_edit()
        elif isinstance(action, BeginTransfer):
            if self._transfer_done:
                # An ordinary move Edit already committed (its display hop and Save) is only reported.
                self._events.append(TransferCommitted(generation, action.txn) if not action.expanded
                                    else TransferFailed(generation, action.txn))
            else:
                self._run_display_move(generation, action)
        elif isinstance(action, (RollbackTransfer, RejectTransfer)):
            pass
        elif isinstance(action, RetireTakeover):
            for request_id in tuple(self._forwards):
                self._rejected.add(request_id)
            self._forwards.clear()
            # A reload or the Visualizer turning off leaves the display's widgets: they fade back in (a scene that
            # is retiring with the generation ignores it).
            self._cover_widgets(False, animate=True)
            if owner is not None and not bool(getattr(owner, "is_retired", True)):
                owner.set_expanded_display(False, animate=False)
        else:  # pragma: no cover - the reducer's action set is closed
            raise TypeError(f"unknown takeover action: {action!r}")

    def _move(self, target_display: str) -> bool:
        try:
            return bool(self._services.move_to_display(str(target_display)))
        except Exception:
            logger.exception("[EXPANDED_VIS] Visualizer display move failed")
            return False

    def _run_display_move(self, generation: int | None, action: BeginTransfer) -> None:
        """One display move as one fade-through across the two displays (Current_Plan 1C.2; supersedes the 1B.12
        "collapse, move, expand" form, which drew the ordinary card on both displays and popped it across).

        The owner prepares the target while the view still draws, fades the view out where it is (the source's
        covered widgets fade back in with it), moves it at zero opacity through the CUSTOM hop and Save (``hop``),
        and fades it in on the target in the route it ends in (``action.end_expanded``; the target's widgets fade
        out with a display-wide arrival). A refused move fades the view back in where it was, so the reducer's
        rollback finds it exactly as it was. A stale completion (another generation or transaction) does nothing."""

        owner = self._services.admitted_owner()
        target = self._services.display_unit(action.target_display)

        def hop() -> bool:
            if self._stale_transfer(generation, action.txn):
                return False
            return self._move(action.target_display)

        def faded_out() -> None:
            if not self._stale_transfer(generation, action.txn) and action.expanded:
                self._cover_widgets(False, animate=True)

        def fading_in(moved: bool) -> None:
            if self._stale_transfer(generation, action.txn):
                return
            if action.end_expanded if moved else action.expanded:
                self._cover_widgets(True, animate=True)      # the display the view arrives on display-wide

        def done(moved: bool) -> None:
            if not self._stale_transfer(generation, action.txn):
                self._complete(TransferCommitted(generation, action.txn) if moved
                               else TransferFailed(generation, action.txn))

        runtime = getattr(target, "runtime", None)
        started = owner is not None and runtime is not None and bool(owner.move_display(
            runtime, end_expanded=bool(action.end_expanded), hop=hop, on_fade_out=faded_out, on_fade_in=fading_in,
            on_complete=done))
        if started:
            return
        # No running owner to draw a fade (or the target is gone): the move happens at once, unseen.
        self._cover_widgets(False, animate=True)
        moved = target is not None and self._move(action.target_display)
        live = self._services.admitted_owner()
        if live is not None and (action.end_expanded if moved else action.expanded):
            live.set_expanded_display(True, animate=False)
            self._cover_widgets(True, animate=False)
        self._events.append(TransferCommitted(generation, action.txn) if moved
                            else TransferFailed(generation, action.txn))

    def _stale_transfer(self, generation: int | None, txn: int) -> bool:
        state = self._state
        return (self._retired or state.generation != generation or state.txn != txn
                or state.phase is not Phase.TRANSFER_PENDING)

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

    # ----------------------------------------------------------------------------------- widget cover (M3)

    def _cover_widgets(self, covered: bool, *, animate: bool) -> None:
        """Cover the owning display's ordinary widgets, or uncover whichever display is covered (idempotent).

        The fade is the owner's fade half, so the widgets leave with the card's first half and return with the
        display-wide card's fade-out; ``animate`` False snaps (a restore before reveal, Edit's collapse). Only one
        display is ever covered: covering another first uncovers the previous one.
        """

        half = getattr(self._services.admitted_owner(), "expanded_display_fade_half_s", None)
        if isinstance(half, (int, float)) and float(half) > 0.0:
            # Remembered: a retirement uncovers after the owner has gone, with the same fade.
            self._fade_half_s = float(half)
        fade = self._fade_half_s if animate else 0.0
        unit = self._services.admitted_unit() if covered else None
        previous = self._cover_unit
        if previous is not None and previous is not unit:
            self._cover_unit = None
            self._project_cover(previous, False, fade)
        if covered and unit is not None and previous is not unit:
            self._cover_unit = unit
            self._project_cover(unit, True, fade)

    def _project_cover(self, unit: Any, covered: bool, fade_s: float) -> None:
        if unit is None or bool(getattr(unit, "is_retired", False)):
            return
        try:
            self._services.cover_widgets(unit, bool(covered), float(fade_s))
        except RuntimeError:
            # A scene already retiring with its generation: nothing of it remains to cover.
            pass

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
