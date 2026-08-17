"""GL Compositor Lifecycle - Extracted from gl_compositor.py.

Contains GL initialization, pipeline setup, cleanup, and shader program creation.
All functions accept the compositor widget instance as the first parameter.
"""

from __future__ import annotations

import ctypes
import sys
import time
import weakref
from typing import TYPE_CHECKING
from PySide6.QtCore import QCoreApplication, QThread
from PySide6.QtGui import QOffscreenSurface, QOpenGLContext

try:
    from OpenGL import GL as gl  # type: ignore[import]
except ImportError:
    gl = None


from core.logging.logger import get_logger, is_perf_metrics_enabled
from core.threading.manager import ThreadManager
from rendering.gl_compositor_pkg.metrics import _GLPipelineState
from rendering.gl_state_manager import GLContextState
from rendering.gl_programs.program_cache import GLProgramCache
from rendering.gl_programs.geometry_manager import GLGeometryManager
from rendering.gl_programs.texture_manager import GLTextureManager
from rendering.transition_registry import (
    iter_transition_descriptors,
    get_transition_descriptor_for_runtime_identity,
    get_transition_program_specs,
)

if TYPE_CHECKING:
    pass

logger = get_logger(__name__)


try:
    from shiboken6 import Shiboken
except Exception:  # pragma: no cover - shiboken may be unavailable in headless tooling
    Shiboken = None


def _qt_object_is_valid(obj: object | None) -> bool:
    if obj is None:
        return False
    if Shiboken is None:
        return True
    try:
        return bool(Shiboken.isValid(obj))
    except Exception:
        return True


def _live_displays_for_compositor(widget) -> list[object]:
    displays: list[object] = []
    seen: set[int] = set()

    try:
        parent = widget.parentWidget()
    except Exception:
        try:
            parent = widget.parent()
        except Exception:
            parent = None
    if parent is not None:
        displays.append(parent)
        seen.add(id(parent))

    try:
        from rendering.display_widget import DisplayWidget

        for display in DisplayWidget.get_all_instances():
            if display is None or id(display) in seen:
                continue
            displays.append(display)
            seen.add(id(display))
    except Exception:
        logger.debug(
            "[GL COMPOSITOR] Failed to enumerate displays for warmup gating",
            exc_info=True,
        )
    return displays


def _deferred_warmup_block_reason(widget) -> str | None:
    """Return the current cross-display reason an optional slice must wait."""

    for display in _live_displays_for_compositor(widget):
        if not _qt_object_is_valid(display):
            continue

        manager = getattr(display, "_widget_manager", None)
        coordinator = getattr(manager, "_fade_coordinator", None)
        if coordinator is not None:
            try:
                fade = coordinator.describe()
            except Exception:
                fade = {}
            if fade.get("startup_holds"):
                return "startup_hold"
            state = str(fade.get("state", ""))
            if state == "IDLE":
                return "first_frame"
            if state == "FADING":
                return "startup_fade"
            # READY with no pending/active fade is not work. An enabled
            # overlay can remain data-unavailable indefinitely (for example,
            # Spotify with no current session); optional warmup must not be
            # stranded waiting for a fade that has not started. Any later
            # request moves the coordinator to FADING synchronously, and the
            # next slice will pause here before touching GL.

        checker = getattr(display, "has_transition_work_pending", None)
        if callable(checker):
            try:
                if bool(checker()):
                    return "transition_work"
            except Exception:
                logger.debug(
                    "[GL COMPOSITOR] Failed to inspect transition work before warmup",
                    exc_info=True,
                )
    return None


def _startup_sequence_fields(widget) -> tuple[bool, bool, list[str], bool, bool]:
    first_frame_ready = False
    critical_gl_ready = False
    holds: list[str] = []
    fade_started = False
    fade_completed = False

    displays = _live_displays_for_compositor(widget)
    if displays:
        display = displays[0]
        manager = getattr(display, "_widget_manager", None)
        coordinator = getattr(manager, "_fade_coordinator", None)
        if coordinator is not None:
            try:
                fade = coordinator.describe()
            except Exception:
                fade = {}
            first_frame_ready = bool(fade.get("compositor_ready"))
            holds = list(fade.get("startup_holds") or [])
            critical_gl_ready = bool(
                first_frame_ready and "critical_gl_startup" not in holds
            )
            fade_started = bool(fade.get("fade_started"))
            fade_completed = bool(fade.get("fade_completed"))
    return (
        first_frame_ready,
        critical_gl_ready,
        holds,
        fade_started,
        fade_completed,
    )


def _log_startup_warmup_state(
    widget,
    *,
    deferred_gl_warmup_started: bool,
    block_reason: str | None,
) -> None:
    fields = _startup_sequence_fields(widget)
    snapshot = (*fields, bool(deferred_gl_warmup_started), block_reason)
    if snapshot == getattr(widget, "_startup_sequence_last_log", None):
        return
    widget._startup_sequence_last_log = snapshot
    logger.info(
        "[STARTUP_SEQUENCE] screen=%s first_frame_ready=%s "
        "critical_gl_ready=%s fade_holds=%s fade_started=%s "
        "fade_completed=%s deferred_gl_warmup_started=%s block_reason=%s",
        getattr(getattr(widget, "parentWidget", lambda: None)(), "screen_index", "?"),
        fields[0],
        fields[1],
        fields[2],
        fields[3],
        fields[4],
        bool(deferred_gl_warmup_started),
        block_reason or "none",
    )


def _schedule_deferred_gl_warmup(widget, callback, *, delay_ms: int = 140) -> None:
    """Schedule warmup owned by the compositor lifecycle that requested it."""
    lifecycle_generation = int(getattr(widget, "_gl_lifecycle_generation", 0))
    callback_key = getattr(callback, "__name__", repr(callback))
    armed = getattr(widget, "_deferred_gl_warmup_armed_callbacks", None)
    if not isinstance(armed, set):
        armed = set()
        widget._deferred_gl_warmup_armed_callbacks = armed
    if callback_key in armed:
        return
    armed.add(callback_key)

    widget_ref = weakref.ref(widget)

    def _run(expected_generation=lifecycle_generation) -> None:
        w = widget_ref()
        if w is None:
            return
        pending = getattr(w, "_deferred_gl_warmup_armed_callbacks", None)
        if isinstance(pending, set):
            pending.discard(callback_key)
        if not _qt_object_is_valid(w):
            logger.warning(
                "[GL COMPOSITOR][WARNING] Skipped deferred GL warmup for deleted widget callback=%s",
                getattr(callback, "__name__", repr(callback)),
            )
            return
        if (
            bool(getattr(w, "_render_shutdown_requested", False))
            or int(getattr(w, "_gl_lifecycle_generation", 0)) != expected_generation
        ):
            logger.info(
                "[LIFECYCLE] Rejected stale deferred GL warmup callback=%s generation=%d",
                getattr(callback, "__name__", repr(callback)),
                expected_generation,
            )
            return
        callback(w)

    parent = getattr(widget, "parentWidget", lambda: None)()
    _run._srpss_runtime_generation = getattr(
        parent,
        "_runtime_generation",
        None,
    )
    ThreadManager.single_shot(max(0, int(delay_ms)), _run)

