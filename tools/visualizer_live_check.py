"""Live-shape check for a Visualizer mode: the real MC saver, invisible, optionally under a game-like load.

    .venv/Scripts/python tools/visualizer_live_check.py --mode extruded_bubble --preset 1 --load game60
    .venv/Scripts/python tools/visualizer_live_check.py --mode shockwave_grid --preset 2 --seconds 90 --load none

Offline harnesses time a renderer or a logical tick on its own. They cannot show what only the live process does:
Qt's threaded render loop holding the GUI thread in its sync request while the previous frame renders (which made EB
draw a revision ~20 ms old, 2026-10-31), or the render and GUI threads stalling behind the logical thread's GIL-held
Python (every GL call hands the GIL over; while the logical tick runs, the render thread gets about one call through
per 5 ms switch interval). This runs the real ``main_mc.py`` and reports that whole chain, so a new or changed mode
meets it before the operator does.

* **Display safety:** the saver runs from a COPY of ``%APPDATA%\\SRPSS`` (mode, preset and ``--set`` overrides are
  written into the copy only) with its windows at opacity 0, click-through, never topmost and never focused. A guard
  checks every visible window of the run once a second and kills the run if any is not; ``--visible`` opts out (an
  ordinary MC run, one display).
* **Music:** ``--clip`` (default a ~2 min mixed real-music recording) is played as the loopback in real time
  (``tools/visualizer_replay/live_audio.py``): the whole live audio path runs on recorded music, every run hears the
  same passages, and playback is reported as playing whatever the machine itself plays. ``--clip none`` uses the
  machine's own audio and Media state.
* **Load:** ``--load game60`` (the reference case) starts ``tools/gpu_load_generator.py`` and waits for its calibrated
  ``ready`` line before the saver starts; ``--load none`` for an idle or operator-supplied load. Conditions are
  sampled throughout and recorded with the result.
* **Report** (``summary.json`` and a table, steady window only: startup and teardown are reported apart): logical
  tick time and its share of the GIL, revisions/s, the age chain (publish -> sync -> render -> swap, the consumed
  revision's age at sync and how many newer ones were waiting), render-mode time, swap pacing, the first 2 s after
  startup, the HUD age, and for Extruded Bubble the render stages (``tools/eb_live_phases.py``). Lines starting
  ``FLAG`` name a known trap; see ``Docs/Guides/Visualizer_Change_Checklist.md`` "Live-shape performance".

Runs take ``--seconds`` plus ~30 s (profile copy, load calibration, startup, teardown). Stop strays by exact PID.
"""
from __future__ import annotations

import argparse
import atexit
import bisect
import ctypes
import json
import os
import re
import shutil
import statistics
import subprocess
import sys
import threading
import time
from ctypes import wintypes
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CLIP = ROOT / "logs" / "visualizer_recordings" / "anything_mixed2.jsonl"    # mixed real music, ~2 min
STEADY_AFTER_STARTUP_NS = 2_000_000_000
LATE_MS = 25.0

# Guide numbers for a 60 Hz panel and the ~90 Hz authored cadence (flags, not pass/fail gates).
_FLAGS = (
    ("publish_to_swap_ms", 20.0, "publish -> swap median over 20 ms: the frame age budget is gone"),
    ("revisions_waiting_at_sync", 0.0, "the sync consumed a stale revision while newer ones waited"),
    ("logical_gil_share", 0.30, "the logical tick holds the GIL over 30% of the time: render/GUI threads stall"),
    ("render_mode_ms", 8.0, "render-mode time over 8 ms: the frame no longer fits half a 60 Hz period"),
    ("steady_late_pct", 10.0, "over 10% of steady frames later than 25 ms"),
    ("post_startup_late_pct", 20.0, "over 20% of the first 2 s after startup later than 25 ms"),
)


def _pct(values, q):
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(q * len(ordered)))] if ordered else None


def _stats(values):
    return {"median": round(statistics.median(values), 2), "p90": round(_pct(values, 0.9), 2)} if values else None


# -- analysis -----------------------------------------------------------------------------------------------------

