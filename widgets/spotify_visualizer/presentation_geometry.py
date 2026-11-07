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

# Expanded Visualizer (plan 01 M2, amended 7 Nov): the wallpaper left outside the expanded card's chrome, in logical
# pixels. Full display is never edge to edge (operator: "we have the overscan rule ... for a good reason"), and the
# operator asked the card to reach much closer to the display's borders than the ordinary edge margin. This is the
# only constant in the inset; everything else is the card's own chrome (``expanded_card_inset``). Two logical
# pixels (three device pixels at 150 %) is the smallest ring of wallpaper that still reads as a gap beyond the
# card's frame on every DPR, so the card is plainly a card near the display's extents, not a bezel line.
EXPANDED_CARD_EDGE_GAP = 2.0


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
        if committed_outer_size is not None
        else min(requested_scale, display_width / extent_width, display_height / extent_height)
    )
    outer_width = extent_width * resolved_scale
    outer_height = extent_height * resolved_scale
    if committed_outer_size is not None:
        # Freeform-3D CUSTOM has two independent authored extents: the outer
        # stage rect and the renderer's logical viewport. A width-derived
        # height silently discards the saved stage's authored aspect when
        # switching between independent freeform profiles. The stage is one
        # persisted authority; do not reverse-infer its height from the render
        # world. Framed 3D modes do not enter this branch: they intentionally
        # share the planar/card geometry contract with framed 2D modes.
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


def expanded_card_inset(ordinary: ResolvedVisualizerPresentation) -> float:
    """How far inside the display's logical rect the expanded card sits, on every side (logical px).

    Only what the card's own chrome needs (operator, 7 Nov: "Don't reach nearly close enough to the screen borders";
    the card keeps its border colour and surface, never edge to edge), plus ``EXPANDED_CARD_EDGE_GAP``:

    * the card border width, the one Card Border Width every card draws (``resolve_card_border_width_px``, AC-09,
      carried by the ordinary record as ``authored_border_width``): the frame is set off from the display edge by
      its own width, so it reads as the card's frame and not as the bezel;
    * when the card casts a shadow, the shadow's displaced body beyond the card (signed base offset plus the
      directional Extra Offset, exactly what the scene's card-shadow underlay adds to the card rect), on the side
      that reaches furthest, so the shadow's silhouette stays on the display.

    The shadow's blur falloff and the transient hover glow halo fade to nothing and may meet the display edge:
    keeping them whole would put the card about 30 px in again (the ordinary edge margin the operator rejected). The
    ordinary card never uses this (its slot is Media's edge margin).
    """

    style = ordinary.shell_style
    inset = float(style["authored_border_width"])
    if bool(style["shadow_enabled"]):
        offset_x, offset_y = (float(value) for value in style["shadow_offset"])
        left, top, right, bottom = (float(value) for value in style["shadow_extensions"])
        inset += max(
            max(0.0, -offset_x) + left,
            max(0.0, -offset_y) + top,
            max(0.0, offset_x) + right,
            max(0.0, offset_y) + bottom,
        )
    return inset + EXPANDED_CARD_EDGE_GAP


