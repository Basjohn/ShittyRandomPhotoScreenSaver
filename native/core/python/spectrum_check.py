"""N2.5's proof of the native Spectrum item (Current_Plan.md item 8b), through ``rendering.native``.

The module (``release/native_module``, built on GitHub) is loaded the product's way, in one child process per graphics
API (Qt Quick's API is process-wide): OpenGL first, then Vulkan on the module's own instance and devices (D6). No window
is ever visible: the Python renderer draws into hidden targets and the native item into the module's hidden host.

Rounds:
  block   (OpenGL child; GPU-free on the native side) the uniform parity of the port. The production owner draws Spectrum
          in process through every run of the widened set (``tools/conventions_identity.mode_runs("spectrum",
          offers=True)``: variants a and b and every Choice offer; settings from the spec, never presets) with the
          Python renderer, and every frame it draws is captured: its logical frame, the presentation it drew with and
          the SpectrumDraw values it bound. Each frame is encoded as Spectrum's native record
          (``spectrum_native_schema.encode``) and its card resolved (``rendering.native.spectrum_presentation``); the
          module's ``spectrum_block`` must give the Python block byte for byte (``pack_block``), the members that are
          positional by construction set from the card on both sides (the quad's matrix and item size, the target map,
          fragPixel's target size) and the clock that only a flag sheet reads taken from the native side when no flag
          is shown; members are compared one by one (padding is never read). Negative controls: the record's first bar
          raised and the card's content fade nudged must each change the block.
  item    (each API) the item's contract in the module's hidden host: frames of a native stream accepted at the sync on
          the render thread (one record per accepted frame, nothing recorded at rest), D2's head read consumes nothing,
          the drop edge clears the card and a newer frame draws again, an unbind releases the reader on the render
          thread, and D1's "close during copy": the reader paused inside a copy (the pause_in_copy hook) while another
          thread closes and unlinks the mapping and retires the stream; the copy completes against the pinned view, the
          frame is discarded and nothing is acknowledged, and the retire call returns at once. Negative control:
          accept_after_retire accepts that frame. Every reader, view, source and QRhi object of the core's is gone at
          the end.
  pixels  (each API) the drawn pixels: a sample of the captured frames drawn by the native item (its target placed on
          the item's own rect, over an opaque black display) against the Python renderer's own draw of the same frame
          into a transparent target of the item's size (OpenGL child; premultiplied over black is the same colour):
          equal byte for byte on OpenGL (rule (a)'s first form, before the owner-level run); on Vulkan, against the
          native OpenGL frames within VULKAN_TOLERANCE levels (rule (b)'s first form). The per-pass GPU time of the
          surface is recorded beside (N2.6's timer).

Usage (repository venv, from the checkout holding the built module):
  python native/core/python/spectrum_check.py --module-dir release/native_module --require-validation
      --layer-path D:\\Temp\\Scratch\\SRPSS\\native_spike\\validation_layers\\extracted
  [--apis opengl vulkan] [--rounds block item pixels] [--sample-every 40] [--label n25_spectrum]
Evidence: .artifacts/evidence/native_core/n2_5/<date>_<label>/ (summary.json; one PNG sheet per API of a few pixel
samples beside their reference). Exit 0 whenever the harness ran; the verdict is the last printed line
("N25 VERDICT PASS" or "N25 VERDICT FAIL: ...").
"""
from __future__ import annotations

import argparse
import base64
import json
import subprocess
import sys
import threading
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
ROUNDS = ("block", "item", "pixels")
CHILD_TIMEOUT_S = 1800
MARGIN = 8                       # logical pixels between the display's corner and the item
REST_FRAMES = 3
VULKAN_TOLERANCE = 1             # 8-bit levels, native Vulkan against native OpenGL (rule (b)'s stated tolerance)
SLOT_BYTES = 4096                # one Spectrum record (1488 bytes) per slot, with room
IDENTITY = {"runtime_generation": 7, "engine_generation": 3, "activation_id": 11}
_ALLOWED_ENV: set[str] = set()
#: Members that are positional by construction (the Python quad's against the core's target) or unread there.
POSITIONAL = ("uMatrix", "uItemSize", "u_item_from_frag", "u_item_from_frag_x", "u_item_from_frag_y", "u_target_px")


