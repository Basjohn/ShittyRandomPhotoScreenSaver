"""Pure presentation policy for all-or-none image generations.

A retained card/grid should not look half-broken while asynchronous artwork is
warming.  Image acquisition remains source-owned; this helper only decides
whether a complete visible generation may project its validated local sources.
"""
from __future__ import annotations

from collections.abc import Iterable


def coherent_image_sources(values: Iterable[object], *, enabled: bool = True) -> tuple[str, ...]:
    normalized = tuple(str(value or "").strip() for value in values)
    if not normalized:
        return ()
    if not enabled or not all(normalized):
        return ("",) * len(normalized)
    return normalized
