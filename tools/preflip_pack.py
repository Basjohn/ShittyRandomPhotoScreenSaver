"""Pre-flip reference pack: the same matrix before and after the flip, gain per row.

A thin driver over ``tools/visualizer_live_check.py`` (the invisible saver on recorded music, one process per row) and
``tools/overhead_baseline.py`` (the offscreen Crossfade control that makes sessions comparable). It adds no
measurement of its own: it enumerates the matrix from the registries, runs each row through the live check, stores
the figures with the conditions they were taken under, and compares two stored baselines.

The matrix (``--list`` prints it and the time it needs, starting nothing):

* every Visualizer mode of ``iter_visualizer_mode_descriptors()`` at its canonical default preset slot (one process
  per mode), and the five transitions of ``SESSION_TRANSITIONS`` (a named set, not a registry sweep: the four heaviest
  by measured cost and Crossfade as the light control; per-transition parity is proved at each port, so this is a load
  comparison). The transitions run as ONE saver session per size and state (``--per-row`` makes each transition its own
  one-transition session; a transition row is never measured outside a session, whose figures alone describe a
  transition): the saver cycles the five in a fixed order, one per image change, and each one's window is cut from the
  frame trace by its run's first and last background-render records, or on the native core's background layer
  (Vulkan) by its run's tick and end records (``tools/live_check_transition_session.py``); a transition whose window has
  no end record is stored failed. Each window also stores the run's hitch figures and verdict (the render thread's
  frame gaps inside it, ``run_gaps``: no gap over 33 ms, the first frame from the run's start included).
  Every other registered transition is selectable as a row by ``--rows`` (``transition/<id>/*``) at the same size and
  state, without joining the default matrix; a transition port records its pre-port row on its own (``--name`` an existing
  baseline adds rows, leaving the rest) and compares the native row against it (``--compare``).
  The profile copy's transition durations are pinned to the canonical ones. A transition window has no swap records
  (the saver has no Visualizer), so its frame pacing, stored as the swap gap, is the gap between Quick's rendered frames;
* one size: ``2160p`` = Display 1 at 3840 x 2160, invisible saver (the windows have an empty region and never show a
  pixel). Nothing runs on Display 0, which is the primary: a primary display is refused outright. The saver's window
  always takes its display's own resolution, so there is no 2560 x 1440 view of Display 1 without changing the product;
* the Usu wallpaper folder and the ``anything_mixed2`` recording, ``--noupdates``;
* two states: ``idle`` (default) and ``loaded`` (``--load game60``: the existing ``tools/gpu_load_generator.py``;
  explicit only, lead only, after the operator's yes, never a default).

    python tools/preflip_pack.py --list
    python tools/preflip_pack.py --rows "visualizer/*"                              # one window, one slice
    python tools/preflip_pack.py --rows "transition/crossfade/*"                    # one row: its own process
    python tools/preflip_pack.py --rows "transition/beam/*" --name before_beam --backend python-gl   # any registered one
    python tools/preflip_pack.py --name before_flip                                 # resumable: reruns skip ok rows
    python tools/preflip_pack.py --name after_flip --compare tools/baselines/preflip/before_flip.json
    python tools/preflip_pack.py --compare-only OLD.json NEW.json

Per row it stores fps, render time (median and p90: the Visualizer's own draw for a mode, Quick's render phase for a
transition row), swap gap, late %, hitches a minute, the saver tree's CPU % of a core, GPU ms per frame (derived from
the tree's GPU engine utilisation over the frame rate, ``null`` when the counters are unavailable), RSS and private
memory and the frames in the first 2 s after startup, plus the conditions: which displays were present, the busiest
other processes by CPU and GPU, the GPU's clock and ``nvidia-smi`` state before the row, and the system sampler's
medians during it. A baseline also carries the offscreen Crossfade control per size, so a comparison can say how far
the session itself moved (``Docs/Reference/Benchmarks.md``: compare within a session, control-relative).
"""
from __future__ import annotations

import argparse
import datetime as _dt
import fnmatch
import json
import shutil
import statistics
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools import artifact_paths  # noqa: E402

BASELINES = ROOT / "tools" / "baselines" / "preflip"
#: Tokens for the live check's ``--app-arg`` (``--app-arg`` here; set once by ``main``): a native Vulkan row passes
#: ``--graphics-backend=vulkan``. Empty for the product's default OpenGL path.
APP_ARGS: list[str] = []
#: Persisted settings every row and session also writes, after its own (``--setting KEY=JSON``; set once by ``main``):
#: a port's run with a look its defaults leave off (N5.2d: motion blur and trails, ``transitions.<section>.motion_blur``).
EXTRA_SETTINGS: list[tuple[str, object]] = []
WALLPAPER = Path("D:/Temp/Scratch/SRPSS/wallpaper_usu")
CLIP = ROOT / "logs" / "visualizer_recordings" / "anything_mixed2.jsonl"
APPLICATION = "Screensaver_MC"

VIZ_SECONDS = 45.0                  # the live check's ``--seconds`` for a Visualizer row (the 15 Nov pass's)
TRANSITION_SECONDS = 75.0           # a per-row transition run: several repeats of one transition
TRANSITION_INTERVAL_S = 8           # fallback image interval when a transition's duration is unknown
ROW_OVERHEAD_S = 30.0               # profile copy, startup, teardown (the live check's own figure)
LOAD_CALIBRATION_S = 25.0           # game60's calibration before the saver starts (an estimate)
CONTROL_SECONDS = 60.0              # the offscreen control run, estimated
GAIN_BAND_PCT = 5.0                 # a row's figure counts as moved only beyond this
SCHEMA = 1
RESOURCE_GROWTH_EXIT = 4        # the live check's exit when --resource-readings finds growth
LOADS = ("game60",)

# The transition set, chosen once (operator, 15 Nov: per-transition parity and regressions are proved at each port, so
# this is only a load comparison). By measured cost in tools/baselines/overhead/2026-11-14_756c9237.json: the four
# heaviest (Exploding Tiles 0.50 CPU + 0.09 GPU ms, Volumetric Dissolve, Disintegrate, Jigsaw, also the heaviest geometry
# prepare) and one light control, Crossfade, already pure data on the native core. The order is the session's order.
SESSION_TRANSITIONS = ("exploding_tiles", "volumetric_dissolve", "disintegrate", "jigsaw", "crossfade")


@dataclass(frozen=True)
class Size:
    name: str
    display: int
    width: int
    height: int


SIZES = {"2160p": Size("2160p", 1, 3840, 2160)}


@dataclass(frozen=True)
class Row:
    key: str                # kind/id/size/state
    kind: str               # visualizer | transition
    ident: str              # mode id | transition stable id
    label: str              # transition setting name | mode id
    size: str
    state: str              # idle | loaded
    seconds: float


# -- the metrics: name, heading, which direction is better --------------------------------------------------------------

