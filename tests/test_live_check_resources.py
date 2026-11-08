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

    class _Manager:
        def __init__(self) -> None:
            controller = SimpleNamespace(mode_id="spectrum", settings_model=SimpleNamespace(mode_activation=None))
            self._quick_visualizer_owner = SimpleNamespace(is_retired=False, controller=controller)
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
