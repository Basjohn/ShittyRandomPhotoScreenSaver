"""N5.7a, the display's background layer on the native core (D7 point 1): GPU-free.

- The presenter's fit and crop has one owner (``rendering.quick.background_placement``), read by the Python presenter's
  retained ``QSGImageNode`` and by the native layer's pass settings: a change of the owner moves both (the negative
  control: neither path keeps a copy of the rule).
- The layer (``rendering.quick.render.native_background``) over a stand-in core: a still, opaque, background-layer
  composite with the product pack's one pass sampling the photo; each new image sent once, the same image never again;
  the first photo fades in, the item's image going fades it out; a lost texture is sent again from the item's image; the
  close retires and destroys it.
- ``BackgroundRenderItem`` makes the layer only on the native background's backend, and only at its first image; on
  OpenGL nothing native is made (production keeps the Python presenter).

The drawn proof is ``native/core/python/background_layer_check.py`` (the hidden host, both backends, real photos).
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from rendering.quick import background_placement as placement_module
from rendering.quick.background_placement import background_placement
from rendering.quick.image_state import PresentationImage


def _image(identity: str, size: tuple[int, int] = (8, 4), value: int = 40) -> PresentationImage:
    width, height = size
    return PresentationImage(identity=identity, source_path="", logical_size=(float(width), float(height)),
                             device_pixel_ratio=1.0, pixel_size=size, row_stride=width * 4,
                             rgba8=bytes((value, value, value, 255)) * (width * height))


# --------------------------------------------------------------------------------------------- the one owner


def test_the_placement_is_the_whole_photo_over_the_whole_item():
    placement = background_placement((2560, 1440), (1706.6666667, 960.0))
    assert placement.source_rect == (0.0, 0.0, 2560.0, 1440.0)
    assert placement.target_rect == (0.0, 0.0, 1706.6666667, 960.0)
    assert placement.source_uv == (0.0, 0.0, 1.0, 1.0)
    with pytest.raises(ValueError):
        background_placement((0, 10), (10.0, 10.0))


def test_the_python_presenter_and_the_native_layer_read_the_one_owner(qt_app, monkeypatch):
    from PySide6.QtQuick import QSGNode

    from rendering.quick.render import background_image_node
    from rendering.quick.render.background_image_node import RetainedBackgroundSceneNode
    from rendering.quick.render.native_background import background_layer_settings
    from rendering.quick.render.telemetry import RenderNodeTelemetry

    rects: dict = {}

    class _FakeImageNode(QSGNode):
        def setOwnsTexture(self, _owns) -> None:  # noqa: N802
            pass

        def setFiltering(self, _filtering) -> None:  # noqa: N802
            pass

        def setTexture(self, _texture) -> None:  # noqa: N802
            pass

        def setSourceRect(self, rect) -> None:  # noqa: N802
            rects["source"] = (rect.x(), rect.y(), rect.width(), rect.height())

        def setRect(self, rect) -> None:  # noqa: N802
            rects["target"] = (rect.x(), rect.y(), rect.width(), rect.height())

    class _Window:
        def createImageNode(self):  # noqa: N802
            return _FakeImageNode()

        def createTextureFromImage(self, _image, _options):  # noqa: N802
            return object()

    monkeypatch.setattr(background_image_node, "validate_or_quit_current_opengl_context", lambda **_kwargs: None)
    node = RetainedBackgroundSceneNode(window=_Window(), telemetry=RenderNodeTelemetry(gui_thread_id=1),
                                       screen_index=0, frame_trace=None)
    node._synchronize_native_image(_image("a"), logical_size=(8.0, 4.0))
    assert rects == {"source": (0.0, 0.0, 8.0, 4.0), "target": (0.0, 0.0, 8.0, 4.0)}
    assert background_layer_settings((8, 4), (8.0, 4.0)) == {"u_source_uv": [0.0, 0.0, 1.0, 1.0]}

    # Negative control: another rule in the owner moves both paths (neither keeps a copy of it).
    def cropped(pixel_size, logical_size):
        return placement_module.BackgroundPlacement(pixel_size=tuple(pixel_size), source_rect=(2.0, 1.0, 4.0, 2.0),
                                                    target_rect=(0.0, 0.0, float(logical_size[0]),
                                                                 float(logical_size[1])))

    monkeypatch.setattr(background_image_node, "background_placement", cropped)
    monkeypatch.setattr(placement_module, "background_placement", cropped)
    node._synchronize_native_image(_image("b"), logical_size=(8.0, 4.0))
    assert rects["source"] == (2.0, 1.0, 4.0, 2.0)
    assert background_layer_settings((8, 4), (8.0, 4.0)) == {"u_source_uv": [0.25, 0.25, 0.5, 0.5]}


# --------------------------------------------------------------------------------------------- the layer


class _Composite:
    def __init__(self, calls: list) -> None:
        self.calls = calls
        self.destroyed = False

    def set(self, **config) -> None:
        self.calls.append(("set", config))

    def window_pixels(self):
        return (16, 8)

    def content_status(self):
        return SimpleNamespace(draws=1, failures=0, refused_run=0, failing=False)

    def state(self) -> dict:
        return {}

    def destroy(self) -> bool:
        self.destroyed = True
        self.calls.append(("destroy",))
        return True


class _Mode:
    def __init__(self, calls: list) -> None:
        self.calls = calls
        self.composite = _Composite(calls)
        self.lost = None

    def still(self, still=True) -> None:
        self.calls.append(("still", still))

    def program(self, passes, settings=None) -> None:
        self.calls.append(("program", passes, settings))

    def on_textures_lost(self, callback) -> None:
        self.lost = callback

    def texture(self, name, pixels, size, **_kwargs) -> None:
        self.calls.append(("texture", name, tuple(size), len(pixels)))

    def settings(self, values) -> None:
        self.calls.append(("settings", values))

    def update(self) -> None:
        self.calls.append(("update",))

    def retire(self) -> None:
        self.calls.append(("retire",))

    def state(self) -> dict:
        return {}


class _Window:
    def size(self):
        return SimpleNamespace(width=lambda: 8, height=lambda: 4)


class _Item:
    def __init__(self) -> None:
        self.w, self.h = 8.0, 4.0

    def width(self) -> float:
        return self.w

    def height(self) -> float:
        return self.h

    def window(self):
        return None                      # no window edges in a GPU-free test


@pytest.fixture
def layer(monkeypatch):
    from rendering.quick.render import native_background

    calls: list = []
    mode = _Mode(calls)
    core = SimpleNamespace(mode=lambda _item: mode)
    monkeypatch.setattr(native_background, "_fade_ms", lambda: 250)
    made = native_background.NativeBackgroundLayer(core, _Item())
    return made, mode, calls


def test_the_layer_is_an_opaque_still_background_with_the_product_pass(layer):
    from rendering.quick.render.native_background import PASS_NAME, SAMPLER, TEXTURE, background_layer_pack_path

    made, mode, calls = layer
    made.present(_image("a"))
    composite_config = next(c[1] for c in calls if c[0] == "set")
    assert composite_config["layer"] == "background" and composite_config["opaque"] is True
    assert composite_config["coverage"] is None and composite_config["visible"] is False
    assert ("still", True) in calls
    passes = next(c[1] for c in calls if c[0] == "program")
    assert [p.name for p in passes] == [PASS_NAME] and passes[0].blend == "replace"
    assert passes[0].pack == background_layer_pack_path().read_bytes()
    assert [(s.name, s.texture, s.filter, s.wrap, s.mips) for s in passes[0].samplers] == [
        (SAMPLER, TEXTURE, "linear", "clamp", "none")]
    # The first photo: its texture once, its placement's settings, and the layer fades in.
    assert [c for c in calls if c[0] == "texture"] == [("texture", TEXTURE, (8, 4), 8 * 4 * 4)]
    assert ("settings", {"u_source_uv": [0.0, 0.0, 1.0, 1.0]}) in calls
    shown = [c[1] for c in calls if c[0] == "set" and c[1].get("visible") is True]
    assert len(shown) == 1 and shown[0]["fade_ms"] == 250 and shown[0]["rect"] == [0.0, 0.0, 8.0, 4.0]


def test_an_image_is_sent_once_and_its_going_fades_the_layer_out(layer):
    made, _mode, calls = layer
    first = _image("a")
    made.present(first)
    made.present(first)                                       # the same image: nothing sent again
    assert len([c for c in calls if c[0] == "texture"]) == 1
    made.present(_image("b", value=90))
    assert len([c for c in calls if c[0] == "texture"]) == 2
    made.present(None)
    assert calls[-1] == ("set", {"visible": False, "fade_ms": 250})   # fade, never vanish
    # A size change places it again, with no image sent.
    sent = len([c for c in calls if c[0] == "texture"])
    made.present(_image("c"))
    made._item.w = 10.0
    made.geometry_changed()
    assert len([c for c in calls if c[0] == "texture"]) == sent + 1
    assert any(c[0] == "set" and c[1].get("rect") == [0.0, 0.0, 10.0, 4.0] for c in calls)


def test_a_lost_photo_is_sent_again_from_the_items_image_and_the_close_retires(layer):
    from rendering.quick.render.native_background import TEXTURE

    made, mode, calls = layer
    made.present(_image("a"))
    mode.lost(["other"])                                      # not the layer's texture: nothing
    assert len([c for c in calls if c[0] == "texture"]) == 1
    mode.lost([TEXTURE])
    assert len([c for c in calls if c[0] == "texture"]) == 2 and made.resent == 1
    made.close()
    assert calls[-2:] == [("retire",), ("destroy",)]
    made.present(_image("b"))                                 # closed: nothing more
    assert len([c for c in calls if c[0] == "texture"]) == 2


# --------------------------------------------------------------------------------------------- the item's route


def test_the_item_makes_the_layer_only_on_the_native_backend_at_its_first_image(qt_app, monkeypatch):
    from rendering.quick.render import background_item, native_background

    made: list = []

    class _Layer:
        def __init__(self) -> None:
            self.images: list = []
            self.closed = False

        def present(self, image) -> None:
            self.images.append(image)

        def geometry_changed(self) -> None:
            pass

        def close(self) -> None:
            self.closed = True

    def attach(_item, backend=None):
        made.append(_Layer())
        return made[-1]

    monkeypatch.setattr(native_background, "attach_native_background", attach)

    # OpenGL (production): the Python presenter only.
    monkeypatch.setattr(background_item, "_native_background_wanted", lambda: False)
    item = background_item.BackgroundRenderItem()
    item.set_presentation_image(_image("a"))
    assert made == [] and item.native_layer is None

    # The native background's backend (no Python renderer there): the layer at the first image, and every change.
    monkeypatch.setattr(background_item, "background_family_available_on_backend", lambda: False)
    monkeypatch.setattr(background_item, "_native_background_wanted", lambda: True)
    item = background_item.BackgroundRenderItem()
    assert made == []                                         # nothing before an image
    first, second = _image("a"), _image("b")
    item.set_presentation_image(first)
    item.set_presentation_image(second)
    item.set_presentation_image(None)
    assert len(made) == 1 and made[0].images == [first, second, None]
    item.close_native_layer()
    assert made[0].closed and item.native_layer is None
