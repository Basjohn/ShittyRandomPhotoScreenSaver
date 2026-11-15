"""N3.3's proof of the native core's compute passes (Current_Plan.md item 8b, N3.3; decision D16;
``native/core/src/compute_passes.h``), through ``rendering.native``, on the harness-only scenes
``native/core/python/compute_passes`` (compute entries, storage buffers and images, and the draws that read them).

The module (``release/native_module``, built on GitHub) is loaded the product's way in one child process per graphics
API (OpenGL, then Vulkan on the module's own instance and device, D6), and the Python reference in a child of its own
(an offscreen OpenGL context, the production GL host's compute calls: ``glDispatchCompute``, ``glBindImageTexture``,
``glMemoryBarrier``). No window is ever visible. Every storage result is read back by the harness only.

Rounds:
  facts      (parent) every pack's ``qsb -d`` reflection: the storage blocks' readonly/writeonly qualifiers, the images'
             flags and formats (D16 choice D's open fact); (each API) the admission refusals they drive (a readonly block
             declared written, a writeonly block declared read, a written block declared read, a writeonly image
             declared read, an image of another format, a 2D image bound to an image3D, an unbound block, one buffer
             bound twice with two accesses: checkpoint audit 5 M3) and the one program taken; the device's compute
             facts.
  parity     (each API; and the reference) field, chain, volume (3D images, per-slice readback: D16's second open fact)
             and population, storage read back after three records: rule (a) native OpenGL against the reference, rule
             (b) native Vulkan against native OpenGL, exact (a difference is reported with its ULP distance); a
             negative control (one input changed) must differ. The scenes' pixels (the draws reading the storage) under
             rule (b); the indirect draw equals the direct draw of the same members; the command equals the CPU's count.
             D4's pair-check kernel (audit 5 M4) through the core's bake equals exact arithmetic on each API and under
             rule (b); its control (the error terms precise keeps, zeroed) must not.
  trigger    (each API) a frame trigger dispatches once per accepted record and never for a card, settings or readback
             re-record; a field trigger only when its field changes; the state after 200 records equals a CPU
             reference, and the control (every record dispatched) integrates more and differs; a node made again
             dispatches fresh and tells the owner once (on_state_lost); the same program sent again, and an image no
             entry of the state binds made again, keep the entries' history (audit 5 M2).
  war        (each API) write-after-read: entry 1 reads X and writes Y, entry 2 writes X: Y holds the earlier X; the
             ping-pong form (audit 5 M4): entry 1 reads A and writes B, entry 2 reads B and writes A, each one past
             what it read.
  copy       (each API) a created buffer and image read zero; a resized buffer keeps its prefix bit-exact and reads
             zero past it.
  rest       (each API) a minute at rest: no compute pass, no dispatch, no object; control: a record every frame.
  steady     (each API) new records for a while: no storage object created.
  retire     (each API) the item destroyed, a program without storage after one holding an image and after one holding
             buffers (audit 5 M1), a destroy between a resize's allocation and its copy: storage back to zero; control:
             the release skipping the storage (counted left behind).
  barriers   (each API; on Vulkan under synchronisation validation) consecutive records of every scene with no readback
             between them (phase "n33 barriers": clean, the ping-pong included); the controls in their own phases:
             written bindings recorded as reads ("n33 control write_as_read": SYNC-HAZARD-READ-AFTER-WRITE) and the
             write-after-read pair in one QRhi pass ("n33 control single_pass": SYNC-HAZARD-WRITE-AFTER-READ); in a
             Vulkan child of its own (the layer reports an id at most 10 times an instance), the ping-pong in one QRhi
             pass (a fact phase) and its control ("n33 control pingpong write_as_read":
             SYNC-HAZARD-WRITE-AFTER-READ). On OpenGL the same
             records' values. OpenGL's glMemoryBarrier calls are not counted: QRhi makes them inside its GL backend
             through resolved function pointers no public API counts (D16's as-built says why).
  cost       (each API; and the reference) GPU time (the content's whole record) median and p90 at 2560x1440 and
             3840x2160 for Waveform's fogged-frame shape (a 128x72x32 volume and the fields) and the drift's (216,000
             state rows), against the Python path's dispatches on the same load (GL_TIME_ELAPSED); the record's
             render-thread time; the thread probe.

Usage (repository venv, from the checkout holding the built module):
  python native/core/python/compute_pass_check.py --module-dir release/native_module --require-validation
      --layer-path D:\\Temp\\Scratch\\SRPSS\\native_spike\\validation_layers\\extracted
  [--apis opengl vulkan] [--rounds facts parity trigger war copy rest steady retire barriers cost] [--label n33_compute]
Evidence: .artifacts/evidence/native_core/n3_3/<date>_<label>/ (summary.json). Exit 0 whenever the harness ran; the
verdict is the last printed line ("N33 VERDICT PASS" or "N33 VERDICT FAIL: ...").
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
from dataclasses import replace
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import vk_validation  # noqa: E402  (native/core/python)
import host_check  # noqa: E402
import mesh_buffer_check as mbc  # noqa: E402  (its stream, scene host and timing helpers)

APIS = ("opengl", "vulkan")
ROUNDS = ("facts", "parity", "trigger", "war", "copy", "rest", "steady", "retire", "barriers", "cost")
CHILD_TIMEOUT_S = 2400
PARITY_SCENES = ("field", "chain", "volume", "population")
PARITY_RECORDS = 3
TRIGGER_RECORDS = 200
REST_SECONDS = 60.0
STEADY_SECONDS = 10.0
BARRIER_RECORDS = 40
COST_HOSTS = ((2560, 1440), (3840, 2160))
COST_FRAMES = 240
COST_SCENES = {"waveform": dict(volume=(128, 72, 32)), "drift": dict(state_rows=216000),
               "population": dict(population=262144)}
CONTROL_PHASES = {"n33 control write_as_read": "SYNC-HAZARD-READ-AFTER-WRITE",
                  "n33 control single_pass": "SYNC-HAZARD-WRITE-AFTER-READ",
                  # Checkpoint audit 5 M4: the ping-pong's write-after-read is barriered only because QRhi knows A is
                  # written; recorded as read, it is not.
                  "n33 control pingpong write_as_read": "SYNC-HAZARD-WRITE-AFTER-READ"}
# Which round runs each control phase. The layer reports one message id at most 10 times an instance (its duplicate
# message limit): once the single-pass control has used SYNC-HAZARD-WRITE-AFTER-READ's ten, a later phase in the same
# process reports none (audit 5 run, 15 Nov). So the ping-pong's phases run in a Vulkan child of their own
# (the "pingpong" round, added whenever the barriers round runs on Vulkan), its fact phase first.
CONTROL_ROUNDS = {"n33 control write_as_read": "barriers", "n33 control single_pass": "barriers",
                  "n33 control pingpong write_as_read": "pingpong"}
# Phases recorded as facts, neither clean nor a control: the ping-pong in one QRhi pass (expected clean: QRhi's in-pass
# read-after-write barrier on B is a compute-to-compute execution dependency that also orders A's write after its read).
FACT_PHASES = ("n33 fact single_pass pingpong",)
_ALLOWED_ENV: set[str] = set()


def _scenes():
    import compute_passes

    return compute_passes


def _work(out: Path) -> Path:
    path = out / "work"
    path.mkdir(parents=True, exist_ok=True)
    return path


# --------------------------------------------------------------------------------------------------- the packs

def bake_packs(out: Path) -> dict:
    """Every scene shader baked once (the parent); each compute pack's qsb reflection kept (the qualifier facts)."""
    cp = _scenes()
    folder = _work(out) / "packs"
    folder.mkdir(parents=True, exist_ok=True)
    packs = cp.bake_all(folder / "src")
    facts = {}
    for name, data in packs.items():
        path = folder / f"{name}.qsb"
        path.write_bytes(data)
        if name.endswith(".comp"):
            reflected = cp.reflection(path)
            facts[name] = {
                "storage_blocks": {b["blockName"]: b.get("qualifierFlags", 0) for b in reflected.get("storageBlocks", [])},
                "storage_images": {i["name"]: {"flags": i.get("imageFlags", 0), "format": i.get("imageFormat"),
                                               "type": i.get("type")} for i in reflected.get("storageImages", [])},
                "local_size": reflected.get("computeLocalSize")}
    (folder / "bake_facts.json").write_text(json.dumps(facts, indent=1), encoding="utf-8")
    return facts


