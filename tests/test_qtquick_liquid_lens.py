"""Liquid Lens: the plan starts in the middle and hops between seeded pitstops that keep the lens
inside the picture, growing at each, then floods from the chosen stop past every corner; the dome
is an exact spherical cap; the shader's helpers equal their mirrors on the GPU; and through the
production host on a real offscreen context (no window): exact and continuous ends, the lens
appears in the middle showing the new picture, it is at its planned stop with the new picture at
its centre, ripples run out from it while the far picture stays untouched, Refraction changes only
the lens, warm-up leaves the first frames nothing to compile, the resolver, and the retired
origin and droplets settings leave stored profiles."""
from __future__ import annotations

import math
import random

import numpy as np
import pytest

from rendering.gl_programs.liquid_lens_options import LIQUID_LENS_STOPS_RANGE
from rendering.gl_programs.liquid_lens_program import (
    LENS_BULGE,
    LENS_FLATTEN,
    LENS_MARGIN,
    LENS_SPREAD,
    LENS_WOBBLE,
    LIQUID_LENS_GLSL,
    lens_cap,
    lens_envelope,
    lens_meniscus,
    lens_plan,
    lens_state,
    lens_twist_angle,
)
from rendering.quick.transitions.parameter_resolution import resolve_parameterized_phase_c_inputs
from tools.transition_contact_sheet import TransitionCapture

W, H = 320, 180
ASPECT = W / H
DURATION_S = 8.0


def _ends_of_dwells(plan):
    return [end for kind, _index, _start, end in plan.segments if kind == "dwell"]


@pytest.mark.parametrize("stops", range(LIQUID_LENS_STOPS_RANGE[0], LIQUID_LENS_STOPS_RANGE[1] + 1))
def test_the_plan_starts_in_the_middle_hops_inside_the_picture_and_floods_past_every_corner(stops):
    for seed in (1, 77, 4242):
        plan = lens_plan(stops, seed, ASPECT)
        assert len(plan.stops) == stops and plan.stops[0] == (0.0, 0.0)
        assert len(plan.radii) == max(1, stops - 1)
        assert all(b > a for a, b in zip(plan.radii, plan.radii[1:]))           # larger at each pitstop
        for index, (x, y) in enumerate(plan.stops[1:], start=1):
            radius = plan.radii[min(index, len(plan.radii) - 1)]
            assert abs(x) + radius <= ASPECT / 2 - LENS_MARGIN + 1e-9 and abs(y) + radius <= 0.5 - LENS_MARGIN + 1e-9
            assert math.dist(plan.stops[index - 1], (x, y)) > 0.12                 # a real hop
        assert plan.segments[-1][3] == pytest.approx(LENS_SPREAD[0])
        # The flood covers every corner at its narrowest wobble and stretch.
        last = plan.stops[-1]
        narrowest = plan.cover * (1.0 - sum(LENS_WOBBLE) - LENS_BULGE)
        assert all(math.dist(last, (cx, cy)) < narrowest for cx in (-ASPECT / 2, ASPECT / 2) for cy in (-0.5, 0.5))
    assert lens_plan(stops, 5, ASPECT) == lens_plan(stops, 5, ASPECT)              # seeded, repeatable
    if stops > 2:
        assert lens_plan(stops, 5, ASPECT).stops != lens_plan(stops, 6, ASPECT).stops


def test_the_lens_settles_at_each_stop_and_its_size_only_steps_up_between_hops():
    plan = lens_plan(5, 9, ASPECT)
    for index, end in enumerate(_ends_of_dwells(plan)):
        state = lens_state(plan, end - 1e-4, DURATION_S)
        assert state.centre == plan.stops[index]
        assert state.radius == pytest.approx(plan.radii[index], rel=0.03)            # settled after its spring
    sizes = [lens_state(plan, t, DURATION_S).radius for t in np.linspace(0.0, LENS_SPREAD[0], 400)]
    settled = [lens_state(plan, end - 1e-4, DURATION_S).radius for end in _ends_of_dwells(plan)]
    assert all(b > a for a, b in zip(settled, settled[1:])) and max(sizes) < 0.35
    hop = next(segment for segment in plan.segments if segment[0] == "hop")
    moving = lens_state(plan, (hop[2] + hop[3]) / 2, DURATION_S)
    assert moving.twist != 0.0 and 0.0 < math.hypot(*moving.bulge) <= LENS_BULGE
    assert lens_state(plan, 0.999, DURATION_S).radius >= plan.cover * 0.999
    assert lens_envelope(0.0) == 0.0 and lens_envelope(LENS_FLATTEN[1]) == 0.0 and lens_envelope(0.4) == 1.0
    # Ripples surge on arrival and calm down at a stop.
    arrival = hop[3]
    assert lens_state(plan, arrival + 0.003, DURATION_S).ripple > lens_state(plan, arrival + 0.09, DURATION_S).ripple


