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


_FIELD_NAMES: dict[type, tuple[str, ...]] = {}


def _with_field(instance, name: str, value):
    """A frozen frame dataclass with one field substituted, built as the frame codec builds a decoded frame (a new
    instance, every field set as it is; nothing re-validated or re-frozen: the other fields are the decoded ones)."""
    import dataclasses

    cls = type(instance)
    names = _FIELD_NAMES.get(cls)
    if names is None:
        names = _FIELD_NAMES[cls] = tuple(field.name for field in dataclasses.fields(cls))
    copy = object.__new__(cls)
    for field_name in names:
        object.__setattr__(copy, field_name, value if field_name == name else getattr(instance, field_name))
    return copy


class FrameBackdropCompletion:
    """The frame completion for frames the engine worker ticked: the reflected wallpaper the owner keeps put into a
    reflecting frame's parameters (native core P2b, work order 5 slice 5.4; checkpoint audits 7 A7-M1 and 8 A8-L1).

    The wallpaper is presentation data the owner makes on the GUI thread from the displayed photograph; the worker's
    presentation state never has one (shipping pixels to the worker to have them shipped back in the frame would be
    the wrong owner). A reflecting mode's frame carries ``backdrop`` / ``backdrop_blend_s`` in its parameters as
    captured in process (Sphere, Extruded Spectrum); the main side puts its own there when it takes the frame
    (``PacketMailbox.set_frame_completion``, on the render thread at sync admission), so the renderer reads exactly
    what it reads in process.

    O(changed) (A8-L1): the decoded parameters are already frozen, so only the two entries are replaced (their
    positions found once per parameter layout) and the frame and its mode state are rebuilt around them without
    re-validation, as the codec built them; the wallpaper is frozen once per wallpaper. Before, every reflecting
    frame re-froze its whole parameter map and re-ran both frames' validation (117 / 78 us median, Sphere / Extruded
    Spectrum). One per owner session, holding the frozen wallpaper; ``release`` (the owner's retire or its fallback in
    process) drops it, so nothing keeps a wallpaper past its owner."""

    __slots__ = ("_presentation", "_wallpaper", "_frozen", "_layout")

    def __init__(self, presentation_state) -> None:
        self._presentation = presentation_state
        self._wallpaper = None             # the wallpaper last frozen, and its frozen fields
        self._frozen = None
        self._layout = None                # (entries length, backdrop index, blend index) of the last layout

    def release(self) -> None:
        self._presentation = self._wallpaper = self._frozen = self._layout = None

    def _positions(self, entries) -> tuple[int, int] | None:
        layout = self._layout
        if layout is not None and layout[0] == len(entries) and entries[layout[1]][0] == "backdrop" \
                and entries[layout[2]][0] == "backdrop_blend_s":
            return layout[1], layout[2]
        found = {name: index for index, (name, _value) in enumerate(entries)
                 if name in ("backdrop", "backdrop_blend_s")}
        if len(found) != 2:
            return None
        self._layout = (len(entries), found["backdrop"], found["backdrop_blend_s"])
        return found["backdrop"], found["backdrop_blend_s"]

    def __call__(self, state):
        """``state`` completed (``state`` itself when nothing differs: no wallpaper, or one the frame has)."""
        from widgets.spotify_visualizer.render_state import FrozenFields, freeze_render_value

        presentation = self._presentation
        mode_state = getattr(state, "mode_state", None)
        parameters = getattr(mode_state, "parameters", None)
        if presentation is None or not isinstance(parameters, FrozenFields):
            return state
        entries = parameters.entries
        positions = self._positions(entries)
        if positions is None:
            return state
        backdrop = getattr(presentation, "_backdrop", None)
        blend_s = getattr(presentation, "_backdrop_blend_s", None)
        at_backdrop, at_blend = positions
        carried = entries[at_backdrop][1]
        carried_identity = None if carried is None else carried.get("identity")
        if carried_identity == (None if backdrop is None else backdrop.identity) and \
                entries[at_blend][1] == blend_s:
            return state
        if backdrop is None:
            frozen = None
        elif self._wallpaper is backdrop:
            frozen = self._frozen
        else:
            frozen = freeze_render_value(backdrop)            # once per wallpaper, as the in-process capture freezes it
            self._wallpaper, self._frozen = backdrop, frozen
        completed = list(entries)
        completed[at_backdrop] = ("backdrop", frozen)
        completed[at_blend] = ("backdrop_blend_s", freeze_render_value(blend_s))
        fields = FrozenFields._from_frozen_entries(tuple(completed))
        return _with_field(state, "mode_state", _with_field(mode_state, "parameters", fields))


__all__ = ["FrameBackdropCompletion", "VisualizerBackdrop", "backdrop_size", "make_visualizer_backdrop"]
