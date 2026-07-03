"""Shared mock visual components for dev-gated Steam cards.

This module is intentionally provider-inert. It owns only immutable mock view
models, deterministic layout metrics, and painter helpers used before any
production Steam data path is wired into runtime cards.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from PySide6.QtCore import QRectF, QSizeF, Qt
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QLinearGradient, QPainter, QPainterPath, QPen


STEAM_CARD_AUTHORED_SIZE = QSizeF(420.0, 180.0)


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
        )


@dataclass(frozen=True)
class SteamCardLayout:
    """Resolved logical/display layout for one card paint pass."""

    target_rect: QRectF
    authored_rect: QRectF
    scale: float
    content_rect: QRectF
    header_rect: QRectF
    art_rect: QRectF
    title_rect: QRectF
    subtitle_rect: QRectF
    metric_rect: QRectF
    status_rect: QRectF
    field_rects: tuple[tuple[str, QRectF, int], ...]
    visible_field_ids: tuple[str, ...]
    paint_fingerprint: tuple[object, ...]

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
    header = QRectF(18.0, 14.0, 222.0, 24.0)
    art = QRectF(290.0, 42.0, 94.0, 74.0)
    title = QRectF(18.0, 45.0, 258.0, 30.0)
    subtitle = QRectF(18.0, 76.0, 258.0, 28.0)
    metric = QRectF(290.0, 122.0, 94.0, 28.0)
    status = QRectF(18.0, 145.0, 258.0, 18.0)

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
        art_rect=_map_rect(art, origin_x, origin_y, scale),
        title_rect=_map_rect(title, origin_x, origin_y, scale),
        subtitle_rect=_map_rect(subtitle, origin_x, origin_y, scale),
        metric_rect=_map_rect(metric, origin_x, origin_y, scale),
        status_rect=_map_rect(status, origin_x, origin_y, scale),
        field_rects=tuple(field_rects),
        visible_field_ids=tuple(field.field_id for field in fields),
        paint_fingerprint=paint_fingerprint,
    )


def _draw_elided_text(
    painter: QPainter,
    rect: QRectF,
    text: str,
    *,
    color: QColor,
    font: QFont,
    flags: Qt.AlignmentFlag | Qt.TextFlag = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
) -> None:
    painter.save()
    try:
        painter.setFont(font)
        painter.setPen(color)
        metrics = QFontMetricsF(font)
        elided = metrics.elidedText(text, Qt.TextElideMode.ElideRight, max(1.0, rect.width()))
        painter.drawText(rect, int(flags), elided)
    finally:
        painter.restore()


def render_steam_card(
    painter: QPainter,
    model: SteamCardViewModel,
    target_rect: QRectF,
    *,
    font_family: str = "Inter",
    font_size: int = 14,
    text_color: QColor | None = None,
    dpr: float = 1.0,
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

        glow = QLinearGradient(layout.authored_rect.topLeft(), layout.authored_rect.bottomRight())
        faint = QColor(accent)
        faint.setAlpha(46)
        transparent = QColor(accent)
        transparent.setAlpha(0)
        glow.setColorAt(0.0, faint)
        glow.setColorAt(1.0, transparent)
        painter.fillRect(layout.authored_rect.adjusted(2, 2, -2, -2), glow)

        accent_pen = QPen(accent, max(1.0, 3.0 * layout.scale))
        accent_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(accent_pen)
        painter.drawLine(layout.header_rect.bottomLeft(), layout.header_rect.bottomRight())

        art_path = QPainterPath()
        art_path.addRoundedRect(layout.art_rect, 10.0 * layout.scale, 10.0 * layout.scale)
        art_fill = QLinearGradient(layout.art_rect.topLeft(), layout.art_rect.bottomRight())
        art_color = QColor(accent)
        art_color.setAlpha(150)
        art_fill.setColorAt(0.0, art_color)
        art_fill.setColorAt(1.0, QColor(10, 16, 26, 190))
        painter.fillPath(art_path, art_fill)
        painter.setPen(QPen(QColor(255, 255, 255, 160), max(1.0, 1.5 * layout.scale)))
        painter.drawPath(art_path)

        base_size = max(7, int(font_size * layout.scale))
        header_font = QFont(font_family, max(6, int(base_size * 0.82)), QFont.Weight.DemiBold)
        title_font = QFont(font_family, max(8, int(base_size * 1.28)), QFont.Weight.Bold)
        subtitle_font = QFont(font_family, max(7, int(base_size * 0.86)), QFont.Weight.Normal)
        metric_font = QFont(font_family, max(8, int(base_size * 1.18)), QFont.Weight.Bold)
        field_font = QFont(font_family, max(6, int(base_size * 0.68)), QFont.Weight.DemiBold)

        _draw_elided_text(painter, layout.header_rect, f"STEAM | {model.header}", color=muted, font=header_font)
        _draw_elided_text(painter, layout.title_rect, model.title, color=color, font=title_font)
        _draw_elided_text(painter, layout.subtitle_rect, model.subtitle, color=muted, font=subtitle_font)
        _draw_elided_text(
            painter,
            layout.metric_rect,
            f"{model.metric_label}: {model.metric_value}",
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
