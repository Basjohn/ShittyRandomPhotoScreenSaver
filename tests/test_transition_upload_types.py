"""R-99: per-run mesh uploads must not mint a permanent ctypes array type each.

ctypes caches one array type per length for the life of the process. Glass and
Crumble meshes change size every run (random shard/chunk counts), so building
``c_float * n`` per upload added one permanent type per distinct size (22 over
132 offscreen runs, ~20 per 140 rotations on the Linux soak). Uploads now pass
plain bytes, which PyOpenGL hands to GL as a pointer.
"""
from __future__ import annotations

import gc

import pytest


def _array_types() -> set[int]:
    return {id(obj) for obj in gc.get_objects() if type(obj).__name__ == "PyCArrayType"}


@pytest.mark.qt
def test_varied_mesh_sizes_create_no_new_ctypes_array_types(qt_app):
    from tools.transition_contact_sheet import TransitionCapture

    capture = TransitionCapture(160, 90)
    try:
        effects = ("glass_shatter", "crumble")
        for effect in effects:  # one-time program/uniform/deletion types
            for seed in (1, 2):
                capture.render(capture.run(effect, seed=seed), 0.5)
        before = _array_types()
        for seed in range(3, 11):
            for effect in effects:
                run = capture.run(effect, seed=seed)
                for progress in (0.3, 0.7):
                    capture.render(run, progress)
        assert _array_types() - before == set()
    finally:
        capture.close()
