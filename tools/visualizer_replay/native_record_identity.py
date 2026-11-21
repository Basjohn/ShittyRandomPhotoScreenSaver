"""Layer L of the fast long-clip proof (``Docs/Guides/Native_Parity_And_Timing_Proof.md``, section 1): per frame, does
the native path receive exactly what the Python renderer uses? CPU only, nothing is drawn.

    python tools/visualizer_replay/native_record_identity.py --mode bubble --recording <take> --seconds 60
        --out .artifacts/evidence/native_core/fast_proof/<YYYYMMDD>_<label>/ [--variant a|b]
        [--module-dir release/native_module] [--control ulp@<input> | drop@<input>]

One production owner (``owner_worker_gate.identity_run``, in process, the parity script of ``owner_render_parity``) is
ticked once over the take. Both paths read the same ticks:

- **The native path** is the product's own ``NativeVisualizerRoute``, attached to the owner's own unshown
  ``VisualizerRenderItem`` as ``QuickSceneController`` attaches it on Vulkan, so every take, record, settings change and
  card is the route's. Its core is a recording stand-in (no GPU): what reaches the core is the payload the route
  publishes (the core admits it by the slot flags, ``native/core/src/stream_source.cpp``'s rule), the settings and card
  it delivers and the target sizes it sends.
- **The Python path** is the mode's real Python renderer drawing the frame the Python node would draw (its admission
  ``render_contract.snapshot_is_render_admissible``; the same take), with its GL calls going to a recording null GL: its
  bound std140 blocks (``PassBlocks.bound``) and its buffer uploads are captured. Nothing of its arithmetic is replaced.

Each input is compared at three levels, byte for byte:

1. **record**: the native record the core holds against ``schema.encode`` of the frame the Python renderer draws (f64,
   every byte: a stale, dropped or perturbed frame shows here);
2. **settings**: each setting the route delivered against the value the Python renderer holds for that name in this
   draw (its block values, and the shared settings functions it calls), as the core's settings JSON writes it;
3. **block**: each pass's block the native module packs (GPU-free ``mode_blocks`` / ``spectrum_block``, the core's own
   packer) against the Python renderer's bound block, member by member over the bytes the shader reads (the mode's
   ``read_spans``), and each instance stream's used bytes against the Python renderer's upload.

Outside L (declared per mode, ``positional``): members that place the draw in its window or target (the quad matrix,
fragPixel's target, Spectrum's window maps), and the inherited scene opacity the Python node folds into ``u_fade`` (no
QML scene here; the tracked scene-fade box). They are layer P's: Spectrum's window maps by rule (a)'s mapping control
(Spectrum's only); every mode's positional members by rule (a)'s pixels on OpenGL (the display and overscan
placements) and by the stream player's rule (b) at the harness's one placement on Vulkan, so a Vulkan-only error at a
fractional product placement is not covered by any layer (checkpoint audit 9 L4). The coverage report names every
delivered setting the Python renderer did not hold this run (``settings_skipped``), so a port cannot hide one.

Standing controls (``--control``, ``tests/test_native_record_identity.py``): ``ulp`` (a record field one f64 ulp up),
``drop`` (a frame never reaching the core), ``setting`` (a delivered setting raised by 0.25) and ``block`` (a packed
native block member raised by 1.0), each at one input, each caught there and nowhere else.

Output (``--out``): ``native_record_identity.json`` (frames compared and expected per half, every mismatching frame with
its first differing field and both values), rewritten every ``PROGRESS_EVERY`` inputs, and ``progress.jsonl`` (one line
per mismatching frame as it happens, and a count line every ``PROGRESS_EVERY`` inputs), so a killed run keeps what it
had. Exit 0 when every expected frame was judged identical, else 1.

A new port adds its mode to ``MODES`` (``LMode``): its renderer modules, its passes' Python labels and layouts, its
positional members, its read spans and its instance streams.
"""
from __future__ import annotations

import argparse
import contextlib
import json
import math
import struct
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import artifact_paths  # noqa: E402

#: Inputs between two progress writes (the report rewritten, a count line appended).
PROGRESS_EVERY = 250
REPORT_NAME = "native_record_identity.json"
PROGRESS_NAME = "progress.jsonl"


# ------------------------------------------------------------------------------------------------ the declarations

@dataclass(frozen=True)
class LMode:
    """One native mode's layer L declaration.

    ``python_modules``: the renderer's modules whose GL entry points the recording GL replaces (``gl``, ``gl_query``,
    ``compile_program``, ``delete_program``). ``passes``: Python ``PassBlocks`` label -> the native pass's name.
    ``layouts``: () -> {pass name: the Python packer's block layout}. ``settings_functions``: shared settings functions
    the renderer calls (module, name), whose results are part of the values it uses. ``positional``: members and settings
    outside L, with the reason. ``read_spans``: (pass, member, member bytes, decoded record, logical frame) -> the byte
    spans the shader reads (None: all). ``streams``: record field -> (its used-length field, the Python buffer's
    owner path on the renderer, the attribute naming the buffer; a stream a stand-in records needs neither: ``()``,
    ``""``). ``ulp_field``: the record field the one-ulp control perturbs (its first element).

    A pass label the renderer binds more than once a draw maps to a tuple of names in bind order; a draw that binds it
    fewer times takes the last names (a pass drawn only on some frames binds first: the Oscilloscope's graticule).
    ``stand_ins``: (renderer, recorder) -> None, called once the renderer exists: its members that would reach GL
    outside ``python_modules`` (a scene target, a stream ring) replaced by recording stand-ins, which put a stream's
    bytes in ``recorder.stream_uploads``. ``drawn``: (decoded native record) -> whether the native program draws any
    pass this frame (None: whenever shown), for a mode whose Python renderer draws nothing on some shown frames.
    ``register``: () -> a context manager registering a mode the product's route does not draw yet, for the run only
    (the port's registration is its last step)."""
    mode_id: str
    python_modules: tuple[str, ...]
    passes: dict[str, str | tuple[str, ...]]
    layouts: Callable[[], dict]
    settings_functions: tuple[tuple[str, str], ...] = ()
    positional: dict[str, str] = field(default_factory=dict)
    read_spans: Callable[..., list | None] | None = None
    streams: dict[str, tuple[str, tuple[str, ...], str]] = field(default_factory=dict)
    ulp_field: str = ""
    stand_ins: Callable[[Any, Any], None] | None = None
    drawn: Callable[[dict], bool] | None = None
    register: Callable[[], Any] | None = None


_IMPL = "rendering.quick.visualizer.implementations"
_WINDOW = "places the draw in its window or target (layer P: rule (a)'s mapping control and pixels)"


def _spectrum_layouts() -> dict:
    from rendering.quick.visualizer.implementations.spectrum import SPECTRUM_BLOCK

    return {"spectrum": SPECTRUM_BLOCK}


