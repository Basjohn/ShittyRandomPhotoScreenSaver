"""One shared, blurred backdrop per display for card surface materials.

``Docs/Architecture/Card_Surface_Materials.md`` owns the design. In short: the backdrop
is read **after** the wallpaper/transition renderer has drawn into the window target,
from the target itself, and drawn nowhere but into this module's own textures. The
background renderer is never redirected, layered, cached or re-dirtied (the Sep 2026
failures), and nothing here runs while every surface is Normal: the owner, this item and
its render node only exist while some card or the Context Menu uses a material.

Render-thread pipeline per refresh (``BackdropPipeline.refresh``):

    window target --blit--> 1/2 res --down--> 1/4 --> 1/8 --> 1/16 --> 1/32
    1/8  --up--> output level 0 (1/4 res, light blur)
    1/32 --up--> 1/16 --up--> output level 1 (1/8 res, heavy blur)

The output is one RGBA8 texture with two mip levels. Every refresh writes alpha 1; the
texture starts transparent, so a card that samples it before the first refresh (or after
a refused one) shows exactly its Normal fill.

The node sits under an opacity node that is 0 (never traversed, no Python call) unless the
item is armed: one-shot after an edge the scene controller already owns, or continuously
while a transition runs, refreshing at most once per ``min_interval_s`` of render-thread
time on frames the display renders anyway. No timer, no frame request of its own.
"""
from __future__ import annotations

import threading
import time
import weakref


from OpenGL import GL as gl
from PySide6.QtCore import QObject, QRectF, Qt, Signal, Slot
from PySide6.QtQuick import (
    QQuickItem,
    QQuickWindow,
    QSGNode,
    QSGOpacityNode,
    QSGRenderNode,
    QSGTexture,
    QSGTextureProvider,
)

from core.logging.logger import get_logger
from rendering.gl_error_policy import raise_pending_gl_error

from .. import gl_query
from ..render_failure_log import RenderFailureLog
from .gl_resources import compile_program, delete_program
from .native_texture_bridge import NativeTextureUnavailable, wrap_gl_texture

logger = get_logger(__name__)

# Pyramid depth (each level halves the previous). The light output upsamples from
# LIGHT_FROM, the heavy output from HEAVY_FROM; both are screen-relative, so a 4K and a
# 1440p display show the same blur relative to the photograph.
_LEVELS = 5                 # 1/2 .. 1/32
_LIGHT_FROM = 3             # 1/8
_HEAVY_FROM = 5             # 1/32

_VERTEX = """#version 460 core
out vec2 vUv;
void main() {
    vec2 p = vec2(float((gl_VertexID << 1) & 2), float(gl_VertexID & 2));
    vUv = p;
    gl_Position = vec4(p * 2.0 - 1.0, 0.0, 1.0);
}
"""

# Dual-filter (Kawase) down/up samplers: smooth, wide blurs from few bilinear taps.
_DOWN = """#version 460 core
in vec2 vUv;
out vec4 fragColor;
uniform sampler2D uSource;
uniform vec2 uHalfPixel;
void main() {
    vec3 sum = texture(uSource, vUv).rgb * 4.0;
    sum += texture(uSource, vUv - uHalfPixel).rgb;
    sum += texture(uSource, vUv + uHalfPixel).rgb;
    sum += texture(uSource, vUv + vec2(uHalfPixel.x, -uHalfPixel.y)).rgb;
    sum += texture(uSource, vUv - vec2(uHalfPixel.x, -uHalfPixel.y)).rgb;
    fragColor = vec4(sum / 8.0, 1.0);
}
"""

_UP = """#version 460 core
in vec2 vUv;
out vec4 fragColor;
uniform sampler2D uSource;
uniform vec2 uHalfPixel;
void main() {
    vec2 h = uHalfPixel;
    vec3 sum = texture(uSource, vUv + vec2(-h.x * 2.0, 0.0)).rgb;
    sum += texture(uSource, vUv + vec2(-h.x, h.y)).rgb * 2.0;
    sum += texture(uSource, vUv + vec2(0.0, h.y * 2.0)).rgb;
    sum += texture(uSource, vUv + vec2(h.x, h.y)).rgb * 2.0;
    sum += texture(uSource, vUv + vec2(h.x * 2.0, 0.0)).rgb;
    sum += texture(uSource, vUv + vec2(h.x, -h.y)).rgb * 2.0;
    sum += texture(uSource, vUv + vec2(0.0, -h.y * 2.0)).rgb;
    sum += texture(uSource, vUv + vec2(-h.x, -h.y)).rgb * 2.0;
    fragColor = vec4(sum / 12.0, 1.0);
}
"""


