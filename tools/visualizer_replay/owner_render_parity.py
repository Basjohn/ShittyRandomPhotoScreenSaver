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
    same passes, programs, post chain and tier. The native route's Waveform program takes the same single sample
    (``native_route.waveform_program`` reads ``waveform.SCENE_SAMPLES`` when it builds): rule (a) judges a multisampled
    scene by its single-sampled form, as the transitions' (D8 point 1; the proof guide, section 3), and its 4x form by
    rule (b) (N5.4: P's first run compared the route's 4x scene with Python's single-sampled one)."""
    from rendering.quick.scene3d import waveform
    from rendering.quick.scene3d.target import SceneTarget

    begin = SceneTarget.begin
    samples_before = waveform.SCENE_SAMPLES

    def single(self, frame, samples, *args, **kwargs):
        del samples
        return begin(self, frame, 1, *args, **kwargs)

    SceneTarget.begin = single
    waveform.SCENE_SAMPLES = 1
    try:
        yield
    finally:
        SceneTarget.begin = begin
        waveform.SCENE_SAMPLES = samples_before


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

    def replace_last(self, item: tuple[tuple[int, ...], bytes]) -> None:
        """The last frame replaced (a control's changed frame), written at the file's end."""
        self._entries.pop()
        self.append(item)

    def __getitem__(self, index: int) -> tuple[tuple[int, ...], bytes]:
        shape, offset, size = self._entries[index]
        self._file.seek(offset)
        return shape, self._file.read(size)

    def __iter__(self):
        return (self[index] for index in range(len(self)))


class _LastFrame:
    """``_SpilledFrames``' interface for a run that judges nothing from pixels (``native_only``: its output is each
    frame's hash): only the latest frame is held, so no frame of the take is stored anywhere. ``on_frame`` still
    receives the frame just drawn; any other index is gone."""

    def __init__(self) -> None:
        self.count = 0
        self.last: tuple[tuple[int, ...], bytes] | None = None

    def append(self, item: tuple[tuple[int, ...], bytes]) -> None:
        self.count += 1
        self.last = item

    def __len__(self) -> int:
        return self.count

    def replace_last(self, item: tuple[tuple[int, ...], bytes]) -> None:
        self.last = item

    def __getitem__(self, index: int) -> tuple[tuple[int, ...], bytes]:
        if index != self.count - 1 or self.last is None:
            raise IndexError(f"frame {index}: this run keeps no frames but the latest")
        return self.last


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
        #: The mode bound to the hidden scene's Visualizer item at each frame (None when skipped or before any
        #: activation), index-aligned with the records. Kept beside the records, never in them: the worker path
        #: binds the partner at its commit reply, not at the in-process input, so records must not carry it.
        self.modes: list[str | None] = []
        #: Whether each frame's lit share is measured (6.7 ms a frame on Bubble's card): only ``rendered_parity`` reads
        #: it, never a native or mask run (fast-proof part 2, step 2).
        self.measure_lit = True
        #: The inputs drawn (None: every one): a windowed run (``coverage_windows``) skips the drawing of the rest, while
        #: the owner's simulation ticks every input (guide section 3: never restarted at a window).
        self.draw_inputs: set | None = None
        #: A backdrop run's (``content_backdrop``) frames of the reference's own background, index-aligned with
        #: ``frames``: each frame's region with the cleared rectangle as it stood before the clear (``under_frame``).
        self.under = _SpilledFrames() if _UNDER_CAPTURE["active"] else None
        self._fbo = 0
        #: GL error codes the drawn frames left pending, by code (``_read`` takes them before its own calls). Qt's GL
        #: backend applies sampler state to a multisample texture a binding samples (the core's transparency resolve),
        #: which the driver refuses with GL_INVALID_ENUM and ignores; PyOpenGL would report it at the read's first call.
        self.left_gl_errors: dict[int, int] = {}
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
        for _ in range(64):                              # the frame's own errors, not the read's (``left_gl_errors``)
            code = int(gl.glGetError())
            if code == gl.GL_NO_ERROR:
                break
            self.left_gl_errors[code] = self.left_gl_errors.get(code, 0) + 1
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

    def under_frame(self, pixels, region: tuple[int, int, int, int], captures: list):
        """The frame's region (``pixels``, top-down RGBA) with each rectangle a backdrop clear took
        (``content_backdrop``'s captures, GL bottom-up in the scene's target) put back as it stood before the clear: what
        the reference's own draw shows there where nothing is drawn. Outside the cleared rectangles both draws are the
        same, so the frame's own pixels stand. The first capture of a frame wins (it is what the reference drew over); a
        capture from a target other than the hidden texture fails, never maps wrong."""
        import numpy

        out = numpy.array(pixels, copy=True)
        left, top, width, height = region
        full_w, full_h = self.host.pixels
        for capture in reversed(captures):
            if tuple(capture["target"]) != (full_w, full_h):
                raise RuntimeError(f"a backdrop clear in a target of {capture['target']}, the hidden texture is "
                                   f"{(full_w, full_h)}: its rectangle cannot be placed")
            c_left, c_bottom, c_width, c_height = capture["rect"]
            c_top = full_h - c_bottom - c_height
            rows = (max(top, c_top), min(top + height, c_top + c_height))
            cols = (max(left, c_left), min(left + width, c_left + c_width))
            if rows[0] >= rows[1] or cols[0] >= cols[1]:
                continue
            taken = numpy.flipud(capture["pixels"])
            out[rows[0] - top:rows[1] - top, cols[0] - left:cols[1] - left] = \
                taken[rows[0] - c_top:rows[1] - c_top, cols[0] - c_left:cols[1] - c_left]
        return out

    def frame(self, index: int) -> dict:
        """Draw the hidden scene and record what it drew: the card's region, and the whole display when due."""
        if self.draw_inputs is not None and index not in self.draw_inputs:
            self.frames.append(((0,), b""))              # outside every window: nothing drawn, indices kept
            if self.under is not None:
                self.under.append(((0,), b""))
            self.modes.append(None)
            return {"region": None, "hash": None, "skipped": True}
        host = self.host
        _UNDER_CAPTURE["captures"] = []
        host.render()
        if self._region is None:
            raise RuntimeError("the owner committed no presentation record before its first frame")
        region = self._region
        pixels = self._read(region)
        if self.under is not None:
            under = self.under_frame(pixels, region, _UNDER_CAPTURE["captures"])
            self.under.append((under.shape, zlib.compress(under.tobytes(), 1)))
        raw = pixels.tobytes()
        record = {"region": list(region), "hash": hashlib.sha256(raw).hexdigest()}
        self.modes.append(self._drawing_mode())  # the mode whose frame this is: judged under its own bounds
        if self.measure_lit:
            self.lit.append(float((pixels[..., :3].max(axis=2) > LIT_LEVEL).mean()))
        self.frames.append((pixels.shape, zlib.compress(raw, 1)))
        if index % FULL_EVERY == 0:
            record["full"] = hashlib.sha256(self._read((0, 0, *host.pixels)).tobytes()).hexdigest()
        return record

    def _drawing_mode(self) -> str | None:
        """The mode bound to the hidden scene's Visualizer item now (None before any activation)."""
        item = getattr(self.host.scene, "_visualizer_item", None) if self.host is not None else None
        identity = getattr(item, "render_identity", None) if item is not None else None
        return None if identity is None else str(identity.mode_id)

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


def _placed_runs(mode, runs, placements, only):
    """Resolve explicit run keys while keeping the default overscan set bounded."""
    requested = set(only)
    planned = []
    for placement in PLACEMENTS:
        if placement not in placements:
            continue
        for suffix, settings in runs:
            key = f"{mode}{suffix}" if placement == "display" else f"{mode}{suffix}@{placement}"
            if requested:
                if key not in requested:
                    continue
            elif placement != "display" and suffix not in OVERSCAN_RUNS:
                continue
            planned.append((key, suffix, settings, placement))
    missing = requested - {key for key, _, _, _ in planned}
    if missing:
        raise ValueError(f"unavailable run keys for the selected mode and placements: {', '.join(sorted(missing))}")
    return planned


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
#: Rule (a)'s scatter per mode (D12 bounds, lead's decisions 17 Nov for Bubble): pixels outside the mask exactly one
#: level off, the NativeFragmentPass two-compiler case (Python's driver-compiled composed GLSL against the qsb pack).
#: Bubble: measured worst 45 a frame on the four 60 s recorded takes (38, 36, 40 and 45; n5_1_bubble/
#: 20261117_rule_a_60s_*), 34 on the 5.5 s replay (20261117_steady_residual_classes/), times 1.5: 68 (checkpoint audit
#: 7 M3). Oscilloscope (lead's decision 21 Nov; D12 "The pixel tolerance"): its beam's one-level pixels outside the
#: mask are judged against Python's own placement variance. The Python renderer against itself, the same frames
#: drawn through the owner's window and through an item-sized window plus a margin (the rasteriser's interpolation
#: follows the viewport), differs by at most 52 such pixels a frame: 48 at 1.5 and 52 at 48/35, over 7 runs x 36
#: frames each (n5_1_oscilloscope/20261121_viewport_class_1_5/ and _48_35/, viewport_probe.py). Bound: that worst,
#: not multiplied. Every other mode admits none.
RULE_A_SCATTER_PIXELS = {"bubble": 68, "oscilloscope": 52}
#: The scatter's spread per mode (checkpoint audit 7 M1): the largest group of touching scatter pixels a frame may hold.
#: Bubble: measured largest 15 on the 5.5 s replay's 2,430 steady pixels (1,908 with no scatter neighbour; most
#: neighbours of one pixel 6; 20261117_steady_residual_classes/steady_classification.json), times 1.5: 22 (17 on the
#: four 60 s takes with ties joined, checkpoint audit 8 M1). A solid block fails, and so do ties inside one: ties join
#: the groups they touch (the 17 Nov isolation clause this replaced was retired by the lead, 21 Nov).
RULE_A_SCATTER_GROUP = {"bubble": 22}
#: The scatter's density per mode (checkpoint audit 8 M1): the most scatter and tie pixels one 16 x 16 window may hold
#: (``pixel_tolerance.SCATTER_WINDOW``). Bubble: measured worst 17 on the four 60 s recorded takes (16, 17, 16 and 17;
#: fast_proof/20261120_m2_* and 20261121_m2_*, ties joined), times 1.5 rounded up: 26.
RULE_A_SCATTER_WINDOW: dict[str, int] = {"bubble": 26}
#: A mode judged by its frame statistics instead of the classes (``pixel_tolerance`` "Statistics"): mode -> (mean
#: absolute, mean signed, share 2 to 3 levels off, share past 3), its single-sampled form against Python's.
#: Waveform Ribbon: layer P's measured worst times 1.5 (two significant figures, rounded up), within the lead's
#: provisional bound (0.16, 0.10, 3 %, 0.6 %, 22 Nov), over 35,531 judged frames of every reaction mode (one full take
#: each, display and overscan for variants a and b, coverage windows from the other two takes, late-song windows
#: included; n5_4/20261122_p_*): worst mean 0.042 and signed 0.041 (human Group Wave input 3835), 2-3 levels 0.34 %
#: (ragdoll Group Wave window, input 66), past 3 0.48 % (human Group Wave input 1255), whose 1.5 times (0.72 %) the
#: provisional 0.6 % caps. 13 frames holding a saturated square (variant b, the Python renderer's own defect too) are
#: set aside, never admitted. Each planted control fails it on almost every frame (human Frozen Past windows, 1,158
#: frames): the ribbons half a pixel right 1,153, the fog x 1.03 1,146, the bloom x 1.03 1,155, the camera x 1.05 and
#: the bloom off 1,158 (n5_4/20261122_p_control_*). Its scene's geometry is
#: placed through the core's target clip (a 64-pixel bucket) where Python's viewport places it directly, so where a
#: ribbon edge runs along a row of pixel centres the whole row flips (P, ragdoll Frozen Past, input 997: 339 pixels past
#: 3 levels and 1,142 at 2 to 3 along one near-horizontal edge, no frame offset: Python's neighbouring frames differ by
#: 129,000), and its bloom and fog round one level apart over wide soft regions (groups of 3,097 one-level pixels).
RULE_A_STATISTICS: dict[str, tuple[float, float, float, float]] = {"waveform_ribbon": (0.063, 0.062, 0.0052, 0.006)}
#: A statistical mode's classes: counted and reported, never a reason.
_COUNTED = 10 ** 9


def composite_tolerance(mode: str | None = None):
    """The composite's tolerance (``RULE_A_*``) as the shared ``pixel_tolerance.Tolerance``; ``mode`` adds its D12
    scatter (``RULE_A_SCATTER_PIXELS``), or its statistical bound (``RULE_A_STATISTICS``)."""
    from tools import pixel_tolerance

    statistics = RULE_A_STATISTICS.get(mode)
    if statistics is not None:
        return pixel_tolerance.Tolerance(f"composite (rule a, {mode}, statistical)", masked_level=RULE_A_FILL_LEVEL,
                                         scatter_pixels=_COUNTED, tie_pixels=_COUNTED, flip_pixels=_COUNTED,
                                         tie_level=RULE_A_EDGE_LEVEL, edge_class=True,
                                         scatter_cluster_pixels=_COUNTED, scatter_window_pixels=_COUNTED,
                                         statistics=pixel_tolerance.FrameStatistics(*statistics))
    scatter = RULE_A_SCATTER_PIXELS.get(mode, 0)
    return pixel_tolerance.Tolerance(f"composite (rule a, {mode})" if scatter else "composite (rule a)",
                                     masked_level=RULE_A_FILL_LEVEL, scatter_pixels=scatter,
                                     tie_pixels=RULE_A_EDGE_PIXELS_PER_FRAME, tie_level=RULE_A_EDGE_LEVEL,
                                     edge_class=True, scatter_cluster_pixels=RULE_A_SCATTER_GROUP.get(mode),
                                     scatter_window_pixels=RULE_A_SCATTER_WINDOW.get(mode))


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


#: The backdrop run's capture (``content_backdrop``): while ``active``, each mode draw's cleared rectangle as it stood
#: before the clear (what the reference's own draw shows there where nothing is drawn), for ``SceneMirror.frame``.
_UNDER_CAPTURE: dict = {"active": False, "captures": []}


def _read_bound_framebuffer(gl, left: int, bottom: int, width: int, height: int):
    """Bottom-up RGBA of a rectangle of the framebuffer bound for drawing (GL coordinates); the read binding, pack
    alignment and pack buffer restored."""
    import numpy

    draw_fbo = int(gl.glGetIntegerv(gl.GL_DRAW_FRAMEBUFFER_BINDING))
    read_fbo = int(gl.glGetIntegerv(gl.GL_READ_FRAMEBUFFER_BINDING))
    pack_buffer = int(gl.glGetIntegerv(gl.GL_PIXEL_PACK_BUFFER_BINDING))
    alignment = int(gl.glGetIntegerv(gl.GL_PACK_ALIGNMENT))
    gl.glBindFramebuffer(gl.GL_READ_FRAMEBUFFER, draw_fbo)
    gl.glBindBuffer(gl.GL_PIXEL_PACK_BUFFER, 0)
    gl.glPixelStorei(gl.GL_PACK_ALIGNMENT, 1)
    try:
        data = gl.glReadPixels(left, bottom, width, height, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE)
    finally:
        gl.glPixelStorei(gl.GL_PACK_ALIGNMENT, alignment)
        gl.glBindBuffer(gl.GL_PIXEL_PACK_BUFFER, pack_buffer)
        gl.glBindFramebuffer(gl.GL_READ_FRAMEBUFFER, read_fbo)
    raw = data if isinstance(data, (bytes, bytearray)) else numpy.asarray(data).tobytes()
    return numpy.frombuffer(raw, dtype=numpy.uint8).reshape(height, width, 4)


@contextlib.contextmanager
def content_backdrop(colour: tuple[int, int, int] = MASK_BACKDROP):
    """For the block, the Python render host clears its viewport (inside any scissor already set) to ``colour`` before
    each mode draw: the reference drawn over a second background (``rule_a_masks``). Before each clear the rectangle is
    read as it stands (``_UNDER_CAPTURE``): the reference's own background there, so a pixel is judged bare only where
    it equals its background in both draws (``pixel_tolerance.translucent_by_backgrounds``). Nothing else about a draw
    changes; the GL state it touches is restored."""
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
            if _UNDER_CAPTURE["active"]:
                _UNDER_CAPTURE["captures"].append({
                    "rect": (left, bottom, right - left, top - bottom), "target": (x + w, y + h),
                    "pixels": _read_bound_framebuffer(gl, left, bottom, right - left, top - bottom)})
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
    _UNDER_CAPTURE["active"] = True
    _UNDER_CAPTURE["captures"] = []
    try:
        yield
    finally:
        QuickVisualizerRenderHost.render = render
        _UNDER_CAPTURE["active"] = False
        _UNDER_CAPTURE["captures"] = []


def rule_a_masks(python: dict, backdrop: dict) -> dict:
    """Per input, the pixels the Python renderer draws translucent: its run against the same run drawn over
    ``MASK_BACKDROP`` (``content_backdrop``), ``pixel_tolerance.translucent_by_backgrounds``, with the backdrop run's
    ``under`` frames as the first draw's own background (a pixel is bare only where it equals its background in both
    draws). An input whose two draws have different regions has no mask (every pixel exact)."""
    from tools import pixel_tolerance

    under = backdrop["under"]
    masks = {}
    for index, (x, y) in enumerate(zip(python["pixels"], backdrop["pixels"])):
        if x["region"] != y["region"]:
            continue
        masks[index] = pixel_tolerance.translucent_by_backgrounds(_pixels(python, index), _pixels(backdrop, index),
                                                                  MASK_BACKDROP, _pixels({"frames": under}, index))
    return masks


def rule_a_frames(native: dict, python: dict, masks: dict, mode: str | None = None) -> list[dict]:
    """``rule_a_frame`` for every input whose drawn region differs between the native run and the Python run."""
    frames = []
    for index, (x, y) in enumerate(zip(native["pixels"], python["pixels"])):
        if x["hash"] == y["hash"]:
            continue
        if x["region"] != y["region"]:
            frames.append({"pass": False, "reasons": [f"input {index}: the regions differ"], "max_level": None,
                           "input": index})
            continue
        verdict = rule_a_frame(_pixels(native, index), _pixels(python, index), masks.get(index), mode)
        verdict["input"] = index
        frames.append(verdict)
    return frames


#: ``--surface-format``: the native item's surface texels for this run (None: the route's own choice).
NATIVE_SURFACE_FORMAT: str | None = None
#: ``--judge-workers``: rule (a)'s frames judged in this many worker processes (0: in this one), merged in input order.
JUDGE_WORKERS = 0
#: ``--native-control``: a negative control on the native frames (``shift``: one level up on every colour channel).
NATIVE_CONTROL: str | None = None
#: ``--shader-control``: the native item draws this ``native_stream_player.SHADER_CONTROLS`` pack (``native_shader_control``).
NATIVE_SHADER_CONTROL: str | None = None
#: ``--stage-control``: the module's harness control of this name held on for the run (``stage_control``; ABI 32's
#: ``card_triangle``: the mode's v_uv passes over the full triangle again, the card quad's negative control).
NATIVE_STAGE_CONTROL: str | None = None
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

    def __init__(self, core, *, keep_frames: bool = True) -> None:
        super().__init__()
        if not keep_frames:
            self.frames = _LastFrame()
        self.core = core
        self.window_host = None
        self.route = None
        self.native_frames = 0
        # The mapping control: the Python renderer's window-pixel map per drawn frame (``_python_mappings_run``).
        self.python_mappings: list | None = None
        self.mapping_compared = 0
        self.mapping_identical = 0
        #: Called with (input, its record, its compressed frame) as each frame is drawn (``LiveJudge.frame``).
        self.on_frame = None

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
        record = super().frame(index)
        if NATIVE_CONTROL == "shift" and not record.get("skipped"):
            # The method proof's control: every native frame one level up on its colour channels.
            import numpy

            shape, data = self.frames[len(self.frames) - 1]
            pixels = numpy.frombuffer(zlib.decompress(data), dtype=numpy.uint8).reshape(shape).copy()
            pixels[..., :3] = numpy.minimum(pixels[..., :3].astype(numpy.int16) + 1, 255).astype(numpy.uint8)
            raw = pixels.tobytes()
            self.frames.replace_last((shape, zlib.compress(raw, 1)))
            record = dict(record, hash=hashlib.sha256(raw).hexdigest())
        if self.on_frame is not None:
            self.on_frame(index, record, self.frames[len(self.frames) - 1])
        return record

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


def drawn_run(mode: str, script, *, worker: bool, supervisor: Any, namespace: int | None, settings: dict,
              lit: bool = True) -> dict:
    """``owner_worker_gate.identity_run`` with the owner's scene drawn: its report plus ``frames`` and ``lit`` (empty
    when ``lit`` is False: a run whose lit share nobody reads)."""
    from tools.visualizer_replay import owner_worker_gate as gate

    mirror = SceneMirror()
    mirror.measure_lit = bool(lit)
    report = gate.identity_run(mode, script, worker=worker, supervisor=supervisor, namespace=namespace,
                               settings=settings, scene_mirror=mirror)
    report["lit"] = mirror.lit
    report["modes"] = mirror.modes
    report["frames"] = mirror.frames
    if mirror.under is not None:
        report["under"] = mirror.under                     # a backdrop run's (``content_backdrop``)
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


def native_drawn_run(mode: str, script, *, settings: dict, core, python_mappings: list | None = None,
                     on_frame=None, draw_inputs: set | None = None, keep_frames: bool = True) -> dict:
    """``drawn_run`` in process with the native Spectrum drawing Spectrum's activations (``NativeSceneMirror``).
    ``on_frame``: called as each frame is drawn (``NativeSceneMirror.on_frame``); ``draw_inputs``: only these inputs are
    drawn (``SceneMirror.draw_inputs``). ``keep_frames`` False: no frame is stored (a hash-only run, ``native_only``)."""
    from tools.visualizer_replay import owner_worker_gate as gate

    mirror = NativeSceneMirror(core, keep_frames=keep_frames)
    mirror.measure_lit = False                       # no native run reads it
    mirror.draw_inputs = draw_inputs
    mirror.on_frame = on_frame
    mirror.python_mappings = python_mappings
    report = gate.identity_run(mode, script, worker=False, supervisor=None, namespace=None, settings=settings,
                               scene_mirror=mirror)
    report["lit"] = mirror.lit
    report["modes"] = mirror.modes
    report["frames"] = mirror.frames
    report["native_frames"] = mirror.native_frames
    report["native_published"] = mirror.native_published
    report["mapping"] = {"compared": mirror.mapping_compared, "identical": mirror.mapping_identical}
    report["outer_origin"] = mirror.first_outer_origin
    report["left_gl_errors"] = {hex(code): count for code, count in mirror.left_gl_errors.items()}
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
        row = _difference_row(index, delta)
        if row is not None:
            rows.append(row)
    return rows


def _difference_row(index: int, delta) -> dict | None:
    """``frame_differences``' row of one input from its per-pixel ``delta`` (None: no pixel differs)."""
    import numpy

    ys, xs = numpy.nonzero(delta)
    if not len(xs):
        return None
    return {"input": index, "pixels": int(len(xs)), "max_level": int(delta.max()),
            "bbox": [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())],
            "levels": {str(level): int((delta == level).sum()) for level in sorted(set(delta[delta > 0].tolist()))[:8]}}


