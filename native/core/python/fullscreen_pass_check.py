"""N4.a's proof of the fullscreen pass and image sampling as a primitive (Current_Plan.md item 8b, section N2b;
``native/core/src/mode_content.h``), through ``rendering.native``: N2.9's generic pass widened to the product's
fullscreen fragments, never a second pass layer, and never registered (no transition is drawn natively in the product).

A transition's own fragment (``rendering/gl_programs/<id>_program.py``, baked here by ``tools/regen_qrc.py``'s baker, the
product file unchanged) is drawn by the core between two real photos (PERSONALSET wallpapers) the item holds as its
textures ``old`` and ``new``: its samplers ``uOldTex`` and ``uNewTex`` bound by name (linear, clamp, no mips: the Python
renderer's state), its ``vUv`` the item quad's, its block filled by name from the core's conventions (``uMatrix``,
``uItemSize``, ``u_target_px``), the settings (every value of ``FullscreenPassRenderer.block_values`` that is not per
frame) and a harness record carrying the per-frame values (``u_progress``, ``u_time``; mode code ``MODE_CODE``, outside
the product's table). The Python reference is the production GL host (``tools/transition_contact_sheet.py``
``TransitionCapture``) drawing the same run at the same progress into a target of the item's device size.

The module (``release/native_module``, built on GitHub) is loaded the product's way, one child process per graphics API:
OpenGL first, then Vulkan on the module's own instance and devices (D6). No window is ever visible (the hidden host).

Rounds:
  shape     (OpenGL child; GPU-free) the seven fullscreen transitions' own packs are admitted with their two pictures
            bound (vUv, one pass block, no u_resolution), each refused unbound; Bubble's pack admitted with its two
            samplers bound and refused unbound; an unknown, doubly bound (by name and by binding), conventions-binding
            and block-binding sampler refused; the harness's settings, record and the core's members fill every block
            member exactly once and agree with the Python renderer's values where the core fills them.
  draw      (each API) Crossfade and Burn (defaults, and every option on in a diagonal direction) at PROGRESS on the
            item at dpr 1 and 1.5: OpenGL equal to the Python renderer pixel for pixel (rule (a)); its negative control
            (the native frame against the Python frame of the next progress) differs; the same frame drawn twice is
            hash-identical; a shader change (Crossfade with its pictures swapped) and a value change (Burn's direction)
            show with no module build (rule (g)); a progress change uploads no texture.
  textures  (each API) the lifetime: uploads once and nothing again at rest (no record, no GPU sample, no upload over
            rest frames); a replaced image of the same size keeps the object; another size recreates it; mips generated
            (a mip-sampled texture counts its levels; a mip sampler over a texture without mips refused); a removed
            texture is released at the next frame and the item waits for it; a node made again reports its textures
            lost and draws again once they are sent; an item destroyed with its textures uploaded, and one destroyed with
            its images never uploaded, leave no texture, byte or copy behind.
  timing    (each API) GPU time of the pass (median and p90 of the surface's record) for Crossfade and Burn at
            TIMING_TARGET, and nothing at rest.
Then Vulkan's frames against OpenGL's (within VULKAN_TOLERANCE levels; both native; rule (b)).

Usage (repository venv, from the checkout holding the built module):
  python native/core/python/fullscreen_pass_check.py --module-dir release/native_module --require-validation
      --layer-path D:\\Temp\\Scratch\\SRPSS\\native_spike\\validation_layers\\extracted
  [--apis opengl vulkan] [--rounds shape draw textures timing] [--photos A.png B.png] [--label n4a_fullscreen_pass]
Evidence: .artifacts/evidence/native_core/n4_a/<date>_<label>/ (summary.json; one PNG sheet per API). Exit 0 whenever
the harness ran; the verdict is the last printed line ("N4A VERDICT PASS" or "N4A VERDICT FAIL: ...").
"""
from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import math
import subprocess
import sys
import tempfile
import time
import traceback
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

APIS = ("opengl", "vulkan")
ROUNDS = ("shape", "draw", "textures", "timing")
CHILD_TIMEOUT_S = 1500
#: The seven transitions that draw one fragment between two pictures through ``FullscreenPassRenderer`` (their modules
#: under ``rendering/quick/transitions/implementations``), the first consumers with N5.7a's presenter.
FULLSCREEN_TRANSITIONS = ("crossfade", "burn", "particle", "ripple", "slide", "warp", "wipe")
#: Drawn natively here: Crossfade's own fragment, and Burn with its own values.
PROVED = ("crossfade", "burn")
#: The widened values: each drawn transition's production defaults and, for Burn, every option on in a diagonal.
VARIANTS = {"crossfade": {}, "burn": {},
            "burn_options": {"direction": 4, "flames": True, "ember_veins": True, "smoke_enabled": True,
                             "ash_enabled": True}}
PROGRESS = (0.0, 0.05, 0.2, 0.35, 0.5, 0.65, 0.8, 0.95, 1.0)
DURATION_MS = 2400
CARD = (640, 360)                # the item's logical size
DPRS = (1.0, 1.5)
MARGIN = 8
REST_FRAMES = 3
TIMED_FRAMES = 60
TIMING_TARGET = (2560, 1440)
VULKAN_TOLERANCE = 1             # 8-bit levels, native Vulkan against native OpenGL
SLOT_BYTES = 256
IDENTITY = {"runtime_generation": 7, "engine_generation": 3, "activation_id": 11}
#: The harness record's mode: outside ``packet_abi.MODE_CODES`` (append-only from 1; a test holds it out).
MODE_ID = "fullscreen_probe"
MODE_CODE = 253
#: The block members a transition changes per frame (the record); every other value is a setting.
PER_FRAME = ("u_progress", "u_time")
TEXTURES = {"uOldTex": "old", "uNewTex": "new"}
PHOTO_FOLDER = Path(r"C:\Users\Basjohn\Documents\[4] WALLPAPERS\PERSONALSET")
PHOTOS = (PHOTO_FOLDER / "859804.png", PHOTO_FOLDER / "698047.png")
_ALLOWED_ENV: set[str] = set()


# --------------------------------------------------------------------------------------------------- the transitions

def renderer_class(transition_id: str):
    """The transition's ``FullscreenPassRenderer`` subclass (the one its module defines)."""
    from rendering.quick.transitions.fullscreen_pass import FullscreenPassRenderer

    module = importlib.import_module(f"rendering.quick.transitions.implementations.{transition_id}")
    found = [value for value in vars(module).values()
             if isinstance(value, type) and issubclass(value, FullscreenPassRenderer)
             and value.__module__ == module.__name__]
    if len(found) != 1:
        raise ValueError(f"{transition_id} defines {len(found)} fullscreen pass renderers, not one")
    return found[0]


def block_name(transition_id: str) -> str:
    """The name of the transition's pass block, as its fragment declares it."""
    import re

    match = re.search(r"uniform\s+(\w+Pass)\s*\{", renderer_class(transition_id).fragment_source)
    if match is None:
        raise ValueError(f"{transition_id}'s fragment declares no pass block")
    return match.group(1)


