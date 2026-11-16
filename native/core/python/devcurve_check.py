"""N5.1's proof of Spline Curve (mode id ``devcurve``) on the native core as generic mode content (Current_Plan.md item
8b; D12), through ``rendering.native``.

The module (``release/native_module``, built on GitHub) is loaded the product's way, in one child process per graphics
API (Qt Quick's API is process-wide): OpenGL first, then Vulkan on the module's own instance and devices (D6). No window
is ever visible: the Python renderer draws into hidden targets and the native item into the module's hidden host.

The OpenGL child captures the frames first: the production owner draws Spline Curve in process through every run of
the widened set (``tools/conventions_identity.mode_runs("devcurve", offers=True)``: variants a and b and every Choice
offer; settings from the spec, never presets) with the Python renderer, on recorded music (the shipped clip), and every
frame it draws is kept: its record (``devcurve_native_schema.encode``), its card (the route's own), its settings (the
route's ``GENERIC_MODE_SETTINGS``) and the DevCurveDraw block the Python renderer bound.

Rounds:
  block   (OpenGL child; GPU-free on the native side) the module's ``mode_blocks`` for each captured frame against the
          Python renderer's block, member by member at the Python packer's offsets (uMatrix aside: the Python quad's
          matrix, the core's zeros, read by no fragment). Every member filled from one source. Controls: a curve sample
          raised and the card's fade nudged each change the module's block.
  item    (each API) the item's contract in the hidden host: one record per accepted frame, nothing recorded at rest,
          the drop edge clears the card and a newer frame draws again, a refused frame (a NaN in the record) keeps the
          card, counted with its reason, an unbind keeps the last frame for the route's fade; no Python thread state on
          the render thread (control: a host rendering on the GUI thread counts them). Rule (g): a Settings change (a
          layer colour, its outline width) and a Studio-shaped change (the record's curves) each show on the same module
          with the same program (its generation unchanged).
  pixels  (each API) a sample of the captured frames drawn by the native item against the Python renderer's own draw
          of the same frame into a transparent target of the item's size (OpenGL child; premultiplied over black is the
          same colour), at dpr 1 and 1.5: on OpenGL within the composite's tolerance for a translucent mode
          (``owner_render_parity.rule_a_verdict``: rule (a)'s first form, before the owner-level run
          ``owner_render_parity.py --native --mode devcurve``); on Vulkan, against the native OpenGL frames within
          VULKAN_RULE_B, pixel by pixel with the reference's alpha as the mask (rule (b)). The surface's GPU time per pass (N2.6's timer) at each dpr.

Usage (repository venv, from the checkout holding the built module):
  python native/core/python/devcurve_check.py --module-dir release/native_module --require-validation
      --layer-path D:\\Temp\\Scratch\\SRPSS\\native_spike\\validation_layers\\extracted
  [--apis opengl vulkan] [--rounds block item pixels] [--sample-every 40] [--label n51_devcurve]
Evidence: .artifacts/evidence/native_core/n5_1_devcurve/<date>_<label>/ (summary.json; one PNG sheet per API and dpr of
a few samples beside their reference). Exit 0 whenever the harness ran; the verdict is the last printed line
("N51 VERDICT PASS" or "N51 VERDICT FAIL: ...").
"""
from __future__ import annotations

import argparse
import base64
import json
import math
import struct
import subprocess
import sys
import time
import traceback
import uuid
from pathlib import Path
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

ROOT = HERE.parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import vk_validation  # noqa: E402  (native/core/python)
import host_check  # noqa: E402
from tools import pixel_tolerance as pt  # noqa: E402

