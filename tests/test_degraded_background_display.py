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


class _FakeLayer:
    """The native layer's surface the item uses: its failure callback and whether it draws."""

    def __init__(self):
        self.callback = None
        self.drawing = True
        self.presented = []

    def on_failure(self, callback):
        self.callback = callback

    def present(self, image):
        self.presented.append(image)


def test_a_layer_that_fails_after_it_was_made_fades_to_the_degraded_display(qt_app, fresh_owner, monkeypatch):
    """Lead decision (N5.2h): the layer's failure puts the degraded display under it at once (the layer then fades
    out over the photo, never to nothing); once it draws again the next photo drops the degraded node under it.
    Control: the failure callback is what degrades (an item whose layer never fails stays native)."""
    from rendering.quick.render import native_background
    from rendering.quick.render.background_item import BackgroundRenderItem

    layer = _FakeLayer()
    monkeypatch.setattr(native_background, "attach_native_background", lambda _item: layer)
    item = BackgroundRenderItem()
    item.set_presentation_image(_image("a", 40))
    assert item.native_layer is layer and not item.degraded and layer.callback is not None
    item.set_presentation_image(_image("b", 60))
    assert not item.degraded                             # control: no failure, no degraded display
    layer.drawing = False
    layer.callback()                                     # the core's verdict: the layer failed after it was made
    assert item.degraded
    item.set_presentation_image(_image("c", 80))         # still failed: the degraded display takes the photo
    assert item.degraded and len(layer.presented) == 3
    layer.drawing = True                                 # it draws again (faded back in over the photo)
    item.set_presentation_image(_image("d", 100))
    assert not item.degraded and len(layer.presented) == 4


def test_the_layers_failure_fades_to_the_photo_on_opengl(tmp_path):
    """background_layer_check's "fail" round in its own process (hidden hosts only): the product route's layer failing
    by the core's verdict fades over the degraded photo (within 1 level through every fade frame, exact after), fades
    back in when it draws again, and the control (the degraded display unhooked) fades to black. Needs the built
    module (only GitHub builds it); skipped where this checkout has none."""
    import json
    import os
    import subprocess
    import sys
    from pathlib import Path

    from rendering.native import loader

    root = Path(__file__).resolve().parents[1]
    module_dir = root / "release" / "native_module"
    if os.name != "nt" or not (module_dir / f"{loader.MODULE_NAME}.pyd").is_file():
        pytest.skip(f"the native core is not built in this checkout: no release/native_module/{loader.MODULE_NAME}.pyd")
    record_path = tmp_path / "child.json"
    env = os.environ.copy()
    env.pop("QT_QPA_PLATFORM", None)        # hidden hosts need Qt's own platform (offscreen has no GPU device)
    proc = subprocess.run(
        [sys.executable, str(root / "native" / "core" / "python" / "background_layer_check.py"), "--child", "--api",
         "opengl", "--rounds", "fail", "--repo", str(root), "--module-dir", str(module_dir), "--out-dir",
         str(tmp_path), "--child-json", str(record_path)],
        capture_output=True, text=True, timeout=1800, cwd=str(root), env=env)
    assert proc.returncode == 0, proc.stderr[-2000:]
    record = json.loads(record_path.read_text(encoding="utf-8"))
    assert not record.get("error"), record.get("error")
    assert record["fail"].get("pass") is True, record["fail"].get("checks") or record["fail"].get("error")
    assert record["live_hosts_at_end"] == 0
