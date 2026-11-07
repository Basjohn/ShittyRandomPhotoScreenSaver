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
  written into the copy only) with its display windows given an empty window region (no pixel and no click, yet presented as an ordinary window: opacity 0 or click-through would make it layered), never topmost and never focused. A guard
  checks every visible window of the run once a second and kills the run if any is not; ``--visible`` opts out (an
  ordinary MC run, one display).
* **Music:** ``--clip`` (default a ~2 min mixed real-music recording) is played as the loopback in real time
  (``tools/visualizer_replay/live_audio.py``): the whole live audio path runs on recorded music, every run hears the
  same passages, and playback is reported as playing whatever the machine itself plays. ``--clip none`` uses the
  machine's own audio and Media state.
* **Load:** ``--load game60`` (the reference case) starts ``tools/gpu_load_generator.py`` and waits for its calibrated
  ``ready`` line before the saver starts; ``--load none`` for an idle or operator-supplied load. Conditions are
  sampled throughout and recorded with the result.
* **Settings round trips:** ``--settings-roundtrip 60,300`` drives the engine's real Settings path at those times
  (``tools/live_check_settings_roundtrip.py``): stop, teardown, barriers, the real dialog (never shown) and the
  replacement up to its reveal, with per-trip timings, generations, memory and the GC thaw/re-freeze; any barrier
  timeout, missing re-freeze or early process exit fails the run (exit 3). The steady figures cover the time before
  the first round trip.
* **Output** goes to ``.artifacts/evidence/visualizers/<mode>/live_check/<YYYYMMDD>_<label>/``
  (``tools/artifact_paths.py``; an explicit ``--out`` inside the repository must follow that layout). The profile
  copy lives only while the run needs it: at the end of every run, failures included, its settings are kept beside
  the results as ``run_settings_v2.json`` (``SRPSS``) and ``run_settings_v2_mc.json`` (``SRPSS_MC``) and the
  ``profile/`` copy (Steam image cache, backups, encrypted credentials) is deleted.
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
sys.path.insert(0, str(ROOT))
from tools.live_check_settings_roundtrip import (  # noqa: E402  (stdlib-only at import)
    analyse_settings_roundtrips, gc_policy_lines, parse_roundtrip_memory, parse_settings_roundtrip,
    print_settings_roundtrips,
)
from tools import artifact_paths  # noqa: E402
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
    ("hitches_per_min", 0.5, "steady frames over 50 ms: a visible hitch (periodic ones point at a timer-driven GIL holder)"),
    ("usage_collect_ms", 40.0, "a usage sample takes over 40 ms of a worker thread, much of it GIL-held: it stalls every thread"),
)


def _pct(values, q):
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(q * len(ordered)))] if ordered else None


def _stats(values):
    return {"median": round(statistics.median(values), 2), "p90": round(_pct(values, 0.9), 2)} if values else None


# -- analysis -----------------------------------------------------------------------------------------------------

def analyse_trace(path: Path, *, steady_stop_ns: int | None = None) -> dict:
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
    if steady_stop_ns is not None:
        stop = min(stop, int(steady_stop_ns))   # --display-off: the steady window ends at the first off edge
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
        "hitches_per_min": round(60.0 * sum(g > 50.0 for g in gaps) / seconds, 2),
        "post_startup_frames": len(early),
        "post_startup_late_pct": round(100.0 * sum(g > LATE_MS for g in early_gaps) / max(len(early_gaps), 1), 1),
        "sync_admissions_per_s": round(sum(1 for _, e, _ in steady if e == 74) / seconds, 1),
    }


def hud_ages(perf_log: Path, mode: str) -> dict | None:
    ages = [float(m.group(1)) for line in perf_log.read_text(encoding="utf-8", errors="replace").splitlines()
            if f"viz_mode={mode} " in line and (m := re.search(r"viz_age_ms=([\d.]+)", line))]
    return _stats(ages[3:-2]) if len(ages) > 6 else None


# -- display power (--display-off) ---------------------------------------------------------------------------------
# The real Windows notification is injected through the production seam: the saver's own display-power window
# procedure receives WM_POWERBROADCAST / PBT_POWERSETTINGCHANGE with a GUID_CONSOLE_DISPLAY_STATE payload, exactly as
# Windows sends it. The panels are never powered off and no power setting changes.