def _spectrum_spans(pass_name, member, size, record, logical):
    if member == "u_time":
        # Only a flag sheet's wave reads the clock (the Python renderer writes it only then).
        from rendering.gl_programs.spectrum_options import SPECTRUM_FLAG_PATTERNS

        shown = str(logical.mode_state.parameters["spectrum_pattern_shown"])
        return [(0, size)] if shown in SPECTRUM_FLAG_PATTERNS else []
    return None


def _devcurve_layouts() -> dict:
    from rendering.quick.visualizer.implementations.devcurve import DEVCURVE_BLOCK

    return {"devcurve": DEVCURVE_BLOCK}


def _bubble_layouts() -> dict:
    from rendering.quick.visualizer.implementations import bubble_ambient_gl
    from rendering.quick.visualizer.implementations.bubble import BUBBLE_BLOCK

    return {"bubble": BUBBLE_BLOCK, "bubble_ambient_points": bubble_ambient_gl._POINT_BLOCK,
            "bubble_ambient_mask": bubble_ambient_gl._MASK_BLOCK}


def _bubble_spans(pass_name, member, size, record, logical):
    """``bubble_check``'s block-round rule: the shader reads the first ``count`` positions and extras, ``3 count`` trail
    samples, and ``u_ambient_px`` only while the ambience is on."""
    if pass_name != "bubble":
        return None
    count = int(record["u_bubble_count"])
    if member in ("u_bubbles_pos", "u_bubbles_extra"):
        return [(0, min(size, 16 * count))]
    if member == "u_bubbles_trail":
        return [(0, min(size, 16 * 3 * count))]
    if member == "u_ambient_px":
        return [(0, size)] if int(record["u_ambient_enabled"]) else []
    return None


def _oscilloscope_layouts() -> dict:
    from rendering.quick.visualizer.implementations.oscilloscope import OSC_BEAM_BLOCK, OSC_GRATICULE_BLOCK

    return {"oscilloscope_graticule": OSC_GRATICULE_BLOCK, "oscilloscope_beam": OSC_BEAM_BLOCK}


class _NullSceneTarget:
    """The Oscilloscope renderer's ``SceneTarget`` for a CPU run: its scope and emission writes do nothing (the target,
    its bloom and its composite are layer P's: the core's own steps, judged by rule (a)'s and rule (b)'s pixels)."""

    has_resources = False

    @contextlib.contextmanager
    def scope(self, *_args, **_kwargs):
        yield

    @contextlib.contextmanager
    def emission_writes(self):
        yield

    def warm(self, *_args, **_kwargs) -> bool:
        return True

    def release(self) -> None:
        pass


class _RecordingStreamRing:
    """A ``StreamRing`` for a CPU run: ``bound`` keeps the bytes the renderer uploads as the stream ``name``."""

    has_resources = False

    def __init__(self, recorder: Any, name: str) -> None:
        self._recorder = recorder
        self._name = name

    @contextlib.contextmanager
    def bound(self, _target, _binding, data, **_kwargs):
        self._recorder.stream_uploads[self._name] = bytes(data)
        yield None

    def warm(self) -> bool:
        return True

    def release(self) -> None:
        pass


def _oscilloscope_stand_ins(renderer, recorder) -> None:
    renderer._target = _NullSceneTarget()
    renderer._stream = _RecordingStreamRing(recorder, "osc_points")


@contextlib.contextmanager
def _oscilloscope_registered():
    """The route draws the Oscilloscope for this run only (``oscilloscope_check.owner``'s registration)."""
    from rendering.quick.visualizer import native_route as route

    saved = (route.GENERIC_MODE_SETTINGS, route.NATIVE_MODE_IDS)
    route.GENERIC_MODE_SETTINGS = {**saved[0], "oscilloscope": route.OSCILLOSCOPE_SETTINGS}
    route.NATIVE_MODE_IDS = saved[1] | {"oscilloscope"}
    try:
        yield
    finally:
        route.GENERIC_MODE_SETTINGS, route.NATIVE_MODE_IDS = saved


MODES: dict[str, LMode] = {
    "spectrum": LMode(
        "spectrum", (f"{_IMPL}.spectrum",), {"Quick Spectrum pass blocks": "spectrum"}, _spectrum_layouts,
        positional={"uMatrix": _WINDOW, "u_target_px": _WINDOW, "u_item_from_frag": _WINDOW,
                    "u_item_from_frag_x": _WINDOW, "u_item_from_frag_y": _WINDOW,
                    "u_window_from_target_x": _WINDOW, "u_window_from_target_y": _WINDOW},
        read_spans=_spectrum_spans, ulp_field="bars"),
    "devcurve": LMode(
        "devcurve", (f"{_IMPL}.devcurve",), {"Quick DevCurve pass blocks": "devcurve"}, _devcurve_layouts,
        settings_functions=((f"{_IMPL}.devcurve", "devcurve_settings_values"),),
        positional={"uMatrix": _WINDOW, "u_target_px": _WINDOW}, ulp_field="u_devcurve_curve_bass"),
    "bubble": LMode(
        "bubble", (f"{_IMPL}.bubble", f"{_IMPL}.bubble_ambient_gl"),
        {"Quick Bubble pass blocks": "bubble", "Bubble ambience pass blocks": "bubble_ambient_points",
         "Bubble ambience mask pass blocks": "bubble_ambient_mask"}, _bubble_layouts,
        settings_functions=((f"{_IMPL}.bubble", "bubble_settings_values"),
                            (f"{_IMPL}.bubble", "bubble_ambient_settings_values")),
        positional={"uMatrix": _WINDOW, "u_target_px": _WINDOW}, read_spans=_bubble_spans,
        streams={"ambient_points": ("ambient_point_floats", ("_ambient_renderer",), "_vbo"),
                 "ambient_occluders": ("ambient_occluder_floats", ("_ambient_renderer",), "_occluder_vbo")},
        ulp_field="u_bubbles_pos"),
    # Its passes share one ring label ("Quick Oscilloscope pass blocks"): the graticule (only when it draws), then the
    # beam. The scene target, bloom and composite are the core's own steps (stand-ins here, layer P's pixels).
    "oscilloscope": LMode(
        "oscilloscope", (f"{_IMPL}.oscilloscope", "rendering.quick.scene3d.resources"),
        {"Quick Oscilloscope pass blocks": ("oscilloscope_graticule", "oscilloscope_beam")}, _oscilloscope_layouts,
        settings_functions=((f"{_IMPL}.oscilloscope", "oscilloscope_settings_values"),),
        positional={"uMatrix": _WINDOW},
        streams={"osc_points": ("osc_point_floats", (), "")}, ulp_field="u_widen",
        stand_ins=_oscilloscope_stand_ins, drawn=lambda record: int(record["osc_segments"]) > 0,
        register=_oscilloscope_registered),
}