def _wgl_proc_address(name: str) -> int | None:
    if sys.platform != "win32":
        return None
    try:
        opengl32 = ctypes.windll.opengl32
        getter = opengl32.wglGetProcAddress
        getter.argtypes = [ctypes.c_char_p]
        getter.restype = ctypes.c_void_p
        ptr = getter(name.encode("ascii"))
    except Exception:
        logger.debug("[GL COMPOSITOR] Failed to resolve WGL proc %s", name, exc_info=True)
        return None

    try:
        value = int(ptr or 0)
    except Exception:
        value = 0
    # Per WGL convention these tiny/sentinel values are invalid pointers.
    if value in {0, 1, 2, 3, -1}:
        return None
    return value


def _disable_current_context_swap_interval() -> tuple[bool | None, int | None, str]:
    """Best-effort WGL swap interval disable for the current Windows GL context.

    Qt's requested QSurfaceFormat can report interval=0 globally while the
    actual QOpenGLWidget context still comes up interval=1. The app's render
    contract is timer-paced, so we try the driver extension once per context and
    log the resulting truth loudly enough for perf triage.
    """

    if sys.platform != "win32":
        return None, None, "non_windows"

    swap_ptr = _wgl_proc_address("wglSwapIntervalEXT")
    if swap_ptr is None:
        return None, None, "wglSwapIntervalEXT_unavailable"

    try:
        fn_type = getattr(ctypes, "WINFUNCTYPE", ctypes.CFUNCTYPE)
        swap_interval = fn_type(ctypes.c_bool, ctypes.c_int)(swap_ptr)
        ok = bool(swap_interval(0))
    except Exception:
        logger.debug("[GL COMPOSITOR] wglSwapIntervalEXT(0) failed", exc_info=True)
        return False, None, "wglSwapIntervalEXT_call_failed"

    current: int | None = None
    get_ptr = _wgl_proc_address("wglGetSwapIntervalEXT")
    if get_ptr is not None:
        try:
            fn_type = getattr(ctypes, "WINFUNCTYPE", ctypes.CFUNCTYPE)
            get_swap_interval = fn_type(ctypes.c_int)(get_ptr)
            current = int(get_swap_interval())
        except Exception:
            logger.debug("[GL COMPOSITOR] wglGetSwapIntervalEXT failed", exc_info=True)
            current = None

    return ok, current, "wglSwapIntervalEXT"


def _transition_program_specs() -> list[tuple[str, str, str]]:
    return get_transition_program_specs()


def startup_transition_program_specs() -> list[tuple[str, str, str]]:
    """Return the small shader subset worth paying for on cold startup."""
    return get_transition_program_specs(startup_only=True)


def deferred_transition_program_specs() -> list[tuple[str, str, str]]:
    return get_transition_program_specs(startup_only=False)


def deferred_transition_resource_identities() -> list[str]:
    identities: list[str] = []
    for descriptor in iter_transition_descriptors():
        if descriptor.startup_compile:
            continue
        if descriptor.compositor_transition_class and descriptor.gl_program_key:
            identities.append(descriptor.compositor_transition_class)
    return identities


def _has_live_visible_base_surface(widget) -> bool:
    try:
        base_pixmap = getattr(widget, "_base_pixmap", None)
        has_live_base = bool(base_pixmap is not None and not base_pixmap.isNull())
    except Exception:
        has_live_base = False
    try:
        is_visible = bool(widget.isVisible())
    except Exception:
        is_visible = False
    frame_state = getattr(widget, "_frame_state", None)
    has_active_transition = bool(
        frame_state is not None
        and getattr(frame_state, "started", False)
        and not getattr(frame_state, "completed", True)
    )
    return is_visible and has_live_base and not has_active_transition


def _ensure_hidden_shared_warmup_context(
    widget,
    *,
    perf_trace: dict[str, object] | None = None,
) -> tuple[QOpenGLContext, QOffscreenSurface] | None:
    trace_enabled = perf_trace is not None
    if trace_enabled:
        perf_trace.update(
            hidden_context_reused=False,
            share_context_present=False,
            share_context_valid=False,
            offscreen_surface_create_ms=0.0,
            shared_context_create_ms=0.0,
        )
        try:
            share_context_probe = widget.context()
        except Exception:
            share_context_probe = None
        perf_trace["share_context_present"] = share_context_probe is not None
        try:
            perf_trace["share_context_valid"] = bool(
                share_context_probe is not None and share_context_probe.isValid()
            )
        except Exception:
            perf_trace["share_context_valid"] = False
    try:
        existing_ctx = getattr(widget, "_deferred_warmup_context", None)
        existing_surface = getattr(widget, "_deferred_warmup_surface", None)
        if (
            isinstance(existing_ctx, QOpenGLContext)
            and isinstance(existing_surface, QOffscreenSurface)
            and existing_ctx.isValid()
            and existing_surface.isValid()
        ):
            if trace_enabled:
                perf_trace["hidden_context_reused"] = True
            return existing_ctx, existing_surface
    except Exception:
        logger.debug("[GL COMPOSITOR] Failed to reuse deferred warmup context", exc_info=True)

    share_ctx = None
    try:
        share_ctx = widget.context()
    except Exception:
        logger.debug("[GL COMPOSITOR] Failed to access compositor context for deferred warmup", exc_info=True)
    if trace_enabled:
        perf_trace["share_context_present"] = share_ctx is not None
        try:
            perf_trace["share_context_valid"] = bool(
                share_ctx is not None and share_ctx.isValid()
            )
        except Exception:
            perf_trace["share_context_valid"] = False
    if share_ctx is None:
        return None

    surface = None
    surface_started: float | None = None
    context_started: float | None = None
    committed = False
    try:
        fmt = share_ctx.format()
        surface_started = time.perf_counter() if trace_enabled else None
        surface = QOffscreenSurface()
        surface.setFormat(fmt)
        surface.create()
        if trace_enabled and surface_started is not None:
            perf_trace["offscreen_surface_create_ms"] = (
                time.perf_counter() - surface_started
            ) * 1000.0
            surface_started = None
        if not surface.isValid():
            logger.warning("[GL COMPOSITOR] Offscreen surface creation failed for deferred warmup")
            return None

        context_started = time.perf_counter() if trace_enabled else None
        context = QOpenGLContext()
        context.setFormat(fmt)
        context.setShareContext(share_ctx)
        context_created = context.create()
        if trace_enabled and context_started is not None:
            perf_trace["shared_context_create_ms"] = (
                time.perf_counter() - context_started
            ) * 1000.0
            context_started = None
        if not context_created or not context.isValid():
            logger.warning("[GL COMPOSITOR] Shared offscreen context creation failed for deferred warmup")
            return None

        widget._deferred_warmup_context = context
        widget._deferred_warmup_surface = surface
        committed = True
        return context, surface
    except Exception:
        logger.debug("[GL COMPOSITOR] Hidden shared deferred warmup context creation failed", exc_info=True)
        return None
    finally:
        if trace_enabled and surface_started is not None:
            perf_trace["offscreen_surface_create_ms"] = (
                time.perf_counter() - surface_started
            ) * 1000.0
        if trace_enabled and context_started is not None:
            perf_trace["shared_context_create_ms"] = (
                time.perf_counter() - context_started
            ) * 1000.0
        if not committed and surface is not None:
            try:
                surface.destroy()
            except Exception:
                logger.debug(
                    "[GL COMPOSITOR] Failed to destroy deferred warmup surface",
                    exc_info=True,
                )