METRICS = (
    ("fps", "fps", "higher"),
    ("render_median_ms", "render med ms", "lower"),
    ("render_p90_ms", "render p90 ms", "lower"),
    ("swap_gap_median_ms", "swap gap med ms", "lower"),
    ("swap_gap_p90_ms", "swap gap p90 ms", "lower"),
    ("late_pct", "late %", "lower"),
    ("hitches_per_min", "hitches/min", "lower"),
    ("cpu_core_pct", "saver CPU % core", "lower"),
    ("gpu_ms_per_frame", "GPU ms/frame", "lower"),
    ("rss_mb", "RSS MB", "lower"),
    ("private_mb", "private MB", "lower"),
    ("first2s_frames", "first 2 s frames", "higher"),
)


# -- the matrix ---------------------------------------------------------------------------------------------------------

def registry_visualizer_modes() -> list[str]:
    from core.settings.visualizer_mode_registry import iter_visualizer_mode_descriptors

    return [descriptor.mode_id for descriptor in iter_visualizer_mode_descriptors()]


def registry_transitions(names=SESSION_TRANSITIONS) -> list[tuple[str, str]]:
    """``(stable_id, setting_name)`` of the named transitions in the given order, read from the registry. A name the
    registry no longer has or no longer offers is an error: the set is chosen, not swept."""
    from rendering.transition_registry import iter_transition_descriptors

    available = {item.stable_id: item.setting_name for item in iter_transition_descriptors() if item.available}
    missing = [name for name in names if name not in available]
    if missing:
        raise ValueError(f"SESSION_TRANSITIONS names {missing}, which the transition registry does not offer")
    return [(name, available[name]) for name in names]


def all_registry_transitions() -> list[tuple[str, str]]:
    """``(stable_id, setting_name)`` of every transition the registry offers, in registry order. These are selectable as
    rows by ``--rows`` (a transition port's layer T) without joining the default matrix, which stays the five of
    ``SESSION_TRANSITIONS``; their keys are ``transition/<stable_id>/<size>/<state>`` like the default rows'."""
    from rendering.transition_registry import iter_transition_descriptors

    return [(item.stable_id, item.setting_name) for item in iter_transition_descriptors() if item.available]


def canonical_transition_durations() -> dict[str, float]:
    """The canonical per-transition durations in milliseconds, by setting name."""
    from core.settings.default_contract import get_canonical_default

    stored = get_canonical_default("transitions.durations", APPLICATION, missing=None)
    return {str(k): float(v) for k, v in (stored or {}).items() if isinstance(v, (int, float))}


def session_interval(labels, durations=None) -> int:
    """Image interval of a session over ``labels``: the longest of their durations completes, then a short settle."""
    from tools.live_check_transition_session import session_interval_s

    known = canonical_transition_durations() if durations is None else durations
    values = [known[label] for label in labels if label in known]
    return session_interval_s(values) if values else TRANSITION_INTERVAL_S


def row_seconds(kind: str, *, viz_seconds: float = VIZ_SECONDS, transition_seconds: float = TRANSITION_SECONDS) -> float:
    return transition_seconds if kind == "transition" else viz_seconds


def enumerate_rows(sizes, state: str, *, modes=None, transitions=None, viz_seconds: float = VIZ_SECONDS,
                   transition_seconds: float = TRANSITION_SECONDS) -> list[Row]:
    """Every row of the matrix for ``sizes`` in one ``state``, enumerated from the registries (or from the injected
    ``modes`` and ``transitions`` providers, which tests use): size-major, Visualizer modes before transitions."""
    mode_ids = list(registry_visualizer_modes() if modes is None else modes)
    transition_ids = list(registry_transitions() if transitions is None else transitions)
    rows = []
    for size in sizes:
        for mode in mode_ids:
            rows.append(Row(f"visualizer/{mode}/{size}/{state}", "visualizer", mode, mode, size, state,
                            viz_seconds))
        for ident, label in transition_ids:
            rows.append(Row(f"transition/{ident}/{size}/{state}", "transition", ident, label, size, state,
                            transition_seconds))
    keys = [row.key for row in rows]
    if len(keys) != len(set(keys)):
        raise ValueError("the matrix has a duplicate row key")
    return rows


def filter_rows(rows: list[Row], patterns: list[str] | None) -> tuple[list[Row], list[str]]:
    """Rows whose key matches any ``fnmatch`` pattern (all rows without patterns), and the patterns that matched none."""
    if not patterns:
        return list(rows), []
    chosen = [row for row in rows if any(fnmatch.fnmatchcase(row.key, pattern) for pattern in patterns)]
    unmatched = [pattern for pattern in patterns if not any(fnmatch.fnmatchcase(row.key, pattern) for row in rows)]
    return chosen, unmatched


def split_patterns(text: str | None) -> list[str]:
    return [part.strip() for part in str(text or "").split(",") if part.strip()]


def pending_rows(rows: list[Row], baseline: dict, *, redo: bool = False) -> list[Row]:
    """Rows still to measure: a row already stored ``ok`` is skipped (resume) unless ``redo``."""
    stored = baseline.get("rows", {})
    return [row for row in rows if redo or stored.get(row.key, {}).get("status") != "ok"]


def plan_units(rows: list[Row], *, per_row: bool = False) -> list[tuple[str, object]]:
    """The saver processes the rows need: ``("row", Row)`` for one process per row, ``("session", [Row, ...])`` for the
    transition rows of one size and state run as one session (in the order the rows have). A transition row is always
    measured in a session (21 Nov: a per-row process reports the Visualizer's fps and late frames, which a saver without
    one never has): ``per_row`` makes each transition its own one-transition session and every Visualizer row its own
    process."""
    if per_row:
        return [("session", [row]) if row.kind == "transition" else ("row", row) for row in rows]
    groups: dict[tuple[str, str], list[Row]] = {}
    for row in rows:
        if row.kind == "transition":
            groups.setdefault((row.size, row.state), []).append(row)
    units, placed = [], set()
    for row in rows:
        group = groups.get((row.size, row.state)) if row.kind == "transition" else None
        if group is None:
            units.append(("row", row))
        elif (row.size, row.state) not in placed:
            placed.add((row.size, row.state))
            units.append(("session", group))
    return units


def unit_seconds(unit, *, durations=None) -> float:
    """The unit's own run time (startup and teardown excluded)."""
    from tools.live_check_transition_session import session_seconds

    kind, payload = unit
    if kind == "row":
        return payload.seconds
    return session_seconds(len(payload), session_interval([r.label for r in payload], durations))


def estimate_seconds(rows: list[Row], *, loaded: bool = False, per_row: bool = False, durations=None) -> float:
    """Wall time the rows take: each saver process's run plus the live check's startup and teardown (and game60's
    calibration)."""
    return sum(unit_seconds(unit, durations=durations) + ROW_OVERHEAD_S + (LOAD_CALIBRATION_S if loaded else 0.0)
               for unit in plan_units(rows, per_row=per_row))


def default_preset_slot(mode: str) -> int:
    """The 1-based preset slot a fresh profile opens on for ``mode`` (the canonical default, not the operator's own)."""
    from core.settings.default_contract import get_canonical_default

    stored = get_canonical_default(f"widgets.spotify_visualizer.preset_{mode}", APPLICATION, missing=None)
    return (int(stored) if isinstance(stored, int) and not isinstance(stored, bool) and stored >= 0 else 0) + 1


