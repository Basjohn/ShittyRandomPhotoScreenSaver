"""N5.4's proof of Waveform Ribbon (mode id ``waveform_ribbon``) on the native core as generic mode content: its
compute entries (the yielding floor, the world field, both fog volumes), the planar reflection with its box chain, the
scene with the floor's maps and pre-pass, the ribbon body through the transparency target, the light, strays and event
sparks added, the bloom and the oriented overlay composite (D12 to D17; Current_Plan.md N5.4), through
``rendering.native``, with the rounds of ``devcurve_check.py`` (the generic modes' harness) and Waveform's own pieces,
as ``oscilloscope_check.py`` does.

The OpenGL child captures every frame the production owner draws with the Python renderer through Waveform's widened
run set (``tools/conventions_identity.mode_runs("waveform_ribbon", offers=True)``: variants a and b and every Choice
offer, the four reaction modes among them; settings from the spec, never presets) on the shipped 5.5 s clip. Each frame
keeps its record (``waveform_native_schema.encode`` of the frame with the framed view of the card the Python renderer
drew: an offline driver's controller carries its own), the route's card, settings and sizes
(``native_route.waveform_settings_values``, ``waveform_sizes``), its program variant (``waveform_variant``), the
stages it draws (``waveform_stages``) and the
blocks the Python renderer packed. A sampled frame keeps its record, settings and sizes per drawn ratio, taken from the
Python reference's own draw of it (its framed view and scene pixels follow the ratio).

Rounds (``devcurve_check``'s):
  block   (OpenGL child) the module's block of every pass for each captured frame against the block the Python renderer
          packed for it (``implementations.waveform_ribbon.PYTHON_PACK_ORDER``), member by member at the Python
          packer's offsets (the body draw's Pulse Rim members aside: the Python body pack leaves them 0, the body
          shader reads none). Controls: the record's time nudged changes the ribbon's block; the card's fade nudged
          changes the composite's.
  item    (each API) the item's contract (one record per accepted frame, nothing at rest, the drop edge, a refused
          frame, unbind, no Python thread state on the render thread); rule (g) with a Settings change (the floor's
          viewport) and a record change (the ribbon's camera).
  pixels  (each API) the sampled frames at dpr 1 and 1.5: on OpenGL against the Python renderer under rule (a)'s
          composite tolerance; on Vulkan against the native OpenGL frames under ``VULKAN_RULE_B`` (rule (b)).
Waveform's own round (asked by name):
  cost    (each API) the surface's GPU time at 2560 x 1440 and 4K, median and p90 of 240 frames, ``nvidia-smi`` before
          and after.

Negative controls (``--control``, each in its own Vulkan child against a finished run's kept OpenGL frames; each must end
"FAILED AS EXPECTED"): ``mvp_nudged`` (record), ``bloom_dropped`` (record), ``skipped_release`` (item).

The owner's rule (a) (``owner_render_parity.py --native``) needs the route to draw the mode; until registration (playbook
checklist 18) ``owner`` runs it with the route's Waveform entries (``native_route.WAVEFORM_ROUTE``) registered for this
process only, every other argument passed through:
  python native/core/python/waveform_check.py owner --out <evidence> --module-dir release/native_module
      --recording <take> --seconds 60 --runs waveform_ribbon --placements display

Usage (repository venv, from the checkout holding the built module):
  python native/core/python/waveform_check.py --module-dir release/native_module --require-validation
      --layer-path D:\\Temp\\Scratch\\SRPSS\\native_spike\\validation_layers\\extracted [--label n54_waveform]
Evidence: .artifacts/evidence/native_core/n5_4_waveform/<date>_<label>/ (summary.json, summary_control_<name>.json,
sheets). Exit 0 whenever the harness ran; the verdict is the last printed line.
"""
from __future__ import annotations

import base64
import dataclasses
import importlib.util
import math
import struct
import subprocess  # noqa: F401  (the harness's children run through it; tests stub it here)
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

ROOT = HERE.parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import pixel_tolerance as pt  # noqa: E402


