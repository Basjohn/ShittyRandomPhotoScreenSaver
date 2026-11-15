"""A transition session inside the invisible live check (``tools/visualizer_live_check.py --transition-session``).

One saver process cycles through a named list of transitions in a fixed order (one per image change) and each
transition's window is cut from the frame trace afterwards, so a transition's figures cost one image interval instead of
one process.

* **Runner side** (``TransitionSessionDriver``): before every image-change batch the engine's own fixed-transition seam
  (``ScreensaverEngine._prepare_random_transition_if_needed``) reads ``transitions.type``; the driver writes the current
  name of the list there first (through the engine's SettingsManager, as the C-key cycle does) and records the call. Every
  transition run the Quick scene is handed (``QuickSceneController.set_transition_run``) is recorded with its run id and
  the transition it resolved to, so the parent never infers which run was which from the order alone. The cursor moves on
  only when a run of the written name starts: the product's own startup reveal is a Crossfade run that follows the first
  call (a real 15 Nov check lost the first name to it), and it must not consume a name of the list.
* **Frames:** a saver without a Visualizer records no ``FRAME_SWAP`` (the scene records it as Visualizer evidence only), so
  a window's frame pacing is the spacing of Quick's ``quick_after_rendering`` records (one per rendered frame, the
  render thread's completion of each); ``frame_source`` says so.
* **Window** (``cut_windows``): a run's id rides in the ``auxiliary`` field of the background node's per-frame records
  (``BACKGROUND_RENDER_BEGIN`` 19 and ``BACKGROUND_RENDER_READY`` 23; 0 = no run). A run's window is from the first begin
  record carrying its id to the last ready record carrying it. A run with no begin record, or whose last begin has no
  ready record after it (the trace or the process ended inside it), is **failed**, never measured on a partial window.
* **Attribution:** the planned names are matched to the post-startup runs by what the run resolved to, each name's first
  run; the run ids of the planned order must increase, or the later row fails (an out-of-order session is not trusted).

Everything here is stdlib at import; the product is imported only inside ``install``.
"""
from __future__ import annotations

import json
import statistics
import time
from pathlib import Path

BACKGROUND_RENDER_BEGIN, BACKGROUND_RENDER_READY = 19, 23
QUICK_BEFORE_RENDERING, QUICK_AFTER_RENDERING = 51, 54
LIFECYCLE_BEGIN, LIFECYCLE_END = 62, 63
LATE_MS, HITCH_MS = 25.0, 50.0
SETTLE_S = 4.0                 # after the longest transition completes, before the next image change
STARTUP_LEAD_S = 25.0          # process start to the first image change's transition (a tolerance, not a measurement)


def parse_session_names(text: str) -> list[str]:
    names = [part.strip() for part in str(text).split(",") if part.strip()]
    if not names or len(set(names)) != len(names):
        raise ValueError(f"--transition-session takes distinct transition names, got {text!r}")
    return names


