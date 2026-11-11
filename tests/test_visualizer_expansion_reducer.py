"""Expanded Visualizer M1: the pure takeover reducer (plan 01 §D, Gate 1).

Table-driven event sequences pin each transaction's trace (outcome, phase, actions per event); an exhaustive
walk over every short event sequence checks the reducer's invariants from every reachable state; and an
accept/reject permutation driver answers every action the way the M2 coordinator will (immediately or after a
disturbance) and checks the result is always coherent. All fixtures are synthetic: mode ids and displays are
labels, capability is the event's fact, nothing reads Settings or presets.
"""
from __future__ import annotations

from collections import deque
from dataclasses import replace
from itertools import product

import pytest

import core.expanded_visualizer_takeover as tk
from core.expanded_visualizer_takeover import (
    BeginEnter, BeginExit, BeginTransfer, CancelEnter, DisplayLost, EditEntered, EditExited,
    EditResolutionDeclined, EndFullscreenEdit, EnterCommitted, EnterFailed, EnterPrepared, ExitCommitted, ForwardModeRequest,
    GenerationReady, GlyphPressed, ModeActivated, ModeCycleRequested, ModeRejected, ModeRequested, Outcome,
    OwnerRetired, PersistIntent,
    Phase,
    RejectModeRequest, RejectTransfer, RetireTakeover, RollbackTransfer, RunEnter,
    SettingsOpened, Shutdown, TransferCommitted, TransferFailed, TransferRequested, reduce,
)

GEN = 1
ACT = 1
A, B = "display-A", "display-B"
CAPABLE, INCAPABLE = "capable-mode", "incapable-mode"


# ---------------------------------------------------------------------------------------------- trace helpers


def _fmt(action) -> str:
    if isinstance(action, BeginEnter):
        return f"BeginEnter[{action.origin.value},{'anim' if action.animate else 'still'}]"
    if isinstance(action, BeginExit):
        return f"BeginExit[{action.reason.value}]"
    if isinstance(action, PersistIntent):
        return f"Persist[{action.requested}]"
    if isinstance(action, ForwardModeRequest):
        return f"Forward[{action.mode_id},{'keep' if action.keep_expanded else 'plain'}]"
    if isinstance(action, BeginTransfer):
        return f"BeginTransfer[{action.target_display},{'expanded' if action.expanded else 'ordinary'}]"
    if isinstance(action, RetireTakeover):
        return f"Retire[{action.reason}]"
    return type(action).__name__


def _line(step: tk.Step) -> str:
    acts = ",".join(_fmt(a) for a in step.actions)
    return f"{step.outcome.value} {step.state.phase.value}" + (f" {acts}" if acts else "")


EventSpec = object  # an event, or a callable(state) -> event (completions name the transaction in flight)


def _run(events: list[EventSpec], state: tk.TakeoverState | None = None):
    state = state or tk.initial_state()
    steps = []
    for spec in events:
        event = spec(state) if callable(spec) else spec
        step = reduce(state, event)
        steps.append(step)
        state = step.state
    return state, steps


def ready(*, requested=False, capable=True, gen=GEN, act=ACT, disp=A, mode=None):
    return GenerationReady(gen, act, disp, mode or (CAPABLE if capable else INCAPABLE), capable, requested)


def glyph(press, expand, *, gen=GEN, act=ACT, disp=A):
    return GlyphPressed(gen, act, disp, press, expand)


def prepared(s):
    return EnterPrepared(s.generation, s.txn)


def committed(s):
    return EnterCommitted(s.generation, s.txn)


def failed(s):
    return EnterFailed(s.generation, s.txn, "preflight")


def exited(s):
    return ExitCommitted(s.generation, s.txn)


def moved(s):
    return TransferCommitted(s.generation, s.txn)


def move_failed(s):
    return TransferFailed(s.generation, s.txn)


def activated(mode, capable, *, act, disp=A):
    return lambda s: ModeActivated(s.generation, act, disp, mode, capable)


EXPAND_BY_USER = [ready(), glyph(1, True), prepared, committed]
EXPANDED_TRACE = [
    "applied ordinary",
    "applied enter_pending BeginEnter[user,anim]",
    "applied entering RunEnter",
    "applied expanded Persist[True]",
]


# ------------------------------------------------------------------------------------------- table of scenarios

