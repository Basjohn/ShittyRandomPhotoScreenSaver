"""Expanded Visualizer takeover: the pure event/action reducer (plan 01 §D, milestone M1).

``reduce(state, event)`` is the one place that decides the takeover's effective state. It is a plain function over
frozen values: no Qt, no GL, no timer, no thread, no QObject, no settings access and no import beyond the standard
library. The coordinator that lands beside the Visualizer host binding at M2 calls it only on events (glyph, mode
request and completion, transfer, monitor loss, Edit, Settings, readiness, shutdown), never per frame, and performs
the actions it returns through the existing owners. Nothing in production calls it yet.

Vocabulary (plan 01 §D)::

    DORMANT            no visualizer owner, or the active mode is not capable
    ORDINARY           capable mode at its canonical rect; widgets and wallpaper normal
    ENTER_PENDING      enter issued; the coordinator is preflighting it (D1 steps 1-5), nothing visible yet
    ENTERING           the one eased viewport transition is running (D1 steps 6-7)
    EXPANDED           display-wide viewport committed
    EXITING            the reverse transition is running (D2)
    TRANSFER_PENDING   one source-collapse + transfer + target-expand transaction is running (D4)
    RETIRING           the generation is closing (Settings, topology loss, shutdown); its late events are ignored

Rules this reducer enforces:

* **Retirement.** Settings, a runtime reload or the Visualizer turning off (``OwnerRetired``), the owning display's
  loss and shutdown retire the generation's state; the persisted intent is untouched.
* **Fences.** Every event names the runtime generation; anything older than the state's generation, or any event
  for a retiring generation, is ``STALE`` and changes nothing. A newer generation is adopted only at its readiness
  edge (``GenerationReady``), which re-evaluates the persisted intent exactly once. Glyph presses must also name the
  current visualizer activation and owning display; completions must name the transaction in flight.
* **Idempotency.** Glyph press ids only increase; a repeated id is ``DUPLICATE``. A press the current phase already
  satisfies (expand while entering or expanded, collapse while collapsing) is coalesced as ``DUPLICATE``. One
  latest opposite press during a running transition is held to its commit edge; there is no queue.
* **Intent.** ``requested`` mirrors ``widgets.spotify_visualizer.expanded_display_requested``. Full display is the
  user's explicit request (operator, 7 Nov: "a preset should not have the power to decide it"), so only two things
  write it. The user's glyph: ``PersistIntent(True)`` once, when a user-initiated enter commits on a capable mode
  (never on press or failure), and ``PersistIntent(False)`` when the user's collapse is accepted. And a switch to an
  incapable mode: ``PersistIntent(False)`` once that mode is the Visualizer's and nothing is drawn expanded any more
  (the collapse has committed), whether it was expanded or only held the intent, and when a generation becomes ready
  on an incapable mode (a mode chosen in Settings). A later capable mode therefore starts ordinary: a mode switch
  never re-expands. Edit, Settings, monitor loss and shutdown collapse or retire without writing it, so the intent
  re-applies at the next eligible edge while the capable mode stays selected (Edit exit, a new generation's
  readiness).
* **Eligibility.** Expansion is effective only when the mode is capable (the caller resolves ``mode_capable`` with
  ``core.settings.visualizer_mode_registry.resolve_expanded_display_capable``: registered, active, enabled and
  opted in), an owner and display are bound, and no ordinary Edit is active. EXPANDED never holds while any of those
  fails.
* **Fullscreen Edit (M3c, operator 8 Nov; supersedes "entering Edit collapses").** Edit entered on a resting
  EXPANDED view keeps it expanded (``edit_fullscreen``): Edit edits the full-display overlays only. Nothing that
  would end it may discard or save its draft implicitly: a collapse press waits for the Edit session's own
  Save/Cancel (``RequestEditResolution``; a declined resolution drops the press), and an incapable mode request or a
  transfer is refused until Edit ends. Edit entered while an enter, exit or transfer runs is an ordinary Edit, which
  collapses as before.
* **Edit beside the view (operator, 11 Nov, plan 1B.1).** Edit edits the display it was entered on. Entered on
  another display while the view rests EXPANDED (``EditEntered.on_view_display`` False), it is an ordinary Edit of
  the other displays only (``edit_elsewhere``): the view stays expanded and running, outside the session, with the
  same holds as Fullscreen Edit (a collapse press waits for the session's own Save/Cancel, an incapable mode request
  and a transfer are refused), since collapsing would put the view's display back into a layout the session does not
  hold. An incapable activation collapses the view and leaves the Edit as an ordinary one (it never held the view).
* **Rollback.** A failed enter restores ORDINARY without touching the intent and without retrying; a failed or lost
  transfer restores the source exactly as it was; a mode request held for a capable -> incapable collapse that is
  then rejected re-expands the still-active capable mode (the mode never changed, so the intent still stands).
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum


class Phase(str, Enum):
    DORMANT = "dormant"
    ORDINARY = "ordinary"
    ENTER_PENDING = "enter_pending"
    ENTERING = "entering"
    EXPANDED = "expanded"
    EXITING = "exiting"
    TRANSFER_PENDING = "transfer_pending"
    RETIRING = "retiring"


#: Phases with a transaction in flight; its completion must name ``TakeoverState.txn``.
TRANSACTION_PHASES = frozenset({Phase.ENTER_PENDING, Phase.ENTERING, Phase.EXITING, Phase.TRANSFER_PENDING})
#: Resting phases: nothing in flight, the scene is coherent.
RESTING_PHASES = frozenset({Phase.DORMANT, Phase.ORDINARY, Phase.EXPANDED})


class Outcome(str, Enum):
    APPLIED = "applied"        # the event was admitted (it may still emit no action)
    STALE = "stale"            # wrong/retired generation, activation, display or transaction: nothing changes
    DUPLICATE = "duplicate"    # a repeated press, or one the current phase already satisfies
    REJECTED = "rejected"      # a current-generation request the takeover cannot honour now
    IGNORED = "ignored"        # current, but no takeover consequence (another display lost, unrelated rejection)


class Origin(str, Enum):
    USER = "user"              # the glyph: commits persist the intent
    RESTORE = "restore"        # the persisted intent re-applied at an eligible edge: never persists
    ROLLBACK = "rollback"      # re-expanding after a held mode request was rejected: never persists


class ExitReason(str, Enum):
    USER = "user"
    EDIT = "edit"
    MODE_INCAPABLE = "mode_incapable"
    CAPABILITY_LOST = "capability_lost"


# --------------------------------------------------------------------------------------------------------- events


@dataclass(frozen=True, slots=True)
class GenerationReady:
    """The reveal coordinator's readiness edge of a (new) display generation: startup, Settings return or topology
    replacement. ``activation``/``display`` are None when no visualizer owner was admitted."""

    generation: int
    activation: int | None
    display: str | None
    mode_id: str | None
    mode_capable: bool
    requested: bool


@dataclass(frozen=True, slots=True)
class GlyphPressed:
    generation: int
    activation: int
    display: str
    press_id: int
    expand: bool               # True: the expand glyph; False: the collapse glyph


@dataclass(frozen=True, slots=True)
class EnterPrepared:
    generation: int
    txn: int


@dataclass(frozen=True, slots=True)
class EnterFailed:
    generation: int
    txn: int
    reason: str = ""


@dataclass(frozen=True, slots=True)
class EnterCommitted:
    generation: int
    txn: int


@dataclass(frozen=True, slots=True)
class ExitCommitted:
    generation: int
    txn: int


@dataclass(frozen=True, slots=True)
class ModeRequested:
    """A mode change asked for through the canonical path (double-click, context menu)."""

    generation: int
    request_id: int
    mode_id: str
    mode_capable: bool


@dataclass(frozen=True, slots=True)
class ModeCycleRequested:
    """The double-click's "next mode" (operator, 7 Nov): ``candidates`` are the other enabled modes in cycle order
    after the current one, wrapping, each with its resolved capability. While expanded the cycle skips incapable
    modes and stays expanded; with no other capable mode it stays where it is. A collapsed view takes the next one."""

    generation: int
    request_id: int
    candidates: tuple[tuple[str, bool], ...]


@dataclass(frozen=True, slots=True)
class ModeActivated:
    """The owner's canonical activation completed. Activation ids only increase within a generation."""

    generation: int
    activation: int
    display: str
    mode_id: str
    mode_capable: bool


