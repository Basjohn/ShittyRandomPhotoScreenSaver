"""Common GL state and lazy renderer lifetime owner for Quick transitions."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from OpenGL import GL as gl

from rendering.quick import gl_query as _query

from .implementation_registry import (
    canonical_enabled_transition_ids,
    iter_quick_transition_implementations,
    resolve_quick_transition_renderer,
)
from .render_contract import QuickTransitionRenderFrame, QuickTransitionRenderer


# The fence captures ~20 states every transition frame; ``gl_query``'s raw getters
# cost ~2.7 us each against ~13 us for PyOpenGL's checked ones.
def _int_state(name: int) -> int:
    return _query.get_int(name)


def _bool_state(name: int) -> bool:
    return _query.get_bool(name)


def _float_state(name: int) -> float:
    return _query.get_float(name)


def _viewport_state() -> tuple[int, int, int, int]:
    values = tuple(int(value) for value in _query.get_ints(gl.GL_VIEWPORT, 4))
    if len(values) != 4:
        raise RuntimeError(f"invalid inherited Quick GL viewport: {values}")
    return values


def _set_enabled(capability: int, enabled: bool) -> None:
    if enabled:
        gl.glEnable(capability)
    else:
        gl.glDisable(capability)


@dataclass(frozen=True, slots=True)
class _InheritedGlState:
    viewport: tuple[int, int, int, int]
    program: int
    vao: int
    array_buffer: int
    active_texture: int
    texture_0: int
    texture_1: int
    draw_framebuffer: int
    read_framebuffer: int
    blend: bool
    blend_equation: tuple[int, int]
    blend_function: tuple[int, int, int, int]
    cull: bool
    depth: bool
    depth_write: bool
    depth_function: int
    depth_clear_value: float
    stencil: bool

    @classmethod
    def capture(cls) -> "_InheritedGlState":
        active_texture = _int_state(gl.GL_ACTIVE_TEXTURE)
        try:
            gl.glActiveTexture(gl.GL_TEXTURE0)
            texture_0 = _int_state(gl.GL_TEXTURE_BINDING_2D)
            gl.glActiveTexture(gl.GL_TEXTURE1)
            texture_1 = _int_state(gl.GL_TEXTURE_BINDING_2D)
        finally:
            gl.glActiveTexture(active_texture)
        return cls(
            viewport=_viewport_state(),
            program=_int_state(gl.GL_CURRENT_PROGRAM),
            vao=_int_state(gl.GL_VERTEX_ARRAY_BINDING),
            array_buffer=_int_state(gl.GL_ARRAY_BUFFER_BINDING),
            active_texture=active_texture,
            texture_0=texture_0,
            texture_1=texture_1,
            draw_framebuffer=_int_state(gl.GL_DRAW_FRAMEBUFFER_BINDING),
            read_framebuffer=_int_state(gl.GL_READ_FRAMEBUFFER_BINDING),
            blend=bool(gl.glIsEnabled(gl.GL_BLEND)),
            blend_equation=(
                _int_state(gl.GL_BLEND_EQUATION_RGB),
                _int_state(gl.GL_BLEND_EQUATION_ALPHA),
            ),
            blend_function=(
                _int_state(gl.GL_BLEND_SRC_RGB),
                _int_state(gl.GL_BLEND_DST_RGB),
                _int_state(gl.GL_BLEND_SRC_ALPHA),
                _int_state(gl.GL_BLEND_DST_ALPHA),
            ),
            cull=bool(gl.glIsEnabled(gl.GL_CULL_FACE)),
            depth=bool(gl.glIsEnabled(gl.GL_DEPTH_TEST)),
            depth_write=_bool_state(gl.GL_DEPTH_WRITEMASK),
            depth_function=_int_state(gl.GL_DEPTH_FUNC),
            depth_clear_value=_float_state(gl.GL_DEPTH_CLEAR_VALUE),
            stencil=bool(gl.glIsEnabled(gl.GL_STENCIL_TEST)),
        )

    def restore(self) -> None:
        # A 3D scene target may still be bound after a failure mid-scene.
        gl.glBindFramebuffer(gl.GL_DRAW_FRAMEBUFFER, self.draw_framebuffer)
        gl.glBindFramebuffer(gl.GL_READ_FRAMEBUFFER, self.read_framebuffer)
        gl.glActiveTexture(gl.GL_TEXTURE1)
        gl.glBindTexture(gl.GL_TEXTURE_2D, self.texture_1)
        gl.glActiveTexture(gl.GL_TEXTURE0)
        gl.glBindTexture(gl.GL_TEXTURE_2D, self.texture_0)
        gl.glActiveTexture(self.active_texture)
        gl.glBindVertexArray(self.vao)
        gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self.array_buffer)
        gl.glUseProgram(self.program)
        gl.glViewport(*self.viewport)
        gl.glDepthMask(gl.GL_TRUE if self.depth_write else gl.GL_FALSE)
        gl.glDepthFunc(self.depth_function)
        gl.glClearDepth(self.depth_clear_value)
        gl.glBlendEquationSeparate(*self.blend_equation)
        gl.glBlendFuncSeparate(*self.blend_function)
        _set_enabled(gl.GL_BLEND, self.blend)
        _set_enabled(gl.GL_CULL_FACE, self.cull)
        _set_enabled(gl.GL_DEPTH_TEST, self.depth)
        _set_enabled(gl.GL_STENCIL_TEST, self.stencil)


class QuickTransitionRenderHost:
    """Resolve enabled renderers lazily and own their context-local lifetime."""

    def __init__(
        self,
        *,
        enabled_transition_ids: Iterable[object] | None = None,
    ) -> None:
        if enabled_transition_ids is None:
            enabled_transition_ids = (
                descriptor.transition_id
                for descriptor in iter_quick_transition_implementations()
            )
        self._enabled_transition_ids = canonical_enabled_transition_ids(
            enabled_transition_ids
        )
        self._implementations: dict[str, QuickTransitionRenderer] = {}

    @property
    def enabled_transition_ids(self) -> frozenset[str]:
        return self._enabled_transition_ids

    @property
    def has_resources(self) -> bool:
        return any(
            implementation.has_resources
            for implementation in self._implementations.values()
        )

    @property
    def resolved_transition_ids(self) -> frozenset[str]:
        return frozenset(self._implementations)

    def set_enabled_transition_ids(self, values: Iterable[object]) -> None:
        """Disable implementations on their render owner and allow lazy re-enable."""

        enabled = canonical_enabled_transition_ids(values)
        self._enabled_transition_ids = enabled
        errors: list[str] = []
        for transition_id, implementation in tuple(self._implementations.items()):
            if transition_id in enabled:
                continue
            try:
                implementation.release_resources()
            except Exception as exc:
                errors.append(f"{transition_id}:{type(exc).__name__}:{exc}")
                continue
            if not implementation.has_resources:
                del self._implementations[transition_id]
        if errors:
            raise RuntimeError(
                "Quick transition disable cleanup incomplete: " + " | ".join(errors)
            )

    def render(self, frame: QuickTransitionRenderFrame) -> str:
        transition_id = frame.run.request.transition_id
        if transition_id not in self._enabled_transition_ids:
            raise RuntimeError(f"Quick transition is disabled: {transition_id}")
        implementation = self._implementations.get(transition_id)
        if implementation is None:
            implementation = resolve_quick_transition_renderer(
                transition_id,
                enabled_transition_ids=self._enabled_transition_ids,
            )
            if implementation is None:
                raise RuntimeError(
                    f"Quick transition renderer is not registered: {transition_id}"
                )
            self._implementations[transition_id] = implementation

        inherited = _InheritedGlState.capture()
        try:
            gl.glDisable(gl.GL_BLEND)
            gl.glDisable(gl.GL_CULL_FACE)
            gl.glDisable(gl.GL_DEPTH_TEST)
            gl.glDisable(gl.GL_STENCIL_TEST)
            gl.glViewport(*frame.viewport)
            implementation.render(frame)
        finally:
            inherited.restore()
        return transition_id

    def park(self) -> None:
        """After a run: let renderers drop per-run targets, keeping programs warm."""

        errors: list[str] = []
        for transition_id, implementation in tuple(self._implementations.items()):
            park = getattr(implementation, "park", None)
            if park is None:
                continue
            try:
                park()
            except Exception as exc:
                errors.append(f"{transition_id}:{type(exc).__name__}:{exc}")
        if errors:
            raise RuntimeError(
                "Quick transition park incomplete: " + " | ".join(errors)
            )

    def release_resources(self) -> None:
        errors: list[str] = []
        for transition_id, implementation in tuple(self._implementations.items()):
            try:
                implementation.release_resources()
            except Exception as exc:
                errors.append(f"{transition_id}:{type(exc).__name__}:{exc}")
                continue
            if not implementation.has_resources:
                del self._implementations[transition_id]
        if errors:
            raise RuntimeError(
                "Quick transition renderer cleanup incomplete: " + " | ".join(errors)
            )
