"""A mode's technical (audio analysis) controls as Studio properties (mode-neutral).

Settings builds these in its per-mode Technical group (``ui.tabs.media.technical_controls``); the Studio shows the
same controls with the same storage keys, ranges, choices and labels, and admits edits with the same coercion and
clamping. Adapters call these instead of carrying their own copies.
"""
from __future__ import annotations

from typing import Any

from ui.studio.schema import CHOICE, SCALAR, SWITCH, StudioProperty

TECHNICAL_GROUP = "Audio Analysis"
_NOTE = ("Live audio analysis for this mode (Settings' Technical controls). The synthetic previews bypass "
         "analysis; recorded clips are re-analysed with these values.")


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


__all__ = ["TECHNICAL_GROUP", "admit_technical", "technical_properties"]
