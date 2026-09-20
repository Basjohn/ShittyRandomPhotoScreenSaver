"""Normal-runtime no-op admission: scene, widget input and pixel-shift timer.

Qt tests use retained ownership methods on small recording targets so that
identical-payload writes cannot pass merely because QML suppresses a notify
signal internally. Full QML/Quick visual behavior remains under its own tests.
"""
from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

import pytest
from PySide6.QtGui import QColor

from rendering.quick.auxiliary import QuickAuxiliaryController, QuickAuxiliaryState
from rendering.quick.scene_controller import QuickSceneController
from rendering.quick.state import QuickInputState
from rendering.quick.widgets.host import RetainedOverlayWidget


class _RecordingItem:
    def __init__(self, initial=None):
        self.properties = dict(initial or {})
        self.writes = []

    def property(self, name):
        return self.properties.get(name)

    def setProperty(self, name, value):
        self.writes.append((name, value))
        self.properties[name] = value
        return True


class _RecordingTimer:
    def __init__(self):
        self.active = False
        self.ms = 0
        self.started = []
        self.stopped = 0

    def isActive(self):
        return self.active

    def interval(self):
        return self.ms

    def start(self, ms):
        self.active = True
        self.ms = ms
        self.started.append(ms)

    def stop(self):
        self.active = False
        self.stopped += 1


def test_pixel_shift_identical_settings_preserve_timer_deadline_and_pause(qt_app):
    owner = QuickAuxiliaryController(screen_index=0, runtime_generation=11)
    timer = _RecordingTimer()
    # The controller exclusively owns timer use; record admissions without
    # waiting 12-60 seconds for the real Qt timer to fire.
    owner._pixel_shift_timer = timer
    published = []
    owner.state_changed.connect(published.append)
    try:
        assert owner.configure_pixel_shift(True, 2)
        assert owner.resume()
        assert timer.started == [30000]
        published_count = len(published)
        for _ in range(24):
            assert not owner.configure_pixel_shift(True, 2)
        assert timer.active and timer.started == [30000] and timer.stopped == 0
        assert len(published) == published_count

        assert owner.configure_pixel_shift(True, 5)
        assert timer.started == [30000, 12000]
        assert not owner.configure_pixel_shift(True, 5)
        assert timer.started == [30000, 12000]
        assert owner.pause()
        assert timer.stopped == 1
        # A stale queued timeout must not mutate presentation while paused.
        original_state = owner.state
        owner._advance_pixel_shift()
        assert owner.state is original_state
        assert not owner.configure_pixel_shift(True, 5)
        assert timer.stopped == 1 and timer.started == [30000, 12000]
        assert owner.resume()
        assert timer.started == [30000, 12000, 12000]
        assert owner.configure_pixel_shift(False, 5)
        assert timer.stopped == 2 and not timer.active
        assert not owner.configure_pixel_shift(False, 5)
        assert timer.stopped == 2
    finally:
        owner.close()
        owner.deleteLater()


def test_auxiliary_projection_skips_identical_native_cursor_edges(qt_app):
    root = _RecordingItem({
        "dimmingEnabled": False, "dimmingOpacity": 0.0,
        "pixelShiftX": 0.0, "pixelShiftY": 0.0,
    })
    scene = SimpleNamespace(
        _scene_root=root,
        _readiness=SimpleNamespace(admission_open=True, runtime_generation=9),
        _window=SimpleNamespace(screen_index=0),
    )
    state = QuickAuxiliaryState(screen_index=0, runtime_generation=9)
    assert QuickSceneController.apply_auxiliary_state(scene, state)
    assert root.writes == []
    for i in range(20):
        assert QuickSceneController.apply_auxiliary_state(
            scene, replace(state, halo_enabled=bool(i % 2), native_cursor_visible=bool(i % 2))
        )
    assert root.writes == []
    updated = replace(state, dimming_enabled=True, dimming_opacity=0.3, pixel_shift_x=2)
    assert QuickSceneController.apply_auxiliary_state(scene, updated)
    assert [name for name, _ in root.writes] == ["dimmingEnabled", "dimmingOpacity", "pixelShiftX"]
    root.writes.clear()
    assert QuickSceneController.apply_auxiliary_state(scene, updated)
    assert root.writes == []
    assert not QuickSceneController.apply_auxiliary_state(
        scene, replace(updated, runtime_generation=10, pixel_shift_x=3)
    )
    assert root.writes == []
    assert QuickSceneController.apply_auxiliary_state(scene, state)
    assert [name for name, _ in root.writes] == ["dimmingEnabled", "dimmingOpacity", "pixelShiftX"]