def _work(out: Path) -> Path:
    path = out / "work"
    path.mkdir(parents=True, exist_ok=True)
    return path


# --------------------------------------------------------------------------------------------------------- capture

def capture_runs(sample_every: int) -> tuple[list[dict], list]:
    """Every frame the Python renderer draws through the widened run set: (records, the snapshots sampled for pixels).
    Each record: run key, frame index, the native record, the card, the Python block (positional members from the
    card), and whether a flag sheet is shown."""
    from core.visualizer_engine import spectrum_native_schema
    from rendering.gl_programs.portable import pack_block
    from rendering.gl_programs.spectrum_options import SPECTRUM_FLAG_PATTERNS
    from rendering.native.composite import composite_geometry
    from rendering.native.spectrum import spectrum_presentation
    from rendering.quick.visualizer.implementations import spectrum as python_spectrum
    from tools import conventions_identity
    import tools.expanded_visualizer_evidence as evidence
    from tools.visualizer_replay import owner_render_parity as parity
    from tools.visualizer_replay import owner_worker_gate as gate
    from widgets.spotify_visualizer import engine_worker_link

    clip = evidence.shipped_clip(5.5)
    records: list[dict] = []
    samples: list = []
    renderer = python_spectrum.QuickSpectrumRenderer
    original = renderer.render
    current: dict = {"key": "", "index": 0}

    def capturing(self, frame):
        original(self, frame)
        snapshot = frame.snapshot
        logical = snapshot.logical
        if int(logical.common.bar_count) <= 0:
            return
        presentation = snapshot.presentation
        geometry = composite_geometry(presentation)
        card = spectrum_presentation(presentation, geometry)
        values = dict(self._values)
        values["uMatrix"] = (0.0,) * 16
        values["uItemSize"] = tuple(card["item_size"])
        values["u_item_from_frag"] = 1
        values["u_item_from_frag_x"] = tuple(card["item_from_target"][:3])
        values["u_item_from_frag_y"] = tuple(card["item_from_target"][3:])
        values["u_target_px"] = tuple(card["target_size"])
        flag = str(logical.mode_state.parameters["spectrum_pattern_shown"]) in SPECTRUM_FLAG_PATTERNS
        entry = {"key": current["key"], "index": current["index"], "flag": flag, "card": card,
                 "record": spectrum_native_schema.encode(logical),
                 "python_block": pack_block(python_spectrum.SPECTRUM_BLOCK, values)}
        records.append(entry)
        if current["index"] % sample_every == 0:
            samples.append((len(records) - 1, snapshot, tuple(frame.logical_size), frame.content_rotation_quarters))
        current["index"] += 1

    renderer.render = capturing
    try:
        for suffix, settings in conventions_identity.mode_runs("spectrum", True):
            current["key"], current["index"] = f"spectrum{suffix}", 0
            engine_worker_link.reset_run_state_for_testing()
            script = parity.parity_script(clip.frames, "spectrum")
            mirror = parity.SceneMirror()
            with parity.single_sample_scene_targets():
                gate.identity_run("spectrum", script, worker=False, supervisor=None, namespace=None,
                                  settings=settings, scene_mirror=mirror)
    finally:
        renderer.render = original
    return records, samples


#: Bytes of one non-array member by its GLSL type.
_TYPE_BYTES_GLSL = {"float": 4, "int": 4, "uint": 4, "bool": 4, "vec2": 8, "ivec2": 8, "vec3": 12, "ivec3": 12,
                    "vec4": 16, "ivec4": 16, "mat4": 64}


