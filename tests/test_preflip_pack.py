"""The pre-flip reference pack's driver: the matrix enumeration, the row filter, resume, the compare arithmetic and the
conditions block, all with stubbed measurement (no saver, no display, no GPU). No preset or product name is pinned: modes
and transitions are fake ids, or read back from the registry the driver itself reads."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytest

from tools import preflip_pack as pack
from tools.visualizer_live_check import parse_setting, summarise_process_samples

MODES = ["mode_a", "mode_b", "mode_c"]
TRANSITIONS = [("t_one", "T One"), ("t_two", "T Two")]


def rows(sizes=("2160p",), state="idle"):
    return pack.enumerate_rows(sizes, state, modes=MODES, transitions=TRANSITIONS)


# -- enumeration ---------------------------------------------------------------------------------------------------------

def test_matrix_is_every_mode_and_transition_at_every_size_and_state():
    matrix = rows()
    assert len(matrix) == len(MODES) + len(TRANSITIONS)
    assert len({row.key for row in matrix}) == len(matrix)
    for size in pack.SIZES:
        assert {r.ident for r in matrix if r.size == size and r.kind == "visualizer"} == set(MODES)
        assert {r.ident for r in matrix if r.size == size and r.kind == "transition"} == {i for i, _ in TRANSITIONS}
    assert {r.state for r in rows(state="loaded")} == {"loaded"}
    assert all(r.key.endswith("/loaded") for r in rows(state="loaded"))


def test_modes_come_from_the_registry_and_transitions_are_the_named_set_resolved_through_it():
    from core.settings.visualizer_mode_registry import iter_visualizer_mode_descriptors
    from rendering.transition_registry import iter_transition_descriptors

    assert pack.registry_visualizer_modes() == [d.mode_id for d in iter_visualizer_mode_descriptors()]
    labels = {d.stable_id: d.setting_name for d in iter_transition_descriptors() if d.available}
    assert pack.registry_transitions() == [(name, labels[name]) for name in pack.SESSION_TRANSITIONS]
    matrix = pack.enumerate_rows(["2160p"], "idle")
    assert {r.ident for r in matrix if r.kind == "visualizer"} == set(pack.registry_visualizer_modes())
    assert [r.ident for r in matrix if r.kind == "transition"] == list(pack.SESSION_TRANSITIONS)


def test_a_named_transition_the_registry_no_longer_offers_is_an_error_not_a_silent_gap():
    with pytest.raises(ValueError):
        pack.registry_transitions(("not_a_transition",))


def test_a_new_registry_entry_becomes_a_row_without_editing_the_driver():
    base = {r.key for r in rows(["2160p"])}
    more = {r.key for r in pack.enumerate_rows(["2160p"], "idle", modes=[*MODES, "mode_new"], transitions=TRANSITIONS)}
    assert more - base == {"visualizer/mode_new/2160p/idle"}


def test_duplicate_registry_ids_are_refused():
    with pytest.raises(ValueError):
        pack.enumerate_rows(["2160p"], "idle", modes=["x", "x"], transitions=[])


# -- row filter and resume -----------------------------------------------------------------------------------------------

def test_filter_by_glob_and_report_patterns_that_match_nothing():
    matrix = rows()
    chosen, unmatched = pack.filter_rows(matrix, ["visualizer/*/2160p/*"])
    assert {r.key for r in chosen} == {r.key for r in matrix if r.kind == "visualizer" and r.size == "2160p"}
    assert unmatched == []
    chosen, unmatched = pack.filter_rows(matrix, ["transition/t_one/*", "nothing/*"])
    assert {r.ident for r in chosen} == {"t_one"} and len(chosen) == 1
    assert unmatched == ["nothing/*"]
    assert pack.filter_rows(matrix, None) == (matrix, [])
    assert pack.split_patterns(" a/* , ,b/* ") == ["a/*", "b/*"]


def test_pending_skips_ok_rows_and_retries_failed_ones():
    matrix = rows(["2160p"])
    baseline = {"rows": {matrix[0].key: {"status": "ok"}, matrix[1].key: {"status": "failed"}}}
    todo = pack.pending_rows(matrix, baseline)
    assert matrix[0] not in todo and matrix[1] in todo and len(todo) == len(matrix) - 1
    assert len(pack.pending_rows(matrix, baseline, redo=True)) == len(matrix)


def _figures(**over):
    base = {name: 10.0 for name, _h, _b in pack.METRICS}
    base.update(over)
    return base


def _summary(**over):
    summary = {"frames_per_s": 60.0, "render_mode_ms": {"median": 4.0, "p90": 6.0},
               "quick_render_ms": {"median": 9.0, "p90": 11.0}, "swap_gap_ms": {"median": 16.6, "p90": 18.0},
               "steady_late_pct": 1.0, "hitches_per_min": 0.5, "post_startup_frames": 120, "post_startup_late_pct": 2.0,
               "steady_seconds": 55.0, "conditions": {"cpu_others_median": 3.0},
               "process": {"cpu_core_pct": 40.0, "gpu_pct": 30.0, "gpu_ms_per_frame": 5.0, "rss_mb": 800.0,
                           "private_mb": 1200.0}}
    summary.update(over)
    return summary


def _no_session(group, out):
    raise AssertionError("a Visualizer row was measured as a transition session")


def visualizer_rows(sizes=("2160p",)):
    """The matrix's Visualizer rows: measured one process each by ``measure`` (transition rows always run in a session;
    tests/test_preflip_session.py proves that path)."""
    return [row for row in rows(sizes) if row.kind == "visualizer"]


def test_measurement_is_resumable_one_saved_row_at_a_time(tmp_path):
    matrix = visualizer_rows(["2160p"])
    path = tmp_path / "b.json"
    baseline = pack.new_baseline("b", commit="abc", load=None, backend="x")
    saves, calls = [], []

    def measure(row, out):
        calls.append(row.key)
        if len(calls) == 3:
            raise KeyboardInterrupt                      # the window ends mid-matrix
        return 0, _summary()

    def save(p, data):
        saves.append(sorted(data["rows"]))
        pack.save_baseline(p, data)

    kwargs = dict(conditions_fn=lambda: {"c": 1}, displays_fn=lambda: [{"index": 1, "width": 3840, "height": 2160,
                                                                       "primary": False}],
                  out_dir_fn=lambda row, session=False: tmp_path / row.ident, save=save, measure_session=_no_session)
    with pytest.raises(KeyboardInterrupt):
        pack.measure_rows(matrix, baseline, path, measure=measure, **kwargs)
    assert len(saves) == 2 and len(saves[-1]) == 2          # each finished row was on disk before the next began
    resumed = pack.load_baseline(path)
    calls.clear()
    outcome = pack.measure_rows(matrix, resumed, path, measure=lambda row, out: (calls.append(row.key), (0, _summary()))[1],
                                **kwargs)
    assert calls == [r.key for r in matrix[2:]]             # the two stored rows are not measured again
    assert len(outcome["ok"]) == len(matrix) - 2
    assert {r["status"] for r in pack.load_baseline(path)["rows"].values()} == {"ok"}


def test_failed_row_is_recorded_and_retried_and_a_missing_display_skips_without_blocking(tmp_path):
    matrix = visualizer_rows(["2160p"])
    baseline = pack.new_baseline("b", commit="abc", load=None, backend=None)
    only_d1 = [{"index": 1, "width": 3840, "height": 2160, "primary": False}]
    out = pack.measure_rows(matrix[:1], baseline, tmp_path / "b.json", measure=lambda r, o: (3, None),
                            conditions_fn=dict, displays_fn=lambda: only_d1,
                            out_dir_fn=lambda r, session=False: tmp_path / "x", save=lambda *a: None,
                            measure_session=_no_session)
    assert out["failed"] == [matrix[0].key] and baseline["rows"][matrix[0].key]["status"] == "failed"
    assert pack.pending_rows(matrix[:1], baseline) == matrix[:1]
    out = pack.measure_rows(matrix, baseline, tmp_path / "b.json", measure=lambda r, o: (0, _summary()),
                            conditions_fn=dict, displays_fn=lambda: [], redo=True,
                            out_dir_fn=lambda r, session=False: tmp_path / "y", save=lambda *a: None,
                            measure_session=_no_session)
    assert set(out["skipped"]) == {r.key for r in matrix} and not out["ok"]


def test_display_problem_names_missing_wrong_size_and_primary():
    d1, d0 = pack.SIZES["2160p"], pack.Size("primary_view", 0, 2560, 1440)
    shown = [{"index": 0, "width": 2560, "height": 1440, "primary": True},
             {"index": 1, "width": 3840, "height": 2160, "primary": False}]
    assert pack.display_problem(d1, shown) is None
    assert "primary" in pack.display_problem(d0, shown)             # the primary is refused outright, no override
    assert "not present" in pack.display_problem(d1, shown[:1])
    wrong = [{"index": 1, "width": 1920, "height": 1080, "primary": False}]
    assert "1920 x 1080" in pack.display_problem(d1, wrong)
    assert all(size.display != 0 for size in pack.SIZES.values())    # nothing in the matrix is on Display 0


# -- the live check's command line -----------------------------------------------------------------------------------------

def test_row_command_is_one_size_invisible_and_never_loaded_by_default(tmp_path):
    viz = next(r for r in rows(["2160p"]) if r.kind == "visualizer")
    trans = next(r for r in rows(["2160p"]) if r.kind == "transition")
    cmd = pack.row_command(viz, tmp_path, preset_slot=lambda mode: 7)
    assert cmd[cmd.index("--mode") + 1] == viz.ident and cmd[cmd.index("--preset") + 1] == "7"
    assert cmd[cmd.index("--display") + 1] == str(pack.SIZES["2160p"].display)
    assert "--visible" not in cmd and "--load" not in cmd and "--no-updates" in cmd and "--process-samples" in cmd
    cmd = pack.row_command(trans, tmp_path)
    assert cmd[cmd.index("--mode") + 1] == "none" and "--preset" not in cmd
    assert cmd[cmd.index("--display") + 1] == str(pack.SIZES["2160p"].display)
    settings = dict(pack.row_settings(trans))
    assert settings["transitions.type"] == trans.label and settings["transitions.random_always"] is False
    assert settings[f"transitions.activation.{trans.label}"] is True
    assert settings["widgets.spotify_visualizer.enabled"] is False
    loaded = pack.enumerate_rows(["2160p"], "loaded", modes=MODES, transitions=TRANSITIONS)[0]
    command = pack.row_command(loaded, tmp_path, preset_slot=lambda mode: 1)
    assert command[command.index("--load") + 1] == "game60"


def test_default_preset_slot_follows_the_canonical_default_one_based():
    from core.settings.default_contract import get_canonical_default

    for mode in pack.registry_visualizer_modes():
        stored = get_canonical_default(f"widgets.spotify_visualizer.preset_{mode}", pack.APPLICATION, missing=None)
        assert pack.default_preset_slot(mode) == (stored if isinstance(stored, int) else 0) + 1


def test_game60_is_an_explicit_choice_and_nothing_else_is_accepted():
    parser = pack.build_parser()
    assert parser.parse_args([]).load is None
    assert parser.parse_args(["--load", "game60"]).load == "game60"
    with pytest.raises(SystemExit):
        parser.parse_args(["--load", "game90"])
    args = parser.parse_args(["--size", "2160p", "--load", "game60"])
    planned, _ = pack.plan_rows(args, modes=MODES, transitions=TRANSITIONS)
    assert {r.state for r in planned} == {"loaded"}
    assert {r.state for r in pack.plan_rows(parser.parse_args([]), modes=MODES, transitions=TRANSITIONS)[0]} == {"idle"}


def test_compare_run_covers_only_rows_the_old_baseline_holds():
    parser = pack.build_parser()
    old = {"rows": {"visualizer/mode_a/2160p/idle": {}, "transition/t_two/2160p/idle": {}, "visualizer/gone/2160p/idle": {}}}
    planned, _ = pack.plan_rows(parser.parse_args(["--size", "2160p"]), modes=MODES, transitions=TRANSITIONS, old=old)
    assert {r.key for r in planned} == {"visualizer/mode_a/2160p/idle", "transition/t_two/2160p/idle"}


def test_every_registered_transition_is_selectable_by_rows_and_the_default_matrix_is_unchanged():
    parser = pack.build_parser()
    registered = pack.all_registry_transitions()
    ids = [ident for ident, _label in registered]
    assert set(pack.SESSION_TRANSITIONS) < set(ids) and "beam" in ids
    default, _ = pack.plan_rows(parser.parse_args([]))
    assert [r.ident for r in default if r.kind == "transition"] == list(pack.SESSION_TRANSITIONS)
    for ident, label in registered:
        planned, unmatched = pack.plan_rows(parser.parse_args(["--rows", f"transition/{ident}/*"]))
        assert unmatched == [] and [r.key for r in planned] == [f"transition/{ident}/2160p/idle"]
        assert planned[0].label == label and planned[0].kind == "transition"
    # the existing baseline rows keep their keys
    for ident in pack.SESSION_TRANSITIONS:
        assert f"transition/{ident}/2160p/idle" in {r.key for r in pack.plan_rows(parser.parse_args(["--rows", "transition/*"]))[0]}
    # negative control: a transition the registry does not offer matches nothing
    planned, unmatched = pack.plan_rows(parser.parse_args(["--rows", "transition/not_a_transition/*"]))
    assert planned == [] and unmatched == ["transition/not_a_transition/*"]


def test_a_compare_rerun_of_a_non_default_transition_needs_its_row_in_the_old_baseline():
    parser = pack.build_parser()
    args = parser.parse_args(["--rows", "transition/t_extra/*"])
    allt = [*TRANSITIONS, ("t_extra", "T Extra")]
    old = {"rows": {"transition/t_extra/2160p/idle": {}}}
    planned, _ = pack.plan_rows(args, modes=MODES, old=old, all_transitions=allt)
    assert [r.key for r in planned] == ["transition/t_extra/2160p/idle"]
    planned, _ = pack.plan_rows(args, modes=MODES, old={"rows": {}}, all_transitions=allt)
    assert planned == []                                    # negative control: no old row, nothing to compare against


def test_a_row_is_recorded_on_its_own_into_an_existing_baseline_without_touching_the_rest(tmp_path):
    path = tmp_path / "named.json"
    first = pack.new_baseline("named", commit="old1234", load=None, backend="python-gl")
    first["rows"]["transition/t_one/2160p/idle"] = {"key": "transition/t_one/2160p/idle", "status": "ok",
                                                    "figures": _figures()}
    first["controls"]["2160p"] = {"control_gpu_quiet_ms": 1.0}
    pack.save_baseline(path, first)
    before = json.dumps(pack.load_baseline(path)["rows"], sort_keys=True)

    baseline = pack.open_baseline(path, "named", commit="new5678", load=None, backend="something-else")
    row = pack.Row("visualizer/m_extra/2160p/idle", "visualizer", "m_extra", "m_extra", "2160p", "idle", 75.0)
    pack.measure_rows([row], baseline, path, measure=lambda r, o: (0, _summary()), conditions_fn=dict,
                      measure_session=_no_session,
                      displays_fn=lambda: [{"index": 1, "width": 3840, "height": 2160, "primary": False}],
                      out_dir_fn=lambda r, session=False: tmp_path / "o",
                      save=lambda p, d: (pack.stamp_new_rows(d, {row.key}, commit="new5678", backend="native-vulkan"),
                                         pack.save_baseline(p, d)))
    merged = pack.load_baseline(path)
    assert merged["commit"] == "old1234" and merged["backend"] == "python-gl" and merged["controls"]["2160p"]
    assert merged["rows"][row.key]["status"] == "ok"
    assert (merged["rows"][row.key]["commit"], merged["rows"][row.key]["backend"]) == ("new5678", "native-vulkan")
    assert "commit" not in merged["rows"]["transition/t_one/2160p/idle"]     # the stored row was not restamped
    kept = {k: v for k, v in merged["rows"].items() if k != row.key}
    assert json.dumps(kept, sort_keys=True) == before
    # negative control: a name with no file is a new baseline carrying the label, not the other file's content
    fresh = pack.open_baseline(tmp_path / "none.json", "none", commit="c", load=None, backend="lbl")
    assert fresh["rows"] == {} and fresh["backend"] == "lbl"


def test_estimate_scales_with_rows_and_load():
    matrix = rows(["2160p"])
    idle = pack.estimate_seconds(matrix, per_row=True)
    loaded = pack.estimate_seconds(matrix, loaded=True, per_row=True)
    # Per row, a Visualizer row is its own process and a transition its own one-transition session.
    assert idle == sum(pack.unit_seconds(unit) + pack.ROW_OVERHEAD_S for unit in pack.plan_units(matrix, per_row=True))
    assert len(pack.plan_units(matrix, per_row=True)) == len(matrix)
    assert loaded - idle == pytest.approx(len(matrix) * pack.LOAD_CALIBRATION_S)


# -- figures ---------------------------------------------------------------------------------------------------------------

def test_figures_use_the_visualizer_draw_else_quicks_render_phase():
    figures = pack.extract_figures(_summary())
    assert (figures["render_median_ms"], figures["render_source"]) == (4.0, "render_mode_ms")
    assert figures["fps"] == 60.0 and figures["first2s_frames"] == 120 and figures["cpu_core_pct"] == 40.0
    figures = pack.extract_figures(_summary(render_mode_ms=None))
    assert (figures["render_median_ms"], figures["render_p90_ms"], figures["render_source"]) == (9.0, 11.0, "quick_render_ms")
    bare = pack.extract_figures({})
    assert bare["fps"] is None and bare["render_source"] is None and bare["gpu_ms_per_frame"] is None


def test_process_samples_summarise_the_steady_window_only():
    samples = [{"perf_ns": t * 10**9, "cpu_core_pct": c, "gpu_pct": g, "rss_mb": r, "private_mb": r * 2}
               for t, c, g, r in ((1, 300.0, 90.0, 500.0), (5, 50.0, 25.0, 800.0), (6, 70.0, 35.0, 810.0),
                                  (7, 60.0, 30.0, 820.0), (20, 5.0, 1.0, 100.0))]
    summary = summarise_process_samples(samples, (4 * 10**9, 10 * 10**9), 60.0)
    assert summary["samples"] == 3 and summary["cpu_core_pct"] == 60.0 and summary["gpu_pct"] == 30.0
    assert summary["gpu_ms_per_frame"] == pytest.approx(30.0 / 100 * 1000 / 60.0, abs=1e-3)
    assert summary["rss_mb"] == 810.0 and summary["private_mb_max"] == 1640.0
    assert summarise_process_samples(samples, (100 * 10**9, 200 * 10**9), 60.0) is None
    none_gpu = summarise_process_samples([{"perf_ns": 1, "cpu_core_pct": 10.0, "gpu_pct": None}], None, 60.0)
    assert none_gpu["gpu_ms_per_frame"] is None and none_gpu["gpu_pct"] is None


def test_live_check_setting_argument_is_key_equals_json():
    assert parse_setting("a.b=[1, 2]") == ("a.b", [1, 2])
    assert parse_setting("a.b.c=\"x=y\"") == ("a.b.c", "x=y")
    for bad in ("novalue", "=1", "a=notjson"):
        with pytest.raises(argparse.ArgumentTypeError):
            parse_setting(bad)


# -- compare arithmetic ----------------------------------------------------------------------------------------------------

def test_gain_is_positive_when_better_in_either_direction_and_none_without_a_ratio():
    assert pack.gain_pct(100.0, 80.0, "lower") == 20.0
    assert pack.gain_pct(100.0, 120.0, "lower") == -20.0
    assert pack.gain_pct(50.0, 60.0, "higher") == 20.0
    assert pack.gain_pct(50.0, 40.0, "higher") == -20.0
    assert pack.gain_pct(0.0, 5.0, "lower") is None and pack.gain_pct(None, 5.0, "lower") is None
    assert pack.gain_pct(5.0, None, "higher") is None
    assert pack.verdict(6.0) == "better" and pack.verdict(-6.0) == "worse" and pack.verdict(5.0) == "flat"
    assert pack.verdict(None) == "n/a"


def _baseline(name, rows_, controls=None):
    return {"name": name, "commit": name, "backend": name, "controls": controls or {}, "rows": rows_}


def _row(**figures):
    return {"status": "ok", "figures": _figures(**figures), "conditions_during": {"cpu_others_median": 3.0}}


def test_compare_reports_gain_per_row_and_per_metric_direction():
    old = _baseline("old", {"k/1": _row(fps=50.0, render_median_ms=10.0, late_pct=4.0),
                            "k/2": _row(), "k/gone": _row()},
                    {"2160p": {"control_gpu_quiet_ms": 0.010}})
    new = _baseline("new", {"k/1": _row(fps=60.0, render_median_ms=5.0, late_pct=4.0),
                            "k/2": {"status": "failed", "figures": None}, "k/added": _row()},
                    {"2160p": {"control_gpu_quiet_ms": 0.012}})
    report = pack.compare_baselines(old, new)
    row = report["rows"]["k/1"]
    assert row["fps"]["gain_pct"] == 20.0 and row["fps"]["verdict"] == "better"
    assert row["render_median_ms"]["gain_pct"] == 50.0
    assert row["late_pct"]["gain_pct"] == 0.0 and row["late_pct"]["verdict"] == "flat"
    assert report["added"] == ["k/added"] and report["removed"] == ["k/gone"] and report["unmeasured"] == ["k/2"]
    assert report["controls"]["2160p"]["ratio"] == 1.2
    assert report["summary"]["fps"] == {"rows": 1, "median_gain_pct": 20.0, "better": 1, "worse": 0}
    text = "\n".join(pack.format_compare(report))
    assert "k/1" in text and "k/added" in text and "x1.2" in text
    assert "| `k/1` |" in pack.compare_markdown(report)


def test_compare_flags_rows_measured_under_different_conditions_and_a_missing_control():
    quiet = {"status": "ok", "figures": _figures(), "conditions_during": {"cpu_others_median": 3.0, "gpu_clock_mhz_median": 2700.0}}
    busy = {"status": "ok", "figures": _figures(), "conditions_during": {"cpu_others_median": 60.0, "gpu_clock_mhz_median": 900.0}}
    report = pack.compare_baselines(_baseline("o", {"k": quiet}), _baseline("n", {"k": busy}))
    notes = report["conditions_differ"]["k"]
    assert any("other processes" in n for n in notes) and any("GPU clock" in n for n in notes)
    assert "no session control" in "\n".join(pack.format_compare(report))


# -- conditions block ------------------------------------------------------------------------------------------------------

def test_conditions_record_displays_processes_gpu_clock_and_smi_state():
    required = {"2160p": pack.SIZES["2160p"], "other": pack.Size("other", 0, 2560, 1440)}
    shown = [{"index": 0, "width": 2560, "height": 1440, "primary": True},
             {"index": 1, "width": 3840, "height": 2160, "primary": False}]
    block = pack.collect_conditions(
        required=required, displays_fn=lambda: shown,
        processes_fn=lambda: [{"pid": 4, "name": "x.exe", "cpu_core_pct": 12.0}],
        gpu_processes_fn=lambda: [{"pid": 5, "name": "y.exe", "gpu_pct": 8.0}],
        nvidia_fn=lambda: {"available": True, "clocks_gr_mhz": 2100.0, "pstate": "P0", "temp_c": 50.0},
        clock=lambda: 0.0)
    assert block["displays"]["displays_on"] is True and block["displays"]["missing"] == {}
    assert block["other_processes_cpu"][0]["name"] == "x.exe" and block["other_processes_gpu"][0]["gpu_pct"] == 8.0
    assert block["gpu_clock_mhz"] == 2100.0 and block["nvidia_smi"]["pstate"] == "P0" and block["captured_at"]
    json.dumps(block)


def test_a_missing_or_resized_display_reads_as_off_and_a_failing_source_never_stops_the_row():
    required = {"2160p": pack.SIZES["2160p"], "other": pack.Size("other", 0, 2560, 1440)}

    def broken():
        raise OSError("counter gone")

    block = pack.collect_conditions(
        required=required, displays_fn=lambda: [{"index": 0, "width": 2560, "height": 1440, "primary": True}],
        processes_fn=broken, gpu_processes_fn=lambda: None, nvidia_fn=broken, clock=lambda: 0.0)
    assert block["displays"]["displays_on"] is False and set(block["displays"]["missing"]) == {"2160p"}
    assert "OSError" in block["other_processes_cpu"]["unavailable"] and block["gpu_clock_mhz"] is None
    resized = pack.displays_state(required, [{"index": 0, "width": 2560, "height": 1440},
                                             {"index": 1, "width": 1920, "height": 1080}])
    assert resized["displays_on"] is False and "1920 x 1080" in resized["missing"]["2160p"]


def test_control_is_read_from_the_overhead_baseline_load_block():
    control = pack.control_from_baseline({"size": "2560x1440", "renderer": "gpu", "commit": "c",
                                          "load": {"control_gpu_quiet": 0.009, "admitted": 90, "controls": 100}})
    assert control["control_gpu_quiet_ms"] == 0.009 and control["admitted"] == 90 and control["size"] == "2560x1440"


# -- storage and markdown --------------------------------------------------------------------------------------------------

def test_baseline_round_trips_atomically_and_renders_a_markdown_table(tmp_path):
    baseline = pack.new_baseline("n", commit="abc", load="game60", backend="python-vulkan")
    baseline["rows"]["visualizer/mode_a/2160p/loaded"] = {"status": "ok", "figures": pack.extract_figures(_summary()),
                                                          "conditions_before": None}
    baseline["rows"]["transition/t_one/2160p/loaded"] = {"status": "failed", "exit_code": 3, "figures": None}
    path = tmp_path / "sub" / "n.json"
    pack.save_baseline(path, baseline)
    assert pack.load_baseline(path)["rows"].keys() == baseline["rows"].keys() and not list(path.parent.glob("*.tmp"))
    markdown = pack.baseline_markdown(pack.load_baseline(path))
    assert "visualizer/mode_a/2160p/loaded" in markdown and "FAILED (exit 3)" in markdown and "game60" in markdown
    assert sum(line.startswith("|---") for line in markdown.splitlines()) == 1


def test_baseline_names_become_slugs_under_the_preflip_folder():
    path = pack.baseline_path("Before Flip")
    assert path.parent == pack.BASELINES and path.name == "before_flip.json"
