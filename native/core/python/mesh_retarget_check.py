"""The N3.2 mesh-buffer harness's retarget round (audit 4 L2).

This module has no CLI, graphics setup, shader baker, validation handling or frame-stream owner. The parent passes
its existing harness module; graphics use its Scene and cleanup, compute uses compute_pass_check.Scene/storage,
and scene-graph reconstruction uses the existing hidden-host invalidation. mesh_buffers owns every shader pack.
"""
from __future__ import annotations

from dataclasses import replace
import struct


LIVE_KEYS = ("mesh_buffers_buffers_created", "mesh_buffers_mesh_uploads", "mesh_buffers_meshes",
             "mesh_buffers_streams", "mesh_buffers_arenas", "mesh_buffers_arena_bytes", "mode_resources")
RESIDENT_KEYS = ("mesh_buffers_streams", "mesh_buffers_arenas", "mesh_buffers_arena_bytes", "mode_resources")


def edge_checks(before: dict, after: dict, *, buffers: int | None = None, rebuild: bool = False) -> dict:
    """Judge real snapshots, including the streams' actual generation (there is no top-level builds field)."""
    old = before["state"]["mesh_buffers"]["generation"]
    new = after["state"]["mesh_buffers"]["generation"]
    checks = {"build_boundary": new > old if rebuild else new == old}
    if buffers is not None:
        checks["only_mesh_buffers_created"] = (
            after["live"]["mesh_buffers_buffers_created"] - before["live"]["mesh_buffers_buffers_created"] == buffers)
    if not rebuild:
        checks["stream_generation_unchanged"] = old == new
        checks["resident_counts_unchanged"] = all(before["live"][k] == after["live"][k] for k in RESIDENT_KEYS)
    return checks


def deform(vertices: bytes, stride: int) -> bytes:
    """Visible silhouette control: position bytes change, count/stride/normals stay the same."""
    data = bytearray(vertices)
    for offset in range(0, len(data), stride):
        x, y, z = struct.unpack_from("<3f", data, offset)
        struct.pack_into("<3f", data, offset, x * 0.57, y * 0.63, z)
    return bytes(data)


def pad_layout(data: bytes, layout):
    """Keep semantic data but change stride and offsets; a stale pipeline would read the sentinel prefix."""
    from rendering.native.mode import MeshAttribute, RecordLayout

    padded = b"".join(struct.pack("<f", 1234.0) + data[i:i + layout.stride]
                      for i in range(0, len(data), layout.stride))
    return padded, RecordLayout(layout.stride + 4, tuple(MeshAttribute(a.name, a.components, a.offset + 4)
                                                       for a in layout.attributes))


def _snapshot(core, scene) -> dict:
    live = core.composite_live()
    return {"live": {key: live[key] for key in LIVE_KEYS}, "state": scene.mode.state()}


