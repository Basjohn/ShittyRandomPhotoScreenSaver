"""Registry-derived release/README WebPs through production offscreen render owners.

No settings writes, runtime window, audio device, environment override or runtime
clock. The existing deterministic recorded-feature replay owns Visualizer time.
Generated files belong in an explicit release evidence directory, outside QRCs.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass, replace
import hashlib
import io
import json
import math
from pathlib import Path
import re
import random
import sys

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

ROOT = Path(__file__).resolve().parents[1]
HOST_MAX_BYTES = 2 * 1024 ** 3 - 1
HOST_MAX_ASSETS = 1000
# WebP encoding: method 6 cost 11x the time of method 4 for 2% smaller files, and keyframes every
# 150 frames (delta frames between) roughly halved the bytes of mostly-still transition frames.
WEBP_METHOD = 4
WEBP_KEYFRAME_SPACING = 150
MANIFEST = "release_media.json"

# Operator transition showcase directive: every transition WebP is composed from the four
# operator-owned Usu scenes (Windows-local, never bundled), 480 px wide ("480p" means the width:
# 854x480 was far too large), smooth (60 fps first), strictly under 10,000,000 bytes. Its own
# ignored folder; never a normal GODZIP payload.
USU_SCENES = tuple(ROOT / "assets" / "usu" / "scenes" / f"UsuScene{index}.png" for index in range(1, 5))
TRANSITION_OUTPUT = ROOT / "assets" / "webp"
TRANSITION_WIDTH = 480
TRANSITION_FPS = 30
TRANSITION_QUALITY = 95
TRANSITION_CAPTURE_SCALE = 2           # captured at twice the published size, then downsampled
TRANSITION_MAX_BYTES = 10_000_000 - 1  # strictly below 10 MB (decimal)
TRANSITION_MID_HOLD_MS = 700           # the new picture rests before the run back starts
TRANSITION_LOOP_HOLD_MS = 350          # each loop end rests on the first picture (both ends meet)
# Every ordered pair of distinct scenes. Each generation picks a pair and the run there's seed
# at random (operator direction); the manifest records the pick, which does not stale an entry.
SCENE_PAIRS = tuple((a, b) for a in range(4) for b in range(4) if a != b)


def pick_showcase(rng: random.Random) -> tuple[tuple[int, int], int]:
    """A random (first, second) scene pair and a random seed for the run there."""
    return rng.choice(SCENE_PAIRS), rng.randrange(1, 2 ** 31)


def transition_size(aspect: float = 16 / 9) -> tuple[int, int]:
    """The published transition size: 480 px wide, height from the composition's aspect (even)."""
    return TRANSITION_WIDTH, round(TRANSITION_WIDTH / aspect / 2) * 2


def load_scenes(paths=USU_SCENES) -> tuple:
    """The four scenes, read once. Missing originals fail loudly: never a substitute."""
    from PIL import Image

    missing = [str(path) for path in paths if not Path(path).is_file()]
    if missing:
        raise FileNotFoundError(f"operator Usu scene originals are missing (never substituted): {missing}")
    scenes = []
    for path in paths:
        with Image.open(path) as image:
            scenes.append(image.convert("RGB"))
    return tuple(scenes)


def fit_scene(scene, size: tuple[int, int]):
    """The scene cropped (never stretched) to the composition, keeping its aspect ratio."""
    from PIL import Image, ImageOps

    return ImageOps.fit(scene, size, Image.Resampling.LANCZOS, centering=(0.5, 0.5))


class SourceChangedError(RuntimeError):
    """A batch cannot continue with different source/recording bytes."""


@dataclass(frozen=True)
class MediaCase:
    kind: str
    identity: str
    variant: str
    label: str
    preset: int | None = None
    settings: dict | None = None
    duration_ms: int = 4000
    preset_file: str | None = None

    @property
    def key(self) -> str:
        return f"{self.kind}/{self.identity}/{self.variant}"

    @property
    def filename(self) -> str:
        return "_".join((self.kind, self.identity, self.variant)) + ".webp"


