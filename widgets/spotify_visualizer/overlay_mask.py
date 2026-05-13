"""Painted-card stencil-mask helpers for the Spotify GL overlay."""
from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QRect


@dataclass(frozen=True)
class PaintedCardMaskUniforms:
    rect_x_px: float
    rect_y_px: float
    rect_w_px: float
    rect_h_px: float
    radius_px: float


def compute_painted_card_mask_uniforms(
    widget_rect: QRect,
    *,
    dpr: float,
    border_width_px: float,
    shrink_right: int,
    shrink_bottom: int,
    radius_extra: int,
) -> PaintedCardMaskUniforms:
    """Return the rounded-rect stencil-mask geometry in framebuffer pixels."""
    card_w = max(1, int(widget_rect.width()) - int(shrink_right))
    card_h = max(1, int(widget_rect.height()) - int(shrink_bottom))
    radius = float(8 + int(radius_extra))

    inset = 1.0 * float(dpr)
    extra = max(0.0, float(border_width_px) * 0.5 * float(dpr))
    rect_x_px = float(inset + extra)
    rect_y_px = float((widget_rect.height() - card_h) * float(dpr) + inset + extra)
    rect_w_px = max(1.0, (card_w - 2.0) * float(dpr) - 2.0 * extra)
    rect_h_px = max(1.0, (card_h - 2.0) * float(dpr) - 2.0 * extra)
    radius_px = float(max(0.0, (radius - 1.0 - float(border_width_px) * 0.5) * float(dpr)))

    return PaintedCardMaskUniforms(
        rect_x_px=rect_x_px,
        rect_y_px=rect_y_px,
        rect_w_px=float(rect_w_px),
        rect_h_px=float(rect_h_px),
        radius_px=radius_px,
    )