def acquire_safe_warmup_context(
    widget,
    *,
    fallback_label: str,
    preserve_live_surface: bool = True,
    perf_trace: dict[str, object] | None = None,
):
    """Acquire a GL context for best-effort warm work without poisoning live presentation.

    Preference order:
    1. hidden shared offscreen context
    2. compositor context only when no live visible base surface must be preserved

    Returns a zero-arg release callable when a context was acquired, otherwise ``None``.
    """

    trace_enabled = perf_trace is not None
    context_prepare_started = time.perf_counter() if trace_enabled else 0.0
    if trace_enabled:
        perf_trace["preserve_live_surface"] = bool(preserve_live_surface)
        perf_trace["live_base_visible"] = bool(
            _has_live_visible_base_surface(widget)
        )
        warmup_target = _ensure_hidden_shared_warmup_context(
            widget,
            perf_trace=perf_trace,
        )
    else:
        warmup_target = _ensure_hidden_shared_warmup_context(widget)
    if trace_enabled:
        perf_trace["context_prepare_ms"] = (
            time.perf_counter() - context_prepare_started
        ) * 1000.0
        perf_trace["hidden_context_created"] = bool(
            warmup_target is not None
            and not bool(perf_trace.get("hidden_context_reused", False))
        )
    if warmup_target is not None:
        context, surface = warmup_target
        make_current_started = time.perf_counter() if trace_enabled else 0.0
        try:
            if context.makeCurrent(surface):
                if trace_enabled:
                    perf_trace["context_route"] = "hidden_shared"
                    perf_trace["context_make_current_ms"] = (
                        time.perf_counter() - make_current_started
                    ) * 1000.0
                return context.doneCurrent
        except Exception:
            logger.debug(
                "[GL COMPOSITOR] Failed to make hidden shared context current for %s",
                fallback_label,
                exc_info=True,
            )
        if trace_enabled:
            perf_trace["context_make_current_ms"] = (
                time.perf_counter() - make_current_started
            ) * 1000.0

    if preserve_live_surface and _has_live_visible_base_surface(widget):
        if trace_enabled:
            perf_trace["context_route"] = "deferred"
        logger.warning(
            "[GL COMPOSITOR][FALLBACK] Hidden shared warmup context unavailable; "
            "deferring %s to first-use warmup to preserve live surface",
            fallback_label,
        )
        return None

    make_current_started = time.perf_counter() if trace_enabled else 0.0
    try:
        widget.makeCurrent()
        if trace_enabled:
            perf_trace["context_route"] = "compositor"
            perf_trace["context_make_current_ms"] = (
                time.perf_counter() - make_current_started
            ) * 1000.0
        return widget.doneCurrent
    except Exception:
        if trace_enabled:
            perf_trace["context_route"] = "failed"
            perf_trace["context_make_current_ms"] = (
                time.perf_counter() - make_current_started
            ) * 1000.0
        logger.debug(
            "[GL COMPOSITOR] Failed to make compositor context current for %s",
            fallback_label,
            exc_info=True,
        )
        return None


def _compile_transition_program(widget, program_name: str, program_attr: str, uniforms_attr: str) -> bool:
    cache = getattr(widget, "_program_cache", None)
    if cache is None:
        raise RuntimeError("Compositor has no local GL program owner")
    program_id = cache.get_program(program_name)
    if program_id is None:
        return False
    setattr(widget._gl_pipeline, program_attr, program_id)
    setattr(widget._gl_pipeline, uniforms_attr, cache.get_uniforms(program_name))
    return True


def _resolve_transition_program_binding(identity: object) -> tuple[str, str, str] | None:
    descriptor = get_transition_descriptor_for_runtime_identity(identity)
    if descriptor is None:
        return None
    if descriptor.program_attr is None or descriptor.uniforms_attr is None or descriptor.gl_program_key is None:
        return None
    return descriptor.gl_program_key, descriptor.program_attr, descriptor.uniforms_attr


def _bind_transition_program_for_identity(widget, identity: object) -> bool:
    binding = _resolve_transition_program_binding(identity)
    if binding is None:
        return True
    if widget._gl_pipeline is None:
        return False
    program_name, program_attr, uniforms_attr = binding
    if getattr(widget._gl_pipeline, program_attr, 0):
        return True
    return _compile_transition_program(
        widget,
        program_name,
        program_attr,
        uniforms_attr,
    )


def bind_transition_program_for_current_context(widget, identity: object) -> bool:
    """Bind shader attrs for a transition identity while the caller owns the current GL context."""
    try:
        return _bind_transition_program_for_identity(widget, identity)
    except Exception:
        logger.debug("[GL COMPOSITOR] Transition program bind failed for %s", identity, exc_info=True)
        return False


def ensure_transition_program_ready(widget, identity: object) -> bool:
    """Ensure shader program attrs are bound for a transition identity."""
    if getattr(widget, "_gl_disabled_for_session", False) or gl is None:
        return False
    if widget._gl_pipeline is None or not getattr(widget._gl_pipeline, "initialized", False):
        return False
    binding = _resolve_transition_program_binding(identity)
    if binding is None:
        return True
    _, program_attr, _ = binding
    if getattr(widget._gl_pipeline, program_attr, 0):
        return True

    try:
        widget.makeCurrent()
    except Exception:
        logger.debug("[GL COMPOSITOR] Failed to make compositor context current for transition program ensure", exc_info=True)
        return False

    try:
        return bind_transition_program_for_current_context(widget, identity)
    finally:
        try:
            widget.doneCurrent()
        except Exception:
            logger.debug("[GL COMPOSITOR] doneCurrent failed after transition program ensure", exc_info=True)


def _warm_next_transition_program(widget) -> None:
    if getattr(widget, "_gl_disabled_for_session", False):
        return
    queue = getattr(widget, "_startup_transition_warm_queue", None)
    if not queue:
        return
    block_reason = _deferred_warmup_block_reason(widget)
    if block_reason is not None:
        _log_startup_warmup_state(
            widget,
            deferred_gl_warmup_started=False,
            block_reason=block_reason,
        )
        _schedule_deferred_gl_warmup(widget, _warm_next_transition_program)
        return
    if not bool(getattr(widget, "_deferred_gl_warmup_started", False)):
        widget._deferred_gl_warmup_started = True
        _log_startup_warmup_state(
            widget,
            deferred_gl_warmup_started=True,
            block_reason=None,
        )

    release_current = acquire_safe_warmup_context(
        widget,
        fallback_label="deferred shader warmup",
        preserve_live_surface=True,
    )
    if release_current is None:
        return

    try:
        while queue:
            program_name, program_attr, uniforms_attr = queue.pop(0)
            if getattr(widget._gl_pipeline, program_attr, 0):
                continue
            if not _compile_transition_program(widget, program_name, program_attr, uniforms_attr):
                logger.debug("[GL COMPOSITOR] Deferred compile failed for %s", program_name)
            # One attempted compile is the complete slice even on failure.
            # Returning to the event loop lets newly pending fades/transitions
            # block the next shader before any more driver work begins.
            break
    finally:
        try:
            if release_current is not None:
                release_current()
        except Exception:
            logger.debug("[GL COMPOSITOR] doneCurrent failed after deferred shader warmup", exc_info=True)

    if queue:
        _schedule_deferred_gl_warmup(widget, _warm_next_transition_program)
    else:
        _schedule_deferred_transition_resource_warmup(widget)


