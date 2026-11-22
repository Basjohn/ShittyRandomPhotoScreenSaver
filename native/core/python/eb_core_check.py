"""N5.6's built proofs of Extruded Bubble's core boxes (ABI 42; ``Current_Plan.md`` N5.6), through ``rendering.native``,
on harness scenes of their own: the module (``release/native_module``, built on GitHub) loaded the product's way in one
child process per graphics API (OpenGL, then Vulkan on the module's own instance and device under validation). No window
is ever visible (hidden hosts only).

The ABI 42 keys the product's face does not speak yet (the port's) are sent as raw declarations (``Raw``) through the
face's own ``program_json``.

Rounds (each with its control):
  limits    a 48-pass, 6-target program admitted and drawn (its last pass's fill read back), nothing recorded at
            rest; 49 passes and 7 targets refused with their reasons; six surface-sized RGBA16F targets' bytes at
            3840x2160.
  skip      a pass's "when" (a record u32): at 0 it draws nothing (the frame equals the program without it), at 1 it
            draws; mode_entries_skipped counts each skipped record. The defocus step and its near layer skipped at 0:
            the frame equals the program without the layer, stage_defocus_records flat. Control: the program-only form
            (no "when") still draws at 0.
  readback  D4's pair-check kernel as a "once" entry with a "readback": read once (check_readbacks +1, about 2 KB), its
            report in the state ("check") exact as DriftSolver.check judges it, taken at a later record (records go on),
            flat over a steady run, the harness readback never used. Control: the kernel without its error terms is
            reported inexact.
  geometry  D3 on a harness writer of geometry_arena.h's layout: one upload a key, the same revision under another
            namespace drawing its own bytes, "@previous" at the swap, a capacity growth, an invalid bank failed once
            with the old drawn, zero residencies after a mode switch and teardown.
  probe     a cube drawn face by face (through v_uv and through uMatrix), its prefilter, every face and level read back
            against a CPU twin of probe.py's chain, lookups at levels 0, 2 and 3 and across face edges. Controls:
            swapped faces, a per-face box chain, a clamped (non-seamless) read.

Usage (repository venv, from the checkout holding the built module):
  python native/core/python/eb_core_check.py --module-dir release/native_module --require-validation
      --layer-path D:\\Temp\\Scratch\\SRPSS\\native_spike\\validation_layers\\extracted [--rounds limits skip readback]
Evidence: .artifacts/evidence/native_core/n5_6/<date>_<label>/summary.json. The verdict is the last printed line
("N56 VERDICT PASS" or "N56 VERDICT FAIL: ...").
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
ROOT = HERE.parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import vk_validation  # noqa: E402
import host_check  # noqa: E402

APIS = ("opengl", "vulkan")
ROUNDS = ("limits", "skip", "readback", "geometry", "probe")
CHILD_TIMEOUT_S = 1800
_ALLOWED_ENV: set[str] = set()
OUT: Path | None = None     # the child's evidence folder (set by child)
API = [""]
CARD = (64, 64)
FILL = [0.25, 0.5, 0.75, 1.0]
EXTRA = [0.5, 0.25, 0.0, 0.0]
CODES = {"skip": 210, "skip_plain": 211, "defocus": 212, "defocus_plain": 213, "geometry": 214,
         "geometry_none": 215}

FILL_FRAG = """#version 440
layout(std140, binding = 18) uniform Fill { vec4 u_fill; };
layout(location = 0) in vec2 v_uv;
layout(location = 0) out vec4 colour;
void main() { colour = u_fill; }
"""
EXTRA_FRAG = """#version 440
layout(std140, binding = 18) uniform Extra { vec4 u_extra; };
layout(location = 0) in vec2 v_uv;
layout(location = 0) out vec4 colour;
void main() { colour = u_extra; }
"""
GEOMETRY_COMP = """#version 440
layout(local_size_x = 64) in;
layout(std430, binding = 1) readonly buffer Current { vec4 cur[]; };
layout(std430, binding = 2) readonly buffer Previous { vec4 prev[]; };
layout(std430, binding = 3) writeonly buffer Result { vec4 result[]; };
void main() {
    uint i = gl_GlobalInvocationID.x;
    result[i] = cur[i];
    result[64u + i] = prev[i];
}
"""
PROBE_SIDE = 32
PROBE_LEVELS = (0, 2, 3)          # the lookups' levels (3: a 4x4 face, the cone's blur past a box's)
LOOK_SIZE = (128, 64)


def face_frag(face: int) -> str:
    """A face pass drawing the world direction of its pixel (probe.py's rotation for ``face``), encoded d * 0.5 + 0.5.
    v_uv is y down (render_contract.py), as in a face framebuffer Python draws: OpenGL's NDC y is 1 - 2 v_uv.y."""
    from rendering.quick.scene3d.probe import scene3d_probe_face_rotation

    r = scene3d_probe_face_rotation(face)
    vec = lambda v: "vec3(%r, %r, %r)" % tuple(float(x) for x in v)  # noqa: E731
    return f"""#version 440
layout(location = 0) in vec2 v_uv;
layout(location = 0) out vec4 colour;
void main() {{
    vec2 ndc = vec2(v_uv.x * 2.0 - 1.0, 1.0 - v_uv.y * 2.0);
    vec3 d = normalize({vec(r[0:3])} * ndc.x + {vec(r[3:6])} * ndc.y - {vec(r[6:9])});
    colour = vec4(d * 0.5 + 0.5, 1.0);
}}
"""


FACE_MATRIX_VERT = """#version 440
layout(std140, binding = 18) uniform FaceDraw { mat4 uMatrix; };
layout(location = 0) out vec2 vNdc;
void main() {
    vec2 p = vec2(gl_VertexIndex == 1 ? 3.0 : -1.0, gl_VertexIndex == 2 ? 3.0 : -1.0);
    vNdc = p;
    // uMatrix maps item pixels (y down, one a face texel) to the face's clip space: OpenGL's NDC as item pixels.
    gl_Position = uMatrix * vec4((p.x * 0.5 + 0.5) * 32.0, (0.5 - p.y * 0.5) * 32.0, 0.0, 1.0);
}
"""


def face_matrix_frag(face: int) -> str:
    """The face drawn as probe.py draws it: OpenGL's clip space (NDC from the vertex) through the core's uMatrix."""
    return face_frag(face).replace("layout(location = 0) in vec2 v_uv;", "layout(location = 0) in vec2 vNdc;").replace(
        "vec2 ndc = vec2(v_uv.x * 2.0 - 1.0, 1.0 - v_uv.y * 2.0);", "vec2 ndc = vNdc;").replace(
        "#version 440\n", "#version 440\nlayout(std140, binding = 18) uniform FaceDraw { mat4 uMatrix; };\n")


LOOK_FRAG = """#version 440
layout(location = 0) in vec2 v_uv;
layout(location = 0) out vec4 l0;
layout(location = 1) out vec4 l2;
layout(location = 2) out vec4 l3;
layout(location = 3) out vec4 dir;
layout(binding = 1) uniform samplerCube uCube;
void main() {
    float lon = (v_uv.x * 2.0 - 1.0) * 3.14159265;
    float lat = (v_uv.y - 0.5) * 3.14159265 * 0.98;
    vec3 d = vec3(cos(lat) * sin(lon), sin(lat), -cos(lat) * cos(lon));
    l0 = vec4(textureLod(uCube, d, 0.0).rgb, 1.0);
    l2 = vec4(textureLod(uCube, d, 2.0).rgb, 1.0);
    l3 = vec4(textureLod(uCube, d, 3.0).rgb, 1.0);
    dir = vec4(d * 0.5 + 0.5, 1.0);
}
"""
SHADERS = {"fill.frag": FILL_FRAG, "extra.frag": EXTRA_FRAG, "geometry.comp": GEOMETRY_COMP, "look.frag": LOOK_FRAG,
           **{f"face{f}.frag": face_frag(f) for f in range(6)},
           **{f"face_matrix{f}.frag": face_matrix_frag(f) for f in range(6)}, "face_matrix.vert": FACE_MATRIX_VERT}


class Raw:
    """A declaration the face does not speak yet (ABI 42's keys), with its pack, for ``program_json``."""

    def __init__(self, declaration: dict, pack: bytes = b"") -> None:
        self._declaration = declaration
        self.pack = pack

    def declaration(self) -> dict:
        return dict(self._declaration)


def _with(entry, **keys):
    """``entry`` with ABI 42 keys added to its declaration, its class kept (``program_json`` still finds its packs)."""
    import copy

    base = type(entry)
    cls = type(f"With{base.__name__}", (base,), {"declaration": lambda self: dict(base.declaration(self), **keys)})
    made = copy.copy(entry)
    object.__setattr__(made, "__class__", cls)
    return made


# --------------------------------------------------------------------------------------------------- the packs

def _work(out: Path) -> Path:
    path = out / "work"
    path.mkdir(parents=True, exist_ok=True)
    return path


def bake_packs(out: Path) -> None:
    import compute_passes as cp
    import post_stages as ps
    import probe_rings

    folder = _work(out) / "packs"
    src = folder / "src"
    packs = {name: probe_rings.bake(text, name, src) for name, text in SHADERS.items()}
    source, broken = cp.pair_check_sources()
    packs["pair_check.comp"] = probe_rings.bake(source, "pair_check.comp", src)
    packs["pair_check_broken.comp"] = probe_rings.bake(broken, "pair_check_broken.comp", src)
    packs.update({f"post_{k}": v for k, v in ps.bake_all(src).items()})
    for name, data in packs.items():
        (folder / f"{name}.qsb").write_bytes(data)


def load_packs(out: Path) -> dict:
    return {p.name[:-4]: p.read_bytes() for p in (_work(out) / "packs").glob("*.qsb")}


# --------------------------------------------------------------------------------------------------- helpers

def _live(core) -> dict:
    return core.composite_live()


def _delta(after: dict, before: dict, key: str) -> float:
    return (after.get(key) or 0) - (before.get(key) or 0)


def _refusal(call) -> str:
    try:
        call()
    except ValueError as exc:
        return f"refused: {exc}"
    return "admitted"


def _targets(scene, timeout_s: float = 10.0, publish: dict | None = None) -> dict:
    """Every readable target texture after the next record (a streamed scene publishes ``publish`` first)."""
    import scene_target_check as stc

    if publish is not None:
        # The record drawn first (a readback asked with it rides on the record already held), then read as it left it.
        scene.publish(**publish)
        scene.mode.update()
        scene.host.frames(2)
    scene.mode.read_targets()
    scene.mode.update()
    deadline = time.monotonic() + timeout_s
    pixels = None
    while pixels is None and time.monotonic() < deadline:
        scene.host.frames(1)
        pixels = scene.mode.target_pixels()
    if pixels is None:
        raise RuntimeError(f"the target readback did not complete ({scene.mode.state().get('last_reason')})")
    out = {}
    for p in pixels:
        array = stc._array(p)["array"]
        cw, ch = p["content"]
        out[p["name"]] = array[array.shape[0] - ch:, :cw].copy()
    return out


def _streamed(core, engine, host, name, passes, targets, settings, entries, record, *, buffers=(), streams=(),
              unread_retry=()):
    """A streamed scene (compute_pass_check's host) with raw ABI 42 entries. A built module before the "when" reader fix
    refuses a field only "when" reads as unknown; the scene is then made again with it declared unread (a fact)."""
    import compute_pass_check as cpc
    import compute_passes as cp
    import mesh_buffers

    schema = mesh_buffers.schema(name, entries, code=CODES[name])
    spec = cp.SceneSpec(name, tuple(passes), tuple(targets), tuple(streams), settings, schema, record,
                        buffers=tuple(buffers))
    try:
        return cpc.Scene(core, engine, host, spec), False
    except ValueError as exc:
        if not unread_retry or "no pass's member" not in str(exc):
            raise

    # The face's program() takes unread=: the spec's program sent with it.
    from rendering.native import mode as face

    real = face.NativeMode.program

    def program(self, passes, settings=None, **kw):
        kw.setdefault("unread", tuple(unread_retry))
        return real(self, passes, settings, **kw)

    face.NativeMode.program = program
    try:
        return cpc.Scene(core, engine, host, spec), True
    finally:
        face.NativeMode.program = real


def _close(scene, host, app) -> None:
    import mesh_buffer_check as mbc

    mbc._close(scene, host, app)


def _still(core, engine, host, card, packs, passes, targets, settings):
    import scene_target_check as stc

    return stc.Scene(core, engine, host, card, 1.0, packs, passes=passes, targets=targets, settings=settings)


def _host(core, card):
    import mesh_buffer_check as mbc

    return core.hidden_host(card[0] + 2 * mbc.MARGIN, card[1] + 2 * mbc.MARGIN)


# --------------------------------------------------------------------------------------------------- limits

def round_limits(core, engine, app, api: str, packs: dict) -> dict:
    import numpy as np
    from rendering.native.mode import MAX_PASSES, MAX_TARGETS, ModePass, ModeTarget, TargetAttachment

    checks, facts = {}, {}

    def program(passes_n: int, targets_n: int, *, surface: bool = False, fmt: str = "rgba8"):
        size = None if surface else (16, 16)
        targets = [ModeTarget("scene" if t == 0 else f"t{t}", (TargetAttachment("colour", fmt),),
                              size=size if (surface or t == 0) else (8, 8)) for t in range(targets_n)]
        passes = [ModePass(f"p{i}", packs["fill.frag"], "replace",
                           target=targets[(i % (targets_n - 1)) + 1 if i < passes_n - 1 and targets_n > 1 else 0].name)
                  for i in range(passes_n)]
        return passes, targets

    host = _host(core, CARD)
    try:
        passes, targets = program(MAX_PASSES, MAX_TARGETS)
        facts["admitted"] = {"passes": len(passes), "targets": len(targets)}
        scene = _still(core, engine, host, CARD, packs, passes, targets, {"u_fill": FILL})
        try:
            got = _targets(scene)
            state = scene.mode.state()
            want = np.array(FILL) * 255.0
            pixel = got.get("scene.colour")
            facts["scene_pixel"] = pixel[0, 0].tolist() if pixel is not None else None
            facts["last_reason"] = state.get("last_reason")
            checks["the_limit_program_is_admitted_and_draws"] = bool(
                pixel is not None and (np.abs(pixel.astype(np.float64) - want) <= 1.0).all()
                and not state.get("content_failing"))
            facts["scene_targets"] = len((state.get("scene_targets") or {}).get("targets", ()))
            checks["every_target_made"] = facts["scene_targets"] == MAX_TARGETS
            records = state.get("records")
            before = _live(core)
            host.frames(8)
            after_state, after = scene.mode.state(), _live(core)
            checks["nothing_recorded_at_rest"] = after_state.get("records") == records
            checks["nothing_made_at_rest"] = after.get("mode_resources") == before.get("mode_resources")
            # One past each limit, refused with its reason; the drawn program kept.
            p49, t6 = program(MAX_PASSES + 1, MAX_TARGETS)
            facts["one_pass_past"] = _refusal(lambda: scene.mode.program(p49, {"u_fill": FILL}, targets=t6))
            p48, t7 = program(MAX_PASSES, MAX_TARGETS + 1)
            facts["one_target_past"] = _refusal(lambda: scene.mode.program(p48, {"u_fill": FILL}, targets=t7))
            checks["one_pass_past_refused_with_its_reason"] = f"1 to {MAX_PASSES} passes" in facts["one_pass_past"]
            checks["one_target_past_refused_with_its_reason"] = (
                f"at most {MAX_TARGETS} targets" in facts["one_target_past"])
            host.frames(2)
            checks["the_drawn_program_kept"] = not scene.mode.state().get("content_failing")
        finally:
            _close(scene, host, app)
    finally:
        host.close()
        host_check._flush_deletes(app)
    # Six surface-sized RGBA16F targets at 3840x2160 (D14's buckets): their bytes as SceneTargetCounts holds them.
    big = (3840, 2160)
    host = _host(core, big)
    try:
        passes, targets = program(MAX_TARGETS, MAX_TARGETS, surface=True, fmt="rgba16f")
        before = _live(core)
        scene = _still(core, engine, host, big, packs, passes, targets, {"u_fill": FILL})
        try:
            scene.mode.update()
            host.frames(3)
            live = _live(core)
            facts["bytes_at_4k"] = {"scene_target_bytes": _delta(live, before, "scene_target_bytes"),
                                    "scene_target_textures": _delta(live, before, "scene_target_textures"),
                                    "state": scene.mode.state().get("scene_targets")}
            floor = MAX_TARGETS * big[0] * big[1] * 8
            checks["six_4k_targets_made"] = (not scene.mode.state().get("content_failing")
                                             and facts["bytes_at_4k"]["scene_target_bytes"] >= floor)
        finally:
            _close(scene, host, app)
    finally:
        host.close()
        host_check._flush_deletes(app)
    return {"pass": all(checks.values()), "checks": checks, "facts": facts}


# --------------------------------------------------------------------------------------------------- skip

def round_skip(core, engine, app, api: str, packs: dict) -> dict:
    import numpy as np
    from rendering.native.mode import ModePass, ModeTarget, TargetAttachment

    checks, facts = {}, {}
    target = ModeTarget("scene", (TargetAttachment("colour", "rgba8"),), size=(16, 16))
    base = ModePass("base", packs["fill.frag"], "replace", target="scene")
    extra = ModePass("extra", packs["extra.frag"], "additive", target="scene")
    settings = {"u_fill": FILL, "u_extra": EXTRA}
    entries = (("w", "u32", 1),)
    to8 = lambda v: np.round(np.clip(np.array(v), 0, 1) * 255).astype(np.uint8)  # noqa: E731
    both = to8(np.array(FILL) + np.array(EXTRA))
    alone = to8(FILL)
    host = _host(core, CARD)
    try:
        scene, unread = _streamed(core, engine, host, "skip", (base, _with(extra, when="w")), (target,), settings,
                                  entries, {"w": 1}, unread_retry=("w",))
        facts["when_field_declared_unread"] = unread
        try:
            on = _targets(scene, publish={"w": 1})["scene.colour"]
            before = _live(core)
            off = _targets(scene, publish={"w": 0})["scene.colour"]
            for _ in range(9):
                scene.draw(1, w=0)
            after = _live(core)
            again = _targets(scene, publish={"w": 1})["scene.colour"]
            facts["skipped"] = _delta(after, before, "mode_entries_skipped")
            facts["pixels"] = {"on": on[0, 0].tolist(), "off": off[0, 0].tolist(), "again": again[0, 0].tolist(),
                               "want_both": both.tolist(), "want_alone": alone.tolist()}
            near = lambda a, b: bool((np.abs(a.astype(np.int16) - b.astype(np.int16)) <= 1).all())  # noqa: E731
            checks["drawn_at_1"] = near(on, both) and near(again, both)
            checks["skipped_at_0"] = near(off, alone)
            checks["each_record_at_0_counted"] = facts["skipped"] >= 10
            checks["no_failure"] = not scene.mode.state().get("content_failing")
        finally:
            _close(scene, host, app)
        # Control: the program-only form (no "when") still draws at 0.
        scene, _u = _streamed(core, engine, host, "skip_plain", (base, extra), (target,), settings, entries, {"w": 1},
                              unread_retry=("w",))
        try:
            plain = _targets(scene, publish={"w": 0})["scene.colour"]
            checks["control_program_only_form_still_draws_at_0"] = near(plain, both)
        finally:
            _close(scene, host, app)
        facts["defocus"] = _defocus_skip(core, engine, app, host, packs, checks)
    finally:
        host.close()
        host_check._flush_deletes(app)
    return {"pass": all(checks.values()), "checks": checks, "facts": facts}


def _defocus_skip(core, engine, app, host, packs, checks) -> dict:
    """The near layer and its defocus step under "when": at 0 the frame equals the program without them, and no
    defocus record is made; at 1 the layer shows."""
    import numpy as np
    import post_stages as ps
    from rendering.native.mode import DefocusStep, ModePass

    stage_packs = {k[len("post_"):]: v for k, v in packs.items() if k.startswith("post_")}
    passes, targets = ps.eb_program(stage_packs, variant="no_transparency", capture=False)
    settings = ps.values_for(passes)
    gated = tuple(_with(p, when="w") if (isinstance(p, ModePass) and p.name == "near") or isinstance(p, DefocusStep)
                  else p for p in passes)
    # The reference: the same program without the near layer, its target and its defocus step.
    plain_passes = tuple(p for p in passes
                         if not ((isinstance(p, ModePass) and p.name == "near") or isinstance(p, DefocusStep)))
    plain_targets = tuple(t for t in targets if t.name != "near")
    plain_settings = ps.values_for(plain_passes)
    entries = (("w", "u32", 1),)
    facts = {}
    card = (128, 96)
    small = _host(core, card)
    try:
        import compute_passes as cp
        cp_card = cp.CARD
        cp.CARD = card                       # the streamed host's card (compute_pass_check reads it at the scene)
        try:
            scene, unread = _streamed(core, engine, small, "defocus", gated, targets, settings, entries, {"w": 1},
                                      unread_retry=("w",))
        finally:
            cp.CARD = cp_card
        try:
            shown = _targets(scene, publish={"w": 1})["scene.colour"]
            before = _live(core)
            hidden = _targets(scene, publish={"w": 0})["scene.colour"]
            for _ in range(4):
                scene.draw(1, w=0)
            after = _live(core)
            facts["defocus_records_at_0"] = _delta(after, before, "stage_defocus_records")
            facts["skipped_at_0"] = _delta(after, before, "mode_entries_skipped")
            after_on = _live(core)
            _targets(scene, publish={"w": 1})
            facts["defocus_records_at_1"] = _delta(_live(core), after_on, "stage_defocus_records")
        finally:
            _close(scene, small, app)
        cp.CARD = card
        try:
            scene, _u = _streamed(core, engine, small, "defocus_plain", plain_passes, plain_targets, plain_settings,
                                  entries, {"w": 0}, unread_retry=("w",))
        finally:
            cp.CARD = cp_card
        try:
            reference = _targets(scene, publish={"w": 0})["scene.colour"]
        finally:
            _close(scene, small, app)
    finally:
        small.close()
        host_check._flush_deletes(app)
    facts["max_difference_skipped_vs_no_layer"] = float(np.abs(hidden.astype(np.float32)
                                                               - reference.astype(np.float32)).max())
    facts["max_difference_shown_vs_no_layer"] = float(np.abs(shown.astype(np.float32)
                                                             - reference.astype(np.float32)).max())
    if OUT is not None:
        np.savez_compressed(OUT / f"defocus_skip_{API[0]}.npz", shown=shown, hidden=hidden, reference=reference)
    diff = np.abs(hidden.astype(np.float32) - reference.astype(np.float32))
    facts["skipped_vs_no_layer_at"] = [int(v) for v in np.unravel_index(int(diff.argmax()), diff.shape)]
    facts["pixels_differing_skipped_vs_no_layer"] = int((diff.max(axis=-1) > 0).sum())
    facts["max_difference_skipped_vs_shown"] = float(np.abs(hidden.astype(np.float32) - shown.astype(np.float32)).max())
    facts["shape"] = list(hidden.shape)
    checks["defocus_skipped_frame_equals_the_program_without_the_layer"] = (
        facts["max_difference_skipped_vs_no_layer"] == 0.0)
    checks["defocus_shown_at_1_differs"] = facts["max_difference_shown_vs_no_layer"] > 0.0
    checks["no_defocus_record_at_0"] = facts["defocus_records_at_0"] == 0
    checks["a_defocus_record_at_1"] = facts["defocus_records_at_1"] >= 1
    facts["when_field_declared_unread"] = unread
    return facts


# --------------------------------------------------------------------------------------------------- readback

def round_readback(core, engine, app, api: str, packs: dict) -> dict:
    import compute_passes as cp

    checks, facts = {}, {}
    host = _host(core, CARD)
    try:
        for name in ("pair_check", "pair_check_broken"):
            spec = cp.scene("pair_check", {"pair_check.comp": packs[f"{name}.comp"]})
            spec.passes = tuple(_with(p, trigger="once", readback="results") for p in spec.passes)
            import compute_pass_check as cpc

            before = _live(core)
            scene = cpc.Scene(core, engine, host, spec)
            try:
                report, records, waited = None, 0, 0
                for i in range(60):
                    scene.draw(1)
                    records += 1
                    report = scene.mode.state().get("check")
                    if report:
                        waited = i + 1
                        break
                mid = _live(core)
                for _ in range(300):        # a steady run: no second readback, no report again
                    scene.draw(1)
                state = scene.mode.state()
                after = _live(core)
            finally:
                _close(scene, host, app)
            judged = cp.pair_check_report(bytes.fromhex(report["hex"])) if report else {"exact": None}
            facts[name] = {"report_entry": report and report.get("entry"), "bytes": report and report.get("bytes"),
                           "records_until_report": waited, "judged": judged,
                           "check_readbacks": _delta(after, before, "check_readbacks"),
                           "check_readback_bytes": _delta(after, before, "check_readback_bytes"),
                           "check_reports": _delta(after, before, "check_reports"),
                           "readbacks_in_steady_run": _delta(after, mid, "check_readbacks"),
                           "harness_readbacks": after.get("compute_readbacks"),
                           "records": state.get("records"), "last_reason": state.get("last_reason")}
        good, broken = facts["pair_check"], facts["pair_check_broken"]
        checks["the_check_is_read_once"] = good["check_readbacks"] == 1 and good["check_reports"] == 1
        checks["about_2kb_read"] = 0 < good["check_readback_bytes"] <= 4096
        checks["the_report_is_exact"] = bool(good["judged"].get("exact"))
        checks["taken_at_a_later_record"] = good["records_until_report"] >= 2
        checks["flat_over_the_steady_run"] = good["readbacks_in_steady_run"] == 0
        checks["records_go_on"] = (good["records"] or 0) >= good["records_until_report"] + 300
        checks["the_harness_readback_unused"] = not good["harness_readbacks"]
        checks["control_the_broken_kernel_is_reported_inexact"] = (broken["judged"].get("exact") is False
                                                                  and broken["check_reports"] == 1)
    finally:
        host.close()
        host_check._flush_deletes(app)
    return {"pass": all(checks.values()), "checks": checks, "facts": facts}


# --------------------------------------------------------------------------------------------------- geometry

GEO_ROWS = 64                     # the vec4 rows the copy entry reads of each key


class Arena:
    """The main process's geometry arena (geometry_arena.h's layout; this harness is its writer): two banks a family,
    each written whole under its sequence (odd while written) before a record names its key."""

    HEADER = 64
    BANK_HEADER = 64

    def __init__(self, families: int = 1, bank_bytes: int = 4096) -> None:
        import struct
        from multiprocessing import shared_memory

        self.families, self.bank_bytes = families, bank_bytes
        self.memory = shared_memory.SharedMemory(create=True, size=self._offset(families, 0))
        self.buf = self.memory.buf
        struct.pack_into("<IIIIQII", self.buf, 0, 0x41475253, 1, families, 2, bank_bytes, self.HEADER,
                         self.BANK_HEADER)

    def _offset(self, family: int, bank: int) -> int:
        return self.HEADER + (family * 2 + bank) * (self.BANK_HEADER + self.bank_bytes)

    @property
    def name(self) -> str:
        return self.memory.name

    def write(self, bank: int, key: tuple, payload: bytes, *, declared_bytes: int | None = None) -> None:
        import struct

        ns, engine, activation, family, capacity, revision = key
        at = self._offset(family, bank)
        sequence = struct.unpack_from("<I", self.buf, at)[0]
        struct.pack_into("<I", self.buf, at, sequence + 1)          # odd: being written
        self.buf[at + self.BANK_HEADER:at + self.BANK_HEADER + len(payload)] = payload
        struct.pack_into("<IQIIIIQ", self.buf, at + 4, len(payload) if declared_bytes is None else declared_bytes,
                         ns, engine, activation, family, capacity, revision)
        struct.pack_into("<I", self.buf, at, sequence + 2)          # even and advanced: whole

    def close(self) -> None:
        self.buf = None
        self.memory.close()
        self.memory.unlink()


def _key_words(key: tuple) -> tuple:
    ns, engine, activation, family, capacity, revision = key
    return (ns & 0xFFFFFFFF, ns >> 32, engine, activation, family, revision & 0xFFFFFFFF, revision >> 32, capacity)


def _rows(tag: float, rows: int) -> bytes:
    import numpy as np

    data = np.zeros((rows, 4), np.float32)
    data[:, 0] = tag
    data[:, 1] = np.arange(rows)
    return data.tobytes()


def round_geometry(core, engine, app, api: str, packs: dict) -> dict:
    """D3's tests on the built module: one revision under two namespaces draws each its own geometry; one upload a key
    (the record carries 8 words whatever the capacity); the old key bound as "@previous" at the swap's record and
    retired after it; a capacity growth as a new key; a key whose bank is invalid failed once, logged, the old drawn;
    zero residencies after a mode switch and after teardown (the item destroyed, the host closed)."""
    import numpy as np
    from rendering.native.mode import ComputeBinding, ComputePass, StorageBuffer

    checks, facts = {}, {}
    copy = ComputePass("copy", packs["geometry.comp"], groups=(1, 1, 1),
                       bindings=(ComputeBinding("Current", "geo", "buffer", "read"),
                                 ComputeBinding("Previous", "geo@previous", "buffer", "read"),
                                 ComputeBinding("Result", "result", "buffer", "write")))
    geo = Raw({"name": "geo", "geometry": {"family": 0, "key": "geo_key"}})
    result = StorageBuffer("result", 2 * GEO_ROWS * 16)
    entries = (("geo_key", "u32", 8),)
    ns_a, ns_b = (7 << 32) | 1, (8 << 32) | 1
    key_a = (ns_a, 2, 9, 0, 64, 5)
    key_b = (ns_b, 2, 9, 0, 64, 5)          # the same revision under another worker's namespace
    key_c = (ns_b, 2, 9, 0, 128, 6)         # a capacity growth: a new key
    key_d = (ns_b, 2, 9, 0, 128, 7)         # its bank invalid (a size past the bank): failed
    arena = Arena(bank_bytes=4096)
    host = _host(core, CARD)

    def result_rows(scene):
        got = scene.storage(app)["result"][3]
        rows = np.frombuffer(got, np.float32).reshape(-1, 4)
        return rows[:GEO_ROWS], rows[GEO_ROWS:2 * GEO_ROWS]

    def tag(rows) -> float:
        values = set(rows[:, 0].tolist())
        return values.pop() if len(values) == 1 else float("nan")

    try:
        arena.write(0, key_a, _rows(1.0, 64))
        arena.write(1, key_b, _rows(2.0, 64))
        base = _live(core)
        scene, unread = _streamed(core, engine, host, "geometry", (copy,), (), {}, entries,
                                  {"geo_key": _key_words(key_a)}, buffers=(geo, result), unread_retry=("geo_key",))
        facts["key_field_declared_unread"] = unread
        try:
            scene.mode._module.composite_mode_geometry_arena(scene.mode._handle(), arena.name)
            for _ in range(50):
                scene.draw(1, geo_key=_key_words(key_a))
            cur, prev = result_rows(scene)
            live = _live(core)
            facts["a"] = {"tag": tag(cur), "previous_tag": tag(prev), "uploads": _delta(live, base, "geometry_uploads"),
                          "resident": live.get("geometry_resident"), "arenas": live.get("geometry_arenas"),
                          "state": scene.mode.state().get("last_reason")}
            checks["key_a_drawn"] = facts["a"]["tag"] == 1.0
            checks["one_upload_for_fifty_records"] = facts["a"]["uploads"] == 1
            checks["one_residency_at_rest"] = facts["a"]["resident"] == 1
            # Key B: the same revision, another namespace (D3 test 1): its own bytes, the old bound as previous at the
            # swap's record, retired after it.
            scene.draw(1, geo_key=_key_words(key_b))
            cur, prev = result_rows(scene)
            facts["b_swap"] = {"tag": tag(cur), "previous_tag": tag(prev)}
            scene.draw(1, geo_key=_key_words(key_b))
            scene.draw(1, geo_key=_key_words(key_b))
            cur, prev = result_rows(scene)
            live = _live(core)
            facts["b_after"] = {"tag": tag(cur), "previous_tag": tag(prev), "resident": live.get("geometry_resident"),
                                "uploads": _delta(live, base, "geometry_uploads"),
                                "released": _delta(live, base, "geometry_released")}
            checks["same_revision_other_namespace_draws_its_own_geometry"] = facts["b_swap"]["tag"] == 2.0
            checks["old_key_bound_as_previous_at_the_swap"] = facts["b_swap"]["previous_tag"] == 1.0
            checks["old_key_retired_after_a_drawn_record"] = (facts["b_after"]["previous_tag"] == 2.0
                                                              and facts["b_after"]["resident"] == 1
                                                              and facts["b_after"]["released"] >= 1)
            # Key C: a capacity growth (a bank of 128 rows), a new key; the record is the same 8 words.
            arena.write(0, key_c, _rows(3.0, 128))
            for _ in range(3):
                scene.draw(1, geo_key=_key_words(key_c))
            cur, _prev = result_rows(scene)
            live = _live(core)
            facts["c"] = {"tag": tag(cur), "uploads": _delta(live, base, "geometry_uploads"),
                          "resident": live.get("geometry_resident")}
            checks["capacity_growth_is_a_new_key"] = facts["c"]["tag"] == 3.0 and facts["c"]["uploads"] == 3
            # Key D: its bank's size past the bank (invalid): failed once, logged, never retried; C still drawn.
            arena.write(1, key_d, _rows(4.0, 16), declared_bytes=8192)
            failed_before = _live(core).get("geometry_failed") or 0
            for _ in range(20):
                scene.draw(1, geo_key=_key_words(key_d))
            cur, _prev = result_rows(scene)
            live = _live(core)
            facts["d"] = {"tag": tag(cur), "failed": (live.get("geometry_failed") or 0) - failed_before,
                          "resident": live.get("geometry_resident"), "content_failing":
                          scene.mode.state().get("content_failing")}
            checks["failed_key_once_old_drawn"] = (facts["d"]["failed"] == 1 and facts["d"]["tag"] == 3.0
                                                   and not facts["d"]["content_failing"])
            # A mode switch: a program without geometry; every residency goes.
            plain = ComputePass("plain", packs["geometry.comp"], groups=(1, 1, 1),
                                bindings=(ComputeBinding("Current", "result", "buffer", "read"),
                                          ComputeBinding("Previous", "result", "buffer", "read"),
                                          ComputeBinding("Result", "other", "buffer", "write")))
            facts["switch_refusal"] = _refusal(lambda: scene.mode.program(
                (plain,), {}, buffers=(result, StorageBuffer("other", 2 * GEO_ROWS * 16)),
                unread=("geo_key",)))
            for _ in range(3):
                scene.draw(1, geo_key=_key_words(key_c))
            facts["after_switch"] = {"resident": _live(core).get("geometry_resident")}
            checks["zero_residencies_after_a_mode_switch"] = facts["after_switch"]["resident"] == 0
        finally:
            _close(scene, host, app)
        # A second item: resident again, then torn down with its host (window destruction).
        scene, _u = _streamed(core, engine, host, "geometry", (copy,), (), {}, entries,
                              {"geo_key": _key_words(key_c)}, buffers=(geo, result), unread_retry=("geo_key",))
        try:
            scene.mode._module.composite_mode_geometry_arena(scene.mode._handle(), arena.name)
            for _ in range(5):
                scene.draw(1, geo_key=_key_words(key_c))
            facts["second_item_resident"] = _live(core).get("geometry_resident")
        finally:
            _close(scene, host, app)
    finally:
        host.close()
        host_check._flush_deletes(app)
        arena.close()
    live = _live(core)
    facts["after_teardown"] = {k: live.get(k) for k in ("geometry_resident", "geometry_arenas", "geometry_uploads",
                                                        "geometry_released", "geometry_failed", "geometry_waits",
                                                        "geometry_reads_found", "geometry_reads_torn")}
    checks["second_item_resident"] = facts["second_item_resident"] == 1
    checks["zero_residencies_and_arenas_after_teardown"] = (live.get("geometry_resident") == 0
                                                            and live.get("geometry_arenas") == 0)
    return {"pass": all(checks.values()), "checks": checks, "facts": facts}


# --------------------------------------------------------------------------------------------------- the probe
# A CPU twin of probe.py's chain on the same scene (each texel the direction it faces): OpenGL's cube-map faces (the
# major-axis table, row 0 at t = 0), bilinear reads clamped at a face's edge, each level probe.py's 32-tap cone over
# the level above. Its control twin: per-face 2x2 box mips (what generateMips gives).

def _face_dir(face, sc, tc):
    import numpy as np

    one = np.ones_like(sc)
    table = {0: (one, -tc, -sc), 1: (-one, -tc, sc), 2: (sc, one, tc), 3: (sc, -one, -tc), 4: (sc, -tc, one),
             5: (-sc, -tc, -one)}
    d = np.stack(table[face], axis=-1)
    return d / np.linalg.norm(d, axis=-1, keepdims=True)


def _texel_dirs(n):
    import numpy as np

    c = (np.arange(n) + 0.5) / n * 2.0 - 1.0
    tc, sc = np.meshgrid(c, c, indexing="ij")          # [row, column]: row t, column s
    return np.stack([_face_dir(f, sc, tc) for f in range(6)])


def _cube_sample(level, d):
    """Bilinear read of ``level`` (6, n, n, 3) along directions ``d`` (..., 3), clamped at the face's edge."""
    import numpy as np

    n = level.shape[1]
    x, y, z = d[..., 0], d[..., 1], d[..., 2]
    ax, ay, az = np.abs(x), np.abs(y), np.abs(z)
    face = np.where((ax >= ay) & (ax >= az), np.where(x > 0, 0, 1),
                    np.where(ay >= az, np.where(y > 0, 2, 3), np.where(z > 0, 4, 5)))
    sc = np.select([face == 0, face == 1, face == 2, face == 3, face == 4, face == 5], [-z, z, x, x, x, -x])
    tc = np.select([face == 0, face == 1, face == 2, face == 3, face == 4, face == 5], [-y, -y, z, -z, -y, -y])
    ma = np.select([face < 2, face < 4], [ax, ay], az)
    s = (sc / ma + 1.0) * 0.5 * n - 0.5
    t = (tc / ma + 1.0) * 0.5 * n - 0.5
    s0, t0 = np.floor(s), np.floor(t)
    fs, ft = (s - s0)[..., None], (t - t0)[..., None]
    s0, t0 = s0.astype(int), t0.astype(int)
    c = lambda v: np.clip(v, 0, n - 1)  # noqa: E731
    v00, v01 = level[face, c(t0), c(s0)], level[face, c(t0), c(s0 + 1)]
    v10, v11 = level[face, c(t0 + 1), c(s0)], level[face, c(t0 + 1), c(s0 + 1)]
    return (v00 * (1 - fs) + v01 * fs) * (1 - ft) + (v10 * (1 - fs) + v11 * fs) * ft


def _cone(source, axis, cone):
    import numpy as np

    helper = np.where(np.abs(axis[..., 1:2]) < 0.99, np.array([0.0, 1.0, 0.0]), np.array([1.0, 0.0, 0.0]))
    u = np.cross(helper, axis)
    u /= np.linalg.norm(u, axis=-1, keepdims=True)
    v = np.cross(axis, u)
    sigma = max(cone * 0.5, 1e-4)
    total, weights = 0.0, 0.0
    for i in range(32):
        cos_t = 1.0 - (i + 0.5) / 32.0 * (1.0 - np.cos(cone))
        theta = np.arccos(cos_t)
        phi = i * 2.39996323
        d = axis * cos_t + (u * np.cos(phi) + v * np.sin(phi)) * np.sin(theta)
        w = np.exp(-theta * theta / (2.0 * sigma * sigma))
        total = total + _cube_sample(source, d) * w
        weights += w
    return total / weights


def probe_models(side: int, levels: int):
    """(cone chain, box chain): each a list of (6, n, n, 3) levels."""
    import math

    import numpy as np

    base = _texel_dirs(side) * 0.5 + 0.5
    cone, box = [base], [base]
    for level in range(1, levels):
        n = max(side >> level, 1)
        cone.append(_cone(cone[-1], _texel_dirs(n), min(2.2 * (math.pi / 2.0) / n, math.pi / 2.0)))
        prev = box[-1]
        box.append(0.25 * (prev[:, 0::2, 0::2] + prev[:, 1::2, 0::2] + prev[:, 0::2, 1::2] + prev[:, 1::2, 1::2]))
    return cone, box


def _probe_program(packs, *, swap: bool = False, mips: str = "linear", matrix: bool = False):
    from rendering.native.mode import ModePass, ModeTarget, PassOutput, PassSampler, TargetAttachment

    cube = Raw({"name": "probe", "size": [PROBE_SIDE, PROBE_SIDE], "colour": [{"name": "colour", "format": "rgba16f"}],
                "cube": True, "allocation": "exact"})
    look = ModeTarget("look", tuple(TargetAttachment(n, "rgba16f") for n in ("l0", "l2", "l3", "dir")),
                      size=LOOK_SIZE, allocation="exact")
    passes = []
    for f in range(6):
        drawn = {0: 1, 1: 0}.get(f, f) if swap else f
        if matrix:
            from rendering.native.mode import PassGeometry

            entry = ModePass(f"face{f}", packs[f"face_matrix{f}.frag"], "replace", target="probe",
                             geometry=PassGeometry(packs["face_matrix.vert"], vertices=3))
        else:
            entry = ModePass(f"face{f}", packs[f"face{f}.frag"], "replace", target="probe")
        passes.append(_with(entry, face=drawn))
    passes.append(Raw({"name": "filter", "prefilter": "probe"}))
    passes.append(ModePass("look", packs["look.frag"], "replace", target="look",
                           outputs=tuple(PassOutput(True, "replace") for _ in range(4)),
                           samplers=(PassSampler("uCube", "probe.colour", "linear", "clamp", mips),)))
    return passes, (cube, look)


def _edge_band(d, n, texels=1.0):
    """Lookups within ``texels`` of a face's edge at a face size ``n``."""
    import numpy as np

    a = np.sort(np.abs(d), axis=-1)
    minor = a[..., 1] / a[..., 2]                       # the larger of the two minor coordinates over the major
    return minor > 1.0 - 2.0 * texels / n


def round_probe(core, engine, app, api: str, packs: dict) -> dict:
    import math

    import numpy as np

    checks, facts = {}, {}
    levels = int(math.log2(PROBE_SIDE)) + 1
    cone, box = probe_models(PROBE_SIDE, levels)
    host = _host(core, CARD)
    got = {}
    try:
        mips = "linear"
        for label, swap, matrix in (("probe", False, False), ("swapped", True, False), ("matrix", False, True)):
            passes, targets = _probe_program(packs, swap=swap, mips=mips, matrix=matrix)
            before = _live(core)
            try:
                scene = _still(core, engine, host, CARD, packs, passes, targets, {})
            except ValueError as exc:
                # A module before the fix refuses a cube's mipped sampler (as a defocus layer's): a fact; the level
                # lookups wait for the rebuild, the faces and levels are still read back.
                if "reads mips of the defocus layer" not in str(exc):
                    raise
                facts["mipped_cube_sampler_refused"] = str(exc)
                mips = "none"
                passes, targets = _probe_program(packs, swap=swap, mips=mips, matrix=matrix)
                scene = _still(core, engine, host, CARD, packs, passes, targets, {})
            try:
                got[label] = _targets(scene)
                state = scene.mode.state()
                live = _live(core)
                facts[f"{label}_counts"] = {k: _delta(live, before, k) for k in
                                            ("scene_cube_face_runs", "scene_cube_prefilters",
                                             "scene_cube_level_copies")}
                facts[f"{label}_reason"] = state.get("last_reason")
                facts[f"{label}_failing"] = state.get("content_failing")
            finally:
                _close(scene, host, app)
    finally:
        host.close()
        host_check._flush_deletes(app)
    live = _live(core)
    facts["after_teardown"] = {k: live.get(k) for k in ("scene_targets", "scene_target_textures", "mode_resources")}
    checks["retired_to_zero"] = all(not v for v in facts["after_teardown"].values())
    look = got["probe"]
    facts["readback_keys"] = sorted(look)
    if OUT is not None:
        for label, images in got.items():
            stem = "probe" if label == "probe" else f"probe_{label}"
            named = {k.replace(".", "_").replace("#", "_f").replace("@", "_l"): v for k, v in images.items()}
            np.savez_compressed(OUT / f"{stem}_{api}.npz", **named)
    d = look["look.dir"][..., :3].astype(np.float64) * 2.0 - 1.0
    d /= np.linalg.norm(d, axis=-1, keepdims=True)
    errors = {}
    for level in PROBE_LEVELS:
        native = look[f"look.l{level}"][..., :3].astype(np.float64)
        for name, model in (("cone", cone), ("box", box)):
            expected = _cube_sample(model[level], d)
            diff = np.abs(native - expected).max(axis=-1)
            band = _edge_band(d, PROBE_SIDE >> level)
            errors[f"l{level}_{name}"] = {"interior_max": float(diff[~band].max()), "edge_max": float(diff[band].max()),
                                         "mean": float(diff.mean())}
    facts["lookup_errors"] = errors
    # Seams: the largest step between neighbouring lookups (along longitude) at level 3, across face edges against
    # inside faces; the CPU twin reads each face alone (clamped): its ratio is the non-seamless control.
    def steps(values):
        return np.abs(np.diff(values, axis=1)).max(axis=-1)

    band = _edge_band(d, PROBE_SIDE >> 3, texels=0.5)[:, 1:]
    native_steps = steps(look["look.l3"][..., :3].astype(np.float64))
    clamped_steps = steps(_cube_sample(cone[3], d))
    facts["seam"] = {"native_edge_over_interior": float(native_steps[band].max() / native_steps[~band].max()),
                     "clamped_edge_over_interior": float(clamped_steps[band].max() / clamped_steps[~band].max())}
    # The cube's own texels, read back: each face and level against the twin (OpenGL's rows), mirrored rows reported.
    faces = {}
    for f in range(6):
        for level in range(levels):
            key = f"probe.colour#{f}" + (f"@{level}" if level else "")      # level 0 read as the face itself
            if key not in look:
                faces[key] = None
                continue
            native = look[key][..., :3].astype(np.float64)
            model = cone[level][f]
            faces[key] = {"as_is": float(np.abs(native - model).max()),
                          "rows_flipped": float(np.abs(native[::-1] - model).max())}
    facts["faces"] = faces
    read = [v for v in faces.values() if v]
    facts["faces_read"] = len(read)
    orientation = "as_is" if all(v["as_is"] <= v["rows_flipped"] for v in read[:6]) else "rows_flipped"
    facts["readback_rows"] = orientation
    facts["face_texel_max_error"] = max(v[orientation] for v in read) if read else None
    swapped = got["swapped"]["look.l0"][..., :3].astype(np.float64)
    matrix_l0 = got["matrix"]["look.l0"][..., :3].astype(np.float64)
    facts["matrix_l0_max_error"] = float(np.abs(matrix_l0 - _cube_sample(cone[0], d)).max())
    checks["faces_drawn_through_umatrix_match_the_twin"] = facts["matrix_l0_max_error"] <= 0.01
    facts["swapped_l0_max_error"] = float(np.abs(swapped - _cube_sample(cone[0], d)).max())
    tol = {0: 0.01, 2: 0.03, 3: 0.05}
    checks["drawn_with_no_failure"] = not facts["probe_failing"] and not facts["probe_reason"]
    checks["six_face_runs_and_a_prefilter"] = (facts["probe_counts"]["scene_cube_face_runs"] >= 6
                                               and facts["probe_counts"]["scene_cube_prefilters"] >= 1)
    checks["every_face_and_level_read_back"] = facts["faces_read"] == 6 * levels
    checks["every_face_and_level_matches_the_twin"] = (facts["face_texel_max_error"] or 1.0) <= 0.03
    e = errors["l0_cone"]
    checks["level_0_lookups_match_the_cone_twin"] = max(e["interior_max"], e["edge_max"]) <= tol[0]
    # The face readback's levels against both twins: the cone's within the bound, the box chain's past it (level 3).
    def texels(f, level):
        native = look[f"probe.colour#{f}" + (f"@{level}" if level else "")][..., :3].astype(np.float64)
        return native[::-1] if orientation == "rows_flipped" else native

    box_error = max(float(np.abs(texels(f, 3) - box[3][f]).max()) for f in range(6)) if read else 0.0
    facts["face_level_3_box_twin_error"] = box_error
    checks["control_box_mips_leave_the_bound_at_level_3_texels"] = box_error > 0.03
    if "mipped_cube_sampler_refused" in facts:
        facts["lookups_at_levels_2_and_3"] = "not run: this module refuses a cube's mipped sampler (fixed, rebuild)"
        checks["mipped_cube_sampler_admitted"] = False
    else:
        for level in PROBE_LEVELS[1:]:
            e = errors[f"l{level}_cone"]
            checks[f"level_{level}_lookups_match_the_cone_twin"] = max(e["interior_max"], e["edge_max"]) <= tol[level]
        checks["control_box_mips_leave_the_bound_at_level_3"] = errors["l3_box"]["interior_max"] > tol[3]
        checks["no_seam_at_level_3"] = facts["seam"]["native_edge_over_interior"] < 2.0
        checks["control_a_clamped_read_shows_the_seam"] = (facts["seam"]["clamped_edge_over_interior"]
                                                           > facts["seam"]["native_edge_over_interior"])
    checks["control_swapped_faces_leave_the_bound"] = facts["swapped_l0_max_error"] > 0.2
    return {"pass": all(checks.values()), "checks": checks, "facts": facts}


# --------------------------------------------------------------------------------------------------- the children

def child(args) -> dict:
    root = host_check._root(args.repo)
    out = Path(args.out_dir)
    record: dict = {"api": args.api, "rounds": list(args.rounds), "module_loaded": False, "instance_created": False}
    global OUT
    OUT = out
    API[0] = args.api
    if args.api == "opengl":
        from rendering.quick.bootstrap import configure_quick_graphics

        configure_quick_graphics(reason="eb-core-check")
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
    rounds = {"limits": round_limits, "skip": round_skip, "readback": round_readback, "geometry": round_geometry,
              "probe": round_probe}
    try:
        for name in args.rounds:
            if vulkan:
                core.set_vulkan_phase(f"n56 {name}")
            try:
                record[name] = rounds[name](core, engine, app, args.api, packs)
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
    return record


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--module-dir", default="release/native_module")
    parser.add_argument("--repo", default=".")
    parser.add_argument("--apis", nargs="+", default=list(APIS), choices=APIS)
    parser.add_argument("--rounds", nargs="+", default=list(ROUNDS), choices=ROUNDS)
    parser.add_argument("--label", default="n56_core")
    parser.add_argument("--layer-path", type=Path, default=None)
    parser.add_argument("--require-validation", action="store_true")
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

    out = artifact_paths.evidence_dir("native_core", "n5_6", args.label)
    out.mkdir(parents=True, exist_ok=True)
    environment = vk_validation.environment_record(_ALLOWED_ENV)
    bake_packs(out)
    results: dict = {}
    for api in [a for a in APIS if a in args.apis]:
        child_json = out / f"child_{api}.json"
        child_json.unlink(missing_ok=True)
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
        record["stderr_tail"] = (stderr or "")[-4000:]
        results[api] = record
    verdicts = {api: host_check.api_verdict(api, record, args.require_validation) for api, record in results.items()}
    failed = [reason for _ok, reasons in verdicts.values() for reason in reasons]
    if not environment["clean"]:
        failed.append(f"environment: {', '.join(environment['contaminating_set'])} set")
    summary = {"apis": args.apis, "rounds": args.rounds, "environment": environment,
               "verdicts": {api: {"pass": ok, "failed": reasons} for api, (ok, reasons) in verdicts.items()},
               "results": results, "pass": not failed}
    (out / "summary.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    for api, (ok, reasons) in verdicts.items():
        print(f"{api}: {'PASS' if ok else 'FAIL'}" + ("" if ok else " (" + "; ".join(reasons)[:2000] + ")"))
    print(f"evidence: {out / 'summary.json'}")
    print("N56 VERDICT " + ("PASS" if not failed else "FAIL: " + "; ".join(failed)[:4000]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
