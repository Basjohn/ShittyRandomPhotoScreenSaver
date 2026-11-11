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
* **Mode switches:** ``--mode-switch 30,42`` makes the production cycle gesture (double-click / context menu: the next
  enabled mode) at those times and records each completion (``tools/live_check_mode_switch.py``); a switch that never
  completes fails the run (exit 3).
* **Experiment admissions:** ``--app-arg=<token>`` adds that token to the saver's argv (only
  ``core.diagnostics.experiment_flags`` tokens are accepted). The Visualizer runs on the engine worker by default
  (Windows); ``--app-arg=--viz-in-process`` runs the in-process control (``engine_worker_path``). On the worker with a ``--clip``, the
  worker plays the same recording (its first ``WORKER_PCM_LOOP_S`` seconds, looped, on the worker's own audio clock:
  the link's recorded-capture control, as its gates use it) and never opens the loopback device.
* **Resource readings:** ``--resource-readings`` reads the saver's process tree from outside (this parent: psutil,
  handles by object type, section views, the session's named ``srpss_viz_`` mappings) every second and ``--settle``
  seconds after each reveal or completed mode switch (``tools/live_check_resources.py``): a per-cycle table, slopes and
  a growth verdict (``resource_summary.json``; growth fails the run, exit 4).
* **Output** goes to ``.artifacts/evidence/visualizers/<mode>/live_check/<YYYYMMDD>_<label>/``
  (``tools/artifact_paths.py``; an explicit ``--out`` inside the repository must follow that layout). The profile
  copy lives only while the run needs it: at the end of every run, failures included, its settings are kept beside
  the results as ``run_settings_v2.json`` (``SRPSS``) and ``run_settings_v2_mc.json`` (``SRPSS_MC``) and the
  ``profile/`` copy (Steam image cache, backups, encrypted credentials) is deleted.
* **Report** (``summary.json`` and a table, steady window only: startup and teardown are reported apart): logical
  tick time and its share of its thread's time, revisions/s, the age chain (publish -> sync -> render -> swap, the
  consumed revision's age at sync and how many newer ones were waiting), render-mode time, swap pacing, the first 2 s
  after startup, the HUD age, and for Extruded Bubble the render stages (``tools/eb_live_phases.py``). Lines starting
  ``FLAG`` name a known trap; see ``Docs/Guides/Visualizer_Change_Checklist.md`` "Live-shape performance".
  On the engine worker the same age chain is read from the worker's own publish stamps (each frame
  slot's ``publish_ns``, on the clock every process shares; the main side records a frame's publish when it takes
  it), and the tick and main's per-frame work are labelled by process and by what was measured (``tick_shares``):
  ``tick_process``, ``tick_to_publish_ms`` and ``tick_wall_share`` (both paths, from the trace), ``main_wall_share``
  and ``main_cpu_share`` (in process the logical tick's, on the worker path the frame take's) and ``worker_tick_ms`` /
  ``worker_tick_wall_share`` (the worker's own process). A wall share is wall time per call times calls per second,
  an upper bound on GIL hold, never the hold itself; the CPU share excludes waits. The count of revisions waiting at
  sync is not measured on the worker path (main records only the frames it took), and ``audio_delivery`` states how
  the recording reached the engine (the worker's is phase-locked to its tick, the in-process run's device-like). A
  worker run with no publish records fails. A Waveform run with a ``--clip`` fails unless the recording reached the live body
  (``waveform_pcm_receipt``): in process from the body's input rows, on the worker path from the frames main rendered
  (a live body with passage above zero; ``waveform_frame_receipt``).

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
from tools.live_check_mode_switch import (  # noqa: E402  (stdlib-only at import)
    analyse_mode_switches, parse_mode_switch, print_mode_switches,
)
from tools import live_check_resources  # noqa: E402  (stdlib-only at import)
from tools import artifact_paths  # noqa: E402
DEFAULT_CLIP = ROOT / "logs" / "visualizer_recordings" / "anything_mixed2.jsonl"    # mixed real music, ~2 min
STEADY_AFTER_STARTUP_NS = 2_000_000_000
LATE_MS = 25.0
WORKER_PCM_LOOP_S = 20.0      # the engine worker's recorded stream (looped): a few MB in each VIS_CONFIGURE
ENGINE_WORKER_ARG = "--viz-engine-worker"
IN_PROCESS_ARG = "--viz-in-process"


def engine_worker_path(app_args) -> bool:
    """Whether the saver runs its Visualizer on the engine worker: as ``core.diagnostics.experiment_flags`` resolves
    the run's tokens (the product's default; ``--app-arg=--viz-in-process`` for the in-process control)."""
    from core.diagnostics.experiment_flags import parse_experiment_flags, visualizer_engine_worker_platform_default

    chosen = parse_experiment_flags(list(app_args)).visualizer_engine_worker
    return visualizer_engine_worker_platform_default() if chosen is None else bool(chosen)

# Guide numbers for a 60 Hz panel and the ~90 Hz authored cadence (flags, not pass/fail gates).
_FLAGS = (
    ("publish_to_swap_ms", 20.0, "publish -> swap median over 20 ms: the frame age budget is gone"),
    ("revisions_waiting_at_sync", 0.0, "the sync consumed a stale revision while newer ones waited"),
    ("logical_tick_wall_share", 0.30, "the logical tick occupies its thread over 30% of the time in main (wall time: "
                                      "an upper bound on its GIL hold): render/GUI threads stall behind it"),
    ("main_wall_share", 0.30, "main's per-frame Visualizer work occupies its thread over 30% of the time (wall time: "
                              "an upper bound on its GIL hold): render/GUI threads stall behind it"),
    ("render_mode_ms", 8.0, "render-mode time over 8 ms: the frame no longer fits half a 60 Hz period"),
    ("steady_late_pct", 10.0, "over 10% of steady frames later than 25 ms"),
    ("post_startup_late_pct", 20.0, "over 20% of the first 2 s after startup later than 25 ms"),
    ("hitches_per_min", 0.5, "steady frames over 50 ms: a visible hitch (periodic ones point at a timer-driven GIL holder)"),
    ("usage_collect_ms", 40.0, "a usage sample takes over 40 ms of its worker thread (wall time; the per-process "
                               "working-set walk no longer holds the GIL, the rest of the sample can): check the "
                               "hitches at the sample's 15 s phase before blaming it"),
)


def _pct(values, q):
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(q * len(ordered)))] if ordered else None


