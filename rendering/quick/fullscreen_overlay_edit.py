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
  (``core.settings.fullscreen_overlays.NOW_PLAYING_CHILD_ROLES``: artwork, the text group, artist, controls, seek
  bar), its payload
  carries ordinary Edit's ``child_geometry`` record map and the Now Playing slot (QML) is its presentation, exposing
  ``customEditableChildRoles`` as every child-capable widget does. So the one child editor (``CustomLayoutOverlay.qml``'s
  child layer; the owner's ``begin_child_move``/``update_child_move``/``begin_child_resize``/``update_child_resize``
  and ``resolve_child_*_geometry``) moves and sizes each part inside the block, with its lock, guides, containment,
  collision preference and undo; this module only carries the records into the overlays' value. Decided (mirroring
  ordinary Edit, where a widget with a visible card keeps its children editable inside the card): the parts are
  editable whether or not the block draws a surface (Card); the card is then the block's visible extent.
* **Geometry: the ordinary Edit handlers, the overlays' own value** (plan 1B.7b). Move, corner drag, wheel, side and
  two-axis diagonal handles and Restore Size are ``QuickCustomLayoutOwner``'s ordinary handlers on these items, bounded
  by and snapped within the expanded card's safe area (``edit_frame``, the owner's ``_edit_frame``) with the other
  items as peers. They change only the session's generic state: the frame rectangle, ``resize_scale`` and the content
  box (``current_content_extent``). This module's ``project`` (the session's change publisher) turns that state into
  the overlays' placement members (``core.settings.fullscreen_overlays.PLACEMENT_KEYS``): ``scale`` is the item's
  ``resize_scale``; a content box axis changed by a side handle becomes the part's text-box extent on that axis (the
  untouched axis keeps its member, natural stays natural); the offset from the anchor corner (fractions of the safe
  area) is the one that draws the frame where the handler put it, keeping the edges the handler kept (a side handle's
  opposite edge, a uniform scale's top centre, Restore Size's top left). The frame is then read back from the live QML,
  so a frame is always what is drawn (content size, stacking and the card's control reserves included) and a clamped
  place is stored as drawn. Positions stay relative to the safe area, so they reflow on displays of other sizes and
  DPRs.
* **Save** writes exactly the placement members into the one value; nothing else is in the session, so the ordinary
  layout and CUSTOM cannot change. Cancel restores the baseline (the committed value) through the session's own
  ``restore_baseline``.

The QML side (``ExpandedVisualizerOverlays.qml``) shows both overlays while editing and reports geometry changes; the
scene controller reads its geometry (``expanded_overlay_edit_geometry``) only at Edit edges.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from copy import deepcopy
from typing import Any

from PySide6.QtCore import QPoint, QRect

from core.settings.fullscreen_overlays import (
    BASE_WIDTH_KEY,
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
from rendering.custom_child_geometry import normalize_child_geometry
from rendering.custom_layout_session import CustomLayoutKey, CustomLayoutSession, CustomLayoutSessionItem
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
#: Now Playing's block also carries its children's records (ordinary Edit's ``child_geometry``; the artwork child record
#: multiplies the size the block's box gives it, plan 1C.3).
PARTS: dict[str, tuple[str, tuple[str, ...]]] = {
    "preset": ("preset", ("offset_x", "offset_y", "scale", "text_width", "text_height")),
    "now_playing": ("now_playing", ("offset_x", "offset_y", "scale", "text_width", "text_height", BASE_WIDTH_KEY,
                                    CHILD_GEOMETRY_KEY)),
    "volume_osd": ("volume_osd", ("offset_x", "offset_y", "scale")),
}
#: The size factor the item's ``resize_scale`` (corner handles and the wheel) projects into.
SCALE_KEY = {"preset": "scale", "now_playing": "scale", "volume_osd": "scale"}
#: The (horizontal, vertical) extents the item's content box (side and diagonal handles) projects into: the toast's
#: text box; Now Playing's block (its width beyond the natural artwork column, its height; plan 1C.3: the artwork and
#: the text reflow inside it by the Media card's artwork rule).
EXTENT_KEYS = {"preset": ("text_width", "text_height"), "now_playing": ("text_width", "text_height"),
               "volume_osd": ()}
#: The parts whose box has a base (plan 1C.3, lead 12 Nov): the block's width and height are stored at the first size
#: gesture on it (a side handle, a corner, the wheel), and its width there as ``base_width``, the Media artwork rule's
#: reference, so that first sample moves nothing.
BASE_KEYS = {"now_playing": BASE_WIDTH_KEY}
#: The parts with extents declare both content axes: the Edit layer draws their side strips and diagonal corners.
CONTENT_AXES = frozenset({"horizontal", "vertical"})
#: The parts whose children ordinary Edit's child editor edits (role descriptors, from the one settings owner).
CHILD_ROLES = {"now_playing": NOW_PLAYING_CHILD_ROLES}
#: The overlays' frames may be a single line of text: their outer floor (replaces the ordinary widget floor).
LAYOUT_MINIMUM_SIZE = (1.0, 1.0)

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


def extent_value(size: float, *, font_size: float, inset: float = 0.0) -> float:
    """The stored text-box extent (ems of the overlay's font) that draws a frame of ``size`` px on one axis.

    ``inset`` is what the frame holds besides the box on that axis: the card padding on both sides, and on Now
    Playing's horizontal axis its natural artwork column (the artwork's natural side and the gap).
    """

    box = max(1.0, float(size) - float(inset))
    return round(max(0.01, min(TEXT_EXTENT_MAX, box / max(1.0, float(font_size)))), 4)


def _clamp_scale(value: float) -> float:
    return round(max(SCALE_MIN, min(SCALE_MAX, float(value))), 4)


def _kept_edge(requested: float, requested_extent: float, previous: float, previous_extent: float,
               drawn_extent: float) -> float:
    """Where a frame of ``drawn_extent`` starts on one axis so it keeps the edge the handler kept: the near edge if it
    stayed, else the far edge if it stayed, else the centre (a move, or a scale about the centre)."""

    if abs(requested - previous) < 0.5:
        return requested
    if abs((requested + requested_extent) - (previous + previous_extent)) < 0.5:
        return requested + requested_extent - drawn_extent
    return requested + (requested_extent - drawn_extent) / 2.0


def _qrect(values: tuple[float, float, float, float], origin: QPoint = QPoint()) -> QRect:
    x, y, width, height = (float(v) for v in values)
    return QRect(int(round(x)) + origin.x(), int(round(y)) + origin.y(),
                 max(1, int(round(width))), max(1, int(round(height))))


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
        # Per part: the frame last drawn (global) and the content box last projected; the safe area (global).
        self._drawn: dict[CustomLayoutKey, QRect] = {}
        self._boxes: dict[CustomLayoutKey, tuple[float, float] | None] = {}
        self._frame: QRect | None = None
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
        self._frame = self._safe_rect(snapshot).translated(self._origin)
        canonical = canonical_fullscreen_overlays()
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
            scale = float(payload[SCALE_KEY[part]])
            # Restore Size's authored payload: the canonical size members (scale, extents, artwork factors), no
            # children's records; the offsets are re-derived from the frame the ordinary reset keeps.
            authored = {key: deepcopy(canonical[overlay][key]) for key in keys if key != CHILD_GEOMETRY_KEY}
            key = CustomLayoutKey(edit_widget_id(part), self._identity)
            self._drawn[key] = QRect(rect)
            self._boxes[key] = None
            session.add_item(CustomLayoutSessionItem(
                source_key=key,
                model_identity=edit_widget_id(part),
                baseline_global_rect=rect,
                current_global_rect=rect,
                baseline_size_payload=payload,
                current_size_payload=dict(payload),
                baseline_enabled=True,
                current_enabled=True,
                resize_capable=True,
                # The overlay's own scale is the ordinary uniform scale: corners and the wheel change it.
                baseline_resize_scale=scale,
                resize_scale=scale,
                size_reset_capable=True,
                authored_reference_size=(rect.width() / scale, rect.height() / scale),
                authored_size_payload=authored,
                layout_minimum_size=LAYOUT_MINIMUM_SIZE,
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
        self._drawn.clear()
        self._boxes.clear()
        self._frame = None

    def edit_frame(self, item: CustomLayoutSessionItem) -> QRect | None:
        """The global rectangle an overlay part is edited inside (the expanded card's safe area); None for any other
        item (the expanded card's own item keeps its display)."""

        if edit_part(item) is None or self._frame is None:
            return None
        return QRect(self._frame)

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
            if _item is not None and edit_part(_item) is not None:
                self._apply_edit(_item)
            self._project_value(self.draft_value())
            changed = self._sync_rects()
        finally:
            self._projecting = False
        self._notify(changed, skip=_item)

    def _apply_edit(self, item: CustomLayoutSessionItem) -> None:
        """Turn ``item``'s edited generic state (frame, ``resize_scale``, content box) into its placement members.

        The size members first (scale; a changed content box axis as that axis's text-box extent), drawn once to learn
        the frame's new size; then the offset that puts that frame where the handler put it, keeping the edges it
        kept. The final frame is read back by ``project`` (what is drawn, a clamped place included).
        """

        part = edit_part(item)
        overlay, keys = PARTS[part]
        key = item.source_key
        requested = QRect(item.current_global_rect)
        previous = QRect(self._drawn.get(key, requested))
        payload = {name: deepcopy(item.current_size_payload[name]) for name in keys
                   if name in item.current_size_payload}
        scale = _clamp_scale(item.resize_scale)
        item.resize_scale = scale
        box = item.current_content_extent
        snapshot = self._geometry()
        if snapshot is None:
            payload[SCALE_KEY[part]] = scale
            item.current_size_payload = payload
            return
        base_key = BASE_KEYS.get(part)
        sizing = scale != float(payload.get(SCALE_KEY[part], scale)) or box is not None
        if base_key is not None and sizing and float(payload.get(base_key) or 0.0) <= 0.0:
            # The first size gesture on the block: store the block as drawn now (its box on both axes, read before
            # this sample changes anything, in ems of the font it is drawn at) and its width as the base. The gesture
            # then changes the box from there, so its first sample moves nothing.
            drawn_now = self._drawn_extents(part, True, True, snapshot)
            for name, value in drawn_now.items():
                if float(payload.get(name) or 0.0) <= 0.0:
                    payload[name] = value
            payload[base_key] = drawn_now[EXTENT_KEYS[part][0]]
        payload[SCALE_KEY[part]] = scale
        if box is not None and EXTENT_KEYS[part]:
            last = self._boxes.get(key)
            reference = last if last is not None else (previous.width() / scale, previous.height() / scale)
            width = float(box[0]) * scale if abs(float(box[0]) - float(reference[0])) > 1e-6 else None
            height = float(box[1]) * scale if abs(float(box[1]) - float(reference[1])) > 1e-6 else None
            payload.update(self._extents_for(part, width, height, snapshot))
        self._boxes[key] = None if box is None else (float(box[0]), float(box[1]))
        item.current_size_payload = payload
        self._project_value(self.draft_value())
        snapshot = self._geometry() or snapshot
        if box is not None and EXTENT_KEYS[part]:
            # The box as drawn (its floors and the safe area applied) on the axes the box changed.
            settled = self._drawn_extents(part, width is not None, height is not None, snapshot)
            if settled and settled != {name: payload.get(name) for name in settled}:
                item.current_size_payload = {**payload, **settled}
                self._project_value(self.draft_value())
                snapshot = self._geometry() or snapshot
        drawn = _qrect(snapshot["parts"][part], self._origin)
        if drawn == requested:
            # The value already draws the frame (Cancel, undo, a size change that kept its place): keep its offsets
            # exactly rather than re-deriving them from integer frames.
            return
        target_x = _kept_edge(requested.x(), requested.width(), previous.x(), previous.width(), drawn.width())
        target_y = _kept_edge(requested.y(), requested.height(), previous.y(), previous.height(), drawn.height())
        slot = snapshot["slots"][overlay]
        position = (slot["pos"][0] + target_x - drawn.x(), slot["pos"][1] + target_y - drawn.y())
        self._place(item, overlay, position, snapshot)

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
            self._drawn[item.source_key] = QRect(rect)
            if rect != item.current_global_rect:
                item.current_global_rect = QRect(rect)
                changed.append(item)
        self._frame = self._safe_rect(snapshot).translated(self._origin)
        return changed

    # ------------------------------------------------------------------------------------------- gestures

    def _place(self, item: CustomLayoutSessionItem, overlay: str, stage_position: tuple[float, float],
               snapshot: Mapping[str, Any]) -> None:
        """Move ``overlay`` to ``stage_position`` and keep the offset it really took (WYSIWYG).

        The overlays clamp themselves to the safe area and clear of the card's controls; the stored offset is the one
        that reproduces the drawn place exactly, never an intent beyond a clamp that would surface on another display.
        """

        slot = snapshot["slots"][overlay]
        offset_x, offset_y = offsets_for_position(stage_position, slot["anchored"],
                                                  (snapshot["safe_width"], snapshot["safe_height"]))
        item.current_size_payload = {**item.current_size_payload, "offset_x": offset_x, "offset_y": offset_y}
        self._project_value(self.draft_value())
        drawn = self._geometry()
        if drawn is None:
            return
        slot = drawn["slots"][overlay]
        effective = offsets_for_position(slot["pos"], slot["anchored"], (drawn["safe_width"], drawn["safe_height"]))
        payload = item.current_size_payload
        if (payload.get("offset_x"), payload.get("offset_y")) != effective:
            item.current_size_payload = {**payload, "offset_x": effective[0], "offset_y": effective[1]}

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
        """The extent members the overlay really drew on the touched axes (its box; floors and the safe area
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


__all__ = [
    "CARD_EDIT_ID",
    "CONTENT_AXES",
    "EDIT_ID_PREFIX",
    "EXTENT_KEYS",
    "FullscreenOverlayEdit",
    "PARTS",
    "draft_value",
    "edit_part",
    "edit_widget_id",
    "extent_value",
    "is_card_item",
    "is_fullscreen_overlay_item",
    "offsets_for_position",
]
