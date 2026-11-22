"""Lazy, instanced renderer for Exploding Tiles.

Four passes per frame, all analytic from the run's progress: the new photograph
lit by the blast, soft tile shadows on it (MIN-blended, 3D Detail permitting),
the beveled slabs (depth-tested), then additive sparks. Their shared per-frame
values travel in one uniform block. With anti-aliasing, bloom or motion blur the
passes render into a scene target that the host's park drops after the run; with
motion blur the slabs also write their screen motion over the shutter.
"""

from __future__ import annotations

from OpenGL import GL as gl
from rendering.gl_programs.exploding_tiles_program import (
    EXPLODING_TILES_BACKDROP_BLOCK,
    EXPLODING_TILES_BACKDROP_FRAGMENT_SOURCE,
    EXPLODING_TILES_BACKDROP_VERTEX_SOURCE,
    EXPLODING_TILES_BLOCK,
    EXPLODING_TILES_BOX_VERTICES,
    EXPLODING_TILES_FRAGMENT_SOURCE,
    EXPLODING_TILES_FRAME_BLOCK,
    EXPLODING_TILES_GHOST_FRAGMENT_SOURCE,
    EXPLODING_TILES_SHADOW_BLOCK,
    EXPLODING_TILES_SHADOW_FRAGMENT_SOURCE,
    EXPLODING_TILES_SHADOW_VERTEX_SOURCE,
    EXPLODING_TILES_SPARK_BLOCK,
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
from rendering.gl_programs.portable import pack_block
from rendering.gl_programs.scene3d import (
    SCENE3D_TRAIL_GHOSTS,
    scene3d_detail,
    scene3d_shutter_progress,
    scene3d_trail_ghosts,
)
from rendering.quick.scene3d.environment import (PHOTO_ENVIRONMENT_MIPS_PROGRAM, PHOTO_ENVIRONMENT_PROGRAM,
                                                 PhotoEnvironment)
from rendering.quick.scene3d.particles import draw_particles, particle_budget
from rendering.quick.scene3d.resources import UNDERLAY_PROGRAM, MeshResources, bind_frame, warm_programs, warm_pass_blocks
from rendering.quick.scene3d.shadows import draw_planar_shadows
from rendering.quick.scene3d.trails import TRAIL_EDGES_PROGRAM, MotionTrails, trail_program
from rendering.quick.scene3d.target import SceneTarget, scene_target_programs, warm_run_resources
from rendering.quick.scene3d.stream import StreamRing
from rendering.quick.scene3d.uniforms import UniformBlock
from rendering.quick.scene3d.resources import pack_floats
from ..directions import direction_vector
from ..native_scene import (QUAD_MESH, TRAIL_EDGES_PASS, NativeScene, NativeSceneMesh, NativeScenePass,
                            NativeScenePasses, eased_show, ghost_pass_name, native_clip_depth, native_one_block,
                            native_without_motion)
from ..render_contract import QuickTransitionRenderFrame

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

    def __init__(self) -> None:
        # A ghost pass gives each of its draws its own pass block copy.
        self._resources = MeshResources("Quick Exploding Tiles", copies=SCENE3D_TRAIL_GHOSTS)
        self._target = SceneTarget("Quick Exploding Tiles")
        self._environment = PhotoEnvironment("Quick Exploding Tiles")   # photo reflections
        self._trails = MotionTrails("Quick Exploding Tiles")
        # Both blocks stream through one ring; the ghosts' values are rebound copies, so the
        # real tiles keep theirs.
        self._stream = StreamRing("Quick Exploding Tiles")
        self._ghost_block = UniformBlock(EXPLODING_TILES_FRAME_BLOCK, "Quick Exploding Tiles ghosts", self._stream)
        self._frame_block = UniformBlock(EXPLODING_TILES_FRAME_BLOCK, "Quick Exploding Tiles", self._stream)
        self._body_key: tuple[int, str] | None = None
        self._body = (0.15, 0.15, 0.15)

    @property
    def has_resources(self) -> bool:
        return (self._resources.has_resources or self._target.has_resources or self._stream.has_resources
                or self._environment.has_resources or self._trails.has_resources)

    def render(self, frame: QuickTransitionRenderFrame) -> None:
        progress = max(0.0, min(1.0, float(frame.sample.eased_progress)))
        try:
            if progress <= 0.0:
                self._resources.draw_image(frame, frame.source_texture_id)
                return
            if progress >= 1.0:
                self._resources.draw_image(frame, frame.destination_texture_id)
                return
            (seed, columns, depth, thickness, force, detail_name, samples, bloom,
             motion_blur, trails) = exploding_tiles_parameters(frame.run.request.parameter_dict())
            # Multisampling, bloom and motion blur arrive resolved (this transition's settings
            # over the 3D Detail tier); the tier itself still sets shadows and the spark budget.
            detail = scene3d_detail(detail_name)
            samples = samples or (1 if bloom > 0.0 or motion_blur or trails else 0)
            grid = exploding_tiles_grid(columns, frame.viewport[2], frame.viewport[3])
            center_out = str(frame.run.request.direction) == "center_out"
            values = self._frame_values(frame.run, progress, frame.logical_size,
                                        (frame.viewport[2], frame.viewport[3]))
            environment = self._environment.texture(frame, self._resources)
            with self._frame_block.bound(values):
                if samples:
                    with self._target.scope(frame, samples, self._resources, bloom=bloom, motion_blur=motion_blur):
                        self._draw_scene(frame, grid, detail, progress, force, center_out, environment,
                                         values if trails else None)
                else:
                    self._draw_scene(frame, grid, detail, progress, force, center_out, environment)
        except Exception:
            self.release_resources()
            raise

    def warm(self, parameters, size: tuple[int, int] | None = None) -> bool:
        """One bounded step of the gradual warm-up for a run with ``parameters`` (render thread,
        between runs): True once that run's first frame will compile nothing and, given the
        render ``size`` in device pixels, allocate nothing."""
        (_seed, _columns, _depth, _thickness, _force, detail_name, samples, bloom,
         motion_blur, trails) = exploding_tiles_parameters(parameters)
        detail = scene3d_detail(detail_name)
        samples = samples or (1 if bloom > 0.0 or motion_blur or trails else 0)
        r = self._resources
        entries = [(r, *UNDERLAY_PROGRAM), (r, *PHOTO_ENVIRONMENT_PROGRAM), (r, *PHOTO_ENVIRONMENT_MIPS_PROGRAM),
                   (r, "backdrop", EXPLODING_TILES_BACKDROP_VERTEX_SOURCE, EXPLODING_TILES_BACKDROP_FRAGMENT_SOURCE)]
        if detail.shadows:
            entries.append((r, "shadows", EXPLODING_TILES_SHADOW_VERTEX_SOURCE, EXPLODING_TILES_SHADOW_FRAGMENT_SOURCE))
        entries.append((r, "tiles", EXPLODING_TILES_VERTEX_SOURCE, EXPLODING_TILES_FRAGMENT_SOURCE))
        if particle_budget(EXPLODING_TILES_SPARKS, detail):
            entries.append((r, "sparks", EXPLODING_TILES_SPARK_VERTEX_SOURCE, EXPLODING_TILES_SPARK_FRAGMENT_SOURCE))
        if trails:
            entries += [(r, "tiles_ghost", EXPLODING_TILES_VERTEX_SOURCE, EXPLODING_TILES_GHOST_FRAGMENT_SOURCE),
                        (r, *TRAIL_EDGES_PROGRAM)]
        if samples:
            entries += [(r, *program) for program in scene_target_programs(samples, bloom > 0.0, motion_blur)]
        if not warm_programs(entries) or not self._stream.warm():
            return False
        if not warm_pass_blocks(self._resources, size):
            return False
        return warm_run_resources(self._target, self._trails, size, samples, motion_blur=motion_blur,
                                  bloom=bloom > 0.0, with_trails=trails)

    def _draw_scene(self, frame, grid, detail, progress: float, force: float, center_out: bool,
                    environment: int, trail_values=None) -> None:
        tiles = grid[0] * grid[1]
        self._draw_backdrop(frame)
        if detail.shadows:
            self._draw_shadows(frame, tiles)
        if trail_values is not None:
            self._trails.draw(self._target, frame, self._resources,
                              scene3d_trail_ghosts(progress, frame.run.request.duration_ms),
                              lambda ghosts: self._draw_tile_ghosts(
                                  frame, ghosts, tiles, environment, trail_values, progress,
                              ))
        self._resources.begin_depth(frame)
        self._draw_tiles(frame, tiles, environment)
        sparks = particle_budget(EXPLODING_TILES_SPARKS, detail)
        if sparks and exploding_tiles_sparks_live(progress, force, center_out):
            self._draw_sparks(frame, sparks)

    def _use(self, key: str, vertex: str, fragment: str, names: tuple[str, ...], frame) -> dict:
        """Use the program with the frame block attached and the photographs ``names`` bound; its pass block's values
        (the frame's matrix and item size among them) are returned for the draw to bind."""
        program = self._resources.program(key, vertex, fragment)
        self._frame_block.attach(program)
        values = self._resources.values(key)
        bind_frame(program, self._resources.uniforms(key, names), frame, values)
        return values

    def _draw_backdrop(self, frame) -> None:
        values = self._use("backdrop", EXPLODING_TILES_BACKDROP_VERTEX_SOURCE, EXPLODING_TILES_BACKDROP_FRAGMENT_SOURCE,
                           ("uNewTex",), frame)
        gl.glDisable(gl.GL_DEPTH_TEST)
        gl.glDepthMask(gl.GL_FALSE)
        with self._resources.pass_blocks.bound(pack_block(EXPLODING_TILES_BACKDROP_BLOCK, values)):
            gl.glBindVertexArray(frame.quad_vao)
            gl.glDrawArrays(gl.GL_TRIANGLE_STRIP, 0, 4)

    def _draw_shadows(self, frame, tiles: int) -> None:
        values = self._use("shadows", EXPLODING_TILES_SHADOW_VERTEX_SOURCE, EXPLODING_TILES_SHADOW_FRAGMENT_SOURCE,
                           ("uNewTex",), frame)
        with self._resources.pass_blocks.bound(pack_block(EXPLODING_TILES_SHADOW_BLOCK, values)):
            draw_planar_shadows(frame, tiles)

    # The photograph the slabs read (bind_frame binds it); the environment's sampler is bound in the source.
    _TILE_SAMPLERS = ("uOldTex",)

    def _draw_tiles(self, frame, tiles: int, environment: int) -> None:
        values = self._use("tiles", EXPLODING_TILES_VERTEX_SOURCE, EXPLODING_TILES_FRAGMENT_SOURCE,
                           self._TILE_SAMPLERS, frame)
        gl.glActiveTexture(gl.GL_TEXTURE2)
        gl.glBindTexture(gl.GL_TEXTURE_2D, environment)
        gl.glActiveTexture(gl.GL_TEXTURE0)
        vao, count = self._resources.mesh("beveled_slab", EXPLODING_TILES_BOX_VERTICES, (3, 3, 2))
        gl.glBindVertexArray(vao)
        with self._target.velocity_writes(), \
                self._resources.pass_blocks.bound(pack_block(EXPLODING_TILES_BLOCK, values)):
            gl.glDrawArraysInstanced(gl.GL_TRIANGLES, 0, count, tiles)

    def _draw_tile_ghosts(self, frame, ghosts, tiles: int, environment: int, values, now: float) -> None:
        """One prepared tile ghost pass; only the ghost's time-derived block fields and fade change."""
        program, uniforms = trail_program(
            self._resources, "tiles", EXPLODING_TILES_VERTEX_SOURCE,
            EXPLODING_TILES_GHOST_FRAGMENT_SOURCE, self._TILE_SAMPLERS,
        )
        self._ghost_block.attach(program)
        pass_values = self._resources.values("tiles_ghost")
        bind_frame(program, uniforms, frame, pass_values)
        gl.glActiveTexture(gl.GL_TEXTURE2)
        gl.glBindTexture(gl.GL_TEXTURE_2D, environment)
        gl.glActiveTexture(gl.GL_TEXTURE0)
        vao, count = self._resources.mesh("beveled_slab", EXPLODING_TILES_BOX_VERTICES, (3, 3, 2))
        gl.glBindVertexArray(vao)
        ghosts = tuple(ghosts)
        if ghosts:
            pass_values["uGhostFade"] = ghosts[0][1]
        with self._ghost_block.bound(values), self._target.velocity_writes(), \
                self._resources.pass_blocks.bound(pack_block(EXPLODING_TILES_BLOCK, pass_values)) as rebind:
            for index, (time, fade) in enumerate(ghosts):
                # A negative shutter makes the ghost vertex stage find the tile at the moment now.
                self._ghost_block.update_fields({
                    "uProgress": time,
                    "uBlast": exploding_tiles_blast(time),
                    "uShutter": time - now,
                })
                if index:                  # each draw keeps the copy it was given (the ring's rebind)
                    pass_values["uGhostFade"] = fade
                    rebind(pack_block(EXPLODING_TILES_BLOCK, pass_values))
                gl.glDrawArraysInstanced(gl.GL_TRIANGLES, 0, count, tiles)

    def _draw_sparks(self, frame, count: int) -> None:
        values = self._use("sparks", EXPLODING_TILES_SPARK_VERTEX_SOURCE, EXPLODING_TILES_SPARK_FRAGMENT_SOURCE,
                           (), frame)
        with self._resources.pass_blocks.bound(pack_block(EXPLODING_TILES_SPARK_BLOCK, values)):
            draw_particles(frame, count)

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

    def park(self) -> None:
        """Drop the per-run target, environment and trails; programs, the slab mesh and the stream ring stay warm."""
        self._target.release()
        self._environment.release()
        self._trails.release()

    def release_resources(self) -> None:
        errors: list[str] = []
        for release in (self._target.release, self._environment.release, self._trails.release,
                        self._frame_block.release, self._ghost_block.release, self._stream.release,
                        self._resources.release_resources):
            try:
                release()
            except Exception as exc:
                errors.append(str(exc))
        if errors:
            raise RuntimeError(" | ".join(errors))


def create_transition_renderer() -> QuickExplodingTilesRenderer:
    return QuickExplodingTilesRenderer()
