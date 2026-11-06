"""Exact replay without a stall: the shared history mechanism of the Studio evaluators (mode-neutral).

An evaluator that replays a mode's production step over a fixture's ticks (the engine-answer modes, Waveform) mixes
in ``ExactReplay`` and supplies the step and its state; the mixin owns everything about *when* it steps:

* **Checkpoints.** Every ``CHECKPOINT_TICKS`` ticks of an exact history it keeps the step state (``_capture``), per
  values signature, for the current values and the last two, so undo/redo and a seek back resume from the latest
  checkpoint at or before the instant instead of the fixture start.
* **Frame budget.** ``set_frame_budget`` (the Studio's ``EVALUATION_BUDGET_S``) bounds the GUI-thread time one
  evaluation spends stepping. A replay that does not fit continues on the next evaluations (``converging``; the
  controller requests the frames) while the last frame shown stays on screen; the replay it lands is the same exact
  replay (equal fixture, values and time give equal frames).
* **Live gestures.** ``exact=False`` applies a changed signature to the running history at the current instant
  (approximate); the gesture end replays exactly. A change nothing has shown yet (a click, a typed value) is shown
  live-applied on its first frame, and the exact replay starts on the next.

The evaluator provides: ``_ticks`` (the fixture's ticks), ``_tick_time(tick)`` (fixture seconds), ``_step(tick)``
(one production step; sets ``_last`` and ``_last_tick``), ``_capture()`` (a state object with ``restore()``),
``_rewind_to_start(values, signature)`` (the history at the fixture start configured for ``signature``),
``_restyle(values, signature)`` (apply ``signature`` to the running history; ``_approximate`` is already True when it
serves a live, approximate frame and False on an exact replay), and optionally ``_restep()`` (re-run
the current instant under new values), ``_present(values)`` (the frame to show from ``_last``) and ``_can_pause()``.

**Seamless loops** (``ui/studio/clip_loop.py``). When the input is a loop (``_inputs.period`` > 0) ``_ticks`` is the
endless ``Cycles`` of it and the evaluator asks ``_history_time(time)`` for the history time of the transport's
unrolled time: the history plays on through each wrap, its state carried, instead of restarting at zero. A rewind to the
start (a new values signature, a seek, new answers) re-anchors to the pass the instant is in (``Anchor.rebase``), so
it replays what it always replayed; checkpoints older than two passes are dropped, so a long run holds no more than a
short one.
"""
from __future__ import annotations

import math
import time as clock
from typing import Any, Mapping

from ui.studio.clip_loop import Anchor