def _graphics(harness, core, engine, app, api, packs, checks, facts, saved):
    import numpy as np
    from post_stage_check import _frame

    mb = harness._scenes()
    host = harness._host(core)

    def edge(label, before, after, **options):
        facts[label] = {"before": before, "after": after}
        checks.update({label + "_" + key: ok for key, ok in edge_checks(before, after, **options).items()})

    try:
        spec = harness.spec_for("box", packs, api)
        name, vertices_a, layout, _, _ = spec.meshes[0]
        vertices_b = deform(vertices_a, layout.stride)
        scene = harness.Scene(core, engine, host, spec)
        try:
            original = scene.pixels(app)
            before = _snapshot(core, scene)
            scene.mode.mesh(name, vertices_a, layout)
            same = scene.pixels(app)
            after = _snapshot(core, scene)
            edge("same_bytes", before, after, buffers=1)
            checks["same_bytes_pixels_exact"] = np.array_equal(original, same)
            before = after
            scene.mode.mesh(name, vertices_b, layout)
            changed = scene.pixels(app)
            after = _snapshot(core, scene)
            edge("changed_bytes", before, after, buffers=1)
            checks["fresh_buffer_changes_geometry"] = not np.array_equal(original, changed)
            rows_a, rows_b = mb.bars(0), mb.bars(7)
            half = mb.BARS // 2
            mixed = rows_b[:4 * half] + rows_a[4 * half:]
            pack = lambda rows: struct.pack(f"<{len(rows)}f", *rows)
            scene.pixels(app, bar_rows=pack(rows_a), bar_floats=4 * mb.BARS)
            before = _snapshot(core, scene)
            scene.mode.mesh(name, vertices_b, layout)
            partial = scene.pixels(app, bar_rows=pack(rows_b), bar_floats=4 * half)
            edge("storage_tail", before, _snapshot(core, scene), buffers=1)
            saved.update(old_geometry=original, changed_geometry=changed, partial_after_replace=partial)
            scene.pixels(app, bar_rows=pack(rows_a), bar_floats=4 * mb.BARS)
            padded, padded_layout = pad_layout(vertices_b, layout)
            before = _snapshot(core, scene)
            scene.mode.mesh(name, padded, padded_layout)
            repacked = scene.pixels(app)
            edge("changed_vertex_layout", before, _snapshot(core, scene), rebuild=True)
            checks["changed_layout_pixels_still_correct"] = np.array_equal(changed, repacked)
            scene.mode.remove_mesh(name)
            scene.pixels(app)  # request completes, but this old scene attachment is not the final presented surface
            state = scene.mode.state()
            facts["removed"] = state
            checks["removed_mesh_names_loss_and_draws_nothing"] = (
                name in str(state.get("last_reason")) and not np.any(_frame(host, scene.card)[..., :3]))
            scene.mode.mesh(name, vertices_b, layout)
            checks["readd_recovers_new_geometry"] = np.array_equal(changed, scene.pixels(app))
        finally:
            harness._close(scene, host, app)

        def fresh(label, mesh, rows):
            fresh_spec = replace(spec, meshes=((name, mesh, layout, None, None),),
                                 record=dict(spec.record, bar_rows=pack(rows), bar_floats=4 * mb.BARS))
            scene = harness.Scene(core, engine, host, fresh_spec)
            try:
                saved[label] = scene.pixels(app)
                return saved[label]
            finally:
                harness._close(scene, host, app)

        expected_b = fresh("fresh_geometry_b", vertices_b, rows_a)
        expected_mix = fresh("fresh_expected_tail", vertices_b, mixed)
        wrong_b = fresh("control_uploaded_full_b", vertices_b, rows_b)
        wrong_geometry = fresh("control_old_geometry", vertices_a, mixed)
        checks["retarget_pixels_equal_fresh_geometry"] = np.array_equal(changed, expected_b)
        checks["unwritten_storage_tail_matches_composite"] = np.array_equal(partial, expected_mix)
        checks["tail_control_full_b_differs"] = not np.array_equal(expected_mix, wrong_b)
        checks["tail_control_old_geometry_differs"] = not np.array_equal(expected_mix, wrong_geometry)

        voxel = harness.spec_for("voxels", packs, api)
        vn, vv, vl, vi, vil = voxel.meshes[0]
        moved = bytearray(vi)
        for offset in range(0, len(moved), vil.stride):
            x = struct.unpack_from("<f", moved, offset)[0]
            struct.pack_into("<f", moved, offset, x + 9.25)
        moved = bytes(moved)
        scene = harness.Scene(core, engine, host, voxel)
        try:
            old_voxels = scene.pixels(app)
            before = _snapshot(core, scene)
            scene.mode.mesh(vn, vv, vl, instances=moved, instance_layout=vil)
            new_voxels = scene.pixels(app)
            after = _snapshot(core, scene)
            edge("changed_instance_bytes", before, after, buffers=2)
            checks["new_instance_buffer_changes_pixels"] = not np.array_equal(old_voxels, new_voxels)
            padded_i, new_il = pad_layout(moved, vil)
            scene.mode.mesh(vn, vv, vl, instances=padded_i, instance_layout=new_il)
            repacked_i = scene.pixels(app)
            edge("changed_instance_layout", after, _snapshot(core, scene), rebuild=True)
            checks["changed_instance_layout_pixels_correct"] = np.array_equal(new_voxels, repacked_i)
        finally:
            harness._close(scene, host, app)

        scene = harness.Scene(core, engine, host, spec, meshes=False)
        try:
            scene.pixels(app)
            checks["fresh_content_missing_mesh_fails_closed"] = (
                name in str(scene.mode.state().get("last_reason")) and not np.any(_frame(host, scene.card)[..., :3]))
            scene.mode.mesh(name, vertices_b, layout)
            checks["fresh_content_resend_recovers"] = np.array_equal(scene.pixels(app), expected_b)
        finally:
            harness._close(scene, host, app)
    finally:
        host.close()
        harness.host_check._flush_deletes(app)
    return spec, name, vertices_b, layout, expected_b


