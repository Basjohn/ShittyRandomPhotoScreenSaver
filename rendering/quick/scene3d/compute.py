"""The compute-dispatch seam for scene3d consumers: explicit groups, explicit barriers, scoped image units.

A consumer compiles its compute program through ``MeshResources.compute_program`` (and lists it
for the gradual warm-up), uses it, binds its inputs and outputs, and calls ``dispatch``. The
dispatching owner also owns the barrier: ``dispatch`` takes the access its readers will make
(``GL_TEXTURE_FETCH_BARRIER_BIT`` for a sampler read, ``GL_SHADER_STORAGE_BARRIER_BIT`` for a storage
buffer, ...) and issues it straight after the dispatch, so no reader has to know a writer exists.

Image units are inherited context state the transition host does not fence; ``bound_image``
hands the unit's previous binding back. There is no queue, scheduler or readback here: the
work runs on the render thread that owns the context, in the frame that needs it.

A dispatch's values travel in one std140 block (Vulkan GLSL has no loose uniforms): the program declares a
``Scene3DBlockLayout`` with ``layout.glsl(COMPUTE_BLOCK_BINDING)`` and the pass's owner, which holds a
``DispatchBlocks``, dispatches inside ``blocks.bound(layout.pack(values))``. Every resource a compute program declares
has its own binding number (samplers, images, storage buffers and the block: one namespace on Vulkan), so a texture
unit or image unit in OpenGL is the binding the source states.
"""
from __future__ import annotations

from contextlib import contextmanager
from typing import Callable, Iterator

from OpenGL import GL as gl

from rendering.gl_programs.scene3d import SCENE3D_COMPUTE_BLOCK_BINDING
from rendering.quick import gl_query

from .stream import StreamRing

# The uniform-buffer binding a compute pass reads its dispatch block from. Clear of every binding the compute programs
# use for samplers, images and storage (Extruded Bubble's drift solver holds 8-14), and of the draws' scene block
# (``SCENE3D_UNIFORM_BINDING``, 15) a pass may run inside; OpenGL 4.3 guarantees 36 points. The seam owns the point:
# each pass binds its own block and leaves the point unbound, so nothing inherits it.
COMPUTE_BLOCK_BINDING = SCENE3D_COMPUTE_BLOCK_BINDING
# One bound scope (a build's dispatches, each with its own copy at the uniform offset alignment, at most 256) holds at
# most this many bytes; a slot holds four scopes, so a fence falls every few frames at most.
_BLOCK_HOLD = 8192


class DispatchBlocks:
    """A compute pass owner's dispatch blocks: a small fenced stream ring (``stream.py``) bound at
    ``COMPUTE_BLOCK_BINDING``. Nothing is allocated until ``warm`` or the first ``bound``; ``release`` returns it to
    zero."""

    def __init__(self, label: str) -> None:
        self._ring = StreamRing(f"{label} dispatch blocks", slots=4, slot_bytes=4 * _BLOCK_HOLD, hold_bytes=_BLOCK_HOLD)

    @property
    def has_resources(self) -> bool:
        return self._ring.has_resources

    def warm(self) -> bool:
        """One warm-up step: True when the ring already exists, else allocate it."""
        return self._ring.warm()

    @contextmanager
    def bound(self, data: bytes) -> Iterator[Callable[[bytes], None]]:
        """Bind ``data`` (a packed std140 block) for the scope's dispatches; yields ``rebind(data)``, with which a
        later dispatch in the scope reads other values (each dispatch already submitted keeps its own copy). The
        point is left unbound afterwards: nothing is read back, and no later command can read the ring."""
        ring = self._ring
        with ring.bound(gl.GL_UNIFORM_BUFFER, COMPUTE_BLOCK_BINDING, data, restore=False):
            yield lambda values: ring.rebind(gl.GL_UNIFORM_BUFFER, COMPUTE_BLOCK_BINDING, values)

    def release(self) -> None:
        self._ring.release()


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
def bound_image(unit: int, texture: int, access: int, image_format: int, *, layered: bool = False,
                restore: bool = True) -> Iterator[None]:
    """Bind level 0 of ``texture`` to image ``unit`` for the scope, then restore the unit. ``layered`` exposes every
    layer (a 3D texture's whole depth to ``image3D``). ``restore=False``: the caller owns the unit for its frame, so
    nothing is read back (a driver round trip) and the unit is left unbound."""
    previous = gl_query.get_indexed_int(gl.GL_IMAGE_BINDING_NAME, unit) if restore else 0
    if previous:
        inherited = (previous,
                     gl_query.get_indexed_int(gl.GL_IMAGE_BINDING_LEVEL, unit),
                     gl_query.get_indexed_int(gl.GL_IMAGE_BINDING_LAYERED, unit),
                     gl_query.get_indexed_int(gl.GL_IMAGE_BINDING_LAYER, unit),
                     gl_query.get_indexed_int(gl.GL_IMAGE_BINDING_ACCESS, unit),
                     gl_query.get_indexed_int(gl.GL_IMAGE_BINDING_FORMAT, unit))
    gl.glBindImageTexture(unit, texture, 0, gl.GL_TRUE if layered else gl.GL_FALSE, 0, access, image_format)
    try:
        yield
    finally:
        if previous:
            name, level, layered, layer, previous_access, previous_format = inherited
            gl.glBindImageTexture(unit, name, level, bool(layered), layer, previous_access, previous_format)
        else:
            gl.glBindImageTexture(unit, 0, 0, gl.GL_FALSE, 0, gl.GL_READ_ONLY, gl.GL_R8)