def pyramid_sizes(width: int, height: int) -> tuple[tuple[int, int], ...]:
    """Level sizes 1/2 .. 1/2**_LEVELS of a ``width`` x ``height`` target (floor, >= 1)."""

    sizes = []
    w, h = int(width), int(height)
    for _ in range(_LEVELS):
        w, h = max(1, w // 2), max(1, h // 2)
        sizes.append((w, h))
    return tuple(sizes)


class BackdropPipeline:
    """Render-thread GL owner of the blit, the blur pyramid and the output texture.

    ``refresh`` reads the framebuffer it is given (the render target the scene is drawing)
    and restores every GL state it touches. All methods need the owning context current.
    """

    def __init__(self) -> None:
        self._down = 0
        self._up = 0
        self._vao = 0
        self._down_source = self._down_half = -1
        self._up_source = self._up_half = -1
        self._size: tuple[int, int] | None = None
        self._levels: list[tuple[int, int, int, int]] = []   # (texture, fbo, w, h) per pyramid level
        self._scratch: list[tuple[int, int, int, int]] = []  # heavy chain intermediates
        self._output = 0
        self._output_fbos: tuple[int, int] = (0, 0)
        self._refused: str | None = None
        self.refresh_count = 0

    @property
    def output_texture(self) -> int:
        return self._output

    @property
    def output_size(self) -> tuple[int, int] | None:
        """Level-0 size of the output texture (1/4 of the target), once allocated."""
        if self._size is None:
            return None
        return pyramid_sizes(*self._size)[1]

    @property
    def refused(self) -> str | None:
        return self._refused

    def initialize(self) -> None:
        if self._down:
            return
        self._down = compile_program(_VERTEX, _DOWN, label="surface backdrop down")
        self._up = compile_program(_VERTEX, _UP, label="surface backdrop up")
        self._down_source = gl.glGetUniformLocation(self._down, "uSource")
        self._down_half = gl.glGetUniformLocation(self._down, "uHalfPixel")
        self._up_source = gl.glGetUniformLocation(self._up, "uSource")
        self._up_half = gl.glGetUniformLocation(self._up, "uHalfPixel")
        self._vao = int(gl.glGenVertexArrays(1))
        # The output name lives as long as the pipeline: a resize re-specifies its storage
        # in place, so the scenegraph wrapper that names it never goes stale.
        self._output = int(gl.glGenTextures(1))

    def ensure_output(self, width: int, height: int) -> None:
        """Allocate the output texture's storage (transparent) for a ``width`` x ``height`` target."""

        if self._size == (int(width), int(height)):
            return
        self._release_levels()
        self._size = (int(width), int(height))
        sizes = pyramid_sizes(width, height)
        for w, h in sizes:
            self._levels.append(self._target(w, h))
        # Heavy chain intermediates: sizes of levels _HEAVY_FROM-1 .. _LIGHT_FROM+1 (exclusive
        # of the output level 1 = level 3 size, written directly).
        for index in range(_HEAVY_FROM - 2, 2, -1):
            w, h = sizes[index]
            self._scratch.append(self._target(w, h))
        level0, level1 = sizes[1], sizes[2]
        prior_unit = gl_query.get_int(gl.GL_ACTIVE_TEXTURE)
        gl.glActiveTexture(gl.GL_TEXTURE0)
        prior = gl_query.get_int(gl.GL_TEXTURE_BINDING_2D)
        try:
            gl.glBindTexture(gl.GL_TEXTURE_2D, self._output)
            for level, (w, h) in enumerate((level0, level1)):
                zeros = bytes(w * h * 4)
                gl.glTexImage2D(gl.GL_TEXTURE_2D, level, gl.GL_RGBA8, w, h, 0,
                                gl.GL_RGBA, gl.GL_UNSIGNED_BYTE, zeros)
            gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_BASE_LEVEL, 0)
            gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MAX_LEVEL, 1)
            gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MIN_FILTER, gl.GL_LINEAR_MIPMAP_LINEAR)
            gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MAG_FILTER, gl.GL_LINEAR)
            gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_S, gl.GL_CLAMP_TO_EDGE)
            gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_T, gl.GL_CLAMP_TO_EDGE)
        finally:
            gl.glBindTexture(gl.GL_TEXTURE_2D, prior)
            gl.glActiveTexture(prior_unit)
        self._output_fbos = (self._framebuffer(self._output, 0), self._framebuffer(self._output, 1))

    @staticmethod
    def _framebuffer(texture: int, level: int) -> int:
        prior = gl_query.get_int(gl.GL_DRAW_FRAMEBUFFER_BINDING)
        fbo = int(gl.glGenFramebuffers(1))
        try:
            gl.glBindFramebuffer(gl.GL_DRAW_FRAMEBUFFER, fbo)
            gl.glFramebufferTexture2D(gl.GL_DRAW_FRAMEBUFFER, gl.GL_COLOR_ATTACHMENT0,
                                      gl.GL_TEXTURE_2D, texture, level)
            status = gl.glCheckFramebufferStatus(gl.GL_DRAW_FRAMEBUFFER)
        finally:
            gl.glBindFramebuffer(gl.GL_DRAW_FRAMEBUFFER, prior)
        if status != gl.GL_FRAMEBUFFER_COMPLETE:
            gl.glDeleteFramebuffers(1, [fbo])
            raise RuntimeError(f"surface backdrop framebuffer incomplete: 0x{int(status):x}")
        return fbo

    def _target(self, width: int, height: int) -> tuple[int, int, int, int]:
        prior_unit = gl_query.get_int(gl.GL_ACTIVE_TEXTURE)
        gl.glActiveTexture(gl.GL_TEXTURE0)
        prior = gl_query.get_int(gl.GL_TEXTURE_BINDING_2D)
        texture = int(gl.glGenTextures(1))
        try:
            gl.glBindTexture(gl.GL_TEXTURE_2D, texture)
            gl.glTexStorage2D(gl.GL_TEXTURE_2D, 1, gl.GL_RGBA8, width, height)
            gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MIN_FILTER, gl.GL_LINEAR)
            gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MAG_FILTER, gl.GL_LINEAR)
            gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_S, gl.GL_CLAMP_TO_EDGE)
            gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_T, gl.GL_CLAMP_TO_EDGE)
        finally:
            gl.glBindTexture(gl.GL_TEXTURE_2D, prior)
            gl.glActiveTexture(prior_unit)
        return texture, self._framebuffer(texture, 0), width, height

    def refresh(self, read_framebuffer: int, width: int, height: int) -> bool:
        """Rebuild the backdrop from ``read_framebuffer`` (``width`` x ``height``); False if refused."""

        self.initialize()
        self.ensure_output(width, height)
        samples = gl_query.get_int(gl.GL_SAMPLES)
        if samples > 0:
            # A multisampled target cannot be downscaled by a blit. The product window is not
            # multisampled; refuse (cards stay Normal) rather than add a resolve pass.
            self._refused = f"multisampled render target ({samples} samples)"
            return False
        self._refused = None
        saved = self._save_state()
        try:
            gl.glDisable(gl.GL_SCISSOR_TEST)
            gl.glDisable(gl.GL_DEPTH_TEST)
            gl.glDisable(gl.GL_STENCIL_TEST)
            gl.glDisable(gl.GL_CULL_FACE)
            gl.glDisablei(gl.GL_BLEND, 0)
            gl.glColorMask(True, True, True, True)
            gl.glBindSampler(0, 0)
            gl.glActiveTexture(gl.GL_TEXTURE0)
            gl.glBindVertexArray(self._vao)
            first = self._levels[0]
            gl.glBindFramebuffer(gl.GL_READ_FRAMEBUFFER, int(read_framebuffer))
            gl.glBindFramebuffer(gl.GL_DRAW_FRAMEBUFFER, first[1])
            gl.glBlitFramebuffer(0, 0, int(width), int(height), 0, 0, first[2], first[3],
                                 gl.GL_COLOR_BUFFER_BIT, gl.GL_LINEAR)
            gl.glUseProgram(self._down)
            gl.glUniform1i(self._down_source, 0)
            for source, target in zip(self._levels, self._levels[1:]):
                self._pass(self._down_half, source, target[1], target[2], target[3])
            gl.glUseProgram(self._up)
            gl.glUniform1i(self._up_source, 0)
            light0, heavy1 = self._output_fbos
            level0, level1 = pyramid_sizes(width, height)[1:3]
            # Light: level _LIGHT_FROM (1/8) -> output level 0 (1/4).
            self._pass(self._up_half, self._levels[_LIGHT_FROM - 1], light0, *level0)
            # Heavy: level _HEAVY_FROM (1/32) -> intermediates -> output level 1 (1/8).
            source = self._levels[_HEAVY_FROM - 1]
            for scratch in self._scratch:
                self._pass(self._up_half, source, scratch[1], scratch[2], scratch[3])
                source = scratch
            self._pass(self._up_half, source, heavy1, *level1)
        finally:
            self._restore_state(saved)
        self.refresh_count += 1
        return True

    @staticmethod
    def _pass(half_location: int, source, framebuffer: int, width: int, height: int) -> None:
        gl.glBindFramebuffer(gl.GL_DRAW_FRAMEBUFFER, framebuffer)
        gl.glViewport(0, 0, width, height)
        gl.glBindTexture(gl.GL_TEXTURE_2D, source[0])
        gl.glUniform2f(half_location, 0.5 / width, 0.5 / height)
        gl.glDrawArrays(gl.GL_TRIANGLES, 0, 3)

    @staticmethod
    def _save_state():
        active = gl_query.get_int(gl.GL_ACTIVE_TEXTURE)
        gl.glActiveTexture(gl.GL_TEXTURE0)
        return (
            gl_query.get_int(gl.GL_DRAW_FRAMEBUFFER_BINDING),
            gl_query.get_int(gl.GL_READ_FRAMEBUFFER_BINDING),
            gl_query.get_ints(gl.GL_VIEWPORT, 4),
            gl_query.is_enabled(gl.GL_SCISSOR_TEST),
            gl_query.is_enabled(gl.GL_DEPTH_TEST),
            gl_query.is_enabled(gl.GL_STENCIL_TEST),
            gl_query.is_enabled(gl.GL_CULL_FACE),
            bool(gl.glIsEnabledi(gl.GL_BLEND, 0)),
            gl_query.get_bools(gl.GL_COLOR_WRITEMASK, 4),
            gl_query.get_int(gl.GL_CURRENT_PROGRAM),
            gl_query.get_int(gl.GL_VERTEX_ARRAY_BINDING),
            gl_query.get_int(gl.GL_TEXTURE_BINDING_2D),
            gl_query.get_int(gl.GL_SAMPLER_BINDING),
            active,
        )

    @staticmethod
    def _restore_state(saved) -> None:
        (draw, read, viewport, scissor, depth, stencil, cull, blend, mask, program, vao, texture,
         sampler, active) = saved
        gl.glBindFramebuffer(gl.GL_DRAW_FRAMEBUFFER, draw)
        gl.glBindFramebuffer(gl.GL_READ_FRAMEBUFFER, read)
        gl.glViewport(*viewport)
        for capability, enabled in ((gl.GL_SCISSOR_TEST, scissor), (gl.GL_DEPTH_TEST, depth),
                                    (gl.GL_STENCIL_TEST, stencil), (gl.GL_CULL_FACE, cull)):
            (gl.glEnable if enabled else gl.glDisable)(capability)
        (gl.glEnablei if blend else gl.glDisablei)(gl.GL_BLEND, 0)
        gl.glColorMask(*mask)
        gl.glUseProgram(program)
        gl.glBindVertexArray(vao)
        gl.glBindTexture(gl.GL_TEXTURE_2D, texture)
        gl.glBindSampler(0, sampler)
        gl.glActiveTexture(active)

    def _release_levels(self) -> None:
        for texture, fbo, _w, _h in (*self._levels, *self._scratch):
            gl.glDeleteFramebuffers(1, [fbo])
            gl.glDeleteTextures([texture])
        self._levels, self._scratch = [], []
        for fbo in self._output_fbos:
            if fbo:
                gl.glDeleteFramebuffers(1, [fbo])
        self._output_fbos = (0, 0)
        self._size = None

    def forget(self) -> None:
        """Drop every GL name without GL calls (no context: the context's death frees them)."""

        self._levels, self._scratch = [], []
        self._output_fbos = (0, 0)
        self._size = None
        self._output = self._down = self._up = self._vao = 0

    def release(self) -> None:
        """Delete every GL object (owning context current); ``initialize`` may rebuild later."""

        self._release_levels()
        if self._output:
            gl.glDeleteTextures([self._output])
            self._output = 0
        for program in (self._down, self._up):
            if program:
                delete_program(program)
        self._down = self._up = 0
        if self._vao:
            gl.glDeleteVertexArrays(1, [self._vao])
            self._vao = 0


