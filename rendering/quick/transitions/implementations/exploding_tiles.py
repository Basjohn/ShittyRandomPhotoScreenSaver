"""Lazy, instanced renderer for Exploding Tiles.

Four passes per frame, all analytic from the run's progress: the new photograph
lit by the blast, soft tile shadows on it (MIN-blended, 3D Detail permitting),
the beveled slabs (depth-tested), then additive sparks. Their shared per-frame
values travel in one uniform block. With anti-aliasing, bloom or motion blur the
passes render into a scene target that the host's park drops after the run; with
motion blur the slabs also write their screen motion over the shutter.
"""

from __future__ import annotations

from rendering.gl_programs.exploding_tiles_program import (
    EXPLODING_TILES_BACKDROP_FRAGMENT_SOURCE,
    EXPLODING_TILES_BACKDROP_VERTEX_SOURCE,
    EXPLODING_TILES_BOX_VERTICES,
    EXPLODING_TILES_FRAGMENT_SOURCE,
    EXPLODING_TILES_FRAME_BLOCK,
    EXPLODING_TILES_GHOST_FRAGMENT_SOURCE,
    EXPLODING_TILES_SHADOW_FRAGMENT_SOURCE,
    EXPLODING_TILES_SHADOW_VERTEX_SOURCE,
    EXPLODING_TILES_SPARK_FRAGMENT_SOURCE,
    EXPLODING_TILES_SPARK_VERTEX_SOURCE,
    EXPLODING_TILES_SPARKS,
    EXPLODING_TILES_VERTEX_SOURCE,
    exploding_tiles_blast,
    exploding_tiles_epicentre,
    exploding_tiles_grid,
    exploding_tiles_parameters,
    exploding_tiles_sparks_live,
)
from rendering.gl_programs.photo_colour import photo_dominant_colour
from rendering.gl_programs.scene3d import scene3d_detail, scene3d_shutter_progress, scene3d_trail_ghosts
from rendering.quick.scene3d.particles import particle_budget
from rendering.quick.scene3d.resources import pack_floats
from ..directions import direction_vector
from ..native_scene import (QUAD_MESH, TRAIL_EDGES_PASS, NativeScene, NativeSceneMesh, NativeScenePass,
                            NativeScenePasses, eased_show, ghost_pass_name, native_clip_depth, native_one_block,
                            native_without_motion)

# N5.2e: the native scene's passes, the texts this renderer compiles with the frame block merged into each pass block
# (``native_one_block``: the core admits one block a pass), each stage writing its own clip depth given its native clip
# depth (the shadows' clip goes through uMatrix); the tile and spark counts are the settings TILE_INSTANCES and
# SPARK_INSTANCES (the spark budget while any can be alive, else 0: Python skips the pass).
TILE_INSTANCES = "tile_instances"
SPARK_INSTANCES = "spark_instances"
_SLAB_INPUTS = (("aPosition", 3), ("aNormal", 3), ("aUv", 2))
_TILE_SAMPLERS = (("uOldTex", "old"), ("uEnvironment", "environment"))
_FRAME = EXPLODING_TILES_FRAME_BLOCK.name


def _merged(vertex: str, fragment: str) -> tuple[str, str]:
    return native_one_block((vertex, fragment), _FRAME)


_SCENE_PASSES = (
    NativeScenePass("backdrop", *_merged(EXPLODING_TILES_BACKDROP_VERTEX_SOURCE, EXPLODING_TILES_BACKDROP_FRAGMENT_SOURCE),
                    QUAD_MESH, "triangle_strip", 4, samplers=(("uNewTex", "new"),)),
    NativeScenePass("shadows", *_merged(EXPLODING_TILES_SHADOW_VERTEX_SOURCE, EXPLODING_TILES_SHADOW_FRAGMENT_SOURCE),
                    QUAD_MESH, "triangle_strip", 4, TILE_INSTANCES, samplers=(("uNewTex", "new"),),
                    blend=(("min", "one", "one"), ("add", "zero", "one"))),
    NativeScenePass("tiles_ghost", *_merged(native_clip_depth(EXPLODING_TILES_VERTEX_SOURCE),
                                            EXPLODING_TILES_GHOST_FRAGMENT_SOURCE),
                    mesh="slab", instances=TILE_INSTANCES, samplers=_TILE_SAMPLERS, target="ghosts"),
    TRAIL_EDGES_PASS,
    NativeScenePass("tiles", *_merged(native_clip_depth(EXPLODING_TILES_VERTEX_SOURCE),
                                      native_without_motion(EXPLODING_TILES_FRAGMENT_SOURCE)),
                    mesh="slab", instances=TILE_INSTANCES, samplers=_TILE_SAMPLERS, depth=True),
    NativeScenePass("tiles_motion", *_merged(native_clip_depth(EXPLODING_TILES_VERTEX_SOURCE),
                                             EXPLODING_TILES_FRAGMENT_SOURCE),
                    mesh="slab", instances=TILE_INSTANCES, samplers=_TILE_SAMPLERS, depth=True, moves=True),
    NativeScenePass("sparks", *_merged(native_clip_depth(EXPLODING_TILES_SPARK_VERTEX_SOURCE),
                                       EXPLODING_TILES_SPARK_FRAGMENT_SOURCE),
                    QUAD_MESH, "triangle_strip", 4, SPARK_INSTANCES, depth=True, depth_write=False,
                    blend=(("add", "one", "one"), ("add", "one", "one"))),
)


