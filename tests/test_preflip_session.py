"""The pre-flip pack's transition session: windows cut from a stubbed frame trace, an end event that never came, attribution
in the planned order, and ``--compare`` over session rows. No saver, no display: traces are lists of
``(ts_ns, event, screen, revision, aux)`` and the saver's own state file is a dict."""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from tools import live_check_transition_session as session
from tools import preflip_pack as pack

MS = 1_000_000
NAMES = ["Name A", "Name B", "Name C"]
LABELS = [("a", "Name A"), ("b", "Name B"), ("c", "Name C")]


def frames(run_id, start_ms, count, *, gap_ms=16.0, slow_at=(), end_record=True):
    """The records of ``count`` frames of one run: Quick's render phase, the background node's begin and ready records
    carrying ``run_id``, and the swap. ``slow_at``: frame indices that swap ``gap_ms * 4`` late (a late frame)."""
    events, now = [], start_ms * MS
    for index in range(count):
        now += int((gap_ms * (4 if index in slow_at else 1)) * MS)
        events += [(now, 51, 0, index, 0), (now + MS, session.BACKGROUND_RENDER_BEGIN, 0, index, run_id),
                   (now + 2 * MS, 54, 0, index, 0), (now + 3 * MS, 6, 0, index, 0)]
        if end_record or index < count - 1:
            events.append((now + 2 * MS, session.BACKGROUND_RENDER_READY, 0, index, run_id))
    return events


def trace(*parts, startup_end_ms=100):
    events = [(1 * MS, 62, -1, 0, 0), (startup_end_ms * MS, 63, -1, 0, 0)]
    for part in parts:
        events += part
    return sorted(events, key=lambda item: item[0])


def state(*runs):
    return {"names": NAMES, "calls": [], "runs": [dict(run_id=r, transition_id=f"id_{n}", name=n, duration_ms=1000, at=0.0)
                                                  for r, n in runs]}


def by_name(analysis):
    return {row["name"]: row for row in analysis["rows"]}


# -- windows ---------------------------------------------------------------------------------------------------------------

def test_a_window_runs_from_its_first_begin_record_to_its_last_ready_record_and_only_its_own_frames_count():
    events = trace(frames(1, 200, 30), frames(2, 1000, 30, slow_at={10}), frames(0, 700, 5))   # aux 0: no run
    windows = session.cut_windows(events)
    assert set(windows) == {1, 2} and all(w["complete"] for w in windows.values())
    first = [e for e in events if e[1] == session.BACKGROUND_RENDER_BEGIN and e[4] == 1]
    last_ready = [e for e in events if e[1] == session.BACKGROUND_RENDER_READY and e[4] == 1]
    assert windows[1]["begin_ns"] == first[0][0] and windows[1]["end_ns"] == last_ready[-1][0]
    analysis = session.analyse_session(events, state((1, "Name A"), (2, "Name B")), ["Name A", "Name B"])
    a, b = by_name(analysis)["Name A"], by_name(analysis)["Name B"]
    assert a["status"] == b["status"] == "ok" and analysis["failures"] == []
    assert a["late_frames"] == 0 and b["late_frames"] >= 1 and b["hitches"] >= 1       # 64 ms gaps: late and a hitch
    assert 55.0 < a["fps"] < 70.0 and a["swap_gap_ms"]["median"] == pytest.approx(16.0, abs=0.5)
    assert a["quick_render_ms"]["median"] == pytest.approx(2.0, abs=0.1)
    assert a["frames"] == 30 and a["frame_source"] == "quick_after_rendering"      # no swap records without a Visualizer


def test_a_run_with_no_end_record_is_failed_not_measured_on_a_partial_window():
    events = trace(frames(1, 200, 30), frames(2, 1000, 30, end_record=False))     # the last ready record never came
    windows = session.cut_windows(events)
    assert windows[1]["complete"] and not windows[2]["complete"] and windows[2]["end_ns"] is None
    analysis = session.analyse_session(events, state((1, "Name A"), (2, "Name B")), ["Name A", "Name B"])
    rows = by_name(analysis)
    assert rows["Name A"]["status"] == "ok"
    assert rows["Name B"]["status"] == "failed" and "end record" in rows["Name B"]["reason"]
    assert "fps" not in rows["Name B"] and len(analysis["failures"]) == 1