@dataclass(frozen=True, slots=True)
class ModeRejected:
    generation: int
    request_id: int


@dataclass(frozen=True, slots=True)
class TransferRequested:
    generation: int
    activation: int
    request_id: int
    target_display: str
    target_ready: bool         # the target participates and preflights (D4); False is refused before any change


@dataclass(frozen=True, slots=True)
class TransferCommitted:
    generation: int
    txn: int


@dataclass(frozen=True, slots=True)
class TransferFailed:
    generation: int
    txn: int


@dataclass(frozen=True, slots=True)
class DisplayLost:
    generation: int
    display: str


@dataclass(frozen=True, slots=True)
class EditEntered:
    generation: int
    #: Edit was entered on the view's own display (Fullscreen Edit when expanded); False: on another display.
    on_view_display: bool = True


@dataclass(frozen=True, slots=True)
class EditExited:
    generation: int
    saved: bool                # Save or Cancel: either way the committed layout is what the takeover returns to


@dataclass(frozen=True, slots=True)
class EditResolutionDeclined:
    """The Edit session's prompt for a glyph press was declined: the draft and Edit stay as they were."""

    generation: int


@dataclass(frozen=True, slots=True)
class SettingsOpened:
    generation: int


@dataclass(frozen=True, slots=True)
class OwnerRetired:
    """The Visualizer owner of this generation retired for another reason (a runtime reload, the Visualizer turned
    off, a failed construction): like Settings, the state dies with it and the intent persists."""

    generation: int
    reason: str = "owner"


@dataclass(frozen=True, slots=True)
class Shutdown:
    generation: int


Event = (
    GenerationReady | GlyphPressed | EnterPrepared | EnterFailed | EnterCommitted | ExitCommitted | ModeRequested
    | ModeCycleRequested | ModeActivated | ModeRejected | TransferRequested | TransferCommitted | TransferFailed | DisplayLost
    | EditEntered | EditExited | EditResolutionDeclined | SettingsOpened | OwnerRetired | Shutdown
)