def qualifier_facts(bake: dict) -> dict:
    """D16's first open fact, from the packs' reflection: readonly (1) and writeonly (2) are recorded for storage blocks
    and images, and an unqualified block records 0."""
    blocks = {f"{n}.{b}": q for n, f in bake.items() for b, q in f["storage_blocks"].items()}
    images = {f"{n}.{i}": v for n, f in bake.items() for i, v in f["storage_images"].items()}
    return {
        "readonly_block_recorded": blocks.get("refusal.comp.In") == 1,
        "writeonly_block_recorded": blocks.get("refusal.comp.Out") == 2,
        "unqualified_block_records_none": blocks.get("refusal.comp.Both") == 0,
        "writeonly_image_recorded": (images.get("refusal.comp.uVol") or {}).get("flags") == 2,
        "readonly_image_recorded": (images.get("blur.comp.uSections") or {}).get("flags") == 1,
        # Qt 6.12.0's dump names ImageFormatRgba16f "rgba16" (qshaderdescription.cpp imageFormatTab); the enum the core
        # reads is the right one (the volume's rgba16f images are admitted below).
        "rgba16f_dump_name": (images.get("refusal.comp.uVol") or {}).get("format"),
    }


def load_packs(out: Path) -> dict:
    folder = _work(out) / "packs"
    return {p.name[:-4]: p.read_bytes() for p in folder.glob("*.qsb")}


# --------------------------------------------------------------------------------------------------- the scene

class Scene(mbc.Scene):
    """mesh_buffer_check's scene host with a compute program (its buffers and images); a scene without targets draws
    into nothing the harness reads but its storage."""

    def __init__(self, core, engine, host, spec, *, dpr: float = 1.0) -> None:
        from PySide6.QtCore import QUrl
        from PySide6.QtQml import QQmlComponent
        from PySide6.QtQuick import QQuickItem

        self.host = host
        self.spec = spec
        self.card = _scenes().CARD
        self.dpr = float(dpr)
        self.component = QQmlComponent(engine)
        self.component.setData(mbc.SCENE_QML, QUrl())
        self.root = self.component.create()
        if self.root is None:
            raise RuntimeError(f"the scene did not load: {self.component.errorString()}")
        self.content = self.root.findChild(QQuickItem, "contentHost")
        host.set_content(self.root)
        self.mode = core.mode(self.content)
        self.mode.composite.set(rect=[0.0, 0.0, float(self.card[0]), float(self.card[1])], coverage=None, quarters=0,
                                visible=True)
        self.mode.card(mbc._card(self.card, self.dpr))
        self.stream = None
        try:
            self.mode.program(spec.passes, spec.settings, targets=spec.targets, streams=spec.streams,
                              buffers=spec.buffers, images=spec.images)
            self.stream = mbc.Stream(spec.schema)
            self.mode.bind(self.stream.name, spec.schema, expect=self.stream.expect)
        except Exception:
            if self.stream is not None:
                self.stream.close()
            self.mode.composite.destroy()
            host.set_content(None)
            raise
        self.values = dict(spec.record)
        self.step = 0

    def storage(self, app, timeout_s: float = 10.0) -> dict:
        """Every storage resource as the last record left it (the readback's record dispatches nothing): name ->
        (kind, format, size, bytes)."""
        self.mode.read_storage()
        deadline = time.monotonic() + timeout_s
        got = None
        while got is None and time.monotonic() < deadline:
            self.host.frames(1)
            got = self.mode.storage_data()
        if got is None:
            raise RuntimeError(f"the storage readback did not complete ({self.mode.state().get('last_reason')})")
        return {g["name"]: (g["kind"], g["format"], tuple(g["size"]), bytes(g["data"])) for g in got}


def _close(scene, host, app) -> None:
    mbc._close(scene, host, app)


def _live(core) -> dict:
    return core.composite_live()


def _delta(after: dict, before: dict, key: str) -> float:
    return (after.get(key) or 0) - (before.get(key) or 0)


def _records(scene, frames: int, *, change=None) -> None:
    """``frames`` new records, one frame each (``change(i)`` gives each record's changed values)."""
    for i in range(frames):
        scene.draw(1, **(change(i) if change else {}))


def spec_for(name: str, packs: dict, **options):
    return _scenes().scene(name, packs, **options)


def _record_values(name: str, frame: int) -> dict:
    cp = _scenes()
    values = {"u_frame": float(frame)}
    if name in ("field", "chain"):
        values["knot_rows"] = struct.pack(f"<{4 * cp.KNOTS}f", *cp.knots(frame))
    if name == "volume":
        values["u_phase"] = 0.125 * (frame % 4)
    return values


# --------------------------------------------------------------------------------------------------- comparison

_FLOATS = {"rgba32f": ("<f4", 4), "r32f": ("<f4", 4), "rgba16f": ("<f2", 2), "r16f": ("<f2", 2), "bytes": ("<f4", 4)}


def compare_storage(a: dict, b: dict) -> dict:
    """Each resource of ``a`` against ``b``: exact, or the count of differing values and their largest ULP distance."""
    import numpy as np

    out = {}
    for name, (kind, fmt, size, data) in a.items():
        other = b.get(name)
        if other is None:
            out[name] = {"exact": False, "missing": True}
            continue
        if other[3] == data:
            out[name] = {"exact": True, "bytes": len(data)}
            continue
        dtype, width = _FLOATS.get(fmt, ("<u1", 1))
        n = min(len(data), len(other[3])) // width
        x = np.frombuffer(data[:n * width], dtype)
        y = np.frombuffer(other[3][:n * width], dtype)
        ints = "<i4" if width == 4 else "<i2"
        ulp = np.abs(x.view(ints).astype(np.int64) - y.view(ints).astype(np.int64))
        differ = np.flatnonzero(x.view(ints) != y.view(ints))
        out[name] = {"exact": False, "bytes": [len(data), len(other[3])], "values_differing": int(differ.size),
                     "max_ulp": int(ulp.max()) if ulp.size else None,
                     "first": [[int(i), float(x[i]), float(y[i])] for i in differ[:6]]}
    return out


def _pixels_equal(a, b) -> dict:
    return mbc._compare(a, b)


# --------------------------------------------------------------------------------------------------- facts

def round_facts(core, engine, app, api: str, packs: dict) -> dict:
    """D16 choice D on the module: every refusal the reflection drives, and the program the core takes."""
    cp = _scenes()
    checks, facts = {}, {}
    host = mbc._host(core)
    try:
        from PySide6.QtCore import QUrl
        from PySide6.QtQml import QQmlComponent
        from PySide6.QtQuick import QQuickItem

        component = QQmlComponent(engine)
        component.setData(mbc.SCENE_QML, QUrl())
        root = component.create()
        host.set_content(root)
        mode = core.mode(root.findChild(QQuickItem, "contentHost"))
        try:
            for label, (entry, buffers, images) in cp.refusal_programs(packs).items():
                try:
                    mode.program((entry,), {"u_a": [1.0, 0.0, 0.0, 0.0]}, buffers=buffers, images=images)
                    facts[label] = "taken"
                except ValueError as exc:
                    facts[label] = f"refused: {exc}"
            checks["the_qualified_program_is_taken"] = facts["accepted"] == "taken"
            for label in facts:
                if label != "accepted":
                    checks[f"{label}_is_refused"] = facts[label].startswith("refused")
            state = mode.state()
            facts["program_compute"] = [p.get("compute") for p in state.get("program", {}).get("passes", [])]
        finally:
            mode.composite.destroy()
            host.set_content(None)
            host_check._drop_item(app, root)
        # The device's compute facts, as the storage state notes them at its first edge.
        scene = Scene(core, engine, host, spec_for("field", packs))
        try:
            scene.draw(2)
            storage = scene.mode.state().get("storage") or {}
            facts["device"] = storage.get("device")
            checks["the_device_reports_compute"] = bool((facts["device"] or {}).get("compute"))
        finally:
            _close(scene, host, app)
    finally:
        host.close()
        host_check._flush_deletes(app)
    return {"pass": all(checks.values()), "checks": checks, "facts": facts}


# --------------------------------------------------------------------------------------------------- parity