class _BackdropShared:
    """Plain state shared by the GUI item, the render node and the texture provider."""

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.requested_serial = 0      # GUI: last one-shot asked for
        self.continuous = False        # GUI: a transition is running
        self.min_interval_s = 0.0      # GUI: continuous refresh spacing
        self.texture: QSGTexture | None = None   # render thread: wrapper of the output name


class SurfaceBackdropRelay(QObject):
    """GUI-thread receiver for the render node's two edges (queued)."""

    refreshed = Signal(int)
    textureReady = Signal()


class SurfaceBackdropTextureProvider(QSGTextureProvider):
    """Hands the shared backdrop texture to card ``ShaderEffect`` sources."""

    def __init__(self, shared: _BackdropShared, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._shared = shared

    def texture(self):  # noqa: D401 - Qt override (render thread)
        with self._shared.lock:
            return self._shared.texture


class _BackdropRenderNode(QSGRenderNode):
    """Reads the drawn frame and rebuilds the backdrop when armed; draws nothing itself."""

    def __init__(self, shared: _BackdropShared, relay: SurfaceBackdropRelay,
                 provider: SurfaceBackdropTextureProvider,
                 window: QQuickWindow | None, screen_index: int) -> None:
        super().__init__()
        self._shared = shared
        self._relay_ref = weakref.ref(relay)
        self._provider_ref = weakref.ref(provider)
        self._window_ref = weakref.ref(window) if window is not None else (lambda: None)
        self._pipeline = BackdropPipeline()
        self._done_serial = 0
        self._last_refresh_s = -1.0
        self._failure_log = RenderFailureLog(logger, f"Surface backdrop screen={screen_index}")
        self._reported_refusal: str | None = None
        self._released = False

    @property
    def pipeline(self) -> BackdropPipeline:
        return self._pipeline

    def changedStates(self) -> QSGRenderNode.StateFlag:
        return (QSGRenderNode.StateFlag.ViewportState | QSGRenderNode.StateFlag.ScissorState
                | QSGRenderNode.StateFlag.BlendState | QSGRenderNode.StateFlag.DepthState
                | QSGRenderNode.StateFlag.StencilState | QSGRenderNode.StateFlag.CullState
                | QSGRenderNode.StateFlag.ColorState | QSGRenderNode.StateFlag.RenderTargetState)

    def rect(self) -> QRectF:
        return QRectF()

    def render(self, _state) -> None:
        if self._released:
            return
        try:
            shared = self._shared
            with shared.lock:
                requested = shared.requested_serial
                continuous = shared.continuous
                interval = shared.min_interval_s
            now = time.monotonic()
            oneshot = requested > self._done_serial
            if not oneshot and not (continuous and (self._last_refresh_s < 0.0
                                                    or now - self._last_refresh_s >= interval)):
                return
            target = self.renderTarget()
            if target is None:
                raise RuntimeError("surface backdrop has no active render target")
            size = target.pixelSize()
            width, height = int(size.width()), int(size.height())
            if width <= 0 or height <= 0:
                raise RuntimeError(f"surface backdrop render target is invalid: {width}x{height}")
            created = False
            with shared.lock:
                needs_texture = shared.texture is None
            refreshed = self._pipeline.refresh(gl_query.get_int(gl.GL_DRAW_FRAMEBUFFER_BINDING),
                                               width, height)
            if needs_texture:
                created = self._publish_texture()
            refusal = self._pipeline.refused
            if refusal is not None and refusal != self._reported_refusal:
                self._reported_refusal = refusal
                logger.warning("[QUICK] Surface backdrop refused, surfaces stay Normal: %s", refusal)
            if refreshed:
                self._last_refresh_s = now
            raise_pending_gl_error(gl, "Surface backdrop")
            if self._failure_log.failing:
                self._failure_log.note_success()
            relay = self._relay_ref()
            if relay is not None:
                try:
                    if created:
                        relay.textureReady.emit()
                    if oneshot:
                        self._done_serial = requested
                        relay.refreshed.emit(requested)
                except RuntimeError:
                    pass   # the GUI item retired while this frame rendered
            elif oneshot:
                self._done_serial = requested
        except Exception as exc:
            self._failure_log.note_failure(f"{type(exc).__name__}: {exc}", exc)
            with self._shared.lock:
                requested = self._shared.requested_serial
            # Never leave the item armed by a failing one-shot: report it done (cards keep
            # whatever the texture holds, transparent = Normal).
            if requested > self._done_serial:
                self._done_serial = requested
                relay = self._relay_ref()
                if relay is not None:
                    try:
                        relay.refreshed.emit(requested)
                    except RuntimeError:
                        pass

    def _publish_texture(self) -> bool:
        window = self._window_ref()
        size = self._pipeline.output_size
        if window is None or size is None or not self._pipeline.output_texture:
            return False
        try:
            texture = wrap_gl_texture(self._pipeline.output_texture, window, size,
                                      options=QQuickWindow.CreateTextureOption.TextureHasMipmaps
                                      | QQuickWindow.CreateTextureOption.TextureHasAlphaChannel)
        except NativeTextureUnavailable as exc:
            raise RuntimeError(f"surface backdrop texture cannot be wrapped: {exc}") from exc
        texture.setFiltering(QSGTexture.Filtering.Linear)
        texture.setMipmapFiltering(QSGTexture.Filtering.Linear)
        texture.setHorizontalWrapMode(QSGTexture.WrapMode.ClampToEdge)
        texture.setVerticalWrapMode(QSGTexture.WrapMode.ClampToEdge)
        with self._shared.lock:
            self._shared.texture = texture
        provider = self._provider_ref()
        if provider is not None:
            try:
                provider.textureChanged.emit()
            except RuntimeError:
                pass
        return True

    def park(self) -> None:
        """Render thread (sync), context current: free every GL object; the node stays.

        Called when the last surface went Normal: the consumers were unbound on the GUI side
        before this sync, so their shader nodes were cleaned up at its start and nothing
        samples the texture. A later unpark rebuilds everything lazily on its first refresh.
        """

        self._drop_gl()
        self._done_serial = 0
        self._last_refresh_s = -1.0

    def release_resources(self) -> None:
        """Render thread: final release (scene-graph invalidation or node destruction)."""

        if self._released:
            return
        self._released = True
        self._drop_gl()

    def _drop_gl(self) -> None:
        with self._shared.lock:
            texture, self._shared.texture = self._shared.texture, None
        from PySide6.QtGui import QOpenGLContext

        if QOpenGLContext.currentContext() is not None:
            self._pipeline.release()
        else:
            # Teardown without a context (process exit): the context's own destruction
            # frees the names; never issue GL calls against no context.
            self._pipeline.forget()
        if texture is not None:
            try:
                texture.deleteLater()   # after Qt's deferred releases; it owns no GL name
            except RuntimeError:
                pass

    def releaseResources(self) -> None:  # noqa: N802 - Qt override
        self.release_resources()


class _NodeRetirement:
    """Render-thread release of the current node on ``sceneGraphInvalidated``."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._node: _BackdropRenderNode | None = None

    def set_node(self, node: _BackdropRenderNode | None) -> None:
        with self._lock:
            self._node = node

    def invalidate(self) -> None:
        with self._lock:
            node, self._node = self._node, None
        if node is not None:
            node.release_resources()


class SurfaceBackdropSource(QQuickItem):
    """The per-display backdrop item (z 2, above the wallpaper and dimming, below cards).

    GUI thread API: ``request_refresh`` (one-shot, an edge) and ``set_continuous`` (a
    transition starts/stops). ``texture_provider_item`` is what card shaders sample.
    """

    textureReadyChanged = Signal()

    def __init__(self, parent: QQuickItem | None = None, *, screen_index: int = -1) -> None:
        super().__init__(parent)
        self.setFlag(QQuickItem.Flag.ItemHasContents, True)
        self.setObjectName("surfaceBackdropSource")
        self._screen_index = int(screen_index)
        self._shared = _BackdropShared()
        self._relay = SurfaceBackdropRelay(self)
        self._relay.refreshed.connect(self._on_refreshed, Qt.ConnectionType.QueuedConnection)
        self._relay.textureReady.connect(self._on_texture_ready, Qt.ConnectionType.QueuedConnection)
        self._provider = SurfaceBackdropTextureProvider(self._shared, self)
        # Parked: no GL objects, never traversed (the owner's demand went to zero).
        self._parked = False
        self._park_pending = False
        # Python keeps the paint nodes it created referenced for the item's whole life;
        # Qt deletes them with the item (never earlier: updatePaintNode always returns it).
        self._paint_root: _BackdropRoot | None = None
        self._acknowledged_serial = 0
        self._texture_ready = False
        self._retirement = _NodeRetirement()
        self._bound_window = None
        self.windowChanged.connect(self._bind_window)
        self._bind_window(self.window())

    # -- GUI thread ---------------------------------------------------------------

    def request_refresh(self) -> None:
        """Rebuild the backdrop on the next rendered frame (one edge, one refresh)."""

        with self._shared.lock:
            self._shared.requested_serial += 1
        self.update()

    def set_continuous(self, active: bool, min_interval_s: float) -> None:
        """Refresh on rendered frames, at most every ``min_interval_s``, while ``active``."""

        active = bool(active)
        with self._shared.lock:
            changed = self._shared.continuous != active
            self._shared.continuous = active
            self._shared.min_interval_s = max(0.0, float(min_interval_s))
        if changed:
            self.update()

    @property
    def armed(self) -> bool:
        with self._shared.lock:
            return self._shared.continuous or self._shared.requested_serial > self._acknowledged_serial

    @property
    def texture_ready(self) -> bool:
        return self._texture_ready

    @property
    def parked(self) -> bool:
        return self._parked

    def set_parked(self, parked: bool) -> None:
        """GUI: park (free GL at the next sync, never traverse) or wake. Unbind consumers first."""

        parked = bool(parked)
        if parked == self._parked:
            return
        self._parked = parked
        if parked:
            with self._shared.lock:
                self._shared.continuous = False
            self._acknowledged_serial = self._shared.requested_serial
            self._park_pending = True
            self._texture_ready = False
            self.update()
        else:
            self.request_refresh()

    @Slot(int)
    def _on_refreshed(self, serial: int) -> None:
        self._acknowledged_serial = max(self._acknowledged_serial, int(serial))
        # Disarm at the next sync (one ordinary frame) unless something newer is pending.
        self.update()

    @Slot()
    def _on_texture_ready(self) -> None:
        if not self._texture_ready:
            self._texture_ready = True
            self.textureReadyChanged.emit()

    def _bind_window(self, window) -> None:
        if window is self._bound_window:
            return
        if self._bound_window is not None:
            try:
                self._bound_window.sceneGraphInvalidated.disconnect(self._retirement.invalidate)
            except (RuntimeError, TypeError):
                pass
        self._bound_window = window
        if window is not None:
            window.sceneGraphInvalidated.connect(self._retirement.invalidate,
                                                 Qt.ConnectionType.DirectConnection)

    # -- Qt overrides ------------------------------------------------------------

    def isTextureProvider(self) -> bool:  # noqa: N802 - Qt override
        return True

    def textureProvider(self):  # noqa: N802 - Qt override (render thread)
        return self._provider

    def updatePaintNode(self, old_node: QSGNode | None, _data) -> QSGNode | None:
        root = self._paint_root
        if root is None or old_node is not root:
            if self._parked:
                return old_node
            root = _BackdropRoot(_BackdropRenderNode(self._shared, self._relay, self._provider,
                                                     self.window(), self._screen_index))
            self._paint_root = root
            self._retirement.set_node(root.node)
        if self._park_pending:
            # Consumers were unbound on the GUI side before this sync; their shader nodes
            # were cleaned up at its start, so nothing samples the texture any more.
            self._park_pending = False
            root.node.park()
        root.setOpacity(1.0 if self.armed and not self._parked else 0.0)
        return root


class _BackdropRoot(QSGOpacityNode):
    """Opacity 0 keeps Qt from traversing (and calling) the render node while disarmed."""

    def __init__(self, node: _BackdropRenderNode) -> None:
        super().__init__()
        self.node = node
        self.setOpacity(0.0)
        self.appendChildNode(node)


__all__ = ["BackdropPipeline", "SurfaceBackdropSource", "pyramid_sizes"]