SCENARIOS: list[tuple[str, list[EventSpec], list[str]]] = [
    ("startup without intent rests ordinary", [ready()], ["applied ordinary"]),
    ("startup restores intent once, unanimated, never writes it",
     [ready(requested=True), prepared, committed],
     ["applied enter_pending BeginEnter[restore,still]", "applied entering RunEnter", "applied expanded"]),
    ("startup on an incapable mode (one chosen in Settings) clears the intent and stays dormant",
     [ready(requested=True, capable=False)], ["applied dormant Persist[False]"]),
    ("startup on an incapable mode without intent writes nothing",
     [ready(capable=False)], ["applied dormant"]),
    ("startup with no visualizer owner is dormant",
     [ready(requested=True, act=None, disp=None)], ["applied dormant"]),
    ("user expand persists only when it commits", EXPAND_BY_USER, EXPANDED_TRACE),
    ("a repeated press id is a duplicate",
     [ready(), glyph(1, True), glyph(1, True)],
     ["applied ordinary", "applied enter_pending BeginEnter[user,anim]", "duplicate enter_pending"]),
    ("a re-delivered press id is a duplicate even for the opposite glyph",
     [*EXPAND_BY_USER, glyph(1, False)], [*EXPANDED_TRACE, "duplicate expanded"]),
    ("a second expand press is coalesced",
     [*EXPAND_BY_USER, glyph(2, True)], [*EXPANDED_TRACE, "duplicate expanded"]),
    ("a glyph from an older generation is stale",
     [ready(gen=2), glyph(1, True, gen=1)], ["applied ordinary", "stale ordinary"]),
    ("a glyph from an older visualizer activation is stale",
     [ready(act=2), glyph(1, True, act=1)], ["applied ordinary", "stale ordinary"]),
    ("a glyph from another display is stale",
     [ready(), glyph(1, True, disp=B)], ["applied ordinary", "stale ordinary"]),
    ("completions for another transaction are stale",
     [ready(), glyph(1, True), lambda s: EnterPrepared(GEN, s.txn + 1), committed, prepared],
     ["applied ordinary", "applied enter_pending BeginEnter[user,anim]", "stale enter_pending",
      "stale enter_pending", "applied entering RunEnter"]),
    ("a failed user enter restores ordinary, keeps the intent off and does not retry",
     [ready(), glyph(1, True), prepared, failed],
     ["applied ordinary", "applied enter_pending BeginEnter[user,anim]", "applied entering RunEnter",
      "applied ordinary CancelEnter"]),
    ("a failed restore keeps the persisted intent",
     [ready(requested=True), failed],
     ["applied enter_pending BeginEnter[restore,still]", "applied ordinary CancelEnter"]),
    ("user collapse writes the intent off, then commits ordinary",
     [*EXPAND_BY_USER, glyph(2, False), exited],
     [*EXPANDED_TRACE, "applied exiting Persist[False],BeginExit[user]", "applied ordinary"]),
    ("collapse while a restore is pending cancels it and writes the intent off",
     [ready(requested=True), glyph(1, False)],
     ["applied enter_pending BeginEnter[restore,still]", "applied ordinary CancelEnter,Persist[False]"]),
    ("collapse while entering is held to the commit edge (one latest intent)",
     [ready(), glyph(1, True), prepared, glyph(2, False), glyph(3, False), committed, exited],
     ["applied ordinary", "applied enter_pending BeginEnter[user,anim]", "applied entering RunEnter",
      "applied entering", "duplicate entering", "applied exiting BeginExit[user]", "applied ordinary"]),
    ("collapse then expand while entering: latest wins, the expand persists",
     [ready(), glyph(1, True), prepared, glyph(2, False), glyph(3, True), committed],
     ["applied ordinary", "applied enter_pending BeginEnter[user,anim]", "applied entering RunEnter",
      "applied entering", "applied entering", "applied expanded Persist[True]"]),
    ("expand while exiting re-enters at the exit commit",
     [*EXPAND_BY_USER, glyph(2, False), glyph(3, True), exited],
     [*EXPANDED_TRACE, "applied exiting Persist[False],BeginExit[user]", "applied exiting",
      "applied enter_pending BeginEnter[user,anim]"]),
    ("Fullscreen Edit: Edit on an expanded view stays expanded, with no collapse transaction and no write",
     [*EXPAND_BY_USER, EditEntered(GEN)], [*EXPANDED_TRACE, "applied expanded"]),
    ("Fullscreen Edit Save and Cancel leave the view expanded and write nothing",
     [*EXPAND_BY_USER, EditEntered(GEN), EditExited(GEN, saved=True), EditEntered(GEN),
      EditExited(GEN, saved=False)],
     [*EXPANDED_TRACE, "applied expanded", "applied expanded", "applied expanded", "applied expanded"]),
    ("a collapse press under Fullscreen Edit asks the session to resolve its draft; declined, nothing collapses",
     [*EXPAND_BY_USER, EditEntered(GEN), glyph(2, False), glyph(3, False), EditResolutionDeclined(GEN),
      EditExited(GEN, saved=False)],
     [*EXPANDED_TRACE, "applied expanded", "applied expanded RequestEditResolution", "duplicate expanded",
      "applied expanded", "applied expanded"]),
    ("a collapse press that waited for the session's own Save is the user's collapse after it",
     [*EXPAND_BY_USER, EditEntered(GEN), glyph(2, False), EditExited(GEN, saved=True), exited],
     [*EXPANDED_TRACE, "applied expanded", "applied expanded RequestEditResolution",
      "applied exiting Persist[False],BeginExit[user]", "applied ordinary"]),
    ("an expand press under Fullscreen Edit is a duplicate (already expanded)",
     [*EXPAND_BY_USER, EditEntered(GEN), glyph(2, True)],
     [*EXPANDED_TRACE, "applied expanded", "duplicate expanded"]),
    ("an incapable mode under Fullscreen Edit is refused (Save or Cancel first); a capable one stays expanded",
     [*EXPAND_BY_USER, EditEntered(GEN), ModeRequested(GEN, 7, INCAPABLE, False),
      ModeRequested(GEN, 8, "capable-2", True), activated("capable-2", True, act=2)],
     [*EXPANDED_TRACE, "applied expanded", "rejected expanded RejectModeRequest",
      "applied expanded Forward[capable-2,keep]", "applied expanded"]),
    ("a cycle under Fullscreen Edit stays on capable modes and stays expanded",
     [*EXPAND_BY_USER, EditEntered(GEN), ModeCycleRequested(GEN, 7, ((INCAPABLE, False), ("capable-2", True)))],
     [*EXPANDED_TRACE, "applied expanded", "applied expanded Forward[capable-2,keep]"]),
    ("a transfer under Fullscreen Edit is refused before any change",
     [*EXPAND_BY_USER, EditEntered(GEN), TransferRequested(GEN, ACT, 5, B, True)],
     [*EXPANDED_TRACE, "applied expanded", "rejected expanded RejectTransfer"]),
    ("an incapable activation under Fullscreen Edit ends the session with its view, then collapses",
     [*EXPAND_BY_USER, EditEntered(GEN), activated(INCAPABLE, False, act=2), exited, EditExited(GEN, saved=False)],
     [*EXPANDED_TRACE, "applied expanded", "applied exiting EndFullscreenEdit,BeginExit[capability_lost]",
      "applied dormant Persist[False]", "duplicate dormant"]),
    ("topology loss under Fullscreen Edit retires the state, not the intent; the replacement restores it",
     [*EXPAND_BY_USER, EditEntered(GEN), DisplayLost(GEN, A), ready(requested=True, gen=2)],
     [*EXPANDED_TRACE, "applied expanded", "applied retiring Retire[topology]",
      "applied enter_pending BeginEnter[restore,still]"]),
    ("Settings under Fullscreen Edit retires the state, not the intent",
     [*EXPAND_BY_USER, EditEntered(GEN), SettingsOpened(GEN), ready(requested=True, gen=2)],
     [*EXPANDED_TRACE, "applied expanded", "applied retiring Retire[settings]",
      "applied enter_pending BeginEnter[restore,still]"]),
    # Display glyphs (operator, 11 Nov; plan 1B.12): "full display on that display" is one transfer transaction.
    ("a display glyph from a collapsed view moves it, then expands there; the expand persists as the glyph's",
     [ready(), TransferRequested(GEN, ACT, 5, B, True, True), moved, prepared, committed],
     ["applied ordinary", "applied transfer_pending BeginTransfer[display-B,ordinary]",
      "applied enter_pending BeginEnter[user,anim]", "applied entering RunEnter", "applied expanded Persist[True]"]),
    ("a failed display move stays collapsed on the source and expands nowhere",
     [ready(), TransferRequested(GEN, ACT, 5, B, True, True), move_failed],
     ["applied ordinary", "applied transfer_pending BeginTransfer[display-B,ordinary]",
      "applied ordinary RollbackTransfer"]),
    ("a display glyph from an expanded view moves it expanded (one collapse + move + expand transaction)",
     [*EXPAND_BY_USER, TransferRequested(GEN, ACT, 5, B, True, True), moved],
     [*EXPANDED_TRACE, "applied transfer_pending BeginTransfer[display-B,expanded]", "applied expanded"]),
    ("a failed expanded move rolls back expanded on the source, the intent untouched",
     [*EXPAND_BY_USER, TransferRequested(GEN, ACT, 5, B, True, True), move_failed],
     [*EXPANDED_TRACE, "applied transfer_pending BeginTransfer[display-B,expanded]",
      "applied expanded RollbackTransfer"]),
    ("a display glyph for an incapable mode is refused before any change",
     [ready(capable=False), TransferRequested(GEN, ACT, 5, B, True, True)],
     ["applied dormant", "rejected dormant RejectTransfer"]),
    ("a display glyph under Edit is refused (the glyph is withdrawn there; a stale press changes nothing)",
     [ready(), EditEntered(GEN), TransferRequested(GEN, ACT, 5, B, True, True)],
     ["applied ordinary", "applied ordinary", "rejected ordinary RejectTransfer"]),
    ("the move's display lost mid-transfer rolls back, nothing expands",
     [ready(), TransferRequested(GEN, ACT, 5, B, True, True), DisplayLost(GEN, B)],
     ["applied ordinary", "applied transfer_pending BeginTransfer[display-B,ordinary]",
      "applied ordinary RollbackTransfer"]),
    # Edit beside the view (operator, 11 Nov; plan 1B.1): Edit edits the display it was entered on.
    ("Edit entered on another display keeps the view expanded, with no collapse transaction and no write",
     [*EXPAND_BY_USER, EditEntered(GEN, False)], [*EXPANDED_TRACE, "applied expanded"]),
    ("an Edit beside the view: Save and Cancel leave it expanded and write nothing",
     [*EXPAND_BY_USER, EditEntered(GEN, False), EditExited(GEN, saved=True), EditEntered(GEN, False),
      EditExited(GEN, saved=False)],
     [*EXPANDED_TRACE, "applied expanded", "applied expanded", "applied expanded", "applied expanded"]),
    ("an Edit beside the view, then one on it: the second is Fullscreen Edit",
     [*EXPAND_BY_USER, EditEntered(GEN, False), EditExited(GEN, saved=False), EditEntered(GEN, True)],
     [*EXPANDED_TRACE, "applied expanded", "applied expanded", "applied expanded"]),
    ("a collapse press under an Edit beside the view waits for its Save/Cancel; declined, nothing collapses",
     [*EXPAND_BY_USER, EditEntered(GEN, False), glyph(2, False), EditResolutionDeclined(GEN),
      EditExited(GEN, saved=True)],
     [*EXPANDED_TRACE, "applied expanded", "applied expanded RequestEditResolution", "applied expanded",
      "applied expanded"]),
    ("a collapse press that waited for the Edit beside the view is the user's collapse after its Save",
     [*EXPAND_BY_USER, EditEntered(GEN, False), glyph(2, False), EditExited(GEN, saved=True), exited],
     [*EXPANDED_TRACE, "applied expanded", "applied expanded RequestEditResolution",
      "applied exiting Persist[False],BeginExit[user]", "applied ordinary"]),
    ("an incapable mode under an Edit beside the view is refused; a capable one stays expanded",
     [*EXPAND_BY_USER, EditEntered(GEN, False), ModeRequested(GEN, 7, INCAPABLE, False),
      ModeRequested(GEN, 8, "capable-2", True), activated("capable-2", True, act=2)],
     [*EXPANDED_TRACE, "applied expanded", "rejected expanded RejectModeRequest",
      "applied expanded Forward[capable-2,keep]", "applied expanded"]),
    ("a transfer under an Edit beside the view is refused before any change",
     [*EXPAND_BY_USER, EditEntered(GEN, False), TransferRequested(GEN, ACT, 5, B, True)],
     [*EXPANDED_TRACE, "applied expanded", "rejected expanded RejectTransfer"]),
    ("an incapable activation under an Edit beside the view collapses it; the Edit goes on as an ordinary one",
     [*EXPAND_BY_USER, EditEntered(GEN, False), activated(INCAPABLE, False, act=2), exited,
      EditExited(GEN, saved=False)],
     [*EXPANDED_TRACE, "applied expanded", "applied exiting BeginExit[capability_lost]",
      "applied dormant Persist[False]", "applied dormant"]),
    ("Edit entered on another display while entering is an ordinary Edit (collapses at the commit edge)",
     [ready(), glyph(1, True), prepared, EditEntered(GEN, False), committed],
     ["applied ordinary", "applied enter_pending BeginEnter[user,anim]", "applied entering RunEnter",
      "applied entering", "applied exiting Persist[True],BeginExit[edit]"]),
    ("an ordinary Edit begun while entering collapses; its Cancel restores expansion after the editor exits",
     [ready(), glyph(1, True), prepared, EditEntered(GEN), committed, exited, EditExited(GEN, saved=False),
      prepared, committed],
     ["applied ordinary", "applied enter_pending BeginEnter[user,anim]", "applied entering RunEnter",
      "applied entering", "applied exiting Persist[True],BeginExit[edit]", "applied ordinary",
      "applied enter_pending BeginEnter[restore,anim]", "applied entering RunEnter", "applied expanded"]),
    ("an ordinary Edit's Save restores expansion the same way",
     [ready(), glyph(1, True), prepared, EditEntered(GEN), committed, exited, EditExited(GEN, saved=True)],
     ["applied ordinary", "applied enter_pending BeginEnter[user,anim]", "applied entering RunEnter",
      "applied entering", "applied exiting Persist[True],BeginExit[edit]", "applied ordinary",
      "applied enter_pending BeginEnter[restore,anim]"]),
    ("an ordinary Edit ending before its collapse commits re-enters at the commit",
     [ready(), glyph(1, True), prepared, EditEntered(GEN), committed, EditExited(GEN, saved=False), exited],
     ["applied ordinary", "applied enter_pending BeginEnter[user,anim]", "applied entering RunEnter",
      "applied entering", "applied exiting Persist[True],BeginExit[edit]", "applied exiting",
      "applied enter_pending BeginEnter[restore,anim]"]),
    ("Edit during a pending restore cancels it",
     [ready(requested=True), EditEntered(GEN)],
     ["applied enter_pending BeginEnter[restore,still]", "applied ordinary CancelEnter"]),
    ("Edit while entering collapses at the commit edge; the user's expand still persists",
     [ready(), glyph(1, True), prepared, EditEntered(GEN), committed],
     ["applied ordinary", "applied enter_pending BeginEnter[user,anim]", "applied entering RunEnter",
      "applied entering", "applied exiting Persist[True],BeginExit[edit]"]),
    ("a glyph under Edit asks the session to resolve its draft, then enters",
     [ready(), EditEntered(GEN), glyph(1, True), glyph(2, True), EditExited(GEN, saved=True)],
     ["applied ordinary", "applied ordinary", "applied ordinary RequestEditResolution", "duplicate ordinary",
      "applied enter_pending BeginEnter[user,anim]"]),
    ("a declined Edit resolution keeps the draft and Edit; nothing enters later",
     [ready(), EditEntered(GEN), glyph(1, True), EditResolutionDeclined(GEN), EditExited(GEN, saved=False)],
     ["applied ordinary", "applied ordinary", "applied ordinary RequestEditResolution", "applied ordinary",
      "applied ordinary"]),
    ("capable -> capable keeps the takeover through the canonical activation",
     [*EXPAND_BY_USER, ModeRequested(GEN, 7, "capable-2", True), activated("capable-2", True, act=2)],
     [*EXPANDED_TRACE, "applied expanded Forward[capable-2,keep]", "applied expanded"]),
    ("capable -> incapable collapses first, then changes mode; the intent is cleared once the mode is incapable",
     [*EXPAND_BY_USER, ModeRequested(GEN, 7, INCAPABLE, False), exited, activated(INCAPABLE, False, act=2)],
     [*EXPANDED_TRACE, "applied exiting BeginExit[mode_incapable]", f"applied ordinary Forward[{INCAPABLE},plain]",
      "applied dormant Persist[False]"]),
    ("expanded -> incapable -> capable does not re-expand (operator, 7 Nov)",
     [*EXPAND_BY_USER, ModeRequested(GEN, 7, INCAPABLE, False), exited, activated(INCAPABLE, False, act=2),
      ModeRequested(GEN, 8, CAPABLE, True), activated(CAPABLE, True, act=3)],
     [*EXPANDED_TRACE, "applied exiting BeginExit[mode_incapable]", f"applied ordinary Forward[{INCAPABLE},plain]",
      "applied dormant Persist[False]", f"applied dormant Forward[{CAPABLE},plain]", "applied ordinary"]),
    ("a held intent (Edit) is cleared by a switch to an incapable mode",
     [ready(requested=True), EditEntered(GEN), activated(INCAPABLE, False, act=2), activated(CAPABLE, True, act=3),
      EditExited(GEN, saved=False)],
     ["applied enter_pending BeginEnter[restore,still]", "applied ordinary CancelEnter",
      "applied dormant Persist[False]", "applied ordinary", "applied ordinary"]),
    ("a capable -> capable switch keeps a held intent",
     [ready(requested=True), EditEntered(GEN), activated("capable-2", True, act=2), EditExited(GEN, saved=True)],
     ["applied enter_pending BeginEnter[restore,still]", "applied ordinary CancelEnter", "applied ordinary",
      "applied enter_pending BeginEnter[restore,anim]"]),
    ("an incapable activation during a pending restore cancels it and clears the intent",
     [ready(requested=True), activated(INCAPABLE, False, act=2)],
     ["applied enter_pending BeginEnter[restore,still]", "applied dormant CancelEnter,Persist[False]"]),
    ("an incapable activation while a user enter runs never persists the intent",
     [ready(), glyph(1, True), prepared, activated(INCAPABLE, False, act=2), committed, exited],
     ["applied ordinary", "applied enter_pending BeginEnter[user,anim]", "applied entering RunEnter",
      "applied entering", "applied exiting BeginExit[capability_lost]", "applied dormant"]),
    ("an incapable activation while a restore runs clears the intent after the collapse commits",
     [ready(requested=True), prepared, activated(INCAPABLE, False, act=2), committed, exited],
     ["applied enter_pending BeginEnter[restore,still]", "applied entering RunEnter", "applied entering",
      "applied exiting BeginExit[capability_lost]", "applied dormant Persist[False]"]),
    ("an incapable activation while a restore fails clears the intent at the cancel",
     [ready(requested=True), prepared, activated(INCAPABLE, False, act=2), failed],
     ["applied enter_pending BeginEnter[restore,still]", "applied entering RunEnter", "applied entering",
      "applied dormant CancelEnter,Persist[False]"]),
    ("an incapable activation during an ordinary transfer clears the intent when it lands",
     [ready(requested=True), failed, TransferRequested(GEN, ACT, 5, B, True), activated(INCAPABLE, False, act=2),
      moved],
     ["applied enter_pending BeginEnter[restore,still]", "applied ordinary CancelEnter",
      f"applied transfer_pending BeginTransfer[{B},ordinary]", "applied transfer_pending",
      "applied dormant Persist[False]"]),
    ("a rejected incapable target re-expands the still-active capable mode",
     [*EXPAND_BY_USER, ModeRequested(GEN, 7, INCAPABLE, False), exited, ModeRejected(GEN, 7), prepared, committed],
     [*EXPANDED_TRACE, "applied exiting BeginExit[mode_incapable]", f"applied ordinary Forward[{INCAPABLE},plain]",
      "applied enter_pending BeginEnter[rollback,anim]", "applied entering RunEnter", "applied expanded"]),
    ("a cycle while expanded skips incapable modes and stays expanded on the next capable one",
     [*EXPAND_BY_USER, ModeCycleRequested(GEN, 7, ((INCAPABLE, False), ("incapable-2", False), ("capable-2", True))),
      activated("capable-2", True, act=2)],
     [*EXPANDED_TRACE, "applied expanded Forward[capable-2,keep]", "applied expanded"]),
    ("a cycle while expanded wraps around to a capable mode before the current one",
     [*EXPAND_BY_USER, ModeCycleRequested(GEN, 7, ((INCAPABLE, False), ("capable-0", True), ("incapable-2", False)))],
     [*EXPANDED_TRACE, "applied expanded Forward[capable-0,keep]"]),
    ("a cycle while expanded with no other capable mode stays on the current mode, expanded",
     [*EXPAND_BY_USER, ModeCycleRequested(GEN, 7, ((INCAPABLE, False), ("incapable-2", False)))],
     [*EXPANDED_TRACE, "rejected expanded RejectModeRequest"]),
    ("an explicit incapable selection while expanded still collapses (Settings, context menu)",
     [*EXPAND_BY_USER, ModeRequested(GEN, 7, INCAPABLE, False)],
     [*EXPANDED_TRACE, "applied exiting BeginExit[mode_incapable]"]),
    ("a cycle from an ordinary card takes the next enabled mode, capable or not",
     [ready(), ModeCycleRequested(GEN, 7, ((INCAPABLE, False), ("capable-2", True)))],
     ["applied ordinary", f"applied ordinary Forward[{INCAPABLE},plain]"]),
    ("a cycle during a transition is refused",
     [ready(), glyph(1, True), ModeCycleRequested(GEN, 7, (("capable-2", True),))],
     ["applied ordinary", "applied enter_pending BeginEnter[user,anim]", "rejected enter_pending RejectModeRequest"]),
    ("an unrelated mode rejection has no takeover consequence",
     [ready(), ModeRejected(GEN, 99)], ["applied ordinary", "ignored ordinary"]),
    ("incapable -> capable never re-expands, even from a saved intent",
     [ready(requested=True, capable=False), activated(CAPABLE, True, act=2)],
     ["applied dormant Persist[False]", "applied ordinary"]),
    ("incapable -> capable without intent rests ordinary",
     [ready(capable=False), activated(CAPABLE, True, act=2)], ["applied dormant", "applied ordinary"]),
    ("an older activation completion is stale",
     [ready(act=3), activated(CAPABLE, True, act=2)], ["applied ordinary", "stale ordinary"]),
    ("a mode request during a transition is rejected and changes nothing",
     [ready(), glyph(1, True), ModeRequested(GEN, 7, INCAPABLE, False)],
     ["applied ordinary", "applied enter_pending BeginEnter[user,anim]", "rejected enter_pending RejectModeRequest"]),
    ("an incapable activation while expanded collapses, then clears the intent once the collapse commits",
     [*EXPAND_BY_USER, activated(INCAPABLE, False, act=2), exited],
     [*EXPANDED_TRACE, "applied exiting BeginExit[capability_lost]", "applied dormant Persist[False]"]),
    ("the intent survives a Settings round trip and a restart while the capable mode stays selected",
     [*EXPAND_BY_USER, SettingsOpened(GEN), ready(requested=True, gen=2), prepared, committed, Shutdown(2)],
     [*EXPANDED_TRACE, "applied retiring Retire[settings]", "applied enter_pending BeginEnter[restore,still]",
      "applied entering RunEnter", "applied expanded", "applied retiring Retire[shutdown]"]),
    ("an expand glyph on an incapable mode is rejected",
     [ready(capable=False), glyph(1, True)], ["applied dormant", "rejected dormant"]),
    ("expanded transfer is one transaction and lands expanded on the target",
     [*EXPAND_BY_USER, TransferRequested(GEN, ACT, 5, B, True), moved],
     [*EXPANDED_TRACE, f"applied transfer_pending BeginTransfer[{B},expanded]", "applied expanded"]),
    ("a failed transfer restores the source exactly",
     [*EXPAND_BY_USER, TransferRequested(GEN, ACT, 5, B, True), move_failed],
     [*EXPANDED_TRACE, f"applied transfer_pending BeginTransfer[{B},expanded]", "applied expanded RollbackTransfer"]),
    ("an unready target is refused before any change",
     [*EXPAND_BY_USER, TransferRequested(GEN, ACT, 5, B, False)],
     [*EXPANDED_TRACE, "rejected expanded RejectTransfer"]),
    ("losing the target mid-transfer rolls back to the source",
     [*EXPAND_BY_USER, TransferRequested(GEN, ACT, 5, B, True), DisplayLost(GEN, B), moved],
     [*EXPANDED_TRACE, f"applied transfer_pending BeginTransfer[{B},expanded]", "applied expanded RollbackTransfer",
      "stale expanded"]),
    ("an ordinary transfer moves without expanding",
     [ready(), TransferRequested(GEN, ACT, 5, B, True), moved],
     ["applied ordinary", f"applied transfer_pending BeginTransfer[{B},ordinary]", "applied ordinary"]),
    ("Edit during an expanded transfer collapses at its commit",
     [*EXPAND_BY_USER, TransferRequested(GEN, ACT, 5, B, True), EditEntered(GEN), moved],
     [*EXPANDED_TRACE, f"applied transfer_pending BeginTransfer[{B},expanded]", "applied transfer_pending",
      "applied exiting BeginExit[edit]"]),
    ("after a transfer the old display's glyph is stale",
     [*EXPAND_BY_USER, TransferRequested(GEN, ACT, 5, B, True), moved, glyph(2, False, disp=A)],
     [*EXPANDED_TRACE, f"applied transfer_pending BeginTransfer[{B},expanded]", "applied expanded",
      "stale expanded"]),
    ("losing the owning display retires safely; late callbacks are stale; the replacement re-evaluates once",
     [*EXPAND_BY_USER, DisplayLost(GEN, A), exited, glyph(2, False),
      ready(requested=True, gen=2, disp=B), ready(requested=True, gen=2, disp=B)],
     [*EXPANDED_TRACE, "applied retiring Retire[topology]", "stale retiring", "stale retiring",
      "applied enter_pending BeginEnter[restore,still]", "stale enter_pending"]),
    ("losing another display is ignored",
     [*EXPAND_BY_USER, DisplayLost(GEN, B)], [*EXPANDED_TRACE, "ignored expanded"]),
    ("Settings retires the state, not the intent; the next generation restores it",
     [*EXPAND_BY_USER, SettingsOpened(GEN), glyph(2, False), ready(requested=True, gen=2)],
     [*EXPANDED_TRACE, "applied retiring Retire[settings]", "stale retiring",
      "applied enter_pending BeginEnter[restore,still]"]),
    ("a retired owner (runtime reload) retires the state, not the intent; the replacement restores it",
     [*EXPAND_BY_USER, OwnerRetired(GEN, "reload"), glyph(2, False), ready(requested=True, gen=2)],
     [*EXPANDED_TRACE, "applied retiring Retire[reload]", "stale retiring",
      "applied enter_pending BeginEnter[restore,still]"]),
    ("an older generation's readiness is stale",
     [ready(gen=3), ready(gen=2)], ["applied ordinary", "stale ordinary"]),
    ("shutdown is terminal",
     [*EXPAND_BY_USER, Shutdown(GEN), ready(gen=2, requested=True), glyph(2, False)],
     [*EXPANDED_TRACE, "applied retiring Retire[shutdown]", "stale retiring", "stale retiring"]),
]


