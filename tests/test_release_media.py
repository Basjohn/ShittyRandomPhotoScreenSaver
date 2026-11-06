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
        descriptor.stable_id for descriptor in iter_transition_descriptors()
        if descriptor.available and descriptor.stable_id not in {"warp_dissolve", "particle"}}
    assert {case.label for case in cases if case.identity == "blinds"} == set(BLINDS_STYLE_CHOICES) - {"Flat"}
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
    from PySide6.QtGui import QGuiApplication
    from widgets.spotify_visualizer.feature_frame import FeatureClip
    from tools.visualizer_replay.driver import load_clips, replay_clip

    # A GUI application: a plain QCoreApplication left behind makes later offscreen GL contexts fail.
    app = QGuiApplication.instance() or QGuiApplication([])
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


def test_transition_showcases_keep_one_frame_rate_and_speed_and_step_only_quality(tmp_path: Path) -> None:
    from tools.release_media import TRANSITION_FPS, TRANSITION_QUALITY, transition_encoding_plan

    plan = transition_encoding_plan(480, TRANSITION_FPS)
    assert {(width, fps, scale) for width, fps, scale, _quality in plan} == {(480, TRANSITION_FPS, 1.0)}
    qualities = [quality for *_rest, quality in plan]
    assert qualities == sorted(qualities, reverse=True) and qualities[0] == TRANSITION_QUALITY and len(qualities) > 1
    import numpy as np

    rng = np.random.default_rng(3)
    frames = []
    for index in range(120):                     # distinct frames: playing faster really drops some
        path = tmp_path / f"{index}.png"
        Image.fromarray(rng.integers(0, 256, (180, 320, 3), dtype=np.uint8)).save(path)
        frames.append(path)
    full = encode_webp(frames, tmp_path / "full.webp", duration_ms=2000, max_bytes=10**7, width=320, fps=30,
                       plan=[(320, 30, 1.0)])
    lower = encode_webp(frames, tmp_path / "lower.webp", duration_ms=2000, max_bytes=full["bytes"] - 1,
                        width=320, fps=30, plan=[(320, 30, 1.0, 95), (320, 30, 1.0, 80)])
    assert lower["dimensions"] == [320, 180] and lower["fps"] == 30 and lower["time_scale"] == 1.0
    assert lower["quality"] == 80 and lower["motion_duration_ms"] == 2000


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


def test_block_spins_showcases_omit_refraction() -> None:
    variants = {case.variant for case in catalogue() if case.identity == "block_spins"}
    assert variants == {"off", "reflection"}



def test_visualizer_frames_crop_to_the_union_of_what_any_frame_draws(tmp_path):
    from PIL import Image
    from tools.release_media import VISUALIZER_BACKGROUND, content_box

    def frame(name, rect):
        image = Image.new("RGB", (200, 100), VISUALIZER_BACKGROUND)
        if rect:
            image.paste((255, 40, 200), rect)
        path = tmp_path / name
        image.save(path)
        return path

    frames = [frame("a.png", (50, 20, 80, 40)), frame("b.png", (90, 30, 120, 70)), frame("c.png", None)]
    left, top, right, bottom = content_box(frames, VISUALIZER_BACKGROUND, 0.02)
    assert (left, top) == (46, 16) and right >= 124 and bottom >= 74          # both frames' content plus 4 px
    assert (right - left) % 2 == 0 and (bottom - top) % 2 == 0
    assert content_box([frames[2]], VISUALIZER_BACKGROUND, 0.02) is None      # nothing drawn: no crop
    edge = content_box([frame("d.png", (0, 0, 10, 10))], VISUALIZER_BACKGROUND, 0.5)
    assert edge[:2] == (0, 0) and edge[2] <= 200 and edge[3] <= 100           # kept inside the frame


# --- Showcase camera parity: a preset is framed as the product frames it -----------------------------------------

