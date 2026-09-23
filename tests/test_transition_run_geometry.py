"""Per-run fracture geometry is prepared off the render thread with identical bytes (TX-01)."""

from __future__ import annotations

import ctypes
from types import SimpleNamespace

import pytest

from rendering.quick.transitions.fracture_geometry import fracture_cells, fracture_vertices
from rendering.quick.transitions.mesh_support import pack_floats
from rendering.quick.transitions.run_geometry import (
    PREPARED_GEOMETRY,
    PreparedGeometryCache,
    build_crumble_geometry,
    build_glass_geometry,
    crumble_geometry_key,
    crumble_vertices,
    debris_instances,
    glass_geometry_key,
    prepare_run_geometry,
)

_ASPECT = 2560 / 1440
_GLASS = {"seed": 417, "shards": 95}
_CRUMBLE = {
    "seed": 123.25,
    "piece_count": 35,
    "crack_complexity": 1.0,
    "weight_mode": 3.0,
    "depth": 0.85,
    "thickness": 0.65,
    "debris": 0.65,
}


def _ctypes_reference(values) -> bytes:
    """The render-thread packing used before TX-01."""
    return bytes((ctypes.c_float * len(values))(*values))


@pytest.fixture(autouse=True)
def _clean_prepared_store():
    PREPARED_GEOMETRY.clear()
    yield
    PREPARED_GEOMETRY.clear()


def test_pack_floats_is_byte_identical_to_ctypes_constructor() -> None:
    values = fracture_vertices(fracture_cells(9, 40, _ASPECT), _ASPECT)
    storage, packed = pack_floats(values)
    assert bytes(packed) == storage.tobytes() == _ctypes_reference(values)


def test_glass_geometry_matches_the_previous_render_thread_build() -> None:
    key = glass_geometry_key(_GLASS, _ASPECT)
    reference = fracture_vertices(fracture_cells(417, 95, _ASPECT), _ASPECT)
    assert build_glass_geometry(key).vertices == _ctypes_reference(reference)


def test_crumble_geometry_matches_the_previous_render_thread_build() -> None:
    key = crumble_geometry_key(_CRUMBLE, _ASPECT)
    shards = fracture_cells(123.25, 35, _ASPECT, 1.0)
    geometry = build_crumble_geometry(key)
    assert geometry.chunks == _ctypes_reference(crumble_vertices(shards, _ASPECT))
    assert geometry.debris == _ctypes_reference(debris_instances(123.25, shards, 0.65))

    no_debris = build_crumble_geometry(crumble_geometry_key({**_CRUMBLE, "debris": 0.0}, _ASPECT))
    assert no_debris.chunks == geometry.chunks
    assert no_debris.debris == b""


def test_prepared_geometry_is_used_without_rebuilding() -> None:
    prepare_run_geometry("glass_shatter", _GLASS, (_ASPECT, _ASPECT, 16 / 10))
    key = glass_geometry_key(_GLASS, _ASPECT)
    prepared = PREPARED_GEOMETRY.get(key)
    assert prepared is not None
    assert PREPARED_GEOMETRY.get(glass_geometry_key(_GLASS, 16 / 10)) is not None

    def _must_not_build(_key):
        raise AssertionError("render thread rebuilt prepared geometry")

    assert PREPARED_GEOMETRY.get_or_build(key, _must_not_build) is prepared


def test_missing_preparation_builds_the_same_bytes_synchronously() -> None:
    key = crumble_geometry_key(_CRUMBLE, _ASPECT)
    built = PREPARED_GEOMETRY.get_or_build(key, build_crumble_geometry)
    assert built == build_crumble_geometry(key)
    assert PREPARED_GEOMETRY.get(key) is built


def test_preparation_failure_is_silent_and_stores_nothing() -> None:
    prepare_run_geometry("crumble", {**_CRUMBLE, "piece_count": 999}, (_ASPECT,))
    prepare_run_geometry("crossfade", {}, (_ASPECT,))
    prepare_run_geometry("glass_shatter", {"seed": 1}, (_ASPECT,))
    assert PREPARED_GEOMETRY.get(glass_geometry_key(_GLASS, _ASPECT)) is None


def test_prepared_store_is_bounded() -> None:
    cache = PreparedGeometryCache(capacity=2)
    cache.put("a", 1)
    cache.put("b", 2)
    assert cache.get("a") == 1  # refresh "a"
    cache.put("c", 3)
    assert cache.get("b") is None
    assert cache.get("a") == 1 and cache.get("c") == 3


def test_display_manager_prepares_geometry_once_per_batch_on_compute(qt_app) -> None:
    from engine.display_manager import DisplayManager
    from rendering.quick.transitions.request_resolution import RandomTransitionSelection

    submitted: list[tuple] = []

    class _Threads:
        def submit_compute_task(self, func, *args, **kwargs):
            submitted.append((func, args, kwargs))
            return "task"

    class _Settings:
        def get(self, key, default=None):
            if key == "transitions":
                return {
                    "type": "Crossfade",
                    "random_always": True,
                    "pool": {"Crumble": True, "Slide": True},
                }
            if key == "display.hw_accel":
                return True
            return default

        def get_bool(self, key, default=False):
            return bool(self.get(key, default))

    def _unit(width: float, height: float):
        return SimpleNamespace(
            display_bounds=lambda: SimpleNamespace(x=0.0, y=0.0, width=width, height=height)
        )

    manager = DisplayManager(settings_manager=_Settings(), thread_manager=_Threads(), runtime_generation=705)
    try:
        manager.displays = [_unit(2560.0, 1440.0), _unit(1920.0, 1200.0)]
        manager.set_random_transition_selection(RandomTransitionSelection("Crumble"))
        spec = manager._resolve_quick_transition_batch_spec()
        assert spec is not None and spec.transition_id == "crumble"
        manager._resolve_quick_transition_batch_spec()

        assert len(submitted) == 1
        func, args, kwargs = submitted[0]
        assert func is prepare_run_geometry
        assert args[0] == "crumble"
        assert args[1] == dict(spec.parameters)
        assert args[2] == (2560.0 / 1440.0, 1920.0 / 1200.0)
        assert kwargs == {"category": "transition_geometry"}

        manager._reset_quick_transition_batch()
        manager.set_random_transition_selection(RandomTransitionSelection("Slide"))
        assert manager._resolve_quick_transition_batch_spec().transition_id == "slide"
        assert len(submitted) == 1
    finally:
        manager.displays = []
        manager.disconnect_monitor_detection()
        manager.deleteLater()
        qt_app.processEvents()
