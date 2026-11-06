"""Seamless Studio clips: the loop period a clip carries, and the ticks of its later passes (mode-neutral).

A shipped clip (``tools/build_studio_clips.py``) is a *loop*: its audio and lanes are baked so the first frame follows
the last one as the recording's own next moment (``tools/studio_clip_loop.py``). The Studio then plays it as one
unbroken timeline instead of restarting: an evaluator steps its production logic on through the wrap over the
clip's ticks again, shifted by whole periods, so the simulation state it carries (bubbles, smoothing, history) never
resets and the preview does not jump.

This module owns the parts every evaluator shares:

* ``loop_period`` / ``tiled_features``: the period a compact clip names, and its frames repeated back to back (the
  analysis workers prime their engine with the pass before the clip, and the tests replay several passes).
* ``Cycles``: the unrolled tick sequence of a looped input, ``tick(i)`` for the ``i``-th tick of an endless run, built
  one pass at a time with the input's own ``shifted(tick, cycle)``.
* ``Anchor``: how a transport instant that may be many passes in maps onto the history an evaluator really replays.
  A rewind (an edit, a seek, new answers) replays from the start of the pass the instant is in, as it always replayed
  from the start of the clip (never every pass played so far); playback after it carries the state across each wrap.
* The tick shifts (``shift_clock_tick``, ``shift_advance``, ``shift_served``): the later passes of a recorded input,
  its times moved whole periods on and its onset serials kept strictly increasing, as a replay of the unbroken
  recording would number them.
"""
from __future__ import annotations

import math
import re
from dataclasses import replace
from pathlib import Path
from typing import Any, Callable, Sequence


def loop_period(path: str | Path) -> float:
    """The loop period (seconds) a compact clip names, 0.0 for a clip that is not a loop (a native recording)."""
    from widgets.spotify_visualizer.compact_clip import is_compact, read_header
    if not is_compact(path):
        return 0.0
    loop = (read_header(path).get("provenance") or {}).get("loop") or {}
    return float(loop.get("period_s", 0.0))


PREROLL_S = 2.0       # the end of the loop an analysis worker replays first (measured: one second already settles it)


def primed(features: Sequence, frames: Sequence, clip_path) -> tuple[list, float | None]:
    """``(frames to replay, the clip's start in seconds)`` for an analysis worker.

    A loop is analysed as it plays: the engine and the modes' analysis first replay the last ``PREROLL_S`` of the
    loop (placed before its start), so the first ticks recorded are the ones a running loop has after its wrap, not a
    cold start. The start is ``None`` (and ``frames`` unchanged) for anything that is not the whole of a loop clip:
    a native recording, or a clip cut short (``features`` is every frame of the clip, ``frames`` the ones replayed)."""
    period = loop_period(clip_path)
    if period <= 0.0 or not features or len(frames) != len(features):
        return list(frames), None
    return preroll_features(features, period, PREROLL_S) + list(frames), features[0].timestamp_us / 1e6


def mark_loop(data: dict, clip_path, start: float | None) -> dict:
    """A worker's record of a clip, marked as a loop when ``primed`` found one (``start`` is not None): its period
    (also its duration, so the transport wraps there) is ``loop_period``."""
    if start is not None:
        period = loop_period(clip_path)
        data["loop_period"] = period
        data["duration"] = period
    return data


def looped_fixture(fixture, data):
    """``fixture`` flagged as a seamless loop when the worker's ``data`` says the clip is one."""
    return replace(fixture, loop=True) if float(data.get("loop_period", 0.0) or 0.0) > 0.0 else fixture


def loop_serial_span(frames) -> int:
    """Capture serials one pass of ``frames`` spans (so a later pass keeps them strictly increasing)."""
    serials = [f.capture_history.capture_serial for f in frames if f.capture_history is not None]
    return (max(serials) - min(serials) + 1) if serials else 0


def shifted_frame(frame, *, seconds: float, serials: int):
    """``frame`` ``seconds`` later with its capture serial advanced (one tiled pass)."""
    history = frame.capture_history
    if history is not None:
        history = replace(history, capture_serial=history.capture_serial + serials)
    return replace(frame, timestamp_us=frame.timestamp_us + int(round(seconds * 1e6)), capture_history=history)


