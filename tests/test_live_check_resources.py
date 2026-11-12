"""The live check's gate 4 options: ``--app-arg``, ``--mode-switch`` and ``--resource-readings``.

``--resource-readings`` reads the saver's tree from outside (``tools/live_check_resources.py``); its verdict must flag
a monotonic rise beyond noise and pass a noisy flat series, and its native reader must see a named frame mapping
appear and go. ``--mode-switch`` drives the production cycle gesture one switch at a time
(``tools/live_check_mode_switch.py``); a switch that never completes fails the run.
"""
from __future__ import annotations

import json
import sys
import time
import uuid
from types import SimpleNamespace

import pytest

from tools import live_check_mode_switch as mode_switch
from tools import live_check_resources as resources
from tools import visualizer_live_check as live_check


def test_app_args_admit_only_experiment_flags_and_are_forwarded_with_the_mode_switches(tmp_path):
    args = live_check.build_parser().parse_args(
        ["--mode", "spectrum", "--app-arg=--viz-engine-worker", "--mode-switch", "40,20", "--resource-readings"])
    assert args.app_arg == ["--viz-engine-worker"] and args.mode_switch == [20.0, 40.0]
    command = live_check.runner_command(args, tmp_path, None)
    assert "--app-arg=--viz-engine-worker" in command
    assert command[command.index("--mode-switch") + 1] == "20,40"
    plain = live_check.runner_command(live_check.build_parser().parse_args(["--mode", "spectrum"]), tmp_path, None)
    assert not any(token.startswith(("--app-arg", "--mode-switch")) for token in plain)
    for bad in ("/c", "/s", "--visible", "--log-dir=elsewhere", "--abc-drive", "--viz-engine-worker2"):
        with pytest.raises(ValueError):
            live_check.parse_app_arg(bad)
    assert live_check.parse_app_arg("--abc-drive=B") == "--abc-drive=B"
    for bad in ("0", "-1", "5,5"):
        with pytest.raises(ValueError):
            mode_switch.parse_mode_switch(bad)


def test_the_run_reads_the_saver_path_as_the_saver_resolves_it(windows_platform):
    # The engine worker is the product's default (Windows): a run with no path token measures it, and the in-process
    # control is stated with --app-arg=--viz-in-process (it wins over --viz-engine-worker, as in experiment_flags).
    assert live_check.parse_app_arg(live_check.IN_PROCESS_ARG) == "--viz-in-process"
    assert live_check.engine_worker_path([]) is True
    assert live_check.engine_worker_path(["--viz-switch-telemetry"]) is True
    assert live_check.engine_worker_path([live_check.ENGINE_WORKER_ARG]) is True
    assert live_check.engine_worker_path([live_check.IN_PROCESS_ARG]) is False
    assert live_check.engine_worker_path([live_check.ENGINE_WORKER_ARG, live_check.IN_PROCESS_ARG]) is False


def test_growth_flags_a_monotonic_rise_beyond_noise_and_passes_a_noisy_flat_series():
    flat = [1500, 1512, 1498, 1507, 1503, 1511, 1499, 1505, 1509, 1501, 1504, 1510, 1500, 1506]
    assert resources.growth(flat, 10.0)["growth"] is False
    leaking = [1500 + 15 * i + (3 if i % 2 else -3) for i in range(20)]
    verdict = resources.growth(leaking, 10.0)
    assert verdict["growth"] is True and 14.0 < verdict["slope"] < 16.0
    small = [100 + 0.2 * i for i in range(20)]                   # a fitted rise of 3.8, under the floor of 5
    assert resources.growth(small, 5.0)["growth"] is False
    assert resources.growth([1, 2, 3], 0.0)["growth"] is None    # too few readings to judge