def _generation(harness, core, engine, app, spec, name, vertices, layout, expected, checks, facts):
    import numpy as np
    from post_stage_check import _frame

    # Preserve the GUI/source owner across real scene-graph retirement and a new hidden host/device. Its uploaded
    # image was consumed; the new content must report loss until a resend, never hold the old QRhi pointers.
    old_host = harness._host(core)
    new_host = None
    scene = harness.Scene(core, engine, old_host, spec)
    try:
        scene.pixels(app)
        old_host.invalidate_scene_graph()
        old_host.set_content(None)
        facts["old_generation_closed"] = old_host.close()
        harness.host_check._flush_deletes(app)
        new_host = harness._host(core)
        scene.host = new_host
        new_host.set_content(scene.root)
        scene.pixels(app)
        facts["new_generation_waiting"] = scene.mode.state()
        checks["new_generation_requires_mesh_resend"] = (
            name in str(scene.mode.state().get("last_reason")) and not np.any(_frame(new_host, scene.card)[..., :3]))
        scene.mode.mesh(name, vertices, layout)
        checks["new_generation_resend_draws_fresh_buffer"] = np.array_equal(scene.pixels(app), expected)
    finally:
        if new_host is not None:
            harness._close(scene, new_host, app)
            new_host.close()
        else:
            # Invalidated hosts refuse frames; use the existing scene/GUI cleanup without its post-close frames.
            scene.stream.close()
            scene.mode.composite.destroy()
            if not old_host.closed:
                old_host.set_content(None)
                old_host.close()
            harness.host_check._drop_item(app, scene.root)
        harness.host_check._flush_deletes(app)


