"""An empty or waiting background is not the display's first frame (N5.2h audit item 1).

Before the switch the Python node's telemetry said whether a swapped frame held a real photo
(``_render_snapshot_has_intentional_base_frame``); the reveal waited for it, so the widgets never faded in over black
or the desktop. Since the switch the background is the native core's layer (or the degraded display's image node), and
its own facts say so: ``NativeBackgroundLayer.photo_drawn`` (the core counted a draw, which it does only once every
texture the program reads is in) and ``BackgroundRenderItem.background_drawn``. These bars pin both, and the core's
rule they read.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

pytest.importorskip("PySide6")

ROOT = Path(__file__).resolve().parents[1]


class _Composite:
    def __init__(self) -> None:
        self.status = SimpleNamespace(draws=0, failures=0, refused_run=0, failing=False)

    def set(self, **_config) -> None:
        pass

    def window_pixels(self):
        return (8, 4)

    def content_status(self):
        return self.status

    def destroy(self) -> bool:
        return True


class _Mode:
    def __init__(self) -> None:
        self.composite = _Composite()

    def __getattr__(self, _name):                 # every other call of the layer: accepted, ignored
        return lambda *args, **kwargs: None


class _Item:
    def width(self) -> float:
        return 8.0

    def height(self) -> float:
        return 4.0

    def window(self):
        return None


def _image(identity: str):
    from rendering.quick.image_state import PresentationImage

    return PresentationImage(identity=identity, source_path="", logical_size=(8.0, 4.0), device_pixel_ratio=1.0,
                             pixel_size=(8, 4), row_stride=32, rgba8=bytes((40, 40, 40, 255)) * 32)


@pytest.fixture
def layer(monkeypatch):
    from rendering.quick.render import native_background

    mode = _Mode()
    monkeypatch.setattr(native_background, "_fade_ms", lambda: 250)
    return native_background.NativeBackgroundLayer(SimpleNamespace(mode=lambda _item: mode), _Item()), mode


def test_a_layer_waiting_for_its_photo_has_drawn_nothing(layer):
    made, mode = layer
    assert made.photo_drawn() is False                       # nothing made yet
    made.present(_image("a"))
    assert made.drawing is True                              # shown (fading in) ...
    assert made.photo_drawn() is False                       # ... but its photo's upload is not in: no draw counted
    mode.composite.status = SimpleNamespace(draws=1, failures=0, refused_run=0, failing=False)
    assert made.photo_drawn() is True


def test_a_failed_or_emptied_or_closed_layer_is_not_a_drawn_photo(layer):
    made, mode = layer
    made.present(_image("a"))
    mode.composite.status = SimpleNamespace(draws=3, failures=1, refused_run=0, failing=True)
    assert made.photo_drawn() is False                       # a content that failed to build
    mode.composite.status = SimpleNamespace(draws=3, failures=0, refused_run=0, failing=False)
    made.present(None)
    assert made.photo_drawn() is False                       # the item's image went
    made.present(_image("b"))
    assert made.photo_drawn() is True
    made.close()
    assert made.photo_drawn() is False


def test_the_core_counts_a_draw_only_with_every_texture_in():
    """``ModeContent::record``: the drawn flag noted for the content's report is ``m_draw && withPasses``, and
    ``withPasses`` needs every texture (and mesh) in, so a still waiting for its photo's upload job counts no draw."""
    source = (ROOT / "native" / "core" / "src" / "mode_content.cpp").read_text(encoding="utf-8")
    assert "const bool withPasses = texturesReady() && meshesReady() && !m_geometryWaiting;" in source
    assert "const bool draw = m_draw && withPasses;" in source
    assert "m_source->noteRecorded(draw, m_reason, m_facts);" in source


def test_the_item_reports_a_drawn_background_only_from_its_layer_or_degraded_node(qt_app, monkeypatch):
    from rendering.quick.render import background_item

    monkeypatch.setattr(background_item, "_native_background_wanted", lambda: False)
    item = background_item.BackgroundRenderItem()
    assert item.background_drawn is False                    # no layer, no degraded node
    item._degraded = True
    assert item.updatePaintNode(None, None) is None          # degraded with no photo (and no window): nothing drawn
    assert item.background_drawn is False
    drawn = {"value": False}
    item._native_layer = SimpleNamespace(photo_drawn=lambda: drawn["value"], close=lambda: None)
    assert item.background_drawn is False
    drawn["value"] = True
    assert item.background_drawn is True
    item._native_layer = None