def bake(text: str, name: str, folder: Path) -> bytes:
    """``text`` baked by ``tools/regen_qrc.py``'s own baker for every shipped target, in ``folder``: no module build."""
    from tools import regen_qrc

    Path(folder).mkdir(parents=True, exist_ok=True)
    source = Path(folder) / name
    source.write_text(text, encoding="utf-8")
    pack = source.with_name(name + ".qsb")
    regen_qrc._bake_quick_shader(regen_qrc.quick_shader_baker(sys.executable), source, pack,
                                 regen_qrc.quick_shader_targets(), subprocess.run)
    return pack.read_bytes()


def samplers(old_mips: str = "none"):
    """The two pictures' samplers, in the Python renderer's state (linear, clamp; no mips); ``old_mips``: the old
    picture's mip filter (the textures round's mip sampler)."""
    from rendering.native.mode import PassSampler

    return tuple(PassSampler(name, texture, "linear", "clamp", old_mips if texture == "old" else "none")
                 for name, texture in TEXTURES.items())


def transition_pass(transition_id: str, folder: Path, *, text: str | None = None, old_mips: str = "none"):
    """The transition's own fragment (or ``text``) baked, as a pass with its pictures bound (blend replace)."""
    from rendering.native.mode import ModePass

    source = renderer_class(transition_id).fragment_source if text is None else text
    return ModePass(transition_id, bake(source, f"{transition_id}.frag", folder), "replace", samplers(old_mips))


SAMPLER_VARIANTS = ("binding17", "block_binding", "shared_binding")


def _replaced(text: str, old: str, new: str) -> str:
    if text.count(old) != 1:
        raise ValueError(f"{old!r} is in the shader {text.count(old)} times, not once")
    return text.replace(old, new)


def sampler_variant_text(kind: str) -> str:
    """Crossfade's fragment with a sampler where a sampler may not be: at the conventions block's binding, at its own
    block's binding, or at the other sampler's binding (``SAMPLER_VARIANTS``)."""
    text = renderer_class("crossfade").fragment_source
    old_line = "layout(binding = 0) uniform sampler2D uOldTex;"
    if kind == "binding17":
        return _replaced(text, old_line, "layout(binding = 17) uniform sampler2D uOldTex;")
    if kind == "block_binding":
        return _replaced(text, old_line, "layout(binding = 18) uniform sampler2D uOldTex;")
    if kind == "shared_binding":
        return _replaced(text, "layout(binding = 1) uniform sampler2D uNewTex;",
                         "layout(binding = 0) uniform sampler2D uNewTex;")
    raise ValueError(f"unknown variant {kind!r} ({', '.join(SAMPLER_VARIANTS)})")


def uv_bits_text() -> str:
    """Crossfade's fragment changed to write the interpolated vUv's low bits (fract(vUv * 2^20): one ulp near 0.5 is
    about 16 levels), its pictures still read: the core's uv seen bit for bit, compared across backends (rule (b)'s
    attribution: a backend difference elsewhere is the fragment's own arithmetic, not the core's uv)."""
    return _replaced(renderer_class("crossfade").fragment_source, "FragColor = mix(oldColor, newColor, t);",
                     "FragColor = vec4(fract(vUv * 1048576.0), fract(vUv.x * 4096.0) "
                     "+ 1e-30 * (oldColor.r + newColor.g + t), 1.0);")


def swapped_crossfade_text() -> str:
    """The proof's shader change (rule (g)): Crossfade with its two pictures swapped."""
    return _replaced(renderer_class("crossfade").fragment_source, "FragColor = mix(oldColor, newColor, t);",
                     "FragColor = mix(newColor, oldColor, t);")


# --------------------------------------------------------------------------------------------------- the values

def block_members(transition_id: str) -> list[str]:
    from rendering.gl_programs.portable import block_declaration, block_layout_from_glsl

    cls = renderer_class(transition_id)
    return [name for name, _kind in block_layout_from_glsl(block_declaration(cls.fragment_source,
                                                                             block_name(transition_id))).fields]


def per_frame_members(transition_id: str) -> tuple[str, ...]:
    members = block_members(transition_id)
    return tuple(name for name in PER_FRAME if name in members)


def split_values(transition_id: str, values: Mapping[str, Any]) -> tuple[dict, dict, dict]:
    """The Python renderer's block values (``FullscreenPassRenderer.block_values``) by the source that fills them in the
    core: (the core's members, the settings, the record)."""
    from rendering.native.mode import MODE_CORE_MEMBERS

    frame = set(per_frame_members(transition_id))
    core = {k: v for k, v in values.items() if k in MODE_CORE_MEMBERS}
    record = {k: v for k, v in values.items() if k in frame}
    settings = {k: v for k, v in values.items() if k not in MODE_CORE_MEMBERS and k not in frame}
    return core, settings, record


def frame_schema(transition_id: str):
    """The harness record of ``transition_id``: its per-frame members as f64 fields (a float each), never registered."""
    from core.visualizer_engine.native_schema import NativeLayout, NativeSchema

    @dataclass(frozen=True, slots=True)
    class HarnessSchema(NativeSchema):
        """A ``NativeSchema`` whose mode code is its own, not ``MODE_CODES``' (never registered)."""

        code: int = 0

        @property
        def mode_code(self) -> int:
            return self.code

    names = per_frame_members(transition_id)
    layout = NativeLayout.build(tuple((name, "f64", 1) for name in names))
    holder: dict[str, Any] = {}

    def encode(values: Mapping[str, Any]) -> bytes:
        return layout.pack(holder["schema"].schema_id, values)

    def decode(payload: bytes) -> dict:
        from core.visualizer_engine.native_schema import validate_record_head

        validate_record_head(payload, holder["schema"])
        unpacked = layout.unpack(payload)
        return {name: unpacked[name] for name in names}

    schema = HarnessSchema(mode_id=MODE_ID, version=1 + FULLSCREEN_TRANSITIONS.index(transition_id), layout=layout,
                           encode=encode, decode=decode, fields=names, checks=(), code=MODE_CODE)
    holder["schema"] = schema
    return schema


def target_pixels(dpr: float, card: tuple[int, int] = CARD) -> tuple[int, int]:
    return (int(round(card[0] * dpr)), int(round(card[1] * dpr)))


def core_agreement(core_values: Mapping[str, Any], card: Mapping[str, Any], target: tuple[int, int]) -> dict:
    """Where the core fills a member the Python renderer also sets, whether the two agree (``uMatrix`` excepted: the
    Python quad's, which no fragment reads; ``uItemSize`` at dpr 1 only, the capture's logical size being its pixels)."""
    out = {}
    for name, value in core_values.items():
        if name == "u_target_px":
            out[name] = [float(v) for v in value] == [float(target[0]), float(target[1])]
        elif name == "uItemSize" and float(card["dpr"]) == 1.0:
            out[name] = [float(v) for v in value] == [float(v) for v in card["item_size"]]
    return out


