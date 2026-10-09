from __future__ import annotations

import hashlib
import json
from pathlib import Path

from PIL import Image
import pytest

from tools.release_media import MediaCase, catalogue, encode_webp, fingerprint, is_current, load_recording, sample_indices, transition_spec


def test_catalogue_tracks_canonical_registry_and_curated_files() -> None:
    from rendering.transition_registry import iter_transition_descriptors
    from core.settings.visualizer_mode_registry import iter_visualizer_mode_descriptors
    from core.settings.visualizer_presets import get_presets
    from rendering.gl_programs.blinds_options import BLINDS_STYLE_CHOICES

    cases = catalogue()
    assert {case.identity for case in cases if case.kind == "transition"} == {
        descriptor.stable_id for descriptor in iter_transition_descriptors() if descriptor.available}
    assert {case.label for case in cases if case.identity == "blinds"} == set(BLINDS_STYLE_CHOICES)
    expected = {(descriptor.mode_id, preset.name) for descriptor in iter_visualizer_mode_descriptors()
                for preset in get_presets(descriptor.mode_id) if not preset.is_custom}
    assert {(case.identity, case.label) for case in cases if case.kind == "visualizer"} == expected
    assert all(Path(case.preset_file).is_file() for case in cases if case.kind == "visualizer")
    assert len({case.filename for case in cases}) == len(cases)


def test_encoder_preserves_loop_duration_and_strips_metadata(tmp_path: Path) -> None:
    frames = []
    for index in range(4):
        path = tmp_path / f"{index}.png"
        image = Image.new("RGB", (320, 180), (index * 70, 20, 50))
        image.save(path)
        frames.append(path)
    output = tmp_path / "motion.webp"
    metadata = encode_webp(frames, output, duration_ms=400, max_bytes=100000, width=320, fps=10)
    assert metadata["quality"] == 92
    assert metadata["bytes"] <= 100000
    assert metadata["sha256"] == hashlib.sha256(output.read_bytes()).hexdigest()
    with Image.open(output) as encoded:
        assert encoded.is_animated and encoded.info["loop"] == 0
        total = 0
        for index in range(encoded.n_frames):
            encoded.seek(index)
            encoded.load()
            total += encoded.info["duration"]
        assert total == 400
        assert not any(encoded.info.get(key) for key in ("icc_profile", "exif", "xmp"))


def test_encoding_reduces_size_at_fixed_quality_and_refuses_impossible_budget(tmp_path: Path) -> None:
    frames = []
    for index in range(4):
        path = tmp_path / f"{index}.png"
        Image.effect_noise((320, 180), 100).convert("RGB").save(path)
        frames.append(path)
    large = encode_webp(frames, tmp_path / "large.webp", duration_ms=400, max_bytes=1000000, width=320, fps=10)
    small = encode_webp(frames, tmp_path / "small.webp", duration_ms=400,
                        max_bytes=large["bytes"] - 1, width=320, fps=10)
    assert small["dimensions"][0] < large["dimensions"][0]
    assert small["quality"] == large["quality"] == 92
    assert len(small["attempts"]) > 1
    with pytest.raises(ValueError, match="exceeds byte budget"):
        encode_webp(frames, tmp_path / "impossible.webp", duration_ms=400, max_bytes=1, width=320, fps=10)
    assert not (tmp_path / "impossible.webp").exists()


def test_stale_detection_includes_clip_parameters_source_and_artifact_bytes(tmp_path: Path) -> None:
    case = MediaCase("transition", "crossfade", "default", "Canonical")
    source = {"source_tree_sha256": "source-a", "revision": "revision-a"}
    options = {"fps": 30}
    digest = fingerprint(case, source, options, "clip-a")
    assert fingerprint(case, {**source, "revision": "revision-b"}, options, "clip-a") == digest
    assert fingerprint(case, {**source, "source_tree_sha256": "source-b"}, options, "clip-a") != digest
    assert fingerprint(case, source, {"fps": 15}, "clip-a") != digest
    assert fingerprint(case, source, options, "clip-b") != digest
    output = tmp_path / "capture.webp"
    output.write_bytes(b"original")
    entry = {"fingerprint": digest, "sha256": hashlib.sha256(b"original").hexdigest()}
    assert is_current(entry, digest, output)
    output.write_bytes(b"changed")
    assert not is_current(entry, digest, output)


def test_release_recording_admission_rejects_fixture_and_archived_take(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="canonical recording"):
        load_recording(tmp_path / "fixture.jsonl", start_seconds=0, duration_seconds=1)
    from tools.visualizer_replay.record import OUTPUT
    with pytest.raises(ValueError, match="canonical recording"):
        load_recording(OUTPUT / "balanced_v1.jsonl", start_seconds=0, duration_seconds=1)