def judged_pass(native: dict, python: dict, masks: dict, switch_input: int, mode: str | None = None) -> dict:
    """``pair_difference``, ``frame_differences``, ``rule_a_frames`` and ``classify_differences`` of one native run
    against its Python run in a single pass (fast-proof part 2, step 1): each differing input decompressed once and its
    delta computed once and shared; the same results, value for value (``tests/test_owner_render_parity_judge.py``)."""
    judge = LiveJudge(python, masks, switch_input, mode)
    for index, record in enumerate(native["pixels"]):
        judge.frame(index, record, native["frames"][index])
    return judge.result()


def _judge_one(index: int, record: dict, reference_record: dict, frame: tuple, reference_frame: tuple, mask,
               switch_input: int, mode: str | None) -> dict:
    """One differing native input against its Python input (records, compressed frames, mask), alone: what it adds to
    rule (a)'s result. Pure, so it may run in a worker process (``LiveJudge(workers=...)``)."""
    import numpy

    from tools import pixel_tolerance

    def pixels(item):
        shape, data = item
        return numpy.frombuffer(zlib.decompress(data), dtype=numpy.uint8).reshape(shape)

    out: dict = {"index": index, "region_differs": False, "verdict": None, "failed": None, "row": None,
                 "classes": None, "max_pixels": 0, "max_level": 0}
    if record["region"] != reference_record["region"]:
        out["region_differs"] = True
        if record["hash"] != reference_record["hash"]:
            verdict = {"pass": False, "reasons": [f"input {index}: the regions differ"], "max_level": None,
                       "input": index}
            out["verdict"] = verdict
            out["failed"] = _failed_record(verdict, pixels(frame), pixels(reference_frame), mask)
        return out
    if record["hash"] == reference_record["hash"]:
        return out                                          # only the whole-display hash differs: counted, not sized
    drawn, reference = pixels(frame), pixels(reference_frame)
    delta = numpy.abs(drawn.astype(numpy.int16) - reference).max(axis=2)
    out["max_pixels"] = int((delta > 0).sum())
    out["max_level"] = int(delta.max())
    out["row"] = _difference_row(index, delta)
    verdict = pixel_tolerance.judge(drawn, reference, composite_tolerance(mode), mask=mask, delta=delta)
    verdict["input"] = index
    out["verdict"] = verdict
    if not verdict["pass"]:
        out["failed"] = _failed_record(verdict, drawn, reference, mask)
    classes = _new_classes()
    _classify_frame(classes, index, reference, delta, switch_input)
    out["classes"] = classes
    return out