def _reading(wall, kind, index, *, main_handles, engine_pid=None, feeds_pid=None, mappings=1):
    processes = [{"pid": 10, "ppid": 1, "main": True, "worker": False, "handles": main_handles, "threads": 50,
                  "rss_mb": 800.0, "private_mb": 1000.0, "handle_types": {"Section": 380, "File": 420}},
                 {"pid": 20, "ppid": 10, "main": False, "worker": True, "handles": 150, "threads": 6,
                  "rss_mb": 30.0, "private_mb": 20.0}]
    if engine_pid is not None:
        processes.append({"pid": engine_pid, "ppid": 10, "main": False, "worker": True, "handles": 202,
                          "threads": 10, "rss_mb": 75.0, "private_mb": 59.0, "viz_sized_views": 1,
                          "shareable_views": 3})
    if feeds_pid is not None:
        processes.append({"pid": feeds_pid, "ppid": 10, "main": False, "worker": True, "handles": 90, "threads": 4,
                          "rss_mb": 40.0, "private_mb": 30.0})
    return {"wall": wall, "edge": {"kind": kind, "index": index, "wall": wall - 5.0}, "late_s": 0.5,
            "processes": processes, "viz_mappings": [f"srpss_viz_x_{index}"] * mappings}


def _run_folder(tmp_path, readings, roles):
    (tmp_path / "logs").mkdir(parents=True)
    (tmp_path / "logs" / "screensaver.log").write_text(
        "".join(f"2026-11-08 17:00:00 - core.process.supervisor - INFO - Started {role} worker (PID: {pid}), "
                "waiting for ready signal...\n" for pid, role in roles.items()), encoding="utf-8")
    (tmp_path / "resource_readings.json").write_text(json.dumps({"settle_s": 5.0, "readings": readings}),
                                                     encoding="utf-8")
    return resources.analyse_resource_readings(tmp_path, kinds=("settings_reveal",))


def test_the_verdict_judges_the_supervisors_workers_and_flags_handle_growth(tmp_path):
    # One engine worker per cycle, a fresh PID each time (retired at every Settings open), a FEEDS parser child that
    # comes and goes (not the supervisor's: reported, never judged), and main-process handles flat with noise.
    roles = {20: "image", **{100 + i: "visualizer" for i in range(21)}}
    flat = [_reading(1000.0 + 25 * i, "settings_reveal", i, main_handles=1500 + (7 if i % 3 else 0),
                     engine_pid=100 + i, feeds_pid=900 + i if i % 4 == 0 else None) for i in range(21)]
    summary = _run_folder(tmp_path / "flat", flat, roles)
    assert summary["cycles"] == 20                                # the startup reveal is not a cycle
    assert summary["growth"] == [] and summary["exact_not_flat"] == []
    assert summary["distinct_engine_worker_pids"] == 20 and summary["readings_without_one_engine_worker"] == 0
    row = summary["rows"][4]
    assert row["processes"] == 3 and row["other_child_pids"] == [904] and row["engine_worker_pid"] == 104
    # Negative controls: 15 more main-process handles a cycle, and a second mapping left behind from cycle 10 on.
    leaking = [_reading(1000.0 + 25 * i, "settings_reveal", i, main_handles=1500 + 15 * i, engine_pid=100 + i,
                        mappings=1 if i < 10 else 2) for i in range(21)]
    summary = _run_folder(tmp_path / "leaking", leaking, roles)
    assert "handles_main" in summary["growth"] and "handles_tree" in summary["growth"]
    assert summary["exact_not_flat"] == ["viz_mappings"]


def _mode_cycle(tmp_path, private_by_lap, modes=("a", "b", "c", "d")):
    """Mode-switch readings: ``private_by_lap[lap][i]`` is the main process's private MB at ``modes[i]``'s visit."""
    readings = [_reading(900.0, "startup_reveal", 0, main_handles=1500)]
    index = 1
    for lap in private_by_lap:
        for mode, private in zip(modes, lap):
            reading = _reading(900.0 + 10 * index, "mode_switch", index, main_handles=1500)
            reading["edge"]["mode"] = mode
            reading["processes"][0]["private_mb"] = private
            readings.append(reading)
            index += 1
    (tmp_path / "logs").mkdir(parents=True)
    (tmp_path / "logs" / "screensaver.log").write_text("", encoding="utf-8")
    (tmp_path / "resource_readings.json").write_text(json.dumps({"settle_s": 5.0, "readings": readings}),
                                                     encoding="utf-8")
    return resources.analyse_resource_readings(tmp_path, kinds=("mode_switch",))


