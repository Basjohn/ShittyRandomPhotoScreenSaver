"""Deterministic process bootstrap for the production Qt Quick presenter.

Environment selection is deliberately separated from Qt configuration so the
render loop and QML root can be fixed before importing Qt.  Graphics and
surface selection must still happen before QApplication and before any Quick
window or scene graph is created.

The one backend owner (D10 point 1, Current_Plan.md item 8b N2.7). This module chooses the process's Qt Quick
graphics backend once, and every answer about it comes from here (:func:`active_quick_backend`):

- OpenGL is the product path, unchanged. Vulkan is the rehearsal path, asked for only by the diagnostic switch
  ``--graphics-backend=vulkan`` (``core.diagnostics.experiment_flags``; never an environment variable) and run by
  the lead, bounded, on Display 1. After the flip the same owner reads a setting instead.
- On Vulkan every product Qt Quick window renders on a device of the native core's, given to it before its first
  show (D6 points 1 and 2: :func:`host_or_quit_quick_window`); the process's Vulkan instance is the module's, made
  after the application and before any window (:func:`start_quick_backend`).
- The start-up fallback (D6 point 5): a Vulkan start that cannot load the module or create the instance runs on
  OpenGL at once, before any window exists, and says so. A Vulkan start that did not complete (a handled failure,
  or a process that died before its first frame, as a driver crashing at device creation would leave it) is
  remembered in one owned place, a small record per start in the state folder beside the settings
  (``<data root>/state/graphics_backend/``), and the next start runs on OpenGL and says why; the one after tries
  Vulkan again. There is never a teardown from Vulkan to OpenGL in a running process.
- A hidden host of the native core is created once per process and kept (facts J1: Qt's threaded render control
  keeps 2 handles and 1 USER object per create and destroy on OpenGL): :func:`native_hidden_host`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import threading
from typing import Any
import weakref


QUICK_RENDER_LOOP = "threaded"
QUICK_OPENGL_VERSION = (4, 6)
QUICK_GLSL_VERSION = (4, 60)
QUICK_SWAP_INTERVAL = 0
QUICK_QML_IMPORT_ENV = "QML_IMPORT_PATH"
#: The Qt Quick backends the owner can run (``--graphics-backend`` names the same pair).
QUICK_BACKENDS = ("opengl", "vulkan")
_QT_GRAPHICS_API_NAMES = {"opengl": "OpenGL", "vulkan": "Vulkan"}
#: The start records' folder under the state folder, and the prefix of each record (one file per Vulkan start).
START_RECORD_FOLDER = "graphics_backend"
START_RECORD_PREFIX = "vulkan_start_"

# These are the 4.6 foundation primitives used by scene3d consumers or admitted
# for its next slices. Naming them here makes startup rejection and the diagnostic
# record explicit without adding extension scans or frame-time driver queries.
_REQUIRED_GL_ENTRY_POINTS: dict[str, tuple[str, ...]] = {
    "direct_state_access": (
        "glCreateBuffers",
        "glNamedBufferStorage",
        "glNamedBufferSubData",
        "glCreateVertexArrays",
        "glVertexArrayVertexBuffer",
        "glEnableVertexArrayAttrib",
        "glVertexArrayAttribFormat",
        "glVertexArrayAttribBinding",
        "glCreateTextures",
        "glTextureStorage2D",
        "glProgramUniform1i",
        "glBindTextures",
        "glBindTextureUnit",
        "glTextureStorage2DMultisample",
        "glTextureParameteri",
        "glGenerateTextureMipmap",
        "glCreateFramebuffers",
        "glNamedFramebufferTexture",
        "glNamedFramebufferDrawBuffers",
        "glCheckNamedFramebufferStatus",
        "glCreateRenderbuffers",
        "glNamedRenderbufferStorageMultisample",
        "glNamedFramebufferRenderbuffer",
    ),
    "immutable_storage": ("glTexStorage2D", "glBufferStorage"),
    "shader_storage_buffers": ("glBindBufferBase",),
    "persistent_streaming": (
        "glMapNamedBufferRange",
        "glBindBuffersRange",
        "glBindBuffersBase",
        "glFenceSync",
        "glClientWaitSync",
        "glDeleteSync",
    ),
    "compute": ("glDispatchCompute", "glMemoryBarrier", "glBindImageTexture"),
}
_validated_contexts_lock = threading.Lock()
_validated_contexts: dict[
    int,
    tuple[weakref.ReferenceType[Any], "QuickOpenGLRuntimeInfo"],
] = {}
# (vendor, renderer) of the last validated production context. Unlike the context cache it
# outlives the windows, so Settings (opened after they close) and the 3D Detail ``Auto``
# resolution still know the GPU. One reference assignment; readers take it as is.
_last_validated_gpu: tuple[str, str] | None = None


def last_validated_gpu() -> tuple[str, str] | None:
    """(GL vendor, GL renderer) of the last validated context, or None before the first."""
    return _last_validated_gpu


@dataclass(frozen=True)
class QuickBootstrapState:
    """Resolved process-level presentation configuration."""

    render_loop: str
    graphics_api: str
    qml_root: Path
    surface_format: Any
    surface_preferences: Any


@dataclass(frozen=True)
class QuickOpenGLRuntimeInfo:
    """One actual production-context OpenGL capability record."""

    requested_gl: tuple[int, int]
    requested_glsl: tuple[int, int]
    actual_gl: tuple[int, int]
    actual_glsl: tuple[int, int]
    vendor: str
    renderer: str
    capabilities: tuple[tuple[str, bool], ...]


def _gl_text(value: object) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value or "")


def _gl_version(value: str, *, label: str) -> tuple[int, int]:
    match = re.search(r"(\d+)\.(\d+)", value)
    if match is None:
        raise RuntimeError(f"OpenGL {label} version was not reported: {value!r}")
    return int(match.group(1)), int(match.group(2))


def _has_resolved_entry_point(gl_api: Any, name: str) -> bool:
    """Reject PyOpenGL's callable-but-unresolved null entry-point wrappers."""

    entry_point = getattr(gl_api, name, None)
    try:
        return callable(entry_point) and bool(entry_point)
    except Exception:
        return False


