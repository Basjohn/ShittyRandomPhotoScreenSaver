"""Schema 2 replay: real-scale lanes (the units production reads, never capped at 1) and Voxel
Sphere through the production capture, deterministically."""
from __future__ import annotations

import pytest

from widgets.spotify_visualizer.feature_frame import (
    REAL_SCALE_SCHEMA_VERSION,
    BandEnergy,
    EnergyLanes,
    FeatureClip,
    FeatureFrame,
    RealScaleLanes,
    TransientEnergy,
    TypedEvent,
)

_FRAME_US = 11_111                        # the logical cadence (90 Hz)


def _lanes(level: float) -> EnergyLanes:
    band = BandEnergy(bass=level, mid=level, high=level * 0.5, overall=level)
    return EnergyLanes(continuous=band, pre_agc=band, bubble=band, transient=TransientEnergy(
        bass=0.0, mid=0.0, high=0.0, overall=0.0, onset_detected=False, onset_type="", onset_strength=0.0))


def _frame(index: int, *, loudness: float, presence: float, events=(), spectrum_level=None) -> FeatureFrame:
    unit = min(1.0, loudness / 17.0)
    live = min(2.5, loudness * 0.3)
    spectrum = tuple((spectrum_level if spectrum_level is not None else loudness) * (1.0 + 0.01 * (k % 7))
                     for k in range(64))
    return FeatureFrame(
        timestamp_us=1_000_000 + index * _FRAME_US, energy=_lanes(unit), raw_bars=(unit,) * 32,
        waveform=(0.0,) * 64, playing=True, visible=True, mode="sphere",
        schema_version=REAL_SCALE_SCHEMA_VERSION,
        real=RealScaleLanes(live=(live, live, live * 0.5, live), musical_level=(loudness, presence),
                            analysis_spectrum=spectrum,
                            events=tuple(TypedEvent(kind, strength) for kind, strength in events)),
    )


def _clip(name: str, segments) -> FeatureClip:
    frames, index = [], 0
    for count, kwargs, event_every in segments:
        for step in range(count):
            events = (("kick", 0.95),) if event_every and step % event_every == event_every - 1 else ()
            frames.append(_frame(index, events=events, **kwargs))
            index += 1
    return FeatureClip(name=name, frames=tuple(frames))


def test_real_scale_lanes_are_not_capped_at_one_and_schema_1_serialises_unchanged():
    frame = _frame(0, loudness=12.0, presence=1.4)
    assert frame.real.musical_level == (12.0, 1.4)
    assert FeatureFrame.from_dict(frame.to_dict()) == frame
    v1 = FeatureFrame(timestamp_us=0, energy=_lanes(0.5), raw_bars=(0.5,) * 32, waveform=(0.0,) * 64,
                      playing=True, visible=True, mode="bubble")
    assert "real" not in v1.to_dict() and v1.schema_version == 1
    with pytest.raises(ValueError):
        FeatureFrame(**{**{f: getattr(v1, f) for f in ("timestamp_us", "energy", "raw_bars", "waveform", "playing",
                                                       "visible")}, "mode": "sphere"})
    with pytest.raises(ValueError):
        RealScaleLanes(live=(3.0, 0, 0, 0), musical_level=(1.0, 1.0), analysis_spectrum=())   # live is clamped 2.5


def _sphere(clip):
    from tools.visualizer_replay.driver import replay_clip

    return replay_clip(clip, "sphere")


def _peak_fragment(result, start, stop):
    return max(max(row["sphere"]["section_drives"]) for row in result["frames"][start:stop])


def test_sphere_replays_deterministically_and_its_reaction_follows_the_music(qt_app):
    clip = _clip("sphere_ramp", (
        (90, dict(loudness=0.0, presence=0.0), 0),            # silence
        (180, dict(loudness=9.0, presence=1.0), 30),          # loud music, a kick every 1/3 s
        (180, dict(loudness=3.0, presence=0.3), 30),          # a quiet passage, the same kicks
    ))
    first, second = _sphere(clip), _sphere(clip)
    assert [row["sphere"] for row in first["frames"]] == [row["sphere"] for row in second["frames"]]
    assert _peak_fragment(first, 0, 90) == 0.0                          # silence authors nothing
    loud = _peak_fragment(first, 90, 270)
    quiet = _peak_fragment(first, 300, 450)
    assert loud > 0.5 and quiet < 0.5 * loud
    assert not any(row["sphere"]["cohorts"] for row in first["frames"][:90])


def test_sphere_refuses_a_schema_1_clip(qt_app):
    from tools.visualizer_replay.driver import load_clips

    clip = next(iter(load_clips().values()))
    with pytest.raises(ValueError):
        _sphere(clip)