def test_ordinary_glow_projection_keeps_semantic_handler_but_skips_noop_writes(qt_app):
    item = _RecordingItem({"cardShellEnabled": True, "widgetGlowClicked": False})
    delivered = []
    widget = SimpleNamespace(_item=item, _input_state_handler=lambda snapshot: delivered.append(snapshot) or True)
    state = QuickInputState(screen_index=0, runtime_generation=3)
    assert RetainedOverlayWidget._apply_input_state(widget, state)
    assert len(item.writes) == 7
    assert item.property("widgetGlowColor") == QColor(*state.widget_glow_color)
    item.writes.clear()
    for _ in range(20):
        assert RetainedOverlayWidget._apply_input_state(widget, state)
    assert item.writes == []
    assert len(delivered) == 21  # Do not suppress legitimate family input routing.

    admitted = replace(state, interaction_mode_enabled=True)
    assert RetainedOverlayWidget._apply_input_state(widget, admitted)
    assert [name for name, _ in item.writes] == ["widgetGlowAdmitted"]
    item.writes.clear()
    item.properties["widgetGlowClicked"] = True
    assert RetainedOverlayWidget._apply_input_state(widget, state)
    assert [name for name, _ in item.writes] == ["widgetGlowAdmitted", "widgetGlowClicked"]
    assert item.property("widgetGlowClicked") is False
    item.writes.clear()
    assert RetainedOverlayWidget._apply_input_state(widget, state)
    assert item.writes == []

class _RecordingGeometryItem(_RecordingItem):
    """Observe the actual QQuickItem setter boundary, not only QML notify."""

    def __init__(self):
        super().__init__()
        self.geometry = [0.0, 0.0, 0.0, 0.0]
        self.geometry_writes = []

    def x(self): return self.geometry[0]
    def y(self): return self.geometry[1]
    def width(self): return self.geometry[2]
    def height(self): return self.geometry[3]

    def _set_geometry(self, axis, value):
        self.geometry[axis] = value
        self.geometry_writes.append((axis, value))

    def setX(self, value): self._set_geometry(0, value)
    def setY(self, value): self._set_geometry(1, value)
    def setWidth(self, value): self._set_geometry(2, value)
    def setHeight(self, value): self._set_geometry(3, value)


def test_ordinary_card_geometry_style_and_visibility_reconcile_only_changed_axes(qt_app):
    from rendering.quick.widgets.host import OverlayCardStyle, OverlayWidgetGeometry

    item = _RecordingGeometryItem()
    retained = SimpleNamespace(item=item)
    first = OverlayWidgetGeometry(15.0, 32.0, 280.0, 105.0)
    style = OverlayCardStyle()
    RetainedOverlayWidget.set_geometry(retained, first)
    RetainedOverlayWidget.set_card_style(retained, style)
    RetainedOverlayWidget.set_fade_opacity(retained, 0.65)
    RetainedOverlayWidget.set_startup_reveal_opacity(retained, 0.25)
    RetainedOverlayWidget.set_working_visible(retained, True)
    assert len(item.geometry_writes) == 4
    assert len(item.writes) == 19  # 16 shell values + two fades + visible
    item.geometry_writes.clear()
    item.writes.clear()
    for _ in range(24):
        RetainedOverlayWidget.set_geometry(retained, first)
        RetainedOverlayWidget.set_card_style(retained, style)
        RetainedOverlayWidget.set_fade_opacity(retained, 0.65)
        RetainedOverlayWidget.set_startup_reveal_opacity(retained, 0.25)
        RetainedOverlayWidget.set_working_visible(retained, True)
    assert item.geometry_writes == [] and item.writes == []

    # Live resize and theme changes must still land independently. A QML-side
    # state correction must not be masked by a cached previous Python style.
    RetainedOverlayWidget.set_geometry(retained, replace(first, y=50.0, width=310.0))
    assert item.geometry_writes == [(1, 50.0), (2, 310.0)]
    item.geometry_writes.clear()
    updated_style = replace(style, border_width=3.0, shadow_color=QColor(7, 8, 9, 120))
    RetainedOverlayWidget.set_card_style(retained, updated_style)
    assert [name for name, _ in item.writes] == ["cardBorderWidth", "cardShadowColor"]
    item.writes.clear()
    item.properties["cardBorderWidth"] = 1.0
    RetainedOverlayWidget.set_card_style(retained, updated_style)
    assert item.writes == [("cardBorderWidth", 3.0)]
    item.writes.clear()
    RetainedOverlayWidget.set_fade_opacity(retained, 0.3)
    RetainedOverlayWidget.set_startup_reveal_opacity(retained, 0.9)
    RetainedOverlayWidget.set_working_visible(retained, False)
    assert [name for name, _ in item.writes] == [
        "fadeOpacity", "startupRevealOpacity", "workingVisible"
    ]