MODE_ID = "devcurve"
APIS = ("opengl", "vulkan")
ROUNDS = ("block", "item", "pixels")
CHILD_TIMEOUT_S = 1800
MARGIN = 8                       # logical pixels between the display's corner and the item
DPRS = (1.0, 1.5)
HOST_PIXELS = (int(math.ceil((1920 + 2 * MARGIN) * 1.5)), int(math.ceil((1080 + 2 * MARGIN) * 1.5)))
REST_FRAMES = 3
#: Rule (b), judged pixel by pixel by the shared tolerance (``tools/pixel_tolerance.py``, D12 "The pixel tolerance"):
#: the two drivers round a translucent pixel (the reference's own alpha strictly between 0 and 255: the mask, saved by
#: the OpenGL child as work/references.npz) one level apart, and a few opaque ones where a value lies within float
#: error of a half level. Measured over the 90 sampled frames (dpr 1 and 1.5): 14 differ, by at most 2 pixels, every
#: one exactly one level off; at most 1 of them outside the mask (scatter, 1 times 1.5 rounded up). No tie.
VULKAN_RULE_B = pt.Tolerance("spline curve, Vulkan against OpenGL (rule b)", masked_level=1, scatter_pixels=2)
SLOT_BYTES = 4096                # one Spline Curve record (3200 bytes) per slot, with room
IDENTITY = {"runtime_generation": 7, "engine_generation": 3, "activation_id": 11}
_ALLOWED_ENV: set[str] = set()


def _work(out: Path) -> Path:
    path = out / "work"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _pack() -> bytes:
    from rendering.native.program_values import mode_fragment_pack

    return mode_fragment_pack(MODE_ID)


def _passes():
    from rendering.native.mode import ModePass

    return [ModePass(MODE_ID, _pack(), "alpha")]


def _schema():
    from core.visualizer_engine import devcurve_native_schema

    return devcurve_native_schema.SCHEMA


def _shown(card: dict, presentation) -> dict:
    """The core members' card the route hands the generic item (``_ModeContent.shown_card``)."""
    from rendering.quick.visualizer.native_route import _ModeContent

    return _ModeContent.shown_card(None, card, SimpleNamespace(presentation=presentation))


# --------------------------------------------------------------------------------------------------------- capture

def capture_runs(sample_every: int) -> tuple[list[dict], list]:
    """Every frame the Python renderer draws through the widened run set: (records, the snapshots sampled for pixels).
    Each record: run key, frame index, the native record, the route's card, the settings, the core card and the
    Python block."""
    from core.visualizer_engine import devcurve_native_schema
    from rendering.gl_programs.portable import pack_block
    from rendering.native.composite import composite_geometry
    from rendering.native.spectrum import spectrum_presentation
    from rendering.quick.visualizer.implementations import devcurve as python_devcurve
    from rendering.quick.visualizer.native_route import GENERIC_MODE_SETTINGS
    from tools import conventions_identity
    import tools.expanded_visualizer_evidence as evidence
    from tools.visualizer_replay import owner_render_parity as parity
    from tools.visualizer_replay import owner_worker_gate as gate
    from widgets.spotify_visualizer import engine_worker_link

    clip = evidence.shipped_clip(5.5)
    records: list[dict] = []
    samples: list = []
    renderer = python_devcurve.QuickDevCurveRenderer
    original = renderer.render
    current: dict = {"key": "", "index": 0}

    def capturing(self, frame):
        original(self, frame)
        snapshot = frame.snapshot
        presentation = snapshot.presentation
        dpr = float(presentation.dpr)
        pixels = (int(frame.viewport[2]), int(frame.viewport[3]))
        card = spectrum_presentation(presentation, composite_geometry(presentation),
                                     window_size=(pixels[0] / dpr, pixels[1] / dpr), window_pixels=pixels)
        values = dict(self._values)
        values["uMatrix"] = (0.0,) * 16
        entry = {"key": current["key"], "index": current["index"], "card": card,
                 "shown": _shown(card, presentation),
                 "settings": GENERIC_MODE_SETTINGS[MODE_ID](snapshot, card),
                 "record": devcurve_native_schema.encode(snapshot.logical),
                 "python_block": pack_block(python_devcurve.DEVCURVE_BLOCK, values),
                 "logical_content_rect": list(frame.logical_content_rect)}
        records.append(entry)
        if current["index"] % sample_every == 0:
            samples.append((len(records) - 1, snapshot, tuple(frame.logical_size), frame.content_rotation_quarters))
        current["index"] += 1

    renderer.render = capturing
    try:
        for suffix, settings in conventions_identity.mode_runs(MODE_ID, True):
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
    return records, samples


