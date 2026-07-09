"""Shared mock visual components for dev-gated Steam cards.

This module is intentionally provider-inert. It owns only immutable mock view
models, deterministic layout metrics, and painter helpers used before any
production Steam data path is wired into runtime cards.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from PySide6.QtCore import QRectF, QSizeF, Qt
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap

from core.steam.achievement_pulse import AchievementPulseResolved
from widgets.shadow_utils import draw_rounded_rect_with_shadow, draw_text_rect_with_shadow


STEAM_CARD_AUTHORED_SIZE = QSizeF(420.0, 180.0)
STEAM_SETTINGS_TARGET = "steam_connection"
STEAM_STALE_CONNECTION_INFO_SECONDS = 24 * 60 * 60


@dataclass(frozen=True)
class SteamCardField:
    """One authored supporting field for a mock Steam card."""

    field_id: str
    label: str
    value: str
    enabled: bool = True

    def fingerprint(self) -> tuple[str, str, str, bool]:
        return (self.field_id, self.label, self.value, self.enabled)


@dataclass(frozen=True)
class SteamCardViewModel:
    """Immutable fixture view model consumed by Steam card painters."""

    card_id: str
    header: str
    title: str
    subtitle: str
    metric_label: str
    metric_value: str
    status: str
    accent: str
    fields: tuple[SteamCardField, ...]
    state: str = "content"
    action_text: str = ""
    action_label: str = ""
    settings_target: str = ""
    show_connection_info: bool = False
    connection_info_target: str = ""
    connection_info_tooltip: str = ""
    cache_age_seconds: float | None = None

    @property
    def enabled_field_ids(self) -> tuple[str, ...]:
        return tuple(field.field_id for field in self.fields if field.enabled)

    def content_fingerprint(self) -> tuple[object, ...]:
        return (
            self.card_id,
            self.header,
            self.title,
            self.subtitle,
            self.metric_label,
            self.metric_value,
            self.status,
            self.accent,
            tuple(field.fingerprint() for field in self.fields),
            self.state,
            self.action_text,
            self.action_label,
            self.settings_target,
            self.show_connection_info,
            self.connection_info_target,
            self.connection_info_tooltip,
            self.cache_age_seconds,
        )


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
        return tuple(sorted({rail for _field_id, _rect, rail in self.field_rects}))


def build_mock_steam_view_model(card_id: str) -> SteamCardViewModel:
    """Return deterministic fixture content for a Steam card id."""

    data = {
        "steam_progress": (
            "Steam Progress",
            "Library Pulse",
            "3 meaningful updates found",
            "Updates",
            "3",
            "Cache fixture",
            "#66c0f4",
            (
                ("owned", "Owned", "214"),
                ("updated", "Updated", "3"),
                ("window", "Window", "24h"),
                ("source", "Source", "Fixture"),
                ("noise", "Noise filter", "On"),
            ),
        ),
        "achievement_pulse": (
            "Achievement Pulse",
            "Hollow Knight",
            "Steel Soul progress is moving again",
            "Unlocked",
            "42/63",
            "Mock achievement snapshot",
            "#c7d5e0",
            (
                ("rarity", "Rarity", "12%"),
                ("session", "Session", "+2"),
                ("total", "Total", "67%"),
                ("source", "Source", "Fixture"),
                ("selected", "Selected", "Recent #1"),
            ),
        ),
        "abandonment_issues": (
            "Abandonment Issues",
            "Outer Wilds",
            "A good game has been politely haunting the shelf",
            "Last Played",
            "9 mo",
            "Observed cache fixture",
            "#f0b35f",
            (
                ("playtime", "Playtime", "18h"),
                ("recent", "Recent", "0m"),
                ("confidence", "Time", "Reliable"),
                ("cooldown", "Cooldown", "Clear"),
                ("reason", "Reason", "Lapsed"),
            ),
        ),
        "friend_pulse": (
            "Friend Pulse",
            "Two friends are active",
            "One is currently playing a game you own",
            "Active",
            "2",
            "Privacy-safe fixture",
            "#ff7aa8",
            (
                ("observed", "Observed", "12m"),
                ("overlap", "Library", "Known"),
                ("privacy", "Privacy", "Strict"),
                ("mode", "Mode", "Single"),
                ("source", "Source", "Fixture"),
            ),
        ),
    }
    header, title, subtitle, metric_label, metric_value, status, accent, fields = data.get(
        card_id,
        data["steam_progress"],
    )
    return SteamCardViewModel(
        card_id=card_id,
        header=header,
        title=title,
        subtitle=subtitle,
        metric_label=metric_label,
        metric_value=metric_value,
        status=status,
        accent=accent,
        fields=tuple(SteamCardField(field_id, label, value) for field_id, label, value in fields),
    )
def build_steam_connect_required_view_model(card_id: str) -> SteamCardViewModel:
    """Return an enabled-card prompt state for missing connection/cache."""

    base = build_mock_steam_view_model(card_id)
    return SteamCardViewModel(
        card_id=base.card_id,
        header=base.header,
        title="",
        subtitle="",
        metric_label="",
        metric_value="",
        status="Steam connection required",
        accent=base.accent,
        fields=(),
        state="connect_required",
        action_text="Connect With Steam To Use",
        action_label="Connect",
        settings_target=STEAM_SETTINGS_TARGET,
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


def _format_playtime(minutes: int | None) -> str:
    if minutes is None:
        return "Unknown"
    hours = minutes / 60.0
    if hours < 1:
        return f"{minutes}m"
    return f"{hours:.1f}h" if hours < 10 else f"{int(round(hours))}h"


def build_achievement_pulse_view_model(
    resolved: AchievementPulseResolved,
    *,
    cache_age_seconds: float | None = None,
    connection_needs_attention: bool = False,
    show_connection_info_icon: bool = True,
) -> SteamCardViewModel:
    """Map a pure Achievement Pulse resolution into the shared card view model."""

    base = build_mock_steam_view_model("achievement_pulse")
    if not resolved.ok:
        model = SteamCardViewModel(
            card_id="achievement_pulse",
            header=base.header,
            title=resolved.title or "Achievement Pulse",
            subtitle=resolved.unavailable_reason or "Achievement data is unavailable.",
            metric_label="State",
            metric_value="Unavailable",
            status=resolved.selection_label,
            accent=base.accent,
            fields=(
                SteamCardField("selected", "Selected", resolved.selection_label),
                SteamCardField("appid", "App", str(resolved.appid or "Unknown")),
                SteamCardField("source", "Source", resolved.source_label),
            ),
            state="unavailable",
        )
    else:
        percent_text = f"{resolved.percent:.0f}%" if resolved.percent is not None else "Unknown"
        latest = resolved.latest_achievement or "No unlocked achievement yet"
        model = SteamCardViewModel(
            card_id="achievement_pulse",
            header=base.header,
            title=resolved.title,
            subtitle=f"Latest: {latest}",
            metric_label="Unlocked",
            metric_value=f"{resolved.unlocked}/{resolved.total}",
            status=resolved.selection_label,
            accent=base.accent,
            fields=(
                SteamCardField("total", "Total", percent_text),
                SteamCardField("latest", "Latest", latest),
                SteamCardField("playtime", "Playtime", _format_playtime(resolved.playtime_forever_minutes)),
                SteamCardField("source", "Source", resolved.source_label),
                SteamCardField("selected", "Selected", resolved.selection_label),
            ),
        )

    return with_stale_connection_info(
        model,
        cache_age_seconds=cache_age_seconds,
        enabled=show_connection_info_icon,
        connection_needs_attention=connection_needs_attention,
    )


def with_stale_connection_info(
    model: SteamCardViewModel,
    *,
    cache_age_seconds: float | None,
    enabled: bool = True,
    connection_needs_attention: bool = True,
) -> SteamCardViewModel:
    """Attach the optional stale-connection info affordance to a cached model."""

    should_show = (
        enabled
        and connection_needs_attention
        and cache_age_seconds is not None
        and cache_age_seconds >= STEAM_STALE_CONNECTION_INFO_SECONDS
    )
    return SteamCardViewModel(
        card_id=model.card_id,
        header=model.header,
        title=model.title,
        subtitle=model.subtitle,
        metric_label=model.metric_label,
        metric_value=model.metric_value,
        status=model.status,
        accent=model.accent,
        fields=model.fields,
        state=model.state,
        action_text=model.action_text,
        action_label=model.action_label,
        settings_target=model.settings_target,
        show_connection_info=should_show,
        connection_info_target=STEAM_SETTINGS_TARGET if should_show else "",
        connection_info_tooltip="Steam connection needs attention; cached data is at least 1 day old." if should_show else "",
        cache_age_seconds=cache_age_seconds,
    )


def with_long_title(model: SteamCardViewModel) -> SteamCardViewModel:
    """Return a long-title variant for deterministic layout bars."""

    return SteamCardViewModel(
        card_id=model.card_id,
        header=model.header,
        title=f"{model.title}: A Very Long Localized Title That Must Scale Without Reauthoring Content",
        subtitle=f"{model.subtitle} with extra localized context that remains authored content.",
        metric_label=model.metric_label,
        metric_value=model.metric_value,
        status=model.status,
        accent=model.accent,
        fields=model.fields,
        state=model.state,
        action_text=model.action_text,
        action_label=model.action_label,
        settings_target=model.settings_target,
        show_connection_info=model.show_connection_info,
        connection_info_target=model.connection_info_target,
        connection_info_tooltip=model.connection_info_tooltip,
        cache_age_seconds=model.cache_age_seconds,
    )


def with_unavailable_state(model: SteamCardViewModel) -> SteamCardViewModel:
    """Return an unavailable/private fixture without changing authored fields."""

    return SteamCardViewModel(
        card_id=model.card_id,
        header=model.header,
        title=model.title,
        subtitle="Private or unavailable source; showing cache-safe fixture state.",
        metric_label="State",
        metric_value="Private",
        status="Unavailable fixture",
        accent=model.accent,
        fields=model.fields,
        state="unavailable",
        action_text=model.action_text,
        action_label=model.action_label,
        settings_target=model.settings_target,
        show_connection_info=model.show_connection_info,
        connection_info_target=model.connection_info_target,
        connection_info_tooltip=model.connection_info_tooltip,
        cache_age_seconds=model.cache_age_seconds,
    )


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


def layout_steam_card(
    model: SteamCardViewModel,
    target_rect: QRectF,
    *,
    dpr: float = 1.0,
) -> SteamCardLayout:
    """Resolve display layout while keeping Custom geometry as uniform scale.

    The authored layout is always computed from ``STEAM_CARD_AUTHORED_SIZE``.
    The target rectangle can shrink or grow that authored card, but it never
    changes visible-field count, rails, or content availability.
    """

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
    field_w = 84.0
    field_h = 18.0
    gap = 8.0
    for index, field in enumerate(fields):
        rail = 0 if index < 4 else 1
        column = index if index < 4 else index - 4
        x = 18.0 + column * (field_w + gap)
        y = 109.0 + rail * 20.0
        field_rects.append((field.field_id, _map_rect(QRectF(x, y, field_w, field_h), origin_x, origin_y, scale), rail))

    action_rects: list[tuple[str, QRectF]] = []
    if model.state == "connect_required" and model.settings_target:
        prompt_rect = QRectF(44.0, 76.0, 332.0, 34.0)
        connect_rect = QRectF(116.0, 76.0, 82.0, 34.0)
        title = prompt_rect
        subtitle = QRectF(44.0, 113.0, 332.0, 24.0)
        status = subtitle
        art = QRectF()
        metric = QRectF()
        field_rects.clear()
        action_rects.append((model.settings_target, _map_rect(connect_rect, origin_x, origin_y, scale)))

    paint_fingerprint = (
        model.content_fingerprint(),
        round(target.width(), 2),
        round(target.height(), 2),
        round(float(dpr), 3),
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
    badge_path.addRoundedRect(layout.header_rect, max(8.0, 12.0 * layout.scale), max(8.0, 12.0 * layout.scale))
    fill_a = QColor(27, 30, 38, 220)
    fill_b = QColor(15, 18, 24, 225)
    badge_fill = QLinearGradient(layout.header_rect.topLeft(), layout.header_rect.bottomRight())
    badge_fill.setColorAt(0.0, fill_a)
    badge_fill.setColorAt(1.0, fill_b)
    painter.fillPath(badge_path, badge_fill)
    draw_rounded_rect_with_shadow(
        painter,
        layout.header_rect.toAlignedRect(),
        max(8.0, 12.0 * layout.scale),
        border,
        max(2, int(round(2.0 * layout.scale))),
        shadow_enabled=True,
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
    """Paint a Steam card mock and return the layout used."""

    layout = layout_steam_card(model, target_rect, dpr=dpr)
    accent = _accent_color(model)
    color = QColor(text_color or QColor(255, 255, 255, 230))
    muted = QColor(color)
    muted.setAlpha(max(120, min(210, int(color.alpha() * 0.72))))

    painter.save()
    try:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        base_size = max(7, int(font_size * layout.scale))
        header_font = QFont(font_family, max(7, int(base_size * 1.05)), QFont.Weight.Bold)
        title_font = QFont(font_family, max(8, int(base_size * 1.28)), QFont.Weight.Bold)
        subtitle_font = QFont(font_family, max(7, int(base_size * 0.86)), QFont.Weight.Normal)
        metric_font = QFont(font_family, max(8, int(base_size * 1.18)), QFont.Weight.Bold)
        field_font = QFont(font_family, max(6, int(base_size * 0.68)), QFont.Weight.DemiBold)

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
            art_path = QPainterPath()
            art_path.addRoundedRect(layout.art_rect, 10.0 * layout.scale, 10.0 * layout.scale)
            art_fill = QLinearGradient(layout.art_rect.topLeft(), layout.art_rect.bottomRight())
            art_color = QColor(accent)
            art_color.setAlpha(90)
            art_fill.setColorAt(0.0, art_color)
            art_fill.setColorAt(1.0, QColor(12, 15, 20, 120))
            painter.fillPath(art_path, art_fill)
            painter.setPen(QPen(QColor(255, 255, 255, 175), max(1.0, 1.5 * layout.scale)))
            painter.drawPath(art_path)

        _draw_elided_text(painter, layout.title_rect, model.title, color=color, font=title_font)
        _draw_elided_text(painter, layout.subtitle_rect, model.subtitle, color=muted, font=subtitle_font)
        metric_text = f"{model.metric_label}: {model.metric_value}" if model.metric_label else model.metric_value
        _draw_elided_text(
            painter,
            layout.metric_rect,
            metric_text,
            color=color,
            font=metric_font,
            flags=Qt.AlignmentFlag.AlignCenter,
        )
        _draw_elided_text(painter, layout.status_rect, model.status, color=muted, font=subtitle_font)

        field_by_id = {field.field_id: field for field in model.fields}
        for field_id, field_rect, rail in layout.field_rects:
            field = field_by_id[field_id]
            pill = QPainterPath()
            pill.addRoundedRect(field_rect, 7.0 * layout.scale, 7.0 * layout.scale)
            fill = QColor(accent)
            fill.setAlpha(38 if rail == 0 else 26)
            painter.fillPath(pill, fill)
            painter.setPen(QPen(QColor(accent.red(), accent.green(), accent.blue(), 120), max(1.0, layout.scale)))
            painter.drawPath(pill)
            _draw_elided_text(
                painter,
                field_rect.adjusted(5.0 * layout.scale, 0.0, -5.0 * layout.scale, 0.0),
                f"{field.label}: {field.value}",
                color=color,
                font=field_font,
            )
    finally:
        painter.restore()

    return layout
