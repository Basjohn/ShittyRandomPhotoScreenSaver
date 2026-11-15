"""The six harnesses that judged Vulkan against OpenGL (or a photo) at "max level at most 1 everywhere" now judge
pixel by pixel through ``tools/pixel_tolerance.py`` (D12 "The pixel tolerance"; Current_Plan.md item 8b side defect).

Each harness's own verdict function is driven on its own saved frame format with the audits' regressions: a uniform
one-level shift, a fixed 10-pixel artefact of 3 levels and 8 pixels off by up to 207 levels must fail it, and the
unchanged frames must pass. The bounds are read from the harnesses, never restated here.
"""
from __future__ import annotations

import sys
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
    """An opaque frame: a dark flat fill and an opaque bar (the audit's synthetic frame)."""
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
    out = image.astype(np.int16)
    out[10, 150:160, :3] += 3
    return np.clip(out, 0, 255).astype(np.uint8)


def _wild(image: np.ndarray) -> np.ndarray:
    out = image.copy()
    for k in range(8):
        out[5 + 10 * k, 140 + 5 * k, :3] = 219 if k % 2 else 12 + 207 - k
    return out


REGRESSIONS = (_shift, _artefact, _wild)


def _scatter(image: np.ndarray, count: int, seed: int = 3) -> np.ndarray:
    """``count`` isolated flat-fill pixels one level off (the two drivers' rounding)."""
    out = image.astype(np.int16)
    rows = np.arange(0, 100, 3)
    cols = np.arange(130, 200, 3)
    cells = [(r, c) for r in rows for c in cols]
    chosen = np.random.default_rng(seed).choice(len(cells), count, replace=False)
    for index in chosen:
        r, c = cells[index]
        out[r, c, :3] += 1
    return out.astype(np.uint8)


# ----------------------------------------------------------------------------------------------------- spectrum

def _spectrum(tmp_path: Path, frames: dict, shifted: dict | None = None):
    sc = _harness("spectrum_check")
    work = tmp_path / "work"
    work.mkdir(exist_ok=True)
    np.savez_compressed(work / "native_opengl.npz", **frames)
    np.savez_compressed(work / "native_vulkan.npz", **(shifted if shifted is not None else frames))
    return sc.vulkan_against_opengl(tmp_path)


def _spectrum_frames(sc) -> dict:
    return {f"{k}" if name == sc.PLACEMENTS[0][0] else f"{k}@{name}": _card()
            for name, _o, _f in sc.PLACEMENTS for k in range(3)}


def test_spectrum_rule_b_admits_scatter_and_refuses_the_regressions(tmp_path):
    sc = _harness("spectrum_check")
    frames = _spectrum_frames(sc)
    assert _spectrum(tmp_path, frames)["pass"]
    cap = sc.VULKAN_RULE_B.scatter_pixels
    near = {k: _scatter(v, 20) for k, v in frames.items()}
    assert 20 <= cap
    assert _spectrum(tmp_path, frames, near)["pass"]
    for regression in REGRESSIONS:
        moved = {k: (regression(v) if k == "0" else v) for k, v in frames.items()}
        assert not _spectrum(tmp_path, frames, moved)["pass"], regression.__name__
    # Control: one frame more scatter than the cap fails; a frame set missing a placement fails.
    over = dict(frames)
    over["1"] = _scatter(frames["1"], 1)
    assert _spectrum(tmp_path, frames, over)["pass"]
    many = frames["1"].astype(np.int16)
    many[::2, ::2, :3] += 1
    over["1"] = many.astype(np.uint8)
    assert not _spectrum(tmp_path, frames, over)["pass"]


# ------------------------------------------------------------------------------------------------- spline curve