# -- one row: the live check's command line ---------------------------------------------------------------------------

def pinned_durations(labels) -> list[tuple[str, object]]:
    """The canonical duration of each transition, written into the profile copy: the copy starts from the operator's own
    profile, whose durations differ (a 15 Nov check saw Crossfade at 12 s and Exploding Tiles at 7.3 s against the
    canonical 8 s), and a before and an after run must time the same transition length."""
    known = canonical_transition_durations()
    return [(f"transitions.durations.{label}", int(known[label])) for label in labels if label in known]


def row_settings(row: Row) -> list[tuple[str, object]]:
    """Persisted settings written into the row's profile copy (through ``SettingsManager``, read back)."""
    from core.settings.default_contract import IMAGE_INTERVAL_MAX_SECONDS

    settings: list[tuple[str, object]] = [("sources.mode", "folders"), ("sources.folders", [str(WALLPAPER)])]
    if row.kind == "visualizer":
        # No transition inside the window: the row measures the Visualizer, not an image change.
        settings.append(("timing.interval", IMAGE_INTERVAL_MAX_SECONDS))
    else:
        settings += [("widgets.spotify_visualizer.enabled", False), ("timing.interval", session_interval([row.label])),
                     ("transitions.random_always", False), ("transitions.type", row.label),
                     (f"transitions.activation.{row.label}", True), *pinned_durations([row.label])]
    return settings + EXTRA_SETTINGS


def session_settings(rows: list[Row], interval_s: int) -> list[tuple[str, object]]:
    """Persisted settings of a transition session: the first transition is the opening type, every one is activated, and
    the image interval lets the longest complete and settle (the driver writes ``transitions.type`` before each change)."""
    settings: list[tuple[str, object]] = [
        ("sources.mode", "folders"), ("sources.folders", [str(WALLPAPER)]),
        ("widgets.spotify_visualizer.enabled", False), ("timing.interval", int(interval_s)),
        ("transitions.random_always", False), ("transitions.type", rows[0].label)]
    settings += [(f"transitions.activation.{row.label}", True) for row in rows]
    return settings + pinned_durations([row.label for row in rows]) + EXTRA_SETTINGS


def session_command(rows: list[Row], out: Path, *, interval_s: int, clip: Path = CLIP,
                    python: str | None = None) -> list[str]:
    """The live check's command line for one transition session of ``rows`` (one process, one size, invisible)."""
    from tools.live_check_transition_session import session_seconds

    size = SIZES[rows[0].size]
    command = [python or sys.executable, str(ROOT / "tools" / "visualizer_live_check.py"), "--mode", "none",
               "--seconds", f"{session_seconds(len(rows), interval_s):g}", "--out", str(out), "--clip", str(clip),
               "--display", str(size.display), "--no-updates", "--process-samples",
               "--transition-session", ",".join(row.label for row in rows)]
    if rows[0].state == "loaded":
        command += ["--load", "game60"]
    command += [f"--app-arg={token}" for token in APP_ARGS]
    for key, value in session_settings(rows, interval_s):
        command.append(f"--setting={key}={json.dumps(value)}")
    return command


def row_command(row: Row, out: Path, *, clip: Path = CLIP, preset_slot=None, python: str | None = None) -> list[str]:
    """The live check's command line for ``row`` (one process, one size, invisible)."""
    size = SIZES[row.size]
    command = [python or sys.executable, str(ROOT / "tools" / "visualizer_live_check.py"),
               "--mode", row.ident if row.kind == "visualizer" else "none",
               "--seconds", f"{row.seconds:g}", "--out", str(out), "--clip", str(clip), "--display", str(size.display),
               "--no-updates", "--process-samples"]
    if row.kind == "visualizer":
        # --resource-readings as the 15 Nov pass ran: the same process also reads its own handles and memory growth.
        command += ["--preset", str((preset_slot or default_preset_slot)(row.ident)), "--resource-readings"]
    if row.state == "loaded":
        command += ["--load", "game60"]
    command += [f"--app-arg={token}" for token in APP_ARGS]
    for key, value in row_settings(row):
        command.append(f"--setting={key}={json.dumps(value)}")
    return command


def display_problem(size: Size, displays: list[dict]) -> str | None:
    """Why a row cannot run on ``size``'s display now (None when it can): the display is missing, is not that size, or
    is the primary (the pack never presents on it). Displays are dicts with ``index``, ``width``, ``height`` (device
    pixels) and ``primary``."""
    present = next((d for d in displays if int(d["index"]) == size.display), None)
    if present is None:
        return f"display {size.display} is not present (present: {sorted(int(d['index']) for d in displays)})"
    if abs(int(present["width"]) - size.width) > 2 or abs(int(present["height"]) - size.height) > 2:
        return (f"display {size.display} is {present['width']} x {present['height']}, the {size.name} rows need "
                f"{size.width} x {size.height}")
    if present.get("primary"):
        return f"display {size.display} is the primary display; the pack never runs there"
    return None


# -- figures ------------------------------------------------------------------------------------------------------------

def _stat(block, key):
    return block.get(key) if isinstance(block, dict) else None


def extract_figures(summary: dict) -> dict:
    """The row's stored figures from the live check's ``summary.json``. The render time is the Visualizer's own draw
    (``render_mode_ms``) where there is one, else Quick's render phase (``quick_render_ms``); ``render_source`` says which."""
    render, source = summary.get("render_mode_ms"), "render_mode_ms"
    if not render:
        render, source = summary.get("quick_render_ms"), "quick_render_ms"
    swap = summary.get("swap_gap_ms")
    process = summary.get("process") or {}
    return {
        "fps": summary.get("frames_per_s"),
        "render_median_ms": _stat(render, "median"), "render_p90_ms": _stat(render, "p90"),
        "render_source": source if render else None,
        "swap_gap_median_ms": _stat(swap, "median"), "swap_gap_p90_ms": _stat(swap, "p90"),
        "late_pct": summary.get("steady_late_pct"), "hitches_per_min": summary.get("hitches_per_min"),
        "cpu_core_pct": process.get("cpu_core_pct"), "gpu_pct": process.get("gpu_pct"),
        "gpu_ms_per_frame": process.get("gpu_ms_per_frame"),
        "rss_mb": process.get("rss_mb"), "private_mb": process.get("private_mb"),
        "first2s_frames": summary.get("post_startup_frames"), "first2s_late_pct": summary.get("post_startup_late_pct"),
        "steady_seconds": summary.get("steady_seconds"),
    }


# -- conditions -----------------------------------------------------------------------------------------------------------

def displays_state(required: dict[str, Size], displays: list[dict]) -> dict:
    """Whether the displays the matrix needs are present at the right size ("on"); a powered-off panel drops out of the
    desktop, so a missing or resized display reads as off."""
    missing = {}
    for name, size in required.items():
        present = next((d for d in displays if int(d["index"]) == size.display), None)
        if present is None or abs(int(present["width"]) - size.width) > 2 or abs(int(present["height"]) - size.height) > 2:
            missing[name] = f"display {size.display} " + ("absent" if present is None else
                                                          f"{present['width']} x {present['height']}")
    return {"displays_on": not missing, "missing": missing, "present": displays}


