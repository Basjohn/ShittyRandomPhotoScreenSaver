"""Fullscreen Edit (Expanded Visualizer M3c): the full-display overlays' geometry inside the one Edit session.

Operator, 8 Nov: "when we choose edit mode during a fullscreen visualizer we should be able to adjust the
size/position/placement of the toast and preset text elements and artwork instead of it going back to the full quick
scene. Like we can most geometry normally."

There is no second editor. Edit entered while the Visualizer is expanded opens the ``QuickCustomLayoutOwner``'s one
``CustomLayoutSession`` on the expanded display with the overlays' parts as its items, drawn and handled by the same
retained Edit layer (frames, corner handles, the wheel, Restore Size, snapping guides, undo, Save/Cancel, Enter/Esc).
This module is what differs about those items:

* **Items.** The preset toast, Now Playing's text block (with its Media Controls when shown) and Now Playing's artwork.
  The artwork stays beside its text: dragging either moves Now Playing as one; its handles size the artwork alone.
* **Geometry is the overlays' own canonical value**, never a rectangle the session owns: each item's
  ``current_size_payload`` is its draft placement (``core.settings.fullscreen_overlays.PLACEMENT_KEYS``: the offset
  from the anchor corner in fractions of the expanded card's safe area, ``scale``, ``artwork_scale``) and its
  rectangle is read back from the live QML after every projection, so a frame is always what is drawn (content
  size, stacking and the card's control reserves included). Positions stay relative to the safe area, so they reflow
  on displays of other sizes and DPRs.
* **Moves** snap with the ordinary Edit rule (``resolve_snap_local_rect_for_edit``) inside the safe area: its edges
  (and so its corners), its centre, and the other overlay's edges, centre and the 30 px gutter.
* **Scaling.** Corner handles and the wheel scale the preset toast and the text by ``scale`` (their font) and the
  artwork by ``artwork_scale``. A corner drag uses the drag-to-scale gesture of ordinary Edit and keeps the frame's
  opposite corner where it was; the wheel and Restore Size keep its top centre (as ordinary Edit does). The artwork
  grows from its place beside the text.
* **Single-axis sizing** (ordinary Edit's ``content_extent``: every part declares both content axes, so the same Edit
  layer draws the same side strips and, on the selected part, the same two-axis diagonal corners). A side handle
  changes only its axis: the text box's ``text_width`` / ``text_height`` (ems of the overlay's font; the text elides,
  or wraps into a taller box) or the artwork's ``artwork_width`` / ``artwork_height`` (factors of its square size; the
  image crops). The dragged edge follows the cursor under the ordinary resize rule (``edge_resize_rect``, bounded by
  the safe area) and snaps with ``resolve_resize_edge_snap`` (the safe area's centre, the other overlay's edges), the
  opposite edge staying put; the artwork again grows from its place. The untouched axis keeps its member exactly
  (natural stays natural); the stored extent is the one the overlay really drew (its floors and the safe area
  included). A uniform scale keeps the box (its extents are font-relative), as ordinary Edit's does; Restore Size
  returns the part's scale and extents to their canonical values, as ordinary Edit drops ``content_extent``.
* **Save** writes exactly the placement members into the one value; nothing else is in the session, so the ordinary
  layout and CUSTOM cannot change. Cancel restores the baseline (the committed value) through the session's own
  ``restore_baseline``.

The QML side (``ExpandedVisualizerOverlays.qml``) shows both overlays while editing and reports geometry changes; the
scene controller reads its geometry (``expanded_overlay_edit_geometry``) only at Edit edges.
"""
from __future__ import annotations

import math
from collections.abc import Callable, Mapping
from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from PySide6.QtCore import QPoint, QRect, QSize

from core.settings.fullscreen_overlays import (
    OFFSET_MAX,
    OFFSET_MIN,
    PLACEMENT_KEYS,
    SCALE_MAX,
    SCALE_MIN,
    TEXT_EXTENT_MAX,
    canonical_fullscreen_overlays,
    normalize_fullscreen_overlays,
)
from rendering.custom_layout_contract import (
    SnapGuide,
    SnapResolution,
    resolve_resize_edge_snap,
    resolve_snap_local_rect_for_edit,
)
from rendering.custom_layout_session import CustomLayoutKey, CustomLayoutSession, CustomLayoutSessionItem
from rendering.quick.custom_layout_size import edge_resize_rect, uniform_wheel_scale

