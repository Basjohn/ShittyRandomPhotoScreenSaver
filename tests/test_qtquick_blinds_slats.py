"""Blinds -> 3D Slats through the production host on a real offscreen context (no window).

Exact and continuous ends, the turning wave (slats at rest are the photographs exactly,
judged through the CPU mirror of the schedule), light only while a slat turns, both axes and
every 3D Detail tier, a dormant Flat style, a warm-up that leaves nothing to the first
frame, park/release, and the resolver's choices.
"""
from __future__ import annotations

import random

import numpy as np
import pytest

from rendering.gl_programs.blinds_slats_program import blinds_slat_lift, blinds_slat_phase
from rendering.quick.transitions.parameter_resolution import resolve_parameterized_phase_c_inputs
from tools.transition_contact_sheet import TransitionCapture

pytestmark = pytest.mark.qt

W, H = 320, 180


def _settings(**blinds) -> dict:
    return {"scene3d_detail": blinds.pop("detail", "High"), "blinds": {"style": "3D Slats", **blinds}}


def _pixels(image) -> np.ndarray:
    return np.asarray(image.convert("RGB"), dtype=np.int16)


@pytest.fixture
def capture(qt_app):
    capture = TransitionCapture(W, H)
    yield capture
    capture.close()


def _bands(count: int, columns: bool) -> list[slice]:
    size = W if columns else H
    return [slice(round(i * size / count), round((i + 1) * size / count)) for i in range(count)]


def _region(image: np.ndarray, band: slice, columns: bool) -> np.ndarray:
    return image[:, band] if columns else image[band]


@pytest.mark.parametrize("direction,columns", (("Vertical", False), ("Horizontal", True)))
@pytest.mark.parametrize("detail", ("High", "Balanced", "Performance"))
def test_slats_at_rest_are_the_photographs_and_turn_in_a_wave(capture, direction, columns, detail):
    count = 12
    run = capture.run("blinds", settings=_settings(direction=direction, slats=count, detail=detail),
                      duration_ms=4000)
    assert run.request.direction == direction.lower()
    source, destination = _pixels(capture.images[0]), _pixels(capture.images[1])
    assert np.array_equal(_pixels(capture.render(run, 0.0)[0]), source)
    assert np.array_equal(_pixels(capture.render(run, 1.0)[0]), destination)
    bands = _bands(count, columns)
    for progress in (0.2, 0.45, 0.7):
        frame = _pixels(capture.render(run, progress)[0])
        phases = [blinds_slat_phase(progress, i, count) for i in range(count)]
        turned = [i for i in range(count) if phases[i] >= 1.0]
        waiting = [i for i in range(count) if phases[i] <= 0.0]
        assert turned or waiting
        for i in turned + waiting:
            # A turning neighbour may overhang the band's edges; its middle is the slat at rest.
            if any(0.0 < phases[j] < 1.0 for j in (i - 1, i + 1) if 0 <= j < count):
                inner = slice(bands[i].start + 3, bands[i].stop - 3)
            else:
                inner = bands[i]
            expected = destination if i in turned else source
            got = _region(frame, inner, columns)
            assert np.abs(got - _region(expected, inner, columns)).max() <= 1, (progress, i)
        # The wave runs from the first slat to the last: turned slats come first.
        assert all(t < w for t in turned for w in waiting)
        moving = [i for i in range(count) if blinds_slat_lift(progress, i, count) > 0.3]
        assert moving
        for i in moving:
            band = _region(frame, bands[i], columns)
            assert np.abs(band - _region(source, bands[i], columns)).mean() > 2
            assert np.abs(band - _region(destination, bands[i], columns)).mean() > 2


def test_ends_are_continuous(capture):
    run = capture.run("blinds", settings=_settings(direction="Vertical"), duration_ms=4000)
    source, destination = _pixels(capture.images[0]), _pixels(capture.images[1])
    near_start = _pixels(capture.render(run, 0.002)[0])
    near_end = _pixels(capture.render(run, 0.998)[0])
    assert np.abs(near_start - source).mean() < 1.0
    assert np.abs(near_end - destination).mean() < 1.0