# -------------------------------------------------------------------------------------------------------- actions


@dataclass(frozen=True, slots=True)
class BeginEnter:
    """Preflight one enter (D1 steps 1-5); answer ``EnterPrepared`` or ``EnterFailed`` with this ``txn``."""

    txn: int
    animate: bool
    origin: Origin


@dataclass(frozen=True, slots=True)
class RunEnter:
    """Run the prepared enter (D1 steps 6-7); answer ``EnterCommitted`` (or ``EnterFailed``)."""

    txn: int
    animate: bool


@dataclass(frozen=True, slots=True)
class CancelEnter:
    """Abandon this enter and restore the ordinary presentation and policy exactly."""

    txn: int


@dataclass(frozen=True, slots=True)
class BeginExit:
    """Collapse (D2); answer ``ExitCommitted``."""

    txn: int
    animate: bool
    reason: ExitReason


@dataclass(frozen=True, slots=True)
class PersistIntent:
    """One narrow canonical write of ``widgets.spotify_visualizer.expanded_display_requested``."""

    requested: bool


@dataclass(frozen=True, slots=True)
class ForwardModeRequest:
    """Hand the request to the canonical mode path (``keep_expanded``: capable -> capable while expanded)."""

    request_id: int
    mode_id: str
    keep_expanded: bool


@dataclass(frozen=True, slots=True)
class RejectModeRequest:
    request_id: int
    reason: str


@dataclass(frozen=True, slots=True)
class BeginTransfer:
    """One transaction on the existing transfer seam; answer ``TransferCommitted`` or ``TransferFailed``."""

    txn: int
    request_id: int
    source_display: str
    target_display: str
    expanded: bool             # collapse the source and expand the target inside the same transaction


@dataclass(frozen=True, slots=True)
class RollbackTransfer:
    txn: int


@dataclass(frozen=True, slots=True)
class RejectTransfer:
    request_id: int
    reason: str


@dataclass(frozen=True, slots=True)
class RequestEditResolution:
    """Ask the Edit session to resolve its draft through its own Save/Cancel path (D1 step 2, D5)."""

    press_id: int


@dataclass(frozen=True, slots=True)
class RetireTakeover:
    """Drop all transient takeover state with the generation; the persisted intent is untouched."""

    reason: str


@dataclass(frozen=True, slots=True)
class EndFullscreenEdit:
    """The expanded view cannot stay (an incapable mode became the Visualizer's): end the Fullscreen Edit session
    before the collapse, without saving its draft. No user action reaches it (an incapable request is refused under
    Fullscreen Edit); it keeps the reducer total."""


Action = (
    BeginEnter | RunEnter | CancelEnter | BeginExit | PersistIntent | ForwardModeRequest | RejectModeRequest
    | BeginTransfer | RollbackTransfer | RejectTransfer | RequestEditResolution | RetireTakeover | EndFullscreenEdit
)


# ---------------------------------------------------------------------------------------------------------- state


@dataclass(frozen=True, slots=True)
class HeldModeRequest:
    request_id: int
    mode_id: str


@dataclass(frozen=True, slots=True)
class TakeoverState:
    phase: Phase = Phase.DORMANT
    generation: int | None = None
    activation: int | None = None
    display: str | None = None
    mode_id: str | None = None
    mode_capable: bool = False
    requested: bool = False
    edit_active: bool = False
    terminal: bool = False
    #: The last transaction issued (process-monotonic); the one in flight while ``phase`` is a transaction phase.
    txn: int = 0
    txn_origin: Origin | None = None
    txn_animate: bool = True
    last_press: int = 0
    #: One latest glyph intent held to the running transition's commit edge (True: expand, False: collapse).
    deferred_expand: bool | None = None
    #: A capable -> incapable mode request held until the collapse commits.
    held_mode_request: HeldModeRequest | None = None
    #: The held request once forwarded: its rejection re-expands the still-active capable mode.
    awaiting_mode_request: int | None = None
    #: An expand press waiting on the Edit session's resolution.
    edit_expand_press: int | None = None
    #: Edit was entered on a resting expanded view (Fullscreen Edit, M3c): the view stays expanded and Edit edits the
    #: full-display overlays only. Only ever True with ``edit_active`` and while EXPANDED (or retiring).
    edit_fullscreen: bool = False
    #: Edit was entered on another display while the view rested EXPANDED (plan 1B.1): an ordinary Edit of the other
    #: displays; the view stays expanded outside the session. Only ever True with ``edit_active`` and while EXPANDED
    #: (or retiring); never together with ``edit_fullscreen``.
    edit_elsewhere: bool = False
    #: A collapse press under Fullscreen Edit (or an Edit beside the view), waiting on the session's own Save/Cancel.
    edit_collapse_press: int | None = None
    transfer_target: str | None = None
    transfer_resume_expanded: bool = False
    #: An incapable mode activated while the view was still expanded (or entering, exiting, transferring): the intent
    #: is cleared at the edge where nothing is drawn expanded any more.
    clear_intent_at_rest: bool = False

    @property
    def edit_keeps_view(self) -> bool:
        """Edit is open while the view stays expanded: Fullscreen Edit, or an Edit beside the view (plan 1B.1)."""
        return self.edit_fullscreen or self.edit_elsewhere

    @property
    def eligible(self) -> bool:
        """Expansion could be effective now (the fifth predicate, before intent). Fullscreen Edit and an Edit beside
        the view keep it."""
        return (self.activation is not None and self.display is not None and self.mode_capable
                and (not self.edit_active or self.edit_keeps_view))


