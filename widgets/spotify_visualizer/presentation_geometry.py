"""Canonical presentation-neutral geometry for the Quick visualizer.

The resolver has no knowledge of QWidget geometry, Settings, mode presets, or
the retired per-mode growth controls.  It produces the single immutable record
consumed by retained Quick chrome, clip geometry, and custom GL.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

from core.settings.visualizer_mode_registry import (
    VisualizerModePresentationPolicy,
    VisualizerShellPolicy,
)
from widgets.spotify_visualizer.presentation_orientation import (
    normalize_content_rotation_quarters,
)
from widgets.spotify_visualizer.render_state import (
    CANONICAL_VISUALIZER_BASELINE_ASPECT_RATIO,
    CANONICAL_VISUALIZER_BASELINE_VIEWPORT_SIZE,
    ResolvedVisualizerPresentation,
    SizeTuple,
    freeze_render_fields,
)


# Visualizer-shell chrome that is deliberately presentation-only rather than a
# persisted Settings product default. Live Settings/theme fields (border width,
# colours, shadow state/blur/direction) are supplied explicitly by the display
# owner; these constants define only the retained Quick card's authored shape.
VISUALIZER_CARD_CORNER_RADIUS = 8.0
VISUALIZER_CARD_CONTENT_INSET = 0.0
VISUALIZER_CARD_SHADOW_SPREAD = 0.0


def _finite(value: object, *, name: str) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{name} must be finite")
    return number


def _positive_size(value: Sequence[object], *, name: str) -> SizeTuple:
    if len(value) != 2:
        raise ValueError(f"{name} must contain width and height")
    size = (
        _finite(value[0], name=f"{name} width"),
        _finite(value[1], name=f"{name} height"),
    )
    if size[0] <= 0.0 or size[1] <= 0.0:
        raise ValueError(f"{name} must be positive")
    return size


def _point(value: Sequence[object], *, name: str) -> tuple[float, float]:
    if len(value) != 2:
        raise ValueError(f"{name} must contain x and y")
    return (
        _finite(value[0], name=f"{name} x"),
        _finite(value[1], name=f"{name} y"),
    )


def _non_negative(value: object, *, name: str) -> float:
    number = _finite(value, name=name)
    if number < 0.0:
        raise ValueError(f"{name} must be non-negative")
    return number


def resolve_visualizer_presentation(
    *,
    policy: VisualizerModePresentationPolicy,
    display_size: Sequence[object],
    outer_origin: Sequence[object] = (0.0, 0.0),
    dpr: float = 1.0,
    uniform_visual_scale: float = 1.0,
    viewport_extent: Sequence[object] | None = None,
    committed_outer_size: Sequence[object] | None = None,
    content_rotation_quarters: object = 0,
    scene_fade: float = 1.0,
    content_fade: float = 1.0,
    border_width: float,
    corner_radius: float,
    content_inset: float,
    background_color: Sequence[object],
    border_color: Sequence[object],
    shadow_enabled: bool,
    shadow_color: Sequence[object],
    shadow_blur: float,
    shadow_offset: Sequence[object],
    shadow_spread: float,
    shadow_extensions: Sequence[object],
) -> ResolvedVisualizerPresentation:
    """Resolve one display-local, scale-committed visualizer presentation.

    ``viewport_extent`` is the logical/render world before uniform visual
    scale.  Its default is the canonical 420x280 baseline.  Supplying a wide,
    tall, or restored CUSTOM extent does not mutate that baseline identity.
    """

    if not isinstance(policy, VisualizerModePresentationPolicy):
        raise TypeError("policy must be a VisualizerModePresentationPolicy")

    display_width, display_height = _positive_size(display_size, name="display size")
    origin_x, origin_y = _point(outer_origin, name="outer origin")
    extent_width, extent_height = _positive_size(
        CANONICAL_VISUALIZER_BASELINE_VIEWPORT_SIZE
        if viewport_extent is None
        else viewport_extent,
        name="viewport extent",
    )
    rotation_quarters = normalize_content_rotation_quarters(
        content_rotation_quarters
    )
    logical_aspect_ratio = (
        extent_height / extent_width
        if rotation_quarters & 1
        else extent_width / extent_height
    )
    requested_scale = _finite(uniform_visual_scale, name="uniform visual scale")
    if requested_scale <= 0.0:
        raise ValueError("uniform visual scale must be positive")

    # Screen-bound reduction remains uniform.  The resolved scale is the
    # committed scale that every downstream geometry consumer receives.
    resolved_scale = (
        requested_scale
        if committed_outer_size is not None and policy.shell_policy is VisualizerShellPolicy.FRAMELESS
        else min(requested_scale, display_width / extent_width, display_height / extent_height)
    )
    outer_width = extent_width * resolved_scale
    outer_height = extent_height * resolved_scale
    if committed_outer_size is not None:
        # Frameless-3D CUSTOM has two independent authored extents: the outer
        # stage rect and the renderer's logical viewport. A width-derived
        # height silently discards the saved stage's aspect, particularly after
        # switching between Shockwave and Sphere. The stage is one persisted
        # authority; do not reverse-infer its height from the render world.
        if policy.shell_policy is not VisualizerShellPolicy.FRAMELESS:
            raise ValueError("explicit CUSTOM outer size is for frameless presentations")
        outer_width, outer_height = _positive_size(
            committed_outer_size, name="committed outer size"
        )
        if outer_width > display_width or outer_height > display_height:
            factor = min(1.0, display_width / outer_width, display_height / outer_height)
            outer_width *= factor
            outer_height *= factor
            resolved_scale *= factor
    origin_x = min(max(0.0, origin_x), max(0.0, display_width - outer_width))
    origin_y = min(max(0.0, origin_y), max(0.0, display_height - outer_height))

    authored_border = _non_negative(border_width, name="border width")
    authored_radius = _non_negative(corner_radius, name="corner radius")
    authored_inset = _non_negative(content_inset, name="content inset")
    authored_shadow_blur = _non_negative(shadow_blur, name="shadow blur")
    authored_shadow_spread = _non_negative(shadow_spread, name="shadow spread")
    authored_shadow_offset = _point(shadow_offset, name="shadow offset")
    if len(shadow_extensions) != 4:
        raise ValueError("shadow extensions must contain left, top, right, bottom")
    authored_shadow_extensions = tuple(
        _non_negative(value, name=f"shadow extension {name}")
        for value, name in zip(
            shadow_extensions,
            ("left", "top", "right", "bottom"),
            strict=True,
        )
    )

    is_card = policy.shell_policy is VisualizerShellPolicy.CARD
    # Card Border Width is visible card chrome, not content geometry. Keep it
    # exact across CUSTOM/world scale so carded Visualizers retain parity with
    # ordinary widgets and the stencil consumes the same visible inset.
    resolved_border = authored_border if is_card else 0.0
    resolved_extra_inset = authored_inset * resolved_scale if is_card else 0.0
    resolved_inset = resolved_border + resolved_extra_inset
    resolved_inset = min(resolved_inset, outer_width / 2.0, outer_height / 2.0)

    # The accepted visualizer card used an 8 logical-pixel visible radius.
    # Scaling it with the visual world made small CUSTOM cards square and also
    # collapsed the inner stencil radius. Radius is visible chrome, so only
    # tiny-card geometry may cap it.
    outer_radius = min(
        authored_radius if is_card else 0.0,
        outer_width / 2.0,
        outer_height / 2.0,
    )
    inner_radius = max(0.0, outer_radius - resolved_inset)
    content_rect = (
        origin_x + resolved_inset,
        origin_y + resolved_inset,
        max(0.0, outer_width - (2.0 * resolved_inset)),
        max(0.0, outer_height - (2.0 * resolved_inset)),
    )
    outer_rect = (origin_x, origin_y, outer_width, outer_height)
    if not is_card:
        content_rect = outer_rect

    style = freeze_render_fields(
        {
            "background_color": tuple(background_color),
            "border_color": tuple(border_color),
            # Retain the authored source explicitly because visible border scaling
            # is intentionally bounded/non-linear; resize must never reverse-
            # derive it from a previously clamped presentation.
            "authored_border_width": authored_border if is_card else 0.0,
            "authored_corner_radius": authored_radius if is_card else 0.0,
            "corner_radius": outer_radius,
            "inner_corner_radius": inner_radius,
            "content_inset": resolved_extra_inset,
            "shadow_blur": (
                authored_shadow_blur * resolved_scale if is_card else 0.0
            ),
            "shadow_color": tuple(shadow_color),
            "shadow_enabled": bool(shadow_enabled and is_card),
            "shadow_offset": (
                authored_shadow_offset[0] * resolved_scale,
                authored_shadow_offset[1] * resolved_scale,
            ),
            "shadow_spread": (
                authored_shadow_spread * resolved_scale if is_card else 0.0
            ),
            "shadow_extensions": tuple(
                value * resolved_scale if is_card else 0.0
                for value in authored_shadow_extensions
            ),
        }
    )

    return ResolvedVisualizerPresentation(
        shell_policy=policy.shell_policy,
        clip_policy=policy.clip_policy,
        viewport_resize_capable=policy.viewport_resize_capable,
        outer_rect=outer_rect,
        content_rect=content_rect,
        dpr=dpr,
        baseline_viewport_size=CANONICAL_VISUALIZER_BASELINE_VIEWPORT_SIZE,
        baseline_aspect_ratio=CANONICAL_VISUALIZER_BASELINE_ASPECT_RATIO,
        uniform_visual_scale=resolved_scale,
        viewport_extent=(extent_width, extent_height),
        current_aspect_ratio=logical_aspect_ratio,
        scene_fade=scene_fade,
        content_fade=content_fade,
        border_width=resolved_border,
        content_rotation_quarters=rotation_quarters,
        shell_style=style,
    )


def resize_visualizer_presentation(
    baseline: ResolvedVisualizerPresentation,
    *,
    display_size: Sequence[object],
    outer_origin: Sequence[object],
    relative_scale: float,
    viewport_extent: Sequence[object] | None = None,
    committed_outer_size: Sequence[object] | None = None,
    content_rotation_quarters: object | None = None,
) -> ResolvedVisualizerPresentation:
    """Reproject one resolved presentation at a new uniform scale and/or extent.

    ``relative_scale`` multiplies the baseline uniform scale (the wheel / corner
    operation).  ``viewport_extent`` overrides the logical world before uniform
    scale (the CUSTOM edge operation); ``None`` keeps the baseline extent.  The
    two operations are independent: changing extent never touches uniform scale,
    and changing scale never touches extent.  Authored chrome scalars are
    recovered from the baseline by de-scaling, so no second style owner is
    invented and finished pixels are never anisotropically stretched.
    """

    if not isinstance(baseline, ResolvedVisualizerPresentation):
        raise TypeError("baseline must be a ResolvedVisualizerPresentation")
    factor = _finite(relative_scale, name="relative scale")
    if factor <= 0.0:
        raise ValueError("relative scale must be positive")
    baseline_scale = baseline.uniform_visual_scale
    target_extent = (
        baseline.viewport_extent
        if viewport_extent is None
        else _positive_size(viewport_extent, name="viewport extent")
    )
    style = baseline.shell_style
    policy = VisualizerModePresentationPolicy(
        shell_policy=baseline.shell_policy,
        clip_policy=baseline.clip_policy,
        viewport_resize_capable=baseline.viewport_resize_capable,
    )
    target_rotation = (
        baseline.content_rotation_quarters
        if content_rotation_quarters is None
        else normalize_content_rotation_quarters(content_rotation_quarters)
    )

    def _authored_scalar(name: str) -> float:
        return float(style[name]) / baseline_scale

    shadow_offset = style["shadow_offset"]
    shadow_extensions = style["shadow_extensions"]
    return resolve_visualizer_presentation(
        policy=policy,
        display_size=display_size,
        outer_origin=outer_origin,
        dpr=baseline.dpr,
        uniform_visual_scale=baseline_scale * factor,
        viewport_extent=target_extent,
        committed_outer_size=committed_outer_size,
        content_rotation_quarters=target_rotation,
        scene_fade=baseline.scene_fade,
        content_fade=baseline.content_fade,
        border_width=float(style["authored_border_width"]),
        corner_radius=float(style["authored_corner_radius"]),
        content_inset=_authored_scalar("content_inset"),
        background_color=style["background_color"],
        border_color=style["border_color"],
        shadow_enabled=bool(style["shadow_enabled"]),
        shadow_color=style["shadow_color"],
        shadow_blur=_authored_scalar("shadow_blur"),
        shadow_offset=(
            float(shadow_offset[0]) / baseline_scale,
            float(shadow_offset[1]) / baseline_scale,
        ),
        shadow_spread=_authored_scalar("shadow_spread"),
        shadow_extensions=tuple(
            float(value) / baseline_scale for value in shadow_extensions
        ),
    )


def resize_visualizer_presentation_uniformly(
    baseline: ResolvedVisualizerPresentation,
    *,
    display_size: Sequence[object],
    outer_origin: Sequence[object],
    relative_scale: float,
) -> ResolvedVisualizerPresentation:
    """Resize one resolved presentation uniformly (baseline extent preserved)."""

    return resize_visualizer_presentation(
        baseline,
        display_size=display_size,
        outer_origin=outer_origin,
        relative_scale=relative_scale,
        viewport_extent=None,
    )


__all__ = [
    "CANONICAL_VISUALIZER_BASELINE_ASPECT_RATIO",
    "CANONICAL_VISUALIZER_BASELINE_VIEWPORT_SIZE",
    "resize_visualizer_presentation",
    "resize_visualizer_presentation_uniformly",
    "resolve_visualizer_presentation",
]
