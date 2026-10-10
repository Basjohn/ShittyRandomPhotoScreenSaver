"""Lazy Quick renderer for Membrane Turnover: the old picture's membrane twists over and away."""

from __future__ import annotations

from collections.abc import Mapping

from OpenGL import GL as gl

from rendering.gl_programs.membrane_options import MEMBRANE_SWEEP_VECTORS
from rendering.gl_programs.membrane_program import MEMBRANE_DONE, MEMBRANE_FRAGMENT_SOURCE, MEMBRANE_VERTEX_SOURCE
from rendering.gl_programs.scene3d import (
    scene3d_detail,
    scene3d_grid_size,
    scene3d_grid_vertices,
    scene3d_request_samples,
)
from rendering.quick.scene3d.environment import PHOTO_ENVIRONMENT_PROGRAM, PhotoEnvironment
from rendering.quick.scene3d.grid import draw_grid
from rendering.quick.scene3d.resources import UNDERLAY_PROGRAM, MeshResources, bind_frame, warm_programs
from rendering.quick.scene3d.target import SceneTarget, scene_target_programs, warm_run_resources
from ..render_contract import QuickTransitionRenderFrame


def membrane_parameters(parameters: Mapping[str, object]) -> tuple[float, int, str]:
    """The resolved gloss, seed and 3D Detail tier, validated before any GL state changes."""
    gloss, seed, detail = parameters.get("gloss"), parameters.get("seed"), parameters.get("detail")
    if isinstance(gloss, bool) or not isinstance(gloss, (int, float)) or not 0.0 <= float(gloss) <= 1.0:
        raise ValueError("Membrane Turnover needs a resolved gloss between 0 and 1")
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise ValueError("Membrane Turnover needs a resolved seed")
    if not isinstance(detail, str):
        raise ValueError("Membrane Turnover needs a resolved 3D Detail tier")
    return float(gloss), seed, detail


class QuickMembraneRenderer:
    transition_id = "membrane"

    _UNIFORMS = ("uMatrix", "uItemSize", "uGridCells", "uSweep", "uProgress", "uSpin", "uSeed", "uGloss",
                 "uOldTex", "uNewTex", "uEnvironment")

    def __init__(self) -> None:
        self._resources = MeshResources("Quick Membrane Turnover")
        self._target = SceneTarget("Quick Membrane Turnover")
        self._environment = PhotoEnvironment("Quick Membrane Turnover")

    @property
    def has_resources(self) -> bool:
        return self._resources.has_resources or self._target.has_resources or self._environment.has_resources

    def render(self, frame: QuickTransitionRenderFrame) -> None:
        progress = max(0.0, min(1.0, float(frame.sample.eased_progress)))
        sweep = MEMBRANE_SWEEP_VECTORS.get(str(frame.run.request.direction))
        if sweep is None:
            raise ValueError(f"unknown resolved Membrane Turnover sweep: {frame.run.request.direction!r}")
        parameters = frame.run.request.parameter_dict()
        gloss, seed, detail = membrane_parameters(parameters)
        try:
            if progress <= 0.0:
                self._resources.draw_image(frame, frame.source_texture_id)
                return
            # Every part of the membrane has landed and faded away: the new picture.
            if progress >= MEMBRANE_DONE:
                self._resources.draw_image(frame, frame.destination_texture_id)
                return
            samples = scene3d_request_samples(parameters)
            environment = self._environment.texture(frame, self._resources)
            if samples:
                with self._target.scope(frame, samples, self._resources):
                    self._draw(frame, progress, sweep, gloss, seed, detail, environment)
            else:
                self._draw(frame, progress, sweep, gloss, seed, detail, environment)
        except Exception:
            self.release_resources()
            raise

    def warm(self, parameters, size: tuple[int, int] | None = None) -> bool:
        """One bounded step of the gradual warm-up for a run with ``parameters`` (render thread,
        between runs): True once that run's first frame will compile nothing and, given the
        render ``size`` in device pixels, allocate nothing."""
        _gloss, _seed, detail = membrane_parameters(parameters)
        samples = scene3d_request_samples(parameters)
        r = self._resources
        entries = [(r, *UNDERLAY_PROGRAM), (r, *PHOTO_ENVIRONMENT_PROGRAM),
                   (r, "membrane", MEMBRANE_VERTEX_SOURCE, MEMBRANE_FRAGMENT_SOURCE)]
        if samples:
            entries += [(r, *program) for program in scene_target_programs(samples, False, False)]
        if not warm_programs(entries):
            return False
        if size is not None:
            columns, rows = scene3d_grid_size(scene3d_detail(detail), size[0] / max(1, size[1]))
            key = f"scene_grid_{columns}x{rows}"
            if not r.has_mesh(key):
                r.mesh(key, scene3d_grid_vertices(columns, rows), (2,))
                return False
        return warm_run_resources(self._target, None, size, samples)

    def park(self) -> None:
        """Drop the per-run target and photo copy; programs and grids stay warm."""
        self._target.release()
        self._environment.release()

    def _draw(self, frame, progress: float, sweep, gloss: float, seed: int, detail: str, environment: int) -> None:
        r = self._resources
        r.draw_image(frame, frame.destination_texture_id)        # the new picture under the membrane
        r.begin_depth(frame)
        program = r.program("membrane", MEMBRANE_VERTEX_SOURCE, MEMBRANE_FRAGMENT_SOURCE)
        # The new picture is drawn underneath, so the sheet itself never reads uNewTex.
        uniforms = r.uniforms("membrane", self._UNIFORMS, required=False)
        bind_frame(program, uniforms, frame)
        width, height = frame.logical_size
        columns, rows = scene3d_grid_size(scene3d_detail(detail), width / height)
        gl.glUniform2f(uniforms["uGridCells"], float(columns), float(rows))
        gl.glUniform2f(uniforms["uSweep"], *sweep)
        gl.glUniform1f(uniforms["uProgress"], progress)
        gl.glUniform1f(uniforms["uSpin"], 1.0 if seed % 2 else -1.0)
        gl.glUniform1f(uniforms["uSeed"], float(seed % 997))
        gl.glUniform1f(uniforms["uGloss"], gloss)
        # Units 0 and 1 hold the photographs (bind_frame); the copy goes on 2 (restored by the host fence).
        gl.glActiveTexture(gl.GL_TEXTURE2)
        gl.glBindTexture(gl.GL_TEXTURE_2D, environment)
        gl.glUniform1i(uniforms["uEnvironment"], 2)
        gl.glActiveTexture(gl.GL_TEXTURE0)
        gl.glEnable(gl.GL_BLEND)
        gl.glBlendFuncSeparate(gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA, gl.GL_ONE, gl.GL_ONE_MINUS_SRC_ALPHA)
        try:
            draw_grid(r, columns, rows)
        finally:
            gl.glDisable(gl.GL_BLEND)

    def release_resources(self) -> None:
        errors: list[str] = []
        for release in (self._target.release, self._environment.release, self._resources.release_resources):
            try:
                release()
            except Exception as exc:
                errors.append(str(exc))
        if errors:
            raise RuntimeError(" | ".join(errors))


def create_transition_renderer() -> QuickMembraneRenderer:
    return QuickMembraneRenderer()
