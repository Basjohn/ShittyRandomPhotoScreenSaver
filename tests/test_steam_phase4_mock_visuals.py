from __future__ import annotations

import inspect
from dataclasses import replace

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPixmap

from widgets.steam_card_widget import STEAM_CARD_DEFINITIONS, SteamCardWidget
from widgets.steam_components import (
    ACHIEVEMENT_PULSE_AUTHORED_SIZE,
    STEAM_CARD_AUTHORED_SIZE,
    build_mock_steam_view_model,
    build_steam_connect_required_view_model,
    layout_steam_card,
    render_steam_card,
    with_long_title,
    with_unavailable_state,
)


def _assert_inside(outer: QRectF, inner: QRectF) -> None:
    if inner.isNull():
        return
    expanded = QRectF(outer).adjusted(-0.75, -0.75, 0.75, 0.75)
    assert expanded.contains(inner), f"{inner} escaped {outer}"


def _render_to_pixmap(model, width: int, height: int, *, dpr: float = 1.0, artwork_image: QImage | None = None):
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
            artwork_image=artwork_image,
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
        build_mock_steam_view_model("achievement_pulse"),
        with_long_title(build_mock_steam_view_model("achievement_pulse")),
        with_unavailable_state(build_mock_steam_view_model("achievement_pulse")),
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
        build_mock_steam_view_model("achievement_pulse"),
        QRectF(0, 0, ACHIEVEMENT_PULSE_AUTHORED_SIZE.width(), ACHIEVEMENT_PULSE_AUTHORED_SIZE.height()),
    )

    assert layout.header_rect.width() >= 250.0
    assert layout.logo_rect.width() >= 28.0
    assert layout.header_text_rect.width() >= 180.0
    assert layout.title_rect.width() >= 300.0


def test_achievement_pulse_authored_layout_keeps_all_data_regions_separate() -> None:
    model = build_mock_steam_view_model("achievement_pulse")
    layout = layout_steam_card(
        model,
        QRectF(0, 0, ACHIEVEMENT_PULSE_AUTHORED_SIZE.width(), ACHIEVEMENT_PULSE_AUTHORED_SIZE.height()),
    )
    field_rects = [rect for _field_id, rect, _rail in layout.field_rects]

    assert layout.art_rect.intersects(layout.title_rect) is False
    assert layout.art_rect.intersects(layout.subtitle_rect) is False
    assert layout.metric_rect.intersects(layout.status_rect) is False
    assert len(field_rects) == len(model.enabled_field_ids)
    for index, rect in enumerate(field_rects):
        assert all(not rect.intersects(other) for other in field_rects[index + 1:])


def test_achievement_pulse_artwork_shapes_follow_authored_alignment_contract() -> None:
    model = build_mock_steam_view_model("achievement_pulse")
    target = QRectF(
        0,
        0,
        ACHIEVEMENT_PULSE_AUTHORED_SIZE.width(),
        ACHIEVEMENT_PULSE_AUTHORED_SIZE.height(),
    )

    wide = layout_steam_card(model, target, artwork_shape="wide")
    square = layout_steam_card(model, target, artwork_shape="square")
    hidden = layout_steam_card(model, target, show_artwork=False)

    assert wide.art_rect.top() == wide.header_rect.top()
    assert square.art_rect.top() == square.title_rect.top()
    assert square.art_rect.width() == square.art_rect.height()
    assert hidden.art_rect.isNull()
    assert hidden.title_rect.width() > wide.title_rect.width()


def test_achievement_pulse_latest_unlocks_and_fields_use_available_vertical_space() -> None:
    model = build_mock_steam_view_model("achievement_pulse")
    target = QRectF(
        0,
        0,
        ACHIEVEMENT_PULSE_AUTHORED_SIZE.width(),
        ACHIEVEMENT_PULSE_AUTHORED_SIZE.height(),
    )
    layout = layout_steam_card(model, target)
    one_rail = layout_steam_card(replace(model, fields=model.fields[:3]), target)

    assert len(layout.latest_unlock_rects) == 3
    assert layout.latest_unlock_rects[0].height() > layout.latest_unlock_rects[1].height()
    assert max(rect.bottom() for _field_id, rect, _rail in one_rail.field_rects) >= 274.0
    assert layout.status_rect.isNull()


def test_achievement_pulse_artwork_paints_its_local_image_after_card_content() -> None:
    model = build_mock_steam_view_model("achievement_pulse")
    artwork = QImage(360, 164, QImage.Format.Format_ARGB32_Premultiplied)
    artwork.fill(QColor("#714c3e"))
    pixmap, layout = _render_to_pixmap(model, 540, 290, artwork_image=artwork)

    pixel = pixmap.toImage().pixelColor(int(layout.art_rect.center().x()), int(layout.art_rect.center().y()))
    assert pixel.name() == "#714c3e"


def test_achievement_pulse_square_artwork_uses_centered_cover_crop() -> None:
    model = build_mock_steam_view_model("achievement_pulse")
    artwork = QImage(300, 100, QImage.Format.Format_ARGB32_Premultiplied)
    artwork.fill(QColor("#c43b36"))
    painter = QPainter(artwork)
    try:
        painter.fillRect(100, 0, 100, 100, QColor("#38a169"))
    finally:
        painter.end()

    pixmap = QPixmap(540, 290)
    pixmap.fill(Qt.GlobalColor.transparent)
    card_painter = QPainter(pixmap)
    try:
        layout = render_steam_card(
            card_painter,
            model,
            QRectF(0, 0, 540, 290),
            artwork_image=artwork,
            artwork_shape="square",
        )
    finally:
        card_painter.end()

    center = pixmap.toImage().pixelColor(int(layout.art_rect.center().x()), int(layout.art_rect.center().y()))
    assert center.name() == "#38a169"


def test_achievement_pulse_runtime_artwork_cache_is_dpr_aware(qt_app) -> None:
    widget = SteamCardWidget(
        definition=STEAM_CARD_DEFINITIONS["achievement_pulse"],
        achievement_artwork_shape="square",
    )
    try:
        source = QImage(300, 100, QImage.Format.Format_ARGB32_Premultiplied)
        source.fill(QColor("#c43b36"))
        source_painter = QPainter(source)
        try:
            source_painter.fillRect(100, 0, 100, 100, QColor("#38a169"))
        finally:
            source_painter.end()
        widget._achievement_artwork = source

        first = widget._scaled_achievement_artwork(QRectF(0, 0, 118, 118), 2.0)
        second = widget._scaled_achievement_artwork(QRectF(0, 0, 118, 118), 2.0)

        assert (first.width(), first.height()) == (236, 236)
        assert first.devicePixelRatio() == 2.0
        assert first.pixelColor(first.width() // 2, first.height() // 2).name() == "#38a169"
        assert second.cacheKey() == first.cacheKey()
    finally:
        widget.deleteLater()


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
