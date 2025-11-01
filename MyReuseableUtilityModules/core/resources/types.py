"""
Resource type definitions for resource management.

This module defines the types and interfaces used by the resource management system.
"""
from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from enum import Enum, auto
from typing import Any, Dict, Optional, Protocol, runtime_checkable


class ResourceType(Enum):
    """Types of resources that can be managed."""
    UNKNOWN = auto()
    FILE_HANDLE = auto()
    NETWORK_CONNECTION = auto()
    DATABASE_CONNECTION = auto()
    GUI_COMPONENT = auto()
    THREAD = auto()
    PROCESS = auto()
    MEMORY_BUFFER = auto()
    CACHE = auto()
    LOCK = auto()
    TIMER = auto()
    WINDOW = auto()
    WINDOW_MANAGER = auto()
    THREAD_POOL = auto()
    CLEANUP_HANDLER = auto()
    CUSTOM = auto()
    # OpenGL-related (Phase 3 cleanup parity)
    TEXTURE = auto()
    OPENGL_SHADER = auto()
    OPENGL_SHADER_PROGRAM = auto()
    OPENGL_BUFFER = auto()
    OPENGL_FRAMEBUFFER = auto()
    OPENGL_RENDERBUFFER = auto()
    OPENGL_QUERY = auto()
    OPENGL_VERTEX_ARRAY = auto()
    OPENGL_SYNC = auto()
    OPENGL_CONTEXT = auto()
    
    @classmethod
    def from_string(cls, value: str) -> 'ResourceType':
        """Convert a string to a ResourceType enum value."""
        try:
            return cls[value.upper()]
        except KeyError:
            return cls.UNKNOWN


@runtime_checkable
class CleanupProtocol(Protocol):
    """Protocol for objects that implement their own cleanup logic."""
    def cleanup(self) -> None:
        """Clean up the resource.
        
        This method should be idempotent and safe to call multiple times.
        It should release any system resources held by the resource.
        """
        ...


@dataclass
class ResourceInfo:
    """Information about a managed resource.
    
    Attributes:
        resource_id: Unique identifier for the resource
        resource_type: Type of the resource
        group: Derived group for deterministic cleanup ordering (e.g., 'qt', 'network_db', 'opengl', 'filesystem', 'other')
        description: Human-readable description
        metadata: Additional metadata about the resource
        created_at: Timestamp when the resource was created
        last_accessed: Timestamp when the resource was last accessed
        reference_count: Number of active references to this resource
    """
    resource_id: str
    resource_type: ResourceType
    group: str = ""
    description: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time, init=False)
    last_accessed: float = field(init=False)
    reference_count: int = 0
    
    def __post_init__(self) -> None:
        """Initialize the resource info."""
        self.last_accessed = self.created_at
        # Derive group from type/metadata for deterministic cleanup ordering
        try:
            self.group = self._derive_group()
        except Exception:
            # Never raise from dataclass init; default to 'other'
            self.group = "other"
    
    def _derive_group(self) -> str:
        """Compute the resource group from type and metadata."""
        rt = self.resource_type
        md = self.metadata or {}
        # OpenGL via metadata flag
        if md.get('gl'):
            return 'opengl'
        # Qt types
        if rt in {ResourceType.GUI_COMPONENT, ResourceType.TIMER, ResourceType.WINDOW, ResourceType.WINDOW_MANAGER}:
            return 'qt'
        # Network/DB
        if rt in {ResourceType.NETWORK_CONNECTION, ResourceType.DATABASE_CONNECTION}:
            return 'network_db'
        # Filesystem
        if rt in {ResourceType.FILE_HANDLE}:
            return 'filesystem'
        return 'other'
    
    def touch(self) -> None:
        """Update the last accessed time to now."""
        self.last_accessed = time.time()
    
    def increment_reference_count(self) -> None:
        """Increment the reference count for this resource."""
        self.reference_count += 1
        self.touch()
    
    def decrement_reference_count(self) -> bool:
        """Decrement the reference count for this resource.
        
        Returns:
            bool: True if the reference count is now zero, False otherwise
        """
        if self.reference_count > 0:
            self.reference_count -= 1
        self.touch()
        return self.reference_count == 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert the resource info to a dictionary.
        
        Returns:
            Dict containing the resource information
        """
        result = asdict(self)
        result['resource_type'] = self.resource_type.name
        result['created_at'] = self.created_at
        result['last_accessed'] = self.last_accessed
        result['reference_count'] = self.reference_count
        return result