class ExactReplay:
    CHECKPOINT_TICKS = 90                  # one checkpoint per second of fixture time at the 90 Hz logical cadence
    KEPT_SIGNATURES = 3                    # the current values and the last two (undo / redo stay instant)

    _budget: float | None = None
    _shown: Any = None                     # the frame the last evaluation returned (shown while converging)
    _anchor: Anchor | None = None          # a loop's transport time -> history time (None: not a loop)
    _anchored: Any = None                  # the input ``_anchor`` belongs to
    _unrolled: float = 0.0                 # the transport time of the evaluation in progress

    # hooks -------------------------------------------------------------------
    def _tick_time(self, tick) -> float:
        raise NotImplementedError

    def _step(self, tick) -> None:
        raise NotImplementedError

    def _capture(self):
        raise NotImplementedError

    def _rewind_to_start(self, values: Mapping[str, Any], signature) -> None:
        raise NotImplementedError

    def _restyle(self, values: Mapping[str, Any], signature=None) -> None:
        raise NotImplementedError

    def _restep(self) -> None:
        """Show a change on the current instant without moving time (approximate)."""
        self._step(self._last_tick)

    def _present(self, values: Mapping[str, Any]):
        if self._last is None:
            raise RuntimeError("Fixture produced no logical frame")
        return self._last

    def _can_pause(self) -> bool:
        """Whether a budgeted replay may stop here (something presentable is on screen or in hand)."""
        return True

    def _loop_anchor(self) -> Anchor:
        """The anchor of the input being replayed (a loop has a period; anything else is one plain pass)."""
        inputs = getattr(self, "_inputs", None)
        period = float(getattr(inputs, "period", 0.0) or 0.0)
        if self._anchor is None or self._anchor.period != period or self._anchored is not inputs:
            self._anchor, self._anchored = Anchor(period), inputs
        return self._anchor

    def _history_time(self, time: float) -> float:
        """The history time of the transport's ``time``: the clip's own time, clamped to it, or, for a loop, the
        unrolled time less the passes before the history's anchor."""
        anchor = self._loop_anchor()
        self._unrolled = float(time)
        if anchor.looped:
            if anchor.virtual(float(time)) < 0.0:      # the transport went back past the anchor (a seek)
                anchor.reset()
            if self._index == 0 and self._last is None:    # a history not yet started begins at this pass
                anchor.rebase(float(time))
            return max(0.0, anchor.virtual(float(time)))
        return max(0.0, min(float(time), self.fixture.duration))

    # state -------------------------------------------------------------------
    def _reset_history(self) -> None:
        self._ticks: tuple = ()
        self._index = 0                    # the next tick to step
        self._time = -math.inf             # the fixture time the history has been stepped to
        self._last = None
        self._last_tick = None
        self._signature = None
        self._approximate = False          # stepped with values other than the current ones
        self._checkpoints: dict = {}       # signature -> {tick index: checkpoint}
        self._converging = False

    def set_frame_budget(self, seconds: float | None) -> None:
        """The GUI-thread time one evaluation may spend replaying (the Studio sets it; None: replay at once).
        With a budget an exact replay that does not fit continues on the next frames (``converging``) while the
        frame shown stays on screen; the replay it converges to is the same exact replay."""
        self._budget = None if seconds is None else max(0.0, float(seconds))

    @property
    def converging(self) -> bool:
        """An exact replay is still catching up with the requested instant (the Studio asks for another frame)."""
        return self._converging

    # history -------------------------------------------------------------------
    def _best_checkpoint(self, signature, time: float):
        best = None
        for checkpoint in self._checkpoints.get(signature, {}).values():
            if checkpoint[1] <= time + 1e-9 and (best is None or checkpoint[0] > best[0]):
                best = checkpoint
        return best

    def _rewind(self, values: Mapping[str, Any], signature, time: float) -> float:
        """Put the exact history of ``signature`` at the latest checkpoint at or before ``time`` (else at the
        start, configured for it): the replay from there is the replay from the start. Returns the history time to
        replay to (a loop re-anchors to the pass the instant is in when it has to start over)."""
        best = self._best_checkpoint(signature, time)
        anchor = self._loop_anchor()
        if best is None and anchor.looped:
            time = anchor.rebase(self._unrolled)
            best = self._best_checkpoint(signature, time)
        if best is not None:
            index, at, state, last, last_tick = best
            state.restore()
            self._index, self._time, self._last, self._last_tick = index, at, last, last_tick
            self._signature = signature
        else:
            self._approximate = False
            self._rewind_to_start(values, signature)
            self._index, self._time, self._last, self._last_tick = 0, -math.inf, None, None
        self._approximate = False
        self.rewinds = getattr(self, "rewinds", 0) + 1
        return time

    def _checkpoint(self) -> None:
        checkpoints = self._checkpoints
        if self._signature not in checkpoints:
            checkpoints[self._signature] = {}
            while len(checkpoints) > self.KEPT_SIGNATURES:
                checkpoints.pop(next(iter(checkpoints)))
        at = self._tick_time(self._ticks[self._index - 1])
        kept = checkpoints[self._signature]
        kept[self._index] = (self._index, at, self._capture(), self._last, self._last_tick)
        per_pass = getattr(self._ticks, "per_pass", 0)
        if per_pass:                       # a loop: nothing older than two passes can be a checkpoint to resume from
            for index in [i for i in kept if i < self._index - 2 * per_pass]:
                del kept[index]

    def _advance(self, time: float, deadline: float | None) -> tuple[bool, int]:
        """Step the ticks up to ``time`` (the first tick always), or until ``deadline``. Returns (reached, ticks
        stepped)."""
        ticks = self._ticks
        stepped = 0
        while self._index < len(ticks):
            tick = ticks[self._index]
            if self._tick_time(tick) > time + 1e-9 and self._last is not None:
                break
            if deadline is not None and stepped and clock.perf_counter() > deadline and self._can_pause():
                self._time = self._tick_time(ticks[self._index - 1])
                return False, stepped
            self._step(tick)
            self._index += 1
            stepped += 1
            if not self._approximate and self._index % self.CHECKPOINT_TICKS == 0:
                self._checkpoint()
        self._time = time
        return True, stepped

    def _replay(self, time: float, values: Mapping[str, Any], signature, *, exact: bool, deadline: float | None):
        """The frame at ``time`` under ``values`` (``signature`` names them) on the configured history."""
        if not exact:
            if time < self._time:
                time = self._rewind(values, signature, time)
            restyled = signature != self._signature
            if restyled:
                self._approximate = True
                self._restyle(values, signature)
            _reached, stepped = self._advance(time, None)
            if restyled and not stepped and self._last_tick is not None:
                self._restep()                         # show the change on this instant (approximate)
            self._converging = False
            self._shown = self._present(values)
            return self._shown
        if signature != self._signature or self._approximate or time < self._time:
            if deadline is not None and signature != self._signature and self._last_tick is not None:
                # A change nothing has shown yet (a click, a typed value): this frame shows it live-applied on
                # the running history; the exact replay starts on the next frame.
                self._approximate = True
                self._restyle(values, signature)
                self._restep()
                self._converging = True
                self._shown = self._present(values)
                return self._shown
            time = self._rewind(values, signature, time)
            if deadline is not None and self._shown is not None and clock.perf_counter() > deadline:
                # The rewind (a configuration build, a state restore) used this frame's budget: stepping starts on
                # the next frame, the frame shown staying meanwhile.
                self._converging = True
                return self._shown
        reached, _stepped = self._advance(time, deadline)
        self._converging = not reached
        if reached or self._shown is None:
            self._shown = self._present(values)
        return self._shown

    def _deadline(self) -> float | None:
        return None if self._budget is None else clock.perf_counter() + self._budget


__all__ = ["ExactReplay"]
