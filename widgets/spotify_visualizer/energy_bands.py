"""Frequency-band energy extraction for audio-reactive visualizers.

Derives bass, mid, high, and overall energy values from the existing
per-bar FFT magnitudes produced by ``_fft_to_bars()``.  These are cheap
to compute — just weighted averages over frequency ranges — and are
consumed by the starfield, blob, and helix shaders.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from core.logging.logger import get_logger

logger = get_logger(__name__)


@dataclass(slots=True)
class EnergyBands:
    """Frequency-band energy snapshot (all values 0..1)."""
    bass: float = 0.0
    mid: float = 0.0
    high: float = 0.0
    overall: float = 0.0


def extract_energy_bands(bars: Sequence[float]) -> EnergyBands:
    """Derive energy bands from a list of FFT bar magnitudes.

    The bar list is split into three frequency regions:
      - **Bass:**  first 25% of bars
      - **Mid:**   25%–60%
      - **High:**  60%–100%
      - **Overall:** RMS of all bars

    Each band value is the average magnitude in that region, clamped
    to [0, 1].  Returns an ``EnergyBands`` dataclass.
    """
    n = len(bars)
    if n == 0:
        return EnergyBands()

    # Split points
    bass_end = max(1, n * 25 // 100)
    mid_end = max(bass_end + 1, n * 60 // 100)

    bass_sum = 0.0
    mid_sum = 0.0
    high_sum = 0.0
    overall_sq = 0.0

    for i in range(n):
        v = float(bars[i])
        if v < 0.0:
            v = 0.0
        if v > 1.0:
            v = 1.0
        overall_sq += v * v

        if i < bass_end:
            bass_sum += v
        elif i < mid_end:
            mid_sum += v
        else:
            high_sum += v

    bass_count = bass_end
    mid_count = mid_end - bass_end
    high_count = max(1, n - mid_end)

    bass = min(1.0, bass_sum / bass_count) if bass_count > 0 else 0.0
    mid = min(1.0, mid_sum / mid_count) if mid_count > 0 else 0.0
    high = min(1.0, high_sum / high_count) if high_count > 0 else 0.0

    # RMS overall energy
    overall = min(1.0, (overall_sq / n) ** 0.5) if n > 0 else 0.0

    return EnergyBands(bass=bass, mid=mid, high=high, overall=overall)
