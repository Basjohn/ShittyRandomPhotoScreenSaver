"""Import-free migration, dormancy and overlap checks for fullscreen/volume chrome.

Full Qt, captured-image, multi-DPI and GPU validation remains in the temporary
material-surface audit plan; these deterministic checks don't claim pixel parity.
"""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_new_fullscreen_default_preserves_existing_style_choices() -> None:
    tree = ast.parse(read("core/settings/default_settings.py"))
    assignment = next(node for node in tree.body if isinstance(node, ast.Assign)
                      and any(isinstance(t, ast.Name) and t.id == "DEFAULT_SETTINGS"
                              for t in node.targets))
    defaults = ast.literal_eval(assignment.value)
    assert defaults["widgets"]["spotify_visualizer"]["fullscreen_overlays"]["display_style"] == "hide_borders"
    styles = read("core/settings/fullscreen_overlays.py")
    assert 'DISPLAY_STYLE_DEFAULT = "default"' in styles
    assert 'DISPLAY_STYLE_HIDE_BORDERS = "hide_borders"' in styles
    geo = read("widgets/spotify_visualizer/presentation_geometry.py")
    assert "if display_style == DISPLAY_STYLE_HIDE_BORDERS:" in geo


def test_border_only_visualizer_skips_transparent_interior() -> None:
    qml = read("rendering/quick/qml/VisualizerPresentation.qml")
    shader = read("rendering/quick/qml/shaders/surface_material.frag")
    assert "active: visualizerPresentationRoot.cardBorderMaterialActive" in qml
    assert "fillSurfaceEnabled: 0.0" in qml
    assert "borderSurfaceEnabled: 1.0" in qml
    assert "if (fillSurfaceEnabled < 0.5 && ringCoverage <= 0.0001)" in shader
    assert "fragColor = vec4(0.0);" in shader
    assert "layout(binding = 1) uniform sampler2D source" in shader


def test_volume_outline_uses_real_material_active_state() -> None:
    overlay = read("rendering/quick/qml/OverlayWidget.qml")
    qml = read("rendering/quick/qml/MediaPresentation.qml")
    assert "readonly property alias cardBorderMaterialActive: card.borderSurfaceMaterialActive" in overlay
    assert "cardBorderMaterialActive ? 0.8 : 1.0" in qml
    assert qml.count("border.color: mediaRoot.effectiveVolumeOutlineColor") == 4
    assert "border.width: mediaRoot.cardBorderMaterialActive" in qml
    assert 'objectName: "mediaAppVolumeExposedOutline"' in qml
    assert 'active: mediaRoot.cardBorderMaterialActive' in qml
    assert 'clip: true' in qml.split('id: appVolumeExposedOutlineLoader', 1)[1].split('MouseArea {',1)[0]
    assert 'height: Math.max(0.0, appVolumeFill.y)' in qml
    assert 'y: appVolumeFill.y + appVolumeFill.height' in qml
    assert 'height: Math.max(0.0, appVolumeTrack.height - y)' in qml
    # No additional material shader, capture owner, timer, or volume semantics.
    assert qml.count('objectName: "mediaAppVolumeTrackMaterial"') == 1
    assert qml.count('objectName: "mediaAppVolumeFillMaterial"') == 1


def test_material_outline_references_a_declared_volume_fill_qml_id() -> None:
    """An objectName is not a QML id: an active material border evaluates this Loader.

    A previously added clipping Loader referenced ``appVolumeFill.y`` and
    ``appVolumeFill.height`` even though that Rectangle had only objectName.
    The QML file compiled, but logged ReferenceError as soon as the Loader
    activated on Windows. Keep the ID and the two live geometry references in
    the same volume track rather than duplicating their formulas.
    """
    qml = read("rendering/quick/qml/MediaPresentation.qml")
    track = qml.split('id: appVolumeTrack\n', 1)[1].split('objectName: "mediaAppVolumeInputArea"', 1)[0]
    assert track.count('id: appVolumeFill\n') == 1
    assert 'id: appVolumeFill\n                    objectName: "mediaAppVolumeFill"' in track
    assert track.count('appVolumeFill.y') == 2
    assert track.count('appVolumeFill.height') == 1
    assert 'active: mediaRoot.cardBorderMaterialActive' in track


def test_track_and_fill_outline_vertical_regions_do_not_overlap() -> None:
    for height in (1.0, 12.0, 90.0, 240.0):
        for level in (0.0, 0.001, 0.25, 0.5, 0.75, 0.999, 1.0):
            filled_height = 0.0 if level <= 0.0 else min(height, max(2.0, height * level))
            fill_y = (height - filled_height) / 2.0
            fill_bottom = fill_y + filled_height
            assert 0 <= fill_y <= fill_bottom <= height
            top = (0.0, fill_y)
            fill = (fill_y, fill_bottom)
            bottom = (fill_bottom, height)
            assert top[1] == fill[0] and fill[1] == bottom[0]
            assert sum(b-a for a,b in (top, fill, bottom)) == height


def test_removed_visual_experiment_has_no_settings_or_shader_binding() -> None:
    paths=("core/settings/default_settings.py", "ui/tabs/widgets_tab_defaults.py",
           "rendering/quick/widgets/surface_material.py",
           "rendering/quick/widgets/host.py", "rendering/quick/qml/OverlayCard.qml",
           "rendering/quick/qml/VisualizerPresentation.qml", "rendering/quick/qml/MaterialSurface.qml",
           "rendering/quick/qml/shaders/surface_material.frag",
           "rendering/quick/scene_controller.py", "engine/display_manager.py")
    for path in paths:
        content=read(path)
        assert "borderRimHighlight" not in content, path
        assert "border_rim_highlight" not in content, path


def test_audit_checklist_is_bounded_and_removable() -> None:
    plan = read("Current_Plan.md")
    audit = read("Docs/Temporary_Material_Surface_Audit_2026-11-19.md")
    assert "Docs/Temporary_Material_Surface_Audit_2026-11-19.md" in plan
    assert "delete the temporary document" in plan
    assert "performance" in audit.lower()
    assert "cleanup" in audit.lower()
