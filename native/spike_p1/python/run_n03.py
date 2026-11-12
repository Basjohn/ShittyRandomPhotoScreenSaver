"""N0.3 driver (Current_Plan.md item 8b; Docs/Future_Work/Native_Core_P3_Decisions.md, "The three test scenes").

The three convention scenes on every backend QRhi gives this machine: Vulkan on our own device (the N0.6 context,
validated when --layer-path gives the layer), OpenGL, D3D11 and D3D12. Harness only, nothing ships, no window, no
environment variable (apart from the layer path, as run_n06.py).

The module draws and reads back (src/n03_scenes.cpp); everything else is here: the geometry, the OpenGL-form matrices
(core/settings/framed_camera.perspective_matrix for the depth scene), the uploaded content, and every check against
the convention the lead decided: core-owned offscreen targets keep texel (0,0) top-left on every backend, a texture
written by one pass is read by the next with no per-pass flip, and every matrix is corrected once, at upload. Readbacks
are memory rows, row 0 first, never flipped.

Runs per backend (each a fresh set of targets in one offscreen frame):
  checker  scene 1: correction "target" (clipSpaceCorrMatrix and, on a Y-up framebuffer, a Y flip: OpenGL is the
           backend that flips), the include's flip 0. Recorded alternative "clip": clipSpaceCorrMatrix alone with the
           include's flip at isYUpInFramebuffer (the route conventions.py's docstring names). Negative controls: the
           include's flip inverted; no correction; the probe block packed by hand (ignoring std140's vec3 rule).
  depth    scene 2: the planes through framed_camera.perspective_matrix, corrected at upload, into D32F with LESS;
           negative controls: the depth part of the correction skipped; no correction.
  cull     scene 3: two triangles, back faces culled, the front face from rule 4 on the uploaded matrix, with Quick's
           Y-down item matrix and an up-facing one; negative controls: the front face fixed counter-clockwise; rule 4
           fed the uncorrected matrix.

Usage (repository venv, the module built on GitHub: tools/build_runner.py --mode github --run --select native_spike):
  python native/spike_p1/python/run_n03.py --module-dir release/native_spike --label n03_scenes
      [--backends vulkan opengl d3d11 d3d12] [--layer-path <folder with VkLayer_khronos_validation.json>]
      [--require-validation]
Evidence: .artifacts/evidence/native_core/n0_3/<date>_<label>/ (summary.json and one sheet per scene). Exit 0 whenever
the probe ran; the verdict is the last line ("N03 VERDICT ...").
"""

from __future__ import annotations

import argparse
import base64
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[2]
for _path in (HERE, REPO_ROOT):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

import numpy as np  # noqa: E402

from core.settings.framed_camera import perspective_matrix  # noqa: E402
from rendering.gl_programs.conventions import front_face_clockwise  # noqa: E402
from rendering.gl_programs.scene3d import Scene3DBlockLayout  # noqa: E402

BACKENDS = ("vulkan", "opengl", "d3d11", "d3d12")
REFERENCE_BACKEND = "opengl"   # "compared with both the analytical image and the OpenGL result"
WIDTH, HEIGHT = 96, 56         # non-square, so a width/height mix-up shows
CELL = 8
PROBE_SIZE = (8, 1)
# The P1 spike's measured backend difference on trivial content (D8 point 1): 0 to 3 of 255.
BACKEND_TOLERANCE_U8 = 3
DEPTH_TOLERANCE = 2.0e-6       # window depth, absolute (about 30 float32 steps just below 1.0)
COORD_TOLERANCE = 1.0e-5       # uv and NDC from the include
ITEM_TOLERANCE = 1.0e-3        # an interpolated item position, in pixels
SRGB_TOLERANCE = 1.0e-3        # the sRGB decode against IEC 61966-2-1
SRGB_BACKEND_TOLERANCE = 1.0e-4
EDGE_MARGIN_PX = 1.0           # scene 3: pixels this close to a triangle edge are not compared (fill rules)

IDENTITY = (1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0)
# Column-major, item pixels (y down) to OpenGL NDC (y up): Qt Quick's item matrix.
QUICK_MATRIX = (2.0 / WIDTH, 0.0, 0.0, 0.0, 0.0, -2.0 / HEIGHT, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, -1.0, 1.0, 0.0, 1.0)
# The up-facing one: the same item pixels, no Y flip (a mirrored item).
UP_MATRIX = (2.0 / WIDTH, 0.0, 0.0, 0.0, 0.0, 2.0 / HEIGHT, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, -1.0, -1.0, 0.0, 1.0)

