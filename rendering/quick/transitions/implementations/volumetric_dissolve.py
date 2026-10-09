"""Lazy Quick renderer for Volumetric Dissolve: the old picture bursts into particles and mist
while the new one resolves through it."""

from __future__ import annotations

from collections.abc import Mapping

from OpenGL import GL as gl

from rendering.gl_programs.scene3d import scene3d_request_samples
from rendering.gl_programs.volumetric_dissolve_options import VOLUMETRIC_DIRECTIONS, VOLUMETRIC_PARTICLE_SIZE_RANGE
from rendering.gl_programs.volumetric_dissolve_program import (
    VOLUMETRIC_BACKDROP_FRAGMENT_SOURCE,
    VOLUMETRIC_FRAME_BLOCK,
    VOLUMETRIC_HOOKS,
    VOLUMETRIC_PARTICLE_FRAGMENT_SOURCE,
    VOLUMETRIC_PARTICLE_VERTEX_SOURCE,
    VOLUMETRIC_VERTICES,
    volumetric_grid,
)
from rendering.quick import gl_query
from rendering.quick.scene3d.environment import PHOTO_ENVIRONMENT_PROGRAM, PhotoEnvironment
from rendering.quick.scene3d.frame import ITEM_QUAD_VERTEX_SOURCE
from rendering.quick.scene3d.passes import blend_scope
from rendering.quick.scene3d.population import CompactedPopulation, population_programs
from rendering.quick.scene3d.resources import UNDERLAY_PROGRAM, MeshResources, bind_frame, warm_programs
from rendering.quick.scene3d.stream import StreamRing
from rendering.quick.scene3d.target import SceneTarget, scene_target_programs, warm_run_resources
from rendering.quick.scene3d.uniforms import UniformBlock
from ..directions import direction_vector
from ..render_contract import QuickTransitionRenderFrame

_DIRECTION_CODES = frozenset(VOLUMETRIC_DIRECTIONS.values())


def volumetric_parameters(parameters: Mapping[str, object]) -> tuple[int, int, float, float]:
    """The resolved seed, particle size, mist and depth, validated before any GL state changes."""
    seed, size = parameters.get("seed"), parameters.get("particle_size")
    mist, depth = parameters.get("mist"), parameters.get("depth")
    if isinstance(seed, bool) or not isinstance(seed, int) or not 1 <= seed <= 65535:
        raise ValueError("Volumetric Dissolve seed must be an integer between 1 and 65535")
    low, high = VOLUMETRIC_PARTICLE_SIZE_RANGE
    if isinstance(size, bool) or not isinstance(size, int) or not low <= size <= high:
        raise ValueError(f"Volumetric Dissolve particle size must be an integer between {low} and {high}")
    for name, value in (("mist", mist), ("depth", depth)):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0.0 <= float(value) <= 1.0:
            raise ValueError(f"Volumetric Dissolve {name} must be between 0 and 1")
    return seed, size, float(mist), float(depth)


def volumetric_sweep(direction: object) -> tuple[tuple[float, float], float]:
    """(unit sweep in item space, radial flag) for a resolved direction."""
    if direction not in _DIRECTION_CODES:
        raise ValueError(f"unknown resolved Volumetric Dissolve direction: {direction!r}")
    if direction == "center_out":
        return (0.0, 1.0), 1.0
    return direction_vector(direction), 0.0


