"""Qt-free source contracts for Widget-theme link identity and static assets.

Runtime/visual behavior still requires the normal PySide6 user-environment gate.
These checks preserve two packaging/ownership facts that are easy to conflate:
Qt resources own Settings-UI embedded assets, while runtime widget imagery remains
raw ``images/`` data that Nuitka must package separately.
"""
from __future__ import annotations

from pathlib import Path
import importlib.util


ROOT = Path(__file__).resolve().parents[1]


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_link_toggle_persists_current_paired_widget_identity() -> None:
    source = _text(ROOT / "ui" / "tabs" / "themes_tab.py")
    assert "selected_id=linked" in source
    assert "selected_id=linked_id" in source
    assert "persist=True" in source
    assert "unlinking later freezes" in source


def test_settings_qrc_and_raw_widget_images_remain_distinct_asset_paths() -> None:
    qrc = _text(ROOT / "ui" / "resources" / "assets.qrc")
    styles = _text(ROOT / "ui" / "tabs" / "shared_styles.py")
    ui_init = _text(ROOT / "ui" / "__init__.py")

    # QRC is the embedded Settings-UI lane: fonts + small QSS icons.
    assert '<qresource prefix="/ui/assets">' in qrc
    assert "fonts/Jost-Regular.ttf" in qrc
    assert "combobox_closed.svg" in qrc
    assert ":/ui/assets/fonts/Jost-Regular.ttf" in styles
    assert ":/ui/assets/circle_checkbox_unchecked.svg" in styles
    assert "assets_rc" in ui_init

    # Runtime branded/widget imagery deliberately stays on the raw images lane.
    achievement = _text(ROOT / "rendering" / "quick" / "widgets" / "achievement_pulse.py")
    abandonment = _text(ROOT / "rendering" / "quick" / "widgets" / "abandonment_issues.py")
    assert '"images" / "Steam_Logo_Cropped.png"' in achievement
    assert '"images" / "Steam_Logo_Cropped.png"' in abandonment
    assert ".resolve().as_uri()" in achievement
    assert "Steam_Logo_Cropped.png" not in qrc

    # Frozen builds must therefore keep shipping the raw images directory.
    for script_name in ("build_nuitka.ps1", "build_nuitka_mc_onedir.ps1"):
        script = _text(ROOT / "scripts" / script_name)
        assert '"--include-data-dir=images=images"' in script, script_name
        assert '"--include-data-dir=themes=themes"' in script, script_name


def test_generated_widget_themes_only_serialize_admitted_semantic_roles() -> None:
    roles_source = _text(ROOT / "ui" / "widget_visual_roles.py")
    # The generated pack is intentionally sparse: it may define shared roles that
    # some consumers have not adopted yet, but it must never serialize local.*
    # presentation terminals or invent per-family persistence vocabulary.
    assert '"header.fill": "local.header.fill"' in roles_source

    for theme_path in (ROOT / "themes" / "widgets").glob("*.srwtheme"):
        payload = theme_path.read_text(encoding="utf-8")
        assert '"local.' not in payload, theme_path.name


def test_lazy_theme_pages_refresh_without_polling_or_cross_tab_theme_owner() -> None:
    widgets = _text(ROOT / "ui" / "tabs" / "widgets_tab_defaults.py")
    themes = _text(ROOT / "ui" / "tabs" / "themes_tab.py")

    # Already-built General swatches follow the process-local publication event.
    assert "subscribe_widget_theme" in widgets
    assert "_widget_theme_controls_unsubscribe" in widgets
    assert "tab.destroyed.connect(_unsubscribe)" in widgets

    # The Widget Themes page refreshes persisted Custom/link state on navigation,
    # rather than maintaining another recurring Settings/theme watcher.
    assert "_refresh_widget_theme_page_from_state" in themes
    assert "if page_index == _WIDGET_THEMES_PAGE" in themes
    assert "state.custom_payload is not None" in themes
    assert "QTimer" not in themes


def test_frozen_theme_root_uses_same_programdata_srpss_asset_root_as_presets(monkeypatch, tmp_path) -> None:
    path = ROOT / "ui" / "settings_theme_paths.py"
    spec = importlib.util.spec_from_file_location("_srpss_settings_theme_paths_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    program_data = tmp_path / "ProgramData"
    monkeypatch.setenv("PROGRAMDATA", str(program_data))
    monkeypatch.setattr(module, "_is_frozen_runtime", lambda: True)
    assert module.resolve_settings_themes_directory() == program_data / "SRPSS" / "themes"

    explicit = tmp_path / "explicit-themes"
    assert module.resolve_settings_themes_directory(explicit) == explicit

    monkeypatch.setattr(module, "_is_frozen_runtime", lambda: False)
    assert module.resolve_settings_themes_directory() == ROOT / "themes"

    widget_paths = _text(ROOT / "ui" / "widget_theme_paths.py")
    assert 'resolve_settings_themes_directory(themes_root) / "widgets"' in widget_paths


def test_installers_seed_and_clean_replace_programdata_theme_tree() -> None:
    normal = _text(ROOT / "scripts" / "SRPSS_Installer.iss")
    media_center = _text(ROOT / "scripts" / "SRPSS_MediaCenter_Installer.iss")

    assert 'Source: ".\\..\\themes\\*"; DestDir: "{commonappdata}\\SRPSS\\themes"' in normal
    assert 'Name: "{commonappdata}\\SRPSS\\themes"' in normal
    assert 'Type: filesandordirs; Name: "{commonappdata}\\SRPSS\\themes"' in normal

    assert 'Source: "..\\release\\media_center\\themes\\*"; DestDir: "{commonappdata}\\SRPSS\\themes"' in media_center
    assert 'Type: filesandordirs; Name: "{commonappdata}\\SRPSS\\themes"' in media_center
