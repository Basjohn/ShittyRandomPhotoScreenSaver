"""Volume, debris and continuous-departure contracts for Quick Crumble."""

from rendering.gl_programs.crumble_program import (
    CRUMBLE_CHIP_VERTICES,
    CRUMBLE_FRAGMENT,
    CRUMBLE_VERTEX,
    DEBRIS_VERTEX,
)
from rendering.quick.transitions.implementations.crumble import (
    _crumble_parameters,
    _debris_instances,
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


def test_debris_metadata_is_bounded_seeded_and_tied_to_static_fracture():
    shards = fracture_cells(12, 128, 16 / 9, 2.0)
    first = _debris_instances(12.5, shards, 0.65)
    assert (
        first == _debris_instances(12.5, shards, 0.65) and 12 <= len(first) // 6 <= 512
    )
    assert first != _debris_instances(19.5, shards, 0.65)


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
    capture = TransitionCapture(320, 180)
    try:
        base = np.asarray(
            capture.render(capture.run("crumble"), 0.53)[0], dtype=np.int16
        )
        changed = np.asarray(
            capture.render(capture.run("crumble", parameters={field: value}), 0.53)[0],
            dtype=np.int16,
        )
        assert np.abs(base - changed).mean() > 0.08, field
    finally:
        capture.close()


def test_crumble_preserves_fractional_seed_identity_and_seam_origins():
    from rendering.quick.transitions.fracture_geometry import fracture_cells
    from rendering.quick.transitions.implementations.crumble import _debris_instances
    import numpy as np

    first = fracture_cells(12.1, 16, 16 / 9)
    assert first != fracture_cells(12.9, 16, 16 / 9)
    instances = np.asarray(_debris_instances(12.1, first, 0.65)).reshape(-1, 6)
    for index, instance in enumerate(instances):
        shard = first[index % len(first)]
        assert tuple(instance[2:4]) == shard.center
        assert instance[4] == shard.variation
        a = np.asarray(shard.polygon[index % len(shard.polygon)])
        b = np.asarray(shard.polygon[(index + 1) % len(shard.polygon)])
        edge = b - a
        point = instance[:2] - a
        assert abs(edge[0] * point[1] - edge[1] * point[0]) < 1e-12
        assert -1e-12 <= float(point @ edge) <= float(edge @ edge) + 1e-12


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
        run=capture.run("crumble",parameters={"weight_mode":0.0})
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
        no_debris=capture.run("crumble",parameters={"weight_mode":0.0,"debris":0.0})
        assert capture.render(run,.26)[0].tobytes()==capture.render(no_debris,.26)[0].tobytes()
        falling=np.asarray(capture.render(run,.55)[0],dtype=np.int16)
        assert np.all(falling==source,axis=2).mean()<.65
    finally:
        capture.close()
