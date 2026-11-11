"""Rendered parity of the production owner, the engine worker against in process, at non-default settings
(native core P2: the design's gate 2 "no visual change", phase-boundary audit M4).

    python tools/visualizer_replay/owner_render_parity.py --out <dir> [--modes ...] [--variants a b]
        [--sampling single product] [--seconds 5.5] [--skip-controls]

``owner_worker_gate``'s identity gate compares the logical frames the real ``QuickDisplayVisualizerOwner`` publishes
to its render bridge on the two process paths, by the digest of each frame's ``repr``, at preset 0. This gate
compares what those frames *draw*, at settings no shipped default has:

- **Non-default settings** (``nondefault_settings``): every Slider, Range, Choice, Toggle, Colour and Triangle of the
  mode's canonical spec (``visualizer_mode_settings``) moved off wherever it sits, derived from the spec (never a
  preset's or a default's value), activated as the mode's Custom preset through the host binding's own activation
  resolution. Two variants: ``a`` (37% of each admitted range, each Choice's second offer, every Toggle on) and ``b``
  (71%, each Choice's last offer, every Toggle off). The mode the script switches to is non-default the same way.
  Path, camera-position, gradient and Studio-record controls keep their resting values.
- **The script** (``parity_script``): ``owner_worker_gate.identity_script`` (play, a warm pause, a park, a mode switch
  through the owner's crossfade) with the presentation inputs the capture reads laid over it: a reflected photograph
  from the start for the reflecting modes and a held-key orbit for the 3D modes.
- **Rendered pixels** (``SceneMirror``): the production ``DisplayScene.qml``, ``QuickSceneController``,
  ``VisualizerRenderItem`` and mode render node drawn through ``QQuickRenderControl`` into a hidden GL texture
  (``expanded_visualizer_evidence.HiddenDisplayHost``: the window is never shown or mapped). The owner's own unshown
  scene forwards the calls that decide what is drawn (the render source it binds, each presentation record it
  commits, each present request, a retained-frame drop) to that scene, which is therefore the single consumer of
  the owner's real render bridge. Every input's presentation is drawn and read back, on both paths, in the same order (a render node's GPU
  state, such as Extruded Bubble's drift solve, advances with the frames drawn), and compared over the card and the
  margin its shadow can reach; every ``FULL_EVERY``-th frame is also hashed over the whole display.

**Sampling.** The 3D modes draw through a multisampled scene target at the 3D Detail tiers that have overlay samples
(``rendering/gl_programs/scene3d.py``). Measured here (11 Nov 2026, RTX-class NVIDIA): a multisampled target is not
bit-reproducible draw to draw. The same retained snapshot drawn again in one process, in process, changes single
pixels by one 8-bit level (Neon Lake: about 1,200 of 390,931 pixels a redraw; Extruded Bubble and Voxel Sphere: one
or two pixels in a few percent of frames), with bloom off, light shafts off and a ``glFinish`` before each read alike;
with one sample per pixel every redraw is identical. So the difference is the multisampled rasterisation of the
mode's own passes on this GPU, on either process path, and no pixel oracle can be exact through it.

- ``single``: every scene target opened with one sample for the run (``single_sample_scene_targets``: the sample
  count ``SceneTarget.begin`` is given, nothing else, so every pass, program, post effect and tier property is drawn
  as the product draws it). **The gate is exact here:** every frame's pixels equal on the two paths.
- ``product``: the tier as resolved for this GPU. A mode whose in-process run repeats exactly (the 2D modes) must
  be exact. A mode whose in-process run does not repeat is reported against that repeat: the differing frames, the
  most pixels differing in one frame and the largest level difference, worker against in process beside in process
  against itself, and it fails if the paths differ by more levels than the same path differs from itself.

Gate (per mode, variant and sampling): the two paths drew the same number of frames over equal regions, the pixels
are equal as above, the logical digests are equal, the worker path stayed on the worker, and the drawn frames changed
over the run and lit the card (a blank card would be equal on any two paths). On a difference both paths' frames of
the first differing input are written beside an amplified difference map.

Controls (``--skip-controls`` omits them): the in-process run repeated (``single``: identical to itself, the
oracle's noise floor is zero), and the mode's Sliders moved a further step must change the drawn frames (the
oracle sees a Settings change; ``single`` only).

Offscreen GL on this machine's GPU: not physical acceptance (no real window, display timing, device or load).
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import sys
import time
import zlib
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import artifact_paths  # noqa: E402

#: The rig's display (``owner_production_replay._Host``'s bounds), logical pixels.
DISPLAY = (1920, 1080)
#: Device pixels around the card that the per-frame comparison covers (its shadow and border antialiasing).
REGION_MARGIN = 64
#: Every this-many frames the whole display is hashed, not only the card's region.
FULL_EVERY = 30
#: variant: (share of each admitted range, Choice index (-1: the last), Toggle state, Colour, Triangle shares).
VARIANTS = {"a": (0.37, 1, True, [208, 96, 48, 255], [0.5, 0.3, 0.2]),
            "b": (0.71, -1, False, [48, 168, 224, 255], [0.2, 0.3, 0.5])}
SAMPLINGS = ("single", "product")
#: A drawn frame counts as lit when this share of the card's region is brighter than ``LIT_LEVEL`` (0-255).
LIT_LEVEL = 24
#: The scene commands of the owner that decide what its retained item draws; each is forwarded to the hidden scene.
FORWARDED = ("set_visualizer_render_source", "apply_visualizer_presentation", "request_visualizer_present",
             "drop_visualizer_retained_frame")


def nondefault_settings(mode: str, variant: str = "a", *, nudge: bool = False) -> dict:
    """Settings-section values moving every spec control of ``mode`` off its resting value, as its Custom preset.

    Derived from the canonical spec only. ``nudge`` moves every non-integer Slider a further 20% of its admitted
    range (the sensitivity control: a Settings change the drawn frames must show).
    """
    from core.settings.visualizer_mode_settings import (
        Choice, Colour, Range, Slider, Toggle, Triangle, require_mode_settings,
    )
    from core.settings.visualizer_presets import get_custom_preset_index

    fraction, choice_index, toggles, colour, shares = VARIANTS[variant]
    result: dict = {}
    for control in require_mode_settings(mode).controls:
        if isinstance(control, (Slider, Range)):
            high = getattr(control, "admission_high", None)
            high = control.high if high is None else high
            low = getattr(control, "admission_low", None)
            low = control.low if low is None else low
            share = fraction + (0.2 if nudge and isinstance(control, Slider) and not control.integer else 0.0)
            value = low + (high - low) * share
            if control.integer:
                value = round(value)
            result[control.key] = [value, value] if isinstance(control, Range) else value
        elif isinstance(control, Choice):
            index = min(choice_index, len(control.choices) - 1) if choice_index >= 0 else len(control.choices) - 1
            result[control.key] = index if control.indexed else control.choices[index]
        elif isinstance(control, Toggle):
            result[control.key] = bool(toggles)
        elif isinstance(control, Colour):
            result[control.key] = list(colour)
        elif isinstance(control, Triangle):
            result[control.key] = list(shares)
    result[f"preset_{mode}"] = get_custom_preset_index(mode)
    return result


def section_settings(mode: str, variant: str, *, nudge: bool = False) -> dict:
    """The rig's Settings-section overlay: ``mode`` and the mode its script switches to, both non-default."""
    from tools.visualizer_replay import owner_worker_gate as gate

    partner = gate.PARTNER.get(mode, "spectrum")
    return {**nondefault_settings(partner, variant), **nondefault_settings(mode, variant, nudge=nudge)}


