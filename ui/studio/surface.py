"""Studio surfaces: the visible top-level window and a hidden render-control host.

Both build the same QML shell (``qml/StudioShell.qml``) around the same viewport
item, and expose the same small signal contract to the controller:

* ``frameStarted``  - a Quick frame is starting (GUI thread); the controller evaluates.
* ``presented``     - the shell's first frame reached the screen/target.
* ``closeRequested``- the user closed the window (close button, Alt+F4, system menu).
* ``lost``          - the window was destroyed without a controller close.
* ``failed(str)``   - the scene graph reported an error.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from PySide6.QtCore import QObject, QRect, QSize, Qt, QUrl, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlComponent, QQmlEngine
from PySide6.QtQuick import QQuickItem, QQuickWindow

from core.logging.logger import get_logger
from ui.studio.viewport import StudioViewportItem

logger = get_logger(__name__)

QML_DIR = Path(__file__).resolve().parent / "qml"
# Wrappers of windows/engines awaiting deferred deletion. Python must not drop the last
# reference first (that would delete the native object synchronously from Python).
_RETIRING: set[QObject] = set()


def _keep_until_destroyed(obj: QObject) -> None:
    _RETIRING.add(obj)
    obj.destroyed.connect(lambda *_args, o=obj: _RETIRING.discard(o))


class StudioShellHost:
    """QML engine + shell root + viewport inside one QQuickWindow."""

    def __init__(self, window: QQuickWindow, bridge: QObject, renderer_factory: Callable[[], Any]) -> None:
        from ui.studio.chrome import register_chrome_types
        register_chrome_types()
        self.window = window
        self.engine = QQmlEngine()
        self.engine.addImportPath(str(QML_DIR))
        self.engine.rootContext().setContextProperty("studio", bridge)
        component = QQmlComponent(self.engine, QUrl.fromLocalFile(str(QML_DIR / "StudioShell.qml")))
        if component.status() != QQmlComponent.Status.Ready:
            errors = "; ".join(error.toString() for error in component.errors())
            raise RuntimeError(f"StudioShell.qml failed to load: {errors}")
        root = component.create(self.engine.rootContext())
        if not isinstance(root, QQuickItem):
            errors = "; ".join(error.toString() for error in component.errors())
            raise RuntimeError(f"StudioShell.qml did not create a Quick item: {errors}")
        self._component = component
        content = window.contentItem()
        root.setParent(content)
        root.setParentItem(content)
        self.root = root
        # Follow the window, not its content item: an unshown render-control window never resizes the latter.
        self._fit = lambda *_args: (root.setWidth(window.width()), root.setHeight(window.height()))
        window.widthChanged.connect(self._fit)
        window.heightChanged.connect(self._fit)
        self._fit()
        slot = root.findChild(QQuickItem, "viewportSlot")
        if slot is None:
            raise RuntimeError("StudioShell.qml has no viewportSlot")
        viewport = StudioViewportItem(renderer_factory, slot)
        viewport.setZ(-1.0)       # QML status/overlay children of the slot draw above the scene
        def fit_viewport(*_args) -> None:
            # Letterbox the presented world extent (the live card's aspect) inside the slot.
            import shiboken6
            if not (shiboken6.isValid(slot) and shiboken6.isValid(viewport)):
                return                      # teardown: the slot's size signals outlive its items
            width, height = slot.width(), slot.height()
            extent = viewport.fit_slot(width, height)
            if extent is not None and width > 0 and height > 0:
                scale = min(width / extent[0], height / extent[1])
                w, h = extent[0] * scale, extent[1] * scale
                viewport.setX((width - w) / 2.0)
                viewport.setY((height - h) / 2.0)
                width, height = w, h
            else:
                viewport.setX(0.0)
                viewport.setY(0.0)
            viewport.setWidth(width)
            viewport.setHeight(height)
            slot.setProperty("frameX", viewport.x())
            slot.setProperty("frameY", viewport.y())
            slot.setProperty("frameWidth", width)
            slot.setProperty("frameHeight", height)

        self._fit_viewport = fit_viewport
        slot.widthChanged.connect(self._fit_viewport)
        slot.heightChanged.connect(self._fit_viewport)
        viewport.extentChanged.connect(self._fit_viewport)
        self._fit_viewport()
        self.viewport = viewport
        self.slot = slot

    def retire(self) -> None:
        """Stop presenting frames. Call ``release_engine`` after the window's deferred deletion is queued."""
        self.viewport.detach()

    def release_engine(self) -> None:
        _keep_until_destroyed(self.engine)
        self.engine.deleteLater()