def _stats(values):
    return {"median": round(statistics.median(values), 2), "p90": round(_pct(values, 0.9), 2)} if values else None


# -- analysis -----------------------------------------------------------------------------------------------------

def revision_rate(publishes: list[tuple[int, int]]) -> float | None:
    """Publications per second from the revision numbering of ``(ts, revision)`` publish records in time order: the
    sum of each step's revision advance over the time they span. On the engine-worker path the main process records
    only the frames it takes, and their revisions are the worker's publication count (``PacketMailbox``: the slot
    sequence), so this is the worker's own publication rate; a step that goes back (a new session) adds nothing."""
    if len(publishes) < 2:
        return None
    advance = sum(max(0, b[1] - a[1]) for a, b in zip(publishes, publishes[1:]))
    span = (publishes[-1][0] - publishes[0][0]) / 1e9
    return round(advance / span, 1) if span > 0 else None


def analyse_trace(path: Path, *, steady_stop_ns: int | None = None, worker_path: bool = False) -> dict:
    """The steady window's age chain from the frame trace. ``worker_path`` (the engine worker admitted): the publish
    records are the frames the main process took, each at the worker's own publish time (``PacketMailbox`` records them
    from the slot's ``publish_ns``, on the clock every process shares), so revisions/s comes from their revision
    numbering (``revision_rate``), ``publish_records_per_s`` counts them, and the waiting count and newest age at sync see only
    newer frames that main later took (lower bounds). The rest of the chain reads exactly as in process."""
    sys.path.insert(0, str(ROOT))
    from tools.frame_trace_report import HEADER, RECORD, _read_trace_chain

    raw, _segments = _read_trace_chain(path)
    events: list[tuple[int, int, int]] = []
    logical: dict[tuple[int, int], int] = {}          # (ts, revision) of a publish -> its logical timestamp (ns)
    for i in range((len(raw) - HEADER.size) // RECORD.size):
        ts, event, _screen, revision, logical_ns, _aux = RECORD.unpack_from(raw, HEADER.size + i * RECORD.size)
        events.append((ts, event, revision))
        if event == 1:
            logical[(ts, revision)] = logical_ns
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
    steady_publishes = [(ts, r) for ts, e, r in steady if e == 1]
    # The tick's own time: its logical timestamp (the tick's authored now, ``perf_counter``) to its publish, both on
    # the publishing process's clock (in process: main; worker path: the worker's stamp). Async-resolved modes carry
    # the resolved frame's time, so theirs includes the resolve.
    tick = [(ts - logical[(ts, r)]) / 1e6 for ts, r in steady_publishes if logical.get((ts, r), 0) > 0]
    tick = [value for value in tick if 0.0 <= value < 1000.0]
    records_per_s = round(len(steady_publishes) / seconds, 1)
    return {
        "path": "engine_worker" if worker_path else "in_process",
        "publish_records": ("frames main took, at the worker's publish stamp" if worker_path
                            else "every publication, at its publish"),
        "steady_seconds": round(seconds, 1),
        "revisions_per_s": revision_rate(steady_publishes) if worker_path else records_per_s,
        "publish_records_per_s": records_per_s,
        "tick_to_publish_ms": _stats(tick),
        "frames_per_s": round(len(swaps) / seconds, 1),
        "consumed_age_at_sync_ms": _stats(consumed),
        "newest_age_at_sync_ms": _stats(newest_age),
        # On the worker path main records a publish only for a frame it took, so a newer frame it never took is
        # invisible here and the count would be zero by construction: not measured, rather than a measured zero.
        "revisions_waiting_at_sync": None if worker_path else _stats(waiting),
        "revisions_waiting_at_sync_note": ("not measured on the engine worker: main records only the frames it took"
                                           if worker_path else "newer publications than the one the sync consumed"),
        "publish_to_swap_ms": _stats(to_swap),
        "render_mode_ms": _stats(render_mode),
        "swap_gap_ms": _stats(gaps),
        "steady_late_pct": round(100.0 * sum(g > LATE_MS for g in gaps) / max(len(gaps), 1), 1),
        "hitches_per_min": round(60.0 * sum(g > 50.0 for g in gaps) / seconds, 2),
        "post_startup_frames": len(early),
        "post_startup_late_pct": round(100.0 * sum(g > LATE_MS for g in early_gaps) / max(len(early_gaps), 1), 1),
        "sync_admissions_per_s": round(sum(1 for _, e, _ in steady if e == 74) / seconds, 1),
    }


#: How the recorded clip reaches the engine on each path (the tick's cost depends on it: phase-locked blocks never
#: arrive mid-tick, a capture thread's do).
AUDIO_DELIVERY = {
    True: (f"the clip's first {WORKER_PCM_LOOP_S:g} s, looped, handed to the engine in whole blocks at the worker's own "
           "cadence edges (PacedPcmSource): phase-locked to the tick, not a device's callback timing"),
    False: "the whole clip replayed as the loopback from a capture thread in real time (device-like callback timing)",
}


def tick_shares(summary: dict, *, worker_path: bool) -> dict:
    """The tick's and main's per-frame work as shares of their threads' time, labelled by process and by what was
    measured (gate 3 compares them in process and on the engine worker).

    A ``*_wall_share`` is the work's wall time per call (median) times its calls per second: how much of the time the
    thread is inside that work. It is **not** GIL hold time: it includes the time the thread waited for the GIL or
    was descheduled inside the call (at 87% system CPU most of an 11 ms tick can be waiting), and time inside C
    calls that release the GIL. A ``*_cpu_share`` is the thread's own CPU time inside the work (mean per call, from
    ``time.thread_time`` around every call, exact over a run though coarse per call) times its calls per second: what
    the thread actually ran, waits excluded. Python exposes no GIL hold time; the hold lies at or below the wall share
    and, where the work is pure Python, near the CPU share.

    ``tick_process``: where the logical tick ran. ``tick_to_publish_ms`` (from the trace, on that process's clock) is
    the tick's start (its authored now) to its publish record, before the wake; ``tick_wall_share`` is that times
    revisions/s, the same figure on both paths, in the process named by ``tick_process``.
    ``main_per_frame_work``: what the main process does per Visualizer frame; in process the logical tick
    (``logical_tick_ms``: ``_publish_logical_state``, capture + publish + the GUI wake), on the worker path the frame
    take (``frame_take_ms``: slot copy, decode and the owner's completion). ``main_wall_share`` / ``main_cpu_share``
    are its shares of its thread. ``worker_tick_ms`` / ``worker_tick_wall_share``: the engine worker's own tick in its
    own process (it never stalls main's threads; its CPU time is not read from here); None in process.
    ``audio_delivery``: how the recording reached the engine on this path."""
    def share(stats, rate, key="median"):
        value = (stats or {}).get(key)
        return round(value * rate / 1000.0, 2) if value is not None and rate else None

    tick_share = share(summary.get("tick_to_publish_ms"), summary.get("revisions_per_s"))
    if worker_path:
        take, rate = summary.get("frame_take_ms"), summary.get("publish_records_per_s")
        return {"tick_process": "engine_worker", "tick_wall_share": tick_share,
                "main_per_frame_work": "frame take (slot copy, decode, completion)",
                "main_wall_share": share(take, rate), "main_cpu_share": share(take, rate, "cpu_mean"),
                "worker_tick_ms": summary.get("tick_to_publish_ms"), "worker_tick_wall_share": tick_share,
                "audio_delivery": AUDIO_DELIVERY[True]}
    tick, rate = summary.get("logical_tick_ms"), summary.get("revisions_per_s")
    return {"tick_process": "main", "tick_wall_share": tick_share,
            "main_per_frame_work": "logical tick (_publish_logical_state: capture, publish, wake)",
            "main_wall_share": summary.get("logical_tick_wall_share"), "main_cpu_share": share(tick, rate, "cpu_mean"),
            "worker_tick_ms": None, "worker_tick_wall_share": None, "audio_delivery": AUDIO_DELIVERY[False]}


def waveform_pcm_receipt(phases: dict, *, recorded: bool, worker_path: bool) -> dict:
    """Fail closed unless the recorded PCM reached the live Waveform body, on whichever process ran it.

    In process the main side sees the body's own inputs (``eb_live_phases``' ``waveform_signals``: rows from
    ``WaveformRibbonFrameRuntime.advance``), and one row must carry bands above zero while playing with the body's own
    source identity. On the engine-worker path the body runs in the worker and main records no input rows; the receipt
    is then the frames main rendered (``waveform_frame_receipt``, ``eb_live_phases.note_waveform_frame``): at least one
    from a live body (playing, its source identity its own) whose published passage is above zero, which only audible
    input reaching that body moves (the worker plays the recording and refuses the device for its life). Input rows on
    the worker path mean the body ran in main (the run left the worker), so they fail too. No evidence on either path
    is an error. Without a recording (``--clip none``) nothing is required."""
    signals = phases.get("waveform_signals", [])
    receipt = phases.get("waveform_frame_receipt") or {}
    result = {"waveform_pcm_evidence": None, "waveform_signal_samples": len(signals),
              "waveform_burst_serial": max((row["bursts"] for row in signals), default=receipt.get("burst_serial", 0)),
              "waveform_frame_receipt": receipt or None}
    if not recorded:
        return result
    if worker_path:
        if signals:
            raise RuntimeError("Engine-worker run: the Waveform body ran in the main process "
                               f"({len(signals)} input rows); the run left the worker")
        if not receipt.get("rendered_frames"):
            raise RuntimeError("Recorded PCM never reached the engine worker's Waveform body "
                               "(no rendered frame from a live body with audible input)")
        result["waveform_pcm_evidence"] = "rendered worker frames (live body, passage > 0)"
        return result
    if not any(max(row["bands"]) > 0. and row["playing"] and row["source_identity"] == row["identity"][1:]
               for row in signals):
        raise RuntimeError("Recorded PCM never reached the live Waveform body")
    result["waveform_pcm_evidence"] = "body input rows (bands > 0, playing, own source)"
    return result


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
            settings_roundtrip: list[float] | None = None, roundtrip_memory: tuple[str, ...] = (),
            app_args: tuple[str, ...] = (), mode_switch: list[float] | None = None) -> None:
    import contextlib

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
    sys.argv = [str(ROOT / "main_mc.py"), "--perf", "--usage", "--frame-trace", "--exit-after", str(int(seconds)),
                *app_args, "/s"]
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
    stack = contextlib.ExitStack()
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
        if engine_worker_path(app_args):
            # The engine worker captures in its own process: every session it hosts plays the same recording on the
            # worker's audio clock and refuses the device (the link's recorded-capture control, as its gates use it).
            from widgets.spotify_visualizer import engine_worker_link

            stack.enter_context(engine_worker_link.recorded_capture_for_testing(
                pcm=pcm[: int(rate * WORKER_PCM_LOOP_S)], pcm_rate=int(rate)))
    phases._install()
    if engine_worker_path(app_args):
        phases._install_frame_take()          # main's per-frame cost on the worker path (the tick runs in the worker)
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
    if mode_switch:
        # The production cycle gesture at each time, one at a time (tools/live_check_mode_switch.py).
        from tools.live_check_mode_switch import ModeSwitchDriver

        from tools.live_check_settings_roundtrip import RoundTripMemoryProbe

        # --roundtrip-memory without round trips classifies at each completed switch instead (same probe, R-175).
        probe = (RoundTripMemoryProbe(roundtrip_memory, out_dir=out)
                 if roundtrip_memory and not settings_roundtrip else None)
        switcher = ModeSwitchDriver(mode_switch, began=began, state_path=out / "mode_switch.json", memory_probe=probe)
        switcher.install()
        atexit.register(switcher.finish)
    atexit.register(lambda: (out / "phases.json").write_text(json.dumps(phases._summary(), indent=1), encoding="utf-8"))
    import runpy
    with stack:
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
                                         "at every reveal; with --mode-switch alone, at every completed switch "
                                         "(runner only; settings_roundtrip_memory.json)")
    parser.add_argument("--mode-switch", metavar="AT[,AT]", type=parse_mode_switch,
                        help="make the production mode-cycle gesture AT s after the runner starts (one at a time); "
                             "a switch that never completes fails the run")
    parser.add_argument("--app-arg", action="append", default=[], type=parse_app_arg, metavar="=TOKEN",
                        help="an experiment-flag token added to the saver's argv, e.g. --app-arg=--viz-in-process "
                             "(the in-process control; the engine worker is the default)")
    parser.add_argument("--resource-readings", action="store_true",
                        help="read the saver's process tree from outside every second and --settle s after each "
                             "reveal / completed mode switch; growth fails the run (resource_summary.json)")
    parser.add_argument("--settle", type=float, default=live_check_resources.DEFAULT_SETTLE_S,
                        help="seconds after a lifecycle edge before its resource reading (default %(default)s)")
    parser.add_argument("--runner", action="store_true", help=argparse.SUPPRESS)
    return parser


