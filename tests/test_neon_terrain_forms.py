"""Neon Lake's Growth and Indents (1B.6): the music's drive of the landforms it holds up or presses in.

Both drives live in the one terrain reaction owner on the capture clock (``ShockwaveGridFrameRuntime``) and read the
music on the fixed real-music scale only: the passage's intensity and each onset's emphasis. Nothing is learned from
the track, no presence ratio (``musical_weight``) gates them, everything ramps, and off they do no work.
"""
from __future__ import annotations

import math
from dataclasses import replace
from types import SimpleNamespace

import pytest

from widgets.spotify_visualizer.render_state import ShockwaveGridFrame
from widgets.spotify_visualizer.shockwave_frame_runtime import (
    FORMS_CEILING, FORMS_HIT_ATTACK, FORMS_HIT_SHARE, FORMS_PASSAGE, ShockwaveGridFrameRuntime, forms_hit, forms_level,
)
from widgets.spotify_visualizer.transient_bus import MUSICAL_USUAL_LOUDNESS

STEP = 1.0 / 60.0


def _onset(serial: int, when: float, loudness: float):
    return SimpleNamespace(serial=serial, timestamp=when, loudness=loudness, magnitude=1.0, presence=1.0,
                           kind="kick")


class _Song:
    """A runtime stepped at 60 Hz through a passage: intensity over time and onsets (time, loudness)."""

    def __init__(self, *, attack=0.35, release=1.2, forms=True):
        self.runtime = ShockwaveGridFrameRuntime()
        self.now = 100.0
        self.serial = 0
        self.attack, self.release, self.forms = attack, release, forms
        self.trace: list[tuple[float, float]] = []

    def play(self, seconds: float, intensity: float, kicks=(), *, loudness=MUSICAL_USUAL_LOUDNESS, playing=True,
             step=STEP):
        """``kicks``: times from the start of this stretch."""
        start, pending = self.now, sorted(kicks)
        while self.now - start < seconds - 1e-9:
            self.now += step
            onsets = []
            while pending and start + pending[0] <= self.now:
                self.serial += 1
                onsets.append(_onset(self.serial, start + pending.pop(0), loudness))
            self.runtime.record_onsets(onsets=onsets, now_ts=self.now, playing=playing, passage_intensity=intensity)
            resolved = self.runtime.advance_terrain_reaction(
                (), now_ts=self.now, playing=playing, identity=(1, 2, 3), source_identity=(2, 3),
                attack=self.attack, release=self.release, motion_speed=0.5, enabled=True, musical_gain=0.0,
                forms=self.forms, passage_intensity=intensity)
            self.trace.append(resolved.forms)
        return self.trace[-1]


def test_the_level_is_a_fixed_curve_of_the_passage_with_headroom():
    low, high = FORMS_PASSAGE
    assert forms_level(0.0) == forms_level(low) == 0.0                 # quiet passages hold nothing up
    levels = [forms_level(low + (high - low) * k / 20.0) for k in range(21)]
    assert levels == sorted(levels) and levels[-1] == pytest.approx(FORMS_CEILING) and forms_level(1.0) == levels[-1]
    assert FORMS_CEILING < 1.0                                         # the loudest passage does not pin
    assert 0.3 < forms_level(0.65) < 0.8                               # a usual passage: clearly up, not full
    # A hit is read on the fixed loudness scale: silence nothing, a usual onset about half, a loud one more, bounded.
    assert forms_hit(0.0) == 0.0
    usual, loud = forms_hit(MUSICAL_USUAL_LOUDNESS), forms_hit(2.0 * MUSICAL_USUAL_LOUDNESS)
    assert 0.3 < usual < 0.7 and usual < loud <= 1.0 and forms_hit(100.0) == loud == 1.0
    assert forms_hit(0.5 * MUSICAL_USUAL_LOUDNESS) < usual