def round_block(core, records: list[dict]) -> dict:
    import struct

    from core.visualizer_engine import spectrum_native_schema
    from tools import conventions_identity

    from rendering.gl_programs.scene3d import _std140_type
    from rendering.quick.visualizer.implementations.spectrum import SPECTRUM_BLOCK

    bars_offset = spectrum_native_schema.LAYOUT.field("bars").offset
    layout = core.spectrum_block_layout()
    # The oracle is the Python packer's own std140 layout (never the module's reflection, which build round 1 showed
    # reporting a scalar array's stride as 0): every member's bytes, arrays whole.
    members = {}
    for (name, glsl_type), offset in zip(SPECTRUM_BLOCK.fields, SPECTRUM_BLOCK.offsets):
        _element, count, _alignment, stride = _std140_type(glsl_type)
        members[name] = (offset, count * stride if "[" in glsl_type else _TYPE_BYTES_GLSL.get(glsl_type, 4))
    reflected = {row[0]: (row[2], row[3], row[4]) for row in layout["members"]}
    layout_differs = {name: {"python": members[name][0], "module": reflected.get(name)}
                      for name in members if reflected.get(name, (None,))[0] != members[name][0]}
    array_strides = {name: {"python": _std140_type(glsl_type)[3], "module": (reflected.get(name) or (0, 0, 0))[2]}
                     for name, glsl_type in SPECTRUM_BLOCK.fields if "[" in glsl_type}
    time_offset = members.get("u_time", (None,))[0]
    mismatched: dict[str, int] = {}
    first_mismatch = None
    compared = drawn_python_not_native = 0
    previous_differs = previous_compared = fade_differs = 0
    for entry in records:
        block, facts = core.spectrum_block(entry["record"], entry["card"])
        expected = bytearray(entry["python_block"])
        if block is None:
            drawn_python_not_native += 1
            if first_mismatch is None:
                first_mismatch = {"key": entry["key"], "index": entry["index"], "reason": facts.get("reason")}
            continue
        if not entry["flag"] and time_offset is not None:
            expected[time_offset:time_offset + 4] = block[time_offset:time_offset + 4]   # unread without a flag sheet
        compared += 1
        # Member by member (the two packers may pad the block's tail differently; padding is never read).
        names = [name for name, (offset, size) in members.items()
                 if len(expected) < offset + size or len(block) < offset + size
                 or expected[offset:offset + size] != block[offset:offset + size]]
        if names:
            for name in names:
                mismatched[name] = mismatched.get(name, 0) + 1
            if first_mismatch is None:
                first_mismatch = {"key": entry["key"], "index": entry["index"], "members": names[:12]}
        # Negative controls: the record's first bar raised (a field the block reads), and the fade nudged.
        mutated = bytearray(entry["record"])
        first_bar = struct.unpack_from("<d", mutated, bars_offset)[0]
        struct.pack_into("<d", mutated, bars_offset, first_bar + 0.25)
        other, _ = core.spectrum_block(bytes(mutated), entry["card"])
        previous_compared += 1
        previous_differs += int(other != block)
        nudged = dict(entry["card"], content_fade=entry["card"]["content_fade"] * 1.001 + 1e-3)
        fade_block, _ = core.spectrum_block(entry["record"], nudged)
        fade_differs += int(fade_block != block)
    runs = sorted({entry["key"] for entry in records})
    checks = {
        "every_run_drew": len(runs) == len(conventions_identity.mode_runs("spectrum", True)),
        "frames_compared": compared > 0 and compared == len(records),
        "module_layout_is_the_python_layout": not layout_differs and all(
            entry["python"] == entry["module"] for entry in array_strides.values()),
        "identical": not mismatched and not drawn_python_not_native,
        "control_mutated_record_differs": previous_compared > 0 and previous_differs == previous_compared,
        "control_fade_differs": fade_differs == compared,
    }
    return {"pass": all(checks.values()), "checks": checks, "runs": runs, "frames": len(records),
            "compared": compared, "mismatched_members": mismatched, "first_mismatch": first_mismatch,
            "drawn_by_python_not_native": drawn_python_not_native, "layout": layout,
            "layout_differs": layout_differs, "array_strides": array_strides,
            "controls": {"previous_compared": previous_compared, "previous_differs": previous_differs,
                         "fade_differs": fade_differs}}


