"""
Base image provider interface for screensaver.

Defines the abstract interface that all image sources must implement.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional, List
from core.logging.logger import get_logger

logger = get_logger(__name__)


class ImageSourceType(Enum):
    """Type of image source."""
    FOLDER = "folder"
    RSS = "rss"
    CUSTOM = "custom"


@dataclass
class ImageMetadata:
    """
    Metadata for an image from any source.
    
    This is the common data structure used by all image providers
    to describe available images.
    """
    # Required fields
    source_type: ImageSourceType
    source_id: str  # Unique identifier for this source
    image_id: str   # Unique identifier for this image within the source
    
    # Path/URL fields (at least one must be provided)
    local_path: Optional[Path] = None  # Local file path
    url: Optional[str] = None          # Remote URL (for RSS feeds)
    
    # Optional metadata
    title: Optional[str] = None
    description: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    file_size: Optional[int] = None
    format: Optional[str] = None  # e.g., "jpg", "png"
    
    # Timestamps
    created_date: Optional[datetime] = None
    modified_date: Optional[datetime] = None
    fetched_date: Optional[datetime] = None
    
    # Source-specific metadata
    tags: Optional[List[str]] = None
    author: Optional[str] = None
    copyright: Optional[str] = None
    
    def __post_init__(self):
        """Validate metadata after initialization."""
        if not self.local_path and not self.url:
            raise ValueError("ImageMetadata must have either local_path or url")
        
        if not self.source_id:
            raise ValueError("ImageMetadata must have a source_id")
        
        if not self.image_id:
            raise ValueError("ImageMetadata must have an image_id")
    
    def is_local(self) -> bool:
        """Check if image is available locally."""
        return self.local_path is not None and self.local_path.exists()
    
    def is_remote(self) -> bool:
        """Check if image is from a remote source."""
        return self.url is not None
    
    def get_display_name(self) -> str:
        """Get a human-readable name for this image."""
        if self.title:
            return self.title
        if self.local_path:
            return self.local_path.name
        if self.url:
            return self.url.split('/')[-1]
        return self.image_id
    
    def __str__(self) -> str:
        """String representation."""
        name = self.get_display_name()
        source = f"{self.source_type.value}:{self.source_id}"
        if self.width and self.height:
            return f"{name} ({self.width}x{self.height}) [{source}]"
        return f"{name} [{source}]"


class ImageProvider(ABC):
    """
    Abstract base class for image providers.
    
    All image sources (folders, RSS feeds, etc.) must implement this interface.
    """
    
    def __init__(self, source_id: str, source_type: ImageSourceType):
        """
        Initialize the image provider.
        
        Args:
            source_id: Unique identifier for this source
            source_type: Type of source
        """
        self.source_id = source_id
        self.source_type = source_type
        self._logger = logger.getChild(f"{source_type.value}.{source_id}")
    
    @abstractmethod
    def get_images(self) -> List[ImageMetadata]:
        """
        Get all available images from this source.
        
        This method should return the complete list of images available
        from this source. For folder sources, this means scanning the
        directory. For RSS feeds, this means parsing the feed.
        
        Returns:
            List of ImageMetadata objects
        
        Raises:
            Exception: If source cannot be accessed or parsed
        """
        pass
    
    @abstractmethod
    def refresh(self) -> bool:
        """
        Refresh the image list from the source.
        
        This should re-scan/re-fetch the image list. For folders,
        this rescans the directory. For RSS feeds, this re-fetches
        the feed.
        
        Returns:
            True if refresh was successful, False otherwise
        """
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """
        Check if this source is currently available.
        
        For folder sources, this checks if the folder exists and is readable.
        For RSS feeds, this might check network connectivity.
        
        Returns:
            True if source is available, False otherwise
        """
        pass
    
    def get_source_info(self) -> dict:
        """
        Get information about this source.
        
        Returns:
            Dictionary with source information
        """
        return {
            'source_id': self.source_id,
            'source_type': self.source_type.value,
            'available': self.is_available()
        }
    
    def __str__(self) -> str:
        """String representation."""
        return f"{self.source_type.value}:{self.source_id}"
    
    def __repr__(self) -> str:
        """Developer representation."""
        return f"<{self.__class__.__name__} source_id={self.source_id}>"