def test_context_menu_theme_and_shadow_noop_reprojection_keeps_live_updates(qt_app):
    from dataclasses import fields
    from rendering.quick.context_menu import (
        QuickContextMenuPaletteStyle, QuickContextMenuShadowStyle,
    )

    root = _RecordingItem()
    scene = SimpleNamespace(
        _scene_root=root, _readiness=SimpleNamespace(admission_open=True)
    )
    shadow = QuickContextMenuShadowStyle(
        enabled=True, color=(9, 18, 27, 128), blur=12.0,
        offset_x=3.0, offset_y=-2.0, extend_left=0.0,
        extend_top=4.0, extend_right=0.0, extend_bottom=0.0,
    )
    palette = QuickContextMenuPaletteStyle(**{
        field.name: (10, 20, 30, 255) for field in fields(QuickContextMenuPaletteStyle)
    })
    assert QuickSceneController.apply_context_menu_shadow_style(scene, shadow)
    assert QuickSceneController.apply_context_menu_palette_style(scene, palette)
    assert len(root.writes) == 9 + len(fields(QuickContextMenuPaletteStyle))
    root.writes.clear()
    for _ in range(24):
        assert QuickSceneController.apply_context_menu_shadow_style(scene, shadow)
        assert QuickSceneController.apply_context_menu_palette_style(scene, palette)
    assert root.writes == []
    assert QuickSceneController.apply_context_menu_shadow_style(
        scene, replace(shadow, blur=21.0, color=(12, 13, 14, 255))
    )
    assert [name for name, _ in root.writes] == [
        "contextMenuShadowColor", "contextMenuShadowBlur"
    ]
    root.writes.clear()
    assert QuickSceneController.apply_context_menu_palette_style(
        scene, replace(palette, menu_text=(40, 50, 60, 255))
    )
    assert [name for name, _ in root.writes] == ["contextMenuTextColor"]
    root.writes.clear()
    root.properties["contextMenuShadowBlur"] = 1.0
    assert QuickSceneController.apply_context_menu_shadow_style(
        scene, replace(shadow, blur=21.0, color=(12, 13, 14, 255))
    )
    assert root.writes == [("contextMenuShadowBlur", 21.0)]
    root.writes.clear()
    scene._readiness.admission_open = False
    assert not QuickSceneController.apply_context_menu_shadow_style(scene, shadow)
    assert not QuickSceneController.apply_context_menu_palette_style(scene, palette)
    assert root.writes == []


def test_context_menu_model_repeat_binding_keeps_one_retained_qobject(qt_app):
    from rendering.quick.context_menu import QuickContextMenuModel

    root = _RecordingItem()
    scene = SimpleNamespace(
        _scene_root=root,
        _readiness=SimpleNamespace(admission_open=True, runtime_generation=7),
        _window=SimpleNamespace(screen_index=2),
        _context_menu_trace_model=None,
        _on_context_menu_visibility_changed=lambda *_args: None,
    )
    model = QuickContextMenuModel(screen_index=2, runtime_generation=7)
    other = QuickContextMenuModel(screen_index=2, runtime_generation=7)
    stale = QuickContextMenuModel(screen_index=2, runtime_generation=8)
    try:
        assert QuickSceneController.bind_context_menu_model(scene, model)
        assert root.writes == [("contextMenuModel", model)]
        root.writes.clear()
        for _ in range(24):
            assert QuickSceneController.bind_context_menu_model(scene, model)
        assert root.writes == []
        assert QuickSceneController.bind_context_menu_model(scene, other)
        assert root.writes == [("contextMenuModel", other)]
        root.writes.clear()
        assert not QuickSceneController.bind_context_menu_model(scene, stale)
        scene._readiness.admission_open = False
        assert not QuickSceneController.bind_context_menu_model(scene, model)
        assert root.writes == []
        assert scene._context_menu_trace_model is other
    finally:
        for candidate in (model, other, stale):
            candidate.deleteLater()