class LiveJudge:
    """Rule (a)'s judge, one native frame at a time as it is drawn (fast-proof part 2, steps 4 and 5): against the
    Python run (drawn or cached first) and its masks, each frame is judged when it arrives (``_judge_one``), its
    failing record kept with its pixels (every failing frame, not the first eight), and with ``progress`` one line per
    frame appended to that file in input order (its hash, and a failing frame's verdict), so a killed run keeps what it
    judged. ``workers``: frames judged in that many worker processes, merged in input order (the same result as one
    process, ``tests/test_owner_render_parity_judge.py``). ``result`` is ``judged_pass``'s."""

    def __init__(self, python: dict, masks, switch_input: int, mode: str | None = None,
                 progress: Path | None = None, workers: int = 0, accepted: dict | None = None,
                 hash_lines: bool = True) -> None:
        self.python = python
        #: An accepted native run against the same Python reference (``accepted_entry``): a frame whose native hash is
        #: that run's keeps its accepted verdict (and failing record) instead of being judged again.
        self.accepted = accepted
        self.carried: list[int] = []
        #: False: progress lines only for failing frames (the drawing wrote each frame's hash line already).
        self.hash_lines = bool(hash_lines)
        self.masks = masks
        self.switch_input = int(switch_input)
        self.mode = mode
        self.progress = progress
        self.count = 0
        self.differing: list[int] = []
        self.paths = {"max_pixels": 0, "max_level": 0, "regions_equal": True}
        self.rows: list[dict] = []
        self.judged: list[dict] = []
        self.failed: list[dict] = []
        self.classes = _new_classes()
        self.skipped: set[int] = set()
        self._pool = None
        if workers and int(workers) > 0:
            from concurrent.futures import ProcessPoolExecutor

            self._pool = ProcessPoolExecutor(max_workers=int(workers))
        self._pending: list = []                     # (index, its record, a future or a done result), input order

    def frame(self, index: int, record: dict, frame: tuple) -> None:
        """Judge native input ``index`` (its record and its compressed frame): at once, or in a worker."""
        self.count = max(self.count, index + 1)
        records = self.python["pixels"]
        if record.get("skipped"):
            self.skipped.add(index)                   # outside every window: not drawn, not judged
            self._pending.append((index, record, None))
        elif index < len(records) and record != records[index]:
            self.differing.append(index)
            # Each frame under the bounds of the mode that drew it (the partner's after the switch: its own).
            carried = self._carried(index, record)
            if carried is not None:
                self.carried.append(index)
                self._pending.append((index, record, carried))
                self._drain(block=False)
                return
            modes = self.python.get("modes") or ()
            drawn_by = (modes[index] if index < len(modes) else None) or self.mode
            arguments = (index, record, records[index], frame, self.python["frames"][index], self.masks.get(index),
                         self.switch_input, drawn_by)
            done = self._pool.submit(_judge_one, *arguments) if self._pool is not None else _judge_one(*arguments)
            self._pending.append((index, record, done))
        else:
            self._pending.append((index, record, None))
        self._drain(block=False)

    def _carried(self, index: int, record: dict) -> dict | None:
        """The accepted run's result for input ``index`` when the native frame is hash-identical to that run's (None:
        judge it)."""
        accepted = self.accepted
        if accepted is None:
            return None
        hashes = accepted["hashes"]
        verdict = accepted["verdicts"].get(index)
        if index >= len(hashes) or hashes[index] != record.get("hash") or verdict is None:
            return None
        return {"region_differs": False, "verdict": dict(verdict), "failed": accepted["failed"].get(index),
                "row": None, "classes": None, "max_pixels": 0, "max_level": 0}

    def _drain(self, *, block: bool) -> None:
        """Merge the pending frames' results in input order, as far as they are done (all, when ``block``)."""
        while self._pending:
            index, record, done = self._pending[0]
            if done is not None and hasattr(done, "result"):
                if not block and not done.done():
                    return
                done = done.result()
            self._pending.pop(0)
            verdict = None
            if done is not None:
                if done["region_differs"]:
                    self.paths["regions_equal"] = False
                self.paths["max_pixels"] = max(self.paths["max_pixels"], done["max_pixels"])
                self.paths["max_level"] = max(self.paths["max_level"], done["max_level"])
                if done["row"] is not None:
                    self.rows.append(done["row"])
                verdict = done["verdict"]
                if verdict is not None:
                    self.judged.append(verdict)
                if done["failed"] is not None:
                    self.failed.append(done["failed"])
                if done["classes"] is not None:
                    for name, entry in done["classes"].items():
                        total = self.classes[name]
                        total["pixels"] += entry["pixels"]
                        total["max_level"] = max(total["max_level"], entry["max_level"])
                        total["inputs"] += entry["inputs"]
            failing = verdict is not None and not verdict["pass"]
            if self.progress is not None and (self.hash_lines or failing):
                line = {"input": index, "hash": record.get("hash")}
                if failing:
                    line["failed"] = {k: verdict.get(k) for k in ("reasons", "max_level", "scatter", "ties",
                                                                  "scatter_group", "scatter_window")}
                with Path(self.progress).open("a", encoding="utf-8") as stream:
                    stream.write(json.dumps(line) + "\n")

    def result(self) -> dict:
        self._drain(block=True)
        if self._pool is not None:
            self._pool.shutdown()
            self._pool = None
        python_frames = len(self.python["pixels"])
        differing = self.differing
        first = differing[0] if differing else (None if self.count == python_frames else min(self.count,
                                                                                              python_frames))
        paths = {"first": first, "frames": len(differing), **self.paths}
        result = {"paths": paths, "rows": self.rows, "judged": self.judged, "classes": self.classes,
                  "failed": self.failed, "carried": list(self.carried)}
        if self.skipped:
            result["skipped"] = sorted(self.skipped)
        return result


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
        run = drawn_run(mode, script, worker=False, supervisor=None, namespace=None, settings=settings, lit=False)
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

    classes = _new_classes()
    for index, (a, b) in enumerate(zip(native["pixels"], python["pixels"])):
        if a["hash"] == b["hash"] or a["region"] != b["region"]:
            continue
        drawn, reference = _pixels(native, index), _pixels(python, index)
        delta = numpy.abs(drawn.astype(numpy.int16) - reference).max(axis=2)
        _classify_frame(classes, index, reference, delta, switch_input)
    return classes


