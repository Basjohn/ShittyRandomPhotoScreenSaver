"""N2.9's proof of generic mode content (Current_Plan.md item 8b; ``native/core/src/mode_content.h``), through
``rendering.native``, on the harness-only mode Probe Rings (``native/core/python/probe_rings``: a Python simulation, two
fragment shaders and a spec; never registered, never in Settings, no preset).

The module (``release/native_module``, built on GitHub) is loaded the product's way, in one child process per graphics
API: OpenGL first, then Vulkan on the module's own instance and devices (D6). No window is ever visible: the item draws
into the module's hidden host.

Rounds:
  blocks  (OpenGL child; GPU-free) what the core uploads, against an independent Python packer: for frames of the
          simulation, each pass's ModeSettings and ModeFrame bytes from ``mode_blocks`` equal the settings and the
          record's fields packed at the members' reflected offsets and strides (float32, int32), member by member.
          Negative controls, each refused with its reason: a record field no pass declares (unknown), a ModeFrame member
          no field names (unfilled), a setting left out (unfilled), a setting no pass declares (unknown), the tinted
          shader with the base spec's settings (unfilled), the base shader with the tinted spec's settings (unknown);
          the runtime schema refused for a wrong fingerprint, overlapping fields, a compiled schema's id and a mode id
          that disagrees with the compiled mode table; a pass declaring a sampler; a pack count unlike the passes'.
  reader  (OpenGL child; GPU-free) the core's reader admits the mode's stream by the schema handed over: frames
          accepted, their fields decoded by the C++ table equal to the schema's own decode. Controls: the reader opened
          without the schema refuses the first slot (an unknown mode code); a record whose ring_count breaks its rule is
          refused after the copy.
  draw    (each API) the item in the hidden host: the drawn rings at the radii the record holds (the centre row's rings,
          within 1.5 px); the glow pass adds light at the centre; nothing recorded at rest (records, surface passes and
          GPU samples unchanged over idle frames); no Python thread state on the render thread. A change shows with no
          module rebuild: a shader change (rings drawn green), a spec value (thickness 2 against 8: wider rings), a
          shader and spec change together (a new ModeSettings member and the control that fills it: tinted), a
          simulation change (twice the speed: the rings where the new record puts them). Controls on the live item: the
          tinted program without its settings is refused (unfilled) and the drawn program stays; the base program
          refuses the tinted settings (unknown); a stream whose schema carries a field no pass declares is refused at
          bind. The surface's GPU time for the two passes, and for a third pass (each pass doubled), median and p90.
Then Vulkan's frames against OpenGL's (within VULKAN_TOLERANCE levels; both native).

Usage (repository venv, from the checkout holding the built module):
  python native/core/python/generic_mode_check.py --module-dir release/native_module --require-validation
      --layer-path D:\\Temp\\Scratch\\SRPSS\\native_spike\\validation_layers\\extracted
  [--apis opengl vulkan] [--rounds blocks reader draw] [--label n29_generic_mode]
Evidence: .artifacts/evidence/native_core/n2_9/<date>_<label>/ (summary.json; one PNG sheet per API). Exit 0 whenever
the harness ran; the verdict is the last printed line ("N29 VERDICT PASS" or "N29 VERDICT FAIL: ...").
"""
from __future__ import annotations

import argparse
import json
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
ROUNDS = ("blocks", "reader", "draw")
CHILD_TIMEOUT_S = 900
MARGIN = 8
CARD = (480, 270)                # the item's logical size; drawn at DPR 1 (its target is CARD device pixels)
REST_FRAMES = 3
VULKAN_TOLERANCE = 1             # 8-bit levels, native Vulkan against native OpenGL
SLOT_BYTES = 1024                # one Probe Rings record (208 bytes) per slot, with room
IDENTITY = {"runtime_generation": 5, "engine_generation": 2, "activation_id": 9}
RADIUS_TOLERANCE_PX = 1.5
TIMED_FRAMES = 60
INT_FIELDS = ("ring_count",)     # the record's u32 fields the shaders declare as int
_ALLOWED_ENV: set[str] = set()


