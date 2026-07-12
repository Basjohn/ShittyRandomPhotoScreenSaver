from __future__ import annotations

import inspect
from dataclasses import replace

import pytest
import widgets.steam_components as steam_components
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPixmap

from widgets.steam_card_widget import STEAM_CARD_DEFINITIONS, SteamCardWidget
from widgets.steam_components import (
    ACHIEVEMENT_PULSE_AUTHORED_SIZE,
    ACHIEVEMENT_PULSE_SQUARE_AUTHORED_SIZE,
    ACHIEVEMENT_SQUARE_ARTWORK_DEFAULT,
    ACHIEVEMENT_SQUARE_ARTWORK_MAX,
    ACHIEVEMENT_SQUARE_ARTWORK_MIN,
    STEAM_CARD_AUTHORED_SIZE,
    SteamCardField,
    _draw_bottom_right_outside_shadow,
    achievement_capsule_geometry,
    achievement_field_rail_count,
    achievement_pulse_authored_size,
    build_mock_steam_view_model,
    build_steam_connect_required_view_model,
    layout_steam_card,
    render_steam_card,
    with_long_title,
    with_unavailable_state,
)


pytestmark = pytest.mark.usefixtures("qt_app")


def _assert_inside(outer: QRectF, inner: QRectF) -> None:
    if inner.isNull():
        return
    expanded = QRectF(outer).adjusted(-0.75, -0.75, 0.75, 0.75)
    assert expanded.contains(inner), f"{inner} escaped {outer}"


def _achievement_target(*, artwork_shape: str = "wide", field_count: int = 5) -> QRectF:
    capsule_height, capsule_gap = achievement_capsule_geometry(
        font_family="Inter",
        capsule_font_size=12,
    )
    size = achievement_pulse_authored_size(
        show_artwork=True,
        artwork_shape=artwork_shape,
        field_rail_count=achievement_field_rail_count(
            field_count,
            double_capsules=False,
        ),
        capsule_height=capsule_height,
        capsule_gap=capsule_gap,
    )
    return QRectF(0, 0, size.width(), size.height())


