"""
Resource manager implementation for screensaver.

Simplified version adapted from SPQDocker reusable modules.
Manages resource lifecycle and ensures proper cleanup.
"""
from __future__ import annotations

import atexit
from dataclasses import dataclass
import sys
import uuid
import weakref
import os
import threading
from types import MappingProxyType
from typing import Any, Callable, Dict, List, Optional, TypeVar, Union

from .types import CleanupProtocol, ResourceInfo, ResourceType
from core.logging.logger import get_logger, is_verbose_logging

T = TypeVar('T')

try:
    from PySide6.QtCore import QObject
except ImportError:  # pragma: no cover - used by non-Qt maintenance tools
    QObject = ()  # type: ignore[assignment,misc]

try:
    from shiboken6 import isValid as _is_valid_qobject
except ImportError:  # pragma: no cover - used by non-Qt maintenance tools
    _is_valid_qobject = None


def _freeze_snapshot_value(value):
    """Detach mutable metadata before exposing an immutable snapshot."""
    if value is None or isinstance(value, (str, int, float, bool, bytes)):
        return value
    if isinstance(value, dict):
        return MappingProxyType({
            key: _freeze_snapshot_value(item) for key, item in value.items()
        })
    if isinstance(value, (list, tuple, set, frozenset)):
        return tuple(_freeze_snapshot_value(item) for item in value)
    return repr(value)


def _freeze_worker_snapshot_value(value):
    """Detach metadata without invoking arbitrary object ``repr`` methods."""
    if value is None or isinstance(value, (str, int, float, bool, bytes)):
        return value
    if isinstance(value, dict):
        return MappingProxyType({
            key: _freeze_worker_snapshot_value(item) for key, item in value.items()
        })
    if isinstance(value, (list, tuple, set, frozenset)):
        return tuple(_freeze_worker_snapshot_value(item) for item in value)
    return MappingProxyType({
        "type": type(value).__name__,
        "identity": id(value),
    })


@dataclass(frozen=True)
class _CleanupHandlerRecord:
    """Cleanup callback storage that does not accidentally own bound objects."""

    callback: Any
    is_method: bool
    is_weak_method: bool
    kind: str
    owner_class: Optional[str]
    owner_id: Optional[int]

    def resolve(self) -> Optional[Callable[..., None]]:
        """Return the currently live callback, if this record still has one."""
        if self.is_weak_method:
            return self.callback()
        return self.callback


def _is_future_registration(resource: Any) -> bool:
    """Avoid adding diagnostic work to the high-volume task-Future path."""
    resource_type = type(resource)
    return (
        resource_type.__name__ == "Future"
        and resource_type.__module__.startswith("concurrent.futures")
    )


def _bounded_creation_site(resource: Any) -> tuple[Optional[str], str]:
    """Capture one caller frame, never a traceback or a retained frame chain."""
    if _is_future_registration(resource):
        return None, "suppressed_high_volume_future"
    try:
        caller = sys._getframe(2)
        return (
            f"{os.path.basename(caller.f_code.co_filename)}:"
            f"{caller.f_lineno}:{caller.f_code.co_name}",
            "caller_frame",
        )
    except (AttributeError, ValueError):
        return None, "unavailable"
    finally:
        # A frame keeps locals alive; do not retain it in registration metadata.
        try:
            del caller
        except UnboundLocalError:
            pass


def _qobject_validity(resource: Any) -> Optional[bool]:
    """Return QObject validity without making Qt a ResourceManager dependency."""
    if not QObject or not isinstance(resource, QObject):
        return None
    if _is_valid_qobject is None:
        return True
    try:
        return bool(_is_valid_qobject(resource))
    except RuntimeError:
        return False


def _infer_runtime_generation(resource: Any, metadata: Dict[str, Any]) -> tuple[Any, str]:
    """Use explicit metadata first, then a short QObject parent walk if available."""
    value = metadata.get("runtime_generation")
    if value is not None:
        return value, "metadata:runtime_generation"

    if not QObject or not isinstance(resource, QObject):
        return None, "unavailable"

    current = resource
    for _ in range(16):
        if _qobject_validity(current) is False:
            return None, "invalid_qobject"
        try:
            value = getattr(current, "_runtime_generation", None)
            if value is not None:
                return value, "qobject_parent"
            current = current.parent()
        except RuntimeError:
            return None, "invalid_qobject"
        if current is None:
            break
    return None, "unavailable"


