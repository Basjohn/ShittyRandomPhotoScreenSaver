"""Actual driver pixels through the production transition host and run contract."""
from __future__ import annotations

import numpy as np
import pytest

from tools.transition_contact_sheet import TransitionCapture


@pytest.fixture
def capture(qt_app):
    result = TransitionCapture(256, 144)
    yield result
    result.close()


@pytest.mark.qt
@pytest.mark.parametrize("effect", [
    "glass_shatter", "exploding_tiles", "pixel_accretion",
    "ink_bloom", "tendril_reveal", "melt_drip", "slide", "crumble",
])
def test_driver_endpoints_continuity_repeatability_and_retirement(capture, effect):
    run = capture.run(effect)
    source, destination = (np.asarray(image, dtype=np.int16) for image in capture.images)
    frames = {t: np.asarray(capture.render(run, t)[0], dtype=np.int16)
              for t in (0., .0001, .28, .53, .78, .9999, 1.)}
    assert np.array_equal(frames[0.], source)
    assert np.array_equal(frames[1.], destination)
    # Endpoint branches alone must not conceal a first/last-frame pop.
    assert np.abs(frames[.0001]-source).mean() < .5
    assert np.abs(frames[.9999]-destination).mean() < .5
    assert np.abs(frames[.53]-source).mean() > 2
    assert np.abs(frames[.53]-destination).mean() > .25
    assert np.array_equal(np.asarray(capture.render(run, .53)[0]), frames[.53])
    assert capture.host.has_resources
    capture.host.set_enabled_transition_ids(())
    assert not capture.host.has_resources
    assert not capture.host.resolved_transition_ids


@pytest.mark.qt
@pytest.mark.parametrize("effect,field,value", [
    ("glass_shatter", "depth", 1.5),
    ("exploding_tiles", "depth", 1.5),
    ("pixel_accretion", "travel", .9),
    ("ink_bloom", "detail", 2.0),
    ("tendril_reveal", "detail", 2.0),
    ("melt_drip", "detail", 2.0),
])
def test_authored_controls_change_rendered_pixels(capture, effect, field, value):
    a = capture.render(capture.run(effect), .32)[0]
    b = capture.render(capture.run(effect, parameters={field: value}), .32)[0]
    assert np.abs(np.asarray(a, dtype=np.int16)-np.asarray(b, dtype=np.int16)).mean() > .1


@pytest.mark.qt
@pytest.mark.parametrize("effect", ["glass_shatter", "exploding_tiles", "pixel_accretion", "melt_drip"])
def test_direction_changes_actual_rendered_motion(capture, effect):
    left = capture.render(capture.run(effect, direction="left"), .32)[0]
    right = capture.render(capture.run(effect, direction="right"), .32)[0]
    assert np.abs(np.asarray(left, dtype=np.int16)-np.asarray(right, dtype=np.int16)).mean() > 2


@pytest.mark.qt
@pytest.mark.parametrize("effect", ["glass_shatter", "exploding_tiles", "pixel_accretion", "ink_bloom", "tendril_reveal", "melt_drip"])
def test_seed_affects_real_geometry_and_each_detail_limit_settles(capture, effect):
    a = capture.render(capture.run(effect, parameters={"seed": 112}), .32)[0]
    b = capture.render(capture.run(effect, parameters={"seed": 3099}), .32)[0]
    assert np.abs(np.asarray(a, dtype=np.int16)-np.asarray(b, dtype=np.int16)).mean() > .1
    if effect in {"ink_bloom", "tendril_reveal", "melt_drip"}:
        for detail in (.5, 2.0):
            run = capture.run(effect, parameters={"seed": 112, "detail": detail})
            first = np.asarray(capture.render(run, .0001)[0], dtype=np.int16)
            last = np.asarray(capture.render(run, .9999)[0], dtype=np.int16)
            assert np.abs(first-np.asarray(capture.images[0], dtype=np.int16)).mean() < .5
            assert np.abs(last-np.asarray(capture.images[1], dtype=np.int16)).mean() < .5


@pytest.mark.qt
@pytest.mark.parametrize("field", ("thickness", "transparency", "refraction", "dispersion", "sheen"))
def test_glass_optical_controls_independently_reach_the_rendered_surface(capture, field):
    # Enable the optical prerequisites so a zero refraction setting cannot
    # make a broken dispersion control appear to pass via some other change.
    optics = {"transparency": 1., "refraction": 1., "dispersion": 1., "sheen": 1., "thickness": 1.}
    a = capture.render(capture.run("glass_shatter", direction="center_out", parameters={**optics, field: 0.}), .38)[0]
    b = capture.render(capture.run("glass_shatter", direction="center_out", parameters={**optics, field: 1.}), .38)[0]
    assert np.abs(np.asarray(a, dtype=np.int16)-np.asarray(b, dtype=np.int16)).mean() > .02


@pytest.mark.qt
@pytest.mark.parametrize("effect", ("glass_shatter", "exploding_tiles"))
@pytest.mark.parametrize("size", ((160, 480), (720, 180)))
def test_complete_fracture_geometry_leaves_extreme_aspects_before_retirement(qt_app, effect, size):
    result = TransitionCapture(*size)
    try:
        destination = np.asarray(result.images[1], dtype=np.int16)
        # Exercise weakest launch / maximum thickness, especially an upward
        # departure against gravity and the furthest edge on a wide display.
        for direction in ("left", "right", "up", "down", "diag_tr_bl", "center_out"):
            run = result.run(effect, direction=direction, parameters={"force": .5, "thickness": 1., "depth": 1.5})
            last = np.asarray(result.render(run, .9999)[0], dtype=np.int16)
            assert np.abs(last-destination).mean() < .5, (effect, size, direction)
    finally:
        result.close()


@pytest.mark.qt
@pytest.mark.parametrize("effect", ("ink_bloom", "tendril_reveal"))
@pytest.mark.parametrize("field", ("depth", "gloss"))
def test_organic_material_controls_reach_the_rendered_geometry(capture,effect,field):
    a=np.asarray(capture.render(capture.run(effect,parameters={field:0.}),.40)[0],dtype=np.int16)
    b=np.asarray(capture.render(capture.run(effect,parameters={field:1.}),.40)[0],dtype=np.int16)
    assert np.abs(a-b).mean()>.02
