"""Driver checks for the volume, gravity and continuous pinch-off of Melt."""

from __future__ import annotations

import numpy as np
import pytest
from PIL import Image
from tools.transition_contact_sheet import TransitionCapture


@pytest.mark.qt
@pytest.mark.parametrize("size", ((180, 480), (640, 160)))
@pytest.mark.parametrize("direction", ("down", "up", "left", "right"))
def test_liquid_volume_settles_without_an_endpoint_cut(qt_app, size, direction):
    capture = TransitionCapture(*size)
    try:
        for detail in (0.5, 2.0):
            run = capture.run(
                "melt_drip",
                direction=direction,
                parameters={"detail": detail, "depth": 1.0},
            )
            source, destination = (
                np.asarray(i, dtype=np.int16) for i in capture.images
            )
            assert (
                np.abs(
                    np.asarray(capture.render(run, 0.0001)[0], dtype=np.int16) - source
                ).mean()
                < 0.5
            )
            for t in (0.9949, 0.9951, 0.9999):
                assert (
                    np.abs(
                        np.asarray(capture.render(run, t)[0], dtype=np.int16)
                        - destination
                    ).mean()
                    < 0.5
                )
    finally:
        capture.close()


@pytest.mark.qt
@pytest.mark.parametrize("field", ("depth", "gloss"))
def test_liquid_material_controls_affect_the_actual_volume(qt_app, field):
    # A uniform material removes image contrast as a possible explanation for
    # the observed lighting: differences must come from geometry or shading.
    capture = TransitionCapture(
        320,
        180,
        Image.new("RGBA", (320, 180), (130, 160, 180, 255)),
        Image.new("RGBA", (320, 180), (0, 0, 0, 255)),
    )
    try:
        images = [
            np.asarray(
                capture.render(capture.run("melt_drip", parameters={field: v}), 0.43)[
                    0
                ],
                dtype=np.int16,
            )
            for v in (0.0, 1.0)
        ]
        assert np.abs(images[0] - images[1]).mean() > 0.5
        foreground = images[1][:, :, :3].max(axis=2) > 30
        assert images[1][:, :, :3][foreground].std() > 15
    finally:
        capture.close()


@pytest.mark.qt
def test_detached_liquid_moves_with_gravity_and_pinch_is_continuous(qt_app):
    capture = TransitionCapture(
        480,
        270,
        Image.new("RGBA", (480, 270), "white"),
        Image.new("RGBA", (480, 270), "black"),
    )
    try:
        run = capture.run("melt_drip", direction="down", seed=713)
        # At this stage the continuous film has left and only detached masses
        # remain. A fixed reveal mask cannot move those masses downward.
        masks = []
        for t in (0.72, 0.74):
            rgb = np.asarray(capture.render(run, t)[0])[:, :, :3]
            masks.append(rgb.max(axis=2) > 40)
        common_columns = masks[0].any(axis=0) & masks[1].any(axis=0)
        displacements = []
        for x in np.flatnonzero(common_columns):
            before = np.flatnonzero(masks[0][:, x])
            after = np.flatnonzero(masks[1][:, x])
            if (
                before.size > 3
                and after.size > 3
                and before[-1] < 265
                and after[-1] < 265
            ):
                displacements.append(after.mean() - before.mean())
        assert len(displacements) > 10
        assert np.median(displacements) > 1.0
        for t in (0.39, 0.43, 0.49, 0.55, 0.61, 0.67, 0.90, 0.995):
            a = np.asarray(capture.render(run, t - 0.0005)[0], dtype=np.int16)
            b = np.asarray(capture.render(run, t + 0.0005)[0], dtype=np.int16)
            assert np.abs(a - b).mean() < 3.0, t
    finally:
        capture.close()
