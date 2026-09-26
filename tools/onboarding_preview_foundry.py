"""Build deterministic Guided Setup preview assets without showing a window.

Every widget preview is the family's production retained presenter, built from
the canonical defaults with its card enabled and fed deterministic fixture
state.  The scene renders through ``QQuickRenderControl`` into a hidden OpenGL
texture (Windows QPA, ``QOffscreenSurface``, operator-approved 2026-09-26): no
``QQuickWindow`` is ever shown, and nothing reaches the desktop.  The Qt
offscreen QPA cannot create OpenGL contexts, so it would silently drop every
effect layer (header logos, card shadows); it is therefore not used here.
Transitions are read back from ``TransitionCapture``'s hidden GL surface.

Run with ``python tools/onboarding_preview_foundry.py``.  This is a release
authoring tool; Guided Setup only reads the committed PNGs and never runs it.
"""
from __future__ import annotations

import argparse
import builtins
import copy
import importlib.abc
import importlib.machinery
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from typing import Any, Callable, Final


ROOT: Final = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT: Final = ROOT / "images" / "onboarding"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Previews are transparent around the card, with the card's real shadow left
# hanging off it, so they sit naturally on any Settings theme.
_SHADOW_MARGIN: Final = 36
_SHADOW_KEEP: Final = 30
# PNG only (Qt's built-in codec; WebP/JPEG plugins are unproven in the frozen
# builds).  Seventeen photographic transition triptychs dominate the total.
_ASSET_BUDGET_BYTES: Final = 10 * 1024 * 1024
_SCENE_SIZE: Final = (1400, 1000)
_WIDGET_ORIGIN: Final = (60.0, 60.0)

# Transition samples.  Most effects read best at the quarter points; an effect
# whose midpoint is a degenerate frame (a spin edge-on) samples just off it.
_DEFAULT_TRANSITION_SAMPLES: Final = (0.25, 0.50, 0.75)
_TRANSITION_SAMPLES: Final = {
    "block_spins": (0.38, 0.46, 0.58),
}

_CREDENTIAL_FILENAMES: Final = frozenset({
    "client_secrets.json",
    "credentials.bin",
    "gmail_credentials.json",
    "gmail_imap_creds.enc",
    "gmail_token.enc",
})

_BLOCKED_CREDENTIAL_MODULES: Final = frozenset({
    "core.gmail.gmail_backend",
    "core.gmail.gmail_bootstrap",
    "core.gmail.gmail_oauth",
    "keyring",
    "win32cred",
})

_GUARDED_CREDENTIAL_APIS: Final = {
    "core.windows.dpapi": ("decrypt_user_data", "load_encrypted"),
    # Friend Pulse imports this module for non-secret hashing/redaction
    # definitions.  Keep those available while making the secret load entry
    # point fail closed.
    "core.steam.credentials": ("load_credentials",),
}


def _append_guard_attempt(audit_log: Path, category: str, operation: str) -> None:
    """Persist one privacy violation without recording arguments or secrets."""

    audit_log.parent.mkdir(parents=True, exist_ok=True)
    with io.open(audit_log, "a", encoding="utf-8") as handle:
        handle.write(json.dumps({"category": category, "operation": operation}) + "\n")


class _GuardedCredentialLoader(importlib.abc.Loader):
    def __init__(self, loader: importlib.abc.Loader, fullname: str, audit_log: Path) -> None:
        self._loader = loader
        self._fullname = fullname
        self._audit_log = audit_log

    def create_module(self, spec):
        create = getattr(self._loader, "create_module", None)
        return create(spec) if callable(create) else None

    def exec_module(self, module) -> None:
        self._loader.exec_module(module)
        _patch_guarded_credential_apis(module, self._fullname, self._audit_log)


class _CredentialImportGuard(importlib.abc.MetaPathFinder):
    def __init__(self, audit_log: Path) -> None:
        self._audit_log = audit_log

    def find_spec(self, fullname: str, path=None, target=None):
        blocked = next(
            (name for name in _BLOCKED_CREDENTIAL_MODULES
             if fullname == name or fullname.startswith(name + ".")),
            None,
        )
        if blocked is not None:
            _append_guard_attempt(self._audit_log, "credential", f"import:{fullname}")
            raise RuntimeError("onboarding preview foundry forbids credential-owner imports")
        if fullname not in _GUARDED_CREDENTIAL_APIS:
            return None
        spec = importlib.machinery.PathFinder.find_spec(fullname, path)
        if spec is None or spec.loader is None:
            return spec
        spec.loader = _GuardedCredentialLoader(spec.loader, fullname, self._audit_log)
        return spec


def _patch_guarded_credential_apis(module: object, fullname: str, audit_log: Path) -> None:
    for name in _GUARDED_CREDENTIAL_APIS.get(fullname, ()):
        if not hasattr(module, name):
            continue

        def blocked(*_args: object, _operation=f"{fullname}.{name}", **_kwargs: object):
            _append_guard_attempt(audit_log, "credential", _operation)
            raise RuntimeError("onboarding preview foundry forbids credential access")

        setattr(module, name, blocked)


def _install_authoring_guards(audit_log: Path) -> None:
    """Install process-wide network and credential-read tripwires.

    Every tripwire records before raising.  The parent checks the durable audit
    file after a worker exits, so a dependency cannot make the authoring run
    look successful by catching the exception.
    """

    audit_log = audit_log.resolve()

    def deny_network(operation: str):
        def blocked(*_args: object, **_kwargs: object):
            _append_guard_attempt(audit_log, "network", operation)
            raise RuntimeError("onboarding preview foundry forbids network access")
        return blocked

    socket.create_connection = deny_network("socket.create_connection")  # type: ignore[assignment]
    for name in (
        "connect", "connect_ex", "send", "sendall", "sendto",
    ):
        setattr(socket.socket, name, deny_network(f"socket.socket.{name}"))
    for name in (
        "getaddrinfo", "gethostbyaddr", "gethostbyname", "gethostbyname_ex",
    ):
        setattr(socket, name, deny_network(f"socket.{name}"))

    original_builtin_open = builtins.open
    original_io_open = io.open
    original_os_open = os.open

    def credential_name(value: object) -> str | None:
        if isinstance(value, int):
            return None
        try:
            name = Path(os.fspath(value)).name.lower()
        except (TypeError, ValueError):
            return None
        return name if name in _CREDENTIAL_FILENAMES else None

    def guarded_builtin_open(file, *args, **kwargs):
        name = credential_name(file)
        if name is not None:
            _append_guard_attempt(audit_log, "credential", f"open:{name}")
            raise RuntimeError("onboarding preview foundry forbids credential access")
        return original_builtin_open(file, *args, **kwargs)

    def guarded_io_open(file, *args, **kwargs):
        name = credential_name(file)
        if name is not None:
            _append_guard_attempt(audit_log, "credential", f"io.open:{name}")
            raise RuntimeError("onboarding preview foundry forbids credential access")
        return original_io_open(file, *args, **kwargs)

    def guarded_os_open(path, *args, **kwargs):
        name = credential_name(path)
        if name is not None:
            _append_guard_attempt(audit_log, "credential", f"os.open:{name}")
            raise RuntimeError("onboarding preview foundry forbids credential access")
        return original_os_open(path, *args, **kwargs)

    builtins.open = guarded_builtin_open
    io.open = guarded_io_open
    os.open = guarded_os_open

    sys.meta_path.insert(0, _CredentialImportGuard(audit_log))
    # Tests or embedding callers may have imported the safe definition modules
    # before installing the foundry boundary.  Patch those existing objects
    # without importing any credential owner ourselves.
    for fullname in _GUARDED_CREDENTIAL_APIS:
        module = sys.modules.get(fullname)
        if module is not None:
            _patch_guarded_credential_apis(module, fullname, audit_log)

def _hidden_gl_environment() -> dict[str, str]:
    """Return a clean Windows-QPA environment for hidden offscreen GL."""

    environment = dict(os.environ)
    environment.pop("QT_QPA_PLATFORM", None)
    environment.pop("QSG_RHI_BACKEND", None)
    environment.setdefault("QT_QPA_FONTDIR", "C:/Windows/Fonts")
    return environment


# --------------------------------------------------------------------------- #
# Hidden Quick scene                                                          #
# --------------------------------------------------------------------------- #