def test_memory_over_mode_switches_is_judged_per_mode_from_the_second_visit(tmp_path):
    """Native core P2 M5: a mode's first visit precedes the heavier modes' high-water, so the first-to-second step
    is the process settling, not a trend (the series across modes read it as growth, on both process paths)."""
    modes = tuple("abcdefghi")
    # Measured, the main process's private MB over nine modes (in process, 11 Nov 2026): two laps of one run, three
    # of another. Measurements of a run, not settings.
    two_laps = [[1041.2, 1031.9, 1015.9, 1140.4, 1142.8, 1212.8, 1334.6, 1421.5, 1195.7],
                [1210.3, 1185.5, 1164.2, 1268.6, 1282.3, 1317.9, 1385.7, 1420.2, 1176.6]]
    three_laps = [[1038.4, 1032.3, 1012.6, 1116.2, 1237.2, 1203.9, 1339.1, 1472.4, 1378.5],
                  [1215.6, 1173.1, 1157.0, 1253.6, 1374.0, 1312.4, 1400.5, 1426.1, 1373.0],
                  [1210.2, 1175.9, 1147.5, 1243.7, 1364.8, 1305.5, 1411.5, 1457.7, 1376.7]]

    # Two laps: the series across modes reads growth (what the gate reported); per mode there is only the first
    # step, which is reported and not judged.
    summary = _mode_cycle(tmp_path / "two", two_laps, modes)
    verdict = summary["metrics"]["private_main_mb"]
    assert verdict["series_growth"] is True
    assert verdict["by_mode"]["first_step_median"] > 50.0 and verdict["by_mode"]["later_steps"] == 0
    assert verdict["growth"] is None and "private_main_mb" not in summary["growth"]

    # Three laps: flat from the second visit on.
    summary = _mode_cycle(tmp_path / "flat", three_laps, modes)
    verdict = summary["metrics"]["private_main_mb"]
    assert verdict["by_mode"]["later_steps"] == len(modes) and abs(verdict["by_mode"]["later_step_median"]) < 10.0
    assert verdict["growth"] is False and "private_main_mb" not in summary["growth"]

    # Negative control: every mode 40 MB higher on every later visit.
    leaking = three_laps[:2] + [[value + 40.0 * lap for value in three_laps[1]] for lap in (1, 2, 3)]
    summary = _mode_cycle(tmp_path / "leak", leaking, modes)
    assert summary["metrics"]["private_main_mb"]["growth"] is True and "private_main_mb" in summary["growth"]

    # Settings round trips have no mode: their memory stays one series.
    roles = {20: "image"}
    reveals = [_reading(1000.0 + 25 * i, "settings_reveal", i, main_handles=1500) for i in range(8)]
    assert "by_mode" not in _run_folder(tmp_path / "reveals", reveals, roles)["metrics"]["private_main_mb"]


def test_a_memory_map_file_never_names_an_alternate_data_stream():
    from tools.live_check_settings_roundtrip import memory_map_file_name

    names = [memory_map_file_name(index) for index in ("switch0:oscilloscope", "switch1:bubble", 3, "reveal 2")]
    assert len(set(names)) == len(names)
    assert all(":" not in name and " " not in name and name.endswith(".json") for name in names)


