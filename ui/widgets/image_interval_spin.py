"""The one "Change Image Every" control: Settings' Display tab and Guided Setup's Transitions page build it here."""
from __future__ import annotations

from PySide6.QtWidgets import QSpinBox

from core.settings.default_contract import (
    IMAGE_INTERVAL_MAX_SECONDS,
    IMAGE_INTERVAL_MIN_SECONDS,
    IMAGE_INTERVAL_STEP_SECONDS,
)

# The unit the control's value is shown in, beside it.
IMAGE_INTERVAL_UNIT = "Seconds"


def make_image_interval_spin(parent=None) -> QSpinBox:
    """A spin box over ``timing.interval``'s admitted range and step (``core.settings.default_contract``)."""
    spin = QSpinBox(parent)
    spin.setRange(IMAGE_INTERVAL_MIN_SECONDS, IMAGE_INTERVAL_MAX_SECONDS)
    spin.setSingleStep(IMAGE_INTERVAL_STEP_SECONDS)
    spin.setAccelerated(True)
    spin.setSuffix("")
    return spin
