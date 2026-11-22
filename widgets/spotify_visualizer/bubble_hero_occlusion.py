"""Class-accurate 2D Bubble foreground occlusion, without a second render pass.

The logical snapshot supplies eight 32-bit words (two uvec4) identifying *actual* big
bubbles by their original hero index (not an inferred rendered-radius cutoff).
The shader shades each hero once, but composites the complete big-bubble class
in front of small-bubble bodies when they overlap. All physics, bodies, timing,
RGB styling, ghost and wake ownership remain with the existing Bubble paths.
"""
from __future__ import annotations

from typing import Iterable

from widgets.spotify_visualizer.bubble_viewport_profile import BUBBLE_RENDER_CAPACITY

MAX_HERO_BUBBLES = BUBBLE_RENDER_CAPACITY
BIG_CLASS_WORDS = 8
_ZERO_BIG_BITS = (0,) * BIG_CLASS_WORDS
_UINT32_MAX = (1 << 32) - 1


def pack_big_class_bits(bubbles: Iterable[object]) -> tuple[int, ...]:
    """Encode the indexed big/small identity for the authoritative hero order.

    Uses the canonical ``is_big`` flag, including promoted bubbles, and neither
    reads nor mutates visualizer simulation state. The resulting two uvec4
    (``u_big_class_bits``, ``u_big_class_bits_hi``) carry the class through the frame to the Bubble shader loop.
    """
    result = [0] * BIG_CLASS_WORDS
    for index, bubble in enumerate(bubbles):
        if index >= MAX_HERO_BUBBLES:
            raise ValueError(f'Bubble foreground class map exceeds {MAX_HERO_BUBBLES} heroes')
        if bool(bubble.is_big):
            result[index >> 5] |= 1 << (index & 31)
    return tuple(result)  # type: ignore[return-value]


def admit_big_class_bits(bits: object, bubble_count: int) -> tuple[int, ...]:
    """Check size, signedness, and no class bits outside the declared heroes. Four words (one uvec4, the 110-hero
    map's shape) are admitted as the first four of the eight, the rest zero."""
    if not isinstance(bits, (list, tuple)) or len(bits) not in (4, BIG_CLASS_WORDS):
        raise ValueError(f'Bubble foreground requires {BIG_CLASS_WORDS} (or four) uint32 class words')
    bits = tuple(bits) + (0,) * (BIG_CLASS_WORDS - len(bits))
    count = int(bubble_count)
    if count < 0 or count > MAX_HERO_BUBBLES:
        raise ValueError(f'Bubble foreground class count is outside its {MAX_HERO_BUBBLES}-hero limit')
    if any(not isinstance(x, int) or isinstance(x, bool) or not 0 <= x <= _UINT32_MAX for x in bits):
        raise ValueError('Bubble foreground class words must be uint32 integers')
    packed = tuple(bits)
    word = count >> 5
    tail_bits = count & 31
    if tail_bits:
        # All high bits within the partially used word must be clear.
        if packed[word] & (_UINT32_MAX ^ ((1 << tail_bits) - 1)):
            raise ValueError('Bubble foreground class bit exceeds the visible hero count')
        word += 1
    if any(packed[word:]):
        raise ValueError('Bubble foreground class bit exceeds the visible hero count')
    return packed  # type: ignore[return-value]


def composite_hero_layers(under, small, big, big_coverage: float):
    """Scalar reference for the GLSL foreground blend (not a CPU render path).

    Big heroes retain their exact original contribution against the existing
    gradient/wake/ghost base. Only the contribution from *small hero bodies* is
    hidden under an actual big-bubble silhouette. At zero big coverage, small
    bodies remain intact; at full coverage, the result is exactly the big layer.
    """
    coverage = max(0.0, min(1.0, float(big_coverage)))
    return tuple(
        b + (s - u) * (1.0 - coverage)
        for u, s, b in zip(under, small, big)
    )


__all__ = ['pack_big_class_bits', 'admit_big_class_bits', 'composite_hero_layers',
           'MAX_HERO_BUBBLES', 'BIG_CLASS_WORDS']