def python_references(samples) -> list:
    """The Python renderer's own draw of each sampled frame into a transparent target the item's size (top-down RGBA;
    the quad through a Qt Quick-like item matrix, Y down)."""
    import numpy as np
    from OpenGL import GL as gl
    from PySide6.QtGui import QOffscreenSurface, QOpenGLContext, QSurfaceFormat

    from rendering.quick.visualizer.render_host import QuickVisualizerRenderHost

    fmt = QSurfaceFormat()
    fmt.setRenderableType(QSurfaceFormat.OpenGL)
    fmt.setProfile(QSurfaceFormat.CoreProfile)
    fmt.setVersion(4, 6)
    context = QOpenGLContext()
    context.setFormat(fmt)
    if not context.create():
        raise RuntimeError("no OpenGL 4.6 context for the Python reference")
    surface = QOffscreenSurface()
    surface.setFormat(fmt)
    surface.create()
    if not context.makeCurrent(surface):
        raise RuntimeError("the Python reference's context is not current")
    host = QuickVisualizerRenderHost()
    references = []
    try:
        for index, snapshot, logical_size, quarters in samples:
            dpr = float(snapshot.presentation.dpr)
            width, height = (int(round(v * dpr)) for v in logical_size)
            color = gl.glGenTextures(1)
            gl.glBindTexture(gl.GL_TEXTURE_2D, color)
            gl.glTexImage2D(gl.GL_TEXTURE_2D, 0, gl.GL_RGBA8, width, height, 0, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE, None)
            fbo = gl.glGenFramebuffers(1)
            gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, fbo)
            gl.glFramebufferTexture2D(gl.GL_FRAMEBUFFER, gl.GL_COLOR_ATTACHMENT0, gl.GL_TEXTURE_2D, color, 0)
            gl.glViewport(0, 0, width, height)
            gl.glDisable(gl.GL_SCISSOR_TEST)
            gl.glClearColor(0.0, 0.0, 0.0, 0.0)
            gl.glClear(gl.GL_COLOR_BUFFER_BIT)
            w, h = logical_size
            matrix = (2.0 / w, 0.0, 0.0, 0.0, 0.0, -2.0 / h, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, -1.0, 1.0, 0.0, 1.0)
            host.render(snapshot=snapshot, viewport=(0, 0, width, height), logical_size=(float(w), float(h)),
                        matrix_values=matrix)
            gl.glPixelStorei(gl.GL_PACK_ALIGNMENT, 1)
            raw = gl.glReadPixels(0, 0, width, height, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE)
            raw = raw if isinstance(raw, (bytes, bytearray)) else np.asarray(raw).tobytes()
            rows = np.frombuffer(raw, dtype=np.uint8).reshape(height, width, 4)[::-1].copy()
            references.append((index, rows, quarters))
            gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, 0)
            gl.glDeleteFramebuffers(1, [fbo])
            gl.glDeleteTextures([color])
    finally:
        host.release_resources()
        context.doneCurrent()
        surface.destroy()
    return references


# --------------------------------------------------------------------------------------------------------- the stream

class Stream:
    """A native Spectrum stream the harness writes (the engine worker's side): a frame mapping and its writer."""

    def __init__(self) -> None:
        from core.visualizer_engine.packet_abi import FramePacketWriter, create_frame_mapping, mode_code

        self.code = mode_code("spectrum")
        self.memory = create_frame_mapping(generation=IDENTITY["runtime_generation"], slot_bytes=SLOT_BYTES,
                                           engine_generation=IDENTITY["engine_generation"],
                                           activation_id=IDENTITY["activation_id"], mode_code=self.code,
                                           token=uuid.uuid4().hex[:12])
        self.writer = FramePacketWriter(self.memory.buf)
        self.closed = False

    @property
    def name(self) -> str:
        return self.memory.name

    @property
    def expect(self) -> dict:
        return {**IDENTITY, "mode_code": self.code}

    def publish(self, record: bytes, timestamp: float) -> int:
        from core.visualizer_engine import spectrum_native_schema
        from core.visualizer_engine.packet_abi import FLAG_PRESENT_FRAME

        return self.writer.publish(record, payload_schema=spectrum_native_schema.SCHEMA_ID, logical_timestamp=timestamp,
                                   flags=FLAG_PRESENT_FRAME, mode_code=self.code, **IDENTITY)

    def consumed(self) -> int:
        return self.writer.consumed_sequence

    def close(self) -> None:
        if self.closed:
            return
        self.closed = True
        self.writer.release()
        self.memory.close()
        self.memory.unlink()


