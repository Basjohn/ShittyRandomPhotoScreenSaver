"""Pure helpers for saving and applying widget layout slots."""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

from core.settings.capability_activation import is_widget_family_effective
from core.settings.widget_family_catalog import get_family_id_for_widget


LAYOUT_SLOTS_VERSION = 1
LAYOUT_SLOT_PAYLOAD_VERSION = 2
LAYOUT_SLOTS_SETTINGS_KEY = "layout_slots"
VALID_LAYOUT_SLOT_IDS = tuple(str(value) for value in range(1, 10)) + ("0",)

_ROOT_LAYOUT_KEYS = ("custom_layout", "custom_layout_restore")
_CLOCK_WIDGET_IDS = ("clock", "clock2", "clock3")
_CLOCK_DISPLAY_MODES = frozenset({"analog", "digital"})

_LAYOUT_SECTION_KEYS = frozenset(
    {
        "enabled",
        "position",
        "monitor",
        "margin",
        "font_family",
        "font_size",
        "display_mode",
        "format",
        "show_seconds",
        "show_timezone",
        "show_numerals",
        "show_condition_icon",
        "show_details_row",
        "show_forecast",
        "show_background",
        "show_controls",
        "show_header_frame",
        "show_album",
        "show_playback_state",
        "show_refresh_spiral",
        "show_separators",
        "show_sender",
        "show_subject",
        "show_envelope_icon",
        "show_three_dot_menu",
        "show_timestamp",
        "show_unread_count_in_header",
        "show_header_border",
        "group_threads",
        "auto_title_case",
        "clean_sender_names",
        "desaturate_when_no_unread",
        "rounded_artwork_border",
        "mute_button_enabled",
        "spotify_volume_enabled",
        "limit",
        "width",
        "height",
        "preferred_width",
        "preferred_height",
        "artwork_size",
        "icon_size",
        "detail_icon_size",
        "header_font_size",
        "grid_rows",
        "grid_columns",
        "grid_cols",
        "image_spacing",
        "image_border_width",
        "cell_base_width",
        "sender_subject_ratio",
        "sender_column_width",  # Legacy slot import; current Gmail saves the ratio.
        "max_sender_words",
        "max_subject_words",
        "date_display_mode",
        "separator_thickness",
        "boundary_separator_thickness",
        "card_border_width_px",
        "stacking_enabled",
    }
)

_SOURCE_SECTION_KEYS = frozenset(
    {
        "account_slot",
        "backend",
        "click_opens_browser",
        "custom_tag",
        "exit_on_click",
        "filter_label",
        "location",
        "play_sound_on_new_mail",
        "privacy_mode",
        "provider",
        "refresh_minutes",
        "sound_file_path",
        "sound_volume_percent",
        "subreddit",
        "tag",
        "timezone",
        "update_interval",
    }
)

_SOURCE_KEY_PREFIXES = (
    "bubble_",
    "devcurve_",
    "osc_",
    "sine_",
    "spectrum_",
)


def normalize_layout_slot_id(slot_id: object) -> str | None:
    """Return the canonical layout slot id, or None for invalid input."""

    text = str(slot_id or "").strip()
    if text in VALID_LAYOUT_SLOT_IDS:
        return text
    return None


def build_default_layout_slots_map() -> dict[str, Any]:
    return {
        "version": LAYOUT_SLOTS_VERSION,
        "slots": {},
    }


def load_layout_slots_map(widgets_config: Mapping[str, Any] | None) -> dict[str, Any]:
    """Return a normalized slots map from a widgets settings mapping."""

    candidate = (
        widgets_config.get(LAYOUT_SLOTS_SETTINGS_KEY, {})
        if isinstance(widgets_config, Mapping)
        else {}
    )
    if not isinstance(candidate, Mapping):
        return build_default_layout_slots_map()

    raw_slots = candidate.get("slots", {})
    if not isinstance(raw_slots, Mapping):
        raw_slots = {}

    slots: dict[str, Any] = {}
    for raw_slot_id, payload in raw_slots.items():
        slot_id = normalize_layout_slot_id(raw_slot_id)
        if slot_id is None or not isinstance(payload, Mapping):
            continue
        slots[slot_id] = deepcopy(dict(payload))

    return {
        "version": int(candidate.get("version", LAYOUT_SLOTS_VERSION) or LAYOUT_SLOTS_VERSION),
        "slots": slots,
    }


