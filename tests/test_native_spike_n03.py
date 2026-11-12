"""N0.3's convention scenes (native/spike_p1: src/n03_scenes.cpp, shaders/n03_*, python/run_n03.py), the parts that
need no GPU module: the shaders bake for every target with the production include spliced in, the include copy the
harness bakes is the production text, the build lists every scene shader, and the analysis tells a right image from a
wrong one (the scenes' checks are not vacuous).
"""
from __future__ import annotations

import base64
import re
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
SPIKE = ROOT / "native" / "spike_p1"
sys.path.insert(0, str(SPIKE / "python"))

import run_n03 as n03  # noqa: E402

SHADERS = SPIKE / "shaders"


def _composed(name: str) -> str:
    """cmake/compose_shader.cmake's splice, in Python."""
    text = (SHADERS / name).read_text(encoding="utf-8")
    text = text.replace("//@srpss_conventions", (SHADERS / "srpss_conventions.glsl").read_text(encoding="utf-8"))
    return text.replace("//@n03_common", (SHADERS / "n03_common.glsl").read_text(encoding="utf-8"))


def _scene_shaders() -> list[str]:
    return sorted(p.name for p in SHADERS.iterdir() if p.name.startswith("n03_") and p.suffix in (".vert", ".frag"))


def test_the_harness_bakes_the_production_include():
    from rendering.gl_programs.conventions import SRPSS_CONVENTIONS_GLSL

    assert (SHADERS / "srpss_conventions.glsl").read_text(encoding="utf-8") == SRPSS_CONVENTIONS_GLSL


def test_the_build_lists_every_scene_shader():
    cmake = (SPIKE / "CMakeLists.txt").read_text(encoding="utf-8")
    listed = re.search(r"set\(_n03_shaders([^)]*)\)", cmake)
    assert listed is not None
    assert sorted(listed.group(1).split()) == _scene_shaders()


def test_every_scene_shader_bakes_for_spirv_hlsl_and_glsl(tmp_path):
    from tools.vulkan_shader_readiness import _qsb, compile_source

    qsb = _qsb()
    if not qsb.exists():
        pytest.skip("this PySide6 has no qsb")
    targets = ("--glsl", "430,330,150", "--hlsl", "50")   # CMakeLists.txt's N0.3 targets
    for name in _scene_shaders():
        source = _composed(name)
        assert "//@" not in source, name
        assert compile_source(qsb, source, tmp_path / name, targets) == (True, ""), name


def test_the_probe_oracle_is_std140():
    # Rule 5: a scalar fills a vec3's padding, a vec3 array and a mat3 (as three columns) stride 16, size rounds to 16.
    assert n03.PROBE_ORACLE.offsets == (0, 12, 16, 64, 112)
    assert n03.PROBE_ORACLE.size == 128


def test_qsbs_reflection_of_the_probe_matches_the_oracle_and_a_tight_layout_does_not(tmp_path):
    """The reflection the module packs from (qsb's, the one QShader carries) against the std140 oracle; the hand
    layout (vec3 rule ignored) is refused, so the comparison is not vacuous."""
    import json
    import subprocess

    from tools.vulkan_shader_readiness import _qsb, compile_source

    qsb = _qsb()
    if not qsb.exists():
        pytest.skip("this PySide6 has no qsb")
    source = tmp_path / "n03_block.frag"
    assert compile_source(qsb, _composed("n03_block.frag"), source, ("--glsl", "430", "--hlsl", "50")) == (True, "")
    dump = subprocess.run([str(qsb), "-d", str(source) + ".qsb"], capture_output=True, text=True, timeout=120).stdout
    description, _end = json.JSONDecoder().raw_decode(dump[dump.index("Reflection info:") + len("Reflection info:"):]
                                                      .lstrip())
    block = next(b for b in description["uniformBlocks"] if b["blockName"] == "Probe")
    reflection = {"size": block["size"],
                  "members": [{"name": m["name"], "offset": m["offset"], "size": m["size"],
                               "array_dims": m.get("arrayDims", []), "array_stride": m.get("arrayStride", 0),
                               "matrix_stride": m.get("matrixStride", 0)} for m in block["members"]]}
    assert n03.probe_layout_matches_oracle(reflection)
    tight = {"size": 92, "members": [
        {"name": "a", "offset": 0, "size": 12, "array_dims": [], "array_stride": 0, "matrix_stride": 0},
        {"name": "f0", "offset": 12, "size": 4, "array_dims": [], "array_stride": 0, "matrix_stride": 0},
        {"name": "arr", "offset": 16, "size": 36, "array_dims": [3], "array_stride": 12, "matrix_stride": 0},
        {"name": "m", "offset": 52, "size": 36, "array_dims": [], "array_stride": 0, "matrix_stride": 12},
        {"name": "tail", "offset": 88, "size": 4, "array_dims": [], "array_stride": 0, "matrix_stride": 0}]}
    assert not n03.probe_layout_matches_oracle(tight)