@pytest.mark.parametrize(("events", "expected"), [pytest.param(e, x, id=n) for n, e, x in SCENARIOS])
def test_event_sequence_trace(events, expected):
    _state, steps = _run(events)
    assert [_line(step) for step in steps] == expected


def test_intent_is_the_last_written_value_through_every_scenario():
    """The reducer's ``requested`` is always the persisted value: the readiness value, then each write."""
    for name, events, _expected in SCENARIOS:
        state = tk.initial_state()
        persisted = False
        for spec in events:
            event = spec(state) if callable(spec) else spec
            step = reduce(state, event)
            if isinstance(event, GenerationReady) and step.outcome is Outcome.APPLIED:
                persisted = event.requested
            for action in step.actions:
                if isinstance(action, PersistIntent):
                    persisted = action.requested
            state = step.state
            assert state.requested is persisted, name


def test_restore_and_rollback_enters_never_write_the_intent():
    for events, skip in (
        ([ready(requested=True), prepared, committed], 0),
        ([*EXPAND_BY_USER, ModeRequested(GEN, 7, INCAPABLE, False), exited, ModeRejected(GEN, 7), prepared,
          committed], len(EXPAND_BY_USER)),
        # An ordinary Edit (begun while entering) collapses; its Cancel restores without writing.
        ([ready(), glyph(1, True), prepared, EditEntered(GEN), committed, exited, EditExited(GEN, saved=False),
          prepared, committed], 5),
        # A Fullscreen Edit round trip writes nothing either.
        ([*EXPAND_BY_USER, EditEntered(GEN), EditExited(GEN, saved=True), EditEntered(GEN),
          EditExited(GEN, saved=False)], len(EXPAND_BY_USER)),
    ):
        _state, steps = _run(events)
        assert not [a for s in steps[skip:] for a in s.actions if isinstance(a, PersistIntent)]


