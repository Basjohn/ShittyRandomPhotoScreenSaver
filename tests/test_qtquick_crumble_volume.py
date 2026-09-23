"""Volume, debris and continuous-departure contracts for Quick Crumble."""

from rendering.gl_programs.crumble_program import (
    CRUMBLE_CHIP_VERTICES,
    CRUMBLE_FRAGMENT,
    CRUMBLE_VERTEX,
    DEBRIS_VERTEX,
)
from rendering.quick.transitions.run_geometry import (
    crumble_parameters as _crumble_parameters,
    debris_instances as _debris_instances,
)
from rendering.quick.transitions.fracture_geometry import fracture_cells
import numpy as np
import pytest
from tools.transition_contact_sheet import TransitionCapture


def test_crumble_requires_explicit_volume_controls_and_preserves_weight_modes():
    params = {
        "seed": 12.5,
        "piece_count": 24,
        "crack_complexity": 1.0,
        "weight_mode": 4.0,
        "depth": 0.85,
        "thickness": 0.65,
        "debris": 0.65,
    }
    assert _crumble_parameters(params) == (12.5, 24, 1.0, 4.0, 0.85, 0.65, 0.65)


def test_closed_fracture_and_instanced_debris_have_no_flat_particle_shortcut():
    assert (
        "aZ" in CRUMBLE_VERTEX
        and "aFace" in CRUMBLE_VERTEX
        and "rotateAxis" in CRUMBLE_VERTEX
    )
    assert (
        "aPosition" in DEBRIS_VERTEX
        and "rotateAxis" in DEBRIS_VERTEX
        and "gl_PointSize" not in DEBRIS_VERTEX
    )
    assert len(CRUMBLE_CHIP_VERTICES) // 6 == 24 and "broken" in CRUMBLE_FRAGMENT
    # Debris must be a mutated solid family rather than repeated identical
    # square/diamond chips.  The shader derives independent XYZ shape scales
    # from per-instance metadata and keeps the whole family deliberately small.
    assert "vec3 shape=" in DEBRIS_VERTEX
    assert "aPosition*shape*scale" in DEBRIS_VERTEX
    assert "(.006+.014*aMeta.y)" in DEBRIS_VERTEX


def test_debris_metadata_is_bounded_seeded_and_tied_to_static_fracture():
    from rendering.quick.transitions.fracture_geometry import crumble_cells

    shards = crumble_cells(12, 128, 16 / 9, 2.0)
    first = _debris_instances(12.5, shards, 0.65)
    assert (
        first == _debris_instances(12.5, shards, 0.65) and 12 <= len(first) // 6 <= 512
    )
    assert first != _debris_instances(19.5, shards, 0.65)
    size_metadata = first[5::6]
    assert len({round(value, 4) for value in size_metadata}) > 8
    assert max(size_metadata) - min(size_metadata) > 0.4


@pytest.mark.qt
def test_real_driver_fall_has_continuous_late_departure_without_an_endpoint_cut(qt_app):
    capture = TransitionCapture(320, 180)
    try:
        run = capture.run("crumble")
        source = np.asarray(capture.images[0], dtype=np.int16)
        destination = np.asarray(capture.images[1], dtype=np.int16)
        first = np.asarray(capture.render(run, 0.0001)[0], dtype=np.int16)
        middle = np.asarray(capture.render(run, 0.53)[0], dtype=np.int16)
        assert np.abs(first - source).mean() < 0.5
        assert np.abs(middle - source).mean() > 2.0
        for progress in (0.95, 0.97, 0.98, 0.99, 0.9999):
            frame = np.asarray(capture.render(run, progress)[0], dtype=np.int16)
            assert np.abs(frame - destination).mean() < 0.5
    finally:
        capture.close()
    assert "if (uProgress" not in CRUMBLE_VERTEX
    assert "discard" not in CRUMBLE_FRAGMENT


# Oracle baseline: the fracture roughness/debris these pixel thresholds were
# calibrated with (the pre-d56d7099 defaults). Product defaults may move freely.
_CALIBRATED = {
    "crack_complexity": 1.0,
    "debris": 0.65,
    "depth": 0.85,
    "thickness": 0.65,
    "piece_count": 16,
}