def test_scene_geometry_states_what_the_checks_assume():
    # Scene 3: authored front is counter-clockwise in OpenGL NDC through Quick's matrix, back is clockwise; the
    # up-facing matrix turns both.
    for matrix, front_sign in ((n03.QUICK_MATRIX, 1.0), (n03.UP_MATRIX, -1.0)):
        areas = {name: n03.signed_area([n03.ndc_of(matrix, x, y) for x, y in pts]) for name, pts, _c in n03.TRIANGLES}
        assert np.sign(areas["front"]) == front_sign and np.sign(areas["back"]) == -front_sign
    # Scene 2: every band edge is a pixel boundary; the planes meant to be clipped fall outside [0, 1], the rest inside.
    for name, (x0, x1, y0, y1), z, _colour in n03.PLANES:
        for value, size in ((x0, n03.WIDTH), (x1, n03.WIDTH)):
            assert ((value + 1.0) * 0.5 * size) == pytest.approx(round((value + 1.0) * 0.5 * size), abs=1e-9)
        for value in (y0, y1):
            assert ((1.0 - value) * 0.5 * n03.HEIGHT) == pytest.approx(round((1.0 - value) * 0.5 * n03.HEIGHT),
                                                                       abs=1e-9)
        d = n03.window_depth(z)
        assert (0.0 <= d <= 1.0) is (not name.endswith("_out")), name


def test_the_handedness_switch_mirrors_the_expected_image():
    culled_q, _f, edge_q = n03.expected_cull_scene(n03.QUICK_MATRIX)
    culled_u, _f, edge_u = n03.expected_cull_scene(n03.UP_MATRIX)
    keep = ~(edge_q | edge_u[::-1])
    assert culled_q[keep].any()
    assert np.array_equal(culled_q[keep], culled_u[::-1][keep])


def _entry(array: np.ndarray) -> dict:
    array = np.ascontiguousarray(array)
    fmt = "rgba8" if array.dtype == np.uint8 else "rgba32f"
    return {"w": array.shape[1], "h": array.shape[0], "format": fmt,
            "b64": base64.b64encode(array.astype(np.uint8 if fmt == "rgba8" else np.float32).tobytes()).decode()}


def _quantised_decode(values: np.ndarray) -> np.ndarray:
    """The exact decode kept to 8 significant bits, as the hardware returned it on Vulkan and D3D in run 1."""
    exact = n03.srgb_decode(values)
    step = 2.0 ** (np.floor(np.log2(np.maximum(exact, 1e-12))) - 7)
    return np.where(exact > 0, np.round(exact / step) * step, 0.0)


