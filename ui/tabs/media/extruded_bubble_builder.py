"""Extruded Bubble's Settings body: the preset row and the Extruded Bubble Studio launcher.

Every Extruded Bubble control (including its audio analysis) is edited in the Studio, which has parity+ with the retired
buckets (``tests/test_visualizer_studio_parity.py`` proves it from the registries)."""
from ui.tabs.media.spec_mode_builder import build_studio_owned_mode_ui

INTRO = "The light, the bubbles, the water and the camera are all edited live in the Studio."


def build_extruded_bubble_ui(tab, parent_layout) -> None:
    build_studio_owned_mode_ui(tab, parent_layout, "extruded_bubble", INTRO)
