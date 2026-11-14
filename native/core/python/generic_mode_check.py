"""N2.9's proof of generic mode content (Current_Plan.md item 8b; ``native/core/src/mode_content.h``), through
``rendering.native``, on the harness-only mode Probe Rings (``native/core/python/probe_rings``: a Python simulation, two
fragment shaders in the product 2D shaders' shape and a spec; never registered, never in Settings, no preset).

The module (``release/native_module``, built on GitHub) is loaded the product's way, in one child process per graphics
API: OpenGL first, then Vulkan on the module's own instance and devices (D6). No window is ever visible: the item draws
into the module's hidden host.

Rounds:
  blocks  (OpenGL child; GPU-free) what the core uploads, against an independent Python packer: for frames of the
          simulation, each pass's block bytes from ``mode_blocks`` equal its members packed at their reflected offsets
          and strides (float32, int32) from the three sources (the core's conventions from the card and the target, the
          settings, the record), member by member. The core's conventions table equals the face's. Refusals, each with
          its reason: a record field no pass declares and a setting no pass declares (unknown); a member no source fills
          (unfilled, from the record and from the settings); a setting naming a core member or a record field (two
          owners); the tinted shader with the base spec's settings and the reverse; a u32 into an int with no range
          rule (L7); the runtime schema refused for a wrong fingerprint, overlapping fields, a compiled schema's id, a
          compiled mode at another version (L6) and a mode id that disagrees with the compiled table; a pass declaring a
          sampler, one with its block at binding 17 (M3), one with two blocks of its own; a pack count unlike the
          passes'. The product's own packs (M5): Oscilloscope and Spline Curve admitted as they are; Bubble refused for
          its samplers, and admitted once a copy of its source drops them (control).
  reader  (OpenGL child; GPU-free) the core's reader admits the mode's stream by the schema handed over: frames
          accepted, their fields decoded by the C++ table equal to the schema's own decode. Controls: the reader opened
          without the schema refuses the first slot (an unknown mode code); a record whose ring_count breaks its rule is
          refused after the copy.
  draw    (each API) the item in the hidden host: the drawn rings at the radii the record holds (the centre row's rings,
          within 1.5 px) at dpr 1 and 1.5 (fragPixel at a fractional ratio, L11); the glow pass (v_uv) adds light at
          the centre; a card change shows (the core's u_fade); nothing recorded at rest; no Python thread state on the
          render thread. A change shows with no module rebuild: a shader change (rings drawn green), a spec value
          (thickness 2 against 8), a shader and spec change together (a new member and the control that fills it), a
          simulation change (twice the speed). A refused frame (a NaN in the record) keeps the last drawn frame, counted
          once, and the next good frame draws (M4). An item with no program fails once and is not rebuilt per frame; a
          program re-arms it (M2, L10). The item fades out, never vanishes (M1). Controls on the live item: the tinted
          program without its settings is refused and the drawn program stays; the base program refuses the tinted
          settings; a stream whose schema carries a field no pass declares is refused at bind. The surface's GPU time for
          two passes and for a third (each pass doubled), median and p90.
  framebuffer (each API) a 2560x1440 hidden host at 150 %: the window's framebuffer the native item reports (Qt's own
          redirect target, L1) is 2560x1440, as against the logical size times the dpr.
Then Vulkan's frames against OpenGL's (within VULKAN_TOLERANCE levels; both native).

Usage (repository venv, from the checkout holding the built module):
  python native/core/python/generic_mode_check.py --module-dir release/native_module --require-validation
      --layer-path D:\\Temp\\Scratch\\SRPSS\\native_spike\\validation_layers\\extracted
  [--apis opengl vulkan] [--rounds blocks reader draw framebuffer] [--label n29_generic_mode]
Evidence: .artifacts/evidence/native_core/n2_9/<date>_<label>/ (summary.json; one PNG sheet per API). Exit 0 whenever
the harness ran; the verdict is the last printed line ("N29 VERDICT PASS" or "N29 VERDICT FAIL: ...").
"""
from __future__ import annotations

import argparse
import json
import math
import struct
import subprocess
import sys
import tempfile
import time
import traceback
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import vk_validation  # noqa: E402  (native/core/python)
import host_check  # noqa: E402

APIS = ("opengl", "vulkan")
ROUNDS = ("blocks", "reader", "draw", "framebuffer")
CHILD_TIMEOUT_S = 900
MARGIN = 8
CARD = (480, 270)                # the item's logical size
DPRS = (1.0, 1.5)                # the draw round's ratios (1.5: fragPixel at a fractional ratio)
REST_FRAMES = 3
VULKAN_TOLERANCE = 1             # 8-bit levels, native Vulkan against native OpenGL
SLOT_BYTES = 1024                # one Probe Rings record (208 bytes) per slot, with room
IDENTITY = {"runtime_generation": 5, "engine_generation": 2, "activation_id": 9}
RADIUS_TOLERANCE_PX = 1.5
TIMED_FRAMES = 60
FADE_MS = 200                    # the draw round's fade (short: the harness pumps until it ends)
FRAMEBUFFER_HOST = (2560, 1440, 1.5)
INT_MEMBERS = ("ring_count",)    # the shaders' int members (every other one is float)
_ALLOWED_ENV: set[str] = set()


def _work(out: Path) -> Path:
    path = out / "work"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _mode():
    import probe_rings

    return probe_rings


def _settings(dpr: float = 1.0, **overrides) -> dict:
    """The base spec's settings, with stored values overridden (spec keys)."""
    pr = _mode()
    stored = dict(pr.DEFAULTS)
    stored.update(overrides)
    return pr.resolve_settings(stored, dpr=dpr)


def _tint_settings(dpr: float = 1.0) -> dict:
    pr = _mode()
    return pr.resolve_settings(dict(pr.TINT_DEFAULTS), dpr=dpr, spec=pr.TINT_SPEC, defaults=pr.TINT_DEFAULTS)


