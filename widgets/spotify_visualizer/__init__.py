"""Spotify Visualizer Widget Package.

This package contains the refactored Spotify visualizer components:
- audio_worker: Audio capture and FFT processing
- beat_engine: Shared beat engine with smoothing

Note: SpotifyVisualizerWidget is still at widgets/spotify_visualizer_widget.py
and has not been moved into this package yet.

Usage:
    from widgets.spotify_visualizer import get_shared_spotify_beat_engine
"""

from widgets.spotify_visualizer.beat_engine import (
    get_shared_spotify_beat_engine,
    _SpotifyBeatEngine,
)
from widgets.spotify_visualizer.audio_worker import (
    SpotifyVisualizerAudioWorker,
    VisualizerMode,
)

__all__ = [
    "get_shared_spotify_beat_engine",
    "_SpotifyBeatEngine",
    "SpotifyVisualizerAudioWorker",
    "VisualizerMode",
]
