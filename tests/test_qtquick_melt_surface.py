"""Driver checks for Melt's cohesive wet front and material response."""

from __future__ import annotations

import numpy as np
import pytest
from PIL import Image
from tools.transition_contact_sheet import TransitionCapture


@pytest.mark.qt
@pytest.mark.parametrize("size", ((180, 480), (640, 160)))
@pytest.mark.parametrize("direction", ("down", "up", "left", "right"))
def test_liquid_front_settles_without_an_endpoint_cut(qt_app, size, direction):
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
def test_liquid_material_controls_affect_the_wet_front(qt_app, field):
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
def test_viscous_film_keeps_irregular_fingers_attached_and_continuous(qt_app):
    capture = TransitionCapture(
        480,
        270,
        Image.new("RGBA", (480, 270), "white"),
        Image.new("RGBA", (480, 270), "black"),
    )
    try:
        run = capture.run("melt_drip", direction="down", seed=713)
        for t in (0.43, 0.55, 0.67):
            rgb = np.asarray(capture.render(run, t)[0])[:, :, :3]
            mask = rgb.max(axis=2) > 40
            edge_rows = []
            continuous_columns = 0
            occupied_columns = 0
            for x in range(mask.shape[1]):
                rows = np.flatnonzero(mask[:, x])
                if rows.size < 3:
                    continue
                occupied_columns += 1
                edge_rows.append(rows[-1])
                # With gravity down the source liquid is one attached film
                # descending from the top.  A detached sphere would create a
                # second island after an empty gap in one or more columns.
                if rows[0] <= 2 and np.diff(rows).max(initial=0) <= 2:
                    continuous_columns += 1
            assert occupied_columns > mask.shape[1] * 0.55
            assert continuous_columns / occupied_columns > 0.97
            # The film must have a visibly irregular hanging front, not a
            # straight wipe wearing a glossy material.
            assert np.std(edge_rows) > 2.0

        # Tiny time steps remain continuous across finger growth/drainage.
        for t in (0.31, 0.43, 0.55, 0.67, 0.82, 0.94):
            a = np.asarray(capture.render(run, t - 0.0005)[0], dtype=np.int16)
            b = np.asarray(capture.render(run, t + 0.0005)[0], dtype=np.int16)
            assert np.abs(a - b).mean() < 3.0, t
    finally:
        capture.close()


@pytest.mark.qt
@pytest.mark.parametrize(
    ("direction", "region"),
    (
        ("down", (slice(0, 60), slice(None))),
        ("up", (slice(120, 180), slice(None))),
        ("right", (slice(None), slice(0, 100))),
        ("left", (slice(None), slice(220, 320))),
    ),
)
def test_melt_preserves_source_pixels_well_behind_the_wet_front(
    qt_app, direction, region
):
    # Regression for the rejected 3D candidate, where horizontal Melt stretched
    # the entire source photograph into giant rectangular bands. The liquid
    # character must stay local to the moving meniscus; dry source remains the
    # source image at its original coordinates.
    width, height = 320, 180
    x = np.arange(width, dtype=np.uint8)[None, :]
    y = np.arange(height, dtype=np.uint8)[:, None]
    rgba = np.empty((height, width, 4), dtype=np.uint8)
    rgba[:, :, 0] = (x * 7 + y * 3) % 251
    rgba[:, :, 1] = (x * 3 + y * 11) % 253
    rgba[:, :, 2] = (x * 13 + y * 5) % 247
    rgba[:, :, 3] = 255
    source_image = Image.fromarray(rgba, "RGBA")
    destination_image = Image.new("RGBA", (width, height), (0, 0, 0, 255))
    capture = TransitionCapture(width, height, source_image, destination_image)
    try:
        run = capture.run(
            "melt_drip",
            direction=direction,
            seed=713,
            parameters={"detail": 1.4, "depth": 1.0, "gloss": 0.6},
        )
        rendered = np.asarray(capture.render(run, 0.43)[0], dtype=np.int16)
        source = np.asarray(source_image, dtype=np.int16)
        assert np.abs(rendered[region] - source[region]).mean() < 0.75
    finally:
        capture.close()