def _work(out: Path) -> Path:
    path = out / "work"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _mode():
    import probe_rings

    return probe_rings


def _settings(**overrides) -> dict:
    """The base spec's settings for the card, with stored values overridden (spec keys)."""
    pr = _mode()
    stored = dict(pr.DEFAULTS)
    stored.update(overrides)
    return pr.resolve_settings(stored, target_px=CARD, dpr=1.0)


def _tint_settings() -> dict:
    pr = _mode()
    return pr.resolve_settings(dict(pr.TINT_DEFAULTS), target_px=CARD, dpr=1.0, spec=pr.TINT_SPEC,
                               defaults=pr.TINT_DEFAULTS)


def _frames(count: int, *, speed: float = 0.35, dt: float = 1.0 / 60.0) -> list[dict]:
    pr = _mode()
    simulation = pr.RingsSimulation(speed=speed)
    return [simulation.step(dt) for _ in range(count)]


def _table(**changes) -> dict:
    from rendering.native.mode import schema_table_entry

    table = schema_table_entry(_mode().SCHEMA)
    table.update(changes)
    return table


# --------------------------------------------------------------------------------------------------- the packer

def expected_block(members: list, values: dict, size: int) -> bytes:
    """``values`` (name -> number or numbers) packed at the reflected members' offsets and strides (rows ``[name,
    type, offset, count, stride, inferred]``): float32, or int32 for ``INT_FIELDS``; zero elsewhere. The core's own
    packing is never read to make it."""
    out = bytearray(size)
    for name, _type, offset, count, stride, _inferred in members:
        value = values[name]
        numbers = [float(v) for v in (value if isinstance(value, (list, tuple)) else [value])]
        components = len(numbers) // max(1, int(count))
        for index, number in enumerate(numbers):
            element, component = divmod(index, components)
            at = int(offset) + element * (int(stride) if int(count) > 1 else 0) + 4 * component
            if name in INT_FIELDS:
                struct.pack_into("<i", out, at, int(number))
            else:
                struct.pack_into("<f", out, at, number)
    return bytes(out)


