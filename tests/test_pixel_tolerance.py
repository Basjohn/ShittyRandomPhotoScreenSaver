"""The shared pixel tolerance of the native parity harnesses (``tools/pixel_tolerance.py``; D12 "The pixel tolerance";
checkpoint audit 3 M1 and audit 4 M2).

- The explained one-level class moves only the pixels of the mask the harness derives from the reference; opaque
  content and background stay exact.
- Ties are capped in count and level and must be isolated or on a content edge; scatter is a share, never the frame.
- The audits' synthetic regressions fail every harness's tolerance: a one-level shift on every pixel, a fixed 10-pixel
  artefact of 3 levels, 8 pixels off by up to 207 levels. Each harness's predicate is driven with them on its own saved
  frame format (mesh buffers, scene targets, the transition route, the owner-level rule (a), Spline Curve's pixels).

Bounds are read from the harnesses' own tolerances, never restated here.
"""
from __future__ import annotations

import sys
import zlib
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
HARNESS = ROOT / "native" / "core" / "python"


def _harness(name: str):
    if str(HARNESS) not in sys.path:
        sys.path.insert(0, str(HARNESS))
    import importlib

    return importlib.import_module(name)


def _card(height: int = 100, width: int = 200) -> np.ndarray:
    """An opaque frame: the card's dark fill and an opaque bar (the audit's synthetic frame)."""
    image = np.zeros((height, width, 4), np.uint8)
    image[..., :3] = 12
    image[..., 3] = 255
    image[40:60, 20:120, :3] = 200
    return image


def _shift(image: np.ndarray, levels: int = 1) -> np.ndarray:
    out = image.astype(np.int16)
    out[..., :3] += levels
    return np.clip(out, 0, 255).astype(np.uint8)


def _artefact(image: np.ndarray) -> np.ndarray:
    """A fixed 10-pixel, 3-level artefact inside the card's flat fill (no edge of anything)."""
    out = image.astype(np.int16)
    out[10, 150:160, :3] += 3
    return np.clip(out, 0, 255).astype(np.uint8)


def _wild(image: np.ndarray) -> np.ndarray:
    """8 scattered pixels off by up to 207 levels (audit 4's probe)."""
    out = image.copy()
    for k in range(8):
        out[5 + 10 * k, 140 + 5 * k, :3] = 219 if k % 2 else 12 + 207 - k
    return out


def _tolerances() -> dict:
    from tools.visualizer_replay import owner_render_parity as parity

    trc = _harness("transition_route_check")
    mbc = _harness("mesh_buffer_check")
    stc = _harness("scene_target_check")
    return {"composite": parity.composite_tolerance(), "fragment_a": trc.FRAGMENT_PASS_RULE_A,
            "fragment_b": trc.FRAGMENT_PASS_RULE_B, "seven_b": trc.SEVEN_RULE_B, "geometry": mbc.GEOMETRY_TOLERANCE,
            "scene_a": stc.SCENE_RULE_A, "scene_b": stc.SCENE_RULE_B}


@pytest.mark.parametrize("name", ("composite", "fragment_a", "fragment_b", "seven_b", "geometry", "scene_a", "scene_b"))
def test_the_audit_regressions_fail_every_harness_tolerance(name):
    from tools import pixel_tolerance as pt

    tolerance = _tolerances()[name]
    reference = _card()
    mask = pt.translucent_by_alpha(reference)                  # opaque content: an empty mask
    assert not mask.any()
    assert pt.judge(reference, reference, tolerance, mask=mask)["pass"]
    for regression in (_shift, _artefact, _wild):
        verdict = pt.judge(regression(reference), reference, tolerance, mask=mask)
        assert not verdict["pass"], (name, regression.__name__, verdict)
    # Control: with a mask over every pixel (the old rule's shape: "any pixel within a level"), the uniform shift is
    # admitted by a tolerance that has the one-level class; the mask is what refuses it.
    if tolerance.masked_level:
        assert pt.judge(_shift(reference), reference, tolerance, mask=np.ones(mask.shape, bool))["pass"]


def test_the_one_level_class_moves_only_the_masked_pixels():
    from tools import pixel_tolerance as pt

    tolerance = _tolerances()["composite"]
    reference = _card()
    reference[40:60, 120:180, 3] = 128                          # a translucent stroke beside the opaque bar
    mask = pt.translucent_by_alpha(reference)
    shifted = reference.copy()
    shifted[40:60, 120:180, :3] += 1                            # every translucent pixel one level off
    verdict = pt.judge(shifted, reference, tolerance, mask=mask)
    assert verdict["pass"] and verdict["masked_differing"] == 20 * 60
    # Controls: the same level on the opaque bar, or on the bare fill, fails.
    for rows, cols in ((slice(40, 60), slice(20, 120)), (slice(70, 90), slice(20, 180))):
        moved = shifted.copy()
        moved[rows, cols, :3] += 1
        assert not pt.judge(moved, reference, tolerance, mask=mask)["pass"]


