"""Spectrum's paused idle must reveal on cold activation, not only via a pause edge.

Spectrum's idle scene is presentation-owned (`mode_capabilities`), so the tick side
publishes it while deliberately keeping the fresh-source fence armed for later
reactive authority. The owner's `waiting_target` transition gate must honor the same
capability: a paused presentation-owned-idle target may advance to the reveal
without waiting for a fresh ENGINE frame (which only arrives on playback), otherwise
switching to Spectrum with playback idle strands the transition forever.
"""

from __future__ import annotations

from types import SimpleNamespace

from core.settings.visualizer_mode_registry import VISUALIZER_MODE_IDS
from widgets.spotify_visualizer import mode_capabilities
from widgets.spotify_visualizer.quick_display_visualizer_owner import (
    QuickDisplayVisualizerOwner,
)


def _gate(mode: str, *, playing: bool) -> bool:
    # Bypass the heavy __init__; the gate reads only controller.playing / mode_id.
    owner = QuickDisplayVisualizerOwner.__new__(QuickDisplayVisualizerOwner)
    owner._controller = SimpleNamespace(playing=playing, mode_id=mode)
    return owner._target_reveals_paused_idle_without_engine_frame()


def test_paused_spectrum_reveals_without_engine_frame():
    assert _gate("spectrum", playing=False) is True


def test_playing_spectrum_still_waits_for_fresh_source():
    assert _gate("spectrum", playing=True) is False


def test_paused_idle_self_animating_modes_are_unaffected():
    # Self-animating modes clear their own fence via engine idle ticks; the exception is not theirs.
    self_animating = tuple(
        mode for mode in VISUALIZER_MODE_IDS if mode_capabilities.is_idle_self_animating(mode)
    )
    assert self_animating
    for mode in self_animating:
        assert _gate(mode, playing=False) is False


def test_capability_table_matches_the_gate_premise():
    # Only Spectrum is presentation-owned-idle; guards against a silent reclassify.
    assert mode_capabilities.has_presentation_owned_idle_scene("spectrum") is True
    assert mode_capabilities.is_idle_self_animating("spectrum") is False
    for mode in VISUALIZER_MODE_IDS:
        if mode != "spectrum":
            assert mode_capabilities.has_presentation_owned_idle_scene(mode) is False