SCENE_QML = b"""import QtQuick
Rectangle {
    color: "#000000"
    Item { objectName: "contentHost"; x: %(margin)d; y: %(margin)d; width: 4; height: 4 }
}
""" % {b"margin": MARGIN}


class Scene:
    """An opaque black display with one native Spectrum at (MARGIN, MARGIN), its target on the item's own rect."""

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
        self.spectrum = core.spectrum(self.content)

    def place(self, card: dict) -> None:
        """The target on the item's own rect (no coverage: the Python reference draws the whole item too)."""
        width, height = card["item_size"]
        self.spectrum.composite.set(rect=[0.0, 0.0, width, height], coverage=None, quarters=int(card["quarters"]),
                                    visible=True)
        self.spectrum.present_raw(card)

    def read(self, card: dict):
        from dataclasses import asdict

        from composite_analysis import frame_rows

        rows = frame_rows(asdict(self.host.read()))
        dpr = float(card["dpr"])
        left = top = int(round(MARGIN * dpr))
        width, height = (int(round(v * dpr)) for v in card["item_size"])
        return rows[top:top + height, left:left + width]

    def close(self, app) -> None:
        self.spectrum.composite.destroy()
        self.host.set_content(None)
        host_check._drop_item(app, self.root)


def _card_for_item(card: dict) -> dict:
    """The card with its target on the item's own rect (offset 0)."""
    dpr = float(card["dpr"])
    width, height = card["item_size"]
    quarters = int(card["quarters"])
    target = [height * dpr, width * dpr] if quarters % 2 else [width * dpr, height * dpr]
    return dict(card, item_from_target=[1.0 / dpr, 0.0, 0.0, 0.0, 1.0 / dpr, 0.0],
                target_size=[float(round(v)) for v in target])