# ------------------------------------------------------------------------------------------- the recording GL

class _NullGL:
    """The Python renderers' GL module for a CPU run: constants are the real ones, every entry point does nothing and
    returns a neutral value, object names count up, and ``glBufferSubData`` keeps the bytes uploaded per buffer."""

    def __init__(self) -> None:
        from OpenGL import GL as real

        self._real = real
        self._next = 0
        self._bound: dict[int, int] = {}
        self.uploads: dict[int, bytes] = {}

    def _name(self, count=1):
        self._next += 1
        return self._next

    def __getattr__(self, name: str):
        if name.startswith("GL_"):
            return getattr(self._real, name)
        if name.startswith("glGen"):
            return self._name
        if name == "glCheckFramebufferStatus":
            return lambda *args: self._real.GL_FRAMEBUFFER_COMPLETE
        if name == "glIsProgram":
            return lambda *args: True
        return _nothing

    def glBindBuffer(self, target, buffer) -> None:
        self._bound[int(target)] = int(buffer)

    def glBufferSubData(self, target, offset, size, data) -> None:
        import numpy as np

        raw = data if isinstance(data, (bytes, bytearray)) else np.ascontiguousarray(data).tobytes()
        self.uploads[self._bound.get(int(target), 0)] = bytes(raw[:int(size)])


def _nothing(*_args, **_kwargs):
    return 0


class _NullQuery:
    """``rendering.quick.gl_query`` for a CPU run: every read is zero."""

    @staticmethod
    def get_int(*_a):
        return 0

    @staticmethod
    def get_ints(_name, count):
        return (0,) * int(count)

    @staticmethod
    def get_bool(*_a):
        return False

    @staticmethod
    def get_bools(_name, count):
        return (False,) * int(count)

    @staticmethod
    def get_float(*_a):
        return 0.0

    @staticmethod
    def get_floats(_name, count):
        return (0.0,) * int(count)

    @staticmethod
    def is_enabled(*_a):
        return False


class RecordingPython:
    """The mode's real Python renderer on the recording GL. ``draw(frame)`` returns what one draw used: its bound
    blocks by pass name (in order), its buffer uploads by stream, and the values it holds by name."""

    def __init__(self, declaration: LMode) -> None:
        from importlib import import_module

        self.declaration = declaration
        self.gl = _NullGL()
        self._modules = [import_module(name) for name in declaration.python_modules]
        self._renderer: Any = None
        self._bound: list[tuple[str, bytes]] = []
        self._settings: dict = {}
        self._capturing = False
        #: A stand-in stream's bytes of this draw, by stream (``LMode.stand_ins``).
        self.stream_uploads: dict[str, bytes] = {}
        # The shared settings functions, wrapped once: they record only inside ``draw`` (the route calls them too).
        for module_name, function_name in declaration.settings_functions:
            module = import_module(module_name)
            original = getattr(module, function_name)
            if getattr(original, "_l_wrapped", False):
                original = original._l_original

            def wrapped(*args, _original=original, **kwargs):
                result = _original(*args, **kwargs)
                if self._capturing:
                    self._settings.update(result)
                return result

            wrapped._l_wrapped = True
            wrapped._l_original = original
            setattr(module, function_name, wrapped)
            self._wrapped = getattr(self, "_wrapped", []) + [(module, function_name, original)]

    def close(self) -> None:
        for module, name, original in getattr(self, "_wrapped", []):
            setattr(module, name, original)

    @contextlib.contextmanager
    def _patched(self):
        from rendering.quick.scene3d.uniforms import PassBlocks

        saved: list = []
        for module in self._modules:
            for name, value in (("gl", self.gl), ("gl_query", _NullQuery), ("compile_program", lambda *a, **k: 1),
                                ("delete_program", _nothing)):
                if hasattr(module, name):
                    saved.append((module, name, getattr(module, name)))
                    setattr(module, name, value)
        recorder = self

        @contextlib.contextmanager
        def bound(blocks, data):
            recorder._bound.append((blocks._ring.label, bytes(data)))
            yield lambda values: recorder._bound.append((blocks._ring.label, bytes(values)))

        class_saved = {name: PassBlocks.__dict__[name] for name in ("bound", "warm", "release")}
        PassBlocks.bound = bound
        PassBlocks.warm = lambda self: True
        PassBlocks.release = lambda self: None
        try:
            yield
        finally:
            for name, value in class_saved.items():
                setattr(PassBlocks, name, value)
            for module, name, value in reversed(saved):
                setattr(module, name, value)

    def draw(self, frame) -> dict:
        from rendering.quick.visualizer.implementation_registry import resolve_quick_visualizer_renderer

        self._bound, self._settings = [], {}
        self.gl.uploads.clear()
        self.stream_uploads.clear()
        with self._patched():
            if self._renderer is None:
                self._renderer = resolve_quick_visualizer_renderer(self.declaration.mode_id)
                if self.declaration.stand_ins is not None:
                    self.declaration.stand_ins(self._renderer, self)
            self._capturing = True
            try:
                self._renderer.render(frame)
            finally:
                self._capturing = False
        blocks: dict[str, bytes] = {}
        by_label: dict[str, list[bytes]] = {}
        for label, data in self._bound:
            by_label.setdefault(label, []).append(data)
        for label, bound in by_label.items():
            names = self.declaration.passes.get(label)
            if names is None:
                raise RuntimeError(f"the Python renderer bound an undeclared pass block {label!r}")
            if isinstance(names, str):
                blocks[names] = bound[-1]                  # one pass: its last write this draw
                continue
            names = tuple(names)
            if len(bound) > len(names):
                raise RuntimeError(f"the Python renderer bound {label!r} {len(bound)} times, declared {len(names)}")
            for name, data in zip(names[len(names) - len(bound):], bound):
                blocks[name] = data
        uploads = dict(self.stream_uploads)
        for stream, (_used, path, attribute) in self.declaration.streams.items():
            if stream in uploads or not attribute:
                continue
            owner = self._renderer
            for step in path:
                owner = getattr(owner, step, None) if owner is not None else None
            buffer = getattr(owner, attribute, 0) if owner is not None else 0
            if buffer and buffer in self.gl.uploads:
                uploads[stream] = self.gl.uploads[buffer]
        values = dict(getattr(self._renderer, "_values", {}) or {})
        values.update(self._settings)
        return {"blocks": blocks, "uploads": uploads, "values": values}


# ---------------------------------------------------------------------------------------- the native stand-in