class _StudioQuickWindow(QQuickWindow):
    closeRequested = Signal()

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt override
        event.accept()
        self.closeRequested.emit()


def material_mode(theme) -> str:
    """The Settings theme's native backdrop mode the Studio window carries: ``off`` (Normal) or its material."""
    from ui.settings_theme_spec import NATIVE_BACKDROP_MODES
    mode = str(getattr(getattr(theme, "backdrop", None), "mode", "off"))
    return mode if mode in NATIVE_BACKDROP_MODES else "off"


def initial_geometry(anchor: QRect | None) -> QRect:
    """Inherit the originating window's screen and centre; desktop-sized within its screen."""
    screen = None
    if anchor is not None and anchor.isValid():
        screen = QGuiApplication.screenAt(anchor.center())
    screen = screen or QGuiApplication.primaryScreen()
    available = screen.availableGeometry()
    width = min(int(available.width() * 0.9), max(1280, anchor.width() if anchor is not None else 0, 1500))
    height = min(int(available.height() * 0.9), max(800, int(width * 0.58)))
    centre = anchor.center() if anchor is not None and anchor.isValid() else available.center()
    rect = QRect(0, 0, width, height)
    rect.moveCenter(centre)
    rect.moveLeft(max(available.left(), min(rect.left(), available.right() - width)))
    rect.moveTop(max(available.top(), min(rect.top(), available.bottom() - height)))
    return rect