# ------------------------------------------------------------------------------- exhaustive invariant walk


def _alphabet(s: tk.TakeoverState) -> list[tk.Event]:
    g = s.generation if s.generation is not None else GEN
    act = s.activation if s.activation is not None else ACT
    disp = s.display or A
    other = B if disp == A else A
    nxt = s.last_press + 1
    return [
        GenerationReady(g + 1, act + 1, A, CAPABLE, True, True),
        GenerationReady(g, act, A, CAPABLE, True, False),
        GlyphPressed(g, act, disp, nxt, True),
        GlyphPressed(g, act, disp, nxt, False),
        GlyphPressed(g, act, disp, s.last_press, True),
        GlyphPressed(g, act, disp, s.last_press, False),
        GlyphPressed(g - 1, act, disp, nxt, True),
        GlyphPressed(g - 1, act, disp, nxt, False),
        GlyphPressed(g, act - 1, disp, nxt, False),
        GlyphPressed(g, act, other, nxt, False),
        EnterCommitted(g - 1, s.txn), ExitCommitted(g - 1, s.txn), TransferFailed(g - 1, s.txn),
        ModeActivated(g - 1, act + 1, disp, INCAPABLE, False), DisplayLost(g - 1, disp), EditEntered(g - 1),
        SettingsOpened(g - 1), Shutdown(g - 1),
        EnterPrepared(g, s.txn), EnterFailed(g, s.txn), EnterCommitted(g, s.txn), ExitCommitted(g, s.txn),
        EnterCommitted(g, s.txn - 1),
        ModeRequested(g, 7, INCAPABLE, False), ModeRequested(g, 8, "capable-2", True),
        ModeActivated(g, act + 1, disp, INCAPABLE, False), ModeActivated(g, act + 1, disp, "capable-2", True),
        ModeRejected(g, 7),
        ModeCycleRequested(g, 11, ((INCAPABLE, False), ("capable-2", True))),
        ModeCycleRequested(g, 12, ((INCAPABLE, False),)), ModeCycleRequested(g, 13, ()),
        TransferRequested(g, act, 9, other, True), TransferRequested(g, act, 9, other, False),
        TransferRequested(g, act, 10, other, True, True),
        TransferCommitted(g, s.txn), TransferFailed(g, s.txn),
        DisplayLost(g, disp), DisplayLost(g, other),
        EditEntered(g), EditEntered(g, False), EditExited(g, False), EditResolutionDeclined(g), SettingsOpened(g),
        Shutdown(g),
        OwnerRetired(g, "reload"), OwnerRetired(g - 1, "reload"),
    ]


