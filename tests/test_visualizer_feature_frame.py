from __future__ import annotations

import subprocess
import sys

import pytest

from tools.generate_visualizer_replay_fixtures import (
    build_fixtures,
    generate_fixtures,
)
from widgets.spotify_visualizer.feature_frame import (
    BandEnergy,
    EnergyLanes,
    FeatureClip,
    FeatureFrame,
    RAW_BAR_COUNT,
    TransientEnergy,
    WAVEFORM_COUNT,
)


def _energy() -> EnergyLanes:
    lane = BandEnergy(0.1, 0.1, 0.1, 0.1)
    return EnergyLanes(
        continuous=lane,
        pre_agc=lane,
        bubble=lane,
        transient=TransientEnergy(0, 0, 0, 0, False, "", 0),
    )


def _frame(timestamp: int = 1) -> FeatureFrame:
    return FeatureFrame(
        timestamp_us=timestamp,
        energy=_energy(),
        raw_bars=(0.1,) * RAW_BAR_COUNT,
        waveform=(0.0,) * WAVEFORM_COUNT,
        playing=True,
        visible=True,
        mode="spectrum",
    )


def test_feature_frame_jsonl_round_trip_is_canonical_and_hashed():
    clip = FeatureClip("round_trip", (_frame(1), _frame(2)))
    encoded = clip.to_jsonl_bytes()

    assert FeatureClip.from_jsonl_bytes(
        "round_trip",
        encoded,
    ).to_jsonl_bytes() == encoded
    assert len(clip.sha256()) == 64


@pytest.mark.parametrize(
    "invalid_value",
    [
        lambda: FeatureFrame(
            1,
            _energy(),
            (0.1,) * 31,
            (0.0,) * WAVEFORM_COUNT,
            True,
            True,
            "spectrum",
        ),
        lambda: BandEnergy(1.1, 0.1, 0.1, 0.1),
        lambda: TransientEnergy(0.1, 0.1, 0.1, 0.1, False, "bass", 0),
        lambda: TransientEnergy(
            0.1,
            0.1,
            0.1,
            0.1,
            True,
            "unknown",
            0.5,
        ),
        lambda: FeatureFrame(
            1,
            _energy(),
            (0.1,) * RAW_BAR_COUNT,
            (2.0,) * WAVEFORM_COUNT,
            True,
            True,
            "blob",
        ),
    ],
)
def test_feature_frame_strict_validation(invalid_value):
    with pytest.raises((TypeError, ValueError)):
        invalid_value()

    with pytest.raises(ValueError):
        FeatureClip("bad_timing", (_frame(2), _frame(2)))


def test_same_seed_is_byte_identical_and_different_seed_diverges():
    first = build_fixtures(10)
    second = build_fixtures(10)

    assert {
        name: clip.to_jsonl_bytes() for name, clip in first.items()
    } == {
        name: clip.to_jsonl_bytes() for name, clip in second.items()
    }
    assert (
        build_fixtures(11)["broadband_noise"].to_jsonl_bytes()
        != first["broadband_noise"].to_jsonl_bytes()
    )


def test_fixture_signal_semantics_are_explicit_and_coherent():
    fixtures = build_fixtures(3)

    for frame in fixtures["silence"].frames:
        assert frame.raw_bars == (0.0,) * RAW_BAR_COUNT
        assert frame.waveform == (0.0,) * WAVEFORM_COUNT
        assert frame.energy.continuous == BandEnergy(0, 0, 0, 0)
        assert frame.energy.transient == TransientEnergy(
            0,
            0,
            0,
            0,
            False,
            "",
            0,
        )

    impulse = fixtures["isolated_impulse"].frames
    assert [
        frame.energy.transient.onset_detected for frame in impulse
    ] == [index == 8 for index in range(len(impulse))]

    for name, cadence in (
        ("beats_60_bpm", 50),
        ("beats_120_bpm", 25),
        ("beats_180_bpm", 17),
    ):
        frames = fixtures[name].frames
        assert [
            frame.energy.transient.onset_detected for frame in frames
        ] == [index % cadence == 0 for index in range(len(frames))]

    bass = fixtures["sustained_bass"].frames[0].energy
    treble = fixtures["sustained_treble"].frames[0].energy
    for lane in (bass.continuous, bass.pre_agc, bass.bubble):
        assert lane.bass > lane.high
    for lane in (treble.continuous, treble.pre_agc, treble.bubble):
        assert lane.high > lane.bass

    ramp = fixtures["gradual_ramp"].frames
    step = fixtures["sudden_volume_step"].frames
    assert ramp[0].energy.continuous.overall < ramp[-1].energy.continuous.overall
    assert step[19].energy.continuous.overall < step[20].energy.continuous.overall
    assert len(
        {
            frame.energy.continuous
            for frame in fixtures["representative_music_features"].frames
        }
    ) > 4


def test_generator_refuses_overwrite_and_includes_required_metadata(tmp_path):
    manifest = generate_fixtures(tmp_path / "fixtures", seed=3)
    with pytest.raises(FileExistsError):
        generate_fixtures(tmp_path / "fixtures", seed=3)

    required_names = {
        "silence",
        "isolated_impulse",
        "beats_60_bpm",
        "beats_120_bpm",
        "beats_180_bpm",
        "sustained_bass",
        "sustained_treble",
        "broadband_noise",
        "gradual_ramp",
        "sudden_volume_step",
        "representative_music_features",
        "irregular_input_cadence",
        "mode_visibility_switch",
    }
    assert required_names <= {
        entry["name"] for entry in manifest["fixtures"]
    }
    assert manifest["presentation_stall_schedule_ms"] == [100, 250, 500]
    assert manifest["no_copyright_statement"]


def test_generator_help_is_safe():
    result = subprocess.run(
        [
            sys.executable,
            "tools/generate_visualizer_replay_fixtures.py",
            "--help",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "--overwrite" in result.stdout