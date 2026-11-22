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

import re
from dataclasses import dataclass, field
from typing import Mapping

from .fullscreen_pass import SHOW_EFFECT, SHOW_NEW, SHOW_OLD

#: What a sampler of a scene pass reads: the run's old picture, its new one, the photo environment's mipped copy, (N5.2d)
#: a run texture the scene sends (``NativeSceneTexture``: Crumble's motion table, sampled nearest) or the trails'
#: ghost buffer (``ghosts``).
SCENE_TEXTURES = ("old", "new", "environment", "motion", "ghosts")
#: The built-in mesh: the item quad's four corners (``aPosition``, 0..1), drawn as a strip.
QUAD_MESH = "quad"
#: N5.2d (N4.i): the targets a scene pass draws into: the scene, or the trails' ghost buffer (R8, MAX).
SCENE_TARGETS = ("scene", "ghosts")


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
    #: N5.2d (N4.i): where it draws (``SCENE_TARGETS``), whether it writes the screen motion (a motion variant: every
    #: velocity attachment written; any other pass on a scene with motion blur masks them, as Python's
    #: ``velocity_writes``), and its viewport (``"allocation"``: the trails' edges, over the target's whole allocation).
    target: str = "scene"
    moves: bool = False
    viewport: str = "content"
    #: N5.2d: a pass with no vertex stage of its own (``vertex_source`` None) draws the core's triangle.
    core_triangle: bool = False
    #: N5.2e: whether a depth-tested pass also writes depth (None: as ``depth``); Exploding Tiles' sparks test and never
    #: write (Python's ``draw_particles``).
    depth_write: bool | None = None

    @property
    def writes_depth(self) -> bool:
        return self.depth if self.depth_write is None else bool(self.depth and self.depth_write)


@dataclass(frozen=True)
class NativeSceneTexture:
    """N5.2d: a texture a run sends with its meshes (Crumble's motion table): its kind (``SCENE_TEXTURES``), floats of
    ``size`` (``format`` ``"rgba32f"``, rows top first, as Python's ``glTexImage2D`` rows bottom first: one row a chunk,
    read by texelFetch, never filtered)."""

    kind: str
    pixels: bytes
    size: tuple[int, int]
    format: str = "rgba32f"


@dataclass(frozen=True)
class NativeScene:
    """A run's scene: its passes in order, its meshes, its requested samples (0: drawn single-sampled) and whether a
    pass reads the photo environment (N4.j: the destination's mipped copy, ``environment_size``). N5.2d (N4.i): whether
    the run blurs its motion (``motion``: the velocity attachments, the tile max, the gather) and draws trails
    (``trails``: the ghost buffer; the edges are one of its passes), and the textures it sends."""

    passes: tuple[NativeScenePass, ...]
    meshes: tuple[NativeSceneMesh, ...] = field(default=())
    samples: int = 0
    environment: bool = False
    motion: bool = False
    trails: bool = False
    textures: tuple[NativeSceneTexture, ...] = ()
    #: N5.2e: the bloom's strength (0: none). With bloom the scene's colour clears to (0, 0, 0, 0), its alpha the light
    #: each pass emits, and the bloom chain of the scene (after the gather with motion blur) adds its glow at the
    #: composite (Python's ``SceneTarget`` with ``bloom``).
    bloom: float = 0.0


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


# ------------------------------------------------------------------------------- N5.2d (N4.i): motion blur and trails

#: The shared post passes' packs (one each, beside the transitions' packs): Python's own texts (``motion.py``,
#: ``trails.py``) baked with the native frame's define (``motion.NATIVE_FRAME_GLSL``).
MOTION_TILE_MAX = "scene3d_motion_tile_max"
MOTION_GATHER = "scene3d_motion_gather"
TRAIL_EDGES = "scene3d_trail_edges"


def native_frame_text(text: str) -> str:
    """``text`` with the native frame's define after its ``#version`` line (the native core's pack of the same text)."""
    from rendering.quick.scene3d.motion import NATIVE_FRAME_DEFINE

    head, newline, rest = text.partition("\n")
    if not head.startswith("#version") or not newline:
        raise ValueError("a post pass's text starts with its #version line")
    return f"{head}\n#define {NATIVE_FRAME_DEFINE}\n{rest}"


def motion_post_sources() -> dict[str, str]:
    """The shared post passes' sources by file name (``tools/regen_qrc.py`` bakes ``<name>.qsb`` from each)."""
    from rendering.quick.scene3d.motion import MOTION_BLUR_PROGRAMS
    from rendering.quick.scene3d.trails import TRAIL_EDGES_PROGRAM

    (_tile_key, tile), (_gather_key, _vertex, gather) = MOTION_BLUR_PROGRAMS
    return {f"{MOTION_TILE_MAX}.comp": native_frame_text(tile), f"{MOTION_GATHER}.frag": native_frame_text(gather),
            f"{TRAIL_EDGES}.frag": native_frame_text(TRAIL_EDGES_PROGRAM[2])}


