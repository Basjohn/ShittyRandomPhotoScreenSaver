"""The 3D transitions the native core draws as data (N5.2c: Blinds, Cube Turn, Depth Card Cascade, Jigsaw).

A ``NativeScenePasses`` renderer draws its run as a few passes into one scene target (colour, depth, the run's samples)
over meshes it builds once per run, with N4.j's photo environment, then composites the scene opaque: the Python
renderer's own shape (``rendering/quick/scene3d/target.py``'s opaque scope, or Quick's framebuffer with 0 samples,
which the core draws as a one-sample target copied exactly). It gives the native core three things, each read by its
own Python renderer too, so there is one owner of each:

- ``native_scene_passes()``: every pass any run may draw (its vertex and fragment texts are the ones the Python renderer
  compiles; ``tools/regen_qrc.py --shaders`` bakes them into ``<transition>_<pass>.vert.qsb`` / ``.frag.qsb``);
- ``native_scene(run, logical_size)``: the run's passes in order, its meshes (bytes and attribute names), its samples
  and whether it reads the photo environment;
- ``scene_show(run, sample)``: what the frame shows (the effect, or one of the two photographs exactly: the frames the
  Python renderer draws as the plain picture), and ``scene_values(run, sample, logical_size)``: every value of every
  pass's block for the frame, by name (one dict; a block takes the names it declares; ``uMatrix`` and ``uItemSize`` are
  the core's members).

The native layer (``rendering.quick.render.native_background``) shows the photographs at the ends with the background
layer's own program on either slot, and the effect with the scene's program.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

from .fullscreen_pass import SHOW_EFFECT, SHOW_NEW, SHOW_OLD

#: What a sampler of a scene pass reads: the run's old picture, its new one, or the photo environment's mipped copy.
SCENE_TEXTURES = ("old", "new", "environment")
#: The built-in mesh: the item quad's four corners (``aPosition``, 0..1), drawn as a strip.
QUAD_MESH = "quad"


@dataclass(frozen=True)
class NativeSceneMesh:
    """A run's mesh: interleaved f32 ``vertices`` with named ``attributes`` ((input name, floats), in order), and an
    optional instance stream (``instances`` with ``instance_attributes``)."""

    name: str
    vertices: bytes
    attributes: tuple[tuple[str, int], ...]
    instances: bytes | None = None
    instance_attributes: tuple[tuple[str, int], ...] = ()


@dataclass(frozen=True)
class NativeScenePass:
    """One pass of a scene: its ``name`` (its packs are ``<transition>_<name>``), the texts the Python renderer compiles,
    its geometry (``mesh``: ``QUAD_MESH`` or a run mesh's name; ``vertices``: a number or ``"mesh"``; ``instances``: a
    number, ``"mesh"`` (the instance stream's) or None for one), its ``samplers`` ((shader name, one of
    ``SCENE_TEXTURES``)), whether it tests and writes depth (LESS, after the flat passes: ``MeshResources.begin_depth``)
    and its ``blend``: ``"replace"`` or Python's ``((op, src, dst), (op, src, dst))`` for colour and alpha."""

    name: str
    vertex_source: str
    fragment_source: str
    mesh: str = QUAD_MESH
    topology: str = "triangles"
    vertices: int | str = "mesh"
    instances: int | str | None = None
    samplers: tuple[tuple[str, str], ...] = ()
    depth: bool = False
    blend: str | tuple = "replace"


@dataclass(frozen=True)
class NativeScene:
    """A run's scene: its passes in order, its meshes, its requested samples (0: drawn single-sampled) and whether a
    pass reads the photo environment (N4.j: the destination's mipped copy, ``environment_size``)."""

    passes: tuple[NativeScenePass, ...]
    meshes: tuple[NativeSceneMesh, ...] = field(default=())
    samples: int = 0
    environment: bool = False


def item_quad_pass(name: str, vertex_source: str, fragment_source: str, samplers: tuple[tuple[str, str], ...] = (),
                   **kw) -> NativeScenePass:
    """A pass drawn over the item quad (the Python renderer's ``frame.quad_vao``, a strip of four)."""
    return NativeScenePass(name, vertex_source, fragment_source, QUAD_MESH, "triangle_strip", 4, samplers=samplers, **kw)


class NativeScenePasses:
    """A transition the native core draws as a scene (the module notes)."""

    transition_id: str = ""

    @classmethod
    def native_scene_passes(cls) -> tuple[NativeScenePass, ...]:
        """Every pass any run of the transition may draw (packs are baked from these, discovered). A class method, so a
        renderer whose shader module loads lazily (Blinds' 3D Slats) loads it only when asked."""
        raise NotImplementedError

    def native_scene(self, run, logical_size: tuple[float, float]) -> NativeScene:
        raise NotImplementedError

    def scene_show(self, run, sample) -> int:
        """``SHOW_EFFECT``, or ``SHOW_OLD`` / ``SHOW_NEW`` where the Python renderer draws that photograph exactly."""
        raise NotImplementedError

    def scene_values(self, run, sample, logical_size: tuple[float, float]) -> dict[str, object]:
        raise NotImplementedError

    @classmethod
    def scene_pass(cls, name: str) -> NativeScenePass:
        for scene_pass in cls.native_scene_passes():
            if scene_pass.name == name:
                return scene_pass
        raise KeyError(f"{cls.transition_id} has no scene pass {name!r}")


def eased_show(progress: float, end: float = 1.0) -> int:
    """The show of a run whose Python renderer draws the old picture at progress 0 and the new one from ``end``."""
    if progress <= 0.0:
        return SHOW_OLD
    if progress >= end:
        return SHOW_NEW
    return SHOW_EFFECT


def flat_values(values: Mapping[str, object]) -> dict[str, object]:
    """``values`` with a packed std140 array of vec4s (bytes) given as its floats (the core packs arrays by element)."""
    import array

    out: dict[str, object] = {}
    for name, value in values.items():
        if isinstance(value, (bytes, bytearray)):
            out[name] = array.array("f", bytes(value)).tolist()
        else:
            out[name] = value
    return out


__all__ = ["NativeScene", "NativeSceneMesh", "NativeScenePass", "NativeScenePasses", "QUAD_MESH", "SCENE_TEXTURES",
           "SHOW_EFFECT", "SHOW_NEW", "SHOW_OLD", "eased_show", "flat_values", "item_quad_pass"]