def schedule_deferred_transition_program_warmup(widget) -> None:
    if getattr(widget, "_startup_transition_warm_queue", None):
        return
    remaining = deferred_transition_program_specs()
    if not remaining:
        _schedule_deferred_transition_resource_warmup(widget)
        return
    widget._startup_transition_warm_queue = list(remaining)
    _schedule_deferred_gl_warmup(widget, _warm_next_transition_program)


def resume_deferred_transition_warmup(widget) -> None:
    """Nudge the existing optional warmup queues after startup fade completion."""

    if getattr(widget, "_gl_disabled_for_session", False):
        return
    if getattr(widget, "_startup_transition_warm_queue", None):
        _schedule_deferred_gl_warmup(
            widget,
            _warm_next_transition_program,
            delay_ms=0,
        )
        return
    if getattr(widget, "_startup_transition_resource_warm_queue", None):
        _schedule_deferred_gl_warmup(
            widget,
            _warm_next_transition_resources,
            delay_ms=0,
        )
        return
    schedule_deferred_transition_program_warmup(widget)


def _schedule_deferred_transition_resource_warmup(widget) -> None:
    if getattr(widget, "_gl_disabled_for_session", False):
        return
    base_pixmap = getattr(widget, "_base_pixmap", None)
    if base_pixmap is None:
        return
    try:
        if base_pixmap.isNull():
            return
    except Exception:
        return
    if getattr(widget, "_startup_transition_warm_queue", None):
        return

    warmed = getattr(widget, "_startup_transition_resource_warm_types", None)
    if not isinstance(warmed, set):
        warmed = set()
        widget._startup_transition_resource_warm_types = warmed

    if getattr(widget, "_startup_transition_resource_warm_queue", None):
        return

    remaining = [
        identity
        for identity in deferred_transition_resource_identities()
        if identity not in warmed
    ]
    if not remaining:
        return

    widget._startup_transition_resource_warm_queue = list(remaining)
    _schedule_deferred_gl_warmup(widget, _warm_next_transition_resources)


def _warm_next_transition_resources(widget) -> None:
    if getattr(widget, "_gl_disabled_for_session", False):
        return
    if getattr(widget, "_startup_transition_warm_queue", None):
        _schedule_deferred_gl_warmup(widget, _warm_next_transition_resources)
        return

    queue = getattr(widget, "_startup_transition_resource_warm_queue", None)
    if not queue:
        return
    block_reason = _deferred_warmup_block_reason(widget)
    if block_reason is not None:
        _log_startup_warmup_state(
            widget,
            deferred_gl_warmup_started=False,
            block_reason=block_reason,
        )
        _schedule_deferred_gl_warmup(widget, _warm_next_transition_resources)
        return
    if not bool(getattr(widget, "_deferred_gl_warmup_started", False)):
        widget._deferred_gl_warmup_started = True
        _log_startup_warmup_state(
            widget,
            deferred_gl_warmup_started=True,
            block_reason=None,
        )

    base_pixmap = getattr(widget, "_base_pixmap", None)
    if base_pixmap is None:
        widget._startup_transition_resource_warm_queue = []
        return
    try:
        if base_pixmap.isNull():
            widget._startup_transition_resource_warm_queue = []
            return
    except Exception:
        widget._startup_transition_resource_warm_queue = []
        return

    warmed = getattr(widget, "_startup_transition_resource_warm_types", None)
    if not isinstance(warmed, set):
        warmed = set()
        widget._startup_transition_resource_warm_types = warmed

    release_current = acquire_safe_warmup_context(
        widget,
        fallback_label="deferred resource warmup",
        preserve_live_surface=True,
    )
    if release_current is None:
        return

    try:
        while queue:
            identity = queue.pop(0)
            if identity in warmed:
                continue
            if not bind_transition_program_for_current_context(widget, identity):
                logger.debug("[GL COMPOSITOR] Deferred transition resource warmup could not bind %s", identity)
                break
            try:
                textures_ready = widget._warm_pixmap_textures_in_current_context(base_pixmap, base_pixmap)
                state_ready = textures_ready and widget._warm_transition_state_in_current_context(
                    identity,
                    base_pixmap,
                    base_pixmap,
                )
            except Exception:
                logger.debug("[GL COMPOSITOR] Deferred transition resource warmup failed for %s", identity, exc_info=True)
                break
            if textures_ready and state_ready:
                warmed.add(identity)
            break
    finally:
        try:
            if release_current is not None:
                release_current()
        except Exception:
            logger.debug("[GL COMPOSITOR] doneCurrent failed after deferred resource warmup", exc_info=True)

    if queue:
        _schedule_deferred_gl_warmup(widget, _warm_next_transition_resources)