def photos(paths, size: tuple[int, int]):
    """The two photos at ``size`` (RGBA, Lanczos), as both renderers receive them."""
    from PIL import Image

    return tuple(Image.open(path).convert("RGBA").resize(size, Image.Resampling.LANCZOS) for path in paths)


def runs(capture, transition_id: str, overrides: Mapping[str, Any]):
    """The production run of ``transition_id`` with its parameters ``overrides`` laid over."""
    from rendering.quick.transitions.state import TransitionRequest, TransitionRun

    run = capture.production_run(transition_id, duration_ms=DURATION_MS)
    if not overrides:
        return run
    r = run.request
    request = TransitionRequest(r.runtime_generation, r.transition_id, r.requested_name, r.selected_from_random,
                                r.duration_ms, r.direction, {**r.parameter_dict(), **overrides}, r.source_image,
                                r.destination_image)
    return TransitionRun.start(run_id=run.run_id + 1, request=request, start_ns=0)


def compare(native, reference) -> dict:
    """RGB levels of two top-down frames of one size: pixels differing, the largest difference, equal."""
    import numpy as np

    if native.shape[:2] != reference.shape[:2]:
        return {"equal": False, "shape": [list(native.shape), list(reference.shape)]}
    difference = np.abs(native[..., :3].astype(np.int16) - reference[..., :3].astype(np.int16))
    differing = int(np.count_nonzero(difference.max(axis=2)))
    return {"equal": differing == 0, "differing_pixels": differing, "max_level": int(difference.max())}


def digest(pixels) -> str:
    return hashlib.sha256(pixels[..., :3].tobytes()).hexdigest()[:16]


# --------------------------------------------------------------------------------------------------- the stream

class Stream:
    """The harness record's frame stream (the engine worker's side in a product mode)."""

    def __init__(self, schema) -> None:
        from core.visualizer_engine.packet_abi import FramePacketWriter, create_frame_mapping

        self.schema = schema
        self.memory = create_frame_mapping(generation=IDENTITY["runtime_generation"], slot_bytes=SLOT_BYTES,
                                           engine_generation=IDENTITY["engine_generation"],
                                           activation_id=IDENTITY["activation_id"], mode_code=MODE_CODE,
                                           token=uuid.uuid4().hex[:12])
        self.writer = FramePacketWriter(self.memory.buf)
        self.step = 0
        self.closed = False

    @property
    def name(self) -> str:
        return self.memory.name

    @property
    def expect(self) -> dict:
        return {**IDENTITY, "mode_code": MODE_CODE}

    def publish(self, values: Mapping[str, Any]) -> int:
        from core.visualizer_engine.packet_abi import FLAG_PRESENT_FRAME

        self.step += 1
        return self.writer.publish(self.schema.encode(values), payload_schema=self.schema.schema_id,
                                   logical_timestamp=float(self.step), flags=FLAG_PRESENT_FRAME,
                                   mode_code=MODE_CODE, **IDENTITY)

    def close(self) -> None:
        if self.closed:
            return
        self.closed = True
        self.writer.release()
        self.memory.close()
        self.memory.unlink()


# --------------------------------------------------------------------------------------------------- the scene

SCENE_QML = b"""import QtQuick
Rectangle {
    color: "#000000"
    Item { objectName: "contentHost"; x: %(margin)d; y: %(margin)d; width: 4; height: 4 }
}
""" % {b"margin": MARGIN}


class Scene:
    """An opaque black display with one fullscreen-pass item at (MARGIN, MARGIN), its target on the item's own rect."""

    def __init__(self, core, engine, host, dpr: float, card: tuple[int, int] = CARD) -> None:
        from PySide6.QtCore import QUrl
        from PySide6.QtQml import QQmlComponent
        from PySide6.QtQuick import QQuickItem

        import probe_rings

        self.host = host
        self.dpr = float(dpr)
        self.size = card
        self.component = QQmlComponent(engine)
        self.component.setData(SCENE_QML, QUrl())
        self.root = self.component.create()
        if self.root is None:
            raise RuntimeError(f"the scene did not load: {self.component.errorString()}")
        self.content = self.root.findChild(QQuickItem, "contentHost")
        host.set_content(self.root)
        self.mode = core.mode(self.content)
        self.mode.composite.set(rect=[0.0, 0.0, float(card[0]), float(card[1])], coverage=None, quarters=0,
                                visible=True)
        self.card = probe_rings.harness_card(card, self.dpr)
        self.mode.card(self.card)
        self.stream = None

    def program(self, transition_id: str, mode_pass, settings: Mapping[str, Any]) -> None:
        schema = frame_schema(transition_id)
        if self.stream is None or self.stream.schema.schema_id != schema.schema_id:
            if self.stream is not None:
                self.mode.unbind()
                self.stream.close()
            self.stream = Stream(schema)
            self.mode.program([mode_pass], settings)
            self.mode.bind(self.stream.name, schema, expect=self.stream.expect)
        else:
            self.mode.program([mode_pass], settings)

    def pictures(self, images) -> None:
        for name, image in zip(TEXTURES.values(), images):
            self.mode.texture(name, image.tobytes(), image.size)

    def show(self, record: Mapping[str, Any]):
        self.stream.publish(record)
        self.mode.update()
        return self.read()

    def read(self):
        from dataclasses import asdict

        from composite_analysis import frame_rows

        rows = frame_rows(asdict(self.host.read()))
        left = int(round(MARGIN * self.dpr))
        width, height = target_pixels(self.dpr, self.size)
        return rows[left:left + height, left:left + width]

    def close(self, app) -> None:
        import host_check

        if self.stream is not None:
            self.stream.close()
        self.mode.composite.destroy()
        self.host.set_content(None)
        host_check._drop_item(app, self.root)


def python_frames(images, size: tuple[int, int], variants: Mapping[str, Mapping[str, Any]]) -> dict:
    """The Python renderer's frames (the production GL host) and its block values, per variant and progress."""
    import numpy as np

    from tools.transition_contact_sheet import TransitionCapture

    capture = TransitionCapture(size[0], size[1], *images)
    out: dict = {}
    try:
        for variant, overrides in variants.items():
            transition_id = "burn" if variant.startswith("burn") else variant
            run = runs(capture, transition_id, overrides)
            renderer = renderer_class(transition_id)()
            for progress in PROGRESS:
                frame = capture.frame(run, progress)
                values = renderer.block_values(frame)
                image, _ms = capture.render(run, progress)
                out[(variant, progress)] = (np.asarray(image, dtype=np.uint8).copy(), values)
    finally:
        capture.close()
    return out


# --------------------------------------------------------------------------------------------------- the rounds

def _refused(call) -> str:
    try:
        call()
    except (ValueError, KeyError) as exc:
        return str(exc)
    return ""


