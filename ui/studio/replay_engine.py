"""The engine side of a Studio evaluator that drives a mode's unchanged production logical path (mode-neutral).

A Studio never re-implements a mode's simulation, timing or capture. It configures a production
``VisualizerRuntimeController`` the way the production offline replay does and serves the production step one
*engine tick* at a time: what the beat engine would answer the mode's step at that instant (post-DSP lanes, typed
events, the authoritative source frame). ``FixtureBeatEngine`` is the production replay engine (no capture, no
worker thread) with those getters answered from the tick; its event scheduler is the production scheduler with the
fixture's clock in place of the process clock (the offline replay pins the process clock instead; a Studio runs
inside the app and must not).

A mode whose step also *consumes the engine's own processing* (the Spectrum family: ``consume_engine_bars`` ticks the
engine and reads its smoothed, shape-processed bars, all computed on the process clock) cannot be served from
authored lanes. For those, the out-of-process worker records, per production tick, every answer the engine gave the
step (``EngineAnswerRecorder``), and the Studio serves exactly those answers back to the same production step
(``RecordedEngineAnswers``). Answers travel as JSON through ``encode_answer`` / ``decode_answer``.
"""
from __future__ import annotations

from dataclasses import dataclass, fields, is_dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class EngineTick:
    """One authored tick's engine answers. ``None`` fields fall through to the production replay engine."""

    now: float
    playing: bool
    bubble: tuple | None = None                          # get_bubble_energy_bands: bass, mid, high, overall
    transient: tuple = (0.0, 0.0, 0.0, False, "", 0.0)   # get_transient_energy_bands fields, in order
    events: tuple = ()                                   # typed events fed this tick: (timestamp, kind, strength)
    authoritative: float = 0.0                           # latest authoritative source frame time (0: none)
    fresh: bool = True                                   # that frame belongs to the engine's current activation
    scheduler: bool = True                               # the engine serves its event scheduler (schema 2)
    energy: tuple | None = None                          # get_energy_bands
    live: tuple | None = None                            # get_live_pre_agc_energy_bands
    musical_level: tuple | None = None                   # get_musical_level: (loudness, presence)
    musical_intensity: float | None = None               # get_musical_intensity
    spectrum: tuple | None = None                        # get_pre_agc_analysis_spectrum


def clocked_scheduler():
    """The production event scheduler with its clock set to fixture time (consume-once, ages as live)."""
    from widgets.spotify_visualizer.transient_bus import OnsetEvent, TransientEventScheduler

    class ClockedEventScheduler(TransientEventScheduler):
        now = 0.0

        def consume_next(self, event_type: str, max_age_s: float = 0.5):
            # TransientEventScheduler.consume_next with ``time.time()`` replaced by the fixture clock.
            cutoff = self.now - max_age_s
            best = None
            for entry in self._ring:
                if (not entry.consumed and entry.event.event_type == event_type
                        and entry.event.timestamp > cutoff):
                    if best is None or entry.event.timestamp < best.event.timestamp:
                        best = entry
            if best is not None:
                best.consumed = True
                return OnsetEvent(timestamp=best.event.timestamp, event_type=best.event.event_type,
                                  strength=best.event.strength)
            return None
    return ClockedEventScheduler()


