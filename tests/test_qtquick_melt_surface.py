"""Driver checks for Melt: origin, gravity, untouched source and seamless field."""

from __future__ import annotations

import numpy as np
import pytest
from PIL import Image

import rendering.quick.transitions.implementations.melt_drip as melt_module
from tools.transition_contact_sheet import TransitionCapture

ORIGINS = ("top_left", "top_center", "top_right", "center_out", "center_in")


def _gradient_image(width, height):
    # Red rises down the frame, green is constant: content pulled down from
    # higher rows lowers red/green, while shading scales both channels alike.
    y = np.linspace(20, 235, height)[:, None]
    rgba = np.empty((height, width, 4), dtype=np.uint8)
    rgba[:, :, 0] = np.broadcast_to(y, (height, width)).astype(np.uint8)
    rgba[:, :, 1] = 128
    rgba[:, :, 2] = 90
    rgba[:, :, 3] = 255
    return Image.fromarray(rgba, "RGBA")


def _frame(capture, run, t):
    return np.asarray(capture.render(run, t)[0], dtype=np.int16)


@pytest.mark.qt
@pytest.mark.parametrize("size", ((180, 480), (640, 160)))
@pytest.mark.parametrize("origin", ORIGINS)
def test_melt_starts_exactly_on_the_source_and_settles_exactly(qt_app, size, origin):
    capture = TransitionCapture(*size)
    try:
        source, destination = (np.asarray(i, dtype=np.int16) for i in capture.images)
        for detail in (0.5, 2.0):
            run = capture.run(
                "melt_drip", direction=origin, parameters={"detail": detail, "depth": 1.0}
            )
            assert np.abs(_frame(capture, run, 0.0001) - source).mean() < 0.5
            # Every point has melted by 0.60 and drained by 0.94.
            for t in (0.9401, 0.97, 0.9999):
                assert np.array_equal(_frame(capture, run, t), destination), t
    finally:
        capture.close()


@pytest.mark.qt
@pytest.mark.parametrize(
    ("origin", "far_region"),
    (
        ("top_left", (slice(110, 180), slice(220, 320))),
        ("top_center", (slice(130, 180), slice(None))),
        ("top_right", (slice(110, 180), slice(0, 100))),
        ("center_out", (slice(0, 30), slice(0, 60))),
        ("center_in", (slice(70, 110), slice(130, 190))),
    ),
)
def test_points_the_melt_has_not_reached_are_the_untouched_source(
    qt_app, origin, far_region
):
    capture = TransitionCapture(320, 180)
    try:
        source = np.asarray(capture.images[0], dtype=np.int16)
        run = capture.run("melt_drip", direction=origin, seed=713)
        rendered = _frame(capture, run, 0.12)
        assert np.array_equal(rendered[far_region], source[far_region])
    finally:
        capture.close()


@pytest.mark.qt
@pytest.mark.parametrize("origin", ORIGINS)
def test_the_melt_starts_at_the_chosen_origin(qt_app, origin):
    width, height = 320, 180
    capture = TransitionCapture(width, height)
    try:
        source = np.asarray(capture.images[0], dtype=np.int16)
        run = capture.run("melt_drip", direction=origin, seed=713)
        changed = np.abs(_frame(capture, run, 0.20) - source).max(axis=2) > 12
        assert changed.mean() > 0.01
        ys, xs = np.nonzero(changed)
        cx, cy = xs.mean() / width, ys.mean() / height
        if origin == "top_left":
            assert cx < 0.4 and cy < 0.5
        elif origin == "top_right":
            assert cx > 0.6 and cy < 0.5
        elif origin == "top_center":
            assert 0.3 < cx < 0.7 and cy < 0.5
        elif origin == "center_out":
            assert 0.3 < cx < 0.7 and 0.25 < cy < 0.75
        else:
            border = np.ones_like(changed)
            border[30:-30, 50:-50] = False
            assert changed[border].mean() > 4 * changed[~border].mean()
    finally:
        capture.close()


@pytest.mark.qt
@pytest.mark.parametrize("origin", ("top_center", "center_out"))
def test_melted_paint_sags_downward_under_its_weight(qt_app, origin):
    image = _gradient_image(320, 180)
    capture = TransitionCapture(320, 180, image, image)
    try:
        source = np.asarray(image, dtype=np.float64)
        run = capture.run(
            "melt_drip", direction=origin, seed=713, parameters={"gloss": 0.0, "depth": 0.0}
        )
        rendered = np.asarray(capture.render(run, 0.30)[0], dtype=np.float64)
        moved = np.abs(rendered - source).max(axis=2) > 6
        assert moved.mean() > 0.05
        ratio = rendered[:, :, 0] / rendered[:, :, 1]
        original = source[:, :, 0] / source[:, :, 1]
        # Content shown in the melt came from higher (redder-is-lower) rows.
        assert (ratio[moved] - original[moved]).mean() < -0.05
    finally:
        capture.close()


@pytest.mark.qt
def test_melt_field_has_no_seams(qt_app, monkeypatch):
    # Regression: the melt-time noise used a chaotic float hash that gave one
    # lattice corner different values in neighbouring cells, cutting the
    # photograph into hard-edged rectangles and straight lines. Render the
    # production field itself and require it to be continuous.
    marker = "    float a=ageAt(screen,aspect);"
    source = melt_module.MELT_FRAGMENT_SOURCE
    assert source.count(marker) == 1
    monkeypatch.setattr(
        melt_module,
        "MELT_FRAGMENT_SOURCE",
        source.replace(
            marker,
            marker + "\n    FragColor=vec4(vec3(a)+1e-9*(uDepth+uGloss),1.);return;",
        ),
    )
    capture = TransitionCapture(320, 180)
    try:
        for origin in ORIGINS:
            for seed in (713, 4242):
                run = capture.run("melt_drip", direction=origin, seed=seed,
                                  parameters={"detail": 2.0})
                age = _frame(capture, run, 0.40)[:, :, 0]
                assert np.abs(np.diff(age, axis=0)).max() <= 24, (origin, seed)
                assert np.abs(np.diff(age, axis=1)).max() <= 24, (origin, seed)
    finally:
        capture.close()


@pytest.mark.qt
@pytest.mark.parametrize("field", ("depth", "gloss"))
def test_liquid_material_controls_affect_the_melt(qt_app, field):
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
            _frame(capture, capture.run("melt_drip", direction="top_center",
                                        parameters={field: v}), 0.40)
            for v in (0.0, 1.0)
        ]
        assert np.abs(images[0] - images[1]).mean() > 0.5
    finally:
        capture.close()


@pytest.mark.qt
@pytest.mark.parametrize("origin", ORIGINS)
def test_melt_is_continuous_in_time(qt_app, origin):
    capture = TransitionCapture(320, 180)
    try:
        run = capture.run("melt_drip", direction=origin, seed=713)
        for t in (0.05, 0.2, 0.35, 0.5, 0.65, 0.8, 0.93):
            a = _frame(capture, run, t - 0.0005)
            b = _frame(capture, run, t + 0.0005)
            assert np.abs(a - b).mean() < 3.0, t
    finally:
        capture.close()
