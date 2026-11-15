"""One pixel tolerance for every native parity harness (D12, "The pixel tolerance"; checkpoint audit 3 M1, audit 4 M2).

A candidate frame (the native core's) is judged against its reference (the Python renderer's, or the other backend's)
pixel by pixel, never by a histogram of levels:

- **Exact** everywhere, opaque content and background included, except the classes below. Each class is bounded by
  the harness's measured worst and its reason, never by "any pixel within a level".
- **The explained class** (``masked_level``, 1): only on the pixels of ``mask``, which the harness derives from the
  reference itself: the translucent pixels (``translucent_by_backgrounds``: the reference drawn over two backgrounds;
  ``translucent_by_alpha``: the reference's own alpha in a target cleared to zero), or the pixels a blended layer
  sums into. There the extra rounding of a premultiplied surface or of a blended layer may move a pixel by one level,
  on any number of them.
- **Scatter** (``scatter_pixels``): pixels outside the mask exactly one level off, at most ``scatter_pixels`` in a
  frame: two compilers (the Python renderer's GLSL and the core's pack, or two backends' drivers) rounding a value
  that lies within float error of a half level. A share of the frame, never the frame: a uniform shift fails.
- **Ties** (``tie_pixels``, ``tie_level``): every other pixel past its allowance. At most ``tie_pixels`` in a frame,
  each at most ``tie_level`` off (2; 3 only for the composite's edge class, ``COMPOSITE_EDGE_LEVEL``, proved per pixel
  in D12), and each isolated (no other pixel past its allowance among its eight neighbours) or on a content edge of the
  reference (its 3x3 neighbourhood spanning at least ``edge_contrast`` levels).
- **Flips** (``flip_pixels``; zero unless a lead's decision names them): a pixel past ``tie_level`` where a threshold
  of the shader ties, at most ``flip_pixels`` in a frame, isolated from every other pixel past its allowance, and on a
  content edge of the reference (a threshold can only tie where the reference itself changes abruptly). The one
  decision so far: Surface Tension's specular flip where pools pinch (D13, N5.2b), one pixel a frame.

Harness code only: no product path imports it.
"""
from __future__ import annotations

from dataclasses import dataclass

#: The 3x3 range (largest channel, 8-bit levels) of the reference that makes a pixel a content edge.
EDGE_CONTRAST = 32
#: Ties are at most this far off (8-bit levels) ...
TIE_LEVEL = 2
#: ... except the composite's edge class (D12: float32 interpolation between the core's triangle and the Python quad
#: over a premultiplied surface, measured at 3).
COMPOSITE_EDGE_LEVEL = 3


@dataclass(frozen=True)
class Tolerance:
    """A harness's admitted residual. Each number is a measured worst whose reason the harness states beside it."""

    name: str
    masked_level: int = 0
    scatter_pixels: int = 0
    tie_pixels: int = 0
    tie_level: int = TIE_LEVEL
    flip_pixels: int = 0
    edge_class: bool = False            # the composite's edge class: ties up to COMPOSITE_EDGE_LEVEL
    edge_contrast: float = EDGE_CONTRAST

    def __post_init__(self) -> None:
        if self.masked_level not in (0, 1):
            raise ValueError("the explained class is one level at most")
        cap = COMPOSITE_EDGE_LEVEL if self.edge_class else TIE_LEVEL
        if not 0 <= self.tie_level <= cap:
            raise ValueError(f"a tie is at most {cap} levels off")
        if min(self.scatter_pixels, self.tie_pixels, self.flip_pixels) < 0:
            raise ValueError("counts are never negative")

    def bound(self) -> dict:
        return {"name": self.name, "masked_level": self.masked_level, "scatter_pixels": self.scatter_pixels,
                "tie_pixels": self.tie_pixels, "tie_level": self.tie_level, "flip_pixels": self.flip_pixels,
                "edge_contrast": self.edge_contrast}


#: Bit for bit.
EXACT = Tolerance("exact")


def levels(candidate, reference):
    """Per pixel, the largest channel difference of two same-shaped arrays (int)."""
    import numpy as np

    a = np.asarray(candidate)
    b = np.asarray(reference)
    if a.shape != b.shape:
        raise ValueError(f"shapes differ: {a.shape} {b.shape}")
    delta = np.abs(a.astype(np.int32) - b.astype(np.int32))
    return delta if delta.ndim == 2 else delta.max(axis=2)


def _neighbourhood(array, reduce):
    """``reduce`` (np.maximum or np.minimum) over each pixel's 3x3 neighbourhood (edges replicated)."""
    import numpy as np

    padded = np.pad(array, [(1, 1), (1, 1)] + [(0, 0)] * (array.ndim - 2), mode="edge")
    h, w = array.shape[:2]
    out = padded[1:1 + h, 1:1 + w].copy()
    for dy in range(3):
        for dx in range(3):
            out = reduce(out, padded[dy:dy + h, dx:dx + w])
    return out


def content_edges(reference, contrast: float = EDGE_CONTRAST):
    """The reference's content edges: pixels whose 3x3 neighbourhood spans at least ``contrast`` in some channel."""
    import numpy as np

    ref = np.asarray(reference).astype(np.float64)
    span = _neighbourhood(ref, np.maximum) - _neighbourhood(ref, np.minimum)
    edge = span >= contrast
    return edge if edge.ndim == 2 else edge.any(axis=2)


