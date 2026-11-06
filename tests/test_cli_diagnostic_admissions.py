"""CLI admissions that replaced the retired SRPSS_* environment gates.

``--profile-cpu``, ``--mc-window-flags=splash`` and ``--log-dir=<path>`` are parsed once from
argv by ``core/diagnostics/experiment_flags.py``. These tests pin the parse, the mode-detection
strip (so a diagnostic token never becomes the RUN/CONFIG argument), and the two consumers that
used to read the environment: the logger's log root and the Media Center window role.
"""

from __future__ import annotations

import pytest

import main
from core.diagnostics import experiment_flags as ef
from core.logging import logger as logger_mod


@pytest.fixture(autouse=True)
def _reset_active_flags():
    ef.override_active_flags_for_testing(None)
    yield
    ef.override_active_flags_for_testing(None)


def test_new_admissions_default_to_off():
    flags = ef.parse_experiment_flags(["main.py", "/s", "--debug"])
    assert flags.profile_cpu is False
    assert flags.mc_window_splash is False
    assert flags.log_dir is None


def test_new_admissions_parse_from_argv():
    flags = ef.parse_experiment_flags(
        ["main.py", "--profile-cpu", "--mc-window-flags=splash", r"--log-dir=C:\scratch dir\logs", "/s"]
    )
    assert flags.profile_cpu is True
    assert flags.mc_window_splash is True
    assert flags.log_dir == r"C:\scratch dir\logs"


def test_default_window_flags_value_and_empty_log_dir_admit_nothing():
    flags = ef.parse_experiment_flags(["main.py", "--mc-window-flags=default", "--log-dir="])
    assert flags.mc_window_splash is False
    assert flags.log_dir is None


def test_new_admission_tokens_are_stripped_from_mode_detection():
    argv = ["main.py", "--profile-cpu", "--mc-window-flags=splash", "--log-dir=x", "/s"]
    assert set(ef.experiment_flag_tokens(argv)) == {
        "--profile-cpu",
        "--mc-window-flags=splash",
        "--log-dir=x",
    }


def test_parse_screensaver_args_ignores_new_admissions(monkeypatch):
    monkeypatch.setattr(
        main.sys, "argv", ["main.py", "--log-dir=x", "--profile-cpu", "--mc-window-flags=splash", "/c"]
    )
    mode, preview_hwnd = main.parse_screensaver_args()
    assert mode is main.ScreensaverMode.CONFIG
    assert preview_hwnd is None


def test_inactive_admissions_read_disabled_until_startup_activates_them():
    assert ef.profile_cpu_admitted() is False
    assert ef.mc_window_splash_admitted() is False
    ef.activate_experiment_flags(
        ef.parse_experiment_flags(["main.py", "--profile-cpu", "--mc-window-flags=splash"])
    )
    assert ef.profile_cpu_admitted() is True
    assert ef.mc_window_splash_admitted() is True


def test_log_dir_redirect_binds_the_log_root_and_fresh_start_clears_only_it(monkeypatch, tmp_path):
    scratch = tmp_path / "scratch_logs"
    scratch.mkdir()
    (scratch / "screensaver.log").write_text("x", encoding="utf-8")
    default_root = tmp_path / "base"
    (default_root / "logs").mkdir(parents=True)
    (default_root / "logs" / "operator.log").write_text("keep", encoding="utf-8")
    monkeypatch.setattr(logger_mod, "_BASE_DIR", default_root)
    monkeypatch.setattr(logger_mod, "_FORCED_LOG_DIR", None)
    monkeypatch.setattr(logger_mod, "_ACTIVE_LOG_DIR", None)

    logger_mod.set_forced_log_dir(str(scratch))
    resolved, deleted = logger_mod.clear_logs_for_fresh_start()

    assert resolved == scratch
    assert deleted == 1
    assert (default_root / "logs" / "operator.log").is_file()
    assert logger_mod.get_log_dir() == scratch


def test_log_dir_redirect_can_be_cleared(monkeypatch, tmp_path):
    monkeypatch.setattr(logger_mod, "_FORCED_LOG_DIR", tmp_path)
    logger_mod.set_forced_log_dir(None)
    assert logger_mod._FORCED_LOG_DIR is None


def test_log_dir_environment_variable_is_ignored(monkeypatch, tmp_path):
    monkeypatch.setenv("SRPSS_FORCE_LOG_DIR", str(tmp_path / "ignored"))
    monkeypatch.setattr(logger_mod, "_FORCED_LOG_DIR", None)
    monkeypatch.setattr(logger_mod, "_ACTIVE_LOG_DIR", None)
    monkeypatch.setattr(logger_mod, "_BASE_DIR", tmp_path / "base")

    assert logger_mod.get_log_dir() == tmp_path / "base" / "logs"


@pytest.mark.parametrize("splash", [False, True])
def test_mc_window_role_follows_the_cli_admission(monkeypatch, splash):
    from engine.display_manager import DisplayManager
    from rendering.quick.state import QuickWindowRole

    monkeypatch.setattr("core.mc.is_mc_build", lambda: True)
    argv = ["main_mc.py", "/s"] + (["--mc-window-flags=splash"] if splash else [])
    ef.activate_experiment_flags(ef.parse_experiment_flags(argv))
    manager = DisplayManager.__new__(DisplayManager)
    manager.settings_manager = None

    policy = manager._quick_window_policy()

    assert policy.role is (
        QuickWindowRole.MEDIA_CENTER_SPLASH if splash else QuickWindowRole.MEDIA_CENTER_TOOL
    )


def test_mc_window_role_ignores_the_retired_environment_variable(monkeypatch):
    from engine.display_manager import DisplayManager
    from rendering.quick.state import QuickWindowRole

    monkeypatch.setattr("core.mc.is_mc_build", lambda: True)
    monkeypatch.setenv("SRPSS_MC_WINDOW_FLAGS", "splash")
    manager = DisplayManager.__new__(DisplayManager)
    manager.settings_manager = None

    assert manager._quick_window_policy().role is QuickWindowRole.MEDIA_CENTER_TOOL
