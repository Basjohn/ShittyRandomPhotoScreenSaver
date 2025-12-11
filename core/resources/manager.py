"""
Resource manager implementation for screensaver.

Simplified version adapted from SPQDocker reusable modules.
Manages resource lifecycle and ensures proper cleanup.
"""
from __future__ import annotations

import atexit
import sys
import uuid
import weakref
import os
import threading
from typing import Any, Callable, Dict, List, Optional, TypeVar, Union

from .types import CleanupProtocol, ResourceInfo, ResourceType
from core.logging.logger import get_logger, is_verbose_logging

T = TypeVar('T')

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
    
    def __init__(self):
        """Initialize the ResourceManager."""
        self._resources: Dict[str, ResourceInfo] = {}
        self._weak_refs: Dict[str, Any] = {}
        self._strong_refs: Dict[str, Any] = {}  # Strong refs for temp files, etc.
        self._cleanup_handlers: Dict[str, Callable[[Any], None]] = {}
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
        self._logger.info("ResourceManager initialized")
    
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
        
        with self._lock:
            # Generate unique ID
            resource_id = f"{resource_type_enum.name.lower()}_{uuid.uuid4().hex[:8]}"
            
            # Create resource info
            resource_info = ResourceInfo(
                resource_id=resource_id,
                resource_type=resource_type_enum,
                description=description,
                metadata=metadata or {}
            )
            
            # Store the resource
            self._resources[resource_id] = resource_info
            
            # Create weak reference with finalizer
            def _finalize(rid: str) -> None:
                if not self._initialized or self._shutdown:
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
                self._cleanup_handlers[resource_id] = (cleanup_handler, False)
            elif isinstance(resource, CleanupProtocol):
                # Store as (handler, is_method) - methods don't need resource arg
                self._cleanup_handlers[resource_id] = (resource.cleanup, True)
            elif hasattr(resource, 'cleanup') and callable(resource.cleanup):
                self._cleanup_handlers[resource_id] = (resource.cleanup, True)
            
            resource_info.increment_reference_count()
            
            self._logger.debug(f"Registered resource: {resource_id} ({description})")
            return resource_id
    
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
            
            # Check reference count
            if not force and self._resources[resource_id].reference_count > 1:
                raise RuntimeError(
                    f"Cannot unregister resource {resource_id} with active references. "
                    f"Reference count: {self._resources[resource_id].reference_count}"
                )
            
            # Get resource and cleanup info before removing
            # Check strong refs first, then weak refs
            resource = self._strong_refs.get(resource_id)
            if resource is None:
                resource = self._weak_refs.get(resource_id, lambda: None)()
            cleanup_info = self._cleanup_handlers.get(resource_id, None)
            
            # Perform cleanup before removing from tracking
            if cleanup_info is not None:
                try:
                    handler, is_method = cleanup_info
                    if is_method:
                        # Method - call without resource arg (only if resource exists)
                        if resource is not None:
                            handler()
                    else:
                        # Function - call with resource arg (only if resource exists)
                        if resource is not None:
                            handler(resource)
                    self._logger.debug(f"Cleaned up resource: {resource_id}")
                except Exception as e:
                    self._logger.error(f"Error cleaning up resource {resource_id}: {e}")
            
            # Now remove from tracking
            self._cleanup_handlers.pop(resource_id, None)
            self._resources.pop(resource_id, None)
            self._weak_refs.pop(resource_id, None)
            self._strong_refs.pop(resource_id, None)  # Remove strong ref if exists
            
            return True
    
    def _finalize_resource(self, resource_id: str) -> None:
        """Called when a resource is garbage collected."""
        with self._lock:
            if resource_id in self._cleanup_handlers:
                # Resource was GC'd but handler still exists. The detailed
                # per-id debug message is only useful when running in verbose
                # diagnostics mode; for normal debug runs we keep logs tight.
                self._cleanup_handlers.pop(resource_id, None)
                self._resources.pop(resource_id, None)
                if is_verbose_logging():
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
        
        with self._lock:
            # Group resources for deterministic cleanup ordering
            groups = {
                'qt': [],
                'network': [],
                'cache': [],
                'filesystem': [],
                'other': []
            }
            
            for resource_id, info in self._resources.items():
                groups[info.group].append(resource_id)
            
            # Cleanup order: Qt first, then others
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
                except Exception:
                    pass
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
        except Exception:
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
                except Exception:
                    pass
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
        except Exception:
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
