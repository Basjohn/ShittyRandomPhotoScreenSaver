"""Lazy Quick renderer for Blinds: the canonical authored flat shader, or 3D Slats."""

from __future__ import annotations

from collections.abc import Mapping
import math

from OpenGL import GL as gl

from rendering.gl_programs.blinds_program import blinds_program
from rendering.gl_programs.portable import pack_block
from rendering.gl_programs.scene3d import scene3d_request_samples
from rendering.quick.render.gl_resources import compile_program, delete_program
from rendering.quick.scene3d.environment import PHOTO_ENVIRONMENT_PROGRAM, PhotoEnvironment
from rendering.quick.scene3d.resources import UNDERLAY_PROGRAM, MeshResources, bind_frame, warm_programs, warm_pass_blocks
from rendering.quick.scene3d.target import SceneTarget, scene_target_programs, warm_run_resources
from rendering.quick.scene3d.uniforms import PassBlocks
from ..fullscreen_pass import fullscreen_pass_parts
from ..render_contract import QuickTransitionRenderFrame

# The flat style: the authored fragment over the item quad, its values one pass block (N1.6).
_FLAT_VERTEX_SOURCE, _FLAT_BLOCK = fullscreen_pass_parts(blinds_program.fragment_source, "BlindsPass")


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


_SLATS_PROGRAM = None


def _slats_program():
    """The 3D Slats shader module, loaded the first time the style is used (Flat never loads it).

    Bound once on that first use, so a running Slats frame never re-enters the import machinery."""
    global _SLATS_PROGRAM
    if _SLATS_PROGRAM is None:
        from rendering.gl_programs import blinds_slats_program
        _SLATS_PROGRAM = blinds_slats_program
    return _SLATS_PROGRAM