def session_interval_s(durations_ms: list[float], settle_s: float = SETTLE_S) -> int:
    """Image interval for a session: the longest transition completes, then ``settle_s`` of rest."""
    return int(-(-(max(durations_ms) / 1000.0 + settle_s) // 1))


def session_seconds(count: int, interval_s: float) -> float:
    """``--seconds`` for ``count`` transitions: the startup lead, one image interval per transition and one more for the
    last transition to finish and its window to close."""
    return STARTUP_LEAD_S + (count + 1) * interval_s


# -- runner side ----------------------------------------------------------------------------------------------------------

class TransitionSessionDriver:
    """Runner side: sets the next transition before each image change and records every transition run started."""

    def __init__(self, names, *, state_path: Path | None = None, began: float | None = None) -> None:
        self.names = list(names)
        self.state_path = Path(state_path) if state_path is not None else None
        self.began = time.monotonic() if began is None else float(began)
        self.calls: list[dict] = []
        self.runs: list[dict] = []
        self.cursor = 0
        self._pending: str | None = None

    def install(self, *, engine_class=None, scene_class=None, patch=setattr) -> None:
        if engine_class is None:
            from engine.screensaver_engine import ScreensaverEngine as engine_class
        if scene_class is None:
            from rendering.quick.scene_controller import QuickSceneController as scene_class
        driver = self
        prepare = engine_class._prepare_random_transition_if_needed
        set_run = scene_class.set_transition_run

        def prepared(engine, *args, **kwargs):
            driver.advance(engine)
            return prepare(engine, *args, **kwargs)

        def recorded_run(scene, run, *args, **kwargs):
            result = set_run(scene, run, *args, **kwargs)
            if run is not None and result:
                driver.record_run(run)
            return result

        patch(engine_class, "_prepare_random_transition_if_needed", prepared)
        patch(scene_class, "set_transition_run", recorded_run)

    def advance(self, engine) -> str:
        """Write the next name into ``transitions.type`` (the seam reads it right after) and record the call."""
        name = self.names[self.cursor % len(self.names)]
        self._pending = name
        settings = engine.settings_manager
        transitions = settings.get("transitions")
        transitions = dict(transitions) if isinstance(transitions, dict) else {}
        transitions["type"] = name
        transitions["random_always"] = False
        settings.set("transitions", transitions)
        self.calls.append({"call": len(self.calls), "name": name, "at": self._now()})
        self._flush()
        return name

    def record_run(self, run) -> None:
        request = run.request
        setting_name = None
        try:
            from rendering.transition_registry import get_transition_descriptor_for_runtime_identity

            descriptor = get_transition_descriptor_for_runtime_identity(request.transition_id)
            setting_name = descriptor.setting_name if descriptor is not None else None
        except Exception:                                     # a lookup failure must not stop the saver
            pass
        self.runs.append({"run_id": int(run.run_id), "transition_id": str(request.transition_id), "name": setting_name,
                          "duration_ms": int(request.duration_ms), "at": self._now()})
        if self._pending is not None and self._pending in (setting_name, str(request.transition_id)):
            self.cursor += 1                       # the written transition started: the next call writes the next name
        self._pending = None
        self._flush()

    def _now(self) -> float:
        return round(time.monotonic() - self.began, 3)

    def state(self) -> dict:
        return {"names": self.names, "calls": self.calls, "runs": self.runs}

    def _flush(self) -> None:
        if self.state_path is not None:
            self.state_path.write_text(json.dumps(self.state(), indent=1), encoding="utf-8")


# -- parent side: the windows -----------------------------------------------------------------------------------------------

def read_trace_events(path: Path) -> list[tuple[int, int, int, int, int]]:
    """``(ts_ns, event, screen, revision, aux)`` of every record of the trace chain, time ordered."""
    from tools.frame_trace_report import HEADER, RECORD, _read_trace_chain

    raw, _segments = _read_trace_chain(path)
    events = []
    for index in range((len(raw) - HEADER.size) // RECORD.size):
        ts, event, screen, revision, _logical, aux = RECORD.unpack_from(raw, HEADER.size + index * RECORD.size)
        events.append((int(ts), int(event), int(screen), int(revision), int(aux)))
    events.sort(key=lambda item: item[0])
    return events


def startup_end_ns(events) -> int | None:
    """The first lifecycle-end record (startup finished); None when the trace holds none."""
    return next((ts for ts, event, *_ in events if event == LIFECYCLE_END), None)


def cut_windows(events) -> dict[int, dict]:
    """``{run_id: {"begin_ns", "end_ns", "complete", "reason"}}`` from the background node's per-frame records.

    ``complete`` is False (with a ``reason``) when no ready record follows the run's last begin record."""
    first_begin, last_begin, last_ready = {}, {}, {}
    for ts, event, _screen, _revision, aux in events:
        if aux <= 0:
            continue
        if event == BACKGROUND_RENDER_BEGIN:
            first_begin.setdefault(aux, ts)
            last_begin[aux] = ts
        elif event == BACKGROUND_RENDER_READY:
            last_ready[aux] = ts
    windows = {}
    for run_id, begin in first_begin.items():
        end = last_ready.get(run_id)
        complete = end is not None and end >= last_begin[run_id]
        windows[run_id] = {"begin_ns": begin, "end_ns": end if complete else None, "complete": complete,
                           "reason": None if complete else ("no end record (BACKGROUND_RENDER_READY) after the last "
                                                            "begin record: the trace or the process ended inside the run")}
    return windows


def _stats(values):
    if not values:
        return None
    ordered = sorted(values)
    return {"median": round(statistics.median(values), 2),
            "p90": round(ordered[min(len(ordered) - 1, int(0.9 * len(ordered)))], 2)}


def window_figures(events, begin_ns: int, end_ns: int, *, samples=None, process_summary=None) -> dict:
    """The window's figures, named as ``tools/preflip_pack.extract_figures`` stores them: fps, render time (Quick's
    render phase), frame time (the gap between rendered frames, stored as the swap gap) median and p90, late frames, hitches and the saver's CPU in the window."""
    swaps = [ts for ts, event, *_ in events if event == QUICK_AFTER_RENDERING and begin_ns <= ts <= end_ns]
    gaps = [(b - a) / 1e6 for a, b in zip(swaps, swaps[1:])]
    span = (swaps[-1] - swaps[0]) / 1e9 if len(swaps) > 1 else 0.0
    render, opened = [], None
    for ts, event, *_ in events:
        if not begin_ns <= ts <= end_ns:
            continue
        if event == QUICK_BEFORE_RENDERING:
            opened = ts
        elif event == QUICK_AFTER_RENDERING and opened is not None:
            render.append((ts - opened) / 1e6)
            opened = None
    fps = round((len(swaps) - 1) / span, 1) if span > 0 else None
    late, hitches = sum(g > LATE_MS for g in gaps), sum(g > HITCH_MS for g in gaps)
    figures = {
        "fps": fps, "frames": len(swaps), "frame_source": "quick_after_rendering", "window_s": round((end_ns - begin_ns) / 1e9, 2),
        "quick_render_ms": _stats(render), "swap_gap_ms": _stats(gaps),
        "late_frames": late, "hitches": hitches,
        "steady_late_pct": round(100.0 * late / len(gaps), 1) if gaps else None,
        "hitches_per_min": round(60.0 * hitches / span, 2) if span > 0 else None,
        "process": None,
    }
    if samples and process_summary is not None:
        figures["process"] = process_summary(samples, (begin_ns, end_ns), fps)
    return figures


def analyse_session(events, state: dict | None, planned: list[str], *, samples=None, process_summary=None,
                    returncode: int | None = 0) -> dict:
    """The session's rows in planned order: ``{"rows": [{"name", "status", "reason", "run_id", ...figures}], "failures"}``.

    ``state`` is the runner's ``transition_session.json``; ``planned`` the names in the order they must run."""
    rows, failures = [], []
    if returncode not in (0, None):
        failures.append(f"the saver process exited with code {returncode}")
    if state is None:
        failures.append("the runner left no transition_session.json (the driver never armed)")
        state = {"runs": [], "calls": []}
    startup = startup_end_ns(events)
    windows = cut_windows(events)
    runs = sorted(state.get("runs", []), key=lambda run: run["run_id"])
    # A run whose first frame precedes the end of startup is the product's own reveal, not a session transition.
    if startup is not None:
        runs = [run for run in runs
                if run["run_id"] not in windows or windows[run["run_id"]]["begin_ns"] >= startup]
    claimed, last_run_id = set(), 0
    for name in planned:
        run = next((r for r in runs if r["run_id"] not in claimed and name in (r.get("name"), r.get("transition_id"))),
                   None)
        row = {"name": name, "status": "ok", "reason": None, "run_id": None}
        if run is None:
            row.update(status="failed", reason="no transition run for this name was recorded after startup")
        else:
            claimed.add(run["run_id"])
            window = windows.get(run["run_id"])
            row.update(run_id=run["run_id"], duration_ms=run.get("duration_ms"))
            if window is None:
                row.update(status="failed", reason="the run has no begin record in the frame trace")
            elif not window["complete"]:
                row.update(status="failed", reason=window["reason"])
            elif run["run_id"] < last_run_id:
                row.update(status="failed", reason=f"run {run['run_id']} came before the previous planned transition's "
                                                   f"run {last_run_id}: the session ran out of order")
            else:
                row.update(window_figures(events, window["begin_ns"], window["end_ns"], samples=samples,
                                          process_summary=process_summary))
                row["begin_ns"], row["end_ns"] = window["begin_ns"], window["end_ns"]
            last_run_id = max(last_run_id, run["run_id"])
        if row["status"] != "ok":
            failures.append(f"{name}: {row['reason']}")
        rows.append(row)
    return {"rows": rows, "failures": failures, "runs_seen": len(runs), "calls": len(state.get("calls", []))}