class QuickVolumetricDissolveRenderer:
    transition_id = "volumetric_dissolve"

    _BACKDROP_UNIFORMS = ("uMatrix", "uItemSize", "uOldTex", "uNewTex", "uNewCopy", "uOldCopy")
    _PARTICLE_UNIFORMS = ("uMatrix", "uItemSize", "uOldTex", "uOldCopy")

    def __init__(self) -> None:
        label = "Quick Volumetric Dissolve"
        self._resources = MeshResources(label)
        self._target = SceneTarget(label)
        self._environment = PhotoEnvironment(label)
        self._particles = CompactedPopulation(label)
        self._stream = StreamRing(label)
        self._frame_block = UniformBlock(VOLUMETRIC_FRAME_BLOCK, label, self._stream)

    @property
    def has_resources(self) -> bool:
        return (self._resources.has_resources or self._target.has_resources or self._environment.has_resources
                or self._particles.has_resources or self._stream.has_resources)

    def render(self, frame: QuickTransitionRenderFrame) -> None:
        progress = max(0.0, min(1.0, float(frame.sample.eased_progress)))
        parameters = frame.run.request.parameter_dict()
        seed, size, mist, depth = volumetric_parameters(parameters)
        sweep, radial = volumetric_sweep(frame.run.request.direction)
        try:
            if progress <= 0.0:
                self._resources.draw_image(frame, frame.source_texture_id)
                return
            if progress >= 1.0:
                self._resources.draw_image(frame, frame.destination_texture_id)
                return
            columns, rows, _size = volumetric_grid(frame.viewport[2], frame.viewport[3], size)
            new_copy = self._environment.texture(frame, self._resources, "destination")
            old_copy = self._environment.texture(frame, self._resources, "source")
            values = {"uGrid": (columns, rows), "uDirection": sweep, "uFrameSize": frame.logical_size,
                      "uProgress": progress, "uSeed": seed, "uDepth": depth, "uMist": mist, "uRadial": radial}
            samples = scene3d_request_samples(parameters)
            if samples:
                with self._target.scope(frame, samples, self._resources):
                    self._draw(frame, values, columns * rows, new_copy, old_copy)
            else:
                self._draw(frame, values, columns * rows, new_copy, old_copy)
        except Exception:
            self.release_resources()
            raise

    def warm(self, parameters, size: tuple[int, int] | None = None) -> bool:
        """One bounded step of the gradual warm-up for a run with ``parameters`` (render thread,
        between runs): True once that run's first frame will compile nothing and, given the
        render ``size`` in device pixels, allocate nothing."""
        _seed, particle_size, _mist, _depth = volumetric_parameters(parameters)
        samples = scene3d_request_samples(parameters)
        r = self._resources
        entries = [(r, *UNDERLAY_PROGRAM), (r, *PHOTO_ENVIRONMENT_PROGRAM),
                   (r, "backdrop", ITEM_QUAD_VERTEX_SOURCE, VOLUMETRIC_BACKDROP_FRAGMENT_SOURCE),
                   (r, "particles", VOLUMETRIC_PARTICLE_VERTEX_SOURCE, VOLUMETRIC_PARTICLE_FRAGMENT_SOURCE)]
        entries += [(r, *program) for program in population_programs("particles", VOLUMETRIC_HOOKS)]
        if samples:
            entries += [(r, *program) for program in scene_target_programs(samples, False, False)]
        if not warm_programs(entries) or not self._stream.warm():
            return False
        if size is not None:
            columns, rows, _size = volumetric_grid(size[0], size[1], particle_size)
            if not self._particles.warm(columns * rows):
                return False
        return warm_run_resources(self._target, None, size, samples)

    def park(self) -> None:
        """Drop the per-run target, photo copies and particle population; programs and the stream stay warm."""
        self._target.release()
        self._environment.release()
        self._particles.release()

    def _draw(self, frame, values: dict, population: int, new_copy: int, old_copy: int) -> None:
        # Units 0 and 1 hold the photographs (bind_frame); the copies go on 2 and 3. The host
        # fence restores units 0-2; unit 3 is handed back here.
        gl.glActiveTexture(gl.GL_TEXTURE2)
        gl.glBindTexture(gl.GL_TEXTURE_2D, new_copy)
        gl.glActiveTexture(gl.GL_TEXTURE3)
        inherited = gl_query.get_int(gl.GL_TEXTURE_BINDING_2D)
        gl.glBindTexture(gl.GL_TEXTURE_2D, old_copy)
        gl.glActiveTexture(gl.GL_TEXTURE0)
        try:
            with self._frame_block.bound(values):
                self._draw_bound(frame, population)
        finally:
            gl.glActiveTexture(gl.GL_TEXTURE3)
            gl.glBindTexture(gl.GL_TEXTURE_2D, inherited)
            gl.glActiveTexture(gl.GL_TEXTURE0)

    def _draw_bound(self, frame, population: int) -> None:
        r = self._resources
        program = r.program("backdrop", ITEM_QUAD_VERTEX_SOURCE, VOLUMETRIC_BACKDROP_FRAGMENT_SOURCE)
        self._frame_block.attach(program)
        uniforms = r.uniforms("backdrop", self._BACKDROP_UNIFORMS)
        gl.glDisable(gl.GL_DEPTH_TEST)
        gl.glDepthMask(gl.GL_FALSE)
        bind_frame(program, uniforms, frame)
        gl.glUniform1i(uniforms["uNewCopy"], 2)
        gl.glUniform1i(uniforms["uOldCopy"], 3)
        gl.glBindVertexArray(frame.quad_vao)
        gl.glDrawArrays(gl.GL_TRIANGLE_STRIP, 0, 4)

        self._particles.warm(population)            # a no-op when warmed for this run's size

        def configure(_key: str, hook_program: int) -> None:
            self._frame_block.attach(hook_program)   # the hooks read the streamed frame block

        with self._particles.bound():
            self._particles.update(r, "particles", VOLUMETRIC_HOOKS, population, VOLUMETRIC_VERTICES, configure)
            program = r.program("particles", VOLUMETRIC_PARTICLE_VERTEX_SOURCE, VOLUMETRIC_PARTICLE_FRAGMENT_SOURCE)
            self._frame_block.attach(program)
            uniforms = r.uniforms("particles", self._PARTICLE_UNIFORMS)
            bind_frame(program, uniforms, frame)
            gl.glUniform1i(uniforms["uOldCopy"], 3)
            gl.glBindVertexArray(frame.quad_vao)
            with blend_scope(gl.GL_FUNC_ADD, gl.GL_ONE, gl.GL_ONE_MINUS_SRC_ALPHA):
                self._particles.draw(gl.GL_TRIANGLE_STRIP)

    def release_resources(self) -> None:
        errors: list[str] = []
        for release in (self._target.release, self._environment.release, self._particles.release,
                        self._frame_block.release, self._stream.release, self._resources.release_resources):
            try:
                release()
            except Exception as exc:
                errors.append(str(exc))
        if errors:
            raise RuntimeError(" | ".join(errors))


def create_transition_renderer() -> QuickVolumetricDissolveRenderer:
    return QuickVolumetricDissolveRenderer()
