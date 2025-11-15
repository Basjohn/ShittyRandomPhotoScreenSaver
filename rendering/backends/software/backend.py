"""Software renderer backend placeholder."""

from __future__ import annotations

from core.logging.logger import get_logger

from ..base import BackendCapabilities, RenderSurface, RendererBackend, SurfaceDescriptor, TransitionPipeline

logger = get_logger(__name__)


class SoftwareRenderSurface(RenderSurface):
    def resize(self, width: int, height: int, dpi: float) -> None:  # type: ignore[override]
        logger.debug("SoftwareRenderSurface.resize -> %sx%s (dpi=%s)", width, height, dpi)

    def begin_frame(self) -> None:  # type: ignore[override]
        logger.debug("SoftwareRenderSurface.begin_frame (noop)")

    def end_frame(self) -> None:  # type: ignore[override]
        logger.debug("SoftwareRenderSurface.end_frame (noop)")

    def present(self) -> None:  # type: ignore[override]
        logger.debug("SoftwareRenderSurface.present (noop)")

    def shutdown(self) -> None:  # type: ignore[override]
        logger.debug("SoftwareRenderSurface.shutdown (noop)")


class SoftwareTransitionPipeline(TransitionPipeline):
    def upload_assets(self, packet) -> None:  # type: ignore[override]
        logger.debug("SoftwareTransitionPipeline.upload_assets (noop)")

    def render(self, packet) -> None:  # type: ignore[override]
        logger.debug("SoftwareTransitionPipeline.render (noop)")

    def cleanup(self) -> None:  # type: ignore[override]
        logger.debug("SoftwareTransitionPipeline.cleanup (noop)")


class SoftwareRendererBackend(RendererBackend):
    """Fallback renderer relying on existing CPU transition pipeline."""

    def initialize(self) -> None:  # type: ignore[override]
        logger.info("Using software renderer backend")

    def shutdown(self) -> None:  # type: ignore[override]
        logger.info("Shutting down software renderer backend")

    def create_surface(self, descriptor: SurfaceDescriptor) -> RenderSurface:  # type: ignore[override]
        return SoftwareRenderSurface(descriptor)

    def destroy_surface(self, surface: RenderSurface) -> None:  # type: ignore[override]
        surface.shutdown()

    def create_transition_pipeline(self, transition_name: str) -> TransitionPipeline:  # type: ignore[override]
        logger.debug("SoftwareRendererBackend.create_transition_pipeline -> %s", transition_name)
        return SoftwareTransitionPipeline()

    def release_transition_pipeline(self, pipeline: TransitionPipeline) -> None:  # type: ignore[override]
        pipeline.cleanup()

    def _build_capabilities(self) -> BackendCapabilities:  # type: ignore[override]
        return BackendCapabilities(
            api_name="Software",
            api_version="CPU",
            supports_triple_buffer=False,
            supports_vsync_toggle=False,
            supports_compute=False,
            supports_hdr=False,
        )
