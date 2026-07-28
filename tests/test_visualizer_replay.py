from __future__ import annotations

import json
import os
from pathlib import Path
import random
import shutil

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from tools.visualizer_replay import (  # noqa: E402
    bootstrap_goldens,
    update_goldens,
    verify_golden_manifest,
    verify_outputs,
    write_artifacts,
)
from widgets.spotify_visualizer.feature_frame import (  # noqa: E402
    BandEnergy,
    EnergyLanes,
    FeatureClip,
    FeatureFrame,
    TransientEnergy,
)
from widgets.spotify_visualizer.beat_engine import _SpotifyBeatEngine  # noqa: E402
from widgets.spotify_visualizer.replay_runtime import (  # noqa: E402
    load_clips,
    replay_clip,
    sample_presentation_trace,
    stable_digest,
)


def _energy(level: float, *, onset: bool = False) -> EnergyLanes:
    continuous = BandEnergy(level, level * 0.72, level * 0.45, level * 0.76)
    pre_agc = BandEnergy(level * 0.92, level * 0.68, level * 0.40, level * 0.70)
    bubble = BandEnergy(level * 0.86, level * 0.64, level * 0.38, level * 0.66)
    transient = TransientEnergy(
        level if onset else 0.0,
        level * 0.35 if onset else 0.0,
        level * 0.20 if onset else 0.0,
        level * 0.55 if onset else 0.0,
        onset,
        "bass" if onset else "",
        level if onset else 0.0,
    )
    return EnergyLanes(continuous, pre_agc, bubble, transient)


def _bars(level: float) -> tuple[float, ...]:
    return tuple(
        min(1.0, level * (0.35 + 0.65 * (1.0 - abs(index - 8) / 24.0)))
        for index in range(32)
    )


def _wave(level: float, phase: int) -> tuple[float, ...]:
    return tuple(
        level * (1.0 if (index + phase) % 8 < 4 else -1.0)
        for index in range(64)
    )


