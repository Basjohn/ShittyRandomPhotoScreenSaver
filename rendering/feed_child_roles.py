"""One stable FEEDS Custom-child inventory, shared by descriptor and Qt model.

Article rows are intentionally represented by one stable ``articles`` group:
article identity and row count change with the feed and may never become saved
geometry keys. Repeated images likewise share one stable ``artwork`` role, so
its freeform geometry can reflow every painted row/card without persisting
volatile story IDs. The shared edit session owns persistence, undo, reset and
lock for these roles.
"""
from __future__ import annotations

from rendering.custom_child_geometry import (
    CustomChildRoleDescriptor,
    freeform_artwork_child_role,
    freeform_layout_block_child_role,
)

FEED_CONTENT_EXTENT_MINIMUM = (320.0, 180.0)

FEED_CUSTOM_CHILD_ROLES = (
    CustomChildRoleDescriptor(
        "header",
        axes=("horizontal", "vertical"),
        minimum_scale=(0.65, 0.65),
        maximum_scale=(1.85, 1.85),
        uniform_scale=True,
        movable=True,
        alignment_flip=True,
        authored_alignment="left",
        semantic_corner_anchor=True,
    ),
    CustomChildRoleDescriptor(
        "refresh", minimum_scale=(0.65, 0.65), maximum_scale=(1.85, 1.85),
        uniform_scale=True, movable=True,
    ),
    freeform_layout_block_child_role(
        "articles", minimum_scale=(0.50, 0.50), maximum_scale=(1.85, 1.85),
        movable=True,
    ),
    # One repeated artwork geometry contract controls every List/Grid image.
    # It deliberately remains a stable family role rather than persisting one
    # record per volatile article identity.  The QML proxy is representative;
    # every delegate consumes the same freeform width/height/offset factors and
    # locally reflows text around the resulting image rectangle.
    freeform_artwork_child_role(
        "artwork",
        minimum_scale=(0.35, 0.35),
        maximum_scale=(1.85, 1.85),
        movable=True,
    ),
    freeform_layout_block_child_role(
        "overflow", minimum_scale=(0.50, 0.65), maximum_scale=(1.85, 1.85),
        movable=True,
    ),
)