def round_shape(core, folder: Path) -> dict:
    from rendering.native.mode import ModePass, PassSampler
    from rendering.native.program_values import mode_fragment_pack

    checks: dict = {}
    facts: dict = {"transitions": {}}
    for transition_id in FULLSCREEN_TRANSITIONS:
        program = transition_pass(transition_id, folder / transition_id)
        (layout,) = core.mode_program_layout([program])["passes"]
        members = {row[0] for row in layout["block"]["members"]}
        unbound = _refused(lambda p=program: core.mode_program_layout([ModePass(p.name, p.pack, p.blend)]))
        facts["transitions"][transition_id] = {"uv": layout["uv"], "block": layout["block"]["name"],
                                               "samplers": layout["samplers"], "unbound": unbound}
        checks[f"{transition_id}_admitted_with_its_pictures"] = (
            layout["uv"] == "vUv" and {(s["name"], s["texture"]) for s in layout["samplers"]} == set(TEXTURES.items())
            and "u_resolution" not in members)
        checks[f"{transition_id}_refused_unbound"] = "unbound" in unbound
    bubble = mode_fragment_pack("bubble")
    import generic_mode_check

    declared = generic_mode_check.bubble_samplers()          # Bubble's own names and bindings (L7)
    bound = tuple(PassSampler(name, f"texture_{index}") for index, (name, _binding) in enumerate(declared))
    facts["bubble_unbound"] = _refused(lambda: core.mode_program_layout([ModePass("bubble", bubble)]))
    (bubble_layout,) = core.mode_program_layout([ModePass("bubble", bubble, samplers=bound)])["passes"]
    checks["bubble_refused_unbound"] = "unbound" in facts["bubble_unbound"]
    checks["bubble_admitted_with_its_samplers_bound"] = (
        len(declared) == 2 and {(s["name"], s["binding"]) for s in bubble_layout["samplers"]} == set(declared))
    crossfade = transition_pass("crossfade", folder / "crossfade")
    old, new = crossfade.samplers

    def layout(given, pack=crossfade.pack):
        return core.mode_program_layout([ModePass("crossfade", pack, "replace", samplers=tuple(given))])

    reasons = {
        "unknown": _refused(lambda: layout([old, new, PassSampler("uMissing", "old")])),
        "doubly_bound_by_name": _refused(lambda: layout([old, new, PassSampler("uOldTex", "new")])),
        "mip_filter_unknown": _refused(lambda: core.module.mode_program_layout(json.dumps({"passes": [{
            "name": "crossfade", "blend": "replace", "samplers": [
                {"name": "uOldTex", "texture": "old", "filter": "linear", "wrap": "clamp", "mips": "trilinear"},
                {"name": "uNewTex", "texture": "new", "filter": "linear", "wrap": "clamp", "mips": "none"}]}]}),
            [crossfade.pack])),
    }
    for kind in SAMPLER_VARIANTS:
        pack = bake(sampler_variant_text(kind), "crossfade.frag", folder / kind)
        reasons[kind] = _refused(lambda p=pack: layout([old, new], pack=p))
    words = {"unknown": "unknown", "doubly_bound_by_name": "doubly bound", "mip_filter_unknown": "mips",
             "binding17": "17", "block_binding": "own block", "shared_binding": "doubly bound"}
    for name, word in words.items():
        checks[f"refused_{name}"] = word in reasons[name]
    checks["control_both_bound_admitted"] = [s["binding"] for s in layout([old, new])["passes"][0]["samplers"]] == [0, 1]
    facts["reasons"] = reasons
    # The one rule over the harness's split: every member filled exactly once, the core's agreeing with Python's.
    import probe_rings

    card = probe_rings.harness_card(CARD, 1.0)
    target = target_pixels(1.0)
    images = photos(PHOTOS, target)
    from tools.transition_contact_sheet import TransitionCapture

    capture = TransitionCapture(target[0], target[1], *images)
    try:
        for variant, overrides in VARIANTS.items():
            transition_id = "burn" if variant.startswith("burn") else variant
            run = runs(capture, transition_id, overrides)
            values = renderer_class(transition_id)().block_values(capture.frame(run, 0.5))
            core_values, settings, record = split_values(transition_id, values)
            members = block_members(transition_id)
            filled = sorted([*core_values, *settings, *record])
            checks[f"{variant}_every_member_filled_once"] = filled == sorted(members)
            agreement = core_agreement(core_values, card, target)
            checks[f"{variant}_core_members_agree"] = bool(agreement) and all(agreement.values())
            facts.setdefault("split", {})[variant] = {"core": sorted(core_values), "settings": sorted(settings),
                                                      "record": sorted(record), "agreement": agreement}
            blocks, info = core.mode_blocks(frame_schema(transition_id),
                                            [transition_pass(transition_id, folder / f"blocks_{variant}")],
                                            settings, frame_schema(transition_id).encode(record), card, target)
            checks[f"{variant}_core_packs_the_split"] = len(blocks) == 1 and set(info["passes"][0]["sources"]) == set(
                members)
    finally:
        capture.close()
    return {"pass": all(checks.values()), "checks": checks, "facts": facts}