def collect_conditions(*, required: dict[str, Size], displays_fn, processes_fn, gpu_processes_fn, nvidia_fn,
                       clock=time.time) -> dict:
    """The conditions block taken before a row: displays on or off, the busiest other processes by CPU and by GPU, the
    GPU's clock and the ``nvidia-smi`` state. Every source is injected (``None`` or an exception reads as unavailable)."""
    def safe(function, default=None):
        try:
            return function()
        except Exception as exc:                       # a missing counter must never stop a measurement
            return default if default is not None else {"unavailable": f"{type(exc).__name__}: {exc}"}

    block = {"captured_at": _dt.datetime.fromtimestamp(clock()).isoformat(timespec="seconds"),
             "displays": displays_state(required, safe(displays_fn, [])),
             "other_processes_cpu": safe(processes_fn), "other_processes_gpu": safe(gpu_processes_fn),
             "nvidia_smi": safe(nvidia_fn)}
    smi = block["nvidia_smi"] if isinstance(block["nvidia_smi"], dict) else {}
    block["gpu_clock_mhz"] = smi.get("clocks_gr_mhz")
    return block


def system_displays() -> list[dict]:
    from tools.d1_run import enumerate_displays

    return [{"index": d.index, "width": d.device_size[0], "height": d.device_size[1], "primary": d.primary,
             "dpr": d.dpr, "name": d.name} for d in enumerate_displays()]


def system_cpu_processes(limit: int = 5, sample_s: float = 1.0) -> list[dict]:
    """The busiest processes by CPU over ``sample_s`` seconds (per cent of one core)."""
    import psutil

    own = {psutil.Process().pid}
    processes = []
    for process in psutil.process_iter(["pid", "name"]):
        try:
            process.cpu_percent(None)
            processes.append(process)
        except psutil.Error:
            continue
    time.sleep(sample_s)
    rows = []
    for process in processes:
        try:
            rows.append({"pid": process.pid, "name": process.info["name"], "cpu_core_pct": process.cpu_percent(None)})
        except psutil.Error:
            continue
    rows = [row for row in rows if row["pid"] not in own and row["cpu_core_pct"] > 0.0]
    return sorted(rows, key=lambda row: -row["cpu_core_pct"])[:limit]


def system_gpu_processes(limit: int = 5, sample_s: float = 1.0) -> list[dict] | None:
    """The busiest processes by GPU engine utilisation over ``sample_s`` seconds (None without the counters)."""
    import psutil
    from tools.visualizer_live_check import _ProcessGpu

    gpu = _ProcessGpu()
    if gpu.by_pid() is None:
        return None
    time.sleep(sample_s)
    readings = gpu.by_pid() or {}
    rows = []
    for pid, value in sorted(readings.items(), key=lambda item: -item[1])[:limit]:
        if value <= 0.0:
            continue
        try:
            name = psutil.Process(pid).name()
        except psutil.Error:
            name = "?"
        rows.append({"pid": pid, "name": name, "gpu_pct": value})
    return rows


def system_nvidia_state() -> dict:
    smi = shutil.which("nvidia-smi")
    if not smi:
        return {"available": False}
    query = ("name,driver_version,pstate,utilization.gpu,clocks.gr,clocks.mem,temperature.gpu,power.draw,"
             "memory.used,clocks_throttle_reasons.active")
    out = subprocess.run([smi, f"--query-gpu={query}", "--format=csv,noheader,nounits"], capture_output=True, text=True,
                         timeout=10, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout.splitlines()[0]
    names = ("name", "driver", "pstate", "util_pct", "clocks_gr_mhz", "clocks_mem_mhz", "temp_c", "power_w",
             "memory_used_mb", "throttle_reasons")
    values = dict(zip(names, (part.strip() for part in out.split(","))))
    for name in ("util_pct", "clocks_gr_mhz", "clocks_mem_mhz", "temp_c", "power_w", "memory_used_mb"):
        try:
            values[name] = float(values[name])
        except (KeyError, ValueError):
            values[name] = None
    return {"available": True, **values}


# -- the session control (the offscreen Crossfade control of tools/overhead_baseline.py) ---------------------------------

def control_from_baseline(data: dict) -> dict:
    """The control figures from an ``overhead_baseline`` result: its load block (control GPU time, other processes' CPU,
    GPU clock) and the renderer."""
    load = data.get("load", {}) or {}
    return {"size": data.get("size"), "renderer": data.get("renderer"), "commit": data.get("commit"),
            "control_gpu_quiet_ms": load.get("control_gpu_quiet"), "control_gpu_min_ms": load.get("control_gpu_min"),
            "control_gpu_max_ms": load.get("control_gpu_max"), "admitted": load.get("admitted"),
            "controls": load.get("controls"), "cpu_others_median": load.get("cpu_others_median"),
            "gpu_clock_mhz_median": load.get("gpu_clock_mhz_median")}


def measure_control(size: Size, out: Path) -> dict:
    """Run the offscreen Crossfade control at the size (``overhead_baseline.py --match crossfade``) and read it back."""
    command = [sys.executable, str(ROOT / "tools" / "overhead_baseline.py"), "--only", "transitions", "--match",
               "crossfade", "--size", f"{size.width}x{size.height}", "--out", str(out)]
    subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=CONTROL_SECONDS * 5, check=True)
    return control_from_baseline(json.loads(out.read_text(encoding="utf-8")))


# -- baseline storage ---------------------------------------------------------------------------------------------------

def baseline_path(name: str) -> Path:
    return BASELINES / f"{artifact_paths.slug(name)}.json"


def new_baseline(name: str, *, commit: str, load: str | None, backend: str | None, now=None) -> dict:
    stamp = (now or _dt.datetime.now()).isoformat(timespec="seconds")
    return {"schema": SCHEMA, "name": name, "commit": commit, "created": stamp, "updated": stamp, "backend": backend,
            "clip": CLIP.name, "wallpaper": str(WALLPAPER), "load": load, "controls": {}, "rows": {},
            "settings": {"viz_seconds": VIZ_SECONDS, "transition_seconds": TRANSITION_SECONDS,
                         "transition_interval_s": TRANSITION_INTERVAL_S,
                         "session_transitions": list(SESSION_TRANSITIONS)}}


def load_baseline(path: Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def save_baseline(path: Path, data: dict, *, now=None) -> None:
    """Atomic: a row's result is on disk before the next row starts, whatever stops the run."""
    data["updated"] = (now or _dt.datetime.now()).isoformat(timespec="seconds")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(data, indent=1) + "\n", encoding="utf-8")
    temporary.replace(path)


def commit_id() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True,
                              timeout=10).stdout.strip() or "unknown"
    except (OSError, subprocess.SubprocessError):
        return "unknown"


# -- running ------------------------------------------------------------------------------------------------------------