def parity_script(clip_frames, mode: str) -> list:
    """``identity_script`` with the presentation inputs the capture reads: a reflected photograph from the start (a
    reflecting mode), a held-key orbit from 0.5 s to 1.2 s (a 3D mode), before the pause, the park and the switch."""
    from tools.visualizer_replay import owner_worker_gate as gate

    script = gate.identity_script(clip_frames, mode)
    start = next(value for kind, value in script if kind == "input").timestamp_us
    out: list = [("reflect", True)] if mode in gate.REFLECTING_MODES else []
    orbit = mode in gate.VIEW_MODES
    began = ended = not orbit
    for kind, value in script:
        if kind == "input":
            elapsed = (value.timestamp_us - start) / 1e6
            if not began and elapsed >= 0.5:
                out.append(("orbit", (1.0, 0.5)))
                began = True
            if not ended and elapsed >= 1.2:
                out.append(("orbit", None))
                ended = True
        out.append((kind, value))
    return out


@contextlib.contextmanager
def single_sample_scene_targets():
    """Every scene target opened single-sampled, for the block: ``SceneTarget.begin`` takes one sample whatever its
    caller asks for (a tier's overlay samples, Waveform Ribbon's fixed four). Nothing else about a draw changes: the
    same passes, programs, post chain and tier."""
    from rendering.quick.scene3d.target import SceneTarget

    begin = SceneTarget.begin

    def single(self, frame, samples, *args, **kwargs):
        del samples
        return begin(self, frame, 1, *args, **kwargs)

    SceneTarget.begin = single
    try:
        yield
    finally:
        SceneTarget.begin = begin


