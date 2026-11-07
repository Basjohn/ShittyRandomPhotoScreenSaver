"""A mode's technical (audio analysis) controls as Studio properties (mode-neutral).

The controls are the mode spec's offered ``technical`` entries (``ModeSettings.technical_controls``,
``core/settings/visualizer_mode_settings.py``); the Settings mode body holds their values in its value cache (no
widget). The Studio shows them with the same storage keys, ranges, choices and labels, and admits edits with the
control's own ``admit``, as Settings and the model do. Adapters call these instead of carrying their own copies.
"""
from __future__ import annotations

from typing import Any

from ui.studio.schema import CHOICE, SCALAR, SWITCH, StudioProperty

TECHNICAL_GROUP = "Audio Analysis"
_NOTE = ("Live audio analysis for this mode (Settings' Technical controls). The synthetic previews bypass "
         "analysis; recorded clips are re-analysed with these values.")


def _offered(mode_id: str):
    from core.settings.visualizer_mode_settings import require_mode_settings
    return require_mode_settings(mode_id).technical_controls()


def technical_keys(mode_id: str) -> frozenset[str]:
    """The storage keys of the mode's offered technical (Audio Analysis) controls."""
    return frozenset(control.key for control in _offered(mode_id))


def clip_analysis_key(clip, mode_id: str, values) -> str:
    """A recorded clip's analysis cache key: the clip and the mode's Audio Analysis values it was analysed under."""
    import json
    keys = sorted(technical_keys(mode_id))
    return clip.description + "|" + json.dumps({key: values.get(key) for key in keys}, sort_keys=True, default=repr)


def technical_properties(mode_id: str, *, workspace: str, group: str = TECHNICAL_GROUP,
                         note: str = _NOTE) -> dict[str, tuple[StudioProperty, Any]]:
    """storage key -> (Studio property, the spec control), in Settings' order."""
    from core.settings.visualizer_mode_settings import Choice, Toggle
    out = {}
    for control in _offered(mode_id):
        key = control.key
        text = control.text if isinstance(control, Toggle) else ""
        label = (control.label or text or key).replace("\n", " ").rstrip(":").strip()
        tooltip = (control.tooltip or "") + ("\n" if control.tooltip else "") + note
        common = dict(id=key, path=(key,), label=label, workspace=workspace, group=group, tooltip=tooltip)
        if isinstance(control, Toggle):
            prop = StudioProperty(instrument=SWITCH, **common)
        elif isinstance(control, Choice):
            prop = StudioProperty(instrument=CHOICE, choices=tuple(control.labels or control.choices),
                                  choice_values=tuple(control.choices), **common)
        else:
            prop = StudioProperty(instrument=SCALAR, minimum=float(control.low), maximum=float(control.high),
                                  decimals=0 if control.integer else 2, integer=control.integer,
                                  units=control.suffix if not control.percent else "", **common)
        out[key] = (prop, control)
    return out


def admit_technical(entry: tuple[StudioProperty, Any], candidate: Any, previous: Any) -> Any:
    """The spec control's own admission of one technical value (Settings' and the model's)."""
    _prop, control = entry
    return control.admit(candidate, previous)


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
