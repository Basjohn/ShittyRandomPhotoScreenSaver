"""
Resource type definitions for screensaver resource management.

Adapted from SPQDocker reusable modules.
"""
from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from enum import Enum, auto
from typing import Any, Dict, Protocol, runtime_checkable


class ResourceType(Enum):
    """Types of resources that can be managed."""
    UNKNOWN = auto()
    FILE_HANDLE = auto()
    NETWORK_CONNECTION = auto()
    GUI_COMPONENT = auto()
    THREAD = auto()
    TIMER = auto()
    WINDOW = auto()
    THREAD_POOL = auto()
    IMAGE_CACHE = auto()
    TEMP_IMAGE = auto()
    NETWORK_REQUEST = auto()
    CUSTOM = auto()
    
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
        """Clean up the resource (idempotent)."""
        ...


@dataclass
class ResourceInfo:
    """Information about a managed resource."""
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
        try:
            self.group = self._derive_group()
        except Exception:
            self.group = "other"
    
    def _derive_group(self) -> str:
        """Compute the resource group from type and metadata."""
        rt = self.resource_type
        
        # Qt types
        if rt in {ResourceType.GUI_COMPONENT, ResourceType.TIMER, ResourceType.WINDOW}:
            return 'qt'
        # Network
        if rt in {ResourceType.NETWORK_CONNECTION, ResourceType.NETWORK_REQUEST}:
            return 'network'
        # Filesystem
        if rt in {ResourceType.FILE_HANDLE}:
            return 'filesystem'
        # Cache
        if rt in {ResourceType.IMAGE_CACHE, ResourceType.TEMP_IMAGE}:
            return 'cache'
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
            bool: True if the reference count is now zero
        """
        if self.reference_count > 0:
            self.reference_count -= 1
        self.touch()
        return self.reference_count == 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert the resource info to a dictionary."""
        result = asdict(self)
        result['resource_type'] = self.resource_type.name
        result['created_at'] = self.created_at
        result['last_accessed'] = self.last_accessed
        result['reference_count'] = self.reference_count
        return result