#: The trails' edge pass in a scene's pass list (after the underlay and the ghosts, before the pieces): the core's
#: triangle over the scene's whole allocation, blended as Python's ``blend_scope(ADD, SRC_ALPHA, ONE_MINUS_SRC_ALPHA)``:
#: the colour over, the alpha kept (ZERO, ONE). N5.2e: with bloom the alpha is emitted light, and an edge blended into it
#: lit every trail outline (N5.2d's opaque scenes never read it).
TRAIL_EDGES_PASS = NativeScenePass(TRAIL_EDGES, None, "", samplers=(("uGhosts", "ghosts"),), core_triangle=True,
                                   viewport="allocation",
                                   blend=(("add", "src_alpha", "one_minus_src_alpha"), ("add", "zero", "one")))


@dataclass(frozen=True)
class MotionGeometry:
    """Python's motion blur geometry for a scene of ``pixels`` (the item's pixel size): its SceneTarget allocation
    (64-pixel buckets), the tile edge (``motion_blur_tile`` of the allocation's height) and the tile counts."""

    allocation: tuple[int, int]
    tile: int
    tiles: tuple[int, int]


def motion_geometry(pixels: tuple[int, int]) -> MotionGeometry:
    from rendering.quick.scene3d.motion import motion_blur_tile
    from rendering.quick.scene3d.target import _bucket

    width, height = _bucket(int(pixels[0])), _bucket(int(pixels[1]))
    tile = motion_blur_tile(height)
    return MotionGeometry((width, height), tile, (-(-width // tile), -(-height // tile)))


def motion_post_values(scene: NativeScene, pixels: tuple[int, int]) -> dict[str, object]:
    """The post passes' values (Python's own: ``MotionBlur.apply``'s and ``MotionTrails.draw``'s blocks)."""
    from rendering.quick.scene3d.trails import TRAIL_STRENGTH, trail_line

    geometry = motion_geometry(pixels)
    values: dict[str, object] = {}
    if scene.motion or scene.trails:
        values["uSize"] = geometry.allocation
    if scene.motion:
        values.update({"uTile": geometry.tile, "uLongest": 2.0 * geometry.tile})
    if scene.trails:
        values.update({"uRadius": trail_line(geometry.allocation[1]), "uStrength": TRAIL_STRENGTH})
    return values


def ghost_pass_name(name: str, age: int) -> str:
    """A ghost pass's name in the program: one pass a ghost (``<pass>_<age>``), drawn from the same packs."""
    return f"{name}_{age}"


def ghost_values(name: str, ghosts, time_uniform: str, at, now: float) -> dict[str, object]:
    """Each ghost pass's own values (``<member>@<pass>``, ABI 37): its moment (``at(time)``: the members that place the
    piece then), the piece now (``<time_uniform>Before``: ``scene3d_ghost_fragment``'s distance test) and its fade
    (``draw_ghosts``'s, oldest first)."""
    values: dict[str, object] = {}
    for age, (time, fade) in enumerate(ghosts):
        scope = ghost_pass_name(name, age)
        for member, value in at(time).items():
            values[f"{member}@{scope}"] = value
        for member, value in at(now).items():
            values[f"{member}Before@{scope}"] = value
        values[f"uGhostFade@{scope}"] = float(fade)
    return values


#: The line ``native_clip_depth`` ends a vertex stage's main with.
NATIVE_CLIP_DEPTH_LINE = ("    gl_Position.z = uMatrix[2][2] * gl_Position.z + uMatrix[3][2] * gl_Position.w;"
                          "  // native: the backend's clip depth (uMatrix's z row)\n")


def native_clip_depth(vertex_source: str) -> str:
    """N5.2d: a vertex stage that writes its own clip depth after ``uMatrix`` (Block Spins: ``projected.z = ...``,
    OpenGL's -w..w) as the native core draws it on every backend: the core's ``uMatrix`` carries QRhi's clip-space
    correction (Vulkan's depth is 0..w: z row (0, 0, 0.5, 0.5)), which the stage's own depth bypasses, so the depth is
    put through the matrix's z row last. On OpenGL that row is (0, 0, 1, 0), the stage's depth exactly (rule a); without
    it Vulkan clips every fragment in front of the slab's middle (found 21 Nov on the ABI 37 build: half of each face
    gone). The Python renderer compiles its own text; this text is the native pack's."""
    body_end = vertex_source.rstrip().rfind("}")
    main = vertex_source.rfind("void main(")
    if body_end < 0 or main < 0 or vertex_source.find("{", main) < 0 or "uMatrix" not in vertex_source:
        raise ValueError("a vertex stage whose main is its last function and that reads uMatrix")
    if vertex_source.count("void main(") != 1 or NATIVE_CLIP_DEPTH_LINE in vertex_source:
        raise ValueError("one main, not yet given its native clip depth")
    depth, close = 0, -1
    for index in range(vertex_source.find("{", main), len(vertex_source)):
        depth += {"{": 1, "}": -1}.get(vertex_source[index], 0)
        if depth == 0:
            close = index
            break
    if close != body_end:
        raise ValueError("main is not the stage's last function")
    return vertex_source[:body_end] + NATIVE_CLIP_DEPTH_LINE + vertex_source[body_end:]


_STD140_BLOCK = re.compile(r"layout\s*\(\s*std140\s*,\s*binding\s*=\s*(\d+)\s*\)\s*uniform\s+(\w+)\s*\{")
_CONVENTIONS_BLOCK = "SrpssConventions"


def native_one_block(stages: tuple[str, ...], frame_block: str) -> tuple[str, ...]:
    """N5.2e: a pass's stages (vertex, fragment) whose programs declare their pass block and a shared frame block
    (Exploding Tiles' ``ExplodingTilesFrame``, one upload a frame in Python) as the native core draws them: one block of
    their own (the core admits one a pass), the pass block with the frame block's members appended, declared the same in
    every stage at the pass block's binding; every value still filled by name. A member in both blocks, a third block
    or a stage declaring a block differently is refused. The Python renderer compiles its own texts."""
    from rendering.gl_programs.portable import _strip_comments, block_declaration, block_layout_from_glsl
    from rendering.gl_programs.scene3d import Scene3DBlockLayout

    declarations: dict[str, tuple[str, int]] = {}
    for text in stages:
        for binding, name in _STD140_BLOCK.findall(_strip_comments(text)):
            if name == _CONVENTIONS_BLOCK:
                continue
            declaration = block_declaration(text, name)
            if declarations.setdefault(name, (declaration, int(binding)))[0] != declaration:
                raise ValueError(f"the stages declare the block {name} differently")
    if frame_block not in declarations:
        raise ValueError(f"no stage declares the frame block {frame_block}")
    own = [name for name in declarations if name != frame_block]
    if len(own) != 1:
        raise ValueError(f"a pass merges one block of its own with {frame_block}, not {own}")
    pass_name = own[0]
    pass_fields = block_layout_from_glsl(declarations[pass_name][0]).fields
    frame_fields = block_layout_from_glsl(declarations[frame_block][0]).fields
    doubled = sorted({name for name, _kind in pass_fields} & {name for name, _kind in frame_fields})
    if doubled:
        raise ValueError(f"{', '.join(doubled)} is a member of both {pass_name} and {frame_block}")
    merged = Scene3DBlockLayout.of(pass_name, tuple(pass_fields) + tuple(frame_fields)).glsl(declarations[pass_name][1])
    out = []
    for text in stages:
        for name in (pass_name, frame_block):
            text = text.replace(declarations[name][0].rstrip("\n"), "")
        if any(name in (pass_name, frame_block) for _binding, name in _STD140_BLOCK.findall(_strip_comments(text))):
            raise ValueError("a block declaration was not removed whole")
        head, newline, rest = text.partition("\n")
        if not head.startswith("#version") or not newline:
            raise ValueError("a stage starts with its #version line")
        out.append(f"{head}\n{merged}{rest}")
    return tuple(out)


def native_without_motion(fragment_source: str) -> str:
    """N5.2e: a fragment that always writes its screen motion (Exploding Tiles' tiles: ``SceneMotion`` and
    ``SceneMotionY`` at locations 1 and 2) as drawn on a scene without motion blur: its motion outputs plain variables
    (their writes dead), since the core refuses outputs past a target's attachments; Python masks the attachment."""
    for output in ("SceneMotion", "SceneMotionY"):
        fragment_source, count = re.subn(rf"layout\s*\(\s*location\s*=\s*\d+\s*\)\s*out\s+vec4\s+{output}\s*;",
                                         f"vec4 {output};", fragment_source)
        if count != 1:
            raise ValueError(f"a motion-writing fragment declares its {output} output once")
    return fragment_source


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


__all__ = ["MOTION_GATHER", "MOTION_TILE_MAX", "MotionGeometry", "NativeScene", "NativeSceneMesh", "NativeScenePass",
           "NativeScenePasses", "NativeSceneTexture", "QUAD_MESH", "SCENE_TARGETS", "SCENE_TEXTURES", "SHOW_EFFECT",
           "SHOW_NEW", "SHOW_OLD", "TRAIL_EDGES", "TRAIL_EDGES_PASS", "eased_show", "flat_values", "ghost_pass_name",
           "ghost_values", "item_quad_pass", "motion_geometry", "motion_post_sources", "motion_post_values",
           "NATIVE_CLIP_DEPTH_LINE", "native_clip_depth", "native_frame_text", "native_one_block",
           "native_without_motion"]