def round_draw(core, engine, app, host, api: str, folder: Path, out: Path, photo_paths) -> dict:
    import numpy as np

    checks: dict = {}
    facts: dict = {}
    frames: dict = {}
    vulkan = api == "vulkan"
    for dpr in DPRS:
        target = target_pixels(dpr)
        images = photos(photo_paths, target)
        references = {} if vulkan else python_frames(images, target, VARIANTS)
        host.set_device_pixel_ratio(dpr)
        scene = Scene(core, engine, host, dpr)
        label = f"dpr{dpr}"
        try:
            scene.pictures(images)
            parity: dict = {}
            for variant, overrides in VARIANTS.items():
                transition_id = "burn" if variant.startswith("burn") else variant
                mode_pass = transition_pass(transition_id, folder / f"{label}_{variant}")
                capture_values = _values(transition_id, overrides, images, target, references, variant)
                first = True
                for progress in PROGRESS:
                    _core, settings, record = split_values(transition_id, capture_values[progress])
                    if first:
                        scene.program(transition_id, mode_pass, settings)
                        first = False
                    else:
                        scene.mode.settings(settings)
                    pixels = scene.show(record)
                    frames[f"{label}_{variant}_{progress:.2f}"] = pixels
                    if not vulkan:
                        parity[f"{variant}_{progress:.2f}"] = compare(pixels, references[(variant, progress)][0])
                if variant == "burn" and not vulkan:
                    # Negative control: the native frame against the Python frame of the next progress differs.
                    shifted = compare(frames[f"{label}_{variant}_{PROGRESS[4]:.2f}"],
                                      references[(variant, PROGRESS[5])][0])
                    checks[f"{label}_control_another_progress_differs"] = not shifted["equal"]
            uploads_before = scene.mode.state().get("texture_uploads")
            # Determinism: the same frame twice (a new record of the same values) is hash-identical.
            transition_id = "burn"
            values = _values(transition_id, VARIANTS["burn_options"], images, target, references, "burn_options")
            _core, settings, record = split_values(transition_id, values[0.5])
            scene.program(transition_id, transition_pass(transition_id, folder / f"{label}_again"), settings)
            once, twice = scene.show(record), scene.show(record)
            checks[f"{label}_same_frame_hash_identical"] = digest(once) == digest(twice)
            checks[f"{label}_progress_changes_upload_no_texture"] = (
                scene.mode.state().get("texture_uploads") == uploads_before == 2)
            # Rule (g): a value change and a shader change show with no module build.
            turned = dict(settings, u_direction=(int(settings["u_direction"]) + 3) % 6)
            scene.mode.settings(turned)
            other_direction = scene.show(record)
            checks[f"{label}_value_change_shows"] = digest(other_direction) != digest(once)
            crossfade = _values("crossfade", {}, images, target, references, "crossfade")
            _core, settings, record = split_values("crossfade", crossfade[0.0])
            scene.program("crossfade", transition_pass("crossfade", folder / f"{label}_swapped",
                                                       text=swapped_crossfade_text()), settings)
            swapped = scene.show(record)
            # The core's uv bits, kept for the Vulkan comparison (rule (b)'s attribution).
            scene.mode.program([transition_pass("crossfade", folder / f"{label}_uv_bits", text=uv_bits_text())],
                               settings)
            frames[f"{label}_uv_bits"] = scene.show(record)
            new_photo = np.asarray(images[1], dtype=np.uint8)
            checks[f"{label}_shader_change_shows"] = compare(swapped, new_photo)["max_level"] <= 1
            frames[f"{label}_shader_change"] = swapped
            facts[label] = {"parity": parity, "state": {k: scene.mode.state().get(k) for k in (
                "accepted", "records", "draws", "texture_uploads", "textures_resident", "textures_lost",
                "last_reason", "refused_frames", "content_failures")}}
            if not vulkan:
                checks[f"{label}_opengl_equal_to_python"] = bool(parity) and all(p["equal"] for p in parity.values())
                facts[label]["parity_worst"] = max(parity.values(), key=lambda p: p.get("max_level", 0))
            # Endpoints are the photos themselves (the transition policy's exact endpoints).
            checks[f"{label}_endpoints_are_the_photos"] = (
                compare(frames[f"{label}_crossfade_0.00"], np.asarray(images[0], dtype=np.uint8))["equal"]
                and compare(frames[f"{label}_crossfade_1.00"], new_photo)["equal"])
        finally:
            scene.close(app)
            host.frames(2)
            _flush(app)
    host.set_device_pixel_ratio(1.0)
    np.savez_compressed(_work(out) / f"native_{api}.npz", **frames)
    _sheet(out, api, frames)
    live = core.composite_live()
    checks["nothing_left"] = _nothing_left(live)
    facts["live_at_end"] = live
    return {"pass": all(checks.values()), "checks": checks, "facts": facts}


_VALUES_CACHE: dict = {}


def _values(transition_id: str, overrides, images, target, references, variant) -> dict:
    """``FullscreenPassRenderer.block_values`` per progress for this variant (from the Python reference's own frames on
    OpenGL; on Vulkan from a run built the same way, with no GL draw)."""
    if references:
        return {progress: references[(variant, progress)][1] for progress in PROGRESS}
    key = (variant, tuple(target))
    if key not in _VALUES_CACHE:
        from rendering.quick.transitions.render_contract import QuickTransitionRenderFrame

        run = _run_without_gl(transition_id, overrides, images, target)
        renderer = renderer_class(transition_id)()
        w, h = target
        values = {}
        for progress in PROGRESS:
            sample = run.sample(run.start_ns + round(progress * (run.end_ns - run.start_ns)))
            # TransitionCapture.frame's frame; its GL names are stand-ins (block_values reads no GL object).
            frame = QuickTransitionRenderFrame(run, sample, (0, 0, w, h), (w, h),
                                               (2 / w, 0, 0, 0, 0, -2 / h, 0, 0, 0, 0, 1, 0, -1, 1, 0, 1), 1, 1, 2)
            values[progress] = renderer.block_values(frame)
        _VALUES_CACHE[key] = values
    return _VALUES_CACHE[key]


def _run_without_gl(transition_id: str, overrides, images, target):
    """The production run ``TransitionCapture`` builds, without its GL target (the Vulkan child)."""
    from rendering.quick.image_state import PresentationImage
    from rendering.quick.transitions.state import TransitionRequest, TransitionRun
    from tools.transition_contact_sheet import production_transition_spec

    spec = production_transition_spec(transition_id, DURATION_MS)
    w, h = target
    presented = [PresentationImage(str(index), "release_capture", (w, h), 1., (w, h), w * 4, image.tobytes())
                 for index, image in enumerate(images)]
    request = spec.build_request(runtime_generation=0, source_image=presented[0], destination_image=presented[1])
    run = TransitionRun.start(run_id=1, request=request, start_ns=0)
    if not overrides:
        return run
    r = run.request
    request = TransitionRequest(r.runtime_generation, r.transition_id, r.requested_name, r.selected_from_random,
                                r.duration_ms, r.direction, {**r.parameter_dict(), **overrides}, r.source_image,
                                r.destination_image)
    return TransitionRun.start(run_id=2, request=request, start_ns=0)


