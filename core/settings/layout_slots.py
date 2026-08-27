"""Pure helpers for saving and applying widget layout slots."""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

from core.settings.capability_activation import is_widget_family_effective
from core.settings.widget_family_catalog import get_family_id_for_widget


LAYOUT_SLOTS_VERSION = 1
LAYOUT_SLOTS_SETTINGS_KEY = "layout_slots"
VALID_LAYOUT_SLOT_IDS = tuple(str(value) for value in range(1, 10)) + ("0",)

_ROOT_LAYOUT_KEYS = ("custom_layout", "custom_layout_restore")

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
        "header_logo_px_adjust",
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
        "version": LAYOUT_SLOTS_VERSION,
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

    for section_id, section_payload in payload_sections.items():
        if not isinstance(section_payload, Mapping):
            continue
        current_section = widgets_config.get(section_id, {})
        if not isinstance(current_section, dict):
            current_section = {}
            widgets_config[str(section_id)] = current_section
        for key, value in section_payload.items():
            key_text = str(key)
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


def _is_layout_field(section_id: str, key: str) -> bool:
    if key in _SOURCE_SECTION_KEYS:
        return False
    if section_id == "spotify_visualizer":
        return key in {"enabled", "position", "monitor", "width", "height"}
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