def test_the_drives_start_at_rest_ramp_in_and_fade_out():
    song = _Song()
    assert song.runtime.advance_terrain_reaction(
        (), now_ts=song.now, playing=True, identity=(1, 2, 3), source_identity=(2, 3), attack=0.35, release=1.2,
        motion_speed=0.5, enabled=True, musical_gain=0.0, forms=True, passage_intensity=1.0).forms == (0.0, 0.0)
    song.play(3.0, 1.0)
    rise = [growth for growth, _indent in song.trace]
    assert rise == sorted(rise) and 0.0 < rise[5] < 0.2 < rise[-1]            # it ramps: nothing pops in
    assert max(b - a for a, b in zip(rise, rise[1:])) < 0.03                   # per 60 Hz frame
    settled = song.play(4.0, 1.0)
    assert settled[0] == pytest.approx(FORMS_CEILING * (1.0 - FORMS_HIT_SHARE[0]), abs=0.01) and settled[0] < 1.0
    start = len(song.trace)
    song.play(8.0, 1.0, playing=False)                                         # the music stops: it lets go
    fall = [growth for growth, _indent in song.trace[start:]]
    assert fall == sorted(fall, reverse=True) and fall[-1] < 0.01
    assert max(a - b for a, b in zip(fall, fall[1:])) < 0.03
    song.play(6.0, 0.0)
    assert song.trace[-1] == (0.0, 0.0) and not song.runtime.terrain_reaction_pending


def test_a_hit_lifts_the_drives_over_a_few_frames_and_lets_go():
    song = _Song()
    song.play(6.0, 0.8)
    rest = song.trace[-1]
    start = len(song.trace)
    song.play(1.5, 0.8, kicks=[0.1])
    growth = [g for g, _i in song.trace[start:]]
    indent = [i for _g, i in song.trace[start:]]
    peak = max(range(len(growth)), key=growth.__getitem__)
    assert growth[peak] > rest[0] * 1.08 and indent[peak] > rest[1] * 1.2      # Indents answer hits more
    assert indent[peak] / rest[1] > growth[peak] / rest[0]
    assert max(b - a for a, b in zip(growth, growth[1:])) < 0.06               # the hit ramps in (no one-frame jump)
    assert 3 <= peak - round(0.1 / STEP) <= round(6 * FORMS_HIT_ATTACK / STEP)
    assert growth[-1] == pytest.approx(rest[0], abs=0.01) and max(growth) < 1.0  # and lets go; never pinned
    # A louder kick hits harder; a kick in silence does nothing.
    loud = _Song()
    loud.play(6.0, 0.8)
    loud.play(1.5, 0.8, kicks=[0.1], loudness=2.0 * MUSICAL_USUAL_LOUDNESS)
    assert max(g for g, _i in loud.trace) > max(growth)
    silent = _Song()
    silent.play(1.0, 0.0, kicks=[0.1, 0.4], loudness=0.01)
    assert max(g for g, _i in silent.trace) == 0.0


def test_the_same_music_draws_the_same_landforms_wherever_in_a_song_it_falls():
    """No learned level: a chorus after a minute of loud music, after silence, or at the very start settles on the
    same drives, and a mid-song kick reads exactly as an opening one (the lane drives' recent-level follower and
    ``musical_weight``'s presence ratio are not on this path)."""
    kicks = [0.25 * k for k in range(1, 12)]

    def chorus(prelude):
        song = _Song()
        for seconds, intensity, loudness in prelude:
            song.play(seconds, intensity, kicks=[0.5 * k for k in range(int(seconds * 2))], loudness=loudness)
        song.play(14.0, 0.85)                                                  # the followers settle into the chorus
        start = len(song.trace)
        song.play(3.0, 0.85, kicks=kicks)
        growth = [g for g, _i in song.trace[start:]]
        indent = [i for _g, i in song.trace[start:]]
        # The kicks' swing and the passage's level (a kick lands a frame earlier or later with the clock's phase,
        # so the traces are compared by what they show, not frame for frame).
        return (min(growth), max(growth), sum(growth) / len(growth), min(indent), max(indent))

    opening = chorus([])
    after_loud = chorus([(60.0, 1.0, 2.0 * MUSICAL_USUAL_LOUDNESS)])
    after_quiet = chorus([(30.0, 0.1, 0.5), (5.0, 0.0, 0.0)])
    assert after_loud == pytest.approx(opening, abs=0.004) and after_quiet == pytest.approx(opening, abs=0.004)
    assert opening[1] - opening[0] > 0.08                                      # the kicks read