POWER_SETTLE_S = 3.0          # seconds after each edge left out of a window's figures
RESUME_WINDOW_NS = 2_000_000_000


def parse_display_off(text: str) -> list[tuple[float, float]]:
    """``AT:FOR[,AT:FOR...]`` seconds after the runner starts -> sorted (off_at, on_at) pairs."""
    pairs = []
    for part in str(text).split(","):
        at, _, duration = part.partition(":")
        off_at, length = float(at), float(duration)
        if off_at <= 0.0 or length <= 0.0:
            raise ValueError(f"--display-off needs positive AT:FOR seconds, got {part!r}")
        pairs.append((off_at, off_at + length))
    pairs.sort()
    for (_, on_at), (next_off, _) in zip(pairs, pairs[1:]):
        if next_off < on_at:
            raise ValueError("--display-off windows overlap")
    return pairs


def _inject_display_power(out: Path, schedule: list[tuple[float, float]]) -> None:
    """Child side: send the console display state to the saver's own power window at the scheduled times."""
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    user32.FindWindowExW.restype = wintypes.HWND
    user32.FindWindowExW.argtypes = [wintypes.HWND, wintypes.HWND, wintypes.LPCWSTR, wintypes.LPCWSTR]
    user32.SendMessageTimeoutW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM,
                                           wintypes.UINT, wintypes.UINT, ctypes.POINTER(ctypes.c_size_t)]
    try:
        from core.windows.display_power_notifier import (
            PBT_POWERSETTINGCHANGE, WINDOW_CLASS_PREFIX, WM_POWERBROADCAST, display_state_payload,
        )
    except ImportError:          # code before the display-power authority: nothing listens, edges are recorded only
        WINDOW_CLASS_PREFIX, WM_POWERBROADCAST, PBT_POWERSETTINGCHANGE = None, 0x0218, 0x8013
        display_state_payload = lambda state: ctypes.c_uint32(state)

    def power_window():
        if WINDOW_CLASS_PREFIX is None:
            return None
        own, child = os.getpid(), None
        while True:
            child = user32.FindWindowExW(wintypes.HWND(-3), child, None, None)    # HWND_MESSAGE children
            if not child:
                return None
            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(child, ctypes.byref(pid))
            name = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(child, name, 256)
            if pid.value == own and name.value.startswith(WINDOW_CLASS_PREFIX):
                return child

    began, log = time.monotonic(), (out / "power_edges.jsonl").open("a", encoding="utf-8")

    def send(state: int) -> None:
        hwnd, payload, result = power_window(), display_state_payload(state), ctypes.c_size_t()
        delivered = bool(hwnd) and bool(user32.SendMessageTimeoutW(
            hwnd, WM_POWERBROADCAST, PBT_POWERSETTINGCHANGE, ctypes.addressof(payload), 0x2, 5000,
            ctypes.byref(result)))
        log.write(json.dumps({"state": state, "perf_ns": time.perf_counter_ns(), "wall": time.time(),
                              "listener": bool(hwnd), "delivered": delivered}) + "\n")
        log.flush()

    def run() -> None:
        for off_at, on_at in schedule:
            for at, state in ((off_at, 0), (on_at, 1)):
                time.sleep(max(0.0, began + at - time.monotonic()))
                send(state)

    threading.Thread(target=run, name="srpss-live-check-display-power", daemon=True).start()