def round_blocks(core, folder: Path) -> dict:
    pr = _mode()
    passes = pr.passes(folder / "base")
    tinted = pr.passes(folder / "tint", rings_text=pr.shader_variant(tint=True))
    settings = _settings()
    checks: dict = {}
    facts: dict = {}
    compared = differing = 0
    first_difference = None
    for index, values in enumerate(_frames(120)):
        if index % 10:
            continue
        blocks, info = core.mode_blocks(pr.SCHEMA, passes, settings, pr.record(values))
        for (settings_bytes, frame_bytes), program_pass in zip(blocks, info["program"]["passes"]):
            for kind, data, source in (("settings", settings_bytes, settings), ("frame", frame_bytes, values)):
                layout = program_pass[kind]
                compared += 1
                expected = expected_block(layout["members"], source, int(layout["size"]))
                if data != expected:
                    differing += 1
                    first_difference = first_difference or {"frame": index, "pass": program_pass["name"],
                                                            "block": kind}
    checks["blocks_equal_the_independent_packer"] = compared > 0 and differing == 0
    facts["blocks"] = {"compared": compared, "differing": differing, "first_difference": first_difference}
    record = pr.record(_frames(30)[-1])

    def refused(call) -> str:
        try:
            call()
        except ValueError as exc:
            return str(exc)
        return ""

    from core.visualizer_engine.native_schema import NativeLayout

    def schema_with(entries) -> dict:
        layout = NativeLayout.build(entries)
        rows = [[f.name, f.kind, f.count, f.offset, "at_most" if f.name == "ring_count" else "",
                 pr.MAX_RINGS if f.name == "ring_count" else 0] for f in layout.fields[2:]]
        names = [row[0] for row in rows]
        return _table(record_bytes=layout.size, fingerprint=layout.fingerprint(), fields=rows,
                      check_order=[names.index("ring_count")] if "ring_count" in names else [])

    base_entries = [(f.name, f.kind, f.count) for f in pr.SCHEMA.layout.fields[2:]]
    spare = schema_with(base_entries + [("spare", "f64", 1)])
    lacking = schema_with([entry for entry in base_entries if entry[0] != "time"])
    reasons = {
        "unknown_record_field": refused(lambda: core.mode_blocks(spare, passes, settings, bytes(spare["record_bytes"]))),
        "unfilled_frame_member": refused(lambda: core.mode_blocks(lacking, passes, settings,
                                                                  bytes(lacking["record_bytes"]))),
        "unfilled_setting": refused(lambda: core.mode_blocks(pr.SCHEMA, passes, {k: v for k, v in settings.items()
                                                                                 if k != "u_glow"}, record)),
        "unknown_setting": refused(lambda: core.mode_blocks(pr.SCHEMA, passes, dict(settings, u_spare=1.0), record)),
        "tinted_shader_base_settings": refused(lambda: core.mode_blocks(pr.SCHEMA, tinted, settings, record)),
        "base_shader_tinted_settings": refused(lambda: core.mode_blocks(pr.SCHEMA, passes, _tint_settings(), record)),
        "schema_fingerprint": refused(lambda: core.mode_blocks(_table(fingerprint="0" * 16), passes, settings, record)),
        "schema_overlap": refused(lambda: core.mode_blocks(
            _table(fields=[[r[0], r[1], r[2], 16 if r[0] == "level" else r[3], r[4], r[5]]
                           for r in _table()["fields"]]), passes, settings, record)),
        "schema_compiled_id": refused(lambda: core.mode_blocks(_compiled_spectrum_table(), passes, settings, record)),
        "schema_mode_table": refused(lambda: core.mode_blocks(_table(mode_id="spectrum"), passes, settings, record)),
        "pass_with_a_sampler": refused(lambda: core.mode_blocks(pr.SCHEMA, _sampler_passes(folder, passes), settings,
                                                                record)),
    }
    expected_words = {"unknown_record_field": "spare", "unfilled_frame_member": "time", "unfilled_setting": "u_glow",
                      "unknown_setting": "u_spare", "tinted_shader_base_settings": "u_tint",
                      "base_shader_tinted_settings": "u_tint", "schema_fingerprint": "fingerprint",
                      "schema_overlap": "overlaps", "schema_compiled_id": "compiled", "schema_mode_table": "spectrum",
                      "pass_with_a_sampler": "primitive"}
    for name, word in expected_words.items():
        checks[f"refused_{name}"] = word in reasons[name]
    # The pack count: the program declares two passes and gets one pack.
    try:
        core.module.mode_program_layout(json.dumps({"passes": [{"name": "rings", "blend": "alpha"},
                                                               {"name": "glow", "blend": "add"}]}),
                                        [passes[0].pack])
        reasons["pack_count"] = ""
    except ValueError as exc:
        reasons["pack_count"] = str(exc)
    checks["refused_pack_count"] = "pack" in reasons["pack_count"]
    facts["reasons"] = reasons
    facts["layout"] = core.mode_program_layout(passes)
    return {"pass": all(checks.values()), "checks": checks, "facts": facts}


def _compiled_spectrum_table() -> dict:
    """Spectrum's compiled schema handed over as a runtime one (refused: a compiled schema is never replaced)."""
    from rendering.native.packet_reader import python_schema_table

    return next(s for s in python_schema_table()["schemas"] if s["mode_id"] == "spectrum")


SAMPLER_LINE = "layout(binding = 3) uniform sampler2D u_probe_texture;\n"


