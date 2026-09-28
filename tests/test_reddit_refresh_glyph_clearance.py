"""Reddit's refresh glyph steps aside instead of drawing over its header.

The branded header never elides, so at a narrow CUSTOM width a long subreddit
name can reach the glyph slot. Laid out by Qt's polish pass on a never-shown
render-control window (the way Arrange's size meter lays cards out).
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict

import pytest
from PySide6.QtCore import QRectF, QUrl
from PySide6.QtQml import QQmlComponent, QQmlEngine
from PySide6.QtQuick import QQuickItem, QQuickRenderControl, QQuickWindow

from core.settings.default_settings import DEFAULT_SETTINGS
from core.settings.models import ShadowSettings
from rendering.quick.bootstrap import quick_qml_root
from rendering.quick.widgets.family_binder import default_ordinary_family_adapters
from rendering.quick.widgets.host import apply_overlay_card_style
from rendering.quick.widgets.registry import ordinary_widget_family_component


@pytest.mark.qt
def test_refresh_glyph_hides_only_when_the_header_would_reach_it(qt_app) -> None:
    from ui.font_registration import ensure_custom_fonts

    ensure_custom_fonts()
    engine = QQmlEngine()
    engine.addImportPath(str(quick_qml_root()))
    control = QQuickRenderControl()
    window = QQuickWindow(control)  # bound to the render control: never shown
    adapter = next(a for a in default_ordinary_family_adapters() if a.presentation_component("reddit"))
    family = ordinary_widget_family_component(adapter.presentation_component("reddit"))
    component = QQmlComponent(engine, QUrl.fromLocalFile(str(quick_qml_root() / family.qml_filename)))

    def layout(subreddit: str, width: int | None):
        widgets = deepcopy(DEFAULT_SETTINGS["widgets"])
        widgets["reddit"]["subreddit"] = subreddit  # TEST INPUT
        widgets["reddit"]["show_refresh_spiral"] = True
        model = adapter.presentation_model(widget_id="reddit", widgets_config=widgets,
                                           shadow_values=asdict(ShadowSettings.from_widgets_map(widgets)))
        if width is not None:
            model.set_content_extent(width, 700)
        item = component.createWithInitialProperties({family.model_property: model})
        assert item is not None, component.errorString()
        item.setParent(engine)
        model.setParent(item)
        apply_overlay_card_style(item, adapter.presentation_card_style(model))
        item.setParentItem(window.contentItem())
        for _ in range(6):
            item.setWidth(item.property("preferredContentWidth"))
            item.setHeight(item.property("preferredContentHeight"))
            control.polishItems()
        glyph = item.findChild(QQuickItem, "redditRefreshTarget")
        header = item.findChild(QQuickItem, "redditHeaderFrame")
        glyph_rect = glyph.mapRectToItem(item, QRectF(0, 0, glyph.width(), glyph.height()))
        header_rect = header.mapRectToItem(item, QRectF(0, 0, header.width(), header.height()))
        result = (glyph.isVisible(), glyph_rect.intersects(header_rect))
        item.setParentItem(None)
        item.deleteLater()
        return result

    try:
        long_name, short_name = "averyveryverylongsubredditname", "pics"
        assert layout(long_name, None) == (True, False)  # the authored width reserves the slot
        visible, _overlap = layout(long_name, 300)
        assert not visible  # the header would reach it: the glyph steps aside
        assert layout(short_name, 300) == (True, False)  # room to spare: it stays
    finally:
        engine.deleteLater()
        window.deleteLater()
        control.deleteLater()
        qt_app.processEvents()