def _has_neighbour(flags):
    """Pixels with another flagged pixel among their eight neighbours."""
    import numpy as np

    flags = np.asarray(flags, bool)
    padded = np.pad(flags.astype(np.int16), 1)
    h, w = flags.shape
    count = sum(padded[dy:dy + h, dx:dx + w] for dy in range(3) for dx in range(3)) - flags.astype(np.int16)
    return count > 0


def judge_delta(delta, tolerance: Tolerance, *, mask=None, edges=None) -> dict:
    """One frame's verdict from its per-pixel difference ``delta`` (int: 8-bit levels, or the unit the harness states),
    the explained ``mask`` (bool; None: no pixel) and the reference's content ``edges`` (bool; None: none)."""
    import numpy as np

    delta = np.asarray(delta)
    shape = delta.shape
    mask = np.zeros(shape, bool) if mask is None else np.asarray(mask, bool)
    edges = np.zeros(shape, bool) if edges is None else np.asarray(edges, bool)
    past = delta > np.where(mask, tolerance.masked_level, 0)
    scatter = past & ~mask & (delta == 1) if tolerance.scatter_pixels else np.zeros(shape, bool)
    rest = past & ~scatter
    tie = rest & (delta <= tolerance.tie_level)
    flip = rest & ~tie
    lonely = ~_has_neighbour(rest)
    placed = lonely | edges
    flip_ok = flip & lonely & edges
    counts = {"scatter": int(scatter.sum()), "ties": int(tie.sum()), "flips": int(flip.sum())}
    reasons = []
    if counts["scatter"] > tolerance.scatter_pixels:
        reasons.append(f"{counts['scatter']} pixels one level off outside the mask (scatter: at most "
                       f"{tolerance.scatter_pixels})")
    if counts["ties"] > tolerance.tie_pixels:
        reasons.append(f"{counts['ties']} ties (at most {tolerance.tie_pixels})")
    stray = int((tie & ~placed).sum())
    if stray:
        reasons.append(f"{stray} ties neither isolated nor on a content edge")
    if counts["flips"] > tolerance.flip_pixels:
        reasons.append(f"{counts['flips']} pixels past {tolerance.tie_level} levels (flips admitted: "
                       f"{tolerance.flip_pixels})")
    elif counts["flips"] and int(flip_ok.sum()) != counts["flips"]:
        reasons.append(f"{counts['flips'] - int(flip_ok.sum())} pixels past {tolerance.tie_level} levels that are not "
                       "isolated on a content edge")
    differing = delta > 0
    return {"pass": not reasons, "reasons": reasons, "differing": int(differing.sum()),
            "max_level": int(delta.max()) if delta.size else 0, "masked_differing": int((differing & mask).sum()),
            "mask_pixels": int(mask.sum()), **counts}


def judge(candidate, reference, tolerance: Tolerance, *, mask=None) -> dict:
    """``judge_delta`` for two 8-bit frames of one shape (the channels the harness compares); the content edges are
    the reference's own. A shape mismatch fails."""
    import numpy as np

    a = np.asarray(candidate)
    b = np.asarray(reference)
    if a.shape != b.shape:
        return {"pass": False, "reasons": [f"shapes differ: {list(a.shape)} {list(b.shape)}"], "differing": -1,
                "max_level": None, "masked_differing": 0, "mask_pixels": 0, "scatter": -1, "ties": -1, "flips": -1}
    delta = levels(a, b)
    edges = content_edges(b, tolerance.edge_contrast) if delta.any() else None
    return judge_delta(delta, tolerance, mask=mask, edges=edges)


def translucent_by_alpha(reference, *, additive: bool = False):
    """The explained pixels of a reference drawn into a target cleared to zero: alpha strictly between 0 and 255 (a
    translucent result), or with ``additive`` every pixel a layer added to (alpha above 0: each sum rounds per layer)."""
    import numpy as np

    alpha = np.asarray(reference)[..., 3]
    return (alpha > 0) if additive else ((alpha > 0) & (alpha < 255))


def translucent_by_backgrounds(first, second, second_background):
    """The translucent pixels of a reference drawn twice, over its own background (``first``) and over the uniform
    colour ``second_background`` (``second``; RGB): the pixels the background shows through (they differ between the
    two draws) that are not the bare second background (nothing drawn). Opaque content and bare background stay out."""
    import numpy as np

    a = np.asarray(first)[..., :3]
    b = np.asarray(second)[..., :3]
    showing = (a != b).any(axis=2)
    bare = (b == np.asarray(second_background, dtype=b.dtype)[:3]).all(axis=2)
    return showing & ~bare


def summarise(frames) -> dict:
    """Many frames' verdicts as one: pass when every frame passes, with the worst figures and the first reasons."""
    frames = list(frames)
    failed = [f for f in frames if not f.get("pass")]
    return {"pass": not failed, "frames": len(frames), "frames_failed": len(failed),
            "max_level": max((f.get("max_level") or 0 for f in frames), default=0),
            "masked_differing_worst_frame": max((f.get("masked_differing", 0) for f in frames), default=0),
            "scatter_worst_frame": max((f.get("scatter", 0) for f in frames), default=0),
            "ties_worst_frame": max((f.get("ties", 0) for f in frames), default=0),
            "flips_worst_frame": max((f.get("flips", 0) for f in frames), default=0),
            "first_reasons": [r for f in failed[:3] for r in f.get("reasons", [])]}