def round_item(core, engine, app, host, records: list[dict]) -> dict:
    """The item's contract on one API (see the module docstring)."""
    chosen = [entry for entry in records if entry["key"] == "spectrum"][:40]
    card = _card_for_item(chosen[0]["card"])
    host.set_device_pixel_ratio(float(card["dpr"]))
    scene = Scene(core, engine, host)
    stream = Stream()
    facts: dict = {}
    checks: dict = {}
    try:
        scene.place(card)
        scene.spectrum.bind(stream.name, expect=stream.expect)
        scene.read(card)
        base = scene.spectrum.state()
        # Frames: one accepted and one record per published frame.
        sequences = []
        for step, entry in enumerate(chosen[:10]):
            sequences.append(stream.publish(entry["record"], float(step)))
            scene.spectrum.update()
            scene.read(card)
        after = scene.spectrum.state()
        checks["each_frame_accepted_once"] = after["accepted"] - base["accepted"] == 10
        checks["each_frame_recorded_once"] = after["records"] - base["records"] == 10
        checks["drawn"] = after["draws"] - base["draws"] == 10
        checks["acknowledged_at_accept"] = stream.consumed() == sequences[-1]
        # At rest: frames without a new publication record nothing.
        host.frames(REST_FRAMES)
        scene.spectrum.update()
        host.frames(REST_FRAMES)
        rest = scene.spectrum.state()
        checks["nothing_recorded_at_rest"] = rest["records"] == after["records"]
        # D2's head read consumes nothing.
        published = stream.publish(chosen[10]["record"], 10.0)
        heads = [scene.spectrum.head() for _ in range(10)]
        checks["head_reads_the_newest_slot"] = all(h and int(h["sequence"]) == published for h in heads)
        checks["head_consumes_nothing"] = stream.consumed() == sequences[-1]
        scene.spectrum.update()
        lit = scene.read(card)
        checks["head_frame_then_accepted"] = stream.consumed() == published and int(lit[..., :3].max()) > 0
        # The drop edge: the card clears; a newer frame draws again.
        scene.spectrum.drop_retained_frame()
        dropped = scene.read(card)
        checks["drop_clears_the_card"] = int(dropped[..., :3].max()) == 0
        stream.publish(chosen[11]["record"], 11.0)
        scene.spectrum.update()
        again = scene.read(card)
        checks["newer_frame_draws_after_drop"] = int(again[..., :3].max()) > 0
        # Unbind: the reader goes on the render thread at the next sync.
        live_bound = core.packet_reader_live()
        scene.spectrum.unbind()
        cleared = scene.read(card)
        state = scene.spectrum.state()
        live_unbound = core.packet_reader_live()
        checks["unbind_clears_the_card"] = int(cleared[..., :3].max()) == 0
        checks["unbind_released_on_the_render_thread"] = (state["released"] >= 1 and state["retiring"] == 0
                                                          and live_unbound["views"] == live_bound["views"] - 1)
        facts["live"] = {"bound": live_bound, "unbound": live_unbound}
        facts["close_during_copy"] = close_during_copy(scene, card, chosen, controls=())
        facts["close_during_copy_control"] = close_during_copy(scene, card, chosen, controls=("accept_after_retire",))
        c, n = facts["close_during_copy"], facts["close_during_copy_control"]
        checks["close_during_copy_discards"] = bool(c.get("paused") and c.get("discarded") == 1
                                                    and c.get("accepted_after") == c.get("accepted_before")
                                                    and c.get("retire_ms", 1e9) < 50.0)
        checks["control_accepts_after_retire"] = bool(n.get("paused") and n.get("discarded") == 0
                                                      and n.get("accepted_after") == n.get("accepted_before") + 1)
        facts["state"] = scene.spectrum.state()
    finally:
        stream.close()
        scene.close(app)
        host.frames(2)
        host_check._flush_deletes(app)
    facts["live_at_end"] = {"readers": core.packet_reader_live(), "composites": core.composite_live()}
    live = facts["live_at_end"]
    checks["nothing_left"] = (live["readers"]["readers"] == 0 and live["readers"]["views"] == 0
                              and live["composites"]["spectrum_sources"] == 0
                              and live["composites"]["spectrum_resources"] == 0)
    return {"pass": all(checks.values()), "checks": checks, "facts": facts}


def close_during_copy(scene, card: dict, chosen: list[dict], controls: tuple[str, ...]) -> dict:
    """D1's test: the reader paused inside a copy; another thread closes and unlinks the mapping and retires the
    stream (timed: it never waits for the paused render thread); the read resumes."""
    stream = Stream()
    result: dict = {"controls": list(controls)}
    try:
        scene.spectrum.bind(stream.name, expect=stream.expect, controls=("pause_in_copy", *controls))
        before = scene.spectrum.state()["reader"]
        result["accepted_before"] = int(before["accepted"])
        stream.publish(chosen[0]["record"], 0.0)

        def side() -> None:
            result["paused"] = scene.spectrum.wait_paused(10000)
            stream.close()                                   # the owner's close and unlink, during the copy
            started = time.perf_counter()
            scene.spectrum.retire()
            result["retire_ms"] = (time.perf_counter() - started) * 1000.0
            scene.spectrum.resume()

        thread = threading.Thread(target=side, name="spectrum-check-close-during-copy")
        thread.start()
        scene.spectrum.update()
        scene.read(card)                                     # the render thread reads (and pauses) at this sync
        thread.join(30.0)
        reader = scene.spectrum.state()["reader"]
        result["accepted_after"] = int(reader["accepted"])
        result["discarded"] = int(reader["copies_discarded"])
        result["last_read"] = scene.spectrum.state()["last_read"]
    finally:
        stream.close()
        scene.spectrum.unbind()
        scene.read(card)
    return result


