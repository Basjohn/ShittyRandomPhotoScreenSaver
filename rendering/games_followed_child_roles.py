"""Presentation-neutral, canonical grouped CUSTOM child roles for Games You Follow.

Kept outside Qt so eventual descriptor/admission can import exactly these identities
without activating a disabled presentation or Steam backend.
"""
from __future__ import annotations

from rendering.custom_child_geometry import CustomChildRoleDescriptor

# Stable steam_progress child identities; never one saved record per story.
FOLLOWED_CHILD_ROLES = (
    CustomChildRoleDescriptor(
        "header", minimum_scale=(0.65, 0.65), maximum_scale=(1.85, 1.85),
        uniform_scale=True, movable=True, alignment_flip=True,
        authored_alignment="left", semantic_corner_anchor=True,
    ),
    CustomChildRoleDescriptor(
        "refresh", minimum_scale=(0.65, 0.65), maximum_scale=(1.85, 1.85),
        uniform_scale=True, movable=True,
    ),
    CustomChildRoleDescriptor(
        "story_tiles", minimum_scale=(0.50, 0.55),
        maximum_scale=(1.70, 1.90), movable=True,
    ),
    CustomChildRoleDescriptor(
        "overflow_summary", minimum_scale=(0.50, 0.65),
        maximum_scale=(1.80, 1.80), movable=True,
    ),
)