def _sampler_passes(folder: Path, passes):
    """The glow pass with a sampler declared and read (a primitive's business, never pass data)."""
    from rendering.native.mode import ModePass

    pr = _mode()
    text = pr.shader_text("glow.frag").replace("void main() {", SAMPLER_LINE + "void main() {", 1)
    text = text.replace("fragColor = vec4(pulse_color.rgb,", "fragColor = texture(u_probe_texture, p) + vec4(pulse_color.rgb,", 1)
    sub = folder / "sampler"
    sub.mkdir(parents=True, exist_ok=True)
    return (passes[0], ModePass("glow", pr.bake(text, "glow.frag", sub), "add"))


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

    def consumed(self) -> int:
        return self.writer.consumed_sequence

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
        # Control: without the schema the mode's code is unknown and the slot is refused at its head.
        blind = core.packet_reader(stream.name, expect=stream.expect)
        readers.append(blind)
        result = blind.read()
        state = blind.state()
        checks["control_without_the_schema_refuses"] = (result == "refused"
                                                         and (state.get("refusal") or {}).get("cause") == "mode")
        facts["without_schema"] = {"result": result, "refusal": state.get("refusal")}
        # A record that breaks its own rule (ring_count 9) is refused after the copy.
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

    def __init__(self, core, engine, host) -> None:
        from PySide6.QtCore import QUrl
        from PySide6.QtQml import QQmlComponent
        from PySide6.QtQuick import QQuickItem

        self.host = host
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

    def read(self):
        from dataclasses import asdict

        from composite_analysis import frame_rows

        rows = frame_rows(asdict(self.host.read()))
        return rows[MARGIN:MARGIN + CARD[1], MARGIN:MARGIN + CARD[0]]

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


def visible_rings(values: dict, thickness: float) -> list[float] | None:
    """The radii (pixels) of the rings bright enough to measure on the centre row, or None when two lie too close to
    tell apart (that frame is not measured)."""
    unit = 0.5 * min(CARD)
    radii = sorted(r * unit for r, a in zip(values["rings"][:values["ring_count"]],
                                            values["ring_alpha"][:values["ring_count"]])
                   if a > 0.25 and r * unit > thickness + 2.0 and r * unit + thickness < CARD[0] / 2.0 - 2.0)
    if any(b - a < thickness + 6.0 for a, b in zip(radii, radii[1:])):
        return None
    return radii


def _radii_match(pixels, values: dict, thickness: float) -> bool | None:
    """Every clearly visible ring of the record is drawn at its radius (within RADIUS_TOLERANCE_PX), and nothing is
    drawn on the centre row where the record has no ring at all (faint rings may or may not pass the threshold). None
    when the frame has nothing to measure."""
    expected = visible_rings(values, thickness)
    if not expected:
        return None
    measured = [centre for centre, _w in ring_runs(pixels)]
    unit = 0.5 * min(CARD)
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


