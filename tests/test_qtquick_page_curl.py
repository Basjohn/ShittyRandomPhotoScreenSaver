"""Page Curl: the curl geometry (CPU mirror, checked on the GPU), and the transition through the
production host on a real offscreen context (no window): exact and continuous ends, the flat
page and the uncovered new picture exact where the curl does not reach, every origin peeling
from its own corner or edge, gloss only on curled paper, a warm-up that leaves the first frames
nothing to do, park/release, and the resolver."""
from __future__ import annotations

import math
import random

import numpy as np
import pytest

from rendering.gl_programs.page_curl_options import PAGE_CURL_ORIGINS
from rendering.gl_programs.page_curl_program import (
    PAGE_CURL_GLSL,
    PAGE_CURL_RADIUS,
    PAGE_CURL_SHADE,
    PAGE_CURL_SHADE_REACH,
    page_curl_direction,
    page_curl_displace,
    page_curl_line,
    page_curl_shade_weight,
    page_curl_span,
)
from rendering.quick.transitions.parameter_resolution import resolve_parameterized_phase_c_inputs
from tools.transition_contact_sheet import TransitionCapture

pytestmark = pytest.mark.qt

W, H = 320, 180
ASPECT = W / H


def test_the_page_never_stretches_and_its_pieces_meet():
    """The curl is a bend, not a stretch: neighbouring points of the page stay as far apart
    along the paper, through the cylinder and onto the folded flap."""
    direction = page_curl_direction("bottom_right", ASPECT)
    line = 0.3
    step = 1e-4
    for s in np.linspace(-0.2, 0.6, 400):
        a = (direction[0] * s, direction[1] * s)
        b = (direction[0] * (s + step), direction[1] * (s + step))
        pa, pb = page_curl_displace(a, direction, line), page_curl_displace(b, direction, line)
        assert math.dist(pa, pb) == pytest.approx(step, rel=1e-3)
    # Ahead of the line: untouched. Half a turn in: on top, twice the radius up.
    assert page_curl_displace((0.5, 0.2), direction, -5.0) == (0.5, 0.2, 0.0)
    folded = page_curl_displace((0.0, 0.0), direction, math.pi * PAGE_CURL_RADIUS + 0.1)
    assert folded[2] == pytest.approx(2 * PAGE_CURL_RADIUS)


def test_the_line_starts_off_the_page_and_ends_with_no_shade():
    for origin in PAGE_CURL_ORIGINS.values():
        direction = page_curl_direction(origin, ASPECT)
        near, far = page_curl_span(direction, ASPECT)
        assert page_curl_line(0.0, near, far) == near
        end = page_curl_line(1.0, near, far)
        assert end - PAGE_CURL_RADIUS > far                      # the curl has left the page
        assert page_curl_shade_weight(end, far) == 0.0
        assert page_curl_shade_weight(far, far) == 1.0


def test_the_curl_matches_its_mirror_on_the_gpu(qt_app):
    from tests.test_scene3d_glsl_mirrors import _GlslProbe, _check

    probe = _GlslProbe()
    try:
        rng = random.Random(5)
        cases = []
        for _ in range(160):
            direction = page_curl_direction(rng.choice(tuple(PAGE_CURL_ORIGINS.values())), ASPECT)
            cases.append(((rng.uniform(-0.9, 0.9), rng.uniform(-0.5, 0.5)), direction, rng.uniform(-1.0, 1.5)))
        gpu = probe.run("vec4 a = arg(0); FragColor = vec4(pageCurlDisplace(a.xy, a.zw, arg(1).x, CURL_RADIUS), 0.0);",
                        [[(*p, *d), (line,)] for p, d, line in cases], declarations=PAGE_CURL_GLSL)
        _check(gpu, [page_curl_displace(p, d, line) for p, d, line in cases])
    finally:
        probe.close()


@pytest.fixture
def capture(qt_app):
    capture = TransitionCapture(W, H)
    yield capture
    capture.close()


def _pixels(image) -> np.ndarray:
    return np.asarray(image.convert("RGB"), dtype=np.int16)


def _along(direction) -> np.ndarray:
    """Each pixel centre's rest position along the curl direction (world units, y up)."""
    xs = ((np.arange(W) + 0.5) / W - 0.5) * ASPECT
    ys = 0.5 - (np.arange(H) + 0.5) / H
    return direction[0] * xs[None, :] + direction[1] * ys[:, None]