class StudioWindowSurface(QObject):
    """The real, visible Studio window (production)."""

    frameStarted = Signal()
    presented = Signal()
    closeRequested = Signal()
    lost = Signal()
    failed = Signal(str)

    def __init__(self, controller, *, anchor: QRect | None = None, theme=None) -> None:
        super().__init__()
        window = _StudioQuickWindow()
        window.setTitle(controller.adapter.title or "Studio")
        # Settings' chrome: frameless, with the shell's custom title bar and forged rounded edge. Under a Glass or
        # Acrylic Settings theme the window carries the same native material as Settings (an alpha surface the
        # theme's translucent roles let it through); Normal stays an opaque window with no backdrop at all.
        from ui.settings_theme_runtime import get_active_settings_theme
        self.theme = theme or get_active_settings_theme()
        self.material = material_mode(self.theme)
        window.setFlags(Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint)
        # A live Settings notification can enable a material later on this same
        # native window. Reserve alpha before creation; Normal still paints opaque.
        surface_format = window.requestedFormat()
        surface_format.setAlphaBufferSize(8)
        window.setFormat(surface_format)
        if self.material != "off":
            window.setColor(Qt.GlobalColor.transparent)
        else:
            window.setColor(Qt.GlobalColor.black)
        self.backdrop_applied = False
        self._applied_backdrop_request = None
        self.maximized = False
        self._normal_geometry: QRect | None = None
        # Settings may be in a modal exec(); the Studio must not be blocked by it, and it is the sole
        # authoring surface while open.
        window.setModality(Qt.WindowModality.ApplicationModal)
        window.setMinimumSize(QSize(960, 600))
        # Closing must not stall the Settings window it returns to: with non-persistent graphics the
        # scene graph, the Studio's GL resources and its context are released inside hide(), i.e.
        # before Settings is revealed, instead of in a later deferred window destruction that would
        # block the Settings event loop right after it reappears.
        window.setPersistentSceneGraph(False)
        window.setPersistentGraphics(False)
        self.window = window
        self._anchor = anchor
        self._presented = False
        self._retired = False
        self.host = StudioShellHost(window, controller.bridge, controller.adapter.create_renderer)
        self.viewport = self.host.viewport
        window.afterAnimating.connect(self.frameStarted.emit)
        window.frameSwapped.connect(self._on_swapped, Qt.ConnectionType.QueuedConnection)
        window.closeRequested.connect(self.closeRequested.emit)
        window.sceneGraphError.connect(self._on_scene_graph_error)
        window.destroyed.connect(self._on_destroyed)

    def show(self) -> None:
        self.window.setGeometry(initial_geometry(self._anchor))
        self.window.show()
        self.apply_backdrop()
        self.window.requestActivate()

    def apply_backdrop(self) -> bool:
        """Apply a changed semantic material request through the existing native owner."""
        request = self.theme.native_backdrop_request()
        if request == self._applied_backdrop_request:
            return self.backdrop_applied
        if self.material == "off" and self._applied_backdrop_request is None:
            return False
        from core import platform_paths
        if not platform_paths.IS_WINDOWS:
            return False
        try:
            from core.windows.dwm_blur import apply_backdrop
            applied = bool(apply_backdrop(int(self.window.winId()), *request))
            # apply_backdrop reports whether a material is ON; a completed Off
            # request deliberately returns False after disabling AccentPolicy.
            if applied or self.material == "off":
                self._applied_backdrop_request = request
            self.backdrop_applied = applied and self.material != "off"
        except Exception:
            logger.debug("[STUDIO] Native backdrop not available", exc_info=True)
        return self.backdrop_applied

    def apply_settings_theme(self, theme) -> None:
        """Reconcile chrome and native tint at the existing theme notification edge."""
        self.theme = theme
        self.material = material_mode(theme)
        self.window.setColor(Qt.GlobalColor.transparent if self.material != "off" else Qt.GlobalColor.black)
        if self.window.isVisible() or self._applied_backdrop_request is not None:
            self.apply_backdrop()

    # Window chrome (the shell's title bar and edges) ---------------------------------
    def start_move(self) -> None:
        """Title bar drag: the system move (Windows snap and Aero snap). From maximised, restore under the pointer
        first, as Settings does."""
        if self.maximized:
            from PySide6.QtGui import QCursor
            cursor = QCursor.pos()
            ratio = 0.5
            if self.window.width() > 0:
                ratio = max(0.05, min(0.95, (cursor.x() - self.window.x()) / self.window.width()))
            self.toggle_maximize()
            self.window.setPosition(int(cursor.x() - self.window.width() * ratio), int(cursor.y() - 20))
        self.window.startSystemMove()

    def start_resize(self, edges: int) -> None:
        if not self.maximized:
            self.window.startSystemResize(Qt.Edge(int(edges)))

    def toggle_maximize(self) -> None:
        """Maximise to the screen's work area, or restore (manual, as Settings: a frameless window)."""
        if self.maximized:
            self.maximized = False
            if self._normal_geometry is not None:
                self.window.setGeometry(self._normal_geometry)
            return
        self._normal_geometry = self.window.geometry()
        screen = self.window.screen() or QGuiApplication.primaryScreen()
        self.maximized = True
        self.window.setGeometry(screen.availableGeometry())

    def minimize(self) -> None:
        self.window.showMinimized()

    def raise_(self) -> None:
        self.window.raise_()
        self.window.requestActivate()

    def covering_window(self):
        """The Studio's top-level window while it is on screen, else None. At an exit Settings is revealed beneath it
        and comes forward once it is gone (``WindowPresence.reveal``)."""
        window = self.window
        return window if not self._retired and window.isVisible() else None

    def request_frame(self) -> None:
        if not self._retired:
            self.window.update()

    def _on_swapped(self) -> None:
        if self._presented or self._retired:
            return
        self._presented = True
        self.presented.emit()

    def _on_scene_graph_error(self, _error, message: str) -> None:
        if not self._retired:
            self.failed.emit(f"Scene graph error: {message}")

    def _on_destroyed(self, *_args) -> None:
        if not self._retired:
            self._retired = True
            self.lost.emit()

    def retire(self) -> None:
        """Hide, then destroy: Quick invalidates the scene graph on its render thread (GL released there)."""
        if self._retired:
            return
        self._retired = True
        window = self.window
        for signal, slot in ((window.afterAnimating, self.frameStarted.emit),
                             (window.closeRequested, self.closeRequested.emit),
                             (window.destroyed, self._on_destroyed)):
            try:
                signal.disconnect(slot)
            except (RuntimeError, TypeError):
                pass
        import time
        from PySide6.QtCore import QMetaObject
        self.host.retire()
        # Never ``window.hide()`` from Python: PySide holds the GIL through that call, and Qt's threaded
        # render loop waits inside it for the render thread, which must run this viewport's Python (the render
        # node's release, ``sceneGraphInvalidated``) to invalidate the scene graph: a deadlock that froze the
        # app with Settings still concealed. The event loop runs the hide and the destruction in C++ with the
        # GIL released (Settings is already revealed by then).
        QMetaObject.invokeMethod(window, "hide", Qt.ConnectionType.QueuedConnection)
        self.hide_deferred = True
        _keep_until_destroyed(window)
        window.destroyed.connect(lambda *_a, t=time.perf_counter(): logger.info(
            "[STUDIO] window destroyed %.1f ms after retirement", (time.perf_counter() - t) * 1000.0))
        window.deleteLater()
        self.host.release_engine()
        logger.info("[STUDIO] window hide and destruction queued to the event loop")