def catalogue() -> list[MediaCase]:
    from core.settings.default_contract import require_canonical_default
    from core.settings.visualizer_mode_registry import iter_visualizer_mode_descriptors
    from core.settings.visualizer_presets import get_presets, get_preset_file_path
    from rendering.transition_registry import iter_transition_descriptors
    from rendering.gl_programs.blinds_options import BLINDS_STYLE_CHOICES
    from rendering.gl_programs.blockspin_options import BLOCK_SPIN_EDGE_GLASS_CHOICES

    cases = []
    durations = require_canonical_default("transitions.durations")
    for descriptor in iter_transition_descriptors():
        if not descriptor.available:
            continue
        identity = descriptor.stable_id
        variants = [("default", "Canonical", {})]
        if identity == "blinds":
            variants = [(_slug(value), value, {"blinds": {"style": value}}) for value in BLINDS_STYLE_CHOICES]
        elif identity == "block_spins":
            variants = [(_slug(value), value, {"blockspin": {"edge_glass": value}})
                        for value in BLOCK_SPIN_EDGE_GLASS_CHOICES]
        for variant, label, settings in variants:
            cases.append(MediaCase("transition", identity, variant, label, settings=settings,
                                   duration_ms=int(durations[descriptor.setting_name])))
    for descriptor in iter_visualizer_mode_descriptors():
        for index, preset in enumerate(get_presets(descriptor.mode_id)):
            if preset.is_custom:
                continue
            path = get_preset_file_path(descriptor.mode_id, index)
            if path is None:
                raise ValueError(f"missing authored preset path: {descriptor.mode_id}:{index}")
            cases.append(MediaCase("visualizer", descriptor.mode_id, _slug(path.stem), preset.name,
                                   preset=index, preset_file=str(path.resolve())))
    names = [case.filename for case in cases]
    if len(names) != len(set(names)):
        raise ValueError("catalogue filename collision")
    return cases


def _slug(value: str) -> str:
    result = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    if not result:
        raise ValueError("empty media identity")
    return result


def load_recording(path: Path, *, start_seconds: float, duration_seconds: float, data: bytes | None = None):
    from widgets.spotify_visualizer.feature_frame import FeatureClip, load_jsonl
    from tools.visualizer_replay.record import OUTPUT

    # Only canonical operator recordings are accepted; archive takes and synthetic
    # golden fixtures must not silently become release music evidence.
    if path.resolve().parent != OUTPUT.resolve() or re.search(r"_(noevents|v\d+)$", path.stem):
        raise ValueError("clip must be a canonical recording under logs/visualizer_recordings")
    clip = load_jsonl(path) if data is None else FeatureClip.from_jsonl_bytes(path.stem, data)
    if any(frame.schema_version != 2 or frame.real is None for frame in clip.frames):
        raise ValueError("release Visualizer captures require schema-2 recorded music")
    origin = clip.frames[0].timestamp_us
    stop = origin + round((start_seconds + duration_seconds) * 1e6)
    if stop > clip.frames[-1].timestamp_us:
        raise ValueError("recording is shorter than the selected interval")
    # Replay the pre-roll too: do not reset logical state at the selected passage.
    return FeatureClip(clip.name, tuple(frame for frame in clip.frames if frame.timestamp_us <= stop))


def sample_indices(clip, start_seconds: float, duration_seconds: float, fps: int) -> tuple[int, ...]:
    import bisect
    timestamps = [frame.timestamp_us for frame in clip.frames]
    origin = timestamps[0] + round(start_seconds * 1e6)
    indices = tuple(bisect.bisect_left(timestamps, origin + round(index * 1e6 / fps))
                    for index in range(max(2, round(duration_seconds * fps))))
    if any(index >= len(timestamps) or not clip.frames[index].visible for index in indices):
        raise ValueError("recording has missing/hidden frames in selected capture interval")
    return indices


