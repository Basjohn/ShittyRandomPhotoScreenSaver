"""``--only-display <index>``: the RUN-only flag that puts the saver's windows on exactly one display (1B.14).

One owner decides which screens get windows, ``DisplayManager._get_allowed_screen_indices``; the flag replaces the
profile's selection there for the run and nowhere else. Absent, the selection is the profile's own. A malformed value
or an index no screen has refuses RUN startup (``main._resolve_only_display``, exit code 2); a display that is gone
admits nothing, never another display. Fake screens only: nothing here creates a window.
"""
from __future__ import annotations

import inspect

import pytest

import main
from core.diagnostics import experiment_flags as ef
from core.settings import SettingsManager
from core.settings.default_contract import require_canonical_default
from core.settings.display_selection import SELECTION_KEY, enabled_monitor_numbers
from tests._display_manager_doubles import bare_display_manager


@pytest.fixture(autouse=True)
def _reset_active_flags():
    ef.override_active_flags_for_testing(None)
    yield
    ef.override_active_flags_for_testing(None)


def _activate(*argv: str) -> None:
    ef.activate_experiment_flags(ef.parse_experiment_flags(["main.py", *argv]))


# -- the parse ------------------------------------------------------------------------------------------------------

def test_both_forms_parse_and_absent_is_none():
    assert ef.parse_only_display(["main.py", "--only-display", "1", "/s"]) == 1
    assert ef.parse_only_display(["main.py", "--only-display=0", "/s"]) == 0
    assert ef.parse_only_display(["main.py", "/s", "--exit-after", "15"]) is None
    assert ef.parse_experiment_flags(["main.py", "--only-display=2", "/s"]).only_display == 2
    assert ef.parse_experiment_flags(["main.py", "/s"]).only_display is None


@pytest.mark.parametrize("argv", [
    ["main.py", "--only-display"],
    ["main.py", "--only-display", "/s"],
    ["main.py", "--only-display=-1", "/s"],
    ["main.py", "--only-display=x", "/s"],
    ["main.py", "--only-display=1.5", "/s"],
    ["main.py", "--only-display=", "/s"],
    ["main.py", "--only-display=1", "--only-display", "2", "/s"],
])
def test_a_malformed_value_is_refused_strictly_and_admits_nothing(argv):
    with pytest.raises(ValueError):
        ef.parse_only_display(argv)
    with pytest.raises(ValueError):
        main._resolve_only_display(argv, 4)
    # The lenient process admission never turns a malformed value into a display choice.
    assert ef.parse_experiment_flags(argv).only_display is None


def test_the_flag_and_its_value_never_reach_mode_detection(monkeypatch):
    # Without the strip, "--only-display" would be the mode argument (an unknown one: RUN in script mode).
    for argv in (["main.py", "--only-display", "1", "/c"], ["main.py", "--only-display=1", "/c"]):
        monkeypatch.setattr(main.sys, "argv", argv)
        assert main.parse_screensaver_args() == (main.ScreensaverMode.CONFIG, None)
    assert ef.experiment_flag_tokens(["main.py", "--only-display", "1", "/s"]) == ("--only-display", "1")
    assert ef.experiment_flag_tokens(["main.py", "--only-display=1", "/s"]) == ("--only-display=1",)


# -- RUN startup: an index no screen has fails closed ---------------------------------------------------------------

def test_run_startup_checks_the_index_against_the_screens_present():
    assert main._resolve_only_display(["main.py", "/s"], 2) is None
    assert main._resolve_only_display(["main.py", "--only-display", "1", "/s"], 2) == 1
    with pytest.raises(ValueError, match="no such display"):
        main._resolve_only_display(["main.py", "--only-display", "2", "/s"], 2)
    with pytest.raises(ValueError, match="no such display"):
        main._resolve_only_display(["main.py", "--only-display", "0", "/s"], 0)


