from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _text(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_build_families_explicitly_carry_current_quick_runtime_dependencies() -> None:
    required = (
        "--include-package=rendering.quick",
        "--include-package=widgets.spotify_visualizer",
        # The Visualizer's engine worker (native core P2b slice 5.7): the spawned child imports its target by name.
        "--include-package=core.visualizer_engine",
        "--include-package=rendering.gl_programs",
        "--include-package=OpenGL",
        "--include-package=pyaudiowpatch",
        "--include-package=sounddevice",
        "--include-data-files=SRPSS.ico=SRPSS.ico",
        "--include-qt-plugins=qml",
        "--include-qt-plugins=multimedia",
        "--include-module=PySide6.QtQuick",
        "--include-module=PySide6.QtQml",
        "--include-module=PySide6.QtMultimedia",
    )
    # ``rendering.gl_compositor_pkg`` was removed in the Qt Quick cutover. Nuitka
    # fatals on a non-existent --include-package, so the build families must never
    # reference it again.
    forbidden = ("rendering.gl_compositor_pkg",)
    for relative in (
        "scripts/venv/build_nuitka.ps1",
        "scripts/venv/build_nuitka_dashboard_onedir.ps1",
    ):
        source = _text(relative)
        for declaration in required:
            assert declaration in source, (relative, declaration)
        for declaration in forbidden:
            assert declaration not in source, (relative, declaration)


def test_build_preflight_and_onedir_validation_cover_qml_shaders_themes_presets_and_sounds() -> None:
    layout = _text("tools/build_layout.ps1")
    for token in (
        "DisplayScene.qml",
        "VisualizerPresentation.qml",
        "WidgetInteractionGlow.qml",
        "widget_glow.frag.qsb",
        "surface_material.frag.qsb",
        "resources\\tutuogg.ogg",
        "resources\\jedimodeyall.mp3",
        "themes\\widgets",
        "presets\\visualizer_modes",
        "widgets\\spotify_visualizer\\shaders",
        "Assert-SRPSSOnefileQuickPayloadContract",
        "Assert-SRPSSOnedirQuickPayload",
        "Assert-SRPSSQmlSourceContract",
    ):
        assert token in layout


def test_diagnostic_frozen_presets_use_shared_curated_authority() -> None:
    presets = _text("core/settings/visualizer_presets.py")
    # Diagnostics are a build profile, not a second authored preset library.
    assert "is_diagnostic_build" not in presets
    assert "return shared_root" in presets
    assert '_shared_presets_base_dir() / "visualizer_mode_overrides"' in presets


def test_installers_offer_profile_scoped_settings_reset() -> None:
    screensaver = _text("scripts/SRPSS_Screensaver_Installer.iss")
    dashboard = _text("scripts/SRPSS_Dashboard_Installer.iss")

    for source in (screensaver, dashboard):
        assert 'Name: "resetsettings"' in source
        assert 'Description: "Revert Settings To Defaults"' in source

    # EXACT-VALUE INVARIANT: after the one-release 5.0.0 migration window, the
    # destructive reset remains available but opt-in in every installer. Change
    # this only with an explicit installer migration/reset policy decision.
    for source in (screensaver, dashboard):
        reset_task = next(
            line.strip()
            for line in source.splitlines()
            if line.strip().startswith('Name: "resetsettings"')
        )
        assert "Flags: unchecked" in reset_task

    assert '{userappdata}\\SRPSS\\settings_v2.json"; Tasks: resetsettings' in screensaver
    for appdata in ("SRPSS_Dashboard", "SRPSS_MC"):
        assert f'{{userappdata}}\\{appdata}\\settings_v2.json"; Tasks: resetsettings' in dashboard

    # A reset clears only that profile’s settings snapshots and QSettings keys.
    for source, profiles in ((screensaver, 1), (dashboard, 2)):
        reset_lines = [
            line.strip() for line in source.splitlines() if "Tasks: resetsettings" in line
        ]
        file_lines = [line for line in reset_lines if line.startswith("Type: files;")]
        registry_lines = [line for line in reset_lines if line.startswith("Root: HKCU;")]
        assert len(file_lines) == profiles, reset_lines
        assert all(line.endswith('settings_v2.json"; Tasks: resetsettings') for line in file_lines)
        assert len(registry_lines) == profiles, reset_lines
        assert all("Flags: deletekey" in line for line in registry_lines)
        assert len(reset_lines) == profiles * 2, reset_lines


def test_legacy_nuitka_entrypoints_delegate_only_to_canonical_workers() -> None:
    for legacy, worker in (
        ("scripts/build_nuitka.ps1", "venv\\build_nuitka.ps1"),
        ("scripts/build_nuitka_dashboard_onedir.ps1", "venv\\build_nuitka_dashboard_onedir.ps1"),
    ):
        source = _text(legacy)
        assert worker in source
        assert "& $worker" in source
        assert "--mingw64" not in source
        assert "-m nuitka" not in source