def python_references(samples, dpr: float) -> list:
    """The Python renderer's own draw of each sampled frame at ``dpr`` into a transparent target the item's size
    (top-down RGBA): ``spectrum_check.python_references`` with the snapshot's presentation at that ratio."""
    import dataclasses

    import spectrum_check

    moved = []
    for index, snapshot, logical_size, quarters in samples:
        presentation = dataclasses.replace(snapshot.presentation, dpr=float(dpr))
        moved.append((index, dataclasses.replace(snapshot, presentation=presentation), logical_size, quarters))
    return spectrum_check.python_references(moved)


# --------------------------------------------------------------------------------------------------------- block

def round_block(core, records: list[dict]) -> dict:
    from rendering.gl_programs.scene3d import _std140_type
    from rendering.quick.visualizer.implementations.devcurve import DEVCURVE_BLOCK
    from tools import conventions_identity

    schema = _schema()
    passes = _passes()
    sizes = {"float": 4, "int": 4, "vec2": 8, "vec4": 16, "mat4": 64}
    members = {}
    for (name, glsl_type), offset in zip(DEVCURVE_BLOCK.fields, DEVCURVE_BLOCK.offsets):
        _element, count, _alignment, stride = _std140_type(glsl_type)
        members[name] = (offset, count * stride if "[" in glsl_type else sizes[glsl_type])
    curve_offset = schema.layout.field("u_devcurve_curve_bass").offset
    mismatched: dict[str, int] = {}
    first_mismatch = None
    layout_differs: dict = {}
    sources: dict = {}
    compared = refused = 0
    mutated_differs = fade_differs = 0
    for entry in records:
        target = tuple(int(v) for v in entry["card"]["target_size"])
        try:
            (block,), facts = core.mode_blocks(schema, passes, entry["settings"], entry["record"], entry["shown"],
                                               target)
        except ValueError as exc:
            refused += 1
            first_mismatch = first_mismatch or {"key": entry["key"], "index": entry["index"], "refused": str(exc)}
            continue
        if not sources:
            sources = dict(facts["passes"][0]["sources"])
            rows = {row[0]: row for row in facts["program"]["passes"][0]["block"]["members"]}
            layout_differs = {name: {"python": offset, "module": (rows.get(name) or [None, None, None])[2]}
                              for name, (offset, _size) in members.items()
                              if (rows.get(name) or [None, None, None])[2] != offset}
        compared += 1
        expected = entry["python_block"]
        if "u_target_px" in members:
            # fragPixel's target is the render target's pixels (N1.4): the window's on the Python route, the core's own
            # target on the native one (as tests/test_native_devcurve.py's _python_block expects).
            offset = members["u_target_px"][0]
            if len(expected) >= offset + 8:
                patched = bytearray(expected)
                struct.pack_into("<2f", patched, offset, float(target[0]), float(target[1]))
                expected = bytes(patched)
        names = [name for name, (offset, size) in members.items() if name != "uMatrix"
                 and (len(expected) < offset + size or block[offset:offset + size] != expected[offset:offset + size])]
        for name in names:
            mismatched[name] = mismatched.get(name, 0) + 1
        if names and first_mismatch is None:
            first_mismatch = {"key": entry["key"], "index": entry["index"], "members": names[:12]}
        mutated = bytearray(entry["record"])
        struct.pack_into("<d", mutated, curve_offset, struct.unpack_from("<d", mutated, curve_offset)[0] + 0.25)
        other = core.mode_blocks(schema, passes, entry["settings"], bytes(mutated), entry["shown"], target)[0][0]
        mutated_differs += int(other != block)
        faded = dict(entry["shown"], content_fade=float(entry["shown"]["content_fade"]) * 0.5 + 0.25)
        fade_block = core.mode_blocks(schema, passes, entry["settings"], entry["record"], faded, target)[0][0]
        fade_differs += int(fade_block != block)
    runs = sorted({entry["key"] for entry in records})
    by_source: dict = {}
    for name, source in sources.items():
        by_source.setdefault(source, []).append(name)
    checks = {
        "every_run_drew": len(runs) == len(conventions_identity.mode_runs(MODE_ID, True)),
        "frames_compared": compared > 0 and compared == len(records),
        "module_layout_is_the_python_layout": not layout_differs,
        "identical": not mismatched and not refused,
        "every_member_has_one_source": set(sources) == set(members),
        "control_mutated_record_differs": mutated_differs == compared,
        "control_fade_differs": fade_differs == compared,
    }
    return {"pass": all(checks.values()), "checks": checks, "runs": runs, "frames": len(records),
            "compared": compared, "refused": refused, "mismatched_members": mismatched,
            "first_mismatch": first_mismatch, "layout_differs": layout_differs,
            "members_by_source": {key: sorted(value) for key, value in by_source.items()},
            "controls": {"mutated_record_differs": mutated_differs, "fade_differs": fade_differs}}