def write_layout_slots_map(
    widgets_config: dict[str, Any],
    layout_slots_map: Mapping[str, Any],
) -> dict[str, Any]:
    """Persist a normalized slots map back into the widgets config."""

    raw_slots = layout_slots_map.get("slots", {})
    if not isinstance(raw_slots, Mapping):
        raw_slots = {}

    slots: dict[str, Any] = {}
    for raw_slot_id, payload in raw_slots.items():
        slot_id = normalize_layout_slot_id(raw_slot_id)
        if slot_id is None or not isinstance(payload, Mapping):
            continue
        slots[slot_id] = deepcopy(dict(payload))

    widgets_config[LAYOUT_SLOTS_SETTINGS_KEY] = {
        "version": int(layout_slots_map.get("version", LAYOUT_SLOTS_VERSION) or LAYOUT_SLOTS_VERSION),
        "slots": slots,
    }
    return widgets_config


def capture_layout_slot(widgets_config: Mapping[str, Any] | None) -> dict[str, Any]:
    """Capture a source-free layout payload from the current widgets config."""

    if not isinstance(widgets_config, Mapping):
        widgets_config = {}

    payload: dict[str, Any] = {
        "version": LAYOUT_SLOT_PAYLOAD_VERSION,
        "widgets": {},
    }
    for root_key in _ROOT_LAYOUT_KEYS:
        value = widgets_config.get(root_key, {})
        payload[root_key] = deepcopy(dict(value)) if isinstance(value, Mapping) else {}

    sections: dict[str, dict[str, Any]] = {}
    for section_id, section in widgets_config.items():
        if section_id in _ROOT_LAYOUT_KEYS or section_id == LAYOUT_SLOTS_SETTINGS_KEY:
            continue
        if not isinstance(section, Mapping):
            continue
        captured = {
            str(key): deepcopy(value)
            for key, value in section.items()
            if _is_layout_field(str(section_id), str(key))
        }
        if captured:
            sections[str(section_id)] = captured
    # Clock active face is layout state, but deliberately not geometry state.
    # The shared baseline (``display_mode``) is captured through the normal layout
    # fields above; explicit per-display overrides must travel with the slot as
    # well so loading a slot restores the face that owned the saved variant rect.
    # Always emit the key for current-format slots, including an empty mapping, so
    # replay can distinguish "this slot had no override" from legacy v1 payloads
    # that were incapable of recording the state at all.
    for clock_id in _CLOCK_WIDGET_IDS:
        section = widgets_config.get(clock_id, {})
        if not isinstance(section, Mapping):
            continue
        # Real Clock sections always own a display_mode baseline.  Also admit an
        # explicit override-only section for defensive/imported mappings, but do
        # not synthesize empty Clock sections in unrelated/minimal fixtures.
        if "display_mode" not in section and "display_mode_overrides" not in section:
            continue
        captured = sections.setdefault(clock_id, {})
        captured["display_mode_overrides"] = _normalize_clock_mode_overrides(
            section.get("display_mode_overrides", {})
        )

    payload["widgets"] = sections
    return payload


def save_layout_slot(
    widgets_config: dict[str, Any],
    slot_id: object,
) -> bool:
    """Capture the current layout into a slot on the provided widgets map."""

    normalized_slot_id = normalize_layout_slot_id(slot_id)
    if normalized_slot_id is None:
        return False

    layout_slots_map = load_layout_slots_map(widgets_config)
    slots = layout_slots_map.setdefault("slots", {})
    if not isinstance(slots, dict):
        slots = {}
        layout_slots_map["slots"] = slots
    slots[normalized_slot_id] = capture_layout_slot(widgets_config)
    write_layout_slots_map(widgets_config, layout_slots_map)
    return True