def round_parity(core, engine, app, api: str, packs: dict, out: Path) -> dict:
    import numpy as np

    cp = _scenes()
    checks, facts, storage, frames = {}, {}, {}, {}
    host = mbc._host(core)
    try:
        for name in PARITY_SCENES + ("population_direct",):
            scene = Scene(core, engine, host, spec_for(name, packs))
            try:
                for frame in range(PARITY_RECORDS):
                    scene.draw(1, **_record_values(name, frame))
                storage[name] = scene.storage(app)
                frames[name] = scene.pixels(app)
                state = scene.mode.state()
                facts[name] = {"last_reason": state.get("last_reason"), "storage": state.get("storage"),
                               "lit": int((frames[name][..., :3].max(axis=2) > 8).sum())}
                checks[f"{name}_draws"] = facts[name]["lit"] > 100
            finally:
                _close(scene, host, app)
        # The negative control: one input changed (the knots of another frame) must change the field.
        scene = Scene(core, engine, host, spec_for("field", packs))
        try:
            for frame in range(PARITY_RECORDS - 1):
                scene.draw(1, **_record_values("field", frame))
            scene.draw(1, **_record_values("field", PARITY_RECORDS + 5))
            control = scene.storage(app)
        finally:
            _close(scene, host, app)
        # Checkpoint audit 5 M4: D4's pair-check kernel (precise) through the core's own bake, judged against exact
        # arithmetic as the product's warm-up check judges it; under rule (b) with the other scenes. Its control: the
        # error terms a compiler that drops precise may lose, zeroed.
        for name in ("pair_check", "pair_check_broken"):
            scene = Scene(core, engine, host, spec_for(name, packs))
            try:
                _records(scene, PARITY_RECORDS)
                got = scene.storage(app)
                if name == "pair_check":
                    storage[name] = got
                facts[name] = dict(cp.pair_check_report(got["results"][3]),
                                   last_reason=scene.mode.state().get("last_reason"))
            finally:
                _close(scene, host, app)
    finally:
        host.close()
        host_check._flush_deletes(app)
    checks["the_pair_check_is_exact_through_the_core_bake"] = bool(facts["pair_check"]["exact"])
    checks["control_the_pair_check_without_its_error_terms_is_not"] = bool(
        not facts["pair_check_broken"]["exact"] and facts["pair_check_broken"]["product_mismatches"]
        and facts["pair_check_broken"]["sum_mismatches"])
    checks["control_another_input_differs"] = not compare_storage(control, storage["field"])["field"]["exact"]
    # The population: the command is (vertices, the CPU's live count, 0, 0); the ids are the live members in id order;
    # the indirect draw equals the direct draw of the same members.
    live = cp.live_members(cp.POPULATION)
    command = struct.unpack("<4I", storage["population"]["command"][3][:16])
    ids = np.frombuffer(storage["population"]["ids"][3], "<u4")[:live]
    expected = [i for i in range(cp.POPULATION) if ((i * 2654435761) % (1 << 32) >> 7) % 3 != 0]
    facts["population_command"] = list(command)
    checks["the_command_holds_the_cpu_count"] = command == (4, live, 0, 0)
    checks["the_ids_are_the_live_members_in_order"] = ids.tolist() == expected
    checks["the_indirect_draw_equals_the_direct_draw"] = _pixels_equal(frames["population"],
                                                                       frames["population_direct"])["exact"]
    # D16's second open fact: a 3D image read back slice by slice (every slice, each different from the next).
    kind, fmt, size, data = storage["volume"]["integrated"]
    slice_bytes = size[0] * size[1] * 8
    slices = [data[i * slice_bytes:(i + 1) * slice_bytes] for i in range(size[2])]
    facts["volume_readback"] = {"size": list(size), "bytes": len(data), "slice_bytes": slice_bytes}
    checks["a_3d_image_reads_back_every_slice"] = (len(data) == slice_bytes * size[2]
                                                   and all(slices[i] != slices[i + 1] for i in range(len(slices) - 1)))
    (_work(out) / f"storage_{api}.json").write_text(json.dumps(
        {n: {r: [v[0], v[1], list(v[2]), v[3].hex()] for r, v in s.items()} for n, s in storage.items()}),
        encoding="utf-8")
    np.savez_compressed(_work(out) / f"pixels_{api}.npz", **frames)
    return {"pass": all(checks.values()), "checks": checks, "facts": facts}


def _load_storage(out: Path, api: str) -> dict:
    path = _work(out) / f"storage_{api}.json"
    if not path.exists():
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    return {n: {r: (v[0], v[1], tuple(v[2]), bytes.fromhex(v[3])) for r, v in s.items()} for n, s in raw.items()}


def cross_compare(out: Path) -> dict:
    """Rule (a): native OpenGL against the reference; rule (b): native Vulkan against native OpenGL (storage exact;
    the draws' pixels exact)."""
    import numpy as np

    gl, vk, ref = (_load_storage(out, a) for a in ("opengl", "vulkan", "reference"))
    result: dict = {}
    if gl and ref:
        compared = {n: compare_storage({k: v for k, v in gl[n].items() if k in ref.get(n, {})}, ref.get(n, {}))
                    for n in PARITY_SCENES if n in gl}
        result["rule_a"] = {"pass": all(c["exact"] for s in compared.values() for c in s.values()),
                            "compared": compared}
    if gl and vk:
        compared = {n: compare_storage(vk[n], gl[n]) for n in gl if n in vk}
        pixels = {}
        gp, vp = (_work(out) / "pixels_opengl.npz", _work(out) / "pixels_vulkan.npz")
        if gp.exists() and vp.exists():
            a, b = dict(np.load(gp)), dict(np.load(vp))
            pixels = {k: _pixels_equal(b[k], a[k]) for k in a if k in b}
        result["rule_b"] = {"pass": all(c["exact"] for s in compared.values() for c in s.values())
                            and all(p["exact"] for p in pixels.values()), "compared": compared, "pixels": pixels}
    return result


# --------------------------------------------------------------------------------------------------- the reference

