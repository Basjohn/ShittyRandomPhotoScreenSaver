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


def complete_frame_backdrop(state, presentation_state):
    """A frame the engine worker ticked, completed with the reflected wallpaper the owner keeps (native core P2b,
    work order 5 slice 5.4; checkpoint audit 7, A7-M1).

    The wallpaper is presentation data the owner makes on the GUI thread from the displayed photograph; the worker's
    presentation state never has one (shipping pixels to the worker to have them shipped back in the frame would be
    the wrong owner). A reflecting mode's frame carries ``backdrop`` / ``backdrop_blend_s`` in its parameters as
    captured in process (Sphere, Extruded Spectrum); the main side puts its own there when it takes the frame, so
    the renderer reads exactly what it reads in process. Returns ``state`` itself when nothing differs (no
    wallpaper: no work)."""
    import dataclasses

    mode_state = getattr(state, "mode_state", None)
    parameters = getattr(mode_state, "parameters", None)
    if parameters is None or "backdrop" not in parameters:
        return state
    backdrop = getattr(presentation_state, "_backdrop", None)
    blend_s = getattr(presentation_state, "_backdrop_blend_s", None)
    carried = parameters.get("backdrop")
    carried_identity = None if carried is None else carried.get("identity")
    if carried_identity == (None if backdrop is None else backdrop.identity) and \
            parameters.get("backdrop_blend_s") == blend_s:
        return state
    from widgets.spotify_visualizer.render_state import freeze_render_fields, freeze_render_value

    # The frozen wallpaper is made once per wallpaper (the frame freezes it as the in-process capture does), not per
    # frame: one reference kept with the wallpaper it froze.
    cached = _FROZEN_WALLPAPER
    if backdrop is None:
        frozen = None
    elif cached[0] is backdrop:
        frozen = cached[1]
    else:
        frozen = freeze_render_value(backdrop)
        cached[0], cached[1] = backdrop, frozen
    fields = freeze_render_fields({**dict(parameters), "backdrop": frozen, "backdrop_blend_s": blend_s})
    return dataclasses.replace(state, mode_state=dataclasses.replace(mode_state, parameters=fields))


_FROZEN_WALLPAPER: list = [None, None]          # (the wallpaper, its frozen fields): the completion's one entry


__all__ = ["VisualizerBackdrop", "backdrop_size", "complete_frame_backdrop", "make_visualizer_backdrop"]
