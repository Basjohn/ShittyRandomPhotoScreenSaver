"""Curated Visualizer presets a stored reference may name (1C.1; Persisted_Input_Compatibility.md).

A profile stores its preset as a slot index plus the preset's identity (its authored name without the slot
number, ``visualizer_preset_indices.preset_identity``). Renumbering a curated preset needs nothing here: the
resolver follows the name. Removing one, or renaming it, does:

* ``SHIPPED_CURATED_PRESETS``: every curated identity a profile may hold, per mode. A new curated preset is added
  here when it ships.
* ``RETIRED_CURATED_PRESETS``: an identity no longer in the tree, and what a stored reference to it opens instead:
  another identity (a rename or a stated successor) or ``None`` (the mode's Preset 1).

``tests/test_visualizer_preset_compat.py`` fails when the preset tree and these two disagree, so removing,
renaming or adding a curated preset without its line here is caught before it ships. Plain data; authored
preset content (values, looks) never enters this file.
"""
from __future__ import annotations

SHIPPED_CURATED_PRESETS: dict[str, tuple[str, ...]] = {
    "spectrum": ("Organs", "Aurora", "Lanterns", "Dot Matrix", "Prism", "Dusk", "Voltage", "Mood Ring"),
    "oscilloscope": ("Phosphor", "Neon Halo", "Lissajous", "Amber Terminal", "Cobalt Terminal"),
    "bubble": ("Deep Sea Abyss", "Going Down", "Orange Soda", "Sideway Swish", "Champagne Piss", "Lava Flow",
               "Abyss", "Deep Sea"),
    "devcurve": ("Deep Blue", "Rainbow Rapids", "Sunset Hills", "Glacier Layers", "Forest Canopy", "Neon Skyline",
                 "Desert Strata", "Ink Wash", "Coral Reef", "Midnight Silk", "Candy Stripes", "Ember Ridge"),
    "sphere": ("Mirror Ball", "Voxel Bloom", "Rainbow Intake", "Rainbow Exhaust", "Glass Current"),
    "extruded_spectrum": ("Silver Shine", "Studio", "Glass Floor", "Chrome Organ"),
    "shockwave_grid": ("Synthwave", "Synthwave Smooth", "Synthwave Dawn"),
    "extruded_bubble": ("Night Water", "Deep Water", "Sunlit Surface", "Soft Rays", "Abyss", "Looking Down",
                        "Ember Drift", "Indie Gogo", "Deep Red Ocean"),
    "waveform_ribbon": ("Complete Scene", "Silk Bands", "Teal And Ember", "Violet Ice", "Deep Sea Gold",
                        "Sunset Swell", "Neon Tide"),
}

RETIRED_CURATED_PRESETS: dict[str, dict[str, str | None]] = {
    # Spectrum round 2 (1B.10, 11 Nov 2026): the five rejected presets of round 1. No stored reference can name
    # them yet (references are written from 12 Nov), recorded so the rule has its first entries.
    "spectrum": {"Tube Lights": None, "Quicksilver": None, "Blueprint": None, "Afterglow": None, "Frost": None},
}


def retired_successor(mode: str, identity: str) -> tuple[bool, str | None]:
    """(listed, successor identity or None for Preset 1) for a stored identity no longer in ``mode``'s tree."""
    entries = RETIRED_CURATED_PRESETS.get(mode, {})
    if identity not in entries:
        return False, None
    return True, entries[identity]


__all__ = ["RETIRED_CURATED_PRESETS", "SHIPPED_CURATED_PRESETS", "retired_successor"]
