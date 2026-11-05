"""Explicit hybrid replay: recompute production body-band DSP from recorded PCM tails.

Ordinary replay serves each frame's recorded post-DSP bands, so a mode's technical
settings (Dynamic Floor, manual floor, Sensitivity) cannot change them. Inside
``reanalyzed_bubble_bands()`` every accepted frame instead feeds its native PCM
tail through ``compute_bars_from_samples`` with the replay worker's *configured*
compute state, and Bubble/EB read bands through the production getter. For Bubble/EB recorded
onsets, loudness and sampled cadence remain unchanged: a controlled hybrid, not a
live run. EB derives its passage inside its runtime from that recomputed body tuple;
its passage never reads the retained historical loudness scalar. Other modes keep
their existing recorded lane ownership. Waveform also reads musical level, passage and typed
onsets from the same reanalysed production bus, with current-source/config fencing. Auto's negotiated block and skipped native
callbacks are not recoverable.
"""
from __future__ import annotations

from contextlib import ExitStack, contextmanager
from unittest.mock import patch

from widgets.spotify_visualizer.beat_engine import _SpotifyBeatEngine
from widgets.spotify_visualizer.feature_replay import PcmReanalysis, ReplayBeatEngine  # noqa: F401  (tool names)


@contextmanager
def reanalyzed_bubble_bands():
    """Patch replay so body bands come from reanalysed PCM; yields the reanalysis."""
    reanalysis = PcmReanalysis()
    original_accept = ReplayBeatEngine.accept_feature_frame

    def accept(engine, feature):
        result = original_accept(engine, feature)
        reanalysis.accept(engine, feature)
        return result

    with ExitStack() as stack:
        stack.enter_context(patch.object(ReplayBeatEngine, "accept_feature_frame", accept))
        for getter in ("get_bubble_energy_bands", "get_extruded_bubble_body_bands"):
            # Older revisions (compared from a worktree) may lack EB's own feed.
            if hasattr(_SpotifyBeatEngine, getter):
                stack.enter_context(patch.object(ReplayBeatEngine, getter, getattr(_SpotifyBeatEngine, getter)))
        yield reanalysis
