"""Liquid Lens: a small thick lens glides in, then spreads to cover the picture even at its narrowest
wobble before its water flattens (the dome a true spherical cap thinning as it spreads); the water's timeline matches its GLSL on the GPU, and through the production host on a
real offscreen context (no window): exact and continuous ends from every origin, the lens comes in
from the side it names, the new picture shows inside it and the old one outside, Refraction and
droplets change only what they own, warm-up leaves the first frames nothing to compile, and the
resolver."""
from __future__ import annotations

import math
import random

import numpy as np
import pytest

from rendering.gl_programs.liquid_lens_options import LIQUID_LENS_ORIGINS
from rendering.gl_programs.liquid_lens_program import (
    LENS_BULGE,
    LENS_FLATTEN,
    LENS_GROW_END,
    LENS_SIZE,
    LENS_SPREAD,
    LENS_WOBBLE,
    LIQUID_LENS_GLSL,
    lens_centre,
    lens_cover,
    lens_cap,
    lens_envelope,
    lens_glide,
    lens_height,
    lens_meniscus,
    lens_path,
    lens_radius,
    lens_thickness,
)
from rendering.quick.transitions.parameter_resolution import resolve_parameterized_phase_c_inputs
from tools.transition_contact_sheet import TransitionCapture

W, H = 320, 180
ASPECT = W / H
_PLAIN = {"liquid_lens": {"droplets": False}}


def test_the_lens_covers_the_picture_before_its_water_flattens():
    assert LENS_GROW_END <= LENS_FLATTEN[0] + 0.02 and LENS_FLATTEN[1] < 1.0
    for origin in LIQUID_LENS_ORIGINS.values():
        start, end = lens_path(origin, ASPECT)
        cover = lens_cover(end, ASPECT)
        narrowest = lens_radius(cover, LENS_GROW_END) * (1.0 - sum(LENS_WOBBLE) - LENS_BULGE)
        centre = lens_centre(start, end, LENS_GROW_END)
        for cx in (-ASPECT / 2, ASPECT / 2):
            for cy in (-0.5, 0.5):
                assert math.hypot(cx - centre[0], cy - centre[1]) < narrowest
    assert lens_height(0.0) == 0.0 and lens_height(LENS_FLATTEN[1]) == 0.0 and lens_height(0.999) == 0.0
    assert lens_height(0.4) > 0.0 and lens_meniscus(0.0) == 0.0 and lens_meniscus(1.0) == 1.0
    cover = lens_cover(lens_path("left", ASPECT)[1], ASPECT)
    radii = [lens_radius(cover, p) for p in np.linspace(0.0, 1.0, 200)]
    assert all(b >= a for a, b in zip(radii, radii[1:]))
    # A small lens while it glides, as thick as half its radius, thinning once it spreads.
    assert lens_radius(cover, LENS_SPREAD) == pytest.approx(LENS_SIZE) and LENS_SIZE < 0.25
    assert lens_thickness(cover, LENS_SPREAD) == pytest.approx(0.5 * LENS_SIZE)
    assert lens_thickness(cover, LENS_GROW_END) < 0.05 * lens_thickness(cover, LENS_SPREAD)


def test_the_dome_is_a_spherical_cap_that_stays_exact_as_it_flattens():
    reach, thick = 0.2, 0.1
    big = (reach * reach + thick * thick) / (2 * thick)
    for u in (0.0, 0.3, 0.7, 0.99):
        assert lens_cap(reach, thick, u) == pytest.approx(math.sqrt(big * big - (u * reach) ** 2) - (big - thick))
    assert lens_cap(reach, thick, 1.0) == 0.0 and lens_cap(reach, 0.0, 0.5) == 0.0
    # Nearly flat it is the parabola it tends to, with no cancellation.
    assert lens_cap(1.5, 1e-6, 0.4) == pytest.approx(1e-6 * (1 - 0.16), rel=1e-4)


@pytest.mark.qt
def test_the_timeline_matches_its_mirror_on_the_gpu(qt_app):
    from tests.test_scene3d_glsl_mirrors import _GlslProbe, _check

    probe = _GlslProbe()
    try:
        progress = list(np.linspace(0.0, 1.0, 64))
        gpu = probe.run("float t = arg(0).x; FragColor = vec4(lensRadius(1.6, t), lensGlide(t), lensEnvelope(t), "
                        "lensThickness(1.6, t) * 10.0 + lensCap(0.2, 0.1, t) + lensMeniscus(t));",
                        [[(p,)] for p in progress], declarations=LIQUID_LENS_GLSL)
        _check(gpu, [(lens_radius(1.6, p), lens_glide(p), lens_envelope(p),
                      lens_thickness(1.6, p) * 10.0 + lens_cap(0.2, 0.1, p) + lens_meniscus(p)) for p in progress])
    finally:
        probe.close()