@dataclass(frozen=True, slots=True)
class Step:
    state: TakeoverState
    actions: tuple[Action, ...]
    outcome: Outcome
    reason: str = ""


def initial_state() -> TakeoverState:
    return TakeoverState()


# -------------------------------------------------------------------------------------------------------- helpers


def _unchanged(state: TakeoverState, outcome: Outcome, reason: str) -> Step:
    return Step(state, (), outcome, reason)


def _applied(state: TakeoverState, *actions: Action) -> Step:
    return Step(state, tuple(actions), Outcome.APPLIED)


def _resting_phase(state: TakeoverState) -> Phase:
    if state.activation is None or state.display is None or not state.mode_capable:
        return Phase.DORMANT
    return Phase.ORDINARY


def _rest(state: TakeoverState) -> TakeoverState:
    """Settle to DORMANT/ORDINARY with nothing in flight."""
    return replace(state, phase=_resting_phase(state), txn_origin=None, deferred_expand=None,
                   transfer_target=None, transfer_resume_expanded=False)


def _begin_enter(state: TakeoverState, origin: Origin, animate: bool) -> tuple[TakeoverState, BeginEnter]:
    txn = state.txn + 1
    state = replace(state, phase=Phase.ENTER_PENDING, txn=txn, txn_origin=origin, txn_animate=animate,
                    deferred_expand=None)
    return state, BeginEnter(txn, animate, origin)


def _begin_exit(state: TakeoverState, reason: ExitReason, animate: bool = True) -> tuple[TakeoverState, BeginExit]:
    txn = state.txn + 1
    origin = Origin.USER if reason is ExitReason.USER else None
    state = replace(state, phase=Phase.EXITING, txn=txn, txn_origin=origin, txn_animate=animate,
                    deferred_expand=None)
    return state, BeginExit(txn, animate, reason)


def _user_collapse(state: TakeoverState) -> tuple[TakeoverState, tuple[Action, ...]]:
    """Accept the user's collapse: the intent is written False now (collapse is always attainable)."""
    if state.requested:
        return replace(state, requested=False, clear_intent_at_rest=False), (PersistIntent(False),)
    return replace(state, clear_intent_at_rest=False), ()


def _clear_intent(state: TakeoverState) -> tuple[TakeoverState, tuple[Action, ...]]:
    """An incapable mode is the Visualizer's and nothing is drawn expanded: drop the intent (one write)."""
    if state.requested:
        return replace(state, requested=False, clear_intent_at_rest=False), (PersistIntent(False),)
    return replace(state, clear_intent_at_rest=False), ()


def _flush_cleared_intent(state: TakeoverState) -> tuple[TakeoverState, tuple[Action, ...]]:
    """At a collapsed edge, perform the clear an incapable activation deferred while the view was expanded."""
    if state.clear_intent_at_rest:
        return _clear_intent(state)
    return state, ()


def _settle_resting(state: TakeoverState, *, animate: bool) -> Step:
    """Rest, then re-apply the intent once if it is eligible (a bounded edge, never a retry loop)."""
    state = _rest(state)
    if state.phase is Phase.ORDINARY and state.requested and state.eligible:
        state, begin = _begin_enter(state, Origin.RESTORE, animate)
        return _applied(state, begin)
    return _applied(state)


def _after_expanded(state: TakeoverState, *actions: Action) -> Step:
    """EXPANDED just became true: honour anything that arrived while the transaction ran."""
    if state.deferred_expand is False:
        # The user's own collapse wins over any automatic one, so it is the one that writes the intent.
        state, writes = _user_collapse(state)
        state, exit_ = _begin_exit(state, ExitReason.USER)
        return _applied(state, *actions, *writes, exit_)
    if state.edit_active and not state.edit_keeps_view:
        # An ordinary Edit (begun while the enter or transfer ran) edits the ordinary layout: collapse first.
        state, exit_ = _begin_exit(state, ExitReason.EDIT)
        return _applied(state, *actions, exit_)
    if not state.mode_capable:
        state, exit_ = _begin_exit(state, ExitReason.CAPABILITY_LOST)
        return _applied(state, *actions, exit_)
    return _applied(replace(state, txn_origin=None, deferred_expand=None), *actions)


def _end_fullscreen_edit(state: TakeoverState) -> tuple[TakeoverState, tuple[Action, ...]]:
    """Drop a Fullscreen Edit whose expanded view cannot stay (never on a user action). An Edit beside the view
    continues as an ordinary Edit: its session never held the view."""
    if state.edit_elsewhere:
        return replace(state, edit_elsewhere=False, edit_collapse_press=None), ()
    if not state.edit_fullscreen:
        return state, ()
    return (replace(state, edit_active=False, edit_fullscreen=False, edit_expand_press=None, edit_collapse_press=None),
            (EndFullscreenEdit(),))


# -------------------------------------------------------------------------------------------------------- reducer