def analyse_trace(path: Path) -> dict:
    sys.path.insert(0, str(ROOT))
    from tools.frame_trace_report import HEADER, RECORD, _read_trace_chain

    raw, _segments = _read_trace_chain(path)
    events: list[tuple[int, int, int]] = []
    for i in range((len(raw) - HEADER.size) // RECORD.size):
        ts, event, _screen, revision, _logical, _aux = RECORD.unpack_from(raw, HEADER.size + i * RECORD.size)
        events.append((ts, event, revision))
    events.sort()
    begins = [ts for ts, e, _ in events if e == 62]
    ends = [ts for ts, e, _ in events if e == 63]
    startup_end = ends[0] if ends else events[0][0]
    teardown = next((ts for ts in begins if ts > startup_end), events[-1][0])
    start, stop = startup_end + STEADY_AFTER_STARTUP_NS, teardown
    published = {r: ts for ts, e, r in events if e == 1}
    pub_times = sorted((ts, r) for ts, e, r in events if e == 1)
    pub_ts = [t for t, _ in pub_times]
    steady = [(ts, e, r) for ts, e, r in events if start <= ts < stop]
    seconds = max((stop - start) / 1e9, 1e-9)
    consumed, newest_age, waiting = [], [], []
    for ts, e, r in steady:
        if e != 4 or r not in published:
            continue
        k = bisect.bisect_right(pub_ts, ts) - 1
        consumed.append((ts - published[r]) / 1e6)
        newest_age.append((ts - pub_ts[k]) / 1e6)
        waiting.append(pub_times[k][1] - r)
    swaps = [ts for ts, e, _ in steady if e == 6]
    gaps = [(b - a) / 1e6 for a, b in zip(swaps, swaps[1:])]
    first_swap: dict[int, int] = {}
    for ts, e, r in steady:
        if e == 6 and r not in first_swap:
            first_swap[r] = ts
    to_swap = [(ts - published[r]) / 1e6 for r, ts in first_swap.items() if r in published]
    begin_mode: dict[int, int] = {}
    render_mode = []
    for ts, e, r in steady:
        if e == 12:
            begin_mode[r] = ts
        elif e == 13 and r in begin_mode:
            render_mode.append((ts - begin_mode.pop(r)) / 1e6)
    early = [ts for ts, e, _ in events if e == 6 and startup_end <= ts < start]
    early_gaps = [(b - a) / 1e6 for a, b in zip(early, early[1:])]
    return {
        "steady_seconds": round(seconds, 1),
        "revisions_per_s": round(sum(1 for _, e, _ in steady if e == 1) / seconds, 1),
        "frames_per_s": round(len(swaps) / seconds, 1),
        "consumed_age_at_sync_ms": _stats(consumed),
        "newest_age_at_sync_ms": _stats(newest_age),
        "revisions_waiting_at_sync": _stats(waiting),
        "publish_to_swap_ms": _stats(to_swap),
        "render_mode_ms": _stats(render_mode),
        "swap_gap_ms": _stats(gaps),
        "steady_late_pct": round(100.0 * sum(g > LATE_MS for g in gaps) / max(len(gaps), 1), 1),
        "post_startup_frames": len(early),
        "post_startup_late_pct": round(100.0 * sum(g > LATE_MS for g in early_gaps) / max(len(early_gaps), 1), 1),
        "sync_admissions_per_s": round(sum(1 for _, e, _ in steady if e == 74) / seconds, 1),
    }


def hud_ages(perf_log: Path, mode: str) -> dict | None:
    ages = [float(m.group(1)) for line in perf_log.read_text(encoding="utf-8", errors="replace").splitlines()
            if f"viz_mode={mode} " in line and (m := re.search(r"viz_age_ms=([\d.]+)", line))]
    return _stats(ages[3:-2]) if len(ages) > 6 else None


# -- the invisible runner (child process) -------------------------------------------------------------------------

def _runner(out: Path, seconds: float, visible: bool, clip: Path | None, clip_start: float) -> None:
    sys.path.insert(0, str(ROOT))
    os.chdir(ROOT)
    from tools import eb_live_phases as phases

    sys.argv = [str(ROOT / "main_mc.py"), "--perf", "--frame-trace", "--exit-after", str(int(seconds)), "/s"]
    phases.production_startup()
    if not visible:
        from PySide6.QtCore import Qt
        from PySide6.QtQuick import QQuickWindow
        from rendering.quick import state, window

        flags = state.QuickWindowPolicy.flags

        def invisible_flags(self):
            return ((flags(self) & ~Qt.WindowType.WindowStaysOnTopHint) | Qt.WindowType.Tool
                    | Qt.WindowType.WindowTransparentForInput | Qt.WindowType.WindowDoesNotAcceptFocus)

        init = window.QuickDisplayWindow.__init__

        def invisible_init(self, *args, **kwargs):
            init(self, *args, **kwargs)
            QQuickWindow.setOpacity(self, 0.0)

        state.QuickWindowPolicy.flags = invisible_flags
        window.QuickDisplayWindow.__init__ = invisible_init
        window.QuickDisplayWindow.setOpacity = lambda self, _opacity: QQuickWindow.setOpacity(self, 0.0)
    if clip is not None:
        # Recorded music where the loopback would deliver it, and playback truth to match: the whole live audio
        # path runs (capture callback, mono mix, DSP, analysis lane) whatever the machine is playing.
        from tools.visualizer_replay.live_audio import RecordedLoopback, recorded_pcm
        from widgets.spotify_visualizer import audio_worker
        from widgets.spotify_visualizer.quick_display_visualizer_owner import QuickDisplayVisualizerOwner

        pcm, rate = recorded_pcm(clip, start=clip_start, seconds=seconds + 60.0)
        audio_worker.create_audio_capture = lambda config=None: RecordedLoopback(config, pcm, rate)
        set_playing = QuickDisplayVisualizerOwner.set_playing
        QuickDisplayVisualizerOwner.set_playing = (
            lambda self, _playing, *, observed_ts=None: set_playing(self, True, observed_ts=observed_ts))
    phases._install()
    atexit.register(lambda: (out / "phases.json").write_text(json.dumps(phases._summary(), indent=1), encoding="utf-8"))
    import runpy
    runpy.run_path(str(ROOT / "main_mc.py"), run_name="__main__")


# -- parent: profile, load, guard, report -------------------------------------------------------------------------

_user32 = ctypes.WinDLL("user32", use_last_error=True)
_EnumWindowsProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)


