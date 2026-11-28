"""Transition frames drawn by the native core, as the product draws them (switch point 2: the media tools).

``NativeTransitionCapture`` has the face the media tools used on ``TransitionCapture`` (``images``,
``production_run``, ``render(run, progress) -> (image, ms)``, ``close``), but the frame is the product's own: the
native background layer (``NativeBackgroundLayer``) in an item filling the process's hidden host
(``bootstrap.native_hidden_host``), its run's clock held at each progress by the capture, the frame read back at its
end. No window is shown and no timer is added; the hidden host is the process's one (kept, at one size).

The process needs the Quick graphics bootstrap before its application exists: the capture makes the application itself
when there is none (``configure_quick_graphics``, then ``QGuiApplication``), and refuses an application made without
it.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_HARNESS = ROOT / "native" / "core" / "python"

SCENE_QML = b"""import QtQuick
Rectangle {
    color: "#000000"
}
"""
#: Frames given at most for a run's fields to commit (its effect waits for them, as in the product).
FIELD_FRAMES = 600


def ensure_application():
    """The process's application, made with the Quick graphics bootstrap when there is none yet."""
    from rendering.quick.bootstrap import configure_quick_graphics

    from PySide6.QtCore import QCoreApplication
    from PySide6.QtGui import QGuiApplication

    app = QCoreApplication.instance()
    if app is None:
        configure_quick_graphics(reason="native-transition-capture")
        app = QGuiApplication([sys.argv[0] if sys.argv else "native-transition-capture"])
    elif not isinstance(app, QGuiApplication):
        raise RuntimeError("the native transition capture needs a QGuiApplication, not a QCoreApplication")
    return app


_EXIT_HOOK: list = []


def _close_host_at_exit() -> None:
    """The kept hidden host closed when the process exits. The owner closes it at the application's quit edge, but a
    tool (or a test process) that never runs an event loop never quits: its live render thread then held the
    interpreter's exit for good (measured: the showcase loop test passed, then its process never ended)."""
    if _EXIT_HOOK:
        return
    import atexit

    from rendering.quick import bootstrap

    _EXIT_HOOK.append(True)
    atexit.register(bootstrap._on_about_to_quit)


class _Clock:
    """The run's clock, held at one progress by the capture (the product's is ``time.monotonic_ns``)."""

    def __init__(self) -> None:
        self.now = 0

    def at(self, run, progress: float) -> None:
        self.now = run.start_ns + round(float(progress) * (run.end_ns - run.start_ns))

    def __call__(self) -> int:
        return self.now


