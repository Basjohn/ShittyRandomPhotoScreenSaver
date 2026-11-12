"""What the frame driver's probe pass must read back (native/core/src/probe_pass.h), and the checks (N2.2).

The pass draws, through an OpenGL-form item matrix (item pixels, y down) that the core corrected once at upload, a
background quad coloured with what the conventions include says about each fragment (fragUv in r and g, ndcToUv of the
clip NDC in b and a) and two triangles with back-face culling (the left one front-facing, the right one back-facing).
The target is read back raw, row 0 first, never flipped (N0.3 rule 2). Under the decided conventions (F1 to F3) the
item pixel (x, y) is the memory texel (x, y) on every backend, so the analytical image is the same everywhere:

- background texel (x, y): ((x + .5) / W, (y + .5) / H) in r and g, the same in b and a (8-bit, round to nearest);
- the front triangle's interior in its colour, at the rows it was authored at (the top of the image);
- the back triangle's interior culled (background).

Checks on the facts the module reports: the matrix was corrected exactly once and is ``clipSpaceCorrMatrix() x the Y
flip where the framebuffer is Y-up`` (F1) times the OpenGL form; the front face the C++ rule chose on the uploaded matrix
equals the production Python rule (``rendering.gl_programs.conventions.front_face_clockwise``) and the decision (counter-
clockwise on Vulkan and D3D, clockwise on the core's OpenGL: F3); the conventions block is (0, the F2 flip, 0, 0).

A negative control changes the correction, the front face or a block value: it must fail an image check wherever it
changes what the rasterizer gets (the matrix's x, y and w rows, the front face or the block), and is vacuous (passes,
recorded as such) only where it changes none of them, as N0.3's controls are.
"""
from __future__ import annotations

from typing import Any, Mapping

import numpy as np

EDGE_MARGIN_PX = 1.0     # pixels this close to a triangle edge are coverage-dependent and not compared
TOLERANCE_U8 = 1         # an exact value written to UNORM8 rounds to the nearest step
IMAGE_CHECKS = ("background_frag_uv", "ndc_to_uv_agrees_with_frag_uv", "front_triangle_kept_where_authored",
                "back_triangle_culled", "not_mirrored")


def matrix(values) -> np.ndarray:
    """A 4x4 from the 16 column-major floats the module reports (std140 mat4 order)."""
    return np.asarray(values, dtype=np.float64).reshape(4, 4).T


def _triangle(facts: Mapping[str, Any], key: str) -> np.ndarray:
    return np.asarray(facts[key], dtype=np.float64).reshape(3, 2)


def _edge_distance(px: np.ndarray, py: np.ndarray, tri: np.ndarray) -> np.ndarray:
    best = np.full(px.shape, np.inf)
    for i in range(3):
        a, b = tri[i], tri[(i + 1) % 3]
        d = b - a
        t = np.clip(((px - a[0]) * d[0] + (py - a[1]) * d[1]) / float(d @ d), 0.0, 1.0)
        best = np.minimum(best, np.hypot(px - (a[0] + t * d[0]), py - (a[1] + t * d[1])))
    return best


def _inside(px: np.ndarray, py: np.ndarray, tri: np.ndarray) -> np.ndarray:
    signs = []
    for i in range(3):
        a, b = tri[i], tri[(i + 1) % 3]
        signs.append((b[0] - a[0]) * (py - a[1]) - (b[1] - a[1]) * (px - a[0]))
    s = np.stack(signs)
    return np.all(s > 0, axis=0) | np.all(s < 0, axis=0)


def expected_image(facts: Mapping[str, Any]) -> dict:
    """The analytical image and its regions, from the module's own facts (size, triangles, colours)."""
    width, height = (int(v) for v in facts["size"])
    y, x = np.mgrid[0:height, 0:width]
    cx, cy = x + 0.5, y + 0.5
    u, v = cx / width, cy / height
    background = np.rint(np.stack([u, v, u, v], -1) * 255.0)
    front, back = _triangle(facts, "front_triangle"), _triangle(facts, "back_triangle")
    edge = (_edge_distance(cx, cy, front) <= EDGE_MARGIN_PX) | (_edge_distance(cx, cy, back) <= EDGE_MARGIN_PX)
    front_in = _inside(cx, cy, front) & ~edge
    back_in = _inside(cx, cy, back) & ~edge
    image = background.copy()
    image[front_in] = np.rint(np.asarray(facts["front_colour"], dtype=np.float64) * 255.0)
    return {"image": image.astype(np.uint8), "background": background.astype(np.uint8), "front": front_in,
            "back": back_in, "edge": edge, "plain": ~(edge | front_in | back_in)}


def decode(rgba: bytes, width: int, height: int) -> np.ndarray:
    return np.frombuffer(rgba, dtype=np.uint8)[: width * height * 4].reshape(height, width, 4)


def _max_abs(a: np.ndarray, b: np.ndarray, mask: np.ndarray) -> int:
    if not mask.any():
        return -1
    return int(np.abs(a.astype(np.int16) - b.astype(np.int16))[mask].max())