def test_a_planned_name_with_no_run_or_no_begin_record_fails_and_a_dead_saver_is_a_failure_too():
    events = trace(frames(1, 200, 30))
    analysis = session.analyse_session(events, state((1, "Name A"), (2, "Name B")), ["Name A", "Name B", "Name C"])
    rows = by_name(analysis)
    assert rows["Name B"]["status"] == "failed" and "begin record" in rows["Name B"]["reason"]      # run 2 left no frames
    assert rows["Name C"]["status"] == "failed" and "no transition run" in rows["Name C"]["reason"]
    assert session.analyse_session(events, None, ["Name A"])["failures"]
    assert any("exited with code 9" in f for f in session.analyse_session(events, state((1, "Name A")), ["Name A"],
                                                                         returncode=9)["failures"])


def native_frames(run_id, start_ms, count, *, gap_ms=16.0, first_ms=4.0, slow_at=(), end_record=True, screen=0):
    """A run the native core draws (Vulkan's background layer) on ``screen``'s window: a NATIVE_TRANSITION_TICK when it
    starts and one per frame, Quick's frames (no background-node record carries the run), and NATIVE_TRANSITION_END at
    its end. The first frame lands ``first_ms`` after the start; ``slow_at``: frames ``gap_ms * 4`` late."""
    start = start_ms * MS
    events = [(start, session.NATIVE_TRANSITION_TICK, screen, 0, run_id)]
    now = start + int(first_ms * MS) - int(gap_ms * MS)
    for index in range(count):
        now += int((gap_ms * (4 if index in slow_at else 1)) * MS)
        events += [(now - MS, session.NATIVE_TRANSITION_TICK, screen, index, run_id), (now, 51, screen, index, 0),
                   (now + MS, 54, screen, index, 0)]
    if end_record:
        events.append((now + 2 * MS, session.NATIVE_TRANSITION_END, screen, count, run_id))
    events.append((now + 20 * MS, 54, screen, count, 0))              # the destination's handover: after the window
    return events


def test_a_native_run_is_cut_from_its_tick_and_end_records_and_is_failed_without_its_end():
    events = trace(native_frames(1, 200, 30), native_frames(2, 1000, 30, end_record=False))
    windows = session.cut_windows(events)
    assert windows[1]["complete"] and windows[1]["native"] and windows[1]["begin_ns"] == 200 * MS
    # Control: the run whose end record never came is failed, never measured on a partial window.
    assert not windows[2]["complete"] and windows[2]["end_ns"] is None and "NATIVE_TRANSITION_END" in windows[2]["reason"]
    rows = by_name(session.analyse_session(events, state((1, "Name A"), (2, "Name B")), ["Name A", "Name B"]))
    assert rows["Name A"]["status"] == "ok" and rows["Name A"]["frames"] == 30           # the handover frame is outside
    assert rows["Name B"]["status"] == "failed"


def test_a_runs_hitch_verdict_is_no_frame_gap_over_33_ms_with_its_first_frame_from_the_runs_start():
    smooth = session.run_gaps(trace(native_frames(1, 200, 60)), 200 * MS, 200 * MS + 61 * 16 * MS, screen=0)
    assert smooth["hitch_verdict"] == "pass" and smooth["gaps_over_limit"] == 0
    assert smooth["gap_ms"]["median"] == pytest.approx(16.0, abs=0.5) and smooth["first_frame_ms"] == pytest.approx(5.0)
    # Controls: one 64 ms gap inside the run, and a first-run compile stall (the first frame 80 ms after the start).
    events = trace(native_frames(1, 200, 60, slow_at={30}))
    rows = by_name(session.analyse_session(events, state((1, "Name A")), ["Name A"]))
    assert rows["Name A"]["status"] == "ok" and rows["Name A"]["hitch_verdict"].startswith("fail: 1 gap")
    stalled = trace(native_frames(1, 200, 60, first_ms=80.0))
    row = by_name(session.analyse_session(stalled, state((1, "Name A")), ["Name A"]))["Name A"]
    assert row["first_frame_ms"] == pytest.approx(81.0) and row["hitch_verdict"].startswith("fail")
    # The figures reach the stored record and its table.
    figures = pack.session_figures(row)
    assert figures["hitch_verdict"] == row["hitch_verdict"] and figures["gap_ms"]["max"] >= 80.0
    assert session.run_gaps(trace(), 0, MS, screen=0)["hitch_verdict"].startswith("fail: no frame")