def reduce(state: TakeoverState, event: Event) -> Step:
    """Apply one event. Pure: returns the next state, the actions to perform in order, and the outcome."""

    if state.terminal:
        return _unchanged(state, Outcome.STALE, "process shutting down")
    if isinstance(event, GenerationReady):
        return _generation_ready(state, event)
    if state.generation is None or event.generation != state.generation:
        return _unchanged(state, Outcome.STALE, "not the current generation")
    if state.phase is Phase.RETIRING:
        return _unchanged(state, Outcome.STALE, "generation retiring")

    handler = _HANDLERS.get(type(event))
    if handler is None:
        raise TypeError(f"unknown takeover event: {event!r}")
    return handler(state, event)


def _generation_ready(state: TakeoverState, event: GenerationReady) -> Step:
    if state.generation is not None and event.generation <= state.generation:
        return _unchanged(state, Outcome.STALE, "generation not newer")
    has_owner = event.activation is not None and event.display is not None
    fresh = TakeoverState(
        generation=event.generation,
        activation=event.activation if has_owner else None,
        display=event.display if has_owner else None,
        mode_id=event.mode_id,
        mode_capable=bool(event.mode_capable) and has_owner,
        requested=bool(event.requested),
        txn=state.txn,
    )
    if has_owner and not fresh.mode_capable and fresh.requested:
        # The generation shows an incapable mode (one chosen in Settings, or the capable one is no longer enabled):
        # the intent does not survive the mode, so a later capable mode starts ordinary.
        fresh, writes = _clear_intent(fresh)
        return _applied(_rest(fresh), *writes)
    # Startup / Settings return / topology replacement: one evaluation, before any retained root is exposed, so the
    # restore is not animated (no ordinary-card flash, no double fade).
    return _settle_resting(fresh, animate=False)


def _glyph(state: TakeoverState, event: GlyphPressed) -> Step:
    if state.activation is None or event.activation != state.activation or event.display != state.display:
        return _unchanged(state, Outcome.STALE, "glyph from another activation or display")
    if event.press_id <= state.last_press:
        return _unchanged(state, Outcome.DUPLICATE, "press already handled")
    state = replace(state, last_press=event.press_id)
    phase = state.phase

    if event.expand:
        if not state.mode_capable:
            return _unchanged(state, Outcome.REJECTED, "mode not capable")
        if state.edit_active and not state.edit_keeps_view:
            if state.edit_expand_press is not None:
                return _unchanged(state, Outcome.DUPLICATE, "Edit resolution already requested")
            state = replace(state, edit_expand_press=event.press_id)
            return _applied(state, RequestEditResolution(event.press_id))
        if phase is Phase.ORDINARY:
            state, begin = _begin_enter(state, Origin.USER, True)
            return _applied(state, begin)
        if phase is Phase.ENTERING and state.deferred_expand is False:
            return _applied(replace(state, deferred_expand=None))
        if phase in (Phase.ENTER_PENDING, Phase.ENTERING, Phase.EXPANDED):
            return _unchanged(state, Outcome.DUPLICATE, "already expanding or expanded")
        if phase is Phase.EXITING:
            if state.deferred_expand is True:
                return _unchanged(state, Outcome.DUPLICATE, "expand already held")
            return _applied(replace(state, deferred_expand=True))
        return _unchanged(state, Outcome.REJECTED, f"busy: {phase.value}")

    # Collapse.
    if state.edit_keeps_view:
        # Fullscreen Edit (or an Edit beside the view): the collapse waits for the Edit session's own Save/Cancel;
        # nothing is discarded or saved implicitly (a declined resolution drops the press).
        if state.edit_collapse_press is not None:
            return _unchanged(state, Outcome.DUPLICATE, "Edit resolution already requested")
        state = replace(state, edit_collapse_press=event.press_id)
        return _applied(state, RequestEditResolution(event.press_id))
    if phase in (Phase.DORMANT, Phase.ORDINARY):
        return _unchanged(state, Outcome.DUPLICATE, "already collapsed")
    if phase is Phase.EXITING:
        if state.deferred_expand is True:
            return _applied(replace(state, deferred_expand=None))
        return _unchanged(state, Outcome.DUPLICATE, "already collapsing")
    if phase is Phase.ENTER_PENDING:
        # Nothing visible has changed yet: abandon the preflight.
        txn = state.txn
        state, writes = _user_collapse(state)
        return _applied(_rest(state), CancelEnter(txn), *writes)
    if phase is Phase.ENTERING:
        if state.deferred_expand is False:
            return _unchanged(state, Outcome.DUPLICATE, "collapse already held")
        return _applied(replace(state, deferred_expand=False))
    if phase is Phase.EXPANDED:
        state, writes = _user_collapse(state)
        state, exit_ = _begin_exit(state, ExitReason.USER)
        return _applied(state, *writes, exit_)
    return _unchanged(state, Outcome.REJECTED, f"busy: {phase.value}")


def _enter_prepared(state: TakeoverState, event: EnterPrepared) -> Step:
    if state.phase is not Phase.ENTER_PENDING or event.txn != state.txn:
        return _unchanged(state, Outcome.STALE, "no such enter pending")
    return _applied(replace(state, phase=Phase.ENTERING), RunEnter(state.txn, state.txn_animate))


