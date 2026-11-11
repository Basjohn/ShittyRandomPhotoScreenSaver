"""Expanded Visualizer overlays (plan 01 §G, M3b): their one canonical setting and its normaliser.

``widgets.spotify_visualizer.fullscreen_overlays`` holds every option of the two full-display overlays (the preset
toast and Now Playing) and their shared font. It is a **global Visualizer setting with a canonical default**, one
value per settings profile, like ``expanded_display_requested``: it has no mode prefix, so mode presets and the Custom
snapshot exclude it by construction (no preset repair fill; the completeness guard is unaffected), and preset
application or the runtime preset transaction never touches it. Settings' Visualizers → Fullscreen Mode pill edits it.

Each overlay's placement is its anchor corner plus an offset and a scale relative to the expanded display's safe area
(``offset_x``/``offset_y`` are fractions of the safe area's width/height in screen axes, ``scale`` multiplies the
overlay's size; zero offset and unit scale are the defaults). Now Playing's artwork size has one carrier, its ``artwork``
child record (plan 1B.7d; the retired ``artwork_scale`` / ``artwork_width`` / ``artwork_height`` load into it). Fullscreen Edit (M3c)
edits exactly these placement values: the offsets, the scales and the single-axis extents below. The corner is Settings'
(the anchor); changing it rebases the offset (:func:`rebase_offset_for_corner`).

Single-axis sizing (Fullscreen Edit's side handles, ordinary Edit's content box; plan 1B.7b): each overlay's parent
edits its text box, ``text_width`` / ``text_height`` in ems of its font size (``0`` = natural), as the Media card's
content extent reflows its content; the artwork's size is its child record's alone. Individual artwork, metadata and control child geometry remains separately editable. No resize changes a curated
Visualizer preset.

Now Playing's parts (Fullscreen Edit's child editing, operator 8 Nov: "I should be able to move every element around in
that block and change it"): ``now_playing.child_geometry`` is ordinary Edit's CUSTOM ``child_geometry`` carrier for the
block's children (:data:`NOW_PLAYING_CHILD_ROLES`: the artwork, title, artist, optional album and Media Controls bar),
one record per moved or sized part (``width_scale``/``height_scale`` of its own drawn size, ``x_offset``/``y_offset``
in fractions of :data:`CHILD_NORMALIZATION_EMS` ems of the overlay's font); ``{}`` (the canonical default) is today's
layout, so a value stored before it reads as it always drew (no bridge). It is parsed by ordinary Edit's own
``normalize_child_geometry`` against the declared roles.

The Volume OSD's placement over the expanded card (``volume_osd``; Fullscreen Edit, operator 8 Nov) mirrors the
overlays' model: ``offset_x``/``offset_y`` in fractions of the safe area and ``scale``, both relative to where the OSD's
ordinary layout puts it (zero offset and unit scale: exactly there). It applies only while the display-wide card is
drawn; the OSD's ordinary placement (ordinary Edit, CUSTOM) is never changed by it. It has no Settings options.

Pure and Qt-free: the settings model, Settings and the display runtime all read it.
"""
from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
import math
from typing import Any

from core.settings.default_contract import require_canonical_default
from rendering.custom_child_geometry import (
    CUSTOM_CHILD_GEOMETRY_PAYLOAD_KEY,
    CustomChildRoleDescriptor,
    freeform_artwork_child_role,
    normalize_child_geometry,
)