def test_gloss_changes_only_turning_slats(capture):
    count = 10
    frames = []
    for gloss in (0.0, 1.0):
        run = capture.run("blinds", settings=_settings(direction="Vertical", slats=count, gloss=gloss), duration_ms=4000)
        frames.append(_pixels(capture.render(run, 0.4)[0]))
    bands = _bands(count, False)
    phases = [blinds_slat_phase(0.4, i, count) for i in range(count)]
    changed = [np.abs(frames[0][bands[i]] - frames[1][bands[i]]).mean() for i in range(count)]
    for i, phase in enumerate(phases):
        neighbours_rest = all(phases[j] in (0.0, 1.0) for j in (i - 1, i + 1) if 0 <= j < count)
        if phase in (0.0, 1.0) and neighbours_rest:
            assert changed[i] == 0.0, i
    assert max(changed) > 1.0


def test_the_schedule_mirror_is_bounded_and_ends_exactly():
    for count in (6, 16, 48):
        for i in range(count):
            assert blinds_slat_phase(0.0, i, count) == 0.0 and blinds_slat_phase(1.0, i, count) == 1.0
            assert blinds_slat_lift(0.0, i, count) == 0.0 and blinds_slat_lift(1.0, i, count) == 0.0
            assert 0.0 <= blinds_slat_lift(0.5, i, count) <= 1.0
        assert blinds_slat_phase(0.3, 0, count) > blinds_slat_phase(0.3, count - 1, count)


def test_flat_style_stays_dormant(capture):
    run = capture.run("blinds", settings={"blinds": {"style": "Flat", "direction": "Vertical"}}, duration_ms=4000)
    assert capture.host.warm_step("blinds", run.request.parameter_dict(), (W, H)) is True
    for progress in (0.0, 0.3, 0.7, 1.0):
        capture.render(run, progress)
    renderer = capture.host._implementations["blinds"]
    assert not renderer._resources.has_resources and not renderer._target.has_resources
    assert not renderer._environment.has_resources


def test_warmed_slats_compile_and_allocate_nothing_on_their_first_frames(qt_app, monkeypatch):
    from tests.test_transition_warmup import _Work

    capture = TransitionCapture(256, 144)
    try:
        work = _Work(monkeypatch)
        run = capture.run("blinds", settings=_settings(direction="Horizontal"), duration_ms=3000)
        parameters, size = run.request.parameter_dict(), (capture.width, capture.height)
        steps = 0
        while not capture.host.warm_step("blinds", parameters, size):
            steps += 1
            assert work.total <= steps and steps < 50
        warmed, allocated = work.total, list(work.allocations)
        capture.render(run, 0.0)
        capture.render(run, 0.4)
        assert work.total == warmed and work.allocations == allocated
        renderer = capture.host._implementations["blinds"]
        capture.host.park()
        assert not renderer._target.has_resources and not renderer._environment.has_resources
        assert renderer._resources.has_resources        # programs and the slat mesh stay warm
        renderer.release_resources()
        assert not renderer.has_resources
    finally:
        capture.close()


def test_the_resolver_picks_an_axis_for_slats_and_repairs_choices():
    seen = set()
    for seed in range(40):
        for direction in ("Diagonal", "Random"):
            resolved = resolve_parameterized_phase_c_inputs(
                "blinds", _settings(direction=direction), random_source=random.Random(seed))
            seen.add(resolved.direction)
    assert seen == {"horizontal", "vertical"}
    resolved = resolve_parameterized_phase_c_inputs(
        "blinds", _settings(slats=500, gloss=7, antialiasing="16x"), random_source=random.Random(1))
    parameters = resolved.parameter_dict()
    assert parameters["style"] == "slats" and parameters["slats"] == 48 and parameters["gloss"] == 1.0
    assert parameters["samples"] == 4       # unknown anti-aliasing follows the High tier
    flat = resolve_parameterized_phase_c_inputs("blinds", {"blinds": {"style": "?"}}, random_source=random.Random(1))
    assert flat.parameter_dict()["style"] == "flat" and "slats" not in flat.parameter_dict()
