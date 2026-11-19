"""Source contracts for the separate Visualizer frame and the shared Media ink.

This does not replace Windows Qt/QML compilation, pixel comparisons or the
Visualizer's 4K/90 Hz material-border GPU cost measurement.
"""
from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_visualizer_uses_existing_border_material_without_covering_content() -> None:
    qml = read("rendering/quick/qml/VisualizerPresentation.qml")
    scene = read("rendering/quick/scene_controller.py")
    manager = read("engine/display_manager.py")

    assert 'property string cardBorderSurfaceMode: "inherit"' in qml
    assert 'property real cardBorderSurfaceOpacityAdjust: 0.0' in qml
    assert 'cardBorderSurfaceMode === "inherit"' in qml
    assert 'cardShellEnabled && cardBorderWidth > 0.0' in qml
    assert 'resolvedCardBorderMaterial !== "normal" && cardSurfaceBackdrop !== null' in qml
    assert 'objectName: "visualizerCardBorderMaterial"' in qml
    assert 'active: visualizerPresentationRoot.cardBorderMaterialActive' in qml
    assert 'visible: active' in qml
    assert 'sourceComponent: MaterialSurface {' in qml
    assert 'fillSurfaceEnabled: 0.0' in qml
    assert 'borderSurfaceEnabled: 1.0' in qml
    assert 'legibilityPanel: false' in qml
    assert 'borderMaterial: visualizerPresentationRoot.resolvedCardBorderMaterial' in qml
    assert 'borderOpacityAdjust: visualizerPresentationRoot.cardBorderSurfaceOpacityAdjust' in qml
    assert 'border.width: visualizerPresentationRoot.cardBorderMaterialActive\n            ? 0.0 : visualizerPresentationRoot.cardBorderWidth' in qml
    # Unlike a normal card, this frame must paint *above* the Visualizer.
    assert qml.index('id: visualizerContentHost') < qml.index('id: visualizerBorderMaterialLoader')
    assert qml.index('id: visualizerBorderMaterialLoader') < qml.index('id: cardFrame')
    assert 'root.setProperty("cardBorderSurfaceMode", self._visualizer_border_surface_mode)' in scene
    assert 'root.setProperty("cardBorderSurfaceOpacityAdjust", self._visualizer_border_surface_opacity_adjust)' in scene
    assert 'resolve_border_surface_mode(self._widgets_config_snapshot)' in manager
    assert 'resolve_opacity_adjust(self._widgets_config_snapshot, "border_surface")' in manager


def test_visualizer_border_demand_dormant_with_missing_shell_width_or_root() -> None:
    path = ROOT / "rendering/quick/scene_controller.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    cls = next(node for node in tree.body if isinstance(node, ast.ClassDef)
               and node.name == "QuickSceneController")
    method = next(node for node in cls.body if isinstance(node, ast.FunctionDef)
                  and node.name == "_surface_materials_in_use")
    fn = ast.FunctionDef(name="demand", args=method.args, body=method.body,
                         decorator_list=[], returns=method.returns, type_comment=None)
    scope: dict[str, object] = {}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[fn], type_ignores=[])),
                 str(path), "exec"), scope)

    class Root:
        def __init__(self, enabled: bool = True, width: float = 3.0) -> None:
            self.enabled = enabled
            self.width = width

        def property(self, name: str) -> object:
            return {"cardShellEnabled": self.enabled, "cardBorderWidth": self.width}[name]

    owner = SimpleNamespace(_ordinary_widget_host=None, _context_menu_surface_material="normal",
                            _visualizer_surface_material="normal", _visualizer_border_surface_mode="glass",
                            _visualizer_root=Root())
    demand = scope["demand"]
    assert demand(owner) == frozenset({"glass"})
    owner._visualizer_root = Root(False)
    assert demand(owner) == frozenset()
    owner._visualizer_root = Root(True, 0.0)
    assert demand(owner) == frozenset()
    owner._visualizer_root = None
    assert demand(owner) == frozenset()
    owner._visualizer_root = Root()
    owner._visualizer_border_surface_mode = "inherit"
    assert demand(owner) == frozenset()
    owner._visualizer_surface_material = "frosted"
    assert demand(owner) == frozenset({"frosted"})


def test_media_dividers_and_outline_have_one_painter_above_material() -> None:
    qml = read("rendering/quick/qml/MediaTransportBar.qml")
    ordinary = read("rendering/quick/qml/MediaPresentation.qml")
    fullscreen = read("rendering/quick/qml/ExpandedVisualizerOverlays.qml")
    model = read("rendering/quick/widgets/media.py")

    assert 'property color outlineColor: "#66ffffff"' in qml
    assert 'property real outlineWidth: 1.5' in qml
    assert 'border.width: 0.0' in qml  # root is the flat/material fill, not the outline
    assert 'objectName: "mediaTransportOutline"' in qml
    assert 'border.color: bar.outlineColor' in qml
    assert 'border.width: bar.floatingGlyphs ? 0.0 : bar.outlineWidth' in qml
    assert qml.count('color: bar.floatingGlyphs ? "transparent" : bar.outlineColor') == 2
    assert 'z: 2' in qml and 'z: 1' in qml
    assert 'outlineColor: mediaRoot.mediaModel.controlsBorderColor' in ordinary
    assert 'outlineColor: overlays.mediaLook("borderColor", "#ffffffff")' in fullscreen
    assert 'outlineWidth: floatingGlyphs ? 0.0 : Math.max(1.0, 1.5 * drawnFactor) + 1.0' in fullscreen
    assert 'controls_separator_color=transport_outline' in model
    assert 'controls_border_color=transport_outline' in model


def test_media_artwork_both_resolve_single_3_25_logical_px_width() -> None:
    media = read("rendering/quick/widgets/media.py")
    ordinary = read("rendering/quick/qml/MediaPresentation.qml")
    fullscreen = read("rendering/quick/qml/ExpandedVisualizerOverlays.qml")
    assert 'return 3.25' in media.split('def artworkBorderWidth(', 1)[1].split('def headerFillColor(', 1)[0]
    assert 'mediaRoot.mediaModel.artworkBorderWidth' in ordinary
    assert '"borderWidth": float(self.artworkBorderWidth)' in media
    assert 'overlays.artLook("borderWidth", 3.25)' in fullscreen
    assert 'border.width: artFrame.strokeWidth' in fullscreen
    assert 'border.width: artworkFrame.artworkStrokeWidth' in ordinary
