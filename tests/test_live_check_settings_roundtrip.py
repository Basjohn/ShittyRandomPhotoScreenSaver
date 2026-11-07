"""The live check's ``--settings-roundtrip`` option: parsing, forwarding, the runner's patches and the verdict.

The round trip below is the engine's real Settings path (``on_settings_requested``: the real stop, the strict display
barrier, the real ``SettingsDialog`` with its own barrier, the replacement up to its reveal) driven by the runner's
driver, with a QObject stand-in for ``DisplayManager`` (as ``tests/test_application_services.py``). The dialog is never
shown: the driver's own ``exec`` replacement is what closes it.
"""
from __future__ import annotations

import time
import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest
from PySide6.QtCore import QCoreApplication, QEvent, QObject, Signal

from tools import live_check_settings_roundtrip as roundtrip
from tools import visualizer_live_check as live_check


def test_option_parses_sorted_positive_times_and_is_forwarded_to_the_runner(tmp_path):
    args = live_check.build_parser().parse_args(["--mode", "bubble", "--settings-roundtrip", "25,10"])
    assert args.settings_roundtrip == [10.0, 25.0]
    command = live_check.runner_command(args, tmp_path, None)
    assert command[command.index("--settings-roundtrip") + 1] == "10,25"
    assert "--runner" in command
    plain = live_check.build_parser().parse_args(["--mode", "bubble"])
    assert plain.settings_roundtrip is None
    assert "--settings-roundtrip" not in live_check.runner_command(plain, tmp_path, None)
    for bad in ("0", "-3", "x", "10,10", "nan", "inf"):
        with pytest.raises(ValueError):
            roundtrip.parse_settings_roundtrip(bad)


class _GCPolicy:
    """The RuntimeGCPolicy surface the engine calls at reveal and teardown."""

    def __init__(self, *, refreeze: bool = True) -> None:
        self.frozen = False
        self.refreeze = refreeze
        self.freezes = 0

    def freeze_stable_generation(self) -> bool:
        if self.frozen or (self.freezes and not self.refreeze):
            return False
        self.frozen = True
        self.freezes += 1
        return True

    def thaw_for_runtime_retirement(self) -> bool:
        was, self.frozen = self.frozen, False
        return was


def _fake_display_manager_class():
    class _FakeDisplayManager(QObject):
        exit_requested = Signal()
        monitors_changed = Signal(int)
        displays_ready = Signal(int)
        authoritative_first_frames_ready = Signal(int)
        startup_reveal_completed = Signal(int)
        transition_completed = Signal(int)
        transition_batch_idle = Signal()
        previous_requested = Signal()
        next_requested = Signal()
        save_image_requested = Signal(int)
        ban_image_requested = Signal(int)
        clear_image_bans_requested = Signal()
        cycle_transition_requested = Signal()
        settings_requested = Signal()
        settings_target_requested = Signal(str)
        custom_layout_reload_requested = Signal(str, int, object)
        jedi_mode_requested = Signal(str, str)

        def __init__(self, *, runtime_generation, **_kwargs):
            super().__init__()
            self._runtime_generation = runtime_generation

        def set_random_transition_selection(self, _selection) -> None:
            return None

        def initialize_displays(self) -> int:
            return 1

        def get_display_count(self) -> int:
            return 1

        def collect_runtime_retirement_roots(self):
            return [self], []

        def cleanup(self) -> None:
            return None

        def retire_runtime(self) -> None:
            self.deleteLater()

    return _FakeDisplayManager


