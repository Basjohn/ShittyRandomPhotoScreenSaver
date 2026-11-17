"""N5.1's proof of Bubble on the native core as generic mode content with its ambient target and streams (D12, D14,
D15; Current_Plan.md, N5.1 Bubble), through ``rendering.native``: rule (b) (Vulkan against native OpenGL) and the
item's contract, with the rounds of ``devcurve_check.py`` (the generic modes' harness) and Bubble's own pieces.

The OpenGL child captures every frame the production owner draws with the Python renderer through Bubble's widened
run set (``tools/conventions_identity.mode_runs("bubble", offers=True)``: variants a and b and every Choice offer;
settings from the spec, never presets) on the shipped 5.5 s clip, the owner replay's own recipe (the four 60 s recorded
takes are rule (a)'s at the owner level, ``owner_render_parity.py --recording``; the owner replay draws OpenGL only, so
rule (b) runs here over the sampled frames of the 5.5 s replay). Each frame keeps its record
(``bubble_native_schema.encode``), the route's card and settings (``native_route.BUBBLE_SETTINGS``), the ambient target's
size (``native_route._bubble_target_sizes``) and the BubbleDraw block the Python renderer bound; a sampled frame keeps
its settings and target size at each drawn ratio (the ambient target and its texel scale follow the ratio).

Rounds (``devcurve_check``'s):
  block   (OpenGL child) the module's block of the ``bubble`` pass for each captured frame against the Python
          renderer's, member by member at the Python packer's offsets, comparing only what the shader reads: the
          positions and extras ``count`` elements, the trail samples ``3 count``, ``u_ambient_px`` only while
          ``u_ambient_enabled``; ``uMatrix`` aside, ``u_target_px`` the core's own target. Controls: a position nudged
          and the card's fade nudged each change the module's block.
  item    (each API) the item's contract (one record per accepted frame, nothing at rest, the drop edge, a refused
          frame, unbind, no Python thread state on the render thread); rule (g) with a Settings change on
          ``u_outline_color`` and a record change on ``u_bubbles_pos``.
  pixels  (each API) the sampled frames at dpr 1 and 1.5: on OpenGL against the Python renderer under rule (a)'s
          composite tolerance with Bubble's D12 scatter; on Vulkan against the native OpenGL frames under
          ``VULKAN_RULE_B`` (rule (b)), the reference's alpha as the mask.

Negative controls (``--control``, each in its own Vulkan child against a finished run's kept OpenGL frames; each must
end "FAILED AS EXPECTED"): ``position_nudged``, ``big_class_bit``, ``sprite_y_up``, ``whole_allocation``,
``mask_dropped`` (pixels) and ``skipped_release`` (item).

Usage (repository venv, from the checkout holding the built module):
  python native/core/python/bubble_check.py --module-dir release/native_module --require-validation
      --layer-path D:\\Temp\\Scratch\\SRPSS\\native_spike\\validation_layers\\extracted [--label n51_bubble]
  python native/core/python/bubble_check.py ... --label n51_bubble --control mask_dropped
Evidence: .artifacts/evidence/native_core/n5_1_bubble/<date>_<label>/ (summary.json, summary_control_<name>.json, sheets).
Exit 0 whenever the harness ran; the verdict is the last printed line.
"""
from __future__ import annotations

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
    """The generic modes' harness (``devcurve_check.py``) as a module of this harness's own, so that Bubble's pieces
    never reach Spline Curve's harness in one process."""
    spec = importlib.util.spec_from_file_location("_bubble_check_rounds", HERE / "devcurve_check.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


base = _generic_rounds()

MODE_ID = "bubble"
#: Rule (b), judged pixel by pixel by the shared tolerance (D12 "The pixel tolerance"), the reference's alpha as the
#: mask (Bubble's card is opaque: the mask is empty): outside it the two compilers' scatter (one pack, its SPIR-V
#: against its GLSL), spread. Measured over the 5.5 s replay's 684 sampled frames (dpr 1 and 1.5; 17 Nov,
#: n5_1_bubble/20261117_rule_b/): 615 differ, every pixel exactly one level, 2,000 in all, at most 21 a frame, the
#: largest group of touching ones 7; no tie, no flip. Bounds times 1.5, decided by the lead (17 Nov): 32 a frame, groups
#: of at most 11.
VULKAN_RULE_B = pt.Tolerance("bubble, Vulkan against OpenGL (rule b)", masked_level=1, scatter_pixels=32,
                             scatter_cluster_pixels=11)
#: The negative controls: the rounds each one's Vulkan child runs and what it breaks.
CONTROLS = {
    "position_nudged": {"rounds": ["pixels"], "breaks": "every record's first bubble moved by 0.01 of the content"},
    "big_class_bit": {"rounds": ["pixels"], "breaks": "the first big-class word's lowest bit flipped (bubble 0's class)"},
    "sprite_y_up": {"rounds": ["pixels"],
                    "breaks": "bubble_ambient_points.frag with vSpriteCoord.y flipped (the sprite's glint mirrored)"},
    "whole_allocation": {"rounds": ["pixels"],
                         "breaks": "bubble.frag sampling the whole ambient allocation (ratio = vec2(1.0))"},
    "mask_dropped": {"rounds": ["pixels"], "breaks": "the hero-circle mask pass left out of the program"},
    "skipped_release": {"rounds": ["item"], "breaks": "the content's release edge omitted (stream and item kept)"},
}
#: The control shaders' edits (one line each, found exactly once).
_SPRITE_LINE = "    vec2 p = 2.0 * (vSpriteCoord - vec2(0.5));\n"
_SPRITE_FLIPPED = "    vec2 p = 2.0 * (vec2(vSpriteCoord.x, 1.0 - vSpriteCoord.y) - vec2(0.5));\n"
_RATIO_LINE = "        vec2 ratio = u_ambient_px / allocation;\n"
_RATIO_WHOLE = "        vec2 ratio = vec2(1.0);\n"


def _schema():
    from core.visualizer_engine import bubble_native_schema

    return bubble_native_schema.SCHEMA


def _slot_bytes() -> int:
    from rendering.quick.visualizer.native_route import _slot_bytes

    return _slot_bytes(MODE_ID)


def _shader_text(filename: str) -> str:
    from widgets.spotify_visualizer import shaders

    return (Path(shaders.__file__).resolve().parent / filename).read_text(encoding="utf-8")


def _control_pack(filename: str, line: str, replacement: str) -> bytes:
    """``filename`` with ``line`` replaced, baked by the product's baker into the run's work folder."""
    import probe_rings

    text = _shader_text(filename)
    if text.count(line) != 1:
        raise RuntimeError(f"{filename}: the control's line is not found exactly once")
    folder = base._work(Path(_OUT["dir"])) / "control_packs"
    return probe_rings.bake(text.replace(line, replacement), filename, folder)


#: The child's evidence folder (the control packs are baked under its work folder).
_OUT: dict = {"dir": "."}


#: The cost round's program variant (None: the route's program): ``no_mask``, ``no_points`` (a pass left out, its
#: cost the difference) or ``empty_twice`` (the two ambient passes drawn twice: with the ambience off, the difference is
#: the cost of the two empty passes).
_VARIANT: dict = {"name": None}
_AMBIENT_PASSES = ("bubble_ambient_points", "bubble_ambient_mask")
#: The settings only the ambient points' pass reads (``bubble_ambient_settings_values``).
_POINTS_ONLY_SETTINGS = frozenset({"uTexelScale", "uSpriteScale", "uGlowSpread", "uMicroColor", "uParticleColor"})


def program(sizes: dict) -> dict:
    """Bubble's program as the route builds it (``native_route.bubble_program``), with the active control's change
    (or the cost round's variant)."""
    import dataclasses

    from rendering.native.program_values import mode_fragment_pack
    from rendering.quick.visualizer import native_route

    pack = mode_fragment_pack(MODE_ID)
    if base.CONTROL == "whole_allocation":
        pack = _control_pack("bubble.frag", _RATIO_LINE, _RATIO_WHOLE)
    built = native_route.bubble_program(pack, sizes)
    passes = list(built["passes"])
    if base.CONTROL == "sprite_y_up":
        flipped = _control_pack("bubble_ambient_points.frag", _SPRITE_LINE, _SPRITE_FLIPPED)
        passes = [dataclasses.replace(p, pack=flipped) if p.name == "bubble_ambient_points" else p for p in passes]
    if base.CONTROL == "mask_dropped" or _VARIANT["name"] == "no_mask":
        passes = [p for p in passes if p.name != "bubble_ambient_mask"]
    if _VARIANT["name"] == "no_points":
        passes = [p for p in passes if p.name != "bubble_ambient_points"]
    if _VARIANT["name"] == "empty_twice":
        again = [dataclasses.replace(p, name=f"{p.name}_again") for p in passes if p.name in _AMBIENT_PASSES]
        passes = passes[:2] + again + passes[2:]
    return dict(built, passes=passes)


def _passes():
    return program({"ambient": (64, 64)})["passes"]


def sizes_at(entry: dict, dpr: float) -> dict:
    sizes = (entry.get("sizes_at") or {}).get(str(float(dpr)), entry["sizes"])
    return {name: tuple(int(v) for v in size) for name, size in sizes.items()}


def program_item(mode, entry: dict, dpr: float, first: bool) -> None:
    """The route's order: the program with its targets and streams and the first settings, then each explicit-size
    target's size (``NativeMode.target_size``); afterwards the settings and the sizes."""
    settings = base.settings_at(entry, dpr)
    if _VARIANT["name"] == "no_points":
        # Without its pass, the points' own block members have no reader (the core refuses an unknown name).
        settings = {k: v for k, v in settings.items() if k not in _POINTS_ONLY_SETTINGS}
    sizes = sizes_at(entry, dpr)
    if first:
        built = program(sizes)
        mode.program(built["passes"], settings, targets=built["targets"], streams=built["streams"])
    else:
        mode.settings(settings)
    for name, size in sizes.items():
        mode.target_size(name, size)


def _field(name: str):
    return _schema().layout.field(name)


def control_record(record: bytes) -> bytes:
    """The record controls: the first bubble's x nudged, or the first big-class word's lowest bit flipped."""
    out = bytearray(record)
    if base.CONTROL == "position_nudged":
        offset = _field("u_bubbles_pos").offset
        struct.pack_into("<d", out, offset, struct.unpack_from("<d", out, offset)[0] + 0.01)
    elif base.CONTROL == "big_class_bit":
        offset = _field("u_big_class_bits").offset
        struct.pack_into("<I", out, offset, struct.unpack_from("<I", out, offset)[0] ^ 1)
    return bytes(out)


def item_settings_change(settings: dict) -> dict:
    """Rule (g)'s Settings change: the outline colour."""
    return dict(settings, u_outline_color=[1.0, 0.1, 0.1, 1.0])


ITEM_RECORD_FIELD = "u_bubbles_pos"


def item_reshaped(record: bytes) -> bytes:
    """Rule (g)'s record change: the first bubble moved a tenth of the content."""
    out = bytearray(record)
    offset = _field(ITEM_RECORD_FIELD).offset
    struct.pack_into("<d", out, offset, struct.unpack_from("<d", out, offset)[0] + 0.1)
    return bytes(out)


# --------------------------------------------------------------------------------------------------------- capture

def capture_runs(sample_every: int) -> tuple[list[dict], list]:
    """Every frame the Python renderer draws through the widened run set: (records, the snapshots sampled for
    pixels). Each record: run key, frame index, the native record, the route's card, the settings and the ambient
    target's size (per drawn ratio for a sample), the core card and the Python BubbleDraw block."""
    import dataclasses

    from core.visualizer_engine import bubble_native_schema
    from rendering.gl_programs.portable import pack_block
    from rendering.native.composite import composite_geometry
    from rendering.native.spectrum import spectrum_presentation
    from rendering.quick.visualizer.implementations import bubble as python_bubble
    from rendering.quick.visualizer.native_route import BUBBLE_SETTINGS, GENERIC_MODE_TARGET_SIZES
    from tools import conventions_identity
    import tools.expanded_visualizer_evidence as evidence
    from tools.visualizer_replay import owner_render_parity as parity
    from tools.visualizer_replay import owner_worker_gate as gate
    from widgets.spotify_visualizer import engine_worker_link

    sizer = GENERIC_MODE_TARGET_SIZES[MODE_ID]
    clip = evidence.shipped_clip(5.5)
    records: list[dict] = []
    samples: list = []
    renderer = python_bubble.QuickBubbleRenderer
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
        settings = BUBBLE_SETTINGS(snapshot, card)
        entry = {"key": current["key"], "index": current["index"], "card": card,
                 "shown": base._shown(card, presentation), "settings": settings,
                 "sizes": {k: list(v) for k, v in sizer(snapshot, settings).items()},
                 "record": bubble_native_schema.encode(snapshot.logical),
                 "python_block": pack_block(python_bubble.BUBBLE_BLOCK, values),
                 "logical_content_rect": list(frame.logical_content_rect)}
        if current["index"] % sample_every == 0:
            entry["settings_at"], entry["sizes_at"] = {}, {}
            if current["key"] not in _COST_SNAPSHOTS and current["index"] >= COST_FROM_FRAME:
                _COST_SNAPSHOTS[current["key"]] = (len(records), snapshot, tuple(frame.logical_size))
            for ratio in (*base.DPRS, *cost_scales(card).values()):
                moved = dataclasses.replace(snapshot, presentation=dataclasses.replace(presentation, dpr=ratio))
                at = BUBBLE_SETTINGS(moved, card)
                entry["settings_at"][str(float(ratio))] = at
                entry["sizes_at"][str(float(ratio))] = {k: list(v) for k, v in sizer(moved, at).items()}
            samples.append((len(records), snapshot, tuple(frame.logical_size), frame.content_rotation_quarters))
        records.append(entry)
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


# --------------------------------------------------------------------------------------------------------- block

def _read_spans(record: dict, name: str, size: int) -> list[tuple[int, int]] | None:
    """The byte spans of member ``name`` (``size`` bytes in the block) the shader reads for this record, relative to
    the member's offset; None: the whole member."""
    count = int(record["u_bubble_count"])
    if name in ("u_bubbles_pos", "u_bubbles_extra"):
        return [(0, min(size, 16 * count))]
    if name == "u_bubbles_trail":
        return [(0, min(size, 16 * 3 * count))]
    if name == "u_ambient_px":
        return [(0, size)] if int(record["u_ambient_enabled"]) else []
    return None


def round_block(core, records: list[dict]) -> dict:
    from core.visualizer_engine import bubble_native_schema
    from rendering.gl_programs.scene3d import _std140_type
    from rendering.native.mode import mode_blocks
    from rendering.quick.visualizer.implementations.bubble import BUBBLE_BLOCK
    from tools import conventions_identity

    schema = _schema()
    sizes = {"float": 4, "int": 4, "uint": 4, "bool": 4, "vec2": 8, "vec3": 12, "vec4": 16, "uvec4": 16,
             "ivec2": 8, "mat4": 64}
    members = {}
    for (name, glsl_type), offset in zip(BUBBLE_BLOCK.fields, BUBBLE_BLOCK.offsets):
        _element, count, _alignment, stride = _std140_type(glsl_type)
        members[name] = (offset, count * stride if "[" in glsl_type else sizes[glsl_type])
    position = _field("u_bubbles_pos").offset
    mismatched: dict[str, int] = {}
    first_mismatch = None
    layout_differs: dict = {}
    sources: dict = {}
    compared = refused = 0
    mutated_differs = fade_differs = 0
    ambient_frames = 0
    import json

    from rendering.native.mode import _card, _settings, program_json, schema_table_entry

    built = program({"ambient": (64, 64)})
    passes = built["passes"]
    index_of = next(i for i, p in enumerate(passes) if p.name == MODE_ID)
    # ``mode.mode_blocks`` declares no targets; Bubble's passes draw into its ambient target, so the program is
    # declared whole (targets and streams), as ``NativeMode.program`` sends it.
    declared, packs = program_json(passes, built["targets"], built["streams"])
    table = json.dumps(dict(schema_table_entry(schema)))

    def blocks(settings, record, shown, target):
        found, facts = core.module.mode_blocks(table, declared, packs, _settings(settings), bytes(record),
                                               _card(shown), (int(target[0]), int(target[1])))
        return [bytes(block) for block in found], json.loads(facts)

    for entry in records:
        target = tuple(int(v) for v in entry["card"]["target_size"])
        try:
            found, facts = blocks(entry["settings"], entry["record"], entry["shown"], target)
        except ValueError as exc:
            refused += 1
            first_mismatch = first_mismatch or {"key": entry["key"], "index": entry["index"], "refused": str(exc)}
            continue
        block = found[index_of]
        if not sources:
            sources = dict(facts["passes"][index_of]["sources"])
            rows = {row[0]: row for row in facts["program"]["passes"][index_of]["block"]["members"]}
            layout_differs = {name: {"python": offset, "module": (rows.get(name) or [None, None, None])[2]}
                              for name, (offset, _size) in members.items()
                              if (rows.get(name) or [None, None, None])[2] != offset}
        compared += 1
        decoded = bubble_native_schema.decode(entry["record"])
        ambient_frames += int(bool(decoded["u_ambient_enabled"]))
        expected = bytearray(entry["python_block"])
        if "u_target_px" in members:
            # fragPixel's target is the render target's pixels (N1.4): the window's on the Python route, the core's
            # own target on the native one.
            offset = members["u_target_px"][0]
            if len(expected) >= offset + 8:
                struct.pack_into("<2f", expected, offset, float(target[0]), float(target[1]))
        names = []
        for name, (offset, size) in members.items():
            if name == "uMatrix":
                continue
            spans = _read_spans(decoded, name, size)
            spans = [(0, size)] if spans is None else spans
            if len(expected) < offset + size or any(
                    block[offset + lo:offset + hi] != bytes(expected[offset + lo:offset + hi]) for lo, hi in spans):
                names.append(name)
        for name in names:
            mismatched[name] = mismatched.get(name, 0) + 1
        if names and first_mismatch is None:
            first_mismatch = {"key": entry["key"], "index": entry["index"], "members": names[:12]}
        mutated = bytearray(entry["record"])
        struct.pack_into("<d", mutated, position, struct.unpack_from("<d", mutated, position)[0] + 0.25)
        other = blocks(entry["settings"], bytes(mutated), entry["shown"], target)[0][index_of]
        mutated_differs += int(other != block)
        faded = dict(entry["shown"], content_fade=float(entry["shown"]["content_fade"]) * 0.5 + 0.25)
        fade_block = blocks(entry["settings"], entry["record"], faded, target)[0][index_of]
        fade_differs += int(fade_block != block)
    runs = sorted({entry["key"] for entry in records})
    by_source: dict = {}
    for name, source in sources.items():
        by_source.setdefault(source, []).append(name)
    checks = {
        "every_run_drew": len(runs) == len(conventions_identity.mode_runs(MODE_ID, True)),
        "frames_compared": compared > 0 and compared == len(records),
        "ambient_frames_compared": ambient_frames > 0,
        "module_layout_is_the_python_layout": not layout_differs,
        "identical": not mismatched and not refused,
        "every_member_has_one_source": set(sources) == set(members),
        "control_mutated_record_differs": mutated_differs == compared,
        "control_fade_differs": fade_differs == compared,
    }
    return {"pass": all(checks.values()), "checks": checks, "runs": runs, "frames": len(records),
            "compared": compared, "refused": refused, "ambient_frames": ambient_frames,
            "mismatched_members": mismatched, "first_mismatch": first_mismatch, "layout_differs": layout_differs,
            "members_by_source": {key: sorted(value) for key, value in by_source.items()},
            "controls": {"mutated_record_differs": mutated_differs, "fade_differs": fade_differs}}


# --------------------------------------------------------------------------------------------------------- cost

#: The cost round (checklist 11; the N5.1 box): GPU time per pass at 4K, median and p90 of at least COST_SAMPLES timed
#: frames, at two scales: ``display_4k``, the rig's card on a 4K display (its 1920 x 1080 display at ratio 2: the card
#: as the product shows it there), and ``card_4k_area``, the same card drawn at a 4K frame's pixel count (a card
#: filling a 4K display, Bubble's worst case; the hidden host's ratio stops at 8).
COST_DPR = 2.0
COST_WIDE_PIXELS = 3840
COST_MAX_HOST_DPR = 8.0
COST_ROUNDS = 3
COST_SAMPLES = 240
COST_MAX_FRAMES = 1200
#: The cost round's frames: the first sampled frame of variant a (ambience on) and of variant b (ambience off) at or
#: after this index, when the ambience is populated.
COST_FROM_FRAME = 160
COST_RUNS = {"ambience_on": MODE_ID, "ambience_off": f"{MODE_ID}:b"}
#: The OpenGL child's snapshots of those frames (run key -> (record index, snapshot, logical size)): the Python
#: renderer's cost at the same frame.
_COST_SNAPSHOTS: dict = {}
#: The empty passes' cost above which the core should skip a pass with no instance (the N5.1 box's rule).
EMPTY_PASS_BOUND_MS = 0.02


def _gpu_state() -> dict:
    """``nvidia-smi``'s state and its process table (other GPU load present or not), taken beside each figure."""
    import shutil
    import subprocess as sp
    import time

    smi = shutil.which("nvidia-smi")
    if not smi:
        return {"nvidia_smi": None}
    try:
        query = sp.run([smi, "--query-gpu=name,utilization.gpu,clocks.gr,clocks.mem,pstate,memory.used,display_active,"
                             "temperature.gpu,power.draw", "--format=csv,noheader"],
                       capture_output=True, text=True, timeout=20).stdout.strip()
        table = sp.run([smi], capture_output=True, text=True, timeout=20).stdout
    except Exception as exc:  # noqa: BLE001
        return {"nvidia_smi": f"error: {exc}"}
    processes = [line.strip() for line in table.splitlines() if line.strip().startswith("|") and (".exe" in line)]
    return {"at": time.strftime("%H:%M:%S"), "nvidia_smi": query, "processes": processes}


def _summary(times: list[int]) -> dict:
    ordered = sorted(times)
    if not ordered:
        return {"samples": 0, "median_ms": None, "p90_ms": None}
    return {"samples": len(ordered), "median_ms": round(ordered[len(ordered) // 2] / 1e6, 4),
            "p90_ms": round(ordered[int(len(ordered) * 0.9)] / 1e6, 4),
            "p10_ms": round(ordered[int(len(ordered) * 0.1)] / 1e6, 4)}


def cost_scales(card: dict) -> dict:
    """The cost round's ratios for ``card``: name -> dpr. ``card_4k_area``: the card at a 4K frame's pixel count
    (3840 x 2160), within the hidden host's largest ratio (8)."""
    width, height = (float(v) for v in card["item_size"])
    return {"display_4k": COST_DPR,
            "card_4k_area": min(COST_MAX_HOST_DPR, (COST_WIDE_PIXELS * 2160.0 / (width * height)) ** 0.5)}


def _cost_entries(records: list) -> dict:
    found = {}
    for name, key in COST_RUNS.items():
        found[name] = next(entry for entry in records if entry is not None and entry["key"] == key
                           and entry.get("settings_at") and entry["index"] >= COST_FROM_FRAME)
    return found


def _native_cost(core, engine, app, host, entry: dict, variant: str | None, dpr: float) -> dict:
    """The item's surface GPU time (the timer's kind 2: every pass of the content) for ``entry`` at ``dpr``,
    re-published each frame (a new sequence, so each frame records), under ``variant``; then nothing at rest."""
    _VARIANT["name"] = variant
    scene = None
    stream = base.Stream()
    try:
        try:
            scene = base.Scene(core, engine, host)
            scene.place(entry, dpr, stream)
        except ValueError as exc:                       # one variant refused: reported, the others still timed
            return {"samples": 0, "median_ms": None, "p90_ms": None, "p10_ms": None, "timed_at_rest": 0,
                    "error": str(exc)}
        state = scene.mode.state()
        host.set_gpu_timer(True)
        for step in range(4):
            stream.publish(entry["record"], float(step))
            scene.mode.update()
            host.frames(1)
        host.gpu_samples()
        times: list[int] = []
        frames = 0
        while frames < COST_MAX_FRAMES and len(times) < COST_SAMPLES:
            stream.publish(entry["record"], float(frames + 4))
            scene.mode.update()
            host.frames(1)
            frames += 1
            times.extend(s.nanoseconds for s in host.gpu_samples() if s.kind == 2)
        host.frames(4)
        times.extend(s.nanoseconds for s in host.gpu_samples() if s.kind == 2)
        # At rest: frames with no new publication time nothing.
        host.frames(8)
        rest = [s for s in host.gpu_samples() if s.kind == 2]
        host.set_gpu_timer(False)
        after = scene.mode.state()
        result = _summary(times)
        result.update(records=frames, passes=[p["name"] if isinstance(p, dict) else p
                                              for p in (state.get("program") or {}).get("passes", [])][:8],
                      timed_at_rest=len(rest), error=after.get("error") or after.get("failure"))
        return result
    finally:
        _VARIANT["name"] = None
        stream.close()
        if scene is not None:
            scene.close(app)
        host.frames(2)
        base.host_check._flush_deletes(app)


def python_cost(snapshot, logical_size, dpr: float) -> dict:
    """The Python renderer's GPU time for the same frame at ``dpr`` (OpenGL, its own render host into a target of the
    item's pixels), GL_TIME_ELAPSED around the whole render, one query a frame."""
    import ctypes
    import dataclasses

    from OpenGL import GL as gl
    from PySide6.QtGui import QOffscreenSurface, QOpenGLContext, QSurfaceFormat

    import spectrum_check
    from rendering.quick.visualizer.render_host import QuickVisualizerRenderHost

    snapshot = dataclasses.replace(snapshot, presentation=dataclasses.replace(snapshot.presentation, dpr=dpr))
    fmt = QSurfaceFormat()
    fmt.setRenderableType(QSurfaceFormat.OpenGL)
    fmt.setProfile(QSurfaceFormat.CoreProfile)
    fmt.setVersion(4, 6)
    context = QOpenGLContext()
    context.setFormat(fmt)
    if not context.create():
        raise RuntimeError("no OpenGL 4.6 context for the Python cost")
    surface = QOffscreenSurface()
    surface.setFormat(fmt)
    surface.create()
    if not context.makeCurrent(surface):
        raise RuntimeError("the Python cost's context is not current")
    host = QuickVisualizerRenderHost()
    times: list[int] = []
    width, height = (int(round(v * dpr)) for v in logical_size)
    color = gl.glGenTextures(1)
    fbo = gl.glGenFramebuffers(1)
    query = (ctypes.c_uint * 1)()
    try:
        gl.glBindTexture(gl.GL_TEXTURE_2D, color)
        gl.glTexImage2D(gl.GL_TEXTURE_2D, 0, gl.GL_RGBA8, width, height, 0, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE, None)
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, fbo)
        gl.glFramebufferTexture2D(gl.GL_FRAMEBUFFER, gl.GL_COLOR_ATTACHMENT0, gl.GL_TEXTURE_2D, color, 0)
        gl.glGenQueries(1, query)
        matrix = spectrum_check._reference_matrix(*logical_size)
        for index in range(COST_SAMPLES + 4):
            gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, fbo)
            gl.glViewport(0, 0, width, height)
            gl.glClearColor(0.0, 0.0, 0.0, 0.0)
            gl.glClear(gl.GL_COLOR_BUFFER_BIT)
            gl.glBeginQuery(gl.GL_TIME_ELAPSED, int(query[0]))
            host.render(snapshot=snapshot, viewport=(0, 0, width, height),
                        logical_size=(float(logical_size[0]), float(logical_size[1])), matrix_values=matrix)
            gl.glEndQuery(gl.GL_TIME_ELAPSED)
            value = (ctypes.c_uint64 * 1)()
            gl.glGetQueryObjectui64v(int(query[0]), gl.GL_QUERY_RESULT, value)
            if index >= 4:                       # the programs' and targets' first frames left out
                times.append(int(value[0]))
    finally:
        gl.glDeleteQueries(1, query)
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, 0)
        gl.glDeleteFramebuffers(1, [fbo])
        gl.glDeleteTextures([color])
        host.release_resources()
        context.doneCurrent()
        surface.destroy()
    return dict(_summary(times), pixels=[width, height])