#: The Edit items' widget ids share this prefix (the Edit QML hides the close control for them).
EDIT_ID_PREFIX = "fullscreen_overlay."
#: Edit part -> (the overlay whose value holds it, the members it writes).
PARTS: dict[str, tuple[str, tuple[str, ...]]] = {
    "preset": ("preset", ("offset_x", "offset_y", "scale", "text_width", "text_height")),
    "now_playing": ("now_playing", ("offset_x", "offset_y", "scale", "text_width", "text_height")),
    "artwork": ("now_playing", ("artwork_scale", "artwork_width", "artwork_height")),
}
#: The size factor each part's corner handles and wheel change.
SCALE_KEY = {"preset": "scale", "now_playing": "scale", "artwork": "artwork_scale"}
#: The (horizontal, vertical) extents each part's side handles change (ordinary Edit's content axes).
EXTENT_KEYS = {"preset": ("text_width", "text_height"), "now_playing": ("text_width", "text_height"),
               "artwork": ("artwork_width", "artwork_height")}
#: Every part declares both content axes: the Edit layer draws its side strips and two-axis diagonal corners.
CONTENT_AXES = frozenset({"horizontal", "vertical"})
#: The part whose payload holds the overlay's position (the artwork moves Now Playing as one).
POSITION_PART = {"preset": "preset", "now_playing": "now_playing", "artwork": "now_playing"}
#: Guide kinds a move publishes (the safe area's edges and centre, the other overlay's edges and centre).
GUIDE_KINDS = frozenset({"edge", "display_center", "peer", "peer_center"})
_CORNER_HANDLES = frozenset({"top_left", "top_right", "bottom_left", "bottom_right"})
_SIDE_HANDLES = frozenset({"left", "right", "top", "bottom"})
_CONTENT_CORNER_HANDLES = frozenset(f"content_{corner}" for corner in _CORNER_HANDLES)

assert {key for _overlay, keys in PARTS.values() for key in keys} == {
    key for keys in PLACEMENT_KEYS.values() for key in keys}, "the Edit parts write exactly the placement members"


def edit_widget_id(part: str) -> str:
    return f"{EDIT_ID_PREFIX}{part}"


def edit_part(item: CustomLayoutSessionItem) -> str | None:
    """The overlay part an Edit item stands for (None: an ordinary item)."""

    identity = str(item.model_identity)
    if not identity.startswith(EDIT_ID_PREFIX):
        return None
    part = identity[len(EDIT_ID_PREFIX):]
    return part if part in PARTS else None


def is_fullscreen_overlay_item(item: CustomLayoutSessionItem) -> bool:
    return edit_part(item) is not None


def draft_value(committed: Mapping[str, Any], items: tuple[CustomLayoutSessionItem, ...]) -> dict[str, Any]:
    """The overlays' value with every Edit item's placement applied (normalised by the one owner)."""

    value = deepcopy(dict(committed))
    for item in items:
        part = edit_part(item)
        if part is None:
            continue
        overlay, keys = PARTS[part]
        target = value.setdefault(overlay, {})
        for key in keys:
            if key in item.current_size_payload:
                target[key] = item.current_size_payload[key]
    return normalize_fullscreen_overlays(value)


def offsets_for_position(position: tuple[float, float], anchored: tuple[float, float],
                         safe_size: tuple[float, float]) -> tuple[float, float]:
    """The offset that places an overlay at ``position`` (stage coordinates) from its corner anchor."""

    width, height = max(1.0, float(safe_size[0])), max(1.0, float(safe_size[1]))

    def clamp(value: float) -> float:
        return round(max(OFFSET_MIN, min(OFFSET_MAX, value)), 6)

    return (clamp((float(position[0]) - float(anchored[0])) / width),
            clamp((float(position[1]) - float(anchored[1])) / height))


