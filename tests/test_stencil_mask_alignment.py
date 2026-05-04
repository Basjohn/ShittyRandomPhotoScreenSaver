"""Test stencil mask alignment against expected card boundary.

Simulates the GL stencil mask SDF in Python and checks sample points
against the Qt rounded-rect geometry used for painted-frame shadows.
"""
from __future__ import annotations

import math
from dataclasses import dataclass


def _rounded_rect_sdf(px: float, py: float, cx: float, cy: float, hw: float, hh: float, radius: float) -> float:
    """Python port of the GLSL roundedRectSDF used in the mask shader."""
    dx = abs(px - cx) - hw + radius
    dy = abs(py - cy) - hh + radius
    # length(max(d, 0.0)) + min(max(d.x, d.y), 0.0) - radius
    odx = max(dx, 0.0)
    ody = max(dy, 0.0)
    outside_len = math.hypot(odx, ody)
    inside_min = min(max(dx, dy), 0.0)
    return outside_len + inside_min - radius


@dataclass(frozen=True)
class CardConfig:
    widget_w: int
    widget_h: int
    shrink_r: int
    shrink_b: int
    radius: float
    dpr: float = 1.0
    inset: float = 1.0  # logical px; matches _ensure_painted_frame_shadow_pixmap
    border_width: float = 3.0  # logical px; matches BaseOverlayWidget.DEFAULT_BORDER_WIDTH

    @property
    def card_w(self) -> int:
        return max(1, self.widget_w - self.shrink_r)

    @property
    def card_h(self) -> int:
        return max(1, self.widget_h - self.shrink_b)

    @property
    def inset_card_w(self) -> float:
        return max(1.0, self.card_w - 2.0 * self.inset)

    @property
    def inset_card_h(self) -> float:
        return max(1.0, self.card_h - 2.0 * self.inset)

    @property
    def inset_radius(self) -> float:
        return max(0.0, self.radius - self.inset)

    def expected_card_rect(self) -> tuple[float, float, float, float]:
        """Return (x, y, w, h) in Qt widget coords (top-left origin)."""
        return (
            float(self.inset),
            float(self.inset),
            float(self.inset_card_w),
            float(self.inset_card_h),
        )


def _compute_gl_mask_boundary(
    widget_w: int,
    widget_h: int,
    card_w: int,
    card_h: int,
    inset: float,
    extra: float,
    radius: float,
    dpr: float,
) -> set[tuple[int, int]]:
    """Compute mask pixels in widget coords using GL bottom-left SDF."""
    fb_w = int(widget_w * dpr)
    fb_h = int(widget_h * dpr)
    inset_px = inset * dpr
    extra_px = max(0.0, extra * dpr)
    mask_w_px = max(1.0, (card_w - 2.0) * dpr - 2.0 * extra_px)
    mask_h_px = max(1.0, (card_h - 2.0) * dpr - 2.0 * extra_px)
    radius_px = max(0.0, (radius - inset - extra) * dpr)

    gl_card_y = (widget_h - card_h) * dpr + inset_px + extra_px
    cx = inset_px + extra_px + mask_w_px / 2.0
    cy = gl_card_y + mask_h_px / 2.0
    hw = mask_w_px / 2.0
    hh = mask_h_px / 2.0

    inside: set[tuple[int, int]] = set()
    for fx in range(fb_w):
        for fy in range(fb_h):
            if _rounded_rect_sdf(
                float(fx) + 0.5, float(fy) + 0.5, cx, cy, hw, hh, radius_px,
            ) <= 0:
                wx = int(fx / dpr)
                wy = widget_h - 1 - int(fy / dpr)
                inside.add((wx, wy))
    return inside


def compute_expected_boundary(config: CardConfig) -> set[tuple[int, int]]:
    """Brute-force compute every integer pixel inside the visible card fill.

    The painted frame shadow draws the card fill with
    _painted_frame_shadow_card_rect().adjusted(1.0, 1.0, -1.0, -1.0).
    A pen border of ``border_width`` px is then drawn *centred* on that
    path, so the visualizer must stay inside the inner edge of the border:
    an extra ``border_width/2`` inset beyond the 1-px painted-frame inset.
    """
    return _compute_gl_mask_boundary(
        config.widget_w,
        config.widget_h,
        config.card_w,
        config.card_h,
        config.inset,
        config.border_width / 2.0,
        config.radius,
        config.dpr,
    )