def transition_spec(identity: str, duration_ms: int, settings: dict | None = None, seed: int = 713):
    """Use the complete production resolver, including non-Phase-C identities."""
    from core.settings.default_contract import require_canonical_default
    from rendering.transition_registry import get_transition_descriptor
    from rendering.quick.transitions.request_resolution import resolve_quick_transition_spec

    descriptor = get_transition_descriptor(identity)
    if descriptor is None or not descriptor.available:
        raise ValueError(f"unavailable transition {identity}")
    defaults = require_canonical_default("transitions")
    values = {**defaults, **(settings or {}), "type": descriptor.setting_name, "random_always": False,
              "activation": {**defaults["activation"], descriptor.setting_name: True},
              "durations": {**defaults["durations"], descriptor.setting_name: duration_ms}}

    class CaptureInput:
        def get(self, key, default=None):
            if key == "transitions":
                return values
            if key == "scene3d.detail":
                return "High"
            return require_canonical_default(key)

    spec = resolve_quick_transition_spec(CaptureInput(), random_source=random.Random(seed))
    if spec is None or spec.transition_id != identity:
        raise ValueError(f"production resolver did not admit selected transition {identity}")
    return spec


def _transition_run(capture, identity: str, duration_ms: int, settings=None, seed: int = 713):
    from rendering.quick.image_state import PresentationImage
    from rendering.quick.transitions.state import TransitionRun

    images = [PresentationImage(str(index), "release_capture", (capture.width, capture.height), 1.,
                                (capture.width, capture.height), capture.width * 4, image.tobytes())
              for index, image in enumerate(capture.images)]
    request = transition_spec(identity, duration_ms, settings, seed).build_request(
        runtime_generation=0, source_image=images[0], destination_image=images[1])
    return TransitionRun.start(run_id=1, request=request, start_ns=0)


def _look(spec) -> tuple:
    """What a viewer sees as a run's direction: its resolved direction, origin or order."""
    parameters = dict(spec.parameters)
    return spec.direction, parameters.get("order"), parameters.get("origin")


def return_seed(case: "MediaCase", duration_ms: int, seed: int, tries: int = 64) -> int:
    """A seed for the showcase's run back whose direction/order differs from the run there.

    The same direction twice in a row reads as a mistake; a transition with no direction choice
    keeps the first seed tried."""
    there = _look(transition_spec(case.identity, duration_ms, case.settings, seed))
    for candidate in range(seed + 1, seed + 1 + tries):
        if _look(transition_spec(case.identity, duration_ms, case.settings, candidate)) != there:
            return candidate
    return seed + 1


def capture_transition_loop(case: "MediaCase", directory: Path, *, size: tuple[int, int], fps: int,
                            duration_ms: int, scenes, pair: tuple[int, int], seed: int) -> list[Path]:
    """One looping showcase: first -> second, a rest on the second, then second -> first in another
    direction/order. Frames sample the whole timeline at ``fps``; the encoder adds the loop's rest on
    the first picture at both ends. Both runs' endpoints must be their photographs exactly."""
    from tools.transition_contact_sheet import TransitionCapture

    first, second = (fit_scene(scenes[index], size) for index in pair)
    directory.mkdir(parents=True, exist_ok=False)
    run_frames = max(2, round(duration_ms * fps / 1000) + 1)
    hold_frames = max(1, round(TRANSITION_MID_HOLD_MS * fps / 1000))
    frames: list[Path] = []

    def save(image) -> None:
        path = directory / f"{len(frames):06d}.png"
        image.save(path)
        frames.append(path)

    legs = ((first, second, seed), (second, first, return_seed(case, duration_ms, seed)))
    for leg, (source, destination, seed) in enumerate(legs):
        capture = TransitionCapture(size[0], size[1], source=source, destination=destination)
        try:
            run = _transition_run(capture, case.identity, duration_ms, case.settings, seed)
            for index in range(run_frames):
                if leg and index == 0:
                    continue                      # the second run starts on the rest's last frame
                image, _ = capture.render(run, index / (run_frames - 1))
                if index in (0, run_frames - 1):
                    endpoint = capture.images[0 if index == 0 else 1]
                    if image.tobytes() != endpoint.tobytes():
                        raise RuntimeError("production transition endpoint does not match its photograph")
                save(image)
                if not leg and index == run_frames - 1:
                    for _ in range(hold_frames):
                        save(image)
        finally:
            capture.close()
    return frames


