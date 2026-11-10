"""Fullscreen Edit (Expanded Visualizer M3c): the full-display overlays' geometry inside the one Edit session.

Operator, 8 Nov: "when we choose edit mode during a fullscreen visualizer we should be able to adjust the
size/position/placement of the toast and preset text elements and artwork instead of it going back to the full quick
scene. Like we can most geometry normally."

There is no second editor. Edit entered while the Visualizer is expanded opens the ``QuickCustomLayoutOwner``'s one
``CustomLayoutSession`` on the expanded display with the overlays' parts as its items, drawn and handled by the same
retained Edit layer (frames, corner handles, the wheel, Restore Size, snapping guides, undo, Save/Cancel, Enter/Esc).
This module is what differs about those items:

* **Items.** The preset toast and Now Playing's block (its whole overlay: artwork, text and Media Controls when shown).
  On a display with a Volume OSD, the OSD too (operator, 8 Nov: it shows during Fullscreen Edit, so it must be
  editable there): its placement over the expanded card, ``volume_osd`` (offset and scale from where its ordinary
  layout puts it), moved and scaled like the toast; it has no single-axis extents (no side strips). Its ordinary
  placement (ordinary Edit, CUSTOM) is never changed by it.
* **Now Playing's parts are its block's children** (operator, 8 Nov: "allow movement within the block that is not
  drawn like we already do for child elements in normal geometry. I should be able to move every element around in
  that block and change it"). The block's item declares ordinary Edit's child roles
  (``core.settings.fullscreen_overlays.NOW_PLAYING_CHILD_ROLES``: artwork, title, artist, controls), its payload
  carries ordinary Edit's ``child_geometry`` record map and the Now Playing slot (QML) is its presentation, exposing
  ``customEditableChildRoles`` as every child-capable widget does. So the one child editor (``CustomLayoutOverlay.qml``'s
  child layer; the owner's ``begin_child_move``/``update_child_move``/``begin_child_resize``/``update_child_resize``
  and ``resolve_child_*_geometry``) moves and sizes each part inside the block, with its lock, guides, containment,
  collision preference and undo; this module only carries the records into the overlays' value. Decided (mirroring
  ordinary Edit, where a widget with a visible card keeps its children editable inside the card): the parts are
  editable whether or not the block draws a surface (Card); the card is then the block's visible extent.
* **Geometry is the overlays' own canonical value**, never a rectangle the session owns: each item's
  ``current_size_payload`` is its draft placement (``core.settings.fullscreen_overlays.PLACEMENT_KEYS``: the offset
  from the anchor corner in fractions of the expanded card's safe area, ``scale``, the extents, the children) and its
  rectangle is read back from the live QML after every projection, so a frame is always what is drawn (content
  size, stacking and the card's control reserves included). Positions stay relative to the safe area, so they reflow
  on displays of other sizes and DPRs.
* **Moves** snap with the ordinary Edit rule (``resolve_snap_local_rect_for_edit``) inside the safe area: its edges
  (and so its corners), its centre, and the other overlay's edges, centre and the 30 px gutter.
* **Scaling.** Corner handles and the wheel scale the preset toast and Now Playing's block by ``scale`` (their font;
  every part follows). A corner drag uses the drag-to-scale gesture of ordinary Edit and keeps the frame's opposite
  corner where it was; the wheel and Restore Size keep its top centre (as ordinary Edit does).
* **Single-axis sizing** uses the existing ordinary Edit side strips and two-axis diagonal handles. Preset-toast
  handles still resize its authored text extents. **Now Playing's parent** X/Y handles instead resize the actual
  artwork border through the existing ``artwork_width`` / ``artwork_height`` factors. Text remains a compact
  vertically centred group beside it; wrapping only responds to genuine changes in available text width. Per-child
  editing still independently sizes/moves artwork, title, artist, album and transport without altering the parent. The dragged edge follows the cursor under the ordinary resize rule
  (``edge_resize_rect``, bounded by the safe area) and snaps with ``resolve_resize_edge_snap`` (the safe area's
  centre, the other overlay's edges), the opposite edge staying put. The untouched axis keeps its member exactly
  (natural stays natural); the stored extent is the one the overlay really drew (its floors and the safe area
  included). A uniform scale keeps the authored text extents and artwork factors unchanged; Restore Size returns
  scale, text extents and artwork factors to their canonical values and clears child geometry records. Nothing
  implicitly changes a user's individual child placement or position.
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
    CHILD_GEOMETRY_KEY,
    NOW_PLAYING_CHILD_ROLES,
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
from rendering.custom_child_geometry import normalize_child_geometry
from rendering.custom_layout_session import CustomLayoutKey, CustomLayoutSession, CustomLayoutSessionItem
from rendering.quick.custom_layout_size import edge_resize_rect, uniform_wheel_scale
from widgets.spotify_visualizer.presentation_orientation import (
    CONTENT_ROTATION_BY_MODE_PAYLOAD_KEY,
    normalize_content_rotation_by_mode,
)

#: The Edit items' widget ids share this prefix (the Edit QML hides the close control for them).
EDIT_ID_PREFIX = "fullscreen_overlay."
#: The expanded Visualizer card's Edit item: it carries only Rotate Widget Content (never moved or sized; see
#: ``FullscreenOverlayEdit.admit``). Its payload is the Visualizer's per-mode orientation map, as on the ordinary
#: Visualizer item.
CARD_EDIT_ID = f"{EDIT_ID_PREFIX}visualizer"
#: Edit part -> (the overlay whose value holds it, the members it writes).
#: Now Playing's block also carries M3c's artwork sizing (drawn as stored; Restore Size resets it) and its children's
#: records (ordinary Edit's ``child_geometry``).
PARTS: dict[str, tuple[str, tuple[str, ...]]] = {
    "preset": ("preset", ("offset_x", "offset_y", "scale", "text_width", "text_height")),
    "now_playing": ("now_playing", ("offset_x", "offset_y", "scale", "text_width", "text_height",
                                    "artwork_scale", "artwork_width", "artwork_height", CHILD_GEOMETRY_KEY)),
    "volume_osd": ("volume_osd", ("offset_x", "offset_y", "scale")),
}
#: The size factor each part's corner handles and wheel change.
SCALE_KEY = {"preset": "scale", "now_playing": "scale", "volume_osd": "scale"}
#: The (horizontal, vertical) extents each part's side handles change (ordinary Edit's content axes).
EXTENT_KEYS = {"preset": ("text_width", "text_height"), "now_playing": ("artwork_width", "artwork_height"),
               "volume_osd": ()}
#: Every part declares both content axes: the Edit layer draws its side strips and two-axis diagonal corners.
CONTENT_AXES = frozenset({"horizontal", "vertical"})
#: The parts whose children ordinary Edit's child editor edits (role descriptors, from the one settings owner).
CHILD_ROLES = {"now_playing": NOW_PLAYING_CHILD_ROLES}
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


def is_card_item(item: CustomLayoutSessionItem) -> bool:
    """The expanded Visualizer card's item (Rotate Widget Content only)."""

    return str(item.model_identity) == CARD_EDIT_ID


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
            if key == CHILD_GEOMETRY_KEY:
                # Ordinary Edit's carrier drops the key when every child is back at its authored place.
                target[key] = deepcopy(dict(item.current_size_payload.get(key) or {}))
            elif key in item.current_size_payload:
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