def round_draw(core, engine, app, host, api: str, folder: Path, out: Path) -> dict:
    import numpy as np

    pr = _mode()
    checks: dict = {}
    facts: dict = {}
    host.set_device_pixel_ratio(1.0)
    scene = Scene(core, engine, host)
    stream = Stream()
    frames = {}
    step = [0]

    def show(values: dict):
        stream.publish(pr.record(values), float(step[0]))
        step[0] += 1
        scene.mode.update()
        return scene.read()

    try:
        base = pr.passes(folder / "draw_base")
        no_glow = _settings(probe_rings_glow=0.0)
        scene.mode.program(base, no_glow)
        scene.mode.bind(stream.name, pr.SCHEMA, expect=stream.expect)
        thickness = float(no_glow["u_thickness_px"])
        # The rings where the record puts them.
        measured = []
        for values in _frames(150):
            pixels = show(values)
            match = _radii_match(pixels, values, thickness)
            if match is not None:
                measured.append(match)
                frames.setdefault("rings", pixels)
        checks["rings_drawn_where_the_record_puts_them"] = len(measured) >= 20 and all(measured)
        facts["rings_measured_frames"] = {"frames": len(measured), "matched": sum(measured)}
        state = scene.mode.state()
        checks["every_frame_accepted"] = state["accepted"] == 150 and state["last_reason"] == ""
        # The glow pass adds light at the centre on a loud frame.
        loud = max(_frames(150), key=lambda v: v["level"])
        dark_centre = show(loud)[CARD[1] // 2, CARD[0] // 2, :3].astype(int)
        scene.mode.settings(_settings())
        lit = show(loud)
        frames["glow"] = lit
        lit_centre = lit[CARD[1] // 2, CARD[0] // 2, :3].astype(int)
        checks["glow_pass_adds_light"] = int(lit_centre.sum()) > int(dark_centre.sum()) + 60
        # Nothing at rest.
        scene.mode.settings(no_glow)
        show(loud)
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
        programs = {"rings+glow": base,
                    "rings+rings+glow": (base[0], _renamed(base[0], "rings_again"), base[1]),
                    "rings+glow+glow": (base[0], base[1], _renamed(base[1], "glow_again"))}
        settings_on = _settings()
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
        sample = next(v for v in _frames(150) if visible_rings(v, thickness) and len(visible_rings(v, thickness)) >= 2)
        reference = show(sample)
        frames["reference"] = reference
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
        # A shader and a spec change together: a new ModeSettings member and the control that fills it.
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
        fast = [v for v in _frames(150, speed=0.7) if visible_rings(v, thickness)]
        slow_radii = visible_rings(sample, thickness)
        fast_sample = next((v for v in fast if visible_rings(v, thickness) != slow_radii), None)
        drawn_fast = show(fast_sample) if fast_sample else None
        checks["simulation_change_shows"] = bool(fast_sample is not None
                                                 and _radii_match(drawn_fast, fast_sample, thickness))
        if drawn_fast is not None:
            frames["simulation_change"] = drawn_fast
        # A stream whose schema carries a field no pass declares is refused at bind.
        from core.visualizer_engine.native_schema import NativeLayout

        layout = NativeLayout.build([(f.name, f.kind, f.count) for f in pr.SCHEMA.layout.fields[2:]]
                                    + [("spare", "f64", 1)])
        rows = [[f.name, f.kind, f.count, f.offset, "at_most" if f.name == "ring_count" else "",
                 pr.MAX_RINGS if f.name == "ring_count" else 0] for f in layout.fields[2:]]
        spare = _table(record_bytes=layout.size, fingerprint=layout.fingerprint(), fields=rows,
                       check_order=[[row[0] for row in rows].index("ring_count")])
        try:
            scene.mode.bind(stream.name, spare, expect=stream.expect)
        except ValueError as exc:
            refusals["schema_with_an_unknown_field"] = str(exc)
        checks["control_unknown_field_refused_at_bind"] = "spare" in refusals.get("schema_with_an_unknown_field", "")
        facts["refusals"] = refusals
        # D5.4: the reads at the sync ran on the render thread, never holding a Python thread state.
        state = scene.mode.state()
        checks["no_python_thread_state_on_the_render_thread"] = bool(
            state.get("syncs_probed") and state.get("syncs_with_python_thread_state") == 0
            and state.get("syncs_on_gui_thread") == 0)
        facts["state"] = {k: state.get(k) for k in ("syncs", "accepted", "records", "draws", "last_reason",
                                                    "syncs_probed", "syncs_with_python_thread_state")}
    finally:
        stream.close()
        scene.close(app)
        host.frames(2)
        host_check._flush_deletes(app)
    np.savez_compressed(_work(out) / f"native_{api}.npz", **{k: v for k, v in frames.items()})
    _sheet(out, api, frames)
    live = core.composite_live()
    checks["nothing_left"] = (live.get("mode_sources") == 0 and live.get("mode_resources") == 0
                              and core.packet_reader_live().get("views") == 0)
    facts["live_at_end"] = live
    return {"pass": all(checks.values()), "checks": checks, "facts": facts}


def _renamed(mode_pass, name: str):
    from dataclasses import replace

    return replace(mode_pass, name=name)


def _sheet(out: Path, api: str, frames: dict) -> None:
    import numpy as np
    from PIL import Image

    order = ["rings", "glow", "shader_change", "spec_change", "shader_and_spec_change", "simulation_change"]
    tiles = [frames[k][..., :3] for k in order if k in frames]
    if tiles:
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
                    else:
                        if host is None:
                            host = core.hidden_host(CARD[0] + 2 * MARGIN, CARD[1] + 2 * MARGIN)
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