def handle_initializeGL(widget) -> None:  # type: ignore[override]
    """Initialize GL state for the compositor.

    Sets up logging and prepares the internal pipeline container. In this
    phase the shader program and fullscreen quad geometry are created when
    OpenGL is available, but all drawing still goes through QPainter until
    later phases explicitly enable the shader path.
    """
    # Transition to INITIALIZING state
    if not widget._gl_state.transition(GLContextState.INITIALIZING):
        logger.warning("[GL COMPOSITOR] Failed to transition to INITIALIZING state")
        return

    try:
        ctx = widget.context()
        swap_disable_ok: bool | None = None
        swap_disable_current: int | None = None
        swap_disable_source = "not_attempted"
        if ctx is not None:
            swap_disable_ok, swap_disable_current, swap_disable_source = _disable_current_context_swap_interval()
            fmt = ctx.format()
            requested_interval = 0
            try:
                requested_interval = int(getattr(widget, "format")().swapInterval())
            except Exception:
                requested_interval = 0
            logger.info(
                "[GL COMPOSITOR] Context initialized: version=%s.%s, swap=%s, interval=%s, requested_interval=%s, wgl_swap_disable=%s, wgl_current_interval=%s, wgl_source=%s",
                fmt.majorVersion(),
                fmt.minorVersion(),
                fmt.swapBehavior(),
                fmt.swapInterval(),
                requested_interval,
                swap_disable_ok,
                swap_disable_current,
                swap_disable_source,
            )
            try:
                format_interval = int(fmt.swapInterval())
                if swap_disable_current is not None:
                    interval_still_constrained = int(swap_disable_current) != 0
                else:
                    interval_still_constrained = swap_disable_ok is not True and format_interval != 0
                if interval_still_constrained:
                    logger.warning(
                        "[PERF][GL COMPOSITOR][WARNING] GL context may still be swap-interval constrained "
                        "format_interval=%s requested_interval=%s wgl_disable=%s wgl_current=%s source=%s "
                        "policy=timer_capped_no_vsync",
                        format_interval,
                        requested_interval,
                        swap_disable_ok,
                        swap_disable_current,
                        swap_disable_source,
                    )
            except Exception:
                pass

        # Log adapter information and detect obvious software GL drivers so
        # shader-backed paths can be disabled proactively. QPainter-based
        # compositor transitions remain available as the safe fallback.
        if gl is not None:
            try:
                vendor_bytes = gl.glGetString(gl.GL_VENDOR)
                renderer_bytes = gl.glGetString(gl.GL_RENDERER)
                version_bytes = gl.glGetString(gl.GL_VERSION)

                def _decode_gl_string(val: object) -> str:
                    if isinstance(val, (bytes, bytearray)):
                        try:
                            return val.decode("ascii", "ignore")
                        except Exception as e:
                            logger.debug("[GL COMPOSITOR] Exception suppressed: %s", e)
                            return ""
                    return str(val) if val is not None else ""

                vendor = _decode_gl_string(vendor_bytes)
                renderer = _decode_gl_string(renderer_bytes)
                version_str = _decode_gl_string(version_bytes)
                logger.info(
                    "[GL COMPOSITOR] OpenGL adapter: vendor=%s, renderer=%s, version=%s",
                    vendor or "?",
                    renderer or "?",
                    version_str or "?",
                )

                # Record GL info in centralized error handler for session-level tracking
                widget._error_handler.record_gl_info(vendor or "", renderer or "", version_str or "")
                
                # Check if error handler detected software GL and demoted capability
                if widget._error_handler.is_software_gl:
                    widget._gl_disabled_for_session = True
                    widget._use_shaders = False
            except Exception:
                logger.debug("[GL COMPOSITOR] Failed to query OpenGL adapter strings", exc_info=True)

        # Prepare an empty pipeline container tied to this context and, if
        # possible, compile the shared card-flip shader program and quad
        # geometry. The pipeline remains disabled for rendering until
        # BlockSpin and other transitions are explicitly ported.
        widget._gl_pipeline = _GLPipelineState()
        widget._use_shaders = False
        widget._gl_disabled_for_session = False
        init_gl_pipeline(widget, )
        timer_queries = getattr(widget, "_gpu_timer_queries", None)
        if timer_queries is not None and gl is not None:
            timer_queries.initialize(gl, context=ctx)
        
        # Transition to READY state on success
        if widget._gl_pipeline and widget._gl_pipeline.initialized:
            widget._gl_state.transition(GLContextState.READY)
        else:
            widget._gl_state.transition(GLContextState.ERROR, "Pipeline initialization failed")
    except Exception as e:
        # If initialization fails at this stage, we simply log and keep
        # using the existing QPainter-only path. Higher levels can decide
        # to disable GL transitions for the session based on this signal
        # in later phases when shader-backed effects are wired.
        logger.debug("[GL COMPOSITOR] initializeGL failed", exc_info=True)
        widget._gl_state.transition(GLContextState.ERROR, str(e))

def init_gl_pipeline(widget) -> None:
    if widget._gl_disabled_for_session:
        return
    if gl is None:
        logger.info("[GL COMPOSITOR] PyOpenGL not available; disabling shader pipeline")
        widget._gl_disabled_for_session = True
        return
    if widget._gl_pipeline is None:
        widget._gl_pipeline = _GLPipelineState()
    if widget._gl_pipeline.initialized:
        return
    
    _pipeline_start = time.time()
    try:
        _shader_start = time.time()
        program = create_card_flip_program(widget, )
        widget._gl_pipeline.basic_program = program
        # Cache uniform locations for the shared card-flip program.
        widget._gl_pipeline.u_angle_loc = gl.glGetUniformLocation(program, "u_angle")
        widget._gl_pipeline.u_aspect_loc = gl.glGetUniformLocation(program, "u_aspect")
        widget._gl_pipeline.u_old_tex_loc = gl.glGetUniformLocation(program, "uOldTex")
        widget._gl_pipeline.u_new_tex_loc = gl.glGetUniformLocation(program, "uNewTex")
        widget._gl_pipeline.u_block_rect_loc = gl.glGetUniformLocation(program, "u_blockRect")
        widget._gl_pipeline.u_block_uv_rect_loc = gl.glGetUniformLocation(program, "u_blockUvRect")
        widget._gl_pipeline.u_spec_dir_loc = gl.glGetUniformLocation(program, "u_specDir")
        widget._gl_pipeline.u_axis_mode_loc = gl.glGetUniformLocation(program, "u_axisMode")

        # Compile only the minimal startup subset now, then warm the rest
        # incrementally after the compositor is live.
        for program_name, program_attr, uniforms_attr in startup_transition_program_specs():
            if not _compile_transition_program(widget, program_name, program_attr, uniforms_attr):
                logger.debug("[GL SHADER] Failed to compile %s shader", program_name)
                widget._gl_disabled_for_session = True
                widget._use_shaders = False
                return

        # NOTE: Shuffle and Claws shader initialization removed - these transitions are retired.

        # Initialize geometry - each compositor needs its own VAOs since
        # OpenGL VAOs are NOT shared between GL contexts (each display has its own context)
        if widget._geometry_manager is None:
            lifetime_identity = f"{type(widget).__name__}:{id(widget)}"
            widget._geometry_manager = GLGeometryManager(
                owner=lifetime_identity, generation=id(widget),
            )
        if not widget._geometry_manager.initialize():
            logger.warning("[GL COMPOSITOR] Failed to initialize geometry manager")
            widget._gl_disabled_for_session = True
            widget._use_shaders = False
            return
        
        # Copy geometry IDs to pipeline state for backward compatibility
        widget._gl_pipeline.quad_vao = widget._geometry_manager.quad_vao
        widget._gl_pipeline.quad_vbo = widget._geometry_manager.quad_vbo
        widget._gl_pipeline.box_vao = widget._geometry_manager.box_vao
        widget._gl_pipeline.box_vbo = widget._geometry_manager.box_vbo
        widget._gl_pipeline.box_vertex_count = widget._geometry_manager.box_vertex_count
        
        # Initialize texture manager - each compositor needs its own textures since
        # OpenGL textures are NOT shared between GL contexts
        if widget._texture_manager is None:
            lifetime_identity = f"{type(widget).__name__}:{id(widget)}"
            widget._texture_manager = GLTextureManager(
                owner=lifetime_identity, generation=id(widget),
            )

        widget._gl_pipeline.initialized = True
        _pipeline_elapsed = (time.time() - _pipeline_start) * 1000.0
        if _pipeline_elapsed > 50.0 and is_perf_metrics_enabled():
            logger.warning("[PERF] [GL COMPOSITOR] Shader pipeline init took %.2fms", _pipeline_elapsed)
        else:
            logger.info("[GL COMPOSITOR] Shader pipeline initialized (%.1fms)", _pipeline_elapsed)
        schedule_deferred_transition_program_warmup(widget)
    except Exception:
        logger.debug("[GL SHADER] Failed to initialize shader pipeline", exc_info=True)
        widget._gl_disabled_for_session = True
        widget._use_shaders = False

