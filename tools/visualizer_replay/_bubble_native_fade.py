"""Passive fade-input capture around the canonical Bubble 549-input owner replay.

No extra GPU draw/readback, GL query or state change. Optional own-vertex adapter
is a separately declared control; baseline mode requires every ordinary hash exact.
Canonical rule-(a) failure remains a failure, separate from capture integrity.
"""
from __future__ import annotations

import contextlib
import importlib.util
import inspect
import json
from pathlib import Path
import struct
import sys




def run(args):
    root = args.repo.resolve()
    sys.path.insert(0, str(root))
    from tools.visualizer_replay._bubble_native_common import (
        sha, wire, json_bytes, provenance, replay_helper_matches, resolve_input, fresh_output, LIVE_KEYS,
    )
    from tools import conventions_identity
    from tools.visualizer_replay import owner_render_parity as parity
    from rendering.quick.visualizer import native_route as route
    from rendering.quick.visualizer.node import VisualizerRenderNode
    from rendering.quick.visualizer.implementations import bubble
    from core.visualizer_engine import bubble_native_schema

    out = fresh_output(args.label)
    baseline_dir = resolve_input(root, args.baseline_dir)
    metadata_bytes = (baseline_dir / "reproduction_metadata.json").read_bytes()
    report_bytes = (baseline_dir / "native_render_parity.json").read_bytes()
    baseline = json.loads(metadata_bytes)
    old = json.loads(report_bytes)["results"]["bubble"]
    module_dir = resolve_input(root, args.module_dir)
    manifest_bytes = (module_dir / "remote_build_manifest.json").read_bytes()
    manifest = json.loads(manifest_bytes)
    saved = (route.GENERIC_MODE_SETTINGS, route.NATIVE_MODE_IDS, parity.SceneMirror.frame,
             parity.native_parity, VisualizerRenderNode._inherited_scene_opacity,
             bubble.QuickBubbleRenderer.render, route.NativeVisualizerRoute.card, route.bubble_program)
    registry = route.GENERIC_MODE_PROGRAMS
    registry_before = dict(registry)
    source = {"native_parity": sha(inspect.getsource(saved[3]).encode()),
              "bubble_program": sha(inspect.getsource(saved[7]).encode())}
    for name in ("bubble.frag", "bubble_ambient_points.vert", "bubble_ambient_points.frag",
                 "bubble_ambient_mask.vert", "bubble_ambient_mask.frag"):
        source[name] = sha((root / "widgets/spotify_visualizer/shaders" / name).read_bytes())
    settings = dict(conventions_identity.mode_runs("bubble", False))[""]
    checks = {"matched_baseline_helper": replay_helper_matches(baseline),
              "same_settings": settings == baseline["settings"],
              "same_manifest": sha(manifest_bytes) == baseline["manifest_sha256"],
              "same_sources": source == baseline["source_sha256"],
              "canonical_bubble_registry": registry.get("bubble") is saved[7],
              "baseline_complete": old["frames_drawn"] == [549, 549]
                  and len(old["python_hashes"]) == len(old["native_hashes"]) == 549}
    if not all(checks.values()):
        raise RuntimeError(f"preflight mismatch: {checks}")
    details = {"scope": __doc__, "helper_sha256": sha(Path(__file__).read_bytes()),
               "baseline_dir": str(baseline_dir), "baseline_metadata_sha256": sha(metadata_bytes),
               "baseline_report_sha256": sha(report_bytes), "baseline_helper_sha256": baseline["helper_sha256"],
               "manifest_sha256": sha(manifest_bytes), "source_sha256": source, "settings": settings,
               "capture_inputs": [244, 346], "quad_control_requested": args.quad_adapter is not None,
               "checks": checks, "captures": {}}
    details["diagnostic_tool"] = provenance("fade")

    active, phases, opacity_rows, cards = {}, {}, {}, {}

    def projection(snapshot):
        record = wire(bubble_native_schema.project(snapshot.logical))
        return {"logical_revision": snapshot.logical_revision,
                "logical_timestamp": snapshot.logical.logical_timestamp,
                "projected_frame": record, "projected_sha256": sha(json_bytes(record))}

    def record_capture(phase, index, entry):
        key = f"{phase}_{index}"
        target = details["captures"].setdefault(key, {"calls": 0, "stable": True, "data": entry})
        target["calls"] += 1
        target["stable"] = target["stable"] and json_bytes(target["data"]) == json_bytes(entry)

    def opacity(node):
        value = saved[4](node)  # the existing production call; no second Qt/GL property query
        if active.get("index") in (244, 346) and active.get("phase") in ("reference", "backdrop"):
            snapshot = node._snapshot
            if snapshot is not None and snapshot.logical.mode_id == "bubble":
                opacity_rows[(active["phase"], active["index"])] = {
                    "inherited_opacity_returned": value,
                    "snapshot_content_fade_before_fold": snapshot.presentation.content_fade,
                    "snapshot_scene_fade_before_fold": snapshot.presentation.scene_fade}
        return value

    def render(owner, frame):
        result = saved[5](owner, frame)
        if active.get("index") in (244, 346) and active.get("phase") in ("reference", "backdrop"):
            key = (active["phase"], active["index"])
            entry = {**projection(frame.snapshot), **opacity_rows.get(key, {}),
                     "renderer_snapshot_content_fade": frame.snapshot.presentation.content_fade,
                     "renderer_snapshot_scene_fade": frame.snapshot.presentation.scene_fade,
                     "actual_values_u_fade": owner._values["u_fade"],
                     "actual_u_fade_float32_hex": struct.pack("<f", owner._values["u_fade"]).hex(),
                     "actual_renderer_values": wire(owner._values)}
            projected = entry["projected_frame"]
            count = int(projected["u_bubble_count"])
            byte_checks = {}
            for name, rows in (("u_bubbles_pos", count), ("u_bubbles_extra", count), ("u_bubbles_trail", 3 * count)):
                numbers = [value for row in projected[name][:rows] for value in row]
                expected = struct.pack(f"<{len(numbers)}f", *numbers)
                actual = owner._values.get(name, b"")
                byte_checks[name] = isinstance(actual, bytes) and actual[:len(expected)] == expected
            byte_checks["u_big_class_bits"] = wire(owner._values["u_big_class_bits"]) == projected["u_big_class_bits"]
            entry["actual_active_uploads_match_projected_source"] = byte_checks
            record_capture(*key, entry)
        return result

    def card(owner, presentation, snapshot, geometry, metrics=None):
        result = saved[6](owner, presentation, snapshot, geometry, metrics)
        # Card() runs before mirror.frame; retain its exact immutable snapshot and result until the ordinary draw.
        cards[id(owner)] = (snapshot, wire(result))
        return result

    def scene_frame(mirror, index):
        if mirror not in phases:
            phases[mirror] = ("native" if isinstance(mirror, parity.NativeSceneMirror)
                              else "reference" if "reference" not in phases.values() else "backdrop")
        active.update(index=index, phase=phases[mirror])
        try:
            result = saved[2](mirror, index)
            if phases[mirror] == "native" and index in (244, 346):
                owner = mirror.route
                snapshot = owner._snapshot
                if snapshot is None or snapshot.logical.mode_id != "bubble":
                    raise RuntimeError(f"native input{index} does not retain Bubble")
                pending_snapshot, submitted_card = cards[id(owner)]
                # Published native state, read after the ordinary render/readback; no new GPU work.
                state = owner._content.item.state()
                entry = {**projection(snapshot), "snapshot_is_submitted_card_source": snapshot is pending_snapshot,
                         "snapshot_content_fade": snapshot.presentation.content_fade,
                         "snapshot_scene_fade": snapshot.presentation.scene_fade,
                         "submitted_card": submitted_card, "published_card_state": state["card"],
                         "state": {name: state.get(name) for name in
                             ("content_failing", "last_refusal", "last_reason", "records", "has_frame")},
                         "settings": wire(owner._settings)}
                if args.quad_adapter:
                    entry["submitted_native_program"] = state["program"]
                record_capture("native", index, entry)
            return result
        finally:
            active.clear()

    def native_parity(core, *positional, **keywords):
        details["runtime"] = dict(core.info)
        module = Path(core.info["module_path"])
        data = module.read_bytes()
        details["module_sha256"] = sha(data)
        checks["same_module"] = sha(data) == baseline["module_sha256"]
        entries = [entry for name, entry in manifest["files"].items() if Path(name).name == module.name]
        checks["official_module"] = len(entries) == 1 and entries[0].get("sha256") == sha(data) and entries[0].get("bytes") == len(data)
        if not checks["same_module"] or not checks["official_module"]:
            raise RuntimeError("loaded module differs from the frozen matched baseline/official manifest")
        details["ownership_before"] = core.composite_live()
        try:
            return saved[3](core, *positional, **keywords)
        finally:
            details["ownership_after"] = core.composite_live()
            details["live_hosts_after"] = core.live_hosts()

    route.GENERIC_MODE_SETTINGS = {**saved[0], "bubble": route.BUBBLE_SETTINGS}
    route.NATIVE_MODE_IDS = saved[1] | {"bubble"}
    parity.SceneMirror.frame, parity.native_parity = scene_frame, native_parity
    VisualizerRenderNode._inherited_scene_opacity = opacity
    bubble.QuickBubbleRenderer.render = render
    route.NativeVisualizerRoute.card = card
    try:
        adapter_context = contextlib.nullcontext(None)
        if args.quad_adapter:
            path = resolve_input(root, args.quad_adapter)
            spec = importlib.util.spec_from_file_location("bubble_quad_evidence_adapter", path)
            adapter = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(adapter)
            sys.path.insert(0, str(root / "native/core/python"))
            import probe_rings
            vertex_source = adapter.generate_vertex_source()
            vertex_pack = probe_rings.bake(vertex_source, "fade_quad.vert", out / "quad_pack")
            details["quad_adapter_sha256"] = sha(path.read_bytes())
            adapter_context = adapter.installed(route, vertex_pack)
        with adapter_context as facts:
            details["quad_adapter"] = facts
            code = parity.main(["--out", str(out), "--native", "--mode", "bubble", "--runs", "bubble",
                                "--placements", "display", "--seconds", "5.5", "--module-dir", str(module_dir)])
        details["owner_exit_code"] = code
        case = json.loads((out / "native_render_parity.json").read_bytes())["results"]["bubble"]
        checks["all_549_python_hashes_exact"] = case["python_hashes"] == old["python_hashes"]
        checks["all_549_native_hashes_exact"] = case["native_hashes"] == old["native_hashes"]
        checks["ordinary_counts_exact"] = all(case[name] == old[name] for name in
            ("inputs", "frames_drawn", "native_frames", "native_published", "switch_input", "region", "dpr"))
        checks["digests_identical"] = case["digests_identical"] is True
        checks["retired_hosts"] = details["live_hosts_after"] == 0
        checks["owned_resources_released"] = all(details["ownership_after"][key] == details["ownership_before"][key]
                                                  for key in LIVE_KEYS)
        for index in (244, 346):
            rows = {phase: details["captures"].get(f"{phase}_{index}") for phase in ("reference", "native", "backdrop")}
            checks[f"input{index}_captures_stable"] = all(row and row["calls"] > 0 and row["stable"] for row in rows.values())
            if not checks[f"input{index}_captures_stable"]:
                continue
            ref, native, back = (rows[phase]["data"] for phase in ("reference", "native", "backdrop"))
            checks[f"input{index}_source_projection_exact"] = ref["projected_sha256"] == native["projected_sha256"] == back["projected_sha256"]
            checks[f"input{index}_actual_python_active_uploads_exact"] = (
                all(ref["actual_active_uploads_match_projected_source"].values())
                and all(back["actual_active_uploads_match_projected_source"].values()))
            # The native program's settings also serve its separate ambient passes. Compare final Bubble
            # settings with the actual final renderer values; retain the other owners' keys explicitly.
            final_names = {name for name, _kind in bubble.BUBBLE_BLOCK.fields}
            final_settings = {key: value for key, value in native["settings"].items() if key in final_names}
            native["settings_outside_final_bubble_block"] = sorted(set(native["settings"]) - final_names)
            checks[f"input{index}_settings_exact"] = all(
                key in ref["actual_renderer_values"] and json_bytes(value) == json_bytes(ref["actual_renderer_values"][key])
                for key, value in final_settings.items()) and bool(final_settings)
            checks[f"input{index}_native_published_card_matches_submission"] = (native["snapshot_is_submitted_card_source"]
                and native["published_card_state"]["content_fade"] == native["submitted_card"]["content_fade"]
                and native["snapshot_content_fade"] == native["submitted_card"]["content_fade"])
            checks[f"input{index}_python_actual_fade_matches_folded_snapshot"] = (
                ref["actual_values_u_fade"] == ref["renderer_snapshot_content_fade"]
                == ref["snapshot_content_fade_before_fold"] * ref["inherited_opacity_returned"])
            checks[f"input{index}_native_not_failed"] = not native["state"]["content_failing"] and not native["state"]["last_refusal"]
            details.setdefault("fade_comparison", {})[str(index)] = {
                "python_actual_fade": ref["actual_values_u_fade"],
                "python_inherited_opacity": ref["inherited_opacity_returned"],
                "native_submitted_card_fade": native["published_card_state"]["content_fade"],
                "same_float32_fade": ref["actual_u_fade_float32_hex"] == struct.pack(
                    "<f", native["published_card_state"]["content_fade"]).hex()}
            if args.quad_adapter:
                passes = native["submitted_native_program"]["passes"]
                final = passes[-1] if passes else {}
                geometry = final.get("geometry", {})
                checks[f"input{index}_submitted_native_own_vertex_quad"] = (final.get("name") == "bubble"
                    and geometry.get("vertices") == 4 and geometry.get("instances") == 1
                    and geometry.get("topology") == "triangle_strip")
        if args.quad_adapter:
            details["native_hashes_changed_in_quad_control"] = not checks.pop("all_549_native_hashes_exact")
            checks["quad_program_restored"] = bool(details["quad_adapter"]["restored"])
            checks["quad_registry_entry_previously_present"] = details["quad_adapter"].get("registry_entry_previously_present") is True
            checks["quad_program_observed"] = (details["quad_adapter"].get("program_observed") is True
                                                and bool(details["quad_adapter"].get("programs")))
        details["passive_guards_pass"] = all(checks.values())
        print("FADE INPUT CAPTURE", json.dumps({"passive_guards_pass": details["passive_guards_pass"],
              "owner_exit_code": code, "failed_checks": [key for key, ok in checks.items() if not ok]}), flush=True)
        return code if details["passive_guards_pass"] else 2
    except BaseException:
        details["capture_failed"] = True
        raise
    finally:
        route.GENERIC_MODE_SETTINGS, route.NATIVE_MODE_IDS = saved[:2]
        parity.SceneMirror.frame, parity.native_parity = saved[2:4]
        VisualizerRenderNode._inherited_scene_opacity = saved[4]
        bubble.QuickBubbleRenderer.render = saved[5]
        route.NativeVisualizerRoute.card = saved[6]
        details["wrappers_restored"] = (route.GENERIC_MODE_SETTINGS is saved[0]
            and route.NATIVE_MODE_IDS is saved[1] and route.bubble_program is saved[7]
            and parity.SceneMirror.frame is saved[2] and parity.native_parity is saved[3]
            and VisualizerRenderNode._inherited_scene_opacity is saved[4]
            and bubble.QuickBubbleRenderer.render is saved[5]
            and route.NativeVisualizerRoute.card is saved[6]
            and route.GENERIC_MODE_PROGRAMS is registry
            and set(registry) == set(registry_before)
            and all(registry[key] is value for key, value in registry_before.items()))
        checks["all_wrappers_restored"] = details["wrappers_restored"]
        details["passive_guards_pass"] = not details.get("capture_failed") and all(checks.values())
        out.mkdir(parents=True, exist_ok=True)
        (out / "fade_capture_metadata.json").write_text(json.dumps(details, indent=2, allow_nan=False) + "\n", encoding="utf-8")
        if not details["wrappers_restored"]:
            raise RuntimeError("diagnostic wrappers did not restore the exact original owners")

