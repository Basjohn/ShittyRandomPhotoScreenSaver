"""A mode's technical (audio analysis) controls as Studio properties (mode-neutral).

The controls are defined once in ``ui.tabs.media.technical_controls``; the Settings mode body holds their values in
its value cache (no widget). The Studio shows the controls with the same storage keys, ranges, choices and labels,
and admits edits with the same coercion and clamping. Adapters call these instead of carrying their own copies.
"""
from __future__ import annotations

from typing import Any

from ui.studio.schema import CHOICE, SCALAR, SWITCH, StudioProperty

TECHNICAL_GROUP = "Audio Analysis"
_NOTE = ("Live audio analysis for this mode (Settings' Technical controls). The synthetic previews bypass "
         "analysis; recorded clips are re-analysed with these values.")


def technical_keys(mode_id: str) -> frozenset[str]:
    """The storage keys of the mode's offered technical (Audio Analysis) controls."""
    from ui.tabs.media.technical_controls import _control_defs_for_mode, _storage_key
    return frozenset(_storage_key(mode_id, defn) for defn in _control_defs_for_mode(mode_id))


def clip_analysis_key(clip, mode_id: str, values) -> str:
    """A recorded clip's analysis cache key: the clip and the mode's Audio Analysis values it was analysed under."""
    import json
    keys = sorted(technical_keys(mode_id))
    return clip.description + "|" + json.dumps({key: values.get(key) for key in keys}, sort_keys=True, default=repr)


def technical_properties(mode_id: str, *, workspace: str, group: str = TECHNICAL_GROUP,
                         note: str = _NOTE) -> dict[str, tuple[StudioProperty, Any]]:
    """storage key -> (Studio property, Settings' control definition), in Settings' order."""
    from ui.tabs.media.technical_controls import _control_defs_for_mode, _storage_key
    out = {}
    for defn in _control_defs_for_mode(mode_id):
        key = _storage_key(mode_id, defn)
        label = (defn.label_text or defn.checkbox_text or key).replace("\n", " ").rstrip(":").strip()
        tooltip = (defn.tooltip or "") + ("\n" if defn.tooltip else "") + note
        common = dict(id=key, path=(key,), label=label, workspace=workspace, group=group, tooltip=tooltip)
        if defn.widget_kind == "checkbox":
            prop = StudioProperty(instrument=SWITCH, **common)
        elif defn.widget_kind == "combo":
            prop = StudioProperty(instrument=CHOICE, choices=tuple(text for text, _v in defn.options),
                                  choice_values=tuple(value for _t, value in defn.options), **common)
        else:
            integer = defn.default_type == "int"
            prop = StudioProperty(instrument=SCALAR, minimum=float(defn.minimum), maximum=float(defn.maximum),
                                  decimals=0 if integer else 2, integer=integer,
                                  units=f" {defn.suffix_text}" if getattr(defn, "suffix_text", "") else "",
                                  **common)
        out[key] = (prop, defn)
    return out


def admit_technical(entry: tuple[StudioProperty, Any], candidate: Any, previous: Any) -> Any:
    """Settings' own coercion (and clamping for numbers) of one technical value."""
    from ui.tabs.media.technical_controls import _clamp_numeric, _coerce_value
    prop, defn = entry
    value = _coerce_value(candidate, defn, previous)
    return _clamp_numeric(value, defn) if prop.instrument == SCALAR else value


RAINBOW_GROUP = "Rainbow"


def rainbow_properties(mode_id: str, *, workspace: str, group: str = RAINBOW_GROUP,
                       subject: str = "the visualiser's colours") -> dict[str, StudioProperty]:
    """The mode's shared rainbow family (Settings' Rainbow bucket: Taste the Rainbow and its Speed), stored per mode;
    empty for a mode without the family. storage key -> Studio property."""
    from core.settings.visualizer_mode_registry import get_owned_mode_setting_keys
    keys = get_owned_mode_setting_keys(mode_id, "rainbow")
    if not keys:
        return {}
    enabled, speed = keys["rainbow_enabled"], keys["rainbow_speed"]
    return {
        enabled: StudioProperty(id=enabled, path=(enabled,), label="Taste the Rainbow", workspace=workspace,
                                group=group, instrument=SWITCH, icon="gradient",
                                tooltip=f"Slowly shift the hue of {subject} through the spectrum. Saved per "
                                        "visualizer mode."),
        # Settings' Speed slider: 1..100 (hundredths).
        speed: StudioProperty(id=speed, path=(speed,), label="Rainbow Speed", workspace=workspace, group=group,
                              instrument=SCALAR, minimum=0.01, maximum=1.0, decimals=2, when=((enabled, (True,)),),
                              tooltip="How fast the hue cycles through the spectrum."),
    }


def admit_rainbow(props: dict[str, StudioProperty], key: str, candidate: Any, previous: Any) -> Any:
    """Settings' own admission of the rainbow family: the toggle is a bool, the speed its 1..100 slider in
    hundredths."""
    prop = props[key]
    if prop.instrument == SWITCH:
        return bool(candidate)
    try:
        value = float(candidate)
    except (TypeError, ValueError):
        return previous
    if value != value:
        return previous
    return round(max(0.01, min(1.0, value)), 2)


__all__ = ["RAINBOW_GROUP", "TECHNICAL_GROUP", "admit_rainbow", "admit_technical", "rainbow_properties",
           "technical_properties"]