def run_live_check_row(row: Row, out: Path, *, timeout_s: float, keep_logs: bool) -> tuple[int, dict | None]:
    """Run one row through the live check; returns (exit code, its ``summary.json`` or None)."""
    return _run_live_check(row_command(row, out), out, timeout_s=timeout_s, keep_logs=keep_logs)


def run_live_check_session(rows: list[Row], out: Path, *, timeout_s: float,
                           keep_logs: bool) -> tuple[int, dict | None]:
    """Run one transition session through the live check; returns (exit code, its ``summary.json`` or None)."""
    return _run_live_check(session_command(rows, out, interval_s=session_interval([r.label for r in rows])), out,
                           timeout_s=timeout_s, keep_logs=keep_logs)


def _run_live_check(command: list[str], out: Path, *, timeout_s: float, keep_logs: bool) -> tuple[int, dict | None]:
    out.mkdir(parents=True, exist_ok=True)
    with (out / "pack_row.txt").open("w", encoding="utf-8") as log:
        log.write(" ".join(command) + "\n")
        log.flush()
        process = subprocess.Popen(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
        try:
            code = process.wait(timeout=timeout_s)
        except subprocess.TimeoutExpired:
            subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], capture_output=True)
            code = -9
    summary_path = out / "summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8")) if summary_path.exists() else None
    if not keep_logs and (out / "logs").exists():
        shutil.rmtree(out / "logs", ignore_errors=True)
    return code, summary


def session_figures(window: dict) -> dict:
    """A session row's stored figures from its transition window (``live_check_transition_session``): the same names a
    per-row run stores. Quick's render phase is the render time; the first-2-seconds figures belong to a process start
    and are not stored for a window. ``late_frames``, ``hitches`` and ``frames`` are the window's own counts."""
    process = window.get("process") or {}
    render, swap = window.get("quick_render_ms"), window.get("swap_gap_ms")
    return {
        "fps": window.get("fps"),
        "render_median_ms": _stat(render, "median"), "render_p90_ms": _stat(render, "p90"),
        "render_source": "quick_render_ms" if render else None,
        "swap_gap_median_ms": _stat(swap, "median"), "swap_gap_p90_ms": _stat(swap, "p90"),
        "frame_source": window.get("frame_source"),
        "late_pct": window.get("steady_late_pct"), "hitches_per_min": window.get("hitches_per_min"),
        "cpu_core_pct": process.get("cpu_core_pct"), "gpu_pct": process.get("gpu_pct"),
        "gpu_ms_per_frame": process.get("gpu_ms_per_frame"),
        "rss_mb": process.get("rss_mb"), "private_mb": process.get("private_mb"),
        "first2s_frames": None, "first2s_late_pct": None, "steady_seconds": window.get("window_s"),
        "late_frames": window.get("late_frames"), "hitches": window.get("hitches"), "frames": window.get("frames"),
        "run_id": window.get("run_id"),
        # The run's hitch figures (``live_check_transition_session.run_gaps``): the render thread's frame gaps inside
        # the run, its first frame from the run's start, and the verdict (no gap over the limit).
        "gap_ms": window.get("gap_ms"), "first_frame_ms": window.get("first_frame_ms"),
        "gaps_over_limit": window.get("gaps_over_limit"), "gap_limit_ms": window.get("gap_limit_ms"),
        "hitch_verdict": window.get("hitch_verdict"),
    }


def session_records(rows: list[Row], code: int, summary: dict | None, out: Path, before: dict, seconds: float) -> list[dict]:
    """One stored record per row of a session, keyed and shaped as a per-row run's (so ``--compare`` reads them alike).
    A row is ok only when the session produced a complete window for it; everything else is stored failed with why."""
    analysis = (summary or {}).get("transition_session") or {}
    by_name = {item["name"]: item for item in analysis.get("rows", ())}
    records = []
    for row in rows:
        window = by_name.get(row.label)
        record = {"key": row.key, "kind": row.kind, "id": row.ident, "label": row.label, "size": row.size,
                  "state": row.state, "seconds": row.seconds, "exit_code": code, "evidence": str(out),
                  "measured_in_s": round(seconds, 1), "conditions_before": before, "session": True,
                  "conditions_during": (summary or {}).get("conditions")}
        if window and window.get("status") == "ok" and code in (0, 3):
            record.update(status="ok", figures=session_figures(window))
        else:
            reason = (window or {}).get("reason") or (f"the session exited {code} and left no window for this transition"
                                                       if window is None else "no complete window")
            record.update(status="failed", figures=None, failure=reason)
        records.append(record)
    return records


def _log_record(record: dict, log) -> None:
    fig = record["figures"] or {}
    gaps = fig.get("gap_ms") or {}
    hitch = (f"  gaps {gaps.get('median')}/{gaps.get('p90')}/{gaps.get('max')} ms, first {fig.get('first_frame_ms')} ms, "
             f"over {fig.get('gap_limit_ms')} ms: {fig.get('gaps_over_limit')}  {fig.get('hitch_verdict')}"
             if "hitch_verdict" in fig else "")
    log(f"  {record['status']:6s} {record['key']}  fps {fig.get('fps')}  render {fig.get('render_median_ms')}/"
        f"{fig.get('render_p90_ms')} ms  late {fig.get('late_pct')} %  cpu {fig.get('cpu_core_pct')} %" + hitch
        + (f"  ({record['failure']})" if record.get("failure") else ""))


def measure_rows(rows: list[Row], baseline: dict, path: Path, *, measure, conditions_fn, displays_fn, out_dir_fn,
                 measure_session, save=save_baseline, redo: bool = False, log=print, clock=time.time,
                 per_row: bool = False) -> dict:
    """Measure ``rows`` one saver process after another, storing each result in ``baseline`` and on disk as it lands.
    Returns ``{"ok": [...], "failed": [...], "skipped": {key: reason}}``. ``measure(row, out) -> (exit code, summary or
    None)`` measures a Visualizer row; ``measure_session(rows, out) -> (exit code, summary or None)`` the pending
    transition rows of one size and state as one session (see ``plan_units``; with ``per_row`` one session each)."""
    outcome = {"ok": [], "failed": [], "skipped": {}}
    for kind, payload in plan_units(pending_rows(rows, baseline, redo=redo), per_row=per_row):
        group = payload if kind == "session" else [payload]
        problem = display_problem(SIZES[group[0].size], displays_fn())
        if problem:
            for row in group:
                outcome["skipped"][row.key] = problem
                log(f"  skip   {row.key}: {problem}")
            continue
        before = conditions_fn()
        began = clock()
        if kind == "session":
            out = out_dir_fn(group[0], session=True)
            code, summary = measure_session(group, out)
            records = session_records(group, code, summary, out, before, clock() - began)
        else:
            out = out_dir_fn(payload)
            code, summary = measure(payload, out)
            record = {"key": payload.key, "kind": payload.kind, "id": payload.ident, "label": payload.label,
                      "size": payload.size, "state": payload.state, "seconds": payload.seconds, "exit_code": code,
                      "evidence": str(out), "measured_in_s": round(clock() - began, 1), "conditions_before": before}
            # Exit 4 is the resource readings' growth verdict: the figures are measured, the growth is a finding.
            if code in (0, RESOURCE_GROWTH_EXIT) and summary:
                record.update(status="ok", figures=extract_figures(summary), conditions_during=summary.get("conditions"),
                              resource_growth=code == RESOURCE_GROWTH_EXIT)
            else:
                record.update(status="failed", figures=None, conditions_during=(summary or {}).get("conditions"))
            records = [record]
        for record in records:
            outcome["ok" if record["status"] == "ok" else "failed"].append(record["key"])
            baseline["rows"][record["key"]] = record
            save(path, baseline)
            _log_record(record, log)
    return outcome


