"""N3.2's proof of the native core's meshes and buffers (Current_Plan.md item 8b, N3.2; decision D15;
``native/core/src/mesh_buffers.h``), through ``rendering.native``, on the harness-only scenes
``native/core/python/mesh_buffers`` (passes with their own vertex stage drawing into a surface-sized RGBA8 scene target
``scene`` the harness reads back).

The module (``release/native_module``, built on GitHub) is loaded the product's way in one child process per graphics
API (OpenGL, then Vulkan on the module's own instance and device, D6), and the Python reference in a child of its own
(an offscreen OpenGL context, the production GL host's calls: buffers, vertex arrays with divisors, storage and uniform
blocks, ``glDrawArraysInstanced``). No window is ever visible.

Rounds:
  parity     (each API; and the reference) the scenes box (a mesh instanced over storage records, depth, cull with the
             front face chosen per record), voxels (a static per-instance stream), sprites (an instance stream written
             per record, the geometry include's instanced quads), beam (a vertex-pulled strip, blend MAX) and streaks
             (the built-in quad, 900 instances, a third culled) at dpr 1 and 1.5. Rule (a): native OpenGL against the
             reference; rule (b): native Vulkan against native OpenGL within 1 level. Native checks: the box culled
             equals the box unculled (depth tested), the wrong front face differs; the sprite coordinate with y up
             differs (negative control); a culled sprite draws nothing (control: the same records without the
             cull draw). The reference also draws the sprites as gl_PointSize points (the figures) and with its
             instance stream read out of step (the negative control: the pixels differ).
  forms      (each API) the batched draw (D15 point 6): sixteen batches as one multi-draw with gl_DrawID (form 3, where
             the device reports the features), one draw a batch at its dynamic offset (form 2: the control that hides
             the features), one direct draw, and sixteen passes each with its own block: equal bit for bit; negative
             control: every batch given the first batch's index. Indirect: drawIndirect from record-written commands
             equals the direct draw. firstInstance 3 on a direct draw (the control): ignored on OpenGL, moved on Vulkan
             (the reason firstInstance is always 0). gl_DrawID, gl_BaseInstance and gl_BaseVertex read back as
             the colour of the multi-draw (first vertex 4) where it is recorded. The device facts (Vulkan) and
             research Q5's bake facts.
  used       (each API) D15 point 4: an f32 stream writes only its used elements (the bytes written per record), a
             storage stream's bytes past its used length are the earlier record's (nothing past it uploaded), an
             instance stream is drawn exactly its used records and another instance count is refused (audit 4 H2;
             control instances_past_used: the Vulkan frames alternate), a record whose used length breaks its
             at_most rule writes nothing.
  rest       (each API) nothing uploaded, written or recorded over frames at rest; control: a new record writes.
  steady     (each API) frames of new records: the core's buffers created, mesh, stream and ownership counts flat, the
             process's private bytes recorded; control: streams made again every record (the counts grow).
  retire     (each API) a mesh replaced and removed, a program without geometry, the item destroyed (once between an
             upload and its first draw): meshes, streams, arenas and bytes back to zero; control: a release that skips
             the meshes (counted left behind).
  cost       (each API) GPU time (the surface figure: the content's whole record) median and p90 per scene at 2560x1440
             and 3840x2160 (the card at dpr 5.33 and 8), and the batched forms; the thread probe.
  stream_ring (each API) D15 point 7, D5.3: payloads at the product's sizes through QRhi's routes (instance stream by
             the fast path; storage by uploadStaticBuffer) with a pass that reads them as the consumer does, against
             the pair's floor (CPU: the record with the data resident plus one copy of the payload into mapped
             memory; GPU: the same instanced pass over a resident mesh instance stream, no copy); per frame the
             record's render-thread time (the core's counter) and the GPU time; and Waveform's 288 KiB capacity
             carrying 4 KiB. The pair is built only if a route misses the floor by 0.05 ms or more.

Usage (repository venv, from the checkout holding the built module):
  python native/core/python/mesh_buffer_check.py --module-dir release/native_module --require-validation
      --layer-path D:\\Temp\\Scratch\\SRPSS\\native_spike\\validation_layers\\extracted
  [--apis opengl vulkan] [--rounds parity forms used rest steady retire cost stream_ring] [--label n32_mesh_buffers]
  [--ring-payloads waveform_288KiB waveform_288KiB_used_4KiB ...]
Evidence: .artifacts/evidence/native_core/n3_2/<date>_<label>/ (summary.json; sheet_<api>.png). Exit 0 whenever the
harness ran; the verdict is the last printed line ("N32 VERDICT PASS" or "N32 VERDICT FAIL: ...").
"""
from __future__ import annotations

import argparse
import ctypes
import json
import math
import shutil
import struct
import subprocess
import sys
import time
import traceback
import uuid
from dataclasses import replace
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import vk_validation  # noqa: E402  (native/core/python)
import host_check  # noqa: E402

APIS = ("opengl", "vulkan")
ROUNDS = ("parity", "forms", "used", "rest", "steady", "retire", "cost", "stream_ring")
CHILD_TIMEOUT_S = 1800
MARGIN = 8
DPRS = (1.0, 1.5)
IDENTITY = {"runtime_generation": 5, "engine_generation": 2, "activation_id": 9}
PARITY_SCENES = ("box", "voxels", "sprites", "beam", "streaks")
# Both rules: within 1 level but for at most this many pixels (D13's tie budget: an additive or blended pixel sums
# per-layer roundings, each within 1 level, of SPIRV-Cross's GLSL against the source's own); the exact counts are kept.
TIE_PIXELS = 8
REST_FRAMES = 8
STEADY_SECONDS = {"sprites": 60.0}  # the plan's steady minute on the per-record instance stream; the others shorter
STEADY_OTHER_SECONDS = 10.0
STEADY_CONTROL_FRAMES = 600
COST_HOSTS = ((2560, 1440), (3840, 2160))
COST_SCENES = ("box", "voxels", "sprites", "beam", "streaks", "cells")
COST_MIN_SAMPLES = 30
COST_MAX_FRAMES = 1500             # Qt's OpenGL timer returns a time for about one frame in 20: a bounded loop
RING_PAYLOADS = (("4KiB", 4096), ("bubble_4.6KB", 4608), ("oscilloscope_48KiB", 49152),
                 ("waveform_160KiB", 163840), ("waveform_288KiB", 294912))
# The lead's partial case (D15 point 4): Waveform's 288 KiB capacity carrying 4 KiB, through the storage route.
RING_PARTIAL = ("waveform_288KiB_used_4KiB", 294912, 1024)
RING_FRAMES = 600                  # the ring's timed records a route (the CPU axis: window means of 20)
COST_FRAMES = 240
FLOOR_MARGIN_MS = 0.05
_ALLOWED_ENV: set[str] = set()


def _scenes():
    import mesh_buffers

    return mesh_buffers


def _work(out: Path) -> Path:
    path = out / "work"
    path.mkdir(parents=True, exist_ok=True)
    return path


# --------------------------------------------------------------------------------------------------- the packs

def bake_packs(out: Path) -> dict:
    """Every scene shader baked once (the parent) into the work folder; the children read them."""
    mb = _scenes()
    folder = _work(out) / "packs"
    folder.mkdir(parents=True, exist_ok=True)
    packs = mb.bake_all(folder / "src")
    optional, facts = mb.bake_optional(folder / "src")
    packs.update(optional)
    for name, data in packs.items():
        (folder / f"{name}.qsb").write_bytes(data)
    (folder / "bake_facts.json").write_text(json.dumps(facts, indent=1), encoding="utf-8")
    return facts


def load_packs(out: Path) -> dict:
    folder = _work(out) / "packs"
    return {p.name[:-4]: p.read_bytes() for p in folder.glob("*.qsb")}


# --------------------------------------------------------------------------------------------------- the stream