def test_ties_are_capped_and_isolated_or_on_an_edge():
    from tools import pixel_tolerance as pt

    tolerance = _tolerances()["composite"]
    reference = _card()
    mask = pt.translucent_by_alpha(reference)
    # Isolated ties at the edge class's level on the flat fill, the cap's number of them: admitted.
    ties = reference.astype(np.int16)
    for k in range(tolerance.tie_pixels):
        ties[5 + 3 * (k % 4), 130 + 3 * (k // 4), :3] += tolerance.tie_level
    assert pt.judge(ties.astype(np.uint8), reference, tolerance, mask=mask)["pass"]
    # Adjacent ties along the bar's edge: admitted (a content edge).
    edge = reference.astype(np.int16)
    edge[39, 30:30 + tolerance.tie_pixels, :3] += tolerance.tie_level
    assert pt.judge(edge.astype(np.uint8), reference, tolerance, mask=mask)["pass"]
    # Controls: one tie too many; one level too far; two adjacent ties on the flat fill.
    more = ties.copy()
    more[90, 190, :3] += 1
    assert not pt.judge(more.astype(np.uint8), reference, tolerance, mask=mask)["pass"]
    far = reference.astype(np.int16)
    far[5, 130, :3] += tolerance.tie_level + 1
    assert not pt.judge(far.astype(np.uint8), reference, tolerance, mask=mask)["pass"]
    pair = reference.astype(np.int16)
    pair[5, 130:132, :3] += 1
    assert not pt.judge(pair.astype(np.uint8), reference, tolerance, mask=mask)["pass"]


def test_a_tie_is_at_most_two_levels_and_three_only_for_the_composite_edge_class():
    from tools import pixel_tolerance as pt

    with pytest.raises(ValueError):
        pt.Tolerance("too far", tie_level=pt.COMPOSITE_EDGE_LEVEL)
    with pytest.raises(ValueError):
        pt.Tolerance("too far", tie_level=pt.COMPOSITE_EDGE_LEVEL + 1, edge_class=True)
    with pytest.raises(ValueError):
        pt.Tolerance("not one level", masked_level=2)
    assert pt.Tolerance("edge", tie_level=pt.COMPOSITE_EDGE_LEVEL, edge_class=True).tie_level == 3
    for tolerance in _tolerances().values():
        assert tolerance.tie_level <= (pt.COMPOSITE_EDGE_LEVEL if tolerance.edge_class else pt.TIE_LEVEL)


def test_scatter_is_a_share_never_the_frame():
    from tools import pixel_tolerance as pt

    tolerance = _tolerances()["seven_b"]
    reference = np.zeros((400, 400, 3), np.uint8) + 90
    rng = np.random.default_rng(3)
    flat = rng.choice(400 * 400, tolerance.scatter_pixels, replace=False)
    scattered = reference.copy().reshape(-1, 3)
    scattered[flat] += 1
    assert pt.judge(scattered.reshape(reference.shape), reference, tolerance)["pass"]
    # Controls: one more pixel; a two-level pixel (the seven have no tie).
    more = scattered.copy()
    more[np.setdiff1d(np.arange(400 * 400), flat)[0]] += 1
    assert not pt.judge(more.reshape(reference.shape), reference, tolerance)["pass"]
    two = scattered.reshape(reference.shape).copy()
    two[200, 200] = 92
    assert not pt.judge(two, reference, tolerance)["pass"]


def test_the_fragment_pass_flip_is_one_isolated_pixel_on_an_edge():
    from tools import pixel_tolerance as pt

    tolerance = _tolerances()["fragment_a"]
    reference = _card()[..., :3]
    flip = reference.copy()
    flip[39, 60] = (230, 235, 253)                              # on the bar's edge
    assert pt.judge(flip, reference, tolerance)["pass"]
    # Controls: on the flat fill; two of them; and every other tolerance refuses even the one.
    flat = reference.copy()
    flat[10, 160] = (230, 235, 253)
    assert not pt.judge(flat, reference, tolerance)["pass"]
    two = flip.copy()
    two[39, 90] = (230, 235, 253)
    assert not pt.judge(two, reference, tolerance)["pass"]
    for name, other in _tolerances().items():
        if name != "fragment_a":
            assert not pt.judge(flip, reference, other)["pass"], name


def test_translucent_by_backgrounds_keeps_opaque_content_and_bare_background_out():
    from tools import pixel_tolerance as pt

    backdrop = (255, 0, 255)
    alpha = np.zeros((4, 4), np.float64)
    alpha[0, :] = 1.0                                          # opaque content
    alpha[1, :] = 0.5                                          # translucent content
    colour = np.array([40.0, 160.0, 90.0])

    def draw(under):
        return np.rint(colour * alpha[..., None] + np.asarray(under, float) * (1.0 - alpha[..., None])).astype(np.uint8)

    first, second = draw((12, 12, 12)), draw(backdrop)
    mask = pt.translucent_by_backgrounds(first, second, backdrop)
    assert mask[1].all() and not mask[0].any() and not mask[2:].any()


def test_the_mesh_buffer_rules_judge_through_the_shared_tolerance(tmp_path):
    mbc = _harness("mesh_buffer_check")
    work = tmp_path / "work"
    work.mkdir()
    reference = {}
    for name in mbc.PARITY_SCENES:
        for dpr in mbc.DPRS:
            frame = _card()
            if name in mbc.ADDITIVE_SCENES:
                frame[..., 3] = 0                               # an additive scene over a cleared target
                frame[40:60, 20:120, 3] = 255
            reference[f"{name}|dpr{dpr}"] = frame
    for dpr in mbc.DPRS:
        for extra in ("sprites.points", "sprites.offset", "cells_direct"):
            reference[f"{extra}|dpr{dpr}"] = _card()
    np.savez_compressed(work / "parity_reference.npz", **reference)

    def verdicts(transform):
        drawn = {k: transform(k, v) for k, v in reference.items()}
        np.savez_compressed(work / "parity_opengl.npz", **drawn)
        np.savez_compressed(work / "parity_vulkan.npz", **drawn)
        result = mbc.cross_compare(tmp_path)
        return result["rule_a"]["pass"], result["rule_b"]["pass"]

    assert verdicts(lambda k, v: v) == (True, True)
    # The additive scene's lit pixels may sit one level off (its blended layers); the box's opaque ones may not.
    lit = f"{mbc.ADDITIVE_SCENES[0]}|dpr{mbc.DPRS[0]}"
    assert verdicts(lambda k, v: _bar_shift(v) if k == lit else v)[0]
    assert not verdicts(lambda k, v: _shift(v) if k.startswith("box|") else v)[0]
    assert not verdicts(lambda k, v: _wild(v) if k.startswith("box|") else v)[0]
    assert not verdicts(lambda k, v: _artefact(v) if k.startswith("voxels|") else v)[0]


def _bar_shift(image: np.ndarray) -> np.ndarray:
    out = image.copy()
    out[40:60, 20:120, :3] += 1
    return out


def test_the_scene_target_rules_judge_through_the_shared_tolerance(tmp_path):
    stc = _harness("scene_target_check")

    def entry(array, fmt):
        return {"array": array, "content": array.shape[1::-1], "size": array.shape[1::-1], "samples": 1,
                "format": fmt}

    colour = np.full((40, 60, 4), 0.5, np.float16)
    reference = {"dpr1": {"ambient.coverage": entry(_card(40, 60), "rgba8"), "scene.colour": entry(colour, "rgba16f")}}
    stc._save(tmp_path, "parity_reference", reference)

    def verdicts(coverage, scene):
        frames = {"dpr1": {"ambient.coverage": entry(coverage, "rgba8"), "scene.colour": entry(scene, "rgba16f")}}
        stc._save(tmp_path, "parity_opengl", frames)
        stc._save(tmp_path, "parity_vulkan", frames)
        result = stc.cross_compare(tmp_path)
        return result["rule_a"]["pass"], result["rule_b"]["pass"]

    assert verdicts(_card(40, 60), colour) == (True, True)
    # A float texel within one float16 ulp: the format's own rounding.
    ulp = colour.copy()
    ulp[3, 3, 0] = np.nextafter(np.float16(0.5), np.float16(1.0))
    assert verdicts(_card(40, 60), ulp) == (True, True)
    # Controls: an opaque RGBA8 texture shifted by one level, or 8 texels at 207 levels.
    assert verdicts(_shift(_card(40, 60)), colour)[0] is False
    wild = _card(40, 60)
    wild[5:13, 50, :3] = 219
    assert verdicts(wild, colour)[0] is False


def test_the_transition_routes_rule_b_judges_through_the_shared_tolerance(tmp_path):
    trc = _harness("transition_route_check")
    work = tmp_path
    photo = np.random.default_rng(5).integers(0, 255, (300, 400, 4), dtype=np.uint8)
    photo[..., 3] = 255
    keys = ("dpr1.0_burn_0.20", "dpr1.0_vhs_0.20")
    np.savez_compressed(work / "route_opengl.npz", **{k: photo for k in keys})

    def verdict(transform):
        np.savez_compressed(work / "route_vulkan.npz", **{k: transform(k, photo) for k in keys})
        return trc.vulkan_against_opengl(work)["pass"]

    assert verdict(lambda k, v: v)
    # Controls: a uniform one-level shift (each key in turn), 8 pixels off by up to 207 levels.
    assert not verdict(lambda k, v: _shift(v) if k == keys[0] else v)
    assert not verdict(lambda k, v: _shift(v) if k == keys[1] else v)

    def wild(k, v):
        out = v.copy()
        out[100:108, 200, :3] = (v[100:108, 200, :3].astype(np.int16) + 207).clip(0, 255) if k == keys[1] else v[100:108, 200, :3]
        return out

    assert not verdict(wild)


def _run(frames):
    """A drawn run in owner_render_parity's shape."""
    out = {"pixels": [], "frames": []}
    for image in frames:
        out["frames"].append((image.shape, zlib.compress(image.tobytes())))
        out["pixels"].append({"hash": zlib.crc32(image.tobytes()), "region": [0, 0, image.shape[1], image.shape[0]]})
    return out


def test_the_owner_rule_a_is_judged_pixel_by_pixel_with_the_translucency_mask():
    from tools.visualizer_replay import owner_render_parity as parity

    frames = []
    backdrop = []
    for k in range(6):
        image = _card()
        image[40:60, 20 + k:120 + k, :3] = 200
        image[70:80, 20:180, :3] = 106                         # a translucent stroke: half of 200 over 12
        frames.append(image)
        over = image.copy()
        over[:, :, :3] = parity.MASK_BACKDROP                   # the backdrop under the content ...
        over[40:60, 20 + k:120 + k, :3] = 200                   # ... the opaque bar covers it ...
        over[70:80, 20:180, :3] = (228, 100, 228)               # ... the stroke lets it through
        backdrop.append(over)
    python, under = _run(frames), _run(backdrop)
    masks = parity.rule_a_masks(python, under)
    assert all(mask[70:80, 20:180].all() and not mask[40:60].any() and not mask[:30].any() for mask in masks.values())

    def verdict(transform):
        return parity.rule_a_verdict(parity.rule_a_frames(_run([transform(f) for f in frames]), python, masks))

    def stroke(image):
        out = image.copy()
        out[70:80, 20:180, :3] += 1
        return out

    assert verdict(lambda f: f)["pass"]
    assert verdict(stroke)["pass"]                              # the translucent pixels one level off
    # The audit's probes: a uniform shift, the fixed artefact, the 207-level pixels.
    for regression in (_shift, _artefact, _wild):
        assert not verdict(regression)["pass"], regression.__name__
    # Spline Curve's pixels (devcurve_check) take the same frame verdict: the reference's own alpha is the mask.
    from tools import pixel_tolerance as pt

    translucent = _card()
    translucent[70:80, 20:180, 3] = 128
    assert parity.rule_a_frame(stroke(translucent)[..., :3], translucent[..., :3],
                               pt.translucent_by_alpha(translucent))["pass"]
    assert not parity.rule_a_frame(_shift(translucent)[..., :3], translucent[..., :3],
                                   pt.translucent_by_alpha(translucent))["pass"]


def _flood_fill_largest(flags) -> int:
    # The per-pixel flood fill the run union-find replaced (21 Nov), kept here as its reference.
    points = set(zip(*np.nonzero(flags)))
    largest = 0
    while points:
        stack, size = [points.pop()], 0
        while stack:
            y, x = stack.pop()
            size += 1
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    if (y + dy, x + dx) in points:
                        points.discard((y + dy, x + dx))
                        stack.append((y + dy, x + dx))
        largest = max(largest, size)
    return largest


def test_the_largest_group_by_runs_equals_the_flood_fill_at_every_density():
    from tools import pixel_tolerance

    rng = np.random.default_rng(3)
    cases = [rng.random((40, 57)) < density for density in (0.0, 0.02, 0.1, 0.3, 0.5, 0.7, 1.0) for _ in range(6)]
    diagonal = np.zeros((20, 20), bool)
    diagonal[np.arange(20), np.arange(20)] = True              # touching only corner to corner
    checker = (np.indices((16, 16)).sum(axis=0) % 2) == 0       # every pixel a diagonal neighbour of the next
    gap = np.zeros((6, 12), bool)
    gap[1, 2:5], gap[3, 2:5] = True, True                       # an empty row between: two groups
    for flags in cases + [diagonal, checker, gap]:
        assert pixel_tolerance._largest_group_by_runs(flags) == _flood_fill_largest(flags)
    assert pixel_tolerance._largest_group_by_runs(gap) == 3 and pixel_tolerance._largest_group_by_runs(diagonal) == 20


def test_a_frame_whose_every_pixel_differs_is_grouped_quickly():
    # A one-level shift flags every pixel of a 739 x 529 card: a second a frame with the flood fill.
    import time

    from tools import pixel_tolerance

    flags = np.ones((529, 739), bool)
    started = time.perf_counter()
    assert pixel_tolerance._largest_group_by_runs(flags) == flags.size
    assert time.perf_counter() - started < 0.2
