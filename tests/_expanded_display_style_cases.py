"""Test-owned inputs for the expanded card's display styles (Current_Plan 1D.2) and the Default style's geometry
baseline.

``tests/fixtures/expanded_default_style_geometry.json`` holds every field of the display-wide record that
``resolve_expanded_visualizer_presentation`` returned for each case below BEFORE display styles existed (recorded
12 Nov 2026 from the pre-1D.2 resolver). Default must reproduce it exactly: the same record, so the same pixels.
Every input here is test-owned chrome and geometry; nothing reads Settings or authored presets.
"""
from __future__ import annotations

import enum
import json
from dataclasses import fields
from pathlib import Path
from typing import Any

BASELINE_PATH = Path(__file__).resolve().parent / "fixtures" / "expanded_default_style_geometry.json"

#: (logical display size, DPR): the development machine's two displays, 100 %, 125 %, a 1366 x 768 at 125 % (neither
#: axis whole logical), portrait, a tiny display (the quarter cap binds).
DISPLAYS = {
    "1920x1080_100": ((1920.0, 1080.0), 1.0),
    "2560x1440_150": ((2560.0 / 1.5, 1440.0 / 1.5), 1.5),
    "3840x2160_150": ((2560.0, 1440.0), 1.5),
    "1920x1080_125": ((1536.0, 864.0), 1.25),
    "1366x768_125": ((1366.0 / 1.25, 768.0 / 1.25), 1.25),
    "portrait_100": ((1080.0, 1920.0), 1.0),
    "tiny": ((20.0, 24.0), 1.0),
}
#: Card chrome variants: a shadow falling south-east with Extra Offset, north-west, none, and no border.
_CHROME = {"border_width": 3.0, "corner_radius": 8.0, "background_color": (20, 22, 26, 200),
           "border_color": (230, 234, 240, 255), "shadow_enabled": True, "shadow_color": (0, 0, 0, 150),
           "shadow_blur": 18.0, "shadow_offset": (0.0, 4.0), "shadow_extensions": (2.0, 2.0, 2.0, 6.0)}
CHROMES = {
    "shadow_se": _CHROME,
    "shadow_nw": {**_CHROME, "shadow_offset": (-5.0, -3.0), "shadow_extensions": (4.0, 4.0, 0.0, 0.0)},
    "no_shadow": {**_CHROME, "border_width": 5.0, "shadow_enabled": False},
    "bare": {**_CHROME, "border_width": 0.0, "shadow_enabled": False},
}
#: Ordinary records: canonical, edge-resized wide and tall CUSTOM worlds, a scaled card, a quarter-turned card.
CARDS = {
    "canonical": {"outer_origin": (32.0, 400.0)},
    "custom_wide": {"outer_origin": (96.0, 180.0), "viewport_extent": (840.0, 280.0)},
    "custom_tall": {"outer_origin": (40.0, 40.0), "viewport_extent": (300.0, 520.0)},
    "scaled": {"outer_origin": (10.0, 10.0), "uniform_visual_scale": 1.6},
    "quarter_turn": {"outer_origin": (12.3, 45.6), "viewport_extent": (630.0, 280.0), "content_rotation_quarters": 1},
}
#: A carded 2D mode, a framed 3D mode and a frameless mode (the resolver is pure: every shell is covered).
MODES = ("devcurve", "extruded_bubble", "sphere")


def ordinary(mode: str, card: str, chrome: str, display: str):
    from core.settings.visualizer_mode_registry import get_visualizer_presentation_policy
    from tests._visualizer_presentation import resolve_presentation

    size, dpr = DISPLAYS[display]
    card_kwargs = dict(CARDS[card])
    if card == "scaled" and display == "tiny":
        card_kwargs.pop("uniform_visual_scale")
    return resolve_presentation(policy=get_visualizer_presentation_policy(mode), display_size=size, dpr=dpr,
                                **CHROMES[chrome], **card_kwargs)


def cases():
    """(label, ordinary record, display size, DPR handed to the resolver or None for the owner's call shape)."""
    for mode in MODES:
        for card in CARDS:
            for chrome in CHROMES:
                for display, (size, dpr) in DISPLAYS.items():
                    record = ordinary(mode, card, chrome, display)
                    # The owner's steady route passes no DPR (the ordinary record's); the display move passes one.
                    yield f"{mode}|{card}|{chrome}|{display}", record, size, (dpr if card != "canonical" else None)


def _plain(value: Any) -> Any:
    if isinstance(value, enum.Enum):
        return value.value
    if isinstance(value, float):
        return value.hex()
    if isinstance(value, (tuple, list)):
        return [_plain(item) for item in value]
    if hasattr(value, "items"):
        return {str(key): _plain(item) for key, item in sorted(value.items())}
    return value


def record_fields(record) -> dict[str, Any]:
    """Every field of a resolved record, floats as exact hex strings (bit for bit)."""
    return {field.name: _plain(getattr(record, field.name)) for field in fields(record)}


def load_baseline() -> dict[str, dict[str, Any]]:
    return json.loads(BASELINE_PATH.read_text(encoding="utf-8"))


def write_baseline(path: Path = BASELINE_PATH) -> int:
    """Record today's Default records (run once, before the resolver changed)."""
    from widgets.spotify_visualizer.presentation_geometry import resolve_expanded_visualizer_presentation

    table = {}
    for label, record, size, dpr in cases():
        table[label] = record_fields(resolve_expanded_visualizer_presentation(record, display_size=size, dpr=dpr))
    rows = [f" {json.dumps(label)}: {json.dumps(table[label], sort_keys=True, separators=(',', ':'))}"
            for label in sorted(table)]
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write("{\n" + ",\n".join(rows) + "\n}\n")
    return len(table)