def _generic_rounds():
    """The generic modes' harness (``devcurve_check.py``) as a module of this harness's own."""
    spec = importlib.util.spec_from_file_location("_waveform_check_rounds", HERE / "devcurve_check.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


base = _generic_rounds()

MODE_ID = "waveform_ribbon"
#: Rule (b) (D12 "The pixel tolerance"): the product's 4x scene, Vulkan against OpenGL. Rule (a)'s statistical form
#: (``pixel_tolerance`` "Statistics"; ``owner_render_parity.RULE_A_STATISTICS``), at rule (a)'s provisional bound until
#: the long takes' measurement and the lead's decision set it: the two backends' 4x sample coverage differs along
#: every edge (the standard run, 176 frames: worst mean 0.049 levels, signed 0.022, 0.75 % of pixels 2-3 levels off,
#: 0.032 % past 3, max 16; class counts up to 19,438 ties a frame), which pixel counts cannot bound.
VULKAN_RULE_B = pt.Tolerance("waveform ribbon, Vulkan against OpenGL (rule b, statistical)", masked_level=1,
                             scatter_pixels=10 ** 9, tie_pixels=10 ** 9, flip_pixels=10 ** 9,
                             statistics=pt.FrameStatistics(0.16, 0.10, 0.030, 0.006))
#: Rule (b)'s known exceptions (lead, 22 Nov): rasterisation ties, not defects, and never a wider bound. Ragdoll take,
#: Frozen Past, inputs 1076 and 4823 (1.31 % and 1.22 % of pixels past 3 levels, max 19 and 10): every compute and
#: storage resource agrees; at 1076 one reflection texel (row 3, column 289) is covered by the mirrored ribbon light on
#: Vulkan only (31.75 against 0.06), a fill tie under the flipped rows, which the floor blurs. Evidence:
#: .artifacts/evidence/native_core/n5_4/20261122_b_fp_1076_raster (per pass), 20261122_b4_ragdoll_fp (the run). The plan's
#: one row-order convention re-baselines rule (b) native-only and removes the flipped rows behind them.
RULE_B_KNOWN_EXCEPTIONS = {("ragdoll_quiet_intro_loud_end1", "waveform_ribbon"): (1076, 4823)}
CONTROLS = {
    "mvp_nudged": {"rounds": ["pixels"], "breaks": "every record's ribbon camera matrix (its first element) x 1.05"},
    "bloom_dropped": {"rounds": ["pixels"], "breaks": "every record's bloom strength set to 0"},
    "skipped_release": {"rounds": ["item"], "breaks": "the content's release edge omitted (stream and item kept)"},
}
#: The Python reference's window margin (device pixels, divisible by 1.5): the SceneTarget's bloom reads past the item.
REFERENCE_MARGIN = 72
#: Frames a new program may take before its floor maps are resident (the texture upload, a job on Vulkan).
TEXTURE_WAIT_FRAMES = 240
#: The textures the floor reads (``waveform_plan.floor_images``).
FLOOR_TEXTURES = 3


def _schema():
    from core.visualizer_engine import waveform_native_schema

    return waveform_native_schema.SCHEMA


def _slot_bytes() -> int:
    from core.visualizer_engine.packet_abi import SLOT_OVERHEAD

    needed = _schema().layout.size + SLOT_OVERHEAD
    return max(4096, -(-needed // 4096) * 4096)


def _field(name: str):
    return _schema().layout.field(name)


#: The child's evidence folder and the records the references fill (``capture_runs``, ``python_references``).
_OUT: dict = {"dir": "."}
_CAPTURED: dict = {"records": None}


# --------------------------------------------------------------------------------------------------------- program

def program(variant: tuple) -> dict:
    """Waveform's program for ``variant`` as the route builds it (``native_route.waveform_program``)."""
    from rendering.quick.visualizer import native_route

    return native_route.waveform_program(tuple(variant))


def _passes():
    return program(_DEFAULT_VARIANT["variant"])["passes"]


def _defaults() -> tuple:
    """(the program variant, the floor's map paths) of the recipe's own Environment and Floor: a delivered input (the
    stream player's) carries neither, and production never changes them (the backdrop and floor are constants)."""
    from core.waveform_ribbon_scene import Environment, Floor

    floor = Floor()
    return ((tuple(float(c) for c in Environment().backdrop),),
            (str(floor.albedo), str(floor.roughness), str(floor.height)))


_DEFAULT_VARIANT: dict = {"variant": _defaults()[0]}


def _variant_key(entry: dict) -> tuple:
    return tuple(tuple(float(c) for c in part) for part in (entry.get("variant") or _defaults()[0]))


def _floor_key(entry: dict) -> tuple:
    return tuple(entry.get("floor") or _defaults()[1])


#: The program each scene item holds: id(mode) -> (variant, floor key, sizes sent).
_HELD: dict = {}


def _sizes_at(entry: dict, dpr: float) -> dict:
    return {name: tuple(size) for name, size in ((entry.get("sizes_at") or {}).get(str(float(dpr)), entry["sizes"])
                                                 .items())}


def program_item(mode, entry: dict, dpr: float, first: bool) -> None:
    """The route's order (``_ModeContent._program``): the meshes and floor maps once, the variant's program with the
    settings when the variant changes, then every size that changed (storage images and explicit targets); else the
    settings."""
    from rendering.quick.visualizer import native_route

    settings = base.settings_at(entry, dpr)
    variant = _variant_key(entry)
    held = _HELD.get(id(mode))
    if first or held is None or held[0] != variant:
        built = program(variant)
        if held is None or held[1] != _floor_key(entry):
            _key, send = native_route.waveform_resources(_FloorSnapshot(_floor_key(entry)))
            send(mode)
        unread = {"unread": built["unread"]} if built.get("unread") else {}
        mode.program(built["passes"], settings, targets=built["targets"], streams=built["streams"],
                     images=built["images"], **unread)
        images = {image.name for image in built["images"]}
        held = (variant, _floor_key(entry), {}, images)
    else:
        mode.settings(settings)
    sizes = _sizes_at(entry, dpr)
    for name, size in sizes.items():
        if held[2].get(name) != size:
            (mode.image_size if name in held[3] else mode.target_size)(name, size)
    _HELD[id(mode)] = (held[0], held[1], sizes, held[3])


class _FloorSnapshot:
    """The snapshot shape ``waveform_resources`` reads (the floor's three map paths)."""

    def __init__(self, paths) -> None:
        from types import SimpleNamespace

        albedo, roughness, height = paths
        floor = SimpleNamespace(albedo=albedo, roughness=roughness, height=height)
        self.logical = SimpleNamespace(mode_state=SimpleNamespace(scene=SimpleNamespace(floor=floor)))


class Scene(base.Scene):
    """The generic scene, which waits for the floor maps after a new program (their upload, a job on Vulkan) and
    publishes a sampled frame's record for the ratio it is drawn at."""

    def __init__(self, core, engine, host) -> None:
        super().__init__(core, engine, host)
        self.waiting = True

    def place(self, entry: dict, dpr: float, stream=None, margins=None) -> dict:
        at = (entry.get("records_at") or {}).get(str(float(dpr)))
        if at is not None:
            entry["record"] = base64.b64decode(at) if isinstance(at, str) else at
        held = _HELD.get(id(self.mode))
        if held is not None and held[0] != _variant_key(entry):
            self.waiting = True
        return super().place(entry, dpr, stream, margins)

    def read(self, card: dict):
        if self.waiting:
            for _ in range(TEXTURE_WAIT_FRAMES):
                state = self.mode.state()
                if (int(state.get("textures_resident") or 0) >= FLOOR_TEXTURES
                        and not (state.get("texture_jobs") or {}).get("pending")):
                    break
                self.mode.update()
                self.host.frames(1)
            self.mode.update()
            self.waiting = False
        return super().read(card)

    def close(self, app) -> None:
        _HELD.pop(id(self.mode), None)
        super().close(app)


def configure_from_settings(settings: dict) -> None:
    """Nothing to configure: the program is the recipe's backdrop's (``_defaults``)."""


def control_record(record: bytes) -> bytes:
    """The record controls: the ribbon's camera matrix scaled, or the bloom strength 0."""
    out = bytearray(record)
    if base.CONTROL == "mvp_nudged":
        offset = _field("ribbon_u_mvp").offset
        struct.pack_into("<d", out, offset, struct.unpack_from("<d", out, offset)[0] * 1.05)
    elif base.CONTROL == "bloom_dropped":
        struct.pack_into("<d", out, _field("u_bloom_strength").offset, 0.0)
    return bytes(out)


def item_settings_change(settings: dict) -> dict:
    """Rule (g)'s Settings change: the floor drawn at a quarter of its viewport (a card-decided member)."""
    width, height = (float(v) for v in settings["floor_u_viewport"])
    return dict(settings, floor_u_viewport=[width * 0.25, height * 0.25])


ITEM_RECORD_FIELD = "ribbon_u_mvp"


def item_reshaped(record: bytes) -> bytes:
    """Rule (g)'s record change: the ribbons' camera matrix scaled (its first element)."""
    out = bytearray(record)
    offset = _field(ITEM_RECORD_FIELD).offset
    struct.pack_into("<d", out, offset, struct.unpack_from("<d", out, offset)[0] * 1.25)
    return bytes(out)


# --------------------------------------------------------------------------------------------------------- capture

def mode_runs() -> list[tuple[str, dict]]:
    from tools import conventions_identity

    return conventions_identity.mode_runs(MODE_ID, True)


def _framed_frame(snapshot, framed_view):
    """``snapshot``'s logical frame with the framed view of the card the Python renderer drew."""
    state = dataclasses.replace(snapshot.logical.mode_state, framed_view=tuple(float(v) for v in framed_view))
    return dataclasses.replace(snapshot.logical, mode_state=state)


def _drawn(frame):
    """(framed view, scene pixels) of a Python render frame, as the renderer reads them; None when nothing is drawn."""
    from rendering.quick.scene3d.frame import item_pixel_rect, orient_visualizer_scene_frame
    from rendering.quick.visualizer.framed_view import framed_view_of_frame

    view = framed_view_of_frame(frame)
    if view is None:
        return None
    _x, _y, width, height = item_pixel_rect(orient_visualizer_scene_frame(frame))
    return tuple(float(v) for v in view), (int(width), int(height))


def capture_runs(sample_every: int) -> tuple[list[dict], list]:
    """Every frame the Python renderer draws through the run set: (records, the snapshots sampled for pixels). Each
    record: run key, frame index, the native record, the route's card, settings and sizes, the core card, the program
    variant, the floor's map paths and the Python blocks by pass (``PYTHON_PACK_ORDER``)."""
    from core.visualizer_engine import waveform_native_schema
    from rendering.gl_programs import scene3d
    from rendering.native.composite import composite_geometry
    from rendering.native.spectrum import spectrum_presentation
    from rendering.quick.visualizer.implementations import waveform_ribbon as python_waveform
    from rendering.quick.visualizer.native_route import (waveform_settings_values, waveform_sizes, waveform_stages,
                                                         waveform_variant)
    import tools.expanded_visualizer_evidence as evidence
    from tools.visualizer_replay import owner_render_parity as parity
    from tools.visualizer_replay import owner_worker_gate as gate
    from widgets.spotify_visualizer import engine_worker_link

    clip = evidence.shipped_clip(5.5)
    records: list[dict] = []
    samples: list = []
    renderer = python_waveform.QuickWaveformRibbonRenderer
    original = renderer.render
    pack = scene3d.Scene3DBlockLayout.pack
    current: dict = {"key": "", "index": 0}
    packed: list = []

    def recording(self, values):
        block = pack(self, values)
        packed.append((self.name, bytes(block)))
        return block

    def capturing(self, frame):
        packed.clear()
        original(self, frame)
        snapshot = frame.snapshot
        presentation = snapshot.presentation
        state = snapshot.logical.mode_state
        drawn = _drawn(frame) if presentation.content_fade > 0.0 and getattr(state, "ready", False) else None
        if drawn is None:
            return
        view, size = drawn
        dpr = float(presentation.dpr)
        pixels = (int(frame.viewport[2]), int(frame.viewport[3]))
        card = spectrum_presentation(presentation, composite_geometry(presentation),
                                     window_size=(pixels[0] / dpr, pixels[1] / dpr), window_pixels=pixels)
        recipe = state.scene
        python = [block for block in packed if not block[0].startswith("Scene")]
        if not python:
            return                      # a preparing frame: the renderer drew nothing yet
        entry = {"key": current["key"], "index": current["index"], "card": card,
                 "shown": base._shown(card, presentation), "settings": waveform_settings_values(snapshot, size),
                 "sizes": {name: list(v) for name, v in waveform_sizes(snapshot, size).items()},
                 "variant": [list(part) for part in waveform_variant(snapshot)],
                 "stages": list(waveform_stages(snapshot, size)),
                 "floor": [str(recipe.floor.albedo), str(recipe.floor.roughness), str(recipe.floor.height)],
                 "record": waveform_native_schema.encode(_framed_frame(snapshot, view)),
                 "python_packs": python, "scene_pixels": list(size)}
        if current["index"] % sample_every == 0:
            samples.append((len(records), snapshot, tuple(frame.logical_size), frame.content_rotation_quarters))
            entry["cost_at"] = {}
            width, height = (float(v) for v in card["item_size"])
            for scale, count in COST_PIXELS.items():
                ratio = min(COST_MAX_HOST_DPR, (count / (width * height)) ** 0.5)
                scene = (int(round(width * ratio)), int(round(height * ratio)))
                entry["cost_at"][scale] = {"dpr": ratio, "scene_pixels": list(scene),
                                           "settings": waveform_settings_values(snapshot, scene),
                                           "sizes": {name: list(v) for name, v in
                                                     waveform_sizes(snapshot, scene).items()}}
        records.append(entry)
        current["index"] += 1

    renderer.render = capturing
    scene3d.Scene3DBlockLayout.pack = recording
    try:
        for suffix, settings in mode_runs():
            current["key"], current["index"] = f"{MODE_ID}{suffix}", 0
            engine_worker_link.reset_run_state_for_testing()
            script = parity.parity_script(clip.frames, MODE_ID)
            mirror = parity.SceneMirror()
            try:
                with parity.single_sample_scene_targets():
                    gate.identity_run(MODE_ID, script, worker=False, supervisor=None, namespace=None,
                                      settings=settings, scene_mirror=mirror)
            finally:
                mirror.close()
    finally:
        renderer.render = original
        scene3d.Scene3DBlockLayout.pack = pack
    _CAPTURED["records"] = records
    return records, samples


def python_references(samples, dpr: float) -> list:
    """The Python renderer's own draw of each sampled frame at ``dpr`` (``devcurve_check.python_references``), and the
    record, settings and sizes of that draw (its framed view and scene pixels follow the ratio) kept on the sample's
    record (``records_at``, ``settings_at``, ``sizes_at``)."""
    from core.visualizer_engine import waveform_native_schema
    from rendering.quick.visualizer.implementations import waveform_ribbon as python_waveform
    from rendering.quick.visualizer.native_route import waveform_settings_values, waveform_sizes

    records = _CAPTURED["records"]
    renderer = python_waveform.QuickWaveformRibbonRenderer
    original = renderer.render
    seen: list = []

    def capturing(self, frame):
        seen.append((frame.snapshot, _drawn(frame)))
        original(self, frame)

    renderer.render = capturing
    try:
        references = _base_references(samples, dpr)
    finally:
        renderer.render = original
    if len(seen) != len(samples):
        raise RuntimeError(f"the references drew {len(seen)} frames for {len(samples)} samples")
    key = str(float(dpr))
    for (index, _snapshot, _size, _quarters), (snapshot, drawn) in zip(samples, seen):
        if drawn is None:
            continue
        view, size = drawn
        entry = records[index]
        record = waveform_native_schema.encode(_framed_frame(snapshot, view))
        entry.setdefault("records_at", {})[key] = base64.b64encode(record).decode("ascii")
        entry.setdefault("settings_at", {})[key] = waveform_settings_values(snapshot, size)
        entry.setdefault("sizes_at", {})[key] = {name: list(v) for name, v in waveform_sizes(snapshot, size).items()}
    return references


_base_references = base.python_references


# --------------------------------------------------------------------------------------------------------- block

def _members(layout) -> dict:
    from rendering.gl_programs.scene3d import _std140_type

    sizes = {"float": 4, "int": 4, "uint": 4, "bool": 4, "vec2": 8, "vec3": 12, "vec4": 16, "mat4": 64}
    members = {}
    for (name, glsl_type), offset in zip(layout.fields, layout.offsets):
        _element, count, _alignment, stride = _std140_type(glsl_type)
        members[name] = (offset, count * stride if "[" in glsl_type else sizes[glsl_type])
    return members


#: The native passes by their Python pack's name (``PYTHON_PACK_ORDER``): the ribbon's light pass packs as ``ribbon``.
_PACK_NAMES = {"ribbon_light": "ribbon"}
#: Members a native pass's block holds that its Python pack leaves 0 (read by none of the pass's shaders).
_UNREAD_IN_PYTHON = {"ribbon_body": ("uPulseRim", "uPulseRimShape")}


def round_block(core, records: list[dict]) -> dict:
    import json

    from rendering.native.mode import _card, _settings, program_json, schema_table_entry
    from core.visualizer_engine.waveform_native_names import CORE_MEMBERS, member_name
    from rendering.quick.visualizer.implementations.waveform_ribbon import named_packs, pass_layout

    schema = _schema()
    table = json.dumps(dict(schema_table_entry(schema)))
    built_by_variant: dict = {}
    now = _field("ribbon_u_mvp").offset

    def blocks(built, settings, record, shown, target):
        declared, packs = built["declared"]
        found, facts = core.module.mode_blocks(table, declared, packs, _settings(settings), bytes(record),
                                               _card(shown), (int(target[0]), int(target[1])))
        return [bytes(block) for block in found], json.loads(facts)

    mismatched: dict[str, int] = {}
    first_mismatch = None
    layout_differs: dict = {}
    compared = refused = unnamed = 0
    passes_compared: dict[str, int] = {}
    mutated_differs = fade_differs = 0
    for entry in records:
        variant = _variant_key(entry)
        built = built_by_variant.get(variant)
        if built is None:
            program_ = program(variant)
            built = dict(program_, declared=program_json(program_["passes"], program_["targets"], program_["streams"],
                                                         images=program_["images"], unread=program_["unread"]))
            built["index"] = {p.name: i for i, p in enumerate(program_["passes"])}
            built_by_variant[variant] = built
        python = named_packs(entry["python_packs"], entry["stages"])
        if python is None:
            unnamed += 1
            first_mismatch = first_mismatch or {"key": entry["key"], "index": entry["index"],
                                                "python_packs": [p[0] for p in entry["python_packs"]]}
            continue
        target = tuple(int(v) for v in entry["card"]["target_size"])
        try:
            found, facts = blocks(built, entry["settings"], entry["record"], entry["shown"], target)
        except ValueError as exc:
            refused += 1
            first_mismatch = first_mismatch or {"key": entry["key"], "index": entry["index"], "refused": str(exc)}
            continue
        compared += 1
        differing = []
        for native_name, index in built["index"].items():
            name = _PACK_NAMES.get(native_name, native_name)
            if name not in python:
                continue
            layout = pass_layout(name)
            members = _members(layout)
            if not layout_differs.get(native_name + ".checked"):
                rows = {row[0]: row for row in facts["program"]["passes"][index]["block"]["members"]}
                for member, (offset, _size) in members.items():
                    # The module's block names each member as its pass file does (the core's field-name form).
                    module = (rows.get(member_name(_pass_id(native_name), member)) or [None] * 3)[2]
                    if module != offset:
                        layout_differs[f"{native_name}.{member}"] = {"python": offset, "module": module}
                layout_differs[native_name + ".checked"] = True
            passes_compared[native_name] = passes_compared.get(native_name, 0) + 1
            block, expected = found[index], python[name]
            for member, (offset, size) in members.items():
                if member in _UNREAD_IN_PYTHON.get(native_name, ()) or member in CORE_MEMBERS:
                    continue              # a core member (u_target_px) is the core's own: Python leaves it 0
                if block[offset:offset + size] != expected[offset:offset + size]:
                    differing.append(f"{native_name}.{member}")
        for name in differing:
            mismatched[name] = mismatched.get(name, 0) + 1
        if differing and first_mismatch is None:
            first_mismatch = {"key": entry["key"], "index": entry["index"], "members": differing[:12]}
        mutated = bytearray(entry["record"])
        struct.pack_into("<d", mutated, now, struct.unpack_from("<d", mutated, now)[0] + 0.25)
        ribbon = built["index"]["ribbon_light"]
        mutated_differs += int(blocks(built, entry["settings"], bytes(mutated), entry["shown"], target)[0][ribbon]
                               != found[ribbon])
        show = built["index"]["waveform_show"]
        faded = dict(entry["shown"], content_fade=float(entry["shown"]["content_fade"]) * 0.5 + 0.25)
        fade_differs += int(blocks(built, entry["settings"], entry["record"], faded, target)[0][show] != found[show])
    layout_differs = {k: v for k, v in layout_differs.items() if not k.endswith(".checked")}
    runs = sorted({entry["key"] for entry in records})
    checks = {
        "every_run_drew": len(runs) == len(mode_runs()),
        "frames_compared": compared > 0 and compared == len(records),
        "every_pass_compared": {"floor", "ribbon_light", "ribbon_body", "ribbon_mirror"} <= set(passes_compared),
        "module_layout_is_the_python_layout": not layout_differs,
        "identical": not mismatched and not refused and not unnamed,
        "control_mutated_record_differs": mutated_differs == compared,
        "control_fade_differs": fade_differs == compared,
    }
    return {"pass": all(checks.values()), "checks": checks, "runs": runs, "frames": len(records),
            "compared": compared, "refused": refused, "unnamed": unnamed, "passes_compared": passes_compared,
            "variants": [list(v) for v in built_by_variant], "mismatched_members": mismatched,
            "first_mismatch": first_mismatch, "layout_differs": layout_differs,
            "controls": {"mutated_record_differs": mutated_differs, "fade_differs": fade_differs}}


def _pass_id(native_name: str) -> str:
    """The pass id whose members a native pass's block holds (``waveform_shader_files.PASS_FILES``)."""
    return {"ribbon_body": "ribbon", "ribbon_light": "ribbon"}.get(native_name, native_name)


# --------------------------------------------------------------------------------------------------------- cost

#: The cost round (layer C): the surface's GPU time (the timer's kind 2: every pass of the content), median and p90 of
#: at least COST_SAMPLES frames, the least-loaded of COST_ROUNDS rounds, at a 2560 x 1440 frame's and a 4K frame's
#: pixel count (the card drawn at the ratio that gives it).
COST_PIXELS = {"1440p": 2560 * 1440, "4k": 3840 * 2160}
COST_MAX_HOST_DPR = 8.0
COST_ROUNDS = 3
COST_SAMPLES = 240
COST_MAX_FRAMES = 1200


def _native_cost(core, engine, app, host, entry: dict, dpr: float) -> dict:
    import bubble_check

    scene = None
    stream = base.Stream()
    try:
        scene = Scene(core, engine, host)
        card = scene.place(entry, dpr, stream)
        record = entry["record"]
        stream.publish(record, 0.0)
        scene.mode.update()
        scene.read(card)
        host.set_gpu_timer(True)
        for step in range(4):
            stream.publish(record, float(step + 1))
            scene.mode.update()
            host.frames(1)
        host.gpu_samples()
        times: list[int] = []
        frames = 0
        while frames < COST_MAX_FRAMES and len(times) < COST_SAMPLES:
            stream.publish(record, float(frames + 5))
            scene.mode.update()
            host.frames(1)
            frames += 1
            times.extend(s.nanoseconds for s in host.gpu_samples() if s.kind == 2)
        host.frames(4)
        times.extend(s.nanoseconds for s in host.gpu_samples() if s.kind == 2)
        host.frames(8)
        rest = [s for s in host.gpu_samples() if s.kind == 2]
        host.set_gpu_timer(False)
        result = bubble_check._summary(times)
        state = scene.mode.state()
        result.update(records=frames, timed_at_rest=len(rest), error=state.get("error") or state.get("failure"))
        return result
    finally:
        stream.close()
        if scene is not None:
            scene.close(app)
        host.frames(2)
        base.host_check._flush_deletes(app)


def round_cost(core, engine, app, api: str, records: list, out: Path) -> dict:
    """The whole surface's GPU time at 2560 x 1440 and 4K on this API (every stage on: the default run's first sampled
    frame at or after frame 160 that draws the fog, the strays, the sparks and the yielding floor), at the
    sizes and settings of the scene at that ratio; ``nvidia-smi`` before and after."""
    import bubble_check

    chosen = [e for e in records if e is not None and e.get("cost_at") and all(e["stages"][:4])]
    entry = next((e for e in chosen if e["key"] == MODE_ID and e["index"] >= 160), chosen[0] if chosen else None)
    if entry is None:
        return {"pass": False, "error": "no sampled frame draws every stage"}
    width, height = (float(v) for v in entry["card"]["item_size"])
    facts: dict = {"gpu_before": bubble_check._gpu_state(), "frame": {"key": entry["key"], "index": entry["index"]}}
    timed: list[dict] = []
    for scale in COST_PIXELS:
        at = entry["cost_at"][scale]
        dpr, scene_pixels = float(at["dpr"]), tuple(at["scene_pixels"])
        moved = dict(entry, settings=at["settings"], sizes=at["sizes"], settings_at={}, sizes_at={}, records_at={})
        host = core.hidden_host(int(math.ceil((width + 2 * base.MARGIN) * dpr)),
                                int(math.ceil((height + 2 * base.MARGIN) * dpr)))
        try:
            host.set_device_pixel_ratio(dpr)
            results = [_native_cost(core, engine, app, host, moved, dpr) for _round in range(COST_ROUNDS)]
        finally:
            host.close()
            base.host_check._flush_deletes(app)
        best = dict(min(results, key=lambda r: float("inf") if r["median_ms"] is None else r["median_ms"]),
                    round_medians=[r["median_ms"] for r in results])
        timed.append(best)
        facts[scale] = {"dpr": round(dpr, 6), "scene_pixels": list(scene_pixels), "surface": best}
    facts["gpu_after"] = bubble_check._gpu_state()
    checks = {"timed": all(r["samples"] >= COST_SAMPLES for r in timed),
              "nothing_timed_at_rest": all(r["timed_at_rest"] == 0 for r in timed),
              "no_error": not any(r.get("error") for r in timed)}
    return {"pass": all(checks.values()), "checks": checks, "facts": facts}


#: The readback round's frames: up to this many sampled frames drawing every stage, spread over the run.
READBACK_FRAMES = 3
READBACK_WAIT_FRAMES = 16


def _readback(scene, card: dict) -> tuple[dict, dict]:
    """One drawn frame's scene targets (``read_targets``: the reflection, the scene, the glow; rows top first on every
    backend) and storage (``read_storage``: the fog volumes and steady shares slice by slice, the floor's fields), each
    name -> (format, size, level, bytes)."""
    scene.mode.read_targets()
    scene.read(card)
    targets = None
    for _ in range(READBACK_WAIT_FRAMES):
        targets = scene.mode.target_pixels()
        if targets is not None:
            break
        scene.host.frames(1)
    scene.mode.read_storage()
    storage = None
    for _ in range(READBACK_WAIT_FRAMES):
        scene.host.frames(1)
        storage = scene.mode.storage_data()
        if storage is not None:
            break
    if targets is None or storage is None:
        raise RuntimeError(f"the readback did not complete (targets {targets is not None}, storage "
                           f"{storage is not None}; {scene.mode.state().get('last_reason')})")
    return ({(t["name"] if "@" in t["name"] else f"{t['name']}@{t.get('level', 0)}"): (t["format"], tuple(t["size"]), int(t.get("level", 0)),
                                                  bytes(t["data"])) for t in targets},
            {s["name"]: (s["format"], tuple(s["size"]), 0, bytes(s["data"])) for s in storage if s["kind"] == "image"})


_READ_DTYPES = {"rgba32f": "<f4", "r32f": "<f4", "rgba16f": "<f2", "r16f": "<f2", "rgba8": "<u1", "r8": "<u1"}


def _decoded(entry: tuple):
    """A readback's values as float64, shaped (slices, rows, columns, channels) (one slice for a 2D resource)."""
    import numpy as np

    fmt, size, _level, data = entry
    dtype = _READ_DTYPES.get(str(fmt).lower())
    if dtype is None:
        return None
    values = np.frombuffer(data, dtype).astype(np.float64)
    width, height = int(size[0]), int(size[1])
    depth = int(size[2]) if len(size) > 2 else 1
    channels = values.size // max(1, width * height * depth)
    return values[:width * height * depth * channels].reshape(depth, height, width, channels)


def compare_readback(a: dict, b: dict) -> dict:
    """Each resource of ``a`` (one backend's readback) against ``b`` (the other's): the same names, formats and sizes,
    the largest and mean absolute difference, and the same difference with ``b``'s rows (and, for a volume, slices)
    reversed: a backend whose rows or slices ran the other way would differ less reversed (E13/E15's trap)."""
    import numpy as np

    out: dict = {}
    for name in sorted(set(a) | set(b)):
        if name not in a or name not in b:
            out[name] = {"pass": False, "missing_on": "opengl" if name not in a else "vulkan"}
            continue
        if a[name][:2] != b[name][:2]:
            out[name] = {"pass": False, "formats_sizes": [list(map(str, a[name][:2])), list(map(str, b[name][:2]))]}
            continue
        x, y = _decoded(a[name]), _decoded(b[name])
        if x is None:
            out[name] = {"pass": a[name][3] == b[name][3], "exact": a[name][3] == b[name][3], "format": a[name][0]}
            continue
        delta = np.abs(x - y)
        # A resource one row (or one slice) deep cannot show that axis's orientation: only the axes it has are judged.
        row_flip = float(np.abs(x - y[:, ::-1]).mean()) if x.shape[1] > 1 else None
        slice_flip = float(np.abs(x - y[::-1]).mean()) if x.shape[0] > 1 else None
        mean = float(delta.mean())
        spread = float(np.abs(x - x.mean()).mean())          # content that does not vary cannot show an orientation
        oriented = all(flip is None or mean < flip or spread == 0.0 for flip in (row_flip, slice_flip))
        out[name] = {"format": a[name][0], "size": list(a[name][1]), "exact": a[name][3] == b[name][3],
                     "max_abs": float(delta.max()), "mean_abs": mean, "row_reversed_mean_abs": row_flip,
                     "slice_reversed_mean_abs": slice_flip, "content_spread": spread, "pass": bool(oriented)}
    return {"pass": bool(out) and all(r["pass"] for r in out.values()), "resources": out}


def round_readback(core, engine, app, api: str, records: list, out: Path) -> dict:
    """E13 and E15's readback (playbook "Proof"): for sampled frames drawing every stage, at dpr 1, the scene targets
    (the planar reflection among them) and every storage image (the fog volumes slice by slice) read back on this API;
    on Vulkan each is judged against the OpenGL child's, name by name (``compare_readback``)."""
    import pickle

    chosen = [e for e in records if e is not None and e.get("cost_at") and all(e["stages"][:4])]
    if not chosen:
        return {"pass": False, "error": "no sampled frame draws every stage"}
    step = max(1, len(chosen) // READBACK_FRAMES)
    chosen = chosen[::step][:READBACK_FRAMES]
    work = out / "work"
    work.mkdir(parents=True, exist_ok=True)
    got: dict = {}
    host = core.hidden_host(*base.HOST_PIXELS)
    try:
        for entry in chosen:
            scene = None
            stream = base.Stream()
            try:
                scene = Scene(core, engine, host)
                card = scene.place(entry, 1.0, stream)
                stream.publish(entry["record"], 0.0)
                scene.mode.update()
                scene.read(card)
                stream.publish(entry["record"], 1.0)
                scene.mode.update()
                got[f"{entry['key']}#{entry['index']}"] = _readback(scene, card)
            finally:
                stream.close()
                if scene is not None:
                    scene.close(app)
                host.frames(2)
                base.host_check._flush_deletes(app)
    finally:
        host.close()
        base.host_check._flush_deletes(app)
    with open(work / f"readback_{api}.pkl", "wb") as handle:
        pickle.dump(got, handle)
    listed = {frame: {"targets": sorted(t), "storage": sorted(s)} for frame, (t, s) in got.items()}
    if api == "opengl":
        return {"pass": all(t and s for t, s in got.values()), "frames": listed}
    reference = work / "readback_opengl.pkl"
    if not reference.is_file():
        return {"pass": False, "error": "no OpenGL readback to judge against", "frames": listed}
    with open(reference, "rb") as handle:
        opengl = pickle.load(handle)
    judged = {}
    for frame, (targets, storage) in got.items():
        if frame not in opengl:
            judged[frame] = {"pass": False, "error": "frame missing on OpenGL"}
            continue
        judged[frame] = {"targets": compare_readback(opengl[frame][0], targets),
                         "storage": compare_readback(opengl[frame][1], storage)}
        judged[frame]["pass"] = judged[frame]["targets"]["pass"] and judged[frame]["storage"]["pass"]
    return {"pass": bool(judged) and all(j["pass"] for j in judged.values()), "frames": judged}


# --------------------------------------------------------------------------------------------------------- the child

_child = base.child
_save = base._save


def _saved(out: Path, records: list[dict], references: dict) -> None:
    """``devcurve_check._save`` without the Python packs (the block round's only)."""
    _save(out, [dict(entry, python_packs=None) for entry in records], references)


def child(args) -> dict:
    _OUT["dir"] = args.out_dir
    base.use_mode(SLOT_BYTES=_slot_bytes())
    return _child(args)


base.use_mode(MODE_ID=MODE_ID, _schema=_schema, _passes=_passes, Scene=Scene,
              capture_runs=capture_runs, python_references=python_references, round_block=round_block,
              program_item=program_item, control_record=control_record, item_settings_change=item_settings_change,
              ITEM_RECORD_FIELD=ITEM_RECORD_FIELD, item_reshaped=item_reshaped, VULKAN_RULE_B=VULKAN_RULE_B,
              SCRIPT=Path(__file__).resolve(), EVIDENCE_TOPIC="n5_4_waveform", DEFAULT_LABEL="n54_waveform",
              CONTROLS=CONTROLS, child=child, _save=_saved,
              EXTRA_ROUNDS={"cost": round_cost, "readback": round_readback}, REFERENCE_MARGIN=REFERENCE_MARGIN)
vulkan_against_opengl = base.vulkan_against_opengl
api_verdict = base.api_verdict


def owner(argv: list[str]) -> int:
    """``owner_render_parity.py`` with the route drawing Waveform; every argument passed through (``--native --mode
    waveform_ribbon`` added)."""
    from tools.visualizer_replay import owner_render_parity as parity

    return parity.main(["--native", "--mode", MODE_ID, *argv])


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv[:1] == ["owner"]:
        return owner(argv[1:])
    return base.main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