def round_cost(core, engine, app, api: str, records: list, out: Path) -> dict:
    """GPU time per pass at 4K on this API (median and p90 of at least COST_SAMPLES frames), each pass's by difference:
    with the ambience on, the route's program against it without the points pass and without the mask pass (what is
    left is the ``bubble`` pass with the target's clear); with the ambience off, the route's program against it with its
    two empty passes drawn twice (their cost, the N5.1 box's 0.02 ms rule). On OpenGL, the Python renderer's cost for
    the same frames. ``nvidia-smi`` before and after."""
    import math

    entries = _cost_entries(records)
    margin = base.MARGIN
    facts: dict = {"gpu_before": _gpu_state(),
                   "frames": {name: {"key": e["key"], "index": e["index"]} for name, e in entries.items()}}
    timed: list[dict] = []

    def minus(a: dict, b: dict, key: str) -> float | None:
        return None if a[key] is None or b[key] is None else round(a[key] - b[key], 4)

    for scale, dpr in cost_scales(entries["ambience_on"]["card"]).items():
        width, height = entries["ambience_on"]["card"]["item_size"]
        host = core.hidden_host(int(math.ceil((width + 2 * margin) * dpr)), int(math.ceil((height + 2 * margin) * dpr)))
        try:
            host.set_device_pixel_ratio(dpr)
            # The variants are timed in turn, COST_ROUNDS times over, and each keeps its least-loaded round (lowest
            # median): another process sharing the GPU (the operator's machine is never idle) skews one round, not
            # every round of one variant; all rounds' medians are kept beside it.
            plan = [("ambience_on", v) for v in (None, "no_points", "no_mask")] + \
                   [("ambience_off", v) for v in (None, "empty_twice")]
            rounds: dict = {}
            for _round in range(COST_ROUNDS):
                for frame, variant in plan:
                    result = _native_cost(core, engine, app, host, entries[frame], variant, dpr)
                    rounds.setdefault((frame, variant or "route"), []).append(result)

            def best(results: list[dict]) -> dict:
                kept = min(results, key=lambda r: float("inf") if r["median_ms"] is None else r["median_ms"])
                return dict(kept, round_medians=[r["median_ms"] for r in results])

            on = {variant: best(results) for (frame, variant), results in rounds.items() if frame == "ambience_on"}
            off = {variant: best(results) for (frame, variant), results in rounds.items() if frame == "ambience_off"}
        finally:
            host.close()
            base.host_check._flush_deletes(app)
        timed += [*on.values(), *off.values()]
        per_pass = {}
        for key in ("median_ms", "p90_ms"):
            points = minus(on["route"], on["no_points"], key)
            mask = minus(on["route"], on["no_mask"], key)
            per_pass[key] = {"whole_ambience_on": on["route"][key], "bubble_ambient_points": points,
                             "bubble_ambient_mask": mask,
                             "bubble_and_clears": None if points is None or mask is None
                             else round(on["route"][key] - points - mask, 4),
                             "whole_ambience_off": off["route"][key],
                             "two_empty_passes": minus(off["empty_twice"], off["route"], key)}
        empty = per_pass["median_ms"]["two_empty_passes"]
        result = {"dpr": round(dpr, 6), "item_pixels": [int(round(width * dpr)), int(round(height * dpr))],
                  "ambience_on": on, "ambience_off": off, "per_pass": per_pass,
                  "empty_passes_above_bound": None if empty is None else empty > EMPTY_PASS_BOUND_MS}
        if api == "opengl":
            result["python"] = {}
            for name, key in COST_RUNS.items():
                if key in _COST_SNAPSHOTS:
                    runs = [python_cost(*_COST_SNAPSHOTS[key][1:], dpr) for _round in range(COST_ROUNDS)]
                    kept = min(runs, key=lambda r: float("inf") if r["median_ms"] is None else r["median_ms"])
                    result["python"][name] = dict(kept, round_medians=[r["median_ms"] for r in runs])
        facts[scale] = result
    facts["gpu_after"] = _gpu_state()
    checks = {"timed": all(r["samples"] >= COST_SAMPLES for r in timed),
              "nothing_timed_at_rest": all(r["timed_at_rest"] == 0 for r in timed),
              "no_error": not any(r.get("error") for r in timed)}
    return {"pass": all(checks.values()), "checks": checks, "facts": facts}


# --------------------------------------------------------------------------------------------------------- the child

_child = base.child


def child(args) -> dict:
    _OUT["dir"] = args.out_dir
    base.use_mode(SLOT_BYTES=_slot_bytes())          # the route's slot for Bubble's record (whole 4096-byte steps)
    return _child(args)


base.use_mode(MODE_ID=MODE_ID, _schema=_schema, _passes=_passes,
              capture_runs=capture_runs, round_block=round_block, program_item=program_item,
              control_record=control_record, item_settings_change=item_settings_change,
              ITEM_RECORD_FIELD=ITEM_RECORD_FIELD, item_reshaped=item_reshaped, VULKAN_RULE_B=VULKAN_RULE_B,
              SCRIPT=Path(__file__).resolve(), EVIDENCE_TOPIC="n5_1_bubble", DEFAULT_LABEL="n51_bubble",
              CONTROLS=CONTROLS, child=child, EXTRA_ROUNDS={"cost": round_cost})
vulkan_against_opengl = base.vulkan_against_opengl
api_verdict = base.api_verdict


def main(argv: list[str] | None = None) -> int:
    return base.main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