@pytest.mark.qt
@pytest.mark.parametrize("refreeze", [True, False])
def test_runner_drives_the_real_settings_path_invisibly_and_records_the_lifecycle(
    monkeypatch, qt_app, qtbot, tmp_path, refreeze,
):
    from core.settings import SettingsManager
    from engine import engine_handlers, runtime_destruction
    from engine.screensaver_engine import EngineState, ScreensaverEngine
    from ui.settings_dialog import SettingsDialog
    from ui.styled_popup import StyledPopup

    engine = ScreensaverEngine()
    engine.settings_manager = SettingsManager(
        organization="Test", application=f"LiveRoundTrip_{uuid.uuid4().hex}", storage_base_dir=tmp_path,
    )
    engine._gc_policy = _GCPolicy(refreeze=refreeze)

    def _start(*, show_first_image=True):
        engine._transition_state(EngineState.RUNNING)
        engine._freeze_revealed_generation()     # the coordinated reveal's freeze edge
        return True

    monkeypatch.setattr("engine.screensaver_engine.DisplayManager", _fake_display_manager_class())
    monkeypatch.setattr(engine, "_initialize_image_sources", lambda: True)
    monkeypatch.setattr(engine, "_start_rss_background_refresh_if_needed", lambda: None)
    monkeypatch.setattr(engine, "_setup_rotation_timer", lambda: None)
    monkeypatch.setattr(engine, "_arm_replacement_watchdog", lambda label=None: None)
    monkeypatch.setattr(engine, "start", _start)
    monkeypatch.setattr(engine_handlers, "log_lifecycle_resource_snapshot", lambda *_a, **_k: None)
    monkeypatch.setattr(engine_handlers, "suppress_runtime_pointer_input", lambda *_a, **_k: None)
    original_exec = SettingsDialog.__dict__.get("exec")

    driver = roundtrip.SettingsRoundTripDriver(
        [0.05], began=time.monotonic(), state_path=tmp_path / "settings_roundtrip.json", dwell_ms=50,
    )
    driver.install(engine_class=ScreensaverEngine, policy_class=_GCPolicy,
                   barrier_class=runtime_destruction.RuntimeDestructionBarrier, patch=monkeypatch.setattr)

    assert engine._initialize_display()
    _start()
    driver.attach(engine)

    def _done() -> None:
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        assert driver.round_trips and driver.round_trips[0].get("completed")
        assert engine._get_state() is EngineState.RUNNING and not engine._settings_dialog_active

    qtbot.waitUntil(_done, timeout=20000)

    # The runner's patches: the real dialog class's exec dwelled and closed it unseen; popups are answered unseen.
    assert SettingsDialog.exec is not original_exec
    assert SettingsDialog.exec.settings_roundtrip_driver is driver
    assert StyledPopup.exec.settings_roundtrip_driver is driver
    record = driver.round_trips[0]
    assert str(record["dialog_generation"]).startswith("settings-dialog:")
    assert record["dialog_visible"] is False and record["popups"] == []
    assert record["dialog_exec_ms"] >= 45.0
    # The real lifecycle edges: the settings stop, both strict barriers, the generation step, the thaw and re-freeze.
    assert record["stop_ms"] is not None
    assert [(b["reason"], b["outcome"]) for b in record["barriers"]] == [
        ("settings", "complete"), ("settings_dialog_close", "complete"),
    ]
    assert record["generation_after"] > record["generation_before"]
    assert record["thawed"] is True and record["refrozen"] is refreeze
    assert record["memory_before"]["rss_mb"] > 0 and record["memory_after"]["private_mb"] > 0

    # The verdict: the run fails exactly when the replacement did not re-freeze.
    driver._event("exit_after_stop")
    summary = roundtrip.analyse_settings_roundtrips(driver.state(), times=[0.05], returncode=0)
    if refreeze:
        assert summary["failures"] == []
    else:
        assert summary["failures"] == ["round trip 0: the replacement revealed without a GC re-freeze"]


@pytest.mark.qt
def test_a_round_trip_due_before_the_generation_revealed_waits_for_its_reveal(monkeypatch, qt_app, qtbot):
    from engine import engine_handlers

    class _Engine(QObject):
        _runtime_generation = 0
        _settings_dialog_active = False
        _pending_runtime_destruction_barrier = None

        def _get_state(self):
            return SimpleNamespace(name="RUNNING")

    requests: list = []
    monkeypatch.setattr(engine_handlers, "on_settings_requested", lambda engine: requests.append(engine))
    engine = _Engine()
    driver = roundtrip.SettingsRoundTripDriver([1.0], began=time.monotonic(), memory=lambda: {})
    driver._dialog_patched = True
    driver._engine_ref = lambda: engine

    driver.fire(0)                       # RUNNING, but the startup generation has not revealed yet
    assert requests == [] and [e["event"] for e in driver.events] == ["deferred"]

    driver._on_reveal(engine, True)      # its reveal admits the waiting round trip
    qtbot.waitUntil(lambda: requests == [engine], timeout=2000)
    assert driver.round_trips[0]["generation_before"] == 0


def _state(**record_overrides) -> dict:
    record = {"index": 0, "fired_at": 10.0, "stop_ms": 40.0, "dialog_generation": "settings-dialog:1:2",
              "dialog_exec_ms": 1500.0, "generation_before": 1, "generation_after": 3, "thawed": True,
              "refrozen": True, "completed": True, "total_ms": 3000.0, "popups": [], "dialog_visible": False,
              "barriers": [{"outcome": "complete", "reason": "settings", "retiring_generation": "1",
                            "elapsed_ms": 200.0}],
              "memory_before": {"rss_mb": 500.0, "private_mb": 600.0},
              "memory_after": {"rss_mb": 510.0, "private_mb": 605.0}}
    record.update(record_overrides)
    return {"round_trips": [record], "events": [{"event": "exit_after_stop", "at": 40.0}]}


