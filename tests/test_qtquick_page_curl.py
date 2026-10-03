"""Page Curl: the roll geometry (CPU mirror, checked on the GPU), and the transition through the
production host on a real offscreen context (no window): exact and continuous ends, the flat
page and the uncovered new picture exact where the roll does not reach, every origin peeling
from its own corner or edge, gloss only on the peeled sheet, a warm-up that leaves the first
frames nothing to do, park/release, and the resolver."""
from __future__ import annotations

import math
import random

import numpy as np
import pytest

from rendering.gl_programs.page_curl_options import PAGE_CURL_ORIGINS
from rendering.gl_programs.page_curl_program import (
    PAGE_CURL_GLSL,
    PAGE_CURL_ROLL_INNER,
    PAGE_CURL_ROLL_PITCH,
    PAGE_CURL_SHADE,
    PAGE_CURL_SHADE_REACH,
    page_curl_direction,
    page_curl_displace,
    page_curl_end_radius,
    page_curl_line,
    page_curl_roll_radius,
    page_curl_row,
    page_curl_row_radius,
    page_curl_shade_weight,
    page_curl_span,
)
from rendering.quick.transitions.parameter_resolution import resolve_parameterized_phase_c_inputs
from tools.transition_contact_sheet import TransitionCapture

pytestmark = pytest.mark.qt

W, H = 320, 180
ASPECT = W / H


@pytest.mark.parametrize("origin", ("bottom_right", "left", "top"))
def test_the_sheet_rolls_without_stretching_or_creasing(origin):
    """The roll is a bend, not a stretch: neighbouring points of a strip stay as far apart along
    the sheet from the flat page through every turn, the sheet leaves the page level (no crease),
    and the free edge is the roll's innermost turn."""
    direction = page_curl_direction(origin, ASPECT)
    near, far = page_curl_span(direction, ASPECT)
    line = near + 0.7 * (far - near)
    step = 1e-4
    base = (-direction[1] * 0.05, direction[0] * 0.05)            # a strip a little off the centre line
    back, ahead = page_curl_row(base, direction, ASPECT)          # the strip's own ends
    lo, hi = float(-back) + 1e-3, float(ahead) - 1e-3
    previous = None
    for s in np.linspace(lo, min(line + 0.2, hi), 500):
        a = (base[0] + direction[0] * s, base[1] + direction[1] * s)
        b = (base[0] + direction[0] * (s + step), base[1] + direction[1] * (s + step))
        pa, pb = page_curl_displace(a, direction, line, ASPECT), page_curl_displace(b, direction, line, ASPECT)
        assert math.dist(pa, pb) == pytest.approx(step, rel=2e-3)
        if previous is not None and s < line - 1e-3:
            assert pa[2] >= 0.0
        previous = pa
    # Just behind the line the sheet still lies level: the roll meets the page without a crease.
    just = (base[0] + direction[0] * (line - 1e-3), base[1] + direction[1] * (line - 1e-3))
    assert page_curl_displace(just, direction, line, ASPECT)[2] < 1e-5
    # Ahead of the line: untouched.
    assert page_curl_displace((0.5, 0.2), direction, near - 1.0, ASPECT) == (0.5, 0.2, 0.0)


def test_the_roll_grows_from_the_free_edge_curl_by_its_pitch():
    assert page_curl_roll_radius(0.0) == pytest.approx(PAGE_CURL_ROLL_INNER)
    lengths = np.linspace(0.0, 2.0, 200)
    radii = page_curl_roll_radius(lengths)
    assert np.all(np.diff(radii) > 0)
    # One more turn is one turn's arc of sheet: about 2 pi r, and adds 2 pi pitch to the radius.
    r = float(page_curl_roll_radius(1.0))
    turn = 2 * math.pi * (r + math.pi * PAGE_CURL_ROLL_PITCH)
    assert float(page_curl_roll_radius(1.0 + turn)) == pytest.approx(r + 2 * math.pi * PAGE_CURL_ROLL_PITCH, rel=0.02)


