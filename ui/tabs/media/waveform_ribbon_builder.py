"""Lazy Waveform Settings body on the shared canonical spec/preset scaffold."""
from ui.tabs.media.spec_mode_builder import build_spec_mode_ui


def build_waveform_ribbon_ui(tab,parent_layout):
    build_spec_mode_ui(tab,parent_layout,'waveform_ribbon')
