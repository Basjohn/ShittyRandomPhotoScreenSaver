"""3D Block Spins' Edge Glass: the slab's edges become polished glass showing the next
image, while the sheen and gloss stay and nothing else in the frame changes.

Offscreen GL through the transition capture harness; no window is shown.
"""
from __future__ import annotations

import math

import numpy as np
import pytest

from core.settings.default_contract import require_canonical_default
from rendering.gl_programs.blockspin_options import BLOCK_SPIN_EDGE_GLASS_CHOICES
from rendering.gl_programs.blockspin_program import (
    BLOCK_SPIN_THICKNESS,
    block_spin_edge_glass_mode,
    block_spin_progress,
)
from rendering.quick.transitions.parameter_resolution import resolve_block_spins_parameters
from tools.transition_contact_sheet import TransitionCapture

WIDTH, HEIGHT = 512, 288
_GLASS = tuple(choice for choice in BLOCK_SPIN_EDGE_GLASS_CHOICES if choice != "Off")


def _frames(capture, choice, progresses, direction="left"):
    run = capture.run("block_spins", direction=direction, duration_ms=8000,
                      settings={"blockspin": {"edge_glass": choice}})
    return run, [np.asarray(capture.render(run, p)[0], dtype=np.int16) for p in progresses]


def _side_faces(capture, run, progress) -> list[tuple[float, float]]:
    """Screen columns each side face covers for a spin about the vertical axis (2 px of slack)."""
    angle = math.pi * block_spin_progress(capture.frame(run, progress).sample.eased_progress)
    faces = []
    for side in (-1.0, 1.0):
        front = side * math.cos(angle)
        back = front + math.sin(angle) * BLOCK_SPIN_THICKNESS
        faces.append(((min(front, back) * 0.5 + 0.5) * WIDTH - 2, (max(front, back) * 0.5 + 0.5) * WIDTH + 2))
    return faces


@pytest.mark.qt
def test_edge_glass_changes_only_the_edges_and_keeps_the_sheen_and_gloss(qt_app):
    capture = TransitionCapture(WIDTH, HEIGHT)
    try:
        progresses = (0.4, 0.47, 0.5, 0.56)
        run, plain = _frames(capture, "Off", progresses)
        for choice in _GLASS:
            _run, glass = _frames(capture, choice, progresses)
            for progress, off, on in zip(progresses, plain, glass):
                # The sheen and gloss are drawn over the glass unchanged, so nothing gets darker.
                assert (on - off).min() >= -1, (choice, progress)
                # Only the side faces change: every changed column lies on one of them.
                changed = np.nonzero(np.abs(on - off).max(axis=(0, 2)) > 1)[0]
                faces = _side_faces(capture, run, progress)
                assert all(any(lo <= x <= hi for lo, hi in faces) for x in changed), (choice, progress)
            # Edge-on, the glass visibly shows the picture.
            index = progresses.index(0.5)
            assert np.abs(glass[index] - plain[index]).max() > 32, choice
    finally:
        capture.close()


@pytest.mark.qt
@pytest.mark.parametrize("choice", BLOCK_SPIN_EDGE_GLASS_CHOICES)
def test_edge_glass_keeps_exact_endpoints_on_every_axis(qt_app, choice):
    capture = TransitionCapture(256, 144)
    try:
        source, destination = (np.asarray(image, dtype=np.int16) for image in capture.images)
        for direction in ("left", "up", "diag_tl_br", "diag_tr_bl"):
            _run, (first, last) = _frames(capture, choice, (0.0, 1.0), direction)
            assert np.array_equal(first, source), direction
            assert np.array_equal(last, destination), direction
    finally:
        capture.close()


def test_edge_glass_resolves_from_the_page_and_repairs_unknown_values():
    canonical = require_canonical_default("transitions.blockspin")
    for choice in BLOCK_SPIN_EDGE_GLASS_CHOICES:
        section = {**canonical, "edge_glass": choice}
        assert resolve_block_spins_parameters({}, section, canonical)["edge_glass"] == choice
    for stored in ("Mirror", None, 3):
        section = {**canonical, "edge_glass": stored}
        assert resolve_block_spins_parameters({}, section, canonical)["edge_glass"] == canonical["edge_glass"]


def test_the_renderer_rejects_an_unresolved_edge_glass():
    assert [block_spin_edge_glass_mode(choice) for choice in BLOCK_SPIN_EDGE_GLASS_CHOICES] == list(
        range(len(BLOCK_SPIN_EDGE_GLASS_CHOICES)))
    with pytest.raises(ValueError, match="edge glass"):
        block_spin_edge_glass_mode("Mirror")