def test_recorded_edges_are_the_reveals_and_completed_mode_switches(tmp_path):
    (tmp_path / "settings_roundtrip.json").write_text(json.dumps({"events": [
        {"event": "armed", "wall": 1.0}, {"event": "reveal", "wall": 2.0, "generation": 0},
        {"event": "reveal", "wall": 30.0, "generation": 1}]}), encoding="utf-8")
    (tmp_path / "mode_switch.json").write_text(json.dumps({"events": [{"event": "reveal", "wall": 3.0}], "switches": [
        {"index": 0, "completed": True, "completed_wall": 40.0, "completed_mode": "bubble"},
        {"index": 1, "completed": False}]}), encoding="utf-8")
    edges = resources.recorded_edges(tmp_path)
    assert [(e["kind"], e["index"], e["wall"]) for e in edges] == [
        ("settings_reveal", 0, 2.0), ("settings_reveal", 1, 30.0), ("startup_reveal", 0, 3.0),
        ("mode_switch", 1, 40.0)]
    (tmp_path / "mode_switch.json").write_text("{ half written", encoding="utf-8")   # mid-rewrite: next tick
    assert [e["kind"] for e in resources.recorded_edges(tmp_path)] == ["settings_reveal", "settings_reveal"]


@pytest.mark.skipif(sys.platform != "win32", reason="Windows object namespace")
def test_the_native_reader_sees_a_frame_mapping_appear_and_go():
    from multiprocessing.shared_memory import SharedMemory

    reader = resources.NativeReader()
    assert reader.type_names, "the object type table did not verify against a section this process created"
    import os

    name = f"{resources.VIZ_MAPPING_PREFIX}test_{uuid.uuid4().hex[:8]}_1"
    before_views = reader.section_views(os.getpid())["viz_sized_views"]
    before_sections = reader.handle_types(os.getpid()).get("Section", 0)
    memory = SharedMemory(name=name, create=True, size=64 + 3 * (1 << 20))
    try:
        assert (name, "Section") in reader.named_objects(resources.VIZ_MAPPING_PREFIX)
        assert reader.section_views(os.getpid())["viz_sized_views"] == before_views + 1
        assert reader.handle_types(os.getpid()).get("Section", 0) == before_sections + 1
    finally:
        memory.close()
        memory.unlink()
    assert (name, "Section") not in reader.named_objects(resources.VIZ_MAPPING_PREFIX)
    assert reader.section_views(os.getpid())["viz_sized_views"] == before_views


def _fake_engine_classes(*, completes: bool):
    from PySide6.QtCore import QObject, QTimer

    from rendering.quick.visualizer.double_click_admission import next_visualizer_mode_id
    from tests._display_manager_doubles import visualizer_owner_double

    # The manager stays its own class on purpose: it models the timed mode cycle the live check drives (a cycle
    # that completes later or never), which a bare DisplayManager cannot do without a running display.
    class _Manager:
        def __init__(self) -> None:
            controller = SimpleNamespace(mode_id="spectrum", settings_model=SimpleNamespace(mode_activation=None))
            self._quick_visualizer_owner = visualizer_owner_double(controller)
            self.cycles = 0

        def _cycle_quick_visualizer_mode(self) -> None:
            self.cycles += 1
            target = next_visualizer_mode_id(self._quick_visualizer_owner.controller.mode_id, None)
            if completes:
                QTimer.singleShot(20, lambda: self._presented(target))

        def _presented(self, mode: str) -> None:
            self._quick_visualizer_owner.controller.mode_id = mode
            self._complete_quick_visualizer_mode_change(mode)

        def _complete_quick_visualizer_mode_change(self, mode_id: str) -> None:
            return None

    class _Engine(QObject):
        def __init__(self) -> None:
            super().__init__()
            self._runtime_generation = 1
            self._settings_dialog_active = False
            self.display_manager = _Manager()

        def initialize(self) -> bool:
            return True

        def stop(self, *, reason=None) -> None:
            return None

        def _freeze_revealed_generation(self) -> bool:
            return True

        def _get_state(self):
            return SimpleNamespace(name="RUNNING")

    return _Engine, _Manager