# --------------------------------------------------------------------------------------------------------- the stream

class Stream:
    """A Spline Curve stream the harness writes (the route's side): a frame mapping and its writer."""

    def __init__(self, identity: dict | None = None) -> None:
        from core.visualizer_engine.packet_abi import FramePacketWriter, create_frame_mapping, mode_code

        self.identity = dict(identity or IDENTITY)
        self.code = mode_code(MODE_ID)
        self.memory = create_frame_mapping(generation=self.identity["runtime_generation"], slot_bytes=SLOT_BYTES,
                                           engine_generation=self.identity["engine_generation"],
                                           activation_id=self.identity["activation_id"], mode_code=self.code,
                                           token=uuid.uuid4().hex[:12])
        self.writer = FramePacketWriter(self.memory.buf)
        self.closed = False

    @property
    def name(self) -> str:
        return self.memory.name

    @property
    def expect(self) -> dict:
        return {**self.identity, "mode_code": self.code}

    def publish(self, record: bytes, timestamp: float) -> int:
        from core.visualizer_engine.packet_abi import FLAG_PRESENT_FRAME

        return self.writer.publish(record, payload_schema=_schema().schema_id, logical_timestamp=timestamp,
                                   flags=FLAG_PRESENT_FRAME, mode_code=self.code, **self.identity)

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
    """An opaque black display with one generic item at (MARGIN, MARGIN), its target on the item's own rect."""

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
        self.programmed = False

    def place(self, entry: dict, dpr: float, stream: Stream | None = None) -> dict:
        """The item at ``entry``'s card under ``dpr`` (its target on the item's own rect, no coverage: the Python
        reference draws the whole item too): the program with the settings the first time (then the stream), else the
        settings."""
        import spectrum_check

        card = spectrum_check._card_for_item(dict(entry["card"], dpr=float(dpr)))
        width, height = card["item_size"]
        self.mode.composite.set(rect=[0.0, 0.0, width, height], coverage=None, quarters=int(card["quarters"]),
                                visible=True)
        shown = dict(entry["shown"], **{key: card[key] for key in ("dpr", "item_from_window", "window_from_target")})
        self.mode.card(shown)
        if not self.programmed:
            self.mode.program(_passes(), entry["settings"])
            self.programmed = True
            if stream is not None:
                self.mode.bind(stream.name, _schema(), expect=stream.expect)
        else:
            self.mode.settings(entry["settings"])
        return card

    def read(self, card: dict):
        from dataclasses import asdict

        from composite_analysis import frame_rows

        rows = frame_rows(asdict(self.host.read()))
        dpr = float(card["dpr"])
        width, height = (int(round(v * dpr)) for v in card["item_size"])
        left = top = int(round(MARGIN * dpr))
        return rows[top:top + height, left:left + width]

    def close(self, app) -> None:
        self.mode.composite.destroy()
        self.host.set_content(None)
        host_check._drop_item(app, self.root)


# --------------------------------------------------------------------------------------------------------- pixels

