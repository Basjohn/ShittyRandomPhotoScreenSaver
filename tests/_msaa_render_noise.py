"""Repeat renders through a 4x MSAA scene target are not bit-identical on the development GPU (side defect 5 Nov).

Measured with every input proven identical (ribbon packet and uniforms, every vertex position, the reduced fields and
fog volumes, the reflection target and all four depth samples): the multisampled colour still differs from one render
of the same frame to the next by up to 3/255 per sample on a small share of samples (Neon Lake: ~3k of ~313k pixels per
render; Waveform: a pixel or two), resolving to 1 level (rarely 2-3) on the shown pixel. The same scenes rendered
single-sample are exact, so this is the driver's multisampled rasterization, not renderer state; an exact equality or a
one-level bound on such renders is a flaky oracle. ``assert_same_msaa_render`` keeps the oracle strict where it
matters: a handful of quantization flips pass, a real change (anything leaking between contexts or snapshots) does not.
"""
from __future__ import annotations

import numpy as np

# Largest per-channel change one flipped sample can make after the resolve (measured 3/255 per sample), and the share
# of pixels that may carry such flips (measured below 1%).
MSAA_NOISE_LEVELS = 3
MSAA_NOISE_SHARE = 0.02


def msaa_render_difference(a, b) -> tuple[int, float]:
    """(largest channel difference, share of pixels that differ at all) between two RGBA renders."""
    difference = np.abs(np.asarray(a, dtype=np.int32) - np.asarray(b, dtype=np.int32))
    differing = difference.max(axis=-1) > 0
    return int(difference.max(initial=0)), float(differing.mean()) if differing.size else 0.0


def assert_same_msaa_render(a, b) -> None:
    largest, share = msaa_render_difference(a, b)
    assert largest <= MSAA_NOISE_LEVELS and share <= MSAA_NOISE_SHARE, (
        f"renders differ beyond multisample quantization noise: {largest} levels on {share:.2%} of pixels")