def test_devcurve_rule_b_explains_translucent_pixels_by_the_references_alpha(tmp_path):
    dc = _harness("devcurve_check")
    work = tmp_path / "work"
    work.mkdir()
    reference = _card()
    reference[70:90, 20:180, 3] = 128                           # a translucent stroke: the mask
    frames = {"0@1.0": reference.copy(), "1@1.5": reference.copy()}
    np.savez_compressed(work / "references.npz", **frames)
    np.savez_compressed(work / "native_opengl.npz", **frames)

    def verdict(transform):
        np.savez_compressed(work / "native_vulkan.npz", **{k: transform(v) for k, v in frames.items()})
        return dc.vulkan_against_opengl(tmp_path)["pass"]

    def stroke(image):
        out = image.copy()
        out[70:90, 20:180, :3] += 1
        return out

    assert verdict(lambda v: v)
    assert verdict(stroke)                                      # every translucent pixel one level off: explained
    # Controls: the same level on the opaque bar and the bare fill (a uniform shift), the artefact, the wild pixels.
    for regression in REGRESSIONS:
        assert not verdict(regression), regression.__name__
    assert not verdict(lambda v: _shift(stroke(v)))
    # Without its references (the mask's source) the rule cannot be judged: it fails.
    (work / "references.npz").unlink()
    assert not dc.vulkan_against_opengl(tmp_path)["pass"]


# ------------------------------------------------------------------------------------------ fullscreen pass

def test_fullscreen_pass_rule_b_is_a_share_of_the_frame_never_the_frame(tmp_path):
    fc = _harness("fullscreen_pass_check")
    work = tmp_path / "work"
    work.mkdir()
    photo = np.random.default_rng(5).integers(0, 255, (360, 640, 4), dtype=np.uint8)
    photo[..., 3] = 255
    frames = {"dpr1.0_burn_0.20": photo, "dpr1.0_uv_bits": photo}
    np.savez_compressed(work / "native_opengl.npz", **frames)

    def verdict(transform):
        np.savez_compressed(work / "native_vulkan.npz", **{k: transform(k, v) for k, v in frames.items()})
        return fc.vulkan_against_opengl(tmp_path)

    assert verdict(lambda k, v: v)["pass"]
    cap = fc.VULKAN_RULE_B.scatter_pixels

    def scatter(count):
        def apply(k, v):
            out = v.astype(np.int16)
            flat = out.reshape(-1, 4)
            flat[: count * 7 : 7, :3] += 1
            return np.clip(out, 0, 255).astype(np.uint8)
        return apply

    assert verdict(scatter(cap))["pass"]
    assert not verdict(scatter(cap + 1))["pass"]
    for regression in REGRESSIONS:
        assert not verdict(lambda k, v, r=regression: r(v))["pass"], regression.__name__
    assert not verdict(lambda k, v: _shift(v))["pass"]
    # The core's uv frames stay identical across the APIs: one pixel off in them is reported.
    one = lambda k, v: _scatter(v, 1) if k.endswith("_uv_bits") else v  # noqa: E731
    assert not verdict(one)["uv_bits_identical"]


# ----------------------------------------------------------------------------------------- background layer

def test_background_layer_rule_b_is_exact(tmp_path):
    blc = _harness("background_layer_check")
    work = tmp_path
    photo = np.random.default_rng(6).integers(0, 255, (120, 200, 4), dtype=np.uint8)
    photo[..., 3] = 255
    frames = {"landscape_fill@1.0": photo, "portrait_fit@1.5": photo}
    np.savez_compressed(work / "frames_opengl.npz", **frames)

    def verdict(transform):
        np.savez_compressed(work / "frames_vulkan.npz", **{k: transform(v) for k, v in frames.items()})
        return blc.vulkan_against_opengl(work)["pass"]

    assert verdict(lambda v: v)
    one = photo.copy()
    one[5, 5, :3] = np.clip(one[5, 5, :3].astype(np.int16) + 1, 0, 255).astype(np.uint8)
    assert not verdict(lambda v: one)                           # a single pixel one level off
    for regression in REGRESSIONS:
        assert not verdict(regression), regression.__name__


# ------------------------------------------------------------------------------------------ backdrop pyramid

def _levels(bp, size_of) -> dict:
    """A case's levels in the saved shape (``<case>|<level>``), each an opaque noisy picture of ``size_of(level)``."""
    rng = np.random.default_rng(8)
    out = {}
    for case in ("dark@1.0@dim0.0", "bright@1.5@dim0.0"):
        for name in bp.LEVEL_RULE_B:
            h, w = size_of(name)
            rows = rng.integers(0, 255, (h, w, 4), dtype=np.uint8)
            rows[..., 3] = 255
            out[f"{case}|{name}"] = rows
    return out


