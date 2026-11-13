"""Diagnostic experiment admission — parsed once at startup, activated deliberately.

These flags admit *opt-in* Visualizer diagnostic tooling retained after the
closed post-switch investigation (``Docs/Reference/
R-80_ABC_EventLoop_Rolling_Window_Contamination.md``). They are **not** product feature gates:
``core/dev_gates.py`` deliberately does not own them, because ``--abc-drive`` and
``--viz-switch-telemetry`` are experiment/debug admissions rather than shippable
capabilities.

Admissions:

* ``--viz-switch-telemetry`` — admit boundary-only render-host switch/resource
  ownership telemetry. Without it, Standard/MC runtime allocates no lifecycle
  telemetry object, takes no new lock, keeps no new bookkeeping, and adds no new
  logging/timer/sampler/GL query.
* ``--abc-drive=A|B|C`` — admit the opt-in in-app A/B/C stress/causal harness.
  Because the harness may need the boundary ownership facts above, ``--abc-drive``
  **implicitly** enables the switch telemetry too.
* ``--profile-cpu`` — wrap the CONFIG or RUN session in ``cProfile`` and write
  ``screensaver_config.pstats`` / ``screensaver_run.pstats`` to the log directory.
* ``--mc-window-flags=splash`` — hardware-ingress harnesses only: give the Media
  Center window the splash top-level role instead of the tool role.
* ``--log-dir=<path>`` — harness log-root redirect: the logger writes its files
  under ``<path>`` (a scratch folder) so the operator's own logs stay untouched.
* The Visualizer's process path (native core P2b). The production Visualizer owner runs
  its Visualizer on the engine worker (``WorkerType.VISUALIZER``: capture, DSP and the
  tick out of process; the owner sends control edges and presents the worker's frames)
  by DEFAULT on every platform (Windows by the operator's decision of 8 Nov, after gates 3
  and 4; Linux since the H3 source flip of 11 Nov, where the path has never run: Linux_Plan.md)
  (:func:`visualizer_engine_worker_platform_default`). In process stays the automatic
  fallback when the worker fails (``engine_worker_link``'s bounded recovery). Two
  diagnostic tokens choose the path for A/B runs, whatever the platform:
  ``--viz-in-process`` (the in-process path; it wins when both are given) and
  ``--viz-engine-worker`` (the worker). Read once per owner construction
  (:func:`visualizer_engine_worker_admitted`).
* ``--only-display <index>`` / ``--only-display=<index>`` — RUN only: the saver's display windows go on exactly one
  display, the 0-based screen index the product's logs report (``screen 0`` is the first screen Qt lists, normally
  the primary). The one consumer is ``DisplayManager._get_allowed_screen_indices`` (it replaces the profile's physical
  selection for the run; nothing is persisted). ``main.py`` refuses a malformed value, or an index no screen has, at
  RUN startup with exit code 2; a display that disappears mid-run leaves the selection empty and never moves the
  saver to another display. Absent, nothing changes (:func:`only_display_index` is ``None``).
* ``--gpu-pass-timing`` — admit the native core's per-pass GPU timer (D8 plus 2, Current_Plan.md item 8b N2.6;
  ``rendering.native.gpu_timing``): GPU time per pass written into the frame trace, so it takes effect only together
  with ``--frame-trace`` (``gpu_pass_timing_wanted``). Without it a host's timer is never switched on and the core
  holds no timer, no query object and no per-frame call for it (:func:`gpu_pass_timing_admitted`). Its consumer is
  the backend owner that attaches native hosts (``rendering.quick.bootstrap``, N2.7: window hosts on Vulkan only).
* ``--graphics-backend=vulkan`` — the Vulkan rehearsal path (D10 point 1, Current_Plan.md item 8b N2.7): the one
  backend owner, ``rendering.quick.bootstrap``, runs the process's Qt Quick windows on Vulkan, on the native core's
  device (D6). Run by the lead only, bounded, on Display 1 (``tools/d1_run.py --app-arg=--graphics-backend=vulkan``).
  ``--graphics-backend=opengl`` names the default. Absent or any other value: OpenGL, the product path, unchanged
  (:func:`graphics_backend_request`). Only the ``=`` form is one token.

All are ordinary argv tokens in the ``=`` form, so a harness that launches a
child passes them as arguments; nothing is read from the environment.

Contract:

* parse the process argv **once** during startup (:func:`parse_experiment_flags`);
* activate the parsed result **deliberately** (:func:`activate_experiment_flags`),
  never at import, never from an environment variable, never from a marker file;
* code that must consult the admission reads :func:`active_experiment_flags` (or a
  named helper), which returns a disabled default until startup activates it;
* tests/tools inject telemetry directly at the owner seam instead of depending on
  process argv; :func:`override_active_flags_for_testing` exists only for the few
  tests that must exercise the process-level admission itself.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

_VALID_CONDITIONS = frozenset({"A", "B", "C"})


@dataclass(frozen=True, slots=True)
class ExperimentFlags:
    """Immutable diagnostic experiment admission derived once from argv."""

    abc_drive: str | None = None
    viz_switch_telemetry: bool = False
    abc_layout_slot: str | None = None
    abc_exclude_seconds: float | None = None
    profile_cpu: bool = False
    mc_window_splash: bool = False
    log_dir: str | None = None
    # The Visualizer's process path: None follows the platform default (the engine worker on every platform), True is
    # ``--viz-engine-worker``, False ``--viz-in-process`` (tests and tools state their path the same way).
    visualizer_engine_worker: bool | None = None
    # ``--only-display``: the one screen index the saver's windows may use (RUN only); None leaves the selection alone.
    only_display: int | None = None
    # ``--gpu-pass-timing``: the native core's per-pass GPU timer, into the frame trace (N2.6).
    gpu_pass_timing: bool = False
    # ``--graphics-backend=<name>``: the Qt Quick graphics backend asked for (one of GRAPHICS_BACKENDS); None is the
    # default (OpenGL). The backend owner (``rendering.quick.bootstrap``) decides what the process actually runs.
    graphics_backend: str | None = None

    @property
    def lifecycle_telemetry_admitted(self) -> bool:
        """True when the boundary render-host telemetry must be allocated.

        ``--abc-drive`` implicitly admits the same telemetry it scores, so either
        flag turns it on; neither leaves it off (Standard/MC runtime).
        """
        return self.viz_switch_telemetry or self.abc_drive is not None


ONLY_DISPLAY_FLAG = "--only-display"
GPU_PASS_TIMING_FLAG = "--gpu-pass-timing"
GRAPHICS_BACKEND_FLAG = "--graphics-backend"
#: The backends ``--graphics-backend`` may name (``rendering.quick.bootstrap.QUICK_BACKENDS`` is the same pair).
GRAPHICS_BACKENDS = ("opengl", "vulkan")


def parse_only_display(argv: Sequence[str]) -> int | None:
    """The ``--only-display`` screen index in ``argv``, strictly: ``None`` when absent.

    Accepts ``--only-display 1`` and ``--only-display=1``. Raises ``ValueError`` for a missing, non-integer or
    negative value, or a second occurrence; whether a screen has that index is checked where the screens are known
    (``main.py``'s RUN startup).
    """
    args = [str(arg) for arg in argv]
    found: int | None = None
    index = 0
    while index < len(args):
        token = args[index].strip()
        raw: str | None = None
        if token == ONLY_DISPLAY_FLAG:
            if index + 1 >= len(args):
                raise ValueError(f"{ONLY_DISPLAY_FLAG} requires a display index (0, 1, ...)")
            raw = args[index + 1].strip()
            index += 1
        elif token.startswith(ONLY_DISPLAY_FLAG + "="):
            raw = token.split("=", 1)[1].strip()
        if raw is not None:
            if found is not None:
                raise ValueError(f"{ONLY_DISPLAY_FLAG} may be supplied only once")
            if not raw.isdigit():
                raise ValueError(f"{ONLY_DISPLAY_FLAG} requires a non-negative integer display index, got {raw!r}")
            found = int(raw)
        index += 1
    return found


def parse_experiment_flags(argv: Sequence[str]) -> ExperimentFlags:
    """Parse the diagnostic experiment flags out of a full argv, once.

    Accepts ``--viz-switch-telemetry``, ``--abc-drive=<A|B|C>`` and the
    space-separated ``--abc-drive <A|B|C>``. An unrecognised/invalid condition
    leaves ``abc_drive`` unset rather than raising, so an ordinary launch is never
    blocked by a malformed diagnostic flag. Pure and side-effect free.
    """
    args = [str(arg) for arg in argv]
    abc_drive: str | None = None
    viz_switch_telemetry = False
    abc_layout_slot: str | None = None
    abc_exclude_seconds: float | None = None
    profile_cpu = False
    mc_window_splash = False
    log_dir: str | None = None
    visualizer_engine_worker: bool | None = None
    in_process_chosen = False
    gpu_pass_timing = False
    graphics_backend: str | None = None
    for index, arg in enumerate(args):
        if arg == "--viz-switch-telemetry":
            viz_switch_telemetry = True
            continue
        if arg.startswith(GRAPHICS_BACKEND_FLAG + "="):
            requested = arg.split("=", 1)[1].strip().lower()
            graphics_backend = requested if requested in GRAPHICS_BACKENDS else None
            continue
        if arg == GPU_PASS_TIMING_FLAG:
            gpu_pass_timing = True
            continue
        if arg == "--viz-engine-worker":
            visualizer_engine_worker = True
            continue
        if arg == "--viz-in-process":
            in_process_chosen = True
            continue
        if arg == "--profile-cpu":
            profile_cpu = True
            continue
        if arg.startswith("--mc-window-flags="):
            mc_window_splash = arg.split("=", 1)[1].strip().lower() == "splash"
            continue
        if arg.startswith("--log-dir="):
            log_dir = arg.split("=", 1)[1].strip() or None
            continue
        value: str | None = None
        if arg.startswith("--abc-drive="):
            value = arg.split("=", 1)[1]
        elif arg == "--abc-drive" and index + 1 < len(args):
            value = args[index + 1]
        if value is not None:
            condition = value.strip().upper()
            if condition in _VALID_CONDITIONS:
                abc_drive = condition
            continue
        slot: str | None = None
        if arg.startswith("--abc-layout-slot="):
            slot = arg.split("=", 1)[1]
        elif arg == "--abc-layout-slot" and index + 1 < len(args):
            slot = args[index + 1]
        if slot is not None:
            slot = slot.strip()
            if slot:
                abc_layout_slot = slot
            continue
        exclude: str | None = None
        if arg.startswith("--abc-exclude-seconds="):
            exclude = arg.split("=", 1)[1]
        elif arg == "--abc-exclude-seconds" and index + 1 < len(args):
            exclude = args[index + 1]
        if exclude is not None:
            try:
                abc_exclude_seconds = max(0.0, float(exclude.strip()))
            except ValueError:
                pass
    if in_process_chosen:
        visualizer_engine_worker = False          # the in-process choice wins (the known-good fallback path)
    try:
        only_display = parse_only_display(args)
    except ValueError:
        only_display = None                       # RUN startup refuses it strictly (main.py); never a fallback here
    return ExperimentFlags(
        abc_drive=abc_drive,
        viz_switch_telemetry=viz_switch_telemetry,
        abc_layout_slot=abc_layout_slot,
        abc_exclude_seconds=abc_exclude_seconds,
        profile_cpu=profile_cpu,
        mc_window_splash=mc_window_splash,
        log_dir=log_dir,
        visualizer_engine_worker=visualizer_engine_worker,
        only_display=only_display,
        gpu_pass_timing=gpu_pass_timing,
        graphics_backend=graphics_backend,
    )


def experiment_flag_tokens(argv: Sequence[str]) -> tuple[str, ...]:
    """Return the argv tokens that belong to diagnostic experiment flags.

    Startup uses this to strip experiment admissions (and the value consumed by
    the space-separated ``--abc-drive B`` form) from the argv handed to
    screensaver mode detection, so a diagnostic flag never leaks into RUN/CONFIG
    parsing.
    """
    args = [str(arg) for arg in argv]
    tokens: list[str] = []
    for index, arg in enumerate(args):
        if (
            arg == "--viz-switch-telemetry"
            or arg == GPU_PASS_TIMING_FLAG
            or arg == "--viz-engine-worker"
            or arg == "--viz-in-process"
            or arg == "--profile-cpu"
            or arg.startswith("--mc-window-flags=")
            or arg.startswith("--log-dir=")
            or arg.startswith("--abc-drive=")
            or arg.startswith("--abc-layout-slot=")
            or arg.startswith("--abc-exclude-seconds=")
            or arg.startswith(ONLY_DISPLAY_FLAG + "=")
            or arg.startswith(GRAPHICS_BACKEND_FLAG + "=")
        ):
            tokens.append(arg)
        elif arg in ("--abc-drive", "--abc-layout-slot", "--abc-exclude-seconds", ONLY_DISPLAY_FLAG):
            tokens.append(arg)
            if index + 1 < len(args):
                tokens.append(args[index + 1])
    return tuple(tokens)


# Process-level activation ---------------------------------------------------
# Set ONCE during startup by the app entrypoint. Not read from argv at import,
# not an environment variable, not a marker file.
_ACTIVE: ExperimentFlags | None = None


def activate_experiment_flags(flags: ExperimentFlags) -> ExperimentFlags:
    """Deliberately activate the parsed flags for the process. Returns them."""
    global _ACTIVE
    _ACTIVE = flags
    return flags


def active_experiment_flags() -> ExperimentFlags:
    """Return the activated flags, or a disabled default before activation."""
    return _ACTIVE if _ACTIVE is not None else ExperimentFlags()


def abc_drive_condition() -> str | None:
    """Return the opt-in visualizer-switch A/B/C experiment condition, if any."""
    return active_experiment_flags().abc_drive


def abc_layout_slot() -> str | None:
    """Return the saved-layout slot the A/B/C baseline recreation should load."""
    return active_experiment_flags().abc_layout_slot


def abc_exclude_seconds() -> float | None:
    """Return an override for the pre-score exclusion window, if set.

    Diagnostic-only: used to age an A control (long Bubble hold before scoring) so
    the process-age/cache confound can be ruled out without switching modes.
    """
    return active_experiment_flags().abc_exclude_seconds


def profile_cpu_admitted() -> bool:
    """True when ``--profile-cpu`` asked for a cProfile of the CONFIG/RUN session."""
    return active_experiment_flags().profile_cpu


def mc_window_splash_admitted() -> bool:
    """True when ``--mc-window-flags=splash`` selected the splash Media Center role."""
    return active_experiment_flags().mc_window_splash


def visualizer_switch_telemetry_admitted() -> bool:
    """True when opt-in render-host switch/resource telemetry must be allocated."""
    return active_experiment_flags().lifecycle_telemetry_admitted


def visualizer_engine_worker_platform_default() -> bool:
    """Whether the Visualizer runs on the engine worker when no path was chosen: on every platform the product
    supports. Windows is the measured, accepted platform (gates 2 to 4, the frozen checks). Linux has the same
    default since the H3 source flip (11 Nov 2026, the operator's 8 Nov decision: no Linux machine, no proving step),
    and **nothing of the worker path has ever run there**: the session's named wake pipe, the worker's spawn under
    forkserver, the shared mapping's tracker and Pulse capture in the worker are source-level only
    (``Linux_Plan.md``, Phase 4). A worker that cannot configure or start leaves the activation in process
    (``engine_worker_link``'s bounded fallback, logged with its reason), and ``--viz-in-process`` chooses that path
    outright. This stays a function so a platform can be taken off the worker in one place."""
    return True


def visualizer_engine_worker_admitted() -> bool:
    """True when the production owner runs its Visualizer on the engine worker: the chosen path
    (``--viz-engine-worker`` / ``--viz-in-process``), else the platform default."""
    chosen = active_experiment_flags().visualizer_engine_worker
    return visualizer_engine_worker_platform_default() if chosen is None else bool(chosen)


def only_display_index() -> int | None:
    """The screen index ``--only-display`` restricts the saver's windows to, or ``None`` (the profile's selection)."""
    return active_experiment_flags().only_display


def gpu_pass_timing_admitted() -> bool:
    """True when ``--gpu-pass-timing`` admitted the native core's per-pass GPU timer (it writes only into a frame trace:
    ``rendering.native.gpu_timing.gpu_pass_timing_wanted``)."""
    return active_experiment_flags().gpu_pass_timing


def graphics_backend_request() -> str | None:
    """The Qt Quick backend ``--graphics-backend`` asked for (``"opengl"`` or ``"vulkan"``), or None (the default).
    Read once, by the backend owner (``rendering.quick.bootstrap.configure_quick_graphics``)."""
    return active_experiment_flags().graphics_backend


def override_active_flags_for_testing(flags: ExperimentFlags | None) -> None:
    """Set/clear the process admission directly (tests of the admission only)."""
    global _ACTIVE
    _ACTIVE = flags


__all__ = [
    "ExperimentFlags",
    "parse_experiment_flags",
    "experiment_flag_tokens",
    "activate_experiment_flags",
    "active_experiment_flags",
    "abc_drive_condition",
    "abc_layout_slot",
    "abc_exclude_seconds",
    "profile_cpu_admitted",
    "mc_window_splash_admitted",
    "visualizer_switch_telemetry_admitted",
    "visualizer_engine_worker_platform_default",
    "visualizer_engine_worker_admitted",
    "ONLY_DISPLAY_FLAG",
    "parse_only_display",
    "only_display_index",
    "GPU_PASS_TIMING_FLAG",
    "gpu_pass_timing_admitted",
    "GRAPHICS_BACKEND_FLAG",
    "GRAPHICS_BACKENDS",
    "graphics_backend_request",
    "override_active_flags_for_testing",
]