def corner_drag_scale(origin: QRect, origin_scale: float, handle: str, dx: float, dy: float) -> float:
    """The absolute scale a corner drag asks for: the dragged corner's distance from the opposite (fixed) corner."""

    horizontal = -1.0 if str(handle).endswith("left") else 1.0
    vertical = -1.0 if str(handle).startswith("top_") else 1.0
    width, height = max(1.0, float(origin.width())), max(1.0, float(origin.height()))
    base = math.hypot(width, height)
    target = math.hypot(max(1.0, width + float(dx) * horizontal), max(1.0, height + float(dy) * vertical))
    return float(origin_scale) * target / base


def resize_edges(handle: str) -> tuple[str | None, str | None]:
    """The (horizontal, vertical) edges a side or two-axis diagonal handle moves (ordinary Edit's semantic ids)."""

    handle = str(handle)
    if handle in ("left", "right"):
        return handle, None
    if handle in ("top", "bottom"):
        return None, handle
    corner = handle.removeprefix("content_")
    return ("left" if corner.endswith("left") else "right"), ("top" if corner.startswith("top_") else "bottom")


def extent_value(part: str, size: float, *, font_size: float, padding: float = 0.0,
                 origin_size: float = 1.0, origin_factor: float = 1.0) -> float:
    """The stored extent that draws ``size`` px on one axis of ``part``'s frame.

    The text parts store their box in ems of the overlay's font (the preset toast's frame includes its card padding);
    the artwork stores a factor of its square size, measured against the gesture's origin frame and factor.
    """

    if part == "artwork":
        factor = float(origin_factor) * float(size) / max(1.0, float(origin_size))
        return _clamp_scale(factor)
    box = max(1.0, float(size) - 2.0 * float(padding))
    return round(max(0.01, min(TEXT_EXTENT_MAX, box / max(1.0, float(font_size)))), 4)


def _clamp_scale(value: float) -> float:
    return round(max(SCALE_MIN, min(SCALE_MAX, float(value))), 4)


def _qrect(values: tuple[float, float, float, float], origin: QPoint = QPoint()) -> QRect:
    x, y, width, height = (float(v) for v in values)
    return QRect(int(round(x)) + origin.x(), int(round(y)) + origin.y(),
                 max(1, int(round(width))), max(1, int(round(height))))


@dataclass(frozen=True, slots=True)
class _ResizeOrigin:
    rect: QRect
    cursor: QPoint
    scale: float
    handle: str
    #: The part's (horizontal, vertical) extents at the gesture's start.
    extents: tuple[float, float] = (0.0, 0.0)


