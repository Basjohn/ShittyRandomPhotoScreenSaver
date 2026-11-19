"""Bounded current-module Bubble rule-(a) reproduction; dormant registration is process-local.

No product settings/presets, shader or tolerance changes. Uses the canonical
owner_render_parity 5.5-second variant-a/display recipe and graphics bootstrap.
Canonical parity and diagnostic integrity remain independent verdicts.
"""
import inspect
import json
from pathlib import Path
import sys




def run(args):
    root = args.repo.resolve()
    sys.path.insert(0, str(root))
    from tools.visualizer_replay._bubble_native_common import (
        sha, provenance, resolve_input, fresh_output, LIVE_KEYS,
    )
    from tools import artifact_paths

    root = artifact_paths.repository_root(root)
    out = fresh_output(args.label)
    module_dir = resolve_input(root, args.module_dir)
    from rendering.quick.visualizer import native_route as route
    from tools.visualizer_replay import owner_render_parity as parity
    from tools import conventions_identity

    saved = (route.GENERIC_MODE_SETTINGS, route.NATIVE_MODE_IDS, parity.NativeSceneMirror.frame,
             parity.native_parity)
    registry = route.GENERIC_MODE_PROGRAMS
    registry_before = dict(registry)
    details = {"scope": "Current Bubble owner rule (a), variant a/display,5.5s; no production registration.",
               "helper_sha256": sha(Path(__file__).read_bytes()),
               "settings": dict(conventions_identity.mode_runs("bubble", False))[""],
               "source_sha256": {"native_parity": sha(inspect.getsource(parity.native_parity).encode()),
                    "bubble_program": sha(inspect.getsource(route.bubble_program).encode())}}
    for name in ("bubble.frag", "bubble_ambient_points.vert", "bubble_ambient_points.frag",
                 "bubble_ambient_mask.vert", "bubble_ambient_mask.frag"):
        path = root / "widgets/spotify_visualizer/shaders" / name
        details["source_sha256"][name] = sha(path.read_bytes())
    manifest_path = module_dir / "remote_build_manifest.json"
    manifest_bytes = manifest_path.read_bytes()
    details["manifest_sha256"] = sha(manifest_bytes)
    details["remote_build_manifest"] = json.loads(manifest_bytes)

    details["diagnostic_tool"] = provenance("replay")

    def frame(mirror, index):
        result = saved[2](mirror, index)
        if index == 244:
            content = getattr(mirror.route, "_content", None)
            if content is not None and hasattr(content, "item"):
                # Read already-published state only, after the canonical render/read.
                details["input244"] = {"state": content.item.state(),
                    "settings": dict(mirror.route._settings or {}),
                    "target_sizes": dict(getattr(content, "_sizes", None) or {})}
                snapshot = mirror.route._snapshot
                if snapshot is not None and snapshot.logical.mode_id == "bubble":
                    from core.visualizer_engine import bubble_native_schema
                    payload = bubble_native_schema.project(snapshot.logical)
                    details["input244"]["projected_frame"] = {k: v.hex() if isinstance(v, bytes) else v
                                                             for k, v in payload.items()}
        return result

    def native_parity(core, *positional, **keywords):
        details["runtime"] = dict(core.info)
        module = Path(core.info["module_path"])
        data = module.read_bytes()
        details["module_sha256"] = sha(data)
        entries = [v for k, v in details["remote_build_manifest"]["files"].items() if Path(k).name == module.name]
        if len(entries) != 1 or entries[0].get("sha256") != sha(data) or entries[0].get("bytes") != len(data):
            raise RuntimeError("loaded module does not match the retained official manifest")
        details["ownership_before"] = core.composite_live()
        try:
            return saved[3](core, *positional, **keywords)
        finally:
            details["ownership_after"] = core.composite_live()
            details["live_hosts_after"] = core.live_hosts()

    route.GENERIC_MODE_SETTINGS = {**saved[0], "bubble": route.BUBBLE_SETTINGS}
    route.NATIVE_MODE_IDS = saved[1] | {"bubble"}
    parity.NativeSceneMirror.frame = frame
    parity.native_parity = native_parity
    try:
        code = parity.main(["--out", str(out), "--native", "--mode", "bubble", "--runs", "bubble",
                            "--placements", "display", "--seconds", "5.5", "--module-dir", str(module_dir)])
        details["owner_exit_code"] = code
        case = json.loads((out / "native_render_parity.json").read_bytes())["results"]["bubble"]
        details["checks"] = {
            "all_549_inputs_drawn": case["frames_drawn"] == [549, 549]
                and len(case["python_hashes"]) == len(case["native_hashes"]) == 549,
            "digests_identical": case["digests_identical"] is True,
            "retired_hosts": details.get("live_hosts_after") == 0,
            "owned_resources_released": all(details["ownership_after"][key] == details["ownership_before"][key]
                for key in LIVE_KEYS),
        }
        return code if all(details["checks"].values()) else 2
    except BaseException:
        details["preparation_or_run_failed"] = True
        raise
    finally:
        route.GENERIC_MODE_SETTINGS, route.NATIVE_MODE_IDS = saved[:2]
        parity.NativeSceneMirror.frame, parity.native_parity = saved[2:]
        details["wrappers_restored"] = (
            route.GENERIC_MODE_SETTINGS is saved[0] and route.NATIVE_MODE_IDS is saved[1]
            and parity.NativeSceneMirror.frame is saved[2] and parity.native_parity is saved[3]
            and route.GENERIC_MODE_PROGRAMS is registry and set(registry) == set(registry_before)
            and all(registry[key] is value for key, value in registry_before.items()))
        details.setdefault("checks", {})["all_wrappers_restored"] = details["wrappers_restored"]
        details["passive_guards_pass"] = (not details.get("preparation_or_run_failed")
            and all(details["checks"].values()))
        out.mkdir(parents=True, exist_ok=True)
        (out / "reproduction_metadata.json").write_text(json.dumps(details, indent=2, default=str), encoding="utf-8")
        if not details["wrappers_restored"]:
            raise RuntimeError("diagnostic wrappers did not restore the exact original owners")