def _compute(harness, core, engine, app, packs, checks, facts):
    import numpy as np
    import compute_pass_check as compute
    from rendering.native.mode import MeshAttribute, RecordLayout

    mb = harness._scenes()
    spec = mb.retarget_compute_scene(packs)
    layout = RecordLayout(16, (MeshAttribute("aValue", 4, 0),))
    data = struct.pack(f"<{4 * mb.RETARGET_ROWS}f", *([0.25] * (4 * mb.RETARGET_ROWS)))
    replacement = struct.pack(f"<{4 * mb.RETARGET_ROWS}f", *([0.75] * (4 * mb.RETARGET_ROWS)))

    def result(scene):
        return np.frombuffer(scene.storage(app)["result"][3], dtype="<f4").reshape(mb.RETARGET_ROWS, 4).copy()

    host = harness._host(core)
    try:
        scene = compute.Scene(core, engine, host, spec)
        try:
            scene.mode.mesh("source_mesh", data, layout, storage=True)
            scene.draw(2)
            first = result(scene)
            before = _snapshot(core, scene)
            scene.mode.mesh("source_mesh", replacement, layout, storage=True)
            scene.draw(2, u_frame=1.0)
            second = result(scene)
            after = _snapshot(core, scene)
            checks["compute_control_reads_original_mesh"] = bool(np.all(first[:, :3] == 0.25))
            checks["compute_retarget_reads_fresh_mesh"] = bool(np.all(second[:, :3] == 0.75))
            checks["compute_retarget_dispatched_new_record"] = bool(np.all(second[:, 3] == 1.0))
            checks["compute_retarget_publishes_one_rebind"] = (after["state"]["texture_jobs"]["rebinds"]
                                                               - before["state"]["texture_jobs"]["rebinds"] == 1)
            checks.update({"compute_retarget_" + key: ok for key, ok in edge_checks(before, after, buffers=1).items()})
            facts["compute_retarget"] = {"first_record": first[0].tolist(), "second_record": second[0].tolist(),
                                         "before": before, "after": after}
            for edge in ("nonstorage", "removed"):
                if edge == "nonstorage":
                    scene.mode.mesh("source_mesh", replacement, layout, storage=False)
                else:
                    scene.mode.remove_mesh("source_mesh")
                before_dispatch = core.composite_live()["compute_dispatches"]
                scene.draw(2, u_frame=1.0)
                state = scene.mode.state()
                after_dispatch = core.composite_live()["compute_dispatches"]
                checks[edge + "_no_dispatch"] = before_dispatch == after_dispatch
                reason = str(state.get("last_reason"))
                checks[edge + "_named_refusal"] = "source_mesh" in reason and (
                    "storage" in reason if edge == "nonstorage" else "lost" in reason)
                facts[edge] = {"dispatch_before": before_dispatch, "dispatch_after": after_dispatch, "state": state}
                scene.mode.mesh("source_mesh", replacement, layout, storage=True)
                scene.draw(2, u_frame=2.0)
                recovered = result(scene)
                checks[edge + "_recovery_exact"] = bool(np.all(recovered[:, :3] == 0.75)
                                                         and np.all(recovered[:, 3] == 2.0))
                facts[edge]["recovered_first"] = recovered[0].tolist()
        finally:
            harness._close(scene, host, app)

        spec = mb.retarget_compute_scene(packs, texture=True)
        scene = compute.Scene(core, engine, host, spec)
        try:
            scene.mode.mesh("source_mesh", data, layout, storage=True)
            scene.mode.texture("probe_texture", bytes((0, 0, 0, 255)) * 4, (2, 2), in_frame=True)
            scene.draw(2)
            first = result(scene)
            checks["combined_initial_exact"] = bool(np.all(first[:, :3] == 0.25) and np.all(first[:, 3] == 0.0))
            before = _snapshot(core, scene)
            scene.mode.mesh("source_mesh", replacement, layout, storage=True)
            # A same-size pixel upload reuses its texture object. Resizing forces an actual object edge.
            scene.mode.texture("probe_texture", bytes((255, 0, 0, 255)) * 16, (4, 4), in_frame=True)
            scene.draw(2, u_frame=3.0)
            second = result(scene)
            after = _snapshot(core, scene)
            checks["combined_new_mesh_and_texture_exact"] = bool(np.all(second[:, :3] == 1.75)
                                                                  and np.all(second[:, 3] == 3.0))
            checks.update({"combined_" + key: ok for key, ok in edge_checks(before, after, buffers=1).items()})
            checks["combined_one_rebind"] = (after["state"]["texture_jobs"]["rebinds"]
                                               - before["state"]["texture_jobs"]["rebinds"] == 1)
            sizes = [next(t["size"] for t in snapshot["state"]["textures"] if t["name"] == "probe_texture")
                     for snapshot in (before, after)]
            checks["combined_texture_size_really_changed"] = sizes == [[2, 2], [4, 4]]
            facts["combined"] = {"first": first[0].tolist(), "second": second[0].tolist(),
                                 "before": before, "after": after,
                                 "reported_texture_sizes": sizes}
        finally:
            harness._close(scene, host, app)
    finally:
        host.close()
        harness.host_check._flush_deletes(app)


def round_retarget(harness, core, engine, app, api: str, packs: dict, out) -> dict:
    """Called only by mesh_buffer_check's API child; its validation, verdict and retirement gates cover this round."""
    from PIL import Image

    checks, facts, saved = {}, {}, {}
    inputs = _graphics(harness, core, engine, app, api, packs, checks, facts, saved)
    _generation(harness, core, engine, app, *inputs, checks, facts)
    _compute(harness, core, engine, app, packs, checks, facts)
    for name, pixels in saved.items():
        Image.fromarray(pixels, "RGBA").save(out / f"retarget_{api}_{name}.png")
    return {"pass": bool(checks) and all(checks.values()), "checks": checks, "facts": facts,
            "not_verified": ["physical driver/device fault recovery"]}
