"""Volumetric Dissolve's Settings choices.

Import-safe for the Settings UI and the request resolver: the shader module
(``volumetric_dissolve_program``) loads only when Volumetric Dissolve renders.
"""

from __future__ import annotations

# Where the dissolve starts and the way it sweeps (labels say where the motion starts), or from
# the centre outward. Random picks one per run.
VOLUMETRIC_DIRECTIONS = {
    "Left to Right": "right",
    "Right to Left": "left",
    "Top to Bottom": "down",
    "Bottom to Top": "up",
    "Diagonal TL-BR": "diag_tl_br",
    "Diagonal TR-BL": "diag_tr_bl",
    "Diagonal BL-TR": "diag_bl_tr",
    "Diagonal BR-TL": "diag_br_tl",
    "Center Out": "center_out",
}
VOLUMETRIC_DIRECTION_CHOICES = (*VOLUMETRIC_DIRECTIONS, "Random")
VOLUMETRIC_PARTICLE_SIZE_RANGE = (2, 8)