def gl_pipeline_has_live_resources(widget) -> bool:
    """Return whether this compositor still owns deletable GL objects."""
    pipeline = getattr(widget, "_gl_pipeline", None)
    if pipeline is not None:
        if bool(getattr(pipeline, "initialized", False)):
            return True
        resource_attrs = (
            "basic_program", "raindrops_program", "warp_program",
            "diffuse_program", "blockflip_program", "crossfade_program",
            "slide_program", "wipe_program", "blinds_program",
            "crumble_program", "particle_program", "burn_program",
            "quad_vbo", "box_vbo", "quad_vao", "box_vao",
        )
        if any(int(getattr(pipeline, attr, 0) or 0) for attr in resource_attrs):
            return True

    geometry_manager = getattr(widget, "_geometry_manager", None)
    if geometry_manager is not None and geometry_manager.has_live_resources():
        return True
    program_cache = getattr(widget, "_program_cache", None)
    if program_cache is not None and program_cache.has_live_programs():
        return True
    timer_queries = getattr(widget, "_gpu_timer_queries", None)
    if timer_queries is not None and timer_queries.has_live_queries():
        return True
    stage_ring = getattr(widget, "_gl_stage_timestamps", None)
    if stage_ring is not None and stage_ring.has_live_queries():
        return True

    manager = getattr(widget, "_texture_manager", None)
    if manager is not None:
        if bool(getattr(manager, "_initialized", False)):
            return True
        if int(getattr(manager, "_old_tex_id", 0) or 0):
            return True
        if int(getattr(manager, "_new_tex_id", 0) or 0):
            return True
        if getattr(manager, "_texture_cache", None):
            return True
        if getattr(manager, "_pbo_pool", None):
            return True
        if getattr(manager, "_texture_resource_ids", None):
            return True
    return False


def cleanup_gl_pipeline(widget) -> None:
    """Delete all live GL objects while the widget context is current."""
    live_resources = gl_pipeline_has_live_resources(widget)
    if widget._gl_pipeline is None and not live_resources:
        _cleanup_deferred_warmup_resources(widget)
        return
    if gl is None:
        if live_resources:
            raise RuntimeError("Cannot delete live GL resources: PyOpenGL is unavailable")
        _cleanup_deferred_warmup_resources(widget)
        return

    widget._startup_transition_warm_queue = []
    widget._startup_transition_resource_warm_queue = []
    widget._startup_transition_resource_warm_types = set()

    is_valid = getattr(widget, "isValid", None)
    if callable(is_valid) and not is_valid():
        if live_resources:
            raise RuntimeError("Cannot delete live GL resources: compositor context is invalid")
        widget._reset_pipeline_state()
        _cleanup_deferred_warmup_resources(widget)
        return

    application = QCoreApplication.instance()
    if application is not None and QThread.currentThread() is not application.thread():
        raise RuntimeError(
            "Cross-thread GL teardown rejected: compositor cleanup must run on the GUI thread"
        )
    try:
        widget.makeCurrent()
    except Exception as exc:
        if live_resources:
            raise RuntimeError(
                "Cannot delete live GL resources: makeCurrent() failed"
            ) from exc
        widget._reset_pipeline_state()
        _cleanup_deferred_warmup_resources(widget)
        return

    context_getter = getattr(widget, "context", None)
    expected_context = context_getter() if callable(context_getter) else None
    current_context = QOpenGLContext.currentContext()
    if expected_context is not None and current_context != expected_context:
        try:
            widget.doneCurrent()
        finally:
            raise RuntimeError(
                "Cannot delete live GL resources: compositor context did not become current"
            )

    cleanup_errors: list[str] = []
    try:
        timer_queries = getattr(widget, "_gpu_timer_queries", None)
        if timer_queries is not None:
            try:
                timer_queries.poll(gl)
                timer_queries.cleanup(gl)
                # Stage-timestamp queries are compositor-context owned; strict
                # deletion, and failed deletion must remain a hard failure.
                stage_ring = getattr(widget, "_gl_stage_timestamps", None)
                if stage_ring is not None and stage_ring.has_live_queries():
                    stage_ring.cleanup(gl)
                # Association history is compositor/runtime scoped, not
                # transition scoped; clear it only here.
                try:
                    from rendering.gl_compositor_pkg.compositor_metrics import (
                        reset_diagnostic_paint_history,
                    )

                    reset_diagnostic_paint_history(widget)
                except Exception:
                    pass
            except Exception as exc:
                cleanup_errors.append(
                    f"timer_queries:{type(exc).__name__}:{exc}"
                )
            finally:
                try:
                    from rendering.gl_compositor_pkg.paint import (
                        maybe_log_gpu_timer_query_window,
                    )

                    maybe_log_gpu_timer_query_window(widget, force=True)
                except Exception:
                    logger.debug(
                        "[PERF][GL COMPOSITOR][GPU] Cleanup summary failed",
                        exc_info=True,
                    )

        manager = getattr(widget, "_texture_manager", None)
        if manager is not None:
            try:
                manager.cleanup(strict=True)
            except Exception as exc:
                cleanup_errors.append(f"textures:{type(exc).__name__}:{exc}")

        pipeline = widget._gl_pipeline
        transition_program_attrs = tuple(
            program_attr
            for _program_name, program_attr, _uniforms_attr in _transition_program_specs()
        )
        program_cache = getattr(widget, "_program_cache", None)
        if program_cache is not None:
            try:
                program_cache.cleanup(strict=True, gl_api=gl)
            except Exception as exc:
                cleanup_errors.append(f"program_cache:{type(exc).__name__}:{exc}")
            finally:
                # Cache cleanup removes successful IDs immediately and retains
                # failed ownership. Mirror that exact truth into pipeline attrs.
                live_program_ids = program_cache.get_program_ids()
                for attr in transition_program_attrs:
                    program_id = int(getattr(pipeline, attr, 0) or 0)
                    if program_id and program_id not in live_program_ids:
                        setattr(pipeline, attr, 0)
        else:
            if any(
                int(getattr(pipeline, attr, 0) or 0)
                for attr in transition_program_attrs
            ):
                cleanup_errors.append("program_cache:missing local owner")

        basic_program = int(getattr(pipeline, "basic_program", 0) or 0)
        if basic_program:
            try:
                gl.glDeleteProgram(basic_program)
                pipeline.basic_program = 0
            except Exception as exc:
                cleanup_errors.append(
                    f"program:basic_program:{type(exc).__name__}:{exc}"
                )

        geometry_manager = getattr(widget, "_geometry_manager", None)
        geometry_attrs = ("quad_vbo", "box_vbo", "quad_vao", "box_vao")
        if geometry_manager is None:
            if any(int(getattr(pipeline, attr, 0) or 0) for attr in geometry_attrs):
                cleanup_errors.append("geometry:missing local owner")
        else:
            try:
                geometry_manager.cleanup(strict=True, gl_api=gl)
            except Exception as exc:
                cleanup_errors.append(f"geometry:{type(exc).__name__}:{exc}")
            finally:
                # Pipeline fields are non-owning draw mirrors of the manager.
                for attr in geometry_attrs:
                    setattr(pipeline, attr, int(getattr(geometry_manager, f"_{attr}", 0) or 0))
                pipeline.box_vertex_count = int(
                    getattr(geometry_manager, "box_vertex_count", 0) or 0
                )
        if cleanup_errors:
            raise RuntimeError(
                "GL resource deletion incomplete: " + " | ".join(cleanup_errors)
            )
        widget._reset_pipeline_state()
    finally:
        try:
            widget.doneCurrent()
        except Exception as exc:
            if not cleanup_errors:
                cleanup_errors.append(f"doneCurrent:{type(exc).__name__}:{exc}")
        _cleanup_deferred_warmup_resources(widget)

    if cleanup_errors:
        raise RuntimeError(
            "GL context release incomplete: " + " | ".join(cleanup_errors)
        )

