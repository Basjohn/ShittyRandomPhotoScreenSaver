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
- ``product``: the sampling as shipped. The pixels are **reported, not judged**: the differing frames, the most
  pixels differing in one frame and the largest level difference, worker against in process beside in process
  against itself (one repeat is one sample of the noise: a short tail can repeat exactly and then differ by a
  pixel). Everything else is still judged.

Gate (per mode, variant and sampling): the two paths drew the same number of frames over equal regions, the pixels
are equal (``single``), the logical digests are equal, the worker path stayed on the worker, and the drawn frames
changed over the run and lit the card (a blank card would be equal on any two paths). On a difference both paths'
frames of the first differing input are written beside an amplified difference map.

Controls (``--skip-controls`` omits them): the in-process run repeated (``single``: identical to itself, the
oracle's noise floor is zero), and the mode's Sliders moved a further step must change the drawn frames (the
oracle sees a Settings change; ``single`` only).

``--native`` (rule (a) of N2.5) draws the widened run set at the rig's own placement and variants a and b again at
``overscan`` (``PLACEMENTS``: Display 1's R-63 window with the card half a device pixel off the grid, N2.8 R-NEW).

Offscreen GL on this machine's GPU: not physical acceptance (no real window, display timing, device or load).
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import math
import sys
import time
import zlib
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import artifact_paths, evidence_media  # noqa: E402

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

    # The switch at 4.2 s, or 1.3 s before the end of a longer clip (a 60 s recorded take shows the mode for its whole
    # length, not its first 4.2 s); a clip of 5.5 s or less keeps 4.2 s exactly.
    span = (clip_frames[-1].timestamp_us - clip_frames[0].timestamp_us) / 1e6 if len(clip_frames) else 0.0
    script = gate.identity_script(clip_frames, mode, switch_at_s=max(4.2, span - 1.3))
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


class _SpilledFrames:
    """A run's compressed frames, ``(shape, zlib bytes)`` by index, kept in an anonymous temporary file in the owner
    scratch instead of memory: a 60 s recorded take is 5,455 frames a path, several gigabytes compressed. The file
    goes when the list is collected or the process exits."""

    def __init__(self) -> None:
        self._file: Any = None
        self._entries: list[tuple[tuple[int, ...], int, int]] = []

    def append(self, item: tuple[tuple[int, ...], bytes]) -> None:
        import tempfile

        from tools import artifact_paths

        shape, data = item
        if self._file is None:
            folder = artifact_paths.scratch_root("owner_render_parity")
            folder.mkdir(parents=True, exist_ok=True)
            self._file = tempfile.TemporaryFile(dir=folder)
        self._file.seek(0, 2)
        self._entries.append((tuple(shape), self._file.tell(), len(data)))
        self._file.write(data)

    def __len__(self) -> int:
        return len(self._entries)

    def __getitem__(self, index: int) -> tuple[tuple[int, ...], bytes]:
        shape, offset, size = self._entries[index]
        self._file.seek(offset)
        return shape, self._file.read(size)

    def __iter__(self):
        return (self[index] for index in range(len(self)))


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
        self.frames = _SpilledFrames()
        self.lit: list[float] = []
        self._fbo = 0
        self._region: tuple[int, int, int, int] | None = None
        self._scene: Any = None
        self._saved: dict = {}
        #: The first committed record's outer origin (display-logical): what the run's placement put the card at.
        self.first_outer_origin: tuple[float, float] | None = None

    def attach(self, runtime: Any) -> None:
        import tools.expanded_visualizer_evidence as evidence

        scene = runtime.scene_controller
        dpr = float(runtime.window.devicePixelRatio())
        _PLACED["dpr"] = dpr                      # the owner built next places its card on this grid (card_placement)
        overscan = OVERSCAN_ROWS if _PLACED["name"] == "overscan" else 0
        self.host = evidence.HiddenDisplayHost(DISPLAY[0], DISPLAY[1], dpr=dpr, overscan_rows=overscan)
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
        # The display's own place in the window (an overscan above it, ``card_placement``), logical.
        x, y = x + self.host.scene_offset[0], y + self.host.scene_offset[1]
        if self.first_outer_origin is None:
            self.first_outer_origin = tuple(float(v) for v in presentation.outer_rect[:2])
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


#: Where a rule (a) run puts the card (N2.8, R-NEW). "display": the rig's own (the owner's origin at the display's
#: corner, the window exactly the display). "overscan": Display 1's R-63 window, the display ``OVERSCAN_ROWS`` logical
#: rows down inside a taller window, and the card's authored origin half a device pixel off the grid on both axes:
#: the record's outer origin at k + 0.5 device pixels, so the scene draws the card on the nearest whole pixels and
#: every renderer must place its content with the drawn card (the native item once sat half a pixel off it, and the
#: composite's quad broke the bars along its diagonal on Vulkan).
PLACEMENTS = ("display", "overscan")
OVERSCAN_ROWS = 2                       # logical rows above the display: Display 1's 3 device rows at 150 %
#: The runs of the widened set drawn at the "overscan" placement too (each a whole rule (a) run): variants a and b.
OVERSCAN_RUNS = ("", ":b")
_PLACED: dict = {"name": "display", "dpr": 1.0}


@contextlib.contextmanager
def card_placement(name: str):
    """The runs inside are drawn at placement ``name`` (``PLACEMENTS``): the hidden window's overscan
    (``SceneMirror.attach``) and, for "overscan", every authored origin the host binding gives an owner
    (``set_authored_outer_origin``) moved half a device pixel past its own whole pixel on both axes, on the grid of
    the dpr the mirror attached at."""
    if name not in PLACEMENTS:
        raise ValueError(f"unknown placement {name!r} (the placements are {', '.join(PLACEMENTS)})")
    from widgets.spotify_visualizer.quick_display_visualizer_owner import QuickDisplayVisualizerOwner

    authored = QuickDisplayVisualizerOwner.set_authored_outer_origin

    def placed(self, x: float, y: float) -> bool:
        dpr = float(_PLACED["dpr"])
        return authored(self, (math.floor(float(x) * dpr) + 0.5) / dpr, (math.floor(float(y) * dpr) + 0.5) / dpr)

    _PLACED["name"] = name
    if name == "overscan":
        QuickDisplayVisualizerOwner.set_authored_outer_origin = placed
    try:
        yield
    finally:
        QuickDisplayVisualizerOwner.set_authored_outer_origin = authored
        _PLACED["name"] = "display"


#: Rule (a)'s tolerance for a mode drawn through the composite's premultiplied surface (lead's decision, N5.1 review;
#: the per-pixel proof: .artifacts/evidence/native_core/n5_1_devcurve/20261115_rule_a_per_pixel/, D12 "As built: Spline
#: Curve"), judged pixel by pixel by the shared tolerance (``tools/pixel_tolerance.py``, D12 "The pixel tolerance";
#: checkpoint audit 3 M1). The Python node rounds once, round(s8 a8 / 255 + d (1 - a8 / 255)); the native item rounds the
#: premultiplied product into its surface first, so a pixel the reference draws translucent (the mask: ``rule_a_masks``)
#: may sit RULE_A_FILL_LEVEL off. Opaque content and the card's own background are exact. Edge pixels flip on float32
#: interpolation between the core's triangle and the Python quad (each within 4e-3 of a device pixel of its rounding
#: boundary): ties, within RULE_A_EDGE_LEVEL, at most RULE_A_EDGE_PIXELS_PER_FRAME a frame (the measured worst, 7 in one
#: frame of Spline Curve's widened run set and overscan runs on 15 Nov, times 1.5, whole pixels), each isolated or on a
#: content edge. One rule for every mode drawn through the composite, Spectrum included (lead, 15 Nov: its translucent
#: bars and glow pass through the same surface).
RULE_A_FILL_LEVEL = 1
RULE_A_EDGE_LEVEL = 3
RULE_A_EDGE_PIXELS_PER_FRAME = 10
#: The colour the translucency run draws under the mode's content (``content_backdrop``): magenta, so that no content
#: pixel short of a near-zero alpha can equal it in all three channels.
MASK_BACKDROP = (255, 0, 255)
#: Rule (a)'s scatter per mode (D12 bounds, lead's decision 17 Nov for Bubble): pixels outside the mask exactly one level
#: off, the NativeFragmentPass two-compiler case (Python's driver-compiled composed GLSL against the qsb pack). Bubble:
#: measured worst 34 a frame (.artifacts/evidence/native_core/n5_1_bubble/20261117_steady_residual_classes/), times 1.5.
#: Every other mode admits none.
RULE_A_SCATTER_PIXELS = {"bubble": 51}


def composite_tolerance(mode: str | None = None):
    """The composite's tolerance (``RULE_A_*``) as the shared ``pixel_tolerance.Tolerance``; ``mode`` adds its D12
    scatter (``RULE_A_SCATTER_PIXELS``)."""
    from tools import pixel_tolerance

    scatter = RULE_A_SCATTER_PIXELS.get(mode, 0)
    return pixel_tolerance.Tolerance(f"composite (rule a, {mode})" if scatter else "composite (rule a)",
                                     masked_level=RULE_A_FILL_LEVEL, scatter_pixels=scatter,
                                     tie_pixels=RULE_A_EDGE_PIXELS_PER_FRAME, tie_level=RULE_A_EDGE_LEVEL,
                                     edge_class=True)


def rule_a_frame(native, python, mask, mode: str | None = None) -> dict:
    """One frame of rule (a): the native frame against the Python frame (same shape, the channels compared) under the
    composite's tolerance, ``mask`` the pixels the Python renderer draws translucent."""
    from tools import pixel_tolerance

    return pixel_tolerance.judge(native, python, composite_tolerance(mode), mask=mask)


def rule_a_verdict(frames, mode: str | None = None) -> dict:
    """Rule (a) over the per-frame verdicts of ``rule_a_frame`` (frames that are equal may be left out): pass, the
    bound and the worst figures."""
    from tools import pixel_tolerance

    summary = pixel_tolerance.summarise(frames)
    return {"bound": composite_tolerance(mode).bound(), **summary,
            "edge_pixels_worst_frame": summary["ties_worst_frame"]}


@contextlib.contextmanager
def content_backdrop(colour: tuple[int, int, int] = MASK_BACKDROP):
    """For the block, the Python render host clears its viewport (inside any scissor already set) to ``colour`` before
    each mode draw: the reference drawn over a second background (``rule_a_masks``). Nothing else about a draw changes;
    the GL state it touches is restored."""
    from OpenGL import GL as gl

    from rendering.quick.visualizer.render_host import QuickVisualizerRenderHost

    render = QuickVisualizerRenderHost.render

    def backdrop(self, *, viewport, **kwargs):
        x, y, w, h = (int(v) for v in viewport)
        scissor = bool(gl.glIsEnabled(gl.GL_SCISSOR_TEST))
        box = [int(v) for v in gl.glGetIntegerv(gl.GL_SCISSOR_BOX)]
        clear = [float(v) for v in gl.glGetFloatv(gl.GL_COLOR_CLEAR_VALUE)]
        mask = [bool(v) for v in gl.glGetBooleanv(gl.GL_COLOR_WRITEMASK)]
        left, bottom = (max(x, box[0]), max(y, box[1])) if scissor else (x, y)
        right = min(x + w, box[0] + box[2]) if scissor else x + w
        top = min(y + h, box[1] + box[3]) if scissor else y + h
        if right > left and top > bottom:
            gl.glEnable(gl.GL_SCISSOR_TEST)
            gl.glScissor(left, bottom, right - left, top - bottom)
            gl.glColorMask(True, True, True, True)
            gl.glClearColor(colour[0] / 255.0, colour[1] / 255.0, colour[2] / 255.0, 1.0)
            gl.glClear(gl.GL_COLOR_BUFFER_BIT)
            gl.glColorMask(*mask)
            gl.glClearColor(*clear)
            gl.glScissor(*box)
            if not scissor:
                gl.glDisable(gl.GL_SCISSOR_TEST)
        return render(self, viewport=viewport, **kwargs)

    QuickVisualizerRenderHost.render = backdrop
    try:
        yield
    finally:
        QuickVisualizerRenderHost.render = render


def rule_a_masks(python: dict, backdrop: dict) -> dict:
    """Per input, the pixels the Python renderer draws translucent: its run against the same run drawn over
    ``MASK_BACKDROP`` (``content_backdrop``), ``pixel_tolerance.translucent_by_backgrounds``. An input whose two draws
    have different regions has no mask (every pixel exact)."""
    from tools import pixel_tolerance

    masks = {}
    for index, (x, y) in enumerate(zip(python["pixels"], backdrop["pixels"])):
        if x["region"] != y["region"]:
            continue
        masks[index] = pixel_tolerance.translucent_by_backgrounds(_pixels(python, index), _pixels(backdrop, index),
                                                                  MASK_BACKDROP)
    return masks


def rule_a_frames(native: dict, python: dict, masks: dict, mode: str | None = None) -> list[dict]:
    """``rule_a_frame`` for every input whose drawn region differs between the native run and the Python run."""
    frames = []
    for index, (x, y) in enumerate(zip(native["pixels"], python["pixels"])):
        if x["hash"] == y["hash"]:
            continue
        if x["region"] != y["region"]:
            frames.append({"pass": False, "reasons": [f"input {index}: the regions differ"], "max_level": None})
            continue
        verdict = rule_a_frame(_pixels(native, index), _pixels(python, index), masks.get(index), mode)
        verdict["input"] = index
        frames.append(verdict)
    return frames


#: ``--surface-format``: the native item's surface texels for this run (None: the route's own choice).
NATIVE_SURFACE_FORMAT: str | None = None
#: ``--unprimed``: the window is not rendered before the owner exists and the route is not prepared at attach (audit
#: N29 round 2, M3: the product's unprimed path, its first frame waiting on the window's edge), a reported case, not a
#: gate.
NATIVE_UNPRIMED = False


class _ParityRoute:
    """``NativeVisualizerRoute`` for the parity runs. With the mapping check, each card's window map is compared with
    the Python renderer's own rows of the same frame (``_python_mappings_run``), as float32 (what the GPU reads)."""

    @staticmethod
    def make(core, content_host, mirror):
        import struct

        from rendering.quick.visualizer.native_route import NativeVisualizerRoute

        def f32(values):
            return struct.pack(f"<{len(values)}f", *values)

        class Route(NativeVisualizerRoute):
            def card(self, presentation, snapshot, geometry, metrics=None):
                card = super().card(presentation, snapshot, geometry, metrics)
                mappings = mirror.python_mappings
                if mappings is not None and self.published < len(mappings):
                    row_x, row_y, _height = mappings[self.published]
                    mirror.mapping_compared += 1
                    mirror.mapping_identical += int(f32(card["item_from_window"]) == f32((*row_x, *row_y)))
                return card

        route = Route(core, content_host)
        if NATIVE_SURFACE_FORMAT is not None:
            route.surface_format = NATIVE_SURFACE_FORMAT      # rule (a)'s target-format measurement (round 5)

            def checking(make):                                # checked on each item the route creates
                def checked(parent):
                    item = make(parent)
                    item.composite.set(surface_format=NATIVE_SURFACE_FORMAT)
                    held = item.composite.state()["config"].get("surface_format", "rgba8")
                    if held != NATIVE_SURFACE_FORMAT:
                        raise RuntimeError(f"the module draws its surface as {held}: build round 5")
                    return item
                return staticmethod(checked)

            route._core = type("Core", (), {"spectrum": checking(core.spectrum), "mode": checking(core.mode)})()
        return route


class NativeSceneMirror(SceneMirror):
    """``SceneMirror`` whose hidden production scene draws Spectrum through the product's native route (N2.5 rule (a),
    D10 point 4): the module's frame driver attached to its window and a ``NativeVisualizerRoute`` attached to its
    Visualizer item, as ``QuickSceneController`` attaches one on Vulkan. The item's own update requests are the
    route's takes (``VisualizerRenderItem.update``); another mode's activation draws through the item's Python node
    (the mixed window)."""

    def __init__(self, core) -> None:
        super().__init__()
        self.core = core
        self.window_host = None
        self.route = None
        self.native_frames = 0
        # The mapping control: the Python renderer's window-pixel map per drawn frame (``_python_mappings_run``).
        self.python_mappings: list | None = None
        self.mapping_compared = 0
        self.mapping_identical = 0

    @property
    def native_published(self) -> int:
        return 0 if self.route is None else self.route.published

    def attach(self, runtime: Any) -> None:
        super().attach(runtime)
        hidden = self.host.scene
        self.window_host = self.core.attach_host(self.host.window)
        item = hidden._ensure_visualizer_items()
        self.route = _ParityRoute.make(self.core, item.parentItem(), self)
        item.attach_native_route(self.route)
        if not NATIVE_UNPRIMED:
            # As the product: the route is prepared at attach (``attach_native_route``) and the window renders long
            # before a Visualizer activates, so the native item has read the window's framebuffer at its own
            # synchronisation (audit N29 L1, round 2 L1) by the first input. ``--unprimed`` runs without both.
            self.route.prepare()
            self.host.render()

    def frame(self, index: int) -> dict:
        if self.route is not None and self.route.identity is not None:
            self.native_frames += 1
        return super().frame(index)

    def close(self) -> None:
        if self.host is not None and self.route is not None:
            self.route.close()
            self.host.render()                           # Qt deletes the node: the reader goes on its thread
            if self.window_host is not None:
                self.window_host.close()
                self.window_host = None
        super().close()


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
        else:
            # A multisampled target does not repeat its own draw, and one repeat is one sample of that noise (a
            # 35-frame tail can repeat exactly and then differ by one pixel): the pixels are reported beside the same
            # path's repeat and not judged here. ``single`` is the exact gate.
            verdict["pixels_judged"] = False
            pixels_ok = bool(paths["regions_equal"] and verdict["frames_drawn"][0] == verdict["frames_drawn"][1])
        verdict["identical"] = bool(pixels_ok and verdict["digests_identical"] and verdict["stayed_on_worker"]
                                    and verdict["meaningful"]
                                    and verdict["final_mode"][0] == verdict["final_mode"][1]
                                    and verdict.get("controls_ok", True))
        if out is not None:
            _write_stills(Path(out), f"{mode}_{variant}_{sampling}", script, worker, in_process, paths)
    return verdict


def native_drawn_run(mode: str, script, *, settings: dict, core, python_mappings: list | None = None) -> dict:
    """``drawn_run`` in process with the native Spectrum drawing Spectrum's activations (``NativeSceneMirror``)."""
    from tools.visualizer_replay import owner_worker_gate as gate

    mirror = NativeSceneMirror(core)
    mirror.python_mappings = python_mappings
    report = gate.identity_run(mode, script, worker=False, supervisor=None, namespace=None, settings=settings,
                               scene_mirror=mirror)
    report["lit"] = mirror.lit
    report["frames"] = mirror.frames
    report["native_frames"] = mirror.native_frames
    report["native_published"] = mirror.native_published
    report["mapping"] = {"compared": mirror.mapping_compared, "identical": mirror.mapping_identical}
    report["outer_origin"] = mirror.first_outer_origin
    return report


def frame_differences(a: dict, b: dict) -> list[dict]:
    """Every input whose drawn region differs: its pixel count, largest 8-bit level and the differing pixels' bounding
    box (left, top, right, bottom in the region's device pixels)."""
    import numpy

    rows = []
    for index, (x, y) in enumerate(zip(a["pixels"], b["pixels"])):
        if x["hash"] == y["hash"] or x["region"] != y["region"]:
            continue
        delta = numpy.abs(_pixels(a, index).astype(numpy.int16) - _pixels(b, index)).max(axis=2)
        ys, xs = numpy.nonzero(delta)
        if not len(xs):
            continue
        rows.append({"input": index, "pixels": int(len(xs)), "max_level": int(delta.max()),
                     "bbox": [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())],
                     "levels": {str(level): int((delta == level).sum()) for level in sorted(set(delta[delta > 0].tolist()))[:8]}})
    return rows


def _write_native_crops(out: Path, name: str, native: dict, python: dict, row: dict) -> list[str]:
    """The worst differing input's crops (the differing pixels' box with 12 px around it, 4x nearest): Python, native
    and the difference x64; plus the whole region of each."""
    import numpy
    from PIL import Image

    out.mkdir(parents=True, exist_ok=True)
    index = row["input"]
    a, b = _pixels(python, index), _pixels(native, index)
    left, top, right, bottom = row["bbox"]
    pad = 12
    box = (max(0, left - pad), max(0, top - pad), min(a.shape[1], right + pad + 1), min(a.shape[0], bottom + pad + 1))
    written = []
    for label, image in (("python", a[..., :3]), ("native", b[..., :3]),
                         ("difference_x64", numpy.clip(numpy.abs(a[..., :3].astype(numpy.int16) - b[..., :3]) * 64,
                                                       0, 255).astype(numpy.uint8))):
        crop = image[box[1]:box[3], box[0]:box[2]]
        path = out / f"{name}_input{index}_{label}_crop_x4.png"
        Image.fromarray(numpy.ascontiguousarray(crop), "RGB").resize(
            (crop.shape[1] * 4, crop.shape[0] * 4), Image.NEAREST).save(path)
        written.append(str(path))
        whole = out / f"{name}_input{index}_{label}.png"
        Image.fromarray(numpy.ascontiguousarray(image), "RGB").save(whole)
        written.append(str(whole))
    return written


def _split_rows(rows: list[dict], switch_input: int) -> dict:
    """The per-input rows split at the mode switch: ``steady`` (Spectrum shown) and ``fade`` (its fade-out and the
    next mode's arrival); for each, the inputs that differ, the largest level, and the pixels differing by more
    than one level."""
    def summary(part: list[dict]) -> dict:
        above_one = sum(count for row in part for level, count in row["levels"].items() if int(level) > 1)
        return {"differing_inputs": len(part), "max_level": max((row["max_level"] for row in part), default=0),
                "pixels": sum(row["pixels"] for row in part), "pixels_above_one_level": above_one,
                "inputs_above_one_level": sum(1 for row in part if row["max_level"] > 1)}
    return {"steady": summary([row for row in rows if row["input"] < switch_input]),
            "fade": summary([row for row in rows if row["input"] >= switch_input])}


def _python_mappings_run(mode: str, script, settings: dict) -> tuple[dict, list]:
    """``drawn_run`` in process, also recording the Python Spectrum renderer's own window-pixel map per drawn frame
    (``u_item_from_frag_x``/``_y`` and its target's height): the input of the mapping control."""
    from rendering.quick.visualizer.implementations import spectrum as python_spectrum

    mappings: list = []
    renderer = python_spectrum.QuickSpectrumRenderer
    original = renderer.render

    def recording(self, frame):
        original(self, frame)
        if int(frame.snapshot.logical.common.bar_count) > 0 and self._values.get("u_item_from_frag") == 1:
            mappings.append((tuple(self._values["u_item_from_frag_x"]), tuple(self._values["u_item_from_frag_y"]),
                             float(frame.viewport[3])))

    renderer.render = recording
    try:
        run = drawn_run(mode, script, worker=False, supervisor=None, namespace=None, settings=settings)
    finally:
        renderer.render = original
    return run, mappings


#: Lit: a pixel whose brightest channel is this far above the card's dark fill (the classification's mask).
_LIT_LEVEL = 40


def classify_differences(native: dict, python: dict, switch_input: int) -> dict:
    """Every pixel more than one level off, by class (the lead's rule (a) reading, 14 Nov): ``fade_frame`` (an input
    at or after the mode switch), ``card_edge_column`` (within 2 device columns of the frame's leftmost or rightmost
    lit column: the outermost bars' outer edges), ``peak_row`` (within a row of a column's topmost lit run when a
    gap separates it from the bar below: the peak marker), ``cap_arc`` (the top 4 rows of the bar's own run in that
    column: its rounded cap), ``other``. Each class: its pixel count and largest level."""
    import numpy

    classes = {name: {"pixels": 0, "max_level": 0, "inputs": 0} for name in
               ("card_edge_column", "peak_row", "cap_arc", "fade_frame", "other")}
    for index, (a, b) in enumerate(zip(native["pixels"], python["pixels"])):
        if a["hash"] == b["hash"] or a["region"] != b["region"]:
            continue
        drawn, reference = _pixels(native, index), _pixels(python, index)
        delta = numpy.abs(drawn.astype(numpy.int16) - reference).max(axis=2)
        ys, xs = numpy.nonzero(delta > 1)
        if not len(ys):
            continue
        labels = numpy.full(len(ys), "other", dtype=object)
        if index >= switch_input:
            labels[:] = "fade_frame"
        else:
            lit = reference[..., :3].max(axis=2) > _LIT_LEVEL
            # The card's own frame (its border rows and columns, lit nearly edge to edge) is not a bar: without this
            # every column's first lit row is the border's (the round-3 report's classes were taken that way).
            lit[lit.mean(axis=1) > 0.8, :] = False
            lit[:, lit.mean(axis=0) > 0.8] = False
            columns = numpy.nonzero(lit.any(axis=0))[0]
            edge = numpy.zeros(len(ys), dtype=bool)
            if len(columns):
                edge = (numpy.abs(xs - columns[0]) <= 2) | (numpy.abs(xs - columns[-1]) <= 2)
            for k in range(len(ys)):
                if edge[k]:
                    labels[k] = "card_edge_column"
                    continue
                column = lit[:, xs[k]]
                runs = numpy.flatnonzero(numpy.diff(numpy.concatenate(([0], column.view(numpy.int8), [0]))))
                starts, ends = runs[0::2], runs[1::2]          # lit runs [start, end) from the top
                if not len(starts):
                    continue
                y = ys[k]
                if len(starts) > 1 and starts[0] - 1 <= y <= ends[0]:
                    labels[k] = "peak_row"
                    continue
                bar = 1 if len(starts) > 1 else 0
                if starts[bar] - 1 <= y < starts[bar] + 4:
                    labels[k] = "cap_arc"
        levels = delta[ys, xs]
        for name in classes:
            chosen = labels == name
            if chosen.any():
                entry = classes[name]
                entry["pixels"] += int(chosen.sum())
                entry["max_level"] = max(entry["max_level"], int(levels[chosen].max()))
                entry["inputs"] += 1
    return classes


def native_parity(core, mode: str, suffix: str, settings: dict, clip_frames, out: Path,
                  placement: str = "display") -> dict:
    """Rule (a) of the port (N2.5): the owner in process drawn by the Python renderer and by the native item, single-
    sampled, frame for frame over the card's region and its margin. Each native card's window map is checked against
    the Python renderer's own rows of the same frame (``mapping``), and every pixel more than a level off is
    classified (``classes``). ``placement``: where both runs put the card (``PLACEMENTS``)."""
    script = parity_script(clip_frames, mode)
    with single_sample_scene_targets(), card_placement(placement):
        if mode == "spectrum":
            python, mappings = _python_mappings_run(mode, script, settings)
        else:
            # A generic mode's card maps nothing per fragment (its uv is the core's, N29 round 2 M6): no mapping control.
            python, mappings = drawn_run(mode, script, worker=False, supervisor=None, namespace=None,
                                         settings=settings), []
        native = native_drawn_run(mode, script, settings=settings, core=core,
                                  python_mappings=mappings if mode == "spectrum" else None)
        # Rule (a)'s mask: the same Python run over a second background (its translucent pixels).
        with content_backdrop():
            backdrop = drawn_run(mode, script, worker=False, supervisor=None, namespace=None, settings=settings)
    masks = rule_a_masks(python, backdrop)
    paths = pair_difference(native, python)
    rows = frame_differences(native, python)
    switch_at = next(i for i, (kind, _v) in enumerate(script) if kind == "mode")
    switch_input = sum(1 for kind, _value in script[:switch_at] if kind == "input")
    run = f"{mode}{suffix}" if placement == "display" else f"{mode}{suffix}@{placement}"
    origin = native.get("outer_origin")
    dpr = float(_PLACED["dpr"])
    fraction = None if origin is None else [round((v * dpr) % 1.0, 4) for v in origin]
    verdict = {"mode": mode, "run": run, "inputs": python["inputs"], "placement": placement,
               "outer_origin": origin, "outer_origin_device_fraction": fraction, "dpr": dpr,
               "frames_drawn": [len(python["pixels"]), len(native["pixels"])],
               "native_frames": native["native_frames"], "native_published": native["native_published"],
               "switch_input": switch_input, "paths": paths, "differing_inputs": len(rows),
               "differing_pixels_total": sum(row["pixels"] for row in rows),
               "max_level": max((row["max_level"] for row in rows), default=0),
               "differences": rows[:200], "region": python["pixels"][0]["region"] if python["pixels"] else None,
               "digests_identical": python["digests"] == native["digests"],
               # Each drawn frame's pixel hash on both paths: a later run is bit-identical to this one where its
               # native hashes are (``against_baseline``), whatever the Python reference did meanwhile.
               "native_hashes": [entry["hash"] for entry in native["pixels"]],
               "python_hashes": [entry["hash"] for entry in python["pixels"]]}
    verdict["identical"] = bool(paths["first"] is None and verdict["digests_identical"]
                                and verdict["native_published"] > 0)
    # Rule (a)'s verdict: the composite's tolerance (RULE_A_*), pixel by pixel with the translucency mask.
    judged = rule_a_frames(native, python, masks, mode)
    verdict["rule_a"] = rule_a_verdict(judged, mode)
    # The mode's shown span in halves (before the switch): adaptive state (Dynamic Floor, normalisers) drifts with a
    # clip's length, so a late divergence shows in the second half's figures, not in the whole run's worst.
    half = switch_input // 2
    verdict["rule_a_halves"] = {
        name: {"inputs": [lo, hi], **rule_a_verdict([f for f in judged if lo <= f.get("input", -1) < hi], mode)}
        for name, lo, hi in (("first", 0, half), ("second", half, switch_input))}
    verdict["rule_a"]["mask_inputs"] = len(masks)
    verdict["rule_a"]["backdrop_frames"] = len(backdrop["pixels"])
    verdict["pass"] = bool(verdict["rule_a"]["pass"] and verdict["digests_identical"] and verdict["native_published"] > 0
                           and paths["regions_equal"] and len(python["pixels"]) == len(native["pixels"])
                           == len(backdrop["pixels"]))
    verdict["split"] = _split_rows(rows, switch_input)
    verdict["mapping"] = dict(native["mapping"], python_frames=len(mappings))
    verdict["classes"] = classify_differences(native, python, switch_input)
    if rows:
        worst = max(rows, key=lambda row: (row["max_level"], row["pixels"]))
        verdict["worst"] = worst
        verdict["crops"] = _write_native_crops(Path(out), run.replace(":", "_").replace("=", "-").replace("@", "_at_"),
                                               native, python, worst)
    return verdict


def run_native(out: Path, *, module_dir: Path, offers: bool, seconds: float = 5.5, only: tuple[str, ...] = (),
               against: Path | None = None, placements: tuple[str, ...] = PLACEMENTS, mode: str = "spectrum",
               recording: str | None = None) -> dict:
    """``native_parity`` over ``mode``'s widened run set (``conventions_identity.mode_runs``; a mode of the route's
    ``NATIVE_MODE_IDS``) at the rig's own placement, and ``OVERSCAN_RUNS`` again at each other placement of
    ``placements`` (keyed ``run@placement``); the report. ``against``: an accepted report this one is compared with
    (``against_baseline``)."""
    baseline = json.loads(Path(against).read_text(encoding="utf-8")) if against is not None else None
    import tools.expanded_visualizer_evidence as evidence
    from rendering.native import load
    from tools import conventions_identity
    from widgets.spotify_visualizer import engine_worker_link

    core = load(module_dir)
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    # ``recording``: the first ``seconds`` of one of the operator's recorded takes (logs/visualizer_recordings, read
    # only) instead of the shipped Studio clip's opening.
    clip = evidence.load_recording(recording, seconds) if recording else evidence.shipped_clip(seconds)
    from rendering.quick.visualizer.native_route import NATIVE_MODE_IDS

    if mode not in NATIVE_MODE_IDS:
        raise ValueError(f"the native route draws {sorted(NATIVE_MODE_IDS)}, not {mode!r}")
    report: dict = {"mode": mode, "offers": offers, "seconds": seconds, "display": list(DISPLAY), "clip": clip.name,
                    "clip_frames": len(clip.frames), "results": {}}
    started = time.perf_counter()
    runs = conventions_identity.mode_runs(mode, offers)
    planned = [(suffix, settings, "display") for suffix, settings in runs] if "display" in placements else []
    planned += [(suffix, settings, placement) for placement in placements if placement != "display"
                for suffix, settings in runs if suffix in OVERSCAN_RUNS]
    try:
        for suffix, settings, placement in planned:
            key = f"{mode}{suffix}" if placement == "display" else f"{mode}{suffix}@{placement}"
            if only and key not in only:
                continue
            engine_worker_link.reset_run_state_for_testing()
            verdict = native_parity(core, mode, suffix, settings, clip.frames, out, placement=placement)
            report["results"][key] = verdict
            print(f"[NATIVE] {key:48s} {verdict['frames_drawn']} frames, native {verdict['native_published']}"
                  f" published; differing inputs {verdict['differing_inputs']}, pixels "
                  f"{verdict['differing_pixels_total']}, max level {verdict['max_level']}; card origin "
                  f"{verdict['outer_origin']} (device fraction {verdict['outer_origin_device_fraction']}); "
                  f"{'IDENTICAL' if verdict['identical'] else 'DIFFERENT'}; edge pixels in the worst frame "
                  f"{verdict['rule_a']['edge_pixels_worst_frame']}; rule (a) {verdict['rule_a']['bound']}: "
                  f"{'PASS' if verdict['pass'] else 'FAIL'}", flush=True)
    finally:
        report["elapsed_s"] = round(time.perf_counter() - started, 1)
        report["identical"] = bool(report["results"]) and all(v["identical"] for v in report["results"].values())
        report["pass"] = bool(report["results"]) and all(v["pass"] for v in report["results"].values())
        if baseline is not None:
            report["against"] = {"baseline": str(against), **against_baseline(baseline, report)}
            for key, entry in report["against"]["runs"].items():
                print(f"[AGAINST] {key:40s} {'SAME' if entry['same'] else 'DIFFERENT ' + json.dumps(entry)}", flush=True)
            print(f"[AGAINST] {'SAME AS THE BASELINE' if report['against']['same'] else 'NOT THE BASELINE'}: {against}",
                  flush=True)
        (out / "native_render_parity.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    return report


#: What a rule (a) report shares with an accepted one, run by run, when the native frames are bit-identical to that
#: run's (the Python renderer is the same, so the same differences mean the same native pixels).
BASELINE_KEYS = ("frames_drawn", "native_frames", "differing_inputs", "differing_pixels_total", "max_level",
                 "differences")


def against_baseline(baseline: dict, report: dict) -> dict:
    """``report`` (``run_native``'s) against an accepted ``baseline`` report: per run, what differs (a run on one side
    only differs). Where both keep frame hashes, the native frames' hashes decide (``native_hashes``; whether the Python
    reference's own frames moved is reported beside, ``python_same``): ``same`` is bit-identical native frames. Else
    only the keys of ``BASELINE_KEYS`` are compared, which proves equal difference rows, never equal frames (audit N29
    round 2, L8): such a run is ``difference_identical`` at best and never ``same``. ``same``: every run of both
    compared by hashes, nothing differing; ``difference_identical``: every run's differences equal, by either."""
    old, new = dict(baseline.get("results") or {}), dict(report.get("results") or {})
    runs: dict = {}
    for key in sorted(set(old) | set(new)):
        a, b = old.get(key), new.get(key)
        if a is None or b is None:
            runs[key] = {"same": False, "only_in": "this run" if a is None else "the baseline"}
            continue
        if "native_hashes" in a and "native_hashes" in b:
            changed = [i for i, (x, y) in enumerate(zip(a["native_hashes"], b["native_hashes"])) if x != y]
            if len(a["native_hashes"]) != len(b["native_hashes"]):
                changed.append("count")
            runs[key] = {"same": not changed, "by": "native_hashes", "native_changed": changed[:40],
                         "python_same": a.get("python_hashes") == b.get("python_hashes"),
                         "max_level": b.get("max_level"), "native_frames": b.get("native_frames")}
            continue
        differing = [name for name in BASELINE_KEYS
                     if name not in a or name not in b or json.loads(json.dumps(a[name])) != json.loads(json.dumps(b[name]))]
        runs[key] = {"same": False, "difference_identical": not differing, "by": "differences",
                     "differing": differing, "max_level": b.get("max_level"), "native_frames": b.get("native_frames")}
    return {"same": bool(runs) and all(entry["same"] for entry in runs.values()),
            "difference_identical": bool(runs) and all(entry.get("difference_identical", entry["same"])
                                                        for entry in runs.values()),
            "runs": runs}


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
    parser.add_argument("--native", action="store_true",
                        help="rule (a) of N2.5: Spectrum drawn by the native item against the Python renderer, in "
                             "process, single-sampled (needs --module-dir)")
    parser.add_argument("--module-dir", type=Path, default=Path("release/native_module"))
    parser.add_argument("--offers", action="store_true",
                        help="with --native: the widened run set (both variants and every Choice offer)")
    parser.add_argument("--runs", nargs="*", default=(), help="with --native: only these run keys (<mode>[:...])")
    parser.add_argument("--mode", default="spectrum",
                        help="with --native: the native mode drawn (the route's NATIVE_MODE_IDS: spectrum, devcurve)")
    parser.add_argument("--surface-format", choices=("rgba8", "rgba16f"), default=None,
                        help="with --native: the native item's surface texels (default: the route's own)")
    parser.add_argument("--unprimed", action="store_true",
                        help="with --native: no render before the owner exists and no route prepare at attach (the "
                             "product's unprimed path, N29 round 2 M3; reported, not a gate)")
    parser.add_argument("--placements", nargs="+", default=list(PLACEMENTS), choices=PLACEMENTS,
                        help="with --native: the card's placements (display: the rig's own; overscan: Display 1's R-63 "
                             "window with the card's origin half a device pixel off the grid, variants a and b)")
    parser.add_argument("--against", type=Path, default=None,
                        help="with --native: an accepted native_render_parity.json; the run passes when every run's "
                             "differences equal it (bit-identical native frames)")
    parser.add_argument("--recording", default=None,
                        help="with --native: one of the operator's recorded takes (logs/visualizer_recordings/<name>"
                             ".jsonl, its first --seconds) instead of the shipped Studio clip")
    args = parser.parse_args(argv)
    # The stills (contact sheets, difference maps) and the report are written into owner scratch and published to
    # ``--out`` by the evidence publisher (``tools/evidence_media.py``); stills stay PNG, lossless.
    evidence_media.redirect_output(args, "out", "owner_render_parity")
    try:
        import psutil
        psutil.Process().nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    except Exception:
        pass
    from rendering.quick.bootstrap import configure_quick_graphics

    configure_quick_graphics(reason="owner-render-parity")      # Qt Quick on OpenGL, as the product selects it
    from PySide6.QtWidgets import QApplication

    app = QApplication(["owner-render-parity"])
    try:
        if args.native:
            global NATIVE_SURFACE_FORMAT, NATIVE_UNPRIMED
            NATIVE_SURFACE_FORMAT = args.surface_format
            NATIVE_UNPRIMED = bool(args.unprimed)
            report = run_native(args.out, module_dir=args.module_dir.resolve(), offers=args.offers,
                                seconds=args.seconds, only=tuple(args.runs),
                                against=None if args.against is None else args.against.resolve(),
                                placements=tuple(args.placements), mode=args.mode, recording=args.recording)
        else:
            report = run(args.out, modes=args.modes, variants=tuple(args.variants), samplings=tuple(args.sampling),
                         seconds=args.seconds, controls=not args.skip_controls)
    except BaseException:
        evidence_media.finish(1)                # a run that broke: its scratch is kept and its path printed
        raise
    del app
    # A run that finished is published whatever its verdict: the frames of a difference are the evidence.
    evidence_media.finish(0)
    if "against" in report:
        return 0 if report["against"]["same"] else 1
    if "pass" in report:                                  # --native: rule (a)'s verdict (rule_a_verdict)
        return 0 if report["pass"] else 1
    return 0 if report["identical"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
