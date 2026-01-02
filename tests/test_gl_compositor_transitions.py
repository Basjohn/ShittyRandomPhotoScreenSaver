"""Parametrized coverage for compositor-driven GL transitions.

These tests consolidate the per-transition modules into a single suite that
asserts every compositor path avoids underlay leaks and blank frames while
running inside a lightweight QWidget hierarchy.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, List

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QWidget

from rendering.gl_compositor import GLCompositorWidget
from transitions.base_transition import BaseTransition
from transitions.gl_compositor_blinds_transition import GLCompositorBlindsTransition
from transitions.gl_compositor_blockflip_transition import GLCompositorBlockFlipTransition
from transitions.gl_compositor_blockspin_transition import GLCompositorBlockSpinTransition
from transitions.gl_compositor_crossfade_transition import GLCompositorCrossfadeTransition
from transitions.gl_compositor_diffuse_transition import GLCompositorDiffuseTransition
from transitions.gl_compositor_peel_transition import GLCompositorPeelTransition
from transitions.gl_compositor_raindrops_transition import GLCompositorRainDropsTransition
from transitions.gl_compositor_slide_transition import GLCompositorSlideTransition
from transitions.gl_compositor_wipe_transition import GLCompositorWipeTransition
from transitions.slide_transition import SlideDirection
from transitions.wipe_transition import WipeDirection
from tests._gl_test_utils import (
    fraction_dark_pixels,
    fraction_matching_color,
    solid_pixmap,
)


@pytest.fixture
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@dataclass(frozen=True)
class TransitionCase:
    """Metadata for a compositor transition test case."""

    name: str
    factory: Callable[[], BaseTransition]
    frames: int = 24
    wait_ms: int = 20
    dark_threshold: float = 0.7
    underlay_threshold: float = 0.05


def _wipe_case(direction: WipeDirection) -> TransitionCase:
    return TransitionCase(
        name=f"wipe-{direction.name.lower()}",
        factory=lambda direction=direction: GLCompositorWipeTransition(
            duration_ms=300,
            direction=direction,
            easing="Auto",
        ),
        frames=24,
    )


TRANSITION_CASES: List[pytest.param] = [
    pytest.param(
        TransitionCase(
            name="crossfade",
            factory=lambda: GLCompositorCrossfadeTransition(duration_ms=300, easing="Auto"),
            frames=20,
        ),
        id="crossfade",
    ),
    pytest.param(
        TransitionCase(
            name="slide-left",
            factory=lambda: GLCompositorSlideTransition(
                duration_ms=300, direction=SlideDirection.LEFT, easing="Auto"
            ),
            frames=24,
        ),
        id="slide-left",
    ),
    pytest.param(
        TransitionCase(
            name="blockflip",
            factory=lambda: GLCompositorBlockFlipTransition(
                duration_ms=400, grid_rows=4, grid_cols=6, flip_duration_ms=150
            ),
            frames=28,
        ),
        id="blockflip",
    ),
    pytest.param(
        TransitionCase(
            name="blockspin",
            factory=lambda: GLCompositorBlockSpinTransition(duration_ms=800, easing="Auto"),
            frames=28,
            dark_threshold=0.85,
        ),
        id="blockspin",
    ),
    pytest.param(
        TransitionCase(
            name="blinds",
            factory=lambda: GLCompositorBlindsTransition(duration_ms=400, slat_rows=5, slat_cols=7),
            frames=28,
        ),
        id="blinds",
    ),
    pytest.param(
        TransitionCase(
            name="diffuse",
            factory=lambda: GLCompositorDiffuseTransition(
                duration_ms=400, block_size=16, shape="Rectangle", easing="Auto"
            ),
            frames=28,
        ),
        id="diffuse",
    ),
    pytest.param(
        TransitionCase(
            name="peel",
            factory=lambda: GLCompositorPeelTransition(duration_ms=700, strips=10),
            frames=32,
            wait_ms=25,
        ),
        id="peel",
    ),
    pytest.param(
        TransitionCase(
            name="raindrops",
            factory=lambda: GLCompositorRainDropsTransition(duration_ms=700, easing="Auto"),
            frames=28,
        ),
        id="raindrops",
    ),
] + [
    pytest.param(_wipe_case(direction), id=f"wipe-{direction.name.lower()}")
    for direction in [
        WipeDirection.LEFT_TO_RIGHT,
        WipeDirection.RIGHT_TO_LEFT,
        WipeDirection.TOP_TO_BOTTOM,
        WipeDirection.BOTTOM_TO_TOP,
        WipeDirection.DIAG_TL_BR,
        WipeDirection.DIAG_TR_BL,
    ]
]


@pytest.mark.qt_no_exception_capture
@pytest.mark.parametrize("case", TRANSITION_CASES)
def test_gl_compositor_transitions_no_underlay_and_no_black(qapp, case: TransitionCase):
    """Every compositor transition should avoid underlay leaks and blank frames."""

    parent = QWidget()
    parent.resize(96, 96)
    palette = parent.palette()
    magenta = QColor(Qt.GlobalColor.magenta)
    palette.setColor(QPalette.ColorRole.Window, magenta)
    parent.setAutoFillBackground(True)
    parent.setPalette(palette)
    parent.show()

    comp = GLCompositorWidget(parent)
    comp.setGeometry(parent.rect())
    comp.show()
    setattr(parent, "_gl_compositor", comp)

    old_pm = solid_pixmap(96, 96, Qt.GlobalColor.red)
    new_pm = solid_pixmap(96, 96, Qt.GlobalColor.blue)
    comp.set_base_pixmap(old_pm)

    transition = case.factory()

    try:
        started = transition.start(old_pm, new_pm, parent)
    except Exception:
        started = False
    if not started:
        pytest.skip(f"{case.name} could not be started in this environment")

    try:
        comp.makeCurrent()
    except Exception:
        pytest.skip(f"GL context not available for GLCompositorWidget ({case.name})")

    frames = []
    for _ in range(case.frames):
        qapp.processEvents()
        frames.append(parent.grab().toImage())
        QTest.qWait(case.wait_ms)

    for img in frames:
        underlay_fraction = fraction_matching_color(img, magenta, tolerance=16)
        dark_fraction = fraction_dark_pixels(img, threshold=16)

        assert (
            underlay_fraction < case.underlay_threshold
        ), f"{case.name} underlay leak detected ({underlay_fraction:.2%})"
        assert (
            dark_fraction < case.dark_threshold
        ), f"{case.name} produced blank/very dark frame ({dark_fraction:.2%})"