class _Composite:
    def __init__(self) -> None:
        self.visible = False

    def set(self, **kwargs) -> None:
        if "visible" in kwargs:
            self.visible = bool(kwargs["visible"])

    def place(self, geometry, origin, *, visible=True, fade_ms=0) -> None:
        self.visible = bool(visible)

    def update(self) -> None:
        pass

    def destroy(self) -> None:
        pass

    def content_status(self):
        return None


class _Item:
    """What a native item was handed (the route's deliveries): its settings, card, target sizes and program."""

    def __init__(self) -> None:
        self.composite = _Composite()
        self.settings_values: dict | None = None
        self.card_values: dict | None = None
        self.sizes: dict = {}
        self.program_args: Any = None

    # Spectrum's item
    def program(self, *args, **kwargs) -> None:
        self.program_args = (args, kwargs)
        if len(args) >= 2:                                   # a generic program carries the first settings
            self.settings_values = dict(args[1])
            for target in kwargs.get("targets") or ():
                if getattr(target, "size", None) is not None:
                    self.sizes[target.name] = tuple(int(v) for v in target.size)

    def bind(self, *args, **kwargs) -> None:
        pass

    def unbind(self) -> None:
        pass

    def present_raw(self, card) -> None:
        self.card_values = dict(card)

    def card(self, card) -> None:
        self.card_values = dict(card)

    def settings(self, values) -> None:
        self.settings_values = dict(values)

    def target_size(self, name, size) -> None:
        self.sizes[name] = tuple(int(v) for v in size)

    def drop_retained_frame(self) -> None:
        pass

    def update(self) -> None:
        pass


class _Core:
    def __init__(self) -> None:
        self.items: list[_Item] = []

    def _make(self, _host):
        item = _Item()
        self.items.append(item)
        return item

    spectrum = _make
    mode = _make


def _route_class():
    from rendering.quick.visualizer.native_route import NativeVisualizerRoute

    class Route(NativeVisualizerRoute):
        """The product's route; only the window's metrics are given (no window exists) and its edges observed."""

        metrics: tuple = ((1920.0, 1080.0), (1920, 1080))
        observer: Any = None

        def _window_metrics(self, presentation, mode_id="spectrum"):
            return self.metrics

        def bind(self, identity):
            super().bind(identity)
            writer = self._writer
            publish = writer.publish

            def recording(payload, **kwargs):
                self._last_publication = (bytes(payload), int(kwargs.get("flags", 0)))
                return publish(payload, **kwargs)

            writer.publish = recording
            self.observer.bound(identity)

        def unbind(self):
            was = self._identity
            super().unbind()
            if was is not None and self.observer is not None:
                self.observer.bound(None)

        def drop(self):
            super().drop()
            self.observer.dropped()

        def _sync(self, **kwargs):
            before = self.published
            result = super()._sync(**kwargs)
            if self.published > before:
                payload, flags = self._last_publication
                self.observer.published(self._snapshot, payload, flags)
            return result

    return Route


# ------------------------------------------------------------------------------------------------ comparisons

def _std140_sizes(layout) -> dict[str, tuple[int, int, str]]:
    """member -> (offset, bytes, glsl type) of a Python block layout."""
    from rendering.gl_programs.scene3d import _std140_type

    scalar = {"float": 4, "int": 4, "uint": 4, "bool": 4, "vec2": 8, "ivec2": 8, "uvec2": 8, "vec3": 12, "ivec3": 12,
              "uvec3": 12, "vec4": 16, "ivec4": 16, "uvec4": 16, "mat4": 64}
    members = {}
    for (name, glsl_type), offset in zip(layout.fields, layout.offsets):
        _element, count, _alignment, stride = _std140_type(glsl_type)
        members[name] = (offset, count * stride if "[" in glsl_type else scalar.get(glsl_type, 4), glsl_type)
    return members


def _word(glsl_type: str) -> str:
    base = glsl_type.split("[")[0]
    if base.startswith(("int", "ivec", "bool")):
        return "<i"
    if base.startswith(("uint", "uvec")):
        return "<I"
    return "<f"


def _first_word(a: bytes, b: bytes, lo: int, hi: int) -> int:
    for at in range(lo, hi, 4):
        if a[at:at + 4] != b[at:at + 4]:
            return at
    return lo


def _plain(value):
    from rendering.native.program_values import _plain as plain

    return plain(value)


def _differing_element(a, b):
    """(index, a, b) of the first element where two decoded record values differ (scalars: index None)."""
    if isinstance(a, (bytes, bytearray)):
        for at in range(0, max(len(a), len(b)), 4):
            if a[at:at + 4] != b[at:at + 4]:
                x = struct.unpack_from("<f", a, at)[0] if at + 4 <= len(a) else None
                y = struct.unpack_from("<f", b, at)[0] if at + 4 <= len(b) else None
                return at // 4, x, y
        return None, None, None
    if isinstance(a, (tuple, list)):
        flat_a = [v for row in a for v in (row if isinstance(row, (tuple, list)) else (row,))]
        flat_b = [v for row in b for v in (row if isinstance(row, (tuple, list)) else (row,))]
        for index, (x, y) in enumerate(zip(flat_a, flat_b)):
            if struct.pack("<d", float(x)) != struct.pack("<d", float(y)):
                return index, x, y
        return len(flat_a), None, None
    return None, a, b