# -- comparison ---------------------------------------------------------------------------------------------------------

def gain_pct(old, new, better: str) -> float | None:
    """Per cent improvement of ``new`` over ``old``: positive is better whichever way the figure runs. None when either
    figure is missing or ``old`` is zero (no ratio exists)."""
    if old is None or new is None or old == 0:
        return None
    change = (new - old) / abs(old) * 100.0
    return round(change if better == "higher" else -change, 1)


def verdict(gain: float | None, band: float = GAIN_BAND_PCT) -> str:
    if gain is None:
        return "n/a"
    return "better" if gain > band else "worse" if gain < -band else "flat"


def _env_differs(old: dict, new: dict) -> list[str]:
    from tools.bench_stability import environment_differs

    return environment_differs(old or {}, new or {})


def compare_baselines(old: dict, new: dict, *, band: float = GAIN_BAND_PCT) -> dict:
    """The gain per row between two stored baselines: ``rows[key] = {metric: {old, new, gain_pct, verdict}}`` for the
    rows both measured ``ok``, ``added`` and ``removed`` keys, the session control's movement per size and the rows whose
    conditions differ enough to mislead. Nothing is thresholded into a pass or fail: the flip's acceptance reads it."""
    old_rows, new_rows = old.get("rows", {}), new.get("rows", {})
    usable = lambda record: record.get("status") == "ok" and record.get("figures")      # noqa: E731
    both = [key for key in new_rows if key in old_rows and usable(new_rows[key]) and usable(old_rows[key])]
    rows, differing = {}, {}
    for key in both:
        old_fig, new_fig = old_rows[key]["figures"], new_rows[key]["figures"]
        rows[key] = {}
        for name, _heading, better in METRICS:
            gain = gain_pct(old_fig.get(name), new_fig.get(name), better)
            rows[key][name] = {"old": old_fig.get(name), "new": new_fig.get(name), "gain_pct": gain,
                               "verdict": verdict(gain, band)}
        notes = _env_differs(old_rows[key].get("conditions_during"), new_rows[key].get("conditions_during"))
        if notes:
            differing[key] = notes
    controls = {}
    for size in sorted(set(old.get("controls", {})) & set(new.get("controls", {}))):
        a, b = old["controls"][size].get("control_gpu_quiet_ms"), new["controls"][size].get("control_gpu_quiet_ms")
        controls[size] = {"old_ms": a, "new_ms": b, "ratio": round(b / a, 2) if a and b else None}
    summary = {}
    for name, _heading, better in METRICS:
        gains = [rows[key][name]["gain_pct"] for key in rows if rows[key][name]["gain_pct"] is not None]
        summary[name] = {"rows": len(gains), "median_gain_pct": round(statistics.median(gains), 1) if gains else None,
                         "better": sum(g > band for g in gains), "worse": sum(g < -band for g in gains)}
    return {"old": old.get("name"), "new": new.get("name"), "old_commit": old.get("commit"),
            "new_commit": new.get("commit"), "old_backend": old.get("backend"), "new_backend": new.get("backend"),
            "band_pct": band, "rows": rows, "added": sorted(set(new_rows) - set(old_rows)),
            "removed": sorted(set(old_rows) - set(new_rows)),
            "unmeasured": sorted(key for key in set(old_rows) & set(new_rows) if key not in rows),
            "controls": controls, "conditions_differ": differing, "summary": summary}


def format_compare(report: dict) -> list[str]:
    lines = [f"Compare {report['old']} ({report['old_commit']}, {report['old_backend']}) -> {report['new']} "
             f"({report['new_commit']}, {report['new_backend']}); gain is positive when better, flat within "
             f"{report['band_pct']:g} %"]
    for size, control in report["controls"].items():
        lines.append(f"  control {size}: Crossfade control {control['old_ms']} -> {control['new_ms']} ms "
                     f"(x{control['ratio']}): the session itself moved by that much")
    if not report["controls"]:
        lines.append("  WARNING: no session control in both baselines; the figures cannot be read control-relative")
    for key, notes in sorted(report["conditions_differ"].items()):
        lines.append(f"  WARNING {key}: conditions differed ({', '.join(notes)})")
    for key, rec in report["rows"].items():
        parts = [f"{name} {rec[name]['old']}->{rec[name]['new']} ({rec[name]['gain_pct']:+.1f}%)"
                 for name, _h, _b in METRICS if rec[name]["gain_pct"] is not None and rec[name]["verdict"] != "flat"]
        lines.append(f"  {key:52s} " + ("; ".join(parts) if parts else "flat"))
    for label, keys in (("added", report["added"]), ("removed", report["removed"]), ("not measured", report["unmeasured"])):
        for key in keys:
            lines.append(f"  {key:52s} {label}")
    for name, heading, _better in METRICS:
        block = report["summary"][name]
        if block["rows"]:
            lines.append(f"  {heading:18s} median gain {block['median_gain_pct']:+.1f}% over {block['rows']} rows "
                         f"({block['better']} better, {block['worse']} worse)")
    return lines


# -- markdown -----------------------------------------------------------------------------------------------------------

def _cell(value, digits=1) -> str:
    return "n/a" if value is None else f"{value:.{digits}f}"


def _pair(a, b, digits=1) -> str:
    return f"{_cell(a, digits)} / {_cell(b, digits)}"


