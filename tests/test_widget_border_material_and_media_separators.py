"""Contracts for proposed widget-border material and shared Media transport dividers.

These source checks run without Qt. They do not replace the Qt 6.12 shader bake,
backend validation, pixel comparisons or GPU measurements in Current_Plan 1.7b.
"""

from pathlib import Path
import ast
import re
from collections.abc import Mapping

ROOT = Path(__file__).resolve().parents[1]


def source(name: str) -> str:
    return (ROOT / name).read_text(encoding="utf-8")


def test_global_border_choice_and_density_ride_existing_persistence_and_style() -> None:
    defaults = source("core/settings/default_settings.py")
    opacities = source("core/settings/surface_opacity.py")
    ui = source("ui/tabs/widgets_tab_defaults.py")
    resolver = source("rendering/quick/widgets/surface_material.py")
    host = source("rendering/quick/widgets/host.py")
    overlay = source("rendering/quick/qml/OverlayWidget.qml")

    assert "'border_surface_mode': 'inherit'" in defaults
    assert "'border_surface_opacity_adjust': 0.0" in defaults
    assert '"border_surface"' in opacities
    assert '"Border Surface:"' in ui and '"Border Opacity:"' in ui
    assert 'for material in ("normal", "inherit", "acrylic", "glass", "frosted", "mica", "smoked"):' in ui
    assert 'border_surface_mode_combo.currentData()' in ui
    assert 'add_material_opacity_slider("border_surface", "Border Opacity:")' in ui
    assert 'resolve_border_surface_mode(widgets_config)' in resolver
    assert 'border_surface_opacity_adjust=border_adjustment' in resolver
    assert 'border_surface_mode: str = "inherit"' in host
    assert '("cardBorderSurfaceMode", "border_surface_mode")' in host
    assert '("cardBorderSurfaceOpacityAdjust", "border_surface_opacity_adjust")' in host
    assert 'demanded.append(style.border_surface_mode)' in host  # independent backdrop demand
    assert 'if style.shell_enabled and style.border_width > 0.0:' in host
    assert 'property alias cardBorderSurfaceMode: card.borderSurfaceMode' in overlay
    assert 'property alias cardBorderSurfaceOpacityAdjust: card.borderSurfaceOpacityAdjust' in overlay


def test_border_mode_resolution_is_stable_for_old_settings_and_unknown_values() -> None:
    path = ROOT / "rendering/quick/widgets/surface_material.py"
    module = ast.parse(path.read_text(encoding="utf-8"))
    resolver = next(node for node in module.body if isinstance(node, ast.FunctionDef)
                    and node.name == "resolve_border_surface_mode")
    scope = {"Mapping": Mapping, "SURFACE_MATERIALS": frozenset(("normal", "glass", "acrylic", "frosted", "mica", "smoked"))}
    exec(compile(ast.Module(body=[resolver], type_ignores=[]), str(path), "exec"), scope)
    resolve = scope["resolve_border_surface_mode"]
    assert resolve({}) == "inherit"
    assert resolve({"global": {"border_surface_mode": "flat"}}) == "normal"
    assert resolve({"global": {"border_surface_mode": "Normal"}}) == "normal"
    assert resolve({"global": {"border_surface_mode": "Smoked"}}) == "smoked"
    assert resolve({"global": {"border_surface_mode": "unknown"}}) == "inherit"


