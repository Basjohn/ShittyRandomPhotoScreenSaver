"""Immutable fixture input at the real BeatEngine post-DSP seam.

The replay engine is production-owned (``widgets.spotify_visualizer.feature_replay``) so the Studio's
recorded fixtures can use it without importing tools; this module keeps the tools' names."""
from __future__ import annotations

from widgets.spotify_visualizer.feature_replay import (  # noqa: F401  (re-exported tool names)
    PRODUCTION_WAVEFORM_BLOCK, SCHEMA_1_MUSIC, ReplayBeatEngine, _bands, _waveform_block, logger,
)
