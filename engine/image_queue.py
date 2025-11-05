"""
Image queue management for screensaver.

Handles image queue with shuffle, history, and wraparound.
"""
import random
from typing import List, Optional, Set
from collections import deque
from sources.base_provider import ImageMetadata
from core.logging.logger import get_logger

logger = get_logger(__name__)


class ImageQueue:
    """
    Manage queue of images for screensaver display.
    
    Features:
    - Queue management with add/clear
    - Shuffle functionality
    - History tracking (prevent recent repeats)
    - Queue wraparound (restart from beginning)
    - Current image tracking
    - Statistics
    """
    
    def __init__(self, shuffle: bool = True, history_size: int = 50):
        """
        Initialize image queue.
        
        Args:
            shuffle: Whether to shuffle images
            history_size: Number of recent images to track
        """
        self.shuffle_enabled = shuffle
        self.history_size = history_size
        
        self._images: List[ImageMetadata] = []
        self._queue: deque[ImageMetadata] = deque()
        self._history: deque[str] = deque(maxlen=history_size)
        self._current_image: Optional[ImageMetadata] = None
        self._current_index: int = -1
        self._wrap_count: int = 0
        
        logger.info(f"ImageQueue initialized (shuffle={shuffle}, history_size={history_size})")
    
    def add_images(self, images: List[ImageMetadata]) -> int:
        """
        Add images to the queue.
        
        Args:
            images: List of image metadata to add
        
        Returns:
            Number of images added
        """
        if not images:
            logger.warning("No images provided to add_images()")
            return 0
        
        # Store original list
        self._images.extend(images)
        
        # Add to queue
        if self.shuffle_enabled:
            # Shuffle new images before adding
            shuffled = images.copy()
            random.shuffle(shuffled)
            self._queue.extend(shuffled)
            logger.debug(f"Added {len(images)} shuffled images to queue")
        else:
            self._queue.extend(images)
            logger.debug(f"Added {len(images)} images to queue (no shuffle)")
        
        logger.info(f"Queue now has {len(self._queue)} images ({len(self._images)} total)")
        return len(images)
    
    def set_images(self, images: List[ImageMetadata]) -> int:
        """
        Replace all images in the queue.
        
        Args:
            images: New list of images
        
        Returns:
            Number of images set
        """
        self.clear()
        return self.add_images(images)
    
    def next(self) -> Optional[ImageMetadata]:
        """
        Get next image from queue.
        
        Returns:
            Next image metadata, or None if queue is empty
        """
        if not self._queue:
            # Queue is empty
            if self._images:
                # Rebuild queue from original list
                logger.info(f"Queue empty, rebuilding from {len(self._images)} images (wrap #{self._wrap_count + 1})")
                self._rebuild_queue()
                self._wrap_count += 1
            else:
                logger.warning("[FALLBACK] No images available in queue")
                return None
        
        if not self._queue:
            logger.warning("[FALLBACK] Queue still empty after rebuild")
            return None
        
        # Get next image
        self._current_image = self._queue.popleft()
        self._current_index += 1
        
        # Add to history
        self._history.append(str(self._current_image.local_path))
        
        logger.debug(f"Next image: {self._current_image.local_path} (index {self._current_index})")
        return self._current_image
    
    def previous(self) -> Optional[ImageMetadata]:
        """
        Go back to previous image in history.
        
        Returns:
            Previous image metadata, or None if no history
        """
        if len(self._history) < 2:
            logger.warning("[FALLBACK] No previous image in history")
            return self._current_image
        
        # Remove current from history
        self._history.pop()
        
        # Get previous path
        prev_path = self._history[-1]
        
        # Find image by path
        for img in self._images:
            if str(img.local_path) == prev_path:
                self._current_image = img
                self._current_index = max(0, self._current_index - 1)
                logger.debug(f"Previous image: {img.local_path}")
                return img
        
        logger.warning(f"[FALLBACK] Previous image not found: {prev_path}")
        return self._current_image
    
    def current(self) -> Optional[ImageMetadata]:
        """
        Get current image without advancing queue.
        
        Returns:
            Current image metadata, or None if no current image
        """
        return self._current_image
    
    def peek(self) -> Optional[ImageMetadata]:
        """
        Peek at next image without removing from queue.
        
        Returns:
            Next image metadata, or None if queue is empty
        """
        if self._queue:
            return self._queue[0]
        
        if self._images:
            # Would rebuild, return first from rebuild
            if self.shuffle_enabled:
                # Can't predict shuffle, return None
                return None
            else:
                return self._images[0]
        
        return None
    
    def _rebuild_queue(self) -> None:
        """Rebuild queue from original image list."""
        if not self._images:
            return
        
        # Start with all images
        if self.shuffle_enabled:
            # Shuffle
            shuffled = self._images.copy()
            random.shuffle(shuffled)
            self._queue.extend(shuffled)
        else:
            # Keep original order
            self._queue.extend(self._images)
        
        logger.debug(f"Queue rebuilt with {len(self._queue)} images")
    
    def shuffle(self) -> None:
        """Shuffle current queue."""
        if not self._queue:
            logger.debug("Queue empty, nothing to shuffle")
            return
        
        # Convert to list, shuffle, rebuild deque
        queue_list = list(self._queue)
        random.shuffle(queue_list)
        self._queue = deque(queue_list)
        
        logger.info(f"Queue shuffled ({len(self._queue)} images)")
    
    def set_shuffle_enabled(self, enabled: bool) -> None:
        """
        Enable or disable shuffle mode.
        
        Args:
            enabled: True to enable shuffle
        """
        if enabled == self.shuffle_enabled:
            return
        
        self.shuffle_enabled = enabled
        logger.info(f"Shuffle {'enabled' if enabled else 'disabled'}")
        
        # Rebuild queue with new shuffle setting
        if self._images:
            remaining = list(self._queue)
            self._queue.clear()
            
            if enabled:
                random.shuffle(remaining)
            
            self._queue.extend(remaining)
            logger.debug(f"Queue rebuilt with new shuffle setting")
    
    def clear(self) -> None:
        """Clear all images and reset queue."""
        count = len(self._images)
        
        self._images.clear()
        self._queue.clear()
        self._history.clear()
        self._current_image = None
        self._current_index = -1
        self._wrap_count = 0
        
        logger.info(f"Queue cleared ({count} images removed)")
    
    def size(self) -> int:
        """
        Get number of images remaining in queue.
        
        Returns:
            Number of images in queue
        """
        return len(self._queue)
    
    def total_images(self) -> int:
        """
        Get total number of images (including already shown).
        
        Returns:
            Total image count
        """
        return len(self._images)
    
    def is_empty(self) -> bool:
        """
        Check if queue is empty.
        
        Returns:
            True if no images available
        """
        return len(self._images) == 0
    
    def get_history(self, count: int = 10) -> List[str]:
        """
        Get recent image history.
        
        Args:
            count: Number of recent images to return
        
        Returns:
            List of recent image paths (most recent last)
        """
        history_list = list(self._history)
        return history_list[-count:] if count < len(history_list) else history_list
    
    def is_in_recent_history(self, image_path: str, lookback: int = 10) -> bool:
        """
        Check if image was recently shown.
        
        Args:
            image_path: Path to check
            lookback: Number of recent images to check
        
        Returns:
            True if image was shown recently
        """
        recent = self.get_history(lookback)
        return image_path in recent
    
    def get_wrap_count(self) -> int:
        """
        Get number of times queue has wrapped around.
        
        Returns:
            Wrap count
        """
        return self._wrap_count
    
    def get_current_index(self) -> int:
        """
        Get current position in overall sequence.
        
        Returns:
            Current index (-1 if no current image)
        """
        return self._current_index
    
    def get_stats(self) -> dict:
        """
        Get queue statistics.
        
        Returns:
            Dict with queue stats
        """
        return {
            'total_images': len(self._images),
            'remaining': len(self._queue),
            'current_index': self._current_index,
            'wrap_count': self._wrap_count,
            'history_size': len(self._history),
            'shuffle_enabled': self.shuffle_enabled,
            'current_image': str(self._current_image.local_path) if self._current_image else None
        }
    
    def remove_image(self, image_path: str) -> bool:
        """
        Remove specific image from queue by path.
        
        Args:
            image_path: Path of image to remove
        
        Returns:
            True if image was found and removed
        """
        # Remove from main list
        removed_from_list = False
        for i, img in enumerate(self._images):
            if str(img.local_path) == image_path:
                self._images.pop(i)
                removed_from_list = True
                break
        
        # Remove from queue
        removed_from_queue = False
        queue_list = list(self._queue)
        new_queue = [img for img in queue_list if str(img.local_path) != image_path]
        
        if len(new_queue) < len(queue_list):
            self._queue = deque(new_queue)
            removed_from_queue = True
        
        if removed_from_list or removed_from_queue:
            logger.info(f"Removed image from queue: {image_path}")
            return True
        
        logger.debug(f"Image not found in queue: {image_path}")
        return False
    
    def __len__(self) -> int:
        """Get number of images in queue."""
        return len(self._queue)
    
    def __bool__(self) -> bool:
        """Check if queue has images."""
        return len(self._images) > 0
    
    def __repr__(self) -> str:
        """String representation."""
        return (f"ImageQueue(total={len(self._images)}, remaining={len(self._queue)}, "
                f"shuffle={self.shuffle_enabled}, wraps={self._wrap_count})")