class Comparator:
    """Per input: the native side (what the core holds) against the Python side (what its renderer used)."""

    def __init__(self, declaration: LMode, core: Any) -> None:
        from core.visualizer_engine.native_schema import schema_for_mode

        self.declaration = declaration
        self.core = core
        self.schema = schema_for_mode(declaration.mode_id)
        self.layouts = {name: _std140_sizes(layout) for name, layout in declaration.layouts().items()}
        self._program_cache: dict = {}
        #: What was actually compared (a run whose levels compared nothing is not a proof): frames per level, member
        #: bytes per pass, setting names, stream bytes.
        self.coverage: dict = {"record_frames": 0, "settings_frames": 0, "settings_names": set(),
                               "settings_skipped": set(),
                               "pass_frames": {}, "member_bytes": {}, "stream_frames": {}, "stream_bytes": {}}

    # ---------------------------------------------------------------------- the native module's blocks
    def native_blocks(self, record: bytes, settings: dict, card: dict, sizes: dict,
                      variant: Any = None) -> tuple[dict, dict]:
        """pass name -> block bytes (None: the pass draws nothing), and member -> source. ``variant``: the program
        variant the route built (``GENERIC_MODE_PROGRAM_VARIANTS``; None for a mode with one program)."""
        if self.core is None:
            return {}, {}
        mode = self.declaration.mode_id
        if mode == "spectrum":
            from rendering.native.program_values import mode_fragment_pack
            from rendering.quick.visualizer.implementations.spectrum import SPECTRUM_FRAME_MEMBERS

            pack = self._program_cache.setdefault("pack", mode_fragment_pack(mode))
            bare = {k: v for k, v in card.items() if k != "settings"}
            block, _facts = self.core.spectrum_block(record, bare, pack, settings)
            sources = {name: ("record" if name in SPECTRUM_FRAME_MEMBERS else
                              "settings" if name in settings else "core") for name in self.layouts["spectrum"]}
            return {"spectrum": None if block is None else bytes(block)}, sources
        from rendering.native.mode import ModePass, _card, _settings, program_json, schema_table_entry
        from rendering.native.program_values import mode_fragment_pack
        from rendering.quick.visualizer.native_route import GENERIC_MODE_PROGRAM_VARIANTS, GENERIC_MODE_PROGRAMS

        key = (tuple(sorted((k, tuple(v)) for k, v in sizes.items())), variant)
        cached = self._program_cache.get(key)
        if cached is None:
            variants = GENERIC_MODE_PROGRAM_VARIANTS.get(mode)
            build = GENERIC_MODE_PROGRAMS.get(mode)
            if variants is not None:
                program = variants[1](variant)            # the route's own builder for the variant it built
            elif build is None:
                program = {"passes": [ModePass(mode, mode_fragment_pack(mode), "alpha")], "targets": [], "streams": []}
            else:
                program = build(mode_fragment_pack(mode), dict(sizes))
            declared, packs = program_json(program["passes"], program["targets"], program["streams"],
                                           unread=program.get("unread", ()))
            table = json.dumps(dict(schema_table_entry(self.schema)))
            cached = self._program_cache[key] = (program, declared, packs, table)
        program, declared, packs, table = cached
        target = tuple(int(v) for v in card.get("target_size") or (1, 1))
        found, facts = self.core.module.mode_blocks(table, declared, packs, _settings(settings), bytes(record),
                                                    _card(card), target)
        facts = json.loads(facts)
        decoded = self.schema.decode(record)
        blocks, sources = {}, {}
        for index, (ps, block) in enumerate(zip(program["passes"], found)):
            geometry = getattr(ps, "geometry", None)
            stream_name = getattr(geometry, "instance_from", None) if geometry is not None else None
            drawn = True
            if stream_name:
                stream = next(s for s in program["streams"] if s.name == stream_name)
                drawn = int(decoded.get(stream.used, 0)) > 0
            for count in (getattr(geometry, "vertices", None), getattr(geometry, "instances", None)):
                if isinstance(count, str):                 # a count the record carries: 0 draws nothing
                    drawn = drawn and int(decoded.get(count, 0)) > 0
            blocks[ps.name] = bytes(block) if drawn else None
            for member, source in (facts["passes"][index].get("sources") or {}).items():
                sources.setdefault(member, source)
        return blocks, sources

    # ------------------------------------------------------------------------------------- one input
    def compare(self, native: dict, python: dict) -> list[dict]:
        """Every difference of this input (empty: identical), first the record's, then settings, blocks, streams."""
        out: list[dict] = []
        if native["drawn"] != python["drawn"]:
            return [{"level": "drawn", "field": "frame", "native": native["drawn"], "python": python["drawn"]}]
        if not native["drawn"]:
            return []
        out += self._record(native["record"], python["record"])
        out += self._settings(native["settings"], python["values"])
        out += self._blocks(native, python)
        return out

    def coverage_report(self) -> dict:
        c = self.coverage
        return {**c, "settings_names": sorted(c["settings_names"]), "settings_skipped": sorted(c["settings_skipped"])}

    def _record(self, native: bytes, python: bytes) -> list[dict]:
        self.coverage["record_frames"] += 1
        if native == python:
            return []
        if len(native) != len(python):
            return [{"level": "record", "field": "(size)", "native": len(native), "python": len(python)}]
        a, b = self.schema.layout.unpack(native), self.schema.layout.unpack(python)
        for f in self.schema.layout.fields:
            if native[f.offset:f.offset + f.size] != python[f.offset:f.offset + f.size]:
                x, y = a[f.name], b[f.name]
                if f.kind == "f32":
                    x = bytes(native[f.offset:f.offset + f.size])
                    y = bytes(python[f.offset:f.offset + f.size])
                index, vx, vy = _differing_element(x, y)
                return [{"level": "record", "field": f.name, "element": index, "native": _show(vx),
                         "python": _show(vy)}]
        return [{"level": "record", "field": "(padding)", "native": None, "python": None}]

    def _settings(self, native: dict, python: dict) -> list[dict]:
        positional = self.declaration.positional
        out = []
        self.coverage["settings_frames"] += 1
        for name in sorted(native):
            if name in positional:
                continue
            if name not in python:
                self.coverage["settings_skipped"].add(name)      # delivered, not held by the Python renderer
                continue
            self.coverage["settings_names"].add(name)
            a, b = json.dumps(_plain(native[name])), json.dumps(_plain(python[name]))
            if a != b:
                out.append({"level": "settings", "field": name, "native": json.loads(a), "python": json.loads(b)})
        return out[:1] if out else []

    def _blocks(self, native: dict, python: dict) -> list[dict]:
        out = []
        native_blocks, sources = native["blocks"], native["sources"]
        if self.core is None:
            return out
        decoded = self.schema.decode(native["record"])
        logical = python["logical"]
        for name, members in self.layouts.items():
            n, p = native_blocks.get(name), python["blocks"].get(name)
            if (n is None) != (p is None):
                out.append({"level": "block", "pass": name, "field": "(pass drawn)", "native": n is not None,
                            "python": p is not None})
                continue
            if n is None:
                continue
            frames = self.coverage["pass_frames"]
            frames[name] = frames.get(name, 0) + 1
            covered = self.coverage["member_bytes"]
            for member, (offset, size, glsl_type) in members.items():
                if member in self.declaration.positional:
                    continue
                spans = self.declaration.read_spans(name, member, size, decoded, logical) \
                    if self.declaration.read_spans else None
                spans = [(0, size)] if spans is None else spans
                key = f"{name}.{member}"
                covered[key] = covered.get(key, 0) + sum(hi - lo for lo, hi in spans)
                for lo, hi in spans:
                    a, b = n[offset + lo:offset + hi], p[offset + lo:offset + hi]
                    if a != b:
                        at = _first_word(n, p, offset + lo, offset + hi)
                        fmt = _word(glsl_type)
                        value = (lambda data: struct.unpack_from(fmt, data, at)[0] if at + 4 <= len(data) else None)
                        out.append({"level": "block", "pass": name, "field": member, "element": (at - offset) // 4,
                                    "source": sources.get(member), "native": _show(value(n)),
                                    "python": _show(value(p))})
                        break
                if out and out[-1].get("pass") == name and out[-1]["field"] == member:
                    break
        for stream, (used, _path, _attribute) in self.declaration.streams.items():
            count = int(decoded[used])
            f = self.schema.layout.field(stream)
            n = bytes(native["record"][f.offset:f.offset + 4 * count])
            p = python["uploads"].get(stream)
            if count == 0 and p is None:
                continue
            c = self.coverage
            c["stream_frames"][stream] = c["stream_frames"].get(stream, 0) + 1
            c["stream_bytes"][stream] = c["stream_bytes"].get(stream, 0) + len(n)
            if p is None or n != p:
                index, x, y = _differing_element(n, p or b"")
                out.append({"level": "stream", "field": stream, "element": index, "native": _show(x),
                            "python": _show(y), "native_floats": count,
                            "python_floats": None if p is None else len(p) // 4})
        return out


def _show(value):
    if isinstance(value, float):
        return float.hex(value) if not math.isfinite(value) else value
    return value


# ------------------------------------------------------------------------------------- the delivery stream

def _jsonable(value):
    """``value`` as plain JSON data (mappings, sequences and numpy scalars resolved; floats kept exactly)."""
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    item = getattr(value, "item", None)
    if callable(item) and not isinstance(value, (str, bytes)):
        return _jsonable(item())
    return value


class DeliveryStream:
    """What the product's route delivered to the native core, input by input (fast-proof part 2 step 4b): the record
    the core holds, the settings, the card and the target sizes, each written when it changes, and whether the native
    side draws. ``deliveries.jsonl`` holds one line per input; ``records.bin`` the records, each stored once per change
    (the line names its offset). A native-only player (``native_stream_player.py``) replays it on either API."""

    def __init__(self, folder: Path, mode: str, keep: tuple[int, int] | None = None) -> None:
        """``keep``: only the inputs in ``[start, end)`` are written (a window run), the first with its whole state."""
        self.folder = Path(folder)
        self.folder.mkdir(parents=True, exist_ok=True)
        self._lines = (self.folder / "deliveries.jsonl").open("w", encoding="utf-8")
        self._records = (self.folder / "records.bin").open("wb")
        self._last: dict = {}
        self._keep = keep
        self._lines.write(json.dumps({"mode": mode, "format": 1, "keep": keep}) + "\n")

    def add(self, index: int, native: dict) -> None:
        if self._keep is not None and not self._keep[0] <= index < self._keep[1]:
            return
        line: dict = {"input": index, "drawn": bool(native["drawn"])}
        if native["drawn"]:
            record = native["record"]
            if record is not self._last.get("record_object") and record != self._last.get("record"):
                line["record"] = [self._records.tell(), len(record)]
                self._records.write(record)
                self._last["record"] = record
            self._last["record_object"] = record
            for key in ("settings", "card", "sizes"):
                value = json.loads(json.dumps(_jsonable(native.get(key) or {})))
                if value != self._last.get(key):
                    line[key] = value
                    self._last[key] = value
        self._lines.write(json.dumps(line) + "\n")

    def close(self) -> None:
        self._lines.close()
        self._records.close()


# --------------------------------------------------------------------------------------------- the mirror

class IdentityMirror:
    """``owner_worker_gate.identity_run``'s scene mirror for layer L: attaches the product's route to the owner's own
    item, and at each input compares the two paths (``Comparator``)."""

    def __init__(self, declaration: LMode, core: Any, *, switch_input: int, out: Path | None,
                 controls: tuple[tuple[str, int], ...] = ()) -> None:
        self.declaration = declaration
        self.comparator = Comparator(declaration, core)
        self.python = RecordingPython(declaration)
        self.switch_input = int(switch_input)
        self.out = out
        self.controls = dict((kind, at) for kind, at in controls)
        self.applied: dict[str, int] = {}
        self.route: Any = None
        self.item: Any = None
        self.index = 0
        self._core_record: bytes | None = None
        self._core_revision: Any = None
        self._python_snapshot: Any = None
        self.mismatches: list[dict] = []
        self.counts = {name: {"expected": 0, "compared": 0, "both_undrawn": 0, "mismatched": 0}
                       for name in ("first", "second", "switch")}
        self.started = time.perf_counter()
        self.route_failures = 0
        self.publications = 0
        self.refused_by_core = 0
        self.refused_by_node = 0
        #: ``DeliveryStream``: what reached the native core per input, kept for a native-only replay (step 4b).
        self.deliveries: DeliveryStream | None = None

    # ---------------------------------------------------------------------------------- the route's edges
    def bound(self, identity) -> None:
        self._core_record = None
        self._python_snapshot = None

    def dropped(self) -> None:
        self._core_record = None
        self._python_snapshot = None

    def published(self, snapshot, payload: bytes, flags: int) -> None:
        from core.visualizer_engine import packet_abi
        from rendering.quick.visualizer.render_contract import snapshot_is_render_admissible

        self.publications += 1
        # The core's admission (stream_source.cpp): a present frame, and a playing one only from its current source.
        admitted = bool(flags & packet_abi.FLAG_PRESENT_FRAME) and (
            not flags & packet_abi.FLAG_PLAYING or bool(flags & packet_abi.FLAG_SOURCE_CURRENT))
        if admitted:
            record = payload
            at = self.controls.get("ulp")
            if at is not None and "ulp" not in self.applied and self.index >= at:
                record = self._perturbed(record)
                self.applied["ulp"] = self.index
            at = self.controls.get("drop")
            if at is not None and "drop" not in self.applied and self.index >= at:
                self.applied["drop"] = self.index         # the core never receives this frame
            else:
                self._core_record = record
        else:
            self.refused_by_core += 1
        if snapshot_is_render_admissible(snapshot):
            self._python_snapshot = snapshot
        else:
            self.refused_by_node += 1

    def _perturbed(self, record: bytes) -> bytes:
        f = self.comparator.schema.layout.field(self.declaration.ulp_field)
        out = bytearray(record)
        value = struct.unpack_from("<d", out, f.offset)[0]
        struct.pack_into("<d", out, f.offset, math.nextafter(value, math.inf))
        return bytes(out)

    # --------------------------------------------------------------------------------- identity_run's mirror
    def attach(self, runtime: Any) -> None:
        from tools.visualizer_replay.owner_render_parity import DISPLAY

        scene = runtime.scene_controller
        self.item = scene._ensure_visualizer_items()
        dpr = float(runtime.window.devicePixelRatio())
        Route = _route_class()
        self.route = Route(_Core(), self.item.parentItem())
        self.route.metrics = ((float(DISPLAY[0]), float(DISPLAY[1])), (round(DISPLAY[0] * dpr), round(DISPLAY[1] * dpr)))
        self.route.observer = self
        self.item.attach_native_route(self.route)
        self.route.prepare()

    def frame(self, index: int) -> dict:
        self.index = index
        native, python = self._native(), self._python()
        if self.deliveries is not None:
            self.deliveries.add(index, native)
        differences = self.comparator.compare(native, python)
        part = ("first" if index < self.switch_input // 2 else "second") if index < self.switch_input else "switch"
        counts = self.counts[part]
        counts["expected"] += 1
        if differences:
            counts["mismatched"] += 1
            entry = {"input": index, "half": part, "first": differences[0], "levels": sorted({d["level"] for d in differences}),
                     "differences": differences[:6], "native_revision": native.get("revision"),
                     "python_revision": python.get("revision")}
            self.mismatches.append(entry)
            self._progress({"mismatch": entry})
        elif native["drawn"]:
            counts["compared"] += 1
        else:
            counts["both_undrawn"] += 1
        self.index = index + 1
        if (index + 1) % PROGRESS_EVERY == 0:
            self._progress({"inputs": index + 1, "counts": self.counts, "mismatches": len(self.mismatches),
                            "elapsed_s": round(time.perf_counter() - self.started, 1)})
            self.write_report({"partial": True})
        return {"input": index, "identical": not differences}

    def _native(self) -> dict:
        route = self.route
        mode = self.declaration.mode_id
        bound = route is not None and route.identity is not None and str(route.identity.mode_id) == mode
        content = route._content if bound else None
        item = getattr(content, "item", None)
        shown = bool(item is not None and item.composite.visible and route._placed is not None)
        if not (bound and shown and self._core_record is not None and item.settings_values is not None
                and item.card_values is not None):
            return {"drawn": False}
        if self.declaration.drawn is not None and not self.declaration.drawn(
                self.comparator.schema.decode(self._core_record)):
            return {"drawn": False}                       # shown, but the program draws no pass this frame
        settings, card = item.settings_values, item.card_values
        sizes = dict(getattr(content, "_sizes", None) or {})
        at = self.controls.get("setting")
        if at is not None and "setting" not in self.applied and self.index >= at:
            # The settings control: the first numeric delivered setting (by name) raised by 0.25 for this frame.
            name = next(n for n in sorted(settings) if isinstance(settings[n], (int, float))
                        and not isinstance(settings[n], bool) and n not in self.declaration.positional)
            settings = dict(settings, **{name: float(settings[name]) + 0.25})
            self.applied["setting"] = self.index
            self.applied["setting_name"] = name
        blocks, sources = self.comparator.native_blocks(self._core_record, settings, card, sizes,
                                                        getattr(content, "_program_variant", None))
        at = self.controls.get("block")
        if at is not None and "block" not in self.applied and self.index >= at and blocks:
            # The block control: one packed member of the first drawn pass with a float member raised by 1.0 for this
            # frame (u_dpr where the pass has it, as audit 9 ran it; else its first float member).
            def floats(name):
                return [m for m, (_o, _s, t) in self.comparator.layouts[name].items()
                        if t == "float" and m not in self.declaration.positional]

            pass_name = next(n for n, b in blocks.items() if b is not None and n in self.comparator.layouts
                             and ("u_dpr" in self.comparator.layouts[n] or floats(n)))
            members = self.comparator.layouts[pass_name]
            member = "u_dpr" if "u_dpr" in members else floats(pass_name)[0]
            offset = members[member][0]
            data = bytearray(blocks[pass_name])
            struct.pack_into("<f", data, offset, struct.unpack_from("<f", data, offset)[0] + 1.0)
            blocks = dict(blocks, **{pass_name: bytes(data)})
            self.applied["block"] = self.index
            self.applied["block_member"] = f"{pass_name}.{member}"
        revision = getattr(route._snapshot, "logical_revision", None)
        return {"drawn": True, "record": self._core_record, "settings": settings, "card": card, "blocks": blocks,
                "sources": sources, "revision": revision, "sizes": sizes}

    def _python(self) -> dict:
        import dataclasses

        from rendering.quick.visualizer.render_contract import QuickVisualizerRenderFrame

        item = self.item
        snapshot = self._python_snapshot
        presentation = getattr(item, "presentation", None)
        identity = getattr(item, "render_identity", None)
        if (snapshot is None or presentation is None or identity is None
                or str(identity.mode_id) != self.declaration.mode_id):
            return {"drawn": False}
        width, height = float(presentation.outer_rect[2]), float(presentation.outer_rect[3])
        if min(width, height) <= 0.0:
            return {"drawn": False}
        (window_w, window_h), pixels = self.route.metrics
        x, y = (float(v) for v in presentation.outer_rect[:2])
        matrix = tuple(struct.unpack("<16f", struct.pack(
            "<16f", 2.0 / window_w, 0.0, 0.0, 0.0, 0.0, -2.0 / window_h, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0,
            -1.0 + 2.0 * x / window_w, 1.0 - 2.0 * y / window_h, 0.0, 1.0)))
        frame = QuickVisualizerRenderFrame(snapshot=snapshot, viewport=(0, 0, int(pixels[0]), int(pixels[1])),
                                           logical_size=(width, height), matrix_values=matrix, quad_vao=1)
        drawn = self.python.draw(frame)
        if not drawn["blocks"]:
            return {"drawn": False}
        del dataclasses
        return {"drawn": True, "record": self.comparator.schema.encode(snapshot.logical), "logical": snapshot.logical,
                "revision": snapshot.logical_revision, **drawn}

    def close(self) -> None:
        if self.route is not None:
            self.route_failures = int(self.route.failures)
        self.python.close()

    # ------------------------------------------------------------------------------------------ output
    def _progress(self, line: dict) -> None:
        if self.out is None:
            return
        with (self.out / PROGRESS_NAME).open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(line, default=str) + "\n")

    def summary(self) -> dict:
        halves = {}
        for name, counts in self.counts.items():
            judged = counts["compared"] + counts["both_undrawn"]
            halves[name] = {**counts, "judged": judged}
        return {"halves": halves, "mismatching_frames": len(self.mismatches), "publications": self.publications,
                "refused_by_core": self.refused_by_core, "refused_by_node": self.refused_by_node,
                "route_failures": self.route_failures, "controls_applied": dict(self.applied),
                "coverage": self.comparator.coverage_report(),
                "elapsed_s": round(time.perf_counter() - self.started, 1)}

    def write_report(self, extra: dict) -> None:
        if self.out is None:
            return
        report = {**getattr(self, "meta", {}), **self.summary(), **extra, "mismatches": self.mismatches}
        (self.out / REPORT_NAME).write_text(json.dumps(report, indent=1, default=str), encoding="utf-8")


# --------------------------------------------------------------------------------------------------- the run

def run(mode: str, *, recording: str | None = None, seconds: float = 60.0, variant: str = "a",
        out: Path | None = None, module_dir: Path | None = None,
        controls: tuple[tuple[str, int], ...] = (), deliveries: Path | None = None,
        window: tuple[int, int] | None = None, restart: bool = False) -> dict:
    """Layer L of ``mode`` over a take (``recording``, its first ``seconds``; None: the shipped Studio clip, a smoke
    check only). ``module_dir``: the native module (its GPU-free block packer); None: the block level is not run.
    ``deliveries``: a folder the run's ``DeliveryStream`` is written to (for ``native_stream_player.py``).
    ``window``: only the inputs ``[start, end)`` are written to it; the simulation still ticks every input from the
    take's first (a window is cut from one continuous run, guide section 3). ``restart``: the coverage proof's control,
    the simulation started cold at the window's first input (the script cut there; its inputs numbered from 0)."""
    import tools.expanded_visualizer_evidence as evidence
    from tools.visualizer_replay import owner_render_parity as parity
    from tools.visualizer_replay import owner_worker_gate as gate
    from widgets.spotify_visualizer import engine_worker_link

    if mode not in MODES:
        raise ValueError(f"layer L declares {sorted(MODES)}, not {mode!r}")
    core = None
    if module_dir is not None:
        from rendering.native import load

        core = load(Path(module_dir))
    clip = evidence.load_recording(recording, seconds) if recording else evidence.shipped_clip(seconds)
    script = parity.parity_script(clip.frames, mode)
    keep = None
    if window is not None:
        start, end = (int(v) for v in window)
        keep = (start, end)
        if restart:
            # The control: everything before the window's first input dropped, so the owner starts cold there.
            positions = [i for i, (kind, _v) in enumerate(script) if kind == "input"]
            script = script[positions[start]:]
            keep = (0, end - start)
    switch_at = next(i for i, (kind, _v) in enumerate(script) if kind == "mode")
    switch_input = sum(1 for kind, _value in script[:switch_at] if kind == "input")
    if out is not None:
        out = Path(out)
        out.mkdir(parents=True, exist_ok=True)
        (out / PROGRESS_NAME).write_text("", encoding="utf-8")
    mirror = IdentityMirror(MODES[mode], core, switch_input=switch_input, out=out, controls=controls)
    mirror.meta = {"mode": mode, "variant": variant, "clip": clip.name, "seconds": seconds,
                   "clip_frames": len(clip.frames), "switch_input": switch_input,
                   "half_inputs": {"first": [0, switch_input // 2], "second": [switch_input // 2, switch_input]},
                   "block_level": core is not None, "module": None if core is None else dict(core.info),
                   "positional": dict(MODES[mode].positional), "controls": [list(c) for c in controls]}
    engine_worker_link.reset_run_state_for_testing()
    settings = parity.section_settings(mode, variant)
    if deliveries is not None:
        mirror.deliveries = DeliveryStream(Path(deliveries), mode, keep=keep)
    register = MODES[mode].register
    try:
        with (register() if register is not None else contextlib.nullcontext()):
            run_report = gate.identity_run(mode, script, worker=False, supervisor=None, namespace=None,
                                           settings=settings, scene_mirror=mirror)
    finally:
        if mirror.deliveries is not None:
            mirror.deliveries.close()
    summary = mirror.summary()
    halves = summary["halves"]
    # Expected: every input of the mode's shown span (the halves); judged: compared or undrawn on both paths.
    complete = all(halves[name]["judged"] == halves[name]["expected"] > 0 for name in ("first", "second"))
    compared = sum(halves[name]["compared"] for name in ("first", "second"))
    report = {**mirror.meta, **summary, "inputs": run_report["inputs"], "final_mode": run_report["final_mode"],
              "identical": bool(complete and not mirror.mismatches and compared > 0),
              "mismatches": mirror.mismatches}
    if out is not None:
        mirror.write_report({"partial": False, "identical": report["identical"], "inputs": report["inputs"],
                             "final_mode": report["final_mode"]})
    return report


def _control(value: str) -> tuple[str, int]:
    kind, _, at = value.partition("@")
    if kind not in ("ulp", "drop", "setting", "block") or not at.isdigit():
        raise argparse.ArgumentTypeError("a control is ulp@, drop@, setting@ or block@<input>")
    return kind, int(at)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--mode", required=True, choices=sorted(MODES))
    parser.add_argument("--recording", default=None,
                        help="one of the operator's recorded takes (logs/visualizer_recordings/<name>.jsonl, read "
                             "only); without it the shipped Studio clip (a smoke check only)")
    parser.add_argument("--seconds", type=float, default=60.0)
    parser.add_argument("--variant", default="a", choices=("a", "b"))
    parser.add_argument("--out", type=artifact_paths.evidence_arg, required=True)
    parser.add_argument("--module-dir", type=Path, default=Path("release/native_module"))
    parser.add_argument("--no-blocks", action="store_true", help="skip the block level (no native module needed)")
    parser.add_argument("--control", type=_control, action="append", default=[],
                        help="a negative control: ulp@<input> (the record's ulp field one ulp up from that input's "
                             "frame) or drop@<input> (that frame never reaches the core)")
    parser.add_argument("--deliveries", type=Path, default=None,
                        help="a folder to write the run's delivery stream to (what reached the native core per input), "
                             "for tools/visualizer_replay/native_stream_player.py")
    args = parser.parse_args(argv)
    try:
        import psutil
        psutil.Process().nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    except Exception:
        pass
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication(["native-record-identity"])
    report = run(args.mode, recording=args.recording, seconds=args.seconds, variant=args.variant, out=args.out,
                 module_dir=None if args.no_blocks else args.module_dir.resolve(), controls=tuple(args.control),
                 deliveries=args.deliveries)
    halves = report["halves"]
    for name in ("first", "second", "switch"):
        h = halves[name]
        print(f"[L] {args.mode} {name:6s}: judged {h['judged']} of {h['expected']} expected "
              f"(compared {h['compared']}, undrawn on both {h['both_undrawn']}), mismatching {h['mismatched']}",
              flush=True)
    coverage = report["coverage"]
    print(f"[L] compared: record {coverage['record_frames']} frames, settings {coverage['settings_frames']} frames over "
          f"{len(coverage['settings_names'])} names, passes {coverage['pass_frames']}, streams "
          f"{coverage['stream_frames']} ({coverage['stream_bytes']} bytes)", flush=True)
    for entry in report["mismatches"][:20]:
        print(f"[L] input {entry['input']}: {json.dumps(entry['first'], default=str)}", flush=True)
    print(f"[L] {args.mode} {report['clip']}: {'IDENTICAL' if report['identical'] else 'NOT IDENTICAL'} "
          f"({report['mismatching_frames']} mismatching frames, {report['elapsed_s']} s)", flush=True)
    del app
    return 0 if report["identical"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
