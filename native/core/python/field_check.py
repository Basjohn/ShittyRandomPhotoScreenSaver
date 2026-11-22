"""N5.2g's built proofs of ABI 43's field recipes (``native/core/src/field_recipe.h``; ``Current_Plan.md`` N5.2g), through
``rendering.native``, on a hidden host in one child process per graphics API (OpenGL, then Vulkan on the module's own
instance and device under validation with the shader-access opt-in). No window is ever visible.

The recipes are the product's (``rendering/quick/scene3d/native_fields.py``: Edge Bloom's edge field over a photograph,
Capillary Bloom's arrival field and extent), their packs the shipped ones. A still item samples each output through a
copy pass (texelFetch, exact) into an explicit-size target of the output's format, read back.

Rounds (each with its control):
  forms     every recipe made by its job (Vulkan with the job service) and in the frame (``in_frame``; OpenGL's only form):
            the outputs' bytes equal between the two forms; the in-frame form on OpenGL against Vulkan's (max difference
            reported). Control: the edge field at other thresholds differs.
  deadline  a field job given a 1 ms deadline gives way to the in-frame form at the next record (the state's
            fields.past_deadline and in_frame), its outputs equal to the job form's. Control: no deadline, committed by
            its job.
  ready     the owner's ready edge names every output (and the photo) once at the commit; frames at rest record nothing
            and deliver no edge. Control: before the commit no edge named an output.
  retire    the item destroyed with a field job in flight and after a commit: the mode textures, job images, queued and
            running jobs and the field recorders back to their counts before the round.

Usage (repository venv, from the checkout holding the built module):
  python native/core/python/field_check.py --module-dir release/native_module --require-validation
      --layer-path D:\\Temp\\Scratch\\SRPSS\\native_spike\\validation_layers\\extracted [--rounds forms deadline]
Evidence: .artifacts/evidence/native_core/n5_2g/<date>_<label>/summary.json. The verdict is the last printed line
("N52G FIELDS VERDICT PASS" or "... FAIL: ...").
"""
from __future__ import annotations

import argparse
import hashlib
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
ROUNDS = ("forms", "deadline", "ready", "retire")
CHILD_TIMEOUT_S = 1800
_ALLOWED_ENV: set[str] = set()
CARD = (64, 64)
PHOTO = (640, 360)
SETTLE_S = 20.0

COPY_FRAG = """#version 440
layout(location = 0) in vec2 v_uv;
layout(location = 0) out vec4 colour;
layout(binding = 1) uniform sampler2D uSource;
void main() {
    ivec2 size = textureSize(uSource, 0);
    colour = texelFetch(uSource, min(ivec2(v_uv * vec2(size)), size - 1), 0);
}
"""