def transition_timeline_ms(duration_ms: int) -> int:
    """The looping showcase's motion timeline (both runs and the rest between them)."""
    return 2 * duration_ms + TRANSITION_MID_HOLD_MS


def capture_frames(case: MediaCase, directory: Path, *, size: tuple[int, int], fps: int,
                   duration_ms: int, clip=None, start_seconds: float = 0) -> list[Path]:
    from tools.transition_contact_sheet import TransitionCapture
    from PIL import Image

    width, height = size
    directory.mkdir(parents=True, exist_ok=False)
    capture = TransitionCapture(width, height)
    frames = []
    host = None
    try:
        if case.kind == "transition":
            run = _transition_run(capture, case.identity, duration_ms, case.settings)
            count = max(2, round(duration_ms * fps / 1000) + 1)
            for index in range(count):
                image, _ = capture.render(run, index / (count - 1))
                if index in (0, count - 1):
                    endpoint = capture.images[0 if index == 0 else 1]
                    if image.tobytes() != endpoint.tobytes():
                        raise RuntimeError("production transition endpoint does not match its photograph")
                path = directory / f"{index:06d}.png"
                image.save(path)
                frames.append(path)
        else:
            from OpenGL import GL as gl
            from rendering.quick.visualizer.render_host import QuickVisualizerRenderHost
            from widgets.spotify_visualizer.render_state import freeze_render_fields
            from widgets.spotify_visualizer.presentation_geometry import resolve_visualizer_presentation
            from core.settings.visualizer_mode_registry import get_visualizer_presentation_policy, get_visualizer_mode_descriptor
            from widgets.spotify_visualizer.backdrop import VisualizerBackdrop
            from tools.visualizer_replay.driver import replay_clip

            if clip is None:
                raise ValueError("recorded clip required for Visualizer capture")
            indices = sample_indices(clip, start_seconds, duration_ms / 1000, fps)
            result = replay_clip(clip, case.identity, preset=case.preset, snapshots_at=indices)
            host = QuickVisualizerRenderHost()
            photo = _transition_run(capture, "crossfade", duration_ms)
            descriptor = get_visualizer_mode_descriptor(case.identity)
            backdrop = VisualizerBackdrop(identity="release_transition_fixture", size=size,
                                          rgba=capture.images[0].tobytes())
            item_width, item_height = width * .7, height * .7
            presentation = resolve_visualizer_presentation(
                policy=get_visualizer_presentation_policy(case.identity), display_size=(width, height),
                viewport_extent=(item_width, item_height), border_width=0, corner_radius=0, content_inset=0,
                background_color=(0, 0, 0, 0), border_color=(0, 0, 0, 0), shadow_enabled=False,
                shadow_color=(0, 0, 0, 0), shadow_blur=0, shadow_offset=(0, 0), shadow_spread=0,
                shadow_extensions=(0, 0, 0, 0))
            matrix = (2 / width, 0, 0, 0, 0, -2 / height, 0, 0, 0, 0, 1, 0, -.7, .7, 0, 1)
            for ordinal, index in enumerate(indices):
                snapshot = result["snapshots"].get(index)
                if snapshot is None:
                    raise RuntimeError(f"production replay did not publish snapshot {index}")
                state = snapshot.logical.mode_state
                parameters = {**dict(state.parameters), "scene3d_detail": "High"}
                if descriptor.backdrop_setting:
                    parameters["backdrop"] = backdrop
                state = replace(state, parameters=freeze_render_fields(parameters))
                snapshot = replace(snapshot, presentation=presentation,
                                   logical=replace(snapshot.logical, mode_state=state))
                gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, capture.fbo)
                gl.glViewport(0, 0, width, height)
                gl.glDisable(gl.GL_SCISSOR_TEST)
                gl.glDepthMask(gl.GL_TRUE)
                gl.glClear(gl.GL_COLOR_BUFFER_BIT | gl.GL_DEPTH_BUFFER_BIT)
                capture.host.render(capture.frame(photo, 0))
                host.render(snapshot=snapshot, viewport=(0, 0, width, height),
                            logical_size=(item_width, item_height), matrix_values=matrix)
                pixels = gl.glReadPixels(0, 0, width, height, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE)
                image = Image.frombytes("RGBA", size, bytes(pixels)).transpose(Image.Transpose.FLIP_TOP_BOTTOM)
                path = directory / f"{ordinal:06d}.png"
                image.save(path)
                frames.append(path)
                if gl.glGetError() != gl.GL_NO_ERROR:
                    raise RuntimeError("Visualizer capture GL error")
    finally:
        if host is not None:
            host.release_resources()
        capture.close()
    return frames