class OffscreenStudioSurface(QObject):
    """The same shell rendered by QQuickRenderControl into a hidden GL texture.

    Used by tests and evidence capture: nothing is ever shown. Frames render only
    when :meth:`pump` is called.
    """

    frameStarted = Signal()
    presented = Signal()
    closeRequested = Signal()
    lost = Signal()
    failed = Signal(str)

    def __init__(self, controller, *, size: tuple[int, int] = (1600, 900), dpr: float = 1.0,
                 present_on_show: bool = True, transparent: bool = False) -> None:
        super().__init__()
        from OpenGL import GL as gl
        from PySide6.QtGui import QOffscreenSurface, QOpenGLContext, QSurfaceFormat
        from PySide6.QtQuick import QQuickGraphicsDevice, QQuickRenderControl, QQuickRenderTarget
        self._gl = gl
        self.size = size
        self.dpr = float(dpr)
        self.pixel_size = (round(size[0] * self.dpr), round(size[1] * self.dpr))
        self.context = QOpenGLContext()
        self.context.setFormat(QSurfaceFormat.defaultFormat())
        if not self.context.create():
            raise RuntimeError("Studio offscreen GL context is unavailable")
        self.surface = QOffscreenSurface()
        self.surface.setFormat(self.context.format())
        self.surface.create()
        self.control = QQuickRenderControl()
        # The render control's RHI imports this context and uses it until the control's own destructor (Qt requires
        # the imported context to outlive the render control). Owning the context and its surface as the control's
        # Qt children makes that order structural: whatever destroys the control (``retire``, a garbage-collected
        # surface whose retirement failed, PySide's exit sweep of Python-owned QObjects, which runs in hash order)
        # destroys them after it, never before. Two independent Python owners let the sweep free the context first,
        # and the control's teardown then used it: an intermittent access violation at interpreter exit.
        self.context.setParent(self.control)
        self.surface.setParent(self.control)
        self.window = QQuickWindow(self.control)
        self.window.resize(*size)
        # ``transparent``: clear to nothing, as the visible window does under a Glass/Acrylic theme, so a grab keeps
        # the chrome's alpha (evidence of what the native material shows through). Otherwise over black.
        self.window.setColor(Qt.GlobalColor.transparent if transparent else Qt.GlobalColor.black)
        self.window.setGraphicsDevice(QQuickGraphicsDevice.fromOpenGLContext(self.context))
        if not self.control.initialize():
            raise RuntimeError("Studio offscreen render control did not initialize")
        self._make_current()
        self.texture = int(gl.glGenTextures(1))
        gl.glBindTexture(gl.GL_TEXTURE_2D, self.texture)
        gl.glTexImage2D(gl.GL_TEXTURE_2D, 0, gl.GL_RGBA8, *self.pixel_size, 0, gl.GL_RGBA,
                        gl.GL_UNSIGNED_BYTE, None)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MIN_FILTER, gl.GL_LINEAR)
        target = QQuickRenderTarget.fromOpenGLTexture(self.texture, QSize(*self.pixel_size))
        target.setDevicePixelRatio(self.dpr)
        self.window.setRenderTarget(target)
        self.host = StudioShellHost(self.window, controller.bridge, controller.adapter.create_renderer)
        self.viewport = self.host.viewport
        self._presented = False
        self._retired = False
        self._present_on_show = present_on_show
        self.frame_requests = 0
        self.frames_rendered = 0

    def _make_current(self) -> None:
        if not self.context.makeCurrent(self.surface):
            raise RuntimeError("Studio offscreen GL context could not be made current")

    def show(self) -> None:
        if self._present_on_show:
            self.pump()

    def raise_(self) -> None:
        return None

    def covering_window(self):
        """Nothing of this surface is ever on screen."""
        return None

    @property
    def retired(self) -> bool:
        return self._retired

    def request_frame(self) -> None:
        if not self._retired:
            self.frame_requests += 1

    def pump(self, frames: int = 1) -> None:
        app = QGuiApplication.instance()
        for _ in range(frames):
            if self._retired:
                return
            app.processEvents()
            self.frame_requests = 0
            self.frameStarted.emit()
            self._make_current()
            self.control.polishItems()
            self.control.beginFrame()
            self.control.sync()
            self.control.render()
            self.control.endFrame()
            self.frames_rendered += 1
            app.processEvents()
            if not self._presented:
                self._presented = True
                self.presented.emit()

    def grab(self):
        """The current frame as a top-down RGBA numpy array."""
        import numpy
        gl = self._gl
        self._make_current()
        gl.glBindTexture(gl.GL_TEXTURE_2D, self.texture)
        data = gl.glGetTexImage(gl.GL_TEXTURE_2D, 0, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE)
        width, height = self.pixel_size
        return numpy.flipud(numpy.frombuffer(bytes(data), dtype=numpy.uint8).reshape(height, width, 4)).copy()

    def retire(self) -> None:
        if self._retired:
            return
        self._retired = True
        from PySide6.QtCore import QCoreApplication, QEvent
        self._make_current()
        self.control.invalidate()        # sceneGraphInvalidated: render-node GL released in this context
        self.host.retire()
        self._gl.glDeleteTextures([self.texture])
        # Destroy the Quick window, render control and engine NOW, while their GL context and offscreen
        # surface still exist. Left to deleteLater they would outlive this surface (nothing runs an
        # event loop in hidden captures/tests) and be destroyed at interpreter exit against a dead context.
        # The render control goes last: its children, the context and the offscreen surface, go with it.
        engine = self.host.engine
        for obj in (self.window, engine, self.control):
            _keep_until_destroyed(obj)
            obj.deleteLater()
        for obj in (self.window, engine, self.control):
            QCoreApplication.sendPostedEvents(obj, QEvent.Type.DeferredDelete)


__all__ = ["OffscreenStudioSurface", "StudioShellHost", "StudioWindowSurface", "initial_geometry", "material_mode"]