class SceneMirror:
    """The owner's unshown scene, drawn: a hidden production scene that takes the owner's own scene commands.

    ``attach(runtime)`` (before the owner is built) creates the hidden host at the runtime's device pixel ratio and
    forwards ``FORWARDED`` (the render source bound, each presentation record committed, each present request, a
    retained-frame drop) from the runtime's scene controller to the hidden one (the runtime's own still runs each:
    the owner reads its drawn record back from it). ``frame(index)`` draws and reads the frame the last presentation left; the frames
    are kept compressed (``frames``) so two runs can be compared pixel by pixel afterwards.
    """

    def __init__(self) -> None:
        self.host: Any = None
        self.frames: list[tuple[tuple[int, ...], bytes]] = []
        self.lit: list[float] = []
        self._fbo = 0
        self._region: tuple[int, int, int, int] | None = None
        self._scene: Any = None
        self._saved: dict = {}

    def attach(self, runtime: Any) -> None:
        import tools.expanded_visualizer_evidence as evidence

        scene = runtime.scene_controller
        dpr = float(runtime.window.devicePixelRatio())
        self.host = evidence.HiddenDisplayHost(DISPLAY[0], DISPLAY[1], dpr=dpr)
        hidden = self.host.scene
        self._scene = scene
        mirror = self

        def forward(name: str):
            own = getattr(scene, name)
            self._saved[name] = own

            def call(*args, **kwargs):
                result = own(*args, **kwargs)
                if mirror.host is not None:
                    getattr(hidden, name)(*args, **kwargs)
                    if name == "apply_visualizer_presentation":
                        mirror._note_presentation(args[0])
                return result

            setattr(scene, name, call)

        for name in FORWARDED:
            if hasattr(scene, name):                    # a tree from before a command existed draws without it
                forward(name)

    def _note_presentation(self, presentation: Any) -> None:
        dpr = self.host.dpr
        if abs(float(presentation.dpr) - dpr) > 1e-9:
            raise RuntimeError(f"the owner resolved its card at DPR {presentation.dpr}, the hidden scene draws at {dpr}")
        x, y, width, height = presentation.outer_rect
        full_w, full_h = self.host.pixels
        left = max(0, int(x * dpr) - REGION_MARGIN)
        top = max(0, int(y * dpr) - REGION_MARGIN)
        right = min(full_w, int((x + width) * dpr + 0.999) + REGION_MARGIN)
        bottom = min(full_h, int((y + height) * dpr + 0.999) + REGION_MARGIN)
        self._region = (left, top, max(1, right - left), max(1, bottom - top))

    def _read(self, region: tuple[int, int, int, int]):
        """Top-down RGBA of ``region`` (left, top, width, height in device pixels) of the hidden texture."""
        import numpy

        host = self.host
        gl = host._gl
        host._current()
        previous = int(gl.glGetIntegerv(gl.GL_READ_FRAMEBUFFER_BINDING))
        if not self._fbo:
            self._fbo = int(gl.glGenFramebuffers(1))
            gl.glBindFramebuffer(gl.GL_READ_FRAMEBUFFER, self._fbo)
            gl.glFramebufferTexture2D(gl.GL_READ_FRAMEBUFFER, gl.GL_COLOR_ATTACHMENT0, gl.GL_TEXTURE_2D,
                                      host.texture, 0)
            if gl.glCheckFramebufferStatus(gl.GL_READ_FRAMEBUFFER) != gl.GL_FRAMEBUFFER_COMPLETE:
                raise RuntimeError("the hidden texture's read framebuffer is incomplete")
        else:
            gl.glBindFramebuffer(gl.GL_READ_FRAMEBUFFER, self._fbo)
        left, top, width, height = region
        gl.glPixelStorei(gl.GL_PACK_ALIGNMENT, 1)
        data = gl.glReadPixels(left, host.pixels[1] - top - height, width, height, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE)
        gl.glBindFramebuffer(gl.GL_READ_FRAMEBUFFER, previous)
        raw = data if isinstance(data, (bytes, bytearray)) else numpy.asarray(data).tobytes()
        return numpy.flipud(numpy.frombuffer(raw, dtype=numpy.uint8).reshape(height, width, 4))

    def frame(self, index: int) -> dict:
        """Draw the hidden scene and record what it drew: the card's region, and the whole display when due."""
        host = self.host
        host.render()
        if self._region is None:
            raise RuntimeError("the owner committed no presentation record before its first frame")
        region = self._region
        pixels = self._read(region)
        raw = pixels.tobytes()
        record = {"region": list(region), "hash": hashlib.sha256(raw).hexdigest()}
        self.lit.append(float((pixels[..., :3].max(axis=2) > LIT_LEVEL).mean()))
        self.frames.append((pixels.shape, zlib.compress(raw, 1)))
        if index % FULL_EVERY == 0:
            record["full"] = hashlib.sha256(self._read((0, 0, *host.pixels)).tobytes()).hexdigest()
        return record

    def close(self) -> None:
        host, self.host = self.host, None
        if host is None:
            return
        for name, own in self._saved.items():
            setattr(self._scene, name, own)
        self._saved.clear()
        if self._fbo:
            host._current()
            host._gl.glDeleteFramebuffers(1, [self._fbo])
            self._fbo = 0
        host.close()