def _cleanup_deferred_warmup_resources(widget) -> None:
    context = getattr(widget, "_deferred_warmup_context", None)
    surface = getattr(widget, "_deferred_warmup_surface", None)
    try:
        widget._deferred_warmup_context = None
        widget._deferred_warmup_surface = None
        widget._deferred_gl_warmup_armed_callbacks = set()
        widget._deferred_gl_warmup_started = False
        widget._startup_sequence_last_log = None
    except Exception:
        pass
    try:
        if isinstance(surface, QOffscreenSurface):
            surface.destroy()
    except Exception:
        logger.debug("[GL COMPOSITOR] Failed to destroy deferred warmup surface", exc_info=True)
    try:
        if isinstance(context, QOpenGLContext):
            context.doneCurrent()
    except Exception:
        logger.debug("[GL COMPOSITOR] Failed to release deferred warmup context", exc_info=True)

def create_card_flip_program(widget) -> int:
    """Compile and link the basic textured card-flip shader program."""

    if gl is None:
        raise RuntimeError("OpenGL context not available for shader program")

    # 3D card-flip program: the vertex shader treats the image pair as a
    # thin 3D slab (box) in world space. Geometry is provided by the
    # dedicated box mesh VBO/VAO created in _init_gl_pipeline.
    vs_source = """#version 410 core
layout(location = 0) in vec3 aPos;
layout(location = 1) in vec3 aNormal;
layout(location = 2) in vec2 aUv;

out vec2 vUv;
out vec3 vNormal;
out vec3 vViewDir;
out float vEdgeX;
flat out int vFaceKind;  // 1=front, 2=back, 3=side

uniform float u_angle;
uniform float u_aspect;
uniform vec4 u_blockRect;   // xy = clip min, zw = clip max
uniform vec4 u_blockUvRect; // xy = uv min,  zw = uv max
uniform float u_specDir;    // -1 or +1, matches fragment shader
uniform int u_axisMode;

void main() {
// Preserve the local X coordinate as a thickness parameter for side
// faces while remapping UVs into the per-tile rectangle.
float edgeCoord = aUv.x;
vEdgeX = edgeCoord;

// Remap local UVs into the per-tile UV rectangle so that a grid of slabs
// each samples its own portion of the image pair.
vUv = mix(u_blockUvRect.xy, u_blockUvRect.zw, aUv);

// Classify faces in object space so texture mapping is stable regardless
// of the current rotation.
int face = 0;
if (abs(aNormal.z) > 0.5) {
    face = (aNormal.z > 0.0) ? 1 : 2;
} else {
    face = 3;
}
vFaceKind = face;

float ca = cos(u_angle);
float sa = sin(u_angle);

// Pure spin around Y; no X tilt so the top face does not open up.
mat3 rotY = mat3(
    ca,  0.0, sa,
    0.0, 1.0, 0.0,
   -sa,  0.0, ca
);

mat3 rotX = mat3(
    1.0, 0.0, 0.0,
    0.0,  ca, -sa,
    0.0,  sa,  ca
);

// Diagonal rotation: rotate around the axis (1,1,0) or (1,-1,0) normalised.
// Rodrigues formula: R(v,a) = v*cos(a) + (k x v)*sin(a) + k*(k.v)*(1-cos(a))
float inv_sqrt2 = 0.70710678;

vec3 pos;
vec3 normal;
if (u_axisMode == 1) {
    pos = rotX * aPos;
    normal = normalize(rotX * aNormal);
} else if (u_axisMode == 2) {
    // Diagonal TL->BR: axis = normalize(1, -1, 0)
    vec3 k = vec3(inv_sqrt2, -inv_sqrt2, 0.0);
    float kDotP = dot(k, aPos);
    vec3 kCrossP = cross(k, aPos);
    pos = aPos * ca + kCrossP * sa + k * kDotP * (1.0 - ca);
    float kDotN = dot(k, aNormal);
    vec3 kCrossN = cross(k, aNormal);
    normal = normalize(aNormal * ca + kCrossN * sa + k * kDotN * (1.0 - ca));
} else if (u_axisMode == 3) {
    // Diagonal TR->BL: axis = normalize(1, 1, 0)
    vec3 k = vec3(inv_sqrt2, inv_sqrt2, 0.0);
    float kDotP = dot(k, aPos);
    vec3 kCrossP = cross(k, aPos);
    pos = aPos * ca + kCrossP * sa + k * kDotP * (1.0 - ca);
    float kDotN = dot(k, aNormal);
    vec3 kCrossN = cross(k, aNormal);
    normal = normalize(aNormal * ca + kCrossN * sa + k * kDotN * (1.0 - ca));
} else {
    pos = rotY * aPos;
    normal = normalize(rotY * aNormal);
}

// Orthographic-style projection: treat the rotated slab as sitting in
// clip space so that when it faces the camera it fills the viewport
// similarly to the old 2D card, without extreme perspective stretching.
vNormal = normal;
vViewDir = vec3(0.0, 0.0, 1.0);

// Use -pos.z so the face nearest the camera always wins the depth test:
// at angle 0 the front (old image) is in front, at angle pi the back
// (new image) is in front. This avoids sudden flips when the CPU swaps
// the base pixmap at transition start/end.
float z_clip = -pos.z * 0.5;  // small but non-zero depth for proper occlusion

// Map the rotated slab into the caller-supplied block rect in clip space.
// When rendering a single full-frame slab the rect covers the entire
// viewport (-1..1 in both axes); in grid mode each tile uses a smaller
// rect.
float nx = pos.x * 0.5 + 0.5;
float ny = pos.y * 0.5 + 0.5;
float x_clip = mix(u_blockRect.x, u_blockRect.z, nx);
float y_clip = mix(u_blockRect.y, u_blockRect.w, ny);

// Add axis mode uniform for BlockSpin
// uniform int u_axisMode;  // 0 = Y, 1 = X
gl_Position = vec4(x_clip, y_clip, z_clip, 1.0);
}
"""

    fs_source = """#version 410 core
in vec2 vUv;
in vec3 vNormal;
in vec3 vViewDir;
in float vEdgeX;
flat in int vFaceKind;  // 1=front, 2=back, 3=side
out vec4 FragColor;

uniform sampler2D uOldTex;
uniform sampler2D uNewTex;
uniform float u_angle;
uniform float u_aspect;
uniform float u_specDir;  // -1 or +1, controls highlight travel direction
uniform int u_axisMode;   // 0 = Y-axis, 1 = X-axis, 2 = diag TL-BR, 3 = diag TR-BL

void main() {
// Qt images are stored top-to-bottom, whereas OpenGL's texture
// coordinates assume (0,0) at the bottom-left. Flip the V coordinate so
// the sampled image appears upright.
vec2 uv_front = vec2(vUv.x, 1.0 - vUv.y);

// For horizontal (Y-axis) spins we mirror the back face horizontally so
// that when the card flips left/right the new image appears with the
// same orientation as a plain 2D draw. For vertical (X-axis) spins the
// geometric rotation inverts the slab in Y, so we sample with the raw
// UVs to keep the new image upright.
vec2 uv_back;
if (u_axisMode == 0) {
    uv_back = vec2(1.0 - vUv.x, 1.0 - vUv.y);  // horizontal spin (Y-axis)
} else if (u_axisMode == 1) {
    uv_back = vec2(vUv.x, vUv.y);               // vertical spin (X-axis)
} else if (u_axisMode == 2) {
    // Diagonal TL->BR: rotation (x,y,z)->(-y,-x,-z) swaps and negates x,y
    uv_back = vec2(1.0 - vUv.y, vUv.x);
} else {
    // Diagonal TR->BL: rotation (x,y,z)->(y,x,-z) swaps x,y
    uv_back = vec2(vUv.y, 1.0 - vUv.x);
}

vec3 n = normalize(vNormal);
vec3 viewDir = normalize(vViewDir);
vec3 lightDir = normalize(vec3(-0.15, 0.35, 0.9));

// Normalised spin progress 0..1 from angle 0..pi and an edge-biased
// highlight envelope so specular accents are strongest near the start
// and end of the spin (slab faces most flush) and softest around the
// midpoint. A complementary mid-spin phase is used for the white rim
// outline so it appears when the slab is most edge-on. Use the absolute
// angle so LEFT/RIGHT and UP/DOWN directions share the same envelope.
float t = clamp(abs(u_angle) / 3.14159265, 0.0, 1.0);
float edgeFactor = abs(t - 0.5) * 2.0;  // 0 at mid-spin, 1 at edges
float highlightPhase = edgeFactor * edgeFactor;
float midPhase = (1.0 - edgeFactor);
midPhase = midPhase * midPhase;

vec3 color;

if (vFaceKind == 3) {
    // Side faces: darker glass core with a moving specular band across
    // the slab thickness, plus a very thin white outline along the rim
    // when the slab is most edge-on.
    vec3 base = vec3(0.0);
    vec3 halfVec = normalize(lightDir + viewDir);
    float ndh = max(dot(n, halfVec), 0.0);

    // Side faces use the original local X coordinate in [0,1] to
    // represent slab thickness from one edge to the other, independent
    // of any grid tiling. Move the highlight band centre from one edge
    // to the opposite edge over the spin, clamped far enough inside the
    // edges so the thicker band never leaves the face.
    float edgeT = (u_specDir < 0.0) ? (1.0 - t) : t;
    float bandHalfWidth = 0.09;  // thicker band for a more readable sheen
    float bandCenter = mix(bandHalfWidth, 1.0 - bandHalfWidth, edgeT);
    float d = abs(vEdgeX - bandCenter);
    float bandMask = 1.0 - smoothstep(bandHalfWidth, bandHalfWidth * 1.6, d);

    // Stronger, brighter specular so the edge sheen is clearly visible
    // and approaches white at its apex without blowing out the face.
    float spec = pow(ndh, 6.0) * bandMask * highlightPhase;
    float edgeSpec = clamp(4.0 * spec, 0.0, 1.0);
    color = mix(base, vec3(1.0), edgeSpec);

    // Thin white outline hugging the side-face rim. This uses both the
    // preserved local thickness coordinate (vEdgeX) and the tile UV's
    // vertical coordinate so the border tracks the outer rectangle of
    // the slab. It is only active around mid-spin so it never appears
    // on the very first/last frames.
    float xEdge = min(vEdgeX, 1.0 - vEdgeX);
    float yEdge = min(vUv.y, 1.0 - vUv.y);
    float edgeDist = min(xEdge, yEdge);
    float outlineMask = 1.0 - smoothstep(0.02, 0.08, edgeDist);
    float outlinePhase = outlineMask * midPhase;
    if (outlinePhase > 0.0) {
        float outlineStrength = clamp(1.2 * outlinePhase, 0.0, 1.0);
        color = mix(color, vec3(1.0), outlineStrength);
    }
} else {
    // Front/back faces: map old/new images directly to their respective
    // geometry so the card ends exactly on the new image without
    // mirroring or late flips.
    if (vFaceKind == 1) {
        color = texture(uOldTex, uv_front).rgb;
    } else {
        color = texture(uNewTex, uv_back).rgb;
    }

    // Subtle vertical rim highlight near the long edges so the slab
    // reads as a solid object while keeping the face image essentially
    // unshaded. Gate this with the same highlightPhase so we do not get
    // bright rims on the very first/last frames.
    float xN = vUv.x * 2.0 - 1.0;
    float rim = 0.0;
    if (rim > 0.0 && highlightPhase > 0.0) {
        vec3 halfVec = normalize(lightDir + viewDir);
        float ndh = max(dot(n, halfVec), 0.0);
        float spec = pow(ndh, 18.0) * highlightPhase;
        vec3 rimColor = color + vec3(spec * 0.45);  // dimmer, reduces bleed
        color = mix(color, rimColor, rim);
    }
}

FragColor = vec4(color, 1.0);
}
"""

    vert = widget._compile_shader(vs_source, gl.GL_VERTEX_SHADER)
    try:
        frag = widget._compile_shader(fs_source, gl.GL_FRAGMENT_SHADER)
    except Exception as e:
        logger.debug("[GL COMPOSITOR] Exception suppressed: %s", e)
        gl.glDeleteShader(vert)
        raise

    try:
        program = gl.glCreateProgram()
        gl.glAttachShader(program, vert)
        gl.glAttachShader(program, frag)
        gl.glLinkProgram(program)
        status = gl.glGetProgramiv(program, gl.GL_LINK_STATUS)
        if status != gl.GL_TRUE:
            log = gl.glGetProgramInfoLog(program)
            logger.debug("[GL SHADER] Failed to link card-flip program: %r", log)
            gl.glDeleteProgram(program)
            raise RuntimeError(f"Failed to link card-flip program: {log!r}")
    finally:
        gl.glDeleteShader(vert)
        gl.glDeleteShader(frag)

    return int(program)