def _target(dpr: float) -> tuple[int, int]:
    return (int(round(CARD[0] * dpr)), int(round(CARD[1] * dpr)))


def _frames(count: int, *, speed: float = 0.35, dt: float = 1.0 / 60.0) -> list[dict]:
    pr = _mode()
    simulation = pr.RingsSimulation(speed=speed)
    return [simulation.step(dt) for _ in range(count)]


def _table(**changes) -> dict:
    from rendering.native.mode import schema_table_entry

    table = schema_table_entry(_mode().SCHEMA)
    table.update(changes)
    return table


def _schema_with(entries, *, ruled: bool = True) -> dict:
    """A runtime table of these ``(name, kind, count)`` entries (ring_count with its at_most rule unless not ``ruled``)."""
    from core.visualizer_engine.native_schema import NativeLayout

    pr = _mode()
    layout = NativeLayout.build(list(entries))
    rule = ruled and any(f.name == "ring_count" for f in layout.fields)
    rows = [[f.name, f.kind, f.count, f.offset, "at_most" if (rule and f.name == "ring_count") else "",
             pr.MAX_RINGS if (rule and f.name == "ring_count") else 0] for f in layout.fields[2:]]
    names = [row[0] for row in rows]
    return _table(record_bytes=layout.size, fingerprint=layout.fingerprint(), fields=rows,
                  check_order=[names.index("ring_count")] if rule else [])


def _base_entries():
    return [(f.name, f.kind, f.count) for f in _mode().SCHEMA.layout.fields[2:]]


# --------------------------------------------------------------------------------------------------- the packer

def core_values(card: dict, target: tuple[int, int]) -> dict:
    """The core's conventions for this card and target, computed here from their definitions (``MODE_CORE_MEMBERS``),
    never read from the core."""
    window_from_target, item_from_window = card["window_from_target"], card["item_from_window"]
    return {"uMatrix": [0.0] * 16, "uItemSize": card["item_size"], "uContentRotationQuarters": card["quarters"],
            "u_resolution": card["oriented_size"], "u_dpr": card["dpr"], "u_viewport_origin_px": [0.0, 0.0],
            "u_quick_item_coords": 1, "u_fade": card["content_fade"], "u_border_width": card["border_width"],
            "u_item_from_frag": 1, "u_item_from_frag_x": item_from_window[:3], "u_item_from_frag_y": item_from_window[3:],
            "u_window_from_target_x": window_from_target[:3], "u_window_from_target_y": window_from_target[3:],
            "u_target_px": [float(target[0]), float(target[1])]}


def expected_block(members: list, values: dict, size: int, ints=INT_MEMBERS) -> bytes:
    """``values`` (name -> number or numbers) packed at the reflected members' offsets and strides (rows ``[name,
    type, offset, count, stride, inferred]``): float32, or int32 for ``ints``; zero elsewhere. The core's own packing
    is never read to make it."""
    out = bytearray(size)
    for name, _type, offset, count, stride, _inferred in members:
        value = values[name]
        numbers = [float(v) for v in (value if isinstance(value, (list, tuple)) else [value])]
        components = len(numbers) // max(1, int(count))
        for index, number in enumerate(numbers):
            element, component = divmod(index, components)
            at = int(offset) + element * (int(stride) if int(count) > 1 else 0) + 4 * component
            if name in ints:
                struct.pack_into("<i", out, at, int(number))
            else:
                struct.pack_into("<f", out, at, number)
    return bytes(out)


def _refused(call) -> str:
    try:
        call()
    except ValueError as exc:
        return str(exc)
    return ""