def other_screen_frames(start_ms, count, *, gap_ms=50.0, screen=0):
    """Another display's window rendering on its own thread: Quick's render phase records on ``screen``, no run."""
    events, now = [], start_ms * MS
    for index in range(count):
        now += int(gap_ms * MS)
        events += [(now, 51, screen, index, 0), (now + 3 * MS, 54, screen, index, 0)]
    return events


def test_a_runs_figures_count_only_its_own_screens_frames():
    """N5.2c audit: each display's window renders on its own thread, so a run's gaps, fps and render times are its own
    screen's frames (the screen its tick records carry), never another window's."""
    events = trace(native_frames(1, 200, 60, screen=1), other_screen_frames(195, 22, screen=0))
    windows = session.cut_windows(events)
    assert windows[1]["screen"] == 1
    row = by_name(session.analyse_session(events, state((1, "Name A")), ["Name A"]))["Name A"]
    assert row["status"] == "ok" and row["screen"] == 1 and row["frames"] == 60 and row["hitch_verdict"] == "pass"
    assert row["gap_ms"]["median"] == pytest.approx(16.0, abs=0.5) and row["quick_render_ms"]["median"] == pytest.approx(1.0)
    # Control: the same frames read as one screen's (the other window's records relabelled onto the run's screen), as an
    # unfiltered count read them, change the frame count, the gaps and the render times.
    merged = [(ts, event, 1 if screen == 0 else screen, revision, aux) for ts, event, screen, revision, aux in events]
    mixed = by_name(session.analyse_session(merged, state((1, "Name A")), ["Name A"]))["Name A"]
    assert mixed["frames"] > 60 and mixed["gap_ms"]["count"] > row["gap_ms"]["count"]
    assert mixed["quick_render_ms"]["p90"] > row["quick_render_ms"]["p90"]
    # Control: the other screen's frames alone are that window's figures (a 50 ms cadence, failing the hitch rule).
    other = session.run_gaps(events, windows[1]["begin_ns"], windows[1]["end_ns"], screen=0)
    assert other["gap_ms"]["count"] < 60 and other["hitch_verdict"].startswith("fail")


# -- attribution ---------------------------------------------------------------------------------------------------------------

def test_runs_are_attributed_to_the_planned_names_by_what_they_resolved_to_and_startup_runs_are_not_session_runs():
    startup = frames(1, 20, 5)                              # the product's own reveal, before startup ended
    events = trace(startup, frames(2, 200, 20), frames(3, 600, 20), frames(4, 1000, 20), startup_end_ms=150)
    runs = state((1, "Name C"), (2, "Name A"), (3, "Name B"), (4, "Name C"))
    analysis = session.analyse_session(events, runs, NAMES)
    assert [(r["name"], r["run_id"]) for r in analysis["rows"]] == [("Name A", 2), ("Name B", 3), ("Name C", 4)]
    assert analysis["failures"] == []
    # matched by the registry's transition id as well as by the setting name
    by_id = state((2, "Name A"), (3, "Name B"), (4, "Name C"))
    for run in by_id["runs"]:
        run["name"] = None
    renamed = session.analyse_session(events, by_id, ["id_Name A", "id_Name B", "id_Name C"])
    assert [r["run_id"] for r in renamed["rows"]] == [2, 3, 4]


def test_a_session_that_ran_out_of_order_does_not_pass():
    events = trace(frames(5, 200, 20), frames(6, 600, 20), frames(7, 1000, 20))
    runs = state((5, "Name B"), (6, "Name A"), (7, "Name C"))             # the planned order is A, B, C
    analysis = session.analyse_session(events, runs, NAMES)
    rows = by_name(analysis)
    assert rows["Name A"]["status"] == "ok" and rows["Name C"]["status"] == "ok"
    assert rows["Name B"]["status"] == "failed" and "out of order" in rows["Name B"]["reason"]


def _run(run_id, name):
    return SimpleNamespace(run_id=run_id, request=SimpleNamespace(transition_id=name, duration_ms=1000))


def test_the_driver_cycles_the_names_in_a_fixed_order_and_writes_the_type_before_each_change(tmp_path):
    written = []

    class Settings:
        def __init__(self):
            self.value = {"type": "x", "random_always": True}

        def get(self, key):
            return self.value

        def set(self, key, value):
            written.append(value["type"])
            self.value = value

    engine = SimpleNamespace(settings_manager=Settings())
    driver = session.TransitionSessionDriver(NAMES, state_path=tmp_path / "s.json")
    driver.advance(engine)
    driver.record_run(_run(1, "startup_crossfade"))                     # the product's own reveal: no name consumed
    for run_id, expected in enumerate(["Name A", "Name B", "Name C", "Name A", "Name B"], start=2):
        assert driver.advance(engine) == expected
        driver.record_run(_run(run_id, expected))
    assert written == ["Name A", "Name A", "Name B", "Name C", "Name A", "Name B"]
    assert engine.settings_manager.value["random_always"] is False
    assert [c["name"] for c in json.loads((tmp_path / "s.json").read_text())["calls"]] == written
    driver.advance(engine)                                              # a written name whose run never started stays
    assert driver.advance(engine) == "Name C" == written[-1]