def _new_classes() -> dict:
    return {name: {"pixels": 0, "max_level": 0, "inputs": 0} for name in
            ("card_edge_column", "peak_row", "cap_arc", "fade_frame", "other")}


def _classify_frame(classes: dict, index: int, reference, delta, switch_input: int) -> None:
    """``classify_differences`` for one differing input (its reference pixels and per-pixel ``delta``)."""
    import numpy

    ys, xs = numpy.nonzero(delta > 1)
    if not len(ys):
        return
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


def failed_frame_records(judged: list[dict], native: dict, python: dict, masks: dict, limit: int = 8) -> list[dict]:
    """The first ``limit`` failing frames of ``rule_a_frames``, each with its reasons and up to 40 pixels past one level
    (where, how far, the reference's own 3x3 range and both colours), so a long run's rare failure is classified
    without a rerun. A frame whose regions differ is kept with its reasons and no pixels (checkpoint audit 7 L1)."""
    failed = []
    for entry in (f for f in judged if not f.get("pass")):
        if limit is not None and len(failed) >= limit:
            break
        index = entry.get("input")
        if index is None:
            failed.append({"input": index, "reasons": entry.get("reasons", []), "pixels_past_one_level": []})
            continue
        failed.append(_failed_record(entry, _pixels(native, index), _pixels(python, index), masks.get(index)))
    return failed


