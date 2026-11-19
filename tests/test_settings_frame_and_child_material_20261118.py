"""Import-free contracts for the Settings-only frame and material child overrides.

These source invariants complement the real Qt/QML Windows visual/resize tests.
They intentionally leave Studio's shared edge defaults and the Media card intact.
"""
from __future__ import annotations

import ast
from collections.abc import Mapping
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def text(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def _resolver(name: str):
    path = ROOT / "rendering/quick/widgets/surface_material.py"
    module = ast.parse(path.read_text(encoding="utf-8"))
    fn = next(node for node in module.body if isinstance(node, ast.FunctionDef) and node.name == name)
    scope = {"Mapping": Mapping}
    exec(compile(ast.Module(body=[fn], type_ignores=[]), str(path), "exec"), scope)
    return scope[name]


def test_header_and_transport_accept_all_explicit_materials_and_legacy_values() -> None:
    header = _resolver("resolve_header_surface_mode")
    bar = _resolver("resolve_media_controls_surface_mode")
    for value in ("normal", "acrylic", "glass", "frosted", "mica", "smoked"):
        assert header({"global": {"header_surface_mode": value}}) == value
        assert bar({"global": {"media_controls_surface_mode": value}}) == value
    assert header({}) == "inherit"
    assert header({"global": {"header_surface_mode": "theme"}}) == "inherit"
    assert bar({"media": {"controls_surface_material": "flat"}}) == "normal"
    assert bar({"global": {"media_controls_surface_mode": "theme"}}) == "inherit"
    assert bar({"global": {"media_controls_surface_mode": "unrecognised"}}) == "inherit"


def test_header_legibility_is_on_for_material_only_and_independent_of_outer_card() -> None:
    header = text("rendering/quick/qml/BrandedHeader.qml")
    child = text("rendering/quick/qml/ChildMaterialSurface.qml")
    transport = text("rendering/quick/qml/MediaTransportBar.qml")
    material = header.split("ChildMaterialSurface {", 1)[1].split("border.color:", 1)[0]
    assert "legibilityPanel: true" in material
    assert 'forceFlat: header.materialMode === "normal"' in material
    assert "card: header.materialCard" in material
    assert "materialOverride: header.materialMode" in material
    assert "legibilityPanel: child.legibilityPanel" in child
    # The volume-like transport bar remains intentionally unguarded.
    assert "legibilityPanel: false" in transport.split("ChildMaterialSurface {", 1)[1].split("Row {", 1)[0]
    # No card-level guard was reconfigured as part of this change.
    assert "cardSurfaceMaterial" in text("rendering/quick/widgets/host.py")


def test_explicit_child_materials_keep_existing_backdrop_demand_alive() -> None:
    host = text("rendering/quick/widgets/host.py")
    styler = text("rendering/quick/widgets/surface_material.py")
    child = text("rendering/quick/qml/ChildMaterialSurface.qml")
    assert "for material in widget.surface_materials" in host
    assert "style.header_surface_mode" in host
    assert "style.media_controls_surface_mode" in host
    assert "header_mode = resolve_header_surface_mode(widgets_config)" in styler
    assert 'resolve_media_controls_surface_mode(widgets_config) if widget_id == "media"' in styler
    assert 'materialOverride !== "inherit"' in child


def test_settings_frame_only_has_requested_delta_without_affecting_studio() -> None:
    dialog = text("ui/settings_dialog.py")
    edge = text("ui/settings_window_edge.py")
    studio = text("ui/studio/chrome.py")
    assert "SETTINGS_DIALOG_BORDER_WIDTH = SETTINGS_OUTER_BORDER_WIDTH + 1.25" in dialog
    assert "SETTINGS_DIALOG_CORNER_RADIUS = SETTINGS_OUTER_CORNER_RADIUS - 0.25" in dialog
    assert "border_width=SETTINGS_DIALOG_BORDER_WIDTH" in dialog
    assert "corner_radius=SETTINGS_DIALOG_CORNER_RADIUS" in dialog
    assert "SETTINGS_OUTER_BORDER_WIDTH = 4.0" in edge
    assert "SETTINGS_OUTER_CORNER_RADIUS = 6.5" in edge
    assert "paint_forged_window_edge(" in studio
    assert "SETTINGS_DIALOG_BORDER_WIDTH" not in studio


def test_all_four_settings_corners_are_native_resize_targets_without_scratch_lines() -> None:
    dialog = text("ui/settings_dialog.py")
    grip = dialog.split("class CornerSizeGrip(QSizeGrip):", 1)[1].split("\nclass ", 1)[0]
    assert 'for corner in ("top_left", "top_right", "bottom_left", "bottom_right")' in dialog
    assert 'self.size_grip = self.corner_size_grips["bottom_right"]' in dialog
    assert "grip.raise_()" in dialog
    assert "SizeFDiagCursor" in dialog and "SizeBDiagCursor" in dialog
    assert "def paintEvent(self, event)" in grip
    assert "event.accept()" in grip
    assert "painter.drawLine" not in grip


def test_all_four_slider_labels_fit_better_and_border_threshold_is_planned() -> None:
    widgets = text("ui/tabs/widgets_tab_defaults.py")
    labels = ("Header Opacity:", "Media Bar Opacity:", "Settings Opacity:", "Widget Opacity:")
    for label in labels:
        assert widgets.count('"' + label + '"') == 1
    assert "Media Bar Opacity Adjust:" not in widgets
    assert "Header Opacity Adjust:" not in widgets
    assert "3.0 logical px" in text("Current_Plan.md")