def fixture_engine_type():
    from widgets.spotify_visualizer.energy_bands import EnergyBands
    from widgets.spotify_visualizer.feature_replay import ReplayBeatEngine
    from widgets.spotify_visualizer.transient_bus import OnsetEvent, TransientEnergyBands

    def bands(values):
        return EnergyBands(*(float(v) for v in values))

    class FixtureBeatEngine(ReplayBeatEngine):
        """The production replay engine (no capture, no worker thread) serving one fixture tick."""

        def __init__(self, bar_count: int) -> None:
            super().__init__(bar_count)
            self.reset_ticks()

        def reset_ticks(self) -> None:
            self._tick: Any = None
            self._fixture_scheduler = clocked_scheduler()

        def serve(self, tick) -> None:
            self._tick = tick
            self._fixture_scheduler.now = float(tick.now)
            for timestamp, kind, strength in tick.events:
                self._fixture_scheduler.feed(OnsetEvent(timestamp=float(timestamp), event_type=str(kind),
                                                        strength=float(strength)))

        def _field(self, name):
            return None if self._tick is None else getattr(self._tick, name, None)

        def get_bubble_energy_bands(self):
            value = self._field("bubble")
            return bands(value) if value is not None else EnergyBands()

        def get_energy_bands(self):
            value = self._field("energy")
            return bands(value) if value is not None else super().get_energy_bands()

        def get_live_pre_agc_energy_bands(self):
            value = self._field("live")
            return bands(value) if value is not None else EnergyBands()

        def get_musical_level(self):
            value = self._field("musical_level")
            return tuple(float(v) for v in value) if value is not None else (0.0, 0.0)

        def get_musical_intensity(self):
            value = self._field("musical_intensity")
            return float(value) if value is not None else 0.0

        def get_pre_agc_analysis_spectrum(self):
            value = self._field("spectrum")
            return tuple(float(v) for v in value) if value is not None else ()

        def get_transient_energy_bands(self):
            if self._tick is None:
                return TransientEnergyBands()
            bass, mid, high, detected, kind, strength = self._tick.transient
            return TransientEnergyBands(bass_transient=float(bass), mid_transient=float(mid),
                                        high_transient=float(high), onset_detected=bool(detected),
                                        onset_type=str(kind), onset_strength=float(strength))

        def get_event_scheduler(self):
            return self._fixture_scheduler if self._tick is not None and self._tick.scheduler else None

        def get_latest_authoritative_frame(self):
            tick = self._tick
            if tick is None or tick.authoritative <= 0.0:
                return 0.0, -1, -1
            if not tick.fresh:
                return float(tick.authoritative), -1, -1
            return float(tick.authoritative), self.get_generation_id(), self.get_activation_id()
    return FixtureBeatEngine


def offline_controller(engine, mode_id: str, settings):
    """A production runtime controller for ``mode_id`` configured exactly as the production offline replay
    configures one (``feature_replay.configure_offline_controller``), on ``engine``."""
    from widgets.spotify_visualizer.feature_replay import configure_offline_controller
    from widgets.spotify_visualizer.runtime_controller import VisualizerRuntimeController
    controller = VisualizerRuntimeController(runtime_generation=0, initial_mode=mode_id,
                                             engine_factory=lambda _bars: engine)
    controller.engine = engine
    configure_offline_controller(controller, mode_id, settings=settings)
    return controller


def recorded_answers(engine, feature) -> dict:
    """What the production replay engine answers after accepting ``feature`` (for the recorded-clip workers)."""
    def four(value):
        return [float(value.bass), float(value.mid), float(value.high), float(value.overall)]
    transient = engine.get_transient_energy_bands()
    ts, generation, activation = engine.get_latest_authoritative_frame()
    real = feature.real
    return {
        "playing": bool(feature.playing),
        "bubble": four(engine.get_bubble_energy_bands()),
        "energy": four(engine.get_energy_bands()),
        "live": four(engine.get_live_pre_agc_energy_bands()),
        "musical_level": [float(v) for v in engine.get_musical_level()],
        "musical_intensity": float(engine.get_musical_intensity()),
        "spectrum": [float(v) for v in engine.get_pre_agc_analysis_spectrum()],
        "transient": [float(transient.bass_transient), float(transient.mid_transient),
                      float(transient.high_transient), bool(transient.onset_detected),
                      str(transient.onset_type), float(transient.onset_strength)],
        "events": ([[feature.timestamp_us / 1e6, e.kind, float(e.strength)] for e in real.events]
                   if real is not None else []),
        "authoritative": float(ts),
        "fresh": bool(generation == engine.get_generation_id() and activation == engine.get_activation_id()),
        "scheduler": engine.get_event_scheduler() is not None,
    }


# ---------------------------------------------------------------------- recorded engine answers
def _answer_types() -> dict[str, type]:
    """The engine value types an answer may carry (anything else is refused when recorded)."""
    from widgets.spotify_visualizer.energy_bands import EnergyBands
    from widgets.spotify_visualizer.transient_bus import MusicalOnset, TransientEnergyBands
    return {"EnergyBands": EnergyBands, "TransientEnergyBands": TransientEnergyBands, "MusicalOnset": MusicalOnset}