def test_verdict_fails_on_a_barrier_timeout_a_missing_refreeze_or_an_early_exit():
    clean = roundtrip.analyse_settings_roundtrips(_state(), times=[10.0], returncode=0)
    assert clean["failures"] == []
    assert clean["round_trips"][0]["rss_mb"] == (500.0, 510.0)

    timeout = _state(barriers=[{"outcome": "timeout", "reason": "settings", "retiring_generation": "1",
                                "elapsed_ms": 30000.0}], completed=False)
    timeout["events"].insert(0, {"event": "barrier", "outcome": "timeout", "reason": "settings",
                                 "retiring_generation": "1", "elapsed_ms": 30000.0, "at": 40.0})
    failures = roundtrip.analyse_settings_roundtrips(timeout, times=[10.0], returncode=1)["failures"]
    assert any("barrier timeout reason=settings" in f for f in failures)
    assert any("exited with code 1" in f for f in failures)
    assert not any("outside a round trip" in f for f in failures)

    assert roundtrip.analyse_settings_roundtrips(_state(refrozen=False), times=[10.0], returncode=0)["failures"] == [
        "round trip 0: the replacement revealed without a GC re-freeze"]

    early = _state()
    early["events"] = []
    assert roundtrip.analyse_settings_roundtrips(early, times=[10.0], returncode=0)["failures"] == [
        "the process ended without the --exit-after terminal stop (a process exit during the run)"]

    missing = roundtrip.analyse_settings_roundtrips(_state(), times=[10.0, 25.0], returncode=0)["failures"]
    assert missing == ["round trip 1 at 25s never started (the process ended or never re-admitted it)"]

    logged = roundtrip.analyse_settings_roundtrips(
        _state(), times=[10.0], returncode=0,
        gc_lines=["[GC_POLICY] Froze 1 stable objects", "[GC_POLICY] Thawed the revealed generation"])
    assert logged["failures"] == ["the log shows 1 GC freezes for 2 reveals"]


def test_gc_policy_lines_include_the_rotated_main_log_oldest_first(tmp_path):
    """A long or heavily logged run rotates screensaver.log; its freezes must still count (7 Nov: a false
    "0 GC freezes for 10 reveals")."""
    (tmp_path / "screensaver.log.2").write_text("a [GC_POLICY] Froze 1 stable objects\n", encoding="utf-8")
    (tmp_path / "screensaver.log.1").write_text("b [GC_POLICY] Froze 2 stable objects\n", encoding="utf-8")
    (tmp_path / "screensaver.log").write_text("c [GC_POLICY] Thawed the revealed generation\n", encoding="utf-8")
    (tmp_path / "screensaver_frame_trace.bin").write_bytes(b"[GC_POLICY] Froze 9")
    assert roundtrip.gc_policy_lines(tmp_path) == [
        "a [GC_POLICY] Froze 1 stable objects", "b [GC_POLICY] Froze 2 stable objects",
        "c [GC_POLICY] Thawed the revealed generation"]


def test_memory_classification_is_opt_in_and_forwarded_only_with_round_trips(tmp_path):
    assert roundtrip.parse_roundtrip_memory("collect") == ("census", "collect")
    assert roundtrip.parse_roundtrip_memory("map,census,tracemalloc") == ("census", "tracemalloc", "map")
    for bad in ("", "census,sweep"):
        with pytest.raises(ValueError):
            roundtrip.parse_roundtrip_memory(bad)
    args = live_check.build_parser().parse_args(
        ["--mode", "bubble", "--settings-roundtrip", "10", "--roundtrip-memory", "collect"])
    command = live_check.runner_command(args, tmp_path, None)
    assert command[command.index("--roundtrip-memory") + 1] == "census,collect"
    plain = live_check.build_parser().parse_args(["--mode", "bubble", "--settings-roundtrip", "10"])
    assert plain.roundtrip_memory == () and "--roundtrip-memory" not in live_check.runner_command(plain, tmp_path, None)
    driver = roundtrip.SettingsRoundTripDriver([1.0], began=time.monotonic(), memory=lambda: {})
    assert driver.memory_probe is None                     # without the option nothing observes a reveal


@pytest.mark.qt
def test_memory_probe_names_a_retired_generation_kept_by_a_cycle_and_what_a_collection_frees(qt_app, tmp_path):
    import gc

    class _Cycle(QObject):
        def __init__(self):
            super().__init__()
            self.me = self

    class _Manager:
        def __init__(self, roots):
            self.roots = roots

        def collect_runtime_retirement_roots(self):
            return list(self.roots), []

    memory = iter([{"rss_mb": float(v), "private_mb": float(v)} for v in range(100, 200)])
    probe = roundtrip.RoundTripMemoryProbe(("census", "collect"), out_dir=tmp_path)
    retired = _Cycle()
    engine = SimpleNamespace(_runtime_generation=0, display_manager=_Manager([retired]))
    was_enabled = gc.isenabled()
    gc.disable()
    try:
        probe.observe(engine, index="startup", memory=lambda: next(memory))
        retired.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)     # its C++ object is gone ...
        del retired                                                             # ... its wrapper stays in a cycle
        engine._runtime_generation, engine.display_manager = 1, _Manager([])
        row = probe.observe(engine, index=0, memory=lambda: next(memory))
    finally:
        if was_enabled:
            gc.enable()
    survivors = row["retired_survivors"]["display:0"]
    assert survivors["qobject_wrappers_alive"] == {"_Cycle": 1} and survivors["native_total"] == 0
    assert row["collect"]["garbage_qobjects"] == {"_Cycle": 1} and row["collect"]["unreachable"] >= 1
    assert "delta" in row and (tmp_path / "settings_roundtrip_memory.json").exists()
    assert probe._survivors("display:1") == {}                                  # the collection freed it
