"""Lazy Settings body for the Oscilloscope visualizer, built from its spec
(``core/settings/visualizer_mode_settings.py``)."""
from __future__ import annotations

from ui.tabs.media.spec_mode_builder import build_spec_mode_ui


def build_oscilloscope_ui(tab, parent_layout) -> None:
    """Build Oscilloscope's body and its consumed technical profile."""

    build_spec_mode_ui(tab, parent_layout, "oscilloscope")
