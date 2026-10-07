"""Sphere's selected three-zone analysis record for the shared FFT worker.

The FFT worker uses the first and penultimate interior boundary of a sorted
notch record. Its other interior notches belong to Spectrum's visual shaper;
Sphere stores only those two consumed fractions, so editing one cannot reveal
an unused shaper notch as a new analysis boundary.
"""
from __future__ import annotations

import math
from collections.abc import Sequence


def normalize_sphere_analysis_notches(value: object) -> list[list]:
    """Keep the exact consumed splits and canonical domain endpoints.

    A formerly selected Spectrum record may have more than four entries.
    Labels and unused interior notches carry no Sphere analysis meaning. Invalid
    authored input is an authority error; this resolver invents no replacement.
    """
    if not isinstance(value, (list, tuple)) or len(value) < 3:
        raise ValueError("Sphere analysis notches require endpoints and interior boundaries")
    positions = []
    for record in value:
        if not isinstance(record, Sequence) or isinstance(record, (str, bytes)) or len(record) != 2:
            raise ValueError("Sphere analysis notches require position/label records")
        try:
            position = float(record[0])
        except (TypeError, ValueError) as exc:
            raise ValueError("Sphere analysis notch positions must be numeric") from exc
        if not math.isfinite(position) or not 0.0 <= position <= 1.0:
            raise ValueError("Sphere analysis notch positions must be finite within 0..1")
        positions.append(position)
    positions.sort()
    return [[0.0, "Bass"], [positions[1], "Mid"], [positions[-2], "Treble"], [1.0, "End"]]