def _enter_failed(state: TakeoverState, event: EnterFailed) -> Step:
    if state.phase not in (Phase.ENTER_PENDING, Phase.ENTERING) or event.txn != state.txn:
        return _unchanged(state, Outcome.STALE, "no such enter in flight")
    # Restore ordinary exactly; the intent is untouched (unless an incapable mode activated meanwhile) and nothing
    # retries until a new edge.
    txn = state.txn
    state, writes = _flush_cleared_intent(_rest(state))
    return _applied(state, CancelEnter(txn), *writes)


def _enter_committed(state: TakeoverState, event: EnterCommitted) -> Step:
    if state.phase is not Phase.ENTERING or event.txn != state.txn:
        return _unchanged(state, Outcome.STALE, "no such enter running")
    expanded = replace(state, phase=Phase.EXPANDED)
    writes: tuple[Action, ...] = ()
    if (state.txn_origin is Origin.USER and state.deferred_expand is not False and not state.requested
            and state.mode_capable):
        # The user's expand succeeded on a capable mode: the only point the intent is written True (D1 step 8).
        expanded = replace(expanded, requested=True)
        writes = (PersistIntent(True),)
    return _after_expanded(expanded, *writes)


def _exit_committed(state: TakeoverState, event: ExitCommitted) -> Step:
    if state.phase is not Phase.EXITING or event.txn != state.txn:
        return _unchanged(state, Outcome.STALE, "no such exit running")
    held = state.held_mode_request
    deferred = state.deferred_expand
    rested, writes = _flush_cleared_intent(_rest(replace(state, held_mode_request=None)))
    if held is not None:
        # Capable -> incapable: the mode changes only after the collapse has committed (D3); the intent is cleared
        # when that mode activates (a rejection leaves the capable mode, and the intent, in place).
        rested = replace(rested, awaiting_mode_request=held.request_id)
        return _applied(rested, *writes, ForwardModeRequest(held.request_id, held.mode_id, False))
    if deferred is True and rested.phase is Phase.ORDINARY and rested.eligible:
        rested, begin = _begin_enter(rested, Origin.USER, True)
        return _applied(rested, *writes, begin)
    step = _settle_resting(rested, animate=True)
    return _applied(step.state, *writes, *step.actions)


def _mode_requested(state: TakeoverState, event: ModeRequested) -> Step:
    phase = state.phase
    if phase in (Phase.DORMANT, Phase.ORDINARY):
        return _applied(state, ForwardModeRequest(event.request_id, event.mode_id, False))
    if phase is Phase.EXPANDED:
        if event.mode_capable:
            return _applied(state, ForwardModeRequest(event.request_id, event.mode_id, True))
        if state.edit_keeps_view:
            # Collapsing would end Fullscreen Edit under its draft, or return the view's display to a layout the Edit
            # beside it does not hold: Save or Cancel first.
            reason = "Fullscreen Edit open" if state.edit_fullscreen else "Edit open on another display"
            return Step(state, (RejectModeRequest(event.request_id, reason),), Outcome.REJECTED, reason)
        state = replace(state, held_mode_request=HeldModeRequest(event.request_id, event.mode_id))
        state, exit_ = _begin_exit(state, ExitReason.MODE_INCAPABLE)
        return _applied(state, exit_)
    return Step(state, (RejectModeRequest(event.request_id, f"busy: {phase.value}"),), Outcome.REJECTED,
                f"busy: {phase.value}")


def _mode_cycle_requested(state: TakeoverState, event: ModeCycleRequested) -> Step:
    phase = state.phase
    candidates = tuple((str(mode), bool(capable)) for mode, capable in event.candidates)
    if phase in (Phase.DORMANT, Phase.ORDINARY):
        if not candidates:
            reason = "no other enabled mode"
            return Step(state, (RejectModeRequest(event.request_id, reason),), Outcome.REJECTED, reason)
        return _applied(state, ForwardModeRequest(event.request_id, candidates[0][0], False))
    if phase is Phase.EXPANDED:
        # Skip enabled modes that cannot be expanded; stay expanded on the next capable one (operator, 7 Nov).
        target = next((mode for mode, capable in candidates if capable), None)
        if target is None:
            reason = "no other enabled capable mode"
            return Step(state, (RejectModeRequest(event.request_id, reason),), Outcome.REJECTED, reason)
        return _applied(state, ForwardModeRequest(event.request_id, target, True))
    reason = f"busy: {phase.value}"
    return Step(state, (RejectModeRequest(event.request_id, reason),), Outcome.REJECTED, reason)