class RecordedArrays:
    """Worker side: the distinct array objects the engine answered, numbered by *identity*.

    An engine hands out the same array object while its source is unchanged (the capture history between capture
    serials) and a mode may tell "the same source" by identity (Oscilloscope's trace rebuild). Each distinct object
    gets one number for the whole recording (a reference is held, so an id is never reused); the answers carry the
    number and the arrays travel once, as raw bytes (``payload``), never as JSON floats."""

    def __init__(self) -> None:
        self._index: dict[int, int] = {}
        self._arrays: list = []

    def __len__(self) -> int:
        return len(self._arrays)

    def number(self, array) -> int:
        key = id(array)
        if key not in self._index:
            self._index[key] = len(self._arrays)
            self._arrays.append(array)
        return self._index[key]

    def payload(self) -> dict:
        """``{"dtypes", "shapes", "blob"}``: every array's dtype and shape and their bytes back to back."""
        import numpy as np
        dtypes, shapes, parts = [], [], []
        for array in self._arrays:
            array = np.asarray(array)
            dtypes.append(array.dtype.str)
            shapes.append(list(array.shape))
            parts.append(np.ascontiguousarray(array).tobytes())
        return {"dtypes": dtypes, "shapes": shapes, "blob": b"".join(parts)}


def served_arrays(payload: Mapping[str, Any] | None, blob: bytes | None = None) -> tuple:
    """Studio side: one read-only array per recorded number (views on one bytes blob, as the engine's own
    ``np.frombuffer`` arrays are), decoded once, so every answer naming a number is the same object."""
    if not payload:
        return ()
    import numpy as np
    data = payload["blob"] if blob is None else blob
    out, offset = [], 0
    for dtype, shape in zip(payload["dtypes"], payload["shapes"]):
        kind = np.dtype(dtype)
        count = 1
        for size in shape:
            count *= int(size)
        out.append(np.frombuffer(data, dtype=kind, count=count, offset=offset).reshape(shape))
        offset += count * kind.itemsize
    if offset != len(data):
        raise ValueError("Recorded arrays do not match their payload")
    return tuple(out)


def encode_answer(value: Any, arrays: RecordedArrays | None = None) -> Any:
    """A JSON form of one engine answer that ``decode_answer`` turns back into an equal value of the same types
    (floats round-trip exactly through JSON). With ``arrays`` a NumPy array is recorded by identity (its number).
    Unknown types raise: an answer is never approximated."""
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, list):
        return {"list": [encode_answer(v, arrays) for v in value]}
    if isinstance(value, tuple):
        return {"tuple": [encode_answer(v, arrays) for v in value]}
    if isinstance(value, dict):
        return {"dict": [[str(k), encode_answer(v, arrays)] for k, v in value.items()]}
    name = type(value).__name__
    if is_dataclass(value) and _answer_types().get(name) is type(value):
        return {"data": name, "fields": {f.name: encode_answer(getattr(value, f.name), arrays)
                                         for f in fields(value)}}
    if arrays is not None and type(value).__name__ == "ndarray" and type(value).__module__ == "numpy":
        return {"array": arrays.number(value)}
    raise TypeError(f"Unrecordable engine answer of type {type(value).__qualname__}")


def decode_answer(data: Any, arrays: tuple = ()) -> Any:
    if not isinstance(data, dict):
        return data
    if "array" in data:
        return arrays[int(data["array"])]
    if "list" in data:
        return [decode_answer(v, arrays) for v in data["list"]]
    if "tuple" in data:
        return tuple(decode_answer(v, arrays) for v in data["tuple"])
    if "dict" in data:
        return {k: decode_answer(v, arrays) for k, v in data["dict"]}
    return _answer_types()[data["data"]](**{k: decode_answer(v, arrays) for k, v in data["fields"].items()})


def _answer_key(name: str, args: tuple, kwargs: Mapping[str, Any]) -> str:
    if not args and not kwargs:
        return name
    import json
    return name + json.dumps([list(args), sorted(kwargs.items())], default=repr)


