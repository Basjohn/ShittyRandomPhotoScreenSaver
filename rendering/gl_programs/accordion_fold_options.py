"""Accordion Fold's Settings choices.

Import-safe for the Settings UI and the request resolver: the shader module
(``accordion_fold_program``) loads only when Accordion Fold renders.
"""

from __future__ import annotations

# The edge the picture folds up against. Random picks one per run.
ACCORDION_EDGES = {"Left": "left", "Right": "right", "Top": "top", "Bottom": "bottom"}
ACCORDION_EDGE_CHOICES = (*ACCORDION_EDGES, "Random")
ACCORDION_PLEATS_RANGE = (4, 16)