def test_backdrop_levels_rule_b_each_level_has_its_own_share(tmp_path):
    bp = _harness("backdrop_pyramid_check")
    work = tmp_path
    sizes = {name: (100, 200) for name in bp.LEVEL_RULE_B}
    sizes["thirty_second"] = (22, 40)                           # the smallest: a shift of all of it is under any other cap
    levels = _levels(bp, lambda name: sizes[name])
    np.savez_compressed(work / "levels_opengl.npz", **levels)

    def verdict(transform):
        np.savez_compressed(work / "levels_vulkan.npz", **{k: transform(k, v) for k, v in levels.items()})
        return bp.vulkan_levels_against_opengl(work)["pass"]

    assert verdict(lambda k, v: v)
    # The smallest level shifted whole stays under the largest level's pixel count: its own cap refuses it.
    assert bp.LEVEL_RULE_B["thirty_second"].scatter_pixels < bp.LEVEL_RULE_B["light"].scatter_pixels
    assert not verdict(lambda k, v: _shift(v) if k.endswith("|thirty_second") else v)
    assert not verdict(lambda k, v: _shift(v))
    for regression in REGRESSIONS:
        assert not verdict(lambda k, v, r=regression: r(v) if k.endswith("|light") else v), regression.__name__
    # A level the harness has no bound for fails.
    unknown = dict(levels)
    unknown["dark@1.0@dim0.0|surprise"] = levels["dark@1.0@dim0.0|light"]
    np.savez_compressed(work / "levels_opengl.npz", **unknown)
    np.savez_compressed(work / "levels_vulkan.npz", **unknown)
    assert not bp.vulkan_levels_against_opengl(work)["pass"]


def test_backdrop_levels_rule_a_and_cards_are_judged_pixel_by_pixel():
    bp = _harness("backdrop_pyramid_check")
    levels = _levels(bp, lambda name: (100, 200))
    native: dict = {}
    for key, rows in levels.items():
        case, name = key.rsplit("|", 1)
        native.setdefault(case, {})[name] = rows
    cases = list(native)
    assert bp.judge_levels_rule_a(native, native, cases)["pass"]
    moved = {c: {n: _shift(r) for n, r in lv.items()} for c, lv in native.items()}
    assert not bp.judge_levels_rule_a(moved, native, cases)["pass"]          # a uniform shift
    wild = {c: {n: (_wild(r) if n == "light" else r) for n, r in lv.items()} for c, lv in native.items()}
    assert not bp.judge_levels_rule_a(wild, native, cases)["pass"]
    # Cards: OpenGL native against today's is exact; the Vulkan cards' one-level pixels are capped per material.
    regions = {"dark": {m: _card() for m in bp.MATERIALS}}
    assert bp.judge_cards_rule_a(regions, regions)["pass"]
    nudged = {"dark": {m: _scatter(_card(), 1) for m in bp.MATERIALS}}
    assert not bp.judge_cards_rule_a(nudged, regions)["pass"]
    assert set(bp.CARD_RULE_B) == set(bp.MATERIALS)


# ----------------------------------------------------------------------------------------------- generic mode

def test_generic_mode_rule_b_is_exact(tmp_path):
    gc = _harness("generic_mode_check")
    work = tmp_path / "work"
    work.mkdir()
    frames = {"rings_dpr1.0": _card(), "glow": _card()}
    np.savez_compressed(work / "native_opengl.npz", **frames)

    def verdict(transform):
        np.savez_compressed(work / "native_vulkan.npz", **{k: transform(v) for k, v in frames.items()})
        return gc.vulkan_against_opengl(tmp_path)["pass"]

    assert verdict(lambda v: v)
    # One pixel one level off is already a difference: the frames are bit for bit the same on the two APIs.
    one = _card()
    one[5, 150, :3] += 1
    assert not verdict(lambda v: one)
    for regression in REGRESSIONS:
        assert not verdict(regression), regression.__name__