# Scene 2's camera: framed_camera's projection (the one owner), 60 degrees vertical, the target's aspect.
NEAR, FAR = 0.5, 50.0
TAN_Y = math.tan(math.radians(30.0))
TAN = (TAN_Y * WIDTH / HEIGHT, TAN_Y)
# (name, (x0, x1, y0, y1) in view NDC, view z, colour), in draw order. Band edges fall on pixel boundaries.
PLANES = (
    ("A", (-1.0, 1.0 / 3.0, 0.5, 1.0), -5.0, (200, 0, 0)),           # band 1: the nearer B is drawn second
    ("B", (-1.0 / 3.0, 1.0, 0.5, 1.0), -3.0, (0, 200, 0)),
    ("B2", (-1.0 / 3.0, 1.0, 0.0, 0.5), -3.0, (0, 0, 200)),          # band 2: the nearer B2 is drawn first
    ("A2", (-1.0, 1.0 / 3.0, 0.0, 0.5), -5.0, (200, 200, 0)),
    ("E1L", (-1.0, 0.0, -0.5, 0.0), -4.0, (0, 200, 200)),            # band 3: LESS rejects an equal depth
    ("E1R", (0.0, 1.0, -0.5, 0.0), -4.0, (0, 200, 200)),
    ("E2R", (0.0, 1.0, -0.5, 0.0), -4.0, (200, 0, 200)),             # E1R's very triangles again
    ("far_in", (-1.0, -0.5, -1.0, -0.5), -FAR * 0.98, (100, 100, 100)),  # band 4: the clip planes
    ("far_out", (-0.5, 0.0, -1.0, -0.5), -FAR * 1.02, (255, 255, 255)),
    ("near_in", (0.0, 0.5, -1.0, -0.5), -NEAR * 1.02, (50, 150, 250)),
    ("near_out", (0.5, 1.0, -1.0, -0.5), -NEAR * 0.98, (250, 150, 50)),
)
# Scene 3: item pixels (y down). Through Quick's matrix the first is counter-clockwise in OpenGL NDC (authored front),
# the second its mirror (authored back).
TRIANGLES = (
    ("front", ((8.0, 8.0), (8.0, 48.0), (40.0, 28.0)), (1.0, 0.0, 0.0, 1.0)),
    ("back", ((88.0, 8.0), (88.0, 48.0), (56.0, 28.0)), (0.0, 1.0, 0.0, 1.0)),
)
PROBE_VALUES = {"a": [1.0, 2.0, 3.0], "f0": [4.0], "arr": [5.0, 6.0, 7.0, 8.0, 9.0, 10.0, 11.0, 12.0, 13.0],
                "m": [14.0, 15.0, 16.0, 17.0, 18.0, 19.0, 20.0, 21.0, 22.0], "tail": [23.0]}
# The std140 oracle (rule 5: the Python packer is what the C++ packer is first tested against). A mat3 is three vec4
# columns in std140, the very layout of a vec3[3]; Scene3DBlockLayout has no mat3 type, so it is stated that way.
PROBE_ORACLE = Scene3DBlockLayout.of("Probe", (("a", "vec3"), ("f0", "float"), ("arr", "vec3[3]"), ("m", "vec3[3]"),
                                              ("tail", "float")))


# ------------------------------------------------------------------------------------------------ content and geometry

