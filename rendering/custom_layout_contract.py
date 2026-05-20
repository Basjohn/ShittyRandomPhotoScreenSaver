"""Contracts and geometry helpers for CUSTOM widget layout editing.

The storage format is intentionally display-local and normalized so saved
layouts remain adaptable across resolution and DPR changes while still
reapplying to the same physical display identity when possible.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from PySide6.QtCore import QPoint, QRect, QSize
from PySide6.QtGui import QGuiApplication, QScreen

from rendering.multi_monitor_coordinator import MultiMonitorCoordinator


CUSTOM_LAYOUT_VERSION = 1
CUSTOM_LAYOUT_SETTINGS_KEY = "custom_layout"
CUSTOM_LAYOUT_RESTORE_VERSION = 1
CUSTOM_LAYOUT_RESTORE_SETTINGS_KEY = "custom_layout_restore"
CUSTOM_LAYOUT_GRID_STEP_PX = 12
CUSTOM_LAYOUT_SNAP_THRESHOLD_PX = 24
CUSTOM_LAYOUT_SNAP_GUTTER_PX = 0
CUSTOM_LAYOUT_TRANSFER_THRESHOLD_PX = 28
CUSTOM_LAYOUT_MIN_WIDGET_SIZE = QSize(80, 48)


@dataclass(frozen=True)
class NormalizedRect:
    x: float
    y: float
    width: float
    height: float

    def to_mapping(self) -> dict[str, float]:
        return {
            "x": float(self.x),
            "y": float(self.y),
            "width": float(self.width),
            "height": float(self.height),
        }


@dataclass(frozen=True)
class CustomLayoutEntry:
    widget_id: str
    rect: NormalizedRect
    size_payload: dict[str, Any]
    resize_mode: str = "none"

    def to_mapping(self) -> dict[str, Any]:
        return {
            "rect": self.rect.to_mapping(),
            "size_payload": dict(self.size_payload),
            "resize_mode": self.resize_mode,
        }


@dataclass(frozen=True)
class SnapGuide:
    position: int
    kind: str
    distance: int = 0


@dataclass(frozen=True)
class SnapResolution:
    rect: QRect
    vertical_guides: tuple[SnapGuide, ...] = ()
    horizontal_guides: tuple[SnapGuide, ...] = ()
    vertical_assists: tuple[SnapGuide, ...] = ()
    horizontal_assists: tuple[SnapGuide, ...] = ()


def get_screen_signature(screen: QScreen | None) -> str:
    """Return the stable display identity used for CUSTOM layout bindings."""

    return MultiMonitorCoordinator._screen_signature(screen)


def get_screen_signature_aliases(screen: QScreen | None) -> tuple[str, ...]:
    """Return canonical plus legacy-compatible signatures for a screen."""

    if screen is None:
        return ("screen:none",)

    aliases: list[str] = []
    canonical = get_screen_signature(screen)
    if canonical:
        aliases.append(canonical)

    identity_parts: list[str] = []
    for label, getter in (
        ("serial", getattr(screen, "serialNumber", None)),
        ("manufacturer", getattr(screen, "manufacturer", None)),
        ("model", getattr(screen, "model", None)),
        ("name", getattr(screen, "name", None)),
    ):
        try:
            if callable(getter):
                value = getter()
                if value:
                    identity_parts.append(f"{label}:{value}")
        except Exception:
            continue

    try:
        geom = screen.geometry()
        geom_part = f"geom:{geom.x()}_{geom.y()}_{geom.width()}x{geom.height()}"
    except Exception:
        geom_part = ""

    legacy = "|".join(identity_parts + ([geom_part] if geom_part else []))
    if legacy and legacy not in aliases:
        aliases.append(legacy)

    if geom_part and geom_part not in aliases and not identity_parts:
        aliases.append(geom_part)

    return tuple(alias for alias in aliases if alias)


def build_default_custom_layout_map() -> dict[str, Any]:
    return {
        "version": CUSTOM_LAYOUT_VERSION,
        "displays": {},
    }


def build_default_custom_layout_restore_map() -> dict[str, Any]:
    return {
        "version": CUSTOM_LAYOUT_RESTORE_VERSION,
        "widgets": {},
    }


def load_custom_layout_map(widgets_config: Mapping[str, Any] | None) -> dict[str, Any]:
    """Return a normalized custom-layout mapping from a widgets settings map."""

    candidate = (
        widgets_config.get(CUSTOM_LAYOUT_SETTINGS_KEY, {})
        if isinstance(widgets_config, Mapping)
        else {}
    )
    if not isinstance(candidate, Mapping):
        return build_default_custom_layout_map()

    displays = candidate.get("displays", {})
    if not isinstance(displays, Mapping):
        displays = {}

    return {
        "version": int(candidate.get("version", CUSTOM_LAYOUT_VERSION) or CUSTOM_LAYOUT_VERSION),
        "displays": {
            str(screen_key): dict(layouts) if isinstance(layouts, Mapping) else {}
            for screen_key, layouts in displays.items()
        },
    }


def write_custom_layout_map(
    widgets_config: dict[str, Any],
    custom_layout_map: Mapping[str, Any],
) -> dict[str, Any]:
    """Persist a normalized custom layout map back into the widgets config."""

    widgets_config[CUSTOM_LAYOUT_SETTINGS_KEY] = {
        "version": int(custom_layout_map.get("version", CUSTOM_LAYOUT_VERSION) or CUSTOM_LAYOUT_VERSION),
        "displays": {
            str(screen_key): dict(layouts) if isinstance(layouts, Mapping) else {}
            for screen_key, layouts in dict(custom_layout_map.get("displays", {})).items()
        },
    }
    return widgets_config


def load_custom_layout_restore_map(widgets_config: Mapping[str, Any] | None) -> dict[str, Any]:
    """Return normalized authored-layout restore metadata from widgets config."""

    candidate = (
        widgets_config.get(CUSTOM_LAYOUT_RESTORE_SETTINGS_KEY, {})
        if isinstance(widgets_config, Mapping)
        else {}
    )
    if not isinstance(candidate, Mapping):
        return build_default_custom_layout_restore_map()

    widgets = candidate.get("widgets", {})
    if not isinstance(widgets, Mapping):
        widgets = {}

    normalized_widgets: dict[str, dict[str, str]] = {}
    for widget_id, payload in widgets.items():
        if not isinstance(payload, Mapping):
            continue
        position = str(payload.get("position", "") or "").strip()
        monitor = str(payload.get("monitor", "ALL") or "ALL").strip() or "ALL"
        if not position:
            continue
        normalized_widgets[str(widget_id)] = {
            "position": position,
            "monitor": monitor,
        }

    return {
        "version": int(candidate.get("version", CUSTOM_LAYOUT_RESTORE_VERSION) or CUSTOM_LAYOUT_RESTORE_VERSION),
        "widgets": normalized_widgets,
    }


def write_custom_layout_restore_map(
    widgets_config: dict[str, Any],
    restore_map: Mapping[str, Any],
) -> dict[str, Any]:
    """Persist authored-layout restore metadata back into widgets config."""

    widgets_payload = restore_map.get("widgets", {})
    if not isinstance(widgets_payload, Mapping):
        widgets_payload = {}
    widgets_config[CUSTOM_LAYOUT_RESTORE_SETTINGS_KEY] = {
        "version": int(restore_map.get("version", CUSTOM_LAYOUT_RESTORE_VERSION) or CUSTOM_LAYOUT_RESTORE_VERSION),
        "widgets": {
            str(widget_id): dict(payload)
            for widget_id, payload in widgets_payload.items()
            if isinstance(payload, Mapping)
        },
    }
    return widgets_config


def get_custom_layout_restore_entry(
    restore_map: Mapping[str, Any],
    widget_id: str,
) -> dict[str, str] | None:
    widgets = restore_map.get("widgets", {})
    if not isinstance(widgets, Mapping):
        return None
    payload = widgets.get(widget_id)
    if not isinstance(payload, Mapping):
        return None
    position = str(payload.get("position", "") or "").strip()
    monitor = str(payload.get("monitor", "ALL") or "ALL").strip() or "ALL"
    if not position:
        return None
    return {
        "position": position,
        "monitor": monitor,
    }


def set_custom_layout_restore_entry(
    restore_map: dict[str, Any],
    widget_id: str,
    *,
    position: str,
    monitor: str,
) -> dict[str, Any]:
    widgets = restore_map.setdefault("widgets", {})
    if not isinstance(widgets, dict):
        widgets = {}
        restore_map["widgets"] = widgets
    widgets[str(widget_id)] = {
        "position": str(position),
        "monitor": str(monitor or "ALL"),
    }
    return restore_map


def get_screen_layout_entries(
    custom_layout_map: Mapping[str, Any],
    screen_signature: str,
) -> dict[str, Any]:
    displays = custom_layout_map.get("displays", {})
    if not isinstance(displays, Mapping):
        return {}
    layouts = displays.get(screen_signature, {})
    return dict(layouts) if isinstance(layouts, Mapping) else {}


def resolve_screen_layout_signature(
    custom_layout_map: Mapping[str, Any],
    screen: QScreen | None,
) -> str | None:
    """Return the matching saved signature for a live screen, if any."""

    displays = custom_layout_map.get("displays", {})
    if not isinstance(displays, Mapping):
        return None
    for alias in get_screen_signature_aliases(screen):
        if alias not in displays:
            continue
        layouts = displays.get(alias)
        if isinstance(layouts, Mapping):
            return alias

    canonical = get_screen_signature(screen)
    if canonical and "|geom:" not in canonical:
        legacy_prefix = f"{canonical}|geom:"
        for saved_signature, layouts in displays.items():
            if not isinstance(saved_signature, str):
                continue
            if saved_signature.startswith(legacy_prefix) and isinstance(layouts, Mapping):
                return saved_signature
    return None


def get_screen_layout_entries_for_screen(
    custom_layout_map: Mapping[str, Any],
    screen: QScreen | None,
) -> tuple[str | None, dict[str, Any]]:
    """Return the matched signature and layouts for a live screen."""

    matched = resolve_screen_layout_signature(custom_layout_map, screen)
    if matched is None:
        return None, {}
    return matched, get_screen_layout_entries(custom_layout_map, matched)


def canonicalize_screen_layout_bucket(
    custom_layout_map: dict[str, Any],
    screen: QScreen | None,
) -> str | None:
    """Move any legacy matching bucket onto the canonical signature."""

    canonical = get_screen_signature(screen)
    if not canonical:
        return None

    displays = custom_layout_map.setdefault("displays", {})
    if not isinstance(displays, dict):
        displays = {}
        custom_layout_map["displays"] = displays

    matched = resolve_screen_layout_signature(custom_layout_map, screen)
    if matched is None:
        displays.setdefault(canonical, {})
        return canonical

    if matched == canonical:
        displays.setdefault(canonical, {})
        return canonical

    source_layouts = displays.get(matched, {})
    target_layouts = displays.get(canonical, {})
    if not isinstance(source_layouts, dict):
        source_layouts = dict(source_layouts) if isinstance(source_layouts, Mapping) else {}
    if not isinstance(target_layouts, dict):
        target_layouts = dict(target_layouts) if isinstance(target_layouts, Mapping) else {}
    merged = dict(source_layouts)
    merged.update(target_layouts)
    displays[canonical] = merged
    displays.pop(matched, None)
    return canonical


def set_screen_layout_entry(
    custom_layout_map: dict[str, Any],
    screen_signature: str,
    widget_id: str,
    entry: CustomLayoutEntry,
) -> dict[str, Any]:
    displays = custom_layout_map.setdefault("displays", {})
    if not isinstance(displays, dict):
        displays = {}
        custom_layout_map["displays"] = displays
    layouts = displays.setdefault(screen_signature, {})
    if not isinstance(layouts, dict):
        layouts = {}
        displays[screen_signature] = layouts
    layouts[widget_id] = entry.to_mapping()
    return custom_layout_map


def remove_screen_layout_entry(
    custom_layout_map: dict[str, Any],
    screen_signature: str,
    widget_id: str,
) -> dict[str, Any]:
    displays = custom_layout_map.get("displays", {})
    if not isinstance(displays, dict):
        return custom_layout_map
    layouts = displays.get(screen_signature, {})
    if not isinstance(layouts, dict):
        return custom_layout_map
    layouts.pop(widget_id, None)
    if not layouts:
        displays.pop(screen_signature, None)
    return custom_layout_map


def deserialize_custom_layout_entry(
    widget_id: str,
    payload: Mapping[str, Any] | None,
) -> CustomLayoutEntry | None:
    if not isinstance(payload, Mapping):
        return None
    rect_payload = payload.get("rect", {})
    if not isinstance(rect_payload, Mapping):
        return None
    try:
        rect = NormalizedRect(
            x=float(rect_payload.get("x", 0.0) or 0.0),
            y=float(rect_payload.get("y", 0.0) or 0.0),
            width=float(rect_payload.get("width", 0.0) or 0.0),
            height=float(rect_payload.get("height", 0.0) or 0.0),
        )
    except Exception:
        return None

    if rect.width <= 0.0 or rect.height <= 0.0:
        return None

    size_payload = payload.get("size_payload", {})
    if not isinstance(size_payload, Mapping):
        size_payload = {}

    resize_mode = str(payload.get("resize_mode", "none") or "none")
    return CustomLayoutEntry(
        widget_id=widget_id,
        rect=rect,
        size_payload=dict(size_payload),
        resize_mode=resize_mode,
    )


def normalize_local_rect(local_rect: QRect, display_size: QSize) -> NormalizedRect:
    width = max(1, int(display_size.width()))
    height = max(1, int(display_size.height()))
    return NormalizedRect(
        x=float(local_rect.x()) / float(width),
        y=float(local_rect.y()) / float(height),
        width=float(local_rect.width()) / float(width),
        height=float(local_rect.height()) / float(height),
    )


def denormalize_local_rect(normalized: NormalizedRect, display_size: QSize) -> QRect:
    width = max(1, int(display_size.width()))
    height = max(1, int(display_size.height()))
    x = int(round(normalized.x * width))
    y = int(round(normalized.y * height))
    w = max(1, int(round(normalized.width * width)))
    h = max(1, int(round(normalized.height * height)))
    return QRect(x, y, w, h)


def snap_rect_to_grid(
    rect: QRect,
    *,
    step_px: int = CUSTOM_LAYOUT_GRID_STEP_PX,
) -> QRect:
    step = max(1, int(step_px))
    return QRect(
        int(round(rect.x() / step) * step),
        int(round(rect.y() / step) * step),
        max(1, int(round(rect.width() / step) * step)),
        max(1, int(round(rect.height() / step) * step)),
    )


def _snap_axis_position(
    position: int,
    span: int,
    boundary_span: int,
    peer_spans: list[tuple[int, int]],
    *,
    threshold_px: int = CUSTOM_LAYOUT_SNAP_THRESHOLD_PX,
    gutter_px: int = CUSTOM_LAYOUT_SNAP_GUTTER_PX,
) -> tuple[int, tuple[SnapGuide, ...]]:
    threshold = max(0, int(threshold_px))
    gutter = max(0, int(gutter_px))
    max_position = max(0, int(boundary_span) - max(1, int(span)))
    current = max(0, min(int(position), max_position))

    candidates: list[tuple[int, int, str, int]] = [
        (0, 1, "edge", 0),
        (max_position, 1, "edge", boundary_span),
    ]

    step = max(1, int(CUSTOM_LAYOUT_GRID_STEP_PX))
    nearest_grid = int(round(current / step) * step)
    for grid_candidate in {
        max(0, min(nearest_grid - step, max_position)),
        max(0, min(nearest_grid, max_position)),
        max(0, min(nearest_grid + step, max_position)),
    }:
        candidates.append((grid_candidate, 0, "grid", grid_candidate))

    if gutter:
        candidates.extend(
            [
                (min(gutter, max_position), 2, "gutter", min(gutter, max_position)),
                (max(0, max_position - gutter), 2, "gutter", boundary_span - gutter),
            ]
        )

    for peer_start, peer_end in peer_spans:
        peer_start = int(peer_start)
        peer_end = int(peer_end)
        candidates.extend(
            {
                (peer_start, 1, "peer", peer_start),
                (peer_end - span, 1, "peer", peer_end),
                (peer_end, 1, "peer", peer_end),
                (peer_start - span, 1, "peer", peer_start),
            }
        )
        if gutter:
            candidates.extend(
                {
                    (peer_start + gutter, 2, "peer_gutter", peer_start + gutter),
                    (peer_end - span - gutter, 2, "peer_gutter", peer_end - gutter),
                    (peer_end + gutter, 2, "peer_gutter", peer_end + gutter),
                    (peer_start - span - gutter, 2, "peer_gutter", peer_start - gutter),
                }
            )

    best = current
    best_priority = 99
    best_delta = threshold + 1
    best_kind = ""
    best_guide = current
    for candidate, priority, kind, guide_position in candidates:
        candidate = max(0, min(int(candidate), max_position))
        delta = abs(candidate - current)
        if delta > threshold:
            continue
        if delta < best_delta or (delta == best_delta and priority < best_priority):
            best = candidate
            best_priority = priority
            best_delta = delta
            best_kind = kind
            best_guide = guide_position
    guides: list[SnapGuide] = []
    if best_delta <= threshold and best_kind:
        guides.append(
            SnapGuide(
                position=max(0, min(int(best_guide), max(0, boundary_span - 1))),
                kind=best_kind,
                distance=int(best_delta),
            )
        )

    return best, tuple(guides)


def _collect_peer_assists_for_axis(
    snapped_position: int,
    span: int,
    boundary_span: int,
    peer_spans: list[tuple[int, int]],
    *,
    threshold_px: int,
    primary_guide: SnapGuide | None,
) -> tuple[SnapGuide, ...]:
    threshold = max(0, int(threshold_px))
    snapped_start = int(snapped_position)
    snapped_end = int(snapped_position) + max(1, int(span))
    max_guide_position = max(0, int(boundary_span) - 1)

    assist_map: dict[int, SnapGuide] = {}
    for peer_start, peer_end in peer_spans:
        for guide_position in (int(peer_start), int(peer_end)):
            distance = min(
                abs(snapped_start - guide_position),
                abs(snapped_end - guide_position),
            )
            if distance > threshold:
                continue
            if (
                primary_guide is not None
                and primary_guide.kind == "peer"
                and primary_guide.position == guide_position
            ):
                continue
            guide = SnapGuide(
                position=max(0, min(guide_position, max_guide_position)),
                kind="peer",
                distance=int(distance),
            )
            prior = assist_map.get(guide.position)
            if prior is None or guide.distance < prior.distance:
                assist_map[guide.position] = guide
    return tuple(sorted(assist_map.values(), key=lambda guide: (guide.distance, guide.position)))


def snap_local_rect_for_edit(
    rect: QRect,
    display_size: QSize,
    *,
    peer_rects: list[QRect] | tuple[QRect, ...] = (),
    threshold_px: int = CUSTOM_LAYOUT_SNAP_THRESHOLD_PX,
    gutter_px: int = CUSTOM_LAYOUT_SNAP_GUTTER_PX,
    min_size: QSize = CUSTOM_LAYOUT_MIN_WIDGET_SIZE,
) -> QRect:
    return resolve_snap_local_rect_for_edit(
        rect,
        display_size,
        peer_rects=peer_rects,
        threshold_px=threshold_px,
        gutter_px=gutter_px,
        min_size=min_size,
    ).rect


def resolve_snap_local_rect_for_edit(
    rect: QRect,
    display_size: QSize,
    *,
    peer_rects: list[QRect] | tuple[QRect, ...] = (),
    threshold_px: int = CUSTOM_LAYOUT_SNAP_THRESHOLD_PX,
    gutter_px: int = CUSTOM_LAYOUT_SNAP_GUTTER_PX,
    min_size: QSize = CUSTOM_LAYOUT_MIN_WIDGET_SIZE,
) -> SnapResolution:
    """Snap a display-local edit rect to nearby guides without crossing bounds.

    The rect may snap to:
    - the real display edges
    - the shared display-local grid
    - peer widget edges
    - optional secondary gutter spacing helpers
    """

    clamped = clamp_local_rect_to_bounds(rect, display_size, min_size=min_size)
    peer_list = [QRect(peer) for peer in peer_rects if isinstance(peer, QRect)]
    x, vertical_candidates = _snap_axis_position(
        clamped.x(),
        clamped.width(),
        display_size.width(),
        [(peer.x(), peer.x() + peer.width()) for peer in peer_list],
        threshold_px=threshold_px,
        gutter_px=gutter_px,
    )
    y, horizontal_candidates = _snap_axis_position(
        clamped.y(),
        clamped.height(),
        display_size.height(),
        [(peer.y(), peer.y() + peer.height()) for peer in peer_list],
        threshold_px=threshold_px,
        gutter_px=gutter_px,
    )
    vertical_guides = vertical_candidates[:1]
    vertical_primary = vertical_guides[0] if vertical_guides else None
    vertical_assists = _collect_peer_assists_for_axis(
        x,
        clamped.width(),
        display_size.width(),
        [(peer.x(), peer.x() + peer.width()) for peer in peer_list],
        threshold_px=threshold_px,
        primary_guide=vertical_primary,
    )
    horizontal_guides = horizontal_candidates[:1]
    horizontal_primary = horizontal_guides[0] if horizontal_guides else None
    horizontal_assists = _collect_peer_assists_for_axis(
        y,
        clamped.height(),
        display_size.height(),
        [(peer.y(), peer.y() + peer.height()) for peer in peer_list],
        threshold_px=threshold_px,
        primary_guide=horizontal_primary,
    )
    return SnapResolution(
        rect=clamp_local_rect_to_bounds(
            QRect(x, y, clamped.width(), clamped.height()),
            display_size,
            min_size=min_size,
        ),
        vertical_guides=vertical_guides,
        horizontal_guides=horizontal_guides,
        vertical_assists=vertical_assists,
        horizontal_assists=horizontal_assists,
    )


def clamp_local_rect_to_bounds(
    rect: QRect,
    display_size: QSize,
    *,
    min_size: QSize = CUSTOM_LAYOUT_MIN_WIDGET_SIZE,
) -> QRect:
    max_width = max(1, int(display_size.width()))
    max_height = max(1, int(display_size.height()))
    width = max(min_size.width(), min(rect.width(), max_width))
    height = max(min_size.height(), min(rect.height(), max_height))
    x = max(0, min(rect.x(), max_width - width))
    y = max(0, min(rect.y(), max_height - height))
    return QRect(x, y, width, height)


def clamp_global_rect_to_screen(
    global_rect: QRect,
    screen: QScreen,
    *,
    min_size: QSize = CUSTOM_LAYOUT_MIN_WIDGET_SIZE,
) -> QRect:
    geom = screen.geometry()
    local = QRect(
        global_rect.x() - geom.x(),
        global_rect.y() - geom.y(),
        global_rect.width(),
        global_rect.height(),
    )
    clamped = clamp_local_rect_to_bounds(local, geom.size(), min_size=min_size)
    return QRect(
        geom.x() + clamped.x(),
        geom.y() + clamped.y(),
        clamped.width(),
        clamped.height(),
    )


def choose_best_screen_for_global_rect(
    global_rect: QRect,
    *,
    cursor_global: QPoint | None = None,
    screens: list[QScreen] | None = None,
) -> QScreen | None:
    screen_iter = list(screens) if screens is not None else list(QGuiApplication.screens())
    if not screen_iter:
        return None

    best_screen: QScreen | None = None
    best_overlap = -1
    overlap_candidates: list[QScreen] = []
    for screen in screen_iter:
        overlap = screen.geometry().intersected(global_rect)
        area = max(0, overlap.width()) * max(0, overlap.height())
        if area > best_overlap:
            best_overlap = area
            overlap_candidates = [screen]
            best_screen = screen
        elif area == best_overlap:
            overlap_candidates.append(screen)

    if len(overlap_candidates) <= 1:
        return best_screen

    if cursor_global is not None:
        for screen in overlap_candidates:
            if screen.geometry().contains(cursor_global):
                return screen

    return overlap_candidates[0]


def should_transfer_rect_to_screen(
    global_rect: QRect,
    *,
    current_screen: QScreen | None,
    candidate_screen: QScreen | None,
    cursor_global: QPoint | None = None,
    threshold_px: int = CUSTOM_LAYOUT_TRANSFER_THRESHOLD_PX,
) -> bool:
    """Return True only when a cross-display handoff looks intentional.

    Edit shells should not transfer ownership merely because another display
    wins a transient overlap calculation near an edge. A transfer only becomes
    eligible once the drag has been pushed materially beyond the current
    display boundary toward the candidate display.
    """

    if current_screen is None or candidate_screen is None or current_screen is candidate_screen:
        return False

    current_geom = current_screen.geometry()
    candidate_geom = candidate_screen.geometry()
    threshold = max(0, int(threshold_px))

    push_left = (
        candidate_geom.right() < current_geom.left()
        and global_rect.left() <= current_geom.left() - threshold
    )
    push_right = (
        candidate_geom.left() > current_geom.right()
        and global_rect.right() >= current_geom.right() + threshold
    )
    push_up = (
        candidate_geom.bottom() < current_geom.top()
        and global_rect.top() <= current_geom.top() - threshold
    )
    push_down = (
        candidate_geom.top() > current_geom.bottom()
        and global_rect.bottom() >= current_geom.bottom() + threshold
    )

    if not any((push_left, push_right, push_up, push_down)):
        return False

    if cursor_global is None:
        return True

    if candidate_geom.contains(cursor_global):
        return True

    if push_left and cursor_global.x() <= current_geom.left():
        return True
    if push_right and cursor_global.x() >= current_geom.right():
        return True
    if push_up and cursor_global.y() <= current_geom.top():
        return True
    if push_down and cursor_global.y() >= current_geom.bottom():
        return True
    return False