def test_the_run_branch_refuses_before_the_engine_starts():
    """Structure: ``main()``'s RUN branch resolves the flag against the live screens and refuses with exit code 2
    before ``run_screensaver`` (the engine) can run; CONFIG never reads it."""
    source = inspect.getsource(main.main)
    run_branch = source[source.index("if mode == ScreensaverMode.RUN:"):]
    resolve = run_branch.index("_resolve_only_display(sys.argv, len(app.screens()))")
    assert resolve < run_branch.index("run_screensaver(")
    refusal = run_branch[resolve:run_branch.index("run_screensaver(")]
    assert "exit_code = 2" in refusal
    config_branch = source[source.index("if mode == ScreensaverMode.CONFIG:"):source.index("if mode == ScreensaverMode.RUN:")]
    assert "only_display" not in config_branch


# -- the one owner: DisplayManager's physical selection --------------------------------------------------------------

def _profile(tmp_path, monkeypatch, selection, screens=("serial:one", "serial:two")):
    from core.settings import monitor_routes

    monkeypatch.setattr(monitor_routes, "current_screen_identities", lambda: screens)
    manager = SettingsManager(application="OnlyDisplayTest", storage_base_dir=tmp_path)
    manager.set(SELECTION_KEY, selection)
    return manager


@pytest.mark.usefixtures("qt_app")
def test_the_flag_replaces_the_profiles_selection_with_exactly_that_display(tmp_path, monkeypatch):
    settings = _profile(tmp_path, monkeypatch, [1])            # the profile shows on the first screen only
    manager = bare_display_manager(settings_manager=settings)
    assert manager._get_allowed_screen_indices(2) == {0}      # absent: the profile's selection, unchanged
    _activate("--only-display", "1", "/s")
    assert manager._get_allowed_screen_indices(2) == {1}
    _activate("--only-display", "0", "/s")
    assert manager._get_allowed_screen_indices(2) == {0}


@pytest.mark.usefixtures("qt_app")
def test_a_display_that_is_gone_admits_nothing_never_another(tmp_path, monkeypatch):
    settings = _profile(tmp_path, monkeypatch, "ALL")
    manager = bare_display_manager(settings_manager=settings)
    _activate("--only-display", "1", "/s")
    assert manager._get_allowed_screen_indices(1) == set()
    assert manager._get_allowed_screen_indices(3) == {1}


def test_absent_flag_leaves_the_canonical_selection_alone():
    manager = bare_display_manager(settings_manager=None)
    expected = {number - 1 for number in enabled_monitor_numbers(require_canonical_default(SELECTION_KEY), 3)}
    assert manager._get_allowed_screen_indices(3) == expected
    _activate("/s")
    assert manager._get_allowed_screen_indices(3) == expected


@pytest.mark.parametrize("flag, expected", [(None, None), ("0", [0]), ("1", [1]), ("2", [])])
def test_initialize_displays_creates_a_unit_for_the_chosen_screen_only(monkeypatch, flag, expected):
    import engine.display_manager as module
    from engine.display_manager import DisplayManager
    from tests.test_qtquick_monitor_wake_reconcile import _Screen, _manager

    if flag is not None:
        _activate("--only-display", flag, "/s")
    manager, _app, _scheduler = _manager(monkeypatch, [_Screen("A", 0), _Screen("B", 1920)])
    created: list[int] = []
    monkeypatch.setattr(module, "QuickSceneFactory", lambda **kwargs: object())
    monkeypatch.setattr(DisplayManager, "_create_display_for_screen",
                        lambda self, index, show_immediately=False: created.append(index))
    for name in ("_admit_quick_visualizer", "_prime_quick_startup_desktop_sources", "_prepare_quick_startup_reveal"):
        monkeypatch.setattr(DisplayManager, name, lambda *args: None)
    try:
        manager.initialize_displays()
        if expected is None:            # absent: whatever the canonical selection admits on two screens
            expected = sorted(n - 1 for n in enabled_monitor_numbers(require_canonical_default(SELECTION_KEY), 2))
        assert created == expected
        assert manager.is_selection_suspended() is (not expected)
    finally:
        manager.disconnect_monitor_detection()
        manager._quick_scene_factory = None