def parse_app_arg(text: str) -> str:
    """An experiment admission for the saver's argv (``core.diagnostics.experiment_flags``); nothing else reaches it
    (a mode, display or log-root token could make the run visible or move its logs away from the report)."""
    from core.diagnostics.experiment_flags import experiment_flag_tokens

    token = str(text)
    needs_value = ("--abc-drive", "--abc-layout-slot", "--abc-exclude-seconds")      # only their "=" form is one token
    if experiment_flag_tokens([token]) != (token,) or token.startswith("--log-dir=") or token in needs_value:
        raise ValueError(f"--app-arg takes one experiment-flag token (e.g. --viz-in-process), got {token!r}")
    return token


def runner_command(args, out: Path, clip: Path | None) -> list[str]:
    """The child command line: every option the runner needs, forwarded as given."""
    return ([sys.executable, str(Path(__file__).resolve()), "--runner", "--mode", args.mode, "--seconds",
             str(args.seconds), "--out", str(out), "--clip", str(clip or "none"), "--clip-start",
             str(args.clip_start)] + (["--visible"] if args.visible else [])
            + (["--display-off", args.display_off] if args.display_off else [])
            + (["--settings-roundtrip", ",".join(f"{at:g}" for at in args.settings_roundtrip)]
               if args.settings_roundtrip else [])
            + (["--roundtrip-memory", ",".join(args.roundtrip_memory)]
               if (args.settings_roundtrip or args.mode_switch) and args.roundtrip_memory else [])
            + (["--mode-switch", ",".join(f"{at:g}" for at in args.mode_switch)] if args.mode_switch else [])
            + [f"--app-arg={token}" for token in args.app_arg])