def baseline_markdown(data: dict) -> str:
    """The summary table for ``Docs/Reference/Benchmarks.md``: one row per measured row, conditions above it."""
    lines = [f"### Pre-flip reference pack: {data['name']} ({data.get('commit')}, {data.get('backend') or 'backend not stated'})",
             "", f"Recorded {data.get('created')} to {data.get('updated')}; load {data.get('load') or 'none (idle)'}; "
             f"clip `{data.get('clip')}`; wallpaper `{data.get('wallpaper')}`. Invisible saver, recorded music, "
             f"`--noupdates`. Compare within a session and control-relative (the control row below).", ""]
    for size, control in sorted(data.get("controls", {}).items()):
        lines.append(f"- Control {size} ({control.get('renderer')}): offscreen Crossfade control "
                     f"{_cell(control.get('control_gpu_quiet_ms'), 4)} ms quiet GPU, admitted "
                     f"{control.get('admitted')}/{control.get('controls')}.")
    sample = next((r["conditions_before"] for r in data["rows"].values() if r.get("conditions_before")), None)
    if sample:
        smi = sample.get("nvidia_smi") or {}
        lines.append(f"- First row's conditions: displays {'on' if sample['displays']['displays_on'] else 'OFF ' + str(sample['displays']['missing'])}; "
                     f"GPU clock {smi.get('clocks_gr_mhz')} MHz, {smi.get('pstate')}, {smi.get('temp_c')} C; busiest other "
                     f"processes by CPU {sample.get('other_processes_cpu')}.")
    lines += ["", "| Row | fps | render med / p90 ms | swap gap med / p90 ms | late % | hitches/min | CPU % core | "
                  "GPU ms/frame | RSS / private MB | first 2 s frames |",
              "|---|---|---|---|---|---|---|---|---|---|"]
    for key in sorted(data["rows"]):
        record = data["rows"][key]
        fig = record.get("figures")
        if record.get("status") != "ok" or not fig:
            lines.append(f"| `{key}` | FAILED (exit {record.get('exit_code')}) | | | | | | | | |")
            continue
        lines.append(f"| `{key}` | {_cell(fig['fps'])} | {_pair(fig['render_median_ms'], fig['render_p90_ms'])} | "
                     f"{_pair(fig['swap_gap_median_ms'], fig['swap_gap_p90_ms'])} | {_cell(fig['late_pct'])} | "
                     f"{_cell(fig['hitches_per_min'], 2)} | {_cell(fig['cpu_core_pct'])} | {_cell(fig['gpu_ms_per_frame'], 3)} | "
                     f"{_pair(fig['rss_mb'], fig['private_mb'], 0)} | {_cell(fig['first2s_frames'], 0)} |")
    hitches = [(key, record["figures"]) for key, record in sorted(data["rows"].items())
               if record.get("status") == "ok" and (record.get("figures") or {}).get("hitch_verdict")]
    if hitches:
        lines += ["", "Transition runs' hitch figures (the render thread's frame gaps inside the run; handover and reveal "
                      "outside it; the first frame from the run's start):", "",
                  "| Row | gap med / p90 / max ms | first frame ms | gaps over limit | verdict |", "|---|---|---|---|---|"]
        for key, fig in hitches:
            gaps = fig.get("gap_ms") or {}
            lines.append(f"| `{key}` | {_cell(gaps.get('median'))} / {_cell(gaps.get('p90'))} / {_cell(gaps.get('max'))} | "
                         f"{_cell(fig.get('first_frame_ms'))} | {fig.get('gaps_over_limit')} (> {fig.get('gap_limit_ms')} ms) "
                         f"| {fig['hitch_verdict']} |")
    return "\n".join(lines) + "\n"


def compare_markdown(report: dict) -> str:
    lines = [f"### Pre-flip gain: {report['old']} -> {report['new']}", "",
             f"{report['old_commit']} ({report['old_backend']}) -> {report['new_commit']} ({report['new_backend']}). Gain is "
             f"positive when better; flat within {report['band_pct']:g} %.", ""]
    for size, control in report["controls"].items():
        lines.append(f"- Control {size}: {control['old_ms']} -> {control['new_ms']} ms (x{control['ratio']}).")
    heads = [heading for _n, heading, _b in METRICS]
    lines += ["", "| Row | " + " | ".join(heads) + " |", "|---|" + "---|" * len(heads)]
    for key, rec in report["rows"].items():
        cells = [("n/a" if rec[name]["gain_pct"] is None else f"{rec[name]['gain_pct']:+.1f}%") for name, _h, _b in METRICS]
        lines.append(f"| `{key}` | " + " | ".join(cells) + " |")
    for label, keys in (("added", report["added"]), ("removed", report["removed"]), ("not measured", report["unmeasured"])):
        if keys:
            lines.append("")
            lines.append(f"{label}: " + ", ".join(f"`{key}`" for key in keys))
    return "\n".join(lines) + "\n"


# -- command line -------------------------------------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0], epilog=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--name", help="the baseline's name (tools/baselines/preflip/<name>.json); a rerun with the "
                                       "same name resumes it. Default <date>_<commit>")
    parser.add_argument("--size", default=",".join(SIZES), help="sizes to run, comma separated (default all): "
                                                               + ", ".join(SIZES))
    parser.add_argument("--rows", metavar="PATTERN[,PATTERN]",
                        help="only rows whose key (kind/id/size/state) matches a glob, e.g. 'visualizer/*' or "
                             "'transition/crossfade/*'. With --rows (or --compare) every registered transition is "
                             "selectable, e.g. 'transition/beam/*'; rows are added to an existing --name baseline "
                             "without touching its other rows, and each says its own commit and backend")
    parser.add_argument("--load", choices=LOADS, help="the loaded state: game60 (explicit only: lead only, after the "
                                                       "operator's yes, 10 minutes at most per run window)")
    parser.add_argument("--backend", help="a label stored with the baseline (e.g. python-vulkan, native-opengl)")
    parser.add_argument("--app-arg", action="append", default=[], metavar="=TOKEN",
                        help="passed to the live check's --app-arg (an experiment_flags token, e.g. --app-arg=--graphics-backend=vulkan for a native Vulkan row); repeatable")
    parser.add_argument("--setting", action="append", default=[], metavar="KEY=JSON",
                        help="a persisted setting every row and session also writes after its own (e.g. "
                             "transitions.crumble.motion_blur=\"On\"); repeatable")
    parser.add_argument("--per-row", action="store_true",
                        help="one saver process per transition row instead of one session per size and state "
                             "(single-row reruns; a lone pending transition row is always per-row)")
    parser.add_argument("--redo", action="store_true", help="measure rows again even when the baseline holds them ok")
    parser.add_argument("--viz-seconds", type=float, default=VIZ_SECONDS)
    parser.add_argument("--transition-seconds", type=float, default=TRANSITION_SECONDS,
                        help="run time of a per-row transition process (a session sizes itself)")
    parser.add_argument("--no-control", action="store_true", help="skip the offscreen Crossfade session control")
    parser.add_argument("--keep-logs", action="store_true", help="keep each row's logs and frame trace")
    parser.add_argument("--list", action="store_true", help="print the rows and the time they need; start nothing")
    parser.add_argument("--compare", type=Path, metavar="BASELINE",
                        help="rerun the same matrix (the rows this baseline holds, in this invocation's sizes and "
                             "state) into --name and report the gain per row")
    parser.add_argument("--compare-only", nargs=2, type=Path, metavar=("OLD", "NEW"), help="compare two stored baselines")
    return parser


def parse_sizes(text: str) -> list[str]:
    names = split_patterns(text)
    unknown = [name for name in names if name not in SIZES]
    if unknown or not names:
        raise SystemExit(f"unknown size {unknown or text!r}; sizes: {', '.join(SIZES)}")
    return names


def stamp_new_rows(baseline: dict, keys, *, commit: str, backend: str | None) -> None:
    """Record the commit and backend a row was measured at on the row itself, for the rows measured in this run only:
    a named baseline that several runs add rows to (a transition's pre-port row recorded on its own) keeps the file's
    own commit and backend, and every row says what it was measured on."""
    for key in keys:
        record = baseline.get("rows", {}).get(key)
        if record is not None:
            record["commit"], record["backend"] = commit, backend or baseline.get("backend")