def test_the_dome_is_a_spherical_cap_that_stays_exact_as_it_flattens():
    reach, thick = 0.2, 0.1
    big = (reach * reach + thick * thick) / (2 * thick)
    for u in (0.0, 0.3, 0.7, 0.99):
        assert lens_cap(reach, thick, u) == pytest.approx(math.sqrt(big * big - (u * reach) ** 2) - (big - thick))
    assert lens_cap(reach, thick, 1.0) == 0.0 and lens_cap(reach, 0.0, 0.5) == 0.0
    assert lens_cap(1.5, 1e-6, 0.4) == pytest.approx(1e-6 * (1 - 0.16), rel=1e-4)
    assert lens_twist_angle(0.8, 0.0) == pytest.approx(0.8) and lens_twist_angle(0.8, 1.0) == 0.0


@pytest.mark.qt
def test_the_shader_helpers_match_their_mirrors_on_the_gpu(qt_app):
    from tests.test_scene3d_glsl_mirrors import _GlslProbe, _check

    probe = _GlslProbe()
    try:
        values = list(np.linspace(0.0, 1.0, 48))
        gpu = probe.run("float t = arg(0).x; FragColor = vec4(lensCap(0.2, 0.1, t), lensMeniscus(t), "
                        "lensTwistAngle(0.8, t), lensCap(1.2, 0.004, t) * 100.0);",
                        [[(v,)] for v in values], declarations=LIQUID_LENS_GLSL)
        _check(gpu, [(lens_cap(0.2, 0.1, v), lens_meniscus(v), lens_twist_angle(0.8, v), lens_cap(1.2, 0.004, v) * 100.0)
                     for v in values])
    finally:
        probe.close()


@pytest.fixture
def capture(qt_app):
    capture = TransitionCapture(W, H)
    yield capture
    capture.close()


def _pixels(image) -> np.ndarray:
    return np.asarray(image.convert("RGB"), dtype=np.int16)


def _screen(point):
    return int((point[0] / ASPECT + 0.5) * W), int((0.5 - point[1]) * H)


@pytest.mark.qt
@pytest.mark.parametrize("stops", (1, 4, 8))
def test_ends_are_exact_and_continuous(capture, stops):
    run = capture.run("liquid_lens", settings={"liquid_lens": {"stops": stops}}, duration_ms=8000)
    source, destination = _pixels(capture.images[0]), _pixels(capture.images[1])
    assert np.array_equal(_pixels(capture.render(run, 0.0)[0]), source)
    assert np.array_equal(_pixels(capture.render(run, 1.0)[0]), destination)
    assert np.abs(_pixels(capture.render(run, 0.995)[0]) - destination).mean() < 0.5
    assert np.abs(_pixels(capture.render(run, 0.005)[0]) - source).mean() < 0.5