def resolve_expanded_visualizer_presentation(
    ordinary: ResolvedVisualizerPresentation,
    *,
    display_size: Sequence[object],
    dpr: float | None = None,
) -> ResolvedVisualizerPresentation:
    """The display-wide variant of one resolved ordinary presentation (Expanded Visualizer, plan 01 §B2/§0.6).

    Expansion is a viewport, not a layout, and full display is not edge to edge (operator, 7 Nov): the Visualizer
    card is placed near the display's visible extents, inset on every side by only what its own chrome needs
    (``expanded_card_inset``), and keeps its chrome: border colour and width, corner radius, shadow and surface.
    ``display_size`` is the display's logical rect (the monitor, never the R-63 overscanned window). The ordinary
    record it derives from is never changed or persisted. The world grows on the card's long axis only, so the
    whole ordinary world stays in view (its extent is contained, never cropped): on an inset card wider than the
    ordinary world's aspect the extent keeps its height and widens to the card's aspect; on a narrower (e.g.
    portrait) display it keeps its width and grows taller. Uniform scale then maps that world onto the inset card, so
    nothing is stretched anisotropically and pixel-like sizes follow the uniform scale as at the card. A framed 3D
    camera keeps its lens and pose; its aperture follows the extent's height exactly as an edge-resized card's does
    (``framed_aperture_scale``). Shell, clip, card chrome (border width, corner radius, colours, and the shadow as
    the card draws it: chrome, not world, so it is not magnified with the display-wide world) and content
    orientation are the ordinary record's, through the same canonical resolver; only DPR may differ (the target
    display's).
    """

    if not isinstance(ordinary, ResolvedVisualizerPresentation):
        raise TypeError("ordinary must be a ResolvedVisualizerPresentation")
    display_width, display_height = _positive_size(display_size, name="display size")
    # Never more than a quarter of the shorter side: a card always remains.
    margin = min(expanded_card_inset(ordinary), min(display_width, display_height) / 4.0)
    card_width, card_height = display_width - 2.0 * margin, display_height - 2.0 * margin
    extent_width, extent_height = ordinary.viewport_extent
    card_aspect = card_width / card_height
    if card_aspect >= extent_width / extent_height:
        expanded_extent = (extent_height * card_aspect, extent_height)
        scale = card_height / extent_height
    else:
        expanded_extent = (extent_width, extent_width / card_aspect)
        scale = card_width / extent_width
    resolved_dpr = ordinary.dpr if dpr is None else _finite(dpr, name="DPR")
    style = ordinary.shell_style
    baseline_scale = ordinary.uniform_visual_scale

    def _authored(name: str) -> float:
        return float(style[name]) / baseline_scale

    def _as_drawn(value: object) -> float:
        # The canonical resolver multiplies shadow geometry by the uniform scale; handing it the drawn value over
        # the display-wide scale makes the expanded card draw exactly the shadow the card draws.
        return float(value) / scale

    shadow_offset = style["shadow_offset"]
    return resolve_visualizer_presentation(
        policy=VisualizerModePresentationPolicy(
            shell_policy=ordinary.shell_policy,
            clip_policy=ordinary.clip_policy,
            viewport_resize_capable=ordinary.viewport_resize_capable,
        ),
        display_size=(display_width, display_height),
        outer_origin=(margin, margin),
        dpr=resolved_dpr,
        uniform_visual_scale=scale,
        viewport_extent=expanded_extent,
        # The inset display rect is the one stage authority: exact, never re-derived from extent x scale.
        committed_outer_size=(card_width, card_height),
        content_rotation_quarters=ordinary.content_rotation_quarters,
        scene_fade=ordinary.scene_fade,
        content_fade=ordinary.content_fade,
        border_width=float(style["authored_border_width"]),
        corner_radius=float(style["authored_corner_radius"]),
        content_inset=_authored("content_inset"),
        background_color=style["background_color"],
        border_color=style["border_color"],
        shadow_enabled=bool(style["shadow_enabled"]),
        shadow_color=style["shadow_color"],
        shadow_blur=_as_drawn(style["shadow_blur"]),
        shadow_offset=(_as_drawn(shadow_offset[0]), _as_drawn(shadow_offset[1])),
        shadow_spread=_as_drawn(style["shadow_spread"]),
        shadow_extensions=tuple(_as_drawn(value) for value in style["shadow_extensions"]),
    )


def framed_aperture_scale(presentation: ResolvedVisualizerPresentation, *, content: bool = False) -> float:
    """Sensor height relative to the canonical authored window.

    Edge resizing reveals/crops world; uniform card scaling changes display size
    only. This never changes the authored lens, eye, world or pixel aspect.
    """
    if not content:
        return presentation.viewport_extent[1]/presentation.baseline_viewport_size[1]
    # Framed historical CUSTOM stages can have independent outer/world aspects.
    # Use their actual vertical projection scale, never the width-derived mesh
    # scale used by other freeform modes.
    outer_height=presentation.outer_rect[3]
    vertical_scale=outer_height/presentation.viewport_extent[1]
    reference_height=vertical_scale*presentation.baseline_viewport_size[1]
    style=presentation.shell_style
    authored_inset=float(style['content_inset'])/presentation.uniform_visual_scale
    reference_inset=2.*(float(style['authored_border_width'])+authored_inset*vertical_scale)
    return presentation.content_rect[3]/max(1e-6,reference_height-reference_inset)


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
    "EXPANDED_CARD_EDGE_GAP",
    "expanded_card_inset",
    "resize_visualizer_presentation",
    "resolve_expanded_visualizer_presentation",
    "resize_visualizer_presentation_uniformly",
    "resolve_visualizer_presentation",
    "framed_aperture_scale",
]
