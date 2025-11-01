"""
Resource manager implementation.

This module provides the ResourceManager class which implements the IResourceManager
interface for managing application resources and ensuring proper cleanup.

The ResourceManager is responsible for:
- Tracking all resources that require explicit cleanup
- Managing resource lifecycle (creation, access, cleanup)
- Preventing resource leaks through reference counting
- Providing thread-safe access to resources
- Supporting automatic cleanup on application shutdown
"""
from __future__ import annotations

import atexit
import logging
import sys
import uuid
import weakref
import os
import shutil
import ctypes
import threading
from typing import Any, Callable, Dict, List, Optional, Type, TypeVar, Union

from .types import CleanupProtocol, ResourceInfo, ResourceType
from utils.lockfree import TripleBuffer
from PySide6.QtCore import QCoreApplication, QThread

# Type variable for generic resource type
T = TypeVar('T')

# Default logger for the resource manager
_logger = logging.getLogger(__name__)


class ResourceManager:
    """
    Centralized resource management for the application.
    
    This class is responsible for tracking and managing all resources that require
    explicit cleanup, such as file handles, network connections, and GUI components.
    
    The ResourceManager uses weak references to track resources while still allowing
    them to be garbage collected. It provides thread-safe operations and supports
    both automatic and manual resource cleanup.
    
    Example usage:
        # Register a resource
        resource_id = resource_manager.register(my_resource, ResourceType.FILE_HANDLE, "My resource")
        
        # Get a resource
        resource = resource_manager.get(resource_id)
        
        # Unregister and clean up
        resource_manager.unregister(resource_id)
    """
    
    def __init__(self):
        """Initialize the ResourceManager with empty resource tracking."""
        self._resources: Dict[str, ResourceInfo] = {}
        self._weak_refs: Dict[str, Any] = {}
        self._cleanup_handlers: Dict[str, Callable[[Any], None]] = {}
        self._logger = _logger.getChild('ResourceManager')
        self._shutdown = False
        self._initialized = False
        # Thread/worker integration (set on attach)
        self._thread_manager: Any | None = None
        self._tm_ref: Any | None = None  # weakref to ThreadManager when available
        self._snapshot_tb: Optional[TripleBuffer] = None
        # Coalesced snapshot publisher: readers are lock-free
        # No raw locks; all mutations must be executed on the UI thread.

        # Register cleanup on interpreter shutdown
        if not getattr(sys, 'is_finalizing', False):
            atexit.register(self.cleanup_all)

        self._initialized = True
    
    def register(
        self, 
        resource: Any, 
        resource_type: Union[ResourceType, str] = ResourceType.UNKNOWN,
        description: str = "",
        cleanup_handler: Optional[Callable[[Any], None]] = None,
        **metadata
    ) -> str:
        """Register a resource for management.
        
        Args:
            resource: The resource to register
            resource_type: Type of the resource (enum or string)
            description: Human-readable description
            cleanup_handler: Optional custom cleanup function for this resource
            **metadata: Additional metadata about the resource
            
        Returns:
            str: Unique resource ID
            
        Raises:
            RuntimeError: If the resource manager has been shut down
            ValueError: If the resource is None or invalid
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

        def _do_register() -> str:
            # Generate a unique ID for this resource
            resource_id = f"{resource_type_enum.name.lower()}_{uuid.uuid4().hex}"
            # Create resource info
            resource_info = ResourceInfo(
                resource_id=resource_id,
                resource_type=resource_type_enum,
                description=description,
                metadata=metadata or {}
            )
            # Store the resource using a weak reference
            self._resources[resource_id] = resource_info

            # Create a weak reference with finalizer
            def _finalize(rid: str) -> None:
                if not self._initialized or self._shutdown:
                    return
                self._logger.debug(f"Finalizing resource {rid}")
                self._finalize_resource(rid)

            # Guard: resource must support weak references to be tracked safely
            try:
                self._weak_refs[resource_id] = weakref.ref(resource, lambda ref, rid=resource_id: _finalize(rid))
            except TypeError as e:
                # Remove partial state and fail explicitly per no-fallback policy
                self._resources.pop(resource_id, None)
                raise ValueError(
                    f"Resource of type {type(resource).__name__} cannot be weak-referenced; "
                    "register an object that supports weakref or implements CleanupProtocol."
                ) from e

            # Determine the cleanup handler
            if cleanup_handler is not None:
                self._cleanup_handlers[resource_id] = cleanup_handler
            elif isinstance(resource, CleanupProtocol):
                self._cleanup_handlers[resource_id] = resource.cleanup
            elif hasattr(resource, 'cleanup') and callable(resource.cleanup):
                self._logger.warning(
                    f"Resource {resource_id} has a cleanup method but doesn't implement CleanupProtocol. "
                    "Consider implementing the protocol for better type safety."
                )
                self._cleanup_handlers[resource_id] = resource.cleanup

            resource_info.increment_reference_count()

            self._logger.debug(f"Registered resource: {resource_info}")
            return resource_id

        # Route via UI-thread single-writer
        return self._enqueue_mutation_sync(_do_register)
    
    def unregister(self, resource_id: str, force: bool = False) -> bool:
        """Unregister and clean up a resource.
        
        Args:
            resource_id: ID of the resource to unregister
            force: If True, force cleanup even if reference count > 0
            
        Returns:
            bool: True if resource was found and unregistered, False otherwise
            
        Raises:
            RuntimeError: If the resource is still referenced and force=False
        """
        def _do_unregister() -> bool:
            if not resource_id:
                return False
            # Check reference count
            if resource_id in self._resources and self._resources[resource_id].reference_count > 1 and not force:
                raise RuntimeError(
                    f"Cannot unregister resource {resource_id} with active references. "
                    f"Reference count: {self._resources[resource_id].reference_count}"
                )

            # Get the resource before removing it
            resource = self._weak_refs.get(resource_id, lambda: None)()
            cleanup_handler = self._cleanup_handlers.pop(resource_id, None)

            # Remove from tracking
            self._resources.pop(resource_id, None)
            self._weak_refs.pop(resource_id, None)

            # Perform cleanup if we have a handler and the resource still exists
            if cleanup_handler is not None and resource is not None:
                try:
                    self._logger.debug(f"Cleaning up resource: {resource_id}")
                    cleanup_handler(resource)
                except Exception as e:
                    self._logger.error(
                        f"Error cleaning up resource {resource_id}: {e}",
                        exc_info=True
                    )
            return True

        return bool(self._enqueue_mutation_sync(_do_unregister))

    def get(self, resource_id: str, default: Any = None) -> Any:
        """Get a registered resource by ID.
        
        Args:
            resource_id: ID of the resource to retrieve
            default: Default value to return if resource is not found
            
        Returns:
            The registered resource, default if not found, or None if garbage collected
        """
        if not resource_id:
            return default
            
        if resource_id not in self._resources:
            return default
        resource = self._weak_refs.get(resource_id, lambda: None)()
        if resource is None:
            # Resource was GC'd; schedule cleanup on UI thread but return default
            try:
                self._enqueue_mutation_sync(lambda: self._finalize_resource(resource_id))
            except Exception:
                pass
            return default
        # Lock-free read; avoid mutating access stats on read path
        return resource
            
    def get_typed(self, resource_id: str, resource_type: Type[T], default: T = None) -> T:
        """Get a registered resource by ID with type checking.
        
        Args:
            resource_id: ID of the resource to retrieve
            resource_type: Expected type of the resource
            default: Default value to return if resource is not found or wrong type
            
        Returns:
            The registered resource with the expected type, or default if not found/wrong type
        """
        resource = self.get(resource_id, default)
        if resource is not None and not isinstance(resource, resource_type):
            self._logger.warning(
                f"Resource {resource_id} is not of type {resource_type.__name__}"
            )
            return default
        return resource
    
    def list_resources(self, resource_type: Optional[Union[ResourceType, str]] = None) -> List[ResourceInfo]:
        """List all registered resources, optionally filtered by type.
        
        Args:
            resource_type: Optional resource type filter (can be enum or string)
            
        Returns:
            List of resource information objects
        """
        resources = list(self._resources.values())
        # Filter by type if specified
        if resource_type is not None:
            if isinstance(resource_type, str):
                resource_type = ResourceType.from_string(resource_type)
            resources = [r for r in resources if r.resource_type == resource_type]
        return resources
            
    def get_resource_info(self, resource_id: str) -> Optional[ResourceInfo]:
        """Get information about a registered resource.
        
        Args:
            resource_id: ID of the resource
            
        Returns:
            ResourceInfo object or None if not found
        """
        return self._resources.get(resource_id)
            
    def exists(self, resource_id: str) -> bool:
        """Check if a resource with the given ID exists.
        
        Args:
            resource_id: ID of the resource to check
            
        Returns:
            bool: True if the resource exists and hasn't been garbage collected
        """
        if resource_id not in self._resources:
            return False
        ref = self._weak_refs.get(resource_id)
        return bool(ref and ref() is not None)
    
    def _finalize_resource(self, resource_id: str) -> None:
        """Called when a resource is garbage collected.
        
        Args:
            resource_id: ID of the resource that was garbage collected
        """
        # Only clean up if we still have a record of this resource
        if resource_id in self._resources:
            self._logger.debug(f"Resource {resource_id} was garbage collected")
            self._resources.pop(resource_id, None)
            self._cleanup_handlers.pop(resource_id, None)
    
    def cleanup_all(self) -> None:
        """Clean up all registered resources.

        Note: This method intentionally allows execution during shutdown. When the
        resource manager is attached to a ThreadManager, it routes via the single-writer;
        otherwise it performs cleanup directly in the caller thread.
        """

        def _do_cleanup_all() -> None:
            self._logger.info("Cleaning up all resources...")
            # Snapshot current resources and compute deterministic ordering
            resources = list(self._resources.values())
            count = len(resources)
            if count == 0:
                self._logger.debug("No resources to clean up")
                return

            def _group_rank(ri: ResourceInfo) -> int:
                # Prefer explicit group if present on ResourceInfo
                try:
                    grp = getattr(ri, 'group', '') or ''
                    if grp:
                        order = {'qt': 0, 'network_db': 1, 'opengl': 2, 'filesystem': 3, 'other': 4}
                        return order.get(grp, 4)
                except Exception:
                    pass
                # Fallback: derive from type/metadata (legacy path)
                rt = ri.resource_type
                qt = {ResourceType.GUI_COMPONENT, ResourceType.TIMER, ResourceType.WINDOW, ResourceType.WINDOW_MANAGER}
                netdb = {ResourceType.NETWORK_CONNECTION, ResourceType.DATABASE_CONNECTION}
                fs = {ResourceType.FILE_HANDLE}
                if getattr(ri, 'metadata', None) and ri.metadata.get('gl', False):
                    return 2
                if rt in qt:
                    return 0
                if rt in netdb:
                    return 1
                if rt in fs:
                    return 3
                return 4

            def _priority(ri: ResourceInfo) -> int:
                try:
                    return int(ri.metadata.get('cleanup_priority', 1_000_000))  # large default
                except Exception:
                    return 1_000_000

            # Sort by (group_rank, cleanup_priority, created_at)
            resources.sort(key=lambda x: (_group_rank(x), _priority(x), x.created_at))
            self._logger.debug(
                "Deterministic cleanup order computed: %s",
                [ri.resource_id for ri in resources]
            )

            self._logger.info(f"Cleaning up {count} resources in deterministic order...")
            for ri in resources:
                rid = ri.resource_id
                # Inline unregister to avoid re-entrancy through the queue
                resource = self._weak_refs.get(rid, lambda: None)()
                cleanup_handler = self._cleanup_handlers.pop(rid, None)
                self._resources.pop(rid, None)
                self._weak_refs.pop(rid, None)
                if cleanup_handler is not None and resource is not None:
                    try:
                        self._logger.debug(f"Cleaning up resource: {rid}")
                        cleanup_handler(resource)
                    except Exception as e:
                        self._logger.error(
                            f"Error cleaning up resource {rid}: {e}",
                            exc_info=True
                        )
            self._logger.info(f"Successfully cleaned up {count} resources")

        self._enqueue_mutation_sync(_do_cleanup_all)
    
    def shutdown(self) -> None:
        """Shut down the resource manager and clean up all resources."""
        if self._shutdown:
            return

        self._logger.info("Shutting down resource manager...")
        # Perform cleanup synchronously on UI thread
        self.cleanup_all()

        self._shutdown = True
        self._resources.clear()
        self._weak_refs.clear()
        self._cleanup_handlers.clear()
    
    def get_icon(self, icon_name: str, default: Any = None):
        """Get an icon resource by name.
        
        Args:
            icon_name: Name of the icon resource
            default: Default value to return if icon is not found
            
        Returns:
            The icon resource, default if not found, or None if garbage collected
        """
        return self.get(f"icon_{icon_name}", default)
    
    def get_style(self, style_name: str, default: Any = None):
        """Get a style resource by name.
        
        Args:
            style_name: Name of the style resource
            default: Default value to return if style is not found
            
        Returns:
            The style resource, default if not found, or None if garbage collected
        """
        return self.get(f"style_{style_name}", default)

    # --- Lock-free read snapshot API ----------------------------------------
    def list_resources_snapshot(self) -> List[ResourceInfo]:
        """Return the latest published snapshot of resources without locking.

        Returns an empty list if snapshots are not initialized yet.
        """
        tb = self._snapshot_tb
        if tb is None:
            return []
        snap = tb.consume_latest()
        if snap is None:
            return []
        # Stored as a tuple for immutability; return as list for convenience
        return list(snap)
    
    # --- Thread/Z-Order integration (thin delegations) ---------------------
    def attach_thread_manager(self, thread_manager: Any) -> None:
        """Attach a ThreadManager instance (avoids circular imports).
        
        Stores a weak reference when possible. This method intentionally does not
        start the mutation worker; it is a minimal integration point used by
        ThreadManager during initialization. Call `start_mutation_worker()` after
        thread pools are initialized to spin up the worker.
        """
        try:
            # Store weakref when possible
            self._tm_ref = weakref.ref(thread_manager) if thread_manager is not None else None
            self._thread_manager = thread_manager
            self._logger.info("ThreadManager attached to ResourceManager")
        except TypeError:
            # Fallback to strong reference with explicit log per no-fallback policy
            self._tm_ref = None
            self._thread_manager = thread_manager
            self._logger.warning("ThreadManager is not weakref-able; stored strong reference")

        # Initialize snapshot buffer; no background worker
        if self._snapshot_tb is None:
            try:
                self._snapshot_tb = TripleBuffer()
            except Exception as e:
                self._logger.error(f"Failed to initialize snapshot buffer: {e}", exc_info=True)

    def start_mutation_worker(self, thread_manager: Any | None = None) -> None:
        """Deprecated: no-op. Mutations run on UI thread via ThreadManager.

        Left in place for compatibility with callers.
        """
        try:
            if self._snapshot_tb is None:
                self._snapshot_tb = TripleBuffer()
        except Exception as e:
            self._logger.error(f"start_mutation_worker (compat) failed: {e}", exc_info=True)

    def stop_mutation_worker(self, timeout: float = 1.0) -> None:
        """Deprecated no-op for compatibility."""
        return

    # --- Qt integration helpers --------------------------------------------
    def _run_on_ui(self, fn: Callable, *args, **kwargs) -> None:
        """Dispatch a callable to the UI thread if ThreadManager is attached.

        Falls back to direct call with a warning (per no-fallback policy, still explicit).
        """
        try:
            tm = self._thread_manager if self._tm_ref is None else (self._tm_ref() if self._tm_ref else None)
            if tm is not None and hasattr(tm, 'run_on_ui_thread'):
                tm.run_on_ui_thread(fn, *args, **kwargs)
                return
            self._logger.warning("UI dispatcher not available; executing on current thread")
        except Exception as e:
            self._logger.error(f"Failed to dispatch to UI thread: {e}")
        try:
            fn(*args, **kwargs)
        except Exception:
            self._logger.exception("UI-thread fallback execution failed")

    def _cleanup_qt(self, obj: Any) -> None:
        """Safely cleanup a Qt QObject/derivative on the UI thread.

        Behavior:
        - QTimer: stop() on UI thread, then deleteLater()
        - QThread-like (has quit/wait): request interruption if available, quit(), wait(500), then deleteLater()
        - QWidget/QObject: prefer deleteLater() on UI thread
        All exceptions are logged; operations are idempotent.
        """

        def _do():
            try:
                # QTimer
                if hasattr(obj, 'isActive') and hasattr(obj, 'stop'):
                    try:
                        if obj.isActive():
                            obj.stop()
                    except Exception:
                        self._logger.debug("QTimer stop failed or not active", exc_info=True)

                # QThread-like
                if hasattr(obj, 'quit') and callable(getattr(obj, 'quit')):
                    try:
                        if hasattr(obj, 'requestInterruption') and callable(getattr(obj, 'requestInterruption')):
                            obj.requestInterruption()
                        obj.quit()
                        if hasattr(obj, 'wait') and callable(getattr(obj, 'wait')):
                            try:
                                obj.wait(500)
                            except TypeError:
                                obj.wait()
                    except Exception:
                        self._logger.debug("QThread quit/wait failed", exc_info=True)

                # Generic QObject/QWidget deletion
                if hasattr(obj, 'deleteLater') and callable(getattr(obj, 'deleteLater')):
                    try:
                        obj.deleteLater()
                    except Exception:
                        self._logger.debug("deleteLater failed", exc_info=True)
                    return

                # Fallback: close() if available; otherwise no-op
                if hasattr(obj, 'close') and callable(getattr(obj, 'close')):
                    try:
                        obj.close()
                    except Exception:
                        self._logger.debug("close() failed", exc_info=True)
            except Exception:
                self._logger.exception("Qt cleanup routine failed")

        # Ensure UI-thread affinity
        self._run_on_ui(_do)

    def register_qt(self, obj: Any, resource_type: Union[ResourceType, str] = ResourceType.GUI_COMPONENT,
                    description: str = "", **metadata) -> str:
        """Register a Qt object with UI-thread-safe cleanup semantics.

        The cleanup handler routes to the UI thread and calls deleteLater() when possible.
        """
        md = dict(metadata or {})
        md.setdefault('qt', True)
        return self.register(obj, resource_type=resource_type, description=description,
                             cleanup_handler=self._cleanup_qt, **md)

    def register_qt_timer(self, timer: Any, description: str = "", **metadata) -> str:
        """Register a QTimer-like object. Ensures stop() on UI thread before deletion."""
        return self.register_qt(timer, resource_type=ResourceType.TIMER, description=description, **metadata)

    def register_qt_thread(self, qthread: Any, description: str = "", **metadata) -> str:
        """Register a QThread-like object. Ensures quit()/wait() then deleteLater()."""
        return self.register_qt(qthread, resource_type=ResourceType.WINDOW_MANAGER, description=description, **metadata)

    # --- Filesystem & OS cleanup helpers -----------------------------------
    def _cleanup_file(self, handle: Any) -> None:
        """Flush and close a file-like handle with explicit logging."""
        try:
            if hasattr(handle, 'flush') and callable(getattr(handle, 'flush')):
                try:
                    handle.flush()
                except Exception:
                    self._logger.debug("file.flush() failed", exc_info=True)
            if hasattr(handle, 'close') and callable(getattr(handle, 'close')):
                try:
                    handle.close()
                except Exception:
                    self._logger.debug("file.close() failed", exc_info=True)
        except Exception:
            self._logger.exception("File handle cleanup failed")

    def register_file(self, handle: Any, description: str = "", **metadata) -> str:
        """Register a file-like handle for deterministic cleanup."""
        return self.register(handle, resource_type=ResourceType.FILE_HANDLE, description=description,
                             cleanup_handler=self._cleanup_file, **metadata)

    def _cleanup_temp_file(self, target: Any, delete: bool = True) -> None:
        """Close and optionally delete a temporary file.

        Supports either a file-like object (with close/name) or a small box object with `value` path.
        """
        try:
            path: str | None = None
            # Close file-like first
            if hasattr(target, 'close') and callable(getattr(target, 'close')):
                try:
                    target.close()
                except Exception:
                    self._logger.debug("temp_file.close() failed", exc_info=True)
                # try to resolve path via .name
                try:
                    path = getattr(target, 'name', None)
                except Exception:
                    path = None
            # Boxed path
            if path is None and hasattr(target, 'value'):
                try:
                    path = str(getattr(target, 'value'))
                except Exception:
                    path = None
            if delete and path:
                try:
                    os.remove(path)
                except FileNotFoundError:
                    pass
                except Exception:
                    self._logger.debug("os.remove(temp_file) failed", exc_info=True)
        except Exception:
            self._logger.exception("Temporary file cleanup failed")

    def register_temp_file(self, target: Any, description: str = "", delete: bool = True, **metadata) -> str:
        """Register a temporary file (path or file-like).

        - If `target` is path-like (str/pathlib), it's boxed for weakref tracking and will be unlinked on cleanup.
        - If `target` is a file-like object, it will be closed and unlinked (when delete=True and name is available).
        """
        md = dict(metadata or {})
        md['temp'] = True
        md['delete'] = bool(delete)

        # Wrap plain path-likes into a weakref-able box
        is_pathlike = isinstance(target, (str, bytes)) or (hasattr(target, '__fspath__'))
        boxed = target
        if is_pathlike:
            class _Box:
                def __init__(self, value: Any) -> None:
                    self.value = value
            boxed = _Box(target)

        def _handler(obj: Any, _delete=md['delete']):
            self._cleanup_temp_file(obj, delete=_delete)

        return self.register(boxed, resource_type=ResourceType.FILE_HANDLE, description=description,
                             cleanup_handler=_handler, **md)

    def _cleanup_temp_dir(self, target: Any, ignore_errors: bool = True) -> None:
        """Delete a temporary directory recursively.

        Supports a small box object with `value` path.
        """
        try:
            path: str | None = None
            if hasattr(target, 'value'):
                try:
                    path = str(getattr(target, 'value'))
                except Exception:
                    path = None
            elif isinstance(target, (str, bytes)) or hasattr(target, '__fspath__'):
                path = str(target)
            if path:
                try:
                    shutil.rmtree(path, ignore_errors=ignore_errors)
                except Exception:
                    self._logger.debug("shutil.rmtree(temp_dir) failed", exc_info=True)
        except Exception:
            self._logger.exception("Temporary directory cleanup failed")

    def register_temp_dir(self, path: Any, description: str = "", ignore_errors: bool = True, **metadata) -> str:
        """Register a temporary directory by path for recursive deletion on cleanup."""
        md = dict(metadata or {})
        md['temp'] = True
        md['is_dir'] = True
        md['ignore_errors'] = bool(ignore_errors)

        # Always box to ensure weakref support
        class _Box:
            def __init__(self, value: Any) -> None:
                self.value = value

        boxed = _Box(path)

        def _handler(obj: Any, _ie=md['ignore_errors']):
            self._cleanup_temp_dir(obj, ignore_errors=_ie)

        return self.register(boxed, resource_type=ResourceType.FILE_HANDLE, description=description,
                             cleanup_handler=_handler, **md)

    def _cleanup_os_handle(self, handle: Any) -> None:
        """Attempt to close a raw OS handle safely on Windows; otherwise call close()."""
        try:
            # If it's an integer, try Windows CloseHandle
            if isinstance(handle, int):
                try:
                    kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
                    kernel32.CloseHandle(ctypes.c_void_p(handle))
                    return
                except Exception:
                    self._logger.debug("kernel32.CloseHandle failed or unavailable", exc_info=True)
            # Otherwise, use close() if available
            if hasattr(handle, 'close') and callable(getattr(handle, 'close')):
                try:
                    handle.close()
                except Exception:
                    self._logger.debug("os_handle.close() failed", exc_info=True)
        except Exception:
            self._logger.exception("OS handle cleanup failed")

    def register_os_handle(self, handle: Any, description: str = "", **metadata) -> str:
        """Register an OS handle-like resource for cleanup.

        Uses FILE_HANDLE resource type to group under 'filesystem/OS' ordering bucket.
        """
        md = dict(metadata or {})
        md['os_handle'] = True
        return self.register(handle, resource_type=ResourceType.FILE_HANDLE, description=description,
                             cleanup_handler=self._cleanup_os_handle, **md)

    # --- OpenGL cleanup helpers (thread-safe, boxed handles) ---------------
    class _GLHandleBox:
        """Weakref-able box for non-weakref-able GL integer handles."""
        __slots__ = ("value",)
        def __init__(self, value: int) -> None:
            self.value = int(value)

    def _mk_gl_cleanup(self, delete_fn: Callable[[int], None],
                        make_current: Optional[Callable[[], None]] = None,
                        done_current: Optional[Callable[[], None]] = None,
                        is_alive: Optional[Callable[[int], bool]] = None) -> Callable[[Any], None]:
        """Create a cleanup handler that deletes a GL handle on the UI thread.

        The input to the handler is a _GLHandleBox instance.
        """
        def _handler(box: Any) -> None:
            def _do():
                try:
                    if make_current:
                        try:
                            make_current()
                        except Exception:
                            self._logger.debug("make_current failed", exc_info=True)
                    # Idempotent guard via internal flag and optional is_alive check
                    try:
                        already = bool(getattr(box, '_rm_deleted', False))
                    except Exception:
                        already = False
                    handle = int(getattr(box, 'value', 0))
                    if not already:
                        if is_alive is None or bool(self._safe_call_bool(is_alive, handle)):
                            try:
                                delete_fn(handle)
                            except Exception:
                                self._logger.debug("GL delete_fn failed", exc_info=True)
                        try:
                            setattr(box, '_rm_deleted', True)
                        except Exception:
                            pass
                except Exception:
                    self._logger.exception("GL cleanup handler failed")
                finally:
                    if done_current:
                        try:
                            done_current()
                        except Exception:
                            self._logger.debug("done_current failed", exc_info=True)
            self._run_on_ui(_do)
        return _handler

    def _mk_gl_obj_cleanup(self, delete_fn: Callable[[Any], None],
                            make_current: Optional[Callable[[], None]] = None,
                            done_current: Optional[Callable[[], None]] = None,
                            is_alive: Optional[Callable[[Any], bool]] = None) -> Callable[[Any], None]:
        """Create a cleanup handler that deletes a non-integer GL object on the UI thread.

        Passes the object directly to delete_fn; suitable for GLsync and context wrappers.
        """
        def _handler(obj: Any) -> None:
            def _do():
                try:
                    if make_current:
                        try:
                            make_current()
                        except Exception:
                            self._logger.debug("make_current failed", exc_info=True)
                    # Idempotent guard via internal flag and optional is_alive check
                    try:
                        already = bool(getattr(obj, '_rm_deleted', False))
                    except Exception:
                        already = False
                    if not already:
                        if is_alive is None or bool(self._safe_call_bool(is_alive, obj)):
                            try:
                                delete_fn(obj)
                            except Exception:
                                self._logger.debug("GL object delete_fn failed", exc_info=True)
                        try:
                            setattr(obj, '_rm_deleted', True)
                        except Exception:
                            pass
                except Exception:
                    self._logger.exception("GL object cleanup handler failed")
                finally:
                    if done_current:
                        try:
                            done_current()
                        except Exception:
                            self._logger.debug("done_current failed", exc_info=True)
            self._run_on_ui(_do)
        return _handler

    def register_gl_handle(self,
                           handle: int,
                           *,
                           description: str = "",
                           delete_fn: Callable[[int], None],
                           resource_type: ResourceType = ResourceType.CUSTOM,
                           make_current: Optional[Callable[[], None]] = None,
                           done_current: Optional[Callable[[], None]] = None,
                           is_alive: Optional[Callable[[int], bool]] = None,
                           **metadata) -> str:
        """Register a raw OpenGL integer handle with UI-thread-safe deletion.

        Boxes the integer to allow weakref tracking and enforces GL metadata.
        """
        md = dict(metadata or {})
        md.setdefault('gl', True)
        md.setdefault('gl_handle', int(handle))
        box = self._GLHandleBox(handle)
        cleanup = self._mk_gl_cleanup(delete_fn, make_current=make_current, done_current=done_current, is_alive=is_alive)
        return self.register(box, resource_type=resource_type, description=description,
                             cleanup_handler=cleanup, **md)

    def register_gl_texture(self, texture_id: int, *, delete_textures: Callable[[List[int]], None],
                            description: str = "", **metadata) -> str:
        """Register a GL texture handle for UI-thread-safe deletion using sequence form."""
        def _del_one(h: int) -> None:
            delete_textures([h])
        return self.register_gl_handle(
            texture_id,
            description=description or f"GL texture {texture_id}",
            delete_fn=_del_one,
            resource_type=ResourceType.TEXTURE,
            **metadata,
        )

    def register_gl_buffer(self, buffer_id: int, *, delete_buffer: Callable[[List[int]], None],
                           description: str = "", **metadata) -> str:
        def _del_one(h: int) -> None:
            delete_buffer([h])
        return self.register_gl_handle(
            buffer_id,
            description=description or f"GL buffer {buffer_id}",
            delete_fn=_del_one,
            resource_type=ResourceType.OPENGL_BUFFER,
            **metadata,
        )

    def register_gl_framebuffer(self, fbo_id: int, *, delete_framebuffer: Callable[[List[int]], None],
                                description: str = "", **metadata) -> str:
        def _del_one(h: int) -> None:
            delete_framebuffer([h])
        return self.register_gl_handle(
            fbo_id,
            description=description or f"GL framebuffer {fbo_id}",
            delete_fn=_del_one,
            resource_type=ResourceType.OPENGL_FRAMEBUFFER,
            **metadata,
        )

    def register_gl_renderbuffer(self, rbo_id: int, *, delete_renderbuffer: Callable[[List[int]], None],
                                 description: str = "", **metadata) -> str:
        def _del_one(h: int) -> None:
            delete_renderbuffer([h])
        return self.register_gl_handle(
            rbo_id,
            description=description or f"GL renderbuffer {rbo_id}",
            delete_fn=_del_one,
            resource_type=ResourceType.OPENGL_RENDERBUFFER,
            **metadata,
        )

    def register_gl_query(self, query_id: int, *, delete_query: Callable[[List[int]], None],
                          description: str = "", **metadata) -> str:
        def _del_one(h: int) -> None:
            delete_query([h])
        return self.register_gl_handle(
            query_id,
            description=description or f"GL query {query_id}",
            delete_fn=_del_one,
            resource_type=ResourceType.OPENGL_QUERY,
            **metadata,
        )

    def register_gl_vertex_array(self, vao_id: int, *, delete_vertex_array: Callable[[List[int]], None],
                                 description: str = "", **metadata) -> str:
        def _del_one(h: int) -> None:
            delete_vertex_array([h])
        return self.register_gl_handle(
            vao_id,
            description=description or f"GL vertex array {vao_id}",
            delete_fn=_del_one,
            resource_type=ResourceType.OPENGL_VERTEX_ARRAY,
            **metadata,
        )

    def register_gl_sync(self, sync_obj: Any, *, delete_sync: Callable[[Any], None],
                         description: str = "",
                         make_current: Optional[Callable[[], None]] = None,
                         done_current: Optional[Callable[[], None]] = None,
                         is_alive: Optional[Callable[[Any], bool]] = None,
                         **metadata) -> str:
        """Register a GL sync object (GLsync) for UI-thread-safe deletion."""
        md = dict(metadata or {})
        md.setdefault('gl', True)
        md.setdefault('gl_sync', True)
        cleanup = self._mk_gl_obj_cleanup(delete_sync, make_current=make_current, done_current=done_current, is_alive=is_alive)
        return self.register(sync_obj, resource_type=ResourceType.OPENGL_SYNC,
                             description=description or "GL sync object",
                             cleanup_handler=cleanup, **md)

    def register_gl_context(self, ctx_obj: Any, *, destroy_context: Callable[[Any], None],
                            description: str = "",
                            make_current: Optional[Callable[[], None]] = None,
                            done_current: Optional[Callable[[], None]] = None,
                            is_alive: Optional[Callable[[Any], bool]] = None,
                            **metadata) -> str:
        """Register an OpenGL context wrapper for deterministic, UI-thread cleanup."""
        md = dict(metadata or {})
        md.setdefault('gl', True)
        md.setdefault('gl_context', True)
        cleanup = self._mk_gl_obj_cleanup(destroy_context, make_current=make_current, done_current=done_current, is_alive=is_alive)
        return self.register(ctx_obj, resource_type=ResourceType.OPENGL_CONTEXT,
                             description=description or "OpenGL context",
                             cleanup_handler=cleanup, **md)

    def register_gl_shader(self, shader_id: int, *, delete_shader: Callable[[int], None],
                           description: str = "", **metadata) -> str:
        """Register a GL shader object handle for UI-thread-safe deletion.

        Caller may optionally provide make_current/done_current via metadata if needed.
        """
        return self.register_gl_handle(
            shader_id,
            description=description or f"GL shader {shader_id}",
            delete_fn=delete_shader,
            resource_type=ResourceType.OPENGL_SHADER,
            **metadata,
        )

    def register_gl_program(self, program_id: int, *, delete_program: Callable[[int], None],
                            description: str = "", **metadata) -> str:
        """Register a GL program object handle for UI-thread-safe deletion.

        For Qt `QOpenGLShaderProgram`, use `register_gl_qt_program` instead.
        """
        return self.register_gl_handle(
            program_id,
            description=description or f"GL program {program_id}",
            delete_fn=delete_program,
            resource_type=ResourceType.OPENGL_SHADER_PROGRAM,
            **metadata,
        )

    def register_gl_qt_program(self, program_obj: Any, *, description: str = "", **metadata) -> str:
        """Register a Qt QOpenGLShaderProgram-like object with UI-thread deleteLater cleanup.

        Marks the resource with gl=True and groups under OpenGL via metadata.
        """
        md = dict(metadata or {})
        md.setdefault('gl', True)
        md.setdefault('shader_program', True)
        desc = description or "Qt OpenGL shader program"
        # Reuse Qt-safe cleanup
        return self.register_qt(program_obj, resource_type=ResourceType.OPENGL_SHADER_PROGRAM,
                                description=desc, **md)

    # --- Network & Database cleanup helpers --------------------------------
    def _cleanup_network(self, conn: Any) -> None:
        """Close a network connection with explicit logging."""
        try:
            if hasattr(conn, 'shutdown') and callable(getattr(conn, 'shutdown')):
                try:
                    conn.shutdown()  # best-effort; signature varies
                except Exception:
                    self._logger.debug("conn.shutdown() failed or not supported", exc_info=True)
            if hasattr(conn, 'close') and callable(getattr(conn, 'close')):
                try:
                    conn.close()
                except Exception:
                    self._logger.debug("conn.close() failed", exc_info=True)
        except Exception:
            self._logger.exception("Network connection cleanup failed")

    def register_network(self, conn: Any, description: str = "", **metadata) -> str:
        """Register a network connection-like object for cleanup."""
        return self.register(conn, resource_type=ResourceType.NETWORK_CONNECTION, description=description,
                             cleanup_handler=self._cleanup_network, **metadata)

    def _cleanup_db(self, session: Any, rollback_on_cleanup: bool = False) -> None:
        """Cleanup a DB session/connection with optional rollback and explicit logs."""
        try:
            if rollback_on_cleanup and hasattr(session, 'rollback') and callable(getattr(session, 'rollback')):
                try:
                    session.rollback()
                except Exception:
                    self._logger.debug("session.rollback() failed", exc_info=True)
            # Common patterns: close(), dispose()
            if hasattr(session, 'close') and callable(getattr(session, 'close')):
                try:
                    session.close()
                except Exception:
                    self._logger.debug("session.close() failed", exc_info=True)
            if hasattr(session, 'dispose') and callable(getattr(session, 'dispose')):
                try:
                    session.dispose()
                except Exception:
                    self._logger.debug("session.dispose() failed", exc_info=True)
        except Exception:
            self._logger.exception("Database session cleanup failed")

    def register_db(self, session: Any, description: str = "", rollback_on_cleanup: bool = False, **metadata) -> str:
        """Register a DB session/connection with optional rollback on cleanup."""
        md = dict(metadata or {})
        md['rollback_on_cleanup'] = bool(rollback_on_cleanup)
        # Bind the flag via a closure so handler sees the choice
        def _handler(obj: Any, _flag=md['rollback_on_cleanup']):
            self._cleanup_db(obj, rollback_on_cleanup=_flag)
        return self.register(session, resource_type=ResourceType.DATABASE_CONNECTION, description=description,
                             cleanup_handler=_handler, **md)

    # --- Network/DB connection pool helpers --------------------------------
    def _cleanup_network_pool(self, pool: Any) -> None:
        """Cleanup a network connection pool by closing members and the pool itself.

        Best-effort logic:
        - If iterable, iterate and close each member (shutdown() then close() when available).
        - Try common pool-level methods: closeall(), close(), dispose().
        """
        try:
            # Close members if pool is iterable
            try:
                iterator = iter(pool)  # type: ignore[arg-type]
            except TypeError:
                iterator = None
            if iterator is not None:
                for conn in iterator:
                    try:
                        self._cleanup_network(conn)
                    except Exception:
                        self._logger.debug("network pool member cleanup failed", exc_info=True)
            # Pool-level shutdowns
            for meth in ("closeall", "close", "dispose"):
                if hasattr(pool, meth) and callable(getattr(pool, meth)):
                    try:
                        getattr(pool, meth)()
                    except Exception:
                        self._logger.debug(f"network pool {meth}() failed", exc_info=True)
        except Exception:
            self._logger.exception("Network pool cleanup failed")

    def register_network_pool(self, pool: Any, description: str = "", **metadata) -> str:
        """Register a network connection pool for deterministic cleanup."""
        md = dict(metadata or {})
        md['pool'] = True
        return self.register(pool, resource_type=ResourceType.NETWORK_CONNECTION, description=description,
                             cleanup_handler=self._cleanup_network_pool, **md)

    def _cleanup_db_pool(self, pool: Any, rollback_members: bool = False) -> None:
        """Cleanup a database connection/session pool.

        Best-effort logic:
        - If iterable, iterate and cleanup sessions/connections (optional rollback, then close/dispose).
        - Try common pool-level methods: closeall(), dispose(), close().
        """
        try:
            # Close members if pool is iterable
            try:
                iterator = iter(pool)  # type: ignore[arg-type]
            except TypeError:
                iterator = None
            if iterator is not None:
                for session in iterator:
                    try:
                        self._cleanup_db(session, rollback_on_cleanup=rollback_members)
                    except Exception:
                        self._logger.debug("db pool member cleanup failed", exc_info=True)
            # Pool-level teardown
            for meth in ("closeall", "dispose", "close"):
                if hasattr(pool, meth) and callable(getattr(pool, meth)):
                    try:
                        getattr(pool, meth)()
                    except Exception:
                        self._logger.debug(f"db pool {meth}() failed", exc_info=True)
        except Exception:
            self._logger.exception("Database pool cleanup failed")

    def register_db_pool(self, pool: Any, description: str = "", rollback_members: bool = False, **metadata) -> str:
        """Register a database connection/session pool for cleanup.

        When `rollback_members=True`, attempts rollback on each pooled session before closing.
        """
        md = dict(metadata or {})
        md['pool'] = True
        md['rollback_members'] = bool(rollback_members)
        def _handler(obj: Any, _flag=md['rollback_members']):
            self._cleanup_db_pool(obj, rollback_members=_flag)
        return self.register(pool, resource_type=ResourceType.DATABASE_CONNECTION, description=description,
                             cleanup_handler=_handler, **md)

    # --- OpenGL cleanup stubs (log-only until verified) --------------------
    def _cleanup_gl_stub(self, obj: Any, kind: str | None = None) -> None:
        """Placeholder GL cleanup that logs intent; real deletion awaits GL-thread policy."""
        try:
            self._logger.warning("GL cleanup stub invoked for kind=%s; no-op for safety", kind or 'unknown')
        except Exception:
            # Ensure no exceptions propagate from logging
            pass

    def register_gl(self, obj: Any, kind: str, description: str = "", **metadata) -> str:
        """Register an OpenGL resource with GL metadata; cleanup currently logs-only.

        Set metadata 'gl': True and 'gl_kind' to support deterministic ordering and future routing.
        """
        md = dict(metadata or {})
        md['gl'] = True
        md['gl_kind'] = str(kind)
        def _handler(o: Any, _k=md['gl_kind']):
            self._cleanup_gl_stub(o, kind=_k)
        return self.register(obj, resource_type=ResourceType.CUSTOM, description=description,
                             cleanup_handler=_handler, **md)

    def begin_context_menu(self, overlay_id: str, menu: Any) -> bool:
        """Begin a context menu session with z-order priority delegation.
        
        Delegates to utils.z_order_manager.ZOrderManager.begin_context_menu.
        Returns True on success, False otherwise.
        """
        try:
            if not overlay_id or menu is None:
                self._logger.error("begin_context_menu: missing overlay_id or menu")
                return False
            from utils.z_order_manager import get_z_order_manager
            zom = get_z_order_manager()
            return bool(zom.begin_context_menu(overlay_id, menu))
        except Exception as e:
            self._logger.error(f"begin_context_menu delegation failed: {e}")
            return False

    def end_context_menu(self, overlay_id: str, menu: Any) -> bool:
        """End a context menu session and restore normal z-order.
        
        Delegates to utils.z_order_manager.ZOrderManager.end_context_menu.
        Returns True on success, False otherwise.
        """
        try:
            if not overlay_id or menu is None:
                self._logger.error("end_context_menu: missing overlay_id or menu")
                return False
            from utils.z_order_manager import get_z_order_manager
            zom = get_z_order_manager()
            return bool(zom.end_context_menu(overlay_id, menu))
        except Exception as e:
            self._logger.error(f"end_context_menu delegation failed: {e}")
            return False

    def enforce_z_order(self, overlay_id: str) -> bool:
        """Enforce normal z-order for the given overlay via centralized manager.
        
        Delegates to utils.z_order_manager.ZOrderManager.enforce_z_order with
        default priority. Returns True on success, False otherwise.
        """
        try:
            if not overlay_id:
                self._logger.error("enforce_z_order: missing overlay_id")
                return False
            from utils.z_order_manager import get_z_order_manager
            zom = get_z_order_manager()
            return bool(zom.enforce_z_order(overlay_id))
        except Exception as e:
            self._logger.error(f"enforce_z_order delegation failed: {e}")
            return False

    # register_overlay is defined below with optional border_widget for compatibility

    def register_overlay(self, overlay_id: str, main_widget: Any, border_widget: Any | None = None) -> bool:
        """Register an overlay with the unified z-order manager.

        Thin delegation to utils.z_order_manager.ZOrderManager.register_overlay.
        """
        try:
            if not overlay_id or main_widget is None:
                self._logger.error("register_overlay: missing overlay_id or main_widget")
                return False
            from utils.z_order_manager import get_z_order_manager
            zom = get_z_order_manager()
            return bool(zom.register_overlay(overlay_id, main_widget, border_widget))
        except Exception as e:
            self._logger.error(f"register_overlay delegation failed: {e}")
            return False

    def unregister_overlay(self, overlay_id: str) -> bool:
        """Unregister an overlay from the unified z-order manager."""
        try:
            if not overlay_id:
                self._logger.error("unregister_overlay: missing overlay_id")
                return False
            from utils.z_order_manager import get_z_order_manager
            zom = get_z_order_manager()
            return bool(zom.unregister_overlay(overlay_id))
        except Exception as e:
            self._logger.error(f"unregister_overlay delegation failed: {e}")
            return False

    def bring_child_to_front(self, widget: Any) -> bool:
        """Bring a child widget's native window to the front of its parent's z-order."""
        try:
            if widget is None:
                self._logger.error("bring_child_to_front: widget is None")
                return False
            from utils.z_order_manager import get_z_order_manager
            zom = get_z_order_manager()
            return bool(zom.bring_child_to_front(widget))
        except Exception as e:
            self._logger.error(f"bring_child_to_front delegation failed: {e}")
            return False

    def place_window_above(self, widget: Any, reference: Any) -> bool:
        """Place a top-level widget directly above a reference window within the same z-band."""
        try:
            if widget is None or reference is None:
                self._logger.error("place_window_above: missing widget or reference")
                return False
            from utils.z_order_manager import get_z_order_manager
            zom = get_z_order_manager()
            return bool(zom.place_window_above(widget, reference))
        except Exception as e:
            self._logger.error(f"place_window_above delegation failed: {e}")
            return False
    
    def __del__(self):
        """Ensure all resources are cleaned up when the manager is garbage collected."""
        self.shutdown()

    # --- Internal: worker & snapshot publication ----------------------------
    def _publish_snapshot(self) -> None:
        tb = self._snapshot_tb
        if tb is None:
            return
        try:
            # Publish immutable container of current ResourceInfo objects
            tb.publish(tuple(self._resources.values()))
        except Exception as e:
            self._logger.error(f"Snapshot publication failed: {e}")

    def _enqueue_mutation_sync(self, func: Callable[[], Any], timeout: float = 5.0) -> Any:
        """Execute a mutation on the UI thread synchronously.

        - If no Qt app exists, execute directly (test mode) and publish snapshot.
        - If already on UI thread, execute directly.
        - Otherwise, dispatch via ThreadManager.run_on_ui_thread and wait.
        """
        try:
            app = QCoreApplication.instance()
        except Exception:
            app = None
        if app is None:
            # Test environment: no Qt
            result = func()
            self._publish_snapshot()
            return result
        if QThread.currentThread() is app.thread():
            result = func()
            self._publish_snapshot()
            return result

        # Dispatch to UI thread and wait for completion (single-writer policy)
        done = threading.Event()
        holder: Dict[str, Any] = {}

        def _wrap():
            try:
                holder['result'] = func()
            finally:
                # Always publish snapshot after mutation
                try:
                    self._publish_snapshot()
                finally:
                    try:
                        done.set()
                    except Exception:
                        pass

        try:
            # Use internal UI dispatcher (avoids circular import on ThreadManager)
            self._run_on_ui(_wrap)
        except Exception:
            # Best-effort fallback: execute directly to avoid loss of mutation
            result = func()
            self._publish_snapshot()
            return result

        # Wait for UI execution to complete
        done.wait(timeout=max(0.05, float(timeout)))
        return holder.get('result')

    def _mutation_worker_loop(self) -> None:
        """Deprecated: no-op."""
        return
