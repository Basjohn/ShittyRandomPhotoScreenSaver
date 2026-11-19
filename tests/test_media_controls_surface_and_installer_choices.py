"""Focused source contracts for the shared Media Control Bar and optional curated assets.

Import-free: verifies both profiles and normal/fullscreen QML without Qt or an installer.
Physical material rendering and ISCC compilation remain platform acceptance gates.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_installers_replace_themes_and_presets_only_when_respective_default_checked_task_selected() -> None:
    for path in ("scripts/SRPSS_Installer.iss", "scripts/SRPSS_MediaCenter_Installer.iss"):
        installer = source(path)
        tasks = installer.split("[Tasks]", 1)[1].split("[Files]", 1)[0]
        files = installer.split("[Files]", 1)[1].split("[Dirs]", 1)[0]
        deletes = installer.split("[InstallDelete]", 1)[1].split("[", 1)[0]
        for task, folder in (("replacethemes", r"\SRPSS\themes"),
                             ("replacevispresets", r"\SRPSS\presets\visualizer_modes")):
            task_line = next(l for l in tasks.splitlines() if f'Name: "{task}"' in l)
            assert "Flags: unchecked" not in task_line
            assert "Description:" in task_line
            assert any(folder in l and f"Tasks: {task}" in l for l in files.splitlines())
            assert any(folder in l and f"Tasks: {task}" in l for l in deletes.splitlines())
        if path.endswith("SRPSS_Installer.iss"):
            # Frozen executable extraction is independent from asset-preservation tasks.
            assert r'Type: filesandordirs; Name: "{localappdata}\SRPSS\onefile"' in deletes


def test_single_media_owned_material_override_is_persisted_not_fullscreen_specific() -> None:
    default = source("core/settings/default_settings.py")
    ui = source("ui/tabs/widgets_tab_defaults.py")
    media_page = source("ui/tabs/widgets_tab_media.py")
    model = source("rendering/quick/widgets/media.py")
    fullscreen_default = source("core/settings/fullscreen_overlays.py")
    fullscreen_ui = source("ui/tabs/visualizers_fullscreen_page.py")
    assert "'controls_surface_material': 'inherit'" in default
    assert '"controls_surface_material"' in model
    assert "controlsSurfaceMaterial" in model
    assert '"materialMode": self.controlsSurfaceMaterial' in model
    assert 'for material in ("normal", "inherit", "acrylic", "glass", "frosted", "mica", "smoked"):' in ui
    assert 'label = "Theme" if material == "inherit"' in ui
    assert 'addItem("Flat (No Material)", "flat")' not in ui
    assert 'if transport_material == "flat":' in model  # Backward-compatible stored preference.
    assert 'transport_material = "normal"' in model
    assert '"media_controls_surface_mode"' in ui
    assert 'resolve_media_controls_surface_mode(widgets_config)' in ui
    assert 'resolve_media_controls_surface_mode(widgets)' in model
    assert '"Control Bar Surface:"' not in media_page
    assert "tab.media_controls_surface_material" not in media_page
    assert "media_controls_surface" not in fullscreen_default
    assert "now_playing_controls_surface" not in fullscreen_ui


def test_normal_and_fullscreen_bar_share_existing_child_surface_renderer_and_same_override() -> None:
    ordinary = source("rendering/quick/qml/MediaPresentation.qml")
    fullscreen = source("rendering/quick/qml/ExpandedVisualizerOverlays.qml")
    bar = source("rendering/quick/qml/MediaTransportBar.qml")
    child = source("rendering/quick/qml/ChildMaterialSurface.qml")
    assert "materialMode: mediaRoot.mediaModel.controlsSurfaceMaterial" in ordinary
    assert "materialBackdrop: mediaRoot.cardSurfaceBackdrop" in ordinary
    assert "inheritedMaterial: mediaRoot.cardSurfaceMaterial" in ordinary
    assert "materialMode: overlays.mediaLook(\"materialMode\", \"inherit\")" in fullscreen
    assert "materialBackdrop: overlays.surfaceBackdrop" in fullscreen
    assert "ChildMaterialSurface {" in bar
    assert 'forceFlat: bar.materialMode === "normal"' in bar
    assert 'bar.materialMode : bar.inheritedMaterial' in bar
    assert "sourceComponent: MaterialSurface {" in child
    assert "legibilityPanel: child.legibilityPanel" in child
    assert "floatingGlyphs || material.active ? \"transparent\"" in bar
    # The existing volume child and card surface continue to use their previous binding.
    assert "id: systemMuteMaterial" in ordinary
    assert "card: mediaRoot" in ordinary


def test_transport_material_uses_volume_semantic_colour_and_no_legibility_guard_only_on_bar() -> None:
    model = source("rendering/quick/widgets/media.py")
    bar = source("rendering/quick/qml/MediaTransportBar.qml")
    ordinary = source("rendering/quick/qml/MediaPresentation.qml")
    fullscreen = source("rendering/quick/qml/ExpandedVisualizerOverlays.qml")
    volume = ordinary.split("id: appVolumeTrackMaterial", 1)[1].split("}", 1)[0]
    child = source("rendering/quick/qml/ChildMaterialSurface.qml")
    material = source("rendering/quick/qml/MaterialSurface.qml")

    # Read the same *resolved* semantic RGBA used by the adjustable volume track,
    # not raw defaults. Normal retains its own pre-existing transport colour.
    assert '"media.volume.track"' in model
    assert '"materialFillColor": name(self.appVolumeTrackColor)' in model
    assert '"surfaceColor": name(self.controlsSurfaceColor)' in model
    assert "materialFillColor: mediaRoot.mediaModel.appVolumeTrackColor" in ordinary
    assert 'materialFillColor: overlays.mediaLook("materialFillColor", ' in fullscreen
    assert 'surfaceColor: overlays.mediaLook("surfaceColor", ' in fullscreen
    assert 'materialMode: overlays.mediaLook("materialMode", "inherit")' in fullscreen
    assert 'materialMode: mediaRoot.mediaModel.controlsSurfaceMaterial' in ordinary
    assert '"sourceMaterial": str(self.style.card_style.surface_material)' in model
    assert '"sourceOpacityAdjust": float(self.style.card_style.surface_opacity_adjust)' in model
    assert 'inheritedMaterial: overlays.mediaLook("sourceMaterial", overlays.surfaceMaterial)' in fullscreen
    assert 'materialOpacityAdjust: overlays.mediaLook("sourceOpacityAdjust", overlays.surfaceOpacityAdjust)' in fullscreen
    assert 'materialMode === "normal" ? surfaceColor : materialFillColor' in bar
    assert 'color: floatingGlyphs || material.active ? "transparent" : bar.adjustedFlatSurfaceColor' in bar
    assert 'fillColor: bar.effectiveSurfaceColor' in bar

    # Exactly the volume child treatment. Other surfaces retain their guards.
    bar_surface = bar.split('ChildMaterialSurface {', 1)[1].split('Row {', 1)[0]
    assert 'tintAlphaScale: 0.4' in bar_surface
    assert 'legibilityPanel: false' in bar_surface
    assert 'tintAlphaScale: 0.4' in volume
    assert 'legibilityPanel: false' in volume
    assert 'property bool legibilityPanel: true' in child
    assert 'property bool legibilityPanel: true' in material
    assert 'legibilityPanel: false' not in ordinary[:ordinary.index('id: appVolumeTrackMaterial')]


def test_linux_installers_have_independent_opt_outs_with_replacement_as_default() -> None:
    import shutil
    import subprocess
    import tempfile
    from tools.linux_build import install_script

    for profile, executable in (("screensaver", "srpss"), ("mc", "srpss-mc")):
        script = install_script(profile)
        assert f'APP="{executable}"' in script
        assert 'REPLACE_THEMES=1' in script
        assert 'REPLACE_PRESETS=1' in script
        assert '--keep-themes) REPLACE_THEMES=0' in script
        assert '--keep-presets) REPLACE_PRESETS=0' in script
        assert 'if (( REPLACE_PRESETS )); then' in script
        assert 'if (( REPLACE_THEMES )); then' in script
        presets = script.split('if (( REPLACE_PRESETS )); then', 1)[1].split('\nfi', 1)[0]
        themes = script.split('if (( REPLACE_THEMES )); then', 1)[1].split('\nfi', 1)[0]
        assert 'rm -rf "$DATA/SRPSS/presets/visualizer_modes"' in presets
        assert 'cp -a "$HERE/presets/visualizer_modes"' in presets
        assert 'rm -rf "$DATA/SRPSS/themes"' in themes
        assert 'cp -a "$HERE/themes"' in themes
        assert 'APP="__APP_BINARY__"' not in script  # Both profiles are substituted.
        assert '[[ -f "$HERE/$APP" && -d "$HERE/themes" && -d "$HERE/presets/visualizer_modes" ]]' in script
        assert 'Unknown option:' in script
        assert 'cannot be combined with catalogue preservation switches' in script
        if shutil.which("bash"):
            syntax = subprocess.run(["bash", "-n"], input=script, text=True, capture_output=True, check=False)
            assert syntax.returncode == 0, syntax.stderr
            # Only option parsing: no install/uninstall and no data mutation.
            with tempfile.TemporaryDirectory() as directory:
                script_path = Path(directory) / "install.sh"
                script_path.write_text(script, encoding="utf-8")
                usage = subprocess.run(["bash", str(script_path), "--help"], text=True, capture_output=True)
                assert usage.returncode == 0 and "--keep-themes" in usage.stdout
                invalid = subprocess.run(["bash", str(script_path), "--unknown"], text=True, capture_output=True)
                assert invalid.returncode == 2 and "Unknown option" in invalid.stderr
                conflicting = subprocess.run(
                    ["bash", str(script_path), "--keep-themes", "--uninstall"],
                    text=True, capture_output=True,
                )
                assert conflicting.returncode == 2 and "cannot be combined" in conflicting.stderr