class QuickBlindsRenderer:
    transition_id = "blinds"

    # The photographs each 3D Slats program reads (bind_frame binds them); every other value is in its pass block.
    _SLAT_SAMPLERS = ("uOldTex", "uNewTex")
    _BACKDROP_SAMPLERS = ("uNewTex",)

    def __init__(self) -> None:
        self._program = 0
        # The flat program's pass block values as its uniforms held them (N1.6), and their ring.
        self._values: dict[str, object] = {}
        self._blocks = PassBlocks("Quick Blinds", block_bytes=_FLAT_BLOCK.size)
        # 3D Slats only: nothing below is touched by the flat style.
        self._resources = MeshResources("Quick Blinds 3D Slats")
        self._target = SceneTarget("Quick Blinds 3D Slats")
        self._environment = PhotoEnvironment("Quick Blinds 3D Slats")

    @property
    def has_resources(self) -> bool:
        return bool(self._program or self._blocks.has_resources or self._resources.has_resources
                    or self._target.has_resources or self._environment.has_resources)

    def render(self, frame: QuickTransitionRenderFrame) -> None:
        parameters = frame.run.request.parameter_dict()
        if _slats_style(parameters):
            self._render_slats(frame, parameters)
            return
        if not self._program:
            self._initialize()
        feather = _blinds_feather(parameters)
        direction = _blinds_direction_mode(frame.run.request.direction)
        cols, rows = _blinds_grid(frame.logical_size)

        # The flat program's values, one pass block (N1.6); u_resolution is declared but never read nor set.
        values = self._values
        values["uMatrix"] = frame.matrix_values
        values["uItemSize"] = frame.logical_size
        values["u_progress"] = float(frame.sample.eased_progress)
        values["u_grid"] = (float(cols), float(rows))
        values["u_feather"] = feather
        values["u_direction"] = direction
        gl.glUseProgram(self._program)
        gl.glActiveTexture(gl.GL_TEXTURE0)
        gl.glBindTexture(gl.GL_TEXTURE_2D, frame.source_texture_id)
        gl.glActiveTexture(gl.GL_TEXTURE1)
        gl.glBindTexture(gl.GL_TEXTURE_2D, frame.destination_texture_id)
        with self._blocks.bound(pack_block(_FLAT_BLOCK, values)):
            gl.glBindVertexArray(frame.quad_vao)
            gl.glDrawArrays(gl.GL_TRIANGLE_STRIP, 0, 4)

    def warm(self, parameters, size: tuple[int, int] | None = None) -> bool:
        """One bounded step of the gradual warm-up for a run with ``parameters`` (render thread,
        between runs). The flat style is one program, compiled in one step, then (given the render
        ``size``) its pass block's ring in the next."""
        if not _slats_style(parameters):
            if not self._program:
                self._initialize()
                return size is None
            return size is None or self._blocks.warm()
        samples = scene3d_request_samples(parameters)
        r, shaders = self._resources, _slats_program()
        entries = [(r, *UNDERLAY_PROGRAM), (r, *PHOTO_ENVIRONMENT_PROGRAM),
                   (r, "backdrop", shaders.BLINDS_BACKDROP_VERTEX_SOURCE, shaders.BLINDS_BACKDROP_FRAGMENT_SOURCE),
                   (r, "slats", shaders.BLINDS_SLATS_VERTEX_SOURCE, shaders.BLINDS_SLATS_FRAGMENT_SOURCE)]
        if samples:
            entries += [(r, *program) for program in scene_target_programs(samples, False, False)]
        if not warm_programs(entries):
            return False
        if not warm_pass_blocks(self._resources, size):
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
        program = r.program("backdrop", shaders.BLINDS_BACKDROP_VERTEX_SOURCE, shaders.BLINDS_BACKDROP_FRAGMENT_SOURCE)
        uniforms = r.uniforms("backdrop", self._BACKDROP_SAMPLERS)
        values = r.values("backdrop")
        gl.glDisable(gl.GL_DEPTH_TEST)
        gl.glDepthMask(gl.GL_FALSE)
        bind_frame(program, uniforms, frame, values)
        values["uProgress"] = progress
        values["uCount"] = count
        values["uVertical"] = columns
        with r.pass_blocks.bound(pack_block(shaders.BLINDS_BACKDROP_BLOCK, values)):
            gl.glBindVertexArray(frame.quad_vao)
            gl.glDrawArrays(gl.GL_TRIANGLE_STRIP, 0, 4)

        r.begin_depth(frame)
        program = r.program("slats", shaders.BLINDS_SLATS_VERTEX_SOURCE, shaders.BLINDS_SLATS_FRAGMENT_SOURCE)
        uniforms = r.uniforms("slats", self._SLAT_SAMPLERS)
        values = r.values("slats")
        bind_frame(program, uniforms, frame, values)
        values["uProgress"] = progress
        values["uCount"] = count
        values["uVertical"] = columns
        values["uGloss"] = gloss
        gl.glActiveTexture(gl.GL_TEXTURE2)                # the environment's binding
        gl.glBindTexture(gl.GL_TEXTURE_2D, environment)
        gl.glActiveTexture(gl.GL_TEXTURE0)
        vao, vertices = r.mesh("slat", shaders.BLINDS_SLAT_BOX_VERTICES, shaders.BLINDS_SLAT_BOX_ATTRIBUTES)
        with r.pass_blocks.bound(pack_block(shaders.BLINDS_SLATS_BLOCK, values)):
            gl.glBindVertexArray(vao)
            gl.glDrawArraysInstanced(gl.GL_TRIANGLES, 0, vertices, count)

    def release_resources(self) -> None:
        errors: list[str] = []
        try:
            self._release_slats()
        except Exception as exc:
            errors.append(str(exc))
        if self._program:
            delete_program(self._program)
            self._program = 0
            self._values = {}              # a new program's values start at zero, as its uniforms did
        try:
            self._blocks.release()
        except Exception as exc:
            errors.append(str(exc))
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
        # u_resolution exists in the legacy shader source but is not read by that shader; it stays in the block at
        # zero, never a runtime requirement.
        held = {name for name, _kind in _FLAT_BLOCK.fields}
        missing = [name for name in ("uMatrix", "uItemSize", "u_progress", "u_grid", "u_feather", "u_direction")
                   if name not in held]
        if missing:
            raise RuntimeError("Quick Blinds pass block is incomplete: " + ", ".join(missing))
        self._program = compile_program(_FLAT_VERTEX_SOURCE, blinds_program.fragment_source, label="Quick Blinds")
        self._values = {}


def create_transition_renderer() -> QuickBlindsRenderer:
    return QuickBlindsRenderer()
