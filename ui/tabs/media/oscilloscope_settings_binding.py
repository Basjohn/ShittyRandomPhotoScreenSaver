"""Persistence binding for the lazy Oscilloscope Settings body (its spec's controls)."""
from __future__ import annotations

from ui.tabs.media.spec_mode_builder import collect_spec_mode_settings, load_spec_mode_settings


def load_oscilloscope_mode_settings(tab, config) -> None:
    load_spec_mode_settings(tab, "oscilloscope", config)


def collect_oscilloscope_mode_settings(tab) -> dict:
    return collect_spec_mode_settings(tab, "oscilloscope")