class _ProcessGpu:
    """Per-process GPU engine utilisation (Windows ``GPU Engine`` counters, summed over a process tree)."""

    def __init__(self) -> None:
        self._pdh = ctypes.WinDLL("pdh")
        self._query, self._counter = ctypes.c_void_p(), ctypes.c_void_p()
        ok = (self._pdh.PdhOpenQueryW(None, None, ctypes.byref(self._query)) == 0
              and self._pdh.PdhAddEnglishCounterW(self._query, r"\GPU Engine(*)\Utilization Percentage", None,
                                                 ctypes.byref(self._counter)) == 0)
        self.available = ok and self._pdh.PdhCollectQueryData(self._query) == 0

    def sample(self, pids: set[int]) -> float | None:
        if not self.available or self._pdh.PdhCollectQueryData(self._query) != 0:
            return None

        class Item(ctypes.Structure):
            _fields_ = [("name", ctypes.c_wchar_p), ("status", wintypes.DWORD), ("value", ctypes.c_double)]

        size, count = wintypes.DWORD(0), wintypes.DWORD(0)
        self._pdh.PdhGetFormattedCounterArrayW(self._counter, 0x200, ctypes.byref(size), ctypes.byref(count), None)
        buffer = ctypes.create_string_buffer(size.value)
        if self._pdh.PdhGetFormattedCounterArrayW(self._counter, 0x200, ctypes.byref(size), ctypes.byref(count),
                                                   buffer) != 0:
            return None
        items = ctypes.cast(buffer, ctypes.POINTER(Item))
        prefixes = tuple(f"pid_{pid}_" for pid in pids)
        return round(sum(items[i].value for i in range(count.value)
                         if items[i].name and items[i].name.startswith(prefixes)), 2)


def _tree_cpu_seconds(pids: set[int]) -> float:
    import psutil
    total = 0.0
    for pid in pids:
        try:
            times = psutil.Process(pid).cpu_times()
            total += times.user + times.system
        except psutil.Error:
            continue
    return total


