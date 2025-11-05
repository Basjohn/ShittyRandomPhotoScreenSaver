"""
Folder-based image source for screensaver.

Scans local directories for image files.
"""
import os
from pathlib import Path
from typing import List, Set
from datetime import datetime
from sources.base_provider import ImageProvider, ImageMetadata, ImageSourceType
from core.logging.logger import get_logger

logger = get_logger(__name__)

# Supported image formats
SUPPORTED_EXTENSIONS = {
    '.jpg', '.jpeg',  # JPEG
    '.png',           # PNG
    '.bmp',           # Bitmap
    '.gif',           # GIF
    '.webp',          # WebP
    '.tiff', '.tif',  # TIFF
    '.ico',           # Icon
    '.jfif',          # JPEG File Interchange Format
}


class FolderSource(ImageProvider):
    """
    Image provider that scans a local folder for images.
    
    Features:
    - Recursive or non-recursive scanning
    - Supports all common image formats
    - Caches scan results
    - Handles permission errors gracefully
    """
    
    def __init__(self, folder_path: str | Path, recursive: bool = True, 
                 source_id: str = None):
        """
        Initialize folder source.
        
        Args:
            folder_path: Path to folder to scan
            recursive: If True, scan subdirectories recursively
            source_id: Optional custom source ID (defaults to folder name)
        """
        self.folder_path = Path(folder_path)
        self.recursive = recursive
        
        # Use folder name as source_id if not provided
        if source_id is None:
            source_id = self.folder_path.name or str(self.folder_path)
        
        super().__init__(source_id, ImageSourceType.FOLDER)
        
        self._images: List[ImageMetadata] = []
        self._last_scan: datetime | None = None
        
        self._logger.info(f"Created FolderSource for '{self.folder_path}' "
                         f"(recursive={recursive})")
    
    def get_images(self) -> List[ImageMetadata]:
        """
        Get all images from this folder.
        
        Returns cached results if available, otherwise scans the folder.
        
        Returns:
            List of ImageMetadata objects
        """
        if not self._images:
            self.refresh()
        return self._images.copy()
    
    def refresh(self) -> bool:
        """
        Scan the folder for images.
        
        Returns:
            True if scan was successful, False otherwise
        """
        if not self.is_available():
            self._logger.error(f"Folder not available: {self.folder_path}")
            return False
        
        self._logger.info(f"Scanning folder: {self.folder_path}")
        start_time = datetime.now()
        
        try:
            images = []
            scanned_files = 0
            found_images = 0
            
            # Choose scanning method
            if self.recursive:
                pattern = '**/*'
            else:
                pattern = '*'
            
            # Scan for image files
            for file_path in self.folder_path.glob(pattern):
                if not file_path.is_file():
                    continue
                
                scanned_files += 1
                
                # Check if file is an image
                if file_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
                    continue
                
                # Create metadata
                try:
                    metadata = self._create_metadata(file_path)
                    images.append(metadata)
                    found_images += 1
                except Exception as e:
                    self._logger.warning(f"Error processing {file_path}: {e}")
                    continue
            
            # Update cache
            self._images = images
            self._last_scan = datetime.now()
            
            scan_duration = (datetime.now() - start_time).total_seconds()
            self._logger.info(f"Scan complete: {found_images} images found "
                            f"({scanned_files} files scanned) in {scan_duration:.2f}s")
            
            return True
            
        except PermissionError as e:
            self._logger.error(f"Permission denied accessing {self.folder_path}: {e}")
            return False
        except Exception as e:
            self._logger.error(f"Error scanning folder: {e}", exc_info=True)
            return False
    
    def is_available(self) -> bool:
        """
        Check if folder exists and is readable.
        
        Returns:
            True if folder is available
        """
        try:
            return self.folder_path.exists() and self.folder_path.is_dir() and os.access(self.folder_path, os.R_OK)
        except Exception as e:
            self._logger.debug(f"Error checking folder availability: {e}")
            return False
    
    def _create_metadata(self, file_path: Path) -> ImageMetadata:
        """
        Create ImageMetadata for a file.
        
        Args:
            file_path: Path to image file
        
        Returns:
            ImageMetadata object
        """
        # Get file stats
        stat = file_path.stat()
        
        # Create unique image ID (relative path from source folder)
        try:
            relative_path = file_path.relative_to(self.folder_path)
            image_id = str(relative_path).replace('\\', '/')
        except ValueError:
            # File is not relative to folder (shouldn't happen)
            image_id = file_path.name
        
        # Create metadata
        metadata = ImageMetadata(
            source_type=ImageSourceType.FOLDER,
            source_id=self.source_id,
            image_id=image_id,
            local_path=file_path,
            title=file_path.stem,  # Filename without extension
            file_size=stat.st_size,
            format=file_path.suffix[1:].lower(),  # Remove leading dot
            created_date=datetime.fromtimestamp(stat.st_ctime),
            modified_date=datetime.fromtimestamp(stat.st_mtime),
        )
        
        return metadata
    
    def get_source_info(self) -> dict:
        """
        Get information about this folder source.
        
        Returns:
            Dictionary with source information
        """
        info = super().get_source_info()
        info.update({
            'folder_path': str(self.folder_path),
            'recursive': self.recursive,
            'image_count': len(self._images),
            'last_scan': self._last_scan.isoformat() if self._last_scan else None
        })
        return info
    
    def get_supported_extensions(self) -> Set[str]:
        """Get set of supported image extensions."""
        return SUPPORTED_EXTENSIONS.copy()
    
    def __str__(self) -> str:
        """String representation."""
        mode = "recursive" if self.recursive else "non-recursive"
        return f"FolderSource({self.folder_path}, {mode}, {len(self._images)} images)"