@pytest.mark.qt
def test_mode_switches_run_one_at_a_time_through_the_cycle_gesture_and_record_each_completion(
        qt_app, qtbot, monkeypatch, tmp_path):
    from rendering.quick.visualizer.double_click_admission import next_visualizer_mode_id

    engine_class, manager_class = _fake_engine_classes(completes=True)
    driver = mode_switch.ModeSwitchDriver([0.05, 0.06, 0.07], began=time.monotonic(),
                                          state_path=tmp_path / "mode_switch.json", timeout_ms=5000)
    driver.install(engine_class=engine_class, manager_class=manager_class, patch=monkeypatch.setattr)
    engine = engine_class()
    assert engine.initialize()
    engine._freeze_revealed_generation()                       # the generation revealed: switches are admitted
    qtbot.waitUntil(lambda: sum(1 for s in driver.switches if s.get("completed")) == 3, timeout=10000)
    expected = "spectrum"
    for record in driver.switches:                            # each fired only after the previous one completed
        assert record["from_mode"] == expected
        expected = next_visualizer_mode_id(expected, None)
        assert record["completed_mode"] == record["expected_mode"] == expected
        assert record["completed_wall"] >= record["fired_wall"]
    assert engine.display_manager.cycles == 3
    engine.stop(reason="cli_exit_after")
    summary = mode_switch.analyse_mode_switches(json.loads((tmp_path / "mode_switch.json").read_text("utf-8")),
                                                times=[0.05, 0.06, 0.07], returncode=0)
    assert summary["failures"] == []
    assert [e["kind"] for e in resources.recorded_edges(tmp_path)] == ["startup_reveal", *["mode_switch"] * 3]


@pytest.mark.qt
def test_memory_classification_runs_at_each_completed_switch_when_asked(qt_app, qtbot, monkeypatch, tmp_path):
    # --roundtrip-memory with --mode-switch alone: R-175's probe observes after each completion; forwarded only then.
    args = live_check.build_parser().parse_args(
        ["--mode", "spectrum", "--mode-switch", "30", "--roundtrip-memory", "collect"])
    command = live_check.runner_command(args, tmp_path, None)
    assert command[command.index("--roundtrip-memory") + 1] == "census,collect"
    alone = live_check.build_parser().parse_args(["--mode", "spectrum", "--roundtrip-memory", "collect"])
    assert "--roundtrip-memory" not in live_check.runner_command(alone, tmp_path, None)

    observed = []
    probe = SimpleNamespace(observe=lambda engine, *, index: observed.append((engine, index)))
    engine_class, manager_class = _fake_engine_classes(completes=True)
    driver = mode_switch.ModeSwitchDriver([0.05, 0.06], began=time.monotonic(), timeout_ms=5000, memory_probe=probe)
    driver.install(engine_class=engine_class, manager_class=manager_class, patch=monkeypatch.setattr)
    engine = engine_class()
    engine.initialize()
    engine._freeze_revealed_generation()
    qtbot.waitUntil(lambda: sum(1 for s in driver.switches if s.get("completed")) == 2, timeout=10000)
    assert [index for _engine, index in observed] == [
        f"switch{s['index']}:{s['completed_mode']}" for s in driver.switches]
    assert all(seen is engine for seen, _index in observed)


@pytest.mark.qt
def test_a_mode_switch_that_never_completes_fails_the_run(qt_app, qtbot, monkeypatch, tmp_path):
    engine_class, manager_class = _fake_engine_classes(completes=False)
    driver = mode_switch.ModeSwitchDriver([0.05], began=time.monotonic(), timeout_ms=100)
    driver.install(engine_class=engine_class, manager_class=manager_class, patch=monkeypatch.setattr)
    engine = engine_class()
    engine.initialize()
    engine._freeze_revealed_generation()
    qtbot.waitUntil(lambda: bool(driver.switches and driver.switches[0].get("timed_out")), timeout=5000)
    engine.stop(reason="cli_exit_after")
    summary = mode_switch.analyse_mode_switches(driver.state(), times=[0.05], returncode=0)
    record = driver.switches[0]
    assert summary["failures"] == [
        f"mode switch 0 ({record['from_mode']} -> {record['expected_mode']}) never completed"]