def _mode_activated(state: TakeoverState, event: ModeActivated) -> Step:
    if state.activation is not None and event.activation <= state.activation:
        return _unchanged(state, Outcome.STALE, "activation not newer")
    state = replace(state, activation=event.activation, display=event.display, mode_id=event.mode_id,
                    mode_capable=bool(event.mode_capable), awaiting_mode_request=None)
    phase = state.phase
    incapable_with_intent = not state.mode_capable and state.requested
    if phase in (Phase.DORMANT, Phase.ORDINARY):
        # Nothing is drawn expanded: an incapable mode clears a held intent now, so a later capable mode starts
        # ordinary (a mode switch never re-expands). A capable -> capable switch keeps a held intent.
        state, writes = _clear_intent(state) if incapable_with_intent else (state, ())
        step = _settle_resting(state, animate=True)
        return _applied(step.state, *writes, *step.actions)
    if phase is Phase.ENTER_PENDING:
        # The preflight belonged to the previous activation: abandon it, then re-evaluate for this one.
        cancelled = CancelEnter(state.txn)
        state, writes = _clear_intent(state) if incapable_with_intent else (state, ())
        step = _settle_resting(state, animate=state.txn_animate)
        return _applied(step.state, cancelled, *writes, *step.actions)
    if incapable_with_intent:
        # Still drawn expanded (or entering, exiting, moving): clear once the collapse has committed.
        state = replace(state, clear_intent_at_rest=True)
    if phase is Phase.EXPANDED and not state.mode_capable:
        state, ends = _end_fullscreen_edit(state)
        state, exit_ = _begin_exit(state, ExitReason.CAPABILITY_LOST)
        return _applied(state, *ends, exit_)
    # ENTERING / EXITING / TRANSFER_PENDING: their commit edges check the new facts.
    return _applied(state)


def _mode_rejected(state: TakeoverState, event: ModeRejected) -> Step:
    if event.request_id != state.awaiting_mode_request:
        return _unchanged(state, Outcome.IGNORED, "not a takeover-held request")
    state = replace(state, awaiting_mode_request=None)
    if state.phase is Phase.ORDINARY and state.requested and state.eligible:
        # The collapse was only for the incapable target; the capable source mode stays: re-expand it (D3).
        state, begin = _begin_enter(state, Origin.ROLLBACK, True)
        return _applied(state, begin)
    return _applied(state)


def _transfer_requested(state: TakeoverState, event: TransferRequested) -> Step:
    if state.activation is None or event.activation != state.activation:
        return _unchanged(state, Outcome.STALE, "transfer from another activation")
    if event.target_display == state.display:
        return _unchanged(state, Outcome.DUPLICATE, "already on that display")
    if state.edit_keeps_view:
        # A move would end Fullscreen Edit under its draft (or move the view under an Edit beside it): Save or Cancel
        # first.
        reason = "Fullscreen Edit open" if state.edit_fullscreen else "Edit open on another display"
        return Step(state, (RejectTransfer(event.request_id, reason),), Outcome.REJECTED, reason)
    if state.phase not in (Phase.DORMANT, Phase.ORDINARY, Phase.EXPANDED):
        reason = f"busy: {state.phase.value}"
        return Step(state, (RejectTransfer(event.request_id, reason),), Outcome.REJECTED, reason)
    if not event.target_ready:
        # Never strand the visualizer: the source stays exactly as it is (D4).
        return Step(state, (RejectTransfer(event.request_id, "target not ready"),), Outcome.REJECTED,
                    "target not ready")
    expanded = state.phase is Phase.EXPANDED
    txn = state.txn + 1
    source = state.display
    state = replace(state, phase=Phase.TRANSFER_PENDING, txn=txn, txn_origin=None,
                    transfer_target=event.target_display, transfer_resume_expanded=expanded)
    return _applied(state, BeginTransfer(txn, event.request_id, str(source), event.target_display, expanded))


def _transfer_rollback(state: TakeoverState) -> Step:
    txn = state.txn
    if state.transfer_resume_expanded:
        restored = replace(state, phase=Phase.EXPANDED, transfer_target=None, transfer_resume_expanded=False)
        step = _after_expanded(restored)
        return _applied(step.state, RollbackTransfer(txn), *step.actions)
    state, writes = _flush_cleared_intent(_rest(state))
    return _applied(state, RollbackTransfer(txn), *writes)


def _transfer_committed(state: TakeoverState, event: TransferCommitted) -> Step:
    if state.phase is not Phase.TRANSFER_PENDING or event.txn != state.txn:
        return _unchanged(state, Outcome.STALE, "no such transfer running")
    moved = replace(state, display=state.transfer_target, transfer_target=None)
    if state.transfer_resume_expanded:
        return _after_expanded(replace(moved, phase=Phase.EXPANDED, transfer_resume_expanded=False))
    moved, writes = _flush_cleared_intent(moved)
    step = _settle_resting(moved, animate=True)
    return _applied(step.state, *writes, *step.actions)


def _transfer_failed(state: TakeoverState, event: TransferFailed) -> Step:
    if state.phase is not Phase.TRANSFER_PENDING or event.txn != state.txn:
        return _unchanged(state, Outcome.STALE, "no such transfer running")
    return _transfer_rollback(state)


def _display_lost(state: TakeoverState, event: DisplayLost) -> Step:
    if state.display is not None and event.display == state.display:
        # The owning display is gone: the generation retires under the existing barriers; the intent survives and
        # the replacement generation re-evaluates it at its readiness edge.
        return _applied(replace(state, phase=Phase.RETIRING), RetireTakeover("topology"))
    if state.phase is Phase.TRANSFER_PENDING and event.display == state.transfer_target:
        return _transfer_rollback(state)
    return _unchanged(state, Outcome.IGNORED, "not the owning or target display")


