"""Fixed346 ambient component capture around the canonical Bubble 549-input replay.

Python reads existing pre/post-mask coverage and post-mask light. Native inserts
one supported CapturePass only after the ordinary346 output, then restores the
canonical program. Every ordinary frame must remain exact against the baseline run given (its preflight refuses a
baseline whose sources differ, such as the pre-mask-repair c53 one).
"""
from __future__ import annotations

import inspect
import json
from pathlib import Path
import struct
import sys


from tools.visualizer_replay._bubble_native_common import (
    sha, wire, json_bytes, provenance, passive_helper_matches, replay_helper_matches,
    resolve_input, fresh_output, LIVE_KEYS,
)


def run(args):
    root = args.repo.resolve()
    sys.path.insert(0, str(root))
    from tools import conventions_identity
    from tools.visualizer_replay import owner_render_parity as parity
    from rendering.quick.visualizer import native_route as route
    from rendering.quick.visualizer.node import VisualizerRenderNode
    from rendering.quick.visualizer.implementations import bubble
    from core.visualizer_engine import bubble_native_schema
    from rendering.quick.visualizer.implementations.bubble_ambient_gl import QuickBubbleAmbientPoints
    import numpy as np

    out = fresh_output(args.label)
    baseline_dir = resolve_input(root, args.baseline_dir)
    metadata_bytes = (baseline_dir / "reproduction_metadata.json").read_bytes()
    report_bytes = (baseline_dir / "native_render_parity.json").read_bytes()
    baseline = json.loads(metadata_bytes)
    old = json.loads(report_bytes)["results"]["bubble"]
    passive_bytes = (resolve_input(root, args.passive_dir) / "fade_capture_metadata.json").read_bytes()
    passive = json.loads(passive_bytes)
    module_dir = resolve_input(root, args.module_dir)
    manifest_bytes = (module_dir / "remote_build_manifest.json").read_bytes()
    manifest = json.loads(manifest_bytes)
    saved = (route.GENERIC_MODE_SETTINGS, route.NATIVE_MODE_IDS, parity.SceneMirror.frame,
             parity.native_parity, VisualizerRenderNode._inherited_scene_opacity,
             bubble.QuickBubbleRenderer.render, route.NativeVisualizerRoute.card, route.bubble_program,
             QuickBubbleAmbientPoints._draw_occluders, QuickBubbleAmbientPoints.render_texture)
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
              "matched_passive_receipt": passive_helper_matches(passive)
                  and passive.get("passive_guards_pass") is True and all(passive["checks"].values())
                  and passive["manifest_sha256"] == sha(manifest_bytes)
                  and passive["source_sha256"] == source and passive["settings"] == settings
                  and passive["module_sha256"] == baseline["module_sha256"]
                  and passive["baseline_helper_sha256"] == baseline["helper_sha256"]
                  and passive["baseline_metadata_sha256"] == sha(metadata_bytes)
                  and passive["baseline_report_sha256"] == sha(report_bytes),
              "baseline_complete": old["frames_drawn"] == [549, 549]
                  and len(old["python_hashes"]) == len(old["native_hashes"]) == 549}
    if not all(checks.values()):
        raise RuntimeError(f"preflight mismatch: {checks}")
    details = {"scope": __doc__, "helper_sha256": sha(Path(__file__).read_bytes()),
               "baseline_dir": str(baseline_dir), "baseline_metadata_sha256": sha(metadata_bytes),
               "baseline_report_sha256": sha(report_bytes), "baseline_helper_sha256": baseline["helper_sha256"],
               "manifest_sha256": sha(manifest_bytes), "source_sha256": source, "settings": settings,
               "capture_inputs": [346], "passive_metadata_sha256": sha(passive_bytes),
               "component_scope": "pre/post coverage and post light; native CapturePass captures color0 only, so no native pre-light",
               "checks": checks, "captures": {}}
    owner_paths = {name: root / name for name in (
        "rendering/quick/visualizer/implementations/bubble.py",
        "rendering/quick/visualizer/implementations/bubble_ambient_gl.py",
        "rendering/quick/visualizer/native_route.py", "native/core/python/scene_target_check.py")}
    details["component_owner_source_sha256"] = {name: sha(path.read_bytes()) for name, path in owner_paths.items()}
    details["diagnostic_tool"] = provenance("components")

    active, phases, opacity_rows, cards = {}, {}, {}, {}
    arrays, component_facts, component_checks = {}, {}, {}
    details.update(component_facts=component_facts, component_checks=component_checks)

    def finite(name, array):
        component_checks[f"{name}_finite"] = bool(np.isfinite(array).all())
        if not component_checks[f"{name}_finite"]:
            raise RuntimeError(f"nonfinite component {name}; no differences admitted")

    def remember(name, array):
        finite(name, array)
        if name in arrays:
            component_checks[f"{name}_repeat_exact"] = bool(np.array_equal(arrays[name], array))
        arrays[name] = array.copy()

    def python_components(owner, stage):
        """Current existing owned FBO. Restore read-FBO/read-buffer/PBO and every altered pack state."""
        from OpenGL import GL as gl
        from rendering.quick import gl_query

        names = (gl.GL_PACK_ALIGNMENT, gl.GL_PACK_ROW_LENGTH, gl.GL_PACK_SKIP_ROWS, gl.GL_PACK_SKIP_PIXELS,
                 gl.GL_PACK_IMAGE_HEIGHT, gl.GL_PACK_SKIP_IMAGES, gl.GL_PACK_SWAP_BYTES, gl.GL_PACK_LSB_FIRST)
        pack = {name: gl_query.get_int(name) for name in names}
        old_fbo = gl_query.get_int(gl.GL_READ_FRAMEBUFFER_BINDING)
        old_buffer = gl_query.get_int(gl.GL_READ_BUFFER)
        old_pbo = gl_query.get_int(gl.GL_PIXEL_PACK_BUFFER_BINDING)
        owner_buffer = None
        width, height = owner.target_size
        try:
            gl.glBindBuffer(gl.GL_PIXEL_PACK_BUFFER, 0)
            for name in names:
                gl.glPixelStorei(name, 1 if name == gl.GL_PACK_ALIGNMENT else 0)
            gl.glBindFramebuffer(gl.GL_READ_FRAMEBUFFER, owner._fbo)
            owner_buffer = gl_query.get_int(gl.GL_READ_BUFFER)
            gl.glReadBuffer(gl.GL_COLOR_ATTACHMENT0)
            raw = gl.glReadPixels(0, 0, width, height, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE)
            data = raw if isinstance(raw, bytes) else np.asarray(raw).tobytes()
            remember(f"reference_{stage}_coverage", np.frombuffer(data, np.uint8).reshape(height, width, 4)[::-1])
            if stage == "post":
                if not owner._light_texture:
                    raise RuntimeError("fixed346 must retain its enabled light attachment")
                gl.glReadBuffer(gl.GL_COLOR_ATTACHMENT1)
                raw = gl.glReadPixels(0, 0, width, height, gl.GL_RGBA, gl.GL_FLOAT)
                data = raw if isinstance(raw, bytes) else np.asarray(raw).tobytes()
                light32 = np.frombuffer(data, np.float32).reshape(height, width, 4)[::-1]
                finite("reference_post_light_float32", light32)
                remember("reference_post_light", light32.astype(np.float16))
            component_facts[f"reference_{stage}"] = {"size": [width, height], "fbo": owner._fbo,
                "coverage_texture": owner._texture, "light_texture": owner._light_texture,
                "orientation": "glReadPixels bottom-first -> flipud", "coverage_format": "rgba8", "light_format": "rgba16f"}
        finally:
            if owner_buffer is not None:
                gl.glReadBuffer(owner_buffer)
            gl.glBindFramebuffer(gl.GL_READ_FRAMEBUFFER, old_fbo)
            gl.glReadBuffer(old_buffer)
            gl.glBindBuffer(gl.GL_PIXEL_PACK_BUFFER, old_pbo)
            for name, value in pack.items():
                gl.glPixelStorei(name, value)

    def mask(owner, *positional, **keywords):
        if active.get("index") == 346 and active.get("phase") == "reference":
            python_components(owner, "pre")
        return saved[8](owner, *positional, **keywords)

    def ambient(owner, *positional, **keywords):
        result = saved[9](owner, *positional, **keywords)
        if active.get("index") == 346 and active.get("phase") == "reference":
            python_components(owner, "post")
        return result

    def native_components(mirror, snapshot, ordinary):
        from rendering.native.mode import CapturePass
        from rendering.native.program_values import mode_fragment_pack
        sys.path.insert(0, str(root / "native/core/python"))
        import scene_target_check as stc

        owner = mirror.route
        content = owner._content
        mode = content.item
        values = dict(owner._settings)
        program = registry["bubble"](mode_fragment_pack("bubble"), dict(content._sizes))
        modified = [program["passes"][0], CapturePass("diagnostic_ambient_before_mask", "ambient"), *program["passes"][1:]]
        before = mode.state()
        component_checks["native_no_prior_pending_readback"] = before.get("target_readback_pending") is False
        if not component_checks["native_no_prior_pending_readback"]:
            raise RuntimeError("native target readback already pending before this diagnostic")
        component_facts["submitted_program_before"] = before["program"]
        component_facts["capture_pass_declaration"] = [item.declaration() for item in modified]
        pixels = None
        try:
            mode.program(modified, values, targets=program["targets"], streams=program["streams"])
            mode.target_pixels()  # discard any earlier completed request, then issue one fresh request
            mode.read_targets()
            mode.update()
            for attempts in range(1, 7):
                mirror.host.render()
                pixels = mode.target_pixels()
                if pixels is not None:
                    break
            component_facts["native_capture_renders"] = attempts
            component_checks["native_fresh_readback_completed"] = pixels is not None
            state = mode.state()
            component_facts["native_published_capture_state"] = state
            component_checks["native_one_read_request"] = state["target_reads_requested"] == before["target_reads_requested"] + 1
            component_checks["native_readback_no_longer_pending"] = state.get("target_readback_pending") is False
            component_checks["native_capture_not_failed"] = not state.get("content_failing") and not state.get("last_refusal") and not state.get("error")
            captured = mirror._read(mirror._region)
            finite("native_capture_final346", captured)
            component_checks["native_capture_final346_exact"] = bool(np.array_equal(captured, ordinary))
            for entry in pixels or []:
                selected = {"ambient.capture_colour": "pre_coverage", "ambient.coverage": "post_coverage",
                            "ambient.light": "post_light"}.get(entry["name"])
                if selected is None:
                    continue
                name = f"native_{selected}"
                remember(name, stc._content(stc._array(entry)))  # native z1 memory: top-first crop, NO flip
                component_facts[name] = {key: entry[key] for key in ("name", "size", "content", "format", "samples", "level")}
                component_facts[name]["crop"] = [0, entry["size"][1] - entry["content"][1], *entry["content"]]
                component_checks[f"{name}_metadata"] = (entry["format"] == ("rgba16f" if selected == "post_light" else "rgba8")
                    and entry["samples"] == 1 and entry["level"] == 0
                    and list(entry["content"]) == [int(value) for value in values["u_ambient_px"]])
            component_checks["native_capture_snapshot_unchanged"] = owner._snapshot is snapshot
        finally:
            mode.program(program["passes"], values, targets=program["targets"], streams=program["streams"])
            mode.update()
            for _ in range(4):
                mirror.host.render()
            restored = mirror._read(mirror._region)
            finite("native_restored_final346", restored)
            component_checks["native_restored_final346_exact"] = bool(np.array_equal(restored, ordinary))
            state = mode.state()
            component_facts["native_published_restored_state"] = state
            # Each supported program() replacement admits a new generation. Compare every semantic field,
            # exempt only that nonce, and require exactly the capture + restoration generation advances.
            component_checks["native_submitted_program_restored"] = {
                key: value for key, value in state["program"].items() if key != "generation"} == {
                key: value for key, value in before["program"].items() if key != "generation"}
            component_checks["native_program_generation_advanced_twice"] = (
                state["program"]["generation"] == before["program"]["generation"] + 2)
            component_checks["native_restore_not_failed"] = not state.get("content_failing") and not state.get("last_refusal") and not state.get("error")
            component_checks["native_restore_snapshot_unchanged"] = owner._snapshot is snapshot

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
        if active.get("index") == 346 and active.get("phase") in ("reference", "backdrop"):
            snapshot = node._snapshot
            if snapshot is not None and snapshot.logical.mode_id == "bubble":
                opacity_rows[(active["phase"], active["index"])] = {
                    "inherited_opacity_returned": value,
                    "snapshot_content_fade_before_fold": snapshot.presentation.content_fade,
                    "snapshot_scene_fade_before_fold": snapshot.presentation.scene_fade}
        return value

    def render(owner, frame):
        result = saved[5](owner, frame)
        if active.get("index") == 346 and active.get("phase") in ("reference", "backdrop"):
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
            if phases[mirror] == "native" and index == 346:
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
                record_capture("native", index, entry)
                ordinary = parity._pixels({"frames": mirror.frames}, index).copy()
                finite("native_ordinary_final346", ordinary)
                component_checks["native_ordinary_final346_exact_baseline"] = sha(ordinary.tobytes()) == old["native_hashes"][346]
                native_components(mirror, snapshot, ordinary)
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
    QuickBubbleAmbientPoints._draw_occluders = mask
    QuickBubbleAmbientPoints.render_texture = ambient
    try:
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
        for index in (346,):
            rows = {phase: details["captures"].get(f"{phase}_{index}") for phase in ("reference", "native", "backdrop")}
            checks[f"input{index}_captures_stable"] = all(row and row["calls"] > 0 and row["stable"] for row in rows.values())
            if not checks[f"input{index}_captures_stable"]:
                continue
            ref, native, back = (rows[phase]["data"] for phase in ("reference", "native", "backdrop"))
            checks[f"input{index}_source_projection_exact"] = ref["projected_sha256"] == native["projected_sha256"] == back["projected_sha256"]
            checks[f"input{index}_projection_matches_passive_receipt"] = all(
                rows[phase]["data"]["projected_sha256"] == passive["captures"][f"{phase}_{index}"]["data"]["projected_sha256"]
                for phase in rows)
            checks[f"input{index}_python_values_match_passive_receipt"] = all(
                json_bytes(rows[phase]["data"]["actual_renderer_values"]) == json_bytes(
                    passive["captures"][f"{phase}_{index}"]["data"]["actual_renderer_values"])
                for phase in ("reference", "backdrop"))
            prior_native = passive["captures"][f"native_{index}"]["data"]
            checks[f"input{index}_native_submission_matches_passive_receipt"] = all(
                json_bytes(native[name]) == json_bytes(prior_native[name])
                for name in ("submitted_card", "published_card_state", "settings"))
            checks[f"input{index}_emitted_light_still_enabled"] = native["projected_frame"]["u_ambient_light_enabled"] == 1
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
        required = {"reference_pre_coverage", "reference_post_coverage", "reference_post_light",
                    "native_pre_coverage", "native_post_coverage", "native_post_light"}
        component_checks["required_components_complete"] = set(arrays) == required
        comparisons = {}
        for stage in ("pre_coverage", "post_coverage", "post_light"):
            reference = arrays.get(f"reference_{stage}")
            native = arrays.get(f"native_{stage}")
            same = reference is not None and native is not None and reference.shape == native.shape and reference.dtype == native.dtype
            component_checks[f"{stage}_shape_dtype_match"] = same
            if not same:
                continue
            finite(f"comparison_reference_{stage}", reference)
            finite(f"comparison_native_{stage}", native)
            delta = np.abs(native.astype(np.float64) - reference.astype(np.float64))
            comparisons[stage] = {"shape": list(reference.shape), "dtype": str(reference.dtype),
                "differing_texels": int(np.any(delta > 0, axis=2).sum()), "max_abs": float(delta.max())}
            fixed = []
            case_origin, case_dpr, region = case["outer_origin"], case["dpr"], case["region"]
            content_rect = details["captures"]["native_346"]["data"]["settings"]["u_content_rect"]
            for x, y in ((266, 143), (270, 143)):
                cx = region[0] + x + .5 - (case_origin[0] + content_rect[0]) * case_dpr
                cy = region[1] + y + .5 - (case_origin[1] + content_rect[1]) * case_dpr
                tx, ty = int(np.floor(cx)), int(np.floor(cy))
                if not (0 <= tx < reference.shape[1] and 0 <= ty < reference.shape[0]):
                    raise RuntimeError("fixed final pixel does not map inside the actual content")
                fixed.append({"final_xy": [x, y], "content_center_xy": [cx, cy], "texel_xy": [tx, ty],
                    "reference": reference[ty, tx].tolist(), "native": native[ty, tx].tolist(), "abs_delta": delta[ty, tx].tolist()})
            comparisons[stage]["fixed_pixels"] = fixed
        details["component_comparisons"] = comparisons
        if "reference_pre_coverage" in arrays:
            projected = details["captures"]["native_346"]["data"]["projected_frame"]
            points = np.frombuffer(bytes.fromhex(projected["ambient_points"]), dtype="<f4").reshape(-1, 6)
            occluders = np.frombuffer(bytes.fromhex(projected["ambient_occluders"]), dtype="<f4").reshape(-1, 4)
            finite("projected_points346", points)
            finite("projected_occluders346", occluders)
            point, hero = points[23].astype(np.float64), occluders[31].astype(np.float64)
            width, height = arrays["reference_pre_coverage"].shape[1::-1]
            px, py = int(point[0] * width), int(point[1] * height)
            native_settings = details["captures"]["native_346"]["data"]["settings"]
            point_center = np.array([point[0] * width, point[1] * height])
            hero_center = np.array([hero[0] * width, hero[1] * height])
            hero_radius = float(hero[2] * native_settings["u_response_radius_scale"] * height)
            point_size = (float(np.clip(point[2] * native_settings["uTexelScale"] * native_settings["uSpriteScale"], 1.0, 128.0))
                          if point[5] <= .5 else None)
            component_facts["orientation_landmark"] = {"point_index": 23, "center_texels": [float(point[0] * width), float(point[1] * height)],
                "reference": "flipud only", "native": "[H-h:H,0:w], NO flip"}
            # The known final bad pixel is mapped above from the actual card origin/content rectangle.
            # Record its vertical mirror, without choosing or fitting the source-defined orientation.
            tx, ty = comparisons["pre_coverage"]["fixed_pixels"][0]["texel_xy"]
            locations = {"suspect_edge": (tx, ty), "suspect_edge_vertical_mirror": (tx, height - 1 - ty),
                         "point23_interior": (px, py), "point23_interior_vertical_mirror": (px, height - 1 - py)}
            landmark = {"hero_index": 31, "hero_source": hero.tolist(), "hero_center_texels": hero_center.tolist(),
                "hero_radius_texels": hero_radius, "hero_alpha": float(hero[3]),
                "point_index": 23, "point_source": point.tolist(), "point_center_texels": point_center.tolist(),
                "point_sprite_size_texels": point_size, "point_radius_texels": None if point_size is None else .5 * point_size,
                "geometry_scope": "CPU double evaluation of actual f32 source records and current shader size formulas; not GPU interpolants",
                "mask_action_scope": "Integrity requires a reduction at the populated source-defined point23 center, not at the disputed edge; neither reduction uniquely identifies the occluder",
                "samples": {}}
            for phase in ("reference", "native"):
                image = arrays.get(f"{phase}_pre_coverage")
                component_checks[f"{phase}_landmark_populated"] = image is not None and bool(np.any(image[max(0, py-4):py+5, max(0, px-4):px+5, 3] > 0))
                post = arrays.get(f"{phase}_post_coverage")
                if image is None or post is None:
                    component_checks[f"{phase}_point23_interior_mask_action"] = False
                    continue
                for label, (sx, sy) in locations.items():
                    center = np.array([sx + .5, sy + .5])
                    pre_value, post_value = image[sy, sx], post[sy, sx]
                    populated = bool(pre_value[3] > 0)
                    reduced = bool(np.any(post_value < pre_value))
                    landmark["samples"][f"{phase}_{label}"] = {"texel_xy": [sx, sy], "center_texels": center.tolist(),
                        "pre_rgba": pre_value.tolist(), "post_rgba": post_value.tolist(),
                        "pre_coverage_populated": populated, "any_component_reduced": reduced,
                        "distance_to_hero_center": float(np.linalg.norm(center - hero_center)),
                        "signed_distance_to_hero_edge": float(np.linalg.norm(center - hero_center) - hero_radius),
                        "distance_to_point_center": float(np.linalg.norm(center - point_center))}
                    if label == "point23_interior":
                        component_checks[f"{phase}_point23_interior_mask_action"] = populated and reduced
            component_facts["hero_point_overlap_landmark"] = landmark
        checks.update(component_checks)
        checks["component_owner_sources_unchanged"] = details["component_owner_source_sha256"] == {
            name: sha(path.read_bytes()) for name, path in owner_paths.items()}
        out.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(out / "ambient_components_346.npz", **arrays)
        details["passive_guards_pass"] = all(checks.values())
        print("FIXED346 COMPONENT CAPTURE", json.dumps({"passive_guards_pass": details["passive_guards_pass"],
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
        QuickBubbleAmbientPoints._draw_occluders = saved[8]
        QuickBubbleAmbientPoints.render_texture = saved[9]
        details["wrappers_restored"] = (route.GENERIC_MODE_SETTINGS is saved[0]
            and route.NATIVE_MODE_IDS is saved[1] and route.bubble_program is saved[7]
            and parity.SceneMirror.frame is saved[2] and parity.native_parity is saved[3]
            and VisualizerRenderNode._inherited_scene_opacity is saved[4]
            and bubble.QuickBubbleRenderer.render is saved[5]
            and route.NativeVisualizerRoute.card is saved[6]
            and QuickBubbleAmbientPoints._draw_occluders is saved[8]
            and QuickBubbleAmbientPoints.render_texture is saved[9]
            and route.GENERIC_MODE_PROGRAMS is registry
            and set(registry) == set(registry_before)
            and all(registry[key] is value for key, value in registry_before.items()))
        checks["all_wrappers_restored"] = details["wrappers_restored"]
        details["passive_guards_pass"] = not details.get("capture_failed") and all(checks.values())
        out.mkdir(parents=True, exist_ok=True)
        (out / "component_capture_metadata.json").write_text(json.dumps(details, indent=2, allow_nan=False) + "\n", encoding="utf-8")
        if not details["wrappers_restored"]:
            raise RuntimeError("diagnostic wrappers did not restore the exact original owners")