def _pixels(run: dict, index: int):
    import numpy

    shape, data = run["frames"][index]
    return numpy.frombuffer(zlib.decompress(data), dtype=numpy.uint8).reshape(shape)


def drawn_run(mode: str, script, *, worker: bool, supervisor: Any, namespace: int | None, settings: dict) -> dict:
    """``owner_worker_gate.identity_run`` with the owner's scene drawn: its report plus ``frames`` and ``lit``."""
    from tools.visualizer_replay import owner_worker_gate as gate

    mirror = SceneMirror()
    report = gate.identity_run(mode, script, worker=worker, supervisor=supervisor, namespace=namespace,
                               settings=settings, scene_mirror=mirror)
    report["lit"] = mirror.lit
    report["frames"] = mirror.frames
    return report


def pair_difference(a: dict, b: dict) -> dict:
    """Two drawn runs, frame for frame: the first differing input, how many inputs differ, the most pixels differing
    in one of them and the largest 8-bit level difference (``None`` / 0 when every frame is equal)."""
    import numpy

    records_a, records_b = a["pixels"], b["pixels"]
    differing = [index for index, (x, y) in enumerate(zip(records_a, records_b)) if x != y]
    result = {"first": differing[0] if differing else (None if len(records_a) == len(records_b)
                                                       else min(len(records_a), len(records_b))),
              "frames": len(differing), "max_pixels": 0, "max_level": 0, "regions_equal": True}
    for index in differing:
        if records_a[index]["region"] != records_b[index]["region"]:
            result["regions_equal"] = False
            continue
        if records_a[index]["hash"] == records_b[index]["hash"]:
            continue                                        # only the whole-display hash differs: counted, not sized
        delta = numpy.abs(_pixels(a, index).astype(numpy.int16) - _pixels(b, index)).max(axis=2)
        result["max_pixels"] = max(result["max_pixels"], int((delta > 0).sum()))
        result["max_level"] = max(result["max_level"], int(delta.max()))
    return result