# NOTE: _create_wipe_program() has been moved to rendering/gl_programs/wipe_program.py
# The WipeProgram helper is now responsible for shader compilation and rendering.

# NOTE: _create_diffuse_program() has been moved to rendering/gl_programs/diffuse_program.py
# The DiffuseProgram helper is now responsible for shader compilation and rendering.

# NOTE: _create_blockflip_program() has been moved to rendering/gl_programs/blockflip_program.py
# The BlockFlipProgram helper is now responsible for shader compilation and rendering.

# NOTE: _create_blinds_program() has been moved to rendering/gl_programs/blinds_program.py
# The BlindsProgram helper is now responsible for shader compilation and rendering.

# NOTE: _create_crossfade_program() has been moved to rendering/gl_programs/crossfade_program.py
# The CrossfadeProgram helper is now responsible for shader compilation and rendering.

# NOTE: _create_slide_program() has been moved to rendering/gl_programs/slide_program.py
# The SlideProgram helper is now responsible for shader compilation and rendering.

# NOTE: _create_shuffle_program() REMOVED - Shuffle transition was retired (dead code)

# NOTE: _create_warp_program() has been moved to rendering/gl_programs/warp_program.py
# The WarpProgram helper is now responsible for shader compilation and rendering.

# NOTE: _create_raindrops_program() has been moved to rendering/gl_programs/raindrops_program.py
# The RaindropsProgram helper is now responsible for shader compilation and rendering.

# NOTE: _create_claws_program() REMOVED - Claws/Shooting Stars transition was retired (dead code)