class FullscreenOverlayEdit:
    """The overlays' part of one Fullscreen Edit session (owned by the ``QuickCustomLayoutOwner`` for its duration).

    ``geometry`` reads the live overlays (the scene controller's ``expanded_overlay_edit_geometry``); ``project``
    publishes a value's QML projection onto them; ``guides`` publishes (vertical, horizontal) guide lists on the
    expanded display's Edit layer.
    """

    def __init__(
        self,
        *,
        display_identity: str,
        display_origin: QPoint,
        monitor_route: str,
        committed: Mapping[str, Any],
        geometry: Callable[[], Mapping[str, Any] | None],
        project: Callable[[Mapping[str, Any]], None],
        guides: Callable[[tuple[tuple[int, str], ...], tuple[tuple[int, str], ...]], None],
    ) -> None:
        self._identity = str(display_identity)
        self._origin = QPoint(display_origin)
        self._monitor_route = str(monitor_route or "ALL")
        self._committed = normalize_fullscreen_overlays(committed)
        self._geometry = geometry
        self._project_value = project
        self._publish_guides = guides
        self._session: CustomLayoutSession | None = None
        self._resize_origins: dict[CustomLayoutKey, _ResizeOrigin] = {}
        # Re-entrancy: a projection syncs every frame itself; QML geometry reports during it are its own echo.
        self._projecting = False

    # ------------------------------------------------------------------------------------------- admission

    @property
    def committed(self) -> dict[str, Any]:
        return deepcopy(self._committed)

    def admit(self, session: CustomLayoutSession) -> bool:
        """Add the three parts to ``session`` from the committed value and the drawn overlays (False: not drawn)."""

        snapshot = self._geometry()
        if snapshot is None:
            return False
        for part, (overlay, keys) in PARTS.items():
            payload = {key: self._committed[overlay][key] for key in keys}
            rect = _qrect(snapshot["parts"][part], self._origin)
            session.add_item(CustomLayoutSessionItem(
                source_key=CustomLayoutKey(edit_widget_id(part), self._identity),
                model_identity=edit_widget_id(part),
                baseline_global_rect=rect,
                current_global_rect=rect,
                baseline_size_payload=payload,
                current_size_payload=dict(payload),
                baseline_enabled=True,
                current_enabled=True,
                resize_capable=True,
                size_reset_capable=True,
                content_extent_axes=CONTENT_AXES,
                current_display_identity=self._identity,
                source_monitor_route=self._monitor_route,
            ))
        self._session = session
        return True

    def retire(self) -> None:
        self._session = None
        self._resize_origins.clear()

    # ----------------------------------------------------------------------------------------- the draft

    def items(self) -> tuple[CustomLayoutSessionItem, ...]:
        session = self._session
        return tuple(item for item in session.items() if edit_part(item) is not None) if session else ()

    def item_for(self, part: str) -> CustomLayoutSessionItem | None:
        return next((item for item in self.items() if edit_part(item) == part), None)

    def draft_value(self) -> dict[str, Any]:
        return draft_value(self._committed, self.items())

    def pending(self) -> bool:
        """An unsaved draft: any part's placement differs from what Edit started from."""

        return any(item.current_size_payload != item.baseline_size_payload for item in self.items())

    def position_item(self, item: CustomLayoutSessionItem) -> CustomLayoutSessionItem:
        """The item whose payload holds ``item``'s position (the artwork moves Now Playing)."""

        part = edit_part(item)
        owner = self.item_for(POSITION_PART[part]) if part is not None else None
        return owner if owner is not None else item

    # ------------------------------------------------------------------------------------------ projection

    def project(self, _item: CustomLayoutSessionItem | None = None) -> None:
        """Publish the draft onto the overlays and read every frame back (the session's change publisher)."""

        if self._projecting:
            return
        self._projecting = True
        try:
            self._project_value(self.draft_value())
            changed = self._sync_rects()
        finally:
            self._projecting = False
        self._notify(changed, skip=_item)

    def geometry_changed(self) -> None:
        """The overlays' geometry changed by itself (a track, the font, a stacking glide): follow it."""

        if self._projecting or self._session is None:
            return
        self._projecting = True
        try:
            changed = self._sync_rects()
        finally:
            self._projecting = False
        self._notify(changed)

    def _notify(self, items: list[CustomLayoutSessionItem], *, skip: CustomLayoutSessionItem | None = None) -> None:
        session = self._session
        if session is None:
            return
        self._projecting = True       # the frames' own publication would only echo this projection
        try:
            for item in items:
                if item is not skip:
                    session.notify_item_changed(item)
        finally:
            self._projecting = False

    def _sync_rects(self) -> list[CustomLayoutSessionItem]:
        snapshot = self._geometry()
        if snapshot is None:
            return []
        changed: list[CustomLayoutSessionItem] = []
        for item in self.items():
            rect = _qrect(snapshot["parts"][edit_part(item)], self._origin)
            if rect != item.current_global_rect:
                item.current_global_rect = QRect(rect)
                changed.append(item)
        return changed

    # ------------------------------------------------------------------------------------------- gestures

    def _move_overlay(self, position_item: CustomLayoutSessionItem, overlay: str,
                      stage_position: tuple[float, float], snapshot: Mapping[str, Any]) -> None:
        slot = snapshot["slots"][overlay]
        offset_x, offset_y = offsets_for_position(stage_position, slot["anchored"],
                                                  (snapshot["safe_width"], snapshot["safe_height"]))
        position_item.current_size_payload = {**position_item.current_size_payload,
                                               "offset_x": offset_x, "offset_y": offset_y}

    def _place(self, item: CustomLayoutSessionItem, overlay: str, stage_position: tuple[float, float],
               snapshot: Mapping[str, Any]) -> None:
        """Move ``overlay`` to ``stage_position`` and keep the offset it really took (WYSIWYG).

        The overlays clamp themselves to the safe area and clear of the card's controls; the stored offset is the one
        that reproduces the drawn place exactly, never an intent beyond a clamp that would surface on another display.
        """

        position_item = self.position_item(item)
        self._move_overlay(position_item, overlay, stage_position, snapshot)
        self.project(item)
        drawn = self._geometry()
        if drawn is None:
            return
        slot = drawn["slots"][overlay]
        effective = offsets_for_position(slot["pos"], slot["anchored"], (drawn["safe_width"], drawn["safe_height"]))
        payload = position_item.current_size_payload
        if (payload.get("offset_x"), payload.get("offset_y")) != effective:
            position_item.current_size_payload = {**payload, "offset_x": effective[0], "offset_y": effective[1]}
            self.project(item)

    def resolve_move(self, item: CustomLayoutSessionItem, proposed: QRect) -> QRect:
        """One drag sample: the overlay follows the part's proposed rectangle, snapped; returns the part's frame."""

        part = edit_part(item)
        snapshot = self._geometry()
        if part is None or snapshot is None:
            return QRect(item.current_global_rect)
        overlay = PARTS[POSITION_PART[part]][0]
        current = item.current_global_rect
        dx, dy = proposed.x() - current.x(), proposed.y() - current.y()
        slot_rect = _qrect(snapshot["slots"][overlay]["rect"])
        proposed_slot = slot_rect.translated(dx, dy)
        stage_x, stage_y = snapshot["stage"][0], snapshot["stage"][1]
        inset = snapshot["safe_inset"]
        safe = QRect(int(round(stage_x + inset)), int(round(stage_y + inset)),
                     max(1, int(round(snapshot["safe_width"]))), max(1, int(round(snapshot["safe_height"]))))
        peer = "now_playing" if overlay == "preset" else "preset"
        peers = [_qrect(snapshot["slots"][peer]["rect"]).translated(-safe.x(), -safe.y())]
        resolution = resolve_snap_local_rect_for_edit(
            proposed_slot.translated(-safe.x(), -safe.y()), safe.size(), peer_rects=peers, min_size=QSize(1, 1))
        snapped = resolution.rect.translated(safe.topLeft())
        slot = snapshot["slots"][overlay]
        position = (slot["pos"][0] + (snapped.x() - slot_rect.x()), slot["pos"][1] + (snapped.y() - slot_rect.y()))
        self._place(item, overlay, position, snapshot)
        self._publish_move_guides(resolution, safe.topLeft())
        return QRect(item.current_global_rect)

    def _publish_move_guides(self, resolution: SnapResolution, offset: QPoint) -> None:
        def collect(guides: tuple[SnapGuide, ...], shift: int) -> tuple[tuple[int, str], ...]:
            seen: list[tuple[int, str]] = []
            for guide in guides:
                entry = (int(guide.position) + shift, str(guide.kind))
                if guide.kind in GUIDE_KINDS and entry not in seen:
                    seen.append(entry)
            return tuple(seen)

        self._publish_guides(
            collect(tuple(resolution.vertical_guides) + tuple(resolution.vertical_assists), offset.x()),
            collect(tuple(resolution.horizontal_guides) + tuple(resolution.horizontal_assists), offset.y()))

    def clear_guides(self) -> None:
        self._publish_guides((), ())

    def _keep(self, item: CustomLayoutSessionItem, anchor: QRect, keep: str) -> None:
        """After a size change, move the overlay so ``item``'s frame keeps ``anchor``'s top centre or a corner."""

        part = edit_part(item)
        if part is None or part == "artwork":
            return      # the artwork grows from its place beside the text
        snapshot = self._geometry()
        if snapshot is None:
            return
        frame = item.current_global_rect
        if keep == "top_centre":
            target_x = anchor.x() + (anchor.width() - frame.width()) / 2.0
            target_y = float(anchor.y())
        else:
            # ``keep`` is the fixed corner (opposite the dragged handle).
            target_x = float(anchor.x() + anchor.width() - frame.width()) if keep.endswith("right") else float(
                anchor.x())
            target_y = float(anchor.y() + anchor.height() - frame.height()) if keep.startswith("bottom") else float(
                anchor.y())
        overlay = PARTS[part][0]
        slot = snapshot["slots"][overlay]
        position = (slot["pos"][0] + target_x - frame.x(), slot["pos"][1] + target_y - frame.y())
        self._place(item, overlay, position, snapshot)

    def _set_members(self, item: CustomLayoutSessionItem, members: Mapping[str, float]) -> bool:
        payload = item.current_size_payload
        if all(payload.get(key) == value for key, value in members.items()):
            return False
        item.current_size_payload = {**payload, **members}
        self.project(item)
        return True

    def _set_scale(self, item: CustomLayoutSessionItem, scale: float) -> bool:
        return self._set_members(item, {SCALE_KEY[edit_part(item)]: _clamp_scale(scale)})

    def begin_resize(self, item: CustomLayoutSessionItem, handle: str, cursor: QPoint) -> bool:
        """A corner (uniform scale), a side (one axis) or a two-axis diagonal (both extents) handle's press."""

        part = edit_part(item)
        handle = str(handle)
        if part is None or handle not in _CORNER_HANDLES | _SIDE_HANDLES | _CONTENT_CORNER_HANDLES:
            return False
        payload = item.current_size_payload
        horizontal, vertical = EXTENT_KEYS[part]
        self._resize_origins[item.source_key] = _ResizeOrigin(
            QRect(item.current_global_rect), QPoint(cursor), float(payload.get(SCALE_KEY[part], 1.0)), handle,
            (float(payload.get(horizontal, 0.0)), float(payload.get(vertical, 0.0))))
        return True

    def update_resize(self, item: CustomLayoutSessionItem, handle: str, cursor: QPoint, finalize: bool) -> bool:
        origin = self._resize_origins.get(item.source_key)
        if origin is None:
            return False
        if finalize:
            self._resize_origins.pop(item.source_key, None)
        if origin.handle not in _CORNER_HANDLES:
            changed = self._resize_extent(item, origin, cursor)
            if finalize:
                self.clear_guides()     # release ends the gesture's guides (ordinary Edit's resize release)
            return changed or finalize
        scale = corner_drag_scale(origin.rect, origin.scale, origin.handle,
                                  cursor.x() - origin.cursor.x(), cursor.y() - origin.cursor.y())
        changed = self._set_scale(item, scale)
        opposite = ("bottom" if origin.handle.startswith("top") else "top") + (
            "_right" if origin.handle.endswith("left") else "_left")
        self._keep(item, origin.rect, opposite)
        return changed or finalize

    def _safe_rect(self, snapshot: Mapping[str, Any]) -> QRect:
        """The safe area in the Edit layer's local coordinates."""

        inset = snapshot["safe_inset"]
        return QRect(int(round(snapshot["stage"][0] + inset)), int(round(snapshot["stage"][1] + inset)),
                     max(1, int(round(snapshot["safe_width"]))), max(1, int(round(snapshot["safe_height"]))))

    def _extents_for(self, part: str, origin: _ResizeOrigin, width: float | None, height: float | None,
                     snapshot: Mapping[str, Any]) -> dict[str, float]:
        """The extent members that draw a frame of ``width`` / ``height`` px (None: that axis is untouched)."""

        slot = snapshot["slots"][PARTS[part][0]]
        font_size = float(slot["font_size"])
        padding = float(slot["padding"]) if part == "preset" else 0.0
        horizontal, vertical = EXTENT_KEYS[part]
        members: dict[str, float] = {}
        for key, size, origin_size, origin_factor in (
                (horizontal, width, origin.rect.width(), origin.extents[0]),
                (vertical, height, origin.rect.height(), origin.extents[1])):
            if size is not None:
                members[key] = extent_value(part, size, font_size=font_size, padding=padding,
                                            origin_size=origin_size, origin_factor=origin_factor)
        return members

    def _resize_extent(self, item: CustomLayoutSessionItem, origin: _ResizeOrigin, cursor: QPoint) -> bool:
        """One side or diagonal sample: the dragged edge(s) follow the cursor, snapped; the untouched axis stays."""

        part = edit_part(item)
        snapshot = self._geometry()
        if part is None or snapshot is None:
            return False
        horizontal_edge, vertical_edge = resize_edges(origin.handle)
        safe = self._safe_rect(snapshot)
        start = origin.rect.translated(-self._origin)
        # Ordinary Edit's one edge rule: the delta from the press, bounded by the safe area on the moving edge.
        rect = edge_resize_rect(start, safe, QSize(1, 1), cursor.x() - origin.cursor.x(), cursor.y() - origin.cursor.y(),
                                horizontal_edge=horizontal_edge, vertical_edge=vertical_edge)
        overlay = PARTS[POSITION_PART[part]][0]
        peer = "now_playing" if overlay == "preset" else "preset"
        resolution = resolve_resize_edge_snap(
            rect.translated(-safe.x(), -safe.y()), safe.size(), horizontal_edge=horizontal_edge,
            vertical_edge=vertical_edge, peer_rects=[_qrect(snapshot["slots"][peer]["rect"]).translated(
                -safe.x(), -safe.y())], min_size=QSize(1, 1))
        target = resolution.rect
        changed = self._set_members(item, self._extents_for(
            part, origin, target.width() if horizontal_edge else None, target.height() if vertical_edge else None,
            snapshot))
        # WYSIWYG: keep the extent the part really drew (its floors and the safe area applied), as offsets do.
        drawn = self._geometry()
        if drawn is not None:
            frame = drawn["parts"][part]
            settled = self._extents_for(part, origin, frame[2] if horizontal_edge else None,
                                        frame[3] if vertical_edge else None, drawn)
            if part != "artwork" and settled != {k: item.current_size_payload.get(k) for k in settled}:
                changed = self._set_members(item, settled) or changed
        # The opposite edge stays where it was (the artwork grows from its place beside the text).
        fixed = ("bottom" if vertical_edge == "top" else "top") + ("_right" if horizontal_edge == "left" else "_left")
        self._keep(item, origin.rect, fixed)
        self._publish_move_guides(resolution, safe.topLeft())
        return changed

    def resize_wheel(self, item: CustomLayoutSessionItem, angle_delta_y: int) -> bool:
        part = edit_part(item)
        if part is None:
            return False
        before = QRect(item.current_global_rect)
        current = float(item.current_size_payload.get(SCALE_KEY[part], 1.0))
        if not self._set_scale(item, uniform_wheel_scale(current, int(angle_delta_y))):
            return False
        self._keep(item, before, "top_centre")
        return True

    def restore_size(self, item: CustomLayoutSessionItem) -> bool:
        """Restore Size: the part's size factor and extents back to their canonical defaults, keeping its top centre.

        Ordinary Edit's Restore Size likewise returns the uniform scale and drops ``content_extent``.
        """

        part = edit_part(item)
        if part is None:
            return False
        self._resize_origins.pop(item.source_key, None)
        canonical = canonical_fullscreen_overlays()[PARTS[part][0]]
        before = QRect(item.current_global_rect)
        if not self._set_members(item, {key: float(canonical[key]) for key in (SCALE_KEY[part], *EXTENT_KEYS[part])}):
            return False
        self._keep(item, before, "top_centre")
        return True

__all__ = [
    "CONTENT_AXES",
    "EDIT_ID_PREFIX",
    "EXTENT_KEYS",
    "FullscreenOverlayEdit",
    "PARTS",
    "corner_drag_scale",
    "draft_value",
    "edit_part",
    "edit_widget_id",
    "extent_value",
    "is_fullscreen_overlay_item",
    "offsets_for_position",
    "resize_edges",
]