def _failed_record(entry: dict, native, python, mask) -> dict:
    """One failing frame's record: its reasons and up to 40 pixels past one level (where, how far, the reference's own
    3x3 range and both colours); frames of other shapes keep their shapes and no pixels."""
    import numpy

    record = {"input": entry.get("input"), "reasons": entry.get("reasons", []), "pixels_past_one_level": []}
    a, b = numpy.asarray(native).astype(int), numpy.asarray(python).astype(int)
    if a.shape != b.shape:
        record["shapes"] = [list(a.shape), list(b.shape)]
        return record
    delta = numpy.abs(a - b)[..., :3].max(axis=2)
    ys, xs = numpy.nonzero(delta > 1)
    for y, x in list(zip(ys.tolist(), xs.tolist()))[:40]:
        patch = b[max(0, y - 1):y + 2, max(0, x - 1):x + 2, :3]
        record["pixels_past_one_level"].append({
            "x": x, "y": y, "level": int(delta[y, x]),
            "reference_range": int((patch.max(axis=(0, 1)) - patch.min(axis=(0, 1))).max()),
            "masked": bool(mask[y, x]) if mask is not None else False,
            "python": b[y, x].tolist(), "native": a[y, x].tolist()})
    return record


def rule_a_halves(judged: list[dict], switch_input: int, mode: str | None = None) -> dict:
    """The mode's shown span (before the switch) in halves: adaptive state (Dynamic Floor, normalisers) drifts with a
    clip's length, so a late divergence shows in the second half's figures, not in the whole run's worst. Every judged
    frame carries its input (a region mismatch included, checkpoint audit 7 L1); one without fails both halves."""
    half = switch_input // 2
    orphans = [f for f in judged if "input" not in f]
    return {name: {"inputs": [lo, hi],
                   **rule_a_verdict([f for f in judged if "input" in f and lo <= f["input"] < hi] + orphans, mode)}
            for name, lo, hi in (("first", 0, half), ("second", half, switch_input))}


def _python_reference(mode: str, script, settings: dict) -> tuple[dict, list]:
    """The Python side of a rule (a) run: its drawn run and (Spectrum) its window maps."""
    if mode == "spectrum":
        return _python_mappings_run(mode, script, settings)
    # A generic mode's card maps nothing per fragment (its uv is the core's, N29 round 2 M6): no mapping control.
    return drawn_run(mode, script, worker=False, supervisor=None, namespace=None, settings=settings, lit=False), []


def _python_masks(mode: str, script, settings: dict, python: dict) -> tuple[dict, int]:
    """Rule (a)'s mask: the same Python run over a second background (its translucent pixels); and that run's frame
    count."""
    with content_backdrop():
        backdrop = drawn_run(mode, script, worker=False, supervisor=None, namespace=None, settings=settings, lit=False)
    return rule_a_masks(python, backdrop), len(backdrop["pixels"])


def _recorded_python_reference(mode: str, script, settings: dict) -> tuple[dict, list, dict, int, dict]:
    """The Python run, its window maps, its masks and the backdrop's frame count (``_python_reference``,
    ``_python_masks``), with what drew them (``python_references.recording``: the sources a cached reference is
    checked against)."""
    from tools.visualizer_replay import python_references

    with python_references.recording() as used:
        python, mappings = _python_reference(mode, script, settings)
        masks, backdrop_frames = _python_masks(mode, script, settings, python)
    return python, mappings, masks, backdrop_frames, used.drawing()


def python_references_root() -> Path:
    from tools.visualizer_replay.python_references import DEFAULT_ROOT
    return DEFAULT_ROOT


def references_only(out: Path, *, mode: str, offers: bool, seconds: float, recording: str, references: Path,
                    placements: tuple[str, ...], only: tuple[str, ...] = ()) -> dict:
    """Port preparation (the guide's section 3, P): draw and store the cached Python references of ``mode``'s run set
    (``conventions_identity.mode_runs``, ``OVERSCAN_RUNS`` again at each other placement) for one take, before the mode
    has a native route. The same Python run, masks and cache key as ``native_parity`` (single-sampled scene targets,
    the placement's card), so the port's first native run reads them; a reference that already exists is kept. Each
    run's key, folder, frame count and wall time are reported."""
    import tools.expanded_visualizer_evidence as evidence
    from PySide6.QtGui import QGuiApplication
    from tools import conventions_identity
    from tools.visualizer_replay import python_references
    from widgets.spotify_visualizer import engine_worker_link

    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    clip = evidence.load_recording(recording, seconds)
    runs = conventions_identity.mode_runs(mode, offers)
    planned = _placed_runs(mode, runs, placements, only)
    report: dict = {"mode": mode, "clip": clip.name, "clip_frames": len(clip.frames), "seconds": seconds,
                    "references": str(references), "results": {}}
    dpr = float(QGuiApplication.primaryScreen().devicePixelRatio())
    for key_name, suffix, settings, placement in planned:
        engine_worker_link.reset_run_state_for_testing()
        key, made_of = python_references.reference_key(mode, suffix, settings, clip.name, clip.frames, placement, dpr)
        folder = Path(references) / key
        started = time.perf_counter()
        if python_references.load(folder, made_of) is not None:
            state, frames = "kept (already stored)", None
        else:
            script = parity_script(clip.frames, mode)
            with single_sample_scene_targets(), card_placement(placement):
                python, mappings, masks, backdrop_frames, drawing = _recorded_python_reference(mode, script,
                                                                                               settings)
                python_references.store(folder, made_of, python, masks, mappings, backdrop_frames, drawing=drawing)
            state, frames = "drawn and stored", len(python["pixels"])
        report["results"][key_name] = {"key": key, "folder": str(folder), "state": state, "frames": frames,
                                       "seconds": round(time.perf_counter() - started, 1)}
        (out / "python_references.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(key_name, report["results"][key_name], flush=True)
    return report


def native_only(core, mode: str, suffix: str, settings: dict, clip_frames, out: Path, placement: str = "display", *,
                against: dict | None = None) -> dict:
    """Native before against native after (the guide's section 3, an optimisation of a landed port): the native run
    alone, each frame's hash written to the run's progress file as it is drawn, against ``against`` (an accepted run's
    entry with ``native_hashes``) when given: no Python render and no tolerance, every frame whose hash changed is
    listed, and a different frame count fails."""
    script = parity_script(clip_frames, mode)
    switch_at = next(i for i, (kind, _v) in enumerate(script) if kind == "mode")
    switch_input = sum(1 for kind, _value in script[:switch_at] if kind == "input")
    run = f"{mode}{suffix}" if placement == "display" else f"{mode}{suffix}@{placement}"
    progress = Path(out) / f"progress_{run.replace(':', '_').replace('=', '-').replace('@', '_at_')}.jsonl"
    Path(out).mkdir(parents=True, exist_ok=True)
    progress.write_text("", encoding="utf-8")
    baseline = None if against is None else list(against.get("native_hashes") or [])
    changed: list[int] = []

    def hashed(index: int, record: dict, _frame) -> None:
        line = {"input": index, "hash": record["hash"]}
        if baseline is not None and (index >= len(baseline) or baseline[index] != record["hash"]):
            changed.append(index)
            line["changed"] = True
        with progress.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(line) + "\n")

    with single_sample_scene_targets(), card_placement(placement):
        native = native_drawn_run(mode, script, settings=settings, core=core, on_frame=hashed, keep_frames=False)
    hashes = [entry["hash"] for entry in native["pixels"]]
    verdict = {"mode": mode, "run": run, "placement": placement, "native_only": True, "inputs": native["inputs"],
               "switch_input": switch_input, "native_frames": native["native_frames"],
               "native_published": native["native_published"], "native_hashes": hashes,
               "region": native["pixels"][0]["region"] if native["pixels"] else None, "progress": str(progress),
               "frames_drawn": [None, len(hashes)]}
    if baseline is not None:
        half = switch_input // 2
        verdict["against"] = {"frames": [len(baseline), len(hashes)], "changed": changed,
                              "changed_halves": {"first": sum(1 for i in changed if i < half),
                                                 "second": sum(1 for i in changed if half <= i < switch_input),
                                                 "switch": sum(1 for i in changed if i >= switch_input)}}
        verdict["identical"] = not changed and len(baseline) == len(hashes)
        verdict["pass"] = verdict["identical"] and verdict["native_published"] > 0
    else:
        # Nothing was compared (audit 9 L3): never a pass or an identity, only the hashes for a later baseline.
        verdict["identical"] = verdict["pass"] = None
        verdict["compared"] = "nothing compared (no --against)"
    return verdict