@pytest.fixture
def capture(qt_app):
    capture = TransitionCapture(W, H)
    yield capture
    capture.close()


def _pixels(image) -> np.ndarray:
    return np.asarray(image.convert("RGB"), dtype=np.int16)


@pytest.mark.qt
@pytest.mark.parametrize("origin", tuple(LIQUID_LENS_ORIGINS.values()))
def test_ends_are_exact_and_continuous(capture, origin):
    run = capture.run("liquid_lens", direction=origin, duration_ms=5000)
    source, destination = _pixels(capture.images[0]), _pixels(capture.images[1])
    assert np.array_equal(_pixels(capture.render(run, 0.0)[0]), source)
    assert np.array_equal(_pixels(capture.render(run, 1.0)[0]), destination)
    assert np.abs(_pixels(capture.render(run, 0.995)[0]) - destination).mean() < 0.5
    assert np.abs(_pixels(capture.render(run, 0.01)[0]) - source).mean() < 0.5


@pytest.mark.qt
@pytest.mark.parametrize("origin,sign", (("left", (-1, 0)), ("right", (1, 0)), ("top", (0, -1)), ("bottom", (0, 1))))
def test_the_lens_comes_in_from_its_side_showing_the_new_picture(capture, origin, sign):
    run = capture.run("liquid_lens", direction=origin, settings=_PLAIN, duration_ms=5000)
    source, destination = _pixels(capture.images[0]), _pixels(capture.images[1])
    frame = _pixels(capture.render(run, 0.3)[0])
    changed = np.abs(frame - source).max(axis=2) > 0
    ys, xs = np.nonzero(changed)
    assert 0.05 < changed.mean() < 0.7
    offset = ((xs.mean() - W / 2) / W, (ys.mean() - H / 2) / H)        # screen, y down
    assert offset[0] * sign[0] + offset[1] * sign[1] > 0.1
    # Around the lens centre the new picture shows through the water.
    centre = lens_centre(*lens_path(origin, ASPECT), 0.3)
    cx, cy = int((centre[0] / ASPECT + 0.5) * W), int((0.5 - centre[1]) * H)
    patch = np.s_[cy - 6:cy + 6, cx - 6:cx + 6]
    assert np.abs(frame[patch] - destination[patch]).mean() < np.abs(frame[patch] - source[patch]).mean()


@pytest.mark.qt
def test_refraction_and_droplets_change_only_what_they_own(capture):
    def frame(progress=0.35, **section):
        run = capture.run("liquid_lens", direction="left", settings={"liquid_lens": {"droplets": False, **section}},
                          duration_ms=5000)
        return _pixels(capture.render(run, progress)[0])

    flat, strong = frame(refraction=0.0), frame(refraction=1.0)
    source = _pixels(capture.images[0])
    outside = np.all(flat == source, axis=2) & np.all(strong == source, axis=2)
    assert outside.any() and (np.abs(flat - strong).max(axis=2) > 8).any()
    wet = frame(droplets=True)
    changed = np.abs(wet - frame()).max(axis=2) > 0
    assert changed.any() and changed.mean() < 0.05                  # a scatter of small drops


@pytest.mark.qt
def test_warmed_runs_compile_nothing_on_their_first_frames(qt_app, monkeypatch):
    from tests.test_transition_warmup import _Work

    capture = TransitionCapture(256, 144)
    try:
        work = _Work(monkeypatch)
        run = capture.run("liquid_lens", direction="center", duration_ms=4000)
        parameters, size = run.request.parameter_dict(), (capture.width, capture.height)
        steps = 0
        while not capture.host.warm_step("liquid_lens", parameters, size):
            steps += 1
            assert work.total <= steps and steps < 10
        warmed = work.total
        for progress in (0.0, 0.3, 0.6, 1.0):
            capture.render(run, progress)
        assert work.total == warmed
        renderer = capture.host._implementations["liquid_lens"]
        capture.host.park()
        renderer.release_resources()
        assert not renderer.has_resources
    finally:
        capture.close()


def test_the_resolver_picks_origins_and_repairs_values():
    seen = {resolve_parameterized_phase_c_inputs("liquid_lens", {}, random_source=random.Random(seed)).direction
            for seed in range(80)}
    assert seen == set(LIQUID_LENS_ORIGINS.values())
    resolved = resolve_parameterized_phase_c_inputs(
        "liquid_lens", {"liquid_lens": {"direction": "Top Left", "refraction": 7, "dispersion": -1,
                                        "droplets": False}},
        random_source=random.Random(1))
    assert resolved.direction == "top_left"
    params = resolved.parameter_dict()
    assert params["refraction"] == 1.0 and params["dispersion"] == 0.0 and params["droplets"] is False
