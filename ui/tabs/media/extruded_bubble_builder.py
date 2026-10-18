"""Lazy Settings body for Extruded Bubble, built from its spec (``core/settings/visualizer_mode_settings.py``)."""
from __future__ import annotations

from ui.tabs.media.spec_mode_builder import build_spec_mode_ui


def build_extruded_bubble_ui(tab, parent_layout) -> None:
    """Build Extruded Bubble's body (its buckets, visual controls and technical profile)."""

    build_spec_mode_ui(tab, parent_layout, "extruded_bubble")
