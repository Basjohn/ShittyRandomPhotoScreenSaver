"""Qt-free contract for live Settings theme QObject lifetime safety.

PySide Python wrappers may briefly outlive their deleted C++ QObject. A stale
SettingsDialog must be pruned from the root-QSS registry instead of aborting the
transactional Settings-theme activation and preventing native Glass/Acrylic from
committing on the current live dialog.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import types

import pytest


ROOT = Path(__file__).resolve().parents[1]


def _load_settings_theme_module(monkeypatch):
    core_pkg = types.ModuleType("core")
    core_pkg.__path__ = [str(ROOT / "core")]
    monkeypatch.setitem(sys.modules, "core", core_pkg)
    logging_pkg = types.ModuleType("core.logging")
    logging_pkg.__path__ = [str(ROOT / "core" / "logging")]
    monkeypatch.setitem(sys.modules, "core.logging", logging_pkg)
    logger_module = types.ModuleType("core.logging.logger")
    logger_module.get_logger = lambda _name: types.SimpleNamespace(debug=lambda *a, **k: None)
    monkeypatch.setitem(sys.modules, "core.logging.logger", logger_module)

    ui_pkg = types.ModuleType("ui")
    ui_pkg.__path__ = [str(ROOT / "ui")]
    monkeypatch.setitem(sys.modules, "ui", ui_pkg)

    runtime = types.ModuleType("ui.settings_theme_runtime")
    runtime.get_active_settings_theme = lambda: object()
    runtime.subscribe_settings_theme = lambda _listener: (lambda: None)
    monkeypatch.setitem(sys.modules, "ui.settings_theme_runtime", runtime)

    spec_module = types.ModuleType("ui.settings_theme_spec")
    spec_module.SettingsThemeSpec = type("SettingsThemeSpec", (), {})
    monkeypatch.setitem(sys.modules, "ui.settings_theme_spec", spec_module)

    qss = types.ModuleType("ui.settings_theme_qss")
    qss.render_qss_color = lambda _value: "#ffffff"
    qss.render_qss_rgba255 = lambda _value: "rgba(255,255,255,255)"
    monkeypatch.setitem(sys.modules, "ui.settings_theme_qss", qss)

    path = ROOT / "ui" / "settings_theme.py"
    spec = importlib.util.spec_from_file_location("_srpss_settings_theme_lifetime_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _FakeWidget:
    def __init__(self, *, live: bool, raises: bool = False):
        self.live = live
        self.raises = raises
        self.styles: list[str] = []

    def setStyleSheet(self, stylesheet: str) -> None:
        if self.raises:
            raise RuntimeError("live renderer failure")
        self.styles.append(stylesheet)


class _FakeShiboken:
    @staticmethod
    def isValid(widget) -> bool:
        return bool(widget.live)


def test_root_qss_registry_prunes_deleted_pyside_wrappers(monkeypatch) -> None:
    module = _load_settings_theme_module(monkeypatch)
    module.Shiboken = _FakeShiboken
    module._load_base_stylesheet = lambda: "BASE"
    module._build_custom_styles = lambda _theme: "CUSTOM"

    dead = _FakeWidget(live=False, raises=True)
    live = _FakeWidget(live=True)
    module._THEMED_WIDGETS.add(dead)
    module._THEMED_WIDGETS.add(live)

    module._refresh_registered_widgets(types.SimpleNamespace(name="Test"))

    assert live.styles == ["BASECUSTOM"]
    assert dead not in module._THEMED_WIDGETS


def test_live_renderer_runtime_error_still_aborts_transaction(monkeypatch) -> None:
    module = _load_settings_theme_module(monkeypatch)
    module.Shiboken = _FakeShiboken
    module._load_base_stylesheet = lambda: "BASE"
    module._build_custom_styles = lambda _theme: "CUSTOM"

    broken_live = _FakeWidget(live=True, raises=True)
    module._THEMED_WIDGETS.add(broken_live)

    with pytest.raises(RuntimeError, match="live renderer failure"):
        module._refresh_registered_widgets(types.SimpleNamespace(name="Test"))

    assert broken_live in module._THEMED_WIDGETS