def checker_content() -> np.ndarray:
    """Scene 1's content, (H, W, 4) uint8, row 0 the top: red 2x, green 4y, blue 255 or 64 by checker parity."""
    y, x = np.mgrid[0:HEIGHT, 0:WIDTH]
    blue = np.where(((x // CELL + y // CELL) & 1) == 1, 255, 64)
    return np.stack([2 * x, 4 * y, blue, np.full_like(x, 255)], axis=-1).astype(np.uint8)


def strip_values() -> np.ndarray:
    """The sRGB strip's bytes, (H, W) uint8: every value 0 to 255, row-major from the top."""
    y, x = np.mgrid[0:HEIGHT, 0:WIDTH]
    return ((x + y * WIDTH) % 256).astype(np.uint8)


def strip_rgba() -> np.ndarray:
    v = strip_values()
    return np.stack([v, v, v, np.full_like(v, 255)], axis=-1)


def srgb_decode(values: np.ndarray) -> np.ndarray:
    c = values.astype(np.float64) / 255.0
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def _vertex(x: float, y: float, z: float, colour) -> list[float]:
    return [float(x), float(y), float(z), 1.0, *(float(c) for c in colour)]


def quad(x0: float, y0: float, x1: float, y1: float, z: float = 0.0, colour=(1.0, 1.0, 1.0, 1.0)) -> list[float]:
    out: list[float] = []
    for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y0), (x1, y1), (x0, y1)):
        out += _vertex(x, y, z, colour)
    return out


FULLSCREEN = quad(-1.0, -1.0, 1.0, 1.0)


def depth_vertices() -> list[float]:
    out: list[float] = []
    for _name, (x0, x1, y0, y1), z, colour in PLANES:
        d = -z
        rgba = (*(c / 255.0 for c in colour), 1.0)
        for nx, ny in ((x0, y0), (x1, y0), (x1, y1), (x0, y0), (x1, y1), (x0, y1)):
            out += _vertex(nx * d * TAN[0], ny * d * TAN[1], z, rgba)
    return out


def cull_vertices() -> list[float]:
    out: list[float] = []
    for _name, points, colour in TRIANGLES:
        for x, y in points:
            out += _vertex(x, y, 0.0, colour)
    return out


def ndc_of(matrix, x: float, y: float) -> tuple[float, float]:
    """A 2D point through a column-major matrix (z 0, w 1; the matrices here are affine in x, y)."""
    return (matrix[0] * x + matrix[4] * y + matrix[12], matrix[1] * x + matrix[5] * y + matrix[13])


def signed_area(points) -> float:
    (ax, ay), (bx, by), (cx, cy) = points
    return 0.5 * ((bx - ax) * (cy - ay) - (cx - ax) * (by - ay))


def window_depth(z: float) -> float:
    """The analytical window depth of view z through framed_camera's projection: NDC z in OpenGL form, then the one
    window range every backend shares after the correction ([0, 1]). Float64 from the float32 z the GPU receives."""
    m = perspective_matrix(TAN, NEAR, FAR)
    z32 = float(np.float32(z))
    clip_z, clip_w = m[10] * z32 + m[14], m[11] * z32 + m[15]
    return 0.5 * (clip_z / clip_w) + 0.5


def memory_ndc() -> tuple[np.ndarray, np.ndarray]:
    """The OpenGL-form NDC of every memory texel's centre under the decided convention (row 0 the top)."""
    y, x = np.mgrid[0:HEIGHT, 0:WIDTH]
    return (x + 0.5) / WIDTH * 2.0 - 1.0, 1.0 - (y + 0.5) / HEIGHT * 2.0


def expected_depth_scene() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """(colour (H, W, 3) uint8, window depth (H, W) float64, winning plane index or -1)."""
    nx, ny = memory_ndc()
    colour = np.zeros((HEIGHT, WIDTH, 3), np.uint8)
    depth = np.ones((HEIGHT, WIDTH))
    label = np.full((HEIGHT, WIDTH), -1)
    for index, (_name, (x0, x1, y0, y1), z, rgb) in enumerate(PLANES):
        d = window_depth(z)
        if not 0.0 <= d <= 1.0:
            continue  # beyond the far plane or in front of the near one: clipped
        passes = (nx > x0) & (nx < x1) & (ny > y0) & (ny < y1) & (d < depth)  # LESS
        colour[passes] = rgb
        depth[passes] = d
        label[passes] = index
    return colour, depth, label


def expected_cull_scene(matrix) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """(culled RGB, facing RGB, edge mask) in memory rows: the authored-front triangle kept and front-facing, the
    authored-back one culled (and back-facing when drawn unculled), under ``matrix``."""
    y, x = np.mgrid[0:HEIGHT, 0:WIDTH]
    px, py = x + 0.5, y + 0.5
    culled = np.zeros((HEIGHT, WIDTH, 3), np.uint8)
    facing = np.zeros((HEIGHT, WIDTH, 3), np.uint8)
    near_edge = np.zeros((HEIGHT, WIDTH), bool)
    for name, points, _colour in TRIANGLES:
        pixels = []
        for ix, iy in points:
            ndx, ndy = ndc_of(matrix, ix, iy)
            pixels.append(((ndx + 1.0) * 0.5 * WIDTH, (1.0 - ndy) * 0.5 * HEIGHT))
        edges = []
        for i in range(3):
            (ax, ay), (bx, by) = pixels[i], pixels[(i + 1) % 3]
            e = (bx - ax) * (py - ay) - (by - ay) * (px - ax)
            edges.append(e)
            near_edge |= np.abs(e) / math.hypot(bx - ax, by - ay) < EDGE_MARGIN_PX
        inside = ((edges[0] > 0) & (edges[1] > 0) & (edges[2] > 0)) | ((edges[0] < 0) & (edges[1] < 0) & (edges[2] < 0))
        if name == "front":
            culled[inside] = (255, 0, 0)
            facing[inside] = (255, 255, 0)
        else:
            facing[inside] = (0, 0, 255)
    return culled, facing, near_edge


def probe_expected() -> np.ndarray:
    v = PROBE_VALUES
    rows = [v["a"] + v["f0"]]
    rows += [v["arr"][3 * i:3 * i + 3] + [0.0] for i in range(3)]
    rows += [v["m"][3 * i:3 * i + 3] + [0.0] for i in range(3)]
    rows += [v["tail"] + [0.0, 0.0, 0.0]]
    return np.array(rows, np.float32).reshape(1, 8, 4)


# ------------------------------------------------------------------------------------------------ the spec

def build_spec() -> dict:
    gl_perspective = list(perspective_matrix(TAN, NEAR, FAR))
    checker_quad = quad(0.0, 0.0, float(WIDTH), float(HEIGHT))
    runs = [
        {"name": "checker_target", "scene": "checker", "correction": "target", "include_flip": 0.0},
        {"name": "checker_clip_route", "scene": "checker", "correction": "clip", "include_flip": "framebuffer"},
        {"name": "checker_include_flip_inverted", "scene": "checker", "correction": "target", "include_flip": 1.0},
        {"name": "checker_uncorrected", "scene": "checker", "correction": "none", "include_flip": 0.0},
        {"name": "checker_hand_packed", "scene": "checker", "correction": "target", "include_flip": 0.0,
         "pack": "hand"},
        {"name": "depth_target", "scene": "depth", "correction": "target", "include_flip": 0.0},
        {"name": "depth_skip_depth", "scene": "depth", "correction": "target_skip_depth", "include_flip": 0.0},
        {"name": "depth_uncorrected", "scene": "depth", "correction": "none", "include_flip": 0.0},
    ]
    for run in runs:
        run["matrix"] = list(QUICK_MATRIX) if run["scene"] == "checker" else gl_perspective
        run["vertices"] = checker_quad if run["scene"] == "checker" else depth_vertices()
    for label, matrix in (("quick", QUICK_MATRIX), ("up", UP_MATRIX)):
        for mode in ("rule", "ccw", "rule_gl_form"):
            runs.append({"name": f"cull_{label}_{mode}", "scene": "cull", "correction": "target", "include_flip": 0.0,
                         "front_face": mode, "matrix": list(matrix), "vertices": cull_vertices()})
    return {
        "width": WIDTH, "height": HEIGHT, "fullscreen": FULLSCREEN,
        "checker": {"cell": CELL,
                    "upload_rgba8": base64.b64encode(checker_content().tobytes()).decode("ascii"),
                    "strip_rgba8": base64.b64encode(strip_rgba().tobytes()).decode("ascii"),
                    "probe": PROBE_VALUES},
        "runs": runs,
    }


# ------------------------------------------------------------------------------------------------ analysis

def decode_image(entry: dict) -> np.ndarray:
    data = base64.b64decode(entry["b64"])
    w, h = int(entry["w"]), int(entry["h"])
    if entry["format"] == "rgba8":
        return np.frombuffer(data, np.uint8).reshape(h, w, 4)
    return np.frombuffer(data, np.float32).reshape(h, w, 4)


def images(run: dict) -> dict:
    return {name: decode_image(entry) for name, entry in run.get("readbacks", {}).items()}


def _equal(a: np.ndarray | None, b: np.ndarray) -> bool:
    return a is not None and a.shape == b.shape and bool(np.array_equal(a, b))


def _max_abs(a: np.ndarray | None, b: np.ndarray, mask: np.ndarray | None = None) -> float | None:
    if a is None or a.shape != b.shape:
        return None
    diff = np.abs(a.astype(np.float64) - b.astype(np.float64))
    if mask is not None:
        diff = diff[mask]
    return float(diff.max()) if diff.size else 0.0


def _within(a, b, tolerance: float, mask=None) -> bool:
    value = _max_abs(a, b, mask)
    return value is not None and value <= tolerance


def _rows(matrix) -> list[list[float]]:
    return [[float(matrix[4 * c + r]) for c in range(4)] for r in range(4)]


def ndc_y_flip_candidate(facts: dict) -> bool:
    """Where the clip NDC's +Y lands on memory row 0 after the "target" correction: on a backend whose NDC is Y up and
    whose framebuffer rows are top-down (D3D, Metal). There ``ndcToUv`` must flip Y to agree with the writer."""
    return bool(facts.get("is_y_up_in_ndc")) and not bool(facts.get("is_y_up_in_framebuffer"))


def analyse_checker(run: dict, facts: dict) -> dict:
    img = images(run)
    content = checker_content()
    y, x = np.mgrid[0:HEIGHT, 0:WIDTH]
    centres = np.stack([x + 0.5, y + 0.5], axis=-1)
    texels = np.stack([x, y], axis=-1).astype(np.float64)
    uv = centres / np.array([WIDTH, HEIGHT], np.float64)
    pixel, uvs, raw, ndc, mapping = (img.get(k) for k in ("pixel", "uv", "raw", "ndc", "mapping"))
    strip = img.get("strip")
    values = strip_values()
    checks: dict = {}
    measures: dict = {}
    checks["texel_origin_top_left"] = _equal(img.get("written"), content)
    checks["upload_row_order"] = _equal(img.get("uploaded_raw"), content) and _equal(img.get("upload_fetch"), content)
    checks["frag_texel_matches_writer"] = (_equal(img.get("fetch"), content) and pixel is not None
                                           and _within(pixel[..., 2:], texels, 0.0))
    checks["frag_uv_matches_writer"] = (_equal(img.get("sample"), content) and uvs is not None
                                        and _within(uvs[..., :2], uv, COORD_TOLERANCE))
    checks["frag_pixel_is_texel_centre"] = pixel is not None and _within(pixel[..., :2], centres, 0.0)
    checks["ndc_to_uv_agrees_with_writer"] = uvs is not None and _within(uvs[..., 2:], uvs[..., :2], COORD_TOLERANCE)
    checks["uv_to_ndc_agrees_with_clip_ndc"] = (mapping is not None and ndc is not None
                                                and _within(mapping[..., :2], ndc[..., :2], COORD_TOLERANCE))
    if strip is not None:
        decoded = srgb_decode(values)
        measures["srgb_max_error_vs_analytic"] = _max_abs(strip[..., 0], decoded)
        checks["srgb_matches_analytic"] = measures["srgb_max_error_vs_analytic"] <= SRGB_TOLERANCE
        checks["srgb_flag_live"] = (_within(strip[..., 1], values / 255.0, 1.0e-6)
                                    and _max_abs(strip[..., 0], values / 255.0) > 0.1)
    else:
        checks["srgb_matches_analytic"] = checks["srgb_flag_live"] = False
    checks["probe_values"] = _equal(img.get("probe"), probe_expected())
    checks["double_correction_refused"] = run.get("double_correction_refused") is True
    # Records (not gating): what the raw values say on this backend.
    info: dict = {}
    info["gl_fragcoord_is_memory_texel_centre"] = raw is not None and _within(raw[..., :2], centres, 0.0)
    info["content_at_memory_texel"] = raw is not None and _within(raw[..., 2:], centres, ITEM_TOLERANCE)
    info["content_upside_down_in_memory"] = _equal(img.get("written"), content[::-1])
    info["ndc_to_uv_of_view_ndc_agrees"] = (mapping is not None and uvs is not None
                                            and _within(mapping[..., 2:], uvs[..., :2], COORD_TOLERANCE))
    if ndc is not None and uvs is not None:
        flip = ndc_y_flip_candidate(facts)
        post = ndc[..., :2].astype(np.float64)
        candidate = np.stack([post[..., 0] * 0.5 + 0.5, (-post[..., 1] if flip else post[..., 1]) * 0.5 + 0.5], -1)
        info["candidate_ndc_y_flip"] = flip
        info["candidate_ndc_to_uv_agrees"] = _within(candidate, uvs[..., :2], COORD_TOLERANCE)
        view = ndc[..., 2:].astype(np.float64)
        info["view_ndc_is_opengl_form"] = _within(view, np.stack(memory_ndc(), -1), COORD_TOLERANCE)
    written = img.get("written")
    if written is not None:
        # The draft's harness readback flipped rows by isYUpInFramebuffer(); whether that shows the content upright.
        shown = written[::-1] if facts.get("is_y_up_in_framebuffer") else written
        info["readback_flip_by_is_y_up_in_framebuffer_upright"] = _equal(shown, content)
    return {"checks": checks, "info": info, "measures": measures}


def analyse_depth(run: dict) -> dict:
    img = images(run)
    colour, depth = img.get("colour"), img.get("depth")
    exp_colour, exp_depth, label = expected_depth_scene()
    covered = label >= 0
    names = [p[0] for p in PLANES]
    checks: dict = {}
    measures: dict = {}
    checks["colour_image"] = colour is not None and _equal(colour[..., :3], exp_colour)
    if colour is not None:
        def region(*plane_names):
            return np.isin(label, [names.index(n) for n in plane_names])
        checks["nearer_plane_wins"] = _equal(colour[..., :3][region("B", "B2")], exp_colour[region("B", "B2")])
        checks["less_rejects_equal_depth"] = _equal(colour[..., :3][region("E1R")], exp_colour[region("E1R")])
        clipped = (~covered) & (memory_ndc()[1] < -0.5)
        checks["near_far_clip"] = (_equal(colour[..., :3][region("far_in", "near_in")],
                                          exp_colour[region("far_in", "near_in")])
                                   and bool(np.all(colour[..., :3][clipped] == 0)))
    if depth is not None:
        measures["window_depth_max_error"] = _max_abs(depth[..., 0], exp_depth, covered)
        checks["window_depth_analytic"] = measures["window_depth_max_error"] <= DEPTH_TOLERANCE
        checks["view_depth_is_window_depth"] = _equal(depth[..., 0], depth[..., 1])
        checks["clear_depth_is_one"] = bool(np.all(depth[..., 0][~covered] == 1.0))
    else:
        checks["window_depth_analytic"] = checks["view_depth_is_window_depth"] = checks["clear_depth_is_one"] = False
    checks["double_correction_refused"] = run.get("double_correction_refused") is True
    return {"checks": checks, "measures": measures}


def analyse_cull(run: dict, facts: dict, matrix) -> dict:
    img = images(run)
    exp_culled, exp_facing, near_edge = expected_cull_scene(matrix)
    keep = ~near_edge
    culled, facing = img.get("culled"), img.get("facing")
    checks: dict = {
        "kept_triangle": culled is not None and _equal(culled[..., :3][keep], exp_culled[keep]),
        "front_facing": facing is not None and _equal(facing[..., :3][keep], exp_facing[keep]),
        "pipelines_prebuilt": run.get("pipelines_prebuilt") == ["ccw", "cw"],
    }
    if run.get("front_face_mode") == "rule":
        python = front_face_clockwise(run["uploaded"], ndc_y_up=bool(facts.get("is_y_up_in_ndc")))
        checks["rule_matches_python"] = run.get("front_face") == ("cw" if python else "ccw")
    return {"checks": checks}


# Each negative control: the checks it must break where it changes anything, and how to tell it changes nothing.
NEGATIVE = {
    "checker_include_flip_inverted": ("checker_target", ("frag_texel_matches_writer", "frag_uv_matches_writer"),
                                      "never"),
    "checker_uncorrected": ("checker_target", ("texel_origin_top_left",), "xy_rows"),
    "checker_hand_packed": ("checker_target", ("probe_values",), "never"),
    "depth_skip_depth": ("depth_target", ("window_depth_analytic",), "z_row"),
    "depth_uncorrected": ("depth_target", ("window_depth_analytic", "colour_image"), "all_rows"),
    "cull_quick_ccw": ("cull_quick_rule", ("kept_triangle",), "front_face"),
    "cull_quick_rule_gl_form": ("cull_quick_rule", ("kept_triangle",), "front_face"),
    "cull_up_ccw": ("cull_up_rule", ("kept_triangle",), "front_face"),
    "cull_up_rule_gl_form": ("cull_up_rule", ("kept_triangle",), "front_face"),
}


def _vacuous(kind: str, run: dict, reference: dict) -> bool:
    """True when the control changes nothing the GPU sees on this backend (it then proves nothing here)."""
    if kind == "never":
        return False
    if kind == "front_face":
        return run.get("front_face") == reference.get("front_face")
    a, b = _rows(run.get("uploaded", IDENTITY)), _rows(reference.get("uploaded", IDENTITY))
    rows = {"xy_rows": (0, 1, 3), "z_row": (2,), "all_rows": (0, 1, 2, 3)}[kind]
    return all(np.allclose(a[r], b[r], rtol=0.0, atol=0.0) for r in rows)


def probe_layout_matches_oracle(reflection: dict) -> bool:
    """The probe block as qsb reflected it against the std140 oracle: every member's offset, the vec3 array's and the
    mat3's 16-byte strides (an array stride the reflection leaves 0 is the member size over its element count, as
    the packer takes it), and the block size rounded up to 16 (SPIR-V reports the end of the last member)."""
    members = {m["name"]: m for m in reflection.get("members", [])}
    oracle = dict(zip((f for f, _t in PROBE_ORACLE.fields), PROBE_ORACLE.offsets))
    arr = members.get("arr", {})
    elements = int(np.prod(arr.get("array_dims") or [0]))
    arr_stride = arr.get("array_stride") or (arr.get("size", 0) // elements if elements else 0)
    size = int(reflection.get("size", 0))
    return (bool(members) and all(members.get(f, {}).get("offset") == off for f, off in oracle.items())
            and arr_stride == 16 and members.get("m", {}).get("matrix_stride") == 16
            and -(-size // 16) * 16 == PROBE_ORACLE.size)


def analyse_backend(result: dict) -> dict:
    facts = result.get("facts", {})
    runs = {run["name"]: run for run in result.get("runs", [])}
    analysis: dict = {}
    for name, run in runs.items():
        if not run.get("ok"):
            analysis[name] = {"checks": {"run_ok": False}, "error": run.get("error")}
            continue
        if run["scene"] == "checker":
            analysis[name] = analyse_checker(run, facts)
        elif run["scene"] == "depth":
            analysis[name] = analyse_depth(run)
        else:
            analysis[name] = analyse_cull(run, facts, QUICK_MATRIX if "_quick_" in name else UP_MATRIX)
    # Rule 4's handedness switch: the up-facing matrix's image, rows mirrored back, is Quick's.
    quick, up = runs.get("cull_quick_rule"), runs.get("cull_up_rule")
    if quick and up and quick.get("ok") and up.get("ok"):
        _c, _f, edge_q = expected_cull_scene(QUICK_MATRIX)
        _c, _f, edge_u = expected_cull_scene(UP_MATRIX)
        keep = ~(edge_q | edge_u[::-1])
        a, b = images(quick).get("culled"), images(up).get("culled")
        analysis["cull_quick_rule"]["checks"]["handedness_same_image"] = (
            a is not None and b is not None and _equal(a[keep], b[::-1][keep]))
    if "checker_target" in analysis:
        analysis["checker_target"]["checks"]["probe_offsets_reflected_equal_oracle"] = probe_layout_matches_oracle(
            facts.get("probe_reflection", {}))
    negatives: dict = {}
    for name, (ref_name, targets, kind) in NEGATIVE.items():
        run, reference = runs.get(name), runs.get(ref_name)
        if not run or not reference or name not in analysis:
            negatives[name] = {"status": "missing"}
            continue
        if _vacuous(kind, run, reference):
            negatives[name] = {"status": "vacuous here", "reason": f"the control changes nothing on this backend "
                                                                    f"({kind})"}
            continue
        broken = [t for t in targets if analysis[name]["checks"].get(t) is False]
        negatives[name] = {"status": "fails as it must" if broken else "DID NOT FAIL", "broken": broken}
    return {"facts": {k: v for k, v in facts.items() if k != "probe_reflection"},
            "probe_reflection": facts.get("probe_reflection"), "runs": analysis, "negatives": negatives}


SCENE_RUNS = {"checker": ("checker_target",), "depth": ("depth_target",),
              "cull": ("cull_quick_rule", "cull_up_rule")}
SCENE_NEGATIVES = {"checker": ("checker_include_flip_inverted", "checker_uncorrected", "checker_hand_packed"),
                   "depth": ("depth_skip_depth", "depth_uncorrected"),
                   "cull": ("cull_quick_ccw", "cull_quick_rule_gl_form", "cull_up_ccw", "cull_up_rule_gl_form")}


def cross_backend(results: dict) -> dict:
    """The backends' correct runs against the reference backend's (OpenGL) and the sRGB decode against OpenGL's."""
    ref = results.get(REFERENCE_BACKEND)
    if not ref:
        return {"reference_missing": True}
    ref_runs = {run["name"]: run for run in ref.get("runs", []) if run.get("ok")}
    out: dict = {}
    for backend, result in results.items():
        if backend == REFERENCE_BACKEND:
            continue
        runs = {run["name"]: run for run in result.get("runs", []) if run.get("ok")}
        entry: dict = {}
        for name, key, tolerance, edge in (("checker_target", "written", 0, None),
                                           ("depth_target", "colour", BACKEND_TOLERANCE_U8, None),
                                           ("depth_target", "depth", DEPTH_TOLERANCE, None),
                                           ("cull_quick_rule", "culled", BACKEND_TOLERANCE_U8, QUICK_MATRIX),
                                           ("cull_up_rule", "culled", BACKEND_TOLERANCE_U8, UP_MATRIX)):
            a = images(runs[name]).get(key) if name in runs else None
            b = images(ref_runs[name]).get(key) if name in ref_runs else None
            if a is None or b is None:
                entry[f"{name}.{key}"] = None
                continue
            mask = None
            if edge is not None:
                mask = ~expected_cull_scene(edge)[2]
            channels = (slice(0, 1) if key == "depth" else slice(0, 3))
            value = _max_abs(a[..., channels], b[..., channels], mask)
            entry[f"{name}.{key}"] = {"max_abs": value, "within": value is not None and value <= tolerance}
        a = images(runs["checker_target"]).get("strip") if "checker_target" in runs else None
        b = images(ref_runs["checker_target"]).get("strip") if "checker_target" in ref_runs else None
        value = _max_abs(a[..., 0], b[..., 0]) if a is not None and b is not None else None
        entry["srgb_vs_opengl"] = {"max_abs": value, "within": value is not None and value <= SRGB_BACKEND_TOLERANCE}
        out[backend] = entry
    return out


def scene_verdicts(analyses: dict, cross: dict, validation: dict | None) -> dict:
    verdicts: dict = {}
    for scene, names in SCENE_RUNS.items():
        failed: list[str] = []
        for backend, analysis in analyses.items():
            for name in names:
                for check, ok in analysis["runs"].get(name, {"checks": {"missing": False}})["checks"].items():
                    if not ok:
                        failed.append(f"{backend}:{name}.{check}")
            for name in SCENE_NEGATIVES[scene]:
                status = analysis["negatives"].get(name, {}).get("status")
                if status not in ("fails as it must", "vacuous here"):
                    failed.append(f"{backend}:{name} {status}")
        if all(analysis["negatives"].get(n, {}).get("status") == "vacuous here"
               for analysis in analyses.values() for n in SCENE_NEGATIVES[scene]):
            failed.append("no negative control changed anything on any backend")
        prefixes = {"checker": ("checker_target.",), "depth": ("depth_target.",), "cull": ("cull_",)}[scene]
        for backend, entry in cross.items():
            if not isinstance(entry, dict):
                failed.append(f"cross-backend: {backend} {entry}")
                continue
            for key, value in entry.items():
                relevant = key.startswith(prefixes) or (scene == "checker" and key == "srgb_vs_opengl")
                if relevant and not (value or {}).get("within"):
                    failed.append(f"cross-backend {backend} vs {REFERENCE_BACKEND}: {key} {value}")
        verdicts[scene] = {"pass": not failed, "failed": failed}
    if validation is not None and not validation.get("clean_or_not_required", False):
        for scene in verdicts:
            verdicts[scene]["pass"] = False
            verdicts[scene]["failed"].append(f"vulkan validation: {validation.get('status')}")
    return verdicts


# ------------------------------------------------------------------------------------------------ evidence sheets

def _sheet(path: Path, columns: list[str], rows: list[tuple[str, list[np.ndarray | None]]], scale: int = 3) -> None:
    from PIL import Image, ImageDraw

    label_w, head_h, pad = 90, 16, 4
    cell_w, cell_h = WIDTH * scale, HEIGHT * scale
    sheet = Image.new("RGB", (label_w + len(columns) * (cell_w + pad), head_h + len(rows) * (cell_h + pad)),
                      (32, 32, 32))
    draw = ImageDraw.Draw(sheet)
    for c, title in enumerate(columns):
        draw.text((label_w + c * (cell_w + pad), 2), title, fill=(230, 230, 230))
    for r, (label, cells) in enumerate(rows):
        top = head_h + r * (cell_h + pad)
        draw.text((4, top + 4), label, fill=(230, 230, 230))
        for c, image in enumerate(cells):
            if image is None:
                continue
            rgb = image[..., :3]
            if rgb.dtype != np.uint8:
                rgb = (np.clip(rgb, 0.0, 1.0) * 255.0 + 0.5).astype(np.uint8)
            tile = Image.fromarray(np.ascontiguousarray(rgb), "RGB").resize((cell_w, cell_h), Image.NEAREST)
            sheet.paste(tile, (label_w + c * (cell_w + pad), top))
    sheet.save(path)


def _depth_view(depth: np.ndarray | None) -> np.ndarray | None:
    """Window depth as grey, stretched over [0.8, 1] so the planes read apart."""
    if depth is None:
        return None
    grey = np.clip((depth[..., 0].astype(np.float64) - 0.8) / 0.2, 0.0, 1.0)
    return np.repeat(grey[..., None], 3, axis=-1)


def write_sheets(out: Path, results: dict) -> list[str]:
    content = checker_content()
    exp_colour, exp_depth, _label = expected_depth_scene()
    exp_q = expected_cull_scene(QUICK_MATRIX)
    exp_u = expected_cull_scene(UP_MATRIX)

    def run_images(backend: str, name: str) -> dict:
        for run in results.get(backend, {}).get("runs", []):
            if run["name"] == name and run.get("ok"):
                return images(run)
        return {}

    written = []
    columns = ["written (target)", "fetch at fragTexel", "written (clip route)", "uncorrected", "flip inverted: fetch"]
    rows = [("expected", [content, content, None, None, None])]
    for backend in results:
        rows.append((backend, [run_images(backend, "checker_target").get("written"),
                               run_images(backend, "checker_target").get("fetch"),
                               run_images(backend, "checker_clip_route").get("written"),
                               run_images(backend, "checker_uncorrected").get("written"),
                               run_images(backend, "checker_include_flip_inverted").get("fetch")]))
    _sheet(out / "n03_scene1_checker.png", columns, rows)
    written.append("n03_scene1_checker.png")

    columns = ["colour", "depth (0.8..1)", "uncorrected colour", "skip-depth depth"]
    rows = [("expected", [exp_colour, np.repeat(np.clip((exp_depth[..., None] - 0.8) / 0.2, 0, 1), 3, -1), None,
                          None])]
    for backend in results:
        rows.append((backend, [run_images(backend, "depth_target").get("colour"),
                               _depth_view(run_images(backend, "depth_target").get("depth")),
                               run_images(backend, "depth_uncorrected").get("colour"),
                               _depth_view(run_images(backend, "depth_skip_depth").get("depth"))]))
    _sheet(out / "n03_scene2_depth.png", columns, rows)
    written.append("n03_scene2_depth.png")

    columns = ["Quick: culled", "Quick: facing", "up: culled", "up: facing", "Quick: CCW fixed", "up: CCW fixed"]
    rows = [("expected", [exp_q[0], exp_q[1], exp_u[0], exp_u[1], None, None])]
    for backend in results:
        rows.append((backend, [run_images(backend, "cull_quick_rule").get("culled"),
                               run_images(backend, "cull_quick_rule").get("facing"),
                               run_images(backend, "cull_up_rule").get("culled"),
                               run_images(backend, "cull_up_rule").get("facing"),
                               run_images(backend, "cull_quick_ccw").get("culled"),
                               run_images(backend, "cull_up_ccw").get("culled")]))
    _sheet(out / "n03_scene3_cull.png", columns, rows)
    written.append("n03_scene3_cull.png")
    return written


# ------------------------------------------------------------------------------------------------ driver

def _evidence_dir(label: str) -> Path:
    from tools import artifact_paths

    folder = artifact_paths.evidence_dir("native_core", "n0_3", label)
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def _strip_blobs(result: dict) -> dict:
    """The module's record without the base64 readbacks (they are in the sheets and the checks)."""
    out = {k: v for k, v in result.items() if k != "runs"}
    out["runs"] = []
    for run in result.get("runs", []):
        slim = {k: v for k, v in run.items() if k != "readbacks"}
        slim["readbacks"] = {name: {k: v for k, v in entry.items() if k != "b64"}
                             for name, entry in run.get("readbacks", {}).items()}
        out["runs"].append(slim)
    return out


def run_backends(native, backends: list[str], require_validation: bool) -> tuple[dict, dict | None]:
    from run_n06 import validation_summary

    spec = json.dumps(build_spec())
    results: dict = {}
    validation = None
    for backend in backends:
        if backend == "vulkan":
            ctx = json.loads(native.n06_context_create(True, "one"))
            if not ctx.get("ok"):
                results[backend] = {"ok": False, "error": "N0.6 context create failed", "context": ctx}
                native.n06_context_destroy()
                continue
            layer = bool(ctx.get("instance", {}).get("validation_layer_loaded"))
            results[backend] = json.loads(native.n03_run(backend, spec))
            teardown = json.loads(native.n06_context_destroy())
            summary = validation_summary(teardown.get("messages", {}))
            status = ("clean" if summary["clean"] else "NOT CLEAN") if layer else "layer not loaded"
            validation = {"layer_loaded": layer, "status": status, "required": require_validation,
                          "clean_or_not_required": (summary["clean"] if layer else not require_validation),
                          "teardown_ok": bool(teardown.get("ok")),
                          **{k: v for k, v in summary.items() if k != "groups"}, "attribution": summary["groups"]}
        else:
            results[backend] = json.loads(native.n03_run(backend, spec))
    return results, validation


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--module-dir", required=True, type=Path)
    parser.add_argument("--label", default="n03_scenes")
    parser.add_argument("--backends", nargs="+", default=list(BACKENDS), choices=BACKENDS)
    parser.add_argument("--layer-path", type=Path, default=None,
                        help="the folder holding VkLayer_khronos_validation.json (run_n06.py's rule: VK_ADD_LAYER_PATH "
                             "for this process only, reported and allowed by the environment check)")
    parser.add_argument("--require-validation", action="store_true",
                        help="a Vulkan run whose validation layer did not load is a FAIL, never a pass with 'owed'")
    args = parser.parse_args()

    from run_n06 import environment_record, use_layer_path
    from run_spike import _import_native

    use_layer_path(args.layer_path)  # before the module or Qt loads the Vulkan loader
    native = _import_native(args.module_dir.resolve())
    missing = [name for name in ("n03_run", "n06_context_create", "n06_context_destroy") if not hasattr(native, name)]
    if missing:
        print(f"N03 VERDICT FAIL: the module has no {', '.join(missing)} (an older build in --module-dir)")
        return 0
    from PySide6.QtGui import QGuiApplication

    app = QGuiApplication([sys.argv[0]])  # no window is ever created
    out = _evidence_dir(args.label)
    results, validation = run_backends(native, list(args.backends), args.require_validation)
    del app
    analyses = {b: analyse_backend(r) for b, r in results.items() if r.get("ok") or r.get("runs")}
    cross = cross_backend(results)
    verdicts = scene_verdicts(analyses, cross, validation)
    failed_backends = [b for b, r in results.items() if not r.get("ok")]
    env = environment_record()
    sheets = write_sheets(out, results)
    summary = {
        "runtime": native.runtime_info(), "python": sys.version, "backends": list(args.backends),
        "verdicts": verdicts, "backends_failed_to_run": failed_backends, "validation": validation,
        "environment": env, "cross_backend": cross, "analysis": analyses, "sheets": sheets,
        "constants": {"size": [WIDTH, HEIGHT], "cell": CELL, "near": NEAR, "far": FAR, "tan": list(TAN),
                      "depth_tolerance": DEPTH_TOLERANCE, "coord_tolerance": COORD_TOLERANCE,
                      "srgb_tolerance": SRGB_TOLERANCE, "backend_tolerance_u8": BACKEND_TOLERANCE_U8,
                      "edge_margin_px": EDGE_MARGIN_PX},
        "module_records": {b: _strip_blobs(r) for b, r in results.items()},
    }
    passed = all(v["pass"] for v in verdicts.values()) and not failed_backends and env["clean"]
    summary["pass"] = passed
    (out / "summary.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    for backend, analysis in analyses.items():
        print(f"\n== {backend}: {analysis['facts'].get('backend')} on {analysis['facts'].get('device')}")
        for name, entry in analysis["runs"].items():
            bad = [k for k, v in entry.get("checks", {}).items() if not v]
            print(f"  {name}: {'all checks hold' if not bad else 'FALSE: ' + ', '.join(bad)}")
        for name, entry in analysis["negatives"].items():
            print(f"  negative {name}: {entry['status']}")
    print(json.dumps({"verdicts": verdicts, "validation": {k: v for k, v in (validation or {}).items()
                                                           if k != "attribution"}}, indent=2, default=str))
    print(f"\nevidence: {out / 'summary.json'}")
    failed = [f"{scene}" for scene, v in verdicts.items() if not v["pass"]] + failed_backends
    if not env["clean"]:
        failed.append("environment")
    print("N03 VERDICT " + ("PASS" if passed else "FAIL: " + ", ".join(failed)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
