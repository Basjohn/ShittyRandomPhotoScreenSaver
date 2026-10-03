"""The wallpaper a 3D Visualizer reflects: a small immutable copy of the displayed photograph.

A mode that reflects (its descriptor's ``backdrop_setting`` above zero, on a 3D Detail tier
with reflections) gets the displayed ``PresentationImage`` downsampled once per image change
(``make_visualizer_backdrop``: a fast quarter-size pass, then a smooth one, about 1.4 ms for 4K)
on the GUI thread by its owner, carried to the renderer in the mode's parameters like any other
immutable value, and uploaded there into the renderer's own small mipmapped texture
(``BackdropEnvironment``). No GL texture is shared with the background (PR-04's lent textures
stay its own) and the target being drawn is never read back.
"""
from __future__ import annotations

from dataclasses import dataclass

from rendering.gl_programs.scene3d import SCENE3D_ENVIRONMENT_SIZE


@dataclass(frozen=True, slots=True)
class VisualizerBackdrop:
    """``identity`` of the photograph it was made from, its ``size`` and RGBA8 pixels, bottom row first."""

    identity: str
    size: tuple[int, int]
    rgba: bytes


def backdrop_size(pixel_size: tuple[int, int]) -> tuple[int, int]:
    """The copy's size: the photograph's aspect, ``SCENE3D_ENVIRONMENT_SIZE`` on the longer side."""
    width, height = max(1, int(pixel_size[0])), max(1, int(pixel_size[1]))
    scale = SCENE3D_ENVIRONMENT_SIZE / max(width, height)
    return max(1, round(width * scale)), max(1, round(height * scale))


def make_visualizer_backdrop(image) -> VisualizerBackdrop:
    """Downsample a ``PresentationImage`` for reflection (rows flipped to GL's bottom-up order)."""
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QImage

    width, height = (int(value) for value in image.pixel_size)
    source = QImage(image.rgba8, width, height, int(image.row_stride), QImage.Format.Format_RGBA8888)
    target = backdrop_size((width, height))
    if width >= 4 * target[0] and height >= 4 * target[1]:
        source = source.scaled(width // 4, height // 4, Qt.AspectRatioMode.IgnoreAspectRatio,
                               Qt.TransformationMode.FastTransformation)
    small = source.scaled(target[0], target[1], Qt.AspectRatioMode.IgnoreAspectRatio,
                          Qt.TransformationMode.SmoothTransformation).flipped(Qt.Orientation.Vertical)
    if small.format() != QImage.Format.Format_RGBA8888:
        small = small.convertToFormat(QImage.Format.Format_RGBA8888)
    row = target[0] * 4
    bits = bytes(small.constBits())
    if small.bytesPerLine() != row:
        bits = b"".join(bits[y * small.bytesPerLine():y * small.bytesPerLine() + row] for y in range(target[1]))
    return VisualizerBackdrop(identity=str(image.identity), size=target, rgba=bits[:row * target[1]])


__all__ = ["VisualizerBackdrop", "backdrop_size", "make_visualizer_backdrop"]