def apply_layout_slot(
    widgets_config: dict[str, Any],
    slot_id: object,
) -> bool:
    """Apply a saved layout slot into the provided widgets map."""

    payload = get_layout_slot_payload(widgets_config, slot_id)
    if payload is None:
        return False

    for root_key in _ROOT_LAYOUT_KEYS:
        value = payload.get(root_key, {})
        widgets_config[root_key] = deepcopy(dict(value)) if isinstance(value, Mapping) else {}

    payload_sections = payload.get("widgets", {})
    if not isinstance(payload_sections, Mapping):
        return True

    try:
        payload_version = int(payload.get("version", 1) or 1)
    except (TypeError, ValueError):
        payload_version = 1

    # v1 slots predate per-display Clock mode capture. Leaving a newer runtime
    # override in place would make the old override defeat the slot's saved
    # ``display_mode`` baseline and select geometry from the wrong face. The only
    # deterministic legacy replay is therefore the saved baseline with no screen
    # overrides. v2+ payloads make the override maps explicit slot state; restore
    # the complete set before ordinary section fields are applied so a missing/
    # empty override cannot inherit a later runtime choice.
    for clock_id in _CLOCK_WIDGET_IDS:
        saved_clock = payload_sections.get(clock_id)
        if not isinstance(saved_clock, Mapping):
            continue
        # A real captured Clock section always contains display_mode.  Preserve
        # compatibility with deliberately partial/imported slot payloads by not
        # touching Clock state that the payload does not represent at all.
        if "display_mode" not in saved_clock and "display_mode_overrides" not in saved_clock:
            continue
        current_clock = widgets_config.get(clock_id, {})
        if not isinstance(current_clock, dict):
            current_clock = dict(current_clock) if isinstance(current_clock, Mapping) else {}
            widgets_config[clock_id] = current_clock
        if payload_version < LAYOUT_SLOT_PAYLOAD_VERSION:
            current_clock.pop("display_mode_overrides", None)
            continue
        current_clock["display_mode_overrides"] = _normalize_clock_mode_overrides(
            saved_clock.get("display_mode_overrides", {})
        )

    for section_id, section_payload in payload_sections.items():
        if not isinstance(section_payload, Mapping):
            continue
        current_section = widgets_config.get(section_id, {})
        if not isinstance(current_section, dict):
            current_section = {}
            widgets_config[str(section_id)] = current_section
        for key, value in section_payload.items():
            key_text = str(key)
            if key_text == "display_mode_overrides":
                continue
            if not _is_layout_field(str(section_id), key_text):
                continue
            if (
                key_text == "enabled"
                and bool(value)
                and not _ordinary_enabled_replay_admitted(widgets_config, str(section_id))
            ):
                # A layout slot may restore ordinary ON, but it is not authority
                # to activate a family/capability or satisfy its dependencies.
                continue
            current_section[key_text] = deepcopy(value)
    return True


def get_layout_slot_payload(
    widgets_config: Mapping[str, Any] | None,
    slot_id: object,
) -> dict[str, Any] | None:
    normalized_slot_id = normalize_layout_slot_id(slot_id)
    if normalized_slot_id is None:
        return None
    layout_slots_map = load_layout_slots_map(widgets_config)
    slots = layout_slots_map.get("slots", {})
    if not isinstance(slots, Mapping):
        return None
    payload = slots.get(normalized_slot_id)
    if not isinstance(payload, Mapping):
        return None
    return deepcopy(dict(payload))


def _normalize_clock_mode_overrides(value: object) -> dict[str, str]:
    """Return only stable screen-signature -> Clock face state entries."""

    if not isinstance(value, Mapping):
        return {}
    normalized: dict[str, str] = {}
    for raw_identity, raw_mode in value.items():
        identity = str(raw_identity or "").strip()
        mode = str(raw_mode or "").strip().lower()
        if identity and mode in _CLOCK_DISPLAY_MODES:
            normalized[identity] = mode
    return normalized


def _is_layout_field(section_id: str, key: str) -> bool:
    if key in _SOURCE_SECTION_KEYS:
        return False
    if section_id == "spotify_visualizer":
        # Active mode is part of the visual layout state: numbered slots are a
        # fenced visualizer/layout hot-swap and the replacement generation must
        # reconstruct the mode that was visible when the slot was authored.
        # Per-mode tuning/presets remain ordinary configuration and are not
        # duplicated into layout slots.
        return key in {"enabled", "position", "monitor", "width", "height", "mode"}
    if any(key.startswith(prefix) for prefix in _SOURCE_KEY_PREFIXES):
        return False
    return key in _LAYOUT_SECTION_KEYS


def _ordinary_enabled_replay_admitted(
    widgets_config: Mapping[str, Any],
    widget_id: str,
) -> bool:
    family_id = get_family_id_for_widget(widget_id)
    if family_id is None:
        return True
    return is_widget_family_effective(widgets_config, family_id)
