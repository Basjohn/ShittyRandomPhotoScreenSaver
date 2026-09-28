"""Focused geometry, blast and departure regressions for Exploding Tiles."""

from __future__ import annotations

from collections import Counter
import importlib.util
from pathlib import Path

import numpy as np
import pytest

from tools.transition_contact_sheet import TransitionCapture


ROOT = Path(__file__).resolve().parents[1]


def _effect():
    spec = importlib.util.spec_from_file_location(
        "_tile_departure", ROOT / "rendering/gl_programs/exploding_tiles_program.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _slab_positions(
    vertices: tuple[float, ...], stride: int
) -> list[tuple[float, ...]]:
    return [
        tuple(round(component, 6) for component in vertices[index : index + 3])
        for index in range(0, len(vertices), stride)
    ]


def test_beveled_slab_is_closed_and_encloses_positive_volume():
    effect = _effect()
    positions = _slab_positions(
        effect.exploding_tiles_box_vertices(),
        effect.EXPLODING_TILES_VERTEX_STRIDE_FLOATS,
    )
    edges: Counter[tuple[tuple[float, ...], tuple[float, ...]]] = Counter()
    signed_volume = 0.0
    for index in range(0, len(positions), 3):
        first, second, third = positions[index : index + 3]
        for start, end in ((first, second), (second, third), (third, first)):
            assert start != end
            edges[tuple(sorted((start, end)))] += 1
        signed_volume += (
            sum(
                first[axis]
                * (
                    second[(axis + 1) % 3] * third[(axis + 2) % 3]
                    - second[(axis + 2) % 3] * third[(axis + 1) % 3]
                )
                for axis in range(3)
            )
            / 6.0
        )

    # Each geometric edge is shared by two outward faces. This rejects a raised
    # lip or an open back even when a front-facing contact sheet looks plausible.
    assert set(edges.values()) == {2}
    assert signed_volume > 0.9
    assert {position[2] for position in positions} == {-0.5, -0.38, 0.38, 0.5}


def test_tiles_launch_with_an_impulse_not_an_ease_in():
    # The rejected "falling tiles" started from rest and accelerated. A blast is
    # the opposite: fastest at release, then drag settles it into a drift.
    effect = _effect()
    travel = effect.exploding_tile_travel
    samples = [travel(t / 100.0) for t in range(0, 99)]
    assert samples[0] == 0.0
    assert all(later > earlier for earlier, later in zip(samples, samples[1:]))
    early_speed = travel(0.02) / 0.02
    late_speed = (travel(0.9) - travel(0.45)) / 0.45
    assert early_speed > 3.0 * late_speed


def test_the_shock_front_releases_tiles_outward_from_the_blast():
    effect = _effect()
    release = effect.exploding_tile_release
    for center_out in (True, False):
        times = [release(reach / 10.0, 1.0, center_out) for reach in range(11)]
        assert times[0] == pytest.approx(effect.EXPLODING_TILES_DETONATION)
        assert times == sorted(times)
        assert times[-1] < 0.5 * effect.EXPLODING_TILES_SETTLE
    assert release(1.0, 2.0, True) < release(1.0, 0.5, True)


def test_the_blast_light_is_exactly_zero_outside_the_detonation():
    effect = _effect()
    detonation = effect.EXPLODING_TILES_DETONATION
    for progress in (0.0, 0.0001, detonation - 0.005, 0.85, 0.9, 0.9999, 1.0):
        assert effect.exploding_tiles_blast(progress) == (0.0, 0.0), progress
    assert effect.exploding_tiles_blast(detonation)[0] > 0.9  # the flash is instant
    peak_fire = max(effect.exploding_tiles_blast(detonation + step / 1000)[1] for step in range(11))
    later_flash, later_fire = effect.exploding_tiles_blast(detonation + 0.1)
    assert later_flash < 0.01 < later_fire < peak_fire


