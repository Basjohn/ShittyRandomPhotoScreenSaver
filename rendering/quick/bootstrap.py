"""Deterministic process bootstrap for the production Qt Quick presenter.

Environment selection is deliberately separated from Qt configuration so the
render loop and QML root can be fixed before importing Qt.  Graphics and
surface selection must still happen before QApplication and before any Quick
window or scene graph is created.
"""

from __future__ import annotations

from dataclasses import dataclass
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

# These are the foundation primitives planned immediately after the 4.6 floor.
# They are core in a real 4.6 context; naming them here makes startup rejection
# and the diagnostic record explicit without adding extension scans or frame-time
# driver queries.
_REQUIRED_GL_ENTRY_POINTS: dict[str, tuple[str, ...]] = {
    "direct_state_access": (
        "glCreateBuffers",
        "glNamedBufferStorage",
        "glCreateTextures",
        "glTextureStorage2D",
    ),
    "immutable_storage": ("glTexStorage2D", "glBufferStorage"),
    "shader_storage_buffers": ("glBindBufferBase",),
    "compute": ("glDispatchCompute", "glMemoryBarrier"),
    "multi_draw_indirect": ("glMultiDrawArraysIndirect",),
}
_validated_contexts_lock = threading.Lock()
_validated_contexts: dict[
    int,
    tuple[weakref.ReferenceType[Any], "QuickOpenGLRuntimeInfo"],
] = {}


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


def configure_quick_graphics(*, reason: str = "quick-bootstrap") -> QuickBootstrapState:
    """Select the production Quick graphics API and global surface format.

    This function intentionally fails if a Qt application already exists.  A
    late call could leave an already-created Quick scene on a different render
    loop, graphics API, or surface format and would make the process topology
    nondeterministic.
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

    QQuickWindow.setGraphicsApi(QSGRendererInterface.GraphicsApi.OpenGL)

    return QuickBootstrapState(
        render_loop=os.environ["QSG_RENDER_LOOP"],
        graphics_api="OpenGL",
        qml_root=qml_root,
        surface_format=surface_format,
        surface_preferences=surface_preferences,
    )
