# SRPSS CLI Flags and Visualizer Logging Refactor Plan

Goal: replace hard-to-remember environment-variable workflows with explicit CLI flags, while keeping env vars and `.cfg` files as backward-compatible fallbacks.

Secondary goal: make Spotify visualizer logs less chunky, less spammy, and easier to scan in an IDE without cutting useful diagnostic data.

This is a clean refactor task. Do not combine it with visualizer bleed fixes.

---

## 1. Current situation

`main.py` already supports some command-line flags:

```text
--debug
-d
--verbose
-v
--viz
--viz-diagnostics
--viz-diag
--fresh
-devblob
--devcurve
```

`main.py` also still uses env vars directly for some runtime behaviour:

```text
SRPSS_PERF_METRICS
SRPSS_PROFILE_CPU
```

`core/logging/logger.py` also reads several env vars directly:

```text
SRPSS_PERF_METRICS
SRPSS_WIDGET_PERF_VERBOSE
SRPSS_VIZ_LOGGING
SRPSS_VIZ_DIAGNOSTICS
SRPSS_FORCE_LOG_DIR
SRPSS_DISABLE_LOGS
SRPSS_FORCE_LOGS
```

The desired final workflow is:

```powershell
python main.py --fresh --viz /s
python main.py --fresh --viz-diag /s
python main.py --fresh --viz-next-transition /s
python main.py --fresh --perf /s
python main.py --fresh --profile-cpu /s
python main.py --fresh --log-dir F:\SRPSSLogs --viz /s
```

instead of needing to remember environment variables.

---

## 2. Do not break Windows screensaver arguments

These must keep working:

```text
/s
/c
/c:HWND
/p HWND
```

Important:

Use `argparse.parse_known_args()` or equivalent so `/s`, `/c`, and `/p HWND` survive and are passed to the existing screensaver-mode parser.

Do not use normal `parse_args()` in a way that rejects Windows screensaver args.

---

## 3. Add a central runtime flags module

Create:

```text
core/runtime_flags.py
```

Suggested implementation:

```python
from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

LogFormat = Literal["aligned", "compact"]


@dataclass(frozen=True)
class RuntimeFlags:
    debug: bool = False
    verbose: bool = False
    fresh: bool = False

    viz: bool = False
    viz_summary: bool = False
    viz_transition: bool = False
    viz_diag: bool = False
    viz_trace: bool = False
    viz_next_transition: bool = False

    perf_metrics: bool | None = None
    profile_cpu: bool = False
    widget_perf_verbose: bool | None = None

    logs_enabled: bool | None = None
    force_logs: bool = False
    disable_logs: bool = False
    log_dir: Path | None = None
    log_format: LogFormat = "aligned"

    devblob: bool = False
    devcurve: bool = False


def parse_runtime_flags(argv: list[str]) -> tuple[RuntimeFlags, list[str]]:
    parser = argparse.ArgumentParser(add_help=False)

    parser.add_argument("--debug", "-d", action="store_true")
    parser.add_argument("--verbose", "-v", action="store_true")
    parser.add_argument("--fresh", action="store_true")

    parser.add_argument("--viz", action="store_true")
    parser.add_argument("--viz-summary", action="store_true")
    parser.add_argument("--viz-transition", action="store_true")
    parser.add_argument(
        "--viz-diagnostics",
        "--viz-diagnostic",
        "--viz-diag",
        dest="viz_diag",
        action="store_true",
    )
    parser.add_argument("--viz-trace", action="store_true")
    parser.add_argument("--viz-next-transition", action="store_true")

    perf_group = parser.add_mutually_exclusive_group()
    perf_group.add_argument("--perf", "--perf-metrics", dest="perf_metrics", action="store_true")
    perf_group.add_argument("--no-perf", "--no-perf-metrics", dest="perf_metrics", action="store_false")
    parser.set_defaults(perf_metrics=None)

    parser.add_argument("--profile-cpu", action="store_true")

    widget_perf_group = parser.add_mutually_exclusive_group()
    widget_perf_group.add_argument("--widget-perf", dest="widget_perf_verbose", action="store_true")
    widget_perf_group.add_argument("--no-widget-perf", dest="widget_perf_verbose", action="store_false")
    parser.set_defaults(widget_perf_verbose=None)

    logs_group = parser.add_mutually_exclusive_group()
    logs_group.add_argument("--logs", dest="logs_enabled", action="store_true")
    logs_group.add_argument("--no-logs", dest="logs_enabled", action="store_false")
    parser.set_defaults(logs_enabled=None)

    parser.add_argument("--force-logs", action="store_true")
    parser.add_argument("--disable-logs", action="store_true")
    parser.add_argument("--log-dir", type=Path)
    parser.add_argument("--log-format", choices=("aligned", "compact"), default="aligned")

    parser.add_argument("-devblob", dest="devblob", action="store_true")
    parser.add_argument("--devcurve", dest="devcurve", action="store_true")

    namespace, remaining = parser.parse_known_args(argv)

    flags = RuntimeFlags(
        debug=bool(namespace.debug),
        verbose=bool(namespace.verbose),
        fresh=bool(namespace.fresh),

        viz=bool(namespace.viz),
        viz_summary=bool(namespace.viz_summary),
        viz_transition=bool(namespace.viz_transition),
        viz_diag=bool(namespace.viz_diag),
        viz_trace=bool(namespace.viz_trace),
        viz_next_transition=bool(namespace.viz_next_transition),

        perf_metrics=namespace.perf_metrics,
        profile_cpu=bool(namespace.profile_cpu),
        widget_perf_verbose=namespace.widget_perf_verbose,

        logs_enabled=namespace.logs_enabled,
        force_logs=bool(namespace.force_logs),
        disable_logs=bool(namespace.disable_logs),
        log_dir=namespace.log_dir,
        log_format=namespace.log_format,

        devblob=bool(namespace.devblob),
        devcurve=bool(namespace.devcurve),
    )

    return flags, remaining
```