class NativeTransitionCapture:
    def __init__(self, width: int, height: int, source=None, destination=None):
        from PySide6.QtCore import QUrl
        from PySide6.QtQml import QQmlComponent, QQmlEngine
        from PySide6.QtQuick import QQuickItem

        from rendering.quick import bootstrap
        from tools.transition_contact_sheet import fixture_images

        self.width, self.height = int(width), int(height)
        self.app = ensure_application()
        self.host = bootstrap.native_hidden_host(self.width, self.height)
        self.core = bootstrap.native_core()
        _close_host_at_exit()
        fixtures = fixture_images(self.width, self.height)
        self.images = tuple(image.convert("RGBA").resize((self.width, self.height)) for image in
                            (source or fixtures[0], destination or fixtures[1]))
        self._engine = QQmlEngine()
        self._component = QQmlComponent(self._engine)
        self._component.setData(SCENE_QML, QUrl())
        self._root = self._component.create()
        if self._root is None:
            raise RuntimeError(f"the capture's scene did not load: {self._component.errorString()}")
        self.host.set_content(self._root)
        self._item = QQuickItem(self._root)
        self._item.setWidth(self.width)
        self._item.setHeight(self.height)
        from rendering.quick.render.native_background import NativeBackgroundLayer

        self._clock = _Clock()
        self.layer = NativeBackgroundLayer(self.core, self._item, self._clock)
        self._run = None
        self._closed = False

    # ------------------------------------------------------------------------------------------------- the run

    def production_run(self, identity: str, duration_ms: int | None = None, settings=None, seed: int = 713,
                       run_id: int = 1, *, detail: str | None = "High", timeline_ms: int | None = None,
                       label: str = "release_capture"):
        """A run resolved exactly as the runtime resolves it (``production_transition_spec``); its timeline is the
        resolved duration, or ``timeline_ms`` when given (the onboarding previews sample a 1000 ms timeline)."""
        from rendering.quick.transitions.state import TransitionRequest, TransitionRun
        from tools.transition_contact_sheet import production_transition_spec

        spec = production_transition_spec(identity, duration_ms, settings, seed, detail)
        images = self._presentation_images(label)
        if timeline_ms is None:
            request = spec.build_request(runtime_generation=0, source_image=images[0], destination_image=images[1])
        else:
            request = TransitionRequest(0, spec.transition_id, spec.requested_name, spec.selected_from_random,
                                        int(timeline_ms), spec.direction, spec.parameters, *images)
        return TransitionRun.start(run_id=run_id, request=request, start_ns=0)

    def _presentation_images(self, label: str):
        from rendering.quick.image_state import PresentationImage

        return [PresentationImage(f"{label}:{index}", label, (self.width, self.height), 1.,
                                  (self.width, self.height), self.width * 4, image.tobytes())
                for index, image in enumerate(self.images)]

    # --------------------------------------------------------------------------------------------- the frames

    def _frames(self, count: int = 1) -> None:
        from PySide6.QtCore import QCoreApplication

        for _ in range(count):
            QCoreApplication.processEvents()
            self.host.frames(1)

    def _settle(self) -> None:
        """The photo committed and the layer's first fade-in run to its end (a harness's wait, never the product's)."""
        from PySide6.QtCore import QCoreApplication, QEventLoop

        self._frames(1)
        if not self.core.wait_jobs_idle(20000):
            raise RuntimeError("the native upload jobs did not finish within 20 s")
        self._frames(2)
        deadline = time.monotonic() + 10.0
        mode = self.layer.mode
        while mode is not None and time.monotonic() < deadline and mode.composite.state().get("fading"):
            QCoreApplication.processEvents(QEventLoop.ProcessEventsFlag.AllEvents, 16)
        self._frames(2)

    def _start(self, run) -> None:
        if self._run is not None:
            self.layer.transition(None)
            self._run = None
        self.layer.present(run.request.source_image)
        self._settle()
        self._clock.at(run, 0.0)
        self.layer.transition(run)
        self._frames(1)
        self._settle()
        for _ in range(FIELD_FRAMES):                   # a fragment run's fields commit before its effect starts
            if not self.layer._fields_pending:
                break
            self._frames(1)
        if self.layer._fields_pending:
            raise RuntimeError(f"{run.request.transition_id}: the run's fields did not commit")
        self.layer._clock_offset_ns = 0                 # the capture holds the run's clock itself
        self._frames(2)
        self._run = run

    def render(self, run, progress: float):
        """The product's frame of ``run`` at ``progress``: (an RGBA image, milliseconds to draw and read it)."""
        from PIL import Image
        from PySide6.QtCore import QCoreApplication

        if str(_HARNESS) not in sys.path:
            sys.path.insert(0, str(_HARNESS))
        from composite_analysis import frame_rows

        if self._closed:
            raise RuntimeError("the capture is closed")
        if self._run is None or self._run.run_id != run.run_id or self._run is not run:
            self._start(run)
        started = time.perf_counter()
        self._clock.at(run, progress)
        self.layer.tick()
        self._frames(1)
        QCoreApplication.processEvents()
        frame = self.host.read()
        rows = frame_rows({"rgba": frame.rgba, "width": frame.width, "height": frame.height,
                           "y_up_in_framebuffer": frame.y_up_in_framebuffer})
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        if self.layer._failure:
            raise RuntimeError(f"{run.request.transition_id}: the native layer failed: {self.layer._failure}")
        return Image.fromarray(rows, "RGBA"), elapsed_ms

    def close(self) -> None:
        """The layer and its scene gone; the hidden host is the process's and stays (closed at the quit)."""
        import shiboken6
        from PySide6.QtCore import QCoreApplication, QEvent

        if self._closed:
            return
        self._closed = True
        try:
            if self._run is not None:
                self.layer.transition(None)
            self.layer.close()
        finally:
            self._run = None
            self.host.set_content(None)
            if self._root is not None and shiboken6.isValid(self._root):
                self._root.setParentItem(None)
                shiboken6.delete(self._root)
            self._root = None
            QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
            self.app.processEvents()
