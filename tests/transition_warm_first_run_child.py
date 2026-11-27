"""Child process of ``test_transition_warm_units.py`` (a fresh interpreter: imports are process-wide): one transition's
first run on the native background layer over a stand-in core, after a warm-up of the given kind, printing as JSON the
modules imported during the run's start and its first frames.

Usage: python tests/transition_warm_first_run_child.py <transition_id> <none|import|product|product_without_layer_units>
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


class _Composite:
    def set(self, **_config) -> None:
        pass

    def window_pixels(self):
        return (64, 36)

    def content_status(self):
        return SimpleNamespace(draws=1, failures=0, refused_run=0, failing=False)

    def state(self) -> dict:
        return {}

    def destroy(self) -> bool:
        return True


class _Mode:
    """Takes every call the layer makes and keeps nothing (the core's side is not what is measured here)."""

    def __init__(self) -> None:
        self.composite = _Composite()

    def state(self) -> dict:
        return {}

    def __getattr__(self, _name):
        return lambda *args, **kwargs: None


class _Signal:
    def connect(self, _slot) -> None:
        pass

    def disconnect(self, _slot) -> None:
        pass


class _Window:
    afterAnimating = _Signal()

    def effectiveDevicePixelRatio(self) -> float:  # noqa: N802
        return 1.0

    def size(self):
        return SimpleNamespace(width=lambda: 64, height=lambda: 36)


class _Item:
    def width(self) -> float:
        return 64.0

    def height(self) -> float:
        return 36.0

    def window(self):
        return _WINDOW


_WINDOW = _Window()


def _image(identity: str, value: int):
    from rendering.quick.image_state import PresentationImage

    return PresentationImage(identity=identity, source_path="", logical_size=(64.0, 36.0), device_pixel_ratio=1.0,
                             pixel_size=(64, 36), row_stride=64 * 4, rgba8=bytes((value, value, value, 255)) * 64 * 36)


def main() -> None:
    transition_id, warm = sys.argv[1], sys.argv[2]
    from PySide6.QtGui import QGuiApplication

    app = QGuiApplication.instance() or QGuiApplication([sys.argv[0]])
    from rendering.quick.render import native_background
    from rendering.quick.render.background_item import BackgroundRenderItem
    from rendering.quick.transitions.state import TransitionRun
    from tools.transition_contact_sheet import production_transition_spec

    native_background.NativeBackgroundLayer._arm = lambda self, signal: None
    native_background._fade_ms = lambda: 0
    if warm == "product_without_layer_units":
        native_background.NATIVE_WARM_UNITS = ()           # the control: the module's import alone (the old warm-up)
    layer = native_background.NativeBackgroundLayer(SimpleNamespace(mode=lambda _item: _Mode()), _Item())
    source, destination = _image("a", 40), _image("b", 200)
    layer.present(source)
    spec = production_transition_spec(transition_id, 1000)
    request = spec.build_request(runtime_generation=0, source_image=source, destination_image=destination)
    run = TransitionRun.start(run_id=1, request=request, start_ns=1_000_000_000)
    units = 0
    if warm == "import":
        from rendering.quick.transitions.implementation_registry import preload_quick_transition_implementation

        preload_quick_transition_implementation(transition_id)
        units = 1
    elif warm.startswith("product"):
        item = BackgroundRenderItem()
        item._native_layer = layer
        while (unit := item._gui_warm_unit(transition_id)) is not None and units < 16:
            unit()
            units += 1
    now = {"ns": run.start_ns}
    layer._clock_ns = lambda: now["ns"]
    before = set(sys.modules)
    layer.transition(run)
    for step in range(1, 6):
        now["ns"] = run.start_ns + (run.end_ns - run.start_ns) * step // 6
        layer.tick()
    imported = sorted(set(sys.modules) - before)
    drawn = layer.runs == 1 and layer.ticks == 5
    layer.close()
    del app
    print(json.dumps({"imported": imported, "units": units, "drawn": drawn}))


if __name__ == "__main__":
    main()