def open_baseline(path: Path, name: str, *, commit: str, load: str | None, backend: str | None) -> dict:
    """The named baseline: loaded when it exists (new rows are added to it, its other rows and its own commit, backend and
    controls untouched), else new. ``--backend`` labels a new file only; rows say their own backend (``stamp_new_rows``)."""
    if path.exists():
        return load_baseline(path)
    return new_baseline(name, commit=commit, load=load, backend=backend)


def plan_rows(args, *, modes=None, transitions=None, old: dict | None = None,
              all_transitions=None) -> tuple[list[Row], list[str]]:
    """The rows this invocation covers: the matrix for its sizes and state, filtered by ``--rows`` and, for a
    ``--compare`` rerun, restricted to rows the old baseline holds. With ``--rows`` or ``--compare`` every transition the
    registry offers is selectable (``all_transitions``, injected by tests); without either, the default matrix."""
    state = "loaded" if args.load else "idle"
    if transitions is None and (args.rows or old is not None):
        transitions = all_registry_transitions() if all_transitions is None else list(all_transitions)
    rows = enumerate_rows(parse_sizes(args.size), state, modes=modes, transitions=transitions,
                          viz_seconds=args.viz_seconds, transition_seconds=args.transition_seconds)
    rows, unmatched = filter_rows(rows, split_patterns(args.rows))
    if old is not None:
        rows = [row for row in rows if row.key in old.get("rows", {})]
    return rows, unmatched


def print_plan(rows: list[Row], *, loaded: bool, per_row: bool = False, log=print) -> None:
    by_size: dict[str, list[Row]] = {}
    for row in rows:
        by_size.setdefault(row.size, []).append(row)
    for size, group in by_size.items():
        seconds = estimate_seconds(group, loaded=loaded, per_row=per_row) + CONTROL_SECONDS
        units = plan_units(group, per_row=per_row)
        log(f"{size} ({SIZES[size].width}x{SIZES[size].height} on Display {SIZES[size].display}): {len(group)} rows in "
            f"{len(units)} saver processes ({sum(r.kind == 'visualizer' for r in group)} Visualizer, "
            f"{sum(r.kind == 'transition' for r in group)} transition), about {seconds / 60:.0f} min including the control")
    for kind, payload in plan_units(rows, per_row=per_row):
        if kind == "session":
            log(f"  session {payload[0].size}/{payload[0].state}: " + ", ".join(r.label for r in payload)
                + f"  every {session_interval([r.label for r in payload])} s, {unit_seconds((kind, payload)):g} s")
        else:
            log(f"  {payload.key}  {payload.seconds:g} s")
    log(f"total about {(estimate_seconds(rows, loaded=loaded, per_row=per_row) + CONTROL_SECONDS * len(by_size)) / 60:.0f} min")


def parse_setting(token: str) -> tuple[str, object]:
    """``KEY=JSON`` as (key, value); refused (ValueError) without a key or with a value that is not JSON."""
    key, separator, value = str(token).partition("=")
    if not key.strip() or not separator:
        raise ValueError(f"--setting takes KEY=JSON, not {token!r}")
    return key.strip(), json.loads(value)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    APP_ARGS[:] = [str(token).lstrip("=") for token in args.app_arg]
    EXTRA_SETTINGS[:] = [parse_setting(token) for token in args.setting]
    if args.compare_only:
        old, new = (load_baseline(p) for p in args.compare_only)
        report = compare_baselines(old, new)
        print("\n".join(format_compare(report)))
        return 0
    old = load_baseline(args.compare) if args.compare else None
    rows, unmatched = plan_rows(args, old=old)
    for pattern in unmatched:
        print(f"WARNING: --rows pattern {pattern!r} matched no row")
    if args.list:
        print_plan(rows, loaded=bool(args.load), per_row=args.per_row)
        return 0
    if not rows:
        print("no rows to run")
        return 1
    for path in (WALLPAPER, CLIP):
        if not path.exists():
            raise SystemExit(f"input not found: {path}")
    commit = commit_id()
    name = args.name or f"{_dt.date.today().isoformat()}_{commit}"
    path = baseline_path(name)
    if old is not None and path.resolve() == args.compare.resolve():
        raise SystemExit("--compare reruns into a new baseline: give --name a different name")
    baseline = open_baseline(path, name, commit=commit, load=args.load, backend=args.backend)
    required = {size: SIZES[size] for size in sorted({row.size for row in rows})}
    todo = pending_rows(rows, baseline, redo=args.redo)
    print(f"{len(rows)} rows, {len(rows) - len(todo)} already stored ok; about "
          f"{estimate_seconds(todo, loaded=bool(args.load), per_row=args.per_row) / 60:.0f} min to run -> {path.relative_to(ROOT)}")
    if not args.no_control:
        for size in required:
            if size not in baseline["controls"]:
                scratch = artifact_paths.scratch_root("preflip_pack") / f"control_{size}.json"
                try:
                    baseline["controls"][size] = measure_control(SIZES[size], scratch)
                except (OSError, subprocess.SubprocessError, ValueError) as exc:
                    print(f"WARNING: no session control for {size}: {exc}")
                else:
                    save_baseline(path, baseline)
    fresh = {row.key for row in todo}

    def save_stamped(target, data):
        stamp_new_rows(data, fresh, commit=commit, backend=args.backend)
        save_baseline(target, data)

    outcome = measure_rows(
        todo, baseline, path, save=save_stamped,
        measure=lambda row, out: run_live_check_row(row, out, timeout_s=row.seconds + 240.0, keep_logs=args.keep_logs),
        conditions_fn=lambda: collect_conditions(required=required, displays_fn=system_displays,
                                                 processes_fn=system_cpu_processes,
                                                 gpu_processes_fn=system_gpu_processes, nvidia_fn=system_nvidia_state),
        displays_fn=system_displays,
        out_dir_fn=lambda row, session=False: artifact_paths.evidence_dir(
            "performance", "preflip_pack",
            artifact_paths.slug(f"{name}_{'session/' + row.size + '/' + row.state if session else row.key}")),
        redo=args.redo, per_row=args.per_row,
        measure_session=lambda group, out: run_live_check_session(
            group, out, timeout_s=unit_seconds(("session", group)) + 240.0, keep_logs=args.keep_logs))
    md_path = path.with_suffix(".md")
    md_path.write_text(baseline_markdown(baseline), encoding="utf-8")
    print(f"ok {len(outcome['ok'])}, failed {len(outcome['failed'])}, skipped {len(outcome['skipped'])}; "
          f"wrote {path.relative_to(ROOT)} and {md_path.relative_to(ROOT)} (summary for Docs/Reference/Benchmarks.md)")
    if old is not None:
        report = compare_baselines(old, baseline)
        print("\n".join(format_compare(report)))
        compare_path = path.with_name(f"{path.stem}_vs_{Path(args.compare).stem}.md")
        compare_path.write_text(compare_markdown(report), encoding="utf-8")
        print(f"wrote {compare_path.relative_to(ROOT)}")
    return 3 if outcome["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
