"""How exactly two renders of one Extruded Spectrum frame agree (plan 1D.5, lead's decision of 12 Nov 2026).

At 8x multisampling (High 3D Detail with Smooth Edges: ``extruded_quality``), with Smooth Edges' ``fwidth`` edge
lines, the GPU does not resolve identical frames bit for bit: one edge pixel toggles by one 8-bit level between
them (measured 12 Nov 2026 on the RTX 4090: 25 of 239 repeats of one frame differed, 12 pixels in all, never by
more than one level; the same frame at 4x, Smooth Edges off or Balanced with Smooth Edges, was exact in all 240). It
is invisible. Exact-equality pixel checks at that setting therefore compare within one level; every other setting
stays exact.
"""
from __future__ import annotations

import numpy as np


def repeat_tolerance(parameters) -> int:
    """The per-channel levels by which two renders of one frame with ``parameters`` may differ: 1 at 8x
    multisampling, 0 (exact) otherwise. Derived from the renderer's own sample count."""
    from rendering.quick.visualizer.implementations.extruded_spectrum import extruded_quality

    samples, _mirror = extruded_quality(parameters)
    return 1 if samples >= 8 else 0


def same_render(first, second, parameters) -> bool:
    """``first`` and ``second`` (pixel arrays of one frame) are the same render: exactly, or within
    ``repeat_tolerance`` levels at 8x multisampling."""
    first, second = np.asarray(first, np.int16), np.asarray(second, np.int16)
    if first.shape != second.shape:
        return False
    return not first.size or int(np.abs(first - second).max()) <= repeat_tolerance(parameters)