def test_the_blast_sits_where_the_pieces_fly_away_from():
    effect = _effect()
    aspect = 16 / 9
    for seed in (1, 713, 65535):
        x, y, reach = effect.exploding_tiles_epicentre(None, seed, aspect)
        assert abs(x) <= 0.08 * aspect and abs(y) <= 0.08
        corners = [(cx, cy) for cx in (-aspect / 2, aspect / 2) for cy in (-0.5, 0.5)]
        assert reach == pytest.approx(max(np.hypot(cx - x, cy - y) for cx, cy in corners))
        # Pieces flying left were blasted from the right edge (world y is up).
        x, y, _reach = effect.exploding_tiles_epicentre((-1.0, 0.0), seed, aspect)
        assert x > aspect / 2 and abs(y) <= 0.25
        x, y, _reach = effect.exploding_tiles_epicentre((0.0, -1.0), seed, aspect)
        assert y < -0.5
        x, y, _reach = effect.exploding_tiles_epicentre((0.7071, 0.7071), seed, aspect)
        assert x < -aspect / 2 and y > 0.5


@pytest.mark.qt
def test_the_blast_opens_the_picture_at_the_detonation(qt_app):
    # Negative control: the rejected ease-in moved the centre by under 1 grey
    # level at this point (0.87); the blast has torn it open.
    capture = TransitionCapture(256, 144)
    try:
        effect = _effect()
        detonation = effect.EXPLODING_TILES_DETONATION
        run = capture.run("exploding_tiles", direction="center_out")
        source = np.asarray(capture.images[0], dtype=np.int16)
        before = np.asarray(capture.render(run, detonation - 0.02)[0], dtype=np.int16)
        after = np.asarray(capture.render(run, detonation + 0.06)[0], dtype=np.int16)
        centre = (slice(36, 108), slice(64, 192))
        assert np.abs(before - source).mean() < 6.0
        assert np.abs(after - source)[centre].mean() > 10.0
    finally:
        capture.close()


@pytest.mark.qt
def test_the_far_wall_rumbles_late_and_slowly_at_an_authored_duration(qt_app):
    # The rumble runs in real time, so it is measured at an 8000 ms run: the same
    # progress rendered one 60 fps frame later in real time isolates it (every other
    # part of the effect follows progress). Negative control, the rejected 8-15 Hz
    # rumble from cracking: 1.9 at p=0.085 and up to 3.5 grey levels per frame.
    capture = TransitionCapture(640, 360)
    try:
        corner = (slice(0, 72), slice(0, 128))

        def rumble(progress: float) -> float:
            runs = [capture.run("exploding_tiles", direction="center_out", duration_ms=duration)
                    for duration in (8000, 8000 + round(1000 / (60 * progress)))]
            first, second = (np.asarray(capture.render(run, progress)[0], dtype=np.int16) for run in runs)
            return float(np.abs(first - second)[corner].mean())

        assert rumble(0.085) < 0.1  # still until well after the detonation
        motion = [rumble(progress) for progress in (0.12, 0.14, 0.16)]
        assert max(motion) > 0.1  # it does shudder before the shock front arrives
        assert max(motion) < 2.0
    finally:
        capture.close()


@pytest.mark.qt
@pytest.mark.parametrize("size", ((160, 480), (720, 180)))
def test_weak_force_geometry_clears_portrait_and_wide_viewports_before_retirement(
    qt_app, size
):
    capture = TransitionCapture(*size)
    try:
        destination = np.asarray(capture.images[1], dtype=np.int16)
        parameters = {"force": 0.5, "thickness": 1.0, "depth": 1.5}
        for direction in ("left", "up", "center_out"):
            run = capture.run(
                "exploding_tiles", direction=direction, parameters=parameters
            )
            late_frame = np.asarray(capture.render(run, 0.98)[0], dtype=np.int16)
            assert np.abs(late_frame - destination).mean() < 0.5, (size, direction)
    finally:
        capture.close()