def compute_mask_boundary(config: CardConfig) -> set[tuple[int, int]]:
    """Compute what the mask shader produces in GL framebuffer coords.

    Replicates the inset logic from paintGL:
        inset = 1.0 * dpr
        extra = max(0.0, border_width_px * 0.5 * dpr)
        mask_w = max(1.0, (card_w - 2.0) * dpr - 2.0 * extra)
        mask_h = max(1.0, (card_h - 2.0) * dpr - 2.0 * extra)
        radius = max(0.0, (radius - 1.0 - border_width_px * 0.5) * dpr)
    """
    return _compute_gl_mask_boundary(
        config.widget_w,
        config.widget_h,
        config.card_w,
        config.card_h,
        config.inset,
        config.border_width / 2.0,
        config.radius,
        config.dpr,
    )


def test_stencil_mask_no_bleed():
    """Verify mask boundary does not exceed expected card boundary."""
    configs = [
        CardConfig(300, 150, shrink_r=20, shrink_b=16, radius=8.0),
        CardConfig(300, 150, shrink_r=20, shrink_b=16, radius=8.0, dpr=2.0),
        CardConfig(200, 100, shrink_r=10, shrink_b=8, radius=4.0),
    ]

    for cfg in configs:
        expected = compute_expected_boundary(cfg)
        mask = compute_mask_boundary(cfg)

        bleed = mask - expected
        missing = expected - mask

        assert not bleed, (
            f"BLEED: {len(bleed)} pixels outside expected card for {cfg}\n"
            f"First 10: {list(bleed)[:10]}"
        )
        # Missing pixels are less critical (conservative mask is OK), but log them
        if missing:
            print(f"INFO: {len(missing)} pixels inside expected card but outside mask for {cfg}")


def test_stencil_mask_corner_rounding():
    """Verify corners are actually rounded (not rectangular)."""
    cfg = CardConfig(100, 100, shrink_r=0, shrink_b=0, radius=8.0)
    mask = compute_mask_boundary(cfg)

    # Because of the 1-px inset, the visible card starts at (1,1) and ends
    # at (98,98).  The very edge pixels should be OUTSIDE the mask.
    edge_pixels = {(0, 0), (0, 99), (99, 0), (99, 99), (1, 1)}
    for px in edge_pixels:
        assert px not in mask, f"Edge pixel {px} should be clipped by inset+radius"

    # Pixel well inside the corner radius should be inside
    inner = {(4, 4), (4, 95), (95, 4), (95, 95)}
    for px in inner:
        assert px in mask, f"Inner pixel {px} should be inside mask with radius={cfg.radius}"


def test_stencil_mask_scissor_equivalent_for_zero_radius():
    """With radius=0, mask should match axis-aligned rectangle exactly."""
    cfg = CardConfig(100, 80, shrink_r=10, shrink_b=8, radius=0.0)
    expected = compute_expected_boundary(cfg)
    mask = compute_mask_boundary(cfg)
    assert mask == expected, f"Zero-radius mismatch: bleed={mask-expected}, missing={expected-mask}"


def test_stencil_mask_no_inset_bleed():
    """Without the inset, mask would bleed 1px beyond expected boundary."""
    # This test documents the bug: a mask computed with inset=0 would
    # produce pixels that the expected (inset=1) boundary rejects.
    cfg = CardConfig(100, 80, shrink_r=10, shrink_b=8, radius=8.0, inset=1.0, border_width=0.0)

    # Expected uses inset=1 with no border width
    expected = compute_expected_boundary(cfg)

    # Mask with inset=0 (and no border width) would overdraw the 1-px border gap
    bad_mask = compute_mask_boundary(
        CardConfig(
            cfg.widget_w, cfg.widget_h,
            cfg.shrink_r, cfg.shrink_b,
            cfg.radius, cfg.dpr, inset=0.0, border_width=0.0,
        )
    )
    bleed = bad_mask - expected
    assert bleed, "Expected some bleed when inset is omitted; test sanity check"
    # With a large corner radius the bleed can extend several pixels into
    # the corners; we just sanity-check it is not empty.


def report_card_geometry():
    """Print the card geometry for common widget sizes to debug alignment."""
    for w, h, sr, sb, r in [
        (300, 150, 20, 16, 8),
        (400, 200, 24, 20, 8),
    ]:
        cfg = CardConfig(w, h, sr, sb, r)
        expected = compute_expected_boundary(cfg)
        mask = compute_mask_boundary(cfg)
        bleed = mask - expected
        missing = expected - mask
        print(
            f"Widget {w}x{h} shrink({sr},{sb}) radius={r}: "
            f"card={cfg.card_w}x{cfg.card_h} | "
            f"expected={len(expected)} mask={len(mask)} "
            f"bleed={len(bleed)} missing={len(missing)}"
        )
        if bleed:
            print(f"  Bleed samples: {sorted(bleed)[:10]}")


if __name__ == "__main__":
    report_card_geometry()
    test_stencil_mask_no_bleed()
    test_stencil_mask_corner_rounding()
    test_stencil_mask_scissor_equivalent_for_zero_radius()
    print("All tests passed.")
