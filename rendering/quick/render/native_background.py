"""The display's background layer on the native core (Current_Plan.md N5.7a, D7 point 1; D10 point 3).

On the Vulkan rehearsal path (the backend owner's choice, ``rendering.quick.bootstrap``) the display's wallpaper comes
from the native core: ``BackgroundRenderItem`` keeps everything it owns (the presentation image, its identity rule, the
transition run, the timing of every change) and hands each new image to this layer, a native composite item in it that
draws the photo with N4.a's fullscreen pass as a still (``native/core/src/mode_content.h``, "Stills") into a target it
keeps. On OpenGL nothing here is created: production keeps the Python presenter (the retained ``QSGImageNode``,
07486d83) until the background family switches as one unit (N5.2h).

- The photo's textures are the core's: the pixels (the item's ``PresentationImage``, which it keeps) are copied once
  into the core and uploaded by N3.8's job service on a Vulkan device with a second queue (in the frame elsewhere); the
  photo drawn changes at the frame edge its job is published at, and until then the previous photo stays (never a
  blank between two photos). The wrapped-texture bridge of the Python presenter (PR-04) is OpenGL only and is not used.
- The fit and crop is the presenter's one owner, ``rendering.quick.background_placement`` (the Python presenter's
  ``QSGImageNode`` reads it too): the pass's ``u_source_uv``, over the item's own rect.
- At rest nothing is drawn again: the layer's target is retained and the core records only when the photo, the placement
  or the item's size changed; Qt composites the retained texture, opaque, in its opaque pass as it does the retained
  image node (``opaque``), and the frame driver records the layer before every other surface (``layer``, D5.2).
- Fade, never vanish: the layer fades in with its first photo and out when the item's image goes or the core's content
  fails; a lost texture (a node made again) is sent again from the image the item keeps.

GUI thread only. Events, never timers: the item's size changes, the window's ``afterSynchronizing`` (once, while the
layer waits for its window's framebuffer) and ``afterRendering`` (once after a change, to read the core's verdict).
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from core.logging.logger import get_logger

logger = get_logger(__name__)

#: The layer's texture and its pass (``background_layer.frag``'s sampler and block).
TEXTURE = "photo"
PASS_NAME = "background_layer"
SAMPLER = "uPhoto"


def _fade_ms() -> int:
    """The layer fades in with its first photo and out when it goes (fade, never vanish): the Visualizer's activation
    fade, the product's fade for a surface that appears (read lazily, so importing this module stays light)."""
    from widgets.spotify_visualizer.quick_display_visualizer_owner import ACTIVATION_SCENE_FADE_DURATION_S

    return round(ACTIVATION_SCENE_FADE_DURATION_S * 1000.0)


def background_layer_pack_path() -> Path:
    """The pass's fragment pack, baked beside its source by ``tools/regen_qrc.py --shaders`` (the frozen build ships the
    folder with the QML)."""
    from rendering.quick.bootstrap import quick_qml_root

    return quick_qml_root() / "shaders" / "background_layer.frag.qsb"


def background_layer_program(pack: bytes | None = None) -> list:
    """The layer's one pass: the photo over the whole target, replacing it (the photo is opaque), sampled linearly with
    no mips and clamped, as the retained image node samples it."""
    from rendering.native.mode import ModePass, PassSampler

    data = background_layer_pack_path().read_bytes() if pack is None else bytes(pack)
    return [ModePass(PASS_NAME, data, "replace", (PassSampler(SAMPLER, TEXTURE, "linear", "clamp", "none"),))]


def background_layer_settings(pixel_size: tuple[int, int], logical_size: tuple[float, float]) -> dict:
    """The pass's settings for a photo of ``pixel_size`` over an item of ``logical_size``: the presenter's placement."""
    from rendering.quick.background_placement import background_placement

    return {"u_source_uv": list(background_placement(pixel_size, logical_size).source_uv)}


def native_background_wanted(backend: str | None = None) -> bool:
    """Whether the display's background comes from the native core on ``backend`` (the process's when None): Vulkan."""
    if backend is None:
        from rendering.quick.bootstrap import quick_backend_api

        backend = quick_backend_api()
    return str(backend) == "vulkan"


