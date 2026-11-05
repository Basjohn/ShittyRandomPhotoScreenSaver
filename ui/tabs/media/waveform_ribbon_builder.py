"""Waveform's Settings body: the preset row and the Waveform Studio launcher.

Every Waveform control (including its audio analysis) is edited in the Studio, which has full parity
with the retired buckets (tests/test_waveform_studio_parity.py proves it from the registries)."""
from ui.tabs.media.spec_mode_builder import build_studio_owned_mode_ui

INTRO = "Shape, colour, reactivity and the world of the Waveform are all edited live in the Studio."


def build_waveform_ribbon_ui(tab, parent_layout):
    build_studio_owned_mode_ui(tab, parent_layout, 'waveform_ribbon', INTRO)