def test_existing_single_shader_draws_border_without_a_second_pass_or_legibility_panel() -> None:
    card = source("rendering/quick/qml/OverlayCard.qml")
    surface = source("rendering/quick/qml/MaterialSurface.qml")
    shader = source("rendering/quick/qml/shaders/surface_material.frag")

    assert card.count("sourceComponent: MaterialSurface {") == 1
    assert 'active: card.surfaceMaterialActive || card.borderSurfaceMaterialActive' in card
    assert 'z: card.borderSurfaceMaterialActive ? 0.5 : -0.5' in card
    assert 'border.width: card.borderSurfaceMaterialActive ? 0.0 : card.borderWidth' in card
    assert 'borderSurfaceMode === "inherit"' in card
    assert 'borderWidth > 0.0' in card
    assert 'borderSurfaceEnabled: card.borderSurfaceMaterialActive ? 1.0 : 0.0' in card
    assert 'fillSurfaceEnabled: card.surfaceMaterialActive ? 1.0 : 0.0' in card
    assert 'property real borderSurfaceEnabled: 0.0' in surface
    assert 'property real fillSurfaceEnabled: 1.0' in surface
    for color in ('"acrylic"', '"glass"', '"frosted"', '"mica"', '"smoked"'):
        assert color in surface
    assert 'readonly property var borderParameters:' in surface
    assert 'readonly property vector4d borderGlassLegibility' in surface
    # Different coefficients, no panelContrastFloor, no ink guard on borderAt.
    border_part = shader.split("vec4 borderAt(", 1)[1].split("void main()", 1)[0]
    assert 'panelCeiling' not in border_part
    assert 'panelLimits' not in border_part
    assert 'adjustedBorderDensity' in border_part
    assert 'textureLod(source' in border_part
    assert 'max(0.0, radius - thickness)' in shader
    assert 'ringCoverage = clamp(inside - innerCoverage' in shader
    assert 'vec4 surface = surfaceAt(' in shader
    assert 'fragColor = (face * max(0.0, inside - ringCoverage) + border * ringCoverage) * qt_Opacity;' in shader
    assert shader.count("layout(binding = 1) uniform sampler2D source") == 1
    assert shader.count("layout(location = 0) out vec4 fragColor") == 1
    assert not re.search(r'\b3\s*(?:logical\s*)?px\s*(?:minimum|threshold)', card)


def test_media_bar_separators_share_single_outline_ink_and_touch_inside_border() -> None:
    model = source("rendering/quick/widgets/media.py")
    bar = source("rendering/quick/qml/MediaTransportBar.qml")
    ordinary = source("rendering/quick/qml/MediaPresentation.qml")
    fullscreen = source("rendering/quick/qml/ExpandedVisualizerOverlays.qml")

    assert '"media.transport.border"' in model
    assert 'controls_border_color=transport_outline' in model
    assert 'controls_separator_color=transport_outline' in model
    assert '"media.transport.separator", local_roles=local_common' not in model
    assert bar.count('color: bar.floatingGlyphs ? "transparent" : bar.outlineColor') == 2
    assert bar.count('height: Math.max(0.0, parent.height - 2.0 * bar.outlineWidth)') == 2
    assert bar.count('y: bar.outlineWidth') == 2
    assert 'objectName: "mediaTransportOutline"' in bar
    assert 'border.width: 0.0' in bar
    assert 'border.color: bar.outlineColor' in bar
    assert 'z: 2' in bar
    assert '(parent.width - 2.0 * bar.separatorWidth) / 3.0' in bar
    assert 'separatorWidth: mediaRoot.scaleAwareStrokeWidth(1.5)' in ordinary
    assert 'separatorWidth: 1.5 * drawnFactor' in fullscreen
    assert 'outlineWidth: floatingGlyphs ? 0.0 : Math.max(1.0, 1.5 * drawnFactor) + 1.0' in fullscreen
    assert 'outlineColor: overlays.mediaLook("borderColor", "#ffffffff")' in fullscreen
    assert 'outlineColor: mediaRoot.mediaModel.controlsBorderColor' in ordinary
    # Never alter the floating glyph presentation.
    assert 'bar.floatingGlyphs' in bar


def test_plan_explicitly_gates_qsb_disabled_state_and_incremental_cost() -> None:
    plan = source("Current_Plan.md")
    scope = plan.split("### 1.7b Material-aware widget border", 1)[1].split("### 1.8", 1)[0]
    for required in (
        "Shader bake and binary admission", "Disabled/compatibility proof",
        "Shader and visual proof", "Incremental cost and dormancy proof",
        "border OFF vs border ON", "90 Hz", "Normal", "1.5",
        "no QML layer/extra capture",
    ):
        assert required in scope
    assert "3 px eligibility gate" in scope  # explicitly rejected, not enforced