def _retire_validated_context(
    context_key: int,
    context_ref: weakref.ReferenceType[Any],
) -> None:
    """Forget one exact context wrapper without disturbing a reused key."""

    with _validated_contexts_lock:
        entry = _validated_contexts.get(context_key)
        if entry is not None and entry[0] is context_ref:
            _validated_contexts.pop(context_key, None)


def validate_current_opengl_context(
    *,
    reason: str,
    context: Any | None = None,
    gl_api: Any | None = None,
) -> QuickOpenGLRuntimeInfo:
    """Log and enforce the actual current 4.6-Core production context once.

    Call only at an existing render-thread context-initialisation boundary. This
    queries driver state once per context; it is intentionally never a frame
    path or a compatibility/fallback selector.
    """

    if context is None:
        from PySide6.QtGui import QOpenGLContext

        context = QOpenGLContext.currentContext()
    if context is None:
        raise RuntimeError(
            f"OpenGL 4.6 Core validation has no current context ({reason})"
        )

    context_key = id(context)
    destroyed = getattr(context, "destroyed", None)
    try:
        probe_ref = weakref.ref(context)
    except TypeError:
        probe_ref = None
    can_cache = probe_ref is not None and callable(getattr(destroyed, "connect", None))
    if can_cache:
        with _validated_contexts_lock:
            cached = _validated_contexts.get(context_key)
            if cached is not None:
                cached_ref, cached_result = cached
                if cached_ref() is context:
                    return cached_result
                # A wrapper can disappear before the C++ context emits
                # destroyed. Never let an id-reused wrapper inherit its record.
                if _validated_contexts.get(context_key) is cached:
                    _validated_contexts.pop(context_key, None)

    if gl_api is None:
        from OpenGL import GL as gl_api

    actual_gl_text = _gl_text(gl_api.glGetString(gl_api.GL_VERSION))
    actual_glsl_text = _gl_text(gl_api.glGetString(gl_api.GL_SHADING_LANGUAGE_VERSION))
    vendor = _gl_text(gl_api.glGetString(gl_api.GL_VENDOR))
    renderer = _gl_text(gl_api.glGetString(gl_api.GL_RENDERER))
    actual_gl = _gl_version(actual_gl_text, label="driver")
    actual_glsl = _gl_version(actual_glsl_text, label="shading-language")

    fmt = context.format()
    profile_name = getattr(fmt.profile(), "name", str(fmt.profile()))
    context_version = (int(fmt.majorVersion()), int(fmt.minorVersion()))
    capabilities = tuple(
        (name, all(_has_resolved_entry_point(gl_api, entry_point) for entry_point in entry_points))
        for name, entry_points in _REQUIRED_GL_ENTRY_POINTS.items()
    )
    missing_capabilities = tuple(name for name, present in capabilities if not present)
    valid = (
        context_version >= QUICK_OPENGL_VERSION
        and actual_gl >= QUICK_OPENGL_VERSION
        and actual_glsl >= QUICK_GLSL_VERSION
        and profile_name == "CoreProfile"
        and not missing_capabilities
    )
    if not valid:
        details = (
            f"requested_gl={QUICK_OPENGL_VERSION[0]}.{QUICK_OPENGL_VERSION[1]} "
            f"requested_glsl={QUICK_GLSL_VERSION[0]}.{QUICK_GLSL_VERSION[1]:02d} "
            f"context_gl={context_version[0]}.{context_version[1]} "
            f"actual_gl={actual_gl_text or '<missing>'} "
            f"actual_glsl={actual_glsl_text or '<missing>'} "
            f"profile={profile_name} vendor={vendor or '<missing>'} "
            f"renderer={renderer or '<missing>'} "
            f"missing_capabilities={','.join(missing_capabilities) or '<none>'}"
        )
        from core.logging.logger import get_logger

        get_logger(__name__).critical(
            "[QUICK_GL] OpenGL 4.6 Core production requirement failed reason=%s %s",
            reason,
            details,
        )
        raise RuntimeError(
            "OpenGL 4.6 Core production requirement was not met; no renderer "
            f"fallback is available ({details})"
        )

    result = QuickOpenGLRuntimeInfo(
        requested_gl=QUICK_OPENGL_VERSION,
        requested_glsl=QUICK_GLSL_VERSION,
        actual_gl=actual_gl,
        actual_glsl=actual_glsl,
        vendor=vendor,
        renderer=renderer,
        capabilities=capabilities,
    )
    global _last_validated_gpu
    _last_validated_gpu = (vendor, renderer)
    if can_cache:
        # Both callbacks capture only the weak reference and integer key. Their
        # identity check prevents a delayed former wrapper/context callback from
        # deleting a newer wrapper's entry when Python recycles an object id.
        context_ref = weakref.ref(
            context,
            lambda retired_ref: _retire_validated_context(context_key, retired_ref),
        )
        destroyed.connect(
            lambda *_args: _retire_validated_context(context_key, context_ref)
        )
        with _validated_contexts_lock:
            _validated_contexts[context_key] = (context_ref, result)

    from core.logging.logger import get_logger

    get_logger(__name__).info(
        "[QUICK_GL] validated reason=%s requested_gl=%s.%s requested_glsl=%s.%02d "
        "actual_gl=%s actual_glsl=%s vendor=%s renderer=%s capabilities=%s",
        reason,
        QUICK_OPENGL_VERSION[0],
        QUICK_OPENGL_VERSION[1],
        QUICK_GLSL_VERSION[0],
        QUICK_GLSL_VERSION[1],
        actual_gl_text,
        actual_glsl_text,
        vendor,
        renderer,
        ",".join(f"{name}={present}" for name, present in capabilities),
    )
    return result


