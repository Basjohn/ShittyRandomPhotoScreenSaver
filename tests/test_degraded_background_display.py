"""N5.2h point 5: a module that loads on neither API leaves the degraded display: the photos through Qt's own image
node (hard cuts, no transitions), the reason logged as an error once, the card backdrop not made. GPU-free where it
can be; the start path runs on the real owner with a loader that fails."""
from __future__ import annotations

import logging

import pytest

from rendering.quick import bootstrap


@pytest.fixture
def fresh_owner():
    bootstrap.reset_quick_backend_for_testing()
    yield bootstrap._owner
    bootstrap.reset_quick_backend_for_testing()


def _failing_loader():
    raise RuntimeError("the module is not built")


def test_an_opengl_start_loads_the_core(qt_app, fresh_owner):
    core = object()
    backend = bootstrap.start_quick_backend(load_core=lambda: core)
    assert backend.api == "opengl" and bootstrap.native_core() is core
    assert bootstrap.degraded_reason() == ""


def test_a_core_that_loads_on_neither_api_degrades_once_with_one_error(qt_app, fresh_owner, caplog):
    with caplog.at_level(logging.ERROR):
        bootstrap.start_quick_backend(load_core=_failing_loader)
        bootstrap._degrade("a second reason")            # later failures never log again
    assert bootstrap.native_core() is None
    assert "not built" in bootstrap.degraded_reason()
    errors = [r for r in caplog.records if r.levelno >= logging.ERROR and "Degraded display" in r.getMessage()]
    assert len(errors) == 1


def _image(identity: str, value: int):
    from rendering.quick.image_state import PresentationImage

    width, height = 8, 4
    return PresentationImage(identity=identity, source_path="", logical_size=(float(width), float(height)),
                             device_pixel_ratio=1.0, pixel_size=(width, height), row_stride=width * 4,
                             rgba8=bytes((value, value, value, 255)) * (width * height))


def test_the_degraded_item_shows_the_photo_through_an_image_node_and_cuts(qt_app, fresh_owner, monkeypatch):
    from rendering.quick.render.background_item import BackgroundRenderItem
    from rendering.quick.render.degraded_background import DegradedBackgroundNode
    from rendering.quick.surface_backdrop_owner import backdrop_available
    import rendering.quick.render.degraded_background as degraded

    item = BackgroundRenderItem()
    assert item._native_layer_wanted                     # OpenGL is a native route now (no Python presenter)
    first, second = _image("a", 40), _image("b", 90)
    item.set_presentation_image(first)                   # no core: the layer cannot be made
    assert item.degraded and item.native_layer is None
    assert backdrop_available() is False

    class _Window:
        def __init__(self):
            self.uploads = []

        def createTextureFromImage(self, image, _options):
            from PySide6.QtQuick import QSGTexture  # noqa: F401  (the real type is not needed here)

            self.uploads.append((image.width(), image.height()))
            return _Texture()

        def createImageNode(self):
            return _ImageNode()

    class _Texture:
        def setParent(self, _parent):
            pass

    class _ImageNode:
        def __init__(self):
            self.textures = []

        def setOwnsTexture(self, owns):
            self.owns = owns

        def setTexture(self, texture):
            self.textures.append(texture)

        def setSourceRect(self, rect):
            self.source = rect

        def setRect(self, rect):
            self.rect = rect

    window = _Window()
    node = DegradedBackgroundNode.__new__(DegradedBackgroundNode)
    node._window, node._image_node, node._image = window, None, None
    node.appendChildNode = lambda child: None
    monkeypatch.setattr(degraded, "shiboken6", type("S", (), {"invalidate": staticmethod(lambda _t: None)}))
    node.synchronize(first, (64.0, 36.0))
    node.synchronize(first, (64.0, 36.0))                # the same photo: no second upload
    node.synchronize(second, (64.0, 36.0))               # a new photo: one texture swap, a hard cut
    assert len(window.uploads) == 2 and len(node._image_node.textures) == 2 and node._image_node.owns
    assert node.image is second