def accepted_entry(entry: dict) -> dict:
    """An accepted report's run entry as ``LiveJudge(accepted=...)`` reads it: its native hashes, every judged frame's
    verdict and every failing frame's record, by input."""
    if "judged_verdicts" not in entry:
        raise ValueError("the accepted run has no judged_verdicts (a report written before --accepted existed)")
    failed = list(entry["rule_a"].get("failed_frames") or [])
    for section in (entry.get("partner") or {}).values():
        failed += list(section.get("failed_frames") or [])
    return {"hashes": list(entry["native_hashes"]),
            "verdicts": {int(v["input"]): v for v in entry["judged_verdicts"]},
            "failed": {int(f["input"]): f for f in failed},
            "reference": (entry.get("python_reference") or {}).get("folder")}


@contextlib.contextmanager
def native_shader_control(mode: str, name: str | None, out: Path):
    """The native item draws ``mode``'s pack baked with one line changed (``native_stream_player.SHADER_CONTROLS``):
    the route's ``mode_fragment_pack`` is the control's for ``mode`` while this holds; the Python reference is not
    touched (it compiles the shader source itself)."""
    if name is None:
        yield
        return
    from rendering.native import program_values
    from tools.visualizer_replay import native_stream_player
    from widgets.spotify_visualizer import shaders

    import probe_rings                                     # native/core/python (native_stream_player's path)

    filename, line, replacement = native_stream_player.SHADER_CONTROLS[mode][name]
    text = (Path(shaders.__file__).resolve().parent / filename).read_text(encoding="utf-8")
    if text.count(line) != 1:
        raise RuntimeError(f"{filename}: the shader control's line is not found exactly once")
    pack = probe_rings.bake(text.replace(line, replacement), filename, Path(out) / "work" / "control_packs")
    original = program_values.mode_fragment_pack
    program_values.mode_fragment_pack = lambda mode_id: pack if mode_id == mode else original(mode_id)
    try:
        yield
    finally:
        program_values.mode_fragment_pack = original