def validate_or_quit_current_opengl_context(
    *,
    reason: str,
    context: Any | None = None,
    gl_api: Any | None = None,
) -> QuickOpenGLRuntimeInfo:
    """Fail closed through the established queued quit authority on incompatibility."""

    try:
        return validate_current_opengl_context(
            reason=reason,
            context=context,
            gl_api=gl_api,
        )
    except Exception:
        # A Python virtual callback failure can otherwise leave an empty Quick
        # window alive. Queue native application termination so no renderer
        # fallback or blank presentation continues after a floor rejection.
        from core.logging.logger import get_logger
        from engine.runtime_destruction import request_application_quit

        get_logger(__name__).critical(
            "[QUICK_GL] terminating after OpenGL 4.6 Core validation failure "
            "reason=%s",
            reason,
            exc_info=True,
        )
        request_application_quit("quick_gl_capability_incompatible")
        raise


def quick_qml_root() -> Path:
    """Return the package-owned root for runtime QML data and imports."""

    return Path(__file__).resolve().parent / "qml"


def _prepend_environment_path(name: str, path: Path) -> None:
    resolved = str(path.resolve())
    existing = [part for part in os.environ.get(name, "").split(os.pathsep) if part]
    resolved_key = os.path.normcase(os.path.normpath(resolved))
    if any(
        os.path.normcase(os.path.normpath(part)) == resolved_key
        for part in existing
    ):
        return
    os.environ[name] = os.pathsep.join((resolved, *existing))