class QuickExplodingTilesRenderer(NativeScenePasses):
    transition_id = "exploding_tiles"
    scene_pixels = True                  # N5.2e: its grid and motion read the item's device pixels

    # ------------------------------------------------------------------------------- N5.2e: the scene, one owner

    def __init__(self) -> None:
        self._body_key: tuple[int, str] | None = None
        self._body = (0.15, 0.15, 0.15)

    @classmethod
    def native_scene_passes(cls) -> tuple[NativeScenePass, ...]:
        return _SCENE_PASSES

    def native_scene(self, run, logical_size: tuple[float, float]) -> NativeScene:
        (_seed, _columns, _depth, _thickness, _force, detail_name, samples, bloom,
         motion, trails) = exploding_tiles_parameters(run.request.parameter_dict())
        detail = scene3d_detail(detail_name)
        samples = samples or (1 if bloom > 0.0 or motion or trails else 0)
        names = (["backdrop"] + (["shadows"] if detail.shadows else [])
                 + (["tiles_ghost", TRAIL_EDGES_PASS.name] if trails else [])
                 + ["tiles_motion" if motion else "tiles"]
                 + (["sparks"] if particle_budget(EXPLODING_TILES_SPARKS, detail) else []))
        passes = tuple(self.scene_pass(name) for name in names)
        slab = NativeSceneMesh("slab", pack_floats(EXPLODING_TILES_BOX_VERTICES), _SLAB_INPUTS)
        return NativeScene(passes, (slab,), samples, True, motion=motion, trails=trails, bloom=bloom)

    def scene_show(self, run, sample) -> int:
        return eased_show(max(0.0, min(1.0, float(sample.eased_progress))))

    def scene_values(self, run, sample, logical_size: tuple[float, float],
                     pixels: tuple[int, int] | None = None) -> dict[str, object]:
        """Every pass's values for the frame: the frame block's (``_frame_values``, one owner), the tile and spark
        counts, each drawn pass's ``uGhostFade`` (0 but on a ghost), and with trails each ghost's moment
        (``<member>@tiles_ghost_<k>``: its time, its blast, its shutter its time minus now, its fade)."""
        progress = max(0.0, min(1.0, float(sample.eased_progress)))
        parameters = run.request.parameter_dict()
        (_seed, _columns, _depth, _thickness, force, detail_name, _samples, _bloom,
         motion, trails) = exploding_tiles_parameters(parameters)
        if pixels is None:
            pixels = (round(logical_size[0]), round(logical_size[1]))
        values = self._frame_values(run, progress, logical_size, pixels)
        grid = values["uGrid"]
        detail = scene3d_detail(detail_name)
        sparks = particle_budget(EXPLODING_TILES_SPARKS, detail)
        values[TILE_INSTANCES] = int(grid[0] * grid[1])
        if sparks:
            live = exploding_tiles_sparks_live(progress, force, str(run.request.direction) == "center_out")
            values[SPARK_INSTANCES] = sparks if live else 0
        values[f"uGhostFade@{'tiles_motion' if motion else 'tiles'}"] = 0.0
        if trails:
            for age, (time, fade) in enumerate(scene3d_trail_ghosts(progress, run.request.duration_ms)):
                scope = ghost_pass_name("tiles_ghost", age)
                values[f"uProgress@{scope}"] = time
                values[f"uBlast@{scope}"] = exploding_tiles_blast(time)
                values[f"uShutter@{scope}"] = time - progress
                values[f"uGhostFade@{scope}"] = float(fade)
        return values

    # The photograph the slabs read (bind_frame binds it); the environment's sampler is bound in the source.
    _TILE_SAMPLERS = ("uOldTex",)

    def _frame_values(self, run, progress: float, logical_size: tuple[float, float],
                      pixels: tuple[int, int]) -> dict[str, object]:
        """The frame block's values (the one owner: ``render``'s and the native scene's), for the item's logical size
        and its device ``pixels`` (Python's ``frame.viewport`` size)."""
        (seed, columns, depth, thickness, force, _detail, samples, bloom,
         motion_blur, trails) = exploding_tiles_parameters(run.request.parameter_dict())
        samples = samples or (1 if bloom > 0.0 or motion_blur or trails else 0)
        direction = run.request.direction
        center_out = str(direction) == "center_out"
        width, height = logical_size
        epicentre = exploding_tiles_epicentre(None if center_out else direction_vector(direction), seed, width / height)
        return {
            "uGrid": exploding_tiles_grid(columns, int(pixels[0]), int(pixels[1])), "uProgress": progress,
            "uSeed": float(seed), "uDepth": depth, "uThickness": thickness, "uForce": force,
            "uCenterOut": 1 if center_out else 0, "uEpicentre": epicentre,
            "uSeconds": run.request.duration_ms / 1000.0, "uBlast": exploding_tiles_blast(progress),
            "uBody": self._body_colour(run), "uEmissive": 1.0 if samples and bloom > 0.0 else 0.0,
            "uShutter": scene3d_shutter_progress(run.request.duration_ms) if motion_blur else 0.0,
            "uViewport": (float(pixels[0]), float(pixels[1])),
        }

    def _body_colour(self, run) -> tuple[float, float, float]:
        """The source's most used colour, found once per run."""
        image = run.request.source_image
        key = (run.run_id, image.identity)
        if key != self._body_key:
            self._body = photo_dominant_colour(image.rgba8, image.pixel_size, image.row_stride)
            self._body_key = key
        return self._body


def create_transition_renderer() -> QuickExplodingTilesRenderer:
    return QuickExplodingTilesRenderer()