# Calls that change the engine (or ask it to do work) rather than read it; a served step never performs them.
def _is_command(name: str) -> bool:
    return name == "tick" or name.startswith(("set_", "reset_", "force_", "ensure_", "acquire", "release", "wake"))


class EngineAnswerRecorder:
    """Worker side: stands in for the engine during one production step and records every answer it gives.

    Read-only getters are recorded once per tick by name (and arguments); a getter answering two different values
    within one tick would make the served step ambiguous, so that raises. Commands (``tick``, ``set_*``, ...) run
    on the real engine and are listed in call order. NumPy arrays are numbered by identity in ``arrays`` (one
    ``RecordedArrays`` for the whole recording)."""

    def __init__(self, engine) -> None:
        object.__setattr__(self, "_engine", engine)
        object.__setattr__(self, "arrays", RecordedArrays())
        object.__setattr__(self, "answers", {})
        object.__setattr__(self, "commands", [])

    def begin(self) -> None:
        object.__setattr__(self, "answers", {})
        object.__setattr__(self, "commands", [])

    def __getattr__(self, name: str):
        value = getattr(self._engine, name)
        if not callable(value):
            raise AttributeError(f"A served step may not read engine attribute {name!r}")
        if _is_command(name):
            def command(*args, **kwargs):
                self.commands.append(name)
                return value(*args, **kwargs)
            return command

        def getter(*args, **kwargs):
            result = value(*args, **kwargs)
            key = _answer_key(name, args, kwargs)
            encoded = encode_answer(result, self.arrays)
            if key in self.answers and self.answers[key] != encoded:
                raise RuntimeError(f"Engine answered {key} twice differently within one tick")
            self.answers[key] = encoded
            return result
        return getter

    def __setattr__(self, name: str, value: Any) -> None:
        raise AttributeError("The engine recorder is read-only")


class RecordedEngineAnswers:
    """Studio side: what the step's engine answers during one served tick (``serve``), from the worker's record.

    Commands are inert (the analysis already ran in the worker). A getter the record lacks falls through to the
    configured ``base`` engine and is counted in ``unrecorded``: a diagnostics-only read (``--viz`` latency
    logging) still answers, and the parity tests require the count to stay zero. ``arrays``: the recording's
    arrays (``served_arrays``), one object per recorded number, so an identity the step checks behaves as live."""

    def __init__(self, base, arrays: tuple = ()) -> None:
        self._base = base
        self._arrays = tuple(arrays)
        self._answers: Mapping[str, Any] = {}
        self._cache: dict[str, Any] = {}
        self.unrecorded = 0

    def serve(self, answers: Mapping[str, Any]) -> None:
        self._answers = answers
        self._cache = {}

    def __getattr__(self, name: str):
        if name.startswith("_"):
            raise AttributeError(name)
        if _is_command(name):
            if not callable(getattr(self._base, name, None)):
                raise AttributeError(name)
            return lambda *args, **kwargs: None

        def getter(*args, **kwargs):
            key = _answer_key(name, args, kwargs)
            if key in self._answers:
                if key not in self._cache:
                    self._cache[key] = decode_answer(self._answers[key], self._arrays)
                value = self._cache[key]
                # A fresh copy of a mutable answer, as the engine hands out (callers may keep or edit it).
                return list(value) if isinstance(value, list) else dict(value) if isinstance(value, dict) else value
            self.unrecorded += 1
            return getattr(self._base, name)(*args, **kwargs)
        if not callable(getattr(self._base, name, None)):
            raise AttributeError(name)
        return getter


# ---------------------------------------------------------------------------- step-state snapshots
def _shared_types() -> tuple:
    import enum
    import threading
    import types
    import weakref
    import numpy as np
    from PySide6.QtCore import QObject
    return (type(threading.RLock()), type(threading.Lock()), QObject, types.FunctionType, types.MethodType,
            types.BuiltinFunctionType, types.ModuleType, type, enum.Enum, np.generic, weakref.ref)


_ATOMS = (int, float, str, bool, bytes, type(None), complex, range, slice)