def test_extruded_replay_uses_registered_production_logical_and_snapshot_path() -> None:
    from PySide6.QtCore import QCoreApplication
    from widgets.spotify_visualizer.feature_frame import FeatureClip
    from tools.visualizer_replay.driver import load_clips, replay_clip

    app = QCoreApplication.instance() or QCoreApplication([])
    original = next(iter(load_clips().values()))
    clip = FeatureClip(original.name, original.frames[:6])
    result = replay_clip(clip, "extruded_spectrum", snapshots_at=(5,))
    snapshot = result["snapshots"][5]
    assert snapshot.logical.mode_id == "extruded_spectrum"
    assert snapshot.logical.common.bars
    assert "extruded_spectrum_depth" in snapshot.logical.mode_state.parameters
    assert result["mode_metrics"]["output_peak"] >= 0


def test_recorded_interval_preserves_preroll_and_samples_feature_timestamps(tmp_path: Path, monkeypatch) -> None:
    from tools.visualizer_replay import record
    from tools.visualizer_replay.sphere_golden import golden_clip

    original, _ = golden_clip()
    monkeypatch.setattr(record, "OUTPUT", tmp_path)
    path = tmp_path / "music.jsonl"
    path.write_bytes(original.to_jsonl_bytes())
    selected = load_recording(path, start_seconds=1, duration_seconds=1)
    assert selected.frames[0] == original.frames[0]
    indices = sample_indices(selected, 1, 1, 30)
    assert len(indices) == 30
    origin = original.frames[0].timestamp_us
    assert selected.frames[indices[0]].timestamp_us >= origin + 1000000
    assert selected.frames[indices[-1]].timestamp_us < origin + 2000000
    assert selected.frames[-1].timestamp_us <= origin + 2000000
    with pytest.raises(ValueError, match="shorter"):
        load_recording(path, start_seconds=100, duration_seconds=1)


def test_transition_endpoint_holds_preserve_exact_total_animation_duration(tmp_path: Path) -> None:
    frames = []
    for index in range(6):
        path = tmp_path / f"{index}.png"
        Image.new("RGB", (320, 180), (index * 40, 20, 50)).save(path)
        frames.append(path)
    output = tmp_path / "motion.webp"
    metadata = encode_webp(frames, output, duration_ms=500, hold_ms=100, max_bytes=100000,
                           width=320, fps=10)
    assert metadata["duration_ms"] == 700
    assert metadata["motion_duration_ms"] == 500
    with Image.open(output) as encoded:
        encoded.seek(0)
        encoded.load()
        assert encoded.info["duration"] >= 100
        first = encoded.convert("RGB").getpixel((0, 0))
        total = 0
        for index in range(encoded.n_frames):
            encoded.seek(index)
            encoded.load()
            total += encoded.info["duration"]
        last = encoded.convert("RGB").getpixel((0, 0))
        assert total == 700
        assert first[0] < 5 and last[0] > 195


def test_source_change_during_capture_discards_media(tmp_path: Path, monkeypatch) -> None:
    from tools import release_media as tool
    from tools import run_matrix

    case = MediaCase("transition", "crossfade", "default", "Canonical")
    pending = MediaCase("transition", "crossfade", "pending", "Pending")
    monkeypatch.setattr(tool, "catalogue", lambda: [case, pending])
    sources = iter(["original", "original", "changed"])
    monkeypatch.setattr(run_matrix, "_source_attribution",
                        lambda: {"source_tree_sha256": next(sources), "unavailable": []})

    def capture(case, directory, **kwargs):
        directory.mkdir()
        frames = []
        for index in range(4):
            path = directory / f"{index}.png"
            Image.new("RGB", (320, 180), (index * 70, 20, 50)).save(path)
            frames.append(path)
        return frames

    monkeypatch.setattr(tool, "capture_transition_loop", lambda case, directory, **kwargs: capture(case, directory))
    scenes = []
    for index in range(4):
        path = tmp_path / f"scene{index}.png"
        Image.new("RGB", (64, 36), (index * 60, 30, 30)).save(path)
        scenes.append(path)
    monkeypatch.setattr(tool, "USU_SCENES", tuple(scenes))
    out = tmp_path / "output"
    code = tool.main(["--output-dir", str(out), "--capture-width", "320", "--width", "320",
                      "--duration-seconds", "0.5", "--fps", "10"])
    assert code == 1
    assert not (out / case.filename).exists()
    failures = json.loads((out / "release_media_failures.json").read_text())
    assert "source changed during capture" in failures[0]["error"]
    assert failures[0]["unattempted"] == [pending.key]