class Reference:
    """The Python owners' compute calls in an offscreen OpenGL context: the same text, the same inputs."""

    def __init__(self, core, packs: dict) -> None:
        from tools.labs.render_target import OffscreenRenderTarget

        self.core = core
        self.packs = packs
        self.target = OffscreenRenderTarget(64, 64, label="n33-reference")
        self.objects: list = []
        self.programs: dict = {}

    def close(self) -> None:
        from OpenGL import GL as gl
        from rendering.quick.render.gl_resources import delete_program

        with self.target.current():
            for kind, name in self.objects:
                if kind == "buffer":
                    gl.glDeleteBuffers(1, [name])
                else:
                    gl.glDeleteTextures(1, [name])
            for program in self.programs.values():
                delete_program(program)
        self.target.close()

    def program(self, name: str) -> int:
        from rendering.quick.render.gl_resources import compile_compute_program

        if name not in self.programs:
            self.programs[name] = compile_compute_program(_scenes().shaders()[name], label=f"n33 {name}")
        return self.programs[name]

    def buffer(self, data: bytes) -> int:
        from OpenGL import GL as gl

        ids = (ctypes.c_uint * 1)()
        gl.glCreateBuffers(1, ids)
        gl.glNamedBufferData(int(ids[0]), len(data), data, gl.GL_DYNAMIC_DRAW)
        self.objects.append(("buffer", int(ids[0])))
        return int(ids[0])

    def image(self, fmt: str, size: tuple) -> int:
        from OpenGL import GL as gl

        internal = {"rgba32f": gl.GL_RGBA32F, "rgba16f": gl.GL_RGBA16F, "r16f": gl.GL_R16F, "r32f": gl.GL_R32F,
                    "rgba8": gl.GL_RGBA8}[fmt]
        ids = (ctypes.c_uint * 1)()
        three = len(size) == 3
        gl.glCreateTextures(gl.GL_TEXTURE_3D if three else gl.GL_TEXTURE_2D, 1, ids)
        texture = int(ids[0])
        if three:
            gl.glTextureStorage3D(texture, 1, internal, *size)
        else:
            gl.glTextureStorage2D(texture, 1, internal, *size)
        self.objects.append(("texture", texture))
        return texture

    def block(self, pack_name: str, values: tuple, compute: tuple) -> int | None:
        if not values:
            return None
        import compute_passes

        reflected = compute_passes.reflection(_work_dir() / "packs" / f"{pack_name}.qsb")
        block = reflected["uniformBlocks"][0]["blockName"]
        given = {}
        for name, _kind, value in values:
            given[name] = list(compute) if value == "compute" else value
        data, _facts = self.core.program_block_pack(self.packs[pack_name], block, given)
        return self.buffer(data)

    def run(self, spec, inputs: dict) -> dict:
        """The scene's dispatches in order (a full barrier between them: the oracle's sequential meaning); every resource
        read back as the core's readback names it."""
        import numpy as np
        from OpenGL import GL as gl

        with self.target.current():
            resources: dict = {}
            for image in spec.images:
                resources[image.name] = ("image", image.format, tuple(image.size), self.image(image.format,
                                                                                               tuple(image.size)))
            for buffer in spec.buffers:
                size = buffer.bytes if isinstance(buffer.bytes, int) else int(spec.settings[buffer.bytes])
                resources[buffer.name] = ("buffer", "bytes", (size, 0, 0), self.buffer(bytes(size)))
            for stream in spec.streams:
                resources[stream.name] = ("stream", "bytes", (0, 0, 0), self.buffer(inputs[stream.field]))
            for pack_name, groups, bindings, values in spec.reference:
                program = self.program(pack_name)
                gl.glUseProgram(program)
                # The native scene's last dispatch is its third: not fresh (u_srpss_compute's rule).
                ubo = self.block(pack_name, values, (PARITY_RECORDS, PARITY_RECORDS - 1, 0, PARITY_RECORDS - 1))
                if ubo is not None:
                    binding = 16 if pack_name.startswith("population") else 0
                    gl.glBindBufferBase(gl.GL_UNIFORM_BUFFER, binding, ubo)
                for point, name in bindings.items():
                    kind, fmt, size, handle = resources[name]
                    if kind == "image":
                        internal = {"rgba32f": gl.GL_RGBA32F, "rgba16f": gl.GL_RGBA16F, "r16f": gl.GL_R16F,
                                    "r32f": gl.GL_R32F}[fmt]
                        gl.glBindImageTexture(point, handle, 0, gl.GL_TRUE if len(size) == 3 else gl.GL_FALSE, 0,
                                              gl.GL_READ_WRITE, internal)
                    else:
                        gl.glBindBufferBase(gl.GL_SHADER_STORAGE_BUFFER, point, handle)
                gl.glDispatchCompute(*groups)
                gl.glMemoryBarrier(gl.GL_ALL_BARRIER_BITS)
            gl.glFinish()
            out = {}
            for name, (kind, fmt, size, handle) in resources.items():
                if kind == "stream":
                    continue
                if kind == "buffer":
                    data = (ctypes.c_ubyte * size[0])()
                    gl.glGetNamedBufferSubData(handle, 0, size[0], data)
                    out[name] = ("buffer", "bytes", size, bytes(data))
                    continue
                gl_format, gl_type, width = {"rgba32f": (gl.GL_RGBA, gl.GL_FLOAT, 16),
                                             "rgba16f": (gl.GL_RGBA, gl.GL_HALF_FLOAT, 8),
                                             "r16f": (gl.GL_RED, gl.GL_HALF_FLOAT, 2),
                                             "r32f": (gl.GL_RED, gl.GL_FLOAT, 4)}[fmt]
                count = int(np.prod(size)) * width
                data = (ctypes.c_ubyte * count)()
                gl.glPixelStorei(gl.GL_PACK_ALIGNMENT, 1)
                gl.glGetTextureImage(handle, 0, gl_format, gl_type, count, data)
                out[name] = ("image", fmt, tuple(size) + ((1,) if len(size) == 2 else ()), bytes(data))
            return out

    def timed(self, spec, inputs: dict, runs: int = 200) -> dict:
        """The scene's dispatches timed with GL_TIME_ELAPSED (the Python path's GPU time on the same load)."""
        from OpenGL import GL as gl

        times = []
        self.run(spec, inputs)                # its resources stay bound in the context for the timed dispatches
        with self.target.current():
            query = (ctypes.c_uint * 1)()
            gl.glGenQueries(1, query)
            for _ in range(runs):
                gl.glBeginQuery(gl.GL_TIME_ELAPSED, query[0])
                for pack_name, groups, bindings, _values in spec.reference:
                    gl.glUseProgram(self.program(pack_name))
                    gl.glDispatchCompute(*groups)
                    gl.glMemoryBarrier(gl.GL_ALL_BARRIER_BITS)
                gl.glEndQuery(gl.GL_TIME_ELAPSED)
                result = ctypes.c_uint64(0)
                gl.glGetQueryObjectui64v(query[0], gl.GL_QUERY_RESULT, ctypes.byref(result))
                times.append(int(result.value))
            gl.glDeleteQueries(1, query)
        return mbc._summary(times)


_WORK: list = []


def _work_dir() -> Path:
    return _WORK[0]


def round_reference(core, packs: dict, out: Path, cost: bool) -> dict:
    """The reference's storage for the parity scenes (and, with ``cost``, its GPU time on the cost loads)."""
    cp = _scenes()
    result: dict = {"pass": True}
    reference = Reference(core, packs)
    try:
        storage = {}
        for name in PARITY_SCENES:
            spec = spec_for(name, packs)
            values = dict(spec.record)
            values.update(_record_values(name, PARITY_RECORDS - 1))
            inputs = {k: v for k, v in values.items() if isinstance(v, (bytes, bytearray))}
            if name == "volume":
                spec = replace(spec, reference=tuple(
                    (p, g, b, tuple((n, k, values["u_phase"] if n == "u_phase" else v) for n, k, v in vals))
                    for p, g, b, vals in spec.reference))
            storage[name] = reference.run(spec, inputs)
        (_work(out) / "storage_reference.json").write_text(json.dumps(
            {n: {r: [v[0], v[1], list(v[2]), v[3].hex()] for r, v in s.items()} for n, s in storage.items()}),
            encoding="utf-8")
        if cost:
            timings = {}
            big = COST_SCENES["waveform"]["volume"]
            spec = spec_for("volume", packs, volume=big)
            spec = replace(spec, reference=tuple((p, g, b, tuple((n, k, 0.0 if v is None else v) for n, k, v in vals))
                                                 for p, g, b, vals in spec.reference))
            timings["waveform_volume"] = reference.timed(spec, {})
            for name in ("field", "chain"):
                s = spec_for(name, packs)
                timings[f"waveform_{name}"] = reference.timed(s, {"knot_rows": s.record["knot_rows"]})
            pop = spec_for("population", packs, population=262144)
            timings["population_262144"] = reference.timed(pop, {})
            result["cost"] = timings
    finally:
        reference.close()
    return result


# --------------------------------------------------------------------------------------------------- trigger

def _state_rows(storage: dict, name: str = "state"):
    import numpy as np

    return np.frombuffer(storage[name][3], "<f4").reshape(-1, 4)


