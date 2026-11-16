"""Optional mesh-buffer unsigned-vector upload proof; no CLI, graphics, validation or lifecycle owner."""
from __future__ import annotations


WIDTHS = (("u_words2", 2), ("u_words3", 3), ("u_words4", 4))
SIZE = (2 * sum(width for _name, width in WIDTHS), 4)
# Synthetic transport values cover zero, bit31, all bits, and low/high16 transitions; no authored setting is pinned.
VALUES = {"u_words2": (0, 0xffffffff), "u_words3": (0x7fffffff, 0x80000000, 0x80000001),
          "u_words4": (0x0000ffff, 0x00010000, 0x89abcdef, 0xfedcba98)}


def _schema():
    """Build the real layout the round binds; native admission validates canonical field names."""
    import mesh_buffers

    return mesh_buffers.schema("uniform_vectors", tuple((name, "u32", width) for name, width in WIDTHS), code=250)


def expected(record):
    """Exact float32 halves of every component, repeated in every row independently of native block bytes."""
    import numpy as np

    scalars = []
    for name, width in WIDTHS:
        words = record[name]
        if len(words) != width or any(not isinstance(word, int) or not 0 <= word <= 0xffffffff for word in words):
            raise ValueError(f"{name} must contain {width} full-range u32 components")
        scalars.extend(half for word in words for half in (word & 0xffff, word >> 16))
    return np.tile(np.asarray(scalars, dtype=np.float32), (SIZE[1], 1))


def pixel_checks(image, record):
    """A missing component, wrong shape, nonfinite value or stale upload cannot satisfy this predicate."""
    import numpy as np

    wanted = expected(record)
    image = np.asarray(image)
    shape = image.shape == wanted.shape
    dtype = image.dtype == np.dtype(np.float32)
    usable = shape and dtype
    return {"shape": shape, "float32": dtype, "finite": bool(np.isfinite(image).all()) if usable else False,
            "all_rows_identical": bool((image == image[0]).all()) if usable else False,
            "exact_components": bool(np.array_equal(image.view(np.uint32), wanted.view(np.uint32))) if usable else False}


def _readback(scene, record):
    """Use the existing bounded target-readback owner; Scene.pixels intentionally handles RGBA8 only."""
    import numpy as np
    from scene_target_check import _metadata_readback

    scene.publish(**record)
    entries = _metadata_readback(scene)
    selected = [entry for entry in entries if entry["name"] == "scene.colour" and entry.get("level", 0) == 0]
    if len(selected) != 1:
        raise RuntimeError("uniform vectors require exactly one scene.colour base-level readback")
    entry = selected[0]
    width, height = entry["size"]
    cw, ch = entry["content"]
    if entry["format"] != "r32f" or (cw, ch) != SIZE or not (width >= cw and height >= ch):
        raise RuntimeError("uniform-vector readback has unexpected R32F size/content metadata")
    if len(entry["data"]) != width * height * 4:
        raise RuntimeError("uniform-vector R32F readback byte count is incomplete")
    return np.frombuffer(entry["data"], dtype="<f4").reshape(height, width)[height-ch:, :cw].copy()


def round_uniform_vectors(harness, core, engine, app, api, packs, out):
    """Read every uvec2/3/4 component after baseline, each last-component mutation, and exact restore."""
    import numpy as np
    from rendering.native.mode import ModePass, ModeTarget, TargetAttachment

    mb = harness._scenes()
    schema = _schema()
    spec = mb.SceneSpec("uniform_vectors", (ModePass("vectors", packs["uniform_vectors.frag"], "replace", target="scene"),),
                        (ModeTarget("scene", (TargetAttachment("colour", "r32f"),), size=SIZE),), (), {}, schema, VALUES)
    host = harness._host(core, card=SIZE)
    scene = None
    checks, facts, arrays = {}, {}, {}
    before = core.composite_live()
    try:
        scene = harness.Scene(core, engine, host, spec, card=SIZE, meshes=False)
        phases = [("baseline", dict(VALUES))]
        for name, _width in WIDTHS:
            changed = dict(VALUES)
            words = list(changed[name])
            words[-1] ^= 0x80000001
            changed[name] = tuple(words)
            phases.append((name + "_last_component", changed))
        phases.append(("restored", dict(VALUES)))
        for label, record in phases:
            image = _readback(scene, record)
            arrays[label] = image
            checks.update({label + "_" + key: value for key, value in pixel_checks(image, record).items()})
            wanted = expected(record)
            facts[label] = {"record": record, "mismatched_columns": np.flatnonzero(np.any(image != wanted, axis=0)).tolist()}
            if label not in ("baseline", "restored"):
                checks[label + "_rejects_baseline_oracle"] = not all(pixel_checks(image, VALUES).values())
        checks["restore_exact"] = np.array_equal(arrays["baseline"], arrays["restored"])
        state, live = scene.mode.state(), core.composite_live()
        targets = {target["name"]: target for target in state.get("scene_targets", {}).get("targets", ())}
        checks["target_ready"] = bool(targets.get("scene", {}).get("ready"))
        checks["records_accepted"] = state.get("records", 0) >= len(phases)
        checks["no_refusal"] = not state.get("last_refusal") and not state.get("content_failing")
        checks["no_draw_refusal"] = live["mesh_buffers_draws_refused"] == before["mesh_buffers_draws_refused"]
        checks["readbacks_complete"] = not state.get("target_readback_pending") and live["scene_target_readbacks"] == 0
        facts["state"] = state
    finally:
        try:
            if scene is not None:
                harness._close(scene, host, app)
        finally:
            host.close()
            harness.host_check._flush_deletes(app)
    live = core.composite_live()
    keys = ("items", "mode_sources", "mode_resources", "scene_targets", "scene_target_textures", "scene_target_bytes",
            "scene_target_readbacks", "mesh_buffers_streams", "mesh_buffers_arenas", "mesh_buffers_arena_bytes")
    checks["retired_to_zero"] = all(live.get(key) == 0 for key in keys)
    facts["retired"] = {key: live.get(key) for key in keys}
    np.savez_compressed(out / f"uniform_vectors_{api}.npz", **arrays)
    return {"pass": all(checks.values()), "checks": checks, "facts": facts}
