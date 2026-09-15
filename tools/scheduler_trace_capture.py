"""Bounded external Windows scheduler capture for SRPSS R-87 attribution.

This tool deliberately lives outside the SRPSS runtime.  It does not sample or
query the GUI/render hot path.  For a short D1-heavy attribution run it starts
Windows Performance Recorder's built-in ``GeneralProfile.Light`` in memory
mode, waits for a bounded interval, records WPR health, and locally reduces
the ETL to a small JSON/text attribution report when an SRPSS log directory is
provided.  A successfully reduced raw ETL is deleted by default.

The raw ETL is a **local-only temporary artifact**.  Never put it in a GODZIP
or hand it off through chat.  The small reducer report is the handoff artifact.
The reducer correlates it with the already-existing ``--frame-trace`` evidence
and distinguishes:

* Ready time   -> runnable but not scheduled (OS/CPU contention)
* Wait time    -> sleeping/blocked until another thread/event readies it
* Running time -> work executing on the render thread before the next marker

Typical use, from an elevated terminal while a stable D1-only heavy SRPSS run
is already active with ``--frame-trace``::

    py tools\\scheduler_trace_capture.py capture --duration-s 60 \
        --srpss-log-dir .\\logs

The default is memory mode on purpose: a short attribution trace should not add
continuous ETL disk I/O to the workload being measured.  ``--filemode`` exists
only for an explicitly longer capture where memory mode is unsuitable.
``--keep-etl`` is an explicit local-debug escape hatch; it never changes the
rule that raw ETLs are not handoff artifacts.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import time
from typing import Callable, Iterable, Sequence

TOOL_VERSION = 2
DEFAULT_PROFILE = "GeneralProfile.Light"
DEFAULT_DURATION_S = 60.0
_FRAME_TRACE_NAME = "screensaver_frame_trace.bin"
_MAIN_LOG_NAME = "screensaver.log"


@dataclass(frozen=True, slots=True)
class CommandResult:
    argv: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str


@dataclass(frozen=True, slots=True)
class ClockAnchor:
    label: str
    perf_counter_ns: int
    wall_time_ns: int
    utc_iso: str
    local_iso: str


def _clock_anchor(label: str) -> ClockAnchor:
    now_utc = datetime.now(timezone.utc)
    return ClockAnchor(
        label=str(label),
        perf_counter_ns=time.perf_counter_ns(),
        wall_time_ns=time.time_ns(),
        utc_iso=now_utc.isoformat(),
        local_iso=now_utc.astimezone().isoformat(),
    )


def _run_command(argv: Sequence[str]) -> CommandResult:
    completed = subprocess.run(
        list(argv),
        check=False,
        capture_output=True,
        text=True,
        errors="replace",
    )
    return CommandResult(
        argv=tuple(str(arg) for arg in argv),
        returncode=int(completed.returncode),
        stdout=str(completed.stdout or ""),
        stderr=str(completed.stderr or ""),
    )


def _find_windows_tool(name: str) -> str | None:
    resolved = shutil.which(name)
    if resolved:
        return resolved
    system_root = os.environ.get("SystemRoot")
    if system_root:
        candidate = Path(system_root) / "System32" / name
        if candidate.is_file():
            return str(candidate)
    return None


def build_start_command(
    wpr_path: str,
    *,
    profile: str = DEFAULT_PROFILE,
    filemode: bool = False,
    temp_dir: Path | None = None,
) -> list[str]:
    command = [str(wpr_path), "-start", str(profile)]
    if filemode:
        command.append("-filemode")
        if temp_dir is not None:
            command.extend(("-recordtempto", str(temp_dir)))
    return command


def build_stop_command(wpr_path: str, etl_path: Path, description: str) -> list[str]:
    return [str(wpr_path), "-stop", str(etl_path), str(description)]


def build_marker_command(wpr_path: str, text: str) -> list[str]:
    # Intentionally no -flush: flushing would perturb the workload and the
    # obsolete MarkerFlush behavior is specifically not wanted here.
    return [str(wpr_path), "-marker", str(text)]


def _command_dict(result: CommandResult) -> dict[str, object]:
    return {
        "argv": list(result.argv),
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def parse_wpr_lost_event_counts(text: str) -> list[int]:
    """Return English WPR status lost-event counters when present.

    WPR output may be localized.  An empty result therefore means "not parsed",
    not "zero".  The complete status text is always preserved beside the ETL.
    """

    values: list[int] = []
    for match in re.finditer(
        r"(?:Dropped\s+event|Events\s+Lost)\s*:\s*([0-9][0-9,]*)",
        str(text),
        flags=re.IGNORECASE,
    ):
        values.append(int(match.group(1).replace(",", "")))
    return values


def inspect_frame_trace_log_dir(log_dir: Path | None) -> dict[str, object] | None:
    if log_dir is None:
        return None
    root = Path(log_dir).expanduser().resolve()
    trace = root / _FRAME_TRACE_NAME
    main_log = root / _MAIN_LOG_NAME
    result: dict[str, object] = {
        "log_dir": str(root),
        "frame_trace_path": str(trace),
        "frame_trace_exists": trace.is_file(),
        "frame_trace_size_bytes": trace.stat().st_size if trace.is_file() else 0,
        "main_log_path": str(main_log),
        "main_log_exists": main_log.is_file(),
        "frame_trace_activation_seen": False,
    }
    if main_log.is_file():
        # Read only the bounded tail.  This check is informational and must not
        # turn the capture tool into a log parser or runtime observer.
        with main_log.open("rb") as handle:
            size = main_log.stat().st_size
            handle.seek(max(0, size - 256 * 1024))
            tail = handle.read().decode("utf-8", errors="replace")
        result["frame_trace_activation_seen"] = (
            "[FRAME_TRACE] explicit binary trace active" in tail
        )
    return result


def _safe_write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    temporary.replace(path)


def _write_text(path: Path, text: str) -> None:
    path.write_text(str(text), encoding="utf-8", errors="replace")


def _unique_capture_dir(base: Path, label: str) -> Path:
    stamp = datetime.now().astimezone().strftime("%Y%m%d_%H%M%S")
    clean = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(label).strip()).strip("_.")
    clean = clean or "d1_heavy"
    candidate = Path(base) / f"{stamp}_{clean}"
    suffix = 2
    while candidate.exists():
        candidate = Path(base) / f"{stamp}_{clean}_{suffix}"
        suffix += 1
    return candidate


def _capture(
    args: argparse.Namespace,
    *,
    runner: Callable[[Sequence[str]], CommandResult] = _run_command,
    sleeper: Callable[[float], None] = time.sleep,
    wpr_path: str | None = None,
    xperf_path: str | None = None,
    reducer: Callable[..., dict[str, object]] | None = None,
) -> int:
    if os.name != "nt" and not bool(args.allow_non_windows_test):
        raise SystemExit("scheduler_trace_capture is Windows-only")

    wpr = wpr_path or _find_windows_tool("wpr.exe")
    if not wpr:
        raise SystemExit(
            "wpr.exe was not found. Install/enable Windows Performance Recorder "
            "or run from a Windows environment that provides it."
        )

    duration_s = float(args.duration_s)
    if duration_s <= 0.0:
        raise SystemExit("--duration-s must be greater than zero")

    preflight = inspect_frame_trace_log_dir(
        Path(args.srpss_log_dir) if args.srpss_log_dir else None
    )
    if preflight is not None:
        if not bool(preflight["frame_trace_exists"]):
            raise SystemExit(
                f"--srpss-log-dir has no {_FRAME_TRACE_NAME}; start SRPSS with "
                "--frame-trace before taking the scheduler capture"
            )
        if int(preflight["frame_trace_size_bytes"]) <= 16:
            raise SystemExit("the SRPSS frame trace exists but contains no records yet")

    out_root = Path(args.out_dir).expanduser().resolve()
    capture_dir = _unique_capture_dir(out_root, args.label)
    capture_dir.mkdir(parents=True, exist_ok=False)
    etl_path = capture_dir / "srpss_scheduler.etl"
    manifest_path = capture_dir / "scheduler_capture_manifest.json"
    wpr_temp = capture_dir / "wpr_temp"
    if args.filemode:
        wpr_temp.mkdir(parents=True, exist_ok=True)

    manifest: dict[str, object] = {
        "tool": "scheduler_trace_capture",
        "tool_version": TOOL_VERSION,
        "status": "starting",
        "scenario": "D1 pure-heavy scheduler attribution",
        "label": str(args.label),
        "profile": str(args.profile),
        "storage_mode": "file" if args.filemode else "memory",
        "duration_s_requested": duration_s,
        "wpr_path": str(wpr),
        "etl_path": str(etl_path),
        "platform": platform.platform(),
        "python": sys.version,
        "frame_trace_preflight": preflight,
        "anchors": [],
        "commands": [],
        "notes": [
            "No SRPSS production/runtime sampling was added by this capture tool.",
            "GeneralProfile.Light is captured externally; default memory mode avoids continuous ETL disk I/O.",
            "Raw ETL is local-only and must never be included in a GODZIP/chat handoff.",
            "When SRPSS logs are supplied, successful local reduction produces the handoff-sized JSON/text report and deletes the ETL by default.",
        ],
    }

    def add_anchor(label: str) -> None:
        anchors = manifest.setdefault("anchors", [])
        assert isinstance(anchors, list)
        anchors.append(asdict(_clock_anchor(label)))
        _safe_write_json(manifest_path, manifest)

    def add_command(name: str, result: CommandResult) -> None:
        commands = manifest.setdefault("commands", [])
        assert isinstance(commands, list)
        entry = _command_dict(result)
        entry["name"] = name
        commands.append(entry)
        _safe_write_json(manifest_path, manifest)

    _safe_write_json(manifest_path, manifest)
    start_command = build_start_command(
        wpr,
        profile=str(args.profile),
        filemode=bool(args.filemode),
        temp_dir=wpr_temp if args.filemode else None,
    )

    recording_started = False
    try:
        add_anchor("before_wpr_start")
        start = runner(start_command)
        add_command("start", start)
        if start.returncode != 0:
            manifest["status"] = "start_failed"
            _safe_write_json(manifest_path, manifest)
            raise SystemExit(
                "WPR failed to start. Run this from an elevated terminal and "
                "make sure another WPR recording is not already active.\n"
                + (start.stderr or start.stdout).strip()
            )
        recording_started = True
        add_anchor("after_wpr_start")

        marker_start = runner(build_marker_command(wpr, "SRPSS_D1_HEAVY_BEGIN"))
        add_command("marker_begin", marker_start)

        manifest["status"] = "recording"
        _safe_write_json(manifest_path, manifest)
        print(f"SRPSS scheduler capture active for {duration_s:.1f}s")
        print(f"Output: {capture_dir}")
        sleeper(duration_s)

        add_anchor("before_wpr_status")
        status = runner([str(wpr), "-status", "collectors", "-details"])
        add_command("status_collectors", status)
        _write_text(
            capture_dir / "wpr_status_collectors.txt",
            (status.stdout or "") + ("\n" + status.stderr if status.stderr else ""),
        )
        lost_counts = parse_wpr_lost_event_counts(status.stdout + "\n" + status.stderr)
        manifest["wpr_lost_event_counts"] = lost_counts
        manifest["wpr_lost_event_any"] = (
            any(value > 0 for value in lost_counts) if lost_counts else None
        )
        manifest["wpr_lost_event_parse_status"] = (
            "parsed" if lost_counts else "not_parsed_from_localized_or_empty_status"
        )

        marker_end = runner(build_marker_command(wpr, "SRPSS_D1_HEAVY_END"))
        add_command("marker_end", marker_end)
        add_anchor("before_wpr_stop")

        description = "SRPSS D1 heavy scheduler attribution"
        stop = runner(build_stop_command(wpr, etl_path, description))
        add_command("stop", stop)
        add_anchor("after_wpr_stop")
        if stop.returncode != 0:
            manifest["status"] = "stop_failed"
            _safe_write_json(manifest_path, manifest)
            raise SystemExit(
                "WPR failed while saving the trace.\n"
                + (stop.stderr or stop.stdout).strip()
            )
        recording_started = False

        if not etl_path.is_file() and not bool(args.allow_non_windows_test):
            manifest["status"] = "etl_missing"
            _safe_write_json(manifest_path, manifest)
            raise SystemExit(f"WPR reported success but no ETL exists at {etl_path}")

        if etl_path.is_file():
            manifest["etl_size_bytes"] = etl_path.stat().st_size

        after = inspect_frame_trace_log_dir(
            Path(args.srpss_log_dir) if args.srpss_log_dir else None
        )
        manifest["frame_trace_postflight"] = after
        if preflight is not None and after is not None:
            manifest["frame_trace_growth_bytes"] = max(
                0,
                int(after["frame_trace_size_bytes"])
                - int(preflight["frame_trace_size_bytes"]),
            )

        # Optional post-capture trace-health report.  xperf is not required for
        # capture and runs only after WPR has stopped, so it cannot perturb the
        # measured interval.
        xperf = xperf_path or _find_windows_tool("xperf.exe")
        if xperf and etl_path.is_file():
            stats_path = capture_dir / "xperf_tracestats.txt"
            stats = runner(
                [str(xperf), "-i", str(etl_path), "-o", str(stats_path), "-a", "tracestats", "-timespan", "actual"]
            )
            add_command("xperf_tracestats", stats)
            manifest["xperf_path"] = str(xperf)
            manifest["xperf_tracestats_path"] = str(stats_path)
        else:
            manifest["xperf_path"] = None

        lost_any = manifest.get("wpr_lost_event_any")
        manifest["trace_health"] = (
            "degraded_lost_events"
            if lost_any is True
            else "no_loss_reported"
            if lost_any is False
            else "status_not_parsed"
        )
        manifest["status"] = "complete"
        _safe_write_json(manifest_path, manifest)

        # Reduce locally while the heavyweight ETL is still present.  The
        # reducer deliberately reads only existing lifecycle/frame-trace
        # evidence and never touches the production hot path.  If reduction
        # succeeds, discard the raw ETL by default: the tiny reports are the
        # handoff artifacts.  On any reducer failure, retain the ETL locally
        # for manual investigation rather than destroying evidence.
        reduction_status = "not_requested"
        if (
            etl_path.is_file()
            and args.srpss_log_dir
            and (not bool(args.allow_non_windows_test) or reducer is not None)
        ):
            try:
                reduce_fn = reducer
                if reduce_fn is None:
                    try:
                        from tools.scheduler_trace_reduce import reduce_capture as reduce_fn
                    except ImportError:  # direct ``python tools\...`` execution
                        from scheduler_trace_reduce import reduce_capture as reduce_fn
                reduce_fn(
                    capture_dir,
                    srpss_log_dir=Path(args.srpss_log_dir),
                )
                reduction_status = "complete"
                manifest["scheduler_attribution_json"] = str(
                    capture_dir / "scheduler_attribution.json"
                )
                manifest["scheduler_attribution_text"] = str(
                    capture_dir / "scheduler_attribution.txt"
                )
                if not bool(getattr(args, "keep_etl", False)):
                    etl_path.unlink()
                    manifest["etl_retained"] = False
                else:
                    manifest["etl_retained"] = True
            except Exception as exc:
                reduction_status = "failed"
                manifest["reduction_error"] = repr(exc)
                manifest["etl_retained"] = etl_path.is_file()
        else:
            manifest["etl_retained"] = etl_path.is_file()
        manifest["reduction_status"] = reduction_status
        _safe_write_json(manifest_path, manifest)

        print("Capture complete.")
        print(f"Manifest: {manifest_path}")
        if reduction_status == "complete":
            print(f"Attribution JSON: {capture_dir / 'scheduler_attribution.json'}")
            print(f"Attribution text: {capture_dir / 'scheduler_attribution.txt'}")
            if manifest.get("etl_retained"):
                print(f"Raw ETL retained LOCAL-ONLY: {etl_path}")
            else:
                print("Raw ETL deleted after successful local reduction.")
        elif etl_path.is_file():
            print(f"Raw ETL retained LOCAL-ONLY (DO NOT ATTACH): {etl_path}")
            if reduction_status == "failed":
                print("Local reduction failed; keep the ETL on this machine for manual analysis.")
        return 0
    except KeyboardInterrupt:
        manifest["status"] = "interrupted"
        _safe_write_json(manifest_path, manifest)
        raise SystemExit("capture interrupted; active WPR recording cancelled")
    finally:
        if recording_started:
            cancel = runner([str(wpr), "-cancel"])
            try:
                add_command("cancel_after_failure", cancel)
            except Exception:
                pass


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="External WPR scheduler attribution capture for SRPSS R-87"
    )
    sub = parser.add_subparsers(dest="command", required=True)
    capture = sub.add_parser(
        "capture",
        help="record one bounded scheduler trace while SRPSS is already in a stable heavy state",
    )
    capture.add_argument("--duration-s", type=float, default=DEFAULT_DURATION_S)
    capture.add_argument("--profile", default=DEFAULT_PROFILE)
    capture.add_argument(
        "--out-dir",
        default=str(Path("logs") / "scheduler_captures"),
        help="parent directory for the timestamped capture directory",
    )
    capture.add_argument("--label", default="D1_heavy")
    capture.add_argument(
        "--srpss-log-dir",
        default="",
        help="optional active SRPSS log directory; verifies --frame-trace and records trace growth",
    )
    capture.add_argument(
        "--filemode",
        action="store_true",
        help="use WPR file mode; memory mode is preferred for the short attribution run",
    )
    capture.add_argument(
        "--keep-etl",
        action="store_true",
        help="retain the raw ETL locally after successful reduction; never attach or package it",
    )
    # Test-only seam; hidden from normal help and never needed on Windows.
    capture.add_argument(
        "--allow-non-windows-test",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    if args.command == "capture":
        return _capture(args)
    parser.error(f"unsupported command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
