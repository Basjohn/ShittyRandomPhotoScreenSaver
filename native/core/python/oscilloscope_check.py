"""N5.1's proof of the Oscilloscope on the native core as generic mode content with its overlay target, its instanced
beam over a storage stream and N3.4's bloom and composite (D12, D14, D15, D17; Current_Plan.md, N5.1 Oscilloscope),
through ``rendering.native``: rule (b) (Vulkan against native OpenGL) and the item's contract, with the rounds of
``devcurve_check.py`` (the generic modes' harness) and the Oscilloscope's own pieces, as ``bubble_check.py`` does.

The OpenGL child captures every frame the production owner draws with the Python renderer through the Oscilloscope's
widened run set (``tools/conventions_identity.mode_runs("oscilloscope", offers=True)``: variants a and b and every
Choice offer; settings from the spec, never presets) on the shipped 5.5 s clip, the owner replay's own recipe. Each
frame keeps its record (``oscilloscope_native_schema.encode``), the route's card and settings
(``native_route.OSCILLOSCOPE_SETTINGS``, per drawn ratio for a sampled frame: one device pixel follows the ratio) and the
two blocks the Python renderer bound. The route draws the program its Glow chooses (``oscilloscope_program``); every run
of the set has Glow above 0. Glow 0's program needs ABI 26 (a program's unread fields): its runs are ``--glow-off``.

Rounds (``devcurve_check``'s):
  block   (OpenGL child) the module's blocks of both passes (the graticule's only for a frame that draws it) against the
          Python renderer's, member by member at the Python packer's offsets, ``uMatrix`` aside (the core's own
          item-to-target matrix). Controls: the flare's widening nudged in the record and the card's fade nudged in the
          composite's block each change the module's blocks.
  item    (each API) the item's contract (one record per accepted frame, nothing at rest, the drop edge, a refused
          frame, unbind, no Python thread state on the render thread); rule (g) with a Settings change on
          ``uGlowColour`` and a record change on ``u_widen``.
  pixels  (each API) the sampled frames at dpr 1 and 1.5: on OpenGL against the Python renderer under rule (a)'s
          composite tolerance; on Vulkan against the native OpenGL frames under ``VULKAN_RULE_B`` (rule (b)), the
          reference's alpha as the mask.
The Oscilloscope's own rounds (asked by name):
  offsets (each API; ABI 27) the item inside a larger target at an odd and an even device offset in each axis
          (``OFFSET_PLACEMENTS``, as the route's quad-aligned surface holds it): the same frames as on the item's own
          rect (rule (b)'s bound) and, on OpenGL, rule (a) against the Python renderer, whose SceneTarget starts at the
          item's own pixel.
  cost    (each API) the GPU time per pass at 2560 x 1440 and 4K.

Negative controls (``--control``, each in its own Vulkan child against a finished run's kept OpenGL frames; each must end
"FAILED AS EXPECTED"): ``widen_nudged`` (record), ``alpha_dropped`` (record), ``beam_edge_narrowed`` (shader),
``bloom_dropped`` (program), ``skipped_release`` (item) and ``old_origin`` (the offsets round at the target's origin).

The owner's rule (a) (``owner_render_parity.py --native``) needs the route to draw the mode; until registration (playbook
checklist 18) ``owner`` runs it with the route's registration process-local, every other argument passed through:
  python native/core/python/oscilloscope_check.py owner --out <evidence> --module-dir release/native_module
      --recording <take> --seconds 60 --runs oscilloscope --placements display

Usage (repository venv, from the checkout holding the built module):
  python native/core/python/oscilloscope_check.py --module-dir release/native_module --require-validation
      --layer-path D:\\Temp\\Scratch\\SRPSS\\native_spike\\validation_layers\\extracted [--label n51_oscilloscope]
  python native/core/python/oscilloscope_check.py ... --label n51_oscilloscope --control bloom_dropped
Evidence: .artifacts/evidence/native_core/n5_1_oscilloscope/<date>_<label>/ (summary.json, summary_control_<name>.json,
sheets). Exit 0 whenever the harness ran; the verdict is the last printed line.
"""
from __future__ import annotations