def transition_encoding_plan(width: int, fps: int) -> list[tuple[int, int, float]]:
    """Transition showcases keep their width and frame rate: a long run plays a little faster
    first (operator direction: 480 wide at 30 fps), and only then does the frame rate drop."""
    plan = [(width, fps, scale) for scale in (1.0, .85, .72, .6)]
    return plan + [(width, max(10, round(fps * step)), .6) for step in (.8, .67)]


def timeline_source_indices(source_count: int, motion_ms: int, hold_ms: int, count: int) -> list[int]:
    """The source frame each of ``count`` output frames shows: a rest of ``hold_ms`` on the first
    frame, the motion spread over ``motion_ms``, a rest on the last frame.

    Rounds halves up, never to even: a 350 ms rest is exactly 10.5 frames at 30 fps, and
    ``round()`` then showed every other source frame twice (motion played at 15 fps)."""
    total = motion_ms + 2 * hold_ms
    indices = []
    for index in range(count):
        if hold_ms:
            at = max(0.0, min(motion_ms, index * total / count - hold_ms))
            position = at / motion_ms * (source_count - 1)
        else:
            position = index * (source_count - 1) / max(count - 1, 1)
        indices.append(min(source_count - 1, math.floor(position + 0.5 + 1e-9)))
    return indices