def test_the_drives_do_not_depend_on_how_the_capture_clock_is_cut():
    fine, coarse = _Song(), _Song()
    fine.play(4.0, 0.9, kicks=[1.0, 2.0], step=1.0 / 120.0)
    coarse.play(4.0, 0.9, kicks=[1.0, 2.0], step=1.0 / 30.0)
    fine.play(1.0, 0.9, step=1.0 / 120.0)
    coarse.play(1.0, 0.9, step=1.0 / 30.0)
    assert fine.trace[-1] == pytest.approx(coarse.trace[-1], abs=0.01)


def test_off_the_landforms_keep_nothing_and_collect_no_onsets():
    song = _Song(forms=False)
    song.play(3.0, 1.0, kicks=[0.5, 1.0, 1.5])
    assert set(song.trace) == {(0.0, 0.0)}
    runtime = song.runtime
    assert (runtime._forms_onset, runtime._forms_level, runtime._forms_hit, runtime._forms_on) == (0.0, 0.0, 0.0, False)
    # On, then off again: back to rest at once, nothing pending on their account.
    song.forms = True
    song.play(3.0, 1.0, kicks=[0.5])
    assert song.trace[-1][0] > 0.3
    song.forms = False
    assert song.play(STEP, 1.0) == (0.0, 0.0) and not runtime.terrain_reaction_pending


def _capture(parameters, monkeypatch, intensity=1.0):
    from tests.test_neon_terrain_reaction import _capture_rig
    rig = _capture_rig(parameters, {"get_musical_intensity": lambda: intensity})
    capture = rig[0]
    monkeypatch.setattr(capture.config_applier, "shockwave_grid_parameters", lambda owner, now: parameters)
    monkeypatch.setattr(capture, "_base_extras", lambda *args: {})
    return rig


def test_the_capture_feeds_the_drives_from_the_passage_alone(monkeypatch):
    """With only Growth / Indents on, the capture reads no loudness level, no presence and no spectrum: the drives
    come from the passage intensity it already had and the onsets."""
    from tests.test_neon_terrain_reaction import _reaction_parameters
    parameters = _reaction_parameters(shockwave_grid_terrain_peaks=0.0, shockwave_grid_terrain_pulses=0.0,
                                      shockwave_grid_terrain_swell=0.0, shockwave_grid_terrain_growth=0.8)
    capture, widget, engine, context, runtime, reads, _spectrum, _controller = _capture(parameters, monkeypatch)
    engine.get_musical_level = lambda: pytest.fail("Growth must not read the loudness / presence level")
    engine.get_pre_agc_analysis_spectrum = lambda: pytest.fail("Growth must not read the spectrum")
    frame, _extra = capture._capture_shockwave_grid(widget, engine, context(10.0))
    assert frame.terrain_forms == (0.0, 0.0)
    for k in range(1, 121):
        frame, extra = capture._capture_shockwave_grid(widget, engine, context(10.0 + k * STEP))
    assert frame.terrain_forms[0] > 0.3 and frame.terrain_bands == (0.0,) * 5
    assert runtime.terrain_reaction_pending or frame.terrain_forms[0] == pytest.approx(FORMS_CEILING * (1.0 - FORMS_HIT_SHARE[0]), abs=0.02)
    # The frame admits exactly two drives within 0..1.
    assert isinstance(frame, ShockwaveGridFrame)
    for broken in ((0.1,), (0.1, 1.2), (-0.1, 0.0), (0.1, math.nan)):
        with pytest.raises(ValueError):
            replace(frame, terrain_forms=broken)
    # Amounts at zero (or the reaction off): no drive, nothing kept.
    on = dict(parameters)
    for change in ({"shockwave_grid_terrain_growth": 0.0}, {"shockwave_grid_terrain_reaction_enabled": False},
                   {"shockwave_grid_terrain_reaction_strength": 0.0}):
        parameters.update({**on, **change})
        off, _extra = capture._capture_shockwave_grid(widget, engine, context(20.0))
        assert off.terrain_forms == (0.0, 0.0) and not runtime._forms_on