def configure_quick_environment() -> Path:
    """Fix the Quick render loop and package QML root before Qt startup."""

    root = quick_qml_root()
    if not root.is_dir():
        raise RuntimeError(f"Qt Quick QML root is unavailable: {root}")

    # This is a production architecture choice, not a user/runtime fallback.
    os.environ["QSG_RENDER_LOOP"] = QUICK_RENDER_LOOP
    _prepend_environment_path(QUICK_QML_IMPORT_ENV, root)
    return root


def configure_quick_graphics(
    *,
    reason: str = "quick-bootstrap",
    backend: str | None = None,
    start_state_dir: Path | None = None,
) -> QuickBootstrapState:
    """Select the production Quick graphics API and global surface format.

    This function intentionally fails if a Qt application already exists.  A
    late call could leave an already-created Quick scene on a different render
    loop, graphics API, or surface format and would make the process topology
    nondeterministic.

    The backend is the owner's choice (:func:`active_quick_backend`): ``backend`` names the request, else the
    diagnostic switch does (``--graphics-backend``), else OpenGL. Every backend gets the same OpenGL surface format
    and application attributes, so a Vulkan start that falls back before any window exists runs exactly the OpenGL
    product configuration. ``start_state_dir`` is where Vulkan start records live (the product's state folder when
    None; tests name their own).
    """

    qml_root = configure_quick_environment()

    # Keep these imports local: configure_quick_environment() must be callable
    # before the process imports Qt at all.
    from PySide6.QtCore import QCoreApplication, Qt
    from PySide6.QtGui import QSurfaceFormat
    from PySide6.QtQuick import QQuickWindow, QSGRendererInterface

    if QCoreApplication.instance() is not None:
        raise RuntimeError(
            "Qt Quick graphics bootstrap must run before QApplication creation"
        )

    chosen = _choose_quick_backend(backend, start_state_dir)

    from rendering.gl_format import build_surface_format

    QCoreApplication.setAttribute(
        Qt.ApplicationAttribute.AA_UseDesktopOpenGL,
        True,
    )
    QCoreApplication.setAttribute(
        Qt.ApplicationAttribute.AA_ShareOpenGLContexts,
        True,
    )

    surface_format, surface_preferences = build_surface_format(reason=reason)
    surface_format.setRenderableType(QSurfaceFormat.RenderableType.OpenGL)
    surface_format.setVersion(*QUICK_OPENGL_VERSION)
    surface_format.setProfile(QSurfaceFormat.OpenGLContextProfile.CoreProfile)
    # Keep the established Quick-era uncapped swap policy. Installed two-display
    # validation rejected forcing swapInterval=1: mixed-refresh presentation lost
    # headroom and user-visible pacing/interactivity regressed materially. The
    # display-local Quick pacer and scene demand remain the presentation owners.
    surface_format.setSwapInterval(QUICK_SWAP_INTERVAL)
    QSurfaceFormat.setDefaultFormat(surface_format)

    if chosen.api == "vulkan":
        QQuickWindow.setGraphicsApi(QSGRendererInterface.GraphicsApi.Vulkan)
    else:
        QQuickWindow.setGraphicsApi(QSGRendererInterface.GraphicsApi.OpenGL)

    return QuickBootstrapState(
        render_loop=os.environ["QSG_RENDER_LOOP"],
        graphics_api=chosen.qt_graphics_api,
        qml_root=qml_root,
        surface_format=surface_format,
        surface_preferences=surface_preferences,
    )


# ------------------------------------------------------------------------------------------- the backend owner (N2.7)


@dataclass(frozen=True)
class QuickBackend:
    """The Qt Quick graphics backend this process runs: the one owner's answer (D10 point 1)."""

    api: str = "opengl"          # what the process runs: one of QUICK_BACKENDS
    requested: str = "opengl"    # what was asked for (the diagnostic switch; OpenGL without it)
    reason: str = ""             # why ``api`` is not ``requested``; "" when it is

    @property
    def qt_graphics_api(self) -> str:
        """Qt's name for it (``QSGRendererInterface.GraphicsApi``)."""
        return _QT_GRAPHICS_API_NAMES[self.api]

    @property
    def fell_back(self) -> bool:
        return self.api != self.requested