def _visible_window_violations(pids: set[int]) -> list[str]:
    """Visible windows of ``pids`` that are not fully transparent, click-through and non-topmost."""
    found: list[str] = []

    def check(hwnd, _lparam):
        pid = wintypes.DWORD()
        _user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value in pids and _user32.IsWindowVisible(hwnd):
            style = _user32.GetWindowLongW(hwnd, -20)                       # GWL_EXSTYLE
            alpha, flags, key = ctypes.c_ubyte(), wintypes.DWORD(), wintypes.DWORD()
            layered = _user32.GetLayeredWindowAttributes(hwnd, ctypes.byref(key), ctypes.byref(alpha),
                                                         ctypes.byref(flags))
            if not (style & 0x80000 and style & 0x20 and not style & 0x8 and layered and flags.value & 2
                    and alpha.value == 0):
                title, name = ctypes.create_unicode_buffer(256), ctypes.create_unicode_buffer(256)
                _user32.GetWindowTextW(hwnd, title, 256)
                _user32.GetClassNameW(hwnd, name, 256)
                found.append(f"hwnd {hwnd} '{title.value}' class {name.value} exstyle {style:#x} alpha {alpha.value}")
        return True

    _user32.EnumWindows(_EnumWindowsProc(check), 0)
    return found


def _process_tree(pid: int) -> set[int]:
    import psutil
    try:
        process = psutil.Process(pid)
        return {pid, *(child.pid for child in process.children(recursive=True))}
    except psutil.Error:
        return {pid}


def _kill_tree(pid: int) -> None:
    subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True)


def _prepare_profile(out: Path, mode: str, preset: int | None, overrides: dict) -> Path:
    """Copy MC's settings profile (``SRPSS_MC``) and the shared data root (``SRPSS``); edit only the copy."""
    appdata = Path(os.environ["APPDATA"])
    for name in ("SRPSS", "SRPSS_MC"):
        shutil.copytree(appdata / name, out / "profile" / name)
    path = out / "profile" / "SRPSS_MC" / "settings_v2.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    visualizer = data["snapshot"]["widgets"]["spotify_visualizer"]
    visualizer["mode"] = mode
    if preset is not None:
        visualizer[f"preset_{mode}"] = preset - 1
    visualizer.update(overrides)
    path.write_text(json.dumps(data, indent=1), encoding="utf-8")
    return out / "profile"


