"""N5.6's built proofs of Extruded Bubble's core boxes (ABI 42; ``Current_Plan.md`` N5.6), through ``rendering.native``,
on harness scenes of their own: the module (``release/native_module``, built on GitHub) loaded the product's way in one
child process per graphics API (OpenGL, then Vulkan on the module's own instance and device under validation). No window
is ever visible (hidden hosts only).

The ABI 42 keys the product's face does not speak yet (the port's) are sent as raw declarations (``Raw``) through the
face's own ``program_json``.

Rounds (each with its control):
  limits    a 48-pass, 6-target program admitted and drawn (its last pass's fill read back), nothing recorded at rest; 49
            passes and 7 targets refused with their reasons; six surface-sized RGBA16F targets' bytes at 3840x2160.
  skip      a pass's "when" (a record u32): at 0 it draws nothing (the frame equals the program without it), at 1 it
            draws; mode_entries_skipped counts each skipped record. The defocus step and its near layer skipped at 0:
            the frame equals the program without the layer, stage_defocus_records flat. Control: the program-only form
            (no "when") still draws at 0.
  readback  D4's pair-check kernel as a "once" entry with a "readback": read once (check_readbacks +1, about 2 KB), its
            report in the state ("check") exact as DriftSolver.check judges it, taken at a later record (records go on),
            flat over a steady run, the harness readback never used. Control: the kernel without its error terms is
            reported inexact.

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
ROUNDS = ("limits", "skip", "readback")
CHILD_TIMEOUT_S = 1800
_ALLOWED_ENV: set[str] = set()
CARD = (64, 64)
FILL = [0.25, 0.5, 0.75, 1.0]
EXTRA = [0.5, 0.25, 0.0, 0.0]
CODES = {"skip": 260, "skip_plain": 261, "defocus": 262, "defocus_plain": 263}

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
SHADERS = {"fill.frag": FILL_FRAG, "extra.frag": EXTRA_FRAG}


class Raw:
    """A declaration the face does not speak yet (ABI 42's keys), with its pack, for ``program_json``."""

    def __init__(self, declaration: dict, pack: bytes = b"") -> None:
        self._declaration = declaration
        self.pack = pack

    def declaration(self) -> dict:
        return dict(self._declaration)


def _with(entry, **keys) -> Raw:
    return Raw(dict(entry.declaration(), **keys), getattr(entry, "pack", b"") or b"")


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

    scene.mode.read_targets()
    if publish is not None:
        scene.publish(**publish)
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
            checks["drawn_at_1"] = bool((on == both).all() and (again == both).all())
            checks["skipped_at_0"] = bool((off == alone).all())
            checks["each_record_at_0_counted"] = facts["skipped"] >= 10
            checks["no_failure"] = not scene.mode.state().get("content_failing")
        finally:
            _close(scene, host, app)
        # Control: the program-only form (no "when") still draws at 0.
        scene, _u = _streamed(core, engine, host, "skip_plain", (base, extra), (target,), settings, entries, {"w": 1},
                              unread_retry=("w",))
        try:
            plain = _targets(scene, publish={"w": 0})["scene.colour"]
            checks["control_program_only_form_still_draws_at_0"] = bool((plain == both).all())
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
    plain_passes, plain_targets = ps.eb_program(stage_packs, variant="no_defocus", capture=False)
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


# --------------------------------------------------------------------------------------------------- the children

def child(args) -> dict:
    root = host_check._root(args.repo)
    out = Path(args.out_dir)
    record: dict = {"api": args.api, "rounds": list(args.rounds), "module_loaded": False, "instance_created": False}
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
    rounds = {"limits": round_limits, "skip": round_skip, "readback": round_readback}
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