class NativeBackgroundLayer:
    """One display's background layer: a native composite item in ``item`` (the ``BackgroundRenderItem``) drawing the
    photo the item hands it."""

    def __init__(self, core: Any, item: Any) -> None:
        self._core = core
        self._item = item
        self._mode: Any = None
        self._image: Any = None          # the PresentationImage drawn (the item keeps it; the core's copy goes)
        self._settings: dict | None = None
        self._placed: tuple | None = None
        self._shown = False
        self._failure: str | None = None
        self._edges: dict[str, Any] = {}
        self.closed = False
        self.sent = 0                    # images handed to the core
        self.resent = 0                  # images sent again after a lost edge

    # ---------------------------------------------------------------------------------------------------- the layer

    @property
    def mode(self) -> Any:
        return self._mode

    def _ensure(self) -> Any:
        if self._mode is None:
            mode = self._core.mode(self._item)
            # Hidden until its first photo, then faded in; a background layer, opaque, never clipped (it is the display).
            mode.composite.set(rect=[0.0, 0.0, 0.0, 0.0], coverage=None, quarters=0, visible=False, opacity=1.0,
                               layer="background", opaque=True)
            mode.still(True)
            mode.program(background_layer_program())
            mode.on_textures_lost(self._textures_lost)
            self._mode = mode
        return self._mode

    def present(self, image: Any) -> None:
        """The item's presentation image changed (``None``: it has none). Never raises: a failure fades the layer out
        and is logged once until the layer draws again."""
        if self.closed:
            return
        try:
            self._present(image)
        except Exception as exc:
            self._fail(f"the background layer could not take the image: {exc}", exc)

    def _present(self, image: Any) -> None:
        if image is None:
            self._image = None
            self._hide()
            return
        mode = self._ensure()
        if image is not self._image:
            mode.texture(TEXTURE, image.rgba8, image.pixel_size)
            self._image = image
            self.sent += 1
        self._sync(force=True)

    def geometry_changed(self) -> None:
        """The item's size changed (or its window's pixels): the layer is placed again. Never raises."""
        if self.closed or self._mode is None:
            return
        try:
            self._sync(force=False)
        except Exception as exc:
            self._fail(f"the background layer could not be placed: {exc}", exc)

    def _sync(self, *, force: bool) -> None:
        mode = self._mode
        image = self._image
        if mode is None or image is None:
            return
        width, height = float(self._item.width()), float(self._item.height())
        changed = force
        settings = background_layer_settings(image.pixel_size, (width, height))
        if settings != self._settings:
            mode.settings(settings)
            self._settings = settings
            changed = True
        placed = (width, height, self._pixel_ratio())
        if placed != self._placed or force:
            changed = True
            config: dict = {"rect": [0.0, 0.0, width, height]}
            if placed[2] is not None:
                config["pixel_ratio"] = list(placed[2])
            if not self._shown and self._failure is None and width > 0.0 and height > 0.0:
                config.update(visible=True, fade_ms=_fade_ms())   # fade, never vanish: in with its first photo
                self._shown = True
            mode.composite.set(**config)
            self._placed = placed
        if not changed:
            return                                                # nothing new: no frame asked for (never a loop)
        mode.update()
        self._arm("afterRendering")                               # the core's verdict, once this change has rendered

    def _pixel_ratio(self) -> tuple[float, float] | None:
        """The window's own logical-to-framebuffer ratio (audit 14 Nov, H1: not the dpr where the window's logical
        size is rounded), from the framebuffer the native item read at its last sync; None until it has read it (the
        window's device pixel ratio is used meanwhile, and the window's next synchronisation places the layer again)."""
        from rendering.native.composite import window_pixel_ratio

        window = self._item.window()
        pixels = self._mode.composite.window_pixels() if self._mode is not None else None
        if window is None or pixels is None:
            self._arm("afterSynchronizing")
            return None
        size = window.size()
        return window_pixel_ratio((float(size.width()), float(size.height())), pixels)

    def _hide(self) -> None:
        if self._mode is not None and self._shown:
            self._mode.composite.set(visible=False, fade_ms=_fade_ms())   # fade, never vanish
            self._shown = False

    def _fail(self, message: str, exc: BaseException | None = None) -> None:
        if self._failure is None:
            logger.error("[BACKGROUND][NATIVE] %s; the layer fades out until it draws again", message,
                         exc_info=exc)
        self._failure = message
        try:
            self._hide()
        except Exception:
            logger.debug("[BACKGROUND][NATIVE] fading the layer out failed", exc_info=True)

    def _verdict(self) -> None:
        """After a change rendered: a content that failed to build fades the layer out; one that draws again (after a
        failure) fades it back in."""
        if self._mode is None:
            return
        status = self._mode.composite.content_status()
        if status is None:
            return
        if status.failing:
            self._fail(f"the background layer's content failed to build ({status.failures} failure(s))")
        elif self._failure is not None and status.draws > 0 and self._image is not None:
            logger.info("[BACKGROUND][NATIVE] The background layer draws again; it fades back in")
            self._failure = None
            self._sync(force=True)

    def _textures_lost(self, names: list[str]) -> None:
        """The core lost the photo's texture (a node made again): it is sent again from the image the item keeps."""
        if self.closed or self._mode is None or self._image is None or TEXTURE not in names:
            return
        try:
            self._mode.texture(TEXTURE, self._image.rgba8, self._image.pixel_size)
            self.resent += 1
            self._mode.update()
        except Exception as exc:
            self._fail(f"the background layer could not send its photo again: {exc}", exc)

    # ---------------------------------------------------------------------------------------------------- the edges

    def _arm(self, signal: str) -> None:
        from rendering.quick.visualizer.native_route import _WindowEdge

        window = self._item.window()
        if window is None:
            return
        edge = self._edges.get(signal)
        if edge is None:
            edge = self._edges[signal] = _WindowEdge(signal, lambda s=signal: self._edge_fired(s))
        edge.arm(window)

    def _edge_fired(self, signal: str) -> None:
        if self.closed:
            return
        try:
            if signal == "afterRendering":
                self._verdict()
            else:
                self._sync(force=False)
        except Exception as exc:
            self._fail(f"the background layer's {signal} edge failed: {exc}", exc)

    def close(self) -> None:
        """The layer goes with its display generation (before the scene root is deleted). Idempotent."""
        if self.closed:
            return
        self.closed = True
        for edge in self._edges.values():
            try:
                edge.disarm()
            except Exception:
                pass
        mode, self._mode = self._mode, None
        self._image = None
        if mode is not None:
            try:
                mode.retire()                     # the lost listener goes with it (audit N38 L4)
            except Exception:
                logger.debug("[BACKGROUND][NATIVE] retiring the layer failed", exc_info=True)
            mode.composite.destroy()

    def state(self) -> dict:
        """The layer's composite and content (the harness's and the rehearsal's reading)."""
        if self._mode is None:
            return {"made": False, "closed": self.closed}
        return {"made": True, "closed": self.closed, "shown": self._shown, "failure": self._failure,
                "sent": self.sent, "resent": self.resent, "composite": self._mode.composite.state(),
                "mode": self._mode.state()}


def attach_native_background(item: Any, backend: str | None = None) -> NativeBackgroundLayer | None:
    """On the native background's backend: the layer of ``item`` (a ``BackgroundRenderItem``) from the process's native
    core (``rendering.quick.bootstrap.native_core``). Elsewhere None, and nothing is created."""
    if not native_background_wanted(backend):
        return None
    from rendering.quick.bootstrap import native_core

    core = native_core()
    if core is None:
        raise RuntimeError("the native background layer needs the native core (start_quick_backend on Vulkan)")
    return NativeBackgroundLayer(core, item)


__all__ = ["NativeBackgroundLayer", "PASS_NAME", "SAMPLER", "TEXTURE", "attach_native_background",
           "background_layer_pack_path", "background_layer_program", "background_layer_settings",
           "native_background_wanted"]