def still_indices(script) -> tuple[int, ...]:
    """Three inputs of ``script`` to keep stills of: early in the run, just before the mode switch, the last."""
    inputs = sum(1 for kind, _value in script if kind == "input")
    switch_at = next(i for i, (kind, _v) in enumerate(script) if kind == "mode")
    switch = sum(1 for kind, _value in script[:switch_at] if kind == "input")
    return tuple(sorted({max(0, inputs // 5), max(0, switch - 5), inputs - 1}))


def rendered_parity(mode: str, variant: str, clip_frames, supervisor: Any, *, sampling: str = "single",
                    out: Path | None = None, controls: bool = True) -> dict:
    """The owner on the engine worker against the same owner in process, at ``variant``'s non-default settings and
    ``sampling``: logical digests and drawn pixels, frame for frame. ``out``: where the stills (and, on a
    difference, both paths' frames of the first differing input and their difference map) are written."""
    if sampling not in SAMPLINGS:
        raise ValueError(f"unknown sampling {sampling!r}")
    script = parity_script(clip_frames, mode)
    settings = section_settings(mode, variant)
    with contextlib.ExitStack() as stack:
        if sampling == "single":
            stack.enter_context(single_sample_scene_targets())
        worker = drawn_run(mode, script, worker=True, supervisor=supervisor, namespace=None, settings=settings)
        in_process = drawn_run(mode, script, worker=False, supervisor=None, namespace=worker["namespace"],
                               settings=settings)
        paths = pair_difference(worker, in_process)
        digest_difference = next((i for i, (x, y) in enumerate(zip(worker["digests"], in_process["digests"]))
                                  if x != y), None)
        drawn = worker["pixels"]
        distinct = len({record["hash"] for record in drawn})
        lit = worker["lit"]
        verdict = {
            "mode": mode, "variant": variant, "sampling": sampling, "partner": worker["final_mode"],
            "inputs": worker["inputs"], "frames_drawn": [len(drawn), len(in_process["pixels"])],
            "frames_published": [len(worker["digests"]), len(in_process["digests"])],
            "paths": paths, "first_digest_difference": digest_difference, "distinct_frames": distinct,
            "lit_share_median": round(sorted(lit)[len(lit) // 2], 4) if lit else 0.0,
            "lit_share_max": round(max(lit), 4) if lit else 0.0, "stayed_on_worker": worker["on_worker"],
            "region": drawn[0]["region"] if drawn else None,
            "stored_mb": round(sum(len(data) for _shape, data in worker["frames"]) / 1e6, 1),
            "final_mode": [worker["final_mode"], in_process["final_mode"]],
            "series": hashlib.sha256("".join(record["hash"] for record in drawn).encode()).hexdigest(),
        }
        verdict["digests_identical"] = bool(worker["digests"] and digest_difference is None
                                            and len(worker["digests"]) == len(in_process["digests"]))
        verdict["meaningful"] = bool(distinct > len(drawn) // 4 and verdict["lit_share_max"] > 0.002)
        verdict["pixels_identical"] = bool(drawn and paths["first"] is None)
        pixels_ok = verdict["pixels_identical"]
        if controls or sampling == "product":
            repeat = drawn_run(mode, script, worker=False, supervisor=None, namespace=worker["namespace"],
                               settings=settings)
            verdict["repeat"] = pair_difference(in_process, repeat)
            verdict["reproducible"] = verdict["repeat"]["first"] is None
            del repeat
        if sampling == "single":
            if controls:
                nudged = drawn_run(mode, script, worker=False, supervisor=None, namespace=worker["namespace"],
                                   settings=section_settings(mode, variant, nudge=True))
                verdict["nudged_frames_changed"] = pair_difference(in_process, nudged)["frames"]
                del nudged
                verdict["controls_ok"] = bool(verdict["reproducible"] and verdict["nudged_frames_changed"] > 0)
        elif not verdict["reproducible"]:
            # The same path does not repeat itself at this sampling: the paths may differ by no more levels than that.
            pixels_ok = bool(paths["regions_equal"] and verdict["frames_drawn"][0] == verdict["frames_drawn"][1]
                             and paths["max_level"] <= verdict["repeat"]["max_level"])
            verdict["bounded_by_repeat"] = pixels_ok
        verdict["identical"] = bool(pixels_ok and verdict["digests_identical"] and verdict["stayed_on_worker"]
                                    and verdict["meaningful"]
                                    and verdict["final_mode"][0] == verdict["final_mode"][1]
                                    and verdict.get("controls_ok", True))
        if out is not None:
            _write_stills(Path(out), f"{mode}_{variant}_{sampling}", script, worker, in_process, paths)
    return verdict


def _write_stills(out: Path, name: str, script, worker: dict, in_process: dict, paths: dict) -> None:
    """One sheet per run: three of the worker path's frames side by side (half size). When the paths differ, both
    paths' frames of the first differing input and an amplified difference map as well."""
    import numpy
    from PIL import Image

    out.mkdir(parents=True, exist_ok=True)
    kept = [_pixels(worker, index) for index in still_indices(script) if index < len(worker["frames"])]
    if kept:
        height = max(frame.shape[0] for frame in kept)
        width = sum(frame.shape[1] for frame in kept)
        sheet = numpy.zeros((height, width, 3), dtype=numpy.uint8)
        x = 0
        for frame in kept:
            sheet[:frame.shape[0], x:x + frame.shape[1]] = frame[..., :3]
            x += frame.shape[1]
        Image.fromarray(sheet, "RGB").resize((max(1, width // 2), max(1, height // 2)), Image.LANCZOS).save(
            out / f"{name}.png")
    first = paths["first"]
    if first is not None and first < min(len(worker["frames"]), len(in_process["frames"])):
        a, b = _pixels(worker, first), _pixels(in_process, first)
        Image.fromarray(a[..., :3], "RGB").save(out / f"{name}_{first}_worker.png")
        Image.fromarray(b[..., :3], "RGB").save(out / f"{name}_{first}_in_process.png")
        if a.shape == b.shape:
            delta = numpy.abs(a[..., :3].astype(numpy.int16) - b[..., :3])
            Image.fromarray(numpy.clip(delta * 64, 0, 255).astype(numpy.uint8), "RGB").save(
                out / f"{name}_{first}_difference_x64.png")


def run(out: Path, *, modes=None, variants=("a", "b"), samplings=SAMPLINGS, seconds: float = 5.5,
        controls: bool = True) -> dict:
    """Every chosen mode, variant and sampling through ``rendered_parity`` on one real engine worker; the report."""
    import tools.expanded_visualizer_evidence as evidence
    from core.process.supervisor import ProcessSupervisor
    from core.process.types import WorkerType
    from core.visualizer_engine.engine_worker import visualizer_worker_main
    from tools.visualizer_replay import owner_worker_gate as gate
    from widgets.spotify_visualizer import engine_worker_link

    chosen = list(modes or gate.modes())
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    report: dict = {"modes": chosen, "variants": list(variants), "samplings": list(samplings), "seconds": seconds,
                    "display": list(DISPLAY), "results": {}}
    supervisor = ProcessSupervisor()
    supervisor.register_worker_factory(WorkerType.VISUALIZER, visualizer_worker_main)
    started = time.perf_counter()
    try:
        if not supervisor.start(WorkerType.VISUALIZER):
            raise RuntimeError("the engine worker did not start")
        clip = evidence.shipped_clip(seconds)
        report["clip"] = clip.name
        for mode in chosen:
            for variant in variants:
                for sampling in samplings:
                    engine_worker_link.reset_run_state_for_testing()
                    verdict = rendered_parity(mode, variant, clip.frames, supervisor, sampling=sampling, out=out,
                                              controls=controls)
                    report["results"][f"{mode}:{variant}:{sampling}"] = verdict
                    paths, repeat = verdict["paths"], verdict.get("repeat")
                    noise = "" if repeat is None else (f" repeat {repeat['frames']} frames/{repeat['max_pixels']} px/"
                                                       f"{repeat['max_level']} levels;")
                    print(f"[RENDERED] {mode:18s} {variant} {sampling:7s} -> {verdict['partner']:18s} "
                          f"{verdict['frames_drawn'][0]} frames ({verdict['distinct_frames']} distinct, lit "
                          f"{verdict['lit_share_median']}); paths {paths['frames']} frames/{paths['max_pixels']} px/"
                          f"{paths['max_level']} levels;{noise} "
                          f"{'OK' if verdict['identical'] else 'DIFFERENT: ' + json.dumps(verdict)}", flush=True)
    finally:
        supervisor.shutdown()
        report["elapsed_s"] = round(time.perf_counter() - started, 1)
        report["identical"] = bool(report["results"]) and all(v["identical"] for v in report["results"].values())
        (out / "owner_render_parity.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    return report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=artifact_paths.evidence_arg, required=True)
    parser.add_argument("--modes", nargs="*")
    parser.add_argument("--variants", nargs="*", default=["a", "b"], choices=sorted(VARIANTS))
    parser.add_argument("--sampling", nargs="*", default=list(SAMPLINGS), choices=SAMPLINGS)
    parser.add_argument("--seconds", type=float, default=5.5)
    parser.add_argument("--skip-controls", action="store_true")
    args = parser.parse_args(argv)
    try:
        import psutil
        psutil.Process().nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    except Exception:
        pass
    from rendering.quick.bootstrap import configure_quick_graphics

    configure_quick_graphics(reason="owner-render-parity")      # Qt Quick on OpenGL, as the product selects it
    from PySide6.QtWidgets import QApplication

    app = QApplication(["owner-render-parity"])
    report = run(args.out, modes=args.modes, variants=tuple(args.variants), samplings=tuple(args.sampling),
                 seconds=args.seconds, controls=not args.skip_controls)
    del app
    return 0 if report["identical"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
