"""Launch-intent contract for missing-source onboarding.

Qt is intentionally not imported here: the destination environment owns the
physical dialog test.  These assertions extract the small onboarding helper
from ``main.py`` and execute it against stubs, while source/AST checks protect
RUN vs CONFIG routing without weakening the application's Qt startup contract.
"""
from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT / "main.py"
SOURCE = MAIN.read_text(encoding="utf-8")
TREE = ast.parse(SOURCE)


def _function(name: str) -> ast.FunctionDef:
    for node in TREE.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"missing function {name}")


def _compile_function(name: str, namespace: dict[str, object]):
    node = _function(name)
    module = ast.Module(body=[node], type_ignores=[])
    ast.fix_missing_locations(module)
    code = compile(module, str(MAIN), "exec")
    exec(code, namespace)
    return namespace[name]


def test_missing_source_run_resumes_instead_of_returning_through_config() -> None:
    run_node = _function("run_screensaver")
    segment = ast.get_source_segment(SOURCE, run_node) or ""
    no_source_start = segment.index("if not folders and not rss_feeds:")
    engine_start = segment.index("# Create and start screensaver engine")
    no_source_block = segment[no_source_start:engine_start]

    assert "_run_missing_sources_onboarding(app, settings)" in no_source_block
    assert "return run_config(app)" not in no_source_block
    assert "Sources configured during onboarding; continuing RUN startup" in no_source_block


def test_config_invocations_remain_settings_only() -> None:
    parse_node = _function("parse_screensaver_args")
    segment = ast.get_source_segment(SOURCE, parse_node) or ""

    assert "if arg == '/s':" in segment
    assert "return ScreensaverMode.RUN, None" in segment
    assert "arg.startswith('/c')" in segment
    assert "arg in ('-c', '-s', '--s')" in segment
    assert "return ScreensaverMode.CONFIG, None" in segment


def test_onboarding_reuses_settings_and_restores_quit_policy() -> None:
    events: list[object] = []

    class App:
        def __init__(self) -> None:
            self.quit_policy = True

        def quitOnLastWindowClosed(self) -> bool:
            return self.quit_policy

        def setQuitOnLastWindowClosed(self, value: bool) -> None:
            events.append(("quit_policy", value))
            self.quit_policy = value

    class Settings:
        def __init__(self) -> None:
            self.values = {"sources.folders": [], "sources.rss_feeds": []}

        def get(self, key: str):
            return self.values[key]

    settings = Settings()

    class Dialog:
        def __init__(self, received_settings, animations) -> None:
            events.append(("dialog_settings_same", received_settings is settings))

        def exec(self) -> int:
            settings.values["sources.rss_feeds"] = ["curated"]
            events.append("dialog_exec")
            return 0

    class Animations:
        def __init__(self, *, owner: str) -> None:
            events.append(("animation_owner", owner))

        def stop(self) -> None:
            events.append("animation_stop")

    class Logger:
        def info(self, *args, **kwargs) -> None:
            pass

        def debug(self, *args, **kwargs) -> None:
            pass

        def exception(self, *args, **kwargs) -> None:
            raise AssertionError("unexpected onboarding exception")

    class MessageBox:
        @staticmethod
        def critical(*args, **kwargs) -> None:
            raise AssertionError("unexpected error popup")

    helper = _compile_function(
        "_run_missing_sources_onboarding",
        {
            "QApplication": object,
            "SettingsManager": object,
            "AnimationManager": Animations,
            "SettingsDialog": Dialog,
            "QMessageBox": MessageBox,
            "logger": Logger(),
        },
    )

    app = App()
    assert helper(app, settings) is True
    assert app.quit_policy is True
    assert ("dialog_settings_same", True) in events
    assert events[1] == ("quit_policy", False)
    assert events[-1] == ("quit_policy", True)
    assert "animation_stop" in events


def test_run_startup_settings_are_resolved_after_onboarding() -> None:
    run_node = _function("run_screensaver")
    segment = ast.get_source_segment(SOURCE, run_node) or ""

    onboarding = segment.index("_run_missing_sources_onboarding(app, settings)")
    interaction_read = segment.index("settings.get_bool('input.interaction_mode')")
    assert interaction_read > onboarding
