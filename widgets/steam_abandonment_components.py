"""Distinct archival presentation for Steam Abandonment Issues."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Mapping

from PySide6.QtCore import QPointF, QRectF, QSizeF, Qt
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

from core.steam.abandonment_issues import AbandonmentResolved, LAST_PLAYED_VERIFIED
from widgets.shadow_utils import draw_text_rect_with_shadow
from widgets.steam_components import (
    STEAM_SETTINGS_TARGET,
    SteamCardField,
    SteamCardViewModel,
    _cover_source_rect,
    _draw_elided_text,
    _draw_header_badge,
    _draw_soft_rounded_shadow,
    _draw_underlined_text,
    with_stale_connection_info,
)


ABANDONMENT_AUTHORED_SIZE = QSizeF(560.0, 300.0)
ABANDONMENT_ARTWORK_SIZE_MIN = 110
ABANDONMENT_ARTWORK_SIZE_DEFAULT = 140
ABANDONMENT_ARTWORK_SIZE_MAX = 180
ABANDONMENT_ACCENT_RGBA = (222, 157, 88, 225)
ABANDONMENT_PRIMARY_REDISCOVERY_MESSAGE = "Long Forgotten"
ABANDONMENT_ALTERNATE_REDISCOVERY_MESSAGES: tuple[str, ...] = (
    "You Don't Even Remember Buying This One Do You?",
    "Was The Sale Really THAT Good?",
    "Your Mother Was Right About You.",
    "I Mean, We All Make Bad Decisions Sometimes...",
    "It's Not Like The Game Has Feelings Or Anything.",
    "Your Library Looks On Judgingly As You Force Feed It",
    "This One Hid Behind 7 Proxies.",
    "You Could - And Do - Play Worse.",
    "That Bundle Sure Seems Silly Now Doesn't It?",
    "If They Remake This Will You Buy And Ignore That Too?",
)
_ABANDONMENT_PRIMARY_MESSAGE_BUCKETS = 60
_ABANDONMENT_MESSAGE_BUCKET_COUNT = 100


@dataclass(frozen=True)
class AbandonmentCardLayout:
    """Resolved card geometry kept testable outside paint."""

    target_rect: QRectF
    authored_rect: QRectF
    scale: float
    header_rect: QRectF
    logo_rect: QRectF
    header_text_rect: QRectF
    archive_tab_rect: QRectF
    art_rect: QRectF
    title_rect: QRectF
    subtitle_rect: QRectF
    age_stamp_rect: QRectF
    field_rects: tuple[tuple[str, QRectF], ...]
    action_rects: tuple[tuple[str, QRectF], ...] = field(default_factory=tuple)
    info_rect: QRectF | None = None


def normalize_abandonment_artwork_size(value: object) -> int:
    try:
        resolved = int(value)
    except (TypeError, ValueError):
        resolved = ABANDONMENT_ARTWORK_SIZE_DEFAULT
    return max(ABANDONMENT_ARTWORK_SIZE_MIN, min(ABANDONMENT_ARTWORK_SIZE_MAX, resolved))


def abandonment_authored_size(
    *,
    show_artwork: bool,
    artwork_shape: str,
    artwork_size: int,
) -> QSizeF:
    """Grow the authored canvas when a taller portrait cover needs it."""

    resolved_size = normalize_abandonment_artwork_size(artwork_size)
    if show_artwork and str(artwork_shape).strip().lower() == "square":
        required_height = 76.0 + resolved_size * 1.4 + 22.0
        return QSizeF(ABANDONMENT_AUTHORED_SIZE.width(), max(ABANDONMENT_AUTHORED_SIZE.height(), required_height))
    return QSizeF(ABANDONMENT_AUTHORED_SIZE)


def abandonment_artwork_dimensions(
    *,
    show_artwork: bool,
    artwork_shape: str,
    artwork_size: int,
) -> QSizeF:
    """Return the authored artwork target shared by layout and worker prep."""

    if not show_artwork:
        return QSizeF()
    resolved_size = normalize_abandonment_artwork_size(artwork_size)
    if str(artwork_shape).strip().lower() == "square":
        return QSizeF(float(resolved_size), resolved_size * 1.4)
    return QSizeF(
        min(238.0, resolved_size * 1.45),
        max(78.0, resolved_size * 0.66),
    )


def format_abandonment_age(inactivity_days: int | None) -> str:
    """Format only a source-proven inactivity interval."""

    if inactivity_days is None:
        return "HISTORY UNKNOWN"
    days = max(0, int(inactivity_days))
    if days < 14:
        return f"{days} DAY{'S' if days != 1 else ''} AGO"
    if days < 70:
        weeks = max(2, int(round(days / 7.0)))
        return f"{weeks} WEEKS AGO"
    if days < 548:
        months = max(2, int(round(days / 30.4375)))
        return f"{months} MONTHS AGO"
    years = days / 365.25
    return f"{years:.1f} YEARS AGO" if years < 10 else f"{int(round(years))} YEARS AGO"


def build_abandonment_view_model(
    resolved: AbandonmentResolved,
    *,
    cache_age_seconds: float | None = None,
    connection_needs_attention: bool = False,
    show_connection_info_icon: bool = True,
    show_rediscovery_message: bool = True,
    field_visibility: Mapping[str, bool] | None = None,
) -> SteamCardViewModel:
    """Map a pure source resolution into archival card copy."""

    visibility = dict(field_visibility or {})

    def _enabled(field_id: str, default: bool) -> bool:
        return bool(visibility.get(field_id, default))

    fields = (
        SteamCardField(
            "playtime",
            "Played",
            _format_playtime(resolved.playtime_minutes),
            _enabled("playtime", True),
        ),
        SteamCardField(
            "queue",
            "Shelf",
            f"{resolved.queue_position} of {resolved.queue_count}" if resolved.queue_count else "Empty",
            _enabled("queue", True),
        ),
        SteamCardField(
            "source",
            "Source",
            resolved.source_label,
            _enabled("source", False),
        ),
        SteamCardField(
            "pinned",
            "Selection",
            "Pinned" if resolved.pinned else "Smart Rotation",
            _enabled("pinned", False),
        ),
    )
    if resolved.ok:
        model = SteamCardViewModel(
            card_id="abandonment_issues",
            appid=resolved.appid,
            header="Abandonment Issues",
            title=resolved.title,
            subtitle=(
                abandonment_rediscovery_message(resolved.appid, resolved.title)
                if show_rediscovery_message
                else ""
            ),
            metric_label="Last Visit",
            metric_value=format_abandonment_age(resolved.inactivity_days),
            status=(
                "PINNED FILE"
                if resolved.pinned
                else f"ARCHIVE {resolved.queue_position:02d}/{resolved.queue_count:02d}"
            ),
            accent="#de9d58",
            fields=fields,
        )
    else:
        model = SteamCardViewModel(
            card_id="abandonment_issues",
            appid=resolved.appid,
            header="Abandonment Issues",
            title=resolved.title or "Rediscovery Shelf",
            subtitle=resolved.unavailable_reason or "Previous play history is unavailable.",
            metric_label="History",
            metric_value=(
                "Unavailable"
                if resolved.last_played_confidence != LAST_PLAYED_VERIFIED
                else format_abandonment_age(resolved.inactivity_days)
            ),
            status="ARCHIVE PAUSED",
            accent="#de9d58",
            fields=fields,
            state="unavailable",
        )
    return with_stale_connection_info(
        model,
        cache_age_seconds=cache_age_seconds,
        enabled=show_connection_info_icon,
        connection_needs_attention=connection_needs_attention,
    )


def layout_abandonment_card(
    model: SteamCardViewModel,
    target_rect: QRectF,
    *,
    show_artwork: bool = True,
    artwork_shape: str = "square",
    artwork_size: int = ABANDONMENT_ARTWORK_SIZE_DEFAULT,
) -> AbandonmentCardLayout:
    """Resolve one uniformly scaling archival card composition."""

    target = QRectF(target_rect)
    authored_size = abandonment_authored_size(
        show_artwork=show_artwork,
        artwork_shape=artwork_shape,
        artwork_size=artwork_size,
    )
    authored_w = authored_size.width()
    authored_h = authored_size.height()
    scale = max(0.05, min(target.width() / authored_w, target.height() / authored_h))
    painted_w = authored_w * scale
    painted_h = authored_h * scale
    origin_x = target.x() + (target.width() - painted_w) * 0.5
    origin_y = target.y() + (target.height() - painted_h) * 0.5

    def _map(rect: QRectF) -> QRectF:
        return QRectF(
            origin_x + rect.x() * scale,
            origin_y + rect.y() * scale,
            rect.width() * scale,
            rect.height() * scale,
        )

    header = QRectF(18.0, 14.0, 322.0, 42.0)
    logo = QRectF(30.0, 20.0, 30.0, 30.0)
    header_text = QRectF(68.0, 17.0, 254.0, 36.0)
    archive_tab = QRectF(407.0, 19.0, 135.0, 30.0)
    shape = "square" if str(artwork_shape).strip().lower() == "square" else "wide"
    art_size = abandonment_artwork_dimensions(
        show_artwork=show_artwork,
        artwork_shape=shape,
        artwork_size=artwork_size,
    )
    if not show_artwork:
        art = QRectF()
        text_left = 24.0
    elif shape == "square":
        art = QRectF(22.0, 76.0, art_size.width(), art_size.height())
        text_left = art.right() + 24.0
    else:
        art = QRectF(22.0, 82.0, art_size.width(), art_size.height())
        text_left = art.right() + 24.0
    text_right = 538.0
    text_width = max(150.0, text_right - text_left)
    title = QRectF(text_left, 74.0, text_width, 46.0)
    subtitle = QRectF(text_left, 119.0, text_width, 34.0)
    age_stamp = QRectF(text_left, 160.0, min(300.0, text_width), 54.0)

    enabled_fields = tuple(field for field in model.fields if field.enabled)
    field_rects: list[tuple[str, QRectF]] = []
    field_width = max(110.0, (text_width - 12.0) * 0.5)
    for index, card_field in enumerate(enabled_fields[:4]):
        row, column = divmod(index, 2)
        field_rects.append(
            (
                card_field.field_id,
                _map(
                    QRectF(
                        text_left + column * (field_width + 12.0),
                        226.0 + row * 31.0,
                        field_width,
                        25.0,
                    )
                ),
            )
        )

    action_rects: list[tuple[str, QRectF]] = []
    if model.state == "connect_required" and model.settings_target:
        title = QRectF(74.0, 122.0, 412.0, 38.0)
        subtitle = QRectF(74.0, 164.0, 412.0, 24.0)
        art = QRectF()
        age_stamp = QRectF()
        field_rects.clear()
        action_rects.append((model.settings_target, _map(QRectF(142.0, 122.0, 90.0, 38.0))))

    return AbandonmentCardLayout(
        target_rect=target,
        authored_rect=QRectF(origin_x, origin_y, painted_w, painted_h),
        scale=scale,
        header_rect=_map(header),
        logo_rect=_map(logo),
        header_text_rect=_map(header_text),
        archive_tab_rect=_map(archive_tab),
        art_rect=_map(art),
        title_rect=_map(title),
        subtitle_rect=_map(subtitle),
        age_stamp_rect=_map(age_stamp),
        field_rects=tuple(field_rects),
        action_rects=tuple(action_rects),
        info_rect=_map(QRectF(318.0, 17.0, 18.0, 18.0)) if model.show_connection_info else None,
    )


def render_abandonment_card(
    painter: QPainter,
    model: SteamCardViewModel,
    target_rect: QRectF,
    *,
    font_family: str,
    font_size: int,
    text_color: QColor,
    logo_pixmap: QPixmap | None,
    artwork_image: QImage | None,
    show_artwork: bool,
    artwork_shape: str,
    artwork_size: int,
    accent_color: QColor,
    content_opacity: float = 1.0,
) -> AbandonmentCardLayout:
    """Paint the archival file-card identity while leaving the header stable."""

    layout = layout_abandonment_card(
        model,
        target_rect,
        show_artwork=show_artwork,
        artwork_shape=artwork_shape,
        artwork_size=artwork_size,
    )
    scale = layout.scale
    color = QColor(text_color)
    muted = QColor(color)
    muted.setAlpha(max(120, int(color.alpha() * 0.72)))
    accent = QColor(accent_color)
    if not accent.isValid():
        accent = QColor(*ABANDONMENT_ACCENT_RGBA)
    header_font = QFont(font_family, max(8, int(font_size * scale * 1.05)), QFont.Weight.Bold)

    painter.save()
    try:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
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
            painter.setPen(QPen(QColor(255, 230, 180, 220), max(1.0, scale)))
            painter.drawEllipse(layout.info_rect)
            _draw_elided_text(
                painter,
                layout.info_rect,
                "i",
                color=QColor(30, 20, 10, 230),
                font=QFont(font_family, max(6, int(font_size * scale * 0.68)), QFont.Weight.Bold),
                flags=Qt.AlignmentFlag.AlignCenter,
            )

        painter.setOpacity(max(0.0, min(1.0, float(content_opacity))))
        _draw_archive_tab(
            painter,
            layout,
            model,
            accent=accent,
            color=color,
            font_family=font_family,
            font_size=font_size,
        )
        if model.state == "connect_required":
            prompt_font = QFont(font_family, max(10, int(font_size * scale * 1.12)), QFont.Weight.Bold)
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
                layout.subtitle_rect,
                model.status,
                color=muted,
                font=QFont(font_family, max(7, int(font_size * scale * 0.82))),
                flags=Qt.AlignmentFlag.AlignCenter,
            )
            return layout

        _draw_artwork_shelf(painter, layout, accent=accent)
        _draw_elided_text(
            painter,
            layout.title_rect,
            model.title,
            color=color,
            font=QFont(font_family, max(11, int(font_size * scale * 1.45)), QFont.Weight.Bold),
        )
        subtitle_font = _fit_wrapped_font(
            QFont(font_family, max(7, int(font_size * scale * 0.88)), QFont.Weight.DemiBold),
            model.subtitle,
            layout.subtitle_rect,
        )
        painter.save()
        try:
            painter.setFont(subtitle_font)
            painter.setPen(muted)
            draw_text_rect_with_shadow(
                painter,
                layout.subtitle_rect.toAlignedRect(),
                int(
                    Qt.AlignmentFlag.AlignLeft
                    | Qt.AlignmentFlag.AlignVCenter
                    | Qt.TextFlag.TextWordWrap
                ),
                model.subtitle,
                font_size=max(1, subtitle_font.pointSize()),
            )
        finally:
            painter.restore()
        _draw_age_stamp(painter, layout, model, accent=accent, color=color, font_family=font_family, font_size=font_size)
        _draw_ledger_fields(painter, layout, model, accent=accent, color=color, muted=muted, font_family=font_family, font_size=font_size)

        if artwork_image is not None and not artwork_image.isNull() and not layout.art_rect.isNull():
            art_radius = max(6.0, 8.0 * scale)
            clip = QPainterPath()
            clip.addRoundedRect(layout.art_rect, art_radius, art_radius)
            painter.save()
            painter.setClipPath(clip)
            painter.drawImage(layout.art_rect, artwork_image, _cover_source_rect(artwork_image, layout.art_rect))
            painter.restore()
            painter.setBrush(Qt.BrushStyle.NoBrush)
            border = QColor(accent)
            border.setAlpha(max(150, border.alpha()))
            painter.setPen(QPen(border, max(1.0, 2.0 * scale)))
            painter.drawPath(clip)
    finally:
        painter.restore()
    return layout


def _draw_archive_tab(
    painter: QPainter,
    layout: AbandonmentCardLayout,
    model: SteamCardViewModel,
    *,
    accent: QColor,
    color: QColor,
    font_family: str,
    font_size: int,
) -> None:
    tab = QPainterPath()
    tab.moveTo(layout.archive_tab_rect.left() + 10.0 * layout.scale, layout.archive_tab_rect.top())
    tab.lineTo(layout.archive_tab_rect.right(), layout.archive_tab_rect.top())
    tab.lineTo(layout.archive_tab_rect.right(), layout.archive_tab_rect.bottom())
    tab.lineTo(layout.archive_tab_rect.left(), layout.archive_tab_rect.bottom())
    tab.closeSubpath()
    fill = QColor(accent)
    fill.setAlpha(min(115, max(55, fill.alpha())))
    painter.fillPath(tab, fill)
    painter.setPen(QPen(QColor(accent.red(), accent.green(), accent.blue(), 205), max(1.0, layout.scale)))
    painter.drawPath(tab)
    _draw_elided_text(
        painter,
        layout.archive_tab_rect.adjusted(10.0 * layout.scale, 0.0, -6.0 * layout.scale, 0.0),
        model.status or "CURATED SHELF",
        color=color,
        font=QFont(font_family, max(6, int(font_size * layout.scale * 0.66)), QFont.Weight.Bold),
        flags=Qt.AlignmentFlag.AlignCenter,
    )


def _draw_artwork_shelf(painter: QPainter, layout: AbandonmentCardLayout, *, accent: QColor) -> None:
    if layout.art_rect.isNull():
        return
    radius = max(6.0, 8.0 * layout.scale)
    backing = layout.art_rect.adjusted(-5.0 * layout.scale, -4.0 * layout.scale, 8.0 * layout.scale, 9.0 * layout.scale)
    _draw_soft_rounded_shadow(painter, backing, radius=radius, scale=layout.scale)
    path = QPainterPath()
    path.addRoundedRect(backing, radius, radius)
    gradient = QLinearGradient(backing.topLeft(), backing.bottomRight())
    warm = QColor(accent)
    warm.setAlpha(78)
    gradient.setColorAt(0.0, warm)
    gradient.setColorAt(0.22, QColor(72, 48, 32, 150))
    gradient.setColorAt(1.0, QColor(18, 20, 23, 205))
    painter.fillPath(path, gradient)
    art_path = QPainterPath()
    art_path.addRoundedRect(layout.art_rect, radius, radius)
    painter.fillPath(art_path, QColor(20, 21, 24, 190))
    painter.save()
    try:
        painter.setClipPath(art_path)
        painter.setPen(QPen(QColor(255, 255, 255, 38), max(1.0, layout.scale)))
        step = max(7.0, 12.0 * layout.scale)
        x = layout.art_rect.left() - layout.art_rect.height()
        while x < layout.art_rect.right():
            painter.drawLine(
                QPointF(x, layout.art_rect.bottom()),
                QPointF(x + layout.art_rect.height(), layout.art_rect.top()),
            )
            x += step
    finally:
        painter.restore()


def _draw_age_stamp(
    painter: QPainter,
    layout: AbandonmentCardLayout,
    model: SteamCardViewModel,
    *,
    accent: QColor,
    color: QColor,
    font_family: str,
    font_size: int,
) -> None:
    if layout.age_stamp_rect.isNull():
        return
    radius = max(4.0, 6.0 * layout.scale)
    path = QPainterPath()
    path.addRoundedRect(layout.age_stamp_rect, radius, radius)
    fill = QColor(accent)
    fill.setAlpha(min(68, max(30, fill.alpha())))
    painter.fillPath(path, fill)
    outline = QColor(accent)
    outline.setAlpha(max(170, outline.alpha()))
    painter.setPen(QPen(outline, max(1.0, 2.0 * layout.scale)))
    painter.drawPath(path)
    inner = layout.age_stamp_rect.adjusted(4.0 * layout.scale, 4.0 * layout.scale, -4.0 * layout.scale, -4.0 * layout.scale)
    inner_path = QPainterPath()
    inner_path.addRoundedRect(inner, max(3.0, 4.0 * layout.scale), max(3.0, 4.0 * layout.scale))
    painter.setPen(QPen(QColor(outline.red(), outline.green(), outline.blue(), 100), max(1.0, layout.scale)))
    painter.drawPath(inner_path)
    label_rect = QRectF(inner.x() + 7.0 * layout.scale, inner.y(), inner.width() * 0.36, inner.height())
    value_rect = QRectF(label_rect.right(), inner.y(), inner.right() - label_rect.right() - 5.0 * layout.scale, inner.height())
    _draw_elided_text(
        painter,
        label_rect,
        model.metric_label.upper(),
        color=QColor(color.red(), color.green(), color.blue(), 190),
        font=QFont(font_family, max(6, int(font_size * layout.scale * 0.68)), QFont.Weight.DemiBold),
    )
    fitted = _fit_font(
        QFont(font_family, max(8, int(font_size * layout.scale * 0.95)), QFont.Weight.Bold),
        model.metric_value,
        value_rect.width(),
    )
    _draw_elided_text(
        painter,
        value_rect,
        model.metric_value,
        color=color,
        font=fitted,
        flags=Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
    )


def _draw_ledger_fields(
    painter: QPainter,
    layout: AbandonmentCardLayout,
    model: SteamCardViewModel,
    *,
    accent: QColor,
    color: QColor,
    muted: QColor,
    font_family: str,
    font_size: int,
) -> None:
    fields = {field.field_id: field for field in model.fields}
    for field_id, rect in layout.field_rects:
        card_field = fields[field_id]
        painter.setPen(QPen(QColor(accent.red(), accent.green(), accent.blue(), 110), max(1.0, layout.scale)))
        painter.drawLine(rect.bottomLeft(), rect.bottomRight())
        dot_size = max(3.0, 4.0 * layout.scale)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(accent.red(), accent.green(), accent.blue(), 195))
        painter.drawEllipse(QRectF(rect.x(), rect.center().y() - dot_size / 2.0, dot_size, dot_size))
        label_rect = rect.adjusted(9.0 * layout.scale, 0.0, -rect.width() * 0.47, 0.0)
        value_rect = QRectF(label_rect.right(), rect.y(), rect.right() - label_rect.right(), rect.height())
        field_font = QFont(font_family, max(6, int(font_size * layout.scale * 0.68)), QFont.Weight.DemiBold)
        _draw_elided_text(painter, label_rect, card_field.label.upper(), color=muted, font=field_font)
        _draw_elided_text(
            painter,
            value_rect,
            str(card_field.value).upper(),
            color=color,
            font=_fit_font(field_font, str(card_field.value).upper(), value_rect.width()),
            flags=Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
        )


def _fit_font(font: QFont, text: str, width: float) -> QFont:
    fitted = QFont(font)
    minimum = max(6, int(fitted.pointSize() * 0.68))
    while fitted.pointSize() > minimum and QFontMetricsF(fitted).horizontalAdvance(text) > width:
        fitted.setPointSize(fitted.pointSize() - 1)
    return fitted


def _fit_wrapped_font(font: QFont, text: str, rect: QRectF) -> QFont:
    fitted = QFont(font)
    minimum = 6
    flags = int(Qt.AlignmentFlag.AlignLeft | Qt.TextFlag.TextWordWrap)
    measure_rect = QRectF(0.0, 0.0, max(1.0, rect.width() - 2.0), 10_000.0)
    available_height = max(1.0, rect.height() - 2.0)
    while fitted.pointSize() > minimum:
        bounds = QFontMetricsF(fitted).boundingRect(measure_rect, flags, text)
        if bounds.height() <= available_height:
            break
        fitted.setPointSize(fitted.pointSize() - 1)
    return fitted


def _format_playtime(minutes: int | None) -> str:
    if minutes is None:
        return "Unknown"
    hours = max(0, int(minutes)) / 60.0
    if hours < 1.0:
        return f"{int(minutes)}m"
    if hours < 10.0:
        return f"{hours:.1f}h"
    return f"{int(round(hours))}h"


def abandonment_rediscovery_message(appid: int | None, title: str) -> str:
    """Choose stable per-game copy without repaint-time randomness."""

    identity = str(appid) if appid is not None else str(title).strip().casefold()
    digest = hashlib.sha256(f"abandonment:{identity}".encode("utf-8")).digest()
    bucket = int.from_bytes(digest[:4], "big") % _ABANDONMENT_MESSAGE_BUCKET_COUNT
    return _rediscovery_message_for_bucket(bucket)


def _rediscovery_message_for_bucket(bucket: int) -> str:
    normalized = int(bucket) % _ABANDONMENT_MESSAGE_BUCKET_COUNT
    if normalized < _ABANDONMENT_PRIMARY_MESSAGE_BUCKETS:
        return ABANDONMENT_PRIMARY_REDISCOVERY_MESSAGE
    alternate_bucket_width = (
        _ABANDONMENT_MESSAGE_BUCKET_COUNT - _ABANDONMENT_PRIMARY_MESSAGE_BUCKETS
    ) // len(ABANDONMENT_ALTERNATE_REDISCOVERY_MESSAGES)
    alternate_index = min(
        len(ABANDONMENT_ALTERNATE_REDISCOVERY_MESSAGES) - 1,
        (normalized - _ABANDONMENT_PRIMARY_MESSAGE_BUCKETS) // alternate_bucket_width,
    )
    return ABANDONMENT_ALTERNATE_REDISCOVERY_MESSAGES[alternate_index]