class _BackendOwner:
    """The owner's process state. GUI thread only (start-up, window creation, the queued completion edge)."""

    def __init__(self) -> None:
        self.backend = QuickBackend()
        self.started = False
        self.record: Path | None = None          # this process's Vulkan start record while it is pending
        self.core: Any = None                    # rendering.native.NativeCore, once loaded
        self.window_hosts: dict[int, Any] = {}   # host handle -> rendering.native.WindowHost
        self.completion: Any = None              # the QObject receiving the first presented frame
        self.completion_windows: list[weakref.ReferenceType[Any]] = []
        self.hidden_host: Any = None
        self.hidden_host_size: tuple[int, int, float] | None = None
        self.hidden_hosts_created = 0
        self.quit_edge_connected = False


_owner = _BackendOwner()


def active_quick_backend() -> QuickBackend:
    """The backend this process runs (OpenGL until the owner chose otherwise)."""
    return _owner.backend


def quick_backend_api() -> str:
    """``"opengl"`` or ``"vulkan"``: the capability registries' "available on this backend" reads this."""
    return _owner.backend.api


def reset_quick_backend_for_testing() -> None:
    """Forget the owner's choice (tests of the owner only; a process chooses once)."""
    global _owner
    _owner = _BackendOwner()


def _logger():
    from core.logging.logger import get_logger

    return get_logger(__name__)


def _start_record_folder(state_dir: Path | None) -> Path:
    if state_dir is None:
        from core.settings.storage_paths import get_state_dir

        state_dir = get_state_dir()
    folder = Path(state_dir) / START_RECORD_FOLDER
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def _process_created(pid: int) -> float | None:
    """The creation time of the live process ``pid``, or None when no such process runs."""
    import psutil

    try:
        return float(psutil.Process(int(pid)).create_time())
    except (psutil.Error, ValueError, OverflowError):
        return None


def _write_record(path: Path, record: dict[str, Any]) -> None:
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(record, sort_keys=True), encoding="utf-8")
    os.replace(temporary, path)


def _consume_unfinished_starts(folder: Path) -> list[dict[str, Any]]:
    """Every remembered Vulkan start that did not complete, oldest first; each is read once and removed (the next
    start runs OpenGL, the one after tries Vulkan again). A pending record whose process still runs is another
    start in progress, not a failure, and is left alone."""
    unfinished: list[dict[str, Any]] = []
    for path in sorted(folder.glob(f"{START_RECORD_PREFIX}*.json")):
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(record, dict):
                raise ValueError("not a record")
        except (OSError, ValueError):
            record = {"state": "unreadable", "started": "", "reason": f"its record {path.name} cannot be read"}
        if record.get("state") == "pending":
            created = _process_created(record.get("pid", -1))
            if created is not None and abs(created - float(record.get("process_created", 0.0))) < 1.0:
                continue
            record["reason"] = "the process ended before its first frame"
        unfinished.append(record)
        try:
            path.unlink()
        except FileNotFoundError:
            pass
    unfinished.sort(key=lambda item: str(item.get("started", "")))
    return unfinished


def _choose_quick_backend(backend: str | None, state_dir: Path | None) -> QuickBackend:
    if backend is None:
        from core.diagnostics.experiment_flags import graphics_backend_request

        backend = graphics_backend_request()
    requested = str(backend or "opengl").strip().lower()
    if requested not in QUICK_BACKENDS:
        raise ValueError(f"unknown Qt Quick backend {backend!r} (the backends are {', '.join(QUICK_BACKENDS)})")
    if requested == "opengl":
        _owner.backend = QuickBackend()
        return _owner.backend
    folder = _start_record_folder(state_dir)
    unfinished = _consume_unfinished_starts(folder)
    if unfinished:
        last = unfinished[-1]
        reason = (f"the Vulkan start of {last.get('started') or 'an earlier run'} did not complete "
                  f"({last.get('reason') or 'no reason recorded'})")
        _owner.backend = QuickBackend("opengl", requested, reason)
        _logger().warning("[QUICK_BACKEND] Starting on OpenGL instead of Vulkan: %s; the next start tries Vulkan "
                          "again", reason)
        return _owner.backend
    record = folder / f"{START_RECORD_PREFIX}{os.getpid()}.json"
    _write_record(record, {
        "backend": "vulkan",
        "state": "pending",
        "pid": os.getpid(),
        "process_created": _process_created(os.getpid()) or 0.0,
        "started": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "reason": "",
    })
    _owner.record = record
    _owner.backend = QuickBackend("vulkan", requested)
    _logger().info("[QUICK_BACKEND] Vulkan requested (diagnostic rehearsal path); start record %s", record)
    return _owner.backend