def _clip(name: str = "representative", *, modes=("spectrum",), frame_count: int = 8) -> FeatureClip:
    frames = []
    for index in range(frame_count):
        mode = modes[min(len(modes) - 1, index * len(modes) // frame_count)]
        previous_mode = (
            modes[min(len(modes) - 1, (index - 1) * len(modes) // frame_count)]
            if index else mode
        )
        level = (0.12, 0.28, 0.82, 0.46)[index % 4]
        frames.append(
            FeatureFrame(
                timestamp_us=100_000 + index * 16_667,
                energy=_energy(level, onset=index % 4 == 2),
                raw_bars=_bars(level),
                waveform=_wave(level, index),
                playing=True,
                visible=True,
                mode=mode,
                control_event="mode_switch" if mode != previous_mode else "none",
            )
        )
    return FeatureClip(name, tuple(frames))


@pytest.mark.qt
def test_replay_is_repeatable_and_restores_random_state(qt_app):
    clip = _clip()
    before = random.getstate()
    first = replay_clip(clip)
    after_first = random.getstate()
    second = replay_clip(clip)

    assert first["digest"] == second["digest"]
    assert first["frames"] == second["frames"]
    assert before == after_first == random.getstate()


@pytest.mark.qt
def test_all_supported_modes_use_actual_tick_and_overlay_path(qt_app):
    modes = ("spectrum", "oscilloscope", "sine_wave", "bubble", "devcurve")
    output = replay_clip(_clip("all_modes", modes=modes, frame_count=15))
    observed_modes = {frame["overlay"]["mode"] for frame in output["frames"]}

    assert observed_modes == set(modes)
    assert {
        frame["tick_path"] for frame in output["frames"]
    } == {"widgets.spotify_visualizer.tick_pipeline.on_tick"}
    assert {
        frame["overlay_path"] for frame in output["frames"]
    } == {"SpotifyBarsGLOverlay.set_state"}
    assert any(frame["overlay"].get("bubble", {}).get("count", 0) > 0 for frame in output["frames"])
    assert any(frame["overlay"].get("devcurve", {}).get("sample_count", 0) > 0 for frame in output["frames"])


@pytest.mark.qt
@pytest.mark.parametrize(
    ("presentation_hz", "stalls"),
    [
        (30, ()),
        (60, ()),
        (90, ()),
        (120, ()),
        (0, (17, 41, 13, 29)),  # irregular opportunities
        (60, (100,)),
        (60, (250,)),
        (60, (500,)),
    ],
)
def test_presentation_schedule_does_not_change_logical_series(qt_app, presentation_hz, stalls):
    clip = _clip("temporal", modes=("spectrum", "bubble"), frame_count=10)
    baseline = replay_clip(clip)
    candidate = replay_clip(
        clip,
        presentation_hz=presentation_hz or None,
        presentation_stalls_ms=stalls,
    )

    assert candidate["digest"] == baseline["digest"]
    assert candidate["frames"] == baseline["frames"]


def test_verify_is_read_only(tmp_path):
    output = {"clip": {"digest": "abc", "frames": []}}
    golden = tmp_path / "clip.json"
    golden.write_text(json.dumps(output["clip"]), encoding="utf-8")
    before = golden.read_bytes()
    before_stat = golden.stat()

    assert verify_outputs(output, tmp_path) == []
    assert golden.read_bytes() == before
    assert golden.stat().st_mtime_ns == before_stat.st_mtime_ns


def test_bootstrap_requires_acknowledgement_and_refuses_overwrite(tmp_path):
    outputs = {"clip": {"digest": "new"}}
    with pytest.raises(PermissionError, match="acknowledge-baseline"):
        bootstrap_goldens(outputs, tmp_path, baseline_acknowledged=False)

    bootstrap_goldens(outputs, tmp_path, baseline_acknowledged=True)
    original = (tmp_path / "clip.json").read_bytes()
    with pytest.raises(FileExistsError, match="refuses to overwrite"):
        bootstrap_goldens(outputs, tmp_path, baseline_acknowledged=True)
    assert (tmp_path / "clip.json").read_bytes() == original


def test_update_policy_requires_behavior_ack_and_approved_declaration(tmp_path):
    outputs = {"clip": {"digest": "new"}}
    declaration = tmp_path / "change.md"
    declaration.write_text("approved: true\ngoldens: true\n", encoding="utf-8")

    with pytest.raises(PermissionError, match="behavior-change"):
        update_goldens(
            outputs,
            tmp_path / "goldens",
            behavior_change_acknowledged=False,
            change_declaration=declaration,
        )
    with pytest.raises(PermissionError, match="approved change declaration"):
        update_goldens(
            outputs,
            tmp_path / "goldens",
            behavior_change_acknowledged=True,
            change_declaration=tmp_path / "missing.md",
        )
    update_goldens(
        outputs,
        tmp_path / "goldens",
        behavior_change_acknowledged=True,
        change_declaration=declaration,
    )
    assert json.loads((tmp_path / "goldens" / "clip.json").read_text()) == outputs["clip"]


def test_golden_drift_detection(tmp_path):
    (tmp_path / "clip.json").write_text('{"digest":"old","frames":[]}', encoding="utf-8")
    errors = verify_outputs({"clip": {"digest": "new", "frames": []}}, tmp_path)
    assert len(errors) == 1
    assert "golden drift expected=old actual=new" in errors[0]


@pytest.mark.qt
def test_metrics_are_quantitative_and_sane(qt_app):
    output = replay_clip(_clip("metrics", frame_count=12))
    metrics = output["metrics"]

    assert 0.0 < metrics["bar_mean"] <= metrics["bar_peak"] <= 1.0
    assert metrics["bar_flux"] > 0.0
    assert 0.0 <= metrics["bar_centroid"] < 32.0
    assert metrics["waveform_rms"] > 0.0
    assert metrics["waveform_peak"] <= 1.0
    assert metrics["waveform_zero_crossings"] > 0
    assert metrics["beat_count"] == metrics["onset_count"] == 3
    assert metrics["response_frame"] >= 0
    assert metrics["bubble_centroid_speed_peak"] == 0.0
    assert metrics["bubble_radius_excursion"] == 0.0
    assert output["digest"]

    bubble = replay_clip(
        _clip("bubble_metrics", modes=("bubble",), frame_count=12)
    )["metrics"]
    assert bubble["bubble_particle_peak"] > 0
    assert bubble["bubble_centroid_speed_peak"] > 0.0
    assert bubble["bubble_radius_change_peak_per_s"] > 0.0
    assert bubble["bubble_radius_excursion"] > 0.0
    assert bubble["bubble_radius_overshoot_ratio"] >= 0.0
    assert bubble["bubble_radius_rebound_count"] >= 0

@pytest.mark.qt
def test_replay_calls_production_engine_tick(qt_app, monkeypatch):
    calls = []
    original_tick = _SpotifyBeatEngine.tick

    def tick_spy(engine):
        calls.append(engine)
        return original_tick(engine)

    monkeypatch.setattr(_SpotifyBeatEngine, "tick", tick_spy)
    output = replay_clip(_clip("production_tick", frame_count=6))

    assert len(calls) == len(output["frames"]) == 6


def test_presentation_trace_samples_latest_completed_state():
    frames = [
        {"timestamp_us": 0, "value": "first"},
        {"timestamp_us": 10_000, "value": "second"},
        {"timestamp_us": 20_000, "value": "third"},
    ]

    trace = sample_presentation_trace(
        frames,
        presentation_intervals_ms=(15,),
    )

    assert [sample["source_index"] for sample in trace] == [0, 1, 2]
    assert [sample["state_digest"] for sample in trace] == [
        stable_digest(frames[0]),
        stable_digest(frames[1]),
        stable_digest(frames[2]),
    ]


@pytest.mark.qt
def test_visibility_toggle_uses_production_tick_gate(qt_app):
    source = _clip("visibility", frame_count=4)
    frames = tuple(
        FeatureFrame(
            timestamp_us=frame.timestamp_us,
            energy=frame.energy,
            raw_bars=frame.raw_bars,
            waveform=frame.waveform,
            playing=frame.playing,
            visible=visible,
            mode=frame.mode,
            control_event="visibility_toggle",
        )
        for frame, visible in zip(source.frames, (True, False, False, True))
    )

    output = replay_clip(FeatureClip("visibility", frames))

    assert [frame["published"] for frame in output["frames"]] == [
        True,
        False,
        False,
        True,
    ]


def test_fixture_hash_tamper_is_rejected(tmp_path):
    source = Path("tests/fixtures/visualizer_replay/v1")
    fixture_dir = tmp_path / "fixtures"
    shutil.copytree(source, fixture_dir)
    fixture = fixture_dir / "silence.jsonl"
    payload = fixture.read_text(encoding="utf-8")
    fixture.write_text(
        payload.replace('"playing":true', '"playing":false', 1),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="fixture hash mismatch"):
        load_clips(fixture_dir)


def test_golden_manifest_verification_is_read_only_and_detects_drift(tmp_path):
    outputs = {"clip": {"digest": "abc", "frames": []}}
    bootstrap_goldens(
        outputs,
        tmp_path,
        baseline_acknowledged=True,
    )
    manifest = tmp_path / "manifest.json"
    before = manifest.read_bytes()
    before_mtime = manifest.stat().st_mtime_ns

    assert verify_golden_manifest(outputs, tmp_path) == []
    assert manifest.read_bytes() == before
    assert manifest.stat().st_mtime_ns == before_mtime

    data = json.loads(manifest.read_text(encoding="utf-8"))
    data["baseline_behavior_commit"] = "wrong"
    manifest.write_text(json.dumps(data), encoding="utf-8")
    assert verify_golden_manifest(outputs, tmp_path) == [
        "golden manifest drift"
    ]


@pytest.mark.qt
def test_artifact_writer_creates_reviewable_pngs_and_html(qt_app, tmp_path):
    outputs = {
        "representative_music_features__spectrum": replay_clip(
            _clip("representative_music_features__spectrum", frame_count=8)
        ),
        "representative_music_features__bubble": replay_clip(
            _clip(
                "representative_music_features__bubble",
                modes=("bubble",),
                frame_count=8,
            )
        ),
    }

    paths = write_artifacts(outputs, tmp_path)

    assert [path.name for path in paths] == [
        "spectrum_logical_contact_sheet.png",
        "bubble_logical_contact_sheet.png",
        "spectrum_bubble_review.html",
    ]
    assert all(path.is_file() and path.stat().st_size > 100 for path in paths)
    assert paths[0].read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
    assert paths[1].read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
    assert "chronologically" in paths[2].read_text(encoding="utf-8")