def _cell_area_cv(shards, aspect: float) -> float:
    import statistics

    areas = [
        abs(sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in zip(poly, poly[1:] + poly[:1]))) * 0.5 * aspect
        for poly in (list(shard.polygon) for shard in shards)
    ]
    return statistics.pstdev(areas) / statistics.mean(areas)


def test_crack_complexity_is_live_across_its_whole_range():
    """Operator decision 2026-09-23: complexity must visibly mutate the fracture.

    Mean piece-size irregularity rises at every step from 0.5 to 2.0 (the old
    jittered grid was flat above ~1.26, including the 1.8 default).
    """

    from rendering.quick.transitions.fracture_geometry import crumble_cells

    aspect = 16 / 9
    steps = (0.5, 0.875, 1.25, 1.625, 2.0)
    irregularity = [
        sum(_cell_area_cv(crumble_cells(seed * 37.1, 35, aspect, c), aspect) for seed in range(16)) / 16
        for c in steps
    ]
    assert all(later > earlier + 0.05 for earlier, later in zip(irregularity, irregularity[1:])), irregularity
    assert irregularity[-1] > 2.0 * irregularity[0], irregularity
    assert crumble_cells(390.1, 35, aspect, 1.5) != crumble_cells(390.1, 35, aspect, 2.0)


def test_each_run_draws_a_different_crack_layout():
    """Seeds pick different pattern families, so runs stop repeating one layout."""

    import random

    from rendering.quick.transitions.fracture_geometry import CRUMBLE_PATTERNS, crumble_cells

    aspect = 16 / 9
    families = {CRUMBLE_PATTERNS[random.Random(seed * 37.1).randrange(len(CRUMBLE_PATTERNS))]
                for seed in range(12)}
    assert families == set(CRUMBLE_PATTERNS)
    per_seed = [_cell_area_cv(crumble_cells(seed * 37.1, 35, aspect, 1.8), aspect) for seed in range(16)]
    assert max(per_seed) - min(per_seed) > 0.3, per_seed


@pytest.mark.parametrize("pieces", (4, 35, 128))
def test_crumble_cells_tile_the_wall_without_gaps_and_repeat_per_seed(pieces):
    from rendering.quick.transitions.fracture_geometry import crumble_cells

    aspect = 16 / 9
    for seed in (1.5, 390.1, 811.0):
        for complexity in (0.5, 1.8, 2.0):
            shards = crumble_cells(seed, pieces, aspect, complexity)
            assert len(shards) == pieces
            area = sum(
                abs(sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in zip(p, p[1:] + p[:1]))) * 0.5
                for p in (list(shard.polygon) for shard in shards)
            )
            assert abs(area - 1.0) < 1e-9  # normalized wall: no gap, no overlap
            assert shards == crumble_cells(seed, pieces, aspect, complexity)


def test_glass_fracture_is_untouched_by_the_crumble_mutation():
    from rendering.quick.transitions.fracture_geometry import crumble_cells, fracture_cells

    assert fracture_cells(12.5, 35, 16 / 9) != crumble_cells(12.5, 35, 16 / 9, 1.0)


def test_debris_amount_drives_chip_count_and_size():
    import statistics

    from rendering.quick.transitions.fracture_geometry import crumble_cells
    from rendering.quick.transitions.run_geometry import debris_instances as _debris_instances

    shards = crumble_cells(12.5, 35, 16 / 9, 1.8)
    by_amount = {amount: _debris_instances(12.5, shards, amount) for amount in (0.2, 0.65, 1.0)}
    counts = [len(values) // 6 for values in by_amount.values()]
    sizes = [statistics.mean(values[5::6]) for values in by_amount.values()]
    assert counts[0] < counts[1] < counts[2], counts
    assert sizes[0] < sizes[1] < sizes[2], sizes


@pytest.mark.qt
@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("depth", 1.5),
        ("thickness", 1.0),
        ("debris", 1.0),
        ("weight_mode", 1.0),
        ("crack_complexity", 2.0),
        ("piece_count", 48),
    ),
)
def test_real_driver_each_crumble_control_changes_the_volume(qt_app, field, value):
    # Compare against the pinned baseline these deltas were calibrated on, not
    # the moving product defaults (d56d7099 raised complexity/debris to 1.8/0.85,
    # which left 2.0/1.0 barely different -- or, for complexity, identical).
    capture = TransitionCapture(320, 180)
    try:
        base = np.asarray(
            capture.render(capture.run("crumble", parameters=_CALIBRATED), 0.53)[0],
            dtype=np.int16,
        )
        changed = np.asarray(
            capture.render(
                capture.run("crumble", parameters={**_CALIBRATED, field: value}), 0.53
            )[0],
            dtype=np.int16,
        )
        assert np.abs(base - changed).mean() > 0.08, field
    finally:
        capture.close()