def _checker_run(facts: dict, *, mirrored: bool = False, hardware: str = "quantised", shader: str = "exact",
                 block_flip: bool | None = None) -> dict:
    """What a backend reads back under the decided convention (the clip NDC per its facts). ``block_flip`` is the
    clip-NDC flip the module wrote into the block (default: the backend's decided value); ``hardware`` the sampler's
    decode of the flagged strip, ``shader`` srgbToLinear's."""
    content = n03.checker_content()
    y, x = np.mgrid[0:n03.HEIGHT, 0:n03.WIDTH]
    ux, uy = (x + 0.5) / n03.WIDTH, (y + 0.5) / n03.HEIGHT
    flip = n03.ndc_y_flip(facts)
    block_flip = flip if block_flip is None else block_flip
    post_y = (1.0 - 2.0 * uy) if flip else (2.0 * uy - 1.0)
    post = np.stack([2.0 * ux - 1.0, post_y], -1)
    view = np.stack([2.0 * ux - 1.0, 1.0 - 2.0 * uy], -1)
    sign = -1.0 if block_flip else 1.0
    ndc_to_uv = np.stack([post[..., 0] * 0.5 + 0.5, sign * post[..., 1] * 0.5 + 0.5], -1)
    uv_to_ndc = np.stack([2 * ux - 1, sign * (2 * uy - 1)], -1)
    one = np.ones_like(ux)
    v = n03.strip_values()
    written = content[::-1] if mirrored else content
    decodes = {"exact": n03.srgb_decode(v), "raw": v / 255.0, "quantised": _quantised_decode(v),
               "shifted": n03.srgb_decode(np.clip(v.astype(int) + 1, 0, 255))}
    readbacks = {
        "written": written, "fetch": written, "sample": written, "upload_fetch": content, "uploaded_raw": content,
        "strip": np.stack([decodes[hardware], v / 255.0, decodes[shader], one], -1),
        "pixel": np.stack([x + 0.5, y + 0.5, x, y], -1),
        "uv": np.concatenate([np.stack([ux, uy], -1), ndc_to_uv], -1),
        "raw": np.stack([x + 0.5, y + 0.5, x + 0.5, y + 0.5], -1),
        "ndc": np.concatenate([post, view], -1),
        "mapping": np.concatenate([uv_to_ndc, view * 0.5 + 0.5], -1),
        "probe": n03.probe_expected(),
    }
    return {"name": "checker_target", "scene": "checker", "ok": True, "double_correction_refused": True,
            "ndc_flip": 1.0 if block_flip else 0.0,
            "readbacks": {k: _entry(a if a.dtype == np.uint8 else a.astype(np.float32)) for k, a in readbacks.items()}}


VULKAN_FACTS = {"is_y_up_in_ndc": False, "is_y_up_in_framebuffer": False}
D3D_FACTS = {"is_y_up_in_ndc": True, "is_y_up_in_framebuffer": False}


def test_the_checker_analysis_passes_the_convention_and_fails_mirrored_rows():
    good = n03.analyse_checker(_checker_run(VULKAN_FACTS), VULKAN_FACTS)
    assert all(good["checks"].values()), good["checks"]
    bad = n03.analyse_checker(_checker_run(VULKAN_FACTS, mirrored=True), VULKAN_FACTS)
    assert bad["checks"]["texel_origin_top_left"] is False
    assert bad["checks"]["frag_texel_matches_writer"] is False


def test_with_the_decided_clip_ndc_flip_d3d_agrees_and_without_it_disagrees():
    # Decided F2: on a Y-up NDC with top-down rows (D3D11, D3D12) the block's y negates the clip NDC's Y.
    decided = n03.analyse_checker(_checker_run(D3D_FACTS), D3D_FACTS)
    assert all(decided["checks"].values()), decided["checks"]
    # Run 1's production include (y never read): the writer's row mirrored, the negative control's failure.
    unflipped = n03.analyse_checker(_checker_run(D3D_FACTS, block_flip=False), D3D_FACTS)
    assert unflipped["checks"]["ndc_to_uv_agrees_with_writer"] is False
    assert unflipped["checks"]["uv_to_ndc_agrees_with_clip_ndc"] is False
    assert unflipped["checks"]["ndc_flip_is_the_backends"] is False
    # The same flip on Vulkan, where the backend's value is 0, breaks it there.
    wrong = n03.analyse_checker(_checker_run(VULKAN_FACTS, block_flip=True), VULKAN_FACTS)
    assert wrong["checks"]["ndc_to_uv_agrees_with_writer"] is False