@pytest.mark.qt
def test_the_lens_appears_in_the_middle_then_sits_at_its_stop_showing_the_new_picture(capture):
    run = capture.run("liquid_lens", settings={"liquid_lens": {"stops": 4}}, duration_ms=8000)
    parameters = run.request.parameter_dict()
    plan = lens_plan(parameters["stops"], parameters["seed"], ASPECT)
    source, destination = _pixels(capture.images[0]), _pixels(capture.images[1])
    first = plan.segments[0]
    frame = _pixels(capture.render(run, first[3] - 0.005)[0])
    changed = np.abs(frame - source).max(axis=2) > 12
    ys, xs = np.nonzero(changed)
    assert 0.005 < changed.mean() < 0.15
    assert abs(xs.mean() - W / 2) < W * 0.08 and abs(ys.mean() - H / 2) < H * 0.12      # in the middle
    for index, end in enumerate(_ends_of_dwells(plan)[1:], start=1):
        frame = _pixels(capture.render(run, end - 0.005)[0])
        cx, cy = _screen(plan.stops[index])
        patch = np.s_[cy - 5:cy + 5, cx - 5:cx + 5]
        assert np.abs(frame[patch] - destination[patch]).mean() < np.abs(frame[patch] - source[patch]).mean()


@pytest.mark.qt
def test_ripples_run_out_from_the_lens_and_the_far_picture_is_untouched(capture):
    run = capture.run("liquid_lens", settings={"liquid_lens": {"stops": 3}}, duration_ms=8000)
    parameters = run.request.parameter_dict()
    plan = lens_plan(parameters["stops"], parameters["seed"], ASPECT)
    arrival = next(segment for segment in plan.segments if segment[0] == "hop")[3]
    state = lens_state(plan, arrival + 0.01, DURATION_S)
    frame, source = _pixels(capture.render(run, arrival + 0.01)[0]), _pixels(capture.images[0])
    yy, xx = np.mgrid[0:H, 0:W]
    distance = np.hypot((xx + 0.5) / H - (state.centre[0] + ASPECT / 2), (yy + 0.5) / H - (0.5 - state.centre[1]))
    ring = (distance > state.radius * 1.25 + 0.03) & (distance < state.radius * 1.25 + 0.1)
    far = distance > state.radius * 1.25 + 0.75
    moved = np.abs(frame - source).max(axis=2)
    assert (moved[ring] > 6).mean() > 0.2
    if far.any():
        assert (moved[far] <= 1).mean() > 0.99


@pytest.mark.qt
def test_refraction_changes_only_the_lens(capture):
    def frame(refraction):
        run = capture.run("liquid_lens", settings={"liquid_lens": {"refraction": refraction, "stops": 4}},
                          duration_ms=8000)
        return _pixels(capture.render(run, 0.35)[0])

    flat, strong = frame(0.0), frame(1.0)
    source = _pixels(capture.images[0])
    outside = np.all(flat == source, axis=2) & np.all(strong == source, axis=2)
    assert outside.mean() > 0.5 and (np.abs(flat - strong).max(axis=2) > 8).any()


@pytest.mark.qt
def test_warmed_runs_compile_nothing_on_their_first_frames(qt_app, monkeypatch):
    from tests.test_transition_warmup import _Work

    capture = TransitionCapture(256, 144)
    try:
        work = _Work(monkeypatch)
        run = capture.run("liquid_lens", duration_ms=8000)
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


def test_the_resolver_seeds_runs_and_repairs_stops():
    first, second = (resolve_parameterized_phase_c_inputs("liquid_lens", {}, random_source=random.Random(s))
                     for s in (1, 2))
    assert first.direction is None and first.parameter_dict()["seed"] != second.parameter_dict()["seed"]
    low, high = LIQUID_LENS_STOPS_RANGE
    for raw, expected in ((0, low), (99, high), ("x", None), (3, 3)):
        resolved = resolve_parameterized_phase_c_inputs(
            "liquid_lens", {"liquid_lens": {"stops": raw, "refraction": 7, "dispersion": -1}},
            random_source=random.Random(1))
        params = resolved.parameter_dict()
        assert low <= params["stops"] <= high and (expected is None or params["stops"] == expected)
        assert params["refraction"] == 1.0 and params["dispersion"] == 0.0


def test_stored_origin_and_droplets_are_dropped():
    from core.settings.transition_retired import strip_retired_transition_settings

    cleaned, changed = strip_retired_transition_settings(
        {"liquid_lens": {"direction": "Left", "droplets": True, "refraction": 0.3}, "membrane": {"direction": "Left"}})
    assert changed and cleaned["liquid_lens"] == {"refraction": 0.3} and cleaned["membrane"] == {"direction": "Left"}