_NON_WRITERS = (GenerationReady, EnterPrepared, EnterFailed, ExitCommitted, ModeRequested, ModeCycleRequested,
                ModeActivated,
                ModeRejected, TransferRequested, TransferCommitted, TransferFailed, DisplayLost, EditEntered,
                EditExited, EditResolutionDeclined, SettingsOpened, OwnerRetired, Shutdown)
_BEGINS = (BeginEnter, BeginExit, BeginTransfer)


def _check(s0: tk.TakeoverState, event: tk.Event, step: tk.Step) -> None:
    s1, actions = step.state, step.actions
    ctx = f"{s0.phase.value} --{event!r}--> {_line(step)}"
    # Fences: another generation (other than a newer readiness), a retiring generation, a foreign activation or
    # display, or a repeated press id, never changes anything.
    newer_ready = isinstance(event, GenerationReady) and (s0.generation is None or event.generation > s0.generation)
    if not newer_ready and (event.generation != s0.generation or s0.phase is Phase.RETIRING):
        assert step.outcome is Outcome.STALE, ctx
    if isinstance(event, GlyphPressed) and event.generation == s0.generation and s0.phase is not Phase.RETIRING:
        if event.activation != s0.activation or event.display != s0.display:
            assert step.outcome is Outcome.STALE, ctx
        elif event.press_id <= s0.last_press:
            assert step.outcome is Outcome.DUPLICATE and s1 == s0, ctx
    if s0.terminal or step.outcome is Outcome.STALE:
        assert s1 == s0 and not actions, ctx
    if step.outcome in (Outcome.DUPLICATE, Outcome.IGNORED):
        assert not actions and replace(s1, last_press=s0.last_press) == s0, ctx
    if step.outcome is Outcome.REJECTED:
        assert all(isinstance(a, (RejectModeRequest, RejectTransfer)) for a in actions), ctx
        assert replace(s1, last_press=s0.last_press) == s0, ctx
    # Expanded only while eligible; nothing half-held at rest.
    if s1.phase is Phase.EXPANDED:
        assert s1.eligible, ctx
    if s1.phase in (Phase.DORMANT, Phase.ORDINARY):
        assert s1.held_mode_request is None and s1.transfer_target is None, ctx
        assert s1.phase is (Phase.ORDINARY if s1.activation is not None and s1.mode_capable else Phase.DORMANT), ctx
    # One transaction at a time, named by the state.
    begins = [a for a in actions if isinstance(a, _BEGINS)]
    assert len(begins) <= 1, ctx
    for begin in begins:
        assert begin.txn == s1.txn == s0.txn + 1 and s1.phase in tk.TRANSACTION_PHASES, ctx
    for a in actions:
        if isinstance(a, BeginEnter):
            assert s1.phase is Phase.ENTER_PENDING and s1.eligible, ctx
        if isinstance(a, (CancelEnter, RollbackTransfer, RunEnter)):
            assert a.txn == s0.txn, ctx
    assert s1.txn >= s0.txn, ctx
    # Only the user's glyph (or the commit of the user's enter, on a capable mode) writes the intent True; False
    # is the user's collapse (also one that waited for Fullscreen Edit's own Save/Cancel), or an incapable mode
    # clearing it where nothing is drawn expanded any more.
    writes = [a for a in actions if isinstance(a, PersistIntent)]
    assert len(writes) <= 1, ctx
    if writes:
        if writes[0].requested:
            assert isinstance(event, EnterCommitted) and s1.mode_capable, ctx
        elif isinstance(event, EditExited) and s0.edit_collapse_press is not None:
            assert any(isinstance(a, BeginExit) and a.reason.value == "user" for a in actions), ctx
        elif isinstance(event, _NON_WRITERS):
            incapable_edge = isinstance(event, (ModeActivated, GenerationReady)) and not event.mode_capable
            assert incapable_edge or getattr(s0, "clear_intent_at_rest", False), ctx
            assert s1.phase not in (Phase.ENTERING, Phase.EXPANDED, Phase.TRANSFER_PENDING), ctx
        assert s1.requested is writes[0].requested, ctx
    elif not isinstance(event, GenerationReady):
        assert s1.requested is s0.requested, ctx
    # A mode switch never re-expands: an incapable mode never rests holding the intent, and a capable activation
    # never begins an enter from a collapsed view unless the intent was held across a capable -> capable switch.
    if s1.phase in tk.RESTING_PHASES and s1.activation is not None and not s1.mode_capable:
        assert not s1.requested and not getattr(s1, "clear_intent_at_rest", False), ctx
    if s1.phase in (Phase.DORMANT, Phase.ORDINARY):
        assert not getattr(s1, "clear_intent_at_rest", False), ctx
    # Retirement only on the three retiring edges.
    if any(isinstance(a, RetireTakeover) for a in actions):
        assert isinstance(event, (SettingsOpened, OwnerRetired, Shutdown, DisplayLost)), ctx
        assert s1.phase is Phase.RETIRING, ctx
    # Keep-expanded forwards only a capable target from EXPANDED; an incapable one is held until the collapse.
    for a in actions:
        if isinstance(a, ForwardModeRequest) and a.keep_expanded:
            assert s0.phase is Phase.EXPANDED and s1.phase is Phase.EXPANDED, ctx
    if isinstance(event, ModeRequested) and not event.mode_capable and s0.phase is Phase.EXPANDED:
        if s0.edit_fullscreen or s0.edit_elsewhere:
            # Fullscreen Edit, or an Edit beside the view: refused until Save or Cancel; nothing changes.
            assert step.outcome is Outcome.REJECTED and s1 == s0, ctx
        else:
            assert not [a for a in actions if isinstance(a, ForwardModeRequest)] and s1.phase is Phase.EXITING, ctx
    # Fullscreen Edit (M3c): only ever with Edit, on an expanded view (or a retiring generation). Entering Edit on a
    # resting expanded view never collapses it; under Fullscreen Edit nothing collapses the view except the user's
    # collapse after the session's own Save/Cancel, or an incapable activation (which ends the session first).
    if s1.edit_fullscreen:
        assert s1.edit_active and s1.phase in (Phase.EXPANDED, Phase.RETIRING), ctx
    # An Edit beside the view (plan 1B.1): the same, never together with Fullscreen Edit.
    if s1.edit_elsewhere:
        assert s1.edit_active and not s1.edit_fullscreen and s1.phase in (Phase.EXPANDED, Phase.RETIRING), ctx
    if isinstance(event, EditEntered) and s0.phase is Phase.EXPANDED and step.outcome is Outcome.APPLIED:
        assert not actions and s1.phase is Phase.EXPANDED, ctx
        assert s1.edit_fullscreen is event.on_view_display and s1.edit_elsewhere is (not event.on_view_display), ctx
    if (s0.edit_fullscreen or s0.edit_elsewhere) and any(isinstance(a, BeginExit) for a in actions):
        assert isinstance(event, (EditExited, ModeActivated)), ctx
        if isinstance(event, ModeActivated) and s0.edit_fullscreen:
            assert isinstance(actions[0], EndFullscreenEdit) and not s1.edit_active, ctx
        if isinstance(event, ModeActivated) and s0.edit_elsewhere:
            # The Edit beside the view never held it: it goes on as an ordinary Edit, nothing ends it.
            assert not any(isinstance(a, EndFullscreenEdit) for a in actions), ctx
            assert s1.edit_active and not s1.edit_elsewhere, ctx
    if (s0.edit_fullscreen or s0.edit_elsewhere) and isinstance(event, TransferRequested) \
            and step.outcome is not Outcome.STALE:
        assert not [a for a in actions if isinstance(a, BeginTransfer)], ctx
    # A cycle never collapses an expanded view and never forwards an incapable mode from it.
    if isinstance(event, ModeCycleRequested) and s0.phase is Phase.EXPANDED and step.outcome is not Outcome.STALE:
        assert s1 == s0, ctx
        capable = {mode for mode, ok in event.candidates if ok}
        for a in actions:
            if isinstance(a, ForwardModeRequest):
                assert a.keep_expanded and a.mode_id in capable, ctx