@pytest.mark.parametrize("detail", ("High", "Balanced", "Performance"))
@pytest.mark.parametrize("origin", ("bottom_right", "top_left", "left", "bottom"))
def test_the_flat_page_and_the_uncovered_picture_are_exact_away_from_the_curl(capture, origin, detail):
    run = capture.run("page_curl", direction=origin, settings={"detail_3d": detail}, duration_ms=4000)
    source, destination = _pixels(capture.images[0]), _pixels(capture.images[1])
    assert np.array_equal(_pixels(capture.render(run, 0.0)[0]), source)
    assert np.array_equal(_pixels(capture.render(run, 1.0)[0]), destination)
    direction = page_curl_direction(origin, ASPECT)
    near, far = page_curl_span(direction, ASPECT)
    along = _along(direction)
    pixel = 2.0 / H                                               # a little more than one pixel, in world units
    for progress in (0.25, 0.4, 0.55):
        frame = _pixels(capture.render(run, progress)[0])
        line = page_curl_line(progress, near, far)
        # Ahead of the flap's furthest reach the page lies flat: the old picture exactly.
        flap_end = line + max(line - near - math.pi * PAGE_CURL_RADIUS, 0.0)
        ahead = along > flap_end + 0.05
        # Well behind the curl (and its perspective): the new picture, shaded as the mirror says.
        behind = along < line - PAGE_CURL_RADIUS - 0.08
        assert ahead.any() or behind.any()
        if ahead.any():
            assert np.abs(frame[ahead] - source[ahead]).max() <= 1, progress
        if behind.any():
            distance = line - along[behind]
            shade = page_curl_shade_weight(line, far) * PAGE_CURL_SHADE * np.exp(
                -np.maximum(distance - PAGE_CURL_RADIUS, 0.0) / (PAGE_CURL_SHADE_REACH * PAGE_CURL_RADIUS))
            expected = destination[behind] * (1.0 - shade[:, None])
            assert np.abs(frame[behind] - expected).max() <= 2 + pixel, progress


def test_ends_are_continuous(capture):
    run = capture.run("page_curl", direction="top_right", duration_ms=4000)
    source, destination = _pixels(capture.images[0]), _pixels(capture.images[1])
    assert np.abs(_pixels(capture.render(run, 0.002)[0]) - source).mean() < 0.5
    assert np.abs(_pixels(capture.render(run, 0.998)[0]) - destination).mean() < 0.5


@pytest.mark.parametrize("origin", tuple(PAGE_CURL_ORIGINS.values()))
def test_every_origin_peels_from_its_own_side(capture, origin):
    run = capture.run("page_curl", direction=origin, duration_ms=4000)
    source, destination = _pixels(capture.images[0]), _pixels(capture.images[1])
    frame = _pixels(capture.render(run, 0.35)[0])
    direction = page_curl_direction(origin, ASPECT)
    near, far = page_curl_span(direction, ASPECT)
    line = page_curl_line(0.35, near, far)
    along = _along(direction)
    first = along <= np.quantile(along, 0.05)
    last = (along >= np.quantile(along, 0.95)) & (along > 2 * line - near - math.pi * PAGE_CURL_RADIUS + 0.05)
    assert last.any()
    # Its own side is uncovered (new picture, shaded at most); the far side, beyond the folded
    # flap, still the old page.
    assert np.abs(frame[first] - destination[first]).mean() < np.abs(frame[first] - source[first]).mean()
    assert np.abs(frame[last] - source[last]).max() <= 1


def test_gloss_changes_only_curled_paper(capture):
    frames = []
    for gloss in (0.0, 1.0):
        run = capture.run("page_curl", direction="bottom_right", settings={"page_curl": {"gloss": gloss}},
                          duration_ms=4000)
        frames.append(_pixels(capture.render(run, 0.45)[0]))
    changed = np.abs(frames[0] - frames[1]).max(axis=2) > 0
    assert changed.any()
    direction = page_curl_direction("bottom_right", ASPECT)
    near, far = page_curl_span(direction, ASPECT)
    line = page_curl_line(0.45, near, far)
    flap_end = line + max(line - near - math.pi * PAGE_CURL_RADIUS, 0.0)
    assert not changed[_along(direction) > flap_end + 0.05].any()


def test_warmed_runs_compile_and_allocate_nothing_on_their_first_frames(qt_app, monkeypatch):
    from tests.test_transition_warmup import _Work

    capture = TransitionCapture(256, 144)
    try:
        work = _Work(monkeypatch)
        run = capture.run("page_curl", direction="left", settings={"detail_3d": "High"}, duration_ms=3000)
        parameters, size = run.request.parameter_dict(), (capture.width, capture.height)
        steps = 0
        while not capture.host.warm_step("page_curl", parameters, size):
            steps += 1
            assert work.total <= steps and steps < 50
        renderer = capture.host._implementations["page_curl"]
        meshes = dict(renderer._resources._meshes)
        warmed, allocated = work.total, list(work.allocations)
        capture.render(run, 0.0)
        capture.render(run, 0.4)
        assert work.total == warmed and work.allocations == allocated
        assert renderer._resources._meshes == meshes            # the tier's grid was ready too
        capture.host.park()
        assert not renderer._target.has_resources and not renderer._environment.has_resources
        renderer.release_resources()
        assert not renderer.has_resources
    finally:
        capture.close()


def test_the_resolver_picks_origins_and_repairs_values():
    seen = set()
    for seed in range(60):
        resolved = resolve_parameterized_phase_c_inputs("page_curl", {}, random_source=random.Random(seed))
        seen.add(resolved.direction)
    assert seen == set(PAGE_CURL_ORIGINS.values())
    resolved = resolve_parameterized_phase_c_inputs(
        "page_curl", {"detail_3d": "Balanced", "page_curl": {"direction": "Top Left", "gloss": 9}},
        random_source=random.Random(1))
    assert resolved.direction == "top_left"
    assert resolved.parameter_dict() == {"gloss": 1.0, "detail": "Balanced", "samples": 0}
