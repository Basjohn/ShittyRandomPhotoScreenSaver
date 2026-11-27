"""Child process of ``test_transition_warm_units.py`` (a fresh interpreter: imports are process-wide): one transition's
first run on the native background layer over a stand-in core, after a warm-up of the given kind, printing as JSON
what the warm-up's units and the run's start and first frames imported and built.

A build is one shader text conversion (``portable._convert``, under ``portable_program`` and ``item_quad_program``) or
one block merge (``native_scene.native_one_block``, under ``population_packs`` too).

Usage: python tests/transition_warm_first_run_child.py <transition_id> <none|import|product>
"""
from __future__ import annotations

import json
import os
import sys
import time
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
_BUILDS = {"count": 0}


def _count_builds() -> None:
    from rendering.gl_programs import portable
    from rendering.quick.transitions import native_scene

    for module, name in ((portable, "_convert"), (native_scene, "native_one_block")):
        original = getattr(module, name)

        def counted(*args, _original=original, **kwargs):
            _BUILDS["count"] += 1
            return _original(*args, **kwargs)

        setattr(module, name, counted)


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

    _count_builds()
    native_background.NativeBackgroundLayer._arm = lambda self, signal: None
    native_background._fade_ms = lambda: 0
    layer = native_background.NativeBackgroundLayer(SimpleNamespace(mode=lambda _item: _Mode()), _Item())
    source, destination = _image("a", 40), _image("b", 200)
    layer.present(source)
    spec = production_transition_spec(transition_id, 1000)
    request = spec.build_request(runtime_generation=0, source_image=source, destination_image=destination)
    run = TransitionRun.start(run_id=1, request=request, start_ns=1_000_000_000)
    units: list[dict] = []
    if warm == "import":                                   # the control: the warm-up before the split (the import alone)
        from rendering.quick.transitions.implementation_registry import preload_quick_transition_implementation

        before, started = set(sys.modules), time.perf_counter()
        preload_quick_transition_implementation(transition_id)
        units.append({"builds": _BUILDS["count"], "imported": len(set(sys.modules) - before),
                      "ms": (time.perf_counter() - started) * 1000.0})
    elif warm == "product":
        item = BackgroundRenderItem()
        item._native_layer = layer
        while (unit := item._gui_warm_unit(transition_id)) is not None and len(units) < 64:
            builds, before, started = _BUILDS["count"], set(sys.modules), time.perf_counter()
            unit()
            units.append({"builds": _BUILDS["count"] - builds, "imported": sorted(set(sys.modules) - before),
                          "ms": (time.perf_counter() - started) * 1000.0})
    now = {"ns": run.start_ns}
    layer._clock_ns = lambda: now["ns"]
    builds, before = _BUILDS["count"], set(sys.modules)
    layer.transition(run)
    for step in range(1, 6):
        now["ns"] = run.start_ns + (run.end_ns - run.start_ns) * step // 6
        layer.tick()
    imported = sorted(set(sys.modules) - before)
    built = _BUILDS["count"] - builds
    drawn = layer.runs == 1 and layer.ticks == 5
    layer.close()
    del app
    print(json.dumps({"imported": imported, "built": built, "units": units, "drawn": drawn}))


if __name__ == "__main__":
    main()