def test_the_interval_lets_the_longest_transition_complete_and_settle():
    assert session.session_interval_s([6500, 8000, 7000]) >= 8 + session.SETTLE_S
    assert session.session_seconds(5, 12) == session.STARTUP_LEAD_S + 6 * 12
    assert pack.session_interval(["a", "b"], durations={"a": 3000.0, "b": 9000.0}) == 9 + int(session.SETTLE_S)
    assert pack.session_interval(["unknown"], durations={}) == pack.TRANSITION_INTERVAL_S


# -- the pack: units, command, records, compare --------------------------------------------------------------------------------

def _rows(state_name="idle", transitions=LABELS):
    return pack.enumerate_rows(["2160p"], state_name, modes=["m"], transitions=transitions)


def test_transition_rows_of_a_size_and_state_form_one_session_and_are_never_measured_outside_one():
    rows = _rows()
    units = pack.plan_units(rows)
    assert [kind for kind, _ in units] == ["row", "session"]
    assert [r.ident for r in units[1][1]] == ["a", "b", "c"]                      # the rows' own order is the session's
    # 21 Nov: a lone transition row and --per-row run one-transition sessions (a row process reports the Visualizer's
    # fps and late frames, which a saver without one never has); Visualizer rows stay their own processes.
    assert [(kind, [r.ident for r in p] if kind == "session" else p.ident)
            for kind, p in pack.plan_units(rows[:2])] == [("row", "m"), ("session", ["a"])]
    assert [(kind, [r.ident for r in p] if kind == "session" else p.ident)
            for kind, p in pack.plan_units(rows, per_row=True)] == [
        ("row", "m"), ("session", ["a"]), ("session", ["b"]), ("session", ["c"])]
    assert len(pack.plan_units(_rows("idle") + _rows("loaded"))) == 4              # a session per state


def test_session_command_is_one_invisible_process_on_one_display_with_the_names_in_order():
    rows = [r for r in _rows() if r.kind == "transition"]
    command = pack.session_command(rows, pack.ROOT / "out", interval_s=12)
    assert command[command.index("--mode") + 1] == "none" and "--visible" not in command and "--load" not in command
    assert command[command.index("--transition-session") + 1] == "Name A,Name B,Name C"
    assert command[command.index("--display") + 1] == str(pack.SIZES["2160p"].display) and "--allow-primary" not in command
    settings = dict(pack.session_settings(rows, 12))
    assert settings["timing.interval"] == 12 and settings["transitions.type"] == "Name A"
    assert all(settings[f"transitions.activation.{name}"] is True for name in NAMES)
    loaded = pack.session_command([r for r in _rows("loaded") if r.kind == "transition"], pack.ROOT / "o", interval_s=12)
    assert loaded[loaded.index("--load") + 1] == "game60"


def _session_summary(names=NAMES, failed=()):
    rows = []
    for index, name in enumerate(names):
        if name in failed:
            rows.append({"name": name, "status": "failed", "reason": "no end record (BACKGROUND_RENDER_READY)"})
        else:
            rows.append({"name": name, "status": "ok", "reason": None, "run_id": index + 2, "fps": 60.0, "frames": 400,
                         "window_s": 7.0, "quick_render_ms": {"median": 3.0 + index, "p90": 5.0},
                         "swap_gap_ms": {"median": 16.6, "p90": 18.0}, "late_frames": 2, "hitches": 0,
                         "steady_late_pct": 0.5, "hitches_per_min": 0.0,
                         "process": {"cpu_core_pct": 40.0 + index, "gpu_pct": 20.0, "gpu_ms_per_frame": 3.0,
                                     "rss_mb": 900.0, "private_mb": 1500.0}})
    return {"conditions": {"cpu_others_median": 3.0}, "transition_session": {"rows": rows, "failures": []}}