def round_textures(core, engine, app, host, folder: Path, photo_paths) -> dict:
    import numpy as np

    checks: dict = {}
    facts: dict = {}
    host.set_device_pixel_ratio(1.0)
    target = target_pixels(1.0)
    images = photos(photo_paths, target)
    crossfade = _values("crossfade", {}, images, target, {}, "crossfade")
    _core, settings, record = split_values("crossfade", crossfade[0.0])
    mode_pass = transition_pass("crossfade", folder / "textures")
    live = core.composite_live
    scene = Scene(core, engine, host, 1.0)
    try:
        scene.pictures(images)
        scene.program("crossfade", mode_pass, settings)
        old_photo = np.asarray(images[0], dtype=np.uint8)
        drawn = scene.show(record)
        state = scene.mode.state()
        counts = live()
        checks["uploaded_once_and_drawn"] = (state.get("texture_uploads") == 2 and compare(drawn, old_photo)["equal"]
                                             and counts["mode_textures"] == 2 and counts["mode_texture_images"] == 0)
        checks["texture_bytes_are_the_base_levels"] = counts["mode_texture_bytes"] == 2 * target[0] * target[1] * 4
        facts["after_first_draw"] = {"state": _texture_state(state), "live": counts}
        # Nothing at rest: rest frames record nothing, time nothing and upload nothing.
        host.set_gpu_timer(True)
        host.frames(4)
        host.gpu_samples()
        before = scene.mode.state()
        surface_before = scene.mode.composite.state()["surface"]["passes_recorded"]
        host.frames(REST_FRAMES)
        scene.mode.update()
        host.frames(REST_FRAMES)
        after = scene.mode.state()
        surface_after = scene.mode.composite.state()["surface"]["passes_recorded"]
        rest_samples = [s for s in host.gpu_samples() if s.kind == 2]
        host.set_gpu_timer(False)
        checks["nothing_at_rest"] = (after["records"] == before["records"] and surface_after == surface_before
                                     and not rest_samples and after["texture_uploads"] == before["texture_uploads"])
        facts["rest"] = {"records": [before["records"], after["records"]],
                         "surface_passes": [surface_before, surface_after], "gpu_surface_samples": len(rest_samples)}
        # A replaced image of the same size: the same object, one upload.
        scene.mode.texture("old", images[1].tobytes(), images[1].size)
        replaced = scene.show(record)
        state, counts = scene.mode.state(), live()
        checks["same_size_replaced_in_place"] = (state["texture_uploads"] == 3 and counts["mode_textures"] == 2
                                                 and compare(replaced, np.asarray(images[1], dtype=np.uint8))["equal"])
        # Another size, with mips: recreated, its levels counted; a mip sampler reads them.
        half = images[0].resize((target[0] // 2, target[1] // 2))
        scene.mode.texture("old", half.tobytes(), half.size, mips=True)
        mip_pass = transition_pass("crossfade", folder / "mips", old_mips="linear")
        scene.program("crossfade", mip_pass, settings)
        mipped = scene.show(record)
        state, counts = scene.mode.state(), live()
        expected = _levels_bytes(half.size) + target[0] * target[1] * 4
        checks["other_size_recreated_with_mips"] = (
            state["texture_uploads"] == 4 and counts["mode_textures"] == 2 and counts["mode_texture_bytes"] == expected
            and float(mipped[..., :3].astype(float).mean()) > 5.0)
        facts["mips"] = {"live": counts, "expected_bytes": expected}
        # Under a mip sampler, the texture without mips is refused and the drawn one kept; the mip program over a
        # texture without mips is refused too.
        refusals = {"texture_without_mips": _refused(lambda: scene.mode.texture("old", images[0].tobytes(),
                                                                                images[0].size))}
        kept = scene.show(record)
        scene.program("crossfade", mode_pass, settings)                      # back to the plain samplers
        scene.pictures(images)                                               # both without mips
        refusals["program_over_no_mips"] = _refused(lambda: scene.mode.program([mip_pass], settings))
        checks["mip_sampler_over_no_mips_refused"] = (all("mips" in r for r in refusals.values())
                                                      and compare(kept, mipped)["equal"])
        facts["refusals"] = refusals
        base = scene.show(record)
        # A removed texture goes at the next frame; the item waits for it.
        scene.mode.remove_texture("new")
        waiting = scene.show(record)
        state, counts = scene.mode.state(), live()
        checks["removed_texture_released_and_waited_for"] = (
            counts["mode_textures"] == 1 and "no texture 'new'" in str(state.get("last_reason"))
            and float(waiting[..., :3].astype(float).max()) == 0.0)
        facts["removed"] = {"live": counts, "last_reason": state.get("last_reason")}
        checks["unknown_texture_removal_refused"] = "new" in _refused(lambda: scene.mode.remove_texture("new"))
        scene.mode.texture("new", images[1].tobytes(), images[1].size)
        restored = scene.show(record)
        checks["sent_again_draws_again"] = compare(restored, base)["equal"]
        # A node made again (the item at no size, then back) has lost its textures: reported, nothing drawn, until sent.
        scene.mode.composite.set(rect=[0.0, 0.0, 0.0, 0.0])
        host.frames(2)
        scene.mode.composite.set(rect=[0.0, 0.0, float(CARD[0]), float(CARD[1])])
        lost_frame = scene.show(record)
        state, counts = scene.mode.state(), live()
        checks["node_made_again_reports_lost"] = (sorted(state.get("textures_lost") or []) == ["new", "old"]
                                                  and counts["mode_textures"] == 0
                                                  and float(lost_frame[..., :3].astype(float).max()) == 0.0)
        facts["lost"] = {"state": _texture_state(state), "live": counts}
        scene.pictures(images)
        again = scene.show(record)
        checks["lost_sent_again_draws"] = compare(again, base)["equal"] and not scene.mode.state().get("textures_lost")
    finally:
        scene.close(app)
        host.frames(2)
        _flush(app)
    counts = live()
    checks["destroyed_with_uploaded_textures_leaves_nothing"] = _nothing_left(counts)
    facts["after_destroy_uploaded"] = counts
    # An item destroyed with images it never uploaded (no frame drawn): the core's copies go with it.
    scene = Scene(core, engine, host, 1.0)
    try:
        scene.pictures(images)
        held = live()
        checks["images_held_until_uploaded"] = (held["mode_texture_images"] == 2
                                                and held["mode_texture_image_bytes"] == 2 * target[0] * target[1] * 4)
    finally:
        scene.close(app)
        host.frames(2)
        _flush(app)
    counts = live()
    checks["destroyed_with_pending_images_leaves_nothing"] = _nothing_left(counts)
    facts["after_destroy_pending"] = counts
    return {"pass": all(checks.values()), "checks": checks, "facts": facts}


def _levels_bytes(size: tuple[int, int]) -> int:
    w, h = size
    total = 0
    while True:
        total += w * h * 4
        if w == 1 and h == 1:
            return total
        w, h = max(1, w // 2), max(1, h // 2)


def _texture_state(state: dict) -> dict:
    return {k: state.get(k) for k in ("textures", "texture_uploads", "textures_resident", "textures_lost",
                                      "last_reason")}


def round_timing(core, engine, app, api: str, folder: Path, photo_paths) -> dict:
    """GPU time of the pass at TIMING_TARGET (the surface's record: the clear and the pass), median and p90."""
    width, height = TIMING_TARGET
    host = core.hidden_host(width + 2 * MARGIN, height + 2 * MARGIN)
    scene = None
    timing: dict = {}
    rest_facts: dict = {}
    checks: dict = {}
    try:
        scene = Scene(core, engine, host, 1.0, card=TIMING_TARGET)
        images = photos(photo_paths, TIMING_TARGET)
        scene.pictures(images)
        host.set_gpu_timer(True)
        for variant in ("crossfade", "burn_options"):
            transition_id = "burn" if variant.startswith("burn") else variant
            values = _values(transition_id, VARIANTS[variant], images, TIMING_TARGET, {}, variant)
            scene.program(transition_id, transition_pass(transition_id, folder / f"timing_{variant}"),
                          split_values(transition_id, values[0.5])[1])
            host.frames(4)
            host.gpu_samples()
            for index in range(TIMED_FRAMES):
                progress = PROGRESS[1 + index % (len(PROGRESS) - 2)]
                scene.stream.publish(split_values(transition_id, values[progress])[2])
                scene.mode.update()
                # A frame read back: the GPU finishes it before the next is recorded, so its latched result is never
                # skipped behind a queue the harness built (the readback lies outside the timed bracket).
                host.read()
            host.frames(4)
            samples = host.gpu_samples()
            times = sorted(s.nanoseconds for s in samples if s.kind == 2)
            state = scene.mode.state()
            timing[variant] = {"kinds": sorted({int(s.kind) for s in samples}), "records": state.get("records"),
                               "accepted": state.get("accepted"), "samples": len(times),
                               "median_ms": round(times[len(times) // 2] / 1e6, 4) if times else None,
                               "p90_ms": round(times[int(len(times) * 0.9)] / 1e6, 4) if times else None}
        # Nothing at rest: no record and no pass timed in a frame after the rest began (a late result of a timed frame
        # is read latched, so it can arrive during the rest; it carries its own, earlier, frame).
        host.frames(REST_FRAMES)
        records_before = scene.mode.state().get("records")
        passes_before = scene.mode.composite.state()["surface"]["passes_recorded"]
        rest_start = host.read().frame
        host.frames(REST_FRAMES)
        scene.mode.update()
        host.frames(REST_FRAMES)
        rest = [s for s in host.gpu_samples() if s.kind == 2 and s.frame > rest_start]
        records_after = scene.mode.state().get("records")
        passes_after = scene.mode.composite.state()["surface"]["passes_recorded"]
        host.set_gpu_timer(False)
        checks["gpu_time_recorded"] = all((entry["samples"] or 0) >= TIMED_FRAMES // 2 for entry in timing.values())
        checks["nothing_timed_at_rest"] = not rest and records_after == records_before and passes_after == passes_before
        rest_facts = {"records": [records_before, records_after], "surface_passes": [passes_before, passes_after],
                      "timed_after_rest_began": len(rest)}
    finally:
        if scene is not None:
            scene.close(app)
        host.frames(1)
        host.close()
        _flush(app)
    return {"pass": all(checks.values()), "checks": checks,
            "facts": {"gpu": timing, "rest": rest_facts, "target": list(TIMING_TARGET)}}


def _nothing_left(live: dict) -> bool:
    return all(not live.get(key) for key in ("items", "surfaces", "surface_resources", "mode_sources", "mode_resources",
                                             "mode_textures", "mode_texture_bytes", "mode_texture_images",
                                             "mode_texture_image_bytes"))


def _flush(app) -> None:
    import host_check

    host_check._flush_deletes(app)


def _work(out: Path) -> Path:
    path = out / "work"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _sheet(out: Path, api: str, frames: dict) -> None:
    import numpy as np
    from PIL import Image

    rows = []
    for variant in VARIANTS:
        tiles = [frames.get(f"dpr1.0_{variant}_{p:.2f}") for p in (0.2, 0.5, 0.8)]
        if all(t is not None for t in tiles):
            rows.append(np.concatenate([t[..., :3] for t in tiles], axis=1))
    if rows:
        Image.fromarray(np.concatenate(rows, axis=0), "RGB").save(out / f"fullscreen_pass_{api}.png")


def vulkan_against_opengl(out: Path) -> dict:
    import numpy as np

    work = _work(out)
    gl_path, vk_path = work / "native_opengl.npz", work / "native_vulkan.npz"
    if not gl_path.exists() or not vk_path.exists():
        return {"pass": False, "error": "a native frame set is missing"}
    gl, vk = np.load(gl_path), np.load(vk_path)
    compared = max_level = 0
    worst = None
    differing: dict = {}
    for key in gl.files:
        if key not in vk.files or gl[key].shape != vk[key].shape:
            return {"pass": False, "error": f"frame {key} is missing or differs in shape"}
        compared += 1
        difference = np.abs(gl[key][..., :3].astype(np.int16) - vk[key][..., :3]).max(axis=2)
        level = int(difference.max())
        if level:
            differing[key] = {"pixels": int(np.count_nonzero(difference)),
                              "above_tolerance": int(np.count_nonzero(difference > VULKAN_TOLERANCE)),
                              "max_level": level, "of": int(difference.size)}
        if level > max_level:
            max_level, worst = level, key
    uv_keys = [key for key in gl.files if key.endswith("_uv_bits")]
    return {"pass": compared > 0 and max_level <= VULKAN_TOLERANCE, "compared": compared, "max_level": max_level,
            "worst": worst, "tolerance": VULKAN_TOLERANCE, "differing": differing,
            "uv_bits_identical": bool(uv_keys) and not any(key in differing for key in uv_keys)}


# --------------------------------------------------------------------------------------------------- the child

def _host_size() -> tuple[int, int]:
    largest = max(DPRS)
    return (int(math.ceil((CARD[0] + 2 * MARGIN) * largest)), int(math.ceil((CARD[1] + 2 * MARGIN) * largest)))


def child(args) -> dict:
    import host_check
    import vk_validation

    root = host_check._root(args.repo)
    out = Path(args.out_dir)
    photo_paths = tuple(Path(p) for p in args.photos)
    record: dict = {"api": args.api, "rounds": list(args.rounds), "module_loaded": False, "instance_created": False,
                    "photos": [p.name for p in photo_paths]}
    if args.api == "opengl":
        from rendering.quick.bootstrap import configure_quick_graphics

        configure_quick_graphics(reason="fullscreen-pass-check")
        from PySide6.QtWidgets import QApplication

        app = QApplication([sys.argv[0]])
    else:
        from PySide6.QtQuick import QQuickWindow, QSGRendererInterface

        QQuickWindow.setGraphicsApi(QSGRendererInterface.GraphicsApi.Vulkan)
        from PySide6.QtGui import QGuiApplication

        app = QGuiApplication([sys.argv[0]])
    from PySide6.QtQml import QQmlEngine
    from rendering.native import NativeCoreUnavailable, load

    try:
        core = load((root / args.module_dir) if not Path(args.module_dir).is_absolute() else Path(args.module_dir))
    except NativeCoreUnavailable as exc:
        record["error"] = f"the module did not load: {exc.reason}"
        return record
    record["module_loaded"] = True
    record["runtime"] = dict(core.info)
    vulkan = args.api == "vulkan"
    if vulkan:
        instance = core.vulkan_instance(validation=True)
        record["instance"] = instance
        if not instance.get("ok"):
            record["error"] = f"the Vulkan instance failed: {instance.get('instance', {}).get('error')}"
            return record
        record["instance_created"] = True
    engine = QQmlEngine()
    host = None
    with tempfile.TemporaryDirectory(prefix="srpss_n4a_") as scratch:
        folder = Path(scratch)
        try:
            for name in args.rounds:
                if name == "shape" and vulkan:
                    continue                                       # GPU-free: the OpenGL child's
                if vulkan:
                    core.set_vulkan_phase(f"n4a {name}")
                try:
                    if name == "shape":
                        record[name] = round_shape(core, folder)
                    elif name == "timing":
                        if host is not None:          # one hidden host at a time while timing (its own, at 2560x1440)
                            record["host_close"] = host.close()
                            host = None
                            _flush(app)
                        record[name] = round_timing(core, engine, app, args.api, folder, photo_paths)
                    else:
                        if host is None:
                            host = core.hidden_host(*_host_size())
                        if name == "draw":
                            record[name] = round_draw(core, engine, app, host, args.api, folder, out, photo_paths)
                        else:
                            record[name] = round_textures(core, engine, app, host, folder, photo_paths)
                except Exception:
                    record[name] = {"pass": False, "error": traceback.format_exc()}
        finally:
            if host is not None:
                if vulkan:
                    core.set_vulkan_phase("n4a close")
                record["host_close"] = host.close()
            _flush(app)
            record["live_hosts_at_end"] = core.live_hosts()
            record["composites_at_end"] = core.composite_live()
            record["readers_at_end"] = core.packet_reader_live()
            if vulkan:
                teardown = core.destroy_vulkan_instance()
                messages = teardown.pop("messages", {}) if isinstance(teardown, dict) else {}
                summary = vk_validation.validation_summary(messages)
                record["instance_teardown"] = teardown
                record["validation"] = {"layer_loaded": bool(record["instance"].get("validation_layer_loaded")),
                                        "per_phase": messages.get("per_phase"),
                                        **{k: v for k, v in summary.items() if k != "groups"},
                                        "attribution": summary["groups"]}
            del engine
    if vulkan:
        record["rounds"] = [n for n in record["rounds"] if n != "shape"]
    return record


def api_verdict(api: str, record: dict, require_validation: bool) -> tuple[bool, list[str]]:
    import host_check

    ok, failed = host_check.api_verdict(api, record, require_validation)
    if record.get("module_loaded") and (api != "vulkan" or record.get("instance_created")):
        live = record.get("composites_at_end") or {}
        if not _nothing_left(live):
            failed.append(f"{api}: composites or textures left at the end ({live})")
        readers = record.get("readers_at_end") or {}
        if readers.get("readers") or readers.get("views"):
            failed.append(f"{api}: packet readers left at the end ({readers})")
    return not failed, failed


def main(argv: list[str] | None = None) -> int:
    import host_check
    import vk_validation

    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--module-dir", default="release/native_module")
    parser.add_argument("--repo", default=".", help="the repository root (default: the current directory)")
    parser.add_argument("--apis", nargs="+", default=list(APIS), choices=APIS)
    parser.add_argument("--rounds", nargs="+", default=list(ROUNDS), choices=ROUNDS)
    parser.add_argument("--photos", nargs=2, default=[str(p) for p in PHOTOS],
                        help="the two real photos (old, new); default two PERSONALSET wallpapers")
    parser.add_argument("--label", default="n4a_fullscreen_pass")
    parser.add_argument("--layer-path", type=Path, default=None,
                        help="the folder holding VkLayer_khronos_validation.json (VK_ADD_LAYER_PATH for this run only)")
    parser.add_argument("--require-validation", action="store_true",
                        help="a Vulkan run whose validation layer did not load is a FAIL, never a pass")
    parser.add_argument("--child", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--api", choices=APIS, help=argparse.SUPPRESS)
    parser.add_argument("--out-dir", help=argparse.SUPPRESS)
    parser.add_argument("--child-json", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    if args.child:
        try:
            record = child(args)
        except Exception:
            text = traceback.format_exc()
            record = {"api": args.api, "error": text.strip().splitlines()[-1], "traceback": text}
        args.child_json.write_text(json.dumps(record, indent=2, default=str), encoding="utf-8")
        return 0

    missing = [p for p in args.photos if not Path(p).is_file()]
    if missing:
        print(f"N4A VERDICT FAIL: the photos are missing ({', '.join(missing)}); pass two with --photos")
        return 0
    vk_validation.use_layer_path(args.layer_path, _ALLOWED_ENV)
    root = host_check._root(args.repo)
    from tools import artifact_paths

    out = artifact_paths.evidence_dir("native_core", "n4_a", args.label)
    out.mkdir(parents=True, exist_ok=True)
    environment = vk_validation.environment_record(_ALLOWED_ENV)
    results: dict = {}
    for api in [a for a in APIS if a in args.apis]:
        child_json = out / f"child_{api}.json"
        command = [sys.executable, str(Path(__file__).resolve()), "--child", "--api", api, "--repo", str(root),
                   "--module-dir", args.module_dir, "--out-dir", str(out), "--child-json", str(child_json),
                   "--rounds", *args.rounds, "--photos", *args.photos]
        started = time.monotonic()
        try:
            proc = subprocess.run(command, capture_output=True, text=True, timeout=CHILD_TIMEOUT_S, cwd=str(root))
            exit_code, stderr = proc.returncode, proc.stderr
        except subprocess.TimeoutExpired as exc:
            exit_code, stderr = "timeout", str(exc.stderr or "")
        record = json.loads(child_json.read_text(encoding="utf-8")) if child_json.exists() else {
            "api": api, "rounds": list(args.rounds), "error": f"the child process ended without a record ({exit_code})"}
        child_json.unlink(missing_ok=True)
        record["exit_code"] = exit_code
        record["seconds"] = round(time.monotonic() - started, 1)
        if exit_code != 0 or record.get("error"):
            record["stderr_tail"] = (stderr or "")[-4000:]
        results[api] = record

    verdicts = {api: api_verdict(api, record, args.require_validation) for api, record in results.items()}
    failed = [reason for _ok, reasons in verdicts.values() for reason in reasons]
    cross = None
    if "vulkan" in results and "opengl" in results and "draw" in args.rounds:
        cross = vulkan_against_opengl(out)
        if not cross.get("pass"):
            brief = {k: v for k, v in cross.items() if k != "differing"}    # the frames' figures are in summary.json
            brief["frames_differing"] = sorted(cross.get("differing", {}))
            failed.append(f"vulkan against opengl: {brief}")
    if not environment["clean"]:
        failed.append(f"environment: {', '.join(environment['contaminating_set'])} set")
    summary = {"apis": args.apis, "rounds": args.rounds, "photos": args.photos, "environment": environment,
               "require_validation": args.require_validation, "vulkan_against_opengl": cross,
               "verdicts": {api: {"pass": ok, "failed": reasons} for api, (ok, reasons) in verdicts.items()},
               "results": results, "pass": not failed}
    (out / "summary.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    for api, (ok, reasons) in verdicts.items():
        print(f"{api}: {'PASS' if ok else 'FAIL'}" + ("" if ok else " (" + "; ".join(reasons)[:2000] + ")"))
    if cross is not None:
        print(f"vulkan against opengl: { {k: v for k, v in cross.items() if k != 'differing'} }")
    print(f"evidence: {out / 'summary.json'} (the work folder holds the frames: delete it once judged)")
    print("N4A VERDICT " + ("PASS" if not failed else "FAIL: " + "; ".join(failed)[:4000]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