def native_parity(core, mode: str, suffix: str, settings: dict, clip_frames, out: Path,
                  placement: str = "display", *, references: Path | None = None, clip_name: str = "",
                  windows: dict | None = None, accepted: dict | None = None) -> dict:
    """Rule (a) of the port (N2.5): the owner in process drawn by the Python renderer and by the native item, single-
    sampled, frame for frame over the card's region and its margin. Each native card's window map is checked against
    the Python renderer's own rows of the same frame (``mapping``), and every pixel more than a level off is
    classified (``classes``). ``placement``: where both runs put the card (``PLACEMENTS``). ``references``: the root of
    the cached Python references (``python_references``): the Python run and its masks are read from there when a
    reference made of exactly this run exists, and stored there when not. ``accepted``: an accepted run of the same
    reference (``accepted_entry``): native frames hash-identical to it keep its verdicts.

    The native run is drawn first, each frame's hash line written as it is drawn, and judged after: the owner's
    activation deadline is on the wall clock, so judging inside its frame loop could cancel a mode switch
    (``owner_worker_gate.TransitionDeadlineFired``)."""
    from tools.visualizer_replay import python_references

    script = parity_script(clip_frames, mode)
    cached = folder = made_of = None
    reference_state = "not used"
    if references is not None:
        from PySide6.QtGui import QGuiApplication

        dpr_now = float(QGuiApplication.primaryScreen().devicePixelRatio())
        key, made_of = python_references.reference_key(mode, suffix, settings, clip_name, clip_frames, placement,
                                                       dpr_now)
        folder = Path(references) / key
        cached = python_references.load(folder, made_of)
        reference_state = "read" if cached is not None else "drawn and stored"
    switch_at = next(i for i, (kind, _v) in enumerate(script) if kind == "mode")
    switch_input = sum(1 for kind, _value in script[:switch_at] if kind == "input")
    run = f"{mode}{suffix}" if placement == "display" else f"{mode}{suffix}@{placement}"
    # One line per native frame as it is drawn, then one per failing frame as it is judged (fast-proof part 2
    # step 4): a killed run keeps what it had.
    progress = Path(out) / f"progress_{run.replace(':', '_').replace('=', '-').replace('@', '_at_')}.jsonl"
    Path(out).mkdir(parents=True, exist_ok=True)
    progress.write_text("", encoding="utf-8")
    with single_sample_scene_targets(), card_placement(placement):
        # The Python reference and its masks first (read or drawn), so each native frame is judged as it is drawn.
        if cached is not None:
            python, masks, mappings, backdrop_frames = cached
        else:
            python, mappings, masks, backdrop_frames, drawing = _recorded_python_reference(mode, script, settings)
            if references is not None:
                python_references.store(folder, made_of, python, masks, mappings, backdrop_frames, drawing=drawing)
        draw_inputs = None
        if windows is not None:
            from tools.visualizer_replay.coverage_windows import window_inputs

            draw_inputs = window_inputs(windows)

        def drawn(index: int, record: dict, _frame) -> None:
            line = {"input": index, "hash": record.get("hash")}
            if record.get("skipped"):
                line["skipped"] = True
            with progress.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(line) + "\n")

        with native_shader_control(mode, NATIVE_SHADER_CONTROL, Path(out)):
            native = native_drawn_run(mode, script, settings=settings, core=core,
                                      python_mappings=mappings if mode == "spectrum" else None, on_frame=drawn,
                                      draw_inputs=draw_inputs)
        if cached is not None and python["digests"] != native["digests"]:
            # The simulation moved since the reference was drawn: never judged against it; drawn again.
            reference_state = "stale (logical digests differ): drawn again and stored"
            python_references.release(cached)             # the stale reference's open files (audit 9 M2)
            python, mappings, masks, backdrop_frames, drawing = _recorded_python_reference(mode, script, settings)
            python_references.store(folder, made_of, python, masks, mappings, backdrop_frames, drawing=drawing)
        if accepted is not None and (reference_state != "read" or accepted.get("reference") != str(folder)):
            accepted = None                               # another reference: every frame is judged
            reference_state += "; the accepted run's reference differs: every frame judged"
        judge = LiveJudge(python, masks, switch_input, mode, progress=progress, workers=JUDGE_WORKERS,
                          accepted=accepted, hash_lines=False)
        for index, record in enumerate(native["pixels"]):
            judge.frame(index, record, native["frames"][index])
    single = judge.result()
    paths, rows = single["paths"], single["rows"]
    origin = native.get("outer_origin")
    dpr = float(_PLACED["dpr"])
    fraction = None if origin is None else [round((v * dpr) % 1.0, 4) for v in origin]
    verdict = {"mode": mode, "run": run, "inputs": python["inputs"], "placement": placement,
               "outer_origin": origin, "outer_origin_device_fraction": fraction, "dpr": dpr,
               "frames_drawn": [len(python["pixels"]), len(native["pixels"])],
               "native_frames": native["native_frames"], "native_published": native["native_published"],
               "left_gl_errors": native["left_gl_errors"],
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
    # Each frame was judged under the bounds of the mode that drew it; the tested mode's frames make rule (a), the
    # partner's (after the switch) their own section under their own bounds.
    drew = {i: (m or mode) for i, m in enumerate(python.get("modes") or ())}
    all_judged = single["judged"]
    # Every judged frame's verdict: a later run against the same reference keeps them for its unchanged frames
    # (``accepted_entry``); and which of this run's came from an accepted run instead of a rejudge.
    verdict["judged_verdicts"] = all_judged
    verdict["carried_from_accepted"] = single["carried"]
    verdict["rejudged"] = len(all_judged) - len(single["carried"])
    judged = [v for v in all_judged if drew.get(v.get("input"), mode) == mode]
    partner_judged = [v for v in all_judged if drew.get(v.get("input"), mode) != mode]
    verdict["rule_a"] = rule_a_verdict(judged, mode)
    # Every failing frame, with its pixels (fast-proof part 2 step 4; the first eight before).
    own_inputs = {v.get("input") for v in judged}
    verdict["rule_a"]["failed_frames"] = [f for f in single["failed"] if f.get("input") in own_inputs]
    verdict["progress"] = str(progress)
    verdict["rule_a_halves"] = rule_a_halves(judged, switch_input, mode)
    partners = sorted({drew[i] for i in drew if drew[i] != mode})
    verdict["partner"] = {
        name: {"inputs": [v.get("input") for v in partner_judged if drew.get(v.get("input")) == name][:1] +
               [v.get("input") for v in partner_judged if drew.get(v.get("input")) == name][-1:],
               "frames": sum(1 for i in drew if drew[i] == name),
               **rule_a_verdict([v for v in partner_judged if drew.get(v.get("input")) == name], name),
               "failed_frames": [f for f in single["failed"] if drew.get(f.get("input")) == name]}
        for name in partners}
    if windows is not None:
        # Each window's figures with its position in the take (guide section 3).
        drawn = [i for i, r in enumerate(native["pixels"]) if not r.get("skipped")]
        verdict["windows"] = []
        for window in windows["windows"]:
            lo, hi = window["inputs"]
            inside = [v for v in judged if lo <= v.get("input", -1) < hi]
            verdict["windows"].append({"inputs": [lo, hi], "seconds": window.get("seconds"),
                                       "reasons": window["reasons"],
                                       "drawn": sum(1 for i in drawn if lo <= i < hi),
                                       "failed": [v["input"] for v in inside if not v.get("pass")],
                                       **rule_a_verdict(inside, mode)})
        verdict["drawn_inputs"] = len(drawn)
    verdict["rule_a"]["mask_inputs"] = len(masks)
    verdict["rule_a"]["backdrop_frames"] = backdrop_frames
    verdict["python_reference"] = {"state": reference_state, "folder": None if folder is None else str(folder)}
    verdict["pass"] = bool(verdict["rule_a"]["pass"] and verdict["digests_identical"] and verdict["native_published"] > 0
                           and paths["regions_equal"] and len(python["pixels"]) == len(native["pixels"])
                           == backdrop_frames and all(p["pass"] for p in verdict["partner"].values()))
    verdict["split"] = _split_rows(rows, switch_input)
    verdict["mapping"] = dict(native["mapping"], python_frames=len(mappings))
    verdict["classes"] = single["classes"]
    if rows:
        worst = max(rows, key=lambda row: (row["max_level"], row["pixels"]))
        verdict["worst"] = worst
        verdict["crops"] = _write_native_crops(Path(out), run.replace(":", "_").replace("=", "-").replace("@", "_at_"),
                                               native, python, worst)
    return verdict


def harness_registration(mode: str):
    """A context manager under which the route draws ``mode`` for the run: ``native_record_identity.MODES[mode].
    register`` for a port the product's route does not draw yet (its registration is the port's last step, after P, T
    and C: Extruded Bubble's ``_eb_registered``), else nothing."""
    from rendering.quick.visualizer.native_route import NATIVE_MODE_IDS

    if mode in NATIVE_MODE_IDS:
        return contextlib.nullcontext()
    from tools.visualizer_replay import native_record_identity

    spec = native_record_identity.MODES.get(mode)
    register = None if spec is None else spec.register
    return contextlib.nullcontext() if register is None else register()


def _largest_geometry_bank() -> int:
    """The D3 bank bytes no admitted activation exceeds (``frame_capacity.geometry_bank_bytes`` at every family's
    canonical maximum): a bank larger than a session's own changes no byte the core reads."""
    from core.constants.extruded_bubble_world import SNOW_FULL, SPECKS_FULL
    from widgets.spotify_visualizer.extruded_bubble_drift_log import CHAIN_GEOMETRY_BYTES, CLOUD_GEOMETRY_BYTES
    from widgets.spotify_visualizer.extruded_bubble_material_paths import CHAIN_PATHS

    largest = max(CHAIN_PATHS * CHAIN_GEOMETRY_BYTES, max(SNOW_FULL, SPECKS_FULL) * CLOUD_GEOMETRY_BYTES)
    return (largest + 15) // 16 * 16


#: The in-process drift arena's writer key namespace (odd and non-zero, as ``GeometryArenaWriter`` draws its own).
IN_PROCESS_WRITER_NAMESPACE = 0x5E5D_0001


@contextlib.contextmanager
def in_process_drift_arena():
    """The engine worker's D3 side, in process (N5.6): the owner replay runs without a worker, so no session opened
    Extruded Bubble's geometry arena and the route names no drift family (``DriftStream.project``: every family absent,
    the drift held). For the run the harness stands in for the worker: the session's arena opened under the in-process
    label namespace (0) as ``engine_worker_link.configure`` opens it, and each logical frame's new keys written by the
    worker's own ``GeometryArenaWriter`` before the route projects that frame (as ``PacketMailbox.publish`` writes them
    before the slot), the previous frame counted consumed (the in-process route takes every frame it projects).

    The writer's key namespace is the fixed ``IN_PROCESS_WRITER_NAMESPACE``, not a fresh random one: the record carries
    it in every geometry key, so two runs of one take (a coverage window against the continuous run, layer L's runs)
    hold the same record bytes only under one namespace. The route's shared projector (``schema.DRIFT``) forgets its
    streams when the arena opens and closes, as a replacement worker's new namespace makes it: another run in the same
    process starts its epochs and serials again under the same namespace."""
    from core.visualizer_engine import extruded_bubble_native_schema as schema
    from core.visualizer_engine import geometry_arena as ga
    from widgets.spotify_visualizer.extruded_bubble_drift_log import FAMILIES

    owner = schema.open_stream_arena(0, _largest_geometry_bank())
    writer = ga.GeometryArenaWriter(owner.name, families=FAMILIES)
    writer.namespace = IN_PROCESS_WRITER_NAMESPACE
    ga._WRITER_NAMESPACE.pack_into(writer._memory.buf, ga._WRITER_NAMESPACE_AT, writer.namespace)
    schema.DRIFT._projectors = {}
    project = schema.DriftStream.project
    sequence = [0]

    def projecting(self, logical):
        writer.before_publish(logical, sequence[0])
        sequence[0] += 1
        writer.published(sequence[0])
        return project(self, logical)

    schema.DriftStream.project = projecting
    try:
        yield writer
    finally:
        schema.DriftStream.project = project
        schema.DRIFT._projectors = {}
        writer.close()
        schema.close_stream_arena(owner)


def run_native(out: Path, **kwargs) -> dict:
    """``_run_native`` with ``mode`` registered on the route for the run (``harness_registration``); Extruded Bubble's
    drift geometry through the in-process arena (``in_process_drift_arena``)."""
    mode = kwargs.get("mode", "spectrum")
    arena = in_process_drift_arena() if mode == "extruded_bubble" else contextlib.nullcontext()
    with harness_registration(mode), arena:
        return _run_native(out, **kwargs)


def _run_native(out: Path, *, module_dir: Path, offers: bool, seconds: float = 5.5, only: tuple[str, ...] = (),
                against: Path | None = None, placements: tuple[str, ...] = PLACEMENTS, mode: str = "spectrum",
                recording: str | None = None, references: Path | None = None,
                native_only_run: bool = False, windows: dict | None = None, accepted: Path | None = None) -> dict:
    """``native_parity`` over ``mode``'s widened run set (``conventions_identity.mode_runs``; a mode of the route's
    ``NATIVE_MODE_IDS``) at the rig's own placement, and ``OVERSCAN_RUNS`` again at each other placement of
    ``placements`` (keyed ``run@placement``); the report. ``against``: an accepted report this one is compared with
    (``against_baseline``). ``native_only_run``: ``native_only`` instead (no Python render; with ``against``, each
    run's native hashes against that report's)."""
    baseline = json.loads(Path(against).read_text(encoding="utf-8")) if against is not None else None
    accepted_report = json.loads(Path(accepted).read_text(encoding="utf-8")) if accepted is not None else None
    import tools.expanded_visualizer_evidence as evidence
    from rendering.native import load
    from tools import conventions_identity
    from widgets.spotify_visualizer import engine_worker_link

    core = load(module_dir)
    if NATIVE_STAGE_CONTROL is not None and not core.module.stage_control(NATIVE_STAGE_CONTROL, True):
        raise ValueError(f"the module has no harness control {NATIVE_STAGE_CONTROL!r}")
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    # ``recording``: the first ``seconds`` of one of the operator's recorded takes (logs/visualizer_recordings, read
    # only) instead of the shipped Studio clip's opening.
    clip = evidence.load_recording(recording, seconds) if recording else evidence.shipped_clip(seconds)
    from rendering.quick.visualizer.native_route import NATIVE_MODE_IDS

    if mode not in NATIVE_MODE_IDS:
        raise ValueError(f"the native route draws {sorted(NATIVE_MODE_IDS)}, not {mode!r}")
    report: dict = {"mode": mode, "offers": offers, "seconds": seconds, "display": list(DISPLAY), "clip": clip.name,
                    "clip_frames": len(clip.frames), "native_only": bool(native_only_run), "api": "opengl",
                    "stage_control": NATIVE_STAGE_CONTROL, "results": {}}
    started = time.perf_counter()
    runs = conventions_identity.mode_runs(mode, offers)
    planned = _placed_runs(mode, runs, placements, only)
    try:
        for key, suffix, settings, placement in planned:
            engine_worker_link.reset_run_state_for_testing()
            if native_only_run:
                entry = None if baseline is None else (baseline.get("results") or {}).get(key)
                if baseline is not None and entry is None:
                    raise ValueError(f"the baseline {against} has no run {key!r}")
                verdict = native_only(core, mode, suffix, settings, clip.frames, out, placement=placement,
                                      against=entry)
                report["results"][key] = verdict
                changed = verdict.get("against", {}).get("changed")
                print(f"[NATIVE ONLY] {key:40s} {len(verdict['native_hashes'])} frames, native "
                      f"{verdict['native_published']} published; "
                      + ("no baseline" if changed is None else
                         f"{len(changed)} frames changed {verdict['against']['changed_halves']} "
                         f"(first {changed[:10]}): {'IDENTICAL' if verdict['identical'] else 'CHANGED'}"), flush=True)
                continue
            entry = None
            if accepted_report is not None:
                entry = (accepted_report.get("results") or {}).get(key)
                if entry is None:
                    raise ValueError(f"the accepted report {accepted} has no run {key!r}")
                entry = accepted_entry(entry)
            verdict = native_parity(core, mode, suffix, settings, clip.frames, out, placement=placement,
                                    references=references, clip_name=clip.name, windows=windows, accepted=entry)
            report["results"][key] = verdict
            carried = len(verdict["carried_from_accepted"])
            print(f"[NATIVE] {key:48s} {verdict['frames_drawn']} frames, native {verdict['native_published']}"
                  + (f" published; {verdict['rejudged']} judged, {carried} kept from the accepted run (hash-"
                     f"identical: their verdicts, not sized here); of the judged, differing inputs "
                     if entry is not None else " published; differing inputs ")
                  + f"{verdict['differing_inputs']}, pixels "
                  f"{verdict['differing_pixels_total']}, max level {verdict['max_level']}; card origin "
                  f"{verdict['outer_origin']} (device fraction {verdict['outer_origin_device_fraction']}); "
                  f"{'bit-identical' if verdict['identical'] else 'not bit-identical'}; edge pixels in the worst "
                  f"frame {verdict['rule_a']['edge_pixels_worst_frame']}; rule (a) {verdict['rule_a']['bound']}: "
                  f"{'PASS under tolerance' if verdict['pass'] else 'FAIL'}", flush=True)
    finally:
        report["elapsed_s"] = round(time.perf_counter() - started, 1)
        report["identical"] = bool(report["results"]) and all(v["identical"] for v in report["results"].values())
        report["pass"] = bool(report["results"]) and all(v["pass"] for v in report["results"].values())
        if report["results"] and all(v.get("identical") is None for v in report["results"].values()):
            # A native-only run with no baseline compared nothing (audit 9 L3).
            report["identical"] = report["pass"] = None
            report["compared"] = "nothing compared (no --against)"
            print("[NATIVE ONLY] nothing compared (no --against): the hashes are kept for a later baseline", flush=True)
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
    parser.add_argument("--runs", nargs="*", default=(),
                        help="explicit run keys (<mode>[:...]); append @overscan to request any run at that placement")
    parser.add_argument("--mode", default="spectrum",
                        help="with --native: the native mode drawn (one of the route's NATIVE_MODE_IDS)")
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
    parser.add_argument("--references", nargs="?", type=Path, default=None, const=Path("default"),
                        help="with --native: cached Python references (tools/visualizer_replay/python_references.py): "
                             "read when one made of exactly this run exists, else drawn and stored; the folder "
                             "(default D:\\Temp\\Scratch\\SRPSS\\fast_proof\\references)")
    parser.add_argument("--references-only", action="store_true",
                        help="draw and store the cached Python references of --mode's runs for --recording (port "
                             "preparation, before the mode has a native route); with --runs, only those run keys")
    parser.add_argument("--native-only", action="store_true",
                        help="with --native: the native runs alone, each frame's hash written as it is drawn; with "
                             "--against, every frame whose hash changed from that report's (native before against "
                             "native after: no Python render, no tolerance)")
    parser.add_argument("--windows", type=Path, default=None,
                        help="with --native: a coverage_windows.json; the native run draws only its windows (with "
                             "their warm-up), the simulation ticks every input, each window reported with its position")
    parser.add_argument("--native-control", choices=("shift",), default=None,
                        help="with --native: a negative control on the native frames (shift: one level up); rule (a) "
                             "must fail")
    parser.add_argument("--accepted", type=Path, default=None,
                        help="with --native --references: an accepted native_render_parity.json of the same runs and "
                             "references; a native frame hash-identical to it keeps its accepted verdict, every other "
                             "frame is judged (the guide's section 7 split: full-take native runs)")
    parser.add_argument("--shader-control", default=None,
                        help="with --native: the native item draws a shader control (native_stream_player's "
                             "SHADER_CONTROLS, e.g. ulp_ring); the Python reference is untouched")
    parser.add_argument("--stage-control", default=None,
                        help="with --native: the module's harness control of this name held on for the run "
                             "(stage_control; card_triangle: the full triangle instead of the card's quad, ABI 32)")
    parser.add_argument("--judge-workers", type=int, default=0,
                        help="with --native: rule (a)'s frames judged in this many worker processes (0: in this one; "
                             "the same verdicts either way)")
    parser.add_argument("--api", choices=("opengl", "vulkan"), default="opengl",
                        help="with --native: the graphics API the owner's scene and the native item draw on")
    args = parser.parse_args(argv)
    if args.api != "opengl":
        parser.error("--api vulkan: the owner replay's hidden host draws OpenGL only; the native item on Vulkan is "
                     "drawn from the take's delivery stream by tools/visualizer_replay/native_stream_player.py "
                     "(native_record_identity.py --deliveries writes the stream)")
    if args.references is not None and str(args.references) == "default":
        from tools.visualizer_replay.python_references import DEFAULT_ROOT

        args.references = DEFAULT_ROOT
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
        if args.references_only:
            report = references_only(args.out, mode=args.mode, offers=args.offers, seconds=args.seconds,
                                     recording=args.recording,
                                     references=args.references or python_references_root(),
                                     placements=tuple(args.placements), only=tuple(args.runs))
            del app
            evidence_media.finish(0)
            return 0
        if args.native:
            global NATIVE_SURFACE_FORMAT, NATIVE_UNPRIMED, JUDGE_WORKERS, NATIVE_CONTROL, NATIVE_SHADER_CONTROL
            global NATIVE_STAGE_CONTROL
            NATIVE_SHADER_CONTROL = args.shader_control
            NATIVE_STAGE_CONTROL = args.stage_control
            JUDGE_WORKERS = max(0, int(args.judge_workers))
            NATIVE_CONTROL = args.native_control
            NATIVE_SURFACE_FORMAT = args.surface_format
            NATIVE_UNPRIMED = bool(args.unprimed)
            report = run_native(args.out, module_dir=args.module_dir.resolve(), offers=args.offers,
                                seconds=args.seconds, only=tuple(args.runs),
                                against=None if args.against is None else args.against.resolve(),
                                placements=tuple(args.placements), mode=args.mode, recording=args.recording,
                                references=args.references, native_only_run=bool(args.native_only),
                                windows=None if args.windows is None else json.loads(
                                    args.windows.read_text(encoding="utf-8")),
                                accepted=None if args.accepted is None else args.accepted.resolve())
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
        if report["pass"] is None:
            return 0                                      # nothing compared: neither a pass nor a failure
        return 0 if report["pass"] else 1
    return 0 if report["identical"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
