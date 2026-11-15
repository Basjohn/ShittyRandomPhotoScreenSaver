"""The block arena's layout (Current_Plan.md item 8b, N3.2; decision D15 point 3; ``native/core/src/mesh_buffers.h``
``arenaLayout``), mirrored GPU-free so a test can hold the core's plan to it.

Every block a content draws with (each pass's own, a batched pass's one copy a batch, the conventions, the clears', the
captures', the nearest resolves') lives in one ``Dynamic`` uniform buffer, each at an offset rounded up to the device's
uniform-buffer offset alignment (``QRhi::ubufAlignment()``: Vulkan's ``minUniformBufferOffsetAlignment``, 1 on OpenGL),
given per draw as a dynamic offset; the arena's size is rounded up to the alignment too.
"""
from __future__ import annotations

from typing import Sequence


def aligned(value: int, alignment: int) -> int:
    """``value`` rounded up to ``alignment`` (1 or more)."""
    alignment = max(1, int(alignment))
    return -(-int(value) // alignment) * alignment


def arena_layout(sizes: Sequence[int], alignment: int) -> tuple[list[int], int]:
    """Each block's offset in order, and the arena's size, for block ``sizes`` at ``alignment``."""
    offsets: list[int] = []
    offset = 0
    for size in sizes:
        if int(size) < 0:
            raise ValueError("a block's size is not negative")
        offset = aligned(offset, alignment)
        offsets.append(offset)
        offset += int(size)
    return offsets, aligned(offset, alignment)


__all__ = ["aligned", "arena_layout"]