class _HiddenQuickScene:
    """The production DisplayScene rendered into a hidden GL texture.

    ``QQuickRenderControl`` owns the render loop, so the ``QQuickWindow`` is a
    scene container that is never shown or mapped.  Rendering happens only when
    :meth:`render` is called.
    """

    def __init__(self, width: int, height: int) -> None:
        from OpenGL import GL as gl
        from PySide6.QtCore import QObject, QSize
        from PySide6.QtGui import QGuiApplication, QOffscreenSurface, QOpenGLContext
        from PySide6.QtQuick import (QQuickGraphicsDevice, QQuickItem, QQuickRenderControl,
            QQuickRenderTarget, QQuickWindow)
        from rendering.quick.scene_controller import QuickSceneFactory
        from rendering.quick.widgets.host import OrdinaryWidgetPresentationHost

        self.app = QGuiApplication.instance()
        if self.app is None or self.app.platformName().strip().lower() != "windows":
            raise RuntimeError("preview capture requires the hidden Windows-QPA GL worker")
        self._gl = gl
        self.width, self.height = width, height
        self.context = QOpenGLContext()
        if not self.context.create():
            raise RuntimeError("hidden preview GL context is unavailable")
        self.surface = QOffscreenSurface()
        self.surface.setFormat(self.context.format())
        self.surface.create()
        self.control = QQuickRenderControl()
        self.window = QQuickWindow(self.control)
        self.window.resize(width, height)
        self.window.setColor("transparent")
        self.window.setGraphicsDevice(QQuickGraphicsDevice.fromOpenGLContext(self.context))
        if not self.control.initialize():
            raise RuntimeError("hidden preview render control did not initialize")
        self._make_current()
        self.texture = int(gl.glGenTextures(1))
        gl.glBindTexture(gl.GL_TEXTURE_2D, self.texture)
        gl.glTexImage2D(gl.GL_TEXTURE_2D, 0, gl.GL_RGBA8, width, height, 0,
                        gl.GL_RGBA, gl.GL_UNSIGNED_BYTE, None)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MIN_FILTER, gl.GL_LINEAR)
        self.window.setRenderTarget(QQuickRenderTarget.fromOpenGLTexture(self.texture, QSize(width, height)))

        self.owner = QObject()
        self.factory = QuickSceneFactory(self.owner)
        self.qml_context, self.root = self.factory.create_display_root(
            owner=self.owner, screen_index=0, runtime_generation=1)
        self.root.setParent(self.window.contentItem())
        self.root.setParentItem(self.window.contentItem())
        self.root.setWidth(width)
        self.root.setHeight(height)

        def item(name: str) -> QQuickItem:
            found = self.root.findChild(QQuickItem, name)
            if found is None:
                raise RuntimeError(f"preview scene is missing {name}")
            return found

        self.find = item
        self.host = OrdinaryWidgetPresentationHost(
            host_item=item("ordinaryWidgetHost"), shadow_host_item=item("ordinaryWidgetShadowHost"),
            foreground_host_item=item("systemAudioOSDForegroundHost"),
            foreground_shadow_host_item=item("systemAudioOSDShadowHost"), context=self.qml_context,
            create_overlay_item=self.factory.create_overlay_widget,
            create_shadow_item=self.factory.create_overlay_card_shadow,
            create_family_item=self.factory.create_ordinary_widget_family,
        )

    def _make_current(self) -> None:
        if not self.context.makeCurrent(self.surface):
            raise RuntimeError("hidden preview GL context could not be made current")

    def render(self) -> None:
        self.app.processEvents()
        self.control.polishItems()
        self.control.beginFrame()
        self.control.sync()
        self.control.render()
        self.control.endFrame()

    def settle(self, *, minimum_ms: int, until: Callable[[], bool], timeout_ms: int = 8000) -> None:
        """Render until ``until`` holds and the minimum settle time has passed."""

        from PySide6.QtCore import QElapsedTimer

        elapsed = QElapsedTimer()
        elapsed.start()
        while True:
            self.render()
            if elapsed.elapsed() >= minimum_ms and until():
                return
            if elapsed.elapsed() > timeout_ms:
                raise RuntimeError("preview scene did not settle before its deadline")

    def read(self):
        """Return the rendered frame as a straight-alpha top-down PIL image."""

        import numpy
        from PIL import Image

        gl = self._gl
        self._make_current()
        gl.glBindTexture(gl.GL_TEXTURE_2D, self.texture)
        data = gl.glGetTexImage(gl.GL_TEXTURE_2D, 0, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE)
        pixels = numpy.frombuffer(bytes(data), dtype=numpy.uint8).reshape(self.height, self.width, 4)
        return _straight_alpha(numpy.flipud(pixels))

    def close(self) -> None:
        self.host.retire_all()
        self.root.setParentItem(None)
        self.root.deleteLater()
        self.qml_context.deleteLater()
        self.app.processEvents()
        self._make_current()
        self._gl.glDeleteTextures([self.texture])
        self.control.invalidate()
        self.window.deleteLater()
        self.control.deleteLater()
        self.owner.deleteLater()
        self.context.doneCurrent()
        self.surface.destroy()
        self.app.processEvents()


def _straight_alpha(pixels):
    """Convert premultiplied RGBA pixels (Quick/GL output) to straight alpha."""

    import numpy
    from PIL import Image

    rgba = pixels.astype(numpy.float32)
    alpha = rgba[..., 3:4]
    rgb = numpy.where(alpha > 0.0, rgba[..., :3] * 255.0 / numpy.maximum(alpha, 1.0), 0.0)
    out = numpy.concatenate((numpy.clip(rgb, 0.0, 255.0), alpha), axis=-1).astype(numpy.uint8)
    return Image.fromarray(out, "RGBA")


def _unsettled_images(item) -> list[str]:
    """Visible Images under ``item`` still decoding, or artwork fades still pending."""

    unsettled: list[str] = []
    pending = [item]
    while pending:
        node = pending.pop()
        pending.extend(node.childItems())
        if not node.isVisible():
            continue
        if str(node.property("_pendingSource") or ""):
            unsettled.append(f"fade:{node.objectName() or node.metaObject().className()}")
            continue
        if not node.inherits("QQuickImageBase"):
            continue
        source = node.property("source")
        source = source.toString() if hasattr(source, "toString") else str(source or "")
        if not source:
            continue
        if node.property("progress") < 1.0:
            unsettled.append(f"loading:{node.objectName() or source}")
        elif node.property("paintedWidth") <= 0.0 and node.width() > 0.0:
            raise RuntimeError(f"preview image failed to decode: {node.objectName() or source}")
    return unsettled


def _capture_item(scene: _HiddenQuickScene, item, *, minimum_ms: int = 1100):
    """Render until settled, then crop the item and its card shadow."""

    from PySide6.QtCore import QRectF

    try:
        scene.settle(minimum_ms=minimum_ms, until=lambda: not _unsettled_images(item))
    except RuntimeError as error:
        raise RuntimeError(f"{error}: {_unsettled_images(item)}") from None
    frame = scene.read()
    rect = item.mapRectToScene(QRectF(0.0, 0.0, item.width(), item.height()))
    left = max(0, int(rect.left()) - _SHADOW_MARGIN)
    top = max(0, int(rect.top()) - _SHADOW_MARGIN)
    right = min(frame.width, int(rect.right()) + _SHADOW_MARGIN + 1)
    bottom = min(frame.height, int(rect.bottom()) + _SHADOW_MARGIN + 1)
    return _trim_to_card(frame.crop((left, top, right, bottom)))


def _trim_to_card(region):
    """Crop evenly around the card body so its directional shadow stays subtle."""

    alpha = region.getchannel("A")
    # Shadow tails are faint; the card body (fill and border) is the densest alpha.
    threshold = max(6, int(alpha.getextrema()[1] * 0.55))
    bounds = alpha.point(lambda value: 255 if value > threshold else 0).getbbox()
    if bounds is None:
        raise RuntimeError("preview capture rendered no pixels")
    pad = _SHADOW_KEEP
    return region.crop((max(0, bounds[0] - pad), max(0, bounds[1] - pad),
                        min(region.width, bounds[2] + pad), min(region.height, bounds[3] + pad)))