def tiled_features(frames: Sequence, period: float, passes: int = 2) -> list:
    """``frames`` (one loop pass) repeated ``passes`` times back to back: the timeline the production replay would
    see if the clip played on. The first pass is returned unchanged."""
    span = loop_serial_span(frames)
    out = list(frames)
    for k in range(1, passes):
        out.extend(shifted_frame(f, seconds=k * period, serials=k * span) for f in frames)
    return out


def preroll_features(frames: Sequence, period: float, seconds: float) -> list:
    """The last ``seconds`` of one pass, placed *before* the pass (one period earlier): the engine an analysis
    worker primes before the clip starts is the one a playing loop would have at its wrap."""
    if seconds <= 0.0 or not frames:
        return []
    last = frames[-1].timestamp_us
    keep = [f for f in frames if (last - f.timestamp_us) / 1e6 <= seconds]
    span = loop_serial_span(frames)
    return [shifted_frame(f, seconds=-period, serials=-span) for f in keep]


class Anchor:
    """Maps the transport's unrolled time onto an evaluator's replayed history (``base`` whole periods back)."""

    def __init__(self, period: float = 0.0) -> None:
        self.period = float(period)
        self.base = 0

    @property
    def looped(self) -> bool:
        return self.period > 0.0

    def reset(self) -> None:
        self.base = 0

    def virtual(self, time: float) -> float:
        """The history time of transport time ``time`` under the current base."""
        return time - self.base * self.period

    def rebase(self, time: float) -> float:
        """Re-anchor for a replay from the start (an edit, a seek, new answers): the history begins at the start of the
        pass ``time`` is in, exactly as a replay always began at the start of the clip, so a rewind costs what it
        always cost however many passes have played. The passes after it carry the state across their wraps.
        Returns the history time to replay to."""
        cycle = int(math.floor(max(0.0, time) / self.period + 1e-9)) if self.looped else 0
        self.base = cycle
        return self.virtual(time)

    def sync(self, period: float) -> "Anchor":
        """This anchor for an input of ``period`` (a different period starts a fresh one)."""
        if float(period) != self.period:
            return Anchor(period)
        return self


class Cycles:
    """The endless tick sequence of a looped input: ``head`` (ticks before the clip's start, which only the first
    pass has: an analysis lead-in), then ``body`` (the clip's own ticks) and the body again, tick ``i`` of pass ``k``
    shifted by ``shifted(tick, k)``.

    Only the passes asked for are built (the two latest are kept), so a long run costs the same as a short one.
    ``len`` is effectively unbounded."""

    UNBOUNDED = 1 << 40

    def __init__(self, head: Sequence, body: Sequence, shifted: Callable[[Any, int], Any]) -> None:
        self._head = tuple(head)
        self._body = tuple(body)
        self._shifted = shifted
        self._passes: dict[int, tuple] = {}

    @property
    def per_pass(self) -> int:
        return len(self._body)

    def __len__(self) -> int:
        return self.UNBOUNDED if self._body else len(self._head)

    def __getitem__(self, index: int):
        index = int(index)
        if index < len(self._head):
            return self._head[index]
        cycle, offset = divmod(index - len(self._head), len(self._body))
        built = self._passes.get(cycle)
        if built is None:
            built = self._body if cycle == 0 else tuple(self._shifted(t, cycle) for t in self._body)
            self._passes[cycle] = built
            for old in [c for c in self._passes if c < cycle - 1]:
                del self._passes[old]
        return built[offset]

    def __iter__(self):
        index = 0
        while True:
            yield self[index]
            index += 1


# ----------------------------------------------------------------------------------- tick shifts
def shift_clock_tick(tick, seconds: float):
    """A tick that carries its own times (``now``, typed events ``(timestamp, kind, strength)``, the authoritative
    frame time): Bubble's ``TickInput`` and Sphere's ``EngineTick``."""
    return replace(
        tick, now=tick.now + seconds,
        events=tuple((float(t) + seconds, kind, strength) for t, kind, strength in tick.events),
        authoritative=tick.authoritative + seconds if tick.authoritative > 0.0 else tick.authoritative)


