"""The Studio's switch rows are real checkboxes that a real click toggles (6 Nov: "Tilt Shift is unclickable").

Every switch row of every Studio is the one QML ``SwitchRow``. It was a ``Row``, which positions each visible child in
sequence and ignores its ``x``: the click area landed past the end of the label, so no switch in any Studio could be
clicked (the bridge-level commit tests could not see it). These tests click the rendered rows through the real
window events of a never-shown offscreen surface (nothing reaches the operator's screen) and read the canonical store.
"""
from __future__ import annotations

from PySide6.QtCore import QCoreApplication, QEvent, QPointF, Qt
from PySide6.QtGui import QMouseEvent

from tests.test_waveform_studio_lifecycle import (          # noqa: F401  (fixtures and the light adapter)
    LightAdapter, MODE, _reset_counts, _surfaces, dialog_tab, no_gl_checks, settings_manager)


def _walk(item):
    for child in item.childItems():
        yield child
        yield from _walk(child)


def _row_item(surface, property_id):
    for item in _walk(surface.host.root):
        if item.objectName() == "inspectorRow":
            data = item.property("rowData")
            if data and data.get("id") == property_id:
                return item
    return None


def _scroll_into_view(row):
    """Bring the row inside the inspector's scroll area (the offscreen window is small)."""
    flick = row.parentItem()
    while flick is not None and flick.property("contentY") is None:
        flick = flick.parentItem()
    if flick is not None:
        offset = row.mapToItem(flick, QPointF(0.0, 0.0)).y()
        flick.setProperty("contentY", max(0.0, flick.property("contentY") + offset - flick.height() / 3.0))


def _press(surface, scene_point):
    for kind in (QEvent.Type.MouseButtonPress, QEvent.Type.MouseButtonRelease):
        QCoreApplication.sendEvent(surface.window, QMouseEvent(
            kind, scene_point, scene_point, Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier))
    QCoreApplication.processEvents()
    surface.pump()


def _open(tab):
    from ui.studio.settings_link import open_mode_studio
    surfaces = []
    controller = open_mode_studio(tab, MODE, adapter=LightAdapter(),
                                  surface_factory=_surfaces(surfaces, size=(1400, 820)))
    surfaces[0].pump(3)
    return controller, surfaces[0]


def _show(controller, surface, prop):
    controller.bridge.setWorkspace(prop.workspace)
    surface.pump(4)
    row = _row_item(surface, prop.id)
    assert row is not None, prop.id
    _scroll_into_view(row)
    surface.pump(2)
    return row


def _hit(row):
    return next(item for item in _walk(row) if item.objectName() == "switchHit")


def _centre(item):
    return item.mapToScene(QPointF(item.width() / 2.0, item.height() / 2.0))


def _switches(controller):
    return [p for p in controller.session.schema.properties if p.instrument == "switch"]


def test_every_live_switch_row_toggles_on_a_real_click_and_saves(qt_app, dialog_tab, settings_manager, no_gl_checks):
    controller, surface = _open(dialog_tab()[1])
    bridge = controller.bridge
    clicked = []
    for prop in _switches(controller):
        if bridge.conditionHidden.get(prop.id):
            continue                                   # a condition that does not hold is covered below
        row = _show(controller, surface, prop)
        if not row.isVisible():
            continue                                   # a collapsed group: its rows are not on screen to click
        before = controller.session.get(prop.path)
        _press(surface, _centre(_hit(row)))
        assert controller.session.get(prop.path) is (not before), prop.id
        stored = settings_manager.get("widgets")["spotify_visualizer"]
        assert bool(stored[prop.path[0]]) is (not before), prop.id            # the canonical store holds it
        _press(surface, _centre(_hit(row)))
        assert controller.session.get(prop.path) is before, prop.id
        clicked.append(prop.id)
    conditional = [p.id for p in _switches(controller) if p.when]
    assert conditional, "the registry declares a conditional switch"
    assert set(conditional) & set(clicked), "a conditional switch whose condition holds is clickable"
    controller.close()


def test_hit_area_lies_inside_its_row_for_every_switch(qt_app, dialog_tab, no_gl_checks):
    """The defect itself: the click area sat past the row's right edge, outside anything the operator could click."""
    controller, surface = _open(dialog_tab()[1])
    seen = 0
    for prop in _switches(controller):
        if controller.bridge.conditionHidden.get(prop.id):
            continue
        row = _show(controller, surface, prop)
        hit = _hit(row)
        top_left = hit.mapToItem(row, QPointF(0.0, 0.0))
        assert top_left.x() <= 0.5 and top_left.y() <= 0.5, prop.id
        assert top_left.x() + hit.width() >= row.width() - 0.5, prop.id
        assert top_left.y() + hit.height() >= row.height() - 0.5, prop.id
        seen += 1
    assert seen
    controller.close()


def test_a_click_beside_the_row_changes_nothing_negative_control(qt_app, dialog_tab, no_gl_checks):
    controller, surface = _open(dialog_tab()[1])
    prop = next(p for p in _switches(controller) if p.when and not controller.bridge.conditionHidden.get(p.id))
    row = _show(controller, surface, prop)
    before = controller.session.get(prop.path)
    inside = _centre(_hit(row))
    _press(surface, QPointF(inside.x() + row.width(), inside.y()))      # right of the row: no switch there
    assert controller.session.get(prop.path) is before
    controller.close()


def test_conditional_switch_is_hidden_and_unclickable_while_its_condition_fails(qt_app, dialog_tab, no_gl_checks):
    from core.settings.visualizer_mode_settings import Choice, Toggle, require_mode_settings
    spec = require_mode_settings(MODE)
    toggle = next(c for c in spec.controls if isinstance(c, Toggle) and c.when)
    (key, accepted), = ((toggle.when,) if isinstance(toggle.when[0], str) else toggle.when)
    accepted = accepted if isinstance(accepted, tuple) else (accepted,)
    driver = spec.control(key)
    assert isinstance(driver, Choice)
    other = next(choice for choice in driver.choices if choice not in accepted)
    controller, surface = _open(dialog_tab()[1])
    bridge = controller.bridge
    prop = next(p for p in _switches(controller) if p.id == toggle.key)
    assert not bridge.conditionHidden.get(prop.id) and controller.session.get(prop.path) in (True, False)

    bridge.setWorkspace(prop.workspace)
    surface.pump(3)
    bridge.commitValue(key, 0, other)
    surface.pump(3)
    assert bridge.conditionHidden.get(prop.id) is True
    row = _row_item(surface, prop.id)
    assert row is not None and not row.isVisible()                    # hidden, so nothing to click

    bridge.commitValue(key, 0, accepted[0])
    surface.pump(3)
    assert not bridge.conditionHidden.get(prop.id)
    row = _show(controller, surface, prop)
    before = controller.session.get(prop.path)
    _press(surface, _centre(_hit(row)))
    assert controller.session.get(prop.path) is (not before)
    controller.close()