def _start_load(profile: str, seconds: float, out: Path) -> subprocess.Popen:
    process = subprocess.Popen([sys.executable, str(ROOT / "tools" / "gpu_load_generator.py"), "--seconds",
                                str(seconds), "--profile", profile], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                               text=True, cwd=ROOT)
    log = (out / "load.txt").open("w", encoding="utf-8")
    ready = threading.Event()

    def pump():
        for line in process.stdout:
            log.write(line)
            log.flush()
            if "ready" in line:
                ready.set()
    threading.Thread(target=pump, daemon=True).start()
    if not ready.wait(90):
        _kill_tree(process.pid)
        raise RuntimeError("the load generator never reported ready (see load.txt)")
    return process


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--mode", required=True)
    parser.add_argument("--preset", type=int, help="curated preset, 1-based (default: the profile's own)")
    parser.add_argument("--set", action="append", default=[], metavar="KEY=JSON",
                        help="visualizer setting override, written into the copied profile only")
    parser.add_argument("--seconds", type=float, default=120.0)
    parser.add_argument("--load", default="game60", help="gpu_load_generator profile, or 'none'")
    parser.add_argument("--visible", action="store_true", help="an ordinary visible MC run (takes one display)")
    parser.add_argument("--clip", default=str(DEFAULT_CLIP),
                        help="recorded-music JSONL replayed as the loopback, or 'none' for the machine's own audio")
    parser.add_argument("--clip-start", type=float, default=0.0, help="seconds into the recording")
    parser.add_argument("--out", type=Path, help="output folder (default logs/live_check/<mode>_<time>)")
    parser.add_argument("--runner", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    out = args.out or ROOT / "logs" / "live_check" / f"{args.mode}_{time.strftime('%Y%m%d_%H%M%S')}"
    clip = None if args.clip == "none" else Path(args.clip).resolve()
    if args.runner:
        _runner(out, args.seconds, args.visible, clip, args.clip_start)
        return 0
    if clip is not None and not clip.exists():
        raise SystemExit(f"recording not found: {clip}")
    out.mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(ROOT))
    from tools.bench_stability import SystemSampler, summarise_environment

    overrides = {key: json.loads(value) for key, value in (item.split("=", 1) for item in args.set)}
    profile_dir = _prepare_profile(out, args.mode, args.preset, overrides)
    load = None if args.load == "none" else _start_load(args.load, args.seconds + 60, out)
    env = {**os.environ, "APPDATA": str(profile_dir), "SRPSS_FORCE_LOG_DIR": str(out / "logs")}
    command = [sys.executable, str(Path(__file__).resolve()), "--runner", "--mode", args.mode, "--seconds",
               str(args.seconds), "--out", str(out), "--clip", str(clip or "none"), "--clip-start",
               str(args.clip_start)] + (["--visible"] if args.visible else [])
    sampler, conditions = SystemSampler(), []
    runner = subprocess.Popen(command, env=env, cwd=ROOT, stdout=(out / "runner.txt").open("w"),
                              stderr=subprocess.STDOUT)
    violation = None
    try:
        while runner.poll() is None:
            time.sleep(1.0)
            conditions.append(sampler.sample())
            if not args.visible:
                found = _visible_window_violations(_process_tree(runner.pid))
                if found:
                    violation = found
                    _kill_tree(runner.pid)
                    break
    finally:
        if runner.poll() is None:
            _kill_tree(runner.pid)
        if load is not None:
            _kill_tree(load.pid)
    if violation:
        print("STOPPED: a saver window was visible:", *violation, sep="\n  ")
        return 2
    trace = out / "logs" / "screensaver_frame_trace.bin"
    if not trace.exists():
        print(f"no frame trace; see {out / 'runner.txt'}")
        return 1
    summary = {"mode": args.mode, "preset": args.preset, "overrides": overrides, "load": args.load,
               "clip": clip.name if clip else None, "clip_start": args.clip_start,
               "visible": args.visible, "conditions": summarise_environment(conditions), **analyse_trace(trace)}
    summary["hud_age_ms"] = hud_ages(out / "logs" / "screensaver_perf.log", args.mode)
    phases_path = out / "phases.json"
    if phases_path.exists():
        phases = json.loads(phases_path.read_text(encoding="utf-8"))
        tick = phases.get("logical_publish")
        summary["logical_tick_ms"] = tick
        if tick:
            summary["logical_gil_share"] = round(tick["median"] * summary["revisions_per_s"] / 1000.0, 2)
        summary["render_stages_ms"] = {k: v for k, v in phases.items()
                                       if isinstance(v, dict) and k != "logical_publish"}
    (out / "summary.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
    for key, value in summary.items():
        if key != "render_stages_ms":
            print(f"{key:28s} {value}")
    for key, limit, message in _FLAGS:
        value = summary.get(key)
        value = value["median"] if isinstance(value, dict) else value
        if value is not None and value > limit:
            print(f"FLAG {key} = {value}: {message}")
    print(f"written {out / 'summary.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