def onset_span(serials, base: int = 0) -> int:
    """Serials one pass of onsets advances a runtime that starts having seen ``base``."""
    serials = [int(s) for s in serials]
    return (max(serials) - int(base)) if serials else 0


def shift_advance(step, seconds: float, serials: int):
    """A frame runtime's ``AdvanceInput`` (Waveform, Extruded Bubble): ``now`` and its musical onsets."""
    return replace(step, now=step.now + seconds,
                   onsets=tuple(replace(o, timestamp=o.timestamp + seconds, serial=o.serial + serials)
                                for o in step.onsets))


_ONSET_CALL = re.compile(r"^get_onset_events\[\[(\d+)\], \[\]\]$")


def _shift_onsets(value, seconds: float, serials: int):
    if isinstance(value, dict):
        if value.get("data") == "MusicalOnset":
            fields = dict(value["fields"])
            fields["timestamp"] = fields["timestamp"] + seconds
            fields["serial"] = fields["serial"] + serials
            return {"data": "MusicalOnset", "fields": fields}
        return {k: _shift_onsets(v, seconds, serials) for k, v in value.items()}
    if isinstance(value, list):
        return [_shift_onsets(v, seconds, serials) for v in value]
    return value


def shift_answers(answers, seconds: float, serials: int) -> dict:
    """Recorded engine answers (``replay_engine.encode_answer`` form) one or more passes on: the authoritative frame
    time, the transient bus's onsets (time and serial) and the onset query's own ``after_serial`` argument, which is
    part of the answer's key. Every other answer (lanes, bars, arrays by identity) is the pass's own."""
    out = {}
    for key, value in answers.items():
        if key == "get_latest_authoritative_frame":
            items = list(value["tuple"])
            if items[0] > 0.0:
                items[0] = items[0] + seconds
            value = {"tuple": items}
        else:
            call = _ONSET_CALL.match(key)
            if call:
                key = f"get_onset_events[[{int(call.group(1)) + serials}], []]"
                value = _shift_onsets(value, seconds, serials)
        out[key] = value
    return out


def served_span(steps) -> int:
    """Onset serials one pass of recorded engine answers advances the runtime that reads them."""
    base, top = None, 0

    def scan(value):
        nonlocal top
        if isinstance(value, dict):
            if value.get("data") == "MusicalOnset":
                top = max(top, int(value["fields"]["serial"]))
            else:
                for item in value.values():
                    scan(item)
        elif isinstance(value, list):
            for item in value:
                scan(item)
    for step in steps:
        for key, value in step.answers.items():
            call = _ONSET_CALL.match(key)
            if call:
                if base is None:
                    base = int(call.group(1))
                scan(value)
    return max(0, top - (base or 0))


def shift_served(tick, seconds: float, serials: int):
    """An engine-answer ``ServedTick`` one or more passes on."""
    return replace(tick, now=tick.now + seconds, answers=shift_answers(tick.answers, seconds, serials))


def unrolled_ticks(inputs, duration: float):
    """The ticks a history replays for ``inputs``: its tuple for one pass, or the endless ``Cycles`` when the input is
    a loop (``period`` > 0): the ticks before the clip's start once, then the clip's own ticks pass after pass
    (``inputs.shifted(tick, pass)`` moves a tick whole passes on)."""
    ticks = tuple(inputs.steps(duration))
    if float(getattr(inputs, "period", 0.0) or 0.0) <= 0.0 or not ticks:
        return ticks
    origin = float(getattr(inputs, "_origin", 0.0))
    head = tuple(t for t in ticks if t.now < origin - 1e-9)
    body = tuple(t for t in ticks if t.now >= origin - 1e-9)
    return Cycles(head, body, inputs.shifted) if body else ticks


__all__ = ["Anchor", "Cycles", "PREROLL_S", "loop_period", "looped_fixture", "mark_loop", "primed", "loop_serial_span", "onset_span", "preroll_features", "served_span",
           "shift_advance", "shift_answers", "shift_clock_tick", "shift_served", "shifted_frame", "tiled_features",
           "unrolled_ticks"]
