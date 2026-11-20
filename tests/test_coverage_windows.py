"""Coverage selection (``tools/visualizer_replay/coverage_windows.py``; guide section 3): a window is cut from one
continuous run of the take from its cold start. A window run of the layer L tool (ticked from input 0, only the window
kept) delivers exactly the full run's records, settings, cards and sizes over the window; a run whose simulation
restarts at the window start is caught (the control). The selection covers every record field's range, and its windows
are the guide's (cold start, switch, late, loudest, quietest, each field's extremes). On the 5.5 s Studio slice (the
parity script's shortest), CPU only.
"""
from __future__ import annotations

import pytest

SECONDS = 5.5
WINDOW = (200, 260)


@pytest.fixture(scope="module")
def full_stream(tmp_path_factory, qt_app):
    from tools.visualizer_replay import native_record_identity as layer_l

    folder = tmp_path_factory.mktemp("full")
    report = layer_l.run("bubble", seconds=SECONDS, module_dir=None, deliveries=folder)
    return folder, report


def test_a_window_cut_from_the_continuous_run_is_byte_identical_and_a_restart_is_caught(full_stream, tmp_path, qt_app):
    from tools.visualizer_replay import coverage_windows as coverage
    from tools.visualizer_replay import native_record_identity as layer_l

    full, _report = full_stream
    window = tmp_path / "window"
    layer_l.run("bubble", seconds=SECONDS, module_dir=None, deliveries=window, window=WINDOW)
    same = coverage.continuity_check(full, window, *WINDOW)
    assert same["identical"] and same["compared"] == WINDOW[1] - WINDOW[0]
    # Control: the simulation started cold at the window's first input differs from the continuous run there.
    restarted = tmp_path / "restarted"
    layer_l.run("bubble", seconds=SECONDS, module_dir=None, deliveries=restarted, window=WINDOW, restart=True)
    caught = coverage.continuity_check(full, restarted, *WINDOW, offset=WINDOW[0])
    assert caught["compared"] == WINDOW[1] - WINDOW[0]
    assert not caught["identical"] and caught["differing"]


def test_the_selection_covers_every_record_field_with_the_guides_windows(full_stream):
    from core.visualizer_engine.native_schema import schema_for_mode
    from tools.visualizer_replay import coverage_windows as coverage

    full, report = full_stream
    selected = coverage.select("bubble", full, recording=None, seconds=SECONDS, switch_input=report["switch_input"])
    assert selected["covered"], {k: v for k, v in selected["coverage"].items() if not v["covered"]}
    reasons = {reason for window in selected["windows"] for reason in window["reasons"]}
    assert {"cold_start", "switch", "late", "loudest", "quietest"} <= reasons
    fields = {f.name for f in schema_for_mode("bubble").layout.fields[2:]}
    assert set(selected["coverage"]) == fields
    assert selected["late_window_in_last_15_s"]
    assert 0 < selected["window_input_count"] < selected["drawn_inputs"]
    # Control: without the window holding a field's largest value, the report finds a field uncovered.
    uncovered = []
    for name, (low, high) in selected["ranges"].items():
        if high <= low:
            continue
        kept = [w for w in selected["windows"] if f"field:{name}:max" not in w["reasons"]]
        report = coverage.coverage_of("bubble", full, kept, selected["ranges"])
        uncovered += [n for n, entry in report.items() if not entry["covered"]]
    assert uncovered
