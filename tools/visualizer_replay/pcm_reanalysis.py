"""Explicit hybrid replay: recompute production body-band DSP from recorded PCM tails.

Ordinary replay serves each frame's recorded post-DSP bands, so a mode's technical
settings (Dynamic Floor, manual floor, Sensitivity) cannot change them. Inside
``reanalyzed_bubble_bands()`` every accepted frame instead feeds its native PCM
tail through ``compute_bars_from_samples`` with the replay worker's *configured*
compute state, and Bubble/EB read bands through the production getter. Recorded
onsets, loudness and sampled cadence remain unchanged: a controlled hybrid, not a
live run. EB derives its passage inside its runtime from that recomputed body tuple;
its passage never reads the retained historical loudness scalar. Other modes keep
their existing recorded lane ownership. Auto's negotiated block and skipped native
callbacks are not recoverable.
"""
from __future__ import annotations

from contextlib import ExitStack, contextmanager
from unittest.mock import patch

import numpy as np

from tools.visualizer_replay.engine import ReplayBeatEngine
from widgets.spotify_visualizer.beat_engine import _SpotifyBeatEngine


class PcmReanalysis:
    """One replay's DSP state; feed every accepted frame once per capture serial."""

    def __init__(self) -> None:
        self.state = None
        self.serial = None
        self.frames = 0

    def accept(self, engine, feature) -> None:
        from widgets.spotify_visualizer.bar_computation import compute_bars_from_samples

        history = feature.capture_history
        if history is None:
            raise ValueError("PCM reanalysis requires native capture history on every frame")
        if self.serial == history.capture_serial:
            return
        worker = engine._audio_worker
        if self.state is None:
            # Taken after the replay applied the mode's technical config, so the
            # configured floor/sensitivity drive the recomputed bands.
            self.state = worker.make_compute_snapshot()
            self.state._np = np
        block = int(worker._preferred_block_size or 0) or history.sample_rate // 100
        samples = np.frombuffer(history.pcm_f32le, dtype="<f4")[-block:]
        if compute_bars_from_samples(self.state, samples) is None:
            raise RuntimeError("production PCM analysis failed")
        worker.commit_compute_snapshot(self.state)
        self.serial = history.capture_serial
        self.frames += 1


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
