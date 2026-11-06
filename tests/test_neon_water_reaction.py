"""Neon Lake's Water Reaction: the lake answers the music read from the admitted waves (fixed real-music scale).

Pass 7 finding (``tools/visualizer_replay/neon_lake_music_response.py``): every continuous lake term read the display
bars, which sit at ~1 through all ordinary music, so a loud passage looked like a usual one. The waves' strengths
already carry the fixed loudness scale; these contracts use test-owned events, never preset values."""
from dataclasses import replace

import numpy as np

from rendering.gl_programs.shockwave_grid_program import (
    WATER_REACT_ACCENT, WATER_REACT_WINDOW, shockwave_music_drive, shockwave_ridge_breath, shockwave_water_reaction,
)
from tests.test_neon_lake_renderer import _snapshot, target  # noqa: F401  (pytest fixture)


def _train(rate, strength, span=6.0, now=0.0):
    """A steady train of waves: ``rate`` a second of ``strength``, ages from ``now`` back over ``span`` seconds."""
    count = int(span * rate)
    return tuple((now + k / rate, 0.0, -1.0, strength) for k in range(count))


def test_louder_passages_drive_more_and_quiet_ones_less_without_pinning():
    quiet = shockwave_water_reaction(_train(2.0, 0.3))[0]
    usual = shockwave_water_reaction(_train(5.0, 0.8))[0]
    loud = shockwave_water_reaction(_train(9.0, 1.6))[0]
    assert 0.0 < quiet < usual < loud < 0.95, (quiet, usual, loud)
    # A pure function of the events: nothing is learned from the track, so the same passage reads the same later.
    assert shockwave_water_reaction(_train(5.0, 0.8)) == shockwave_water_reaction(_train(5.0, 0.8))


def test_a_wave_rises_and_fades_without_a_step():
    ages = np.arange(0.0, WATER_REACT_WINDOW[1] + 0.5, 1.0 / 60.0)   # one 60 Hz frame apart
    levels = np.array([shockwave_water_reaction(((age, 0.0, -1.0, 1.0),))[0] for age in ages])
    accents = np.array([shockwave_water_reaction(((age, 0.0, -1.0, 1.0),))[1] for age in ages])
    assert levels[0] == 0.0 and accents[0] == 0.0, "a newborn wave adds nothing yet (no one-frame jump)"
    assert levels[ages >= WATER_REACT_WINDOW[1]].max() == 0.0, "forgotten before the ring can drop it"
    # A full-strength wave out of silence eases in: no frame-to-frame step a flash would make (the level ~0.04 a
    # frame; the accent, light, rises faster but over several frames).
    assert np.abs(np.diff(levels)).max() < 0.06 and np.abs(np.diff(accents)).max() < 0.25
    assert accents[ages > 3 * WATER_REACT_ACCENT[1]].max() < accents.max() * 0.2, "the accent settles"


def test_beats_swing_the_passage_level_multiplicatively():
    steady = _train(5.0, 0.8, now=0.3)
    on_beat = ((0.1, 0.0, -1.0, 0.8),) + steady
    assert shockwave_music_drive(on_beat) > shockwave_music_drive(steady)
    # A quiet passage's beats never reach a loud passage's drive.
    quiet_beat = ((0.1, 0.0, -1.0, 0.3),) + _train(2.0, 0.3, now=0.3)
    assert shockwave_music_drive(quiet_beat) < shockwave_music_drive(_train(9.0, 1.6, now=0.3))


def test_ridge_breath_is_the_midband_exactly_at_zero():
    for midband in (0.0, 0.37, 0.99):
        assert shockwave_ridge_breath(midband, 0.8, 0.0) == midband
    assert shockwave_ridge_breath(0.99, 0.2, 1.0) < 0.99, "Water Reaction 1: the pinned midband gives way"


def _lake(amount, events):
    snapshot = _snapshot(shockwave_grid_water_reaction=amount, shockwave_grid_water_shine=0.8,
                         shockwave_grid_water_detail=0.4)
    state = snapshot.logical.mode_state
    return replace(snapshot, logical=replace(snapshot.logical, mode_state=replace(state, events=events)))


def test_water_reaction_lights_the_lake_with_the_music_and_does_nothing_at_zero(target):
    capture, host = target
    loud = _train(9.0, 1.6, span=4.0, now=0.2)
    capture.render(host, _lake(0.0, loud))
    off = capture.render(host, _lake(0.0, loud)).astype(int)
    capture.render(host, _lake(1.0, ()))
    silent = capture.render(host, _lake(1.0, ())).astype(int)
    capture.render(host, _lake(1.0, loud))
    on = capture.render(host, _lake(1.0, loud)).astype(int)
    lit = np.abs(on - off)[..., :3].max(axis=-1) > 24
    assert lit.mean() > 0.01, "a loud passage lights the lake"
    # No music, no net: the reaction is the drive, not the control alone (the ridge breath may still change).
    assert (np.abs(on - off)[..., :3].max(axis=-1) > 24).sum() > 5 * (np.abs(silent - off)[..., :3].max(axis=-1) > 24).sum()
