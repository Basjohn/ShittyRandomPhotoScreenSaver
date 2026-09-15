from pathlib import Path
import importlib.util


def _load():
    path = Path(__file__).resolve().parents[1] / "tools" / "qsg_render_timing_report.py"
    spec = importlib.util.spec_from_file_location("qsg_render_timing_report", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_qt6_threaded_timing_lines_are_reduced():
    mod = _load()
    lines = [
        "DEBUG message=[window 0x1][render thread 0x2] syncAndRender: start, elapsed since last call: 11 ms",
        "DEBUG message=[window 0x1][render thread 0x2] syncAndRender: frame rendered in 8ms, sync=2, render=5, swap=1",
        "DEBUG message=[window 0x1][render thread 0x2] syncAndRender: frame rendered in 10ms, sync=3, render=6, swap=1",
    ]
    metrics = mod.parse_lines(lines)
    assert metrics["since_last"] == [11.0]
    assert metrics["frame_total"] == [8.0, 10.0]
    assert metrics["sync"] == [2.0, 3.0]
    assert metrics["render"] == [5.0, 6.0]
    assert metrics["swap"] == [1.0, 1.0]
    report = mod.render_report(metrics)
    assert "qsg_native_frames=2" in report
    assert "sync_ms n=2 median=2.500" in report


def test_legacy_window_time_is_supported():
    mod = _load()
    metrics = mod.parse_lines([
        "window Time: sinceLast=12, sync=2, first render=7, after final swap=3"
    ])
    assert metrics["since_last"] == [12.0]
    assert metrics["frame_total"] == [12.0]
    assert metrics["sync"] == [2.0]
    assert metrics["render"] == [7.0]
    assert metrics["swap"] == [3.0]


def test_qsg_timing_runtime_admission_is_retired_but_reporter_is_preserved():
    root = Path(__file__).resolve().parents[1]
    main_source = (root / "main.py").read_text(encoding="utf-8")
    foundry_source = (root / "tools" / "godzip_foundry_core.py").read_text(encoding="utf-8")
    flags_source = (root / "core" / "diagnostics" / "experiment_flags.py").read_text(encoding="utf-8")
    assert "apply_qsg_render_timing_environment" not in main_source
    assert "apply_qsg_render_timing_environment" not in flags_source
    assert '"--qsg-render-timing", # retired R-87 observer' in foundry_source
    # Keep the old token mode-filtered so an old shortcut cannot break /s parsing.
    assert '"--noupdates", "--frame-trace", "--qsg-render-timing"' in main_source


def test_rejected_gil_switch_flag_is_not_runtime_cli_or_foundry_surface():
    root = Path(__file__).resolve().parents[1]
    main_source = (root / "main.py").read_text(encoding="utf-8")
    foundry_source = (root / "tools" / "godzip_foundry_core.py").read_text(encoding="utf-8")
    flags_source = (root / "core" / "diagnostics" / "experiment_flags.py").read_text(encoding="utf-8")
    assert "--gil-switch-1ms" not in main_source
    assert "--gil-switch-1ms" not in foundry_source
    assert "--gil-switch-1ms" not in flags_source
