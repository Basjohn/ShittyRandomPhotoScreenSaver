"""Qt-free retirement contract for the legacy Settings base stylesheet.

The physical legacy asset is intentionally outside GODZIP payloads, so this
module proves the production dependency seam instead: live Settings/tray source
must render from permanent structural owners plus SettingsThemeSpec semantics
without loading the old monolithic path.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import types


ROOT = Path(__file__).resolve().parents[1]


def _source(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _load_menu_renderer_without_ui_package_init():
    """Load the Qt-free menu renderer without executing ``ui.__init__``.

    The product ``ui`` package imports generated Qt resources, so normal Python
    package import requires PySide even though the renderer itself does not.
    This helper proves the renderer in the same dependency-starved environment
    used by documentation/authority tests.
    """

    names = (
        "ui",
        "ui.settings_theme_spec",
        "ui.settings_theme_qss",
        "ui.settings_theme_runtime",
        "ui.settings_menu_style",
    )
    old = {name: sys.modules.get(name) for name in names}
    try:
        ui_pkg = types.ModuleType("ui")
        ui_pkg.__path__ = [str(ROOT / "ui")]
        sys.modules["ui"] = ui_pkg

        spec_module = _load_module(
            "ui.settings_theme_spec", ROOT / "ui" / "settings_theme_spec.py"
        )
        _load_module("ui.settings_theme_qss", ROOT / "ui" / "settings_theme_qss.py")

        runtime = types.ModuleType("ui.settings_theme_runtime")
        runtime.get_active_settings_theme = lambda: spec_module.DEFAULT_DARK_SETTINGS_THEME
        sys.modules["ui.settings_theme_runtime"] = runtime

        menu_module = _load_module(
            "ui.settings_menu_style", ROOT / "ui" / "settings_menu_style.py"
        )
        return menu_module, spec_module
    finally:
        for name, previous in old.items():
            if previous is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = previous


def _load_settings_renderer_without_ui_package_init():
    names = (
        "core",
        "core.logging",
        "core.logging.logger",
        "ui",
        "ui.settings_theme_spec",
        "ui.settings_theme_qss",
        "ui.settings_theme_runtime",
        "ui.settings_theme",
    )
    old = {name: sys.modules.get(name) for name in names}
    try:
        core_pkg = types.ModuleType("core")
        core_pkg.__path__ = [str(ROOT / "core")]
        sys.modules["core"] = core_pkg
        logging_pkg = types.ModuleType("core.logging")
        logging_pkg.__path__ = [str(ROOT / "core" / "logging")]
        sys.modules["core.logging"] = logging_pkg
        logger_module = types.ModuleType("core.logging.logger")
        logger_module.get_logger = lambda _name: types.SimpleNamespace(
            debug=lambda *a, **k: None,
            exception=lambda *a, **k: None,
        )
        sys.modules["core.logging.logger"] = logger_module

        ui_pkg = types.ModuleType("ui")
        ui_pkg.__path__ = [str(ROOT / "ui")]
        sys.modules["ui"] = ui_pkg
        spec_module = _load_module(
            "ui.settings_theme_spec", ROOT / "ui" / "settings_theme_spec.py"
        )
        _load_module("ui.settings_theme_qss", ROOT / "ui" / "settings_theme_qss.py")
        runtime = types.ModuleType("ui.settings_theme_runtime")
        runtime.get_active_settings_theme = lambda: spec_module.DEFAULT_DARK_SETTINGS_THEME
        runtime.subscribe_settings_theme = lambda _listener: (lambda: None)
        sys.modules["ui.settings_theme_runtime"] = runtime
        renderer = _load_module("ui.settings_theme", ROOT / "ui" / "settings_theme.py")
        return renderer, spec_module
    finally:
        for name, previous in old.items():
            if previous is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = previous


def test_production_settings_sources_do_not_reference_legacy_dark_qss_path() -> None:
    for relative in (
        "ui/settings_theme.py",
        "ui/settings_menu_style.py",
        "ui/system_tray.py",
        "ui/styled_popup.py",
        "tools/flicker_test.py",
        "tools/godzip_foundry_theme.py",
    ):
        text = _source(relative)
        assert "dark.qss" not in text, relative
        assert "themes/dark.qss" not in text, relative

    settings_theme = _source("ui/settings_theme.py")
    assert "_load_base_stylesheet" not in settings_theme
    assert "_build_settings_root_stylesheet" in settings_theme
    assert "QLabel:disabled" in settings_theme
    assert '"label_disabled_text": _theme_qss_color(theme, "text.disabled")' in settings_theme

    tray = _source("ui/system_tray.py")
    assert "build_tray_menu_stylesheet" in tray


def test_permanent_base_structural_owner_has_no_palette_literals() -> None:
    text = _source("ui/settings_theme.py")
    start = text.index("def _build_base_structural_styles")
    end = text.index("def _build_custom_styles", start)
    structural = text[start:end]

    # The replacement for the monolith may own typography/geometry only. Palette
    # authority remains in SettingsThemeSpec and semantic component renderers.
    assert "rgba(" not in structural
    assert "#" not in structural
    assert "font-family: 'Jost'" in structural
    assert "QCheckBox" in structural
    assert "background: transparent" in structural
    assert "QDialogButtonBox" in structural
    assert "button-layout: 1" in structural
    assert "margin: 10px" in structural


def test_complete_settings_root_renders_without_legacy_file_or_placeholders() -> None:
    renderer, spec_module = _load_settings_renderer_without_ui_package_init()
    theme = spec_module.DEFAULT_DARK_SETTINGS_THEME
    qss = renderer._build_settings_root_stylesheet(theme)

    assert "%(" not in qss
    assert "QDialogButtonBox" in qss
    assert "button-layout: 1" in qss
    assert "QLabel:disabled" in qss
    disabled = theme.color("text.disabled")
    assert f"#{disabled.r:02x}{disabled.g:02x}{disabled.b:02x}" in qss.lower()


def test_tray_menu_structure_is_narrow_and_semantic() -> None:
    menu_module, spec_module = _load_menu_renderer_without_ui_package_init()
    qss = menu_module.build_tray_menu_stylesheet(spec_module.DEFAULT_DARK_SETTINGS_THEME)

    # Preserve the accepted legacy menu geometry while consuming existing
    # semantic context-menu roles rather than a second dark-only palette.
    assert "QMenu {" in qss
    assert "padding: 4px;" in qss
    assert "border-radius: 4px;" in qss
    assert "padding: 6px 25px 6px 20px;" in qss
    assert "height: 1px;" in qss
    assert "margin: 4px 0;" in qss
    assert "rgba(" in qss


def test_color_picker_wrapper_owns_legacy_subsettings_chrome_semantically() -> None:
    text = _source("ui/styled_popup.py")
    assert "def _build_color_picker_wrapper_stylesheet" in text
    assert "self.setStyleSheet(_build_color_picker_wrapper_stylesheet(picker_theme))" in text
    assert '"window.titlebar.surface"' in text
    assert '"color_picker.window_text"' in text
    assert '"chrome.outer_border"' in text
    assert "QDialogButtonBox { button-layout: 1; margin: 0; padding: 0; }" in text

def test_build_and_installer_have_no_legacy_stylesheet_filename_contract() -> None:
    for relative in (
        "scripts/SRPSS_Installer.iss",
        "scripts/SRPSS_MediaCenter_Installer.iss",
        "tools/build_layout.ps1",
        "tools/build_runner.py",
    ):
        assert "dark.qss" not in _source(relative), relative

    build_layout = _source("tools/build_layout.ps1")
    assert "*.srtheme" in build_layout
    assert "*.srwtheme" in build_layout

    # Installers copy the theme directory generically; removing one obsolete
    # file therefore needs no filename-specific installer rewrite.
    assert "themes\\*" in _source("scripts/SRPSS_Installer.iss")

