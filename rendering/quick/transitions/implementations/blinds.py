"""Lazy Quick renderer for Blinds: the canonical authored flat shader, or 3D Slats."""

from __future__ import annotations

from collections.abc import Mapping
import math

from OpenGL import GL as gl

from rendering.gl_programs.blinds_program import blinds_program
from rendering.gl_programs.scene3d import scene3d_request_samples
from rendering.quick.render.gl_resources import compile_program
from rendering.quick.scene3d.environment import PHOTO_ENVIRONMENT_PROGRAM, PhotoEnvironment
from rendering.quick.scene3d.frame import ITEM_QUAD_VERTEX_SOURCE
from rendering.quick.scene3d.resources import UNDERLAY_PROGRAM, MeshResources, bind_frame, warm_programs
from rendering.quick.scene3d.target import SceneTarget, scene_target_programs, warm_run_resources
from ..render_contract import (
    QUICK_TRANSITION_VERTEX_SOURCE,
    QuickTransitionRenderFrame,
)


_BLINDS_DIRECTION_MODES = {
    "horizontal": 0,
    "vertical": 1,
    "diagonal": 2,
}
_AUTHORED_SLAT_COLS = 7
_MIN_FEATHER = 0.001
_MAX_FEATHER = 0.5


def _blinds_direction_mode(direction: object) -> int:
    """Map one fully resolved authored direction to the shader mode."""

    value = str(direction).strip().lower()
    mode = _BLINDS_DIRECTION_MODES.get(value)
    if mode is None:
        raise ValueError(f"unknown resolved Blinds direction: {direction!r}")
    return mode


def _blinds_feather(parameters: Mapping[str, object]) -> float:
    """Read the resolved shader feather without a renderer-side UI fallback."""

    raw = parameters.get("feather")
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        raise ValueError("Blinds requires resolved numeric parameter 'feather'")
    value = float(raw)
    if not math.isfinite(value):
        raise ValueError("Blinds feather must be finite")
    if not _MIN_FEATHER <= value <= _MAX_FEATHER:
        raise ValueError(
            f"Blinds feather must be between {_MIN_FEATHER} and {_MAX_FEATHER}"
        )
    return value


def _blinds_grid(logical_size: tuple[float, float]) -> tuple[int, int]:
    """Preserve the compositor Blinds grid derived from display aspect ratio."""

    if len(logical_size) != 2:
        raise ValueError("Blinds logical size must contain width and height")
    width, height = (float(value) for value in logical_size)
    if not math.isfinite(width) or not math.isfinite(height):
        raise ValueError("Blinds logical size must be finite")
    if width <= 0.0 or height <= 0.0:
        raise ValueError("Blinds logical size must be positive")

    # GLCompositorBlindsTransition historically used its default slat_cols=7,
    # doubled it, then derived row count from the target aspect ratio.  Its
    # slat_rows constructor value never participated in the effective grid.
    cols = max(2, _AUTHORED_SLAT_COLS * 2)
    aspect = height / max(1.0, width)
    rows = max(2, int(round(cols * aspect)))
    return cols, rows


def _slats_parameters(parameters: Mapping[str, object]) -> tuple[int, float]:
    """The resolved 3D Slats count and gloss, validated before any GL state changes."""
    slats, gloss = parameters.get("slats"), parameters.get("gloss")
    if isinstance(slats, bool) or not isinstance(slats, int) or not 6 <= slats <= 48:
        raise ValueError("Blinds 3D Slats needs a resolved slat count between 6 and 48")
    if isinstance(gloss, bool) or not isinstance(gloss, (int, float)) or not 0.0 <= float(gloss) <= 1.0:
        raise ValueError("Blinds 3D Slats needs a resolved gloss between 0 and 1")
    return slats, float(gloss)


def _slats_style(parameters: Mapping[str, object]) -> bool:
    return parameters.get("style", "flat") == "slats"


def _slats_program():
    """The 3D Slats shader module, loaded the first time the style is used (Flat never loads it)."""
    from rendering.gl_programs import blinds_slats_program

    return blinds_slats_program