class Stream:
    """A scene's frame stream the harness writes (the engine worker's side)."""

    def __init__(self, schema) -> None:
        from core.visualizer_engine.packet_abi import FramePacketWriter, create_frame_mapping

        self.schema = schema
        slot = -(-(schema.layout.size + 256) // 16) * 16
        self.memory = create_frame_mapping(generation=IDENTITY["runtime_generation"], slot_bytes=slot,
                                           engine_generation=IDENTITY["engine_generation"],
                                           activation_id=IDENTITY["activation_id"], mode_code=schema.mode_code,
                                           token=uuid.uuid4().hex[:12])
        self.writer = FramePacketWriter(self.memory.buf)
        self.closed = False

    @property
    def name(self) -> str:
        return self.memory.name

    @property
    def expect(self) -> dict:
        return {**IDENTITY, "mode_code": self.schema.mode_code}

    def publish(self, payload: bytes, timestamp: float) -> int:
        from core.visualizer_engine.packet_abi import FLAG_PRESENT_FRAME

        return self.writer.publish(payload, payload_schema=self.schema.schema_id, logical_timestamp=timestamp,
                                   flags=FLAG_PRESENT_FRAME, mode_code=self.schema.mode_code, **IDENTITY)

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


def _card(card, dpr: float) -> dict:
    import probe_rings

    return probe_rings.harness_card(card, dpr)


def _host(core, dpr: float = 1.0, card=None):
    card = card or _scenes().CARD
    return core.hidden_host(int(math.ceil((card[0] + 2 * MARGIN) * dpr)), int(math.ceil((card[1] + 2 * MARGIN) * dpr)),
                            dpr=dpr)


class Scene:
    """An opaque black display with one generic mode item drawing a harness scene at (MARGIN, MARGIN), bound to a
    stream of its own schema."""

    def __init__(self, core, engine, host, spec, *, dpr: float = 1.0, card=None, meshes: bool = True) -> None:
        from PySide6.QtCore import QUrl
        from PySide6.QtQml import QQmlComponent
        from PySide6.QtQuick import QQuickItem

        self.host = host
        self.spec = spec
        self.card = card or _scenes().CARD
        self.dpr = float(dpr)
        self.component = QQmlComponent(engine)
        self.component.setData(SCENE_QML, QUrl())
        self.root = self.component.create()
        if self.root is None:
            raise RuntimeError(f"the scene did not load: {self.component.errorString()}")
        self.content = self.root.findChild(QQuickItem, "contentHost")
        host.set_content(self.root)
        self.mode = core.mode(self.content)
        self.mode.composite.set(rect=[0.0, 0.0, float(self.card[0]), float(self.card[1])], coverage=None, quarters=0,
                                visible=True)
        self.mode.card(_card(self.card, self.dpr))
        self.stream = None
        try:
            if meshes:
                self.send_meshes()
            self.mode.program(spec.passes, spec.settings, targets=spec.targets, streams=spec.streams)
            self.stream = Stream(spec.schema)
            self.mode.bind(self.stream.name, spec.schema, expect=self.stream.expect)
        except Exception:
            # A refused scene leaves nothing behind (its item and stream go before the error is raised).
            if self.stream is not None:
                self.stream.close()
            self.mode.composite.destroy()
            host.set_content(None)
            raise
        self.values = dict(spec.record)
        self.step = 0

    def send_meshes(self) -> None:
        for name, vertices, layout, instances, instance_layout in self.spec.meshes:
            self.mode.mesh(name, vertices, layout, instances=instances, instance_layout=instance_layout)

    def publish(self, **changes) -> None:
        self.values.update(changes)
        self.stream.publish(self.spec.schema.encode(self.values), float(self.step))
        self.step += 1

    def draw(self, frames: int = 1, **changes) -> None:
        self.publish(**changes)
        self.mode.update()
        self.host.frames(frames)

    def pixels(self, app, timeout_s: float = 10.0, **changes):
        """The scene target's content as this record leaves it (RGBA8, rows top first)."""
        import numpy as np

        self.mode.read_targets()
        self.publish(**changes)
        self.mode.update()
        deadline = time.monotonic() + timeout_s
        while True:
            self.host.frames(1)
            got = self.mode.target_pixels()
            if got is not None or time.monotonic() > deadline:
                break
        if got is None:
            raise RuntimeError(f"the target readback did not complete ({self.mode.state().get('last_reason')})")
        entry = next(p for p in got if p["name"] == "scene.colour")
        width, height = entry["size"]
        cw, ch = entry["content"]
        array = np.frombuffer(entry["data"], np.uint8)[:width * height * 4].reshape(height, width, 4)
        return array[height - ch:, :cw].copy()

    def close(self, app) -> None:
        self.stream.close()
        self.mode.composite.destroy()
        self.host.set_content(None)
        host_check._drop_item(app, self.root)


def _close(scene, host, app) -> None:
    scene.close(app)
    host.frames(2)
    host_check._flush_deletes(app)


def _front_cw(api: str) -> int:
    """N0.3 rule 4 on the matrix as the core uploads it (the correction flips Y on both of the core's backends: a
    mirrored matrix), with the backend's clip Y (up on OpenGL, down on Vulkan)."""
    from rendering.gl_programs.conventions import front_face_clockwise

    mirrored = (1.0, 0, 0, 0, 0, 1.0)
    return int(front_face_clockwise(mirrored, ndc_y_up=(api == "opengl")))


def spec_for(name: str, packs: dict, api: str, **options):
    return _scenes().scene(name, packs, front_cw=_front_cw(api), **options)


def _compare(a, b) -> dict:
    import numpy as np

    if a.shape != b.shape:
        return {"shape": [list(a.shape), list(b.shape)], "exact": False, "past0": -1, "past1": -1, "max": None}
    diff = np.abs(a.astype(np.int16) - b.astype(np.int16)).max(axis=2)
    return {"exact": bool((diff == 0).all()), "max": int(diff.max()), "past0": int((diff > 0).sum()),
            "past1": int((diff > 1).sum()), "lit": int((a[..., :3].max(axis=2) > 8).sum())}


# --------------------------------------------------------------------------------------------------- parity

def _variants(name: str, packs: dict, api: str) -> dict:
    """The native variants beside a scene: name -> spec."""
    base = spec_for(name, packs, api)
    out = {"": base}
    if name == "box":
        geometry = base.passes[0].geometry
        out["cull_none"] = replace(base, passes=(replace(base.passes[0], geometry=replace(geometry, cull="none")),))
        out["wrong_front"] = replace(base, settings=dict(base.settings, u_front_cw=1 - _front_cw(api)))
    if name == "sprites":
        out["y_up"] = replace(base, passes=(replace(base.passes[0], pack=packs["sprite_yup.frag"]),))
    return out


def round_parity(core, engine, app, api: str, packs: dict, out: Path) -> dict:
    import numpy as np

    frames, checks, facts = {}, {}, {}
    for dpr in DPRS:
        host = _host(core, dpr)
        try:
            for name in PARITY_SCENES:
                for variant, spec in _variants(name, packs, api).items():
                    scene = Scene(core, engine, host, spec, dpr=dpr)
                    try:
                        key = f"{name}{'.' + variant if variant else ''}|dpr{dpr}"
                        frames[key] = scene.pixels(app)
                        state = scene.mode.state()
                        if not variant:
                            facts[key] = {"last_reason": state.get("last_reason"), "records": state.get("records"),
                                          "mesh_buffers": state.get("mesh_buffers"),
                                          "lit": int((frames[key][..., :3].max(axis=2) > 8).sum())}
                    finally:
                        _close(scene, host, app)
        finally:
            host.close()
            host_check._flush_deletes(app)
    for dpr in DPRS:
        tag = f"|dpr{dpr}"
        box, cull_none, wrong = frames["box" + tag], frames["box.cull_none" + tag], frames["box.wrong_front" + tag]
        checks[f"box_culled_equals_unculled_dpr{dpr}"] = _compare(box, cull_none)["exact"]
        checks[f"box_wrong_front_face_differs_dpr{dpr}"] = _compare(box, wrong)["past1"] > 100
        checks[f"sprite_y_up_control_differs_dpr{dpr}"] = _compare(frames["sprites" + tag],
                                                                   frames["sprites.y_up" + tag])["past1"] > 50
        for name in PARITY_SCENES:
            checks[f"{name}_draws_dpr{dpr}"] = int((frames[name + tag][..., :3].max(axis=2) > 8).sum()) > 200
        facts[f"controls_dpr{dpr}"] = {"box_vs_cull_none": _compare(box, cull_none),
                                       "box_vs_wrong_front": _compare(box, wrong),
                                       "sprites_vs_y_up": _compare(frames["sprites" + tag],
                                                                   frames["sprites.y_up" + tag])}
    # The plan's "a culled sprite draws nothing": every record of kind 2 (srpssSpriteCulled), against the control
    # without the cull (the same records draw).
    culled = _culled_sprites(core, engine, app, api, packs)
    facts["culled_sprites"] = culled
    checks["a_culled_sprite_draws_nothing"] = culled["culled_lit"] == 0 and culled["control_lit"] > 200
    np.savez_compressed(_work(out) / f"parity_{api}.npz", **frames)
    _sheet(out, f"sheet_{api}.png", {k: v for k, v in frames.items() if "." not in k.split("|")[0]})
    return {"pass": all(checks.values()), "checks": checks, "facts": facts}


def _culled_sprites(core, engine, app, api: str, packs: dict) -> dict:
    import struct as _struct

    mb = _scenes()
    rows = list(mb.points())
    for i in range(mb.POINTS):
        rows[6 * i + 5] = 2.0                                  # every sprite of the cull's kind
    spec = spec_for("sprites", packs, api)
    record = dict(spec.record, point_rows=_struct.pack(f"<{len(rows)}f", *rows))
    out = {}
    host = _host(core)
    try:
        for label, pack in (("culled", None), ("control", packs["sprite_nocull.vert"])):
            variant = spec if pack is None else replace(spec, passes=(replace(
                spec.passes[0], geometry=replace(spec.passes[0].geometry, vertex_pack=pack)),))
            scene = Scene(core, engine, host, replace(variant, record=record))
            try:
                pixels = scene.pixels(app)
                out[f"{label}_lit"] = int((pixels[..., :4].max(axis=2) > 0).sum())
            finally:
                _close(scene, host, app)
    finally:
        host.close()
        host_check._flush_deletes(app)
    return out


# --------------------------------------------------------------------------------------------------- used lengths

def round_used(core, engine, app, api: str, packs: dict) -> dict:
    """D15 point 4 (the lead, 15 Nov): an f32 stream writes only its used elements. The bytes written per record are
    the used bytes (sprites: 40 of 192 records); a storage stream's bytes past the used length keep the earlier
    record's (the beam drawn past its used points equals the composite of both records: nothing past was uploaded);
    an instance stream is drawn exactly its used records, another count refused (checkpoint audit 4, H2: only a
    storage stream keeps the bytes past its used length); a record whose used length breaks its at_most rule is refused
    by the reader and writes nothing."""
    import struct as _struct

    mb = _scenes()
    checks, facts = {}, {}
    host = _host(core)
    try:
        # The bytes written: 40 sprites' 240 floats a record, not the field's 1,152.
        spec = spec_for("sprites", packs, api)
        scene = Scene(core, engine, host, spec)
        try:
            scene.draw(3, point_count=40, point_floats=240)
            before = core.composite_live()
            for _ in range(10):
                scene.draw(1)
            after = core.composite_live()
            written = after["mesh_buffers_stream_bytes_written"] - before["mesh_buffers_stream_bytes_written"]
            writes = after["mesh_buffers_stream_writes"] - before["mesh_buffers_stream_writes"]
            facts["sprites_40"] = {"writes": writes, "bytes_written": written}
            checks["only_the_used_bytes_are_written"] = writes == 10 and written == 10 * 240 * 4
        finally:
            _close(scene, host, app)
        # Past the used length the storage keeps the last full record's bytes.
        spec = spec_for("beam", packs, api)
        full_a = list(mb.trace(0))
        full_b = list(mb.trace(7))
        half = mb.TRACE_POINTS // 2
        composite = full_b[:2 * half] + full_a[2 * half:]
        pack = (lambda values: _struct.pack(f"<{len(values)}f", *values))
        scene = Scene(core, engine, host, spec)
        try:
            scene.pixels(app)                                  # record A, every point used
            partial = scene.pixels(app, trace_rows=pack(full_b), trace_floats=2 * half)
            composed = scene.pixels(app, trace_rows=pack(composite), trace_floats=2 * mb.TRACE_POINTS)
            plain_b = scene.pixels(app, trace_rows=pack(full_b), trace_floats=2 * mb.TRACE_POINTS)
        finally:
            _close(scene, host, app)
        facts["beam_partial_against_composite"] = _compare(partial, composed)
        facts["beam_partial_against_b"] = _compare(partial, plain_b)
        checks["bytes_past_the_used_length_were_not_uploaded"] = (_compare(partial, composed)["exact"]
                                                                  and not _compare(partial, plain_b)["exact"])
        # Checkpoint audit 4, H2: an instance stream is drawn exactly its used records (QRhi's fast path is a
        # whole-buffer update: past the used length are another frame slot's bytes on Vulkan, undefined on OpenGL).
        instance = _instance_used(core, engine, app, api, packs, host)
        facts["instance_stream"] = instance["facts"]
        checks.update(instance["checks"])
        # A record past its rule: refused at the reader, nothing written, the last frame kept.
        scene = Scene(core, engine, host, spec)
        try:
            kept = scene.pixels(app)
            before = core.composite_live()
            scene.draw(3, trace_floats=2 * 256 + 1)
            after = core.composite_live()
            state = scene.mode.state()
            facts["past_the_rule"] = {"writes": after["mesh_buffers_stream_writes"] - before[
                "mesh_buffers_stream_writes"], "last_reason": state.get("last_reason"),
                "refusal": state.get("refusal") or (state.get("reader") or {}).get("refusal")}
            checks["a_used_length_past_its_rule_writes_nothing"] = facts["past_the_rule"]["writes"] == 0
        finally:
            _close(scene, host, app)
    finally:
        host.close()
        host_check._flush_deletes(app)
    return {"pass": all(checks.values()), "checks": checks, "facts": facts}


def _instance_used(core, engine, app, api: str, packs: dict, host) -> dict:
    """Audit 4 H2 on the sprites' instance stream: record A (every sprite), then three records B of 40 used sprites
    each equal a fresh item's 40-sprite frame (nothing of A, no frame-slot difference); an instance count other than the
    used records is refused (nothing drawn, the reason given). Control ``instances_past_used``: the count of 120 drawn
    over 40 used records reads past the used length, and on Vulkan the frames alternate between the frame slots."""
    import struct as _struct

    mb = _scenes()
    pack = (lambda values: _struct.pack(f"<{len(values)}f", *values))
    used = 40
    b_rows = mb.points(5)
    spec = spec_for("sprites", packs, api)
    checks, facts = {}, {}
    scene = Scene(core, engine, host, spec)
    try:
        scene.pixels(app)                                      # record A, every sprite used
        b = [scene.pixels(app, point_rows=pack(b_rows), point_count=used, point_floats=6 * used) for _ in range(3)]
        before = core.composite_live().get("mesh_buffers_draws_refused", 0)
        refused = scene.pixels(app, point_count=mb.POINTS)     # another count than the 40 used records
        state = scene.mode.state()
        facts["refused"] = {"lit": int((refused[..., :4].max(axis=2) > 0).sum()),
                            "draws_refused": core.composite_live().get("mesh_buffers_draws_refused", 0) - before,
                            "last_reason": state.get("last_reason"),
                            "state": (state.get("mesh_buffers") or {}).get("draws_refused")}
    finally:
        _close(scene, host, app)
    fresh_record = dict(spec.record, point_rows=pack(b_rows), point_count=used, point_floats=6 * used)
    scene = Scene(core, engine, host, replace(spec, record=fresh_record))
    try:
        fresh = scene.pixels(app)
    finally:
        _close(scene, host, app)
    facts["b_against_fresh"] = [_compare(frame, fresh) for frame in b]
    checks["an_instance_stream_draws_exactly_its_used_records"] = (
        all(c["exact"] for c in facts["b_against_fresh"]) and int((fresh[..., :3].max(axis=2) > 8).sum()) > 200)
    checks["another_instance_count_is_refused"] = (facts["refused"]["lit"] == 0 and facts["refused"]["draws_refused"] > 0
                                                   and "used record" in str(facts["refused"]["last_reason"]))
    # The control: the count of 120 drawn over the 40 used records, past the used length.
    core.module.mesh_buffer_control(json.dumps({"instances_past_used": True}))
    try:
        scene = Scene(core, engine, host, spec)
        try:
            scene.pixels(app)                                  # record A in one slot
            past = [scene.pixels(app, point_rows=pack(b_rows), point_floats=6 * used) for _ in range(3)]
        finally:
            _close(scene, host, app)
    finally:
        core.module.mesh_buffer_control(json.dumps({"instances_past_used": False}))
    facts["control_past_used"] = {
        "frame1_vs_frame2": _compare(past[0], past[1]), "frame2_vs_frame3": _compare(past[1], past[2]),
        "frame1_vs_fresh_40": _compare(past[0], fresh)}
    differs = facts["control_past_used"]["frame1_vs_frame2"]["past1"] > 100
    if api == "vulkan":
        checks["control_past_used_alternates_on_vulkan"] = differs
    else:
        facts["control_past_used"]["opengl_frames_differ"] = differs  # undefined bytes: recorded, not judged
    checks["control_past_used_draws_past_the_40"] = not facts["control_past_used"]["frame1_vs_fresh_40"]["exact"]
    return {"checks": checks, "facts": facts}


# --------------------------------------------------------------------------------------------------- the reference

def _ref_matrix(card, dpr: float, size) -> list[float]:
    """``itemClipMatrix``'s Python mirror for the harness card (identity maps, upright), uncorrected: column-major."""
    w, h = float(size[0]), float(size[1])
    return [2.0 * dpr / w, 0.0, 0.0, 0.0, 0.0, -2.0 * dpr / h, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, -1.0, 1.0, 0.0, 1.0]


class Reference:
    """The Python owners' calls in an offscreen OpenGL context: the same shader text, the same records."""

    def __init__(self, core, packs: dict, dpr: float) -> None:
        from tools.labs.render_target import OffscreenRenderTarget

        mb = _scenes()
        self.core = core
        self.packs = packs
        self.dpr = float(dpr)
        self.size = (int(round(mb.CARD[0] * dpr)), int(round(mb.CARD[1] * dpr)))
        self.target = OffscreenRenderTarget(*self.size, label="n32-reference")
        self.objects: list = []

    def close(self) -> None:
        from OpenGL import GL as gl

        with self.target.current():
            for kind, name in self.objects:
                if kind == "buffer":
                    gl.glDeleteBuffers(1, [name])
                elif kind == "vao":
                    gl.glDeleteVertexArrays(1, [name])
                else:
                    from rendering.quick.render.gl_resources import delete_program

                    delete_program(name)
        self.target.close()

    def buffer(self, data: bytes) -> int:
        from OpenGL import GL as gl

        ids = (ctypes.c_uint * 1)()
        gl.glCreateBuffers(1, ids)
        gl.glNamedBufferData(int(ids[0]), len(data), data, gl.GL_STATIC_DRAW)
        self.objects.append(("buffer", int(ids[0])))
        return int(ids[0])

    def vao(self, bindings) -> int:
        """``bindings``: (buffer, offset, stride, divisor, ((location, components, offset), ...))."""
        from OpenGL import GL as gl

        ids = (ctypes.c_uint * 1)()
        gl.glCreateVertexArrays(1, ids)
        vao = int(ids[0])
        for index, (buffer, offset, stride, divisor, attributes) in enumerate(bindings):
            gl.glVertexArrayVertexBuffer(vao, index, buffer, offset, stride)
            gl.glVertexArrayBindingDivisor(vao, index, divisor)
            for location, components, relative in attributes:
                gl.glEnableVertexArrayAttrib(vao, location)
                gl.glVertexArrayAttribFormat(vao, location, components, gl.GL_FLOAT, gl.GL_FALSE, relative)
                gl.glVertexArrayAttribBinding(vao, location, index)
        self.objects.append(("vao", vao))
        return vao

    def program(self, vertex: str, fragment: str) -> int:
        from rendering.quick.render.gl_resources import compile_program

        mb = _scenes()
        program = compile_program(mb.compose(vertex), mb.compose(fragment), label="n32 reference")
        self.objects.append(("program", program))
        return program

    def block(self, pack: bytes, block_name: str, block_text: str, settings: dict, **extra) -> int:
        mb = _scenes()
        values = {"uMatrix": _ref_matrix(mb.CARD, self.dpr, self.size), "uItemSize": list(map(float, mb.CARD)),
                  "u_target_px": [float(self.size[0]), float(self.size[1])], "u_dpr": self.dpr, "u_srpss_batch": 0,
                  "u_frame": 0.0}
        values.update(settings)
        values.update(extra)
        values = {k: v for k, v in values.items() if k in block_text}
        data, _facts = self.core.program_block_pack(pack, block_name, values)
        return self.buffer(data)

    def draw(self, name: str, *, offset_instances: bool = False, points: bool = False):
        """The scene ``name`` drawn as the core draws it (the Python renderer's calls); its pixels top first."""
        import numpy as np
        from OpenGL import GL as gl

        from rendering.gl_programs.conventions import OPENGL_CONVENTIONS

        mb = _scenes()
        spec = mb.scene(name, self.packs, front_cw=0)
        with self.target.current():
            self.target.bind(clear=(0.0, 0.0, 0.0, 0.0))
            conventions = self.buffer(struct.pack("<4f", *OPENGL_CONVENTIONS))
            gl.glBindBufferBase(gl.GL_UNIFORM_BUFFER, 17, conventions)
            gl.glDisable(gl.GL_CULL_FACE)
            gl.glDisable(gl.GL_DEPTH_TEST)
            gl.glDisable(gl.GL_BLEND)
            record = spec.record
            if name == "box":
                program = self.program(mb.BOX_VERT, mb.BOX_FRAG)
                ubo = self.block(self.packs["box.vert"], "BoxDraw", mb.BOX_BLOCK, spec.settings)
                mesh = self.buffer(mb.box_mesh())
                vao = self.vao([(mesh, 0, 24, 0, ((0, 3, 0), (1, 3, 12)))])
                gl.glBindBufferBase(gl.GL_SHADER_STORAGE_BUFFER, 3, self.buffer(record["bar_rows"]))
                gl.glEnable(gl.GL_DEPTH_TEST)
                gl.glDepthFunc(gl.GL_LESS)
                gl.glDepthMask(gl.GL_TRUE)
                gl.glEnable(gl.GL_CULL_FACE)
                gl.glCullFace(gl.GL_BACK)
                gl.glFrontFace(gl.GL_CCW)
                self._run(program, ubo, vao, gl.GL_TRIANGLES, 36, record["bar_count"])
                gl.glDisable(gl.GL_CULL_FACE)
                gl.glDisable(gl.GL_DEPTH_TEST)
            elif name == "voxels":
                program = self.program(mb.VOXEL_VERT, mb.VOXEL_FRAG)
                ubo = self.block(self.packs["voxel.vert"], "VoxelDraw", mb.VOXEL_BLOCK, spec.settings)
                mesh = self.buffer(mb.box_mesh())
                cells = self.buffer(mb.voxel_instances())
                vao = self.vao([(mesh, 0, 24, 0, ((0, 3, 0), (1, 3, 12))), (cells, 0, 16, 1, ((2, 4, 0),))])
                self._blend("alpha")
                self._run(program, ubo, vao, gl.GL_TRIANGLES, 36, mb.VOXELS)
            elif name == "sprites":
                fragment = mb.SPRITE_FRAG_POINTS if points else mb.SPRITE_FRAG
                program = self.program(mb.SPRITE_POINT_VERT if points else mb.SPRITE_VERT, fragment)
                ubo = self.block(self.packs["sprite.vert"], "SpriteDraw", mb.SPRITE_BLOCK, spec.settings)
                data = record["point_rows"]
                if offset_instances:
                    data = data[16:] + bytes(16)        # the negative control: the attributes read out of step
                rows = self.buffer(data)
                self._blend("premultiplied")
                if points:
                    vao = self.vao([(rows, 0, 24, 0, ((0, 4, 0), (1, 2, 16)))])
                    gl.glEnable(gl.GL_PROGRAM_POINT_SIZE)
                    gl.glUseProgram(program)
                    gl.glBindBufferBase(gl.GL_UNIFORM_BUFFER, 18, ubo)
                    gl.glBindVertexArray(vao)
                    gl.glDrawArrays(gl.GL_POINTS, 0, record["point_count"])
                    gl.glDisable(gl.GL_PROGRAM_POINT_SIZE)
                else:
                    vao = self.vao([(rows, 0, 24, 1, ((0, 4, 0), (1, 2, 16)))])
                    self._run(program, ubo, vao, gl.GL_TRIANGLE_STRIP, 4, record["point_count"])
            elif name == "beam":
                program = self.program(mb.BEAM_VERT, mb.BEAM_FRAG)
                ubo = self.block(self.packs["beam.vert"], "BeamDraw", mb.BEAM_BLOCK, spec.settings)
                gl.glBindBufferBase(gl.GL_SHADER_STORAGE_BUFFER, 3, self.buffer(record["trace_rows"]))
                vao = self.vao([])
                self._blend("max")
                self._run(program, ubo, vao, gl.GL_TRIANGLE_STRIP, 4, record["segments"])
            elif name == "streaks":
                program = self.program(mb.STREAK_VERT, mb.STREAK_FRAG)
                ubo = self.block(self.packs["streak.vert"], "StreakDraw", mb.STREAK_BLOCK, spec.settings)
                self._blend("additive")
                self._run(program, ubo, self.target.vao, gl.GL_TRIANGLE_STRIP, 4, mb.STREAKS)
            elif name == "cells_direct":
                program = self.program(mb.CELL_VERT_DIRECT, mb.CELL_FRAG)
                ubo = self.block(self.packs["cell_direct.vert"], "CellDraw", mb.CELL_BLOCK, spec.settings)
                gl.glBindBufferBase(gl.GL_SHADER_STORAGE_BUFFER, 3, self.buffer(record["cell_rows"]))
                table = struct.pack(f"<{len(record['batch_table'])}I", *record["batch_table"])
                gl.glBindBufferBase(gl.GL_SHADER_STORAGE_BUFFER, 4, self.buffer(table))
                self._blend("alpha")
                self._run(program, ubo, self.vao([]), gl.GL_TRIANGLE_STRIP, 4, mb.CELLS)
            else:
                raise KeyError(name)
            gl.glDisable(gl.GL_BLEND)
            gl.glFinish()
            return np.ascontiguousarray(self.target.read_rgba())

    def _run(self, program: int, ubo: int, vao: int, mode, count: int, instances: int) -> None:
        from OpenGL import GL as gl

        gl.glUseProgram(program)
        gl.glBindBufferBase(gl.GL_UNIFORM_BUFFER, 18, ubo)
        gl.glBindVertexArray(vao)
        gl.glDrawArraysInstanced(mode, 0, count, int(instances))
        gl.glBindVertexArray(0)

    @staticmethod
    def _blend(kind: str) -> None:
        from OpenGL import GL as gl

        gl.glEnable(gl.GL_BLEND)
        if kind == "max":
            gl.glBlendEquationSeparate(gl.GL_MAX, gl.GL_MAX)
            gl.glBlendFuncSeparate(gl.GL_ONE, gl.GL_ONE, gl.GL_ONE, gl.GL_ONE)
            return
        gl.glBlendEquationSeparate(gl.GL_FUNC_ADD, gl.GL_FUNC_ADD)
        factors = {"alpha": (gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA, gl.GL_ONE, gl.GL_ONE_MINUS_SRC_ALPHA),
                   "premultiplied": (gl.GL_ONE, gl.GL_ONE_MINUS_SRC_ALPHA, gl.GL_ONE, gl.GL_ONE_MINUS_SRC_ALPHA),
                   "additive": (gl.GL_ONE, gl.GL_ONE, gl.GL_ONE, gl.GL_ONE)}[kind]
        gl.glBlendFuncSeparate(*factors)


def round_reference(core, packs: dict, out: Path) -> dict:
    import numpy as np

    frames = {}
    for dpr in DPRS:
        reference = Reference(core, packs, dpr)
        try:
            tag = f"|dpr{dpr}"
            for name in PARITY_SCENES:
                frames[name + tag] = reference.draw(name)
            frames["sprites.points" + tag] = reference.draw("sprites", points=True)
            frames["sprites.offset" + tag] = reference.draw("sprites", offset_instances=True)
            frames["cells_direct" + tag] = reference.draw("cells_direct")
        finally:
            reference.close()
    np.savez_compressed(_work(out) / "parity_reference.npz", **frames)
    _sheet(out, "sheet_reference.png", frames)
    return {"pass": True, "frames": sorted(frames)}


def cross_compare(out: Path) -> dict:
    """Rule (a): native OpenGL against the reference (exact); rule (b): native Vulkan against native OpenGL (within 1
    level); the sprites' figures against gl_PointSize; the offset stream's negative control."""
    import numpy as np

    def load(name):
        path = _work(out) / f"parity_{name}.npz"
        return dict(np.load(path)) if path.exists() else {}

    gl, vk, ref = load("opengl"), load("vulkan"), load("reference")
    result: dict = {}
    if gl and ref:
        per = {f"{name}|dpr{dpr}": _compare(gl[f"{name}|dpr{dpr}"], ref[f"{name}|dpr{dpr}"])
               for name in PARITY_SCENES for dpr in DPRS}
        result["rule_a"] = {"pass": all(0 <= v["past1"] <= TIE_PIXELS for v in per.values()), "compared": per,
                            "exact": sorted(k for k, v in per.items() if v["exact"])}
        sprites = {f"dpr{dpr}": {"quads_vs_points": _compare(gl[f"sprites|dpr{dpr}"], ref[f"sprites.points|dpr{dpr}"]),
                                 "reference_quads_vs_points": _compare(ref[f"sprites|dpr{dpr}"],
                                                                       ref[f"sprites.points|dpr{dpr}"])}
                   for dpr in DPRS}
        result["sprites_against_points"] = sprites
        offset = {f"dpr{dpr}": _compare(gl[f"sprites|dpr{dpr}"], ref[f"sprites.offset|dpr{dpr}"]) for dpr in DPRS}
        result["control_offset_stream_differs"] = {"pass": all(v["past1"] > 50 for v in offset.values()),
                                                   "compared": offset}
    else:
        result["rule_a"] = {"pass": False, "error": "a frame set is missing"}
    if vk and gl:
        per = {f"{name}|dpr{dpr}": _compare(vk[f"{name}|dpr{dpr}"], gl[f"{name}|dpr{dpr}"])
               for name in PARITY_SCENES for dpr in DPRS}
        result["rule_b"] = {"pass": all(0 <= v["past1"] <= TIE_PIXELS for v in per.values()), "compared": per,
                            "exact": sorted(k for k, v in per.items() if v["exact"])}
    else:
        result["rule_b"] = {"pass": False, "error": "a frame set is missing"}
    return result


def _sheet(out: Path, name: str, frames: dict) -> None:
    import numpy as np
    from PIL import Image

    tiles = [Image.fromarray(np.ascontiguousarray(v[..., :3])).resize((320, 180)) for _k, v in sorted(frames.items())]
    if not tiles:
        return
    columns = 5
    rows = -(-len(tiles) // columns)
    sheet = Image.new("RGB", (320 * columns, 180 * rows))
    for index, tile in enumerate(tiles):
        sheet.paste(tile, (320 * (index % columns), 180 * (index // columns)))
    sheet.save(out / name)


# --------------------------------------------------------------------------------------------------- forms

def _cells_passes(packs: dict, api: str):
    """The sixteen batches as sixteen passes, each its own block (N3.1's form)."""
    from rendering.native.mode import ModePass, PassGeometry

    mb = _scenes()
    base = spec_for("cells_direct", packs, api)
    geometry = base.passes[0].geometry
    passes = tuple(ModePass(f"cells{b}", packs["cell.frag"], "alpha", target="scene",
                            geometry=PassGeometry(packs[f"cell_pass{b}.vert"], topology="triangle_strip", vertices=4,
                                                  instances=4, storage=geometry.storage))
                   for b in range(mb.BATCHES))
    return replace(base, passes=passes)


def round_forms(core, engine, app, api: str, packs: dict, facts_in: dict) -> dict:
    checks, facts = {}, {"bake": facts_in}
    host = _host(core)
    frames = {}
    live = {}
    try:
        state = host.state()
        device = (state.get("device") or {}).get("vk_device")
        if device:
            raw = core.module.vulkan_device_facts(int(device))
            facts["device"] = json.loads(raw) if isinstance(raw, str) else raw
        dp = "cell_dp.vert" in packs

        def run(label, spec, control=None):
            if control:
                core.module.mesh_buffer_control(json.dumps(control))
            before = core.composite_live()
            scene = Scene(core, engine, host, spec)
            try:
                frames[label] = scene.pixels(app)
                after = core.composite_live()
                live[label] = {k: after.get(k, 0) - before.get(k, 0) for k in
                               ("mesh_buffers_indirect_draws", "mesh_buffers_batched_indirect",
                                "mesh_buffers_batched_loop")}
                live[label]["last_reason"] = scene.mode.state().get("last_reason")
            finally:
                _close(scene, host, app)
                if control:
                    core.module.mesh_buffer_control(json.dumps({k: (0 if isinstance(v, int) and not isinstance(
                        v, bool) else False) for k, v in control.items()}))

        run("cells", spec_for("cells", packs, api))
        run("cells_loop", spec_for("cells", packs, api), {"hide_draw_parameters": True})
        run("cells_direct", spec_for("cells_direct", packs, api))
        run("cells_passes", _cells_passes(packs, api))
        run("cells_flat", spec_for("cells_flat", packs, api))
        run("streaks", spec_for("streaks", packs, api))
        run("streaks_indirect", spec_for("streaks_indirect", packs, api))
        run("streaks_first3", spec_for("streaks", packs, api), {"direct_first_instance": 3})
        if "cell_ids.vert" in packs:
            # gl_DrawID, gl_BaseInstance and gl_BaseVertex drawn as the colour by the multi-draw (first vertex 4).
            base = spec_for("cells", packs, api)
            geometry = replace(base.passes[0].geometry, draw_parameters_pack=packs["cell_ids.vert"], first_vertex=4)
            run("cells_ids", replace(base, passes=(replace(base.passes[0], blend="replace", geometry=geometry),)))
    finally:
        host.close()
        host_check._flush_deletes(app)
    c = {k: _compare(frames["cells_direct"], frames[k]) for k in ("cells", "cells_loop", "cells_passes", "cells_flat")}
    facts["cells_against_direct"] = c
    facts["counts"] = live
    facts["draw_parameters_pack"] = "cell_dp.vert" in packs
    checks["form2_loop_equals_direct"] = c["cells_loop"]["exact"]
    checks["batched_equals_direct"] = c["cells"]["exact"]
    checks["sixteen_passes_equal_the_batched_draw"] = c["cells_passes"]["exact"]
    checks["control_first_offset_differs"] = c["cells_flat"]["past1"] > 50
    if "cells_ids" in frames and live["cells_ids"]["mesh_buffers_batched_indirect"] > 0:
        mb = _scenes()
        decoded = []
        for i in range(mb.CELLS):
            x, y = 30.0 + (i % 16) * 27.0, 40.0 + (i // 16) * 50.0
            r, g, b, _a = (int(v) for v in frames["cells_ids"][int(y), int(x)])
            decoded.append((i // 4, r, g, b))
        facts["draw_parameters_read_back"] = {
            "draw_id_is_the_batch": all(r == batch for batch, r, _g, _b in decoded),
            "base_instance": sorted({g for _batch, _r, g, _b in decoded}),
            "base_vertex": sorted({b for _batch, _r, _g, b in decoded}), "first_vertex": 4}
        checks["gl_draw_id_reads_the_batch"] = facts["draw_parameters_read_back"]["draw_id_is_the_batch"]
        checks["gl_base_instance_reads_0"] = facts["draw_parameters_read_back"]["base_instance"] == [0]
        # gl_BaseVertex of a non-indexed draw: Vulkan's is the command's first vertex; OpenGL's (ARB_shader_draw_
        # parameters) has no baseVertex parameter there and reads 0. Both recorded; each backend held to its rule.
        expected_base_vertex = [4] if api == "vulkan" else [0]
        facts["draw_parameters_read_back"]["expected_base_vertex"] = expected_base_vertex
        checks["gl_base_vertex_reads_its_backends_value"] = (facts["draw_parameters_read_back"]["base_vertex"]
                                                            == expected_base_vertex)
    else:
        facts["draw_parameters_read_back"] = "not recorded (no form 3 on this backend, or no pack)"
    checks["control_hide_draws_the_loop"] = (live["cells_loop"]["mesh_buffers_batched_loop"] > 0
                                             and live["cells_loop"]["mesh_buffers_batched_indirect"] == 0)
    form3 = live["cells"]["mesh_buffers_batched_indirect"] > 0
    facts["form3_recorded"] = form3
    if api == "vulkan" and facts.get("device", {}).get("shader_draw_parameters") and dp:
        checks["form3_recorded_where_the_features_are_reported"] = form3
    s = {k: _compare(frames["streaks"], frames[k]) for k in ("streaks_indirect", "streaks_first3")}
    facts["streaks"] = s
    checks["indirect_equals_direct"] = s["streaks_indirect"]["exact"] and live["streaks_indirect"][
        "mesh_buffers_indirect_draws"] > 0
    if api == "opengl":
        checks["first_instance_3_ignored_on_opengl"] = s["streaks_first3"]["exact"]
    else:
        facts["first_instance_3_moves_on_vulkan"] = not s["streaks_first3"]["exact"]
    return {"pass": all(checks.values()), "checks": checks, "facts": facts}


# --------------------------------------------------------------------------------------------------- rest, steady

MB_KEYS = ("mesh_buffers_meshes", "mesh_buffers_mesh_bytes", "mesh_buffers_mesh_images", "mesh_buffers_mesh_uploads",
           "mesh_buffers_streams", "mesh_buffers_stream_bytes", "mesh_buffers_stream_writes",
           "mesh_buffers_stream_bytes_written", "mesh_buffers_arenas", "mesh_buffers_arena_bytes",
           "mesh_buffers_arena_writes", "mesh_buffers_buffers_created")


def _mb(live: dict) -> dict:
    return {k: live.get(k) for k in MB_KEYS}


def round_rest(core, engine, app, api: str, packs: dict) -> dict:
    checks, facts = {}, {}
    host = _host(core)
    try:
        for name in ("box", "sprites", "cells"):
            scene = Scene(core, engine, host, spec_for(name, packs, api))
            try:
                scene.draw(3)
                host.frames(2)
                before, state_before = core.composite_live(), scene.mode.state()
                host.frames(REST_FRAMES)
                scene.mode.update()
                host.frames(REST_FRAMES)
                after, state_after = core.composite_live(), scene.mode.state()
                scene.draw(2)
                control = core.composite_live()
                unchanged = all(after.get(k) == before.get(k) for k in MB_KEYS)
                checks[f"{name}_nothing_uploaded_or_written_at_rest"] = unchanged
                checks[f"{name}_nothing_recorded_at_rest"] = state_after.get("records") == state_before.get("records")
                checks[f"{name}_control_a_record_writes"] = (
                    control["mesh_buffers_arena_writes"] > after["mesh_buffers_arena_writes"])
                checks[f"{name}_no_python_thread_state_on_the_render_thread"] = bool(
                    state_after.get("syncs_probed") and state_after.get("syncs_with_python_thread_state") == 0)
                facts[name] = {"before": _mb(before), "after": _mb(after), "control": _mb(control),
                               "records": [state_before.get("records"), state_after.get("records")]}
            finally:
                _close(scene, host, app)
    finally:
        host.close()
        host_check._flush_deletes(app)
    return {"pass": all(checks.values()), "checks": checks, "facts": facts}


def round_steady(core, engine, app, api: str, packs: dict) -> dict:
    """D15 point 8: frames of new records allocate nothing; control: the streams made again every record."""
    checks, facts = {}, {}
    host = _host(core)
    try:
        for name in ("box", "sprites", "beam", "cells", "streaks_indirect"):
            spec = spec_for(name, packs, api)
            for control in (False, True):
                if control and name not in ("sprites", "streaks_indirect"):
                    continue
                scene = Scene(core, engine, host, spec)
                try:
                    scene.draw(4)
                    if control:
                        core.module.mesh_buffer_control(json.dumps({"recreate_streams": True}))
                    first, counters_first = core.composite_live(), core.process_counters()
                    started = time.perf_counter()
                    budget = STEADY_SECONDS.get(name, STEADY_OTHER_SECONDS)
                    drawn, private = 0, []
                    while (drawn < STEADY_CONTROL_FRAMES) if control else (time.perf_counter() - started < budget):
                        scene.draw(1)
                        drawn += 1
                        if drawn % 2000 == 0:
                            private.append(round(core.process_counters().get("private_mib", 0.0), 2))
                    seconds = time.perf_counter() - started
                    last, counters_last = core.composite_live(), core.process_counters()
                    if control:
                        core.module.mesh_buffer_control(json.dumps({"recreate_streams": False}))
                    created = last["mesh_buffers_buffers_created"] - first["mesh_buffers_buffers_created"]
                    flat = all(last.get(k) == first.get(k) for k in ("mesh_buffers_meshes", "mesh_buffers_mesh_bytes",
                                                                    "mesh_buffers_streams", "mesh_buffers_stream_bytes",
                                                                    "mesh_buffers_arenas", "mesh_buffers_arena_bytes",
                                                                    "mode_resources", "mode_sources", "items"))
                    label = f"{name}{'_control' if control else ''}"
                    # Private memory over the run (MiB): the first sample after warm-up against the last; QRhi's
                    # and the driver's heaps are in it (choice I: reported, not counted).
                    facts[label] = {"frames": drawn, "seconds": round(seconds, 2), "buffers_created": created,
                                    "private_mib_samples": private[:3] + private[-3:],
                                    "stream_writes": last["mesh_buffers_stream_writes"]
                                    - first["mesh_buffers_stream_writes"],
                                    "stream_bytes_written": last["mesh_buffers_stream_bytes_written"]
                                    - first["mesh_buffers_stream_bytes_written"],
                                    "arena_writes": last["mesh_buffers_arena_writes"]
                                    - first["mesh_buffers_arena_writes"],
                                    "private_mib": [counters_first.get("private_mib"),
                                                    counters_last.get("private_mib")],
                                    "handles": [counters_first.get("handles"), counters_last.get("handles")]}
                    if control:
                        checks[f"{label}_streams_made_again_grow_the_count"] = created >= drawn // 2
                    else:
                        checks[f"{label}_no_buffer_created"] = created == 0
                        checks[f"{label}_counts_flat"] = flat
                        checks[f"{label}_every_record_written"] = facts[label]["arena_writes"] >= drawn // 2
                finally:
                    _close(scene, host, app)
    finally:
        host.close()
        host_check._flush_deletes(app)
    return {"pass": all(checks.values()), "checks": checks, "facts": facts}


# --------------------------------------------------------------------------------------------------- retire

def round_retire(core, engine, app, api: str, packs: dict) -> dict:
    from rendering.native.mode import ModePass, ModeTarget, TargetAttachment

    import probe_rings

    checks, facts = {}, {}
    host = _host(core)
    try:
        baseline = core.composite_live()
        spec = spec_for("box", packs, api)
        scene = Scene(core, engine, host, spec)
        try:
            scene.draw(3)
            held = core.composite_live()
            # A mesh replaced: uploaded at the next record, the old one released after it.
            scene.mode.mesh("box", spec.meshes[0][1], spec.meshes[0][2])
            scene.draw(3)
            replaced = core.composite_live()
            pixels = scene.pixels(app)
            facts["replaced_lit"] = int((pixels[..., :3].max(axis=2) > 8).sum())
            # Removed: the content draws nothing (the mesh is lost) and holds none.
            scene.mode.remove_mesh("box")
            scene.draw(3)
            removed = core.composite_live()
            facts["removed_reason"] = scene.mode.state().get("last_reason")
            # A program without geometry: streams and the content's own buffers go with the old build.
            flat = probe_rings.bake("#version 440\nlayout(location = 0) out vec4 fragColor;\nlayout(std140, binding = 18) "
                                    "uniform Flat { vec4 u_flat; };\nvoid main() { fragColor = u_flat; }\n",
                                    "flat.frag", _scratch())
            scene.mode.unbind()
            scene.mode.program((ModePass("flat", flat, "replace", target="scene"),), {"u_flat": [0.2, 0.3, 0.4, 1.0]},
                               targets=(ModeTarget("scene", (TargetAttachment("colour", "rgba8"),)),))
            scene.mode.still()
            scene.mode.update()
            host.frames(3)
            plain = core.composite_live()
        finally:
            _close(scene, host, app)
        gone = core.composite_live()
        # Destroyed between an upload and its first draw: the mesh sent, the item gone before a record.
        scene = Scene(core, engine, host, spec)
        _close(scene, host, app)
        early = core.composite_live()
        # The control: a release that skips the meshes (they are counted left behind).
        core.module.mesh_buffer_control(json.dumps({"skip_mesh_release": True}))
        try:
            scene = Scene(core, engine, host, spec)
            try:
                scene.draw(3)
            finally:
                _close(scene, host, app)
            control = core.composite_live()
        finally:
            core.module.mesh_buffer_control(json.dumps({"skip_mesh_release": False}))
    finally:
        host.close()
        host_check._flush_deletes(app)
    keys = ("mesh_buffers_meshes", "mesh_buffers_mesh_bytes", "mesh_buffers_mesh_images", "mesh_buffers_streams",
            "mesh_buffers_stream_bytes", "mesh_buffers_arenas", "mesh_buffers_arena_bytes")
    pick = (lambda d: {k: d.get(k) for k in keys + ("mode_resources", "mode_sources")})
    facts.update({"baseline": pick(baseline), "held": pick(held), "replaced": pick(replaced), "removed": pick(removed),
                  "plain": pick(plain), "gone": pick(gone), "early": pick(early), "control": pick(control)})
    checks["held_while_drawn"] = held["mesh_buffers_meshes"] >= 1 and held["mesh_buffers_streams"] >= 1
    checks["replaced_holds_one_mesh_and_draws"] = (replaced["mesh_buffers_meshes"] == held["mesh_buffers_meshes"]
                                                   and facts["replaced_lit"] > 200)
    checks["removed_releases_the_mesh"] = removed["mesh_buffers_meshes"] == held["mesh_buffers_meshes"] - 1
    checks["removed_reason_names_the_mesh"] = "box" in str(facts.get("removed_reason"))
    # The built-in quad is made only for a program that draws it: the box and the flat program hold none.
    checks["no_builtin_quad_unless_drawn"] = held["mesh_buffers_meshes"] == 1 and plain["mesh_buffers_meshes"] == 0
    checks["a_program_without_geometry_releases_the_streams"] = plain["mesh_buffers_streams"] == 0
    checks["destruction_leaves_nothing"] = all(gone.get(k) == 0 for k in keys)
    checks["destroyed_before_its_first_draw_leaves_nothing"] = all(early.get(k) == 0 for k in keys)
    checks["control_skipped_release_leaves_the_mesh"] = control["mesh_buffers_meshes"] > 0
    return {"pass": all(checks.values()), "checks": checks, "facts": facts}


_SCRATCH: list = []


def _scratch() -> Path:
    import tempfile

    if not _SCRATCH:
        _SCRATCH.append(tempfile.TemporaryDirectory(prefix="srpss_n32_"))
    return Path(_SCRATCH[0].name)


# --------------------------------------------------------------------------------------------------- cost

def _summary(times: list[int]) -> dict:
    times = sorted(times)
    if not times:
        return {"samples": 0, "median_ms": None, "p90_ms": None, "p10_ms": None}
    return {"samples": len(times), "median_ms": round(times[len(times) // 2] / 1e6, 4),
            "p90_ms": round(times[int(len(times) * 0.9)] / 1e6, 4), "p10_ms": round(times[int(len(times) * 0.1)] / 1e6, 4)}


def _timed(host, scene, *, min_samples: int = COST_MIN_SAMPLES, frames: int = RING_FRAMES) -> dict:
    """GPU time (the surface figure) and the frame's wall time, over at least ``frames`` new records and until
    ``min_samples`` GPU times are read (bounded by COST_MAX_FRAMES)."""
    host.set_gpu_timer(True)
    scene.draw(4)
    host.gpu_samples()
    gpu: list[int] = []
    wall: list[float] = []
    record_ms: list[float] = []      # the render thread's record (the core's own timer), mean per window of 20
    write_ms: list[float] = []       # its stream and arena writes alone
    drawn = 0

    def live() -> dict:
        raw = scene.mode._module.composite_live()
        return json.loads(raw) if isinstance(raw, str) else dict(raw)

    last = core_counts = live()
    timed = "mesh_buffers_records_timed" in core_counts
    while drawn < COST_MAX_FRAMES and (drawn < frames or len(gpu) < min_samples):
        scene.publish()
        scene.mode.update()
        started = time.perf_counter()
        host.frames(1)
        wall.append((time.perf_counter() - started) * 1000.0)
        drawn += 1
        if drawn % 20 == 0:
            gpu += [s.nanoseconds for s in host.gpu_samples() if s.kind == 2]
            if timed:
                now = live()
                records = now["mesh_buffers_records_timed"] - last["mesh_buffers_records_timed"]
                if records > 0:
                    record_ms.append((now["mesh_buffers_record_ns"] - last["mesh_buffers_record_ns"]) / records / 1e6)
                    write_ms.append((now["mesh_buffers_stream_write_ns"] - last["mesh_buffers_stream_write_ns"])
                                    / records / 1e6)
                last = now
    host.frames(4)
    gpu += [s.nanoseconds for s in host.gpu_samples() if s.kind == 2]
    host.set_gpu_timer(False)
    wall.sort()
    result = _summary(gpu)
    result.update({"frames": drawn, "wall_median_ms": round(wall[len(wall) // 2], 4),
                   "wall_p10_ms": round(wall[int(len(wall) * 0.1)], 4)})
    if record_ms:
        record_ms.sort()
        write_ms.sort()
        result.update({"record_cpu_median_ms": round(record_ms[len(record_ms) // 2], 4),
                       "record_cpu_p10_ms": round(record_ms[int(len(record_ms) * 0.1)], 4),
                       "write_cpu_median_ms": round(write_ms[len(write_ms) // 2], 4)})
    return result


def round_cost(core, engine, app, api: str, packs: dict) -> dict:
    mb = _scenes()
    checks, facts = {}, {}
    for size in COST_HOSTS:
        dpr = size[0] / mb.CARD[0]
        label = f"{size[0]}x{size[1]}"
        facts[label] = {}
        host = _host(core, dpr)
        try:
            for name in COST_SCENES:
                for loop in ((False, True) if name == "cells" else (False,)):
                    if loop:
                        core.module.mesh_buffer_control(json.dumps({"hide_draw_parameters": True}))
                    scene = Scene(core, engine, host, spec_for(name, packs, api), dpr=dpr)
                    try:
                        key = name + ("_loop" if loop else "")
                        facts[label][key] = _timed(host, scene, frames=COST_FRAMES)
                        state = scene.mode.state()
                        facts[label][key]["last_reason"] = state.get("last_reason")
                        checks[f"{label}_{key}_timed"] = facts[label][key]["samples"] >= COST_MIN_SAMPLES
                    finally:
                        _close(scene, host, app)
                        if loop:
                            core.module.mesh_buffer_control(json.dumps({"hide_draw_parameters": False}))
        finally:
            host.close()
            host_check._flush_deletes(app)
    return {"pass": all(checks.values()), "checks": checks, "facts": facts}


def _copy_ms(size: int, repeats: int = 400) -> float:
    """One copy of ``size`` bytes into a buffer already allocated and touched (the median of ``repeats``), ms."""
    import numpy as np

    source = np.frombuffer(bytes(range(256)) * (size // 256 + 1), np.uint8)[:size].copy()
    target = np.empty_like(source)
    np.copyto(target, source)
    times = []
    for _ in range(repeats):
        started = time.perf_counter_ns()
        np.copyto(target, source)
        times.append(time.perf_counter_ns() - started)
    times.sort()
    return round(times[len(times) // 2] / 1e6, 4)


def round_stream_ring(core, engine, app, api: str, packs: dict, only=None) -> dict:
    """D15 point 7: each payload through QRhi's routes against the pair's floor (module notes)."""
    mb = _scenes()
    checks, facts = {}, {}
    host = _host(core)
    try:
        payloads = (("none", 0, None),) + tuple((label, size, None) for label, size in RING_PAYLOADS) + (RING_PARTIAL,)
        for label, size, used in payloads:
            if only and label not in only and label != "none":
                continue
            entry = {}
            kinds = ("none",) if size == 0 else (("storage", "floor") if used is not None else
                                                 ("instance", "storage", "floor"))
            for kind in kinds:
                spec = mb.ring_scene(packs, size // 4, kind, used_floats=used if kind == "storage" else None)
                scene = Scene(core, engine, host, spec)
                try:
                    entry[kind] = _timed(host, scene)
                    entry[kind]["last_reason"] = scene.mode.state().get("last_reason")
                finally:
                    _close(scene, host, app)
            facts[label] = entry
            if size == 0:
                continue
            floor = entry["floor"]
            # The CPU axis: the render thread's record (the core's timer) where the module counts it, else the frame's
            # wall time on the GUI thread (a module before the counter: noisier, the whole frame).
            first = entry.get("instance") or entry["storage"]
            cpu_key = "record_cpu_median_ms" if "record_cpu_median_ms" in first else "wall_median_ms"
            if cpu_key == "record_cpu_median_ms":
                # The pair's CPU floor: the record with the data resident (the floor scene) plus one copy of the
                # payload into memory already mapped (timed here, the copy a persistent mapping would cost). Not the
                # instance route's own write: on OpenGL QRhi's Dynamic fast path is itself a buffer update call. A
                # partial payload's floor copies only its used bytes.
                copy_ms = _copy_ms(4 * used if used is not None else size)
                cpu_floor = floor[cpu_key] + copy_ms
                entry["cpu_floor_ms"] = {"floor_record_ms": floor[cpu_key], "payload_copy_ms": copy_ms,
                                         "floor_ms": round(cpu_floor, 4)}
            else:
                cpu_floor = first[cpu_key]
            entry["cpu_axis"] = cpu_key
            if used is not None:
                entry["used_bytes"] = 4 * used
            for route in [r for r in ("instance", "storage") if r in entry]:
                got = entry[route]
                ok_gpu = (got["median_ms"] is not None and floor["median_ms"] is not None
                          and got["median_ms"] - floor["median_ms"] < FLOOR_MARGIN_MS)
                ok_cpu = got[cpu_key] - cpu_floor < FLOOR_MARGIN_MS
                entry[f"{route}_within_floor"] = {"gpu": ok_gpu, "cpu": ok_cpu}
                checks[f"{label}_{route}_within_0.05ms_of_the_floor"] = ok_gpu and ok_cpu
    finally:
        host.close()
        host_check._flush_deletes(app)
    return {"pass": all(checks.values()), "checks": checks, "facts": facts}


# --------------------------------------------------------------------------------------------------- the child

def child(args) -> dict:
    root = host_check._root(args.repo)
    out = Path(args.out_dir)
    record: dict = {"api": args.api, "rounds": list(args.rounds), "module_loaded": False, "instance_created": False}
    if args.api in ("opengl", "reference"):
        from rendering.quick.bootstrap import configure_quick_graphics

        configure_quick_graphics(reason="mesh-buffer-check")
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
    packs = load_packs(out)
    bake_facts = json.loads((_work(out) / "packs" / "bake_facts.json").read_text(encoding="utf-8"))
    try:
        if args.api == "reference":
            record["reference"] = round_reference(core, packs, out)
            record["rounds"] = ["reference"]
        else:
            for name in args.rounds:
                if vulkan:
                    core.set_vulkan_phase(f"n32 {name}")
                try:
                    if name == "parity":
                        record[name] = round_parity(core, engine, app, args.api, packs, out)
                    elif name == "forms":
                        record[name] = round_forms(core, engine, app, args.api, packs, bake_facts)
                    elif name == "rest":
                        record[name] = round_rest(core, engine, app, args.api, packs)
                    elif name == "steady":
                        record[name] = round_steady(core, engine, app, args.api, packs)
                    elif name == "retire":
                        record[name] = round_retire(core, engine, app, args.api, packs)
                    elif name == "cost":
                        record[name] = round_cost(core, engine, app, args.api, packs)
                    elif name == "stream_ring":
                        record[name] = round_stream_ring(core, engine, app, args.api, packs, args.ring_payloads)
                    elif name == "used":
                        record[name] = round_used(core, engine, app, args.api, packs)
                except Exception:
                    record[name] = {"pass": False, "error": traceback.format_exc()}
    finally:
        host_check._flush_deletes(app)
        record["live_hosts_at_end"] = core.live_hosts()
        record["composites_at_end"] = core.composite_live()
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
        for holder in _SCRATCH:
            holder.cleanup()
    return record


def api_verdict(api: str, record: dict, require_validation: bool) -> tuple[bool, list[str]]:
    if api == "reference":
        entry = record.get("reference") or {}
        return bool(entry.get("pass")), ([] if entry.get("pass") else
                                         [f"reference: {(entry.get('error') or record.get('error') or 'failed')[-1500:]}"])
    ok, failed = host_check.api_verdict(api, record, require_validation)
    if record.get("module_loaded") and (api != "vulkan" or record.get("instance_created")):
        live = record.get("composites_at_end") or {}
        left = {k: live.get(k) for k in ("items", "mode_sources", "mode_resources", "mesh_buffers_streams",
                                         "mesh_buffers_arenas") if live.get(k)}
        # The retire round's control leaves its meshes behind by design (counted); nothing else may be left.
        if left:
            failed.append(f"{api}: left at the end ({left})")
    return not failed, failed


def _gpu_conditions() -> dict:
    smi = shutil.which("nvidia-smi")
    if not smi:
        return {"nvidia_smi": None}
    try:
        text = subprocess.run([smi, "--query-gpu=utilization.gpu,clocks.gr,memory.used,display_active",
                               "--format=csv,noheader"], capture_output=True, text=True, timeout=20).stdout.strip()
    except Exception as exc:  # noqa: BLE001
        text = f"error: {exc}"
    return {"nvidia_smi": text, "at": time.strftime("%H:%M:%S")}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--module-dir", default="release/native_module")
    parser.add_argument("--repo", default=".", help="the repository root (default: the current directory)")
    parser.add_argument("--apis", nargs="+", default=list(APIS), choices=APIS)
    parser.add_argument("--rounds", nargs="+", default=list(ROUNDS), choices=ROUNDS)
    parser.add_argument("--label", default="n32_mesh_buffers")
    parser.add_argument("--ring-payloads", nargs="+", default=None,
                        choices=[label for label, _size in RING_PAYLOADS] + [RING_PARTIAL[0]],
                        help="stream_ring: only these payloads (default: every one)")
    parser.add_argument("--layer-path", type=Path, default=None,
                        help="the folder holding VkLayer_khronos_validation.json (VK_ADD_LAYER_PATH for this run only)")
    parser.add_argument("--require-validation", action="store_true",
                        help="a Vulkan run whose validation layer did not load is a FAIL, never a pass")
    parser.add_argument("--child", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--api", choices=(*APIS, "reference"), help=argparse.SUPPRESS)
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

    out = artifact_paths.evidence_dir("native_core", "n3_2", args.label)
    out.mkdir(parents=True, exist_ok=True)
    environment = vk_validation.environment_record(_ALLOWED_ENV)
    conditions = {"before": _gpu_conditions()}
    bake = bake_packs(out)
    results: dict = {}
    children = [a for a in APIS if a in args.apis]
    if "parity" in args.rounds and "opengl" in args.apis:
        children.append("reference")
    for api in children:
        child_json = out / f"child_{api}.json"
        command = [sys.executable, str(Path(__file__).resolve()), "--child", "--api", api, "--repo", str(root),
                   "--module-dir", args.module_dir, "--out-dir", str(out), "--child-json", str(child_json),
                   "--rounds", *args.rounds] + (["--ring-payloads", *args.ring_payloads] if args.ring_payloads else [])
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
    conditions["after"] = _gpu_conditions()

    verdicts = {api: api_verdict(api, record, args.require_validation) for api, record in results.items()}
    failed = [reason for _ok, reasons in verdicts.values() for reason in reasons]
    cross = None
    if "parity" in args.rounds:
        cross = cross_compare(out)
        for rule in ("rule_a", "rule_b", "control_offset_stream_differs"):
            needed = {"rule_a": "opengl" in args.apis, "control_offset_stream_differs": "opengl" in args.apis,
                      "rule_b": "vulkan" in args.apis and "opengl" in args.apis}[rule]
            if needed and not (cross.get(rule) or {}).get("pass"):
                compared = (cross.get(rule) or {}).get("compared") or {}
                failed.append(f"{rule}: " + json.dumps({k: v for k, v in compared.items() if not v.get("exact")}
                                                        or cross.get(rule))[:1500])
    if not environment["clean"]:
        failed.append(f"environment: {', '.join(environment['contaminating_set'])} set")
    summary = {"apis": args.apis, "rounds": args.rounds, "environment": environment, "gpu_conditions": conditions,
               "bake": bake, "require_validation": args.require_validation, "cross": cross,
               "verdicts": {api: {"pass": ok, "failed": reasons} for api, (ok, reasons) in verdicts.items()},
               "results": results, "pass": not failed}
    (out / "summary.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    for api, (ok, reasons) in verdicts.items():
        print(f"{api}: {'PASS' if ok else 'FAIL'}" + ("" if ok else " (" + "; ".join(reasons)[:2000] + ")"))
    if cross is not None:
        print("cross: " + json.dumps({rule: v.get("pass") for rule, v in cross.items() if isinstance(v, dict)
                                      and "pass" in v}))
    print(f"evidence: {out / 'summary.json'} (the work folder holds the frames and packs: delete it once judged)")
    print("N32 VERDICT " + ("PASS" if not failed else "FAIL: " + "; ".join(failed)[:4000]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