def extent_value(size: float, *, font_size: float, inset: float = 0.0) -> float:
    """The stored text-box extent (ems of the overlay's font) that draws a frame of ``size`` px on one axis.

    ``inset`` is what the frame holds besides the text box on that axis: the card padding on both sides, and on Now
    Playing's horizontal axis its artwork and the gap beside it.
    """

    box = max(1.0, float(size) - float(inset))
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
    # Frozen artwork axes at pointer-down: resize is absolute from the gesture origin, not the
    # mutable current text width (which can reflow while the user drags a handle).
    artwork_size: tuple[float, float] = (0.0, 0.0)
    artwork_factors: tuple[float, float] = (1.0, 1.0)


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
        orientation: Callable[[], None] | None = None,
    ) -> None:
        self._identity = str(display_identity)
        self._origin = QPoint(display_origin)
        self._monitor_route = str(monitor_route or "ALL")
        self._committed = normalize_fullscreen_overlays(committed)
        self._geometry = geometry
        self._project_value = project
        self._publish_guides = guides
        # Publishes the card part's draft orientation to the Visualizer (the scene's viewport/orientation seam).
        self._publish_orientation = orientation
        self._session: CustomLayoutSession | None = None
        self._resize_origins: dict[CustomLayoutKey, _ResizeOrigin] = {}
        # Re-entrancy: a projection syncs every frame itself; QML geometry reports during it are its own echo.
        self._projecting = False

    # ------------------------------------------------------------------------------------------- admission

    @property
    def committed(self) -> dict[str, Any]:
        return deepcopy(self._committed)

    def admit(self, session: CustomLayoutSession, *,
              card: tuple[tuple[float, float], Mapping[str, int]] | None = None,
              child_collision: bool = True) -> bool:
        """Add the parts to ``session`` from the committed value and the drawn overlays (False: not drawn).

        ``child_collision`` is ordinary Edit's global child/child collision preference
        (``widgets.global.child_collision_enabled``), applied to Now Playing's parts as to every multi-child widget.

        ``card`` (the Visualizer's committed physical extent and per-mode orientation map), given when the live mode
        can turn its content, adds the expanded card's item first, below the overlays' frames: ordinary Edit's
        Visualizer frame offers Rotate Widget Content, and so does the expanded card. It is never moved or sized
        (the expanded card is a viewport, not a layout): it is not resizable, has no Restore Size, no content axes,
        and its QML frame takes no press, so the background stays Edit's (its double-click Saves). Its frame is the
        whole card, so the glyph continues the card's own bottom-right glyph row (one line with Reset Camera).
        """

        snapshot = self._geometry()
        if snapshot is None:
            return False
        if card is not None:
            self._admit_card(session, snapshot, card)
        for part, (overlay, keys) in PARTS.items():
            if part not in snapshot["parts"]:
                continue        # the Volume OSD on a display without one
            payload = {key: deepcopy(self._committed[overlay][key]) for key in keys}
            roles = CHILD_ROLES.get(part, ())
            children = normalize_child_geometry(payload.get(CHILD_GEOMETRY_KEY), roles) if roles else {}
            if roles and not payload.get(CHILD_GEOMETRY_KEY):
                # Ordinary Edit's carrier holds no key while every child is authored: Cancel/undo compare alike.
                payload.pop(CHILD_GEOMETRY_KEY, None)
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
                content_extent_axes=CONTENT_AXES if EXTENT_KEYS[part] else frozenset(),
                # Ordinary Edit's editable children (Now Playing's parts): the one child editor's roles and records.
                custom_child_roles=roles,
                child_collision_enabled=bool(child_collision),
                baseline_child_sizes=dict(children),
                current_child_sizes=dict(children),
                current_display_identity=self._identity,
                source_monitor_route=self._monitor_route,
            ))
        self._session = session
        return True

    def _admit_card(self, session: CustomLayoutSession, snapshot: Mapping[str, Any],
                    card: tuple[tuple[float, float], Mapping[str, int]]) -> None:
        extent, rotations = card
        # The whole card: its Rotate Widget Content continues the card's own bottom-right glyph row (the frame's
        # Edit row reads the card's row geometry, so the frame must be the card).
        rect = _qrect(tuple(snapshot["stage"]), self._origin)
        payload: dict[str, Any] = {}
        normalized = normalize_content_rotation_by_mode(rotations)
        if normalized:
            payload[CONTENT_ROTATION_BY_MODE_PAYLOAD_KEY] = normalized
        session.add_item(CustomLayoutSessionItem(
            source_key=CustomLayoutKey(CARD_EDIT_ID, self._identity),
            model_identity=CARD_EDIT_ID,
            baseline_global_rect=rect,
            current_global_rect=rect,
            baseline_size_payload=payload,
            current_size_payload=dict(payload),
            baseline_enabled=True,
            current_enabled=True,
            resize_capable=False,
            size_reset_capable=False,
            content_rotation_capable=True,
            # The committed physical world the orientation turns (published with it; never edited here).
            baseline_viewport_extent=(float(extent[0]), float(extent[1])),
            current_display_identity=self._identity,
            source_monitor_route=self._monitor_route,
        ))

    def retire(self) -> None:
        self._session = None
        self._resize_origins.clear()

    # ------------------------------------------------------------------------------ the card's orientation

    def card_item(self) -> CustomLayoutSessionItem | None:
        session = self._session
        return next((item for item in session.items() if is_card_item(item)), None) if session else None

    def orientation_draft(self) -> dict[str, int] | None:
        """The card's draft per-mode orientation map (None: no card part, so nothing to turn)."""

        card = self.card_item()
        if card is None:
            return None
        return normalize_content_rotation_by_mode(card.current_size_payload.get(CONTENT_ROTATION_BY_MODE_PAYLOAD_KEY, {}))

    def orientation_pending(self) -> bool:
        card = self.card_item()
        return card is not None and card.current_size_payload != card.baseline_size_payload

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

        return self.orientation_pending() or any(
            item.current_size_payload != item.baseline_size_payload for item in self.items())

    def position_item(self, item: CustomLayoutSessionItem) -> CustomLayoutSessionItem:
        """The item whose payload holds ``item``'s position (every part holds its own)."""

        return item

    # ------------------------------------------------------------------------------------------ projection

    def project(self, _item: CustomLayoutSessionItem | None = None) -> None:
        """Publish the draft onto the overlays and read every frame back (the session's change publisher)."""

        if _item is not None and is_card_item(_item):
            # A turn (or its undo): the expanded card shows the draft orientation; the overlays are unchanged.
            if self._publish_orientation is not None:
                self._publish_orientation()
            return
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
            values = snapshot["parts"].get(edit_part(item))
            if values is None:
                continue        # the Volume OSD left this display mid-session: its frame stays where it was
            rect = _qrect(values, self._origin)
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
        overlay = PARTS[part][0]
        current = item.current_global_rect
        dx, dy = proposed.x() - current.x(), proposed.y() - current.y()
        slot_rect = _qrect(snapshot["slots"][overlay]["rect"])
        proposed_slot = slot_rect.translated(dx, dy)
        stage_x, stage_y = snapshot["stage"][0], snapshot["stage"][1]
        inset = snapshot["safe_inset"]
        safe = QRect(int(round(stage_x + inset)), int(round(stage_y + inset)),
                     max(1, int(round(snapshot["safe_width"]))), max(1, int(round(snapshot["safe_height"]))))
        peers = [_qrect(slot["rect"]).translated(-safe.x(), -safe.y())
                 for name, slot in snapshot["slots"].items() if name != overlay]
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
        if part is None:
            return
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
        if handle not in _CORNER_HANDLES and not EXTENT_KEYS[part]:
            return False        # no single-axis extents (the Volume OSD): corners and the wheel only
        payload = item.current_size_payload
        art = (0.0, 0.0)
        factors = (1.0, 1.0)
        if part == "now_playing":
            snapshot = self._geometry()
            if snapshot is None:
                return False
            art = tuple(snapshot["slots"]["now_playing"]["artwork_size"])
            factors = (float(payload["artwork_width"]), float(payload["artwork_height"]))
        self._resize_origins[item.source_key] = _ResizeOrigin(
            QRect(item.current_global_rect), QPoint(cursor), float(payload.get(SCALE_KEY[part], 1.0)), handle,
            art, factors)
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

    def _extents_for(self, part: str, width: float | None, height: float | None,
                     snapshot: Mapping[str, Any]) -> dict[str, float]:
        """The extent members that draw a frame of ``width`` / ``height`` px (None: that axis is untouched)."""

        slot = snapshot["slots"][PARTS[part][0]]
        font_size = float(slot["font_size"])
        padding = 2.0 * float(slot["padding"])
        horizontal, vertical = EXTENT_KEYS[part]
        members: dict[str, float] = {}
        for key, size, inset in ((horizontal, width, padding + float(slot.get("beside", 0.0))),
                                 (vertical, height, padding)):
            if size is not None:
                members[key] = extent_value(size, font_size=font_size, inset=inset)
        return members

    def _drawn_extents(self, part: str, horizontal: bool, vertical: bool,
                       snapshot: Mapping[str, Any]) -> dict[str, float]:
        """The extent members the overlay really drew on the touched axes (its text box; floors and the safe area
        applied)."""

        slot = snapshot["slots"][PARTS[part][0]]
        font_size = float(slot["font_size"])
        box = slot["text"]
        keys = EXTENT_KEYS[part]
        members: dict[str, float] = {}
        if horizontal:
            members[keys[0]] = extent_value(box[2], font_size=font_size)
        if vertical:
            members[keys[1]] = extent_value(box[3], font_size=font_size)
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
        overlay = PARTS[part][0]
        resolution = resolve_resize_edge_snap(
            rect.translated(-safe.x(), -safe.y()), safe.size(), horizontal_edge=horizontal_edge,
            vertical_edge=vertical_edge, peer_rects=[
                _qrect(slot["rect"]).translated(-safe.x(), -safe.y())
                for name, slot in snapshot["slots"].items() if name != overlay], min_size=QSize(1, 1))
        target = resolution.rect
        if part == "now_playing":
            # The parent frame is artwork + gap + an independently laid-out text group. Delta-based axis sizing
            # turns the exact pointer displacement into artwork width/height, without feeding metadata reflow
            # back into the gesture. A visible card border is the artwork frame itself.
            from rendering.quick.fullscreen_artwork_resize import artwork_factor_after_frame_delta

            members = {}
            for key, touched, new_frame_size, old_frame_size, old_art_size, old_factor in (
                ("artwork_width", horizontal_edge is not None, target.width(), origin.rect.width(),
                 origin.artwork_size[0], origin.artwork_factors[0]),
                ("artwork_height", vertical_edge is not None, target.height(), origin.rect.height(),
                 origin.artwork_size[1], origin.artwork_factors[1]),
            ):
                if touched and old_art_size > 0.0:
                    members[key] = artwork_factor_after_frame_delta(
                        old_factor, old_art_size, new_frame_size - old_frame_size)
            changed = self._set_members(item, members)
        else:
            changed = self._set_members(item, self._extents_for(
                part, target.width() if horizontal_edge else None, target.height() if vertical_edge else None,
                snapshot))
            # The toast uses its actual drawn text extents: it floors them when the text cannot shrink more.
            drawn = self._geometry()
            if drawn is not None:
                settled = self._drawn_extents(part, horizontal_edge is not None, vertical_edge is not None, drawn)
                if settled != {k: item.current_size_payload.get(k) for k in settled}:
                    changed = self._set_members(item, settled) or changed
        # The opposite edge stays where it was.
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
        """Restore Size: the part's size factors and extents back to their canonical defaults and its children back
        to their authored places and sizes, keeping its top centre.

        Ordinary Edit's Restore Size likewise returns the uniform scale, drops ``content_extent`` and restores the
        authored child geometry (``restore_authored_child_geometry``: the records and the payload's carrier together).
        """

        part = edit_part(item)
        if part is None:
            return False
        self._resize_origins.pop(item.source_key, None)
        canonical = canonical_fullscreen_overlays()[PARTS[part][0]]
        before = QRect(item.current_global_rect)
        members = {key: float(canonical[key]) for key in PARTS[part][1]
                   if key not in ("offset_x", "offset_y", CHILD_GEOMETRY_KEY)}
        children = bool(item.current_child_sizes) or bool(item.current_size_payload.get(CHILD_GEOMETRY_KEY))
        if children:
            item.current_size_payload = item.restore_authored_child_geometry(item.current_size_payload)
        if not self._set_members(item, members) and not children:
            return False
        if children:
            self.project(item)
        self._keep(item, before, "top_centre")
        return True

__all__ = [
    "CARD_EDIT_ID",
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
    "is_card_item",
    "is_fullscreen_overlay_item",
    "offsets_for_position",
    "resize_edges",
]