def test_the_srgb_check_gates_the_shaders_decode_and_records_the_samplers():
    # Decided F4: srgbToLinear's decode is the exact curve on every backend; the sampler's decode is a record only.
    result = n03.analyse_checker(_checker_run(VULKAN_FACTS, hardware="raw"), VULKAN_FACTS)
    assert result["checks"]["srgb_shader_decode_matches_analytic"] is True
    assert result["info"]["srgb_flag_live"] is False          # Qt defect E on OpenGL: recorded, not gating
    # No decode in the shader, or one a byte off: refused.
    for shader in ("raw", "shifted"):
        bad = n03.analyse_checker(_checker_run(VULKAN_FACTS, shader=shader), VULKAN_FACTS)
        assert bad["checks"]["srgb_shader_decode_matches_analytic"] is False, shader
    # The hardware's 8-significant-bit decode (run 1: 0.00375 at byte 251) keeps every byte; a shifted one does not.
    kept = n03.analyse_checker(_checker_run(VULKAN_FACTS, hardware="quantised"), VULKAN_FACTS)
    assert kept["measures"]["srgb_identifies_its_byte"] is True
    assert kept["measures"]["srgb_max_error_vs_analytic"] > 1.0e-3
    v = n03.strip_values()
    shifted = n03.srgb_decode(np.clip(v.astype(int) + 1, 0, 255))
    assert n03.srgb_decode_measures(shifted, v)["srgb_identifies_its_byte"] is False


def test_the_cull_analysis_fails_the_wrong_triangle():
    culled, facing, _edge = n03.expected_cull_scene(n03.QUICK_MATRIX)
    alpha = np.full(culled.shape[:2] + (1,), 255, np.uint8)
    run = {"name": "cull_quick_rule", "scene": "cull", "ok": True, "front_face_mode": "fixed",
           "pipelines_prebuilt": ["ccw", "cw"],
           "readbacks": {"culled": _entry(np.concatenate([culled, alpha], -1)),
                         "facing": _entry(np.concatenate([facing, alpha], -1))}}
    assert all(n03.analyse_cull(run, VULKAN_FACTS, n03.QUICK_MATRIX)["checks"].values())
    wrong = np.zeros_like(culled)   # the authored-back triangle kept, the front one culled
    wrong[np.all(facing == (0, 0, 255), axis=-1)] = (0, 255, 0)
    run["readbacks"]["culled"] = _entry(np.concatenate([wrong, alpha], -1))
    assert n03.analyse_cull(run, VULKAN_FACTS, n03.QUICK_MATRIX)["checks"]["kept_triangle"] is False


def test_the_depth_analysis_reads_the_window_depth():
    colour, depth, _label = n03.expected_depth_scene()
    alpha = np.full(colour.shape[:2] + (1,), 255, np.uint8)
    d = depth.astype(np.float32)[..., None]
    run = {"name": "depth_target", "scene": "depth", "ok": True, "double_correction_refused": True,
           "readbacks": {"colour": _entry(np.concatenate([colour, alpha], -1)),
                         "depth": _entry(np.concatenate([d, d, 0 * d, 0 * d + 1], -1))}}
    assert all(n03.analyse_depth(run)["checks"].values())
    ndc_depth = (2.0 * depth - 1.0).astype(np.float32)[..., None]   # the depth part of the correction skipped
    run["readbacks"]["depth"] = _entry(np.concatenate([ndc_depth, ndc_depth, 0 * d, 0 * d + 1], -1))
    assert n03.analyse_depth(run)["checks"]["window_depth_analytic"] is False