def round_pixels(core, engine, app, host, api: str, records: list[dict], references: list, out: Path) -> dict:
    """The sampled frames drawn by the native item against the references (see the module docstring)."""
    import numpy as np

    scene = None
    stream = Stream()
    compared = differing = 0
    max_level = 0
    worst = None
    native_frames = {}
    timings = []
    try:
        for step, (index, reference, _quarters) in enumerate(references):
            entry = records[index]
            card = _card_for_item(entry["card"])
            if scene is None:
                host.set_device_pixel_ratio(float(card["dpr"]))
                scene = Scene(core, engine, host)
                scene.spectrum.bind(stream.name, expect=stream.expect)
                host.set_gpu_timer(True)
            scene.place(card)
            stream.publish(entry["record"], float(step))
            scene.spectrum.update()
            drawn = scene.read(card)
            native_frames[index] = drawn
            if drawn.shape[:2] != reference.shape[:2]:
                differing += 1
                worst = worst or {"index": index, "shape": [list(drawn.shape), list(reference.shape)]}
                continue
            compared += 1
            delta = np.abs(drawn[..., :3].astype(np.int16) - reference[..., :3]).max()
            if delta:
                differing += 1
                if int(delta) > max_level:
                    max_level = int(delta)
                    worst = {"index": index, "key": entry["key"], "frame": entry["index"], "level": int(delta),
                             "pixels": int((np.abs(drawn[..., :3].astype(np.int16) - reference[..., :3]).max(axis=2)
                                            > 0).sum())}
        timings = [sample.nanoseconds for sample in host.gpu_samples() if sample.kind == 2]
        host.set_gpu_timer(False)
    finally:
        stream.close()
        if scene is not None:
            scene.close(app)
        host.frames(2)
        host_check._flush_deletes(app)
    np.savez_compressed(_work(out) / f"native_{api}.npz", **{str(k): v for k, v in native_frames.items()})
    _sheet(out, api, references[:4], native_frames)
    ordered = sorted(timings)
    gpu = {"surface_passes": len(ordered),
           "median_ms": round(ordered[len(ordered) // 2] / 1e6, 4) if ordered else None,
           "p90_ms": round(ordered[int(len(ordered) * 0.9)] / 1e6, 4) if ordered else None}
    checks = {"samples_compared": compared > 0 and compared == len(references)}
    if api == "opengl":
        checks["equal_to_the_python_renderer"] = differing == 0
    return {"pass": all(checks.values()), "checks": checks, "compared": compared, "differing": differing,
            "max_level": max_level, "worst": worst, "gpu": gpu}


def vulkan_against_opengl(out: Path) -> dict:
    """Rule (b)'s first form: the Vulkan frames against the native OpenGL frames of the same samples."""
    import numpy as np

    work = _work(out)
    gl_path, vk_path = work / "native_opengl.npz", work / "native_vulkan.npz"
    if not gl_path.exists() or not vk_path.exists():
        return {"pass": False, "error": "a native frame set is missing"}
    gl, vk = np.load(gl_path), np.load(vk_path)
    compared = differing = max_level = 0
    for key in gl.files:
        if key not in vk.files or gl[key].shape != vk[key].shape:
            differing += 1
            continue
        compared += 1
        level = int(np.abs(gl[key][..., :3].astype(np.int16) - vk[key][..., :3]).max())
        differing += int(level > 0)
        max_level = max(max_level, level)
    return {"pass": compared > 0 and max_level <= VULKAN_TOLERANCE, "compared": compared, "differing": differing,
            "max_level": max_level, "tolerance": VULKAN_TOLERANCE}


def _sheet(out: Path, api: str, references, native_frames) -> None:
    import numpy as np
    from PIL import Image

    rows = []
    for index, reference, _quarters in references:
        drawn = native_frames.get(index)
        if drawn is None or drawn.shape != reference.shape:
            continue
        delta = np.clip(np.abs(drawn[..., :3].astype(np.int16) - reference[..., :3]) * 64, 0, 255).astype(np.uint8)
        rows.append(np.concatenate([reference[..., :3], drawn[..., :3], delta], axis=1))
    if rows:
        width = max(row.shape[1] for row in rows)
        sheet = np.concatenate([np.pad(row, ((0, 4), (0, width - row.shape[1]), (0, 0))) for row in rows], axis=0)
        Image.fromarray(sheet, "RGB").save(out / f"pixels_{api}_python_native_difference_x64.png")


# --------------------------------------------------------------------------------------------------------- the child

def _save_records(out: Path, records: list[dict], references: list) -> None:
    import numpy as np

    work = _work(out)
    rows = [{"key": e["key"], "index": e["index"], "flag": e["flag"], "card": e["card"],
             "record": base64.b64encode(e["record"]).decode("ascii")} for e in records]
    (work / "records.json").write_text(json.dumps(rows), encoding="utf-8")
    np.savez_compressed(work / "references.npz", **{str(index): rows_ for index, rows_, _q in references})


def _load_records(out: Path) -> tuple[list[dict], list]:
    import numpy as np

    work = _work(out)
    rows = json.loads((work / "records.json").read_text(encoding="utf-8"))
    records = [dict(row, record=base64.b64decode(row["record"])) for row in rows]
    data = np.load(work / "references.npz")
    references = [(int(key), data[key], 0) for key in sorted(data.files, key=int)]
    return records, references


def child(args) -> dict:
    root = host_check._root(args.repo)
    out = Path(args.out_dir)
    record: dict = {"api": args.api, "rounds": list(args.rounds), "module_loaded": False, "instance_created": False}
    if args.api == "opengl":
        from rendering.quick.bootstrap import configure_quick_graphics

        configure_quick_graphics(reason="spectrum-check")       # Qt Quick on OpenGL, as the product selects it
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
    if args.api == "opengl":
        records, samples = capture_runs(args.sample_every)
        references = python_references(samples)
        _save_records(out, records, references)
        del samples
        if "block" in args.rounds:
            try:
                record["block"] = round_block(core, records)
            except Exception:
                record["block"] = {"pass": False, "error": traceback.format_exc()}
    else:
        records, references = _load_records(out)
    engine = QQmlEngine()
    host = None
    try:
        host = core.hidden_host(1920 + 2 * MARGIN, 1080 + 2 * MARGIN)
        for name in [n for n in args.rounds if n != "block"]:
            if vulkan:
                core.set_vulkan_phase(f"n25 {name}")
            try:
                if name == "item":
                    record[name] = round_item(core, engine, app, host, records)
                else:
                    record[name] = round_pixels(core, engine, app, host, args.api, records, references, out)
            except Exception:
                record[name] = {"pass": False, "error": traceback.format_exc()}
    finally:
        if host is not None:
            if vulkan:
                core.set_vulkan_phase("n25 close")
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
    if "block" in args.rounds and args.api != "opengl":
        record["rounds"] = [n for n in record["rounds"] if n != "block"]
    return record


def api_verdict(api: str, record: dict, require_validation: bool) -> tuple[bool, list[str]]:
    ok, failed = host_check.api_verdict(api, record, require_validation)
    if record.get("module_loaded") and (api != "vulkan" or record.get("instance_created")):
        live = record.get("composites_at_end") or {}
        if any(live.get(key) for key in ("items", "surfaces", "surface_resources", "spectrum_sources",
                                         "spectrum_resources")):
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
    parser.add_argument("--sample-every", type=int, default=40, help="every Nth drawn frame of each run is a pixel sample")
    parser.add_argument("--label", default="n25_spectrum")
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

    if "opengl" not in args.apis:
        parser.error("the OpenGL child captures the frames and the references every other API compares against")
    vk_validation.use_layer_path(args.layer_path, _ALLOWED_ENV)
    root = host_check._root(args.repo)
    from tools import artifact_paths

    out = artifact_paths.evidence_dir("native_core", "n2_5", args.label)
    out.mkdir(parents=True, exist_ok=True)
    environment = vk_validation.environment_record(_ALLOWED_ENV)
    results: dict = {}
    for api in [a for a in APIS if a in args.apis]:
        child_json = out / f"child_{api}.json"
        command = [sys.executable, str(Path(__file__).resolve()), "--child", "--api", api, "--repo", str(root),
                   "--module-dir", args.module_dir, "--out-dir", str(out), "--child-json", str(child_json),
                   "--sample-every", str(args.sample_every), "--rounds", *args.rounds]
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
    if "vulkan" in results and "pixels" in args.rounds:
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
    print("N25 VERDICT " + ("PASS" if not failed else "FAIL: " + "; ".join(failed)[:4000]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
