"""Child process for ``tests/test_studio_exit_vulkan.py`` (not collected: no ``test_`` prefix).

The Studio's own Quick window (the production ``StudioWindowSurface``, its QML shell and engine) open on Vulkan in a
process whose backend the native core started, kept off screen (a 64x64 transparent tool window at opacity 0, as
``tests/_quick_exit_route_probe.py`` keeps its display window). At its first presented frame a failing route's real
exit runs (``exit_application_after_quick_release``: no display window is alive while Settings is open, so it ends the
loop at once); the process then ends with a normal interpreter exit, so a Studio window still alive when the loop ends
shows as the process's end.

The controller is wired to the application's quit as ``ui/studio/settings_link.open_mode_studio`` wires it
(``aboutToQuit`` -> ``close_for_quit``). The toy mode is inspector-only (no viewport, so no OpenGL render node on a
Vulkan window) and the presence conceals nothing (no Settings window is ever shown).

usage: python tests/_studio_exit_probe.py <state_dir> <wired|unwired> <qt|core>

``unwired`` is the negative control: the quit edge is not connected, so the Studio window is alive when the loop ends.
``qt``: the window as the product makes it today (not handed to the native core; Qt Quick's own Vulkan device).
``core``: the window handed to the native core before its first show (``bootstrap.host_quick_window``), as a display
window is and as a Studio previewing a native renderer will be.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    import dataclasses

    import shiboken6
    from PySide6.QtCore import QObject, QSize, Qt, QTimer, Slot
    from PySide6.QtWidgets import QApplication

    from rendering.quick import bootstrap

    state_dir, variant, device = Path(sys.argv[1]), sys.argv[2], sys.argv[3]
    bootstrap.configure_quick_graphics(reason="studio-exit-probe", backend="vulkan", start_state_dir=state_dir)
    app = QApplication(sys.argv[:1])
    bootstrap.start_quick_backend()
    from engine.runtime_destruction import exit_application_after_quick_release
    from ui.studio.adapter import REFERENCE, StudioCapabilities, StudioFixture, StudioModeAdapter
    from ui.studio.controller import StudioController
    from ui.studio.schema import SCALAR, StudioProperty, StudioSchema, Workspace
    from ui.studio.surface import StudioWindowSurface

    @dataclasses.dataclass(frozen=True)
    class Frame:
        time: float

    class Evaluator:
        fixture = StudioFixture("still", "Still", REFERENCE, 4.0)

        def fixtures(self):
            return (self.fixture,)

        def select(self, _fixture_id):
            return self.fixture

        def evaluate(self, time, _values, *, exact=True, revision=None):
            return Frame(round(time, 6))

        def measurements(self):
            return {}

        def release(self):
            pass

    class InspectorOnlyToy(StudioModeAdapter):
        """An inspector-only mode: no viewport, so no OpenGL render node on a Vulkan window."""
        mode_id = "exit_probe"
        title = "Exit Probe"

        def capabilities(self):
            return StudioCapabilities(viewport=False, camera=False, handles=False)

        def schema(self):
            return StudioSchema("exit_probe", "Exit Probe", (Workspace("look", "Look", ("Gain",)),), (
                StudioProperty("gain", ("gain",), "Gain", "look", "Gain", SCALAR, 0., 2.),),
                lambda _key, candidate, _previous: max(0., min(2., float(candidate))))

        def scene_objects(self, _values):
            return ()

        def create_evaluator(self):
            return Evaluator()

        def create_renderer(self):
            raise AssertionError("an inspector-only Studio creates no renderer")

    class Store:
        values = {"gain": 1.0}

        def snapshot(self):
            return dict(self.values)

        def commit(self, values, _changed):
            self.values = dict(values)
            return dict(self.values)

        def preset_label(self):
            return "Custom"

    class Presence:
        concealed = False

        def conceal(self):
            self.concealed = True

        def reveal(self, **_kwargs):
            self.concealed = False

    class OffScreenStudioSurface(StudioWindowSurface):
        """The production surface; only where it shows differs (never visible)."""

        def show(self) -> None:
            window = self.window
            window.setOpacity(0.0)
            window.setMinimumSize(QSize(1, 1))
            window.setModality(Qt.WindowModality.NonModal)
            window.setFlag(Qt.WindowType.WindowTransparentForInput, True)
            window.setFlag(Qt.WindowType.Tool, True)
            bound = window.screen().geometry()
            window.setGeometry(bound.x() + 16, bound.y() + 16, 64, 64)
            if device == "core":
                bootstrap.host_quick_window(window)      # on the native core's device, as a display window is
            window.show()

    surfaces: list[StudioWindowSurface] = []

    def factory(controller):
        surfaces.append(OffScreenStudioSurface(controller))
        return surfaces[-1]

    controller = StudioController(InspectorOnlyToy(), Store(), Presence(), factory)
    if variant == "wired":
        app.aboutToQuit.connect(controller.close_for_quit)
    report: dict = {"variant": variant, "device": device}
    assert controller.open(), "the Studio did not open"
    window = surfaces[0].window

    class Presented(QObject):
        @Slot()
        def frame(self):
            if "api" in report:
                return               # a second queued frame of the same burst
            window.frameSwapped.disconnect(presented.frame)
            report["api"] = window.rendererInterface().graphicsApi().name
            report["hosts"] = len(bootstrap._owner.window_hosts)
            exit_application_after_quick_release(1, "studio_exit_probe")

    presented = Presented()
    window.frameSwapped.connect(presented.frame, Qt.ConnectionType.QueuedConnection)
    window.requestUpdate()
    QTimer.singleShot(15000, lambda: (report.__setitem__("timeout", True), app.exit(2)))
    report["exec_code"] = app.exec()
    report["studio_window_alive_at_loop_end"] = shiboken6.isValid(window)
    report["controller_state"] = controller.state
    report["hosts_left"] = len(bootstrap._owner.window_hosts)
    print("PROBE " + json.dumps(report), flush=True)
    return 0                 # a normal interpreter exit, never os._exit: the process's own end is what is tested


if __name__ == "__main__":
    sys.exit(main())
