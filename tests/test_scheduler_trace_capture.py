from __future__ import annotations

import argparse
from pathlib import Path

from tools.scheduler_trace_capture import (
    CommandResult,
    build_marker_command,
    build_start_command,
    build_stop_command,
    inspect_frame_trace_log_dir,
    parse_wpr_lost_event_counts,
)


def test_default_start_is_light_memory_mode_without_recordtempto(tmp_path: Path) -> None:
    command = build_start_command(
        r"C:\\Windows\\System32\\wpr.exe",
        temp_dir=tmp_path,
    )
    assert command == [
        r"C:\\Windows\\System32\\wpr.exe",
        "-start",
        "GeneralProfile.Light",
    ]
    assert "-filemode" not in command
    assert "-recordtempto" not in command


def test_filemode_is_explicit_and_can_pin_temp_location(tmp_path: Path) -> None:
    command = build_start_command(
        "wpr.exe",
        profile="GeneralProfile.Light",
        filemode=True,
        temp_dir=tmp_path,
    )
    assert command == [
        "wpr.exe",
        "-start",
        "GeneralProfile.Light",
        "-filemode",
        "-recordtempto",
        str(tmp_path),
    ]


def test_stop_and_marker_do_not_request_flush(tmp_path: Path) -> None:
    etl = tmp_path / "trace.etl"
    assert build_stop_command("wpr.exe", etl, "desc") == [
        "wpr.exe",
        "-stop",
        str(etl),
        "desc",
    ]
    marker = build_marker_command("wpr.exe", "SRPSS_D1_HEAVY_BEGIN")
    assert marker == ["wpr.exe", "-marker", "SRPSS_D1_HEAVY_BEGIN"]
    assert "-flush" not in marker


def test_wpr_lost_event_parser_is_conservative() -> None:
    text = """
Dropped event           : 0
Collector Name          : NT Kernel Logger
Events Lost             : 0
Collector Name          : WPR Event Collector
Events Lost             : 1,234
"""
    assert parse_wpr_lost_event_counts(text) == [0, 0, 1234]
    assert parse_wpr_lost_event_counts("localized output with no English labels") == []


def test_frame_trace_log_dir_preflight_is_bounded_and_informational(tmp_path: Path) -> None:
    trace = tmp_path / "screensaver_frame_trace.bin"
    trace.write_bytes(b"SRPSSFT1" + b"x" * 128)
    (tmp_path / "screensaver.log").write_text(
        "old\n[FRAME_TRACE] explicit binary trace active path=x\\screensaver_frame_trace.bin\n",
        encoding="utf-8",
    )
    result = inspect_frame_trace_log_dir(tmp_path)
    assert result is not None
    assert result["frame_trace_exists"] is True
    assert result["frame_trace_size_bytes"] == trace.stat().st_size
    assert result["frame_trace_activation_seen"] is True


def test_capture_orchestration_records_health_and_frame_trace_growth(tmp_path: Path) -> None:
    from argparse import Namespace
    import json

    from tools.scheduler_trace_capture import _capture

    logs = tmp_path / "logs"
    logs.mkdir()
    trace = logs / "screensaver_frame_trace.bin"
    trace.write_bytes(b"SRPSSFT1" + b"x" * 128)
    (logs / "screensaver.log").write_text(
        "[FRAME_TRACE] explicit binary trace active path=x\n",
        encoding="utf-8",
    )
    calls: list[list[str]] = []

    def runner(argv):
        command = [str(value) for value in argv]
        calls.append(command)
        if "-status" in command:
            return CommandResult(
                tuple(command),
                0,
                "Dropped event : 0\nEvents Lost : 0\nEvents Lost : 0\n",
                "",
            )
        if "-stop" in command:
            etl = Path(command[command.index("-stop") + 1])
            etl.write_bytes(b"fake-etl")
        return CommandResult(tuple(command), 0, "ok", "")

    def sleeper(seconds: float) -> None:
        assert seconds == 60.0
        trace.write_bytes(trace.read_bytes() + b"y" * 256)

    args = Namespace(
        duration_s=60.0,
        profile="GeneralProfile.Light",
        out_dir=str(tmp_path / "captures"),
        label="D1_heavy",
        srpss_log_dir=str(logs),
        filemode=False,
        allow_non_windows_test=True,
    )
    assert _capture(
        args,
        runner=runner,
        sleeper=sleeper,
        wpr_path="wpr.exe",
        xperf_path="",
    ) == 0

    capture_dirs = list((tmp_path / "captures").iterdir())
    assert len(capture_dirs) == 1
    manifest = json.loads(
        (capture_dirs[0] / "scheduler_capture_manifest.json").read_text(
            encoding="utf-8"
        )
    )
    assert manifest["status"] == "complete"
    assert manifest["storage_mode"] == "memory"
    assert manifest["wpr_lost_event_any"] is False
    assert manifest["frame_trace_growth_bytes"] == 256
    assert (capture_dirs[0] / "srpss_scheduler.etl").is_file()
    assert [command[1] for command in calls[:5]] == [
        "-start",
        "-marker",
        "-status",
        "-marker",
        "-stop",
    ]


