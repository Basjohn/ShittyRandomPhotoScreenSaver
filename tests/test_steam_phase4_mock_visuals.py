from __future__ import annotations

import inspect
import pytest
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QPainter, QPixmap

from widgets.steam_card_widget import STEAM_CARD_DEFINITIONS, SteamCardWidget
from widgets.steam_card_models import (
    build_mock_steam_view_model,
    build_steam_connect_required_view_model,
    with_long_title,
    with_unavailable_state,
)
from widgets.steam_components import (
    STEAM_CARD_AUTHORED_SIZE,
    layout_steam_card,
    render_steam_card,
)


pytestmark = pytest.mark.usefixtures("qt_app")


def _assert_inside(outer: QRectF, inner: QRectF) -> None:
    if inner.isNull():
        return
    expanded = QRectF(outer).adjusted(-0.75, -0.75, 0.75, 0.75)
    assert expanded.contains(inner), f"{inner} escaped {outer}"


def _render_to_pixmap(
    model,
    width: int,
    height: int,
    *,
    dpr: float = 1.0,
):
    pixmap = QPixmap(max(1, int(width * dpr)), max(1, int(height * dpr)))
    pixmap.setDevicePixelRatio(dpr)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    try:
        layout = render_steam_card(
            painter,
            model,
            QRectF(0, 0, width, height),
            font_family="Inter",
            font_size=14,
            dpr=dpr,
        )
    finally:
        painter.end()
    return pixmap, layout


def test_steam_mock_view_models_are_deterministic_and_cover_all_cards() -> None:
    for widget_id in STEAM_CARD_DEFINITIONS:
        first = build_mock_steam_view_model(widget_id)
        second = build_mock_steam_view_model(widget_id)

        assert first == second
        assert first.card_id == widget_id
        assert len(first.enabled_field_ids) >= 5
        assert first.content_fingerprint() == second.content_fingerprint()


def test_steam_custom_scaling_does_not_change_field_count_or_rails() -> None:
    model = build_mock_steam_view_model("steam_progress")
    normal = layout_steam_card(model, QRectF(0, 0, 420, 180))
    tight = layout_steam_card(model, QRectF(0, 0, 210, 90))
    tall = layout_steam_card(model, QRectF(0, 0, 260, 260))

    assert normal.visible_field_ids == model.enabled_field_ids
    assert tight.visible_field_ids == normal.visible_field_ids
    assert tall.visible_field_ids == normal.visible_field_ids
    assert tight.rails == normal.rails
    assert tall.rails == normal.rails
    assert tight.scale < normal.scale
    assert tall.scale < normal.scale


def test_steam_layout_rects_stay_inside_target_for_phase4_matrix() -> None:
    geometries = (
        QRectF(0, 0, 420, 180),
        QRectF(0, 0, 640, 240),
        QRectF(0, 0, 250, 130),
        QRectF(0, 0, 210, 90),
        QRectF(0, 0, 280, 300),
    )
    variants = (
        build_mock_steam_view_model("steam_progress"),
        with_long_title(build_mock_steam_view_model("steam_progress")),
        with_unavailable_state(build_mock_steam_view_model("steam_progress")),
    )

    for model in variants:
        for geometry in geometries:
            layout = layout_steam_card(model, geometry)
            for rect in (
                layout.authored_rect,
                layout.content_rect,
                layout.header_rect,
                layout.art_rect,
                layout.title_rect,
                layout.subtitle_rect,
                layout.metric_rect,
                layout.status_rect,
            ):
                _assert_inside(geometry, rect)
            for _field_id, rect, _rail in layout.field_rects:
                _assert_inside(geometry, rect)


def test_steam_header_layout_reserves_room_for_long_card_titles() -> None:
    layout = layout_steam_card(
        build_mock_steam_view_model("steam_progress"),
        QRectF(0, 0, 420, 180),
    )

    assert layout.header_rect.width() >= 250.0
    assert layout.logo_rect.width() >= 28.0
    assert layout.header_text_rect.width() >= 180.0
    assert layout.title_rect.width() >= 270.0


def test_steam_render_helper_handles_dpr_and_fixture_variants(qt_app) -> None:
    for widget_id in STEAM_CARD_DEFINITIONS:
        pixmap, layout = _render_to_pixmap(build_mock_steam_view_model(widget_id), 420, 180, dpr=1.0)
        assert not pixmap.isNull()
        assert layout.visible_field_ids == build_mock_steam_view_model(widget_id).enabled_field_ids

    model = with_long_title(build_mock_steam_view_model("friend_pulse"))
    pixmap_1x, layout_1x = _render_to_pixmap(model, 420, 180, dpr=1.0)
    pixmap_2x, layout_2x = _render_to_pixmap(model, 420, 180, dpr=2.0)
    unavailable_pixmap, unavailable_layout = _render_to_pixmap(
        with_unavailable_state(model),
        250,
        130,
        dpr=1.25,
    )

    assert not pixmap_1x.isNull()
    assert not pixmap_2x.isNull()
    assert not unavailable_pixmap.isNull()
    assert layout_1x.visible_field_ids == model.enabled_field_ids
    assert layout_2x.visible_field_ids == model.enabled_field_ids
    assert unavailable_layout.visible_field_ids == model.enabled_field_ids
    assert layout_1x.paint_fingerprint != layout_2x.paint_fingerprint
    assert layout_1x.paint_fingerprint != unavailable_layout.paint_fingerprint


def test_steam_connect_required_prompt_uses_prompt_layout_without_mock_artifact(qt_app) -> None:
    model = build_steam_connect_required_view_model("steam_progress")
    pixmap, layout = _render_to_pixmap(model, 420, 180, dpr=1.0)

    assert not pixmap.isNull()
    assert layout.visible_field_ids == ()
    assert layout.art_rect.isNull()
    assert layout.action_rects
    assert layout.title_rect.center().x() == layout.authored_rect.center().x()
    assert layout.status_rect.center().x() == layout.authored_rect.center().x()


def test_steam_card_widget_paints_mock_model_without_provider_or_timer_hooks(qt_app) -> None:
    forbidden_sources = (
        "core.steam.backend",
        "core.steam.cache",
        "core.steam.assets",
        "core.steam.credentials",
        "QTimer",
        "singleShot",
    )
    source = "\n".join(
        (
            inspect.getsource(SteamCardWidget.__init__),
            inspect.getsource(SteamCardWidget._activate_impl),
            inspect.getsource(SteamCardWidget._start_widget_fade_in),
            inspect.getsource(SteamCardWidget._paint_before_native_text),
            inspect.getsource(SteamCardWidget.set_view_model),
        )
    )
    for forbidden in forbidden_sources:
        assert forbidden not in source

    widget = SteamCardWidget(definition=STEAM_CARD_DEFINITIONS["abandonment_issues"])
    try:
        widget.resize(int(STEAM_CARD_AUTHORED_SIZE.width()), int(STEAM_CARD_AUTHORED_SIZE.height()))
        pixmap = QPixmap(widget.size())
        pixmap.fill(Qt.GlobalColor.transparent)
        widget.render(pixmap)
        layout = widget.last_layout()

        assert widget.text() == ""
        assert layout is not None
        assert layout.visible_field_ids == widget._view_model.enabled_field_ids
    finally:
        widget.deleteLater()
