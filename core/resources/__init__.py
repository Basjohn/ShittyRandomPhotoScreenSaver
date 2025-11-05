"""Resource management for screensaver application."""

from .manager import ResourceManager
from .types import ResourceType, ResourceInfo, CleanupProtocol

__all__ = ['ResourceManager', 'ResourceType', 'ResourceInfo', 'CleanupProtocol']
