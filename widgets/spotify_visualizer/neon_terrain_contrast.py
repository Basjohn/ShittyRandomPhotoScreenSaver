"""Eight activation-owned contrast slots, never a published raw-spectrum copy."""
from __future__ import annotations

import math
import threading


class NeonTerrainContrast:
    """Copy only derived scalars while the verified compute state is still owned.

    Analysis completion and logical capture use different threads. The small
    critical section prevents a capture mixing regions from different sources;
    neither producer nor consumer creates a per-frame container here.
    """

    def __init__(self) -> None:
        self._values = [0.0] * 8
        self._pending = [0.0] * 8
        self._lock = threading.Lock()

    def publish(self, spectrum, bars, *, mirrored: bool) -> None:
        count, raw_count = len(bars), len(spectrum)
        with self._lock:
            for region in range(8):
                numerator = denominator = 0.0
                lo, hi = region * count / 8.0, (region + 1) * count / 8.0
                if raw_count and count:
                    for index in range(math.floor(lo), min(count, math.ceil(hi))):
                        overlap = max(0.0, min(hi, index + 1) - max(lo, index))
                        weight = max(0.0, float(bars[index])) * overlap
                        if mirrored:
                            centre = (count - 1) * 0.5
                            coordinate = abs(index - centre) / max(centre, 1.0)
                        else:
                            coordinate = index / max(count - 1, 1)
                        position = coordinate * (raw_count - 1)
                        lower = int(position)
                        upper = min(lower + 1, raw_count - 1)
                        level = (float(spectrum[lower])
                                 + (float(spectrum[upper]) - float(spectrum[lower])) * (position - lower))
                        if not math.isfinite(level) or level < 0.0:
                            raise ValueError("Neon terrain analysis magnitude must be finite and non-negative")
                        numerator += weight * (0.30 + 0.70 * level / (0.45 + level))
                        denominator += weight
                self._pending[region] = numerator / denominator if denominator > 0.0 else 0.0
            for region in range(8):
                self._values[region] = self._pending[region]

    def apply_to(self, targets: list[float]) -> None:
        """Condition the existing authored targets in place, before hysteresis."""
        if len(targets) != 8:
            raise ValueError("Neon terrain contrast requires eight targets")
        with self._lock:
            for region in range(8):
                targets[region] *= self._values[region]
