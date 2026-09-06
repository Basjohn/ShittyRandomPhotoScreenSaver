from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _text(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_build_families_explicitly_carry_current_quick_runtime_dependencies() -> None:
    required = (
        "--include-package=rendering.quick",
        "--include-package=widgets.spotify_visualizer",
        "--include-package=rendering.gl_programs",
        "--include-package=rendering.gl_compositor_pkg",
        "--include-package=OpenGL",
        "--include-package=pyaudiowpatch",
        "--include-package=sounddevice",
        "--include-qt-plugins=qml",
        "--include-qt-plugins=multimedia",
        "--include-module=PySide6.QtQuick",
        "--include-module=PySide6.QtQml",
        "--include-module=PySide6.QtMultimedia",
    )
    for relative in (
        "scripts/build_nuitka.ps1",
        "scripts/build_nuitka_mc_onedir.ps1",
        "scripts/venv/build_nuitka.ps1",
        "scripts/venv/build_nuitka_mc_onedir.ps1",
    ):
        source = _text(relative)
        for declaration in required:
            assert declaration in source, (relative, declaration)


def test_build_preflight_and_onedir_validation_cover_qml_shaders_themes_presets_and_sounds() -> None:
    layout = _text("tools/build_layout.ps1")
    for token in (
        "DisplayScene.qml",
        "VisualizerPresentation.qml",
        "WidgetInteractionGlow.qml",
        "widget_glow.frag.qsb",
        "resources\\tutuogg.ogg",
        "resources\\jedimodeyall.mp3",
        "themes\\widgets",
        "presets\\visualizer_modes",
        "widgets\\spotify_visualizer\\shaders",
        "Assert-SRPSSOnefileQuickPayloadContract",
        "Assert-SRPSSOnedirQuickPayload",
    ):
        assert token in layout


def test_diagnostic_frozen_profile_uses_bundled_theme_and_preset_payloads() -> None:
    theme_paths = _text("ui/settings_theme_paths.py")
    assert "is_diagnostic_build" in theme_paths
    assert "return _source_themes_directory()" in theme_paths

    presets = _text("core/settings/visualizer_presets.py")
    assert presets.count("is_diagnostic_build") >= 2
    assert "return bundled_root" in presets
    assert "return bundled_overrides_root" in presets


def test_installers_offer_opt_in_profile_scoped_settings_reset() -> None:
    standard = _text("scripts/SRPSS_Installer.iss")
    diagnostic = _text("scripts/SRPSS_Diagnostic_Installer.iss")
    media_center = _text("scripts/SRPSS_MediaCenter_Installer.iss")

    for source in (standard, diagnostic, media_center):
        assert 'Name: "resetsettings"' in source
        assert 'Description: "Revert Settings To Defaults"' in source
        assert 'Flags: unchecked' in source

    assert '{userappdata}\\SRPSS\\settings_v2.json"; Tasks: resetsettings' in standard
    assert '{userappdata}\\SRPSS\\settings_v2.json"; Tasks: resetsettings' in diagnostic
    assert '{userappdata}\\SRPSS_MC\\settings_v2.json"; Tasks: resetsettings' in media_center

    # Reset is intentionally surgical: no broad APPDATA/cache/credential deletion.
    for source in (standard, diagnostic, media_center):
        reset_lines = [line for line in source.splitlines() if "Tasks: resetsettings" in line]
        assert len(reset_lines) == 1
        assert reset_lines[0].strip().startswith("Type: files;")
        assert reset_lines[0].strip().endswith('settings_v2.json"; Tasks: resetsettings')