def _render_to_pixmap(
    model,
    width: int,
    height: int,
    *,
    dpr: float = 1.0,
    artwork_image: QImage | None = None,
    **render_options,
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
            artwork_image=artwork_image,
            **render_options,
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
            for _field_id, rect, _rail in layout.field_detail_rects:
                _assert_inside(geometry, rect)


def test_steam_header_layout_reserves_room_for_long_card_titles() -> None:
    layout = layout_steam_card(
        build_mock_steam_view_model("achievement_pulse"),
        _achievement_target(),
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
    wide_target = _achievement_target(artwork_shape="wide")
    square_target = _achievement_target(artwork_shape="square")

    wide = layout_steam_card(model, wide_target, artwork_shape="wide")
    square = layout_steam_card(model, square_target, artwork_shape="square")
    smallest = layout_steam_card(
        model,
        square_target,
        artwork_shape="square",
        square_artwork_size=ACHIEVEMENT_SQUARE_ARTWORK_MIN - 100,
    )
    largest = layout_steam_card(
        model,
        square_target,
        artwork_shape="square",
        square_artwork_size=ACHIEVEMENT_SQUARE_ARTWORK_MAX + 100,
    )
    hidden = layout_steam_card(model, wide_target, show_artwork=False)

    assert wide.art_rect.top() == wide.header_rect.top()
    assert square.art_rect.top() == square.header_rect.top()
    assert square.art_rect.right() == wide.art_rect.right()
    assert square.art_rect.width() == square.art_rect.height()
    assert square.art_rect.width() == ACHIEVEMENT_SQUARE_ARTWORK_DEFAULT
    assert smallest.art_rect.width() == ACHIEVEMENT_SQUARE_ARTWORK_MIN
    assert largest.art_rect.width() == ACHIEVEMENT_SQUARE_ARTWORK_MAX
    assert smallest.art_rect.topRight() == largest.art_rect.topRight()
    assert largest.art_rect.intersects(largest.header_rect) is False
    assert square.art_rect.center().x() == square.metric_rect.center().x()
    assert square.art_rect.bottom() < square.metric_rect.top()
    assert largest.metric_rect.bottom() < min(
        rect.top() for _field_id, rect, _rail in largest.field_rects
    )
    assert hidden.art_rect.isNull()
    assert hidden.title_rect.width() > wide.title_rect.width()


def test_achievement_pulse_double_capsules_give_every_field_an_aligned_value_rail() -> None:
    long_previous = "Dark Souls III: The Fire Fades Edition"
    model = replace(
        build_mock_steam_view_model("achievement_pulse"),
        fields=(
            SteamCardField("total", "Total", "13%"),
            SteamCardField("playtime", "Playtime", "39h"),
            SteamCardField("previous", "Previous", long_previous),
            SteamCardField("source", "Source", "Cache"),
        ),
    )
    target = QRectF(
        0,
        0,
        ACHIEVEMENT_PULSE_SQUARE_AUTHORED_SIZE.width(),
        ACHIEVEMENT_PULSE_SQUARE_AUTHORED_SIZE.height(),
    )

    doubled = layout_steam_card(
        model,
        target,
        artwork_shape="square",
        double_capsules=True,
    )
    compact = layout_steam_card(
        model,
        target,
        artwork_shape="square",
        double_capsules=False,
    )
    short = layout_steam_card(
        replace(
            model,
            fields=tuple(
                replace(field, value="Celeste") if field.field_id == "previous" else field
                for field in model.fields
            ),
        ),
        target,
        artwork_shape="square",
        double_capsules=True,
    )

    assert [field_id for field_id, _rect, _rail in doubled.field_detail_rects] == [
        "total",
        "playtime",
        "previous",
        "source",
    ]
    assert compact.field_detail_rects == ()
    assert len(short.field_detail_rects) == len(short.field_rects) == 4
    detail_by_id = {
        field_id: rect for field_id, rect, _rail in doubled.field_detail_rects
    }
    for field_id, top_rect, _rail in doubled.field_rects:
        detail_rect = detail_by_id[field_id]
        assert top_rect.x() == detail_rect.x()
        assert top_rect.width() == detail_rect.width()
        assert detail_rect.top() - top_rect.bottom() == pytest.approx(6.0 * doubled.scale)
    all_rects = [rect for _field_id, rect, _rail in doubled.field_rects + doubled.field_detail_rects]
    for index, rect in enumerate(all_rects):
        assert all(not rect.intersects(other) for other in all_rects[index + 1:])


def test_achievement_pulse_double_capsule_layout_has_pre_application_measurement_fallback(monkeypatch) -> None:
    model = replace(
        build_mock_steam_view_model("achievement_pulse"),
        fields=(
            SteamCardField("previous", "Previous", "A Very Long Previous Game Name That Needs Its Own Rail"),
        ),
    )
    monkeypatch.setattr(steam_components, "_gui_application_available", lambda: False)

    layout = layout_steam_card(
        model,
        QRectF(0, 0, ACHIEVEMENT_PULSE_AUTHORED_SIZE.width(), ACHIEVEMENT_PULSE_AUTHORED_SIZE.height()),
        double_capsules=True,
    )

    assert tuple(field_id for field_id, _rect, _rail in layout.field_detail_rects) == ("previous",)


def test_achievement_pulse_double_capsule_renders_label_above_fitted_full_value(monkeypatch) -> None:
    calls: list[tuple[str, int, Qt.AlignmentFlag | Qt.TextFlag]] = []
    original = steam_components._draw_elided_text

    def _capture(painter, rect, text, *, color, font, flags=Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, shadow=True):
        calls.append((text, font.pointSize(), flags))
        return original(painter, rect, text, color=color, font=font, flags=flags, shadow=shadow)

    monkeypatch.setattr(steam_components, "_draw_elided_text", _capture)
    long_previous = "DARK SOULS III: THE FIRE FADES EDITION"
    long_selection = "RECENT SELECTION WITH A VERY LONG DESCRIPTION"
    model = replace(
        build_mock_steam_view_model("achievement_pulse"),
        fields=(
            SteamCardField("total", "Total", "13%"),
            SteamCardField("playtime", "Playtime", "39h"),
            SteamCardField("previous", "Previous", long_previous),
            SteamCardField("selected", "Selected", long_selection),
        ),
    )
    pixmap = QPixmap(540, 318)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    try:
        render_steam_card(
            painter,
            model,
            QRectF(0, 0, 540, 318),
            artwork_shape="square",
            double_capsules=True,
        )
    finally:
        painter.end()

    label_call = next(call for call in calls if call[0] == "PREVIOUSLY")
    selected_label_call = next(call for call in calls if call[0] == "SELECTED")
    value_call = next(call for call in calls if call[0] == long_previous)
    assert label_call[2] & Qt.AlignmentFlag.AlignHCenter
    assert selected_label_call[2] & Qt.AlignmentFlag.AlignHCenter
    assert value_call[2] & Qt.AlignmentFlag.AlignHCenter
    assert value_call[1] < label_call[1]


def test_achievement_capsule_font_size_grows_capsules_and_authored_card_without_overlap() -> None:
    model = replace(
        build_mock_steam_view_model("achievement_pulse"),
        fields=(
            SteamCardField("total", "Total", "13%"),
            SteamCardField("playtime", "Playtime", "39h"),
            SteamCardField("previous", "Previous", "Soulstone Survivors"),
            SteamCardField("source", "Source", "Cache"),
        ),
    )
    target = QRectF(0, 0, 540, 600)
    normal = layout_steam_card(
        model,
        target,
        double_capsules=True,
        capsule_font_size=12,
    )
    large = layout_steam_card(
        model,
        target,
        double_capsules=True,
        capsule_font_size=28,
    )

    normal_height = normal.field_rects[0][1].height() / normal.scale
    large_height = large.field_rects[0][1].height() / large.scale
    assert large_height > normal_height
    assert large.authored_rect.height() > normal.authored_rect.height()
    all_rects = [rect for _field_id, rect, _rail in large.field_rects + large.field_detail_rects]
    for index, rect in enumerate(all_rects):
        assert large.authored_rect.contains(rect)
        assert all(not rect.intersects(other) for other in all_rects[index + 1:])


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

    assert len(layout.latest_unlock_rects) == 5
    assert layout.latest_unlock_rects[0].height() > layout.latest_unlock_rects[1].height()
    assert max(rect.bottom() for _field_id, rect, _rail in one_rail.field_rects) >= 274.0
    assert layout.status_rect.isNull()


def test_latest_achievement_artwork_uses_dead_space_without_reflow() -> None:
    model = replace(
        build_mock_steam_view_model("achievement_pulse"),
        latest_unlock_icon_url="https://steamcdn-a.akamaihd.net/latest.jpg",
    )
    target = _achievement_target(artwork_shape="square")

    square = layout_steam_card(
        model,
        target,
        artwork_shape="square",
        show_latest_artwork=True,
    )
    hidden = layout_steam_card(
        model,
        target,
        artwork_shape="square",
        show_latest_artwork=False,
    )

    assert square.latest_unlock_art_rect.width() == 40.0
    assert square.latest_unlock_art_rect.height() == 40.0
    assert square.latest_unlock_art_rect.top() == square.latest_unlock_rects[0].top()
    assert 5.0 <= square.latest_unlock_art_rect.left() - square.latest_unlock_rects[0].right() <= 12.0
    assert square.latest_unlock_art_rect.center().x() < square.title_rect.right()
    assert square.latest_unlock_art_rect.right() < square.art_rect.left()
    assert square.title_rect == hidden.title_rect
    assert square.header_rect == hidden.header_rect
    assert square.art_rect == hidden.art_rect
    assert square.metric_rect == hidden.metric_rect
    assert square.field_rects == hidden.field_rects
    assert hidden.latest_unlock_art_rect.isNull()
    assert all(
        not rect.intersects(square.latest_unlock_art_rect)
        for rect in square.latest_unlock_rects
    )


def test_latest_achievement_artwork_paints_inside_its_framed_slot() -> None:
    model = replace(
        build_mock_steam_view_model("achievement_pulse"),
        latest_unlock_icon_url="https://steamcdn-a.akamaihd.net/latest.jpg",
    )
    icon = QImage(64, 64, QImage.Format.Format_ARGB32_Premultiplied)
    icon.fill(QColor("#2a78c5"))
    pixmap, layout = _render_to_pixmap(
        model,
        540,
        290,
        show_latest_artwork=True,
        latest_artwork_image=icon,
    )

    pixel = pixmap.toImage().pixelColor(
        int(layout.latest_unlock_art_rect.center().x()),
        int(layout.latest_unlock_art_rect.center().y()),
    )
    assert pixel.name() == "#2a78c5"


def test_achievement_pulse_artwork_paints_its_local_image_after_card_content() -> None:
    model = build_mock_steam_view_model("achievement_pulse")
    artwork = QImage(360, 164, QImage.Format.Format_ARGB32_Premultiplied)
    artwork.fill(QColor("#714c3e"))
    pixmap, layout = _render_to_pixmap(model, 540, 290, artwork_image=artwork)

    pixel = pixmap.toImage().pixelColor(int(layout.art_rect.center().x()), int(layout.art_rect.center().y()))
    assert pixel.name() == "#714c3e"


def test_achievement_pulse_square_artwork_cover_fills_from_portrait_source() -> None:
    model = build_mock_steam_view_model("achievement_pulse")
    artwork = QImage(100, 300, QImage.Format.Format_ARGB32_Premultiplied)
    artwork.fill(QColor("#c43b36"))
    painter = QPainter(artwork)
    try:
        painter.fillRect(0, 100, 100, 100, QColor("#38a169"))
        painter.fillRect(0, 200, 100, 100, QColor("#3769b0"))
    finally:
        painter.end()

    pixmap = QPixmap(540, 318)
    pixmap.fill(Qt.GlobalColor.transparent)
    card_painter = QPainter(pixmap)
    try:
        layout = render_steam_card(
            card_painter,
            model,
            QRectF(0, 0, 540, 318),
            artwork_image=artwork,
            artwork_shape="square",
        )
    finally:
        card_painter.end()

    rendered = pixmap.toImage()
    center_y = int(layout.art_rect.center().y())
    left = rendered.pixelColor(int(layout.art_rect.left() + 3), center_y)
    center = rendered.pixelColor(int(layout.art_rect.center().x()), center_y)
    right = rendered.pixelColor(int(layout.art_rect.right() - 3), center_y)
    assert left.name() == "#38a169"
    assert center.name() == "#38a169"
    assert right.name() == "#38a169"


def test_achievement_pulse_runtime_artwork_cache_is_dpr_aware(qt_app) -> None:
    widget = SteamCardWidget(
        definition=STEAM_CARD_DEFINITIONS["achievement_pulse"],
        achievement_artwork_shape="square",
    )
    try:
        source = QImage(100, 300, QImage.Format.Format_ARGB32_Premultiplied)
        source.fill(QColor("#c43b36"))
        source_painter = QPainter(source)
        try:
            source_painter.fillRect(0, 100, 100, 100, QColor("#38a169"))
            source_painter.fillRect(0, 200, 100, 100, QColor("#3769b0"))
        finally:
            source_painter.end()
        widget._achievement_artwork = source

        first = widget._scaled_achievement_artwork(QRectF(0, 0, 180, 180), 2.0)
        second = widget._scaled_achievement_artwork(QRectF(0, 0, 180, 180), 2.0)

        assert (first.width(), first.height()) == (360, 360)
        assert first.devicePixelRatio() == 2.0
        assert first.pixelColor(first.width() // 2, first.height() // 2).name() == "#38a169"
        assert second.cacheKey() == first.cacheKey()
    finally:
        widget.deleteLater()


def test_achievement_pulse_capsule_shadow_is_exclusively_bottom_right(qt_app) -> None:
    image = QImage(220, 90, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    try:
        _draw_bottom_right_outside_shadow(
            painter,
            QRectF(20, 20, 160, 40),
            radius=8.0,
            scale=1.0,
        )
    finally:
        painter.end()

    assert image.pixelColor(18, 18).alpha() == 0
    assert image.pixelColor(182, 62).alpha() > 0


def test_achievement_pulse_capsules_and_latest_unlocks_use_authored_text_alignment(monkeypatch) -> None:
    calls: list[tuple[str, Qt.AlignmentFlag | Qt.TextFlag]] = []
    original = steam_components._draw_elided_text

    def _capture(painter, rect, text, *, color, font, flags=Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, shadow=True):
        calls.append((text, flags))
        return original(painter, rect, text, color=color, font=font, flags=flags, shadow=shadow)

    monkeypatch.setattr(steam_components, "_draw_elided_text", _capture)
    model = build_mock_steam_view_model("achievement_pulse")
    pixmap, _layout = _render_to_pixmap(model, 540, 290)

    assert not pixmap.isNull()
    assert ("TOTAL", Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter) in calls
    capsule_labels = {"TOTAL", "PLAYTIME", "PREVIOUS", "SOURCE", "SELECTED"}
    assert all(text not in {f"{label}:" for label in capsule_labels} for text, _flags in calls)
    value_flags = next(flags for text, flags in calls if text == "67%")
    assert value_flags & Qt.AlignmentFlag.AlignRight
    assert all(text != "Total: 67%" for text, _flags in calls)
    assert all(not text.startswith("Latest:") for text, _flags in calls)
    assert all(not text.startswith(("2. ", "3. ", "4. ", "5. ")) for text, _flags in calls)


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