def round_blocks(core, folder: Path) -> dict:
    from rendering.native.mode import MODE_CORE_MEMBERS, ModePass

    pr = _mode()
    passes = pr.passes(folder / "base")
    tinted = pr.passes(folder / "tint", rings_text=pr.shader_variant(tint=True))
    settings = _settings()
    card = pr.harness_card(CARD, 1.0)
    target = _target(1.0)
    checks: dict = {"core_table_is_the_faces": core.mode_core_members() == MODE_CORE_MEMBERS}
    facts: dict = {}
    compared = differing = 0
    first_difference = None
    sources_seen: set = set()
    for index, values in enumerate(_frames(120)):
        if index % 10:
            continue
        blocks, info = core.mode_blocks(pr.SCHEMA, passes, settings, pr.record(values), card, target)
        everything = {**core_values(card, target), **settings, **values}
        for data, program_pass, sources in zip(blocks, info["program"]["passes"], info["passes"]):
            layout = program_pass["block"]
            compared += 1
            sources_seen |= set(sources["sources"].values())
            if data != expected_block(layout["members"], everything, int(layout["size"])):
                differing += 1
                first_difference = first_difference or {"frame": index, "pass": program_pass["name"]}
    checks["blocks_equal_the_independent_packer"] = compared > 0 and differing == 0
    checks["every_source_fills_some_member"] = sources_seen == {"core", "settings", "record"}
    facts["blocks"] = {"compared": compared, "differing": differing, "first_difference": first_difference}
    record = pr.record(_frames(30)[-1])

    def blocks(schema, program=passes, given=settings, given_card=card):
        return core.mode_blocks(schema, program, given, record if schema is pr.SCHEMA else bytes(schema["record_bytes"]),
                                given_card, target)

    spare = _schema_with(_base_entries() + [("spare", "f64", 1)])
    lacking = _schema_with([entry for entry in _base_entries() if entry[0] != "time"])
    unruled = _schema_with(_base_entries(), ruled=False)
    compiled = next(row for row in _compiled_table()["schemas"] if row["mode_id"] == "spectrum")
    shadow = _table(mode_id="spectrum", mode_code=compiled["mode_code"], version=compiled["version"] + 1,
                    schema_id=((compiled["version"] + 1) << 16) | 0x100 | compiled["mode_code"])
    reasons = {
        "unknown_record_field": _refused(lambda: blocks(spare)),
        "unfilled_from_the_record": _refused(lambda: blocks(lacking)),
        "unfilled_setting": _refused(lambda: blocks(pr.SCHEMA, given={k: v for k, v in settings.items()
                                                                       if k != "u_glow"})),
        "unknown_setting": _refused(lambda: blocks(pr.SCHEMA, given=dict(settings, u_spare=1.0))),
        "setting_names_a_core_member": _refused(lambda: blocks(pr.SCHEMA, given=dict(settings, u_fade=1.0))),
        "setting_names_a_record_field": _refused(lambda: blocks(pr.SCHEMA, given=dict(settings, level=1.0))),
        "tinted_shader_base_settings": _refused(lambda: blocks(pr.SCHEMA, program=tinted)),
        "base_shader_tinted_settings": _refused(lambda: blocks(pr.SCHEMA, given=_tint_settings())),
        "u32_into_int_without_a_rule": _refused(lambda: blocks(unruled)),
        "no_card": _refused(lambda: blocks(pr.SCHEMA, given_card=None)),
        "schema_fingerprint": _refused(lambda: blocks(_table(fingerprint="0" * 16))),
        "schema_overlap": _refused(lambda: blocks(
            _table(fields=[[r[0], r[1], r[2], 16 if r[0] == "level" else r[3], r[4], r[5]] for r in _table()["fields"]]))),
        "schema_compiled_id": _refused(lambda: blocks(compiled)),
        "schema_compiled_mode_other_version": _refused(lambda: blocks(shadow)),
        "schema_mode_table": _refused(lambda: blocks(_table(mode_id="spectrum"))),
        "pass_with_a_sampler": _refused(lambda: core.mode_program_layout(_variant_pass(folder, "sampler"))),
        "pass_block_at_binding_17": _refused(lambda: core.mode_program_layout(_variant_pass(folder, "binding17"))),
        "pass_with_two_blocks": _refused(lambda: core.mode_program_layout(_variant_pass(folder, "two_blocks"))),
    }
    expected_words = {"unknown_record_field": "spare", "unfilled_from_the_record": "time",
                      "unfilled_setting": "u_glow", "unknown_setting": "u_spare",
                      "setting_names_a_core_member": "core member", "setting_names_a_record_field": "record's field",
                      "tinted_shader_base_settings": "u_tint", "base_shader_tinted_settings": "u_tint",
                      "u32_into_int_without_a_rule": "range rule", "no_card": "card",
                      "schema_fingerprint": "fingerprint", "schema_overlap": "overlaps",
                      "schema_compiled_id": "compiled", "schema_compiled_mode_other_version": "compiled",
                      "schema_mode_table": "spectrum", "pass_with_a_sampler": "primitive",
                      "pass_block_at_binding_17": "17", "pass_with_two_blocks": "one block of its own"}
    for name, word in expected_words.items():
        checks[f"refused_{name}"] = word in reasons[name]
    reasons["pack_count"] = _refused(lambda: core.module.mode_program_layout(
        json.dumps({"passes": [{"name": "rings", "blend": "alpha"}, {"name": "glow", "blend": "add"}]}),
        [passes[0].pack]))
    checks["refused_pack_count"] = "pack" in reasons["pack_count"]
    # The product's own 2D packs (audit N29 M5): admitted as they are, Bubble refused for its samplers alone.
    from rendering.native.program_values import mode_fragment_pack

    product = {}
    for mode_id in ("oscilloscope", "devcurve", "bubble"):
        product[mode_id] = _refused(lambda m=mode_id: core.mode_program_layout([ModePass(m, mode_fragment_pack(m))]))
    product["bubble_without_samplers"] = _refused(lambda: core.mode_program_layout(_bubble_without_samplers(folder)))
    checks["product_oscilloscope_admitted"] = product["oscilloscope"] == ""
    checks["product_devcurve_admitted"] = product["devcurve"] == ""
    checks["product_bubble_refused_for_its_samplers"] = "sampler" in product["bubble"]
    checks["control_bubble_without_samplers_admitted"] = product["bubble_without_samplers"] == ""
    facts["reasons"] = reasons
    facts["product"] = product
    facts["layout"] = core.mode_program_layout(passes)
    return {"pass": all(checks.values()), "checks": checks, "facts": facts}


def _compiled_table() -> dict:
    from rendering.native.packet_reader import python_schema_table

    return python_schema_table()


SAMPLER_LINE = "layout(binding = 3) uniform sampler2D u_probe_texture;\n"
SECOND_BLOCK = "layout(std140, binding = 19) uniform ProbeSecond { float u_second; };\n"


def _variant_pass(folder: Path, kind: str):
    """The glow pass changed to declare what a pass may not: a sampler (a primitive's business), its block at binding
    17 (the conventions block's), or a second block of its own."""
    from rendering.native.mode import ModePass

    pr = _mode()
    text = pr.shader_text("glow.frag")
    if kind == "sampler":
        text = text.replace("void main() {", SAMPLER_LINE + "void main() {", 1).replace(
            "fragColor = vec4(pulse_color.rgb,", "fragColor = texture(u_probe_texture, v_uv) + vec4(pulse_color.rgb,", 1)
    elif kind == "binding17":
        text = text.replace("binding = 18) uniform ProbeRingsDraw", "binding = 17) uniform ProbeRingsDraw", 1)
    else:
        text = text.replace("void main() {", SECOND_BLOCK + "void main() {", 1).replace(
            "fragColor = vec4(pulse_color.rgb,", "fragColor = vec4(u_second) + vec4(pulse_color.rgb,", 1)
    return [ModePass("glow", pr.bake(text, "glow.frag", folder / f"variant_{kind}"), "add")]


