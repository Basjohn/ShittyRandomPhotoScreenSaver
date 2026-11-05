"""The environment a reflecting 3D mode mirrors in the Studio (mode-neutral).

Production gives a reflecting mode (its descriptor's ``backdrop_setting`` above zero, on a 3D Detail tier with
reflections) the photograph on screen, downsampled by ``widgets.spotify_visualizer.backdrop.make_visualizer_backdrop``
into the presentation state's ``_backdrop`` (``QuickDisplayVisualizerOwner._refresh_backdrop``). The Studio has no
photograph on screen, so it reflects one the saver would show: the first image of the saver's own folder sources
(``sources.folders``, the folder source's supported formats, in a stable order). Only when no source image is
available does it reflect a neutral generated sky (a soft vertical gradient), never nothing: a mirror preset
previewed with nothing to reflect would show plain cubes the live saver never shows.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

_SCAN_LIMIT = 4000            # files looked at per folder before giving up (a huge library is not walked)
_MAX_EDGE = 1920              # the photograph is scaled like a displayed one would be before the backdrop pass


def first_source_image(folders: Iterable[str]) -> Path | None:
    from sources.folder_source import SUPPORTED_EXTENSIONS
    for folder in folders or ():
        root = Path(str(folder))
        if not root.is_dir():
            continue
        seen = 0
        for directory, names, files in _walk(root):
            for name in sorted(files):
                seen += 1
                if Path(name).suffix.lower() in SUPPORTED_EXTENSIONS:
                    return Path(directory) / name
                if seen >= _SCAN_LIMIT:
                    break
            if seen >= _SCAN_LIMIT:
                break
    return None


def _walk(root: Path):
    import os
    for directory, names, files in os.walk(root):
        names.sort()
        yield directory, names, files


def neutral_image():
    """A soft generated sky (no file): what is reflected when the saver has no source image."""
    from PySide6.QtGui import QColor, QImage, QLinearGradient, QPainter
    image = QImage(512, 288, QImage.Format.Format_RGBA8888)
    painter = QPainter(image)
    gradient = QLinearGradient(0, 0, 0, image.height())
    for stop, colour in ((0.0, "#9fb7cf"), (0.45, "#d9e1e8"), (0.55, "#7a8794"), (1.0, "#2a3138")):
        gradient.setColorAt(stop, QColor(colour))
    painter.fillRect(image.rect(), gradient)
    painter.end()
    return image


def environment_image(folders: Iterable[str]) -> Any:
    """A ``PresentationImage`` to reflect: the saver's first source image, else the neutral sky."""
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QImage
    from rendering.quick.display_image_route import presentation_image_from_processed_qimage
    path = first_source_image(folders)
    image = QImage(str(path)) if path is not None else QImage()
    if image.isNull():
        return presentation_image_from_processed_qimage(neutral_image(), image_path="studio:neutral-sky")
    if max(image.width(), image.height()) > _MAX_EDGE:
        image = image.scaled(_MAX_EDGE, _MAX_EDGE, Qt.AspectRatioMode.KeepAspectRatio,
                             Qt.TransformationMode.SmoothTransformation)
    return presentation_image_from_processed_qimage(image, image_path=str(path))


def refresh_backdrop(state, mode_id: str, image) -> None:
    """Production's reflection rule on a presentation state (``_refresh_backdrop``): the backdrop of ``image`` while
    the mode reflects (its backdrop setting above zero on a tier with reflections), nothing otherwise."""
    from core.settings.visualizer_mode_registry import get_visualizer_mode_descriptor
    from rendering.gl_programs.scene3d import scene3d_detail
    setting = get_visualizer_mode_descriptor(mode_id).backdrop_setting
    reflects = (image is not None and bool(setting) and float(getattr(state, f"_{setting}")) > 0.0
                and scene3d_detail(state._scene3d_detail).reflections)
    current = getattr(state, "_backdrop", None)
    if not reflects:
        state._backdrop = None
        return
    if current is not None and current.identity == image.identity:
        return
    from widgets.spotify_visualizer.backdrop import make_visualizer_backdrop
    state._backdrop = make_visualizer_backdrop(image)
    state._backdrop_blend_s = None


def settle_backdrop(environment, frame, mirror, settled):
    """Introduce a frame's backdrop to a production renderer's ``BackdropEnvironment`` as already settled.

    A reflecting renderer fades a newly displayed wallpaper in over its blend time from when it first sees it
    (``BackdropEnvironment.textures``). In the saver the photograph has been on screen for a while; a Studio frame is
    one instant of a fixture, so the environment is shown the backdrop *before* the frame's logical time (a settled
    reflection), exactly as if the saver had already shown it. ``mirror(parameters)`` is the renderer's own
    reflect amount; ``settled`` the identity already introduced. Returns the identity now settled."""
    from rendering.quick.visualizer.implementation_values import parameter
    logical = frame if hasattr(frame, "mode_state") else None
    state = logical.mode_state if logical is not None else frame
    parameters = state.parameters
    if mirror(parameters) <= 0.0:
        return settled
    backdrop = parameter(parameters, "backdrop")
    if backdrop is None:
        return settled
    identity = str(backdrop["identity"])
    if identity == settled:
        return settled
    now = float(getattr(logical, "logical_timestamp", 0.0))
    environment.textures(backdrop, now - environment.BLEND_S - 1.0, parameter(parameters, "backdrop_blend_s"))
    return identity


__all__ = ["environment_image", "first_source_image", "neutral_image", "refresh_backdrop", "settle_backdrop"]