import dataclasses
import importlib.util
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
    """The generic modes' harness (``devcurve_check.py``) as a module of this harness's own, so that the Oscilloscope's
    pieces never reach Spline Curve's harness in one process."""
    spec = importlib.util.spec_from_file_location("_oscilloscope_check_rounds", HERE / "devcurve_check.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


base = _generic_rounds()

MODE_ID = "oscilloscope"
#: Rule (b), judged pixel by pixel by the shared tolerance (D12 "The pixel tolerance") under ``reference_mask`` (the
#: reference's translucent pixels and, with Glow, every pixel its glow lights). Measured over the 5.5 s replay's 126
#: sampled frames (dpr 1 and 1.5; 20 Nov, n5_1_oscilloscope/20261120_n51_oscilloscope/): every differing pixel on the
#: mask, at most 103 a frame, at one level but for ties at two levels (the bloom's float16 chain rounded by two
#: compilers), at most 2 a frame; no scatter, no flip. The bound, the measured worst times 1.5 (the lead's decision, 21
#: Nov; D12 "As built: Oscilloscope"): 3 ties a frame at 2 levels, no scatter.
VULKAN_RULE_B = pt.Tolerance("oscilloscope, Vulkan against OpenGL (rule b)", masked_level=1, scatter_pixels=0,
                             tie_pixels=3, tie_level=2)
#: The negative controls: the rounds each one's Vulkan child runs and what it breaks.
CONTROLS = {
    "widen_nudged": {"rounds": ["pixels"], "breaks": "every record's flare widening raised by 0.5 (a wider beam)"},
    "alpha_dropped": {"rounds": ["pixels"], "breaks": "every record's live trace alpha set to 0 (the live trace gone)"},
    "beam_edge_narrowed": {"rounds": ["pixels"],
                           "breaks": "oscilloscope_beam_body.glsl's anti-aliased edge one pixel inward"},
    "bloom_dropped": {"rounds": ["pixels"], "breaks": "the glow composite reading no bloom (strength 0 in the block)"},
    "skipped_release": {"rounds": ["item"], "breaks": "the content's release edge omitted (stream and item kept)"},
    "old_origin": {"rounds": ["offsets"],
                   "breaks": "stage_control's bloom_at_target_origin: the bloom's grid and the composite's texel at the "
                             "target's origin (before ABI 27), not the item's own pixel"},
}
#: Glow 0's runs (``--glow-off``): the plain program, which leaves the record's bloom strength unread (ABI 26).
GLOW_OFF: dict = {"on": False}
GLOW_OFF_LABEL = "glow_off"
_EDGE_LINE = "    float core = 1.0 - smoothstep(vCore - uPixel, vCore + uPixel, dist);\n"
_EDGE_NARROW = "    float core = 1.0 - smoothstep(vCore - 2.0 * uPixel, vCore, dist);\n"


def _schema():
    from core.visualizer_engine import oscilloscope_native_schema

    return oscilloscope_native_schema.SCHEMA


def _slot_bytes() -> int:
    from rendering.quick.visualizer.native_route import _slot_bytes

    return _slot_bytes(MODE_ID)


#: The child's evidence folder (the control packs are baked under its work folder).
_OUT: dict = {"dir": "."}


def _control_beam_pack(plain: bool) -> bytes:
    """The beam's fragment with its anti-aliased edge narrowed, baked by the product's baker into the work folder."""
    import probe_rings
    from widgets.spotify_visualizer import shaders

    folder = Path(shaders.__file__).resolve().parent
    body = (folder / "oscilloscope_beam_body.glsl").read_text(encoding="utf-8")
    block = (folder / "oscilloscope_beam_block.glsl").read_text(encoding="utf-8")
    if body.count(_EDGE_LINE) != 1:
        raise RuntimeError("oscilloscope_beam_body.glsl: the control's line is not found exactly once")
    text = ("#version 460 core\n" + ("#define OSC_PLAIN\n" if plain else "")
            + body.replace('#include "oscilloscope_beam_block.glsl"\n', block).replace(_EDGE_LINE, _EDGE_NARROW))
    return probe_rings.bake(text, "oscilloscope_beam_control.frag", base._work(Path(_OUT["dir"])) / "control_packs")


def program(glow: bool) -> dict:
    """The Oscilloscope's program as the route builds it (``native_route.oscilloscope_program``), with the active
    control's change."""
    from rendering.quick.visualizer import native_route

    built = native_route.oscilloscope_program(glow)
    passes = list(built["passes"])
    if base.CONTROL == "beam_edge_narrowed":
        pack = _control_beam_pack(not glow)
        passes = [dataclasses.replace(p, pack=pack) if p.name == "oscilloscope_beam" else p for p in passes]
    return dict(built, passes=passes)


def _passes():
    return program(not GLOW_OFF["on"])["passes"]


def program_item(mode, entry: dict, dpr: float, first: bool) -> None:
    """The route's order: the program with its target and stream and the first settings, afterwards the settings."""
    settings = base.settings_at(entry, dpr)
    if first:
        built = program(not GLOW_OFF["on"])
        unread = {"unread": built["unread"]} if built.get("unread") else {}
        mode.program(built["passes"], settings, targets=built["targets"], streams=built["streams"], **unread)
    else:
        mode.settings(settings)


def _field(name: str):
    return _schema().layout.field(name)


def control_record(record: bytes) -> bytes:
    """The record controls: the flare's widening raised, the live trace's alpha dropped, or the bloom strength 0."""
    out = bytearray(record)
    if base.CONTROL == "widen_nudged":
        offset = _field("u_widen").offset
        struct.pack_into("<d", out, offset, struct.unpack_from("<d", out, offset)[0] + 0.5)
    elif base.CONTROL == "alpha_dropped":
        offset = _field("u_alpha").offset
        count = sum(1 for i in range(16) if struct.unpack_from("<d", out, offset + 8 * i)[0] > 0.0)
        if count:
            struct.pack_into("<d", out, offset + 8 * (count - 1), 0.0)
    elif base.CONTROL == "bloom_dropped":
        struct.pack_into("<d", out, _field("u_bloom_strength").offset, 0.0)
    return bytes(out)


def reference_mask(reference):
    """The one-level class's mask: the reference's translucent pixels and, with Glow, every pixel it lights. The glow is
    light the composite adds over the card (premultiplied, alpha untouched), so a pixel it reaches outside the beam
    keeps alpha 0 and a beam pixel at alpha 255 still takes its sum: the pixels a blended layer sums into (D12 "The
    pixel tolerance", point 2; ``mesh_buffer_check``'s "above 0 in an additive scene"). Glow 0 has no such layer."""
    import numpy as np

    translucent = pt.translucent_by_alpha(reference)
    if GLOW_OFF["on"]:
        return translucent
    return translucent | (np.asarray(reference)[..., :4].max(axis=-1) > 0)


def item_settings_change(settings: dict) -> dict:
    """Rule (g)'s Settings change: the beam's glow colour (and so its light) and the analog dimming; at Glow 0, where
    the glow colour lights nothing, the beam's base half width doubled as well."""
    changed = dict(settings, uGlowColour=[1.0, 0.1, 0.1, 1.0], uAnalog=1.0 - float(settings["uAnalog"]))
    if GLOW_OFF["on"]:
        changed["uCoreBase"] = 2.0 * float(settings["uCoreBase"])
    return changed


ITEM_RECORD_FIELD = "u_widen"


def item_reshaped(record: bytes) -> bytes:
    """Rule (g)'s record change: the beam widened."""
    out = bytearray(record)
    offset = _field(ITEM_RECORD_FIELD).offset
    struct.pack_into("<d", out, offset, struct.unpack_from("<d", out, offset)[0] + 1.0)
    return bytes(out)


# --------------------------------------------------------------------------------------------------------- capture

def mode_runs() -> list[tuple[str, dict]]:
    """The run set: the widened set (every run has Glow above 0), or with ``--glow-off`` variants a and b at Glow 0."""
    from tools import conventions_identity

    runs = conventions_identity.mode_runs(MODE_ID, True)
    if GLOW_OFF["on"]:
        return [(":osc_glow=0", {**runs[0][1], "osc_glow": 0.0}), (":b:osc_glow=0", {**runs[1][1], "osc_glow": 0.0})]
    return runs


def capture_runs(sample_every: int) -> tuple[list[dict], list]:
    """Every frame the Python renderer draws through the run set: (records, the snapshots sampled for pixels). Each
    record: run key, frame index, the native record, the route's card, the settings (per drawn ratio for a sample), the
    core card and the Python blocks (the beam's, then the graticule's when it drew)."""
    from core.visualizer_engine import oscilloscope_native_schema
    from rendering.gl_programs.portable import pack_block
    from rendering.native.composite import composite_geometry
    from rendering.native.spectrum import spectrum_presentation
    from rendering.quick.visualizer.implementations import oscilloscope as python_osc
    from rendering.quick.visualizer.native_route import OSCILLOSCOPE_SETTINGS
    import tools.expanded_visualizer_evidence as evidence
    from tools.visualizer_replay import owner_render_parity as parity
    from tools.visualizer_replay import owner_worker_gate as gate
    from widgets.spotify_visualizer import engine_worker_link

    clip = evidence.shipped_clip(5.5)
    records: list[dict] = []
    samples: list = []
    renderer = python_osc.QuickOscilloscopeRenderer
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
        # The renderer's own early returns: nothing drawn this frame (its value dicts keep an earlier frame's).
        field = tuple(frame.logical_content_rect)
        drew = bool(presentation.content_fade > 0.0 and snapshot.logical.mode_state.trace_alphas
                    and field[2] > 0.0 and field[3] > 0.0)
        block = b""
        if drew:
            beam = dict(self._resources.values("beam"), uMatrix=(0.0,) * 16)
            block = pack_block(python_osc.OSC_BEAM_BLOCK, beam)
            if python_osc.oscilloscope_frame_values(snapshot.logical)["osc_graticule_vertices"]:
                graticule = dict(self._resources.values("graticule"), uMatrix=(0.0,) * 16)
                block += pack_block(python_osc.OSC_GRATICULE_BLOCK, graticule)
        entry = {"key": current["key"], "index": current["index"], "card": card,
                 "shown": base._shown(card, presentation), "settings": OSCILLOSCOPE_SETTINGS(snapshot, card),
                 "record": oscilloscope_native_schema.encode(snapshot.logical), "python_block": block,
                 "drew": drew, "logical_content_rect": list(frame.logical_content_rect)}
        if current["index"] % sample_every == 0:
            entry["settings_at"] = {}
            for ratio in base.DPRS:
                moved = dataclasses.replace(snapshot, presentation=dataclasses.replace(presentation, dpr=ratio))
                entry["settings_at"][str(float(ratio))] = OSCILLOSCOPE_SETTINGS(moved, card)
            samples.append((len(records), snapshot, tuple(frame.logical_size), frame.content_rotation_quarters))
        records.append(entry)
        current["index"] += 1

    renderer.render = capturing
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
    return records, samples


# --------------------------------------------------------------------------------------------------------- block

def _members(layout) -> dict:
    from rendering.gl_programs.scene3d import _std140_type

    sizes = {"float": 4, "int": 4, "uint": 4, "bool": 4, "vec2": 8, "vec3": 12, "vec4": 16, "mat4": 64}
    members = {}
    for (name, glsl_type), offset in zip(layout.fields, layout.offsets):
        _element, count, _alignment, stride = _std140_type(glsl_type)
        members[name] = (offset, count * stride if "[" in glsl_type else sizes[glsl_type])
    return members


def round_block(core, records: list[dict]) -> dict:
    import json

    from core.visualizer_engine import oscilloscope_native_schema
    from rendering.native.mode import _card, _settings, program_json, schema_table_entry
    from rendering.quick.visualizer.implementations.oscilloscope import OSC_BEAM_BLOCK, OSC_GRATICULE_BLOCK

    schema = _schema()
    built = program(not GLOW_OFF["on"])
    passes = built["passes"]
    beam_index = next(i for i, p in enumerate(passes) if p.name == "oscilloscope_beam")
    graticule_index = next(i for i, p in enumerate(passes) if p.name == "oscilloscope_graticule")
    composite_index = next(i for i, p in enumerate(passes) if p.name == "oscilloscope_show")
    declared, packs = program_json(passes, built["targets"], built["streams"], unread=built.get("unread", ()))
    table = json.dumps(dict(schema_table_entry(schema)))
    layouts = {beam_index: (OSC_BEAM_BLOCK, _members(OSC_BEAM_BLOCK)),
               graticule_index: (OSC_GRATICULE_BLOCK, _members(OSC_GRATICULE_BLOCK))}
    widen = _field("u_widen").offset

    def blocks(settings, record, shown, target):
        found, facts = core.module.mode_blocks(table, declared, packs, _settings(settings), bytes(record),
                                               _card(shown), (int(target[0]), int(target[1])))
        return [bytes(block) for block in found], json.loads(facts)

    mismatched: dict[str, int] = {}
    first_mismatch = None
    layout_differs: dict = {}
    compared = refused = graticule_frames = 0
    mutated_differs = fade_differs = 0
    sources: dict = {}
    for entry in records:
        if not entry["drew"]:
            continue
        target = tuple(int(v) for v in entry["card"]["target_size"])
        try:
            found, facts = blocks(entry["settings"], entry["record"], entry["shown"], target)
        except ValueError as exc:
            refused += 1
            first_mismatch = first_mismatch or {"key": entry["key"], "index": entry["index"], "refused": str(exc)}
            continue
        if not sources:
            for index in layouts:
                sources[passes[index].name] = dict(facts["passes"][index]["sources"])
                rows = {row[0]: row for row in facts["program"]["passes"][index]["block"]["members"]}
                for name, (offset, _size) in layouts[index][1].items():
                    if (rows.get(name) or [None, None, None])[2] != offset:
                        layout_differs[f"{passes[index].name}.{name}"] = {"python": offset,
                                                                          "module": (rows.get(name) or [None] * 3)[2]}
        compared += 1
        decoded = oscilloscope_native_schema.decode(entry["record"])
        python = entry["python_block"]
        expected = {beam_index: python[:OSC_BEAM_BLOCK.size]}
        if decoded["osc_graticule_vertices"]:
            graticule_frames += 1
            expected[graticule_index] = python[OSC_BEAM_BLOCK.size:]
        names = []
        for index, block in expected.items():
            for name, (offset, size) in layouts[index][1].items():
                if name == "uMatrix":
                    continue
                if found[index][offset:offset + size] != block[offset:offset + size]:
                    names.append(f"{passes[index].name}.{name}")
        for name in names:
            mismatched[name] = mismatched.get(name, 0) + 1
        if names and first_mismatch is None:
            first_mismatch = {"key": entry["key"], "index": entry["index"], "members": names[:12]}
        mutated = bytearray(entry["record"])
        struct.pack_into("<d", mutated, widen, struct.unpack_from("<d", mutated, widen)[0] + 0.25)
        mutated_differs += int(blocks(entry["settings"], bytes(mutated), entry["shown"], target)[0][beam_index]
                               != found[beam_index])
        faded = dict(entry["shown"], content_fade=float(entry["shown"]["content_fade"]) * 0.5 + 0.25)
        fade_differs += int(blocks(entry["settings"], entry["record"], faded, target)[0][composite_index]
                            != found[composite_index])
    runs = sorted({entry["key"] for entry in records})
    drawn = sum(1 for entry in records if entry["drew"])
    checks = {
        "every_run_drew": len(runs) == len(mode_runs()),
        "frames_compared": compared > 0 and compared == drawn,
        "graticule_frames_compared": graticule_frames > 0,
        "module_layout_is_the_python_layout": not layout_differs,
        "identical": not mismatched and not refused,
        "control_mutated_record_differs": mutated_differs == compared,
        "control_fade_differs": fade_differs == compared,
    }
    return {"pass": all(checks.values()), "checks": checks, "runs": runs, "frames": len(records), "drawn": drawn,
            "compared": compared, "graticule_frames": graticule_frames, "refused": refused,
            "mismatched_members": mismatched, "first_mismatch": first_mismatch, "layout_differs": layout_differs,
            "sources": sources, "controls": {"mutated_record_differs": mutated_differs, "fade_differs": fade_differs}}


# --------------------------------------------------------------------------------------------------------- cost

#: The cost round (checklist 11; the box's layer C): the surface's GPU time (the timer's kind 2: every pass of the
#: content) per pass by difference, median and p90 of at least COST_SAMPLES frames, the least-loaded of COST_ROUNDS
#: rounds, at a 2560 x 1440 frame's and a 4K frame's pixel count (the card drawn at the ratio that gives it).
COST_PIXELS = {"1440p": 2560 * 1440, "4k": 3840 * 2160}
COST_MAX_HOST_DPR = 8.0
COST_ROUNDS = 3
COST_SAMPLES = 240
COST_MAX_FRAMES = 1200
#: The record variants a pass's cost is the difference of: the graticule's vertices 0, the beam's instances 0.
COST_VARIANTS = ("route", "no_graticule", "no_beam")


def _cost_record(record: bytes, variant: str) -> bytes:
    out = bytearray(record)
    if variant == "no_graticule":
        struct.pack_into("<I", out, _field("osc_graticule_vertices").offset, 0)
    elif variant == "no_beam":
        struct.pack_into("<I", out, _field("osc_segments").offset, 0)
    return bytes(out)


def _native_cost(core, engine, app, host, entry: dict, variant: str, dpr: float) -> dict:
    import bubble_check

    scene = None
    stream = base.Stream()
    record = _cost_record(entry["record"], variant)
    try:
        scene = base.Scene(core, engine, host)
        scene.place(entry, dpr, stream)
        host.set_gpu_timer(True)
        for step in range(4):
            stream.publish(record, float(step))
            scene.mode.update()
            host.frames(1)
        host.gpu_samples()
        times: list[int] = []
        frames = 0
        while frames < COST_MAX_FRAMES and len(times) < COST_SAMPLES:
            stream.publish(record, float(frames + 4))
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
    """GPU time per pass at 2560 x 1440 and 4K on this API: the whole surface (the route's program), the graticule and
    the beam by difference (their counts 0 in the record), the rest (the target's clear, the bloom and the composite);
    ``nvidia-smi`` before and after. The frame: the first sampled frame of variant a at or after frame 160 that draws
    the graticule."""
    import math

    import bubble_check

    entry = next(e for e in records if e is not None and e["key"] == MODE_ID and e.get("settings_at")
                 and e["index"] >= 160)
    width, height = (float(v) for v in entry["card"]["item_size"])
    facts: dict = {"gpu_before": bubble_check._gpu_state(), "frame": {"key": entry["key"], "index": entry["index"]}}
    timed: list[dict] = []
    for scale, pixels in COST_PIXELS.items():
        dpr = min(COST_MAX_HOST_DPR, (pixels / (width * height)) ** 0.5)
        # The settings as captured (their one device pixel the capture's: the beam's anti-aliased edge, a cost of nothing).
        moved = entry
        host =core.hidden_host(int(math.ceil((width + 2 * base.MARGIN) * dpr)),
                                int(math.ceil((height + 2 * base.MARGIN) * dpr)))
        try:
            host.set_device_pixel_ratio(dpr)
            rounds: dict = {}
            for _round in range(COST_ROUNDS):
                for variant in COST_VARIANTS:
                    rounds.setdefault(variant, []).append(_native_cost(core, engine, app, host, moved, variant, dpr))
        finally:
            host.close()
            base.host_check._flush_deletes(app)
        best = {variant: dict(min(results, key=lambda r: float("inf") if r["median_ms"] is None else r["median_ms"]),
                              round_medians=[r["median_ms"] for r in results]) for variant, results in rounds.items()}
        timed += list(best.values())
        per_pass = {}
        for key in ("median_ms", "p90_ms"):
            whole = best["route"][key]
            graticule = None if whole is None else round(whole - best["no_graticule"][key], 4)
            beam = None if whole is None else round(whole - best["no_beam"][key], 4)
            per_pass[key] = {"whole": whole, "graticule": graticule, "beam": beam,
                             "clear_bloom_composite": None if whole is None else round(whole - graticule - beam, 4)}
        facts[scale] = {"dpr": round(dpr, 6), "item_pixels": [int(round(width * dpr)), int(round(height * dpr))],
                        "variants": best, "per_pass": per_pass}
    facts["gpu_after"] = bubble_check._gpu_state()
    checks = {"timed": all(r["samples"] >= COST_SAMPLES for r in timed),
              "nothing_timed_at_rest": all(r["timed_at_rest"] == 0 for r in timed),
              "no_error": not any(r.get("error") for r in timed)}
    return {"pass": all(checks.values()), "checks": checks, "facts": facts}


# --------------------------------------------------------------------------------------------------------- offsets

#: ABI 27's proof (the lead's decision, 21 Nov: Python's SceneTarget is the oracle): the item inside a larger target, as
#: the route's quad-aligned surface holds it, at an odd and an even device offset in each axis (left, top, right, bottom
#: margins in device pixels; the target stays within the item's 64-pixel allocation bucket, so the bloom's levels are
#: Python's sizes). The bloom's first downsample and the composite then pair and read pixels from the item's own pixel.
OFFSET_PLACEMENTS = {"odd": (1, 1, 1, 1), "even": (2, 2, 2, 2), "odd_x_even_y": (1, 2, 1, 2),
                     "even_x_odd_y": (2, 1, 2, 1)}
OFFSET_PER_RUN = 3                   # each run's first sampled frames at each dpr (every display: audit 10, M1)
#: The Python reference's window margin (device pixels, divisible by 1.5): the reference drawn as the product draws it,
#: its SceneTarget's overrun past the item kept (audit 10, M1: an item-sized window cut it on every side).
REFERENCE_MARGIN = 72


def _per_run(records: list, references: list) -> list:
    """Each run's first OFFSET_PER_RUN samples of ``references`` (the run is the record's key)."""
    taken: dict = {}
    chosen = []
    for sample in references:
        key = records[sample[0]]["key"]
        if taken.get(key, 0) < OFFSET_PER_RUN:
            taken[key] = taken.get(key, 0) + 1
            chosen.append(sample)
    return chosen


def _offset_frames(core, engine, app, host, records: list, chosen: list, dpr: float, margins) -> list:
    """``chosen``'s frames drawn with the target at ``margins`` around the item (None: the item's own rect), read on
    the item's own rect."""
    scene = None
    stream = base.Stream()
    frames = []
    try:
        scene = base.Scene(core, engine, host)
        for step, (index, _reference, _quarters) in enumerate(chosen):
            entry = records[index]
            card = scene.place(entry, dpr, stream, margins)
            stream.publish(entry["record"], float(step))
            scene.mode.update()
            frames.append(scene.read(card))
    finally:
        stream.close()
        if scene is not None:
            scene.close(app)
        host.frames(2)
        base.host_check._flush_deletes(app)
    return frames


def round_offsets(core, engine, app, api: str, records: list, out: Path) -> dict:
    """The item at each OFFSET_PLACEMENTS placement against the same frames with the target on the item's own rect
    (this API's, under rule (b)'s bound: the placement changes nothing of what is drawn) and, on OpenGL, against the
    Python renderer under rule (a)'s composite tolerance. The ``old_origin`` control (stage_control's
    bloom_at_target_origin: the grid and texel at the target's origin, as before ABI 27) must fail it."""
    from tools.visualizer_replay import owner_render_parity as parity

    _saved, references = base._load(out)
    if base.CONTROL == "old_origin" and not core.module.stage_control("bloom_at_target_origin", True):
        return {"pass": False, "error": "the module has no bloom_at_target_origin control (it predates ABI 27)"}
    host = core.hidden_host(*base.HOST_PIXELS)
    by_dpr: dict = {}
    checks: dict = {}
    try:
        for dpr in base.DPRS:
            host.set_device_pixel_ratio(float(dpr))
            chosen = _per_run(records, references[dpr])
            own = _offset_frames(core, engine, app, host, records, chosen, dpr, None)
            for name, margins in OFFSET_PLACEMENTS.items():
                placed = _offset_frames(core, engine, app, host, records, chosen, dpr, margins)
                against_own: list[dict] = []
                against_python: list[dict] = []
                shapes_equal = True
                for (index, reference, _quarters), drawn, item in zip(chosen, placed, own):
                    if drawn.shape != item.shape or drawn.shape[:2] != reference.shape[:2]:
                        shapes_equal = False
                        continue
                    mask = reference_mask(reference)
                    against_own.append(dict(pt.judge(drawn[..., :3], item[..., :3], VULKAN_RULE_B, mask=mask),
                                            index=index))
                    if api == "opengl":
                        against_python.append(dict(parity.rule_a_frame(drawn[..., :3], reference[..., :3], mask,
                                                                       MODE_ID), index=index))
                key = f"{name}@{dpr}"
                own_summary = pt.summarise(against_own)
                by_dpr[key] = {"margins": list(margins), "compared": len(against_own),
                               "max_level_against_own": max((int(v["max_level"]) for v in against_own), default=0),
                               "against_own": own_summary}
                checks[f"{key}_compared"] = shapes_equal and len(against_own) == len(chosen) > 0
                checks[f"{key}_as_on_its_own_rect"] = bool(own_summary["pass"])
                if api == "opengl":
                    rule_a = parity.rule_a_verdict(against_python, MODE_ID)
                    by_dpr[key]["rule_a"] = rule_a
                    checks[f"{key}_rule_a"] = bool(rule_a["pass"])
    finally:
        if base.CONTROL == "old_origin":
            core.module.stage_control("bloom_at_target_origin", False)
        host.close()
        base.host_check._flush_deletes(app)
    return {"pass": all(checks.values()), "checks": checks, "by_placement": by_dpr,
            "control": base.CONTROL if base.CONTROL == "old_origin" else None}


# --------------------------------------------------------------------------------------------------------- the child

_child = base.child


def child(args) -> dict:
    _OUT["dir"] = args.out_dir
    base.use_mode(SLOT_BYTES=_slot_bytes())          # the route's slot for the record (whole 4096-byte steps)
    return _child(args)


base.use_mode(MODE_ID=MODE_ID, _schema=_schema, _passes=_passes,
              capture_runs=capture_runs, round_block=round_block, program_item=program_item,
              control_record=control_record, item_settings_change=item_settings_change, reference_mask=reference_mask,
              ITEM_RECORD_FIELD=ITEM_RECORD_FIELD, item_reshaped=item_reshaped, VULKAN_RULE_B=VULKAN_RULE_B,
              SCRIPT=Path(__file__).resolve(), EVIDENCE_TOPIC="n5_1_oscilloscope", DEFAULT_LABEL="n51_oscilloscope",
              CONTROLS=CONTROLS, child=child, EXTRA_ROUNDS={"cost": round_cost, "offsets": round_offsets},
              REFERENCE_MARGIN=REFERENCE_MARGIN)
vulkan_against_opengl = base.vulkan_against_opengl
api_verdict = base.api_verdict


def owner(argv: list[str]) -> int:
    """``owner_render_parity.py`` with the route drawing the Oscilloscope, registered for this process only (its
    production registration is the port's last step); every argument passed through (``--native --mode oscilloscope``
    added)."""
    from rendering.quick.visualizer import native_route as route
    from tools.visualizer_replay import owner_render_parity as parity

    saved = (route.GENERIC_MODE_SETTINGS, route.NATIVE_MODE_IDS)
    route.GENERIC_MODE_SETTINGS = {**saved[0], MODE_ID: route.OSCILLOSCOPE_SETTINGS}
    route.NATIVE_MODE_IDS = saved[1] | {MODE_ID}
    try:
        return parity.main(["--native", "--mode", MODE_ID, *argv])
    finally:
        route.GENERIC_MODE_SETTINGS, route.NATIVE_MODE_IDS = saved


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv[:1] == ["owner"]:
        return owner(argv[1:])
    # Glow 0's runs: ``--glow-off`` in the parent; a child (this script again, run by the shared rounds with their own
    # arguments) knows them by its evidence folder, whose label always carries GLOW_OFF_LABEL.
    if "--glow-off" in argv:
        argv.remove("--glow-off")
        GLOW_OFF["on"] = True
        if "--label" in argv:
            at = argv.index("--label") + 1
            if GLOW_OFF_LABEL not in argv[at]:
                argv[at] += f"_{GLOW_OFF_LABEL}"
        else:
            argv += ["--label", f"n51_oscilloscope_{GLOW_OFF_LABEL}"]
    elif "--child" in argv and "--out-dir" in argv and GLOW_OFF_LABEL in Path(argv[argv.index("--out-dir") + 1]).name:
        GLOW_OFF["on"] = True
    return base.main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