def _framed_cases():
    from core.settings.framed_camera import spec_for_mode
    from core.settings.visualizer_presets import get_presets
    return [(case.identity, case.preset) for case in catalogue()
            if case.kind == "visualizer" and spec_for_mode(case.identity) is not None
            and get_presets(case.identity)[case.preset].starting_view is not None]


def _replay_activation_parameters(mode: str, preset: int, settings=None) -> dict:
    """The Visualizer parameters the showcase's replay activation hands the renderer, with no ticking."""
    from PySide6.QtGui import QGuiApplication
    from core.settings.framed_camera import spec_for_mode
    from tools.visualizer_replay.engine import ReplayBeatEngine
    from widgets.spotify_visualizer.config_applier import spec_mode_parameters
    from widgets.spotify_visualizer.feature_replay import configure_offline_controller
    from widgets.spotify_visualizer.runtime_controller import VisualizerRuntimeController

    QGuiApplication.instance() or QGuiApplication([])
    engine = ReplayBeatEngine(32)
    controller = VisualizerRuntimeController(runtime_generation=0, initial_mode=mode,
                                             engine_factory=lambda _count: engine)
    controller.engine = engine
    try:
        configure_offline_controller(controller, mode, preset, settings=settings)
        spec = spec_for_mode(mode)
        host = controller.presentation_state
        return {**spec_mode_parameters(host, mode), **{key: getattr(host, "_" + key) for key in spec.input_keys}}
    finally:
        controller.close_render_admission()
        engine.deleteLater()


def _camera(mode: str, parameters, presentation):
    """The physical eye, effective offset and vertical lens tangent a renderer would draw these through."""
    from core.settings.framed_camera import resolve_camera_frame, spec_for_mode, viewport_tangents
    from widgets.spotify_visualizer.presentation_geometry import framed_aperture_scale

    spec = spec_for_mode(mode)
    values = {key: parameters[key] for key in spec.input_keys}
    _axes, eye, offset = resolve_camera_frame(spec, values)
    tan_y = viewport_tangents(float(values[spec.key("camera_fov")]), 1.0, framed_aperture_scale(presentation))[1]
    return (*eye, *offset, tan_y)


def _default_card(mode: str):
    from core.settings.visualizer_mode_registry import get_visualizer_presentation_policy
    from widgets.spotify_visualizer.presentation_geometry import resolve_visualizer_presentation

    return resolve_visualizer_presentation(
        policy=get_visualizer_presentation_policy(mode), display_size=(1920.0, 1080.0),
        border_width=0.0, corner_radius=0.0, content_inset=0.0, background_color=(0, 0, 0, 0),
        border_color=(0, 0, 0, 0), shadow_enabled=False, shadow_color=(0, 0, 0, 0), shadow_blur=0.0,
        shadow_offset=(0.0, 0.0), shadow_spread=0.0, shadow_extensions=(0.0, 0.0, 0.0, 0.0))


def _product_camera(mode: str, preset: int):
    """The camera the product frames a selected preset with: the activation's resolved settings, the reset
    (Home) route's starting pose, and the canonical default card."""
    from core.settings.framed_camera import spec_for_mode
    from core.settings.visualizer_presets import resolve_visualizer_activation_payload
    from core.settings.visualizer_view_orbit import starting_camera_pose

    spec = spec_for_mode(mode)
    settings = resolve_visualizer_activation_payload({"mode": mode, f"preset_{mode}": preset}).resolved_config
    parameters = {key: settings[key] for key in spec.input_keys}
    parameters.update(starting_camera_pose(mode, preset))
    return _camera(mode, parameters, _default_card(mode))


def _assert_same_camera(left, right) -> None:
    assert len(left) == len(right)
    for a, b in zip(left, right):
        assert a == pytest.approx(b, abs=1e-6)


