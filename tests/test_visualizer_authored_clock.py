"""The Visualizer's authored clock is monotonic and owns every logical step (Architecture Checklist AC-12).

A wall-clock step (a time sync, a manual change) used to reach every mode: the tick, the beat engine's smoothing, play
ramp and keepalive, the onset ages and the capture timestamps all read ``time.time()``. These tests replay a shipped
native-PCM clip through the production logical tick for EVERY Visualizer mode while the wall clock jumps back 5 s and
then forward 60 s between ticks, the authored clock advancing steadily: every published frame must be exactly the
frame of the same replay without the jumps (so its simulation dt never sees them), its logical timestamps must
advance by bounded steps, and every number it publishes must stay finite. Negative control: the same replay with the
authored clock reading the jumping wall clock (what the tick read before) publishes different frames and a negative
step. Structure only; the clip is a shipped asset and no preset or default value is pinned.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import fields, is_dataclass
import math
import re
import time
from pathlib import Path

import pytest

from core.settings.visualizer_mode_registry import iter_all_visualizer_mode_descriptors
from tools.visualizer_replay import driver
from tools.visualizer_replay.pcm_reanalysis import reanalyzed_bubble_bands
from widgets.spotify_visualizer import feature_replay
from widgets.spotify_visualizer.compact_clip import load_feature_clip
from widgets.spotify_visualizer.feature_frame import FeatureClip

CLIP = Path(__file__).resolve().parents[1] / "assets" / "production" / "studio_clips" / "rag_doll.srclip"
SECONDS = 3.0
BACK, FORWARD = (1.0, -5.0), (2.0, 60.0)   # (seconds into the clip, wall-clock jump)
MODES = [descriptor.mode_id for descriptor in iter_all_visualizer_mode_descriptors()]


@pytest.fixture(scope="module")
def clip():
    full = load_feature_clip(CLIP)
    origin = full.frames[0].timestamp_us
    return FeatureClip("authored_clock", tuple(frame for frame in full.frames
                                               if (frame.timestamp_us - origin) / 1e6 <= SECONDS)), origin / 1e6


def _jump(now, origin):
    elapsed = now - origin
    return now + (BACK[1] if elapsed >= BACK[0] else 0.) + (FORWARD[1] if elapsed >= FORWARD[0] else 0.)


@contextmanager
def _wall_clock_jumps(origin, *, authored_follows_wall=False):
    """The production deterministic clock, with ``time.time`` (and, for the negative control, the authored clock)
    jumping back then forward while the replay's own clock advances steadily."""
    real = feature_replay.deterministic_clock

    @contextmanager
    def jumping():
        with real() as now:
            saved = time.time
            time.time = lambda: _jump(now[0], origin)
            try:
                if authored_follows_wall:
                    from core.authored_clock import pinned_authored_clock
                    with pinned_authored_clock(lambda: _jump(now[0], origin)):
                        yield now
                else:
                    yield now
            finally:
                time.time = saved
    original = driver.deterministic_clock
    driver.deterministic_clock = jumping
    try:
        yield
    finally:
        driver.deterministic_clock = original


def _replay(clip, mode):
    with reanalyzed_bubble_bands():
        return driver.replay_clip(clip, mode)["logical_series"]


# Extruded Bubble's drift families carry a process-wide revision counter (one per published geometry), so a second
# replay in the same process numbers them on from the first; the geometry itself is compared byte for byte.
_REVISION = re.compile(r"(DriftFamily\(family='\w+', )revision=\d+")


def _published(frames):
    return [_REVISION.sub(r"\1revision=_", repr(frame)) for frame in frames]


def _finite(value, path="frame"):
    if isinstance(value, float):
        assert math.isfinite(value), path
    elif isinstance(value, (tuple, list)):
        for index, item in enumerate(value):
            _finite(item, f"{path}[{index}]")
    elif is_dataclass(value) and not isinstance(value, type):
        for field in fields(value):
            _finite(getattr(value, field.name), f"{path}.{field.name}")


@pytest.mark.parametrize("mode", MODES)
def test_a_wall_clock_step_never_reaches_a_published_frame(clip, mode):
    clip, origin = clip
    steady = _replay(clip, mode)
    with _wall_clock_jumps(origin):
        jumped = _replay(clip, mode)
    assert _published(jumped) == _published(steady)
    stamps = [frame.logical_timestamp for frame in jumped]
    steps = [b - a for a, b in zip(stamps, stamps[1:])]
    assert steps and min(steps) >= 0. and max(steps) < .25
    for frame in jumped:
        _finite(frame.logical_timestamp)
        _finite(frame.mode_state)


def test_negative_control_a_tick_on_the_wall_clock_sees_the_jumps(clip):
    clip, origin = clip
    steady = _replay(clip, "bubble")
    with _wall_clock_jumps(origin, authored_follows_wall=True):
        jumped = _replay(clip, "bubble")
    stamps = [frame.logical_timestamp for frame in jumped]
    assert min(b - a for a, b in zip(stamps, stamps[1:])) < -4.
    assert _published(jumped) != _published(steady)


def test_the_authored_clock_is_monotonic_and_pins_restore():
    import core.authored_clock as authored_clock
    readings = [authored_clock.authored_now() for _ in range(1000)]
    assert all(b >= a for a, b in zip(readings, readings[1:]))
    with authored_clock.pinned_authored_clock(lambda: 7.):
        assert authored_clock.authored_now() == 7.
    assert authored_clock.authored_now() != 7.