def _record_failed_start(reason: str) -> None:
    record = _owner.record
    if record is None:
        return
    try:
        current = json.loads(record.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        current = {"backend": "vulkan", "pid": os.getpid()}
    current.update(state="failed", reason=reason)
    _write_record(record, current)
    _owner.record = None


def _forget_start_record(how: str) -> None:
    """The start completed (or the process quit cleanly): its record goes."""
    record, _owner.record = _owner.record, None
    if record is None:
        return
    try:
        record.unlink()
    except FileNotFoundError:
        pass
    _logger().info("[QUICK_BACKEND] Vulkan start complete (%s)", how)


def _native_module_dir() -> Path | None:
    """Where the native core is loaded from: the package (the product build and a frozen build carry it there), else
    a source checkout's ``release/native_module`` (where a GitHub build of the module lands)."""
    import importlib.util

    try:
        if importlib.util.find_spec("rendering.native._srpss_native_core") is not None:
            return None
    except (ImportError, ValueError):
        pass
    candidate = Path(__file__).resolve().parents[2] / "release" / "native_module"
    return candidate if candidate.is_dir() else None


def _load_native_core() -> Any:
    from rendering.native import load

    return load(_native_module_dir())


def _fall_back_before_any_window(reason: str) -> None:
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQuick import QQuickWindow, QSGRendererInterface

    if any(isinstance(window, QQuickWindow) for window in QGuiApplication.allWindows()):
        # Never a teardown from Vulkan to OpenGL in a running process (D6 point 5): too late to change.
        _record_failed_start(reason)
        raise RuntimeError(f"the Vulkan start failed after a Qt Quick window exists ({reason})")
    QQuickWindow.setGraphicsApi(QSGRendererInterface.GraphicsApi.OpenGL)
    requested = _owner.backend.requested
    _owner.backend = QuickBackend("opengl", requested, f"the Vulkan start failed: {reason}")
    _record_failed_start(reason)
    _logger().warning("[QUICK_BACKEND] Vulkan start failed (%s): this process runs on OpenGL, and so does the next "
                      "start", reason)


def start_quick_backend(*, load_core: Any = None) -> QuickBackend:
    """After the application and before any Qt Quick window: on Vulkan, load the native core and create the process
    instance (D6 point 1). A failure falls back to OpenGL here, before any window exists, and is remembered.
    ``load_core`` returns the ``rendering.native.NativeCore`` to use (tests and tools; the product loads its own).
    On OpenGL nothing happens. Returns the backend the process runs."""
    backend = _owner.backend
    if backend.api != "vulkan" or _owner.started:
        return _owner.backend
    from PySide6.QtCore import QCoreApplication

    app = QCoreApplication.instance()
    if app is None:
        raise RuntimeError("the Qt Quick backend starts after the application is created")
    _owner.started = True
    _connect_quit_edge(app)
    try:
        core = (load_core or _load_native_core)()
        created = core.vulkan_instance()
        if not created.get("ok"):
            detail = created.get("error") or dict(created.get("instance") or {}).get("error") or "no reason given"
            raise RuntimeError(f"the native core's Vulkan instance was not created: {detail}")
    except Exception as exc:
        _fall_back_before_any_window(str(getattr(exc, "reason", "") or exc))
        return _owner.backend
    _owner.core = core
    _logger().info("[QUICK_BACKEND] Vulkan: the native core %s (Qt %s) owns the instance; windows render on its "
                   "devices", core.version, core.qt_version)
    return _owner.backend


def _connect_quit_edge(app: Any) -> None:
    if not _owner.quit_edge_connected:
        _owner.quit_edge_connected = True
        app.aboutToQuit.connect(_on_about_to_quit)


def _on_about_to_quit() -> None:
    # The kept hidden host goes with the process, before Qt's own teardown (its render thread is the core's).
    host, _owner.hidden_host = _owner.hidden_host, None
    if host is not None:
        host.close()
    # A process that quits cleanly did not fail its start, whether or not a frame was presented.
    _forget_start_record("the process quit cleanly")


def _completion_receiver() -> Any:
    if _owner.completion is None:
        from PySide6.QtCore import QObject, Slot

        class _StartCompletion(QObject):
            """Receives the first frame a hosted window presented (queued from the render thread)."""

            @Slot()
            def frame_presented(self) -> None:
                _complete_start("first frame presented")

        _owner.completion = _StartCompletion()
    return _owner.completion


def _complete_start(how: str) -> None:
    receiver = _owner.completion
    windows, _owner.completion_windows = _owner.completion_windows, []
    for window_ref in windows:
        window = window_ref()
        if window is None or receiver is None:
            continue
        try:
            window.frameSwapped.disconnect(receiver.frame_presented)
        except (RuntimeError, TypeError):
            pass
    _forget_start_record(how)


def _close_window_host(handle: int) -> None:
    host = _owner.window_hosts.pop(handle, None)
    if host is not None:
        host.close()


def host_quick_window(window: Any) -> Any:
    """On Vulkan: hand ``window`` (a product ``QQuickWindow``, before its first show) to the native core, whose
    device it then renders on (D6); returns its ``rendering.native.WindowHost``, closed when the window is destroyed.
    The first frame any hosted window presents completes the Vulkan start. On OpenGL nothing happens (None). A failure
    is remembered (the next start runs OpenGL) and raised."""
    if _owner.backend.api != "vulkan":
        return None
    core = _owner.core
    try:
        if core is None:
            raise RuntimeError("no native core: start_quick_backend() runs after the application and before any "
                               "window (D6 point 1)")
        host = core.attach_host(window)
    except Exception as exc:
        reason = f"the window could not be hosted on the native core's device: {exc}"
        _record_failed_start(reason)
        _logger().critical("[QUICK_BACKEND] %s; the next start runs on OpenGL", reason)
        raise RuntimeError(reason) from exc
    from functools import partial
    from PySide6.QtCore import Qt

    _owner.window_hosts[host.handle] = host
    window.destroyed.connect(partial(_close_window_host, host.handle))
    if _owner.record is not None:
        receiver = _completion_receiver()
        window.frameSwapped.connect(receiver.frame_presented, Qt.ConnectionType.QueuedConnection)
        _owner.completion_windows.append(weakref.ref(window))
    return host


def host_or_quit_quick_window(window: Any, *, reason: str) -> Any:
    """:func:`host_quick_window` failing closed through the established queued quit authority, as the OpenGL
    validation does: no window renders on a device that is not the module's."""
    try:
        return host_quick_window(window)
    except Exception:
        from engine.runtime_destruction import request_application_quit

        _logger().critical("[QUICK_BACKEND] terminating after a failed Vulkan window host reason=%s", reason,
                           exc_info=True)
        request_application_quit("quick_backend_window_host_failed")
        raise


def native_hidden_host(width: int, height: int, *, dpr: float = 1.0) -> Any:
    """The process's one hidden host of the native core (``rendering.native.HiddenHost``), created at the first
    request and kept, never one per use (facts J1). It renders ``width`` x ``height`` device pixels at ``dpr``; a
    request for another size is refused (the host is never rebuilt). On Vulkan it needs the started backend."""
    size = (int(width), int(height), float(dpr))
    host = _owner.hidden_host
    if host is not None and not host.closed:
        if size != _owner.hidden_host_size:
            raise ValueError(f"the process's hidden host renders {_owner.hidden_host_size}, not {size}; it is "
                             "created once and kept")
        return host
    core = _owner.core
    if core is None:
        if _owner.backend.api == "vulkan":
            raise RuntimeError("the Vulkan backend has not started: start_quick_backend() comes first")
        core = _load_native_core()
        _owner.core = core
    from PySide6.QtCore import QCoreApplication

    app = QCoreApplication.instance()
    if app is None:
        raise RuntimeError("a hidden host needs the application")
    host = core.hidden_host(size[0], size[1], dpr=size[2])
    _owner.hidden_host, _owner.hidden_host_size = host, size
    _owner.hidden_hosts_created += 1
    _connect_quit_edge(app)          # it is closed when the application quits, never earlier
    return host