---

## 4. Update `main.py`

Replace direct `sys.argv` checks with the central parser.

Current shape:

```python
fresh_mode = '--fresh' in sys.argv
debug_mode = '--debug' in sys.argv or '-d' in sys.argv
verbose_mode = '--verbose' in sys.argv or '-v' in sys.argv
viz_mode = '--viz' in sys.argv
viz_diag_mode = '--viz-diagnostics' in sys.argv or '--viz-diag' in sys.argv
setup_logging(debug=debug_mode, verbose=verbose_mode, viz=viz_mode, viz_diag=viz_diag_mode)
```

Target shape:

```python
from core.runtime_flags import parse_runtime_flags

def main():
    runtime_flags, screensaver_argv = parse_runtime_flags(sys.argv[1:])

    fresh_result = None
    if runtime_flags.fresh:
        fresh_result = clear_logs_for_fresh_start()

    setup_logging(
        debug=runtime_flags.debug,
        verbose=runtime_flags.verbose,
        viz=runtime_flags.viz,
        viz_diag=runtime_flags.viz_diag,
        runtime_flags=runtime_flags,
    )

    mode, preview_hwnd = parse_screensaver_args(["SRPSS"] + screensaver_argv)
```

Then change:

```python
def parse_screensaver_args() -> tuple[ScreensaverMode, int | None]:
```

to:

```python
def parse_screensaver_args(argv: list[str] | None = None) -> tuple[ScreensaverMode, int | None]:
    if argv is None:
        argv = sys.argv
```

Use `argv` inside the function instead of direct `sys.argv`.

---

## 5. Preserve backward compatibility

Do not remove env vars in the first pass.

Priority order should be:

```text
CLI flag
then .cfg file
then env var
then default
```

Examples:

```text
--perf beats SRPSS_PERF_METRICS=0
--no-perf beats SRPSS_PERF_METRICS=1
--log-dir F:\SRPSSLogs beats SRPSS_FORCE_LOG_DIR
--no-logs beats SRPSS_FORCE_LOGS
--logs beats SRPSS_DISABLE_LOGS
```

Keep `.perf.cfg`, `.viz.cfg`, `.logdir.cfg`, and `.logging.cfg` working for packaged builds.

---

## 6. Update `setup_logging()`

Current signature:

```python
def setup_logging(
    debug: bool = False,
    verbose: bool = False,
    viz: bool = False,
    viz_diag: bool = False,
) -> None:
```

Target signature:

```python
def setup_logging(
    debug: bool = False,
    verbose: bool = False,
    viz: bool = False,
    viz_diag: bool = False,
    runtime_flags: object | None = None,
) -> None:
```

Inside `setup_logging()`, apply `runtime_flags` as overrides after env/cfg defaults are read.

Pseudo-logic:

```python
if runtime_flags is not None:
    if runtime_flags.perf_metrics is not None:
        _PERF_METRICS_ENABLED = runtime_flags.perf_metrics

    if runtime_flags.widget_perf_verbose is not None:
        _WIDGET_PERF_VERBOSE = runtime_flags.widget_perf_verbose

    if runtime_flags.log_dir is not None:
        _FORCED_LOG_DIR = runtime_flags.log_dir

    if runtime_flags.viz or runtime_flags.viz_summary or runtime_flags.viz_transition or runtime_flags.viz_diag or runtime_flags.viz_trace:
        _VIZ_LOGGING_ENABLED = True

    if runtime_flags.viz_diag or runtime_flags.viz_trace:
        _VIZ_DIAGNOSTICS_ENABLED = True
```

For log enable/disable:

```python
if runtime_flags.logs_enabled is True:
    logging_disabled = False
elif runtime_flags.logs_enabled is False:
    logging_disabled = True

if runtime_flags.force_logs:
    logging_disabled = False

if runtime_flags.disable_logs:
    logging_disabled = True
```

---

## 7. Replace remaining env-only CPU profiling checks

Current pattern:

```python
profile_flag = os.getenv("SRPSS_PROFILE_CPU", "").strip().lower()
if profile_flag in ("1", "true", "on", "yes"):
    ...
```

Target helper:

```python
def _profile_cpu_enabled(runtime_flags) -> bool:
    if runtime_flags.profile_cpu:
        return True
    profile_flag = os.getenv("SRPSS_PROFILE_CPU", "").strip().lower()
    return profile_flag in ("1", "true", "on", "yes")
```

Use this in both RUN and CONFIG branches.

For the final perf parser auto-run, prefer logger state rather than re-reading env:

```python
from core.logging.logger import is_perf_metrics_enabled

if is_perf_metrics_enabled():
    ...
```

If `is_perf_metrics_enabled()` does not exist, add it.

---

## 8. Add visualizer logging levels

Implement these logical levels:

```text
summary
transition
diagnostic
trace
next-transition
```

Suggested behaviour:

```text
--viz
    summary + transition

--viz-summary
    summary only

--viz-transition
    summary + transition

--viz-diag
    summary + transition + diagnostic

--viz-trace
    summary + transition + diagnostic + trace

--viz-next-transition
    enable trace for only the next transition window, then auto-disable
```

Do not make `--viz` mean full trace spam.

---

## 9. Text alignment

Text alignment is possible and already partly present.

Keep the existing aligned formatter style:

```python
"%(asctime)s - %(name)-30s - %(levelname)-8s - %(message)s"
```

Add compact format:

```python
"%(asctime)s %(levelname).1s %(name)s %(message)s"
```

Add helper:

```python
def _build_formatter(log_format: str, *, console: bool = False) -> logging.Formatter:
    if log_format == "compact":
        return logging.Formatter(
            "%(asctime)s %(levelname).1s %(name)s %(message)s",
            datefmt="%H:%M:%S" if console else "%Y-%m-%d %H:%M:%S",
        )

    return logging.Formatter(
        "%(asctime)s - %(name)-30s - %(levelname)-8s - %(message)s",
        datefmt="%H:%M:%S" if console else "%Y-%m-%d %H:%M:%S",
    )
```

Use this for:

```text
main log
console log
perf log
visualizer log
```

Default:

```text
--log-format aligned
```

because aligned logs are easier to scan in an IDE.

---

## 10. Standardize visualizer transition line layout

Use consistent key order.

Recommended order:

```text
tx
phase
from
to
mode
preset
gen
act
overlay_gen
overlay_act
display
target
visual
energy
src_display
src_target
src_visual
src_energy
result
warnings
```

Example:

```text
[SPOTIFY_VIS][TX_RESET] tx=42 phase=reset from=devcurve to=spectrum mode=spectrum preset=custom:5 gen=3 act=3 overlay=-/- display=0.000/0.000 target=0.000/0.000 visual=0.000/0.000 energy=0.000/0.000 src_display=-/- result=ok
```

Do not randomly reorder keys between log lines.

---

## 11. Add startup flag summary

After logging initializes, log one effective flag summary:

```text
[FLAGS] debug=0 verbose=0 fresh=1 perf=0 profile_cpu=0 widget_perf=0 viz=1 viz_summary=1 viz_transition=1 viz_diag=0 viz_trace=0 log_format=aligned log_dir=...
```

This prevents future confusion about which flags were active.

---

## 12. Aggregate spammy visualizer logs

Demote to trace or aggregate:

```text
[PERF] FFT task submitted
[SPOTIFY_VIS][GLOW] ...
[SPOTIFY_VIS][FLOOR] ...
[SPOTIFY_VIS][BARS] Bars=[...]
Positioned visualizer widget geom=...
Rainbow ACTIVE...
Shader bars snapshot...
```

Keep as summary/transition:

```text
Mode cycle requested
Visualization mode changed
MODE_RESET_ASSERT
RENDER_STATE / STATE at transition checkpoints
Engine delivered fresh frame after reset
OVERLAY RESET
TX_SUMMARY
ANOMALY
```

Normal run should show roughly:

```text
[CFG] create / changed refresh
[TX_START]
[TX_CONFIG]
[TX_RESET]
[TX_FIRST_FRAME]
[TX_OVERLAY]
[TX_DONE]
[ANOMALY] only if something is wrong
[PERF_SUMMARY] every 30-60 seconds
```

---

## 13. Add transition summary

At the end of each mode switch, log one summary.

Example:

```text
[SPOTIFY_VIS][TX_SUMMARY] tx=42 from=devcurve to=spectrum result=ok duration_ms=842 reset_zero_ok=True first_frame=3/3 overlay=3/3 stale_frame_rejected=0 max_display_before_reset=0.000 first_display=0.911/0.617 floor_manual=0.450 floor_applied_first=0.494 expansion=5.587 warnings=0
```

This should be the first line inspected during future visualizer debugging.

---

## 14. Add anomaly lines

Emit a clear warning when known-bad states happen.

Examples:

```text
[SPOTIFY_VIS][ANOMALY] stale_display_source tx=42 mode=spectrum display_src=2/2 engine=3/3 display=0.841/0.698
```

```text
[SPOTIFY_VIS][ANOMALY] nonzero_bars_before_reset tx=42 mode=spectrum phase=after_technical_config display=0.973/0.789
```

```text
[SPOTIFY_VIS][ANOMALY] overlay_activation_mismatch tx=42 mode=spectrum overlay=2/2 engine=3/3
```

This is better than forcing a human to infer problems from thousands of lines.

---

## 15. Document preferred usage

Add:

```text
Docs/CLI_FLAGS.md
```

Suggested contents:

```text
Preferred commands:

python main.py --fresh --viz /s
python main.py --fresh --viz-diag /s
python main.py --fresh --viz-trace /s
python main.py --fresh --viz-next-transition /s
python main.py --fresh --perf /s
python main.py --fresh --profile-cpu /s
python main.py --fresh --log-dir F:\SRPSSLogs --viz /s
python main.py --fresh --log-format compact --viz /s
python main.py --fresh --log-format aligned --viz /s

Legacy env vars still supported:

SRPSS_PERF_METRICS
SRPSS_PROFILE_CPU
SRPSS_WIDGET_PERF_VERBOSE
SRPSS_VIZ_LOGGING
SRPSS_VIZ_DIAGNOSTICS
SRPSS_FORCE_LOG_DIR
SRPSS_DISABLE_LOGS
SRPSS_FORCE_LOGS
```

---

## 16. Tests to add

Create:

```text
tests/test_runtime_flags.py
```

Tests:

```python
def test_parse_runtime_flags_keeps_windows_run_arg():
    flags, remaining = parse_runtime_flags(["--viz", "--fresh", "/s"])
    assert flags.viz is True
    assert flags.fresh is True
    assert remaining == ["/s"]
```

```python
def test_parse_runtime_flags_keeps_preview_args():
    flags, remaining = parse_runtime_flags(["--viz-diag", "/p", "12345"])
    assert flags.viz_diag is True
    assert remaining == ["/p", "12345"]
```

```python
def test_perf_flags_are_tristate():
    flags, _ = parse_runtime_flags([])
    assert flags.perf_metrics is None

    flags, _ = parse_runtime_flags(["--perf"])
    assert flags.perf_metrics is True

    flags, _ = parse_runtime_flags(["--no-perf"])
    assert flags.perf_metrics is False
```

```python
def test_log_format_flag():
    flags, _ = parse_runtime_flags(["--log-format", "compact"])
    assert flags.log_format == "compact"
```

```python
def test_log_dir_flag():
    flags, _ = parse_runtime_flags(["--log-dir", "F:\\SRPSSLogs"])
    assert str(flags.log_dir).endswith("SRPSSLogs")
```

Also update or add tests for:

```text
parse_screensaver_args(["SRPSS", "/s"])
parse_screensaver_args(["SRPSS", "/c"])
parse_screensaver_args(["SRPSS", "/c:1234"])
parse_screensaver_args(["SRPSS", "/p", "1234"])
```

---

## 17. Migration rule

Do not delete env var support in the first pass.

First pass:

- add flags
- make flags override env vars
- log effective flags at startup
- add tests
- document usage

Second pass, later:

- update docs to prefer flags
- leave env vars as legacy fallback
- remove env vars only if there is a strong reason

---

## 18. Definition of done

Done when:

- [ ] Existing flags still work.
- [ ] `/s`, `/c`, `/c:HWND`, and `/p HWND` still work.
- [ ] `--perf` replaces `SRPSS_PERF_METRICS=1`.
- [ ] `--profile-cpu` replaces `SRPSS_PROFILE_CPU=1`.
- [ ] `--widget-perf` replaces `SRPSS_WIDGET_PERF_VERBOSE=1`.
- [ ] `--log-dir PATH` replaces `SRPSS_FORCE_LOG_DIR`.
- [ ] `--logs`, `--no-logs`, and `--force-logs` replace log env toggles.
- [ ] Env vars still work as fallback.
- [ ] CLI flags override env vars.
- [ ] Startup logs show effective flags.
- [ ] Aligned log format is available.
- [ ] Compact log format is available.
- [ ] Tests cover runtime flag parsing.
- [ ] Tests cover screensaver arg preservation.