_STARTS = {
    "fresh": tk.initial_state(),
    "ordinary": _run([ready()])[0],
    "dormant-after-incapable": _run([ready(requested=True, capable=False)])[0],
    "edit-held-intent": _run([ready(requested=True), EditEntered(GEN)])[0],
    "entering-then-incapable": _run([ready(requested=True), prepared, activated(INCAPABLE, False, act=2)])[0],
    "restore-pending": _run([ready(requested=True)])[0],
    "entering": _run([ready(), glyph(1, True), prepared])[0],
    "expanded": _run(EXPAND_BY_USER)[0],
    "exiting": _run([*EXPAND_BY_USER, glyph(2, False)])[0],
    "edit": _run([ready(requested=True), EditEntered(GEN)])[0],
    "fullscreen-edit": _run([*EXPAND_BY_USER, EditEntered(GEN)])[0],
    "fullscreen-edit-collapse-held": _run([*EXPAND_BY_USER, EditEntered(GEN), glyph(2, False)])[0],
    "edit-beside-view": _run([*EXPAND_BY_USER, EditEntered(GEN, False)])[0],
    "edit-beside-view-collapse-held": _run([*EXPAND_BY_USER, EditEntered(GEN, False), glyph(2, False)])[0],
    "transfer": _run([*EXPAND_BY_USER, TransferRequested(GEN, ACT, 5, B, True)])[0],
    "display-glyph-move": _run([ready(), TransferRequested(GEN, ACT, 5, B, True, True)])[0],
    "held-mode": _run([*EXPAND_BY_USER, ModeRequested(GEN, 7, INCAPABLE, False)])[0],
}