def test_every_catalogued_transition_uses_complete_production_request_resolution() -> None:
    for case in catalogue():
        if case.kind != "transition":
            continue
        spec = transition_spec(case.identity, 500, case.settings)
        assert spec.transition_id == case.identity
        assert spec.duration_ms == 500
        assert not spec.selected_from_random


def test_showcases_pick_random_scene_pairs_and_seeds() -> None:
    import random
    from tools.release_media import SCENE_PAIRS, pick_showcase, transition_size

    rng = random.Random(5)
    picks = [pick_showcase(rng) for _ in range(60)]
    assert all(pair in SCENE_PAIRS and pair[0] != pair[1] for pair, _seed in picks)
    assert len({pair for pair, _seed in picks}) > len(SCENE_PAIRS) // 2   # the scenes are used in many orders
    assert len({seed for _pair, seed in picks}) == len(picks)
    width, height = transition_size()
    assert width == 480 and height % 2 == 0 and abs(width / height - 16 / 9) < 0.02


def test_missing_operator_scenes_fail_loudly(tmp_path: Path) -> None:
    from tools.release_media import load_scenes

    with pytest.raises(FileNotFoundError, match="never substituted"):
        load_scenes((tmp_path / "absent.png",))


def test_the_showcase_never_runs_back_in_the_same_direction() -> None:
    from tools.release_media import _look, return_seed

    for case in catalogue():
        if case.kind != "transition":
            continue
        there = _look(transition_spec(case.identity, 500, case.settings, 713))
        looks = {_look(transition_spec(case.identity, 500, case.settings, seed)) for seed in range(700, 760)}
        back = _look(transition_spec(case.identity, 500, case.settings, return_seed(case, 500, 713)))
        if len(looks) > 1:                       # the transition has a direction/order choice
            assert back != there, case.key
            from rendering.quick.transitions.directions import _DIRECTIONS
            a, b = _DIRECTIONS.get(str(there[0])), _DIRECTIONS.get(str(back[0]))
            if a is not None and b is not None:  # sweeps run back broadly the other way
                assert a[0] * b[0] + a[1] * b[1] <= 0.25 * (a[0] ** 2 + a[1] ** 2) ** .5 * (b[0] ** 2 + b[1] ** 2) ** .5


def test_transition_showcases_play_faster_before_shrinking_or_dropping_frames(tmp_path: Path) -> None:
    from tools.release_media import transition_encoding_plan

    plan = transition_encoding_plan(480, 30)
    assert all(width == 480 for width, _fps, _scale in plan)
    scales = [scale for _width, fps, scale in plan if fps == 30]
    assert scales == sorted(scales, reverse=True) and scales[0] == 1.0 and len(scales) > 1
    assert plan.index(next(step for step in plan if step[1] < 30)) == len(scales)
    import numpy as np

    rng = np.random.default_rng(3)
    frames = []
    for index in range(120):                     # distinct frames: playing faster really drops some
        path = tmp_path / f"{index}.png"
        Image.fromarray(rng.integers(0, 256, (180, 320, 3), dtype=np.uint8)).save(path)
        frames.append(path)
    full = encode_webp(frames, tmp_path / "full.webp", duration_ms=2000, max_bytes=10**7, width=320, fps=30,
                       plan=[(320, 30, 1.0)])
    faster = encode_webp(frames, tmp_path / "faster.webp", duration_ms=2000, max_bytes=full["bytes"] - 1,
                         width=320, fps=30, plan=[(320, 30, 1.0), (320, 30, .6)])
    assert faster["dimensions"] == [320, 180] and faster["fps"] == 30 and faster["time_scale"] == .6
    assert faster["motion_duration_ms"] == 1200


def test_showcase_sampling_shows_every_motion_frame_once() -> None:
    from tools.release_media import timeline_source_indices

    # 30 fps capture of a 4700 ms motion, 30 fps output with 350 ms rests (10.5 frames each):
    # the old round-half-to-even sampling repeated every other frame (54 repeats, 15 fps motion).
    motion, hold, fps = 4700, 350, 30
    sources = round(motion * fps / 1000) + 1
    count = round((motion + 2 * hold) * fps / 1000)
    indices = timeline_source_indices(sources, motion, hold, count)
    assert indices[0] == 0 and indices[-1] == sources - 1
    inside = [i for i in indices if 0 < i < sources - 1]
    assert len(inside) == len(set(inside)) == sources - 2          # every motion frame, once
    assert all(b - a in (0, 1) for a, b in zip(indices, indices[1:]))

