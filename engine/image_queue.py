"""
Image queue management for screensaver.

Handles image queue with shuffle, history, wraparound, and ratio-based
source selection between local folders and RSS/JSON feeds.
"""
import random
import threading
from typing import List, Optional
from collections import deque
from urllib.parse import urlparse
from sources.base_provider import ImageMetadata, ImageSourceType
from core.logging.logger import get_logger

logger = get_logger(__name__)

# History lookback constants - RSS needs longer history to avoid repetition
# with small cache sizes
LOCAL_IMAGE_LOOKBACK = 5   # Local images can repeat after 5 transitions
RSS_IMAGE_LOOKBACK = 15    # RSS images need 15+ transitions before repeat


def _extract_domain(image: ImageMetadata) -> str:
    """Extract domain from RSS image URL or source_id for diversity tracking."""
    # Try URL first
    if image.url:
        try:
            parsed = urlparse(image.url)
            return parsed.netloc.lower()
        except Exception:
            pass
    # Try source_id (often contains feed URL)
    if image.source_id:
        try:
            if '/' in image.source_id:
                # Likely a URL-based source_id
                parsed = urlparse(image.source_id)
                if parsed.netloc:
                    return parsed.netloc.lower()
        except Exception:
            pass
    return "unknown"


class ImageQueue:
    """
    Manage queue of images for screensaver display.
    
    Features:
    - Queue management with add/clear
    - Shuffle functionality
    - History tracking (prevent recent repeats)
    - Queue wraparound (restart from beginning)
    - Current image tracking
    - Ratio-based source selection (local vs RSS)
    - Fallback logic when sources unavailable
    - Statistics
    """
    
    def __init__(self, shuffle: bool = True, history_size: int = 50, local_ratio: int = 60):
        """
        Initialize image queue.
        
        Args:
            shuffle: Whether to shuffle images
            history_size: Number of recent images to track
            local_ratio: Percentage of images from local sources (0-100).
                        Remaining percentage comes from RSS/JSON feeds.
                        Only active when both source types are available.
        """
        # Ensure shuffle is boolean (settings may return strings)
        if isinstance(shuffle, str):
            self.shuffle_enabled = shuffle.lower() == 'true'
        else:
            self.shuffle_enabled = bool(shuffle)
        self.history_size = history_size
        
        # Ratio-based source selection
        self._local_ratio = max(0, min(100, int(local_ratio)))
        
        # Separate pools for local and RSS images
        self._local_images: List[ImageMetadata] = []
        self._rss_images: List[ImageMetadata] = []
        self._local_queue: deque[ImageMetadata] = deque()
        self._rss_queue: deque[ImageMetadata] = deque()
        
        # Combined view for backwards compatibility
        self._images: List[ImageMetadata] = []
        self._queue: deque[ImageMetadata] = deque()
        
        # FIX: Store ImageMetadata objects directly instead of string paths (fixes RSS None path issue)
        self._history: deque[ImageMetadata] = deque(maxlen=history_size)
        self._current_image: Optional[ImageMetadata] = None
        self._current_index: int = -1
        self._wrap_count: int = 0
        
        # Tracking for ratio enforcement
        self._local_count: int = 0
        self._rss_count: int = 0
        
        # Track last RSS domain for diversity (prefer different domains)
        self._last_rss_domain: str = ""
        
        # FIX: Add thread safety with RLock (reentrant for same thread)
        self._lock = threading.RLock()
        
        logger.info(f"ImageQueue initialized (shuffle={shuffle}, history_size={history_size}, local_ratio={local_ratio}%)")
    
    def add_images(self, images: List[ImageMetadata]) -> int:
        """
        Add images to the queue (thread-safe).
        
        Images are automatically categorized into local or RSS pools based on
        their source_type. The ratio-based selection uses these separate pools.
        
        Args:
            images: List of image metadata to add
        
        Returns:
            Number of images added
        """
        if not images:
            logger.warning("No images provided to add_images()")
            return 0
        
        # FIX: Thread-safe queue modification
        with self._lock:
            # Categorize images by source type
            local_new: List[ImageMetadata] = []
            rss_new: List[ImageMetadata] = []
            
            for img in images:
                if img.source_type == ImageSourceType.FOLDER:
                    local_new.append(img)
                else:
                    # RSS, CUSTOM, or any other type goes to RSS pool
                    rss_new.append(img)
            
            # Store in respective pools
            self._local_images.extend(local_new)
            self._rss_images.extend(rss_new)
            self._images.extend(images)  # Combined for backwards compatibility
            
            # Add to respective queues
            if self.shuffle_enabled:
                if local_new:
                    shuffled_local = local_new.copy()
                    random.shuffle(shuffled_local)
                    self._local_queue.extend(shuffled_local)
                if rss_new:
                    shuffled_rss = rss_new.copy()
                    random.shuffle(shuffled_rss)
                    self._rss_queue.extend(shuffled_rss)
                # Combined queue for backwards compatibility
                shuffled = images.copy()
                random.shuffle(shuffled)
                self._queue.extend(shuffled)
            else:
                self._local_queue.extend(local_new)
                self._rss_queue.extend(rss_new)
                self._queue.extend(images)
            
            logger.info(
                f"Added {len(images)} images (local={len(local_new)}, rss={len(rss_new)}). "
                f"Pools: local={len(self._local_queue)}, rss={len(self._rss_queue)}"
            )
            return len(images)
    
    def set_images(self, images: List[ImageMetadata]) -> int:
        """
        Replace all images in the queue (thread-safe).
        
        Args:
            images: New list of images
        
        Returns:
            Number of images set
        """
        # FIX: Lock both operations atomically
        with self._lock:
            self.clear()
            return self.add_images(images)
    
    def set_local_ratio(self, ratio: int) -> None:
        """
        Set the local/RSS usage ratio.
        
        Args:
            ratio: Percentage of images from local sources (0-100)
        """
        with self._lock:
            old_ratio = self._local_ratio
            self._local_ratio = max(0, min(100, int(ratio)))
            if old_ratio != self._local_ratio:
                logger.info(f"Local ratio changed: {old_ratio}% -> {self._local_ratio}%")
    
    def get_local_ratio(self) -> int:
        """Get current local/RSS usage ratio."""
        return self._local_ratio
    
    def _should_use_local(self) -> bool:
        """
        Determine if next image should come from local pool based on ratio.
        
        Uses a probabilistic approach with smart fallback:
        - If RSS pool is too small (< 5 unique images), prefer local to avoid repeats
        - Otherwise use ratio-based selection
        
        Returns:
            True if should use local pool, False for RSS pool
        """
        # If only one pool has images, use that pool
        has_local = len(self._local_queue) > 0 or len(self._local_images) > 0
        has_rss = len(self._rss_queue) > 0 or len(self._rss_images) > 0
        
        if has_local and not has_rss:
            return True
        if has_rss and not has_local:
            return False
        if not has_local and not has_rss:
            return True  # Doesn't matter, both empty
        
        # Both pools have images
        rss_pool_size = len(self._rss_queue) + len(self._rss_images)
        
        # If RSS pool is too small, strongly prefer local to avoid repeats
        # This prevents the same few RSS images from appearing over and over
        if rss_pool_size < 5:
            # 90% chance to use local when RSS pool is tiny
            return random.randint(0, 99) < 90
        elif rss_pool_size < 10:
            # 80% chance to use local when RSS pool is small
            return random.randint(0, 99) < 80
        
        # Normal ratio-based selection
        return random.randint(0, 99) < self._local_ratio
    
    def _rebuild_local_queue(self) -> None:
        """Rebuild local queue from local images."""
        if not self._local_images:
            return
        if self.shuffle_enabled:
            shuffled = self._local_images.copy()
            random.shuffle(shuffled)
            self._local_queue.extend(shuffled)
        else:
            self._local_queue.extend(self._local_images)
        logger.debug(f"Local queue rebuilt with {len(self._local_queue)} images")
    
    def _rebuild_rss_queue(self) -> None:
        """Rebuild RSS queue from RSS images."""
        if not self._rss_images:
            return
        if self.shuffle_enabled:
            shuffled = self._rss_images.copy()
            random.shuffle(shuffled)
            self._rss_queue.extend(shuffled)
        else:
            self._rss_queue.extend(self._rss_images)
        logger.debug(f"RSS queue rebuilt with {len(self._rss_queue)} images")
    
    def _get_image_key(self, image: ImageMetadata) -> str:
        """Get a unique key for an image to check for duplicates."""
        if image.local_path:
            return str(image.local_path)
        return image.url or ""
    
    def _is_in_recent_history(self, image: ImageMetadata, lookback: Optional[int] = None) -> bool:
        """Check if image was shown in the last N images.
        
        Uses different lookback values for RSS vs local images to prevent
        RSS image repetition with small cache sizes.
        """
        if not self._history:
            return False
        key = self._get_image_key(image)
        if not key:
            return False
        
        # Use appropriate lookback based on image source type
        if lookback is None:
            if image.source_type == ImageSourceType.RSS:
                lookback = RSS_IMAGE_LOOKBACK
            else:
                lookback = LOCAL_IMAGE_LOOKBACK
        
        # Check last N items in history
        recent = list(self._history)[-lookback:]
        for hist_img in recent:
            hist_key = self._get_image_key(hist_img)
            if hist_key == key:
                return True
        return False
    
    def next(self) -> Optional[ImageMetadata]:
        """
        Get next image from queue using ratio-based source selection (thread-safe).
        
        Selection priority (fallback order):
        1. Local New > RSS Different Domain > Local Cache > RSS Cache
        
        When both local and RSS sources are available, uses the configured
        local_ratio to probabilistically select from the appropriate pool.
        Falls back to the other pool if the selected pool is empty.
        
        Ensures the same image is not returned twice in a row by checking
        recent history and trying alternative images. For RSS images, also
        prefers images from different domains than the last RSS image.
        
        Returns:
            Next image metadata, or None if all queues are empty
        """
        with self._lock:
            # Determine which pool to use
            use_local = self._should_use_local()
            
            # Collect candidates from the appropriate pool without permanently removing them
            # We'll scan through available images to find one not in recent history
            image = None
            skipped_candidates = []
            different_domain_candidate = None  # Track a valid RSS from different domain
            
            # Try primary pool first, then fallback
            pools_to_try = []
            if use_local:
                pools_to_try = [('local', self._get_from_local_pool), ('rss', self._get_from_rss_pool)]
            else:
                pools_to_try = [('rss', self._get_from_rss_pool), ('local', self._get_from_local_pool)]
            
            # Add combined queue as last resort
            pools_to_try.append(('combined', self._get_from_combined_queue))
            
            for pool_name, get_func in pools_to_try:
                # Try to get up to 15 images from this pool to find a non-duplicate
                # (increased from 10 to match RSS_IMAGE_LOOKBACK)
                for _ in range(15):
                    candidate = get_func()
                    if candidate is None:
                        break
                    
                    # Check if this image is in recent history
                    # Uses source-type-aware lookback (RSS=15, local=5)
                    if not self._is_in_recent_history(candidate):
                        # For RSS images, also prefer different domain
                        if pool_name == 'rss' and self._last_rss_domain:
                            candidate_domain = _extract_domain(candidate)
                            if candidate_domain != self._last_rss_domain:
                                # Perfect: not in history AND different domain
                                image = candidate
                                break
                            elif different_domain_candidate is None:
                                # Save as fallback - not in history but same domain
                                different_domain_candidate = candidate
                                skipped_candidates.append((pool_name, candidate))
                                continue
                        else:
                            # Local image or no previous RSS domain - accept immediately
                            image = candidate
                            break
                    else:
                        # Save for potential reuse if we can't find a non-duplicate
                        skipped_candidates.append((pool_name, candidate))
                        logger.debug(
                            f"Skipping recent duplicate from {pool_name}: {self._get_image_key(candidate)}"
                        )
                
                if image is not None:
                    break
            
            # If no ideal image found, try the different-domain RSS candidate
            if image is None and different_domain_candidate is not None:
                image = different_domain_candidate
            
            # If still no image, use the first skipped candidate
            if image is None and skipped_candidates:
                pool_name, image = skipped_candidates[0]
                logger.warning(
                    f"Could not find non-duplicate, using: {self._get_image_key(image)} from {pool_name}"
                )
            
            # Put back any unused skipped candidates to their respective queues
            for pool_name, candidate in skipped_candidates:
                if candidate is not image:
                    if pool_name == 'local':
                        self._local_queue.appendleft(candidate)
                    elif pool_name == 'rss':
                        self._rss_queue.appendleft(candidate)
                    else:
                        self._queue.appendleft(candidate)
            
            if image is None:
                logger.warning("[FALLBACK] No images available from any pool")
                return None
            
            self._current_image = image
            self._current_index += 1
            self._history.append(image)
            
            # Track source type for stats and domain diversity
            if image.source_type == ImageSourceType.FOLDER:
                self._local_count += 1
            else:
                self._rss_count += 1
                # Track last RSS domain for diversity in future selections
                self._last_rss_domain = _extract_domain(image)
            
            # Log with pool sizes for debugging
            local_pool_size = len(self._local_queue) + len(self._local_images)
            rss_pool_size = len(self._rss_queue) + len(self._rss_images)
            logger.debug(
                f"Next image: {image.local_path or image.url} "
                f"(source={image.source_type.value}, local_count={self._local_count}, rss_count={self._rss_count}, "
                f"local_pool={local_pool_size}, rss_pool={rss_pool_size})"
            )
            return image
    
    def _get_from_local_pool(self) -> Optional[ImageMetadata]:
        """Get next image from local pool, rebuilding if needed."""
        if not self._local_queue:
            if self._local_images:
                self._rebuild_local_queue()
                self._wrap_count += 1
            else:
                return None
        
        if not self._local_queue:
            return None
        
        return self._local_queue.popleft()
    
    def _get_from_rss_pool(self) -> Optional[ImageMetadata]:
        """Get next image from RSS pool, rebuilding if needed."""
        if not self._rss_queue:
            if self._rss_images:
                self._rebuild_rss_queue()
            else:
                return None
        
        if not self._rss_queue:
            return None
        
        return self._rss_queue.popleft()
    
    def _get_from_combined_queue(self) -> Optional[ImageMetadata]:
        """Get next image from combined queue (backwards compatibility)."""
        if not self._queue:
            if self._images:
                self._rebuild_queue()
                self._wrap_count += 1
            else:
                return None
        
        if not self._queue:
            return None
        
        return self._queue.popleft()
    
    def previous(self) -> Optional[ImageMetadata]:
        """
        Go back to previous image in history (thread-safe).
        
        Returns:
            Previous image metadata, or None if no history
        """
        # FIX: Thread-safe access and use ImageMetadata objects directly from history
        with self._lock:
            if len(self._history) < 2:
                logger.warning("[FALLBACK] No previous image in history")
                return self._current_image
            
            # Remove current from history
            self._history.pop()
            
            # FIX: Get previous ImageMetadata directly (O(1) instead of O(n) search)
            prev_image = self._history[-1]
            self._current_image = prev_image
            self._current_index = max(0, self._current_index - 1)
            
            logger.debug(f"Previous image: {prev_image.local_path}")
            return prev_image
    
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
        # FIX: Direct access instead of unnecessary copy
        with self._lock:
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
    
    def peek_many(self, count: int = 1) -> List[ImageMetadata]:
        """
        Peek at the next N images without removing them from the queue.
        
        Args:
            count: Number of items to peek
        
        Returns:
            List of up to N ImageMetadata entries
        """
        if count <= 0:
            return []
        with self._lock:
            if not self._queue:
                return []
            ql = list(self._queue)
            return ql[:min(count, len(ql))]
    
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
        """Shuffle current queue (thread-safe)."""
        # FIX: Thread-safe shuffle
        with self._lock:
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
        Enable or disable shuffle mode (thread-safe).
        
        Args:
            enabled: True to enable shuffle
        """
        # FIX: Thread-safe mode change
        with self._lock:
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
                logger.debug("Queue rebuilt with new shuffle setting")
    
    def clear(self) -> None:
        """Clear all images and reset queue (thread-safe)."""
        # FIX: Thread-safe clear
        with self._lock:
            count = len(self._images)
            
            # Clear separate pools
            self._local_images.clear()
            self._rss_images.clear()
            self._local_queue.clear()
            self._rss_queue.clear()
            
            # Clear combined (backwards compatibility)
            self._images.clear()
            self._queue.clear()
            self._history.clear()
            self._current_image = None
            self._current_index = -1
            self._wrap_count = 0
            
            # Reset ratio tracking
            self._local_count = 0
            self._rss_count = 0
            
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
    
    def get_all_images(self) -> List[ImageMetadata]:
        """Return a snapshot of all images known to the queue.

        The returned list is a shallow copy and safe for callers to
        inspect without holding queue internals.
        """
        with self._lock:
            return list(self._images)
    
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
        if count < len(history_list):
            history_list = history_list[-count:]
        return [str(img.local_path) for img in history_list]
    
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
        return str(image_path) in recent
    
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
            Dict with queue stats including pool information
        """
        total_shown = self._local_count + self._rss_count
        actual_local_pct = (self._local_count / total_shown * 100) if total_shown > 0 else 0
        actual_rss_pct = (self._rss_count / total_shown * 100) if total_shown > 0 else 0
        
        return {
            'total_images': len(self._images),
            'remaining': len(self._queue),
            'current_index': self._current_index,
            'wrap_count': self._wrap_count,
            'history_size': len(self._history),
            'shuffle_enabled': self.shuffle_enabled,
            'current_image': str(self._current_image.local_path) if self._current_image else None,
            # Pool stats
            'local_pool_total': len(self._local_images),
            'local_pool_remaining': len(self._local_queue),
            'rss_pool_total': len(self._rss_images),
            'rss_pool_remaining': len(self._rss_queue),
            # Ratio stats
            'local_ratio_setting': self._local_ratio,
            'local_shown': self._local_count,
            'rss_shown': self._rss_count,
            'actual_local_pct': round(actual_local_pct, 1),
            'actual_rss_pct': round(actual_rss_pct, 1),
        }
    
    def has_both_source_types(self) -> bool:
        """Check if both local and RSS sources are available."""
        has_local = len(self._local_images) > 0
        has_rss = len(self._rss_images) > 0
        return has_local and has_rss
    
    def remove_image(self, image_path: str) -> bool:
        """
        Remove specific image from queue by path (thread-safe).
        
        Args:
            image_path: Path of image to remove
        
        Returns:
            True if image was found and removed
        """
        # FIX: Thread-safe removal
        with self._lock:
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