def encode_webp(frames: list[Path], output: Path, *, duration_ms: int, max_bytes: int,
                width: int, fps: int, hold_ms: int = 0, fps_steps: tuple[float, ...] = (1.0, .75, .5),
                quality: int = 92, plan: list[tuple[int, int, float]] | None = None) -> dict:
    """Encode the lossless capture with the first (width, fps, time scale) attempt under budget.

    Without a ``plan`` the width steps down (x0.75, x0.5) and inside each width the frame rate
    steps by ``fps_steps``; a time scale below 1 plays the motion faster (holds keep their length).
    Quality never drops. All candidates come from the same lossless high-resolution capture."""
    from PIL import Image

    if (not frames or not 0 < duration_ms <= 60000 or not 0 <= hold_ms <= 1000 or not 50 <= quality <= 100 or not 0 < max_bytes <= HOST_MAX_BYTES
            or not 10 <= fps <= 60 or width < 160):
        raise ValueError("invalid encoding budget/dimensions/fps")
    if plan is None:
        widths = list(dict.fromkeys([width, max(160, round(width * .75)), max(160, round(width * .5))]))
        rates = list(dict.fromkeys(max(10, round(fps * step)) for step in fps_steps))
        plan = [(target, rate, 1.0) for target in widths for rate in rates]
    attempts = []
    with Image.open(frames[0]) as first:
        source_size = first.size
    for target_width, rate, scale in plan:
        if target_width < 160 or not 10 <= rate <= 60 or not 0 < scale <= 1:
            raise ValueError("invalid encoding attempt")
        target_size = (target_width, max(1, round(source_size[1] * target_width / source_size[0])))
        motion_ms = max(1, round(duration_ms * scale))
        total_duration_ms = motion_ms + 2 * hold_ms
        count = max(2, round(total_duration_ms * rate / 1000))
        images = []
        try:
            for source_index in timeline_source_indices(len(frames), motion_ms, hold_ms, count):
                with Image.open(frames[source_index]) as source:
                    image = source.convert("RGB").resize(target_size, Image.Resampling.LANCZOS)
                    image.info.clear()
                    images.append(image)
            durations = [round((i + 1) * total_duration_ms / count) - round(i * total_duration_ms / count) for i in range(count)]
            stream = io.BytesIO()
            images[0].save(stream, format="WEBP", save_all=True, append_images=images[1:],
                           duration=durations, loop=0, quality=quality, method=WEBP_METHOD,
                           kmin=WEBP_KEYFRAME_SPACING - 1, kmax=WEBP_KEYFRAME_SPACING,
                           exif=b"", icc_profile=b"", xmp=b"")
            data = stream.getvalue()
        finally:
            for image in images:
                image.close()
        attempts.append({"width": target_width, "fps": rate, "time_scale": scale, "bytes": len(data)})
        if len(data) <= max_bytes:
            with Image.open(io.BytesIO(data)) as encoded:
                if not encoded.is_animated or encoded.info.get("loop") != 0:
                    raise ValueError("capture encoded as a still image, not an infinite animation")
                if any(encoded.info.get(key) for key in ("exif", "icc_profile", "xmp")):
                    raise ValueError("unexpected encoded metadata")
            output.write_bytes(data)
            return {"dimensions": list(target_size), "fps": rate, "duration_ms": total_duration_ms,
                    "motion_duration_ms": motion_ms, "endpoint_hold_ms": hold_ms, "time_scale": scale,
                    "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(),
                    "quality": quality, "loop": 0, "attempts": attempts}
    raise ValueError(f"media exceeds byte budget at retained quality: {attempts}")