def round_pixels(core, engine, app, host, api: str, records: list[dict], references: dict, out: Path) -> dict:
    import numpy as np

    by_dpr: dict = {}
    native_frames = {}
    for dpr in DPRS:
        scene = None
        stream = Stream()
        stats = {"compared": 0, "differing": 0, "max_level": 0, "worst": None}
        judged: list[dict] = []
        timings = []
        from tools import pixel_tolerance
        from tools.visualizer_replay import owner_render_parity as parity
        try:
            host.set_device_pixel_ratio(float(dpr))
            scene = Scene(core, engine, host)
            host.set_gpu_timer(True)
            for step, (index, reference, _quarters) in enumerate(references[dpr]):
                entry = records[index]
                card = scene.place(entry, dpr, stream)
                stream.publish(entry["record"], float(step))
                scene.mode.update()
                drawn = scene.read(card)
                native_frames[f"{index}@{dpr}"] = drawn
                if drawn.shape[:2] != reference.shape[:2]:
                    stats["differing"] += 1
                    stats["worst"] = stats["worst"] or {"index": index, "shape": [list(drawn.shape),
                                                                                  list(reference.shape)]}
                    continue
                stats["compared"] += 1
                delta = np.abs(drawn[..., :3].astype(np.int16) - reference[..., :3]).max(axis=2)
                level = int(delta.max())
                if level:
                    # The reference is drawn into a transparent target: its own alpha is the translucency mask.
                    verdict = parity.rule_a_frame(drawn[..., :3], reference[..., :3],
                                                  pixel_tolerance.translucent_by_alpha(reference))
                    verdict["index"] = index
                    judged.append(verdict)
                    stats["differing"] += 1
                    if level > stats["max_level"]:
                        stats["max_level"] = level
                        stats["worst"] = {"index": index, "key": entry["key"], "frame": entry["index"],
                                          "level": level, "pixels": int((delta > 0).sum())}
            timings = [sample.nanoseconds for sample in host.gpu_samples() if sample.kind == 2]
            host.set_gpu_timer(False)
        finally:
            stream.close()
            if scene is not None:
                scene.close(app)
            host.frames(2)
            host_check._flush_deletes(app)
        ordered = sorted(timings)
        stats["gpu"] = {"surface_passes": len(ordered),
                        "median_ms": round(ordered[len(ordered) // 2] / 1e6, 4) if ordered else None,
                        "p90_ms": round(ordered[int(len(ordered) * 0.9)] / 1e6, 4) if ordered else None}
        # Rule (a) under the composite's tolerance for a translucent mode (owner_render_parity.rule_a_verdict, the
        # lead's decision on N5.1's per-pixel proof), pixel by pixel through the shared tolerance.
        stats["rule_a"] = parity.rule_a_verdict(judged)
        by_dpr[str(dpr)] = stats
        _sheet(out, api, dpr, references[dpr][:4], native_frames)
    np.savez_compressed(_work(out) / f"native_{api}.npz", **native_frames)
    checks = {f"samples_compared_dpr{dpr}": by_dpr[str(dpr)]["compared"] == len(references[dpr]) > 0 for dpr in DPRS}
    if api == "opengl":
        for dpr in DPRS:
            checks[f"rule_a_within_the_composite_tolerance_dpr{dpr}"] = by_dpr[str(dpr)]["rule_a"]["pass"]
    return {"pass": all(checks.values()), "checks": checks, "by_dpr": by_dpr}


def _sheet(out: Path, api: str, dpr: float, references, native_frames) -> None:
    import numpy as np
    from PIL import Image

    rows = []
    for index, reference, _quarters in references:
        drawn = native_frames.get(f"{index}@{dpr}")
        if drawn is None or drawn.shape != reference.shape:
            continue
        delta = np.clip(np.abs(drawn[..., :3].astype(np.int16) - reference[..., :3]) * 64, 0, 255).astype(np.uint8)
        rows.append(np.concatenate([reference[..., :3], drawn[..., :3], delta], axis=1))
    if rows:
        width = max(row.shape[1] for row in rows)
        sheet = np.concatenate([np.pad(row, ((0, 4), (0, width - row.shape[1]), (0, 0))) for row in rows], axis=0)
        Image.fromarray(sheet, "RGB").save(out / f"pixels_{api}_dpr{dpr}_python_native_difference_x64.png")


def vulkan_against_opengl(out: Path) -> dict:
    """Rule (b): the Vulkan frames against the native OpenGL frames of the same samples."""
    import numpy as np

    work = _work(out)
    gl_path, vk_path = work / "native_opengl.npz", work / "native_vulkan.npz"
    ref_path = work / "references.npz"
    if not gl_path.exists() or not vk_path.exists() or not ref_path.exists():
        return {"pass": False, "error": "a native frame set or the references (the mask's source) is missing"}
    gl, vk, refs = np.load(gl_path), np.load(vk_path), np.load(ref_path)
    compared = differing = max_level = missing = 0
    judged: list[dict] = []
    for key in gl.files:
        if key not in vk.files or key not in refs.files or gl[key].shape != vk[key].shape \
                or refs[key].shape[:2] != gl[key].shape[:2]:
            missing += 1
            continue
        compared += 1
        verdict = pt.judge(vk[key][..., :3], gl[key][..., :3], VULKAN_RULE_B,
                           mask=pt.translucent_by_alpha(refs[key]))
        judged.append(verdict)
        differing += int(verdict["differing"] > 0)
        max_level = max(max_level, int(verdict["max_level"]))
    tolerance = pt.summarise(judged)
    return {"pass": compared > 0 and not missing and tolerance["pass"], "compared": compared,
            "differing": differing, "missing": missing, "max_level": max_level, "tolerance": tolerance,
            "bound": VULKAN_RULE_B.bound()}


# --------------------------------------------------------------------------------------------------------- item

def _record_with(base: bytes, **fields) -> bytes:
    """``base`` with record fields replaced (name -> one number for the field's first element)."""
    out = bytearray(base)
    for name, value in fields.items():
        struct.pack_into("<d", out, _schema().layout.field(name).offset, float(value))
    return bytes(out)


def _find_key(value, key: str) -> list:
    found = []
    if isinstance(value, dict):
        for name, inner in value.items():
            if name == key:
                found.append(inner)
            else:
                found += _find_key(inner, key)
    elif isinstance(value, list):
        for inner in value:
            found += _find_key(inner, key)
    return found


def round_item(core, engine, app, host, records: list[dict]) -> dict:
    chosen = [entry for entry in records if entry["key"] == MODE_ID][:40]
    dpr = 1.5
    host.set_device_pixel_ratio(dpr)
    scene = Scene(core, engine, host)
    stream = Stream()
    facts: dict = {}
    checks: dict = {}
    try:
        card = scene.place(chosen[0], dpr, stream)
        scene.read(card)
        base = scene.mode.state()
        sequences = []
        for step, entry in enumerate(chosen[:10]):
            sequences.append(stream.publish(entry["record"], float(step)))
            scene.mode.update()
            scene.read(card)
        after = scene.mode.state()
        checks["each_frame_accepted_once"] = after["accepted"] - base["accepted"] == 10
        checks["each_frame_recorded_once"] = after["records"] - base["records"] == 10
        checks["drawn"] = after["draws"] - base["draws"] == 10
        checks["acknowledged_at_accept"] = stream.consumed() == sequences[-1]
        # At rest: frames without a new publication record nothing.
        host.frames(REST_FRAMES)
        scene.mode.update()
        host.frames(REST_FRAMES)
        rest = scene.mode.state()
        checks["nothing_recorded_at_rest"] = rest["records"] == after["records"]
        facts["records"] = {"before": base["records"], "after": after["records"], "rest": rest["records"]}
        # Rule (g): a Settings change (a layer colour and its outline width) and a Studio-shaped change (the record's
        # curve) each show, with no pipeline built again and the program unchanged.
        drawn = scene.read(card)
        program_generation = scene.mode.state()["program"]["generation"]
        changed = dict(chosen[9]["settings"])
        changed["u_devcurve_layer_bass_color"] = [1.0, 0.1, 0.1, 1.0]
        changed["u_devcurve_layer_bass_outline_width"] = float(changed["u_devcurve_layer_bass_outline_width"]) * 2.0
        scene.mode.settings(changed)
        scene.mode.update()
        recoloured = scene.read(card)
        checks["settings_change_shows"] = bool((recoloured != drawn).any())
        stream.publish(_record_with(chosen[9]["record"], u_devcurve_curve_bass=0.05), 20.0)
        scene.mode.update()
        reshaped = scene.read(card)
        checks["record_change_shows"] = bool((reshaped != recoloured).any())
        state = scene.mode.state()
        # The same module and the same program (no module build, no new program: rule (g)).
        checks["no_new_program_for_a_settings_or_record_change"] = state["program"]["generation"] == program_generation
        facts["program_generation"] = [program_generation, state["program"]["generation"]]
        scene.mode.settings(chosen[9]["settings"])
        # The drop edge: the card clears; a newer frame draws again.
        stream.publish(chosen[10]["record"], 21.0)
        scene.mode.update()
        lit = scene.read(card)
        scene.mode.drop_retained_frame()
        dropped = scene.read(card)
        checks["drop_clears_the_card"] = int(lit[..., :3].max()) > 0 and int(dropped[..., :3].max()) == 0
        stream.publish(chosen[11]["record"], 22.0)
        scene.mode.update()
        again = scene.read(card)
        checks["newer_frame_draws_after_drop"] = int(again[..., :3].max()) > 0
        # A refused frame (a NaN curve sample: no defined conversion) keeps the card, counted with its reason.
        refused_before = int(scene.mode.state().get("refused_frames", 0))
        stream.publish(_record_with(chosen[12]["record"], u_devcurve_curve_bass=float("nan")), 23.0)
        scene.mode.update()
        kept = scene.read(card)
        refusal = scene.mode.state()
        checks["refused_frame_keeps_the_card"] = bool((kept == again).all()) and int(kept[..., :3].max()) > 0
        checks["refused_frame_counted_once_with_its_reason"] = (
            int(refusal.get("refused_frames", 0)) == refused_before + 1
            and "u_devcurve_curve_bass" in str(refusal.get("last_refusal")))
        facts["refused_frame"] = {"refused_frames": [refused_before, refusal.get("refused_frames")],
                                  "last_refusal": refusal.get("last_refusal")}
        # Unbind: the last drawn frame stays for the route's fade.
        stream.publish(chosen[13]["record"], 24.0)
        scene.mode.update()
        last = scene.read(card)
        scene.mode.unbind()
        after_unbind = scene.read(card)
        checks["unbind_keeps_the_last_frame_for_the_fade"] = (int(last[..., :3].max()) > 0
                                                               and bool((after_unbind == last).all()))
        state = scene.mode.state()
        edges = _find_key(host.state(), "edges_with_python_thread_state")
        facts["thread_probe"] = {"syncs": state.get("syncs_probed"),
                                 "syncs_with_python_thread_state": state.get("syncs_with_python_thread_state"),
                                 "syncs_on_gui_thread": state.get("syncs_on_gui_thread"),
                                 "edges_with_python_thread_state": edges}
        checks["no_python_thread_state_on_the_render_thread"] = bool(
            state.get("syncs_probed") and state.get("syncs_with_python_thread_state") == 0
            and state.get("syncs_on_gui_thread") == 0 and edges and all(value == 0 for value in edges))
    finally:
        stream.close()
        scene.close(app)
        host.frames(2)
        host_check._flush_deletes(app)
    facts["thread_probe_control"] = _gui_thread_probe(core, engine, app, chosen)
    checks["control_gui_thread_host_counts_python_thread_states"] = bool(
        (facts["thread_probe_control"].get("syncs_with_python_thread_state") or 0) > 0)
    live = {"readers": core.packet_reader_live(), "composites": core.composite_live()}
    facts["live_at_end"] = live
    checks["nothing_left"] = (live["readers"]["readers"] == 0 and live["readers"]["views"] == 0
                              and not live["composites"].get("mode_sources")
                              and not live["composites"].get("mode_resources"))
    return {"pass": all(checks.values()), "checks": checks, "facts": facts}


def _gui_thread_probe(core, engine, app, chosen: list[dict]) -> dict:
    """The probe's negative control: the same item on a hidden host rendering on the calling (GUI, Python) thread."""
    host = core.hidden_host(1000, 700, threaded=False)
    result: dict = {}
    try:
        host.set_device_pixel_ratio(1.0)
        scene = Scene(core, engine, host)
        stream = Stream()
        try:
            scene.place(chosen[0], 1.0, stream)
            stream.publish(chosen[0]["record"], 0.0)
            scene.mode.update()
            host.frames(2)
            state = scene.mode.state()
            result = {key: state.get(key) for key in ("syncs_probed", "syncs_with_python_thread_state",
                                                      "syncs_on_gui_thread")}
        finally:
            stream.close()
            scene.close(app)
            host.frames(1)
    finally:
        host.close()
        host_check._flush_deletes(app)
    return result


# --------------------------------------------------------------------------------------------------------- the child

def _save(out: Path, records: list[dict], references: dict) -> None:
    import numpy as np

    work = _work(out)
    rows = [{key: (base64.b64encode(value).decode("ascii") if isinstance(value, bytes) else value)
             for key, value in entry.items() if key != "python_block"} for entry in records]
    (work / "records.json").write_text(json.dumps(rows), encoding="utf-8")
    np.savez_compressed(work / "references.npz", **{f"{index}@{dpr}": rows_ for dpr, refs in references.items()
                                                     for index, rows_, _q in refs})


def _load(out: Path) -> tuple[list[dict], dict]:
    import numpy as np

    work = _work(out)
    rows = json.loads((work / "records.json").read_text(encoding="utf-8"))
    records = [dict(row, record=base64.b64decode(row["record"])) for row in rows]
    data = np.load(work / "references.npz")
    references: dict = {dpr: [] for dpr in DPRS}
    for key in data.files:
        index, dpr = key.split("@")
        references[float(dpr)].append((int(index), data[key], 0))
    for dpr in DPRS:
        references[dpr].sort(key=lambda item: item[0])
    return records, references


def child(args) -> dict:
    root = host_check._root(args.repo)
    out = Path(args.out_dir)
    record: dict = {"api": args.api, "rounds": list(args.rounds), "module_loaded": False, "instance_created": False}
    if args.api == "opengl":
        from rendering.quick.bootstrap import configure_quick_graphics

        configure_quick_graphics(reason="devcurve-check")       # Qt Quick on OpenGL, as the product selects it
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
        references = {dpr: python_references(samples, dpr) for dpr in DPRS}
        _save(out, records, references)
        del samples
        record["captured"] = {"frames": len(records), "samples": len(references[DPRS[0]])}
        if "block" in args.rounds:
            try:
                record["block"] = round_block(core, records)
            except Exception:
                record["block"] = {"pass": False, "error": traceback.format_exc()}
    else:
        records, references = _load(out)
    engine = QQmlEngine()
    host = None
    try:
        host = core.hidden_host(*HOST_PIXELS)
        for name in [n for n in args.rounds if n != "block"]:
            if vulkan:
                core.set_vulkan_phase(f"n51 {name}")
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
                core.set_vulkan_phase("n51 close")
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
    if args.api != "opengl":
        record["rounds"] = [n for n in record["rounds"] if n != "block"]
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
    parser.add_argument("--sample-every", type=int, default=40, help="every Nth drawn frame of each run is a pixel sample")
    parser.add_argument("--label", default="n51_devcurve")
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

    out = artifact_paths.evidence_dir("native_core", "n5_1_devcurve", args.label)
    out.mkdir(parents=True, exist_ok=True)
    environment = vk_validation.environment_record(_ALLOWED_ENV)
    results: dict = {}
    for api in [a for a in APIS if a in args.apis]:
        child_json = out / f"child_{api}.json"
        child_json.unlink(missing_ok=True)  # discard any earlier child record before launch
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
    print("N51 VERDICT " + ("PASS" if not failed else "FAIL: " + "; ".join(failed)[:4000]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
