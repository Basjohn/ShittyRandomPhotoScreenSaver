"""Provider-inert QWidget helpers for dev-gated Steam card scaffolds."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from PySide6.QtCore import QRectF, QSizeF, Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontMetricsF,
    QImage,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)

from widgets.shadow_utils import draw_rounded_rect_border, draw_text_rect_with_shadow
from widgets.steam_card_models import SteamCardField, SteamCardViewModel


STEAM_CARD_AUTHORED_SIZE = QSizeF(420.0, 180.0)
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
    field_rects: tuple[tuple[str, QRectF, int], ...]
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
                    for _field_id, _rect, rail in self.field_rects
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
        QFontMetricsF(font).horizontalAdvance(label_text) + 2.0 * scale,
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


def _capsule_label_text(field: SteamCardField) -> str:
    return field.label.upper()


def layout_steam_card(
    model: SteamCardViewModel,
    target_rect: QRectF,
    *,
    dpr: float = 1.0,
) -> SteamCardLayout:
    """Resolve the fixed dev-scaffold card under uniform Custom scaling."""

    target = QRectF(target_rect)
    authored_w = STEAM_CARD_AUTHORED_SIZE.width()
    authored_h = STEAM_CARD_AUTHORED_SIZE.height()
    scale = max(0.05, min(target.width() / authored_w, target.height() / authored_h))
    painted_w = authored_w * scale
    painted_h = authored_h * scale
    origin_x = target.x() + (target.width() - painted_w) * 0.5
    origin_y = target.y() + (target.height() - painted_h) * 0.5
    authored_rect = QRectF(origin_x, origin_y, painted_w, painted_h)

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

    fields = _enabled_fields(model.fields)
    field_rects: list[tuple[str, QRectF, int]] = []
    for index, card_field in enumerate(fields):
        rail = 0 if index < 4 else 1
        column = index if index < 4 else index - 4
        x = 18.0 + column * 92.0
        y = 109.0 + rail * 20.0
        field_rects.append(
            (
                card_field.field_id,
                _map_rect(QRectF(x, y, 84.0, 18.0), origin_x, origin_y, scale),
                rail,
            )
        )

    action_rects: list[tuple[str, QRectF]] = []
    if model.state == "connect_required" and model.settings_target:
        title = QRectF(44.0, 76.0, 332.0, 34.0)
        subtitle = QRectF(44.0, 113.0, 332.0, 24.0)
        status = subtitle
        art = QRectF()
        metric = QRectF()
        field_rects.clear()
        connect_rect = QRectF(116.0, 76.0, 82.0, 34.0)
        action_rects.append(
            (
                model.settings_target,
                _map_rect(connect_rect, origin_x, origin_y, scale),
            )
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
        field_rects=tuple(field_rects),
        visible_field_ids=tuple(field.field_id for field in fields),
        paint_fingerprint=(
            model.content_fingerprint(),
            round(target.width(), 2),
            round(target.height(), 2),
            round(float(dpr), 3),
        ),
        action_rects=tuple(action_rects),
        info_rect=(
            _map_rect(info, origin_x, origin_y, scale)
            if info is not None
            else None
        ),
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
) -> SteamCardLayout:
    """Paint one provider-inert dev scaffold and return its layout."""

    layout = layout_steam_card(model, target_rect, dpr=dpr)
    accent = _accent_color(model)
    color = QColor(text_color or QColor(255, 255, 255, 230))
    muted = QColor(color)
    muted.setAlpha(max(120, min(210, int(color.alpha() * 0.72))))

    painter.save()
    try:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        base_size = max(7, int(font_size * layout.scale))
        header_font = QFont(
            font_family,
            max(7, int(base_size * 1.05)),
            QFont.Weight.Bold,
        )
        title_font = QFont(
            font_family,
            max(8, int(base_size * 1.28)),
            QFont.Weight.Bold,
        )
        subtitle_font = QFont(
            font_family,
            max(7, int(base_size * 0.86)),
            QFont.Weight.Normal,
        )
        metric_font = QFont(
            font_family,
            max(8, int(base_size * 1.18)),
            QFont.Weight.Bold,
        )
        field_font = QFont(
            font_family,
            max(7, int(base_size * 0.72)),
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
            painter.setPen(
                QPen(QColor(255, 230, 180, 220), max(1.0, layout.scale))
            )
            painter.drawEllipse(layout.info_rect)
            _draw_elided_text(
                painter,
                layout.info_rect,
                "i",
                color=QColor(30, 20, 10, 230),
                font=field_font,
                flags=Qt.AlignmentFlag.AlignCenter,
            )

        if model.state == "connect_required":
            prompt_font = QFont(
                font_family,
                max(9, int(base_size * 1.12)),
                QFont.Weight.Bold,
            )
            _draw_underlined_text(
                painter,
                layout.title_rect,
                model.action_label or "Connect",
                model.action_text.replace(
                    model.action_label or "Connect", "", 1
                )
                or " With Steam To Use",
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

        art_radius = max(6.0, 8.0 * layout.scale)
        _draw_soft_rounded_shadow(
            painter,
            layout.art_rect,
            radius=art_radius,
            scale=layout.scale,
        )
        art_path = QPainterPath()
        art_path.addRoundedRect(layout.art_rect, art_radius, art_radius)
        art_fill = QLinearGradient(
            layout.art_rect.topLeft(), layout.art_rect.bottomRight()
        )
        art_color = QColor(accent)
        art_color.setAlpha(90)
        art_fill.setColorAt(0.0, art_color)
        art_fill.setColorAt(1.0, QColor(12, 15, 20, 120))
        painter.fillPath(art_path, art_fill)
        painter.setPen(
            QPen(
                QColor(255, 255, 255, 175),
                max(1.0, 2.0 * layout.scale),
            )
        )
        painter.drawPath(art_path)

        _draw_elided_text(
            painter,
            layout.title_rect,
            model.title,
            color=color,
            font=_fit_font_to_width(
                title_font,
                model.title,
                layout.title_rect.width(),
            ),
        )
        _draw_elided_text(
            painter,
            layout.subtitle_rect,
            model.subtitle,
            color=muted,
            font=subtitle_font,
        )
        metric_text = (
            f"{model.metric_label}: {model.metric_value}"
            if model.metric_label
            else model.metric_value
        )
        _draw_elided_text(
            painter,
            layout.metric_rect,
            metric_text,
            color=color,
            font=_fit_font_to_width(
                metric_font,
                metric_text,
                layout.metric_rect.width(),
                minimum_ratio=0.5,
            ),
            flags=Qt.AlignmentFlag.AlignCenter,
        )
        if model.status:
            _draw_elided_text(
                painter,
                layout.status_rect,
                model.status,
                color=muted,
                font=subtitle_font,
            )

        field_by_id = {field.field_id: field for field in model.fields}
        for field_id, field_rect, rail in layout.field_rects:
            field = field_by_id[field_id]
            _draw_capsule_shell(
                painter,
                field_rect,
                rail=rail,
                accent=accent,
                scale=layout.scale,
                fill_color=None,
                border_color=None,
            )
            label_text = _capsule_label_text(field)
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
                str(field.value).upper(),
                color=color,
                font=field_font,
                flags=(
                    Qt.AlignmentFlag.AlignRight
                    | Qt.AlignmentFlag.AlignVCenter
                ),
            )
    finally:
        painter.restore()

    return layout