@pytest.mark.parametrize("start", list(_STARTS))
def test_every_short_event_sequence_keeps_the_invariants(start):
    depth = 4
    frontier = deque([(_STARTS[start], 0)])
    seen = {_STARTS[start]}
    transitions = 0
    while frontier:
        state, level = frontier.popleft()
        for event in _alphabet(state):
            step = reduce(state, event)
            _check(state, event, step)
            transitions += 1
            if state.terminal:
                assert step.outcome is Outcome.STALE
            if level + 1 < depth and step.state not in seen:
                seen.add(step.state)
                frontier.append((step.state, level + 1))
    assert transitions > 100


def test_a_retiring_generation_answers_nothing_until_a_newer_readiness():
    retiring = _run([*EXPAND_BY_USER, SettingsOpened(GEN)])[0]
    for event in _alphabet(retiring):
        step = reduce(retiring, event)
        if isinstance(event, GenerationReady) and event.generation > GEN:
            assert step.outcome is Outcome.APPLIED
        else:
            assert step.outcome is Outcome.STALE and not step.actions and step.state == retiring


# ------------------------------------------------------------------- accept/reject permutations (coordinator)


class _Coordinator:
    """Answers each action as the M2 coordinator will, from a script of accept/reject decisions."""

    def __init__(self, *, prepare=True, commit=True, transfer=True, mode=True):
        self.script = {"prepare": prepare, "commit": commit, "transfer": transfer, "mode": mode}
        self.writes: list[bool] = []
        self.mode_capable: dict[str, bool] = {}

    def answer(self, s: tk.TakeoverState, action) -> tk.Event | None:
        g = s.generation
        if isinstance(action, BeginEnter):
            return EnterPrepared(g, action.txn) if self.script["prepare"] else EnterFailed(g, action.txn)
        if isinstance(action, RunEnter):
            return EnterCommitted(g, action.txn) if self.script["commit"] else EnterFailed(g, action.txn)
        if isinstance(action, BeginExit):
            return ExitCommitted(g, action.txn)
        if isinstance(action, BeginTransfer):
            return TransferCommitted(g, action.txn) if self.script["transfer"] else TransferFailed(g, action.txn)
        if isinstance(action, ForwardModeRequest):
            if not self.script["mode"]:
                return ModeRejected(g, action.request_id)
            return ModeActivated(g, (s.activation or 0) + 1, s.display or A, action.mode_id,
                                 self.mode_capable.get(action.mode_id, False))
        if isinstance(action, PersistIntent):
            self.writes.append(action.requested)
        return None