def test_capture_interrupt_cancels_active_wpr_recording(tmp_path: Path) -> None:
    from argparse import Namespace

    from tools.scheduler_trace_capture import _capture

    calls: list[list[str]] = []

    def runner(argv):
        command = [str(value) for value in argv]
        calls.append(command)
        if "-start" in command:
            return CommandResult(tuple(command), 0, "ok", "")
        if "-marker" in command:
            raise KeyboardInterrupt
        if "-cancel" in command:
            return CommandResult(tuple(command), 0, "cancelled", "")
        return CommandResult(tuple(command), 0, "ok", "")

    args = Namespace(
        duration_s=60.0,
        profile="GeneralProfile.Light",
        out_dir=str(tmp_path / "captures"),
        label="D1_heavy",
        srpss_log_dir="",
        filemode=False,
        allow_non_windows_test=True,
    )
    try:
        _capture(
            args,
            runner=runner,
            sleeper=lambda _seconds: None,
            wpr_path="wpr.exe",
            xperf_path="",
        )
    except SystemExit as exc:
        assert "interrupted" in str(exc)
    else:
        raise AssertionError("expected interrupted capture to exit")
    assert any("-cancel" in command for command in calls)


def test_successful_local_reduction_deletes_raw_etl_by_default(tmp_path: Path) -> None:
    from argparse import Namespace
    import json

    from tools.scheduler_trace_capture import _capture

    logs = tmp_path / "logs"
    logs.mkdir()
    trace = logs / "screensaver_frame_trace.bin"
    trace.write_bytes(b"SRPSSFT1" + b"x" * 128)
    (logs / "screensaver.log").write_text(
        "[FRAME_TRACE] explicit binary trace active path=x\n",
        encoding="utf-8",
    )

    def runner(argv):
        command = [str(value) for value in argv]
        if "-status" in command:
            return CommandResult(tuple(command), 0, "Dropped event : 0\nEvents Lost : 0\n", "")
        if "-stop" in command:
            etl = Path(command[command.index("-stop") + 1])
            etl.write_bytes(b"fake-etl")
        return CommandResult(tuple(command), 0, "ok", "")

    def reducer(capture_dir: Path, *, srpss_log_dir: Path):
        assert srpss_log_dir == logs
        (capture_dir / "scheduler_attribution.json").write_text("{}", encoding="utf-8")
        (capture_dir / "scheduler_attribution.txt").write_text("small", encoding="utf-8")
        return {}

    args = Namespace(
        duration_s=1.0,
        profile="GeneralProfile.Light",
        out_dir=str(tmp_path / "captures"),
        label="D1_heavy",
        srpss_log_dir=str(logs),
        filemode=False,
        keep_etl=False,
        allow_non_windows_test=True,
    )
    assert _capture(
        args,
        runner=runner,
        sleeper=lambda _seconds: None,
        wpr_path="wpr.exe",
        xperf_path="",
        reducer=reducer,
    ) == 0

    capture_dir = next((tmp_path / "captures").iterdir())
    manifest = json.loads(
        (capture_dir / "scheduler_capture_manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["reduction_status"] == "complete"
    assert manifest["etl_retained"] is False
    assert not (capture_dir / "srpss_scheduler.etl").exists()
    assert (capture_dir / "scheduler_attribution.json").is_file()
    assert (capture_dir / "scheduler_attribution.txt").is_file()
