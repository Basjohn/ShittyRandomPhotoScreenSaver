"""The compute-dispatch seam for scene3d consumers: explicit groups, explicit barriers, scoped image units.

A consumer compiles its compute program through ``MeshResources.compute_program`` (and lists it
for the gradual warm-up), uses it, binds its inputs and outputs, and calls ``dispatch``. The
dispatching owner also owns the barrier: ``dispatch`` takes the access its readers will make
(``GL_TEXTURE_FETCH_BARRIER_BIT`` for a sampler read, ``GL_SHADER_STORAGE_BARRIER_BIT`` for a storage
buffer, ...) and issues it straight after the dispatch, so no reader has to know a writer exists.

Image units are inherited context state the transition host does not fence; ``bound_image``
hands the unit's previous binding back. There is no queue, scheduler or readback here: the
work runs on the render thread that owns the context, in the frame that needs it.
"""
from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from OpenGL import GL as gl

from rendering.quick import gl_query


def dispatch(groups: tuple[int, int, int], barriers: int) -> None:
    """Dispatch the compute program in use over ``groups`` and make its writes visible to
    the later accesses named by ``barriers``."""
    x, y, z = (int(value) for value in groups)
    if min(x, y, z) < 1:
        raise ValueError(f"empty compute dispatch {groups}")
    if not barriers:
        raise ValueError("a compute dispatch names the barrier its readers need")
    gl.glDispatchCompute(x, y, z)
    gl.glMemoryBarrier(barriers)


@contextmanager
def bound_image(unit: int, texture: int, access: int, image_format: int) -> Iterator[None]:
    """Bind level 0 of ``texture`` to image ``unit`` for the scope, then restore the unit."""
    previous = gl_query.get_indexed_int(gl.GL_IMAGE_BINDING_NAME, unit)
    if previous:
        inherited = (previous,
                     gl_query.get_indexed_int(gl.GL_IMAGE_BINDING_LEVEL, unit),
                     gl_query.get_indexed_int(gl.GL_IMAGE_BINDING_LAYERED, unit),
                     gl_query.get_indexed_int(gl.GL_IMAGE_BINDING_LAYER, unit),
                     gl_query.get_indexed_int(gl.GL_IMAGE_BINDING_ACCESS, unit),
                     gl_query.get_indexed_int(gl.GL_IMAGE_BINDING_FORMAT, unit))
    gl.glBindImageTexture(unit, texture, 0, gl.GL_FALSE, 0, access, image_format)
    try:
        yield
    finally:
        if previous:
            name, level, layered, layer, previous_access, previous_format = inherited
            gl.glBindImageTexture(unit, name, level, bool(layered), layer, previous_access, previous_format)
        else:
            gl.glBindImageTexture(unit, 0, 0, gl.GL_FALSE, 0, gl.GL_READ_ONLY, gl.GL_R8)