def _clone(value: Any, memo: dict, shared: tuple) -> Any:
    """A deep copy of plain step state. Locks, QObjects, functions, enums and the ``memo``-seeded objects are
    shared (they hold no per-tick state, or are the owners being restored); anything unknown refuses loudly."""
    if isinstance(value, _ATOMS):
        return value
    key = id(value)
    if key in memo:
        return memo[key]
    if isinstance(value, shared):
        return value
    if isinstance(value, list):
        out: Any = memo.setdefault(key, [])
        out.extend(_clone(item, memo, shared) for item in value)
        return out
    if isinstance(value, dict):
        out = memo.setdefault(key, {} if type(value) is dict else type(value)())
        for k, item in value.items():
            out[_clone(k, memo, shared)] = _clone(item, memo, shared)
        return out
    if isinstance(value, tuple):
        items = tuple(_clone(item, memo, shared) for item in value)
        if all(a is b for a, b in zip(items, value)):
            out = value
        else:
            out = type(value)(*items) if hasattr(value, "_fields") else type(value)(items)
        memo[key] = out
        return out
    if isinstance(value, (set, frozenset)):
        out = memo[key] = type(value)(_clone(item, memo, shared) for item in value)
        return out
    import types
    if isinstance(value, types.MappingProxyType):        # a read-only view (published drives): view a copy
        out = memo[key] = types.MappingProxyType(_clone(dict(value), memo, shared))
        return out
    from collections import deque
    if isinstance(value, deque):
        out = memo[key] = deque((_clone(item, memo, shared) for item in value), maxlen=value.maxlen)
        return out
    import numpy as np
    if isinstance(value, np.ndarray):
        out = memo[key] = value.copy()
        return out
    import shiboken6
    if isinstance(value, shiboken6.Shiboken.Object):
        out = memo[key] = type(value)(value)              # a Qt value type (QColor, QPointF, ...)
        return out
    cls = type(value)
    if hasattr(value, "__dict__") or getattr(cls, "__slots__", None):
        out = memo[key] = object.__new__(cls)
        for name, item in getattr(value, "__dict__", {}).items():
            object.__setattr__(out, name, _clone(item, memo, shared))
        for klass in cls.__mro__:
            for name in getattr(klass, "__slots__", ()):
                if name not in ("__dict__", "__weakref__") and hasattr(value, name):
                    object.__setattr__(out, name, _clone(getattr(value, name), memo, shared))
        return out
    raise TypeError(f"Step state holds an uncopyable {cls.__qualname__}")


class StepState:
    """The per-tick state of a production ``VisualizerRuntimeController`` (its own attributes, its logical tick
    state and its presentation state, the mode runtimes they hold included), captured and put back in place.

    A Studio evaluator rewinds its production step with it instead of configuring a new controller: a capture
    right after configuration (``pristine``) and periodic checkpoints. ``keep`` lists objects that are shared, not
    copied (the engine and the engine-answer view the step reads through)."""

    def __init__(self, controller, keep: tuple = (), *, owners: tuple | None = None) -> None:
        # ``owners``: capture these objects instead of a controller's three (a mode that steps its frame runtime
        # directly, such as Waveform, captures that runtime).
        self._owners = tuple(owners) if owners is not None else (
            controller, controller.logical_tick_state, controller.presentation_state)
        self._keep = tuple(keep)
        self._shared = _shared_types()
        self._state = self._copy({owner: dict(vars(owner)) for owner in self._owners})

    def _copy(self, states):
        memo = {id(obj): obj for obj in self._owners + self._keep}
        return {owner: {name: _clone(value, memo, self._shared) for name, value in state.items()}
                for owner, state in states.items()}

    def restore(self) -> None:
        """Put the captured state back (a fresh copy each time, so the capture stays reusable)."""
        fresh = self._copy(self._state)
        for owner, state in fresh.items():
            owner.__dict__.clear()
            owner.__dict__.update(state)


__all__ = ["EngineAnswerRecorder", "EngineTick", "RecordedArrays", "RecordedEngineAnswers", "StepState",
           "clocked_scheduler", "decode_answer", "encode_answer", "fixture_engine_type", "offline_controller",
           "recorded_answers", "served_arrays"]