class QuickBlindsRenderer:
    transition_id = "blinds"

    _SLAT_UNIFORMS = ("uMatrix", "uItemSize", "uOldTex", "uNewTex", "uEnvironment", "uProgress", "uCount",
                      "uVertical", "uGloss")
    _BACKDROP_UNIFORMS = ("uMatrix", "uItemSize", "uNewTex", "uProgress", "uCount", "uVertical")

    def __init__(self) -> None:
        self._program = 0
        self._uniforms: dict[str, int] = {}
        # 3D Slats only: nothing below is touched by the flat style.
        self._resources = MeshResources("Quick Blinds 3D Slats")
        self._target = SceneTarget("Quick Blinds 3D Slats")
        self._environment = PhotoEnvironment("Quick Blinds 3D Slats")

    @property
    def has_resources(self) -> bool:
        return bool(self._program or self._resources.has_resources or self._target.has_resources
                    or self._environment.has_resources)

    def render(self, frame: QuickTransitionRenderFrame) -> None:
        parameters = frame.run.request.parameter_dict()
        if _slats_style(parameters):
            self._render_slats(frame, parameters)
            return
        if not self._program:
            self._initialize()
        uniforms = self._uniforms
        feather = _blinds_feather(parameters)
        direction = _blinds_direction_mode(frame.run.request.direction)
        cols, rows = _blinds_grid(frame.logical_size)

        gl.glUseProgram(self._program)
        gl.glUniformMatrix4fv(
            uniforms["uMatrix"],
            1,
            gl.GL_FALSE,
            frame.matrix_values,
        )
        gl.glUniform2f(uniforms["uItemSize"], *frame.logical_size)
        gl.glUniform1f(
            uniforms["u_progress"],
            float(frame.sample.eased_progress),
        )
        gl.glUniform2f(uniforms["u_grid"], float(cols), float(rows))
        gl.glUniform1f(uniforms["u_feather"], feather)
        gl.glUniform1i(uniforms["u_direction"], direction)
        gl.glActiveTexture(gl.GL_TEXTURE0)
        gl.glBindTexture(gl.GL_TEXTURE_2D, frame.source_texture_id)
        gl.glUniform1i(uniforms["uOldTex"], 0)
        gl.glActiveTexture(gl.GL_TEXTURE1)
        gl.glBindTexture(gl.GL_TEXTURE_2D, frame.destination_texture_id)
        gl.glUniform1i(uniforms["uNewTex"], 1)
        gl.glBindVertexArray(frame.quad_vao)
        gl.glDrawArrays(gl.GL_TRIANGLE_STRIP, 0, 4)

    def warm(self, parameters, size: tuple[int, int] | None = None) -> bool:
        """One bounded step of the gradual warm-up for a run with ``parameters`` (render thread,
        between runs). The flat style is one small program compiled on first use."""
        if not _slats_style(parameters):
            return True
        samples = scene3d_request_samples(parameters)
        r, shaders = self._resources, _slats_program()
        entries = [(r, *UNDERLAY_PROGRAM), (r, *PHOTO_ENVIRONMENT_PROGRAM),
                   (r, "backdrop", ITEM_QUAD_VERTEX_SOURCE, shaders.BLINDS_BACKDROP_FRAGMENT_SOURCE),
                   (r, "slats", shaders.BLINDS_SLATS_VERTEX_SOURCE, shaders.BLINDS_SLATS_FRAGMENT_SOURCE)]
        if samples:
            entries += [(r, *program) for program in scene_target_programs(samples, False, False)]
        if not warm_programs(entries):
            return False
        return warm_run_resources(self._target, None, size, samples)

    def park(self) -> None:
        """Drop the per-run target and environment; programs and the slat mesh stay warm."""
        self._target.release()
        self._environment.release()

    def _render_slats(self, frame: QuickTransitionRenderFrame, parameters: Mapping[str, object]) -> None:
        count, gloss = _slats_parameters(parameters)
        mode = _blinds_direction_mode(frame.run.request.direction)
        if mode == 2:
            raise ValueError("Blinds 3D Slats turn about horizontal or vertical axes only")
        progress = max(0.0, min(1.0, float(frame.sample.eased_progress)))
        try:
            if progress <= 0.0:
                self._resources.draw_image(frame, frame.source_texture_id)
                return
            if progress >= 1.0:
                self._resources.draw_image(frame, frame.destination_texture_id)
                return
            # Direction "Horizontal" keeps the flat style's vertical stripes: columns.
            columns = 1 if mode == 0 else 0
            samples = scene3d_request_samples(parameters)
            environment = self._environment.texture(frame, self._resources)
            if samples:
                with self._target.scope(frame, samples, self._resources):
                    self._draw_slats(frame, progress, count, columns, gloss, environment)
            else:
                self._draw_slats(frame, progress, count, columns, gloss, environment)
        except Exception:
            self._release_slats()
            raise

    def _draw_slats(self, frame, progress: float, count: int, columns: int, gloss: float,
                    environment: int) -> None:
        r, shaders = self._resources, _slats_program()
        program = r.program("backdrop", ITEM_QUAD_VERTEX_SOURCE, shaders.BLINDS_BACKDROP_FRAGMENT_SOURCE)
        uniforms = r.uniforms("backdrop", self._BACKDROP_UNIFORMS)
        gl.glDisable(gl.GL_DEPTH_TEST)
        gl.glDepthMask(gl.GL_FALSE)
        bind_frame(program, uniforms, frame)
        gl.glUniform1f(uniforms["uProgress"], progress)
        gl.glUniform1i(uniforms["uCount"], count)
        gl.glUniform1i(uniforms["uVertical"], columns)
        gl.glBindVertexArray(frame.quad_vao)
        gl.glDrawArrays(gl.GL_TRIANGLE_STRIP, 0, 4)

        r.begin_depth(frame)
        program = r.program("slats", shaders.BLINDS_SLATS_VERTEX_SOURCE, shaders.BLINDS_SLATS_FRAGMENT_SOURCE)
        uniforms = r.uniforms("slats", self._SLAT_UNIFORMS)
        bind_frame(program, uniforms, frame)
        gl.glUniform1f(uniforms["uProgress"], progress)
        gl.glUniform1i(uniforms["uCount"], count)
        gl.glUniform1i(uniforms["uVertical"], columns)
        gl.glUniform1f(uniforms["uGloss"], gloss)
        gl.glActiveTexture(gl.GL_TEXTURE2)
        gl.glBindTexture(gl.GL_TEXTURE_2D, environment)
        gl.glUniform1i(uniforms["uEnvironment"], 2)
        gl.glActiveTexture(gl.GL_TEXTURE0)
        vao, vertices = r.mesh("slat", shaders.BLINDS_SLAT_BOX_VERTICES, shaders.BLINDS_SLAT_BOX_ATTRIBUTES)
        gl.glBindVertexArray(vao)
        gl.glDrawArraysInstanced(gl.GL_TRIANGLES, 0, vertices, count)

    def release_resources(self) -> None:
        errors: list[str] = []
        try:
            self._release_slats()
        except Exception as exc:
            errors.append(str(exc))
        if self._program:
            gl.glDeleteProgram(self._program)
            self._program = 0
            self._uniforms.clear()
        if errors:
            raise RuntimeError(" | ".join(errors))

    def _release_slats(self) -> None:
        errors: list[str] = []
        for release in (self._target.release, self._environment.release, self._resources.release_resources):
            try:
                release()
            except Exception as exc:
                errors.append(str(exc))
        if errors:
            raise RuntimeError(" | ".join(errors))

    def _initialize(self) -> None:
        program = compile_program(
            QUICK_TRANSITION_VERTEX_SOURCE,
            blinds_program.fragment_source,
            label="Quick Blinds",
        )
        self._program = program
        try:
            # u_resolution exists in the legacy shader source but is not read
            # by that shader and may be optimized out.  Do not turn an unused
            # compatibility uniform into a new runtime requirement.
            uniform_names = (
                "uMatrix",
                "uItemSize",
                "u_progress",
                "u_grid",
                "u_feather",
                "u_direction",
                "uOldTex",
                "uNewTex",
            )
            uniforms = {
                name: int(gl.glGetUniformLocation(program, name))
                for name in uniform_names
            }
            missing = [
                name for name, location in uniforms.items() if location < 0
            ]
            if missing:
                raise RuntimeError(
                    "Quick Blinds uniforms are incomplete: " + ", ".join(missing)
                )
            self._uniforms = uniforms
        except Exception:
            self.release_resources()
            raise


def create_transition_renderer() -> QuickBlindsRenderer:
    return QuickBlindsRenderer()