def _bubble_without_samplers(folder: Path):
    """A copy of the product's bubble.frag whose two samplers are taken out (their reads a constant): what is left of
    Bubble's shape is admitted, so its samplers alone are refused."""
    from rendering.native.mode import ModePass
    from tools import regen_qrc

    pr = _mode()
    text = (regen_qrc.mode_shader_dir() / "bubble.frag").read_text(encoding="utf-8")
    lines = []
    for line in text.splitlines(keepends=True):
        if "uniform sampler2D" in line:
            continue
        lines.append(line)
    text = "".join(lines)
    for sampler in ("u_ambient_texture", "u_ambient_light"):
        text = text.replace(f"texture({sampler},", "srpssNoTexture(")
    text = text.replace("void main()", "vec4 srpssNoTexture(vec2 uv) { return vec4(0.0 * uv.x); }\nvoid main()", 1)
    return [ModePass("bubble", pr.bake(text, "bubble.frag", folder / "bubble_without_samplers"), "alpha")]


# --------------------------------------------------------------------------------------------------- the stream

class Stream:
    """The mode's frame stream the harness writes (the engine worker's side)."""

    def __init__(self) -> None:
        from core.visualizer_engine.packet_abi import FramePacketWriter, create_frame_mapping

        pr = _mode()
        self.memory = create_frame_mapping(generation=IDENTITY["runtime_generation"], slot_bytes=SLOT_BYTES,
                                           engine_generation=IDENTITY["engine_generation"],
                                           activation_id=IDENTITY["activation_id"], mode_code=pr.MODE_CODE,
                                           token=uuid.uuid4().hex[:12])
        self.writer = FramePacketWriter(self.memory.buf)
        self.closed = False

    @property
    def name(self) -> str:
        return self.memory.name

    @property
    def expect(self) -> dict:
        return {**IDENTITY, "mode_code": _mode().MODE_CODE}

    def publish(self, payload: bytes, timestamp: float) -> int:
        from core.visualizer_engine.packet_abi import FLAG_PRESENT_FRAME

        pr = _mode()
        return self.writer.publish(payload, payload_schema=pr.SCHEMA.schema_id, logical_timestamp=timestamp,
                                   flags=FLAG_PRESENT_FRAME, mode_code=pr.MODE_CODE, **IDENTITY)

    def close(self) -> None:
        if self.closed:
            return
        self.closed = True
        self.writer.release()
        self.memory.close()
        self.memory.unlink()


def round_reader(core) -> dict:
    pr = _mode()
    checks: dict = {}
    facts: dict = {}
    stream = Stream()
    readers = []
    try:
        reader = core.packet_reader(stream.name, expect=stream.expect, schema=pr.SCHEMA)
        readers.append(reader)
        matched = 0
        frames = _frames(20)
        for step, values in enumerate(frames):
            stream.publish(pr.record(values), float(step))
            if reader.read() != "accepted":
                break
            frame = reader.frame()
            if frame is not None and frame.fields is not None:
                decoded = pr.SCHEMA.decode(frame.payload)
                matched += int(json.dumps(dict(frame.fields), sort_keys=True) == json.dumps(
                    {k: (list(v) if isinstance(v, tuple) else v) for k, v in decoded.items()}, sort_keys=True))
        checks["frames_accepted_and_decoded_by_the_schema"] = matched == len(frames)
        facts["matched"] = matched
        blind = core.packet_reader(stream.name, expect=stream.expect)
        readers.append(blind)
        result = blind.read()
        state = blind.state()
        checks["control_without_the_schema_refuses"] = (result == "refused"
                                                         and (state.get("refusal") or {}).get("cause") == "mode")
        facts["without_schema"] = {"result": result, "refusal": state.get("refusal")}
        broken = bytearray(pr.record(frames[-1]))
        struct.pack_into("<I", broken, pr.SCHEMA.layout.field("ring_count").offset, pr.MAX_RINGS + 1)
        stream.publish(bytes(broken), 99.0)
        result = reader.read()
        state = reader.state()
        checks["record_rule_refused"] = (result == "refused" and (state.get("refusal") or {}).get("cause") == "record")
        facts["broken_record"] = {"result": result, "refusal": state.get("refusal")}
    finally:
        for reader in readers:
            reader.close()
        stream.close()
    live = core.packet_reader_live()
    checks["readers_closed"] = live.get("readers") == 0 and live.get("views") == 0
    return {"pass": all(checks.values()), "checks": checks, "facts": facts}


# --------------------------------------------------------------------------------------------------- the scene

SCENE_QML = b"""import QtQuick
Rectangle {
    color: "#000000"
    Item { objectName: "contentHost"; x: %(margin)d; y: %(margin)d; width: 4; height: 4 }
}
""" % {b"margin": MARGIN}


class Scene:
    """An opaque black display with one generic mode item at (MARGIN, MARGIN), its target on the item's own rect."""

    def __init__(self, core, engine, host, dpr: float) -> None:
        from PySide6.QtCore import QUrl
        from PySide6.QtQml import QQmlComponent
        from PySide6.QtQuick import QQuickItem

        self.host = host
        self.dpr = float(dpr)
        self.component = QQmlComponent(engine)
        self.component.setData(SCENE_QML, QUrl())
        self.root = self.component.create()
        if self.root is None:
            raise RuntimeError(f"the scene did not load: {self.component.errorString()}")
        self.content = self.root.findChild(QQuickItem, "contentHost")
        host.set_content(self.root)
        self.mode = core.mode(self.content)
        self.mode.composite.set(rect=[0.0, 0.0, float(CARD[0]), float(CARD[1])], coverage=None, quarters=0,
                                visible=True)
        self.mode.card(_mode().harness_card(CARD, self.dpr))

    def read(self):
        from dataclasses import asdict

        from composite_analysis import frame_rows

        rows = frame_rows(asdict(self.host.read()))
        left = int(round(MARGIN * self.dpr))
        width, height = _target(self.dpr)
        return rows[left:left + height, left:left + width]

    def close(self, app) -> None:
        self.mode.composite.destroy()
        self.host.set_content(None)
        host_check._drop_item(app, self.root)