FULLSCREEN_OVERLAYS_KEY = "widgets.spotify_visualizer.fullscreen_overlays"
#: The two overlays, in their canonical order.
OVERLAY_IDS = ("preset", "now_playing")
#: The Volume OSD's placement over the expanded card (placement members only; not an overlay of its own).
VOLUME_OSD_ID = "volume_osd"
#: Anchor corners, in Settings' order.
CORNERS = ("top_left", "top_right", "bottom_left", "bottom_right")
MEDIA_CONTROLS_STYLES = ("bar", "floating")
FONT_SIZE_MIN, FONT_SIZE_MAX = 12, 72
OFFSET_MIN, OFFSET_MAX = -1.0, 1.0
SCALE_MIN, SCALE_MAX = 0.5, 3.0
#: The size factors (each clamped to SCALE_MIN..SCALE_MAX): the overlays' uniform scales.
SCALE_KEYS = ("scale",)
#: Retired Now Playing members (plan 1B.7d: one artwork size carrier, its ``artwork`` child record). A stored value
#: that still has them loads through :func:`_bridge_artwork_factors` (Docs/Architecture/Persisted_Input_Compatibility.md).
LEGACY_ARTWORK_FACTOR_KEYS = ("artwork_scale", "artwork_width", "artwork_height")
#: Text-box extents in ems (0 = natural): each overlay's parent side handles edit them (ordinary Edit's content box).
TEXT_EXTENT_KEYS = ("text_width", "text_height")
TEXT_EXTENT_MAX = 60.0
#: Now Playing's per-part geometry member (ordinary Edit's CUSTOM ``child_geometry`` carrier).
CHILD_GEOMETRY_KEY = CUSTOM_CHILD_GEOMETRY_PAYLOAD_KEY
#: Now Playing's children in Fullscreen Edit (ordinary Edit's child-role descriptors, mirroring the Media card's): the
#: artwork is ordinary Edit's freeform artwork frame (free X/Y, the image cropped); the title and the artist line scale
#: uniformly (their text keeps its shape, as the Media card's metadata and artist do); the Media Controls bar sizes
#: freely on each axis (as the Media card's transport controls). Every one moves. Alignment is declared as on the Media
#: card (plan 1B.7c): the title, like Media's header, carries the block's one orientation (``alignment_flip``: its record's
#: ``alignment`` flips the corner's authored side) and its ``semantic_corner_anchor``; the artist and album lines flip
#: their own text alignment on top of that orientation (Media's metadata and artist).
NOW_PLAYING_CHILD_ROLES: tuple[CustomChildRoleDescriptor, ...] = (
    freeform_artwork_child_role("artwork", minimum_scale=(0.40, 0.40), maximum_scale=(3.00, 3.00), movable=True),
    CustomChildRoleDescriptor("title", axes=("horizontal", "vertical"), minimum_scale=(0.50, 0.50),
                              maximum_scale=(2.50, 2.50), uniform_scale=True, movable=True, alignment_flip=True,
                              authored_alignment="left", semantic_corner_anchor=True),
    CustomChildRoleDescriptor("artist", axes=("horizontal", "vertical"), minimum_scale=(0.50, 0.50),
                              maximum_scale=(2.50, 2.50), uniform_scale=True, movable=True, alignment_flip=True,
                              authored_alignment="left"),
    CustomChildRoleDescriptor("album", axes=("horizontal", "vertical"), minimum_scale=(0.50, 0.50),
                              maximum_scale=(2.50, 2.50), uniform_scale=True, movable=True, alignment_flip=True,
                              authored_alignment="left"),
    CustomChildRoleDescriptor("controls", axes=("horizontal", "vertical"), minimum_scale=(0.50, 0.50),
                              maximum_scale=(2.50, 2.50), uniform_scale=False, movable=True),
    # The optional Seek Bar (plan 1B.7g): the Media card's ``seek_bar`` role, its limits included.
    CustomChildRoleDescriptor("seek_bar", axes=("horizontal", "vertical"), minimum_scale=(0.35, 0.50),
                              maximum_scale=(2.00, 3.00), uniform_scale=False, movable=True),
)
#: The children's offsets are fractions of a square of this many ems of the overlay's (scaled) font: they move with the
#: block's scale and the font size, and never with a track's text length.
CHILD_NORMALIZATION_EMS = 10.0
#: The placement members Fullscreen Edit writes, per overlay (the corner is Settings').
PLACEMENT_KEYS = {"preset": ("offset_x", "offset_y", "scale", "text_width", "text_height"),
                  "now_playing": ("offset_x", "offset_y", "scale", "text_width", "text_height", CHILD_GEOMETRY_KEY),
                  VOLUME_OSD_ID: ("offset_x", "offset_y", "scale")}

_TRUE = frozenset({"1", "true", "yes", "on"})
_FALSE = frozenset({"0", "false", "no", "off"})


