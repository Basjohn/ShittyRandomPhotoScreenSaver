"""Presentation-neutral ordinary-widget outer-geometry resolution (H).

The Quick production path resolves each ordinary widget's outer display-space
rectangle from its **content-driven size** (the retained QML item's resolved
implicit content size), a named **anchor** (the persisted ``position`` setting),
a **margin**, and a min-visible **clamp** against the display bounds. A G CUSTOM
committed rectangle, when present, overrides this anchored placement.

This module owns only the pure geometry math. It reproduces the stable committed
placement of the legacy ``widgets/base_overlay_widget.py::_update_position``
anchor+margin+clamp path, with two deliberate omissions that are QWidget-era
artifacts rather than committed geometry:

- the visible-content padding compensation (``_compute_visual_offset``) is
  unnecessary because the retained item's reported implicit size is already the
  visible content and the ``OverlayCard`` shell owns padding; and
- pixel-shift offset is applied downstream by the Quick shared pixel-shift
  transform (``QuickAuxiliaryController``), so it must not be baked into the
  committed rectangle here or it would double-apply.

It imports no QWidget/Quick/settings/provider code — only the host geometry
dataclass — so it stays a pure, deterministically testable seam.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum

from .host import OverlayWidgetGeometry


# The universal default overlay margin (px) when neither the instance nor the
# canonical default carries one. Matches the legacy overlay default.
DEFAULT_MARGIN_PX = 30.0


# Matches the legacy min-visible clamp: a widget may be dragged/anchored partly
# off-display but always keeps this many pixels reachable on screen.
MIN_VISIBLE_PX = 10.0


class OverlayAnchor(Enum):
    """The nine canonical overlay anchors, keyed by canonical setting token."""

    TOP_LEFT = "top_left"
    TOP_CENTER = "top_center"
    TOP_RIGHT = "top_right"
    MIDDLE_LEFT = "middle_left"
    CENTER = "center"
    MIDDLE_RIGHT = "middle_right"
    BOTTOM_LEFT = "bottom_left"
    BOTTOM_CENTER = "bottom_center"
    BOTTOM_RIGHT = "bottom_right"

    @classmethod
    def from_setting(cls, value: object) -> "OverlayAnchor":
        """Normalize a persisted ``position`` value (e.g. ``"Top Right"``).

        Unknown/absent values resolve to ``TOP_RIGHT``, matching the legacy
        ``OverlayPosition.from_string`` fallback exactly.
        """

        token = str(value or "").strip().lower().replace(" ", "_")
        try:
            return cls(token)
        except ValueError:
            return cls.TOP_RIGHT


_LEFT_ANCHORS = frozenset(
    {OverlayAnchor.TOP_LEFT, OverlayAnchor.MIDDLE_LEFT, OverlayAnchor.BOTTOM_LEFT}
)
_RIGHT_ANCHORS = frozenset(
    {OverlayAnchor.TOP_RIGHT, OverlayAnchor.MIDDLE_RIGHT, OverlayAnchor.BOTTOM_RIGHT}
)
_TOP_ANCHORS = frozenset(
    {OverlayAnchor.TOP_LEFT, OverlayAnchor.TOP_CENTER, OverlayAnchor.TOP_RIGHT}
)
_BOTTOM_ANCHORS = frozenset(
    {
        OverlayAnchor.BOTTOM_LEFT,
        OverlayAnchor.BOTTOM_CENTER,
        OverlayAnchor.BOTTOM_RIGHT,
    }
)


def resolve_anchored_geometry(
    *,
    content_size: tuple[float, float],
    anchor: OverlayAnchor | str,
    margin: float,
    display_bounds: OverlayWidgetGeometry,
) -> OverlayWidgetGeometry:
    """Resolve the committed outer rectangle for a content-sized overlay widget.

    ``content_size`` is the retained item's resolved implicit content size.
    ``display_bounds`` is the display-space host rectangle (normally origin
    ``(0, 0)`` and the full display size). The returned rectangle keeps the
    content size and places it per the anchor/margin, clamped so at least
    :data:`MIN_VISIBLE_PX` stays on the display.
    """

    resolved_anchor = (
        anchor if isinstance(anchor, OverlayAnchor) else OverlayAnchor.from_setting(anchor)
    )
    width = float(content_size[0])
    height = float(content_size[1])
    if width <= 0.0 or height <= 0.0:
        raise ValueError(f"overlay content size must be positive: {content_size!r}")

    bounds_width = float(display_bounds.width)
    bounds_height = float(display_bounds.height)
    margin_px = float(margin)

    if resolved_anchor in _LEFT_ANCHORS:
        x = margin_px
    elif resolved_anchor in _RIGHT_ANCHORS:
        x = bounds_width - width - margin_px
    else:  # centered horizontally
        x = (bounds_width - width) / 2.0

    if resolved_anchor in _TOP_ANCHORS:
        y = margin_px
    elif resolved_anchor in _BOTTOM_ANCHORS:
        y = bounds_height - height - margin_px
    else:  # centered vertically
        y = (bounds_height - height) / 2.0

    # Min-visible clamp against the display bounds (legacy semantics).
    max_x = bounds_width - MIN_VISIBLE_PX
    max_y = bounds_height - MIN_VISIBLE_PX
    min_x = MIN_VISIBLE_PX - width
    min_y = MIN_VISIBLE_PX - height
    x = max(min_x, min(x, max_x))
    y = max(min_y, min(y, max_y))

    return OverlayWidgetGeometry(
        x=float(display_bounds.x) + x,
        y=float(display_bounds.y) + y,
        width=width,
        height=height,
    )


@dataclass(frozen=True)
class OverlayGeometryPolicy:
    """Resolved per-widget outer-geometry policy for one display generation.

    The policy carries the persisted anchor + margin and an optional G CUSTOM
    committed rectangle. ``resolve`` turns a live content size into the final
    outer rectangle: a committed CUSTOM rectangle wins outright (its size is the
    committed size, independent of live content), otherwise the content size is
    anchored per the persisted placement.
    """

    widget_id: str
    anchor: OverlayAnchor
    margin: float
    committed_rect: OverlayWidgetGeometry | None = None

    @property
    def has_committed_rect(self) -> bool:
        return self.committed_rect is not None

    def resolve(
        self,
        content_size: tuple[float, float],
        display_bounds: OverlayWidgetGeometry,
    ) -> OverlayWidgetGeometry:
        if self.committed_rect is not None:
            return self.committed_rect
        return resolve_anchored_geometry(
            content_size=content_size,
            anchor=self.anchor,
            margin=self.margin,
            display_bounds=display_bounds,
        )


def _resolve_margin(
    values: Mapping[str, object],
    canonical: Mapping[str, object],
) -> float:
    raw = values.get("margin", canonical.get("margin"))
    if raw is None:
        return DEFAULT_MARGIN_PX
    try:
        return float(raw)
    except (TypeError, ValueError):
        return DEFAULT_MARGIN_PX


def resolve_overlay_geometry_policy(
    widget_id: str,
    widgets_config: Mapping[str, object] | None,
    *,
    committed_rect: OverlayWidgetGeometry | None = None,
) -> OverlayGeometryPolicy:
    """Resolve the anchor + margin geometry policy for one widget instance.

    Reads the persisted ``position`` (anchor) and ``margin`` for ``widget_id``,
    falling back to canonical defaults and then to ``TOP_RIGHT`` / the default
    margin. ``committed_rect`` is an already-resolved G CUSTOM committed
    rectangle (display-space) that, when provided, overrides anchored placement.
    """

    from core.settings.defaults import get_default_settings

    config: Mapping[str, object] = (
        widgets_config if isinstance(widgets_config, Mapping) else {}
    )
    values = config.get(widget_id, {})
    if not isinstance(values, Mapping):
        values = {}
    canonical = get_default_settings().get("widgets", {}).get(widget_id, {})
    if not isinstance(canonical, Mapping):
        canonical = {}

    anchor = OverlayAnchor.from_setting(
        values.get("position", canonical.get("position"))
    )
    margin = _resolve_margin(values, canonical)
    return OverlayGeometryPolicy(
        widget_id=str(widget_id),
        anchor=anchor,
        margin=margin,
        committed_rect=committed_rect,
    )


class OverlayGeometryBinding:
    """Drive one retained item's outer geometry from live content size + policy.

    This is the Python half of the content-driven geometry contract (option A):
    the retained QML item reports its resolved implicit content size, and this
    binding turns that into the item's committed outer rectangle through the
    widget's :class:`OverlayGeometryPolicy` and the current display bounds. The
    display/runtime owner connects the QML implicit-size change signal to
    :meth:`update_content_size`; a topology change calls :meth:`set_display_bounds`
    to re-anchor.

    Identical effective geometry is a technical no-op: the geometry sink is only
    invoked when the resolved rectangle actually changes, so a content-size
    signal that does not move the committed rectangle never re-lays-out the item.
    A committed CUSTOM rectangle (carried by the policy) wins outright, so live
    content-size churn cannot disturb a user's CUSTOM placement.
    """

    def __init__(
        self,
        *,
        policy: OverlayGeometryPolicy,
        display_bounds: OverlayWidgetGeometry,
        geometry_sink,
    ) -> None:
        if not callable(geometry_sink):
            raise TypeError("overlay geometry sink must be callable")
        self._policy = policy
        self._display_bounds = display_bounds
        self._geometry_sink = geometry_sink
        self._last_content_size: tuple[float, float] | None = None
        self._current_geometry: OverlayWidgetGeometry | None = None

    @property
    def policy(self) -> OverlayGeometryPolicy:
        return self._policy

    @property
    def current_geometry(self) -> OverlayWidgetGeometry | None:
        return self._current_geometry

    def update_content_size(
        self, content_size: tuple[float, float]
    ) -> OverlayWidgetGeometry | None:
        """Resolve and apply geometry for a new content size; no-op if unchanged.

        Returns the newly applied geometry, or ``None`` when the resolved
        rectangle is identical to the current one (a technical no-op).
        """

        size = (float(content_size[0]), float(content_size[1]))
        # A non-positive size means the family has not declared a real preferred
        # size yet; keep any prior size rather than raising, and let a committed
        # CUSTOM rect (if any) still apply independently of content size.
        if size[0] > 0.0 and size[1] > 0.0:
            self._last_content_size = size
        return self._reapply()

    def set_display_bounds(
        self, display_bounds: OverlayWidgetGeometry
    ) -> OverlayWidgetGeometry | None:
        """Re-anchor against new display bounds (e.g. a topology change)."""

        self._display_bounds = display_bounds
        return self._reapply()

    def _reapply(self) -> OverlayWidgetGeometry | None:
        # A committed CUSTOM rectangle does not need a content size; anchored
        # placement does. Without a content size yet, there is nothing to apply.
        if self._policy.has_committed_rect:
            geometry = self._policy.resolve((1.0, 1.0), self._display_bounds)
        elif self._last_content_size is not None:
            geometry = self._policy.resolve(
                self._last_content_size, self._display_bounds
            )
        else:
            return None
        if geometry == self._current_geometry:
            return None
        self._current_geometry = geometry
        self._geometry_sink(geometry)
        return geometry


def connect_overlay_preferred_size(item, binding: OverlayGeometryBinding):
    """Wire a retained item's QML preferred-size report to a geometry binding.

    The retained ``OverlayWidget`` reports its declared preferred content size
    (size only) via the ``preferredContentSizeChanged`` signal; this connects
    that signal to :meth:`OverlayGeometryBinding.update_content_size` and applies
    the current declared size once. Python (the binding) owns anchor/clamp/outer
    geometry; QML never anchors itself. There is no width feedback, polling,
    timer or per-frame callback. Returns the initially applied geometry, if any.
    """

    signal = getattr(item, "preferredContentSizeChanged", None)
    if signal is not None and hasattr(signal, "connect"):
        signal.connect(
            lambda width, height: binding.update_content_size((width, height))
        )
    try:
        width = float(item.property("preferredContentWidth") or 0.0)
        height = float(item.property("preferredContentHeight") or 0.0)
    except (TypeError, ValueError):
        width = height = 0.0
    return binding.update_content_size((width, height))


__all__ = [
    "DEFAULT_MARGIN_PX",
    "MIN_VISIBLE_PX",
    "OverlayAnchor",
    "OverlayGeometryBinding",
    "OverlayGeometryPolicy",
    "connect_overlay_preferred_size",
    "resolve_anchored_geometry",
    "resolve_overlay_geometry_policy",
]
