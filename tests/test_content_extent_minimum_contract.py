"""Width/height handles stop where each card can still reflow.

Runtime Edit and Settings Arrange floor a content-extent box at the family's
declared ``content_extent_minimum_size``. A card whose own model or QML clamps
its reflow box above that floor would be shrunk as a whole inside a smaller
box, leaving dead space the operator never asked for (Arrange cannot show it).
Each family is laid out by Qt's polish pass on a never-shown render-control
window, as Arrange's size meter does.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict

import pytest
from PySide6.QtCore import QUrl
from PySide6.QtQml import QQmlComponent, QQmlEngine
from PySide6.QtQuick import QQuickRenderControl, QQuickWindow

from core.settings.default_settings import DEFAULT_SETTINGS
from core.settings.models import ShadowSettings
from rendering.quick.bootstrap import quick_qml_root
from rendering.quick.widgets.family_binder import default_ordinary_family_adapters
from rendering.quick.widgets.host import apply_overlay_card_style
from rendering.quick.widgets.registry import ordinary_widget_family_component
from rendering.widget_descriptors import get_widget_runtime_descriptors


def _content_extent_descriptors():
    descriptors = get_widget_runtime_descriptors()
    values = descriptors.values() if isinstance(descriptors, dict) else descriptors
    return [descriptor for descriptor in values if descriptor.content_extent_axes]


@pytest.mark.qt
def test_every_content_extent_floor_is_one_the_card_really_reflows_into(qt_app) -> None:
    from ui.font_registration import ensure_custom_fonts

    ensure_custom_fonts()
    widgets = deepcopy(DEFAULT_SETTINGS["widgets"])
    engine = QQmlEngine()
    engine.addImportPath(str(quick_qml_root()))
    control = QQuickRenderControl()
    window = QQuickWindow(control)  # bound to the render control: never shown
    adapters = default_ordinary_family_adapters()
    components: dict[str, QQmlComponent] = {}
    checked = []
    try:
        for descriptor in _content_extent_descriptors():
            widget_id = descriptor.widget_id
            adapter = next((a for a in adapters if a.presentation_component(widget_id)), None)
            if adapter is None:
                continue
            family = ordinary_widget_family_component(adapter.presentation_component(widget_id))
            component = components.setdefault(family.family_id, QQmlComponent(
                engine, QUrl.fromLocalFile(str(quick_qml_root() / family.qml_filename))))
            model = adapter.presentation_model(widget_id=widget_id, widgets_config=widgets,
                                               shadow_values=asdict(ShadowSettings.from_widgets_map(widgets)))
            model.set_content_extent(1, 1)  # far below any floor: the card clamps to its own
            item = component.createWithInitialProperties({family.model_property: model})
            assert item is not None, (widget_id, component.errorString())
            item.setParent(engine)
            model.setParent(item)
            apply_overlay_card_style(item, adapter.presentation_card_style(model))
            item.setParentItem(window.contentItem())
            for _ in range(6):
                item.setWidth(item.property("preferredContentWidth"))
                item.setHeight(item.property("preferredContentHeight"))
                control.polishItems()
            reflow = (item.property("preferredContentWidth"), item.property("preferredContentHeight"))
            item.setParentItem(None)
            item.deleteLater()
            declared = descriptor.content_extent_minimum_size
            assert declared is not None, f"{widget_id} declares no width/height floor; its card stops at {reflow}"
            if not descriptor.content_extent_floor_at_authored_size:  # those floor at their natural size at runtime
                assert reflow[0] <= declared[0] + 0.5 and reflow[1] <= declared[1] + 0.5, (widget_id, declared, reflow)
            checked.append(widget_id)
        assert checked
    finally:
        engine.deleteLater()
        window.deleteLater()
        control.deleteLater()
        qt_app.processEvents()
