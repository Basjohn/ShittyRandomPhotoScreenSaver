"""Guided Setup's last step offers Finish and Finish & Run; both save.

Finish & Run closes Settings asking to run: a running saver or a RUN launch
waiting on Settings resumes by itself on close; a Settings-only (CONFIG) launch
continues into RUN in the same process. No window is shown and no saver runs.
"""
from __future__ import annotations

import ast
from copy import deepcopy
from pathlib import Path

import pytest

from core.settings.default_settings import DEFAULT_SETTINGS

ROOT = Path(__file__).resolve().parents[1]


class _Settings:
    def __init__(self):
        self.values = deepcopy(DEFAULT_SETTINGS)
        self.values["sources"]["folders"] = ["C:/Pictures"]  # TEST INPUT: sources exist
        self.saves = 0

    def get(self, key, default=None):
        value = self.values
        for part in key.split("."):
            if not isinstance(value, dict) or part not in value:
                return deepcopy(default)
            value = value[part]
        return deepcopy(value)

    def set(self, key, value, *args, **kwargs):
        target = self.values
        parts = key.split(".")
        for part in parts[:-1]:
            target = target.setdefault(part, {})
        target[parts[-1]] = deepcopy(value)

    def save(self):
        self.saves += 1


@pytest.mark.usefixtures("qt_app")
@pytest.mark.parametrize("run", [False, True])
def test_the_last_step_offers_both_and_both_save(run) -> None:
    from ui.onboarding.wizard import GuidedSetupPanel

    settings = _Settings()
    panel = GuidedSetupPanel(settings)
    events = []
    panel.finished.connect(lambda completed: events.append(("finished", completed)))
    panel.runRequested.connect(lambda: events.append(("run",)))
    try:
        panel.show_page("sources")
        assert panel.finish_and_run_button.isHidden()  # only on the last step
        panel.show_page("ready")
        assert not panel.finish_and_run_button.isHidden()
        panel.settings.set("widgets.weather.location", "TEST INPUT")
        (panel.finish_and_run_button if run else panel.next).click()
        assert settings.get("widgets.weather.location") == "TEST INPUT"  # saved either way
        assert events == ([("finished", True), ("run",)] if run else [("finished", True)])
    finally:
        panel.deleteLater()


def test_settings_keeps_the_run_request_only_when_it_really_closes() -> None:
    from ui.settings_dialog import SettingsDialog

    class Host:
        run_requested = False

        def __init__(self, closes):
            self._closes = closes

        def close(self):
            return self._closes

    for closes in (True, False):
        host = Host(closes)
        SettingsDialog.request_run_after_close(host)
        assert host.run_requested is closes  # staying at a close prompt drops it


def _main_function(name: str) -> ast.FunctionDef:
    source = (ROOT / "main.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    return next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == name), source


def test_a_settings_only_launch_reports_the_run_request_and_releases_settings() -> None:
    node, source = _main_function("run_config_session")
    events = []

    class Dialog:
        def __init__(self, *_args):
            self.run_requested = True

        def show(self):
            events.append("show")

        def deleteLater(self):
            events.append("deleteLater")

    class App:
        def exec(self):
            return 0

        def sendPostedEvents(self, *_args):
            events.append("deferred deletes")

    class Animations:
        def __init__(self, **_kwargs):
            pass

        def stop(self):
            events.append("animations stopped")

    class _Event:
        class Type:
            DeferredDelete = object()

    namespace = {
        "QApplication": object, "SettingsManager": lambda: object(), "AnimationManager": Animations,
        "_settings_dialog_class": lambda: Dialog, "_message_box_class": lambda: None, "QEvent": _Event,
        "logger": type("L", (), {"info": staticmethod(lambda *a, **k: None),
                                  "debug": staticmethod(lambda *a, **k: None),
                                  "exception": staticmethod(lambda *a, **k: None)})(),
    }
    module = ast.Module(body=[node], type_ignores=[])
    exec(compile(ast.fix_missing_locations(module), "main.py", "exec"), namespace)
    assert namespace["run_config_session"](App()) == (0, True)
    assert events == ["show", "animations stopped", "deleteLater", "deferred deletes"]


def test_a_config_launch_continues_into_run_when_settings_asks() -> None:
    node, source = _main_function("main")
    segment = ast.get_source_segment(source, node) or ""
    config = segment.index("if mode == ScreensaverMode.CONFIG:")
    run = segment.index("if mode == ScreensaverMode.RUN:")
    assert config < run  # CONFIG is decided first, then RUN may follow
    between = segment[config:run]
    assert "run_config_session(app)" in between
    assert "mode = ScreensaverMode.RUN" in between
