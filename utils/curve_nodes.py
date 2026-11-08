"""Smooth node-curve sampling, shared by the shape editors (Settings/Studio) and the renderers that bake their
curves (Neon Lake's terrain shaper). Pure Python: the visualizer engine worker bakes curves without importing
any Settings widget (native core P2)."""
from __future__ import annotations

from typing import List


def interpolate_nodes(nodes: List[List[float]], num_samples: int) -> List[float]:
    """Smoothly interpolate node control points into a sampled curve.

    Args:
        nodes: Sorted list of [x, y] pairs, x in [0,1], y in [0,1].
        num_samples: Number of output samples.

    Returns:
        List of *num_samples* floats in [0, 1].
    """
    if not nodes:
        return [0.5] * num_samples
    if len(nodes) == 1:
        return [max(0.0, min(1.0, nodes[0][1]))] * num_samples

    xs = [n[0] for n in nodes]
    ys = [n[1] for n in nodes]

    result: List[float] = []
    for i in range(num_samples):
        t = i / max(1, num_samples - 1)
        if t <= xs[0]:
            result.append(ys[0])
        elif t >= xs[-1]:
            result.append(ys[-1])
        else:
            for j in range(len(xs) - 1):
                if xs[j] <= t <= xs[j + 1]:
                    seg_len = xs[j + 1] - xs[j]
                    if seg_len < 1e-9:
                        result.append(ys[j])
                    else:
                        frac = (t - xs[j]) / seg_len
                        frac = frac * frac * (3.0 - 2.0 * frac)
                        result.append(ys[j] + (ys[j + 1] - ys[j]) * frac)
                    break
            else:
                result.append(ys[-1])
    return result


def interpolate_nodes_mirrored(nodes: List[List[float]], num_bars: int) -> List[float]:
    """Produce a full mirrored bar-height profile from half-range nodes.

    Nodes define the center-to-edge profile.  This function samples
    *num_bars* values where bar 0 is the left edge, center is the middle,
    and bar num_bars-1 is the right edge.  Both halves mirror the same
    node curve.
    """
    half = num_bars // 2
    half_samples = interpolate_nodes(nodes, max(2, half + 1))
    result: List[float] = []
    center_pos = (float(num_bars) - 1.0) * 0.5
    max_dist = max(center_pos, 1.0)
    for i in range(num_bars):
        dist = abs(float(i) - center_pos)
        sample_pos = (dist / max_dist) * float(len(half_samples) - 1)
        idx0 = int(sample_pos)
        idx1 = min(idx0 + 1, len(half_samples) - 1)
        frac = max(0.0, min(1.0, sample_pos - float(idx0)))
        result.append(half_samples[idx0] + (half_samples[idx1] - half_samples[idx0]) * frac)
    # Smooth the center bar so it doesn't dip below its mirrored
    # neighbors when the node curve starts at a local minimum.
    center = num_bars // 2
    if num_bars % 2 == 1 and num_bars >= 3 and center > 0:
        result[center] = max(result[center], (result[center - 1] + result[center + 1]) * 0.5)
    return result