def round_trigger(core, engine, app, api: str, packs: dict) -> dict:
    import numpy as np

    checks, facts = {}, {}
    host = mbc._host(core)
    try:
        # The frame trigger: one dispatch an accepted record; none for a card, a settings or a readback re-record.
        scene = Scene(core, engine, host, spec_for("field", packs))
        try:
            scene.draw(2)
            before = _live(core)
            _records(scene, 20, change=lambda i: _record_values("field", i))
            after = _live(core)
            facts["frame_trigger_20_records"] = _delta(after, before, "compute_dispatches")
            checks["a_frame_trigger_dispatches_once_per_record"] = facts["frame_trigger_20_records"] == 20
            records_before = scene.mode.state().get("records")
            before = _live(core)
            for i in range(10):
                card = mbc._card(scene.card, scene.dpr)
                card["content_fade"] = 1.0 - 0.05 * (i + 1)
                scene.mode.card(card)
                host.frames(1)
            for i in range(5):
                scene.mode.settings(dict(scene.spec.settings, u_scale=[0.125 + 0.01 * i, 0.125, 0.125, 0.0]))
                host.frames(1)
            scene.storage(app)
            after = _live(core)
            records_after = scene.mode.state().get("records")
            facts["re_records"] = {"records": [records_before, records_after],
                                   "dispatches": _delta(after, before, "compute_dispatches"),
                                   "skipped": _delta(after, before, "compute_skipped")}
            checks["a_card_settings_or_readback_re_record_dispatches_nothing"] = (
                facts["re_records"]["dispatches"] == 0 and (records_after or 0) - (records_before or 0) >= 10)
        finally:
            _close(scene, host, app)
        # The field trigger: dispatched only when `step` changes (two entries); the state against the CPU.
        for control in (False, True):
            core.module.compute_control(json.dumps({"trigger_every_record": control}))
            scene = Scene(core, engine, host, spec_for("state", packs))
            try:
                before = _live(core)
                steps = [1 + i // 2 for i in range(TRIGGER_RECORDS)]   # changes every second record
                _records(scene, TRIGGER_RECORDS, change=lambda i: {"step": steps[i], "u_frame": float(i)})
                after = _live(core)
                rows = _state_rows(scene.storage(app))
                key = "control" if control else "trigger"
                distinct = len(set(steps))
                facts[key] = {"dispatches": _delta(after, before, "compute_dispatches"), "distinct_steps": distinct,
                              "row0": rows[0].tolist(), "row_last": rows[-1].tolist()}
                expected = np.array([distinct, steps[-1], steps[-2] if steps[-2] != steps[-1] else steps[-3], 0.0])
                expected[3] = float(distinct - 1)               # fresh 0, the dispatches before the last
                if not control:
                    checks["a_field_trigger_dispatches_only_on_a_change"] = facts[key]["dispatches"] == 2 * distinct
                    checks["the_state_equals_the_cpu_reference"] = bool(np.all(rows == expected))
                    facts["cpu_reference"] = expected.tolist()
                else:
                    checks["control_every_record_integrates_more_and_differs"] = (
                        facts[key]["dispatches"] == 2 * TRIGGER_RECORDS and float(rows[0][0]) != float(distinct))
            finally:
                _close(scene, host, app)
                core.module.compute_control(json.dumps({"trigger_every_record": False}))
        # Checkpoint audit 5 M2: fresh is per entry. The same program sent again over its kept storage, then an image no
        # entry of the state binds made again (its size changed), restart neither entry: each step goes on from the
        # last, not fresh. The state scene with one unrelated image beside it.
        from rendering.native.mode import StorageImage

        spec = replace(spec_for("state", packs), images=(StorageImage("unrelated", (8, 8), "r32f"),))
        scene = Scene(core, engine, host, spec)
        try:
            _records(scene, 6, change=lambda i: {"step": 1 + i, "u_frame": float(i)})
            before_rows = _state_rows(scene.storage(app))[0].tolist()
            before = _live(core)
            scene.mode.program(spec.passes, spec.settings, targets=spec.targets, streams=spec.streams,
                               buffers=spec.buffers, images=spec.images)
            scene.draw(1, step=7, u_frame=7.0)
            resent = _state_rows(scene.storage(app))[0].tolist()
            middle = _live(core)
            scene.mode.image_size("unrelated", (16, 8))
            scene.draw(1, step=8, u_frame=8.0)
            imaged = _state_rows(scene.storage(app))
            after = _live(core)
            facts["kept_history"] = {
                "row0_after_6_steps": before_rows, "row0_after_the_program_again": resent,
                "row0_after_an_unrelated_image": imaged[0].tolist(),
                "resend": {k: _delta(middle, before, k) for k in ("compute_objects_created", "compute_clears",
                                                                  "compute_dispatches")},
                "image": {k: _delta(after, middle, k) for k in ("compute_objects_created", "compute_clears",
                                                                 "compute_dispatches")}}
            # Row 0 is (dispatches since fresh, trigger, its last value, fresh * 1000 + dispatches before this one).
            checks["six_steps_reach_6_6_5_5"] = before_rows == [6.0, 6.0, 5.0, 5.0]
            checks["the_same_program_again_keeps_each_entrys_history"] = resent == [7.0, 7.0, 6.0, 6.0]
            checks["an_image_no_entry_binds_made_again_restarts_no_entry"] = bool(
                np.all(imaged == np.array([8.0, 8.0, 7.0, 7.0])))     # every row (both entries' halves)
            checks["the_program_again_made_and_cleared_nothing"] = (facts["kept_history"]["resend"][
                "compute_objects_created"] == 0 and facts["kept_history"]["resend"]["compute_clears"] == 0)
        finally:
            _close(scene, host, app)
        # A node made again: storage made zeroed, the entries dispatch fresh, the owner told once.
        scene = Scene(core, engine, host, spec_for("state", packs))
        calls: list = []
        try:
            scene.mode.on_state_lost(lambda names: calls.append(sorted(names)))
            _records(scene, 6, change=lambda i: {"step": 1 + i, "u_frame": float(i)})
            before = _live(core)
            scene.mode.composite.set(rect=[0.0, 0.0, 0.0, 0.0])
            host.frames(3)
            scene.mode.composite.set(rect=[0.0, 0.0, float(scene.card[0]), float(scene.card[1])])
            scene.draw(2, step=100, u_frame=100.0)
            app.processEvents()
            host.frames(2)
            app.processEvents()
            after = _live(core)
            rows = _state_rows(scene.storage(app))
            facts["made_again"] = {"calls": calls, "states_lost": _delta(after, before, "compute_states_lost"),
                                   "row0": rows[0].tolist()}
            checks["a_node_made_again_dispatches_fresh"] = rows[0].tolist() == [1.0, 100.0, 0.0, 1000.0]
            checks["the_owner_is_told_once"] = calls == [["out", "state"]] and facts["made_again"]["states_lost"] == 1
        finally:
            scene.mode.on_state_lost(None)
            _close(scene, host, app)
    finally:
        host.close()
        host_check._flush_deletes(app)
    return {"pass": all(checks.values()), "checks": checks, "facts": facts}


# --------------------------------------------------------------------------------------------------- war, copy

def round_war(core, engine, app, api: str, packs: dict) -> dict:
    import numpy as np

    checks, facts = {}, {}
    host = mbc._host(core)
    try:
        scene = Scene(core, engine, host, spec_for("war", packs))
        try:
            # Four records, one frame each (one scene.draw publishes one record): the last record's read pass sees the
            # X the record before it wrote, and its write pass then overwrites X.
            _records(scene, 4)
            got = scene.storage(app)
            x = np.frombuffer(got["x"][3], "<f4").reshape(-1, 4)
            y = np.frombuffer(got["y"][3], "<f4").reshape(-1, 4)
            serial = float(x[0][0])
            serial_before = serial - 1.0
            expected_y = np.array([[2 * serial_before + 0.5, 2 * i + 0.5, 2 * 0.25 + 0.5, 2.5] for i in range(len(y))])
            facts["x0"], facts["y0"] = x[0].tolist(), y[0].tolist()
            checks["y_holds_the_earlier_x"] = bool(np.all(y == expected_y))
            checks["x_holds_this_record"] = bool(np.all(x[:, 1] == np.arange(len(x))))
        finally:
            _close(scene, host, app)
        # Checkpoint audit 5 M4, the ping-pong form (two buffers): ping reads A and writes B, pong reads B and writes A,
        # each one past what it read; after n dispatches in all A counts n, B one less, and each holds what it read.
        scene = Scene(core, engine, host, spec_for("war_pingpong", packs))
        try:
            before = _live(core)
            _records(scene, 4, change=lambda i: {"u_frame": float(i)})
            dispatches = _delta(_live(core), before, "compute_dispatches")
            got = scene.storage(app)
            a = np.frombuffer(got["a"][3], "<f4").reshape(-1, 4)
            b = np.frombuffer(got["b"][3], "<f4").reshape(-1, 4)
            facts["pingpong"] = {"dispatches": dispatches, "a0": a[0].tolist(), "b0": b[0].tolist()}
            checks["pingpong_dispatched_both_entries_every_record"] = dispatches == 8
            checks["pingpong_a_counts_every_dispatch"] = bool(np.all(a[:, 0] == dispatches))
            checks["pingpong_b_is_one_behind_and_read_a_before_a_was_written"] = bool(
                np.all(b[:, 0] == dispatches - 1) and np.all(b[:, 2] == dispatches - 2))
            checks["pingpong_a_read_b_after_b_was_written"] = bool(np.all(a[:, 2] == dispatches - 1))
            checks["pingpong_rows_are_their_own"] = bool(np.all(a[:, 1] == np.arange(len(a)))
                                                         and np.all(b[:, 1] == np.arange(len(b))))
        finally:
            _close(scene, host, app)
    finally:
        host.close()
        host_check._flush_deletes(app)
    return {"pass": all(checks.values()), "checks": checks, "facts": facts}


def round_copy(core, engine, app, api: str, packs: dict) -> dict:
    import numpy as np

    cp = _scenes()
    checks, facts = {}, {}
    host = mbc._host(core)
    try:
        scene = Scene(core, engine, host, spec_for("state", packs))
        try:
            _records(scene, 5, change=lambda i: {"step": 1 + i, "u_frame": float(i)})
            before = _state_rows(scene.storage(app)).copy()
            live0 = _live(core)
            rows = 2 * cp.STATE_ROWS
            scene.mode.settings(dict(scene.spec.settings, state_bytes=16 * rows, u_grid=cp.state_grid(rows)))
            host.frames(2)
            after = _state_rows(scene.storage(app))
            live1 = _live(core)
            facts["resize"] = {"rows": [len(before), len(after)], "copies": _delta(live1, live0, "compute_copies"),
                               "clears": _delta(live1, live0, "compute_clears"),
                               "dispatches": _delta(live1, live0, "compute_dispatches")}
            checks["a_resized_buffer_keeps_its_prefix"] = bool(np.array_equal(after[:len(before)], before))
            checks["past_the_prefix_reads_zero"] = bool(np.all(after[len(before):] == 0.0))
            checks["the_resize_copied_and_dispatched_nothing"] = (facts["resize"]["copies"] == 2
                                                                  and facts["resize"]["dispatches"] == 0)
        finally:
            _close(scene, host, app)
        # A created image reads zero where nothing wrote it: the blur's image made taller writes only its first row.
        scene = Scene(core, engine, host, spec_for("chain", packs))
        try:
            scene.draw(2)
            scene.mode.image_size("give", (64, 2))
            scene.draw(2)
            got = scene.storage(app)
            give = np.frombuffer(got["give"][3], "<f4").reshape(2, 64, 4)
            facts["give"] = {"size": list(got["give"][2]), "row0_max": float(np.abs(give[0]).max())}
            checks["a_created_image_reads_zero_where_unwritten"] = bool(np.all(give[1] == 0.0)) and float(
                np.abs(give[0]).max()) > 0.0
        finally:
            _close(scene, host, app)
    finally:
        host.close()
        host_check._flush_deletes(app)
    return {"pass": all(checks.values()), "checks": checks, "facts": facts}


# --------------------------------------------------------------------------------------------------- rest, steady

def round_rest(core, engine, app, api: str, packs: dict) -> dict:
    checks, facts = {}, {}
    host = mbc._host(core)
    try:
        scene = Scene(core, engine, host, spec_for("population", packs))
        try:
            scene.draw(3)
            before = _live(core)
            records_before = scene.mode.state().get("records")
            deadline = time.monotonic() + REST_SECONDS
            frames = 0
            while time.monotonic() < deadline:
                host.frames(1)
                frames += 1
            after = _live(core)
            keys = ("compute_dispatches", "compute_passes", "compute_objects_created", "compute_clears",
                    "compute_copies", "compute_skipped")
            facts["rest"] = {"frames": frames, "records": [records_before, scene.mode.state().get("records")],
                             **{k: _delta(after, before, k) for k in keys}}
            checks["a_minute_at_rest_records_no_compute"] = all(facts["rest"][k] == 0 for k in keys)
            before = _live(core)
            _records(scene, 60)
            after = _live(core)
            facts["control"] = {k: _delta(after, before, k) for k in ("compute_dispatches", "compute_passes")}
            checks["control_a_record_every_frame_dispatches"] = facts["control"]["compute_dispatches"] == 3 * 60
        finally:
            _close(scene, host, app)
    finally:
        host.close()
        host_check._flush_deletes(app)
    return {"pass": all(checks.values()), "checks": checks, "facts": facts}


def round_steady(core, engine, app, api: str, packs: dict) -> dict:
    checks, facts = {}, {}
    host = mbc._host(core)
    try:
        for name in ("state", "population", "volume"):
            scene = Scene(core, engine, host, spec_for(name, packs))
            try:
                scene.draw(4, **({"step": 1} if name == "state" else {}))
                before = _live(core)
                state_before = scene.mode.state()
                deadline = time.monotonic() + STEADY_SECONDS
                i = 0
                while time.monotonic() < deadline:
                    scene.draw(1, **({"step": 2 + i, "u_frame": float(i)} if name == "state" else {"u_frame": float(i)}))
                    i += 1
                after = _live(core)
                state_after = scene.mode.state()
                facts[name] = {"records": i, "objects_created": _delta(after, before, "compute_objects_created"),
                               "buffers_created": _delta(after, before, "mesh_buffers_buffers_created"),
                               "dispatches": _delta(after, before, "compute_dispatches")}
                checks[f"{name}_creates_no_object_in_steady_records"] = (facts[name]["objects_created"] == 0
                                                                         and facts[name]["buffers_created"] == 0)
                checks[f"{name}_no_python_thread_state_on_the_render_thread"] = bool(
                    state_after.get("syncs_probed") and state_after.get("syncs_with_python_thread_state") == 0)
                del state_before
            finally:
                _close(scene, host, app)
    finally:
        host.close()
        host_check._flush_deletes(app)
    return {"pass": all(checks.values()), "checks": checks, "facts": facts}


# --------------------------------------------------------------------------------------------------- retire

def round_retire(core, engine, app, api: str, packs: dict) -> dict:
    keys = ("compute_buffers", "compute_buffer_bytes", "compute_images", "compute_image_bytes")
    checks, facts = {}, {}
    host = mbc._host(core)
    try:
        # The item destroyed.
        for name in ("state", "volume", "population"):
            scene = Scene(core, engine, host, spec_for(name, packs))
            scene.draw(3, **({"step": 1} if name == "state" else {}))
            facts[f"{name}_held"] = {k: _live(core)[k] for k in keys}
            _close(scene, host, app)
            host.frames(2)
            facts[f"{name}_destroyed"] = {k: _live(core)[k] for k in keys}
            checks[f"{name}_destroyed_leaves_nothing"] = all(v == 0 for v in facts[f"{name}_destroyed"].values())
            checks[f"{name}_held_storage"] = facts[f"{name}_held"]["compute_buffers"] + facts[f"{name}_held"][
                "compute_images"] > 0
        # A program without storage on the same item (the same record: its stream kept, no compute, no image).
        from rendering.native.mode import ModePass

        scene = Scene(core, engine, host, spec_for("field", packs))
        try:
            scene.draw(3)
            held = {k: _live(core)[k] for k in keys}
            scene.mode.program((ModePass("plain", packs["plain.frag"], "replace", target="scene"),), {},
                               targets=scene.spec.targets, streams=scene.spec.streams)
            scene.draw(3)
            facts["program_without_storage"] = {"held": held, "after": {k: _live(core)[k] for k in keys},
                                                "last_reason": scene.mode.state().get("last_reason")}
            checks["a_program_without_storage_releases_it"] = (held["compute_images"] > 0 and all(
                v == 0 for v in facts["program_without_storage"]["after"].values()))
        finally:
            _close(scene, host, app)
        # Checkpoint audit 5 M1: the same after a program holding buffers (the population's five; the field above holds
        # one image only). Its buffers go through a resize's delayed release: at the next record's sync, before the item
        # goes.
        scene = Scene(core, engine, host, spec_for("population", packs))
        try:
            scene.draw(3)
            held = {k: _live(core)[k] for k in keys}
            scene.mode.program((ModePass("plain", packs["plain.frag"], "replace", target="scene"),), {},
                               targets=scene.spec.targets, streams=scene.spec.streams)
            _records(scene, 3)                # three records: the first replaces them, the next releases them
            facts["buffers_then_a_program_without_storage"] = {
                "held": held, "after": {k: _live(core)[k] for k in keys},
                "storage": scene.mode.state().get("storage"), "last_reason": scene.mode.state().get("last_reason")}
            checks["a_program_without_storage_releases_the_last_programs_buffers"] = (held["compute_buffers"] > 0 and all(
                v == 0 for v in facts["buffers_then_a_program_without_storage"]["after"].values()))
        finally:
            _close(scene, host, app)
        # Destroyed between a resize's allocation and its copy (the settings set, the item gone before a frame).
        scene = Scene(core, engine, host, spec_for("state", packs))
        scene.draw(3, step=1)
        scene.mode.settings(dict(scene.spec.settings, state_bytes=32 * 256))
        _close(scene, host, app)
        host.frames(2)
        facts["destroyed_mid_resize"] = {k: _live(core)[k] for k in keys}
        checks["destroyed_mid_resize_leaves_nothing"] = all(v == 0 for v in facts["destroyed_mid_resize"].values())
        # The control: a release that skips the storage (left behind, counted).
        core.module.compute_control(json.dumps({"skip_storage_release": True}))
        try:
            scene = Scene(core, engine, host, spec_for("war", packs))
            scene.draw(3)
            _close(scene, host, app)
            host.frames(2)
            facts["control_skipped_release"] = {k: _live(core)[k] for k in keys}
            checks["control_skipped_release_leaves_the_storage"] = facts["control_skipped_release"]["compute_buffers"] > 0
        finally:
            core.module.compute_control(json.dumps({"skip_storage_release": False}))
        # The left-behind storage goes at the next storage sync on the same QRhi once the control is off, so the
        # control leaks nothing into the device's teardown.
        scene = Scene(core, engine, host, spec_for("field", packs))
        scene.draw(3)
        _close(scene, host, app)
        host.frames(2)
        facts["after_the_control"] = {k: _live(core)[k] for k in keys}
        checks["the_control_leaves_nothing_after_it"] = all(v == 0 for v in facts["after_the_control"].values())
    finally:
        host.close()
        host_check._flush_deletes(app)
    return {"pass": all(checks.values()), "checks": checks, "facts": facts}


# --------------------------------------------------------------------------------------------------- barriers

def round_barriers(core, engine, app, api: str, packs: dict) -> dict:
    """Consecutive records with no readback between them, then each control in its own phase."""
    checks, facts = {}, {}
    host = mbc._host(core)
    vulkan = api == "vulkan"
    try:
        for name in ("field", "chain", "volume", "state", "population", "war", "war_pingpong"):
            if vulkan:
                core.set_vulkan_phase("n33 barriers")
            scene = Scene(core, engine, host, spec_for(name, packs))
            try:
                _records(scene, BARRIER_RECORDS, change=lambda i: dict(_record_values(name, i),
                                                                       **({"step": 1 + i} if name == "state" else {})))
            finally:
                _close(scene, host, app)
        for phase, control, scenes in (("n33 control write_as_read", {"write_as_read": True}, ("chain", "state")),
                                       ("n33 control single_pass", {"single_pass": True}, ("war",))):
            if vulkan:
                core.set_vulkan_phase(phase)
            core.module.compute_control(json.dumps(control))
            try:
                for name in scenes:
                    scene = Scene(core, engine, host, spec_for(name, packs))
                    try:
                        _records(scene, 12, change=lambda i: dict(_record_values(name, i),
                                                                  **({"step": 1 + i} if name == "state" else {})))
                    finally:
                        _close(scene, host, app)
            finally:
                core.module.compute_control(json.dumps({k: False for k in control}))
        if vulkan:
            core.set_vulkan_phase("n33 after barriers")
        checks["barrier_records_ran"] = True
    finally:
        host.close()
        host_check._flush_deletes(app)
    return {"pass": all(checks.values()), "checks": checks, "facts": facts}


def round_pingpong(core, engine, app, api: str, packs: dict) -> dict:
    """The ping-pong's Vulkan phases, in a child of their own (CONTROL_ROUNDS): the single-pass fact, then the control
    (written bindings recorded as reads)."""
    host = mbc._host(core)
    try:
        for phase, control in (("n33 fact single_pass pingpong", {"single_pass": True}),
                               ("n33 control pingpong write_as_read", {"write_as_read": True})):
            core.set_vulkan_phase(phase)
            core.module.compute_control(json.dumps(control))
            try:
                scene = Scene(core, engine, host, spec_for("war_pingpong", packs))
                try:
                    _records(scene, 12, change=lambda i: _record_values("war_pingpong", i))
                finally:
                    _close(scene, host, app)
            finally:
                core.module.compute_control(json.dumps({k: False for k in control}))
        core.set_vulkan_phase("n33 after pingpong")
    finally:
        host.close()
        host_check._flush_deletes(app)
    return {"pass": True, "checks": {"pingpong_phases_ran": True}, "facts": {}}


def split_validation(messages: dict) -> dict:
    """The validation summary outside the control phases (must be clean) and, per control phase, whether its expected
    hazard was reported."""
    entries = messages.get("entries", [])
    clean_entries = [e for e in entries if (e.get("phase") or "") not in CONTROL_PHASES
                     and (e.get("phase") or "") not in FACT_PHASES]
    clean_errors = sum(int(e.get("count", 1)) for e in clean_entries if e.get("severity") == "error")
    clean_warnings = sum(int(e.get("count", 1)) for e in clean_entries if e.get("severity") == "warning")
    rest = dict(messages, entries=clean_entries, errors=clean_errors, warnings=clean_warnings)
    summary = vk_validation.validation_summary(rest)
    controls = {}
    for phase, hazard in CONTROL_PHASES.items():
        found = [e for e in entries if e.get("phase") == phase]
        controls[phase] = {"expected": hazard, "found": sorted({e.get("id") for e in found if e.get("id")}),
                           "reported": any(e.get("id") == hazard for e in found)}
    facts = {phase: sorted({e.get("id") for e in entries if e.get("phase") == phase and e.get("id")})
             for phase in FACT_PHASES}
    return {"outside_controls": {k: v for k, v in summary.items() if k != "groups"},
            "attribution": summary["groups"], "controls": controls, "facts": facts}


# --------------------------------------------------------------------------------------------------- cost

def _cost_spec(name: str, packs: dict):
    cp = _scenes()
    if name == "waveform":
        big = COST_SCENES["waveform"]["volume"]
        spec = spec_for("volume", packs, volume=big)
        spec = replace(spec, images=tuple(replace(i, size=big) for i in spec.images),
                       settings=dict(spec.settings, u_slice=[(2 + 0.5) / big[2], 0.25, 0.0, 0.0]))
        return spec
    if name == "drift":
        return spec_for("state", packs, state_rows=COST_SCENES["drift"]["state_rows"])
    if name == "population":
        return spec_for("population", packs, population=COST_SCENES["population"]["population"])
    raise KeyError(name)


def round_cost(core, engine, app, api: str, packs: dict) -> dict:
    cp = _scenes()
    checks, facts = {}, {}
    for size in COST_HOSTS:
        dpr = size[0] / cp.CARD[0]
        label = f"{size[0]}x{size[1]}"
        facts[label] = {}
        host = mbc._host(core, dpr)
        try:
            for name in ("waveform", "drift", "population", "field", "chain"):
                spec = _cost_spec(name, packs) if name in COST_SCENES else spec_for(name, packs)
                scene = Scene(core, engine, host, spec, dpr=dpr)
                try:
                    if name == "drift":
                        counter = {"i": 0}

                        def publish(original=scene.publish, counter=counter, **changes):
                            counter["i"] += 1
                            original(step=counter["i"], **changes)

                        scene.publish = publish
                    facts[label][name] = mbc._timed(host, scene, frames=COST_FRAMES)
                    facts[label][name]["last_reason"] = scene.mode.state().get("last_reason")
                    checks[f"{label}_{name}_timed"] = facts[label][name]["samples"] >= mbc.COST_MIN_SAMPLES
                finally:
                    _close(scene, host, app)
        finally:
            host.close()
            host_check._flush_deletes(app)
    return {"pass": all(checks.values()), "checks": checks, "facts": facts}


# --------------------------------------------------------------------------------------------------- the child

def child(args) -> dict:
    root = host_check._root(args.repo)
    out = Path(args.out_dir)
    _WORK.append(_work(out))
    record: dict = {"api": args.api, "rounds": list(args.rounds), "module_loaded": False, "instance_created": False}
    if args.api in ("opengl", "reference"):
        from rendering.quick.bootstrap import configure_quick_graphics

        configure_quick_graphics(reason="compute-pass-check")
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
        # The layer's shader-access hazard checks are off by default; without them sync validation reports no storage
        # hazard at all and the barrier controls prove nothing, so the harness fails closed when they did not load.
        instance = core.vulkan_instance(validation=True, shader_accesses=True)
        record["instance"] = instance
        if not instance.get("ok"):
            record["error"] = f"the Vulkan instance failed: {instance.get('instance', {}).get('error')}"
            return record
        if not (instance.get("instance") or {}).get("synchronisation_shader_accesses"):
            record["error"] = ("the layer's shader-access hazard checks did not load: "
                               f"{(instance.get('instance') or {}).get('synchronisation_shader_accesses_note')}")
            return record
        record["instance_created"] = True
    engine = QQmlEngine()
    packs = load_packs(out)
    try:
        if args.api == "reference":
            record["reference"] = round_reference(core, packs, out, cost="cost" in args.rounds)
            record["rounds"] = ["reference"]
        else:
            rounds = {"facts": lambda: round_facts(core, engine, app, args.api, packs),
                      "parity": lambda: round_parity(core, engine, app, args.api, packs, out),
                      "trigger": lambda: round_trigger(core, engine, app, args.api, packs),
                      "war": lambda: round_war(core, engine, app, args.api, packs),
                      "copy": lambda: round_copy(core, engine, app, args.api, packs),
                      "rest": lambda: round_rest(core, engine, app, args.api, packs),
                      "steady": lambda: round_steady(core, engine, app, args.api, packs),
                      "retire": lambda: round_retire(core, engine, app, args.api, packs),
                      "barriers": lambda: round_barriers(core, engine, app, args.api, packs),
                      "pingpong": lambda: round_pingpong(core, engine, app, args.api, packs),
                      "cost": lambda: round_cost(core, engine, app, args.api, packs)}
            for name in args.rounds:
                if vulkan:
                    core.set_vulkan_phase(f"n33 {name}")
                try:
                    record[name] = rounds[name]()
                except Exception:
                    record[name] = {"pass": False, "error": traceback.format_exc()}
    finally:
        host_check._flush_deletes(app)
        record["live_hosts_at_end"] = core.live_hosts()
        record["composites_at_end"] = core.composite_live()
        if vulkan:
            teardown = core.destroy_vulkan_instance()
            messages = teardown.pop("messages", {}) if isinstance(teardown, dict) else {}
            split = split_validation(messages)
            record["instance_teardown"] = teardown
            record["validation"] = {"layer_loaded": bool(record["instance"].get("validation_layer_loaded")),
                                    "per_phase": messages.get("per_phase"), **split["outside_controls"],
                                    "controls": split["controls"], "fact_phases": split["facts"],
                                    "attribution": split["attribution"]}
        del engine
    return record


def api_verdict(api: str, record: dict, require_validation: bool) -> tuple[bool, list[str]]:
    if api == "reference":
        entry = record.get("reference") or {}
        return bool(entry.get("pass")), ([] if entry.get("pass") else
                                         [f"reference: {(entry.get('error') or record.get('error') or 'failed')[-1500:]}"])
    ok, failed = host_check.api_verdict(api, record, require_validation)
    if api == "vulkan":
        for phase, c in ((record.get("validation") or {}).get("controls") or {}).items():
            if CONTROL_ROUNDS.get(phase) in record.get("rounds", []) and not c.get("reported"):
                failed.append(f"vulkan: the control phase '{phase}' reported no {c.get('expected')} ({c.get('found')})")
    if record.get("module_loaded") and (api != "vulkan" or record.get("instance_created")):
        live = record.get("composites_at_end") or {}
        left = {k: live.get(k) for k in ("items", "mode_sources", "mode_resources", "compute_readbacks") if live.get(k)}
        # The retire round's control leaves its storage behind by design (counted); nothing else may be left.
        if left:
            failed.append(f"{api}: left at the end ({left})")
    return not failed, failed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--module-dir", default="release/native_module")
    parser.add_argument("--repo", default=".", help="the repository root (default: the current directory)")
    parser.add_argument("--apis", nargs="+", default=list(APIS), choices=APIS)
    parser.add_argument("--rounds", nargs="+", default=list(ROUNDS), choices=(*ROUNDS, "pingpong"))
    parser.add_argument("--label", default="n33_compute")
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

    out = artifact_paths.evidence_dir("native_core", "n3_3", args.label)
    out.mkdir(parents=True, exist_ok=True)
    environment = vk_validation.environment_record(_ALLOWED_ENV)
    conditions = {"before": mbc._gpu_conditions()}
    bake = bake_packs(out)
    qualifiers = qualifier_facts(bake)
    results: dict = {}
    main_rounds = [r for r in args.rounds if r != "pingpong"]
    children = [(a, a, main_rounds) for a in APIS if a in args.apis]
    if ("parity" in args.rounds or "cost" in args.rounds) and "opengl" in args.apis:
        children.append(("reference", "reference", [r for r in main_rounds if r != "facts"]))
    if "vulkan" in args.apis and ("barriers" in args.rounds or "pingpong" in args.rounds):
        # The ping-pong's control in a process of its own (CONTROL_ROUNDS: the layer's per-id message limit).
        children.append(("vulkan_pingpong", "vulkan", ["pingpong"]))
    for key, api, rounds in children:
        child_json = out / f"child_{key}.json"
        command = [sys.executable, str(Path(__file__).resolve()), "--child", "--api", api, "--repo", str(root),
                   "--module-dir", args.module_dir, "--out-dir", str(out), "--child-json", str(child_json),
                   "--rounds", *rounds]
        started = time.monotonic()
        try:
            proc = subprocess.run(command, capture_output=True, text=True, timeout=CHILD_TIMEOUT_S, cwd=str(root))
            exit_code, stderr = proc.returncode, proc.stderr
        except subprocess.TimeoutExpired as exc:
            exit_code, stderr = "timeout", str(exc.stderr or "")
        record = json.loads(child_json.read_text(encoding="utf-8")) if child_json.exists() else {
            "api": api, "rounds": list(rounds), "error": f"the child process ended without a record ({exit_code})"}
        child_json.unlink(missing_ok=True)
        record["exit_code"] = exit_code
        record["seconds"] = round(time.monotonic() - started, 1)
        if exit_code != 0 or record.get("error"):
            record["stderr_tail"] = (stderr or "")[-4000:]
        results[key] = record
    conditions["after"] = mbc._gpu_conditions()

    apis_of = {key: api for key, api, _rounds in children}
    verdicts = {key: api_verdict(apis_of[key], record, args.require_validation) for key, record in results.items()}
    failed = [reason for _ok, reasons in verdicts.values() for reason in reasons]
    if "facts" in args.rounds:
        for key, value in qualifiers.items():
            if key != "rgba16f_dump_name" and not value:
                failed.append(f"facts: {key}")
    cross = None
    if "parity" in args.rounds:
        cross = cross_compare(out)
        for rule, needed in (("rule_a", "opengl" in args.apis),
                             ("rule_b", "vulkan" in args.apis and "opengl" in args.apis)):
            if needed and not (cross.get(rule) or {}).get("pass"):
                failed.append(f"{rule}: " + json.dumps(cross.get(rule), default=str)[:1500])
    if not environment["clean"]:
        failed.append(f"environment: {', '.join(environment['contaminating_set'])} set")
    summary = {"apis": args.apis, "rounds": args.rounds, "environment": environment, "gpu_conditions": conditions,
               "bake": bake, "qualifiers": qualifiers, "require_validation": args.require_validation, "cross": cross,
               "verdicts": {api: {"pass": ok, "failed": reasons} for api, (ok, reasons) in verdicts.items()},
               "results": results, "pass": not failed}
    (out / "summary.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    for api, (ok, reasons) in verdicts.items():
        print(f"{api}: {'PASS' if ok else 'FAIL'}" + ("" if ok else " (" + "; ".join(reasons)[:2000] + ")"))
    if cross is not None:
        print("cross: " + json.dumps({rule: v.get("pass") for rule, v in cross.items() if isinstance(v, dict)}))
    print(f"evidence: {out / 'summary.json'} (the work folder holds the packs and readbacks: delete it once judged)")
    print("N33 VERDICT " + ("PASS" if not failed else "FAIL: " + "; ".join(failed)[:4000]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