def _drive(state, events, coordinator: _Coordinator, *, disturb: tk.Event | None = None, at: int = -1):
    """Feed ``events``; answer every action (FIFO, as the coordinator's completion edges arrive); inject one
    disturbance before the ``at``-th answer."""
    pending: deque = deque()
    answered = 0
    for event in events:
        step = reduce(state, event)
        state = step.state
        pending.extend(step.actions)
        while pending:
            # Every transaction is bounded by an event: a reducer that answers its own failure with a retry would
            # loop here forever, so a runaway is a failure, never a hang.
            assert answered < 200, f"the coordinator loop did not settle: {state}"
            if disturb is not None and answered == at:
                step = reduce(state, disturb)
                state = step.state
                pending.extend(step.actions)
                disturb = None
                continue
            reply = coordinator.answer(state, pending.popleft())
            answered += 1
            if reply is not None:
                step = reduce(state, reply)
                state = step.state
                pending.extend(step.actions)
    return state


_DISTURBANCES = {
    "none": None,
    "collapse": GlyphPressed(GEN, ACT, A, 50, False),
    "expand": GlyphPressed(GEN, ACT, A, 50, True),
    "edit": EditEntered(GEN),
    "edit-beside": EditEntered(GEN, False),
    "settings": SettingsOpened(GEN),
    "lost": DisplayLost(GEN, A),
    "other-lost": DisplayLost(GEN, B),
}

_FLOWS = {
    "user-expand": (False, [glyph(1, True)]),
    "restore": (True, []),
    "capable->incapable": (True, [ModeRequested(GEN, 7, INCAPABLE, False)]),
    "capable->capable": (True, [ModeRequested(GEN, 8, "capable-2", True)]),
    "transfer": (True, [TransferRequested(GEN, ACT, 9, B, True)]),
    "display-glyph": (False, [TransferRequested(GEN, ACT, 9, B, True, True)]),
}


@pytest.mark.parametrize("flow", list(_FLOWS))
@pytest.mark.parametrize("disturbance", list(_DISTURBANCES))
@pytest.mark.parametrize(("prepare", "commit", "transfer", "mode"), list(product((True, False), repeat=4)))
def test_accept_reject_permutations_always_settle_coherently(flow, disturbance, prepare, commit, transfer, mode):
    requested, events = _FLOWS[flow]
    coordinator = _Coordinator(prepare=prepare, commit=commit, transfer=transfer, mode=mode)
    coordinator.mode_capable = {CAPABLE: True, "capable-2": True, INCAPABLE: False}
    disturb = _DISTURBANCES[disturbance]
    for at in range(0, 6) if disturb is not None else (-1,):
        # Begin expanded where the flow needs it (immediate accepts), then run the flow under the script.
        start = _drive(tk.initial_state(), [ready(requested=requested)], _Coordinator())
        if flow in ("user-expand", "display-glyph"):
            assert start.phase is Phase.ORDINARY
        else:
            assert start.phase is Phase.EXPANDED
        final = _drive(start, events, coordinator, disturb=disturb, at=at)

        assert final.phase in tk.RESTING_PHASES or final.phase is Phase.RETIRING, (flow, disturbance, at, final)
        if final.phase is Phase.EXPANDED:
            assert final.eligible and final.requested
        if final.phase is not Phase.RETIRING and final.requested and final.eligible and prepare and commit:
            # Nothing left an eligible intent collapsed when every enter would have succeeded.
            assert final.phase is Phase.EXPANDED, (flow, disturbance, at, final)
        if disturbance in ("settings", "lost") and at < 6:
            assert final.phase in (Phase.RETIRING, *tk.RESTING_PHASES)


def test_immediate_accepts_reach_the_expected_end_states():
    c = _Coordinator()
    c.mode_capable = {CAPABLE: True, "capable-2": True, INCAPABLE: False}
    expanded = _drive(tk.initial_state(), [ready(), glyph(1, True)], c)
    assert expanded.phase is Phase.EXPANDED and c.writes == [True]
    to_incapable = _drive(expanded, [ModeRequested(GEN, 7, INCAPABLE, False)], c)
    assert to_incapable.phase is Phase.DORMANT and to_incapable.mode_id == INCAPABLE and not to_incapable.requested
    back = _drive(to_incapable, [ModeRequested(GEN, 8, CAPABLE, True)], c)
    # Full display is only ever the user's request: switching back to a capable mode starts ordinary.
    assert back.phase is Phase.ORDINARY and not back.requested and c.writes == [True, False]


def test_immediate_rejects_leave_mode_and_expansion_intact():
    accept = _Coordinator()
    expanded = _drive(tk.initial_state(), [ready(requested=True)], accept)
    reject = _Coordinator(mode=False, transfer=False)
    after_mode = _drive(expanded, [ModeRequested(GEN, 7, INCAPABLE, False)], reject)
    assert after_mode.phase is Phase.EXPANDED and after_mode.mode_id == CAPABLE and after_mode.requested
    after_transfer = _drive(after_mode, [TransferRequested(GEN, after_mode.activation, 9, B, True)], reject)
    assert after_transfer.phase is Phase.EXPANDED and after_transfer.display == A
    assert reject.writes == []


def test_failed_enter_never_loops():
    c = _Coordinator(prepare=False)
    state = _drive(tk.initial_state(), [ready(requested=True)], c)
    assert state.phase is Phase.ORDINARY and state.requested
    assert state.txn == 1, "a failed restore must not retry until a new edge"


def test_unknown_event_type_is_a_programming_error():
    state = _run([ready()])[0]

    class Bogus:
        generation = GEN

    with pytest.raises(TypeError):
        reduce(state, Bogus())  # type: ignore[arg-type]


def test_reducer_never_mutates_its_input_state():
    state = _run(EXPAND_BY_USER)[0]
    snapshot = repr(state)
    for event in _alphabet(state):
        reduce(state, event)
    assert repr(state) == snapshot
    with pytest.raises(Exception):
        state.phase = Phase.DORMANT  # type: ignore[misc]
