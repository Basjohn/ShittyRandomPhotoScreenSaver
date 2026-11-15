"""The scene targets' rules as the native core applies them (Current_Plan.md item 8b, N3.1; decision D14;
``native/core/src/scene_targets.h``), in Python: the reference the module's GPU-free entries are held to
(``tests/test_native_scene_targets.py``) and what a harness uses to place a target's content in a readback.

- Allocation (D14 point 2, choice A): 64 px buckets, each axis on its own; an axis grows at once, to the needed size's
  bucket, whenever the needed size passes it, and shrinks, to the needed size's bucket, only when the needed size falls
  two or more buckets below it (audit 2, L1: a grow on one axis never re-buckets the other one down); decided at the
  size edge, never by a timer.
- Placement (D14 point 2): the content sits at image rows ``[H-h, H)`` and columns ``[0, w)`` of the allocation (the
  Python renderer's GL bottom-left), so a read past the content's edge reads what the Python renderer's reads. QRhi's
  viewport counts from the framebuffer's bottom-left; on OpenGL the core's targets are flipped (F1: memory row 0 is the
  image's top), so its y is ``H - h`` there and ``0`` on every other backend.
- The clamp (D14 point 7): the largest supported count not above the request, 1 when there is none.
"""
from __future__ import annotations

from typing import Iterable

#: The allocation bucket (``kSceneBucket``), the Python renderer's ``SCENE_TARGET_BUCKET``.
SCENE_BUCKET = 64


def bucket_pixels(pixels: int) -> int:
    """``pixels`` rounded up to the bucket (at least one bucket)."""
    p = max(1, int(pixels))
    return max(SCENE_BUCKET, -(-p // SCENE_BUCKET) * SCENE_BUCKET)


def next_allocation(current: tuple[int, int], needed: tuple[int, int]) -> tuple[tuple[int, int], str]:
    """The allocation for ``needed`` given ``current`` ((0, 0): none yet), and why it changed ("" when it did not)."""
    bucketed = (bucket_pixels(needed[0]), bucket_pixels(needed[1]))
    if current[0] <= 0 or current[1] <= 0:
        return bucketed, "made"
    # Each axis on its own (audit 2, L1): a grow on one axis never re-buckets the other one down.
    grown = shrunk = False
    axes = []
    for have, need, bucket in zip(current, needed, bucketed):
        if need > have:
            grown = True
            axes.append(bucket)
        elif have - bucket >= 2 * SCENE_BUCKET:
            shrunk = True
            axes.append(bucket)
        else:
            axes.append(int(have))
    return (axes[0], axes[1]), "grown" if grown else "shrunk" if shrunk else ""


def content_viewport(y_up_in_framebuffer: bool, allocation: tuple[int, int],
                     content: tuple[int, int]) -> tuple[int, int, int, int]:
    """QRhi's viewport (x, y from the framebuffer's bottom-left, w, h) of ``content`` in ``allocation``."""
    width = min(int(content[0]), int(allocation[0]))
    height = min(int(content[1]), int(allocation[1]))
    return 0, (int(allocation[1]) - height) if y_up_in_framebuffer else 0, width, height


def content_rows(allocation: tuple[int, int], content: tuple[int, int]) -> tuple[int, int]:
    """The image rows (top first) the content occupies in its allocation: ``[H - h, H)``."""
    return int(allocation[1]) - int(content[1]), int(allocation[1])


def clamp_samples(supported: Iterable[int], requested: int) -> int:
    """The largest count in ``supported`` not above ``requested``; 1 when there is none."""
    best = 1
    for count in supported:
        if best < int(count) <= int(requested):
            best = int(count)
    return best


__all__ = ["SCENE_BUCKET", "bucket_pixels", "clamp_samples", "content_rows", "content_viewport", "next_allocation"]
