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
  that lies within float error of a half level. A share of the frame, never the frame: a uniform shift fails. Where
  a harness states its spread (``scatter_cluster_pixels``), no group of touching scatter and tie pixels may be larger
  (a tie joins the groups it touches), so a compact one-level patch or line fails however few its pixels; with a
  density bound (``scatter_window_pixels``) no ``SCATTER_WINDOW`` square window may hold more scatter and tie pixels.
  (Scatter never takes a tie's isolation away: the 17 Nov clause that did, for ties inside a one-level patch, was
  retired by the lead on 21 Nov once the joined groups and the density bound covered that case.)
- **Ties** (``tie_pixels``, ``tie_level``): every other pixel past its allowance. At most ``tie_pixels`` in a frame,
  each at most ``tie_level`` off (2; 3 only for the composite's edge class, ``COMPOSITE_EDGE_LEVEL``, proved per pixel
  in D12), and each isolated (no other pixel past its allowance among its eight neighbours) or on a content edge of the
  reference (its 3x3 neighbourhood spanning at least ``edge_contrast`` levels).
- **Flips** (``flip_pixels``; zero unless a lead's decision names them): a pixel past ``tie_level`` where a threshold
  of the shader ties, at most ``flip_pixels`` in a frame, isolated from every other pixel past its allowance, and on a
  content edge of the reference (a threshold can only tie where the reference itself changes abruptly). The one
  decision so far: Surface Tension's specular flip where pools pinch (D13, N5.2b), one pixel a frame.
- **Statistics** (``statistics``, a ``FrameStatistics``; the lead's decision for Waveform Ribbon, 22 Nov, N5.4): a
  whole 3D scene whose geometry the two paths place through different float arithmetic (the core's target clip against
  Python's viewport) flips whole rows of pixel centres where an edge runs along them, and its bloom and fog round in
  wide soft regions, so counts of pixels do not bound it. Its frame is judged by shares instead: the mean absolute and
  the mean signed difference (8-bit levels over every channel compared), the share of pixels 2 to 3 levels off and the
  share past 3. With ``statistics`` set these four are the frame's only reasons; the class counts are still reported.

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
#: The density window of the spread rule (checkpoint audit 8 M1): the most scatter and tie pixels any window of this
#: many device pixels a side may hold (``Tolerance.scatter_window_pixels``).
SCATTER_WINDOW = 16


@dataclass(frozen=True)
class FrameStatistics:
    """A frame's statistical bound (module docstring, "Statistics"): each figure at most this, over the frame."""

    mean_abs: float                     # mean |candidate - reference|, levels, every compared channel
    mean_signed: float                  # |mean (candidate - reference)|, levels
    tie_share: float                    # share of pixels whose largest channel is 2 to 3 levels off (0 to 1)
    flip_share: float                   # share of pixels past 3 levels (0 to 1)

    def __post_init__(self) -> None:
        if min(self.mean_abs, self.mean_signed, self.tie_share, self.flip_share) < 0:
            raise ValueError("a statistical bound is never negative")
        if max(self.tie_share, self.flip_share) > 1:
            raise ValueError("a share is at most the whole frame")


def frame_statistics(candidate, reference) -> dict:
    """The four figures ``FrameStatistics`` bounds, for two same-shaped 8-bit frames: their colour channels (an RGBA
    frame's alpha left out, as the bound was measured)."""
    import numpy as np

    diff = np.asarray(candidate).astype(np.int16) - np.asarray(reference).astype(np.int16)
    if diff.ndim == 3 and diff.shape[-1] == 4:
        diff = diff[..., :3]
    largest = np.abs(diff).max(axis=-1) if diff.ndim == 3 else np.abs(diff)
    pixels = max(1, largest.size)
    return {"mean_abs": float(np.abs(diff).mean()) if diff.size else 0.0,
            "mean_signed": float(diff.mean()) if diff.size else 0.0,
            "tie_share": float(((largest >= 2) & (largest <= 3)).sum()) / pixels,
            "flip_share": float((largest > 3).sum()) / pixels}


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
    #: Scatter's spread (checkpoint audit 7 M1): the largest 8-connected group of scatter pixels a frame may hold (None:
    #: no spread rule, the count alone). Groups are taken over scatter and ties together (checkpoint audit 8 M1): a tie
    #: joins the groups it touches instead of splitting a line in two, so ties inside a one-level patch fail with it.
    scatter_cluster_pixels: int | None = None
    #: Scatter's density (checkpoint audit 8 M1; needs ``scatter_cluster_pixels``): the most scatter and tie pixels any
    #: ``SCATTER_WINDOW`` x ``SCATTER_WINDOW`` window may hold (None: no density bound), so a one-level patch dithered
    #: into small groups fails.
    scatter_window_pixels: int | None = None
    #: The statistical bound (module docstring, "Statistics"; None: the classes above judge the frame).
    statistics: FrameStatistics | None = None

    def __post_init__(self) -> None:
        if self.masked_level not in (0, 1):
            raise ValueError("the explained class is one level at most")
        cap = COMPOSITE_EDGE_LEVEL if self.edge_class else TIE_LEVEL
        if not 0 <= self.tie_level <= cap:
            raise ValueError(f"a tie is at most {cap} levels off")
        if min(self.scatter_pixels, self.tie_pixels, self.flip_pixels) < 0:
            raise ValueError("counts are never negative")
        if self.scatter_cluster_pixels is not None and not 1 <= self.scatter_cluster_pixels <= self.scatter_pixels:
            raise ValueError("a scatter group is at least one pixel and at most the scatter allowance")
        if self.scatter_window_pixels is not None and (self.scatter_cluster_pixels is None
                                                        or self.scatter_window_pixels < 1):
            raise ValueError("a density bound is at least one pixel and belongs to a stated spread")

    def bound(self) -> dict:
        bound = {"name": self.name, "masked_level": self.masked_level, "scatter_pixels": self.scatter_pixels,
                 "tie_pixels": self.tie_pixels, "tie_level": self.tie_level, "flip_pixels": self.flip_pixels,
                 "edge_contrast": self.edge_contrast}
        if self.scatter_cluster_pixels is not None:
            bound["scatter_cluster_pixels"] = self.scatter_cluster_pixels
        if self.scatter_window_pixels is not None:
            bound["scatter_window_pixels"] = self.scatter_window_pixels
            bound["scatter_window"] = SCATTER_WINDOW
        if self.statistics is not None:
            bound["statistics"] = {"mean_abs": self.statistics.mean_abs, "mean_signed": self.statistics.mean_signed,
                                   "tie_share": self.statistics.tie_share, "flip_share": self.statistics.flip_share}
        return bound


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


def content_edges_at(reference, flags, contrast: float = EDGE_CONTRAST):
    """``content_edges`` read only at the pixels of ``flags`` (bool, the frame's shape): the same answer there, False
    elsewhere. The judge reads edges only at its ties and flips, so it asks here for those (fast-proof part 2, step 1:
    the whole-frame neighbourhood was 59 of the judge's 76 s on a 10 s Bubble take)."""
    import numpy as np

    ref = np.asarray(reference)
    flags = np.asarray(flags, bool)
    out = np.zeros(flags.shape, bool)
    ys, xs = np.nonzero(flags)
    if not len(ys):
        return out
    h, w = ref.shape[:2]
    # The 3x3 neighbourhood with the edges replicated (``_neighbourhood``'s pad mode), gathered at the flagged pixels.
    window = np.stack([ref[np.clip(ys + dy, 0, h - 1), np.clip(xs + dx, 0, w - 1)].astype(np.float64)
                       for dy in (-1, 0, 1) for dx in (-1, 0, 1)])
    edge = (window.max(axis=0) - window.min(axis=0)) >= contrast
    out[ys, xs] = edge if edge.ndim == 1 else edge.any(axis=1)
    return out


def _has_neighbour(flags):
    """Pixels with another flagged pixel among their eight neighbours."""
    import numpy as np

    flags = np.asarray(flags, bool)
    padded = np.pad(flags.astype(np.int16), 1)
    h, w = flags.shape
    count = sum(padded[dy:dy + h, dx:dx + w] for dy in range(3) for dx in range(3)) - flags.astype(np.int16)
    return count > 0


def _largest_group_by_runs(flags) -> int:
    """``largest_group`` without SciPy: each row's runs of flagged pixels, joined (union-find) to the runs of the row
    above that touch them 8-connected (column ranges overlapping by one either side). Its work grows with the runs, not
    the pixels: a frame whose every pixel differs (a one-level shift) is a run a row, where a per-pixel flood fill took
    a second a frame (21 Nov)."""
    import numpy as np

    h, w = flags.shape
    padded = np.zeros((h, w + 2), np.int8)
    padded[:, 1:-1] = flags
    edges = np.diff(padded, axis=1)
    rows_s, starts = np.nonzero(edges == 1)            # run starts (column of the first flagged pixel)
    rows_e, ends = np.nonzero(edges == -1)             # run ends (one past the last flagged pixel)
    sizes = (ends - starts).tolist()
    rows, starts, ends = rows_s.tolist(), starts.tolist(), ends.tolist()
    parent = list(range(len(sizes)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    previous: list[int] = []                           # the runs of the row above (indices), in column order
    current: list[int] = []
    row = None
    for index, y in enumerate(rows):
        if y != row:
            previous = current if row is not None and y == row + 1 else []
            current, row, cursor = [], y, 0
        current.append(index)
        # Runs above overlapping [start - 1, end + 1): both lists are in column order, so a cursor walks them once.
        while cursor < len(previous) and ends[previous[cursor]] < starts[index]:
            cursor += 1
        probe = cursor
        while probe < len(previous) and starts[previous[probe]] <= ends[index]:
            a, b = find(index), find(previous[probe])
            if a != b:
                parent[a] = b
            probe += 1
    totals: dict[int, int] = {}
    for index, size in enumerate(sizes):
        root = find(index)
        totals[root] = totals.get(root, 0) + size
    return max(totals.values(), default=0)


def largest_group(flags) -> int:
    """The pixel count of the largest 8-connected group of ``flags`` (0 when none)."""
    import numpy as np

    flags = np.asarray(flags, bool)
    if not flags.any():
        return 0
    try:
        from scipy import ndimage
    except ImportError:
        return _largest_group_by_runs(flags)
    labels, count = ndimage.label(flags, structure=np.ones((3, 3), bool))
    return int(np.bincount(labels.ravel())[1:].max()) if count else 0


def densest_window(flags, size: int = SCATTER_WINDOW) -> int:
    """The most ``flags`` any ``size`` x ``size`` window holds (a frame smaller than the window: the whole frame)."""
    import numpy as np

    flags = np.asarray(flags, bool)
    if not flags.any():
        return 0
    h, w = flags.shape
    sy, sx = min(size, h), min(size, w)
    total = np.zeros((h + 1, w + 1), np.int64)
    total[1:, 1:] = flags.astype(np.int64).cumsum(axis=0).cumsum(axis=1)
    windows = total[sy:, sx:] - total[:-sy, sx:] - total[sy:, :-sx] + total[:-sy, :-sx]
    return int(windows.max())


def judge_delta(delta, tolerance: Tolerance, *, mask=None, edges=None) -> dict:
    """One frame's verdict from its per-pixel difference ``delta`` (int: 8-bit levels, or the unit the harness states),
    the explained ``mask`` (bool; None: no pixel) and the reference's content ``edges`` (bool; None: none; or a function
    of the pixels it is read at, ``content_edges_at``: only ties and flips are ever read)."""
    import numpy as np

    delta = np.asarray(delta)
    shape = delta.shape
    mask = np.zeros(shape, bool) if mask is None else np.asarray(mask, bool)
    past = delta > np.where(mask, tolerance.masked_level, 0)
    scatter = past & ~mask & (delta == 1) if tolerance.scatter_pixels else np.zeros(shape, bool)
    rest = past & ~scatter
    if callable(edges):
        edges = edges(rest)
    edges = np.zeros(shape, bool) if edges is None else np.asarray(edges, bool)
    tie = rest & (delta <= tolerance.tie_level)
    flip = rest & ~tie
    spread = tolerance.scatter_cluster_pixels is not None
    # Isolated: no other pixel past its allowance (a tie or a flip) among its eight neighbours; scatter never counts.
    lonely = ~_has_neighbour(rest)
    placed = lonely | edges
    flip_ok = flip & lonely & edges
    counts = {"scatter": int(scatter.sum()), "ties": int(tie.sum()), "flips": int(flip.sum())}
    reasons = []
    if counts["scatter"] > tolerance.scatter_pixels:
        reasons.append(f"{counts['scatter']} pixels one level off outside the mask (scatter: at most "
                       f"{tolerance.scatter_pixels})")
    if spread:
        # Ties join the groups they touch (checkpoint audit 8 M1: two ties split a one-level line into passing thirds).
        joined = scatter | tie
        counts["scatter_group"] = largest_group(joined)
        if counts["scatter_group"] > tolerance.scatter_cluster_pixels:
            reasons.append(f"a group of {counts['scatter_group']} touching scatter and tie pixels (scatter is spread: "
                           f"groups of at most {tolerance.scatter_cluster_pixels})")
        counts["scatter_window"] = densest_window(joined)
        window = tolerance.scatter_window_pixels
        if window is not None and counts["scatter_window"] > window:
            reasons.append(f"{counts['scatter_window']} scatter and tie pixels in one {SCATTER_WINDOW} x "
                           f"{SCATTER_WINDOW} window (at most {window})")
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


def judge(candidate, reference, tolerance: Tolerance, *, mask=None, delta=None) -> dict:
    """``judge_delta`` for two 8-bit frames of one shape (the channels the harness compares); the content edges are
    the reference's own, read only where the judge reads them (``content_edges_at``). ``delta``: ``levels`` of the
    two, when the caller has it already. A shape mismatch fails."""
    import numpy as np

    a = np.asarray(candidate)
    b = np.asarray(reference)
    if a.shape != b.shape:
        return {"pass": False, "reasons": [f"shapes differ: {list(a.shape)} {list(b.shape)}"], "differing": -1,
                "max_level": None, "masked_differing": 0, "mask_pixels": 0, "scatter": -1, "ties": -1, "flips": -1}
    delta = levels(a, b) if delta is None else delta
    contrast = tolerance.edge_contrast
    verdict = judge_delta(delta, tolerance, mask=mask, edges=lambda flags: content_edges_at(b, flags, contrast))
    bound = tolerance.statistics
    if bound is None:
        return verdict
    # The statistical bound: the four shares are the frame's only reasons; the class counts stay reported.
    figures = frame_statistics(a, b)
    reasons = []
    if figures["mean_abs"] > bound.mean_abs:
        reasons.append(f"mean difference {figures['mean_abs']:.4f} levels (at most {bound.mean_abs})")
    if abs(figures["mean_signed"]) > bound.mean_signed:
        reasons.append(f"mean signed difference {figures['mean_signed']:+.4f} levels (within {bound.mean_signed})")
    if figures["tie_share"] > bound.tie_share:
        reasons.append(f"{100 * figures['tie_share']:.3f}% of pixels 2 to 3 levels off (at most "
                       f"{100 * bound.tie_share:.3f}%)")
    if figures["flip_share"] > bound.flip_share:
        reasons.append(f"{100 * figures['flip_share']:.3f}% of pixels past 3 levels (at most "
                       f"{100 * bound.flip_share:.3f}%)")
    return dict(verdict, **figures, pass_classes=verdict["pass"], class_reasons=verdict["reasons"], reasons=reasons,
                **{"pass": not reasons})


def peer_mask(*masks):
    """Rule (b)'s mask (the lead's decision, 21 Nov; D12 "The pixel tolerance"): rule (b) judges two peer backends,
    neither of them the reference, so its explained class is the union of what the mode's mask marks in each frame (and
    in the reference, where the harness has one), never one side's alone. A pixel the class covers on either side may
    move by the class's level: the Oscilloscope's glow lights a faint fringe pixel on one backend that the other's
    discard cut leaves dark (checkpoint audit 10 L1). ``None`` masks (a side whose frame cannot show the class) are
    skipped; ``None`` when every one is."""
    import numpy as np

    given = [np.asarray(m, bool) for m in masks if m is not None]
    if not given:
        return None
    union = given[0].copy()
    for m in given[1:]:
        union |= m
    return union


def lit(frame):
    """The pixels a frame lights (any colour channel above 0; an opaque readback over black): the frame-side form of
    a mask class of "every pixel a blended layer sums into" (the Oscilloscope's glow)."""
    import numpy as np

    return np.asarray(frame)[..., :3].max(axis=-1) > 0


def translucent_by_alpha(reference, *, additive: bool = False):
    """The explained pixels of a reference drawn into a target cleared to zero: alpha strictly between 0 and 255 (a
    translucent result), or with ``additive`` every pixel a layer added to (alpha above 0: each sum rounds per layer)."""
    import numpy as np

    alpha = np.asarray(reference)[..., 3]
    return (alpha > 0) if additive else ((alpha > 0) & (alpha < 255))


def translucent_by_backgrounds(first, second, second_background, first_background):
    """The translucent pixels of a reference drawn twice, over its own background (``first``) and over the uniform
    colour ``second_background`` (``second``; RGB): the pixels the background shows through (they differ between the
    two draws) that are not bare. A pixel is bare (nothing drawn) only if it equals its own background in every draw
    (lead's decision, 21 Nov): the second background in ``second`` and ``first_background`` in ``first`` (what the
    first draw shows where nothing is drawn: an RGB colour, or a frame of ``first``'s shape). Content faded so far that
    it rounds to the second background in one draw is still content where the other draw shows it (Spectrum's
    switch fade: 13-22 over its card fill of 12, exactly magenta over the magenta second background). Opaque content
    and bare background stay out."""
    import numpy as np

    a = np.asarray(first)[..., :3]
    b = np.asarray(second)[..., :3]
    under = np.asarray(first_background)
    under = under[..., :3] if under.ndim == a.ndim else under[:3]
    showing = (a != b).any(axis=2)
    bare = (b == np.asarray(second_background, dtype=b.dtype)[:3]).all(axis=2) & (a == under).all(axis=2)
    return showing & ~bare


def summarise(frames) -> dict:
    """Many frames' verdicts as one: pass when every frame passes, with the worst figures and the first reasons."""
    frames = list(frames)
    failed = [f for f in frames if not f.get("pass")]
    return {"pass": not failed, "frames": len(frames), "frames_failed": len(failed),
            "max_level": max((f.get("max_level") or 0 for f in frames), default=0),
            "masked_differing_worst_frame": max((f.get("masked_differing", 0) for f in frames), default=0),
            "mask_pixels_largest_frame": max((f.get("mask_pixels", 0) for f in frames), default=0),
            "scatter_worst_frame": max((f.get("scatter", 0) for f in frames), default=0),
            "scatter_group_worst_frame": max((f.get("scatter_group", 0) for f in frames), default=0),
            "scatter_window_worst_frame": max((f.get("scatter_window", 0) for f in frames), default=0),
            "ties_worst_frame": max((f.get("ties", 0) for f in frames), default=0),
            "flips_worst_frame": max((f.get("flips", 0) for f in frames), default=0),
            **({"mean_abs_worst_frame": max(f.get("mean_abs", 0.0) for f in frames),
                "mean_signed_worst_frame": max((abs(f.get("mean_signed", 0.0)) for f in frames), default=0.0),
                "tie_share_worst_frame": max(f.get("tie_share", 0.0) for f in frames),
                "flip_share_worst_frame": max(f.get("flip_share", 0.0) for f in frames)}
               if any("mean_abs" in f for f in frames) else {}),
            "first_reasons": [r for f in failed[:3] for r in f.get("reasons", [])]}
