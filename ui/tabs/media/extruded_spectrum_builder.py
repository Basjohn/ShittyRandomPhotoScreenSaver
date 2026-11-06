"""Extruded Spectrum's Settings body: the preset row and the Extruded Spectrum Studio launcher.

Every Extruded Spectrum control (including its audio analysis) is edited in the Studio, which has parity+ with the retired
buckets (``tests/test_visualizer_studio_parity.py`` proves it from the registries)."""
from ui.tabs.media.spec_mode_builder import build_studio_owned_mode_ui

INTRO = "The bars, their shape, finish and reactivity are all edited live in the Studio."


def build_extruded_spectrum_ui(tab, parent_layout) -> None:
    build_studio_owned_mode_ui(tab, parent_layout, "extruded_spectrum", INTRO)