def test_showcase_frames_every_framed_preset_with_the_view_the_product_activates() -> None:
    from tools.release_media import showcase_presentation

    cases = _framed_cases()
    assert {mode for mode, _preset in cases}, "no framed mode authors a starting view"
    for mode, preset in cases:
        parameters = _replay_activation_parameters(mode, preset)
        _assert_same_camera(_camera(mode, parameters, showcase_presentation(mode, (1280, 720))),
                            _product_camera(mode, preset))


def test_showcase_camera_check_fails_without_the_starting_view_or_on_a_stretched_card() -> None:
    from core.settings.default_contract import require_canonical_default
    from core.settings.visualizer_mode_registry import get_visualizer_presentation_policy
    from core.settings.visualizer_presets import resolve_visualizer_activation_payload
    from core.settings.visualizer_view_orbit import starting_camera_pose
    from tools.release_media import showcase_presentation
    from widgets.spotify_visualizer.presentation_geometry import resolve_visualizer_presentation

    # A preset whose authored view is not the canonical home (otherwise dropping it proves nothing).
    cases = [(mode, preset) for mode, preset in _framed_cases()
             if any(value != require_canonical_default("widgets.spotify_visualizer." + key)
                    for key, value in starting_camera_pose(mode, preset).items())]
    assert cases, "every authored starting view equals the canonical home"
    mode, preset = cases[0]
    product = _product_camera(mode, preset)
    presentation = showcase_presentation(mode, (1280, 720))
    parameters = _replay_activation_parameters(mode, preset)
    _assert_same_camera(_camera(mode, parameters, presentation), product)       # the control the negatives differ from

    # Negative 1: the activation without its starting view (the pose leaves reset to canonical home).
    config = dict(resolve_visualizer_activation_payload({"mode": mode, f"preset_{mode}": preset}).resolved_config)
    for key in starting_camera_pose(mode, preset):
        config[key] = require_canonical_default("widgets.spotify_visualizer." + key)
    unposed = _replay_activation_parameters(mode, preset, settings=config)
    with pytest.raises(AssertionError):
        _assert_same_camera(_camera(mode, unposed, presentation), product)

    # Negative 2: the card's world extent enlarged instead of the card scaled (a taller sensor: a wider lens).
    stretched = resolve_visualizer_presentation(
        policy=get_visualizer_presentation_policy(mode), display_size=(1280, 720), viewport_extent=(896, 504),
        border_width=0, corner_radius=0, content_inset=0, background_color=(0, 0, 0, 0),
        border_color=(0, 0, 0, 0), shadow_enabled=False, shadow_color=(0, 0, 0, 0), shadow_blur=0,
        shadow_offset=(0, 0), shadow_spread=0, shadow_extensions=(0, 0, 0, 0))
    with pytest.raises(AssertionError):
        _assert_same_camera(_camera(mode, parameters, stretched), product)


def test_showcase_snapshot_changes_only_detail_backdrop_and_presentation() -> None:
    from PySide6.QtGui import QGuiApplication
    from widgets.spotify_visualizer.feature_frame import FeatureClip
    from tools.release_media import showcase_presentation, showcase_snapshot
    from tools.visualizer_replay.driver import load_clips, replay_clip

    QGuiApplication.instance() or QGuiApplication([])
    original = next(iter(load_clips().values()))
    clip = FeatureClip(original.name, original.frames[:6])
    mode, preset = next(case for case in _framed_cases() if case[0] == "extruded_bubble")
    snapshot = replay_clip(clip, mode, preset=preset, snapshots_at=(5,))["snapshots"][5]
    shown = showcase_snapshot(snapshot, showcase_presentation(mode, (1280, 720)))
    before, after = dict(snapshot.logical.mode_state.parameters), dict(shown.logical.mode_state.parameters)
    assert {key for key in after if after.get(key) != before.get(key)} <= {"scene3d_detail"}
    assert after["scene3d_detail"] == "High"
    assert shown.presentation is not snapshot.presentation