def _measure(rows, summary, code=0):
    baseline = pack.new_baseline("s", commit="abc", load=None, backend="x")
    calls = []

    def measure_session(group, out):
        calls.append([r.key for r in group])
        return code, summary

    pack.measure_rows(rows, baseline, None, measure=lambda r, o: (0, None), measure_session=measure_session,
                      conditions_fn=dict, displays_fn=lambda: [{"index": 1, "width": 3840, "height": 2160, "primary": False}],
                      out_dir_fn=lambda row, session=False: pack.ROOT / "out", save=lambda *a: None)
    return baseline, calls


def test_a_session_stores_one_ok_row_per_transition_under_the_same_keys_as_a_per_row_run():
    rows = [r for r in _rows() if r.kind == "transition"]
    baseline, calls = _measure(rows, _session_summary(), code=0)
    assert calls == [[r.key for r in rows]]                                           # one process for all three
    assert set(baseline["rows"]) == {r.key for r in rows}
    record = baseline["rows"]["transition/b/2160p/idle"]
    assert record["status"] == "ok" and record["session"] is True
    figures = record["figures"]
    assert figures["fps"] == 60.0 and figures["render_median_ms"] == 4.0 and figures["swap_gap_p90_ms"] == 18.0
    assert figures["cpu_core_pct"] == 41.0 and figures["late_frames"] == 2 and figures["first2s_frames"] is None
    assert figures["render_source"] == "quick_render_ms" and {name for name, _h, _b in pack.METRICS} <= set(figures)
    json.dumps(baseline)
    assert "transition/b/2160p/idle" in pack.baseline_markdown(baseline)


def test_per_row_sessions_write_each_row_to_its_own_folder_and_a_shared_session_to_one():
    rows = [r for r in _rows() if r.kind == "transition"]
    for per_row, expected in ((True, [(r.key, False) for r in rows]), (False, [(rows[0].key, True)])):
        outs = []

        def out_dir(row, session=False):
            outs.append((row.key, session))
            return pack.ROOT / "out"

        baseline = pack.new_baseline("s", commit="abc", load=None, backend="x")
        pack.measure_rows(rows, baseline, None, measure=lambda r, o: (0, None),
                          measure_session=lambda group, out: (0, _session_summary()), conditions_fn=dict,
                          displays_fn=lambda: [{"index": 1, "width": 3840, "height": 2160, "primary": False}],
                          out_dir_fn=out_dir, save=lambda *a: None, per_row=per_row)
        assert outs == expected


def test_a_window_the_session_could_not_close_is_stored_failed_with_its_reason_and_the_others_survive():
    rows = [r for r in _rows() if r.kind == "transition"]
    baseline, _ = _measure(rows, _session_summary(failed={"Name B"}), code=3)          # the live check exits 3 on a failure
    statuses = {r["label"]: r["status"] for r in baseline["rows"].values()}
    assert statuses == {"Name A": "ok", "Name B": "failed", "Name C": "ok"}
    failed = baseline["rows"]["transition/b/2160p/idle"]
    assert failed["figures"] is None and "end record" in failed["failure"]
    dead, _ = _measure(rows, None, code=-9)                                           # no summary at all: all failed
    assert {r["status"] for r in dead["rows"].values()} == {"failed"}
    assert all("exited -9" in r["failure"] for r in dead["rows"].values())


def test_compare_reads_session_rows_like_any_other_row():
    rows = [r for r in _rows() if r.kind == "transition"]
    old, _ = _measure(rows, _session_summary())
    better = _session_summary()
    for item in better["transition_session"]["rows"]:
        item["quick_render_ms"] = {"median": item["quick_render_ms"]["median"] / 2, "p90": 2.0}
    new, _ = _measure(rows, better)
    old["name"], new["name"] = "old", "new"
    report = pack.compare_baselines(old, new)
    assert set(report["rows"]) == {r.key for r in rows} and not report["added"] and not report["removed"]
    assert report["rows"]["transition/a/2160p/idle"]["render_median_ms"]["verdict"] == "better"
    assert report["rows"]["transition/a/2160p/idle"]["render_median_ms"]["gain_pct"] == 50.0
    assert report["rows"]["transition/a/2160p/idle"]["fps"]["verdict"] == "flat"
    assert "transition/c/2160p/idle" in "\n".join(pack.format_compare(report))
    mixed, _ = _measure(rows, _session_summary(failed={"Name A"}), code=3)           # a failed row is "not measured"
    assert pack.compare_baselines(old, mixed)["unmeasured"] == ["transition/a/2160p/idle"]