def ring_runs(pixels, threshold: int = 24) -> list[tuple[float, int]]:
    """(centre distance from the card's centre in pixels, width) of each bright run on the centre row, right half."""
    import numpy as np

    height, width = pixels.shape[:2]
    row = pixels[height // 2, width // 2:, :3].max(axis=1).astype(int)
    runs, start = [], None
    for x, value in enumerate(list(row) + [0]):
        if value > threshold and start is None:
            start = x
        elif value <= threshold and start is not None:
            weights = row[start:x].astype(float)
            centre = float(np.sum((np.arange(start, x) + 0.5) * weights) / np.sum(weights))
            runs.append((centre + (width // 2) - width / 2.0, x - start))
            start = None
    return runs


def visible_rings(values: dict, thickness: float, size: tuple[int, int] = CARD) -> list[float] | None:
    """The radii (pixels, in a target of ``size``) of the rings bright enough to measure on the centre row, or None when
    two lie too close to tell apart (that frame is not measured)."""
    unit = 0.5 * min(size)
    radii = sorted(r * unit for r, a in zip(values["rings"][:values["ring_count"]],
                                            values["ring_alpha"][:values["ring_count"]])
                   if a > 0.25 and r * unit > thickness + 2.0 and r * unit + thickness < size[0] / 2.0 - 2.0)
    if any(b - a < thickness + 6.0 for a, b in zip(radii, radii[1:])):
        return None
    return radii


def _radii_match(pixels, values: dict, thickness: float, size: tuple[int, int] = CARD) -> bool | None:
    """Every clearly visible ring of the record is drawn at its radius (within RADIUS_TOLERANCE_PX), and nothing is
    drawn on the centre row where the record has no ring at all (faint rings may or may not pass the threshold). None
    when the frame has nothing to measure."""
    expected = visible_rings(values, thickness, size)
    if not expected:
        return None
    measured = [centre for centre, _w in ring_runs(pixels)]
    unit = 0.5 * min(size)
    every = [r * unit for r in values["rings"][:values["ring_count"]]]
    found = all(any(abs(m - e) <= RADIUS_TOLERANCE_PX for m in measured) for e in expected)
    no_strays = all(any(abs(m - r) <= RADIUS_TOLERANCE_PX + thickness for r in every) for m in measured)
    return found and no_strays


def _channel_means(pixels):
    import numpy as np

    rgb = pixels[..., :3].astype(float)
    lit = rgb.max(axis=2) > 40
    if not lit.any():
        return (0.0, 0.0, 0.0)
    return tuple(float(np.mean(rgb[..., c][lit])) for c in range(3))


def _renamed(mode_pass, name: str):
    from dataclasses import replace

    return replace(mode_pass, name=name)


def _measure_rings(core, engine, app, host, folder: Path, dpr: float, frames: dict) -> dict:
    """The rings at their record's radii at ``dpr`` (glow off)."""
    pr = _mode()
    host.set_device_pixel_ratio(dpr)
    scene = Scene(core, engine, host, dpr)
    stream = Stream()
    measured = []
    try:
        settings = _settings(dpr, probe_rings_glow=0.0)
        scene.mode.program(pr.passes(folder / f"measure_{dpr}"), settings)
        scene.mode.bind(stream.name, pr.SCHEMA, expect=stream.expect)
        thickness = float(settings["u_thickness_px"])
        size = _target(dpr)
        for step, values in enumerate(_frames(150)):
            stream.publish(pr.record(values), float(step))
            scene.mode.update()
            pixels = scene.read()
            match = _radii_match(pixels, values, thickness, size)
            if match is not None:
                measured.append(match)
                frames.setdefault(f"rings_dpr{dpr}", pixels)
        state = scene.mode.state()
    finally:
        stream.close()
        scene.close(app)
        host.frames(2)
        host_check._flush_deletes(app)
    return {"frames": len(measured), "matched": sum(measured), "pass": len(measured) >= 20 and all(measured),
            "accepted": state["accepted"], "last_reason": state["last_reason"]}


def round_draw(core, engine, app, host, api: str, folder: Path, out: Path) -> dict:
    import numpy as np

    pr = _mode()
    checks: dict = {}
    facts: dict = {}
    frames: dict = {}
    for dpr in DPRS:
        measured = _measure_rings(core, engine, app, host, folder, dpr, frames)
        facts[f"rings_dpr{dpr}"] = measured
        checks[f"rings_drawn_where_the_record_puts_them_dpr{dpr}"] = measured["pass"]
    host.set_device_pixel_ratio(1.0)
    scene = Scene(core, engine, host, 1.0)
    stream = Stream()
    step = [0]

    def show(values: dict, raw: bytes | None = None):
        stream.publish(raw if raw is not None else pr.record(values), float(step[0]))
        step[0] += 1
        scene.mode.update()
        return scene.read()

    try:
        base = pr.passes(folder / "draw_base")
        no_glow = _settings(probe_rings_glow=0.0)
        scene.mode.program(base, no_glow)
        scene.mode.bind(stream.name, pr.SCHEMA, expect=stream.expect)
        thickness = float(no_glow["u_thickness_px"])
        loud = max(_frames(150), key=lambda v: v["level"])
        dark_centre = show(loud)[CARD[1] // 2, CARD[0] // 2, :3].astype(int)
        scene.mode.settings(_settings())
        lit = show(loud)
        frames["glow"] = lit
        checks["glow_pass_adds_light"] = int(lit[CARD[1] // 2, CARD[0] // 2, :3].astype(int).sum()) \
            > int(dark_centre.sum()) + 60
        scene.mode.settings(no_glow)
        sample = next(v for v in _frames(150) if visible_rings(v, thickness) and len(visible_rings(v, thickness)) >= 2)
        reference = show(sample)
        frames["reference"] = reference
        # A card change shows: the core's u_fade from the card.
        scene.mode.card(pr.harness_card(CARD, 1.0, fade=0.5))
        halved = show(sample)
        scene.mode.card(pr.harness_card(CARD, 1.0))
        bright = lambda pixels: float(pixels[..., :3].astype(float).sum())   # noqa: E731
        checks["card_change_shows"] = 0.35 * bright(reference) < bright(halved) < 0.65 * bright(reference)
        # Nothing at rest.
        show(sample)
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
        checks["nothing_recorded_at_rest"] = (after["records"] == before["records"]
                                              and surface_after == surface_before and not rest_samples)
        facts["rest"] = {"records": [before["records"], after["records"]],
                         "surface_passes": [surface_before, surface_after], "gpu_surface_samples": len(rest_samples)}
        # GPU time: the two passes, then a third pass (each pass doubled).
        timing = {}
        settings_on = _settings()
        programs = {"rings+glow": base,
                    "rings+rings+glow": (base[0], _renamed(base[0], "rings_again"), base[1]),
                    "rings+glow+glow": (base[0], base[1], _renamed(base[1], "glow_again"))}
        for label, program in programs.items():
            scene.mode.program(program, settings_on)
            for values in _frames(TIMED_FRAMES):
                stream.publish(pr.record(values), float(step[0]))
                step[0] += 1
                scene.mode.update()
                host.frames(1)
            host.frames(4)
            times = sorted(s.nanoseconds for s in host.gpu_samples() if s.kind == 2)
            timing[label] = {"samples": len(times),
                             "median_ms": round(times[len(times) // 2] / 1e6, 4) if times else None,
                             "p90_ms": round(times[int(len(times) * 0.9)] / 1e6, 4) if times else None}
        host.set_gpu_timer(False)
        facts["gpu"] = timing
        checks["gpu_time_recorded"] = all((entry["samples"] or 0) >= TIMED_FRAMES // 2 for entry in timing.values())
        scene.mode.program(base, no_glow)
        reference = show(sample)
        # A refused frame keeps the last drawn frame (M4): a NaN level; then the next good frame draws.
        nan = bytearray(pr.record(sample))
        struct.pack_into("<d", nan, pr.SCHEMA.layout.field("level").offset, math.nan)
        refused_before = scene.mode.state().get("refused_frames", 0)
        kept = show(sample, raw=bytes(nan))
        state = scene.mode.state()
        good = show(sample)
        checks["refused_frame_keeps_the_card"] = (int(np.abs(kept.astype(int) - reference.astype(int)).max()) == 0
                                                  and bright(kept) > 0)
        checks["refused_frame_counted_with_its_reason"] = (state.get("refused_frames", 0) == refused_before + 1
                                                           and "level" in str(state.get("last_refusal")))
        checks["good_frame_after_a_refused_one_draws"] = int(np.abs(good.astype(int) - reference.astype(int)).max()) == 0
        # A shader change: the rings drawn green.
        green = pr.passes(folder / "draw_green", rings_text=pr.shader_variant(green=True))
        scene.mode.program(green)                                 # the settings given before stay
        drawn_green = show(sample)
        frames["shader_change"] = drawn_green
        r, g, b = _channel_means(drawn_green)
        r0, g0, b0 = _channel_means(reference)
        checks["shader_change_shows"] = g > 3.0 * max(r, b, 1.0) and g0 < 3.0 * max(r0, b0, 1.0)
        facts["channel_means"] = {"reference": [r0, g0, b0], "shader_change": [r, g, b]}
        # A spec value: thickness 2 against 8.
        scene.mode.program(base, _settings(probe_rings_glow=0.0, probe_rings_thickness=2.0))
        thin = ring_runs(show(sample))
        scene.mode.settings(_settings(probe_rings_glow=0.0, probe_rings_thickness=8.0))
        thick_pixels = show(sample)
        thick = ring_runs(thick_pixels)
        frames["spec_change"] = thick_pixels
        checks["spec_change_shows"] = bool(thin and thick and float(np.median([w for _c, w in thick]))
                                           >= float(np.median([w for _c, w in thin])) + 4.0)
        facts["widths"] = {"thin": thin, "thick": thick}
        # A shader and a spec change together: a new member and the control that fills it.
        tinted = pr.passes(folder / "draw_tint", rings_text=pr.shader_variant(tint=True))
        refusals = {}
        try:
            scene.mode.program(tinted)                            # the base settings lack u_tint: refused
        except ValueError as exc:
            refusals["tinted_program_without_its_settings"] = str(exc)
        still = show(sample)
        checks["control_refused_program_keeps_the_drawn_one"] = (
            "u_tint" in refusals.get("tinted_program_without_its_settings", "")
            and int(np.abs(still.astype(int) - thick_pixels.astype(int)).max()) == 0)
        try:
            scene.mode.settings(_tint_settings())                  # the base program has no u_tint: refused
        except ValueError as exc:
            refusals["tinted_settings_on_the_base_program"] = str(exc)
        checks["control_unknown_setting_refused"] = "u_tint" in refusals.get("tinted_settings_on_the_base_program", "")
        scene.mode.program(tinted, dict(_tint_settings(), u_glow=0.0))
        drawn_tint = show(sample)
        frames["shader_and_spec_change"] = drawn_tint
        r, g, b = _channel_means(drawn_tint)
        checks["shader_and_spec_change_shows"] = g > 3.0 * max(r, b, 1.0)
        # A simulation change: twice the speed, the rings where its record puts them.
        scene.mode.program(base, no_glow)
        slow_radii = visible_rings(sample, thickness)
        fast_sample = next((v for v in _frames(150, speed=0.7)
                            if visible_rings(v, thickness) and visible_rings(v, thickness) != slow_radii), None)
        drawn_fast = show(fast_sample) if fast_sample else None
        checks["simulation_change_shows"] = bool(fast_sample is not None
                                                 and _radii_match(drawn_fast, fast_sample, thickness))
        if drawn_fast is not None:
            frames["simulation_change"] = drawn_fast
        # A stream whose schema carries a field no pass declares is refused at bind.
        spare = _schema_with(_base_entries() + [("spare", "f64", 1)])
        try:
            scene.mode.bind(stream.name, spare, expect=stream.expect)
        except ValueError as exc:
            refusals["schema_with_an_unknown_field"] = str(exc)
        checks["control_unknown_field_refused_at_bind"] = "spare" in refusals.get("schema_with_an_unknown_field", "")
        facts["refusals"] = refusals
        state = scene.mode.state()
        checks["no_python_thread_state_on_the_render_thread"] = bool(
            state.get("syncs_probed") and state.get("syncs_with_python_thread_state") == 0
            and state.get("syncs_on_gui_thread") == 0)
        facts["state"] = {k: state.get(k) for k in ("syncs", "accepted", "records", "draws", "refused_frames",
                                                    "last_refusal", "last_reason", "syncs_probed",
                                                    "syncs_with_python_thread_state")}
        # The fade (M1): a hide fades the item out over fade_ms, never at once.
        scene.mode.composite.set(visible=False, fade_ms=FADE_MS)
        started = scene.mode.composite.state()
        host_check._wait_until(app, lambda: not scene.mode.composite.state().get("fading"),
                               timeout=10.0 * FADE_MS / 1000.0)
        ended = scene.mode.composite.state()
        checks["the_item_fades_out"] = (started.get("shown") is True and started.get("fading") is True
                                        and ended.get("shown") is False and ended.get("fading") is False)
        facts["fade"] = {"started": {k: started.get(k) for k in ("shown", "shown_opacity", "fading")},
                         "ended": {k: ended.get(k) for k in ("shown", "shown_opacity", "fading")}}
    finally:
        stream.close()
        scene.close(app)
        host.frames(2)
        host_check._flush_deletes(app)
    facts["failure"] = content_failure(core, engine, app, host, folder)
    checks["content_failure_recorded_once_and_rearmed_by_a_program"] = facts["failure"]["held"]
    np.savez_compressed(_work(out) / f"native_{api}.npz", **{k: v for k, v in frames.items()})
    _sheet(out, api, frames)
    live = core.composite_live()
    checks["nothing_left"] = (live.get("mode_sources") == 0 and live.get("mode_resources") == 0
                              and core.packet_reader_live().get("views") == 0)
    facts["live_at_end"] = live
    return {"pass": all(checks.values()), "checks": checks, "facts": facts}


def content_failure(core, engine, app, host, folder: Path, frames: int = 5) -> dict:
    """Audit N29 M2 and L10: an item with a stream and a card but no program cannot build its content. The failure is
    one edge (recorded once), the frames after it create nothing again (no QRhi object of the content stays alive),
    and a program (a changed input) re-arms it: the next frame draws."""
    pr = _mode()
    scene = Scene(core, engine, host, 1.0)
    stream = Stream()
    states, live = [], []
    drawn = None
    try:
        scene.mode.bind(stream.name, pr.SCHEMA, expect=stream.expect)
        values = _frames(60)[-1]
        for step in range(frames):
            stream.publish(pr.record(values), float(step))
            scene.mode.update()
            host.frames(1)
            states.append(scene.mode.state())
            live.append(core.composite_live().get("mode_resources"))
        scene.mode.program(pr.passes(folder / "failure"), _settings(probe_rings_glow=0.0))
        stream.publish(pr.record(values), float(frames))
        scene.mode.update()
        host.frames(1)
        drawn = scene.mode.state()
    finally:
        stream.close()
        scene.close(app)
        host.frames(2)
        host_check._flush_deletes(app)
    last = states[-1] if states else {}
    held = (bool(states) and last.get("content_failures") == 1 and last.get("draws") == 0
            and all(value == 0 for value in live) and drawn is not None and drawn.get("draws", 0) >= 1)
    return {"held": held, "failures": [s.get("content_failures") for s in states], "records": [s.get("records")
                                                                                              for s in states],
            "mode_resources": live, "last_reason": last.get("last_reason"),
            "after_program": None if drawn is None else {k: drawn.get(k) for k in ("draws", "last_reason")}}


def round_framebuffer(core, engine, app, api: str) -> dict:
    """Audit N29 L1: the window's framebuffer the native item reports is Qt's own (the hidden host's redirect target:
    2560x1440 at 150 %), not the logical size times the dpr."""
    width, height, dpr = FRAMEBUFFER_HOST
    host = core.hidden_host(width, height, dpr=dpr)
    scene = None
    try:
        scene = Scene(core, engine, host, dpr)
        host.frames(2)
        pixels = scene.mode.composite.window_pixels()
        window = scene.content.window()
        logical = (window.width(), window.height())
        sync = scene.mode.composite.state().get("sync", {})
    finally:
        if scene is not None:
            scene.close(app)
        host.frames(1)
        host.close()
        host_check._flush_deletes(app)
    checks = {"window_pixels_are_the_framebuffer": pixels == (width, height),
              "the_sync_reports_the_same": sync.get("window_pixels") == [width, height]}
    return {"pass": all(checks.values()), "checks": checks,
            "facts": {"window_pixels": pixels, "logical_size": logical,
                      "logical_times_dpr": [round(logical[0] * dpr, 3), round(logical[1] * dpr, 3)]}}


def _sheet(out: Path, api: str, frames: dict) -> None:
    import numpy as np
    from PIL import Image

    order = ["rings_dpr1.0", "glow", "shader_change", "spec_change", "shader_and_spec_change", "simulation_change"]
    tiles = [frames[k][..., :3] for k in order if k in frames]
    if tiles:
        height = max(tile.shape[0] for tile in tiles)
        tiles = [np.pad(tile, ((0, height - tile.shape[0]), (0, 0), (0, 0))) for tile in tiles]
        Image.fromarray(np.concatenate(tiles, axis=1), "RGB").save(out / f"probe_rings_{api}.png")


def vulkan_against_opengl(out: Path) -> dict:
    import numpy as np

    work = _work(out)
    gl_path, vk_path = work / "native_opengl.npz", work / "native_vulkan.npz"
    if not gl_path.exists() or not vk_path.exists():
        return {"pass": False, "error": "a native frame set is missing"}
    gl, vk = np.load(gl_path), np.load(vk_path)
    compared = max_level = 0
    for key in gl.files:
        if key not in vk.files or gl[key].shape != vk[key].shape:
            return {"pass": False, "error": f"frame {key} is missing or differs in shape"}
        compared += 1
        max_level = max(max_level, int(np.abs(gl[key][..., :3].astype(np.int16) - vk[key][..., :3]).max()))
    return {"pass": compared > 0 and max_level <= VULKAN_TOLERANCE, "compared": compared, "max_level": max_level,
            "tolerance": VULKAN_TOLERANCE}


# --------------------------------------------------------------------------------------------------- the child

def _host_size() -> tuple[int, int]:
    largest = max(DPRS)
    return (int(math.ceil((CARD[0] + 2 * MARGIN) * largest)), int(math.ceil((CARD[1] + 2 * MARGIN) * largest)))


def child(args) -> dict:
    root = host_check._root(args.repo)
    out = Path(args.out_dir)
    record: dict = {"api": args.api, "rounds": list(args.rounds), "module_loaded": False, "instance_created": False}
    if args.api == "opengl":
        from rendering.quick.bootstrap import configure_quick_graphics

        configure_quick_graphics(reason="generic-mode-check")
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
    with tempfile.TemporaryDirectory(prefix="srpss_n29_") as scratch:
        folder = Path(scratch)
        try:
            for name in args.rounds:
                if name in ("blocks", "reader") and vulkan:
                    continue                                       # GPU-free: the OpenGL child's
                if vulkan:
                    core.set_vulkan_phase(f"n29 {name}")
                try:
                    if name == "blocks":
                        record[name] = round_blocks(core, folder)
                    elif name == "reader":
                        record[name] = round_reader(core)
                    elif name == "framebuffer":
                        record[name] = round_framebuffer(core, engine, app, args.api)
                    else:
                        if host is None:
                            host = core.hidden_host(*_host_size())
                        record[name] = round_draw(core, engine, app, host, args.api, folder, out)
                except Exception:
                    record[name] = {"pass": False, "error": traceback.format_exc()}
        finally:
            if host is not None:
                if vulkan:
                    core.set_vulkan_phase("n29 close")
                record["host_close"] = host.close()
            host_check._flush_deletes(app)
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
        record["rounds"] = [n for n in record["rounds"] if n not in ("blocks", "reader")]
    return record


def api_verdict(api: str, record: dict, require_validation: bool) -> tuple[bool, list[str]]:
    ok, failed = host_check.api_verdict(api, record, require_validation)
    if record.get("module_loaded") and (api != "vulkan" or record.get("instance_created")):
        live = record.get("composites_at_end") or {}
        if any(live.get(key) for key in ("items", "surfaces", "surface_resources", "mode_sources", "mode_resources")):
            failed.append(f"{api}: composites left at the end ({live})")
        readers = record.get("readers_at_end") or {}
        if readers.get("readers") or readers.get("views"):
            failed.append(f"{api}: packet readers left at the end ({readers})")
    return not failed, failed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--module-dir", default="release/native_module")
    parser.add_argument("--repo", default=".", help="the repository root (default: the current directory)")
    parser.add_argument("--apis", nargs="+", default=list(APIS), choices=APIS)
    parser.add_argument("--rounds", nargs="+", default=list(ROUNDS), choices=ROUNDS)
    parser.add_argument("--label", default="n29_generic_mode")
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

    vk_validation.use_layer_path(args.layer_path, _ALLOWED_ENV)
    root = host_check._root(args.repo)
    from tools import artifact_paths

    out = artifact_paths.evidence_dir("native_core", "n2_9", args.label)
    out.mkdir(parents=True, exist_ok=True)
    environment = vk_validation.environment_record(_ALLOWED_ENV)
    results: dict = {}
    for api in [a for a in APIS if a in args.apis]:
        child_json = out / f"child_{api}.json"
        command = [sys.executable, str(Path(__file__).resolve()), "--child", "--api", api, "--repo", str(root),
                   "--module-dir", args.module_dir, "--out-dir", str(out), "--child-json", str(child_json),
                   "--rounds", *args.rounds]
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
            failed.append(f"vulkan against opengl: {cross}")
    if not environment["clean"]:
        failed.append(f"environment: {', '.join(environment['contaminating_set'])} set")
    summary = {"apis": args.apis, "rounds": args.rounds, "environment": environment,
               "require_validation": args.require_validation, "vulkan_against_opengl": cross,
               "verdicts": {api: {"pass": ok, "failed": reasons} for api, (ok, reasons) in verdicts.items()},
               "results": results, "pass": not failed}
    (out / "summary.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    for api, (ok, reasons) in verdicts.items():
        print(f"{api}: {'PASS' if ok else 'FAIL'}" + ("" if ok else " (" + "; ".join(reasons)[:2000] + ")"))
    if cross is not None:
        print(f"vulkan against opengl: {cross}")
    print(f"evidence: {out / 'summary.json'} (the work folder holds the frames: delete it once judged)")
    print("N29 VERDICT " + ("PASS" if not failed else "FAIL: " + "; ".join(failed)[:4000]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