def analyse_display_power(trace: Path, edges: list[dict], samples: list[dict]) -> dict:
    """Off-state cost and resume shape, per edge pair, from the frame trace and per-second process samples."""
    sys.path.insert(0, str(ROOT))
    from tools.frame_trace_report import HEADER, RECORD, _read_trace_chain

    raw, _segments = _read_trace_chain(trace)
    events = sorted(RECORD.unpack_from(raw, HEADER.size + i * RECORD.size)[:2]
                    for i in range((len(raw) - HEADER.size) // RECORD.size))
    settle = int(POWER_SETTLE_S * 1e9)

    def window(begin_ns: int, end_ns: int) -> dict:
        seconds = max((end_ns - begin_ns) / 1e9, 1e-9)
        chosen = [s for s in samples if begin_ns <= s["perf_ns"] < end_ns]
        cpu = [s["cpu_core_pct"] for s in chosen if s.get("cpu_core_pct") is not None]
        gpu = [s["gpu_pct"] for s in chosen if s.get("gpu_pct") is not None]
        others = [s["cpu_others"] for s in chosen if "cpu_others" in s]
        count = lambda kind: sum(1 for ts, e in events if e == kind and begin_ns <= ts < end_ns)
        return {"seconds": round(seconds, 1), "swaps_per_s": round(count(6) / seconds, 2),
                "publishes_per_s": round(count(1) / seconds, 2), "saver_cpu_core_pct": _stats(cpu),
                "saver_gpu_pct": _stats(gpu), "others_cpu_pct": _stats(others), "samples": len(chosen)}

    pairs, offs = [], [e for e in edges if e["state"] == 0]
    for off in offs:
        on = next((e for e in edges if e["state"] == 1 and e["perf_ns"] > off["perf_ns"]), None)
        if on is None:
            continue
        # Windows never reach into a neighbouring pair (bursts): before ends at this OFF, after at the next OFF.
        previous_on = max((e["perf_ns"] for e in edges if e["state"] == 1 and e["perf_ns"] < off["perf_ns"]),
                          default=None)
        next_off = min((e["perf_ns"] for e in offs if e["perf_ns"] > on["perf_ns"]), default=None)
        before_start = max(off["perf_ns"] - (on["perf_ns"] - off["perf_ns"]), off["perf_ns"] - 30_000_000_000,
                           previous_on if previous_on is not None else 0)
        after_end = on["perf_ns"] + min(on["perf_ns"] - off["perf_ns"], 30_000_000_000)
        resume_end = on["perf_ns"] + RESUME_WINDOW_NS
        if next_off is not None:
            after_end, resume_end = min(after_end, next_off), min(resume_end, next_off)
        swaps_after = [ts for ts, e in events if e == 6 and ts >= on["perf_ns"]]
        resume = [ts for ts in swaps_after if ts < resume_end]
        gaps = [(b - a) / 1e6 for a, b in zip(resume, resume[1:])]
        # The logical side of resume: a hole here (rather than in swaps) is a time-gap / cadence failure.
        published = [ts for ts, e in events if e == 1 and on["perf_ns"] <= ts < resume_end]
        publish_gaps = [(b - a) / 1e6 for a, b in zip(published, published[1:])]
        pairs.append({
            "listener": bool(off.get("listener")), "delivered": bool(off.get("delivered") and on.get("delivered")),
            "on_before": window(before_start + settle, off["perf_ns"]),
            "off": window(off["perf_ns"] + settle, on["perf_ns"]),
            "on_after": window(on["perf_ns"] + settle, after_end),
            "first_swap_after_on_ms": round((swaps_after[0] - on["perf_ns"]) / 1e6, 1) if swaps_after else None,
            "resume_2s": {"seconds": round((resume_end - on["perf_ns"]) / 1e9, 2),
                          "frames": len(resume), "swap_gap_ms": _stats(gaps),
                          "late_pct": round(100.0 * sum(g > LATE_MS for g in gaps) / max(len(gaps), 1), 1),
                          "max_gap_ms": round(max(gaps), 1) if gaps else None,
                          "publishes": len(published), "publish_gap_ms": _stats(publish_gaps),
                          "max_publish_gap_ms": round(max(publish_gaps), 1) if publish_gaps else None,
                          "first_publish_after_on_ms": (round((published[0] - on["perf_ns"]) / 1e6, 1)
                                                        if published else None)},
        })
    return {"edges": edges, "pairs": pairs}


# -- the invisible runner (child process) -------------------------------------------------------------------------

def _runner(out: Path, seconds: float, visible: bool, clip: Path | None, clip_start: float, mode: str,
            display_off: list[tuple[float, float]] | None = None,
            settings_roundtrip: list[float] | None = None, roundtrip_memory: tuple[str, ...] = ()) -> None:
    began = time.monotonic()
    sys.path.insert(0, str(ROOT))
    os.chdir(ROOT)
    if roundtrip_memory:
        from tools.live_check_settings_roundtrip import RoundTripMemoryProbe

        RoundTripMemoryProbe.start_tracing(roundtrip_memory)     # before the application's imports
    from tools import eb_live_phases as phases

    # Isolate the copied profile through explicit runner-side path injection, without process environment edits.
    # Both resolvers are installed before application imports can retain their path functions.
    from core.settings import storage_paths, json_store
    profile_root=(out/'profile').resolve()
    storage_paths._appdata_root=lambda:profile_root
    json_store._default_appdata_dir=lambda:profile_root
    from core.logging import logger
    logger._FORCED_LOG_DIR=(out/'logs').resolve()

    # --usage as the operator always runs: its sampler is part of the live shape (a 15 s GIL-held hitch, 2026-10-31).
    sys.argv = [str(ROOT / "main_mc.py"), "--perf", "--usage", "--frame-trace", "--exit-after", str(int(seconds)), "/s"]
    phases.production_startup()
    if not visible:
        # Invisible but presented like a visible window: an empty window region clips every pixel and every click,
        # while the window stays an ordinary (non-layered) one, so its swap is paced by its own display. Opacity 0 or
        # WindowTransparentForInput would make it layered, and a layered window's swap is not vsync-paced (it ran at
        # the 90 Hz publication rate on a 60 Hz panel).
        from PySide6.QtCore import Qt
        from rendering.quick import state, window

        flags = state.QuickWindowPolicy.flags

        def invisible_flags(self):
            return ((flags(self) & ~Qt.WindowType.WindowStaysOnTopHint) | Qt.WindowType.Tool
                    | Qt.WindowType.WindowDoesNotAcceptFocus)

        show_on_screen = window.QuickDisplayWindow.show_on_screen
        gdi32 = ctypes.WinDLL("gdi32")

        def invisible_show(self):
            # Placement is committed and the show is only queued: create the native window now, on its screen
            # (earlier, in __init__, it is created before its screen and the display reads as displaced).
            show_on_screen(self)
            _user32.SetWindowRgn(int(self.winId()), gdi32.CreateRectRgn(0, 0, 0, 0), False)

        state.QuickWindowPolicy.flags = invisible_flags
        window.QuickDisplayWindow.show_on_screen = invisible_show
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
    if mode=='waveform_ribbon':phases._install_waveform()
    if display_off:
        _inject_display_power(out, display_off)
    if settings_roundtrip:
        # The engine's real Settings path at each time; the dialog never shows (tools/live_check_settings_roundtrip.py).
        from tools.live_check_settings_roundtrip import RoundTripMemoryProbe, SettingsRoundTripDriver

        probe = RoundTripMemoryProbe(roundtrip_memory, out_dir=out) if roundtrip_memory else None
        driver = SettingsRoundTripDriver(settings_roundtrip, began=began, state_path=out / "settings_roundtrip.json",
                                         memory_probe=probe)
        driver.install()
        atexit.register(driver.finish)
    atexit.register(lambda: (out / "phases.json").write_text(json.dumps(phases._summary(), indent=1), encoding="utf-8"))
    import runpy
    runpy.run_path(str(ROOT / "main_mc.py"), run_name="__main__")


# -- parent: profile, load, guard, report -------------------------------------------------------------------------

# Windows-only harness; the module still imports elsewhere so its portable helpers stay testable.
if sys.platform == "win32":
    _user32 = ctypes.WinDLL("user32", use_last_error=True)
    _EnumWindowsProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
else:
    _user32 = _EnumWindowsProc = None


def _visible_window_violations(pids: set[int]) -> list[str]:
    """Visible windows of ``pids`` that could show a pixel or take a click: anything but a non-topmost window
    with an empty window region (or one fully transparent, click-through and layered)."""
    found: list[str] = []
    gdi32 = ctypes.WinDLL("gdi32")

    def check(hwnd, _lparam):
        pid = wintypes.DWORD()
        _user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value in pids and _user32.IsWindowVisible(hwnd):
            style = _user32.GetWindowLongW(hwnd, -20)                       # GWL_EXSTYLE
            region = gdi32.CreateRectRgn(0, 0, 0, 0)
            empty = _user32.GetWindowRgn(hwnd, region) == 1                 # NULLREGION
            gdi32.DeleteObject(region)
            alpha, flags, key = ctypes.c_ubyte(), wintypes.DWORD(), wintypes.DWORD()
            layered = _user32.GetLayeredWindowAttributes(hwnd, ctypes.byref(key), ctypes.byref(alpha),
                                                         ctypes.byref(flags))
            transparent = (style & 0x80000 and style & 0x20 and layered and flags.value & 2 and alpha.value == 0)
            if style & 0x8 or not (empty or transparent):
                title, name = ctypes.create_unicode_buffer(256), ctypes.create_unicode_buffer(256)
                _user32.GetWindowTextW(hwnd, title, 256)
                _user32.GetClassNameW(hwnd, name, 256)
                found.append(f"hwnd {hwnd} '{title.value}' class {name.value} exstyle {style:#x} alpha {alpha.value}")
        return True

    _user32.EnumWindows(_EnumWindowsProc(check), 0)
    return found


def usage_summary(usage_log: Path) -> dict | None:
    """The usage sampler's cost and what it walks (the operator always runs with --usage)."""
    if not usage_log.exists():
        return None
    rows = re.findall(r"collect_ms=([\d.]+).*?processes=(\d+) children=(\d+).*?threads_app=(\d+) handles_app=(\d+)",
                      usage_log.read_text(encoding="utf-8", errors="replace"))[1:]  # the first sample primes caches
    if not rows:
        return None
    column = lambda i: [float(row[i]) for row in rows]
    return {"samples": len(rows), "collect_ms": _stats(column(0)), "processes": statistics.median(column(1)),
            "threads": statistics.median(column(3)), "handles": statistics.median(column(4))}


def _tree_snapshot(pid: int) -> list[dict]:
    """Name, thread count and command of every process in the saver's tree (what the usage sampler walks)."""
    import psutil
    snapshot = []
    try:
        processes = [psutil.Process(pid), *psutil.Process(pid).children(recursive=True)]
    except psutil.Error:
        return snapshot
    for process in processes:
        try:
            snapshot.append({"pid": process.pid, "parent": process.ppid(), "name": process.name(),
                             "threads": process.num_threads(), "cmd": " ".join(process.cmdline())[:200]})
        except psutil.Error:
            continue
    return snapshot


def _process_tree(pid: int) -> set[int]:
    import psutil
    try:
        process = psutil.Process(pid)
        return {pid, *(child.pid for child in process.children(recursive=True))}
    except psutil.Error:
        return {pid}


def _kill_tree(pid: int) -> None:
    subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True)


def _prepare_profile(out: Path, mode: str, preset: int | None, overrides: dict, *, appdata_root=None) -> Path:
    """Copy MC's settings profile (``SRPSS_MC``) and the shared data root (``SRPSS``); edit only the copy."""
    appdata = Path(os.environ["APPDATA"]) if appdata_root is None else Path(appdata_root)
    for name in ("SRPSS", "SRPSS_MC"):
        shutil.copytree(appdata / name, out / "profile" / name)
    path = out / "profile" / "SRPSS_MC" / "settings_v2.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    visualizer = data["snapshot"]["widgets"]["spotify_visualizer"]
    visualizer["mode"] = mode
    if preset is not None:
        visualizer[f"preset_{mode}"] = preset - 1
    if overrides:
        from core.settings.visualizer_presets import (
            resolve_visualizer_activation_payload, get_custom_preset_index,
            build_normalized_custom_snapshot, VISUALIZER_CUSTOM_STORAGE_KEY,
        )
        # Curated artwork owns its settings and would overwrite raw --set values
        # at activation. Resolve it first, then use the real Custom authority in
        # this disposable profile. Never edit a user's authored preset file.
        visualizer.update(resolve_visualizer_activation_payload(visualizer,mode=mode).resolved_config)
        visualizer.update(overrides)
        visualizer[f"preset_{mode}"] = get_custom_preset_index(mode)
        cache = dict(visualizer.get(VISUALIZER_CUSTOM_STORAGE_KEY,{}))
        cache[mode] = build_normalized_custom_snapshot(mode,visualizer)
        visualizer[VISUALIZER_CUSTOM_STORAGE_KEY] = cache
    path.write_text(json.dumps(data, indent=1), encoding="utf-8")
    return out / "profile"


# The profile folders' settings, kept beside the results once the copy is deleted.
RUN_SETTINGS = (("SRPSS", "run_settings_v2.json"), ("SRPSS_MC", "run_settings_v2_mc.json"))


def retire_profile_copy(out: Path) -> list[Path]:
    """Keep the run's settings files beside the results, then delete ``<out>/profile`` (every run, every path).

    The copy holds the shared data root too (Steam image cache, backups, encrypted Gmail credentials): 9.8 GB
    over 36 runs before this. Nothing the summary or the reports read lives in it.
    """
    profile = out / "profile"
    kept: list[Path] = []
    for folder, name in RUN_SETTINGS:
        source = profile / folder / "settings_v2.json"
        if source.is_file():
            target = out / name
            shutil.copyfile(source, target)
            kept.append(target)
    if profile.exists():
        shutil.rmtree(profile)
    return kept


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


def build_parser() -> argparse.ArgumentParser:
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
    parser.add_argument("--out", type=artifact_paths.evidence_arg,
                        help="output folder (default .artifacts/evidence/visualizers/<mode>/live_check/"
                             "<YYYYMMDD>_<label>; inside the repository it must follow that layout)")
    parser.add_argument("--label", help="run label for the default output folder (default p<preset>_<time>)")
    parser.add_argument("--display-off", metavar="AT:FOR[,AT:FOR]",
                        help="inject the console display OFF at AT s after the runner starts and ON again FOR s later, "
                             "through the saver's own WM_POWERBROADCAST window procedure (panels are never touched)")
    parser.add_argument("--settings-roundtrip", metavar="AT[,AT]", type=parse_settings_roundtrip,
                        help="drive the engine's real Settings path (stop, teardown, barriers, dialog, replacement) "
                             "AT s after the runner starts; the dialog never shows. Fails the run on a barrier "
                             "timeout, a reveal without a GC re-freeze or a process exit")
    parser.add_argument("--roundtrip-memory", metavar="census[,collect][,tracemalloc][,map]", type=parse_roundtrip_memory,
                        default=(), help="with --settings-roundtrip: classify what each round trip leaves behind "
                                         "at every reveal (runner only; settings_roundtrip_memory.json)")
    parser.add_argument("--runner", action="store_true", help=argparse.SUPPRESS)
    return parser


def runner_command(args, out: Path, clip: Path | None) -> list[str]:
    """The child command line: every option the runner needs, forwarded as given."""
    return ([sys.executable, str(Path(__file__).resolve()), "--runner", "--mode", args.mode, "--seconds",
             str(args.seconds), "--out", str(out), "--clip", str(clip or "none"), "--clip-start",
             str(args.clip_start)] + (["--visible"] if args.visible else [])
            + (["--display-off", args.display_off] if args.display_off else [])
            + (["--settings-roundtrip", ",".join(f"{at:g}" for at in args.settings_roundtrip)]
               if args.settings_roundtrip else [])
            + (["--roundtrip-memory", ",".join(args.roundtrip_memory)]
               if args.settings_roundtrip and args.roundtrip_memory else []))


def default_out(args) -> Path:
    label = args.label or artifact_paths.run_label(f"p{args.preset}" if args.preset else "profile")
    return artifact_paths.evidence_dir(f"visualizers/{args.mode}", "live_check", artifact_paths.slug(label))


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    clip = None if args.clip == "none" else Path(args.clip).resolve()
    if args.runner:
        _runner(args.out, args.seconds, args.visible, clip, args.clip_start, args.mode,
                parse_display_off(args.display_off) if args.display_off else None, args.settings_roundtrip,
                args.roundtrip_memory if args.settings_roundtrip else ())
        return 0
    out = artifact_paths.checked_output(args.out) if args.out is not None else default_out(args)
    if clip is not None and not clip.exists():
        raise SystemExit(f"recording not found: {clip}")
    out.mkdir(parents=True, exist_ok=True)
    try:
        return _measure(args, out, clip)
    finally:
        kept = retire_profile_copy(out)
        print(f"profile copy deleted; kept {', '.join(path.name for path in kept) or 'no settings'}")


def _measure(args, out: Path, clip: Path | None) -> int:
    sys.path.insert(0, str(ROOT))
    from tools.bench_stability import SystemSampler, summarise_environment

    overrides = {key: json.loads(value) for key, value in (item.split("=", 1) for item in args.set)}
    _prepare_profile(out, args.mode, args.preset, overrides)
    load = None if args.load == "none" else _start_load(args.load, args.seconds + 60, out)
    command = runner_command(args, out, clip)
    if args.display_off:
        parse_display_off(args.display_off)
    sampler, conditions = SystemSampler(), []
    gpu, power_samples, cpu_previous = (_ProcessGpu() if args.display_off else None), [], None
    runner = subprocess.Popen(command, cwd=ROOT, stdout=(out / "runner.txt").open("w"),
                              stderr=subprocess.STDOUT)
    violation, tree, started = None, None, time.monotonic()
    try:
        while runner.poll() is None:
            time.sleep(1.0)
            conditions.append(sampler.sample())
            if gpu is not None:
                pids = _process_tree(runner.pid)
                now_ns, cpu_now = time.perf_counter_ns(), _tree_cpu_seconds(pids)
                row = {"perf_ns": now_ns, "gpu_pct": gpu.sample(pids), "cpu_others": conditions[-1]["cpu_others"]}
                if cpu_previous is not None:
                    row["cpu_core_pct"] = round(100.0 * (cpu_now - cpu_previous[1])
                                                / max((now_ns - cpu_previous[0]) / 1e9, 1e-9), 1)
                cpu_previous = (now_ns, cpu_now)
                power_samples.append(row)
            if tree is None and time.monotonic() - started > min(30.0, args.seconds / 2):
                tree = _tree_snapshot(runner.pid)
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
    roundtrips = None
    if args.settings_roundtrip:
        state_path = out / "settings_roundtrip.json"
        roundtrips = analyse_settings_roundtrips(
            json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else None,
            times=args.settings_roundtrip, returncode=runner.returncode, gc_lines=gc_policy_lines(out / "logs"))
        (out / "settings_roundtrip_summary.json").write_text(json.dumps(roundtrips, indent=1), encoding="utf-8")
        print_settings_roundtrips(roundtrips)
        if roundtrips["failures"]:
            print(f"FAILED: {len(roundtrips['failures'])} Settings round-trip failure(s); "
                  f"see {out / 'settings_roundtrip_summary.json'} and {out / 'runner.txt'}")
            return 3
    if runner.returncode != 0:
        raise RuntimeError(f'Live runner exited {runner.returncode}; see {out / "runner.txt"}')
    return _report(args, out, clip, overrides, summarise_environment(conditions), power_samples, tree, roundtrips)


def _report(args, out: Path, clip: Path | None, overrides: dict, conditions: dict, power_samples: list,
            tree, roundtrips) -> int:
    trace = out / "logs" / "screensaver_frame_trace.bin"
    if not trace.exists():
        print(f"no frame trace; see {out / 'runner.txt'}")
        return 1
    summary = {"mode": args.mode, "preset": args.preset, "overrides": overrides, "load": args.load,
               "clip": clip.name if clip else None, "clip_start": args.clip_start,
               "visible": args.visible, "conditions": conditions}
    edges_path = out / "power_edges.jsonl"
    edges = ([json.loads(line) for line in edges_path.read_text(encoding="utf-8").splitlines() if line.strip()]
             if edges_path.exists() else [])
    summary.update(analyse_trace(trace, steady_stop_ns=edges[0]["perf_ns"] if edges else None))
    if args.display_off:
        (out / "power_samples.jsonl").write_text("".join(json.dumps(row) + "\n" for row in power_samples),
                                                 encoding="utf-8")
        summary["display_power"] = analyse_display_power(trace, edges, power_samples)
    summary["hud_age_ms"] = hud_ages(out / "logs" / "screensaver_perf.log", args.mode)
    usage = usage_summary(out / "logs" / "screensaver_usage.log")
    summary["usage"] = usage
    summary["usage_collect_ms"] = usage["collect_ms"] if usage else None
    summary["process_tree"] = tree
    if roundtrips is not None:
        summary["settings_roundtrip"] = {k: v for k, v in roundtrips.items() if k != "gc_policy_lines"}
    phases_path = out / "phases.json"
    if args.mode=='waveform_ribbon' and not phases_path.exists():
        raise RuntimeError('Waveform run has no phase/admission receipt')
    if phases_path.exists():
        phases = json.loads(phases_path.read_text(encoding="utf-8"))
        actual=phases.get('waveform_configuration')
        if args.mode=='waveform_ribbon':
            if not phases.get('waveform_render'):raise RuntimeError('Waveform run has no steady renderer measurements')
            if not actual:raise RuntimeError('Waveform run did not admit a configured logical scene')
            mismatch={key:(value,actual.get(key)) for key,value in overrides.items()
                      if key not in actual or actual[key]!=value}
            if mismatch:raise RuntimeError(f'Runtime overrides did not reach Waveform: {mismatch}')
            summary['actual_waveform_configuration']=actual
            signals=phases.get('waveform_signals',[])
            if clip is not None and not any(max(row['bands'])>0. and row['playing']
                    and row['source_identity']==row['identity'][1:] for row in signals):
                raise RuntimeError('Recorded PCM never reached the live Waveform body')
            summary['waveform_signal_samples']=len(signals)
            summary['waveform_burst_serial']=max((row['bursts'] for row in signals),default=0)
        tick = phases.get("logical_publish")
        summary["logical_tick_ms"] = tick
        if tick:
            summary["logical_gil_share"] = round(tick["median"] * summary["revisions_per_s"] / 1000.0, 2)
        summary["render_stages_ms"] = {k: v for k, v in phases.items()
                                       if isinstance(v, dict) and k != "logical_publish"}
    (out / "summary.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
    for key, value in summary.items():
        if key not in ("render_stages_ms", "process_tree", "actual_waveform_configuration", "display_power",
                       "settings_roundtrip"):
            print(f"{key:28s} {value}")
    for key, limit, message in _FLAGS:
        value = summary.get(key)
        value = value["median"] if isinstance(value, dict) else value
        if value is not None and value > limit:
            print(f"FLAG {key} = {value}: {message}")
    for index, pair in enumerate((summary.get("display_power") or {}).get("pairs", ())):
        print(f"display power pair {index}: listener={pair['listener']} delivered={pair['delivered']} "
              f"first_swap_after_on_ms={pair['first_swap_after_on_ms']} resume_2s={pair['resume_2s']}")
        for name in ("on_before", "off", "on_after"):
            print(f"  {name:9s} {pair[name]}")
    print(f"written {out / 'summary.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
