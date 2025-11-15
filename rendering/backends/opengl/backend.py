"""OpenGL renderer backend using the existing QOpenGLWidget-based pipeline."""

from __future__ import annotations

from core.logging.logger import get_logger

from ..base import BackendCapabilities, RenderSurface, RendererBackend, SurfaceDescriptor, TransitionPipeline

logger = get_logger(__name__)


class OpenGLRenderSurface(RenderSurface):
    def resize(self, width: int, height: int, dpi: float) -> None:  # type: ignore[override]
        logger.debug("OpenGLRenderSurface.resize -> %sx%s (dpi=%s)", width, height, dpi)

    def begin_frame(self) -> None:  # type: ignore[override]
        pass

    def end_frame(self) -> None:  # type: ignore[override]
        pass

    def present(self) -> None:  # type: ignore[override]
        pass

    def shutdown(self) -> None:  # type: ignore[override]
        pass


class OpenGLTransitionPipeline(TransitionPipeline):
    def upload_assets(self, packet) -> None:  # type: ignore[override]
        pass

    def render(self, packet) -> None:  # type: ignore[override]
        pass

    def cleanup(self) -> None:  # type: ignore[override]
        pass


class OpenGLRendererBackend(RendererBackend):
    """Thin wrapper around existing QOpenGLWidget-based pipeline."""

    def initialize(self) -> None:  # type: ignore[override]
        logger.info("Using OpenGL renderer backend")

    def shutdown(self) -> None:  # type: ignore[override]
        logger.info("Shutting down OpenGL renderer backend")

    def create_surface(self, descriptor: SurfaceDescriptor) -> RenderSurface:  # type: ignore[override]
        return OpenGLRenderSurface(descriptor)

    def destroy_surface(self, surface: RenderSurface) -> None:  # type: ignore[override]
        surface.shutdown()

    def create_transition_pipeline(self, transition_name: str) -> TransitionPipeline:  # type: ignore[override]
        return OpenGLTransitionPipeline()

    def release_transition_pipeline(self, pipeline: TransitionPipeline) -> None:  # type: ignore[override]
        pipeline.cleanup()

    def _build_capabilities(self) -> BackendCapabilities:  # type: ignore[override]
        return BackendCapabilities(
            api_name="OpenGL",
            api_version="4.x",
            supports_triple_buffer=False,
            supports_vsync_toggle=False,
            supports_compute=False,
            supports_hdr=False,
        )