def test_the_line_starts_off_the_page_at_an_even_pace_and_ends_with_no_shade():
    for origin in PAGE_CURL_ORIGINS.values():
        direction = page_curl_direction(origin, ASPECT)
        near, far = page_curl_span(direction, ASPECT)
        assert page_curl_line(0.0, near, far) == near
        end = page_curl_line(1.0, near, far)
        assert end - page_curl_end_radius(near, far) > far             # the roll has left the page
        assert page_curl_shade_weight(end, near, far) == 0.0
        assert page_curl_shade_weight(far, near, far) == 1.0
        speeds = np.diff([page_curl_line(t, near, far) for t in np.linspace(0.3, 0.7, 9)])
        assert speeds.max() - speeds.min() < 1e-9                        # an even pace through the middle


def test_the_roll_matches_its_mirror_on_the_gpu(qt_app):
    from tests.test_scene3d_glsl_mirrors import _GlslProbe, _check

    probe = _GlslProbe()
    try:
        rng = random.Random(5)
        cases = []
        for _ in range(200):
            direction = page_curl_direction(rng.choice(tuple(PAGE_CURL_ORIGINS.values())), ASPECT)
            cases.append(((rng.uniform(-0.88, 0.88), rng.uniform(-0.49, 0.49)), direction, rng.uniform(-1.0, 1.6)))
        gpu = probe.run(
            "vec4 a = arg(0); vec2 extent = vec2(0.5 * arg(1).y, 0.5);"
            " FragColor = vec4(pageCurlDisplace(a.xy, a.zw, arg(1).x, extent),"
            " pageCurlRowRadius(a.xy, a.zw, arg(1).x, extent));",
            [[(*p, *d), (line, ASPECT)] for p, d, line in cases], declarations=PAGE_CURL_GLSL)
        _check(gpu, [(*page_curl_displace(p, d, line, ASPECT), float(page_curl_row_radius(p, d, line, ASPECT)))
                     for p, d, line in cases])
    finally:
        probe.close()


@pytest.fixture
def capture(qt_app):
    capture = TransitionCapture(W, H)
    yield capture
    capture.close()


def _pixels(image) -> np.ndarray:
    return np.asarray(image.convert("RGB"), dtype=np.int16)


def _points() -> tuple[np.ndarray, np.ndarray]:
    """Each pixel centre's rest position (world units, y up)."""
    xs = ((np.arange(W) + 0.5) / W - 0.5) * ASPECT
    ys = 0.5 - (np.arange(H) + 0.5) / H
    return np.broadcast_to(xs[None, :], (H, W)), np.broadcast_to(ys[:, None], (H, W))


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
    reach = 1.3 * page_curl_end_radius(near, far) + 0.03          # the largest roll, in perspective
    pixel = 2.0 / H                                               # a little more than one pixel, in world units
    for progress in (0.25, 0.4, 0.55):
        frame = _pixels(capture.render(run, progress)[0])
        line = page_curl_line(progress, near, far)
        # Ahead of the roll the page lies flat: the old picture exactly.
        ahead = along > line + reach
        # Well behind the roll (and its perspective): the new picture, shaded as the mirror says.
        radius = page_curl_row_radius(_points(), direction, line, ASPECT)
        distance = line - along
        behind = distance > radius + 0.15
        assert ahead.any() or behind.any()
        if ahead.any():
            assert np.abs(frame[ahead] - source[ahead]).max() <= 1, progress
        if behind.any():
            shade = page_curl_shade_weight(line, near, far) * PAGE_CURL_SHADE * np.exp(
                -np.maximum(distance - 0.5 * radius, 0.0) / (PAGE_CURL_SHADE_REACH * radius))
            expected = destination[behind] * (1.0 - shade[behind][:, None])
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
    last = (along >= np.quantile(along, 0.95)) & (along > line + 1.3 * page_curl_end_radius(near, far) + 0.03)
    assert last.any()
    # Its own side is uncovered (new picture, shaded at most); the far side, beyond the roll,
    # still the old page.
    assert np.abs(frame[first] - destination[first]).mean() < np.abs(frame[first] - source[first]).mean()
    assert np.abs(frame[last] - source[last]).max() <= 1


def test_gloss_changes_only_the_peeled_sheet(capture):
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
    assert not changed[_along(direction) > line + 1.3 * page_curl_end_radius(near, far) + 0.03].any()


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