def image_checks(facts: Mapping[str, Any], image: np.ndarray) -> tuple[dict, dict]:
    """The image against the analytical one: (checks, measures)."""
    exp = expected_image(facts)
    bg, plain = exp["background"], exp["plain"] | exp["back"]
    colour = np.rint(np.asarray(facts["front_colour"], dtype=np.float64) * 255.0).astype(np.int16)
    is_front_colour = np.all(np.abs(image.astype(np.int16) - colour) <= TOLERANCE_U8, axis=-1)
    measures = {
        "background_rg_max_abs": _max_abs(image[..., :2], bg[..., :2], exp["plain"]),
        "ndc_to_uv_vs_frag_uv_max_abs": _max_abs(image[..., 2:], image[..., :2], exp["plain"]),
        "front_max_abs": _max_abs(image, exp["image"], exp["front"]),
        "back_vs_background_max_abs": _max_abs(image, bg, exp["back"]),
        "front_colour_pixels_outside_front": int((is_front_colour & ~(exp["front"] | exp["edge"])).sum()),
        "front_pixels": int(exp["front"].sum()),
        "back_pixels": int(exp["back"].sum()),
    }
    checks = {
        "background_frag_uv": 0 <= measures["background_rg_max_abs"] <= TOLERANCE_U8,
        "ndc_to_uv_agrees_with_frag_uv": 0 <= measures["ndc_to_uv_vs_frag_uv_max_abs"] <= TOLERANCE_U8,
        "front_triangle_kept_where_authored": 0 <= measures["front_max_abs"] <= TOLERANCE_U8,
        "back_triangle_culled": 0 <= measures["back_vs_background_max_abs"] <= TOLERANCE_U8,
        "not_mirrored": measures["front_colour_pixels_outside_front"] == 0 and bool(plain.any()),
    }
    return checks, measures


def fact_checks(facts: Mapping[str, Any]) -> dict:
    """The module's conventions against the decisions and the production Python rule."""
    from rendering.gl_programs.conventions import front_face_clockwise

    ndc_up, fb_up = bool(facts["is_y_up_in_ndc"]), bool(facts["is_y_up_in_framebuffer"])
    flip = np.diag([1.0, -1.0 if fb_up else 1.0, 1.0, 1.0])
    correction = matrix(facts["target_correction"])
    rule_cw = facts.get("front_face_rule_on_uploaded") == "cw"
    return {
        "corrected_once": facts.get("corrected") is True and facts.get("double_correction_refused") is True,
        "correction_is_clip_corr_times_y_flip": bool(np.allclose(correction, matrix(facts["clip_space_corr"]) @ flip,
                                                                 atol=1e-7)),
        "uploaded_is_correction_times_gl_form": bool(np.allclose(matrix(facts["uploaded"]),
                                                                 correction @ matrix(facts["gl_form"]), atol=1e-6)),
        "front_face_rule_matches_python": front_face_clockwise(facts["uploaded"], ndc_y_up=ndc_up) == rule_cw,
        "front_face_matches_decision": rule_cw == fb_up,
        "front_face_used_is_the_rule": facts.get("front_face") == facts.get("front_face_rule_on_uploaded"),
        "conventions_block_decided": [float(v) for v in facts["conventions_block"]]
        == [0.0, 1.0 if (ndc_up and not fb_up) else 0.0, 0.0, 0.0],
    }


def analyse(readback: Mapping[str, Any]) -> dict:
    """One readback (``facts``, ``rgba``, ``width``, ``height``) under the decided conventions."""
    facts = readback["facts"]
    width, height = int(readback["width"]), int(readback["height"])
    size_ok = [width, height] == [int(v) for v in facts["size"]] and len(readback["rgba"]) >= width * height * 4
    if not size_ok:
        return {"checks": {"size_matches": False}, "measures": {}, "pass": False, "image_pass": False}
    image = decode(readback["rgba"], width, height)
    checks, measures = image_checks(facts, image)
    checks.update(fact_checks(facts))
    checks["size_matches"] = True
    return {"checks": checks, "measures": measures, "pass": all(checks.values()),
            "image_pass": all(checks[k] for k in IMAGE_CHECKS)}


def effective(facts: Mapping[str, Any]) -> tuple:
    """What the rasterizer gets from a configuration: the uploaded matrix's x, y and w rows, the front face, the block."""
    rows = matrix(facts["uploaded"])[[0, 1, 3]]
    return (tuple(np.round(rows, 6).ravel()), facts.get("front_face"),
            tuple(float(v) for v in facts["conventions_block"]))


def negative_verdict(default_facts: Mapping[str, Any], readback: Mapping[str, Any]) -> dict:
    """A negative control's run: it must fail an image check exactly where it changes what the rasterizer gets."""
    facts = readback["facts"]
    changes = effective(facts) != effective(default_facts)
    width, height = int(readback["width"]), int(readback["height"])
    checks, measures = image_checks(facts, decode(readback["rgba"], width, height))
    failed = not all(checks.values())
    return {"changes_anything": changes, "image_failed": failed, "ok": failed == changes,
            "status": ("fails, as it must" if failed else "PASSES although it changes the rasterizer's input")
            if changes else ("vacuous here (changes nothing), passes" if not failed else "FAILS although it changes "
                                                                                          "nothing"),
            "failed_checks": sorted(k for k, value in checks.items() if not value), "measures": measures}