def _place_preferred(scene: _HiddenQuickScene, presentation, *, scale: float = 1.0) -> None:
    """Size a presentation to its declared preferred content size, as runtime does."""

    from rendering.quick.widgets.host import OverlayWidgetGeometry

    for _ in range(6):
        scene.render()
    width = float(presentation.item.property("preferredContentWidth") or 0.0)
    height = float(presentation.item.property("preferredContentHeight") or 0.0)
    if width <= 1.0 or height <= 1.0:
        raise RuntimeError(f"{type(presentation).__name__} declared no preferred size")
    presentation.set_geometry(OverlayWidgetGeometry(
        _WIDGET_ORIGIN[0], _WIDGET_ORIGIN[1], round(width * scale), round(height * scale)))


def _frame_preview(image, destination: Path) -> tuple[int, int]:
    from PIL import Image

    image.thumbnail((820, 560), Image.Resampling.LANCZOS)
    image.save(destination, "PNG", optimize=True)
    return image.width, image.height


# --------------------------------------------------------------------------- #
# Fixtures (deterministic, fictional, local only)                             #
# --------------------------------------------------------------------------- #


def _preview_widgets(**sections: dict[str, object]) -> dict[str, Any]:
    """Canonical widget defaults with the named sections enabled and carded."""

    from core.settings.default_contract import require_canonical_default

    widgets = copy.deepcopy(require_canonical_default("widgets"))
    for key, overrides in sections.items():
        section = widgets.setdefault(key, {})
        section.update({"enabled": True, "show_background": True})
        section.update(overrides)
    return widgets


def _preview_shadows() -> dict[str, object]:
    from core.settings.default_contract import require_canonical_default

    return dict(require_canonical_default("widgets.shadows"))


def _gradient_art(path: Path, size: tuple[int, int], stops: tuple[str, str], motif: int) -> Path:
    """A synthetic artwork thumbnail; never a real cover, photo or person."""

    from PySide6.QtCore import QPointF, Qt
    from PySide6.QtGui import QColor, QImage, QLinearGradient, QPainter, QRadialGradient

    image = QImage(size[0], size[1], QImage.Format.Format_ARGB32_Premultiplied)
    painter = QPainter(image)
    try:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        gradient = QLinearGradient(0.0, 0.0, size[0], size[1])
        gradient.setColorAt(0.0, QColor(stops[0]))
        gradient.setColorAt(1.0, QColor(stops[1]))
        painter.fillRect(image.rect(), gradient)
        glow = QRadialGradient(QPointF(size[0] * (0.3 + 0.2 * (motif % 3)), size[1] * 0.38), size[1] * 0.55)
        glow.setColorAt(0.0, QColor(255, 244, 214, 190))
        glow.setColorAt(1.0, QColor(255, 244, 214, 0))
        painter.fillRect(image.rect(), glow)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(8, 12, 24, 120))
        base = size[1] * 0.72
        step = size[0] / 6.0
        for index in range(7):
            peak = base - size[1] * (0.12 + 0.1 * ((index * (motif + 2)) % 3))
            painter.drawPolygon([QPointF(step * (index - 1), size[1]), QPointF(step * index, peak),
                                 QPointF(step * (index + 1), size[1])])
    finally:
        painter.end()
    if not image.save(str(path), "PNG"):
        raise RuntimeError(f"could not save synthetic artwork {path.name}")
    return path


def _avatar_art(path: Path, stops: tuple[str, str]) -> Path:
    """A synthetic portrait silhouette; deliberately not any real identity."""

    from PySide6.QtCore import QRectF, Qt
    from PySide6.QtGui import QColor, QImage, QLinearGradient, QPainter

    image = QImage(96, 96, QImage.Format.Format_ARGB32_Premultiplied)
    painter = QPainter(image)
    try:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        gradient = QLinearGradient(0.0, 0.0, 96.0, 96.0)
        gradient.setColorAt(0.0, QColor(stops[0]))
        gradient.setColorAt(1.0, QColor(stops[1]))
        painter.fillRect(image.rect(), gradient)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(255, 255, 255, 215))
        painter.drawEllipse(QRectF(30.0, 18.0, 36.0, 36.0))
        painter.drawRoundedRect(QRectF(16.0, 58.0, 64.0, 50.0), 25.0, 25.0)
    finally:
        painter.end()
    if not image.save(str(path), "PNG"):
        raise RuntimeError(f"could not save synthetic avatar {path.name}")
    return path


class _Lease:
    """Activation-compatible inert service: no source, network or timer."""

    def __init__(self, on_start: Callable[[Any], None] | None = None) -> None:
        self.consumer = None
        self._on_start = on_start

    def configure(self, _config: Any) -> None:
        return None

    def set_thread_manager(self, *_args: Any, **_kwargs: Any) -> None:
        return None

    def attach_consumer(self, consumer: Any) -> None:
        self.consumer = consumer

    def detach_consumer(self, consumer: Any = None) -> None:
        if consumer is None or consumer is self.consumer:
            self.consumer = None

    def start(self, *_args: Any, **_kwargs: Any) -> bool:
        if self._on_start is not None and self.consumer is not None:
            self._on_start(self.consumer)
        return True

    def stop(self) -> None:
        return None

    def refresh(self, *_args: Any, **_kwargs: Any) -> bool:
        return False

    def request_refresh(self) -> bool:
        return False

    def update_visible_range(self, _first: int, _last: int) -> bool:
        return True

    def current_snapshot(self) -> None:
        return None

    def set_provider_runtime(self, *_args: Any, **_kwargs: Any) -> bool:
        return True

    def set_runtime_volume_source(self, *_args: Any) -> bool:
        return True

    def set_volume_optimistic(self, _level: float) -> bool:
        return True

    def seek_fraction(self, _fraction: float, *, execute: bool = True) -> bool:
        return bool(execute)

    def toggle_mute(self) -> bool:
        return True

    def step_system_volume(self, _delta: float) -> float:
        return 0.5


class _WeatherLease(_Lease):
    def __init__(self, sample: dict[str, object]) -> None:
        super().__init__()
        self._sample = sample
        self.location = ""

    def set_location(self, location: str) -> None:
        self.location = str(location or "")

    def has_cached_data(self) -> bool:
        return False

    def is_running(self) -> bool:
        return True

    def fetch_weather(self) -> None:
        return None

    def publish(self) -> None:
        if self.consumer is not None:
            self.consumer.on_weather_state(dict(self._sample), from_cache=False)


def _activate(presentation) -> None:
    presentation.activate(object())