def photo_pixels():
    """A deterministic picture with structure (discs, bars and a gradient), RGBA8 rows top first."""
    import numpy as np

    w, h = PHOTO
    y, x = np.mgrid[0:h, 0:w].astype(np.float64)
    r = 0.5 + 0.5 * np.sin(x / 23.0) * np.cos(y / 17.0)
    g = ((x // 40 + y // 30) % 2) * 0.6 + 0.2
    b = np.clip(1.0 - np.hypot(x - w * 0.6, y - h * 0.4) / 180.0, 0.0, 1.0)
    disc = np.hypot(x - 160.0, y - 200.0) < 70.0
    r = np.where(disc, 0.95, r)
    rgba = np.stack([r, g, b, np.ones_like(r)], axis=-1)
    return (rgba * 255.0 + 0.5).astype(np.uint8).tobytes()


def recipes(low_high=(0.05, 0.12)):
    from rendering.gl_programs.capillary_bloom_program import CAPILLARY_COST_GLSL
    from rendering.quick.scene3d.native_fields import edge_field_recipe, propagation_recipe, propagation_seed_layout
    from rendering.quick.transitions.implementations.capillary_bloom import QuickCapillaryBloomRenderer

    edge = edge_field_recipe(PHOTO, *low_high, input_texture="photo", output="edge_field")
    _key, sources, bound, values = QuickCapillaryBloomRenderer._field_inputs(4, 0.6, 1234, PHOTO)
    prop = propagation_recipe("capillary", propagation_seed_layout(CAPILLARY_COST_GLSL), PHOTO, sources, bound, values, arrival="arrival",
                              extent="extent")
    return {"edge": edge, "propagation": prop}


def _pack_folder() -> Path:
    from rendering.quick.render.native_background import transition_pack_path

    return transition_pack_path("crossfade").parent


def _copy_program(copy_pack: bytes, recipe):
    """One copy pass per output into an explicit target of its format and size."""
    from rendering.native.mode import ModePass, ModeTarget, PassSampler, TargetAttachment

    passes, targets = [], []
    for output in recipe.recipe["outputs"]:
        image = next(i for i in recipe.recipe["images"] if i["name"] == output["image"])
        name = f"t_{output['texture']}"
        fmt = "rgba16f" if image["format"] == "rgba16f" else "r32f"
        targets.append(ModeTarget(name, (TargetAttachment("colour", fmt),), size=tuple(image["size"])))
        passes.append(ModePass(f"copy_{output['texture']}", copy_pack, "replace",
                               (PassSampler("uSource", output["texture"], "nearest", "clamp", "none"),), target=name))
    return passes, targets


class FieldScene:
    def __init__(self, core, engine, host, packs: dict, recipe, *, in_frame: bool, deadline_ms: int = 0,
                 listen: bool = True, photo: bool = True) -> None:
        import eb_core_check as eb

        passes, targets = _copy_program(packs["copy.frag"], recipe)
        self.ready: list[list[str]] = []
        self.scene = eb._still(core, engine, host, CARD, packs, passes, targets, {})
        self.mode = self.scene.mode
        if listen:
            self.mode.on_textures_ready(lambda names: self.ready.append(list(names)))
        if photo:
            self.mode.texture("photo", photo_pixels(), PHOTO, in_frame=in_frame)
        pixels = photo_pixels() if recipe.recipe.get("input") else None
        self.mode.field(recipe.recipe, recipe.pack_bytes(_pack_folder()), list(recipe.blocks), pixels=pixels,
                        size=PHOTO if pixels else (0, 0), in_frame=in_frame, deadline_ms=deadline_ms)
        self.outputs = recipe.outputs

    def settle(self, app, timeout_s: float = SETTLE_S) -> dict:
        deadline = time.monotonic() + timeout_s
        while True:
            self.mode.update()
            self.scene.host.frames(1)
            app.processEvents()
            state = self.mode.state()
            fields = state.get("fields") or {}
            made = (fields.get("committed", 0) or 0) + (fields.get("in_frame", 0) or 0)
            if (made >= 1 and (state.get("texture_jobs") or {}).get("pending", 0) == 0) or time.monotonic() > deadline:
                self.scene.host.frames(2)
                app.processEvents()
                return self.mode.state()

    def read(self, app) -> dict:
        import eb_core_check as eb

        got = eb._targets(self.scene)
        return {name[len("t_"):].split(".")[0]: array for name, array in got.items()}

    def close(self, app) -> None:
        import eb_core_check as eb

        eb._close(self.scene, self.scene.host, app)


def _hash(array) -> str:
    return hashlib.sha256(array.tobytes()).hexdigest()[:16]


def _made(core, engine, app, packs, recipe, *, in_frame: bool, deadline_ms: int = 0):
    import eb_core_check as eb

    host = eb._host(core, CARD)
    scene = None
    try:
        scene = FieldScene(core, engine, host, packs, recipe, in_frame=in_frame, deadline_ms=deadline_ms)
        state = scene.settle(app)
        out = scene.read(app)
        return out, state, list(scene.ready)
    finally:
        if scene is not None:
            scene.close(app)
        host.close()


# --------------------------------------------------------------------------------------------------- forms

def round_forms(core, engine, app, api: str, packs: dict, out: Path) -> dict:
    import numpy as np

    checks, facts = {}, {}
    vulkan = api == "vulkan"
    arrays = {}
    for name, recipe in recipes().items():
        in_frame, state_in, _ = _made(core, engine, app, packs, recipe, in_frame=True)
        facts[f"{name}_in_frame_fields"] = state_in.get("fields")
        facts[f"{name}_in_frame_hashes"] = {k: _hash(v) for k, v in in_frame.items()}
        checks[f"{name}_in_frame_made"] = (state_in.get("fields") or {}).get("in_frame", 0) >= 1 and bool(in_frame)
        arrays[name] = in_frame
        for key, array in in_frame.items():
            np.save(out / f"{api}_{name}_{key}_in_frame.npy", array)
        if vulkan:
            job, state_job, _ = _made(core, engine, app, packs, recipe, in_frame=False)
            facts[f"{name}_job_fields"] = state_job.get("fields")
            facts[f"{name}_job_hashes"] = {k: _hash(v) for k, v in job.items()}
            checks[f"{name}_made_by_its_job"] = (state_job.get("fields") or {}).get("committed", 0) >= 1
            checks[f"{name}_job_equals_in_frame"] = (sorted(job) == sorted(in_frame) and all(
                np.array_equal(job[k], in_frame[k]) for k in in_frame))
        finite = all(np.isfinite(a.astype(np.float64)).all() for a in in_frame.values())
        checks[f"{name}_outputs_finite"] = finite
    edge = arrays["edge"]["edge_field"].astype(np.float64)
    facts["edge_distance_range"] = [float(edge[..., 0].min()), float(edge[..., 0].max())]
    facts["edge_strength_max"] = float(edge[..., 1].max())
    checks["edge_field_has_contours"] = facts["edge_strength_max"] > 0.5 and facts["edge_distance_range"][0] < 0.01
    arrival = arrays["propagation"]["arrival"].astype(np.float64)
    extent = float(arrays["propagation"]["extent"].astype(np.float64).ravel()[0])
    facts["arrival_max"] = float(arrival.max())
    facts["extent"] = extent
    checks["extent_is_the_arrivals_largest"] = abs(extent - facts["arrival_max"]) <= 1e-6 * max(1.0, extent)
    # Control: other thresholds change the edge field (the hashes see the recipe).
    other, _state, _ = _made(core, engine, app, packs, recipes((0.09, 0.2))["edge"], in_frame=True)
    checks["control_other_thresholds_differ"] = not np.array_equal(other["edge_field"], arrays["edge"]["edge_field"])
    return {"pass": all(checks.values()), "checks": checks, "facts": facts}


# --------------------------------------------------------------------------------------------------- deadline

def round_deadline(core, engine, app, api: str, packs: dict, out: Path) -> dict:
    import numpy as np

    checks, facts = {}, {}
    if api != "vulkan":
        return {"pass": True, "checks": {}, "facts": {"skipped": "no job service on OpenGL (in-frame only)"}}
    recipe = recipes()["edge"]
    job, state_job, _ = _made(core, engine, app, packs, recipe, in_frame=False)
    facts["no_deadline_fields"] = state_job.get("fields")
    checks["control_without_a_deadline_its_job_commits"] = (state_job.get("fields") or {}).get("committed", 0) >= 1
    attempts = []
    for _attempt in range(3):
        late, state, _ = _made(core, engine, app, packs, recipe, in_frame=False, deadline_ms=1)
        fields = state.get("fields") or {}
        attempts.append(fields)
        if fields.get("past_deadline", 0) >= 1:
            break
    facts["deadline_attempts"] = attempts
    last = attempts[-1]
    checks["past_its_deadline_the_job_gives_way"] = last.get("past_deadline", 0) >= 1 and last.get("in_frame", 0) >= 1
    checks["the_in_frame_outputs_equal_the_jobs"] = all(np.array_equal(late[k], job[k]) for k in job)
    jobs = core.job_counts()
    facts["job_counts_after"] = jobs
    return {"pass": all(checks.values()), "checks": checks, "facts": facts}


# --------------------------------------------------------------------------------------------------- ready

def round_ready(core, engine, app, api: str, packs: dict, out: Path) -> dict:
    import eb_core_check as eb

    checks, facts = {}, {}
    recipe = recipes()["propagation"]
    host = eb._host(core, CARD)
    scene = None
    try:
        scene = FieldScene(core, engine, host, packs, recipe, in_frame=False)
        checks["control_nothing_named_before_the_commit"] = not scene.ready
        state = scene.settle(app)
        facts["edges"] = list(scene.ready)
        named = {name for names in scene.ready for name in names}
        checks["every_output_named"] = set(recipe.outputs) <= named
        outputs_edges = [names for names in scene.ready if set(recipe.outputs) & set(names)]
        checks["the_outputs_named_once"] = len(outputs_edges) == 1
        records = state.get("records")
        before = len(scene.ready)
        for _ in range(8):
            scene.scene.host.frames(1)
            app.processEvents()
        after = scene.mode.state()
        facts["records_at_rest"] = [records, after.get("records")]
        checks["nothing_recorded_at_rest"] = after.get("records") == records
        checks["no_edge_at_rest"] = len(scene.ready) == before
        facts["ready_counters"] = [after.get("textures_ready_edges"), after.get("textures_ready_delivered")]
    finally:
        if scene is not None:
            scene.close(app)
        host.close()
    return {"pass": all(checks.values()), "checks": checks, "facts": facts}


# --------------------------------------------------------------------------------------------------- retire

def _counts(core) -> dict:
    live = core.composite_live()
    jobs = core.job_counts()
    fields = core.field_counts()
    return {"mode_textures": live.get("mode_textures"), "mode_texture_images": live.get("mode_texture_images"),
            "job_images": jobs.get("job_images"), "jobs_queued": jobs.get("jobs_queued"),
            "jobs_running": jobs.get("jobs_running"), "field_recorders": fields.get("field_recorders")}


def round_retire(core, engine, app, api: str, packs: dict, out: Path) -> dict:
    import eb_core_check as eb

    checks, facts = {}, {}
    host_check._flush_deletes(app)
    before = _counts(core)
    facts["before"] = before
    for label, settle in (("after_commit", True), ("in_flight", False)):
        host = eb._host(core, CARD)
        scene = FieldScene(core, engine, host, packs, recipes()["edge"], in_frame=False)
        if settle:
            scene.settle(app)
        else:
            scene.mode.update()
            host.frames(1)
        scene.close(app)
        host.close()
        host_check._flush_deletes(app)
        core.wait_jobs_idle(5000)
        for _ in range(6):
            app.processEvents()
        host_check._flush_deletes(app)
        after = _counts(core)
        facts[label] = after
        checks[f"{label}_back_to_before"] = after == before
    return {"pass": all(checks.values()), "checks": checks, "facts": facts}


# --------------------------------------------------------------------------------------------------- the children

def bake_packs(out: Path) -> None:
    import probe_rings

    folder = out / "work" / "packs"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "copy.frag.qsb").write_bytes(probe_rings.bake(COPY_FRAG, "copy.frag", folder / "src"))


def load_packs(out: Path) -> dict:
    return {p.name[:-4]: p.read_bytes() for p in (out / "work" / "packs").glob("*.qsb")}


def child(args) -> dict:
    root = host_check._root(args.repo)
    out = Path(args.out_dir)
    record: dict = {"api": args.api, "rounds": list(args.rounds), "module_loaded": False, "instance_created": False}
    if args.api == "opengl":
        from rendering.quick.bootstrap import configure_quick_graphics

        configure_quick_graphics(reason="field-check")
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
        instance = core.vulkan_instance(validation=True, shader_accesses=True)
        record["instance"] = instance
        if not instance.get("ok"):
            record["error"] = f"the Vulkan instance failed: {instance.get('instance', {}).get('error')}"
            return record
        record["instance_created"] = True
    engine = QQmlEngine()
    packs = load_packs(out)
    rounds = {"forms": round_forms, "deadline": round_deadline, "ready": round_ready, "retire": round_retire}
    try:
        for name in args.rounds:
            if vulkan:
                core.set_vulkan_phase(f"n52g {name}")
            try:
                record[name] = rounds[name](core, engine, app, args.api, packs, out)
            except Exception:
                record[name] = {"pass": False, "error": traceback.format_exc()}
    finally:
        host_check._flush_deletes(app)
        record["live_hosts_at_end"] = core.live_hosts()
        record["composites_at_end"] = core.composite_live()
        record["job_services"] = core.job_services_state()
        if vulkan:
            teardown = core.destroy_vulkan_instance()
            messages = teardown.pop("messages", {}) if isinstance(teardown, dict) else {}
            summary = vk_validation.validation_summary(messages)
            record["instance_teardown"] = teardown
            record["validation"] = {"layer_loaded": bool(record["instance"].get("validation_layer_loaded")),
                                    "shader_accesses": (record["instance"].get("synchronisation_shader_accesses")
                                                        or (record["instance"].get("instance") or {}).get(
                                                            "synchronisation_shader_accesses")),
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
    parser.add_argument("--label", default="fields")
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

    out = artifact_paths.evidence_dir("native_core", "n5_2g", args.label)
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
    # OpenGL's in-frame outputs against Vulkan's (both written by this run).
    try:
        import numpy as np

        cross = {}
        for path in sorted(out.glob("opengl_*_in_frame.npy")):
            other = out / path.name.replace("opengl_", "vulkan_", 1)
            if other.is_file():
                a, b = np.load(path).astype(np.float64), np.load(other).astype(np.float64)
                cross[path.stem[len("opengl_"):]] = {"max_abs": float(np.abs(a - b).max()),
                                                     "differing": int((a != b).sum()), "texels": int(a.size)}
        if cross:
            results["opengl_against_vulkan"] = cross
    except Exception:
        results["opengl_against_vulkan"] = {"error": traceback.format_exc()}
    summary = {"apis": args.apis, "rounds": args.rounds, "environment": environment,
               "verdicts": {api: {"pass": ok, "failed": reasons} for api, (ok, reasons) in verdicts.items()},
               "results": results, "pass": not failed}
    (out / "summary.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    for api, (ok, reasons) in verdicts.items():
        print(f"{api}: {'PASS' if ok else 'FAIL'}" + ("" if ok else " (" + "; ".join(reasons)[:2000] + ")"))
    print(f"evidence: {out / 'summary.json'}")
    print("N52G FIELDS VERDICT " + ("PASS" if not failed else "FAIL: " + "; ".join(failed)[:4000]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
