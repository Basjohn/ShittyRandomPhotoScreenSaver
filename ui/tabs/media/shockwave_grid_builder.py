"""Neon Lake's Settings body: the preset row and the Studio launcher.

Every Neon Lake control is edited in the Studio (parity+: ``tests/test_visualizer_studio_parity.py``), the authored
terrain included: the Studio's shared brush instrument paints it on the live preview (``ui/studio/brush.py``)."""
from __future__ import annotations

from ui.tabs.media.spec_mode_builder import build_studio_owned_mode_ui

INTRO = "Shape the terrain, water, sky, light, camera and reactivity live in the Studio."


def build_shockwave_grid_ui(tab, parent_layout) -> None:
    build_studio_owned_mode_ui(tab, parent_layout, "shockwave_grid", INTRO)
