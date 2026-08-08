"""GLTextureManager - Centralized texture management for GL compositor.

Handles texture upload, caching, PBO pooling, and cleanup.
"""

from __future__ import annotations

import ctypes
import logging
import time
from dataclasses import dataclass
from typing import Dict, List, Optional

from PySide6.QtGui import QImage, QPixmap

try:
    from OpenGL import GL as gl
except ImportError:
    gl = None

from core.logging.logger import is_perf_metrics_enabled

logger = logging.getLogger(__name__)


@dataclass
class PBOEntry:
    """PBO pool entry tracking ID, size, and usage state."""
    pbo_id: int
    size: int
    in_use: bool = False
    resource_id: Optional[str] = None


class GLTextureManager:
    """Manages OpenGL textures for image display.
    
    Features:
    - Texture caching with LRU eviction
    - PBO pooling for async DMA uploads
    - Automatic cleanup on context loss
    
    Thread Safety:
    - All methods must be called from UI thread with valid GL context
    """
    
    # Per-compositor retention budgets. Active transition pairs may temporarily
    # exceed the cache budget, but become immediately evictable on completion.
    MAX_CACHED_TEXTURES = 12
    MAX_CACHED_TEXTURE_BYTES = 128 * 1024 * 1024
    MAX_PBO_POOL_ENTRIES = 1
    MAX_PBO_POOL_BYTES = 64 * 1024 * 1024
    UPLOAD_STALL_THRESHOLD_MS = 20.0
    _TRANSITION_METRIC_NAMES = (
        "texture_cache_hits",
        "texture_allocations",
        "texture_allocation_bytes",
        "texture_uploads",
        "texture_upload_failures",
        "upload_bytes",
        "texture_deletions",
        "texture_deleted_bytes",
        "pbo_creations",
        "pbo_created_bytes",
        "pbo_reuses",
        "pbo_deletions",
        "pbo_deleted_bytes",
        "pbo_uploads",
        "direct_uploads",
        "upload_total_ms",
        "upload_max_ms",
        "slow_upload_count",
        "slow_upload_total_ms",
        "slow_upload_max_ms",
        "pbo_slow_upload_count",
        "pbo_slow_upload_total_ms",
        "direct_slow_upload_count",
        "direct_slow_upload_total_ms",
    )
    
    def __init__(
        self,
        owner: str = "GLTextureManager",
        generation: object = None,
        *,
        max_cached_texture_bytes: Optional[int] = None,
        max_pbo_pool_bytes: Optional[int] = None,
    ):
        self._initialized: bool = False
        self._owner = str(owner)
        self._generation = generation
        self._max_cached_texture_bytes = max(
            1,
            int(max_cached_texture_bytes or self.MAX_CACHED_TEXTURE_BYTES),
        )
        self._max_pbo_pool_bytes = max(
            1,
            int(max_pbo_pool_bytes or self.MAX_PBO_POOL_BYTES),
        )
        
        # Texture cache: pixmap.cacheKey() -> texture_id
        self._texture_cache: Dict[int, int] = {}
        self._texture_lru: List[int] = []
        self._texture_bytes_by_id: Dict[int, int] = {}
        self._current_texture_bytes = 0
        self._terminal_textures_reclaimed = 0
        self._terminal_transitions = 0
        self._texture_cache_hits = 0
        self._texture_allocations = 0
        self._texture_allocation_bytes = 0
        self._texture_uploads = 0
        self._texture_upload_failures = 0
        self._upload_bytes = 0
        self._texture_deletions = 0
        self._texture_deleted_bytes = 0
        self._pbo_creations = 0
        self._pbo_created_bytes = 0
        self._pbo_reuses = 0
        self._pbo_deletions = 0
        self._pbo_deleted_bytes = 0
        self._pbo_uploads = 0
        self._direct_uploads = 0
        self._upload_total_ms = 0.0
        self._upload_max_ms = 0.0
        self._slow_upload_count = 0
        self._slow_upload_total_ms = 0.0
        self._slow_upload_max_ms = 0.0
        self._pbo_slow_upload_count = 0
        self._pbo_slow_upload_total_ms = 0.0
        self._direct_slow_upload_count = 0
        self._direct_slow_upload_total_ms = 0.0
        self._transition_metrics: Optional[dict[str, int | float]] = None
        
        # Current transition textures
        self._old_tex_id: int = 0
        self._new_tex_id: int = 0
        
        # PBO pool for async uploads
        self._pbo_pool: List[PBOEntry] = []
        self._texture_resource_ids: Dict[int, str] = {}
        
    @property
    def old_tex_id(self) -> int:
        """Current old texture ID for transitions."""
        return self._old_tex_id
    
    @property
    def new_tex_id(self) -> int:
        """Current new texture ID for transitions."""
        return self._new_tex_id
    
    def initialize(self) -> bool:
        """Initialize the texture manager. Returns success."""
        if gl is None:
            logger.debug("[GL TEXTURE] PyOpenGL not available")
            return False
        self._initialized = True
        return True
    
    def is_initialized(self) -> bool:
        """Check if manager is initialized."""
        return self._initialized

    def _begin_transition_metrics(self) -> None:
        """Open one passive diagnostic window around a texture transition."""
        if is_perf_metrics_enabled():
            self._transition_metrics = {
                name: 0 for name in self._TRANSITION_METRIC_NAMES
            }
        else:
            self._transition_metrics = None

    def _record_transition_metric(
        self,
        name: str,
        value: int | float = 1,
    ) -> None:
        metrics = self._transition_metrics
        if metrics is not None:
            metrics[name] = metrics.get(name, 0) + value

    def _record_texture_deletion(self, tracked_bytes: int = 0) -> None:
        tracked_bytes = max(0, int(tracked_bytes))
        self._texture_deletions += 1
        self._texture_deleted_bytes += tracked_bytes
        self._record_transition_metric("texture_deletions")
        self._record_transition_metric("texture_deleted_bytes", tracked_bytes)

    def _record_pbo_deletion(self, tracked_bytes: int) -> None:
        tracked_bytes = max(0, int(tracked_bytes))
        self._pbo_deletions += 1
        self._pbo_deleted_bytes += tracked_bytes
        self._record_transition_metric("pbo_deletions")
        self._record_transition_metric("pbo_deleted_bytes", tracked_bytes)
    
    # -------------------------------------------------------------------------
    # Texture Upload
    # -------------------------------------------------------------------------
    
    def upload_pixmap(self, pixmap: QPixmap) -> int:
        """Upload a QPixmap as a GL texture and return its ID.
        
        Returns 0 on failure. Uses PBO for async DMA transfer when available.
        """
        if gl is None or pixmap is None or pixmap.isNull():
            return 0
        
        _upload_start = time.perf_counter()
        
        # Convert to ARGB32 + GL_BGRA for correct channel ordering
        image = pixmap.toImage().convertToFormat(QImage.Format.Format_ARGB32)
        w = image.width()
        h = image.height()
        if w <= 0 or h <= 0:
            logger.debug("[GL TEXTURE] Rejecting zero-sized pixmap (%dx%d)", w, h)
            try:
                from rendering.gl_error_handler import GLErrorHandler

                GLErrorHandler().record_texture_failure("Zero-sized pixmap")
            except Exception as e:
                logger.debug("[GL TEXTURE] Exception suppressed: %s", e)
            return 0
        
        # Get image data
        try:
            ptr = image.constBits()
            if hasattr(ptr, "setsize"):
                ptr.setsize(image.sizeInBytes())
                data = bytes(ptr)
            else:
                data = ptr.tobytes()
        except Exception:
            logger.debug("[GL TEXTURE] Failed to access image bits", exc_info=True)
            return 0
        
        data_size = len(data)
        texture_bytes = w * h * 4
        tex = gl.glGenTextures(1)
        tex_id = int(tex)
        if tex_id > 0:
            self._texture_allocations += 1
            self._texture_allocation_bytes += texture_bytes
            self._record_transition_metric("texture_allocations")
            self._record_transition_metric(
                "texture_allocation_bytes",
                texture_bytes,
            )
        
        # Try PBO upload for better performance
        use_pbo = False
        pbo_id = 0
        
        try:
            if hasattr(gl, 'GL_PIXEL_UNPACK_BUFFER') and data_size > 0:
                pbo_id = self._get_or_create_pbo(data_size)
                if pbo_id > 0:
                    gl.glBindBuffer(gl.GL_PIXEL_UNPACK_BUFFER, pbo_id)
                    try:
                        # Orphan without shrinking a reused PBO behind its
                        # exact owner-side size/accounting metadata.
                        pbo_capacity = self._pbo_capacity(pbo_id)
                        gl.glBufferData(gl.GL_PIXEL_UNPACK_BUFFER, pbo_capacity, None, gl.GL_STREAM_DRAW)
                        mapped_ptr = gl.glMapBuffer(gl.GL_PIXEL_UNPACK_BUFFER, gl.GL_WRITE_ONLY)
                        if mapped_ptr:
                            ctypes.memmove(mapped_ptr, data, data_size)
                            gl.glUnmapBuffer(gl.GL_PIXEL_UNPACK_BUFFER)
                            use_pbo = True
                        else:
                            gl.glBufferSubData(gl.GL_PIXEL_UNPACK_BUFFER, 0, data_size, data)
                            use_pbo = True
                    except Exception as e:
                        logger.debug("[GL TEXTURE] Exception suppressed: %s", e)
                        gl.glBufferData(gl.GL_PIXEL_UNPACK_BUFFER, pbo_capacity, None, gl.GL_STREAM_DRAW)
                        gl.glBufferSubData(gl.GL_PIXEL_UNPACK_BUFFER, 0, data_size, data)
                        use_pbo = True
        except Exception as e:
            logger.debug("[GL TEXTURE] Exception suppressed: %s", e)
            use_pbo = False
            if pbo_id > 0:
                try:
                    gl.glBindBuffer(gl.GL_PIXEL_UNPACK_BUFFER, 0)
                    self._release_pbo(pbo_id)
                except Exception as e:
                    logger.debug("[GL TEXTURE] Exception suppressed: %s", e)
                pbo_id = 0
        
        # Upload texture - bind once, set all parameters in batch
        gl.glBindTexture(gl.GL_TEXTURE_2D, tex_id)
        try:
            # Batch GL state changes to reduce driver overhead
            gl.glPixelStorei(gl.GL_UNPACK_ALIGNMENT, 1)
            # Set texture parameters - these are per-texture state, set once
            gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MIN_FILTER, gl.GL_LINEAR)
            gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MAG_FILTER, gl.GL_LINEAR)
            gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_S, gl.GL_CLAMP_TO_EDGE)
            gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_T, gl.GL_CLAMP_TO_EDGE)
            
            if use_pbo:
                gl.glTexImage2D(
                    gl.GL_TEXTURE_2D, 0, gl.GL_RGBA8, w, h, 0,
                    gl.GL_BGRA, gl.GL_UNSIGNED_BYTE, None
                )
            else:
                gl.glTexImage2D(
                    gl.GL_TEXTURE_2D, 0, gl.GL_RGBA8, w, h, 0,
                    gl.GL_BGRA, gl.GL_UNSIGNED_BYTE, data
                )
        except Exception:
            logger.debug("[GL TEXTURE] Upload failed", exc_info=True)
            self._texture_upload_failures += 1
            self._record_transition_metric("texture_upload_failures")
            try:
                gl.glDeleteTextures(int(tex_id))
                if tex_id > 0:
                    self._record_texture_deletion(texture_bytes)
            except Exception as e:
                logger.debug("[GL TEXTURE] Exception suppressed: %s", e)
            if pbo_id > 0:
                try:
                    gl.glBindBuffer(gl.GL_PIXEL_UNPACK_BUFFER, 0)
                    self._release_pbo(pbo_id)
                except Exception as e:
                    logger.debug("[GL TEXTURE] Exception suppressed: %s", e)
            return 0
        finally:
            gl.glBindTexture(gl.GL_TEXTURE_2D, 0)
            if pbo_id > 0:
                try:
                    gl.glBindBuffer(gl.GL_PIXEL_UNPACK_BUFFER, 0)
                    self._release_pbo(pbo_id)
                except Exception as e:
                    logger.debug("[GL TEXTURE] Exception suppressed: %s", e)
        
        # Log slow uploads
        _upload_elapsed = (time.perf_counter() - _upload_start) * 1000.0
        self._texture_uploads += 1
        self._upload_bytes += data_size
        self._upload_total_ms += _upload_elapsed
        self._upload_max_ms = max(self._upload_max_ms, _upload_elapsed)
        if use_pbo:
            self._pbo_uploads += 1
            self._record_transition_metric("pbo_uploads")
        else:
            self._direct_uploads += 1
            self._record_transition_metric("direct_uploads")
        self._record_transition_metric("texture_uploads")
        self._record_transition_metric("upload_bytes", data_size)
        self._record_transition_metric("upload_total_ms", _upload_elapsed)
        if self._transition_metrics is not None:
            self._transition_metrics["upload_max_ms"] = max(
                float(self._transition_metrics["upload_max_ms"]),
                _upload_elapsed,
            )
        if _upload_elapsed > self.UPLOAD_STALL_THRESHOLD_MS:
            self._slow_upload_count += 1
            self._slow_upload_total_ms += _upload_elapsed
            self._slow_upload_max_ms = max(
                self._slow_upload_max_ms,
                _upload_elapsed,
            )
            self._record_transition_metric("slow_upload_count")
            self._record_transition_metric("slow_upload_total_ms", _upload_elapsed)
            if self._transition_metrics is not None:
                self._transition_metrics["slow_upload_max_ms"] = max(
                    float(self._transition_metrics["slow_upload_max_ms"]),
                    _upload_elapsed,
                )
            if use_pbo:
                self._pbo_slow_upload_count += 1
                self._pbo_slow_upload_total_ms += _upload_elapsed
                self._record_transition_metric("pbo_slow_upload_count")
                self._record_transition_metric(
                    "pbo_slow_upload_total_ms",
                    _upload_elapsed,
                )
            else:
                self._direct_slow_upload_count += 1
                self._direct_slow_upload_total_ms += _upload_elapsed
                self._record_transition_metric("direct_slow_upload_count")
                self._record_transition_metric(
                    "direct_slow_upload_total_ms",
                    _upload_elapsed,
                )
        if _upload_elapsed > self.UPLOAD_STALL_THRESHOLD_MS and is_perf_metrics_enabled():
            logger.warning("[PERF] [GL TEXTURE] Slow upload: %.2fms (%dx%d, pbo=%s)", 
                          _upload_elapsed, w, h, use_pbo)
        
        # Register texture with ResourceManager for VRAM leak prevention
        try:
            from core.resources.manager import ResourceManager
            rm = ResourceManager.get_or_create_app_shared()
            rid = rm.register_gl_texture(
                tex_id,
                description=f"GLTextureManager {w}x{h}",
                owner=self._owner,
                generation=self._generation,
                dimensions=(w, h),
                format="RGBA8",
                tracked_bytes=w * h * 4,
            )
            if rid:
                self._texture_resource_ids[tex_id] = rid
        except Exception as e:
            logger.debug("[GL TEXTURE] Exception suppressed: %s", e)  # Non-critical - texture still usable
        
        self._texture_bytes_by_id[tex_id] = texture_bytes
        self._current_texture_bytes += texture_bytes
        return tex_id
    
    # -------------------------------------------------------------------------
    # Texture Caching
    # -------------------------------------------------------------------------
    
    def get_or_create_texture(self, pixmap: QPixmap) -> int:
        """Get or upload a texture under count and exact RGBA8 byte budgets."""
        if gl is None or pixmap is None or pixmap.isNull():
            return 0

        key = 0
        try:
            if hasattr(pixmap, "cacheKey"):
                key = int(pixmap.cacheKey())
        except Exception as exc:
            logger.debug("[GL TEXTURE] cacheKey unavailable: %s", exc)

        if key > 0:
            texture_id = int(self._texture_cache.get(key, 0) or 0)
            if texture_id:
                self._texture_cache_hits += 1
                self._record_transition_metric("texture_cache_hits")
                if key in self._texture_lru:
                    self._texture_lru.remove(key)
                self._texture_lru.append(key)
                return texture_id

        texture_id = int(self.upload_pixmap(pixmap) or 0)
        if not texture_id:
            return 0

        cache_key = key if key > 0 else -texture_id
        replaced_id = int(self._texture_cache.get(cache_key, 0) or 0)
        if replaced_id and replaced_id != texture_id:
            self._delete_cached_texture(cache_key)
        self._texture_cache[cache_key] = texture_id
        if cache_key in self._texture_lru:
            self._texture_lru.remove(cache_key)
        self._texture_lru.append(cache_key)
        self._evict_cache_to_budget(
            protected_ids={texture_id, self._old_tex_id, self._new_tex_id}
        )
        return texture_id

    def _delete_cached_texture(self, cache_key: int) -> bool:
        texture_id = int(self._texture_cache.get(cache_key, 0) or 0)
        if not texture_id:
            if cache_key in self._texture_lru:
                self._texture_lru.remove(cache_key)
            return True
        try:
            gl.glDeleteTextures(texture_id)
        except Exception:
            logger.debug(
                "[GL TEXTURE] Failed to delete cached texture %s",
                texture_id,
                exc_info=True,
            )
            return False
        texture_bytes = self._texture_bytes_by_id.get(texture_id, 0)
        self._record_texture_deletion(texture_bytes)
        self._texture_cache.pop(cache_key, None)
        if cache_key in self._texture_lru:
            self._texture_lru.remove(cache_key)
        self._current_texture_bytes = max(
            0,
            self._current_texture_bytes - self._texture_bytes_by_id.pop(texture_id, 0),
        )
        self._release_texture_tracking(texture_id)
        return True

    def _evict_cache_to_budget(self, protected_ids: Optional[set[int]] = None) -> None:
        """Evict unpinned LRU textures until count and byte budgets are met."""
        protected = {int(value) for value in (protected_ids or set()) if value}
        failed_keys: set[int] = set()
        while (
            len(self._texture_cache) > self.MAX_CACHED_TEXTURES
            or self._current_texture_bytes > self._max_cached_texture_bytes
        ):
            candidate = next(
                (
                    cache_key
                    for cache_key in self._texture_lru
                    if int(self._texture_cache.get(cache_key, 0) or 0) not in protected
                    and cache_key not in failed_keys
                ),
                None,
            )
            if candidate is None:
                break
            if not self._delete_cached_texture(candidate):
                failed_keys.add(candidate)

    def get_stats(self) -> dict[str, int | float]:
        """Return exact compositor-owned texture and PBO retention."""
        return {
            "texture_count": len(self._texture_cache),
            "texture_bytes": self._current_texture_bytes,
            "max_texture_bytes": self._max_cached_texture_bytes,
            "pbo_count": len(self._pbo_pool),
            "pbo_bytes": sum(entry.size for entry in self._pbo_pool),
            "max_pbo_bytes": self._max_pbo_pool_bytes,
            "terminal_textures_reclaimed": self._terminal_textures_reclaimed,
            "terminal_transitions": self._terminal_transitions,
            "texture_cache_hits": self._texture_cache_hits,
            "texture_allocations": self._texture_allocations,
            "texture_allocation_bytes": self._texture_allocation_bytes,
            "texture_uploads": self._texture_uploads,
            "texture_upload_failures": self._texture_upload_failures,
            "upload_bytes": self._upload_bytes,
            "texture_deletions": self._texture_deletions,
            "texture_deleted_bytes": self._texture_deleted_bytes,
            "pbo_creations": self._pbo_creations,
            "pbo_created_bytes": self._pbo_created_bytes,
            "pbo_reuses": self._pbo_reuses,
            "pbo_deletions": self._pbo_deletions,
            "pbo_deleted_bytes": self._pbo_deleted_bytes,
            "pbo_uploads": self._pbo_uploads,
            "direct_uploads": self._direct_uploads,
            "upload_total_ms": self._upload_total_ms,
            "upload_max_ms": self._upload_max_ms,
            "slow_upload_count": self._slow_upload_count,
            "slow_upload_total_ms": self._slow_upload_total_ms,
            "slow_upload_max_ms": self._slow_upload_max_ms,
            "pbo_slow_upload_count": self._pbo_slow_upload_count,
            "pbo_slow_upload_total_ms": self._pbo_slow_upload_total_ms,
            "direct_slow_upload_count": self._direct_slow_upload_count,
            "direct_slow_upload_total_ms": self._direct_slow_upload_total_ms,
        }
    # -------------------------------------------------------------------------
    # Transition Texture Management
    # -------------------------------------------------------------------------
    
    def prepare_transition_textures(self, old_pixmap: QPixmap, new_pixmap: QPixmap) -> bool:
        """Prepare old/new texture pair for transition. Returns success."""
        if old_pixmap is None or old_pixmap.isNull() or new_pixmap is None or new_pixmap.isNull():
            return False
        
        self.release_transition_textures()
        self._begin_transition_metrics()
        
        try:
            self._old_tex_id = self.get_or_create_texture(old_pixmap)
            self._new_tex_id = self.get_or_create_texture(new_pixmap)
        except Exception:
            logger.debug("[GL TEXTURE] Failed to prepare transition textures", exc_info=True)
            self.release_transition_textures()
            return False
        
        if not self._old_tex_id or not self._new_tex_id:
            self.release_transition_textures()
            return False
        
        return True
    
    def release_transition_textures(
        self,
        *,
        retain_active: Optional[str] = None,
    ) -> None:
        """Release pair pins and retire obsolete terminal textures.

        A terminal presentation boundary supplies ``retain_active`` so only
        the texture backing the committed base image survives. Preparation
        and failure cleanup omit it and retain the ordinary byte-budgeted
        cache semantics.
        """
        # Terminal release is idempotent.  The compositor's outer transition
        # cleanup may defensively re-enter after the real terminal boundary;
        # with no pinned pair there is no second transition to retire or log.
        if (
            retain_active in {"new", "old"}
            and not self._old_tex_id
            and not self._new_tex_id
        ):
            return

        retained_id = 0
        if retain_active == "new":
            retained_id = int(self._new_tex_id or 0)
        elif retain_active == "old":
            retained_id = int(self._old_tex_id or 0)
        self._old_tex_id = 0
        self._new_tex_id = 0
        if retain_active in {"new", "old"}:
            self._terminal_transitions += 1
            before = len(self._texture_cache)
            for cache_key, texture_id in tuple(self._texture_cache.items()):
                if int(texture_id or 0) != retained_id:
                    self._delete_cached_texture(cache_key)
            self._terminal_textures_reclaimed += max(
                0,
                before - len(self._texture_cache),
            )
        self._evict_cache_to_budget()
        if retain_active in {"new", "old"} and is_perf_metrics_enabled():
            stats = self.get_stats()
            metrics = self._transition_metrics or {
                name: 0 for name in self._TRANSITION_METRIC_NAMES
            }
            logger.info(
                "[PERF] [GL RETENTION] owner=%s terminal=%d retain_active=%s "
                "retained_texture=%d texture_count=%d texture_bytes=%d "
                "texture_cache_hits=%d texture_allocations=%d "
                "texture_allocation_bytes=%d texture_uploads=%d "
                "texture_upload_failures=%d upload_bytes=%d "
                "texture_deletions=%d texture_deleted_bytes=%d "
                "terminal_historical_deletions=%d pbo_count=%d "
                "pbo_idle_count=%d pbo_capacity_bytes=%d "
                "pbo_creations=%d pbo_created_bytes=%d pbo_reuses=%d "
                "pbo_deletions=%d pbo_deleted_bytes=%d pbo_uploads=%d "
                "direct_uploads=%d upload_total_ms=%.2f upload_max_ms=%.2f "
                "slow_upload_count=%d slow_upload_total_ms=%.2f "
                "slow_upload_max_ms=%.2f pbo_slow_upload_count=%d "
                "pbo_slow_upload_total_ms=%.2f direct_slow_upload_count=%d "
                "direct_slow_upload_total_ms=%.2f",
                self._owner,
                stats["terminal_transitions"],
                retain_active,
                retained_id,
                stats["texture_count"],
                stats["texture_bytes"],
                metrics["texture_cache_hits"],
                metrics["texture_allocations"],
                metrics["texture_allocation_bytes"],
                metrics["texture_uploads"],
                metrics["texture_upload_failures"],
                metrics["upload_bytes"],
                metrics["texture_deletions"],
                metrics["texture_deleted_bytes"],
                max(0, before - len(self._texture_cache)),
                stats["pbo_count"],
                sum(1 for entry in self._pbo_pool if not entry.in_use),
                stats["pbo_bytes"],
                metrics["pbo_creations"],
                metrics["pbo_created_bytes"],
                metrics["pbo_reuses"],
                metrics["pbo_deletions"],
                metrics["pbo_deleted_bytes"],
                metrics["pbo_uploads"],
                metrics["direct_uploads"],
                metrics["upload_total_ms"],
                metrics["upload_max_ms"],
                metrics["slow_upload_count"],
                metrics["slow_upload_total_ms"],
                metrics["slow_upload_max_ms"],
                metrics["pbo_slow_upload_count"],
                metrics["pbo_slow_upload_total_ms"],
                metrics["direct_slow_upload_count"],
                metrics["direct_slow_upload_total_ms"],
            )
        self._transition_metrics = None
    
    def has_transition_textures(self) -> bool:
        """Check if transition textures are ready."""
        return bool(self._old_tex_id and self._new_tex_id)
    
    # -------------------------------------------------------------------------
    # PBO Pool Management
    # -------------------------------------------------------------------------
    
    def _get_or_create_pbo(self, required_size: int) -> int:
        """Get a PBO from pool or create new one. Returns PBO ID or 0."""
        if gl is None:
            return 0
        
        # Look for available PBO of sufficient size
        for entry in self._pbo_pool:
            if not entry.in_use and entry.size >= required_size:
                entry.in_use = True
                self._pbo_reuses += 1
                self._record_transition_metric("pbo_reuses")
                return entry.pbo_id
        
        # Create new PBO
        try:
            pbo = gl.glGenBuffers(1)
            pbo_id = int(pbo)
            if pbo_id > 0:
                # Storage is allocated exactly once by ``upload_pixmap`` after
                # this name is returned. Allocating here and then immediately
                # orphaning in the caller duplicated a full-frame driver
                # allocation for every newly-created staging buffer.
                entry = PBOEntry(pbo_id, required_size, True)
                self._pbo_pool.append(entry)
                self._pbo_creations += 1
                self._pbo_created_bytes += required_size
                self._record_transition_metric("pbo_creations")
                self._record_transition_metric("pbo_created_bytes", required_size)
                
                # Register PBO with ResourceManager for VRAM leak prevention
                try:
                    from core.resources.manager import ResourceManager
                    rm = ResourceManager.get_or_create_app_shared()
                    entry.resource_id = rm.register_gl_vbo(
                        pbo_id,
                        description=f"GLTextureManager PBO {required_size}B",
                        owner=self._owner,
                        generation=self._generation,
                        dimensions=None,
                        format="PIXEL_UNPACK_BUFFER",
                        tracked_bytes=required_size,
                    )
                except Exception as e:
                    logger.debug("[GL TEXTURE] Exception suppressed: %s", e)  # Non-critical
                
                return pbo_id
        except Exception as e:
            logger.debug("[GL TEXTURE] Exception suppressed: %s", e)
        return 0
    
    def _pbo_capacity(self, pbo_id: int) -> int:
        for entry in self._pbo_pool:
            if entry.pbo_id == pbo_id:
                return max(1, int(entry.size))
        return 1

    def _release_pbo(self, pbo_id: int) -> None:
        """Mark a PBO idle and trim retained staging storage to its byte cap."""
        for entry in self._pbo_pool:
            if entry.pbo_id == pbo_id:
                entry.in_use = False
                self._trim_pbo_pool()
                return

    def _trim_pbo_pool(self) -> None:
        """Retain at most one useful idle PBO within the exact byte budget."""
        idle = sorted(
            (entry for entry in self._pbo_pool if not entry.in_use),
            key=lambda entry: entry.size,
            reverse=True,
        )
        keep_ids: set[int] = set()
        retained_bytes = 0
        for entry in idle:
            if (
                len(keep_ids) < self.MAX_PBO_POOL_ENTRIES
                and retained_bytes + entry.size <= self._max_pbo_pool_bytes
            ):
                keep_ids.add(entry.pbo_id)
                retained_bytes += entry.size

        retained: List[PBOEntry] = []
        for entry in self._pbo_pool:
            if entry.in_use or entry.pbo_id in keep_ids:
                retained.append(entry)
                continue
            try:
                gl.glDeleteBuffers(1, [entry.pbo_id])
                self._release_resource_tracking(entry.resource_id)
                self._record_pbo_deletion(entry.size)
            except Exception:
                logger.debug("[GL TEXTURE] Failed to trim idle PBO", exc_info=True)
                retained.append(entry)
        self._pbo_pool = retained

    def _cleanup_pbo_pool(self, *, strict: bool = False) -> None:
        """Delete all PBOs, retaining failed entries in strict teardown."""
        if gl is None:
            if strict and self._pbo_pool:
                raise RuntimeError("Cannot delete live PBOs: PyOpenGL is unavailable")
            return
        failed_entries: List[PBOEntry] = []
        errors: list[str] = []
        for entry in self._pbo_pool:
            try:
                gl.glDeleteBuffers(1, [entry.pbo_id])
                self._release_resource_tracking(entry.resource_id)
                self._record_pbo_deletion(entry.size)
            except Exception as exc:
                failed_entries.append(entry)
                errors.append(f"pbo={entry.pbo_id}:{type(exc).__name__}:{exc}")
                logger.debug("[GL TEXTURE] PBO deletion failed", exc_info=True)
        self._pbo_pool = failed_entries if strict else []
        if strict and errors:
            raise RuntimeError("PBO deletion incomplete: " + " | ".join(errors))

    # -------------------------------------------------------------------------
    # Cleanup
    # -------------------------------------------------------------------------

    def cleanup_cache(self, *, strict: bool = False) -> None:
        """Delete cached textures, retaining ownership if strict deletion fails."""
        ids = [int(texture_id) for texture_id in self._texture_cache.values() if texture_id]
        if gl is None:
            if strict and ids:
                raise RuntimeError("Cannot delete live textures: PyOpenGL is unavailable")
            self._texture_cache.clear()
            self._texture_lru.clear()
            self._texture_bytes_by_id.clear()
            self._current_texture_bytes = 0
            return

        try:
            if ids:
                deleted_bytes = sum(
                    self._texture_bytes_by_id.get(texture_id, 0)
                    for texture_id in ids
                )
                arr = (ctypes.c_uint * len(ids))(*ids)
                gl.glDeleteTextures(len(ids), arr)
                for texture_id in ids:
                    self._release_texture_tracking(texture_id)
                self._texture_deletions += len(ids)
                self._texture_deleted_bytes += deleted_bytes
                self._record_transition_metric("texture_deletions", len(ids))
                self._record_transition_metric(
                    "texture_deleted_bytes",
                    deleted_bytes,
                )
        except Exception as exc:
            logger.debug("[GL TEXTURE] Cached texture deletion failed", exc_info=True)
            if strict:
                raise RuntimeError("Cached texture deletion incomplete") from exc
        else:
            self._texture_cache.clear()
            self._texture_lru.clear()
            self._texture_bytes_by_id.clear()
            self._current_texture_bytes = 0
            return

        # Legacy non-strict callers retain their historical best-effort reset.
        self._texture_cache.clear()
        self._texture_lru.clear()
        self._texture_bytes_by_id.clear()
        self._current_texture_bytes = 0

    def cleanup(self, *, strict: bool = False) -> None:
        """Release textures and PBOs; strict mode preserves failed ownership."""
        self.release_transition_textures()
        errors: list[str] = []
        try:
            self.cleanup_cache(strict=strict)
        except Exception as exc:
            errors.append(f"textures:{type(exc).__name__}:{exc}")
        try:
            self._cleanup_pbo_pool(strict=strict)
        except Exception as exc:
            errors.append(f"pbos:{type(exc).__name__}:{exc}")
        if errors:
            raise RuntimeError("GLTextureManager cleanup incomplete: " + " | ".join(errors))
        self._initialized = False
    def _release_texture_tracking(self, texture_id: int) -> None:
        resource_id = self._texture_resource_ids.pop(int(texture_id), None)
        self._release_resource_tracking(resource_id)

    @staticmethod
    def _release_resource_tracking(resource_id: Optional[str]) -> None:
        if not resource_id:
            return
        try:
            from core.resources.manager import ResourceManager
            manager = ResourceManager.get_app_shared()
            if manager is not None:
                manager.release_tracking(resource_id)
        except Exception as e:
            logger.debug("[GL TEXTURE] Failed to release resource tracking: %s", e)