def _edit_entered(state: TakeoverState, event: EditEntered) -> Step:
    if state.edit_active:
        return _unchanged(state, Outcome.DUPLICATE, "Edit already active")
    phase = state.phase
    if phase is Phase.EXPANDED:
        if event.on_view_display:
            # Fullscreen Edit (operator, 8 Nov; M3c): the view stays expanded and Edit edits the full-display
            # overlays only. No collapse transaction; the intent is untouched.
            return _applied(replace(state, edit_active=True, edit_fullscreen=True))
        # An Edit beside the view (operator, 11 Nov; plan 1B.1): Edit edits the display it was entered on; the view
        # stays expanded and running, outside the session. No collapse transaction; the intent is untouched.
        return _applied(replace(state, edit_active=True, edit_elsewhere=True))
    state = replace(state, edit_active=True)
    if phase is Phase.ENTER_PENDING:
        txn = state.txn
        return _applied(_rest(state), CancelEnter(txn))
    # An ordinary Edit. DORMANT / ORDINARY need nothing; ENTERING / TRANSFER_PENDING collapse at their commit edge;
    # EXITING continues.
    return _applied(replace(state, deferred_expand=None if phase is Phase.EXITING else state.deferred_expand))


def _edit_exited(state: TakeoverState, event: EditExited) -> Step:
    if not state.edit_active:
        return _unchanged(state, Outcome.DUPLICATE, "Edit not active")
    pending = state.edit_expand_press
    collapse = state.edit_collapse_press
    kept_view = state.edit_keeps_view
    state = replace(state, edit_active=False, edit_fullscreen=False, edit_elsewhere=False, edit_expand_press=None,
                    edit_collapse_press=None)
    if kept_view:
        # Save or Cancel ended Fullscreen Edit (or an Edit beside the view): the view stays expanded. A collapse press
        # that waited for the session's resolution is the user's collapse now.
        if collapse is not None and state.phase is Phase.EXPANDED:
            state, writes = _user_collapse(state)
            state, exit_ = _begin_exit(state, ExitReason.USER)
            return _applied(state, *writes, exit_)
        return _applied(state)
    if state.phase in (Phase.DORMANT, Phase.ORDINARY):
        if pending is not None and state.eligible:
            state, begin = _begin_enter(_rest(state), Origin.USER, True)
            return _applied(state, begin)
        # Save or Cancel: the committed layout is restored; expansion returns only now, after the editor exited.
        return _settle_resting(state, animate=True)
    if pending is not None and state.phase is Phase.EXITING:
        state = replace(state, deferred_expand=True)
    return _applied(state)


def _edit_resolution_declined(state: TakeoverState, event: EditResolutionDeclined) -> Step:
    if state.edit_expand_press is None and state.edit_collapse_press is None:
        return _unchanged(state, Outcome.IGNORED, "no Edit resolution pending")
    return _applied(replace(state, edit_expand_press=None, edit_collapse_press=None))


def _settings_opened(state: TakeoverState, event: SettingsOpened) -> Step:
    # Today's teardown: the intent persists, the state dies with the generation.
    return _applied(replace(state, phase=Phase.RETIRING), RetireTakeover("settings"))


def _owner_retired(state: TakeoverState, event: OwnerRetired) -> Step:
    return _applied(replace(state, phase=Phase.RETIRING), RetireTakeover(str(event.reason) or "owner"))


def _shutdown(state: TakeoverState, event: Shutdown) -> Step:
    return _applied(replace(state, phase=Phase.RETIRING, terminal=True), RetireTakeover("shutdown"))


_HANDLERS = {
    GlyphPressed: _glyph,
    EnterPrepared: _enter_prepared,
    EnterFailed: _enter_failed,
    EnterCommitted: _enter_committed,
    ExitCommitted: _exit_committed,
    ModeRequested: _mode_requested,
    ModeCycleRequested: _mode_cycle_requested,
    ModeActivated: _mode_activated,
    ModeRejected: _mode_rejected,
    TransferRequested: _transfer_requested,
    TransferCommitted: _transfer_committed,
    TransferFailed: _transfer_failed,
    DisplayLost: _display_lost,
    EditEntered: _edit_entered,
    EditExited: _edit_exited,
    EditResolutionDeclined: _edit_resolution_declined,
    SettingsOpened: _settings_opened,
    OwnerRetired: _owner_retired,
    Shutdown: _shutdown,
}


__all__ = [
    "Action", "BeginEnter", "BeginExit", "BeginTransfer", "CancelEnter", "DisplayLost", "EditEntered",
    "EditExited", "EditResolutionDeclined", "EndFullscreenEdit", "EnterCommitted", "EnterFailed", "EnterPrepared", "Event",
    "ExitCommitted", "ExitReason", "ForwardModeRequest", "GenerationReady", "GlyphPressed", "HeldModeRequest",
    "ModeActivated", "ModeCycleRequested", "ModeRejected", "ModeRequested", "Origin", "Outcome", "OwnerRetired", "PersistIntent", "Phase",
    "RESTING_PHASES", "RejectModeRequest", "RejectTransfer", "RequestEditResolution", "RetireTakeover",
    "RollbackTransfer", "RunEnter", "SettingsOpened", "Shutdown", "Step", "TRANSACTION_PHASES", "TakeoverState",
    "TransferCommitted", "TransferFailed", "TransferRequested", "initial_state", "reduce",
]