def test_crumble_preserves_fractional_seed_identity_and_seam_origins():
    from rendering.quick.transitions.fracture_geometry import crumble_cells
    from rendering.quick.transitions.run_geometry import debris_instances as _debris_instances
    import numpy as np

    first = crumble_cells(12.1, 16, 16 / 9, 1.0)
    assert first != crumble_cells(12.9, 16, 16 / 9, 1.0)
    parents = {shard.center: shard for shard in first}
    instances = np.asarray(_debris_instances(12.1, first, 0.65)).reshape(-1, 6)
    for instance in instances:
        # Every chip breaks off a real border of its own parent piece.
        shard = parents[tuple(instance[2:4])]
        assert instance[4] == shard.variation
        on_edge = False
        for index, corner in enumerate(shard.polygon):
            a = np.asarray(corner)
            b = np.asarray(shard.polygon[(index + 1) % len(shard.polygon)])
            edge = b - a
            point = instance[:2] - a
            if (abs(edge[0] * point[1] - edge[1] * point[0]) < 1e-12
                    and -1e-12 <= float(point @ edge) <= float(edge @ edge) + 1e-12):
                on_edge = True
                break
        assert on_edge


def test_crumble_failed_instance_deletion_keeps_handle_and_releases_other_resources(
    monkeypatch,
):
    from rendering.quick.transitions.implementations import crumble
    import pytest

    renderer = crumble.QuickCrumbleRenderer()
    renderer._debris_vbo = 71
    released = []
    monkeypatch.setattr(
        renderer._resources, "release_resources", lambda: released.append(True)
    )

    def fail(*args):
        raise RuntimeError("injected instance deletion failure")

    monkeypatch.setattr(crumble.gl, "glDeleteBuffers", fail)
    with pytest.raises(RuntimeError, match="cleanup incomplete"):
        renderer.release_resources()
    assert renderer._debris_vbo == 71 and released == [True]
    monkeypatch.setattr(crumble.gl, "glDeleteBuffers", lambda *args: None)
    renderer.release_resources()
    assert renderer._debris_vbo == 0 and released == [True, True]


@pytest.mark.qt
def test_cracks_grow_before_the_intact_wall_or_debris_moves(qt_app):
    capture=TransitionCapture(640,360)
    try:
        run=capture.run("crumble",parameters={**_CALIBRATED,"weight_mode":0.0})
        source=np.asarray(capture.images[0],dtype=np.int16)
        dark_counts=[]
        for progress in (.06,.15,.26):
            pixels=np.asarray(capture.render(run,progress)[0],dtype=np.int16)
            dark=(pixels[:,:,:3].sum(axis=2)<source[:,:,:3].sum(axis=2)*.45)
            dark_counts.append(int(dark.sum()))
            # The photo itself stays registered and still: almost all changed
            # pixels are the narrow growing fissures, not movement or a fade.
            assert np.all(pixels==source,axis=2).mean()>.90
        assert 0<dark_counts[0]<dark_counts[1]<dark_counts[2]
        assert dark_counts[2]>640*360*.005
        no_debris=capture.run("crumble",parameters={**_CALIBRATED,"weight_mode":0.0,"debris":0.0})
        assert capture.render(run,.26)[0].tobytes()==capture.render(no_debris,.26)[0].tobytes()
        falling=np.asarray(capture.render(run,.55)[0],dtype=np.int16)
        assert np.all(falling==source,axis=2).mean()<.65
    finally:
        capture.close()