def default_out(args) -> Path:
    label = args.label or artifact_paths.run_label(f"p{args.preset}" if args.preset else "profile")
    return artifact_paths.evidence_dir(f"visualizers/{args.mode}", "live_check", artifact_paths.slug(label))


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    clip = None if args.clip == "none" else Path(args.clip).resolve()
    if args.runner:
        _runner(args.out, args.seconds, args.visible, clip, args.clip_start, args.mode,
                parse_display_off(args.display_off) if args.display_off else None, args.settings_roundtrip,
                args.roundtrip_memory if (args.settings_roundtrip or args.mode_switch) else (), tuple(args.app_arg),
                args.mode_switch)
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
    resources = (live_check_resources.TreeResourceSampler(runner.pid, out, settle_s=args.settle)
                 if args.resource_readings else None)
    try:
        while runner.poll() is None:
            time.sleep(1.0)
            conditions.append(sampler.sample())
            if resources is not None:
                resources.poll(live_check_resources.recorded_edges(out))
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
        if resources is not None:
            resources.close()
    if violation:
        print("STOPPED: a saver window was visible:", *violation, sep="\n  ")
        return 2
    switches = None
    if args.mode_switch:
        state_path = out / "mode_switch.json"
        switches = analyse_mode_switches(json.loads(state_path.read_text(encoding="utf-8"))
                                         if state_path.exists() else None,
                                         times=args.mode_switch, returncode=runner.returncode)
        (out / "mode_switch_summary.json").write_text(json.dumps(switches, indent=1), encoding="utf-8")
        print_mode_switches(switches)
    resource_summary = None
    if resources is not None:
        kinds = (("settings_reveal",) if args.settings_roundtrip else ()) + (("mode_switch",) if args.mode_switch
                                                                             else ())
        resource_summary = live_check_resources.analyse_resource_readings(
            out, kinds=kinds or ("settings_reveal", "startup_reveal"))
        (out / "resource_summary.json").write_text(json.dumps(resource_summary, indent=1), encoding="utf-8")
        live_check_resources.print_resource_table(resource_summary)
    if switches is not None and switches["failures"]:
        print(f"FAILED: {len(switches['failures'])} mode switch failure(s); see {out / 'mode_switch_summary.json'}")
        return 3
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
    result = _report(args, out, clip, overrides, summarise_environment(conditions), power_samples, tree, roundtrips)
    if resource_summary is not None and (resource_summary["growth"] or resource_summary["exact_not_flat"]):
        print(f"FAILED: resource growth {resource_summary['growth']}, exact counts not flat "
              f"{resource_summary['exact_not_flat']}; see {out / 'resource_summary.json'}")
        return 4
    return result


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
    worker_path = engine_worker_path(args.app_arg)
    summary.update(analyse_trace(trace, steady_stop_ns=edges[0]["perf_ns"] if edges else None,
                                 worker_path=worker_path))
    if worker_path and not summary["publish_records_per_s"]:
        # Fail closed: without the worker's publish stamps the age chain would read as empty, not as measured.
        raise RuntimeError("engine-worker run recorded no publish in the trace (no publish_ns reached the main side)")
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
            summary.update(waveform_pcm_receipt(phases, recorded=clip is not None, worker_path=worker_path))
        tick = phases.get("logical_publish")
        summary["logical_tick_ms"] = tick
        if tick:
            summary["logical_tick_wall_share"] = round(tick["median"] * summary["revisions_per_s"] / 1000.0, 2)
        summary["frame_take_ms"] = phases.get("frame_take")
        summary["render_stages_ms"] = {k: v for k, v in phases.items()
                                       if isinstance(v, dict) and k not in ("logical_publish", "frame_take")}
    summary.update(tick_shares(summary, worker_path=worker_path))
    (out / "summary.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
    for key, value in summary.items():
        if key not in ("render_stages_ms", "process_tree", "actual_waveform_configuration", "display_power",
                       "settings_roundtrip"):
            print(f"{key:28s} {value}")
    for key, limit, message in _FLAGS:
        if key == "main_wall_share" and summary.get("tick_process") == "main":
            continue                                   # in process it is logical_tick_wall_share, flagged above
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