def _lifetime_scope(metadata: Dict[str, Any], runtime_generation: Any) -> str:
    """Keep process-scoped registrations distinct from generation-owned entries."""
    explicit_scope = metadata.get("lifetime_scope", metadata.get("scope"))
    if isinstance(explicit_scope, str):
        normalized = explicit_scope.lower()
        if normalized in {"process", "runtime"}:
            return normalized
    return "runtime" if runtime_generation is not None else "unspecified"

_logger = get_logger("resources.manager")


class ResourceManager:
    """
    Centralized resource management for the screensaver.
    
    Tracks and manages all resources that require explicit cleanup.
    Uses weak references to allow garbage collection while tracking resources.
    Thread-safe operations with proper cleanup ordering.
    
    Includes object pooling for QPixmap/QImage to reduce GC pressure.
    """
    
    # Pool configuration
    PIXMAP_POOL_MAX_SIZE = 8  # Max pooled pixmaps per size bucket
    IMAGE_POOL_MAX_SIZE = 8   # Max pooled images per size bucket
    _app_shared_manager: Optional["ResourceManager"] = None
    _app_shared_lock = threading.RLock()

    @classmethod
    def set_app_shared(cls, manager: Optional["ResourceManager"]) -> Optional["ResourceManager"]:
        """Register the app-shared ResourceManager used by leaf/runtime fallback paths."""
        with cls._app_shared_lock:
            cls._app_shared_manager = manager
            return cls._app_shared_manager

    @classmethod
    def get_app_shared(cls) -> Optional["ResourceManager"]:
        """Return the currently registered app-shared ResourceManager, if any."""
        with cls._app_shared_lock:
            return cls._app_shared_manager

    @classmethod
    def get_or_create_app_shared(cls) -> "ResourceManager":
        """Return the app-shared ResourceManager, creating one if necessary."""
        with cls._app_shared_lock:
            manager = cls._app_shared_manager
            if manager is None or getattr(manager, "_shutdown", False):
                manager = cls()
                cls._app_shared_manager = manager
            return manager
    
    def __init__(self):
        """Initialize the ResourceManager."""
        self._resources: Dict[str, ResourceInfo] = {}
        self._weak_refs: Dict[str, Any] = {}
        self._strong_refs: Dict[str, Any] = {}  # Strong refs for temp files, etc.
        self._cleanup_handlers: Dict[str, _CleanupHandlerRecord] = {}
        self._registration_details: Dict[str, Dict[str, Any]] = {}
        self._logger = _logger
        self._shutdown = False
        self._initialized = False
        self._lock = threading.RLock()
        
        # Object pools for reducing GC pressure
        # Key: (width, height) tuple, Value: list of pooled objects
        self._pixmap_pool: Dict[tuple, List[Any]] = {}
        self._image_pool: Dict[tuple, List[Any]] = {}
        self._pool_lock = threading.Lock()
        self._pool_stats = {"pixmap_hits": 0, "pixmap_misses": 0, 
                          "image_hits": 0, "image_misses": 0}
        
        # Register cleanup on interpreter shutdown
        if not getattr(sys, 'is_finalizing', False):
            atexit.register(self.cleanup_all)
        
        self._initialized = True
        self._logger.debug("ResourceManager initialized")
    
    def register(
        self, 
        resource: Any, 
        resource_type: Union[ResourceType, str] = ResourceType.UNKNOWN,
        description: str = "",
        cleanup_handler: Optional[Callable[[Any], None]] = None,
        **metadata
    ) -> str:
        """
        Register a resource for management.
        
        Args:
            resource: The resource to register
            resource_type: Type of the resource
            description: Human-readable description
            cleanup_handler: Optional custom cleanup function
            **metadata: Additional metadata
        
        Returns:
            str: Unique resource ID
        
        Raises:
            ValueError: If resource is None or can't be weak-referenced
            RuntimeError: If manager is shut down
        """
        if resource is None:
            raise ValueError("Cannot register None as a resource")
        if self._shutdown:
            raise RuntimeError("Cannot register new resources after shutdown")
        
        # Convert string resource_type to enum if needed
        if isinstance(resource_type, str):
            resource_type_enum = ResourceType.from_string(resource_type)
        else:
            resource_type_enum = resource_type

        registration_metadata = dict(metadata)
        runtime_generation, generation_source = _infer_runtime_generation(
            resource, registration_metadata
        )
        lifetime_scope = _lifetime_scope(registration_metadata, runtime_generation)
        creation_site, creation_site_kind = _bounded_creation_site(resource)
        if runtime_generation is not None:
            registration_metadata.setdefault("runtime_generation", runtime_generation)
        registration_metadata.setdefault("lifetime_scope", lifetime_scope)
        
        with self._lock:
            # Generate unique ID
            resource_id = f"{resource_type_enum.name.lower()}_{uuid.uuid4().hex[:8]}"
            
            # Create resource info
            resource_info = ResourceInfo(
                resource_id=resource_id,
                resource_type=resource_type_enum,
                description=description,
                metadata=registration_metadata
            )
            
            # Store the resource
            self._resources[resource_id] = resource_info
            
            # Create weak reference with finalizer
            def _finalize(rid: str) -> None:
                if not self._initialized:
                    return
                # In non-verbose mode we skip the per-resource debug line to
                # keep logs readable; the real work still happens in
                # _finalize_resource.
                if is_verbose_logging():
                    self._logger.debug(f"Finalizing resource {rid}")
                self._finalize_resource(rid)
            
            try:
                self._weak_refs[resource_id] = weakref.ref(
                    resource, 
                    lambda ref, rid=resource_id: _finalize(rid)
                )
            except TypeError as e:
                # Can't create weak reference - remove partial state
                self._resources.pop(resource_id, None)
                raise ValueError(
                    f"Resource of type {type(resource).__name__} cannot be weak-referenced"
                ) from e
            
            # Determine cleanup handler
            if cleanup_handler is not None:
                cleanup_record = self._make_cleanup_handler_record(
                    cleanup_handler, is_method=False
                )
            elif isinstance(resource, CleanupProtocol):
                cleanup_record = self._make_cleanup_handler_record(
                    resource.cleanup, is_method=True
                )
            elif hasattr(resource, 'cleanup') and callable(resource.cleanup):
                cleanup_record = self._make_cleanup_handler_record(
                    resource.cleanup, is_method=True
                )
            else:
                cleanup_record = None

            if cleanup_record is not None:
                self._cleanup_handlers[resource_id] = cleanup_record

            self._registration_details[resource_id] = {
                "runtime_generation": runtime_generation,
                "generation_source": generation_source,
                "lifetime_scope": lifetime_scope,
                "resource_class": type(resource).__name__,
                "resource_identity": id(resource),
                "owner_class": registration_metadata.get("owner_class")
                or type(resource).__name__,
                "owner_id": registration_metadata.get("owner_id")
                or id(resource),
                "creation_site": creation_site,
                "creation_site_kind": creation_site_kind,
                "cleanup_handler_kind": (
                    cleanup_record.kind if cleanup_record is not None else "none"
                ),
                "cleanup_handler_owner_class": (
                    cleanup_record.owner_class if cleanup_record is not None else None
                ),
                "cleanup_handler_owner_id": (
                    cleanup_record.owner_id if cleanup_record is not None else None
                ),
                "cleanup_callback_retains_owner": (
                    cleanup_record is not None
                    and cleanup_record.owner_id is not None
                    and not cleanup_record.is_weak_method
                ),
            }

            # A PySide wrapper can remain reachable after its C++ QObject has
            # emitted ``destroyed``.  Release passive accounting at the C++
            # lifetime boundary as well as at Python weak finalization so a
            # retired generation cannot accumulate invalid GUI/timer records.
            if QObject and isinstance(resource, QObject):
                try:
                    manager_ref = weakref.ref(self)

                    def _release_destroyed_qobject(
                        *_args: object,
                        rid: str = resource_id,
                        rm_ref: weakref.ReferenceType[ResourceManager] = manager_ref,
                    ) -> None:
                        manager = rm_ref()
                        if manager is not None:
                            manager.release_tracking(rid)

                    resource.destroyed.connect(_release_destroyed_qobject)
                except (AttributeError, RuntimeError, TypeError):
                    self._logger.debug(
                        "Could not attach QObject destruction accounting release for %s",
                        resource_id,
                        exc_info=True,
                    )
            
            resource_info.increment_reference_count()
            
            self._logger.debug(f"Registered resource: {resource_id} ({description})")
            return resource_id

    @staticmethod
    def _make_cleanup_handler_record(
        cleanup_handler: Callable[..., None], *, is_method: bool
    ) -> _CleanupHandlerRecord:
        """Weakly retain ordinary Python bound methods when their owner supports it."""
        owner = getattr(cleanup_handler, "__self__", None)
        is_bound_method = owner is not None and getattr(cleanup_handler, "__func__", None) is not None
        owner_class = type(owner).__name__ if is_bound_method else None
        owner_id = id(owner) if is_bound_method else None
        if is_bound_method:
            try:
                return _CleanupHandlerRecord(
                    callback=weakref.WeakMethod(cleanup_handler),
                    is_method=is_method,
                    is_weak_method=True,
                    kind="weak_bound_method",
                    owner_class=owner_class,
                    owner_id=owner_id,
                )
            except TypeError:
                # Built-in/C-extension methods can be non-weak-referenceable.
                pass
        return _CleanupHandlerRecord(
            callback=cleanup_handler,
            is_method=is_method,
            is_weak_method=False,
            kind="bound_method" if is_bound_method else "function",
            owner_class=owner_class,
            owner_id=owner_id,
        )
    
    def register_qt(
        self,
        widget: Any,
        resource_type: ResourceType = ResourceType.GUI_COMPONENT,
        description: str = "",
        **metadata
    ) -> str:
        """
        Register a Qt widget with automatic cleanup.
        
        Args:
            widget: Qt widget to register
            resource_type: Type of resource
            description: Description
            **metadata: Additional metadata
        
        Returns:
            str: Resource ID
        """
        def qt_cleanup(w):
            try:
                if hasattr(w, 'deleteLater'):
                    w.deleteLater()
                elif hasattr(w, 'close'):
                    w.close()
            except Exception as e:
                self._logger.debug(f"Qt cleanup failed: {e}")
        
        # qt_cleanup expects resource argument, so it's a function not a method
        return self.register(
            widget,
            resource_type,
            description,
            cleanup_handler=qt_cleanup,
            **metadata
        )
    
    def register_temp_file(
        self,
        path: str,
        description: str = "",
        delete: bool = True,
        **metadata
    ) -> str:
        """
        Register a temporary file for cleanup.
        
        Args:
            path: File path
            description: Description
            delete: Whether to delete file on cleanup
            **metadata: Additional metadata
        
        Returns:
            str: Resource ID
        """
        # Use a simple object as placeholder since path is a string
        class TempFileRef:
            def __init__(self, p):
                self.path = p
        
        ref = TempFileRef(path)
        
        def file_cleanup(obj):
            if delete and os.path.exists(obj.path):
                try:
                    os.remove(obj.path)
                    self._logger.debug(f"Deleted temp file: {obj.path}")
                except Exception as e:
                    self._logger.warning(f"Failed to delete temp file {obj.path}: {e}")
        
        resource_id = self.register(
            ref,
            ResourceType.FILE_HANDLE,
            description or f"Temp file: {path}",
            cleanup_handler=file_cleanup,
            file_path=path,
            **metadata
        )
        
        # Keep strong reference to prevent GC before cleanup
        with self._lock:
            self._strong_refs[resource_id] = ref
        
        return resource_id
    
    def register_gl_handle(
        self,
        handle: int,
        handle_type: str,
        cleanup_func: Optional[Callable[[int], None]] = None,
        description: str = "",
        group: str = "gl",
        **metadata
    ) -> str:
        """
        Register an OpenGL handle for passive accounting.
        
        GL handles (VAOs, VBOs, textures, programs) must be registered
        immediately after creation so ownership and byte accounting remain
        visible. The context-bound owner is solely responsible for deletion
        and must call release_tracking() after a successful delete.
        
        Args:
            handle: The GL handle (integer from glGen*/glCreate*)
            handle_type: Type of handle ("vao", "vbo", "texture", "program", "shader", "query")
            cleanup_func: Deprecated compatibility argument. It is never
                retained or invoked because this registry does not own a GL
                context.
            description: Human-readable description
            group: Resource group for batch cleanup (default "gl")
            **metadata: Additional metadata
        
        Returns:
            str: Resource ID
        
        Example:
            vbo = gl.glGenBuffers(1)
            self._resources.register_gl_handle(
                vbo, "vbo",
                description="Quad VBO",
                owner="compositor:0",
            )
        """
        # Create a wrapper object to hold the handle since int can't be weak-referenced
        class GLHandleRef:
            def __init__(self, h: int, t: str):
                self.handle = h
                self.handle_type = t
        
        ref = GLHandleRef(handle, handle_type)
        
        resource_id = self.register(
            ref,
            ResourceType.NATIVE_HANDLE,
            description or f"GL {handle_type}: {handle}",
            gl_handle=handle,
            gl_handle_type=handle_type,
            group=group,
            **metadata
        )
        
        # Keep strong reference to prevent GC before explicit cleanup
        with self._lock:
            self._strong_refs[resource_id] = ref
        
        return resource_id
    
    def register_gl_program(
        self,
        program: int,
        description: str = "",
        group: str = "gl",
        **metadata
    ) -> str:
        """Register a GL shader program for passive accounting."""
        return self.register_gl_handle(
            program, "program",
            description=description or f"GL Program {program}",
            group=group,
            **metadata
        )
    
    def register_gl_vao(
        self,
        vao: int,
        description: str = "",
        group: str = "gl",
        **metadata
    ) -> str:
        """Register a GL VAO for passive accounting."""
        return self.register_gl_handle(
            vao, "vao",
            description=description or f"GL VAO {vao}",
            group=group,
            **metadata
        )
    
    def register_gl_vbo(
        self,
        vbo: int,
        description: str = "",
        group: str = "gl",
        **metadata
    ) -> str:
        """Register a GL VBO for passive accounting."""
        return self.register_gl_handle(
            vbo, "vbo",
            description=description or f"GL VBO {vbo}",
            group=group,
            **metadata
        )
    
    def register_gl_texture(
        self,
        texture: int,
        description: str = "",
        group: str = "gl",
        **metadata
    ) -> str:
        """Register a GL texture for passive accounting."""
        return self.register_gl_handle(
            texture, "texture",
            description=description or f"GL Texture {texture}",
            group=group,
            **metadata
        )
    
    def get_gl_stats(self) -> Dict[str, int]:
        """Get statistics about registered GL handles."""
        with self._lock:
            stats = {
                "vao": 0,
                "vbo": 0,
                "texture": 0,
                "program": 0,
                "shader": 0,
                "query": 0,
                "total": 0,
            }
            for rid, info in self._resources.items():
                if info.resource_type == ResourceType.NATIVE_HANDLE:
                    handle_type = info.metadata.get("gl_handle_type", "")
                    if handle_type in stats:
                        stats[handle_type] += 1
                        stats["total"] += 1
            return stats

    def _snapshot_entry(
        self,
        info: ResourceInfo,
        *,
        inspect_live_resource: bool = True,
    ) -> MappingProxyType:
        """Build one detached diagnostic record while the registry lock is held."""
        metadata = dict(info.metadata)
        details = self._registration_details.get(info.resource_id, {})
        freeze_value = (
            _freeze_snapshot_value
            if inspect_live_resource
            else _freeze_worker_snapshot_value
        )
        tracked_bytes = metadata.get("tracked_bytes")
        if not (
            isinstance(tracked_bytes, int)
            and not isinstance(tracked_bytes, bool)
            and tracked_bytes >= 0
        ):
            tracked_bytes = None
        dimensions = metadata.get("dimensions")
        if isinstance(dimensions, (list, tuple)):
            dimensions = tuple(dimensions)
        elif dimensions is not None:
            dimensions = None

        resource = None
        if inspect_live_resource:
            strong_resource = self._strong_refs.get(info.resource_id)
            weak_resource = self._weak_refs.get(info.resource_id)
            resource = strong_resource if strong_resource is not None else (
                weak_resource() if weak_resource is not None else None
            )
        return MappingProxyType({
            "resource_id": info.resource_id,
            "resource_type": info.resource_type.name,
            "description": freeze_value(info.description),
            "group": metadata.get("group", info.group),
            "gl_handle_type": freeze_value(
                metadata.get("gl_handle_type")
            ),
            "owner": freeze_value(metadata.get("owner")),
            "generation": freeze_value(metadata.get("generation")),
            "runtime_generation": freeze_value(
                details.get("runtime_generation")
            ),
            "generation_source": details.get("generation_source"),
            "lifetime_scope": details.get("lifetime_scope"),
            "resource_class": details.get("resource_class"),
            "resource_identity": details.get("resource_identity"),
            "owner_class": details.get("owner_class"),
            "owner_id": details.get("owner_id"),
            "creation_site": details.get("creation_site"),
            "creation_site_kind": details.get("creation_site_kind"),
            "weak_live": resource is not None if inspect_live_resource else None,
            "qobject_valid": (
                _qobject_validity(resource)
                if inspect_live_resource and resource is not None
                else None
            ),
            "cleanup_handler_kind": details.get("cleanup_handler_kind", "none"),
            "cleanup_handler_owner_class": details.get("cleanup_handler_owner_class"),
            "cleanup_handler_owner_id": details.get("cleanup_handler_owner_id"),
            "cleanup_callback_retains_owner": details.get(
                "cleanup_callback_retains_owner", False
            ),
            "dimensions": dimensions,
            "format": freeze_value(metadata.get("format")),
            "tracked_bytes": tracked_bytes,
            "lease_count": None,
        })

    def _accounting_snapshot_for_ids(
        self,
        resource_ids: Optional[set[str]] = None,
        *,
        inspect_live_resources: bool = True,
    ):
        """Return the existing aggregate snapshot, optionally filtered to known ids."""
        with self._lock:
            resources = []
            known_tracked_bytes = 0
            unknown_tracked_resources = 0
            for info in self._resources.values():
                if resource_ids is not None and info.resource_id not in resource_ids:
                    continue
                entry = self._snapshot_entry(
                    info,
                    inspect_live_resource=inspect_live_resources,
                )
                if entry["tracked_bytes"] is None:
                    unknown_tracked_resources += 1
                else:
                    known_tracked_bytes += entry["tracked_bytes"]
                resources.append(entry)
            return MappingProxyType({
                "total_resources": len(resources),
                "known_tracked_bytes": known_tracked_bytes,
                "unknown_tracked_resources": unknown_tracked_resources,
                "resources": tuple(resources),
            })

    def get_accounting_snapshot(self):
        """Return an immutable, detached snapshot of registered resources."""
        return self._accounting_snapshot_for_ids()

    def get_usage_accounting_snapshot(self):
        """Return worker-safe accounting without dereferencing live resources.

        The periodic usage sampler runs outside the GUI thread.  It may read
        immutable registration metadata and byte counts, but it must not
        dereference QObject weakrefs, call Shiboken validity checks, or invoke
        arbitrary object ``repr`` methods.
        """
        return self._accounting_snapshot_for_ids(inspect_live_resources=False)

    def get_generation_accounting_snapshot(
        self, runtime_generation: Any, *, include_process_scoped: bool = False
    ):
        """Return a read-only snapshot of entries owned by one runtime generation.

        Process-scoped records are deliberately excluded unless the caller opts in;
        this is diagnostic selection only and never performs cleanup.
        """
        with self._lock:
            resource_ids = {
                resource_id
                for resource_id, details in self._registration_details.items()
                if details.get("runtime_generation") == runtime_generation
                and (
                    include_process_scoped
                    or details.get("lifetime_scope") != "process"
                )
            }
        return self._accounting_snapshot_for_ids(resource_ids)

    def get_resources_by_runtime_generation(
        self, runtime_generation: Any, *, include_process_scoped: bool = False
    ) -> tuple[MappingProxyType, ...]:
        """Return read-only entry details for one runtime generation without cleanup."""
        return self.get_generation_accounting_snapshot(
            runtime_generation,
            include_process_scoped=include_process_scoped,
        )["resources"]
    
    def get(self, resource_id: str) -> Optional[Any]:
        """
        Get a resource by ID.
        
        Args:
            resource_id: Resource ID
        
        Returns:
            The resource or None if not found or garbage collected
        """
        with self._lock:
            # Check strong refs first
            if resource_id in self._strong_refs:
                resource = self._strong_refs[resource_id]
                if resource_id in self._resources:
                    self._resources[resource_id].touch()
                return resource
            
            # Then check weak refs
            if resource_id not in self._weak_refs:
                return None
            
            weak_ref = self._weak_refs[resource_id]
            resource = weak_ref()
            
            if resource is not None and resource_id in self._resources:
                self._resources[resource_id].touch()
            
            return resource
    
    def unregister(self, resource_id: str, force: bool = False) -> bool:
        """
        Unregister and clean up a resource.
        
        Args:
            resource_id: ID of resource to unregister
            force: If True, force cleanup even if reference count > 0
        
        Returns:
            bool: True if resource was unregistered
        """
        with self._lock:
            if not resource_id or resource_id not in self._resources:
                return False

            if not force and self._resources[resource_id].reference_count > 1:
                raise RuntimeError(
                    f"Cannot unregister resource {resource_id} with active references. "
                    f"Reference count: {self._resources[resource_id].reference_count}"
                )

            resource = self._strong_refs.pop(resource_id, None)
            if resource is None:
                resource = self._weak_refs.get(resource_id, lambda: None)()
            cleanup_info = self._cleanup_handlers.pop(resource_id, None)
            self._resources.pop(resource_id, None)
            self._weak_refs.pop(resource_id, None)
            self._registration_details.pop(resource_id, None)

        # Cleanup may call GL; registry locks must never cross this boundary.
        if cleanup_info is not None:
            try:
                handler = cleanup_info.resolve()
                if handler is None:
                    return True
                if cleanup_info.is_method:
                    if resource is not None:
                        handler()
                elif resource is not None:
                    handler(resource)
                self._logger.debug(f"Cleaned up resource: {resource_id}")
            except Exception as e:
                self._logger.error(f"Error cleaning up resource {resource_id}: {e}")

        return True

    def release_tracking(self, resource_id: str) -> bool:
        """Forget an owner-deleted resource without invoking its cleanup."""
        with self._lock:
            if not resource_id or resource_id not in self._resources:
                return False
            self._cleanup_handlers.pop(resource_id, None)
            self._resources.pop(resource_id, None)
            self._weak_refs.pop(resource_id, None)
            self._strong_refs.pop(resource_id, None)
            self._registration_details.pop(resource_id, None)
            return True
    
    def _finalize_resource(self, resource_id: str) -> None:
        """Called when a resource is garbage collected."""
        with self._lock:
            was_registered = resource_id in self._resources
            self._cleanup_handlers.pop(resource_id, None)
            self._resources.pop(resource_id, None)
            self._weak_refs.pop(resource_id, None)
            self._strong_refs.pop(resource_id, None)
            self._registration_details.pop(resource_id, None)
            if was_registered and is_verbose_logging():
                self._logger.debug(f"Resource {resource_id} was garbage collected")
    
    def get_all_resources(self) -> List[ResourceInfo]:
        """Get information about all registered resources."""
        with self._lock:
            return [info for info in self._resources.values()]
    
    def get_resources_by_type(self, resource_type: ResourceType) -> List[ResourceInfo]:
        """Get all resources of a specific type."""
        with self._lock:
            return [info for info in self._resources.values() 
                   if info.resource_type == resource_type]
    
    def cleanup_all(self) -> None:
        """Clean up all registered resources.
        
        WARNING: This method should only be called from the main/UI thread.
        Calling from a ThreadManager callback can cause deadlocks.
        """
        if self._shutdown:
            return
        
        # Safety check: warn if called from non-main thread
        # This helps catch potential deadlock scenarios where cleanup_all()
        # is called from a ThreadManager callback
        main_thread = threading.main_thread()
        current_thread = threading.current_thread()
        if current_thread != main_thread:
            self._logger.warning(
                "[THREAD_SAFETY] cleanup_all() called from non-main thread '%s'. "
                "This may cause deadlocks. Should be called from UI thread only.",
                current_thread.name
            )
        
        self._logger.info("Cleaning up all resources...")
        self._shutdown = True
        with self._app_shared_lock:
            if self.__class__._app_shared_manager is self:
                self.__class__._app_shared_manager = None
        
        with self._lock:
            groups = {
                'qt': [],
                'network': [],
                'cache': [],
                'filesystem': [],
                'other': [],
            }
            for resource_id, info in self._resources.items():
                groups[info.group].append(resource_id)

        # Cleanup handlers run outside the registry lock. GL records are passive
        # accounting entries and therefore have no cleanup handler.
        cleanup_order = ['qt', 'network', 'cache', 'filesystem', 'other']
        for group in cleanup_order:
            for resource_id in groups[group]:
                try:
                    self.unregister(resource_id, force=True)
                except Exception as e:
                    self._logger.error(f"Error cleaning up {resource_id}: {e}")
        
        # Clear object pools
        try:
            self.clear_pools()
        except Exception as e:
            self._logger.debug(f"Error clearing pools: {e}")
        
        self._logger.info("Resource cleanup complete")
    
    def shutdown(self) -> None:
        """Shutdown the resource manager."""
        self.cleanup_all()
    
    # -------------------------------------------------------------------------
    # Object Pooling for QPixmap/QImage
    # -------------------------------------------------------------------------
    
    def acquire_pixmap(self, width: int, height: int) -> Optional[Any]:
        """
        Acquire a QPixmap from the pool or return None if none available.
        
        The caller should check if None is returned and create a new QPixmap.
        Pooled pixmaps are cleared before being returned.
        
        Args:
            width: Required width
            height: Required height
            
        Returns:
            QPixmap from pool or None
        """
        key = (width, height)
        with self._pool_lock:
            if key in self._pixmap_pool and self._pixmap_pool[key]:
                pixmap = self._pixmap_pool[key].pop()
                self._pool_stats["pixmap_hits"] += 1
                # Clear the pixmap for reuse
                try:
                    pixmap.fill()  # Fill with transparent
                except Exception as e:
                    _logger.debug("[RESOURCES] Exception suppressed: %s", e)
                return pixmap
            self._pool_stats["pixmap_misses"] += 1
            return None
    
    def release_pixmap(self, pixmap: Any) -> bool:
        """
        Return a QPixmap to the pool for reuse.
        
        Args:
            pixmap: QPixmap to return to pool
            
        Returns:
            True if pooled, False if pool is full or pixmap is invalid
        """
        if pixmap is None:
            return False
        try:
            if pixmap.isNull():
                return False
            key = (pixmap.width(), pixmap.height())
        except Exception as e:
            _logger.debug("[RESOURCES] Exception suppressed: %s", e)
            return False
        
        with self._pool_lock:
            if key not in self._pixmap_pool:
                self._pixmap_pool[key] = []
            if len(self._pixmap_pool[key]) < self.PIXMAP_POOL_MAX_SIZE:
                self._pixmap_pool[key].append(pixmap)
                return True
            return False
    
    def acquire_image(self, width: int, height: int, format_hint: Any = None) -> Optional[Any]:
        """
        Acquire a QImage from the pool or return None if none available.
        
        Args:
            width: Required width
            height: Required height
            format_hint: Optional QImage.Format to match
            
        Returns:
            QImage from pool or None
        """
        key = (width, height)
        with self._pool_lock:
            if key in self._image_pool and self._image_pool[key]:
                image = self._image_pool[key].pop()
                self._pool_stats["image_hits"] += 1
                # Fill with transparent
                try:
                    image.fill(0)
                except Exception as e:
                    _logger.debug("[RESOURCES] Exception suppressed: %s", e)
                return image
            self._pool_stats["image_misses"] += 1
            return None
    
    def release_image(self, image: Any) -> bool:
        """
        Return a QImage to the pool for reuse.
        
        Args:
            image: QImage to return to pool
            
        Returns:
            True if pooled, False if pool is full or image is invalid
        """
        if image is None:
            return False
        try:
            if image.isNull():
                return False
            key = (image.width(), image.height())
        except Exception as e:
            _logger.debug("[RESOURCES] Exception suppressed: %s", e)
            return False
        
        with self._pool_lock:
            if key not in self._image_pool:
                self._image_pool[key] = []
            if len(self._image_pool[key]) < self.IMAGE_POOL_MAX_SIZE:
                self._image_pool[key].append(image)
                return True
            return False
    
    def clear_pools(self) -> None:
        """Clear all object pools."""
        with self._pool_lock:
            self._pixmap_pool.clear()
            self._image_pool.clear()
            self._logger.debug("Object pools cleared")
    
    def get_pool_stats(self) -> Dict[str, Any]:
        """Get object pool statistics."""
        with self._pool_lock:
            total_pixmaps = sum(len(v) for v in self._pixmap_pool.values())
            total_images = sum(len(v) for v in self._image_pool.values())
            return {
                "pixmap_pool_size": total_pixmaps,
                "image_pool_size": total_images,
                "pixmap_buckets": len(self._pixmap_pool),
                "image_buckets": len(self._image_pool),
                **self._pool_stats
            }
    
    def get_stats(self) -> Dict[str, Any]:
        """Get resource manager statistics."""
        with self._lock:
            stats = {
                'total_resources': len(self._resources),
                'by_type': {},
                'by_group': {},
                'pools': self.get_pool_stats()
            }
            
            for info in self._resources.values():
                # By type
                type_name = info.resource_type.name
                stats['by_type'][type_name] = stats['by_type'].get(type_name, 0) + 1
                
                # By group
                stats['by_group'][info.group] = stats['by_group'].get(info.group, 0) + 1
            
            return stats