def canonical_fullscreen_overlays(application: str | None = None) -> dict[str, Any]:
    """A fresh copy of the canonical default (fail-loud when the schema lacks it)."""

    value = require_canonical_default(FULLSCREEN_OVERLAYS_KEY, application)
    if not isinstance(value, Mapping):
        raise TypeError(f"canonical {FULLSCREEN_OVERLAYS_KEY} must be a mapping")
    return deepcopy(dict(value))


def _bool(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and value in (0, 1):
        return bool(value)
    if isinstance(value, str):
        text = value.strip().lower()
        if text in _TRUE:
            return True
        if text in _FALSE:
            return False
    return default


def _number(value: Any, default: float, low: float, high: float) -> float:
    if isinstance(value, bool):
        return default
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return default
    if not math.isfinite(number):
        return default
    return max(low, min(high, number))


def normalize_fullscreen_overlays(value: Any, application: str | None = None) -> dict[str, Any]:
    """The stored value as the canonical shape: every key the canonical default declares, each admitted.

    Unknown keys are dropped; a missing or malformed member falls back to its canonical default (never to
    ``bool(value)``); numbers are clamped to their admitted ranges; a corner must be one of :data:`CORNERS`.
    """

    result = canonical_fullscreen_overlays(application)
    if not isinstance(value, Mapping):
        return result
    family = value.get("font_family")
    if isinstance(family, str) and family.strip():
        result["font_family"] = family.strip()
    if "font_size" in value:
        size = _number(value.get("font_size"), float(result["font_size"]), FONT_SIZE_MIN, FONT_SIZE_MAX)
        result["font_size"] = int(round(size))
    for overlay in (*OVERLAY_IDS, VOLUME_OSD_ID):
        raw = value.get(overlay)
        if not isinstance(raw, Mapping):
            continue
        target = result[overlay]
        for key, default in tuple(target.items()):
            if key not in raw:
                continue
            item = raw[key]
            if key == CHILD_GEOMETRY_KEY:
                target[key] = normalize_now_playing_children(item)
            elif key == "media_controls_style":
                if isinstance(item, str) and item.strip().lower() in MEDIA_CONTROLS_STYLES:
                    target[key] = item.strip().lower()
            elif key == "corner":
                if isinstance(item, str) and item.strip().lower() in CORNERS:
                    target[key] = item.strip().lower()
            elif isinstance(default, bool):
                target[key] = _bool(item, default)
            elif key in ("offset_x", "offset_y"):
                target[key] = _number(item, float(default), OFFSET_MIN, OFFSET_MAX)
            elif key in SCALE_KEYS:
                target[key] = _number(item, float(default), SCALE_MIN, SCALE_MAX)
            elif key in TEXT_EXTENT_KEYS:
                target[key] = _number(item, float(default), 0.0, TEXT_EXTENT_MAX)
        if overlay == "now_playing":
            _bridge_artwork_factors(raw, target)
    return result


def _bridge_artwork_factors(raw: Mapping[str, Any], target: dict[str, Any]) -> None:
    """Load bridge (plan 1B.7d): a value stored with the retired block factors ``artwork_scale`` /
    ``artwork_width`` / ``artwork_height`` folds them into the ``artwork`` child record, the one artwork size carrier,
    so the artwork keeps its drawn size (the record's factors multiply; the role's limits clamp them)."""

    def factor(key: str) -> float:
        return _number(raw.get(key), 1.0, SCALE_MIN, SCALE_MAX)

    uniform = factor("artwork_scale")
    width, height = uniform * factor("artwork_width"), uniform * factor("artwork_height")
    if abs(width - 1.0) < 1e-9 and abs(height - 1.0) < 1e-9:
        return
    children = dict(target.get(CHILD_GEOMETRY_KEY) or {})
    record = dict(children.get("artwork") or {})
    record["width_scale"] = float(record.get("width_scale", 1.0)) * width
    record["height_scale"] = float(record.get("height_scale", 1.0)) * height
    record.setdefault("x_offset", 0.0)
    record.setdefault("y_offset", 0.0)
    children["artwork"] = record
    target[CHILD_GEOMETRY_KEY] = normalize_now_playing_children(children)


def normalize_now_playing_children(raw: Any) -> dict[str, dict[str, Any]]:
    """Now Playing's ``child_geometry`` as stored: ordinary Edit's parse (known roles, clamped, authored records
    omitted), each record in its canonical mapping form."""

    return {role_id: size.to_mapping()
            for role_id, size in normalize_child_geometry(raw, NOW_PLAYING_CHILD_ROLES).items()}


def rebase_offset_for_corner(options: Mapping[str, Any], corner: str) -> dict[str, Any]:
    """One overlay's options with its anchor moved to ``corner`` (Settings' Corner choice), its offset rebased.

    The offset is relative to the anchor corner, so a new corner reinterprets it. Each axis keeps its offset when it
    still points into the display from the new corner (right of a left corner, left of a right corner, below a top
    corner, above a bottom corner; zero always does): the overlay stays in bounds, the same distance in from the new
    anchor's edge. An axis whose offset would push the overlay out past the new anchor's edge resets to zero, so the
    overlay sits at the new corner instead of against the far side. Pure; everything but the offset is unchanged.
    """

    result = dict(options)
    corner = str(corner)
    if corner not in CORNERS:
        return result
    result["corner"] = corner
    inward_x = 1.0 if corner.endswith("_left") else -1.0
    inward_y = 1.0 if corner.startswith("top_") else -1.0
    for key, inward in (("offset_x", inward_x), ("offset_y", inward_y)):
        value = result.get(key, 0.0)
        try:
            number = float(value)
        except (TypeError, ValueError):
            number = 0.0
        if not math.isfinite(number) or number * inward < 0.0:
            number = 0.0
        result[key] = number
    return result


def volume_osd_anchor(authored: tuple[float, float, float, float], scale: float) -> tuple[float, float]:
    """Where the Volume OSD's top-left sits at a zero offset: its ordinary rectangle scaled about its own centre."""

    x, y, width, height = (float(v) for v in authored)
    factor = max(SCALE_MIN, min(SCALE_MAX, float(scale)))
    return x + width * (1.0 - factor) / 2.0, y + height * (1.0 - factor) / 2.0


def volume_osd_rect(authored: tuple[float, float, float, float], safe: tuple[float, float, float, float],
                    offset_x: float, offset_y: float, scale: float) -> tuple[float, float, float, float]:
    """The Volume OSD's rectangle over the expanded card (``volume_osd``), in the coordinates of ``authored``.

    Its ordinary rectangle (``authored``) scaled about its centre by ``scale``, moved by the offset (fractions of the
    safe area ``safe``: x, y, width, height) and kept inside the safe area, as the overlays are.
    """

    _x, _y, width, height = (float(v) for v in authored)
    safe_x, safe_y, safe_width, safe_height = (float(v) for v in safe)
    factor = max(SCALE_MIN, min(SCALE_MAX, float(scale)))
    drawn_width, drawn_height = max(1.0, width * factor), max(1.0, height * factor)
    anchor_x, anchor_y = volume_osd_anchor(authored, factor)

    def clamp(value: float, low: float, high: float) -> float:
        return max(low, min(max(low, high), value))

    return (clamp(anchor_x + float(offset_x) * safe_width, safe_x, safe_x + safe_width - drawn_width),
            clamp(anchor_y + float(offset_y) * safe_height, safe_y, safe_y + safe_height - drawn_height),
            drawn_width, drawn_height)


__all__ = [
    "CHILD_GEOMETRY_KEY",
    "CHILD_NORMALIZATION_EMS",
    "CORNERS",
    "FONT_SIZE_MAX",
    "FONT_SIZE_MIN",
    "FULLSCREEN_OVERLAYS_KEY",
    "LEGACY_ARTWORK_FACTOR_KEYS",
    "OFFSET_MAX",
    "OFFSET_MIN",
    "OVERLAY_IDS",
    "PLACEMENT_KEYS",
    "SCALE_KEYS",
    "SCALE_MAX",
    "SCALE_MIN",
    "TEXT_EXTENT_KEYS",
    "TEXT_EXTENT_MAX",
    "NOW_PLAYING_CHILD_ROLES",
    "VOLUME_OSD_ID",
    "canonical_fullscreen_overlays",
    "normalize_fullscreen_overlays",
    "normalize_now_playing_children",
    "rebase_offset_for_corner",
    "volume_osd_anchor",
    "volume_osd_rect",
]
