"""Shared mock visual components for dev-gated Steam cards.

This module is intentionally provider-inert. It owns only immutable mock view
models, deterministic layout metrics, and painter helpers used before any
production Steam data path is wired into runtime cards.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import math
from typing import Iterable

from PySide6.QtCore import QRectF, QSizeF, Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontMetricsF,
    QGuiApplication,
    QImage,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)

from widgets.shadow_utils import draw_rounded_rect_border, draw_text_rect_with_shadow
from widgets.steam_card_models import (
    SteamCardField,
    SteamCardViewModel,
    build_mock_steam_view_model,
    build_steam_connect_required_view_model,
    with_long_title,
    with_unavailable_state,
)


STEAM_CARD_AUTHORED_SIZE = QSizeF(420.0, 180.0)
ACHIEVEMENT_PULSE_AUTHORED_SIZE = QSizeF(600.0, 290.0)
ACHIEVEMENT_PULSE_SQUARE_AUTHORED_SIZE = QSizeF(600.0, 318.0)
ACHIEVEMENT_PULSE_PORTRAIT_AUTHORED_SIZE = QSizeF(600.0, 334.0)
ACHIEVEMENT_SQUARE_ARTWORK_MIN = 140
ACHIEVEMENT_SQUARE_ARTWORK_DEFAULT = 140
ACHIEVEMENT_SQUARE_ARTWORK_MAX = 190
ACHIEVEMENT_PORTRAIT_ASPECT_RATIO = 1.4
ACHIEVEMENT_CAPSULE_FILL_RGBA = (199, 213, 224, 38)
ACHIEVEMENT_CAPSULE_BORDER_RGBA = (199, 213, 224, 145)
ACHIEVEMENT_CAPSULE_FONT_SIZE_MIN = 8
ACHIEVEMENT_CAPSULE_FONT_SIZE_DEFAULT = 12
ACHIEVEMENT_CAPSULE_FONT_SIZE_MAX = 32
ACHIEVEMENT_CAPSULE_BASE_HEIGHT = 26.0
ACHIEVEMENT_CAPSULE_BASE_GAP = 6.0
@dataclass(frozen=True)
class SteamCardLayout:
    """Resolved logical/display layout for one card paint pass."""

    target_rect: QRectF
    authored_rect: QRectF
    scale: float
    content_rect: QRectF
    header_rect: QRectF
    logo_rect: QRectF
    header_text_rect: QRectF
    art_rect: QRectF
    title_rect: QRectF
    subtitle_rect: QRectF
    metric_rect: QRectF
    status_rect: QRectF
    latest_unlock_rects: tuple[QRectF, ...]
    latest_unlock_art_rect: QRectF
    field_rects: tuple[tuple[str, QRectF, int], ...]
    field_detail_rects: tuple[tuple[str, QRectF, int], ...]
    visible_field_ids: tuple[str, ...]
    paint_fingerprint: tuple[object, ...]
    action_rects: tuple[tuple[str, QRectF], ...] = field(default_factory=tuple)
    info_rect: QRectF | None = None

    @property
    def rails(self) -> tuple[int, ...]:
        return tuple(
            sorted(
                {
                    rail
                    for _field_id, _rect, rail in self.field_rects + self.field_detail_rects
                }
            )
        )


def _crop_logo_pixmap_to_alpha_bounds(pixmap: QPixmap, path_hint: str | None = None) -> QPixmap:
    """Return a tight crop of the visible Steam glyph if a source has padding."""

    if pixmap.isNull():
        return pixmap
    try:
        from PIL import Image

        if path_hint:
            with Image.open(path_hint) as image:
                alpha = image.convert("RGBA").getchannel("A")
                bounds = alpha.getbbox()
            if bounds is None:
                return pixmap
            left, top, right, bottom = bounds
            cropped = pixmap.copy(left, top, max(1, right - left), max(1, bottom - top))
            return cropped if not cropped.isNull() else pixmap
    except Exception:
        return pixmap
    return pixmap


def _accent_color(model: SteamCardViewModel) -> QColor:
    color = QColor(model.accent)
    return color if color.isValid() else QColor("#66c0f4")


def _map_rect(rect: QRectF, origin_x: float, origin_y: float, scale: float) -> QRectF:
    return QRectF(
        origin_x + rect.x() * scale,
        origin_y + rect.y() * scale,
        rect.width() * scale,
        rect.height() * scale,
    )


def _enabled_fields(fields: Iterable[SteamCardField]) -> tuple[SteamCardField, ...]:
    return tuple(field for field in fields if field.enabled)


def normalize_achievement_square_artwork_size(value: object) -> int:
    """Clamp compact artwork width to the authored header/title envelope."""

    try:
        resolved = int(value)
    except (TypeError, ValueError):
        resolved = ACHIEVEMENT_SQUARE_ARTWORK_DEFAULT
    return max(ACHIEVEMENT_SQUARE_ARTWORK_MIN, min(ACHIEVEMENT_SQUARE_ARTWORK_MAX, resolved))


def normalize_achievement_artwork_shape(value: object) -> str:
    """Normalize Achievement Pulse artwork modes without collapsing portrait."""

    shape = str(value or "").strip().lower()
    return shape if shape in {"wide", "square", "portrait"} else "portrait"


def normalize_achievement_capsule_font_size(value: object) -> int:
    """Clamp the independently authored supporting-capsule font size."""

    try:
        resolved = int(value)
    except (TypeError, ValueError):
        resolved = ACHIEVEMENT_CAPSULE_FONT_SIZE_DEFAULT
    return max(
        ACHIEVEMENT_CAPSULE_FONT_SIZE_MIN,
        min(ACHIEVEMENT_CAPSULE_FONT_SIZE_MAX, resolved),
    )


def _capsule_text_rects(
    rect: QRectF,
    *,
    label_text: str,
    font: QFont,
    scale: float,
) -> tuple[QRectF, QRectF]:
    inner = rect.adjusted(7.0 * scale, 0.0, -7.0 * scale, 0.0)
    label_width = min(
        inner.width() * 0.58,
        _layout_text_advance(font, label_text) + 2.0 * scale,
    )
    gap = max(3.0, 4.0 * scale)
    label_rect = QRectF(inner.x(), inner.y(), label_width, inner.height())
    value_rect = QRectF(
        label_rect.right() + gap,
        inner.y(),
        max(1.0, inner.right() - label_rect.right() - gap),
        inner.height(),
    )
    return label_rect, value_rect


def _capsule_label_text(field: SteamCardField, *, doubled: bool) -> str:
    if doubled and field.field_id == "previous":
        return "PREVIOUSLY"
    return field.label.upper()


def _gui_application_available() -> bool:
    return isinstance(QGuiApplication.instance(), QGuiApplication)


def _layout_text_advance(font: QFont, text: str) -> float:
    """Measure layout text without making pre-QApplication probes fatal."""

    if _gui_application_available():
        return QFontMetricsF(font).horizontalAdvance(text)

    point_size = font.pointSizeF()
    if point_size <= 0:
        point_size = 10.0
    narrow = set(" !'(),.:;I[]`ijl|1")
    wide = set("MW@#%&QO0")
    units = sum(0.38 if char in narrow else 0.92 if char in wide else 0.68 for char in text)
    return units * point_size


def _layout_font_height(font: QFont) -> float:
    """Measure text height with a deterministic pre-QApplication fallback."""

    if _gui_application_available():
        return QFontMetricsF(font).height()
    point_size = font.pointSizeF()
    return max(1.0, (point_size if point_size > 0 else 10.0) * 1.35)


def achievement_capsule_geometry(
    *,
    font_family: str,
    capsule_font_size: int,
) -> tuple[float, float]:
    """Return authored capsule height/gap that safely contains the chosen font."""

    resolved_size = normalize_achievement_capsule_font_size(capsule_font_size)
    font = QFont(font_family, resolved_size, QFont.Weight.DemiBold)
    text_height = _layout_font_height(font)
    field_height = max(
        ACHIEVEMENT_CAPSULE_BASE_HEIGHT,
        float(math.ceil(text_height + 8.0)),
    )
    field_gap = max(
        ACHIEVEMENT_CAPSULE_BASE_GAP,
        float(math.ceil(text_height * 0.25)),
    )
    return field_height, field_gap


def achievement_field_rail_count(field_count: int, *, double_capsules: bool) -> int:
    """Return whole-row rail occupancy for three supporting fields per row."""

    compact_rows = max(1, (max(0, int(field_count)) + 2) // 3)
    return compact_rows * (2 if double_capsules else 1)


def _plan_achievement_fields(
    fields: tuple[SteamCardField, ...],
    *,
    double_capsules: bool,
) -> tuple[tuple[tuple[SteamCardField, int, int, bool], ...], int]:
    placements: list[tuple[SteamCardField, int, int, bool]] = []
    rail_stride = 2 if double_capsules else 1
    for index, card_field in enumerate(fields):
        compact_row, column = divmod(index, 3)
        placements.append(
            (card_field, compact_row * rail_stride, column, bool(double_capsules))
        )

    rail_count = achievement_field_rail_count(
        len(fields),
        double_capsules=double_capsules,
    )
    return tuple(placements), rail_count


def achievement_pulse_authored_size(
    *,
    show_artwork: bool,
    artwork_shape: str,
    artwork_size: int = ACHIEVEMENT_SQUARE_ARTWORK_DEFAULT,
    field_rail_count: int = 2,
    capsule_height: float = ACHIEVEMENT_CAPSULE_BASE_HEIGHT,
    capsule_gap: float = ACHIEVEMENT_CAPSULE_BASE_GAP,
) -> QSizeF:
    """Return the authored canvas for the selected Achievement Pulse artwork mode."""

    rail_count = max(1, int(field_rail_count))
    field_height = max(ACHIEVEMENT_CAPSULE_BASE_HEIGHT, float(capsule_height))
    field_gap = max(ACHIEVEMENT_CAPSULE_BASE_GAP, float(capsule_gap))
    baseline_block_height = (
        2.0 * ACHIEVEMENT_CAPSULE_BASE_HEIGHT + ACHIEVEMENT_CAPSULE_BASE_GAP
    )
    required_block_height = rail_count * field_height + max(0, rail_count - 1) * field_gap
    extra_height = max(0.0, required_block_height - baseline_block_height)
    resolved_shape = normalize_achievement_artwork_shape(artwork_shape)
    if show_artwork and resolved_shape == "portrait":
        portrait_height = (
            normalize_achievement_square_artwork_size(artwork_size)
            * ACHIEVEMENT_PORTRAIT_ASPECT_RATIO
        )
        required_height = (
            14.0
            + portrait_height
            + 6.0
            + 28.0
            + 12.0
            + required_block_height
            + 16.0
        )
        return QSizeF(
            ACHIEVEMENT_PULSE_PORTRAIT_AUTHORED_SIZE.width(),
            max(ACHIEVEMENT_PULSE_PORTRAIT_AUTHORED_SIZE.height(), required_height),
        )
    if show_artwork and resolved_shape == "square":
        return QSizeF(
            ACHIEVEMENT_PULSE_SQUARE_AUTHORED_SIZE.width(),
            ACHIEVEMENT_PULSE_SQUARE_AUTHORED_SIZE.height() + extra_height,
        )
    return QSizeF(
        ACHIEVEMENT_PULSE_AUTHORED_SIZE.width(),
        ACHIEVEMENT_PULSE_AUTHORED_SIZE.height() + extra_height,
    )


def layout_steam_card(
    model: SteamCardViewModel,
    target_rect: QRectF,
    *,
    dpr: float = 1.0,
    show_artwork: bool = True,
    artwork_shape: str = "wide",
    square_artwork_size: int = ACHIEVEMENT_SQUARE_ARTWORK_DEFAULT,
    show_latest_artwork: bool = False,
    double_capsules: bool = False,
    capsule_font_size: int = ACHIEVEMENT_CAPSULE_FONT_SIZE_DEFAULT,
    font_family: str = "Inter",
    font_size: int = 14,
) -> SteamCardLayout:
    """Resolve display layout while keeping Custom geometry as uniform scale.

    The authored layout is computed from the selected card/mode envelope. The
    target rectangle can shrink or grow that authored card, but it never changes
    visible-field count, rail ownership, or content availability.
    """

    target = QRectF(target_rect)
    is_achievement_pulse = model.card_id == "achievement_pulse"
    resolved_artwork_shape = normalize_achievement_artwork_shape(artwork_shape)
    vertical_art_mode = bool(
        is_achievement_pulse
        and show_artwork
        and resolved_artwork_shape in {"square", "portrait"}
    )
    resolved_square_artwork_size = normalize_achievement_square_artwork_size(square_artwork_size)
    fields = _enabled_fields(model.fields)
    achievement_placements: tuple[tuple[SteamCardField, int, int, bool], ...] = ()
    achievement_rail_count = max(1, (len(fields) + 2) // 3)
    capsule_height = ACHIEVEMENT_CAPSULE_BASE_HEIGHT
    capsule_gap = ACHIEVEMENT_CAPSULE_BASE_GAP
    if is_achievement_pulse:
        achievement_placements, achievement_rail_count = _plan_achievement_fields(
            fields,
            double_capsules=double_capsules,
        )
        capsule_height, capsule_gap = achievement_capsule_geometry(
            font_family=font_family,
            capsule_font_size=capsule_font_size,
        )
    authored_size = (
        achievement_pulse_authored_size(
            show_artwork=show_artwork,
            artwork_shape=resolved_artwork_shape,
            artwork_size=resolved_square_artwork_size,
            field_rail_count=achievement_rail_count,
            capsule_height=capsule_height,
            capsule_gap=capsule_gap,
        )
        if is_achievement_pulse
        else STEAM_CARD_AUTHORED_SIZE
    )
    authored_w = authored_size.width()
    authored_h = authored_size.height()
    scale = max(0.05, min(target.width() / authored_w, target.height() / authored_h))
    painted_w = authored_w * scale
    painted_h = authored_h * scale
    origin_x = target.x() + (target.width() - painted_w) * 0.5
    origin_y = target.y() + (target.height() - painted_h) * 0.5

    authored_rect = QRectF(origin_x, origin_y, painted_w, painted_h)

    if is_achievement_pulse:
        logical_content = QRectF(18.0, 14.0, 564.0, authored_h - 30.0)
        header = QRectF(18.0, 14.0, 302.0, 38.0)
        logo = QRectF(30.0, 19.0, 28.0, 28.0)
        header_text = QRectF(66.0, 16.0, 236.0, 34.0)
        if not show_artwork:
            art = QRectF()
            title_width = 564.0
        elif resolved_artwork_shape in {"square", "portrait"}:
            art_left = 582.0 - resolved_square_artwork_size
            art_height = (
                resolved_square_artwork_size * ACHIEVEMENT_PORTRAIT_ASPECT_RATIO
                if resolved_artwork_shape == "portrait"
                else resolved_square_artwork_size
            )
            art = QRectF(
                art_left,
                14.0,
                float(resolved_square_artwork_size),
                float(art_height),
            )
            title_width = art_left - 32.0
        else:
            art = QRectF(402.0, 14.0, 180.0, 86.0)
            title_width = 370.0
        title = QRectF(18.0, 62.0, title_width, 34.0)
        subtitle = QRectF(18.0, 100.0, title_width, 88.0)
        # Keep the metric visually attached to the artwork while using the
        # otherwise-empty outer gutter. Constraining it to the exact artwork
        # width elides ordinary two-digit achievement totals at high DPI.
        metric = (
            QRectF(art.x() - 10.0, art.bottom() + 6.0, art.width() + 20.0, 28.0)
            if vertical_art_mode
            else QRectF(392.0, 108.0, 200.0, 28.0)
        )
        status = QRectF()
        info = QRectF(300.0, 14.0, 18.0, 18.0) if model.show_connection_info else None
        latest_art_anchor_x = art.x() if not art.isNull() else 582.0
        show_latest_icon = bool(
            show_latest_artwork
            and model.latest_unlock_icon_url
            and model.latest_unlocks
        )
        latest_artwork = QRectF()
        secondary_text_width = title_width
        if show_latest_icon:
            latest_font_size = max(6, int(round((int(font_size * 0.86) + 2) * 0.5)))
            latest_font = QFont(font_family, latest_font_size, QFont.Weight.DemiBold)
            previous_width = max(
                (_layout_text_advance(latest_font, text) for text in model.latest_unlocks[1:4]),
                default=0.0,
            )
            latest_icon_x = min(
                latest_art_anchor_x - 48.0,
                18.0 + previous_width + 10.0,
            )
            latest_icon_x = max(18.0, latest_icon_x)
            latest_artwork = QRectF(latest_icon_x, 130.0, 40.0, 40.0)
            secondary_text_width = max(60.0, latest_artwork.left() - 26.0)
        logical_latest_rects = tuple(
            QRectF(
                18.0,
                100.0 if index == 0 else 130.0 + (index - 1) * 14.0,
                secondary_text_width if show_latest_icon and 1 <= index <= 3 else title_width,
                26.0 if index == 0 else 13.0,
            )
            for index, _latest in enumerate(model.latest_unlocks[:5])
        )
    else:
        logical_content = QRectF(18.0, 16.0, 384.0, 148.0)
        header = QRectF(18.0, 14.0, 254.0, 40.0)
        logo = QRectF(30.0, 19.0, 30.0, 30.0)
        header_text = QRectF(67.0, 16.0, 183.0, 34.0)
        art = QRectF(294.0, 42.0, 88.0, 74.0)
        title = QRectF(18.0, 45.0, 278.0, 30.0)
        subtitle = QRectF(18.0, 76.0, 278.0, 28.0)
        metric = QRectF(294.0, 122.0, 88.0, 28.0)
        status = QRectF(18.0, 145.0, 278.0, 18.0)
        info = QRectF(250.0, 14.0, 18.0, 18.0) if model.show_connection_info else None
        logical_latest_rects = ()
        latest_artwork = QRectF()

    field_rects: list[tuple[str, QRectF, int]] = []
    field_detail_rects: list[tuple[str, QRectF, int]] = []
    field_w = 182.0 if is_achievement_pulse else 84.0
    field_h = capsule_height if is_achievement_pulse else 18.0
    gap = 9.0 if is_achievement_pulse else 8.0
    achievement_last_rail_y = authored_h - 16.0 - field_h
    achievement_rail_step = field_h + capsule_gap
    achievement_first_rail_y = (
        achievement_last_rail_y - (achievement_rail_count - 1) * achievement_rail_step
    )
    if is_achievement_pulse:
        for card_field, rail, column, use_double in achievement_placements:
            x = 18.0 + column * (field_w + gap)
            y = achievement_first_rail_y + rail * achievement_rail_step
            field_rects.append(
                (
                    card_field.field_id,
                    _map_rect(QRectF(x, y, field_w, field_h), origin_x, origin_y, scale),
                    rail,
                )
            )
            if use_double:
                detail_rail = rail + 1
                detail_y = achievement_first_rail_y + detail_rail * achievement_rail_step
                field_detail_rects.append(
                    (
                        card_field.field_id,
                        _map_rect(
                            QRectF(x, detail_y, field_w, field_h),
                            origin_x,
                            origin_y,
                            scale,
                        ),
                        detail_rail,
                    )
                )
    else:
        for index, card_field in enumerate(fields):
            rail = 0 if index < 4 else 1
            column = index if index < 4 else index - 4
            x = 18.0 + column * (field_w + gap)
            y = 109.0 + rail * 20.0
            field_rects.append(
                (
                    card_field.field_id,
                    _map_rect(QRectF(x, y, field_w, field_h), origin_x, origin_y, scale),
                    rail,
                )
            )

    action_rects: list[tuple[str, QRectF]] = []
    if model.state == "connect_required" and model.settings_target:
        prompt_rect = QRectF(44.0, 76.0, 332.0, 34.0)
        connect_rect = QRectF(116.0, 76.0, 82.0, 34.0)
        title = prompt_rect
        subtitle = QRectF(44.0, 113.0, 332.0, 24.0)
        status = subtitle
        art = QRectF()
        metric = QRectF()
        logical_latest_rects = ()
        latest_artwork = QRectF()
        field_rects.clear()
        field_detail_rects.clear()
        action_rects.append((model.settings_target, _map_rect(connect_rect, origin_x, origin_y, scale)))

    paint_fingerprint = (
        model.content_fingerprint(),
        round(target.width(), 2),
        round(target.height(), 2),
        round(float(dpr), 3),
        bool(show_artwork),
        resolved_artwork_shape,
        resolved_square_artwork_size,
        bool(show_latest_artwork),
        bool(model.latest_unlock_icon_url),
        bool(double_capsules),
        normalize_achievement_capsule_font_size(capsule_font_size),
        tuple(field_id for field_id, _rect, _rail in field_detail_rects),
    )

    return SteamCardLayout(
        target_rect=target,
        authored_rect=authored_rect,
        scale=scale,
        content_rect=_map_rect(logical_content, origin_x, origin_y, scale),
        header_rect=_map_rect(header, origin_x, origin_y, scale),
        logo_rect=_map_rect(logo, origin_x, origin_y, scale),
        header_text_rect=_map_rect(header_text, origin_x, origin_y, scale),
        art_rect=_map_rect(art, origin_x, origin_y, scale),
        title_rect=_map_rect(title, origin_x, origin_y, scale),
        subtitle_rect=_map_rect(subtitle, origin_x, origin_y, scale),
        metric_rect=_map_rect(metric, origin_x, origin_y, scale),
        status_rect=_map_rect(status, origin_x, origin_y, scale),
        latest_unlock_rects=tuple(_map_rect(rect, origin_x, origin_y, scale) for rect in logical_latest_rects),
        latest_unlock_art_rect=_map_rect(latest_artwork, origin_x, origin_y, scale),
        field_rects=tuple(field_rects),
        field_detail_rects=tuple(field_detail_rects),
        visible_field_ids=tuple(field.field_id for field in fields),
        paint_fingerprint=paint_fingerprint,
        action_rects=tuple(action_rects),
        info_rect=_map_rect(info, origin_x, origin_y, scale) if info is not None else None,
    )


def _draw_elided_text(
    painter: QPainter,
    rect: QRectF,
    text: str,
    *,
    color: QColor,
    font: QFont,
    flags: Qt.AlignmentFlag | Qt.TextFlag = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
    shadow: bool = True,
) -> None:
    painter.save()
    try:
        painter.setFont(font)
        painter.setPen(color)
        metrics = QFontMetricsF(font)
        elided = metrics.elidedText(text, Qt.TextElideMode.ElideRight, max(1.0, rect.width()))
        draw_text_rect_with_shadow(
            painter,
            rect.toAlignedRect(),
            int(flags),
            elided,
            font_size=max(1, font.pointSize()),
            enabled=shadow,
        )
    finally:
        painter.restore()


def _draw_underlined_text(
    painter: QPainter,
    rect: QRectF,
    prefix: str,
    suffix: str,
    *,
    color: QColor,
    font: QFont,
) -> None:
    painter.save()
    try:
        font = QFont(font)
        min_point_size = max(6, int(round(font.pointSize() * 0.72)))
        painter.setFont(font)
        painter.setPen(color)
        metrics = QFontMetricsF(font)
        prefix_width = metrics.horizontalAdvance(prefix)
        suffix_width = metrics.horizontalAdvance(suffix)
        total_width = prefix_width + suffix_width
        while total_width > rect.width() and font.pointSize() > min_point_size:
            font.setPointSize(font.pointSize() - 1)
            painter.setFont(font)
            metrics = QFontMetricsF(font)
            prefix_width = metrics.horizontalAdvance(prefix)
            suffix_width = metrics.horizontalAdvance(suffix)
            total_width = prefix_width + suffix_width
        if total_width > rect.width():
            suffix = metrics.elidedText(suffix, Qt.TextElideMode.ElideRight, max(1.0, rect.width() - prefix_width))
            suffix_width = metrics.horizontalAdvance(suffix)
            total_width = prefix_width + suffix_width
        x = rect.x() + max(0.0, (rect.width() - total_width) * 0.5)
        y = rect.y() + (rect.height() + metrics.ascent() - metrics.descent()) * 0.5
        prefix_rect = QRectF(x, rect.y(), prefix_width + 2.0, rect.height())
        suffix_rect = QRectF(x + prefix_width, rect.y(), suffix_width + 2.0, rect.height())
        draw_text_rect_with_shadow(
            painter,
            prefix_rect.toAlignedRect(),
            int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
            prefix,
            font_size=max(1, font.pointSize()),
        )
        underline_y = y + max(1.0, 2.0 * rect.height() / 28.0)
        painter.drawLine(
            QRectF(x, underline_y, prefix_width, 1.0).topLeft(),
            QRectF(x + prefix_width, underline_y, 1.0, 1.0).topLeft(),
        )
        draw_text_rect_with_shadow(
            painter,
            suffix_rect.toAlignedRect(),
            int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
            suffix,
            font_size=max(1, font.pointSize()),
        )
    finally:
        painter.restore()


def _draw_header_badge(
    painter: QPainter,
    layout: SteamCardLayout,
    model: SteamCardViewModel,
    *,
    logo_pixmap: QPixmap | None,
    header_font: QFont,
    text_color: QColor,
) -> None:
    border = QColor(255, 255, 255, 235)
    badge_path = QPainterPath()
    badge_path.addRoundedRect(layout.header_rect, max(6.0, 8.0 * layout.scale), max(6.0, 8.0 * layout.scale))
    fill_a = QColor(27, 30, 38, 220)
    fill_b = QColor(15, 18, 24, 225)
    badge_fill = QLinearGradient(layout.header_rect.topLeft(), layout.header_rect.bottomRight())
    badge_fill.setColorAt(0.0, fill_a)
    badge_fill.setColorAt(1.0, fill_b)
    painter.fillPath(badge_path, badge_fill)
    draw_rounded_rect_border(
        painter,
        layout.header_rect.toAlignedRect(),
        max(6.0, 8.0 * layout.scale),
        border,
        max(2, int(round(2.0 * layout.scale))),
    )

    if logo_pixmap is not None and not logo_pixmap.isNull():
        try:
            dpr = max(1.0, float(painter.device().devicePixelRatioF()))
        except Exception:
            dpr = 1.0
        target_w = max(1, int(round(layout.logo_rect.width() * dpr)))
        target_h = max(1, int(round(layout.logo_rect.height() * dpr)))
        scaled = logo_pixmap.scaled(
            target_w,
            target_h,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        try:
            scaled.setDevicePixelRatio(dpr)
        except Exception:
            pass
        logical_w = max(1.0, float(scaled.width()) / dpr)
        logical_h = max(1.0, float(scaled.height()) / dpr)
        logo_x = layout.logo_rect.x() + max(0.0, (layout.logo_rect.width() - logical_w) * 0.5)
        logo_y = layout.logo_rect.y() + max(0.0, (layout.logo_rect.height() - logical_h) * 0.5)
        painter.drawPixmap(int(round(logo_x)), int(round(logo_y)), scaled)
    else:
        accent = _accent_color(model)
        painter.setBrush(QColor(accent.red(), accent.green(), accent.blue(), 210))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(layout.logo_rect)
        _draw_elided_text(
            painter,
            layout.logo_rect,
            "S",
            color=QColor(255, 255, 255, 235),
            font=header_font,
            flags=Qt.AlignmentFlag.AlignCenter,
        )

    _draw_elided_text(
        painter,
        layout.header_text_rect,
        model.header,
        color=text_color,
        font=header_font,
        flags=Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
    )


def _draw_soft_rounded_shadow(
    painter: QPainter,
    rect: QRectF,
    *,
    radius: float,
    scale: float,
) -> None:
    """Paint the same inexpensive multi-pass shadow used by Media artwork."""

    painter.save()
    try:
        painter.setPen(Qt.PenStyle.NoPen)
        for offset, alpha in ((2.0, 25), (4.0, 35), (6.0, 45), (8.0, 30)):
            distance = offset * scale
            shadow_rect = rect.adjusted(distance, distance, distance, distance)
            shadow_path = QPainterPath()
            shadow_path.addRoundedRect(shadow_rect, radius, radius)
            painter.setBrush(QColor(0, 0, 0, alpha))
            painter.drawPath(shadow_path)
    finally:
        painter.restore()


def _cover_source_rect(image: QImage, target_rect: QRectF) -> QRectF:
    """Return a centered source crop that fills the target without distortion."""

    source_w = max(1.0, float(image.width()))
    source_h = max(1.0, float(image.height()))
    target_w = max(1.0, target_rect.width())
    target_h = max(1.0, target_rect.height())
    source_aspect = source_w / source_h
    target_aspect = target_w / target_h
    if source_aspect > target_aspect:
        crop_w = source_h * target_aspect
        return QRectF((source_w - crop_w) * 0.5, 0.0, crop_w, source_h)
    crop_h = source_w / target_aspect
    return QRectF(0.0, (source_h - crop_h) * 0.5, source_w, crop_h)


def _draw_bottom_right_outside_shadow(
    painter: QPainter,
    rect: QRectF,
    *,
    radius: float,
    scale: float,
) -> None:
    """Paint a capsule shadow only beyond its bottom/right silhouette."""

    original = QPainterPath()
    original.addRoundedRect(rect, radius, radius)
    painter.save()
    try:
        painter.setPen(Qt.PenStyle.NoPen)
        for offset, alpha in ((2.0, 42), (4.0, 30), (6.0, 18)):
            shifted = QPainterPath(original)
            shifted.translate(offset * scale, offset * scale)
            outside = shifted.subtracted(original)
            painter.setBrush(QColor(0, 0, 0, alpha))
            painter.drawPath(outside)
    finally:
        painter.restore()


def _draw_capsule_shell(
    painter: QPainter,
    rect: QRectF,
    *,
    rail: int,
    accent: QColor,
    scale: float,
    fill_color: QColor | None,
    border_color: QColor | None,
) -> None:
    radius = max(6.0, 8.0 * scale)
    pill = QPainterPath()
    pill.addRoundedRect(rect, radius, radius)
    _draw_bottom_right_outside_shadow(painter, rect, radius=radius, scale=scale)

    fill = QColor(fill_color) if fill_color is not None else QColor(accent)
    if fill_color is None:
        fill.setAlpha(38 if rail == 0 else 26)
    painter.fillPath(pill, fill)

    border = QColor(border_color) if border_color is not None else QColor(accent)
    if border_color is None:
        border.setAlpha(145)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.setPen(QPen(border, max(1.0, scale)))
    painter.drawPath(pill)


def _fit_font_to_width(
    font: QFont,
    text: str,
    width: float,
    *,
    minimum_ratio: float = 0.65,
    minimum_point_size: int | None = None,
) -> QFont:
    fitted = QFont(font)
    ratio_minimum = max(6, int(round(fitted.pointSize() * max(0.25, minimum_ratio))))
    minimum = (
        ratio_minimum
        if minimum_point_size is None
        else max(6, min(fitted.pointSize(), int(minimum_point_size)))
    )
    while fitted.pointSize() > minimum and QFontMetricsF(fitted).horizontalAdvance(text) > width:
        fitted.setPointSize(fitted.pointSize() - 1)
    return fitted


def render_steam_card(
    painter: QPainter,
    model: SteamCardViewModel,
    target_rect: QRectF,
    *,
    font_family: str = "Inter",
    font_size: int = 14,
    text_color: QColor | None = None,
    dpr: float = 1.0,
    logo_pixmap: QPixmap | None = None,
    artwork_image: QImage | None = None,
    latest_artwork_image: QImage | None = None,
    show_artwork: bool = True,
    artwork_shape: str = "wide",
    square_artwork_size: int = ACHIEVEMENT_SQUARE_ARTWORK_DEFAULT,
    show_latest_artwork: bool = False,
    double_capsules: bool = False,
    capsule_font_size: int = ACHIEVEMENT_CAPSULE_FONT_SIZE_DEFAULT,
    capsule_fill_color: QColor | None = None,
    capsule_border_color: QColor | None = None,
) -> SteamCardLayout:
    """Paint a Steam card mock and return the layout used."""

    layout = layout_steam_card(
        model,
        target_rect,
        dpr=dpr,
        show_artwork=show_artwork,
        artwork_shape=artwork_shape,
        square_artwork_size=square_artwork_size,
        show_latest_artwork=show_latest_artwork,
        double_capsules=double_capsules,
        capsule_font_size=capsule_font_size,
        font_family=font_family,
        font_size=font_size,
    )
    accent = _accent_color(model)
    color = QColor(text_color or QColor(255, 255, 255, 230))
    muted = QColor(color)
    muted.setAlpha(max(120, min(210, int(color.alpha() * 0.72))))

    painter.save()
    try:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        base_size = max(7, int(font_size * layout.scale))
        header_font = QFont(font_family, max(7, int(base_size * 1.05)), QFont.Weight.Bold)
        title_extra = int(round(5.0 * layout.scale)) if model.card_id == "achievement_pulse" else 0
        title_font = QFont(font_family, max(8, int(base_size * 1.28) + title_extra), QFont.Weight.Bold)
        subtitle_font = QFont(font_family, max(7, int(base_size * 0.86)), QFont.Weight.Normal)
        latest_primary_size = max(8, int(base_size * 0.86) + int(round(2.0 * layout.scale)))
        latest_primary_font = QFont(font_family, latest_primary_size, QFont.Weight.DemiBold)
        latest_secondary_font = QFont(font_family, max(6, int(round(latest_primary_size * 0.5))), QFont.Weight.DemiBold)
        metric_scale = 0.95 if model.card_id == "achievement_pulse" else 1.18
        metric_font = QFont(font_family, max(8, int(base_size * metric_scale)), QFont.Weight.Bold)
        field_font = QFont(
            font_family,
            max(
                7,
                int(
                    normalize_achievement_capsule_font_size(capsule_font_size)
                    * layout.scale
                ),
            ),
            QFont.Weight.DemiBold,
        )

        _draw_header_badge(
            painter,
            layout,
            model,
            logo_pixmap=logo_pixmap,
            header_font=header_font,
            text_color=color,
        )
        if layout.info_rect is not None:
            painter.setBrush(QColor(240, 144, 45, 230))
            painter.setPen(QPen(QColor(255, 230, 180, 220), max(1.0, layout.scale)))
            painter.drawEllipse(layout.info_rect)
            info_font = QFont(font_family, max(6, int(base_size * 0.68)), QFont.Weight.Bold)
            _draw_elided_text(
                painter,
                layout.info_rect.adjusted(0.0, -0.5 * layout.scale, 0.0, 0.0),
                "i",
                color=QColor(30, 20, 10, 230),
                font=info_font,
                flags=Qt.AlignmentFlag.AlignCenter,
            )

        if model.state == "connect_required":
            prompt_font = QFont(font_family, max(9, int(base_size * 1.12)), QFont.Weight.Bold)
            _draw_underlined_text(
                painter,
                layout.title_rect,
                model.action_label or "Connect",
                model.action_text.replace(model.action_label or "Connect", "", 1) or " With Steam To Use",
                color=color,
                font=prompt_font,
            )
            _draw_elided_text(
                painter,
                layout.status_rect,
                model.status,
                color=muted,
                font=subtitle_font,
                flags=Qt.AlignmentFlag.AlignCenter,
            )
            return layout

        if not layout.art_rect.isNull() and layout.art_rect.width() > 0 and layout.art_rect.height() > 0:
            art_radius = max(6.0, 8.0 * layout.scale)
            _draw_soft_rounded_shadow(
                painter,
                layout.art_rect,
                radius=art_radius,
                scale=layout.scale,
            )
            art_path = QPainterPath()
            art_path.addRoundedRect(layout.art_rect, art_radius, art_radius)
            art_fill = QLinearGradient(layout.art_rect.topLeft(), layout.art_rect.bottomRight())
            art_color = QColor(accent)
            art_color.setAlpha(90)
            art_fill.setColorAt(0.0, art_color)
            art_fill.setColorAt(1.0, QColor(12, 15, 20, 120))
            painter.fillPath(art_path, art_fill)
            painter.setPen(QPen(QColor(255, 255, 255, 175), max(1.0, 2.0 * layout.scale)))
            painter.drawPath(art_path)

        if not layout.latest_unlock_art_rect.isNull():
            latest_art_radius = max(4.0, 6.0 * layout.scale)
            _draw_soft_rounded_shadow(
                painter,
                layout.latest_unlock_art_rect,
                radius=latest_art_radius,
                scale=layout.scale,
            )
            latest_art_path = QPainterPath()
            latest_art_path.addRoundedRect(
                layout.latest_unlock_art_rect,
                latest_art_radius,
                latest_art_radius,
            )
            painter.fillPath(latest_art_path, QColor(12, 15, 20, 180))
            painter.setPen(
                QPen(QColor(255, 255, 255, 175), max(1.0, 1.5 * layout.scale))
            )
            painter.drawPath(latest_art_path)

        fitted_secondary_fonts = tuple(
            _fit_font_to_width(
                latest_secondary_font,
                latest,
                latest_rect.width(),
                minimum_point_size=6,
            )
            for latest, latest_rect in zip(
                model.latest_unlocks[1:],
                layout.latest_unlock_rects[1:],
            )
        )
        latest_primary_draw_font = latest_primary_font
        if layout.latest_unlock_rects and model.latest_unlocks:
            latest_primary_draw_font = _fit_font_to_width(
                latest_primary_font,
                model.latest_unlocks[0],
                layout.latest_unlock_rects[0].width(),
                minimum_point_size=latest_secondary_font.pointSize(),
            )
        title_floor = (
            latest_primary_draw_font.pointSize()
            if layout.latest_unlock_rects
            else subtitle_font.pointSize()
        )
        title_draw_font = _fit_font_to_width(
            title_font,
            model.title,
            layout.title_rect.width(),
            minimum_point_size=title_floor,
        )
        _draw_elided_text(
            painter,
            layout.title_rect,
            model.title,
            color=color,
            font=title_draw_font,
        )
        if layout.latest_unlock_rects:
            for index, (latest, latest_rect) in enumerate(zip(model.latest_unlocks, layout.latest_unlock_rects)):
                _draw_elided_text(
                    painter,
                    latest_rect,
                    latest,
                    color=color if index == 0 else muted,
                    font=(
                        latest_primary_draw_font
                        if index == 0
                        else fitted_secondary_fonts[index - 1]
                    ),
                )
        elif model.subtitle:
            _draw_elided_text(painter, layout.subtitle_rect, model.subtitle, color=muted, font=subtitle_font)
        metric_text = f"{model.metric_label}: {model.metric_value}" if model.metric_label else model.metric_value
        metric_font = _fit_font_to_width(
            metric_font,
            metric_text,
            layout.metric_rect.width(),
            minimum_ratio=0.5,
        )
        _draw_elided_text(
            painter,
            layout.metric_rect,
            metric_text,
            color=color,
            font=metric_font,
            flags=Qt.AlignmentFlag.AlignCenter,
        )
        if model.status and not layout.status_rect.isNull():
            _draw_elided_text(painter, layout.status_rect, model.status, color=muted, font=subtitle_font)

        field_by_id = {field.field_id: field for field in model.fields}
        detail_by_id = {
            field_id: (detail_rect, detail_rail)
            for field_id, detail_rect, detail_rail in layout.field_detail_rects
        }
        for field_id, field_rect, rail in layout.field_rects:
            field = field_by_id[field_id]
            _draw_capsule_shell(
                painter,
                field_rect,
                rail=rail,
                accent=accent,
                scale=layout.scale,
                fill_color=capsule_fill_color,
                border_color=capsule_border_color,
            )
            value_text = str(field.value).upper()
            detail = detail_by_id.get(field_id)
            label_text = _capsule_label_text(field, doubled=detail is not None)
            if detail is not None:
                label_rect = field_rect.adjusted(
                    7.0 * layout.scale,
                    0.0,
                    -7.0 * layout.scale,
                    0.0,
                )
                _draw_elided_text(
                    painter,
                    label_rect,
                    label_text,
                    color=color,
                    font=field_font,
                    flags=Qt.AlignmentFlag.AlignCenter,
                )
                detail_rect, detail_rail = detail
                _draw_capsule_shell(
                    painter,
                    detail_rect,
                    rail=detail_rail,
                    accent=accent,
                    scale=layout.scale,
                    fill_color=capsule_fill_color,
                    border_color=capsule_border_color,
                )
                value_rect = detail_rect.adjusted(
                    7.0 * layout.scale,
                    0.0,
                    -7.0 * layout.scale,
                    0.0,
                )
                fitted_font = _fit_font_to_width(field_font, value_text, value_rect.width())
                _draw_elided_text(
                    painter,
                    value_rect,
                    value_text,
                    color=color,
                    font=fitted_font,
                    flags=Qt.AlignmentFlag.AlignCenter,
                )
                continue

            label_rect, value_rect = _capsule_text_rects(
                field_rect,
                label_text=label_text,
                font=field_font,
                scale=layout.scale,
            )
            _draw_elided_text(
                painter,
                label_rect,
                label_text,
                color=color,
                font=field_font,
            )
            _draw_elided_text(
                painter,
                value_rect,
                value_text,
                color=color,
                font=field_font,
                flags=Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            )

    finally:
        painter.restore()

    if artwork_image is not None and not artwork_image.isNull() and not layout.art_rect.isNull():
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        painter.setOpacity(1.0)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
        art_radius = max(6.0, 8.0 * layout.scale)
        artwork_clip = QPainterPath()
        artwork_clip.addRoundedRect(layout.art_rect, art_radius, art_radius)
        painter.setClipPath(artwork_clip)
        painter.drawImage(layout.art_rect, artwork_image, _cover_source_rect(artwork_image, layout.art_rect))
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
        artwork_border = QPainterPath()
        artwork_border.addRoundedRect(layout.art_rect, art_radius, art_radius)
        painter.setPen(QPen(QColor(255, 255, 255, 175), max(1.0, 2.0 * layout.scale)))
        painter.drawPath(artwork_border)
        painter.restore()

    if (
        latest_artwork_image is not None
        and not latest_artwork_image.isNull()
        and not layout.latest_unlock_art_rect.isNull()
    ):
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        latest_art_radius = max(4.0, 6.0 * layout.scale)
        latest_art_clip = QPainterPath()
        latest_art_clip.addRoundedRect(
            layout.latest_unlock_art_rect,
            latest_art_radius,
            latest_art_radius,
        )
        painter.setClipPath(latest_art_clip)
        painter.drawImage(
            layout.latest_unlock_art_rect,
            latest_artwork_image,
            _cover_source_rect(latest_artwork_image, layout.latest_unlock_art_rect),
        )
        painter.setClipping(False)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(
            QPen(QColor(255, 255, 255, 190), max(1.0, 1.5 * layout.scale))
        )
        painter.drawPath(latest_art_clip)
        painter.restore()

    return layout