def _preview_clocks(scene: _HiddenQuickScene, art: Path):
    """Clock 1 (analog, the default) beside Clock 2 (digital)."""

    from datetime import datetime
    from PIL import Image
    from rendering.quick.widgets.clock import (ClockPresentationConfig, ClockPresentationModel,
        ClockPresentationStyle, RetainedClockPresentation)
    from rendering.quick.widgets.host import OverlayWidgetGeometry

    # Secondary clocks inherit the base style and mode; a per-display override
    # is the product's way to show a different face.
    widgets = _preview_widgets(clock={"display_mode": "analog"},
                               clock2={"display_mode_overrides": {"preview": "digital"}})
    captures = []
    for widget_id in ("clock", "clock2"):
        config = ClockPresentationConfig.from_widgets_mapping(widget_id, widgets, display_signature="preview")
        model = ClockPresentationModel(config, ClockPresentationStyle.project(config, _preview_shadows()),
            now_provider=lambda _zone: datetime(2026, 8, 25, 13, 24, 30), parent=scene.owner)
        presentation = RetainedClockPresentation(host=scene.host, model=model,
            geometry=OverlayWidgetGeometry(*_WIDGET_ORIGIN, 300, 300),
            display_bounds=OverlayWidgetGeometry(0.0, 0.0, *_SCENE_SIZE), display_identity="preview")
        # Not activated: activation subscribes the shared ticker; the fixed
        # ``now_provider`` already supplies the frozen preview time.
        _place_preferred(scene, presentation)
        captures.append(_capture_item(scene, presentation.item))
        presentation.retire()
    gap = 12
    height = max(image.height for image in captures)
    combined = Image.new("RGBA", (sum(image.width for image in captures) + gap, height), (0, 0, 0, 0))
    x = 0
    for image in captures:
        combined.alpha_composite(image, (x, (height - image.height) // 2))
        x += image.width + gap
    return combined


def _preview_weather(scene: _HiddenQuickScene, art: Path):
    from rendering.quick.widgets.weather import (RetainedWeatherPresentation, WeatherPresentationConfig,
        WeatherPresentationModel, WeatherPresentationStyle)
    from rendering.quick.widgets.host import OverlayWidgetGeometry

    widgets = _preview_widgets(weather={"location": "Cape Town", "show_forecast": True,
                                        "show_details_row": True})
    config = WeatherPresentationConfig.from_widgets_mapping(widgets)
    lease = _WeatherLease({
        "temperature": 22.4, "condition": "partly cloudy", "location": "Cape Town", "weather_code": 2,
        "is_day": 1, "precipitation_probability": 17, "humidity": 68, "windspeed": 12.6,
        "forecast": "Tomorrow: 19°C, light rain",
    })
    model = WeatherPresentationModel(config, WeatherPresentationStyle.project(config, _preview_shadows()),
                                     lease, parent=scene.owner)
    presentation = RetainedWeatherPresentation(host=scene.host, model=model,
                                               geometry=OverlayWidgetGeometry(*_WIDGET_ORIGIN, 400, 240))
    _activate(presentation)
    lease.publish()
    _place_preferred(scene, presentation)
    return presentation


def _preview_media(scene: _HiddenQuickScene, art: Path):
    from PySide6.QtGui import QImage
    from core.media.media_controller import MediaPlaybackState, MediaTrackInfo
    from rendering.quick.widgets.host import OverlayWidgetGeometry
    from rendering.quick.widgets.media import (MediaPresentationConfig, MediaPresentationModel,
        MediaPresentationStyle, RetainedMediaPresentation)
    from widgets.media_runtime import MediaRuntimeSnapshot, PreparedMediaArtwork
    from widgets.media_volume_runtime import MediaVolumeRuntimeSnapshot
    from widgets.system_mute_runtime import SystemMuteRuntimeSnapshot

    widgets = _preview_widgets(media={"spotify_volume_enabled": True, "mute_button_enabled": True})
    config = MediaPresentationConfig.from_widgets_mapping(widgets)

    class VolumeLease(_Lease):
        def current_snapshot(self):
            return MediaVolumeRuntimeSnapshot(revision=1, provider=config.provider, browser_process=None,
                                              supported=True, available=True, level=0.68, source="preview")

    class MuteLease(_Lease):
        def current_snapshot(self):
            return SystemMuteRuntimeSnapshot(revision=1, available=True, muted=False, source="preview")

    model = MediaPresentationModel(config, MediaPresentationStyle.project(config, _preview_shadows()),
        scene.factory.media_artwork_provider, _Lease(), volume_runtime_service=VolumeLease(),
        system_mute_runtime_service=MuteLease(), parent=scene.owner)
    presentation = RetainedMediaPresentation(host=scene.host, model=model,
                                             geometry=OverlayWidgetGeometry(*_WIDGET_ORIGIN, 600, 300))
    _activate(presentation)
    artwork = QImage(str(art))
    if artwork.isNull():
        raise RuntimeError("synthetic media artwork did not load")
    model.on_media_runtime_snapshot(MediaRuntimeSnapshot(
        1, config.provider,
        MediaTrackInfo(title="Neon Harbour", artist="The Quiet Arcade", album="Night Transit",
                       state=MediaPlaybackState.PLAYING, can_play_pause=True, can_next=True,
                       can_previous=True, can_seek=True, position_ms=84_000, duration_ms=231_000),
        PreparedMediaArtwork((1, "onboarding-preview-artwork"), artwork, 0.0)))
    if not model.hasArtwork:
        raise RuntimeError("media preview artwork was not admitted")
    _place_preferred(scene, presentation)
    return presentation


def _preview_reddit(scene: _HiddenQuickScene, art: Path):
    from core.reddit_preparation import RedditPost
    from rendering.quick.widgets.host import OverlayWidgetGeometry
    from rendering.quick.widgets.reddit import (RedditPresentationConfig, RedditPresentationModel,
        RedditPresentationStyle, RetainedRedditPresentation)

    widgets = _preview_widgets(reddit={"subreddit": "wallpapers", "limit": 5})
    config = RedditPresentationConfig.from_widgets_mapping(widgets, widget_id="reddit")
    model = RedditPresentationModel(config, RedditPresentationStyle.project(config, _preview_shadows()),
                                    parent=scene.owner)
    now = 100_000_000.0
    model.publish_posts((
        RedditPost("Sunrise over the fjord, shot on my phone", "https://reddit.invalid/1", 2140, now - 25 * 60),
        RedditPost("Minimal dark mountains [3840x2160]", "https://reddit.invalid/2", 1310, now - 3 * 3600),
        RedditPost("Rainy neon street at night", "https://reddit.invalid/3", 980, now - 7 * 3600),
        RedditPost("Aurora above the cabin", "https://reddit.invalid/4", 760, now - 26 * 3600),
        RedditPost("Desert road, golden hour", "https://reddit.invalid/5", 540, now - 3 * 86400),
    ), now_ts=now)
    presentation = RetainedRedditPresentation(host=scene.host, model=model,
                                              geometry=OverlayWidgetGeometry(*_WIDGET_ORIGIN, 560, 280))
    presentation.activate()
    _place_preferred(scene, presentation)
    return presentation


def _preview_gmail(scene: _HiddenQuickScene, art: Path):
    from datetime import datetime, timezone
    from core.gmail.gmail_client import EmailMetadata
    from rendering.quick.widgets.gmail import (GmailPresentationConfig, GmailPresentationModel,
        GmailPresentationStyle, RetainedGmailPresentation)
    from types import SimpleNamespace
    from rendering.quick.widgets.host import OverlayWidgetGeometry

    def email(identity: str, sender: str, subject: str, unread: bool, minute: int) -> EmailMetadata:
        return EmailMetadata(id=identity, thread_id=f"thread-{identity}", sender=sender, subject=subject,
            date=datetime(2026, 8, 27, 14, minute, tzinfo=timezone.utc),
            labels=("INBOX", "UNREAD") if unread else ("INBOX",), is_unread=unread, provider="gmail_api")

    widgets = _preview_widgets(gmail={"limit": 4})
    config = GmailPresentationConfig.from_widgets_mapping(widgets)
    model = GmailPresentationModel(config, GmailPresentationStyle.project(config, _preview_shadows()),
                                   parent=scene.owner)
    presentation = RetainedGmailPresentation(host=scene.host, model=model,
                                             geometry=OverlayWidgetGeometry(*_WIDGET_ORIGIN, 560, 260))
    presentation.activate()
    emails = (
        email("one", "Mira Holt <mira@example.invalid>", "Weekend photos are up", True, 42),
        email("two", "Book Club <club@example.invalid>", "Next month's pick", True, 30),
        email("three", "Build Bot <ci@example.invalid>", "Nightly build passed", True, 12),
        email("four", "Calendar <calendar@example.invalid>", "Dinner at 7 tomorrow", False, 3),
    )
    # The runtime snapshot shape, without importing the credential-owning
    # Gmail runtime module (the foundry's import guard forbids it).
    model.on_gmail_runtime_snapshot(SimpleNamespace(revision=1, emails=emails, unread_count=3,
        error=None, refreshing=False, source="preview"))
    _place_preferred(scene, presentation)
    return presentation


_FRIENDS: Final = (
    ("nova", "Nova", 220, "Half-Life 2", 1, ("#5bd6ff", "#3152a4")),
    ("wren", "Wren", 1145360, "Hades", 1, ("#c995ff", "#6c3ca5")),
    ("kestrel", "Kestrel", 440, "Team Fortress 2", 1, ("#ffb86b", "#b75b42")),
    ("juniper", "Juniper", 753640, "Outer Wilds", 1, ("#7de0bc", "#227a69")),
    ("orbit", "Orbit", None, None, 1, ("#ffd572", "#a86835")),
    ("sable", "Sable", None, None, 3, ("#86a8ff", "#4a529f")),
    ("marlowe", "Marlowe", None, None, 2, ("#f28cb1", "#984269")),
    ("pixel", "Pixel", None, None, 0, ("#9fd478", "#477a3d")),
)


def _preview_steam(scene: _HiddenQuickScene, art: Path):
    from core.steam.friend_pulse import FriendPulseEntry, FriendPulseSnapshot, project_friend_pulse
    from core.steam.models import SteamResultStatus
    from rendering.quick.widgets.friend_pulse import (FriendPulsePresentationConfig,
        FriendPulsePresentationModel, FriendPulsePresentationStyle, RetainedFriendPulsePresentation)
    from rendering.quick.widgets.host import OverlayWidgetGeometry

    widgets = _preview_widgets(friend_pulse={})
    config = FriendPulsePresentationConfig.from_widgets_mapping(widgets)
    model = FriendPulsePresentationModel(config, FriendPulsePresentationStyle.project(config, _preview_shadows()),
                                         runtime_generation=1, parent=scene.owner)
    model.set_runtime_service(_Lease())
    presentation = RetainedFriendPulsePresentation(host=scene.host, model=model,
        geometry=OverlayWidgetGeometry(*_WIDGET_ORIGIN, config.authored_width, config.authored_height))
    _activate(presentation)
    avatars = {identity: _avatar_art(art.parent / f"avatar_{identity}.png", stops).resolve().as_uri()
               for identity, _name, _app, _game, _state, stops in _FRIENDS}
    snapshot = FriendPulseSnapshot(status=SteamResultStatus.SUCCESS, authoritative=True, playing_count=4,
        online_count=7, entries=tuple(FriendPulseEntry(identity, name, app, game, persona_state=state)
                                      for identity, name, app, game, state, _stops in _FRIENDS))
    projection = project_friend_pulse(snapshot, privacy_mode="Rich", capacity=config.capacity,
        avatar_sources=avatars, friend_action_identities={entry.identity_fingerprint for entry in snapshot.entries})
    model.on_friend_pulse_runtime_snapshot(snapshot, projection)
    _place_preferred(scene, presentation)
    return presentation


def _preview_system_stats(scene: _HiddenQuickScene, art: Path):
    from types import SimpleNamespace
    from core.system_stats.source import CpuRamSample
    from rendering.quick.widgets.host import OverlayWidgetGeometry
    from rendering.quick.widgets.system_stats import (RetainedSystemStatsPresentation,
        SystemStatsPresentationConfig, SystemStatsPresentationModel, SystemStatsPresentationStyle)

    widgets = _preview_widgets(system_stats={})
    config = SystemStatsPresentationConfig.from_widgets_mapping(widgets)
    model = SystemStatsPresentationModel(config, SystemStatsPresentationStyle.project(config, _preview_shadows()),
                                         runtime_generation=1, parent=scene.owner)
    model.set_runtime_service(_Lease())
    presentation = RetainedSystemStatsPresentation(host=scene.host, model=model,
                                                   geometry=OverlayWidgetGeometry(*_WIDGET_ORIGIN, 520, 270))
    _activate(presentation)
    model.on_system_stats_runtime_snapshot(SimpleNamespace(revision=1, sample=CpuRamSample(
        "ok", 37.6, "ok", round(10.7 * 1024**3), round(31.9 * 1024**3))))
    _place_preferred(scene, presentation)
    return presentation


def _preview_feeds(scene: _HiddenQuickScene, art: Path):
    from core.feeds.models import FeedDocument, FeedHealth, FeedItem, FeedRefreshResult, FeedSnapshot
    from rendering.quick.widgets.feeds import (FeedPresentationConfig, FeedPresentationModel,
        FeedPresentationStyle, RetainedFeedPresentation)
    from rendering.quick.widgets.host import OverlayWidgetGeometry

    stories = (
        ("story-1", "Coastal towns prepare for a record tide", "Harbour Post", ("#244c7e", "#65c5e8")),
        ("story-2", "New telescope images reveal a stellar nursery", "Sky Desk", ("#663f8c", "#e67d9f")),
        ("story-3", "Rail link reopens after a year of repairs", "Metro Wire", ("#2c706d", "#c6dc72")),
        ("story-4", "Local orchestra tours small mountain villages", "Valley Times", ("#8a4b2a", "#f2b26b")),
        ("story-5", "City parks add night-time lantern trails", "Harbour Post", ("#1f3a5a", "#9ab8d8")),
        ("story-6", "Volunteers restore a century-old lighthouse", "Coast Weekly", ("#3b2f5c", "#c79ad8")),
    )
    # The runtime artwork cache hands the model file URIs (core.feeds.artwork).
    artwork = tuple((identity, _gradient_art(art.parent / f"{identity}.png", (640, 360), stops, index)
                     .resolve().as_uri())
                    for index, (identity, _title, _publisher, stops) in enumerate(stories))
    widgets = _preview_widgets(feeds_news_world={"item_limit": len(stories), "show_images": True})
    config = FeedPresentationConfig.from_widgets_mapping(widgets, widget_id="feeds_news_world")
    model = FeedPresentationModel(config, FeedPresentationStyle.project(config, _preview_shadows()))
    model.set_runtime_service(_Lease())
    presentation = RetainedFeedPresentation(host=scene.host, model=model,
        geometry=OverlayWidgetGeometry(*_WIDGET_ORIGIN, config.preferred_width, config.preferred_height))
    _activate(presentation)
    # Ages are relative to authoring time, so the card reads "2H AGO", not weeks.
    published = int(time.time())
    snapshot = FeedSnapshot(FeedDocument("World News", "https://news.invalid/", "rss", tuple(
        FeedItem(identity, title, summary="", author=publisher, published_at=published - 2400 * (index + 1))
        for index, (identity, title, publisher, _stops) in enumerate(stories))), fetched_at=published)
    model.on_feed_runtime_result(FeedRefreshResult("available", snapshot, FeedHealth(),
                                                   local_artwork_by_item=artwork), from_cache=False)
    _place_preferred(scene, presentation)
    return presentation


def _preview_system_audio_osd(scene: _HiddenQuickScene, art: Path):
    from types import SimpleNamespace
    from rendering.quick.widgets.host import OverlayWidgetGeometry
    from rendering.quick.widgets.system_audio_osd import (RetainedSystemAudioOSDPresentation,
        SystemAudioOSDConfig, SystemAudioOSDPresentationModel)

    def volume(revision: int, level: float):
        return SimpleNamespace(revision=revision, endpoint_token=1, available=True, volume=level,
                               muted=False, source="preview")

    # The first snapshot silently seeds state; a change is what reveals the OSD.
    lease = _Lease(lambda consumer: consumer.on_system_mute_runtime_snapshot(volume(1, .60)))
    # The OSD hides after its inactivity deadline; hold it for the capture.
    widgets = _preview_widgets(system_audio_osd={"inactivity_ms": 12000})
    model = SystemAudioOSDPresentationModel(SystemAudioOSDConfig.from_widgets_mapping(widgets))
    model.set_system_mute_runtime_service(lease)
    presentation = RetainedSystemAudioOSDPresentation(host=scene.host, model=model,
                                                      geometry=OverlayWidgetGeometry(*_WIDGET_ORIGIN, 430, 70))
    _activate(presentation)
    # Admit the item and let its initial hidden fade finish before the volume
    # event, as at runtime (the OSD exists long before anyone touches volume).
    _place_preferred(scene, presentation)
    scene.settle(minimum_ms=1400, until=lambda: True)
    model.on_system_mute_runtime_snapshot(volume(2, .68))
    if not model.revealed:
        raise RuntimeError("system-audio OSD fixture did not reveal")
    return presentation


def _preview_visualizers(scene: _HiddenQuickScene, art: Path):
    """The real Visualizer card shell with canonical Spectrum bars composited inside."""

    from PIL import Image
    from PySide6.QtCore import QRectF
    from PySide6.QtQuick import QQuickItem
    from widgets.spotify_visualizer.presentation_geometry import VisualizerShellPolicy

    width, height = 600, 250
    bars_path = art.parent / "spectrum_bars.png"
    snapshot = _render_spectrum_preview(bars_path, width=width, height=height)
    presentation = snapshot.presentation
    style = presentation.shell_style
    loader = scene.find("visualizerPresentationLoader")
    loader.setProperty("active", True)
    root = loader.property("item")
    if not isinstance(root, QQuickItem):
        raise RuntimeError("VisualizerPresentation.qml did not load")
    loader.setX(_WIDGET_ORIGIN[0]); loader.setY(_WIDGET_ORIGIN[1])
    loader.setWidth(width); loader.setHeight(height)
    root.setX(0.0); root.setY(0.0); root.setWidth(width); root.setHeight(height)

    def color(value):
        from PySide6.QtGui import QColor
        red, green, blue, alpha = value
        return QColor(int(red), int(green), int(blue), int(alpha))

    # Same projection as QuickSceneController's shell publication.
    root.setProperty("cardShellEnabled", presentation.shell_policy is VisualizerShellPolicy.CARD)
    root.setProperty("cardBackgroundColor", color(style["background_color"]))
    root.setProperty("cardBorderColor", color(style["border_color"]))
    root.setProperty("cardBorderWidth", presentation.border_width)
    root.setProperty("cardCornerRadius", float(style["corner_radius"]))
    root.setProperty("cardShadowEnabled", bool(style["shadow_enabled"]))
    root.setProperty("cardShadowColor", color(style["shadow_color"]))
    root.setProperty("cardShadowBlur", float(style["shadow_blur"]))
    root.setProperty("cardShadowOffsetX", float(style["shadow_offset"][0]))
    root.setProperty("cardShadowOffsetY", float(style["shadow_offset"][1]))
    root.setProperty("cardShadowSpread", float(style["shadow_spread"]))
    for index, edge in enumerate(("Left", "Top", "Right", "Bottom")):
        root.setProperty(f"cardShadowExtend{edge}", float(style["shadow_extensions"][index]))
    root.setProperty("presentationActive", True)
    scene.settle(minimum_ms=300, until=lambda: True)
    frame = scene.read()
    rect = root.mapRectToScene(QRectF(0.0, 0.0, width, height))
    left, top = int(rect.left()), int(rect.top())
    with Image.open(bars_path) as bars:
        frame.alpha_composite(bars.convert("RGBA"), (left, top))
    loader.setProperty("active", False)
    return _trim_to_card(frame.crop((left - _SHADOW_MARGIN, top - _SHADOW_MARGIN,
                                     left + width + _SHADOW_MARGIN, top + height + _SHADOW_MARGIN)))


# Widget family id -> preview builder.  Builders return either a retained
# presentation (captured here) or an already-composed image.
_WIDGET_PREVIEWS: Final = {
    "clocks": _preview_clocks,
    "weather": _preview_weather,
    "media": _preview_media,
    "reddit": _preview_reddit,
    "gmail": _preview_gmail,
    "steam": _preview_steam,
    "system_stats": _preview_system_stats,
    "feeds": _preview_feeds,
    "system_audio_osd": _preview_system_audio_osd,
    "visualizers": _preview_visualizers,
}


def _build_widget_previews(output: Path, scratch: Path, *,
                           families: list[str] | None = None) -> list[dict[str, object]]:
    from PySide6.QtGui import QGuiApplication

    app = QGuiApplication.instance() or QGuiApplication(["onboarding-preview-foundry"])
    del app
    art = _gradient_art(scratch / "media_artwork.png", (480, 480), ("#27336e", "#e7678a"), 1)
    scene = _HiddenQuickScene(*_SCENE_SIZE)
    rows: list[dict[str, object]] = []
    try:
        for family_id, builder in _WIDGET_PREVIEWS.items():
            if families and family_id not in families:
                continue
            built = builder(scene, art)
            if hasattr(built, "item"):
                image = _capture_item(scene, built.item)
                built.retire()
            else:
                image = built
            name = f"widget_{family_id}.png"
            width, height = _frame_preview(image, output / name)
            rows.append({"family_id": family_id, "path": name, "size": [width, height]})
    finally:
        scene.close()
    return rows


def _build_spectrum_preview_snapshot(*, width: int, height: int):
    """Build one deterministic Spectrum snapshot through the production capture seam."""

    from dataclasses import asdict

    from core.settings.default_contract import require_canonical_default
    from core.settings.models import ShadowSettings, SpotifyVisualizerSettings
    from core.settings.shadow_direction import (
        resolve_directional_extensions,
        resolve_signed_offset,
    )
    from core.settings.visualizer_mode_registry import get_visualizer_presentation_policy
    from core.settings.visualizer_presets import resolve_visualizer_activation_payload
    from rendering.quick.shadow_snapshot import QuickShadowSnapshot
    from rendering.quick.widgets.host import ORDINARY_CARD_SHADOW_BASE
    from ui.widget_theme_spec import DEFAULT_DARK_WIDGET_THEME
    from widgets.spotify_visualizer.config_applier import (
        apply_logical_vis_mode_kwargs,
        apply_presentation_vis_mode_kwargs,
    )
    from widgets.spotify_visualizer.logical_frame_capture import (
        capture_visualizer_logical_frame,
    )
    from widgets.spotify_visualizer.logical_tick_state import (
        install_default_logical_tick_state,
    )
    from widgets.spotify_visualizer.presentation_geometry import (
        VISUALIZER_CARD_CONTENT_INSET,
        VISUALIZER_CARD_CORNER_RADIUS,
        VISUALIZER_CARD_SHADOW_SPREAD,
        resolve_visualizer_presentation,
    )
    from widgets.spotify_visualizer.presentation_state import (
        install_default_presentation_state,
    )
    from widgets.spotify_visualizer.render_state import (
        compose_visualizer_render_snapshot,
    )
    from widgets.spotify_visualizer.runtime_controller import (
        VisualizerRuntimeController,
    )

    # Use the same preset/default normalization and typed model consumed by the
    # display owner.  A foundry image must not become a second table of Spectrum
    # colours, topology, bar count, or renderer parameters.
    activation = resolve_visualizer_activation_payload(
        {"mode": "spectrum", "preset_spectrum": 0},
        mode="spectrum",
    )
    model = SpotifyVisualizerSettings.from_mapping(
        activation.resolved_config,
        apply_preset_overlay=False,
    )
    resolved = asdict(model)
    controller = VisualizerRuntimeController(
        runtime_generation=1,
        bar_count=model.resolve_bar_count("spectrum"),
        initial_mode="spectrum",
    )
    state = controller.logical_tick_state
    install_default_logical_tick_state(state, bar_count=controller.bar_count)
    install_default_presentation_state(controller.presentation_state)
    apply_logical_vis_mode_kwargs(state, resolved)
    apply_presentation_vis_mode_kwargs(controller.presentation_state, resolved)
    controller.enabled = True
    controller.playing = True

    # Project the same compiled Widget Theme and canonical shadow/default inputs
    # that DisplayManager supplies to the production presentation resolver.
    shadow = QuickShadowSnapshot.from_mapping(asdict(ShadowSettings()))
    shadow_color = list(shadow.color)
    shadow_color[3] = max(
        0,
        min(255, int(round(shadow_color[3] * shadow.frame_opacity))),
    )
    # The direct render host consumes item-local coordinates, just as the
    # retained QSG node does.  Make the authored viewport exactly the asset
    # canvas so the preview is a clean crop of that real local surface.
    extent = (float(width), float(height))
    presentation = resolve_visualizer_presentation(
        policy=get_visualizer_presentation_policy("spectrum"),
        display_size=(float(width), float(height)),
        outer_origin=(0.0, 0.0),
        viewport_extent=extent,
        border_width=float(require_canonical_default("widgets.global.card_border_width_px")),
        corner_radius=VISUALIZER_CARD_CORNER_RADIUS,
        content_inset=VISUALIZER_CARD_CONTENT_INSET,
        background_color=DEFAULT_DARK_WIDGET_THEME.color("card.background").as_tuple(),
        border_color=DEFAULT_DARK_WIDGET_THEME.color("card.border").as_tuple(),
        shadow_enabled=shadow.enabled,
        shadow_color=tuple(shadow_color),
        shadow_blur=min(80.0, shadow.blur_radius),
        shadow_offset=resolve_signed_offset(shadow.direction, *ORDINARY_CARD_SHADOW_BASE),
        shadow_spread=VISUALIZER_CARD_SHADOW_SPREAD,
        shadow_extensions=resolve_directional_extensions(
            shadow.direction, shadow.frame_extra_offset
        ),
    )
    controller.commit_presentation_metrics(presentation)

    # Fixed synthetic analyser output is the only fixture.  Two production
    # captures create a stable live body plus the preset's real falling peaks /
    # ghost state; every style and topology field still comes from config.
    high_bars = tuple(
        0.24 + 0.68 * (((index * 17 + 11) % 31) / 30.0)
        for index in range(controller.bar_count)
    )
    current_bars = tuple(
        max(0.10, value - (0.08 + 0.22 * ((index % 5) / 4.0)))
        for index, value in enumerate(high_bars)
    )
    state._display_bars = list(high_bars)
    state._display_bars_source_generation = 1
    state._display_bars_source_activation = 1
    state._last_engine_generation_seen = 1
    state._last_engine_activation_seen = 1
    first = capture_visualizer_logical_frame(
        state,
        now_ts=1.0,
        changed=True,
        mode_reveal_ready=True,
    )
    if first is None:
        raise RuntimeError("canonical Spectrum preview capture rejected its first fixture frame")
    state._has_pushed_first_frame = True
    state._display_bars = list(current_bars)
    logical = capture_visualizer_logical_frame(
        state,
        now_ts=1.12,
        changed=True,
        mode_reveal_ready=True,
    )
    if logical is None:
        raise RuntimeError("canonical Spectrum preview capture rejected its settled fixture frame")
    return compose_visualizer_render_snapshot(
        logical,
        presentation,
        logical_revision=2,
    )


def _render_spectrum_preview(path: Path, *, width: int, height: int):
    """Render canonical Spectrum bars on transparency through the production GL host.

    The Visualizer card shell is QML (``VisualizerPresentation.qml``); the caller
    composites these bars into the real card.  Returns the render snapshot.
    """

    from OpenGL import GL as gl
    from PIL import Image
    from PySide6.QtGui import QGuiApplication, QOffscreenSurface, QOpenGLContext, QSurfaceFormat
    from rendering.quick.visualizer.render_host import QuickVisualizerRenderHost

    app = QGuiApplication.instance() or QGuiApplication(["onboarding-spectrum"])
    platform = app.platformName().strip().lower()
    if platform != "windows":
        raise RuntimeError(
            "Spectrum preview requires the hidden Windows-QPA QOffscreenSurface worker"
        )
    context = QOpenGLContext(); fmt = QSurfaceFormat(); fmt.setRenderableType(QSurfaceFormat.OpenGL)
    fmt.setProfile(QSurfaceFormat.CoreProfile); fmt.setVersion(4, 1); context.setFormat(fmt)
    if not context.create(): raise RuntimeError("offscreen Spectrum GL context unavailable")
    surface = QOffscreenSurface(); surface.setFormat(context.format()); surface.create()
    if not context.makeCurrent(surface): raise RuntimeError("offscreen Spectrum GL admission failed")
    color = depth = fbo = 0; host = QuickVisualizerRenderHost()
    try:
        color = int(gl.glGenTextures(1)); gl.glBindTexture(gl.GL_TEXTURE_2D, color)
        gl.glTexImage2D(gl.GL_TEXTURE_2D, 0, gl.GL_RGBA8, width, height, 0, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE, None)
        depth = int(gl.glGenRenderbuffers(1)); gl.glBindRenderbuffer(gl.GL_RENDERBUFFER, depth)
        gl.glRenderbufferStorage(gl.GL_RENDERBUFFER, gl.GL_DEPTH_COMPONENT24, width, height)
        fbo = int(gl.glGenFramebuffers(1)); gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, fbo)
        gl.glFramebufferTexture2D(gl.GL_FRAMEBUFFER, gl.GL_COLOR_ATTACHMENT0, gl.GL_TEXTURE_2D, color, 0)
        gl.glFramebufferRenderbuffer(gl.GL_FRAMEBUFFER, gl.GL_DEPTH_ATTACHMENT, gl.GL_RENDERBUFFER, depth)
        if gl.glCheckFramebufferStatus(gl.GL_FRAMEBUFFER) != gl.GL_FRAMEBUFFER_COMPLETE: raise RuntimeError("Spectrum FBO incomplete")
        snapshot = _build_spectrum_preview_snapshot(width=width, height=height)
        gl.glViewport(0, 0, width, height); gl.glClearColor(0., 0., 0., 0.); gl.glClear(gl.GL_COLOR_BUFFER_BIT | gl.GL_DEPTH_BUFFER_BIT)
        # Quick's item coordinates are top-left based; match the production
        # render-frame transform before readback flips OpenGL's framebuffer.
        matrix = (2/width, 0, 0, 0, 0, -2/height, 0, 0, 0, 0, 1, 0, -1, 1, 0, 1)
        if host.render(snapshot=snapshot, viewport=(0, 0, width, height), logical_size=(float(width), float(height)), matrix_values=matrix) != "spectrum": raise RuntimeError("Spectrum renderer was not admitted")
        import numpy
        pixels = numpy.frombuffer(bytes(gl.glReadPixels(0, 0, width, height, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE)),
                                  dtype=numpy.uint8).reshape(height, width, 4)
        _straight_alpha(numpy.flipud(pixels)).save(path, "PNG")
        return snapshot
    finally:
        host.release_resources()
        if fbo: gl.glDeleteFramebuffers(1, [fbo])
        if depth: gl.glDeleteRenderbuffers(1, [depth])
        if color: gl.glDeleteTextures([color])
        context.doneCurrent(); surface.destroy()


def _build_transition_previews(output: Path) -> list[dict[str, object]]:
    from PIL import Image
    from rendering.quick.transitions.implementation_registry import iter_quick_transition_implementations
    from tools.transition_contact_sheet import TransitionCapture

    source_path, destination_path = _prepare_transition_artwork(output)
    source, destination = Image.open(source_path), Image.open(destination_path)
    rows: list[dict[str, object]] = []
    for implementation in iter_quick_transition_implementations():
        capture = TransitionCapture(480, 270, source, destination)
        try:
            run = _resolved_transition_run(capture, implementation.transition_id)
            samples = _TRANSITION_SAMPLES.get(implementation.transition_id, _DEFAULT_TRANSITION_SAMPLES)
            frames = [capture.render(run, progress)[0] for progress in samples]
            triptych = Image.new("RGBA", (1440, 294), "#151b24")
            for index, frame in enumerate(frames):
                triptych.paste(frame, (index * 480, 24))
            from PIL import ImageDraw, ImageFont
            draw = ImageDraw.Draw(triptych)
            font = ImageFont.truetype("C:/Windows/Fonts/segoeui.ttf", 16)
            for index, label in enumerate(f"{round(value * 100)}%" for value in samples):
                draw.text((index * 480 + 12, 1), label, font=font, fill=(235, 242, 250))
            name = f"transition_{implementation.transition_id}.png"
            triptych.save(output / name, "PNG", optimize=True)
            rows.append({"transition_id": implementation.transition_id, "path": name,
                         "size": [1440, 294], "progress": list(samples)})
        finally:
            capture.close()
    return rows


def _prepare_transition_artwork(output: Path) -> tuple[Path, Path]:
    """Bundle the approved operator artworks as fixed preview inputs."""
    from PIL import Image, ImageOps
    approved = (
        Path("D:/Artwork/Projects/Monsters/Letting1B.jpg"),
        Path("D:/Artwork/Projects/Hunguponyou/Finals/MassiveDS.jpg"),
    )
    targets = (output / "transition_source.png", output / "transition_destination.png")
    for source, target in zip(approved, targets, strict=True):
        if not source.is_file():
            raise RuntimeError(f"approved transition artwork is missing: {source}")
        with Image.open(source) as original:
            ImageOps.fit(original.convert("RGB"), (480, 270), Image.Resampling.LANCZOS).save(target, "PNG", optimize=True)
    return targets


def _resolved_transition_run(capture: object, transition_id: str):
    """Use the same default/parameter resolver that admits runtime requests."""

    import copy
    import random
    from core.settings.default_contract import require_canonical_default
    from rendering.quick.image_state import PresentationImage
    from rendering.quick.transitions.request_resolution import resolve_quick_transition_spec
    from rendering.quick.transitions.state import TransitionRequest, TransitionRun
    from rendering.transition_registry import get_transition_descriptor_for_runtime_identity

    descriptor = get_transition_descriptor_for_runtime_identity(transition_id)
    if descriptor is None:
        raise RuntimeError(f"unknown transition identity {transition_id!r}")
    transitions = copy.deepcopy(require_canonical_default("transitions"))
    transitions["type"] = descriptor.setting_name
    transitions["random_always"] = False
    transitions.setdefault("activation", {})[descriptor.setting_name] = True
    transitions.setdefault("pool", {})[descriptor.setting_name] = True
    class DefaultsOnlySettings:
        def get(self, key: str): return transitions if key == "transitions" else None
        def get_bool(self, _key: str): return True
    spec = resolve_quick_transition_spec(DefaultsOnlySettings(), random_source=random.Random(713))
    if spec is None or spec.transition_id != transition_id:
        raise RuntimeError(f"production resolver did not admit {transition_id}")
    images = [PresentationImage(str(index), "onboarding", (capture.width, capture.height), 1.,
        (capture.width, capture.height), capture.width * 4, image.tobytes())
        for index, image in enumerate(capture.images)]
    # TransitionCapture.frame maps a supplied fraction to nanoseconds in one
    # second.  Keep the production-resolved direction/parameters but use its
    # diagnostic 1000ms timeline so 25/50/75 are real fractional samples.
    request = TransitionRequest(0, spec.transition_id, spec.requested_name, spec.selected_from_random,
        1000, spec.direction, spec.parameters, *images)
    return TransitionRun.start(run_id=1, request=request, start_ns=0)


def _guard_attempts(audit_log: Path) -> list[dict[str, str]]:
    if not audit_log.is_file():
        return []
    attempts = []
    for line in audit_log.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            value = {"category": "invalid", "operation": "unreadable audit record"}
        attempts.append({
            "category": str(value.get("category", "unknown")),
            "operation": str(value.get("operation", "unknown")),
        })
    return attempts


def _raise_if_guard_attempts(audit_log: Path) -> None:
    attempts = _guard_attempts(audit_log)
    if not attempts:
        return
    summary = ", ".join(
        f"{item['category']}:{item['operation']}" for item in attempts[:8]
    )
    raise RuntimeError(
        "onboarding preview foundry blocked forbidden authoring work: " + summary
    )


def _run_foundry_worker(
    worker: str,
    output: Path,
    audit_log: Path,
) -> None:
    if worker not in {"widgets", "gl"}:
        raise ValueError(f"unknown foundry worker: {worker}")
    option = "--widgets-worker" if worker == "widgets" else "--gl-worker"
    completed = subprocess.run(
        [
            sys.executable,
            str(Path(__file__).resolve()),
            option,
            "--output",
            str(output),
            "--audit-log",
            str(audit_log),
        ],
        cwd=ROOT,
        env=_hidden_gl_environment(),
        text=True,
        capture_output=True,
        check=False,
        timeout=300,
    )
    # The audit is authoritative even if worker code caught the guard error and
    # returned zero.  Check it before interpreting process success.
    _raise_if_guard_attempts(audit_log)
    if completed.returncode:
        raise RuntimeError(
            f"onboarding preview {worker} worker failed\n{completed.stderr[-4000:]}"
        )


def _manifest_payload(output: Path) -> dict[str, object]:
    """Inspect a complete staged asset set without mutating it."""

    from PIL import Image
    from core.settings.widget_family_catalog import get_widget_family_catalog
    from rendering.quick.transitions.implementation_registry import iter_quick_transition_implementations

    widgets = []
    for family in get_widget_family_catalog():
        name = f"widget_{family.family_id}.png"
        path = output / name
        if not path.is_file():
            raise RuntimeError(f"onboarding preview is missing {name}")
        with Image.open(path) as image:
            if image.format != "PNG" or image.width <= 0 or image.height <= 0:
                raise RuntimeError(f"onboarding preview is not a valid PNG: {name}")
            widgets.append({
                "family_id": family.family_id,
                "path": name,
                "size": [image.width, image.height],
            })
    transitions = []
    for item in iter_quick_transition_implementations():
        name = f"transition_{item.transition_id}.png"
        path = output / name
        if not path.is_file():
            raise RuntimeError(f"onboarding preview is missing {name}")
        with Image.open(path) as image:
            if image.format != "PNG" or image.width <= 0 or image.height <= 0:
                raise RuntimeError(f"onboarding preview is not a valid PNG: {name}")
            transitions.append({
                "transition_id": item.transition_id,
                "path": name,
                "size": [image.width, image.height],
                "progress": list(_TRANSITION_SAMPLES.get(item.transition_id, _DEFAULT_TRANSITION_SAMPLES)),
            })
    total = sum(path.stat().st_size for path in output.glob("*.png"))
    if total > _ASSET_BUDGET_BYTES:
        raise RuntimeError(f"onboarding preview assets exceed 10 MB ({total} bytes)")
    return {
        "format": "png",
        "version": 1,
        "widgets": widgets,
        "transitions": transitions,
        "generation": {
            "widgets": "hidden Windows-QPA QQuickRenderControl worker",
            "gl": "hidden Windows-QPA QOffscreenSurface worker",
        },
        "total_png_bytes": total,
    }


def _write_manifest(output: Path) -> dict[str, object]:
    manifest = _manifest_payload(output)
    (output / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


def build(output: Path) -> dict[str, object]:
    """Build in isolated hidden-GL workers and publish only a validated full set."""

    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix="srpss-onboarding-preview-",
        dir=str(output.parent),
    ) as temporary:
        staging = Path(temporary) / "assets"
        staging.mkdir()
        audit_log = Path(temporary) / "guard_attempts.jsonl"
        _run_foundry_worker("widgets", staging, audit_log)
        _run_foundry_worker("gl", staging, audit_log)
        _apply_operator_sheet(staging)
        manifest = _write_manifest(staging)
        _raise_if_guard_attempts(audit_log)
        output.mkdir(parents=True, exist_ok=True)
        for staged in staging.iterdir():
            if staged.is_file():
                shutil.copy2(staged, output / staged.name)
    return manifest


def _apply_operator_sheet(staging: Path) -> None:
    """Replace fixture previews with cut-outs of the operator's real screenshot.

    Clocks stay rendered here.  Without the (unshipped, operator-owned) sheet
    the fixture previews are kept, so the build never depends on it.
    """

    from tools import onboarding_sheet_previews

    if onboarding_sheet_previews.DEFAULT_SHEET.is_file():
        onboarding_sheet_previews.build(onboarding_sheet_previews.DEFAULT_SHEET, staging)


def assemble_manifest(output: Path) -> dict[str, object]:
    """Record already-generated widget and transition worker assets together."""
    return _write_manifest(output.resolve())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--gl-worker", action="store_true")
    parser.add_argument("--widgets-worker", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--widgets-only", action="store_true")
    parser.add_argument("--family", action="append", help="limit --widgets-only to these families")
    parser.add_argument("--assemble-manifest", action="store_true")
    parser.add_argument("--audit-log", type=Path, help=argparse.SUPPRESS)
    parser.add_argument(
        "--guard-probe",
        choices=("swallowed-network", "swallowed-credential"),
        help=argparse.SUPPRESS,
    )
    args = parser.parse_args(argv)
    if args.assemble_manifest:
        print(json.dumps(assemble_manifest(args.output.resolve()), indent=2))
        return 0
    if not any((
        args.gl_worker,
        args.widgets_worker,
        args.widgets_only,
        args.guard_probe,
    )):
        print(json.dumps(build(args.output.resolve()), indent=2))
        return 0

    def run_guarded(audit_log: Path) -> int:
        _install_authoring_guards(audit_log)
        if args.guard_probe == "swallowed-network":
            try:
                socket.getaddrinfo("example.invalid", 443)
            except RuntimeError:
                pass
        elif args.guard_probe == "swallowed-credential":
            from core.steam.credentials import load_credentials
            try:
                load_credentials()
            except RuntimeError:
                pass
        elif args.gl_worker:
            output = args.output.resolve()
            output.mkdir(parents=True, exist_ok=True)
            _build_transition_previews(output)
        elif args.widgets_worker or args.widgets_only:
            from rendering.quick.bootstrap import configure_quick_graphics
            configure_quick_graphics(reason="onboarding-preview-foundry")
            output = args.output.resolve()
            output.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(prefix="srpss-onboarding-preview-") as temporary:
                widgets = _build_widget_previews(output, Path(temporary), families=args.family)
            if args.widgets_only:
                print(json.dumps({"widgets": widgets}, indent=2))
        _raise_if_guard_attempts(audit_log)
        return 0

    if args.audit_log is not None:
        return run_guarded(args.audit_log.resolve())
    with tempfile.TemporaryDirectory(prefix="srpss-onboarding-guard-") as temporary:
        return run_guarded(Path(temporary) / "attempts.jsonl")


if __name__ == "__main__":
    raise SystemExit(main())