def fingerprint(case: MediaCase, provenance: dict, options: dict, clip_hash: str | None) -> str:
    payload = {"case": vars(case), "source": provenance.get("source_tree_sha256"),
               "options": options, "clip": clip_hash}
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def is_current(entry: dict, digest: str, output: Path) -> bool:
    return (entry.get("fingerprint") == digest and output.is_file()
            and hashlib.sha256(output.read_bytes()).hexdigest() == entry.get("sha256"))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--kind", choices=("transition", "visualizer"))
    parser.add_argument("--id")
    parser.add_argument("--variant")
    parser.add_argument("--clip", type=Path)
    parser.add_argument("--start-seconds", type=float, default=0)
    parser.add_argument("--duration-seconds", type=float)
    parser.add_argument("--capture-width", type=int, default=1280)
    parser.add_argument("--width", type=int, default=960)
    parser.add_argument("--fps", type=int, default=30)
    parser.add_argument("--max-bytes", type=int, default=10 * 1024 ** 2)
    args = parser.parse_args(argv)
    transitions_only = args.kind == "transition"
    if transitions_only and args.output_dir is None and not args.list:
        args.output_dir = TRANSITION_OUTPUT
    from tools.run_matrix import _source_attribution
    provenance = _source_attribution() if not args.list else None
    if provenance is not None:
        provenance["captured"] = "before_catalogue"
    cases = [case for case in catalogue() if (not args.kind or args.kind == case.kind)
             and (not args.id or args.id == case.identity) and (not args.variant or args.variant == case.variant)]
    if not cases:
        parser.error("selection matched no canonical media case")
    if args.list:
        print(json.dumps([vars(case) for case in cases], indent=2))
        return 0
    if args.output_dir is None:
        parser.error("--output-dir is required for generation")
    if (not math.isfinite(args.start_seconds) or args.start_seconds < 0
            or args.duration_seconds is not None and (not math.isfinite(args.duration_seconds) or not 0 < args.duration_seconds <= 30)
            or not 160 <= args.width <= args.capture_width <= 3840 or not 10 <= args.fps <= 60
            or not 0 < args.max_bytes <= HOST_MAX_BYTES):
        parser.error("invalid capture bounds")
    output = args.output_dir.resolve()
    if (output == ROOT or output == ROOT / "logs"
            or ROOT in output.parents and ROOT / "logs" not in output.parents and output != TRANSITION_OUTPUT):
        parser.error("repository captures must use assets/webp (transitions) or a dedicated ignored logs "
                     "subdirectory; external release directories are allowed")
    if output == TRANSITION_OUTPUT and not transitions_only:
        parser.error("assets/webp holds transition showcases only (--kind transition)")
    scenes = None
    scene_hashes = None
    if any(case.kind == "transition" for case in cases):
        scenes = load_scenes()
        scene_hashes = [hashlib.sha256(path.read_bytes()).hexdigest() for path in USU_SCENES]
    output.mkdir(parents=True, exist_ok=True)
    manifest_path = output / MANIFEST
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {"schema_version": 1, "entries": {}}
    if type(manifest.get("schema_version")) is not int or manifest["schema_version"] != 1 or not isinstance(manifest.get("entries"), dict):
        parser.error("unsupported media manifest")
    if len(set(manifest["entries"]) | {case.key for case in cases}) > HOST_MAX_ASSETS:
        parser.error("media selection exceeds the GitHub release asset count limit")
    if provenance["unavailable"]:
        parser.error(f"source attribution unavailable: {provenance['unavailable']}")
    failures = []
    batch_clip_hash = None
    for case_index, case in enumerate(cases):
        try:
            current_source = _source_attribution()
            current_source["captured"] = "before_capture"
            if current_source["unavailable"] or current_source.get("source_tree_sha256") != provenance.get("source_tree_sha256"):
                raise SourceChangedError(f"source unavailable/changed during catalogue generation; rerun at a stable checkpoint: {current_source['unavailable']}")
            duration_ms = round(args.duration_seconds * 1000) if args.duration_seconds else case.duration_ms
            hold_ms = TRANSITION_LOOP_HOLD_MS if case.kind == "transition" else 0
            clip = None
            clip_hash = None
            if case.kind == "visualizer":
                if args.clip is None:
                    raise ValueError("--clip canonical schema-2 recorded music is required")
                clip_bytes = args.clip.read_bytes()
                clip = load_recording(args.clip, start_seconds=args.start_seconds, duration_seconds=duration_ms / 1000,
                                      data=clip_bytes)
                clip_hash = hashlib.sha256(clip_bytes).hexdigest()
                if batch_clip_hash is not None and batch_clip_hash != clip_hash:
                    raise SourceChangedError("recorded clip changed between cases; rerun with stable recorded input")
                batch_clip_hash = clip_hash
            if case.kind == "transition":
                width, height = transition_size()
                capture_size = (width * TRANSITION_CAPTURE_SCALE, height * TRANSITION_CAPTURE_SCALE)
                max_bytes = min(args.max_bytes, TRANSITION_MAX_BYTES)
                pair, seed = pick_showcase(random.SystemRandom())
                options = {"capture_size": list(capture_size), "width": width, "fps": TRANSITION_FPS,
                           "quality": TRANSITION_QUALITY, "max_bytes": max_bytes, "duration_ms": duration_ms,
                           "endpoint_hold_ms": hold_ms, "mid_hold_ms": TRANSITION_MID_HOLD_MS,
                           "scene_sha256": scene_hashes}
            else:
                width, max_bytes = args.width, args.max_bytes
                capture_size = (args.capture_width, round(args.capture_width * 9 / 16))
                options = {"capture_width": args.capture_width, "width": args.width, "fps": args.fps,
                           "max_bytes": args.max_bytes, "duration_ms": duration_ms, "start_seconds": args.start_seconds,
                           "endpoint_hold_ms": hold_ms}
            digest = fingerprint(case, current_source, options, clip_hash)
            entry = manifest["entries"].get(case.key, {})
            target = output / case.filename
            if target.exists() and not entry:
                raise ValueError(f"refusing to overwrite media outside manifest ownership: {target}")
            if is_current(entry, digest, target):
                print(f"CURRENT {case.key}", flush=True)
                continue
            import tempfile
            with tempfile.TemporaryDirectory(prefix="capture_", dir=output) as temporary:
                encoded = Path(temporary) / "encoded.webp"
                if case.kind == "transition":
                    frames = capture_transition_loop(case, Path(temporary) / "frames", size=capture_size,
                                                     fps=TRANSITION_FPS, duration_ms=duration_ms, scenes=scenes,
                                                     pair=pair, seed=seed)
                    # Reduce the frame rate before the size, and the size before any quality.
                    metadata = encode_webp(frames, encoded, duration_ms=transition_timeline_ms(duration_ms),
                                           max_bytes=max_bytes, width=width, fps=TRANSITION_FPS, hold_ms=hold_ms,
                                           quality=TRANSITION_QUALITY,
                                           plan=transition_encoding_plan(width, TRANSITION_FPS))
                    metadata["scene_pair"], metadata["seeds"] = list(pair), [seed, return_seed(case, duration_ms, seed)]
                else:
                    frames = capture_frames(case, Path(temporary) / "frames", size=capture_size, fps=args.fps,
                                            duration_ms=duration_ms, clip=clip, start_seconds=args.start_seconds)
                    metadata = encode_webp(frames, encoded, duration_ms=duration_ms, max_bytes=max_bytes,
                                           width=width, fps=args.fps, hold_ms=hold_ms)
                after_source = _source_attribution()
                after_source["captured"] = "after_capture"
                if after_source["unavailable"] or after_source.get("source_tree_sha256") != current_source.get("source_tree_sha256"):
                    raise SourceChangedError("source changed during capture; artifact discarded, rerun at a stable checkpoint")
                if clip is not None and hashlib.sha256(args.clip.read_bytes()).hexdigest() != clip_hash:
                    raise SourceChangedError("recorded clip changed during capture; artifact discarded")
                target.write_bytes(encoded.read_bytes())
            manifest["entries"][case.key] = {**vars(case), **metadata, "file": case.filename,
                                             "fingerprint": digest, "source": current_source,
                                             "source_after": after_source,
                                             "clip": (str(args.clip.resolve()) if clip is not None else
                                                      "usu_scenes:" + "->".join(USU_SCENES[i].name for i in pair)
                                                      if case.kind == "transition" else None),
                                             "clip_sha256": clip_hash, "start_seconds": args.start_seconds}
            manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
            print(f"GENERATED {case.key}: {metadata['bytes']} bytes, {metadata['dimensions']} at {metadata['fps']} fps, "
                  f"quality {metadata['quality']}, {len(metadata['attempts'])} encoding attempts", flush=True)
        except Exception as exc:
            failure = {"case": case.key, "error": str(exc)}
            if isinstance(exc, SourceChangedError):
                failure["unattempted"] = [pending.key for pending in cases[case_index + 1:]]
            failures.append(failure)
            print(f"FAILED {case.key}: {exc}", file=sys.stderr, flush=True)
            if isinstance(exc, SourceChangedError):
                print("ABORTED remaining cases because batch inputs changed", file=sys.stderr, flush=True)
                break
    (output / "release_media_failures.json").write_text(json.dumps(failures, indent=2) + "\n")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
