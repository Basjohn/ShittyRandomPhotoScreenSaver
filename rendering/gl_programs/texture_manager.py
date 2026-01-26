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

# Module-level singleton
_texture_manager: Optional["GLTextureManager"] = None


def get_texture_manager() -> "GLTextureManager":
    """Get the singleton GLTextureManager instance."""
    global _texture_manager
    if _texture_manager is None:
        _texture_manager = GLTextureManager()
    return _texture_manager


def cleanup_texture_manager() -> None:
    """Cleanup and reset the singleton instance."""
    global _texture_manager
    if _texture_manager is not None:
        _texture_manager.cleanup()
        _texture_manager = None


@dataclass
class PBOEntry:
    """PBO pool entry tracking ID, size, and usage state."""
    pbo_id: int
    size: int
    in_use: bool = False


class GLTextureManager:
    """Manages OpenGL textures for image display.
    
    Features:
    - Texture caching with LRU eviction
    - PBO pooling for async DMA uploads
    - Automatic cleanup on context loss
    
    Thread Safety:
    - All methods must be called from UI thread with valid GL context
    """
    
    # Cache configuration
    MAX_CACHED_TEXTURES = 12
    MAX_CACHED_IMAGES = 8  # Cache converted ARGB32 images
    
    def __init__(self):
        self._initialized: bool = False
        
        # Texture cache: pixmap.cacheKey() -> texture_id
        self._texture_cache: Dict[int, int] = {}
        self._texture_lru: List[int] = []
        
        # Image conversion cache: pixmap.cacheKey() -> (QImage, bytes, width, height)
        # Caches the expensive ARGB32 conversion to avoid repeating it
        self._image_cache: Dict[int, tuple] = {}
        self._image_lru: List[int] = []
        
        # Current transition textures
        self._old_tex_id: int = 0
        self._new_tex_id: int = 0
        
        # PBO pool for async uploads
        self._pbo_pool: List[PBOEntry] = []
        
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
    
    # -------------------------------------------------------------------------
    # Texture Upload
    # -------------------------------------------------------------------------
    
    def upload_pixmap(self, pixmap: QPixmap) -> int:
        """Upload a QPixmap as a GL texture and return its ID.
        
        Returns 0 on failure. Uses PBO for async DMA transfer when available.
        Caches converted ARGB32 images to avoid expensive CPU-side conversion.
        """
        if gl is None or pixmap is None or pixmap.isNull():
            return 0
        
        _upload_start = time.time()
        
        # Check image conversion cache first
        cache_key = 0
        try:
            if hasattr(pixmap, "cacheKey"):
                cache_key = int(pixmap.cacheKey())
        except Exception as e:
            logger.debug("[GL TEXTURE] Exception suppressed: %s", e)
        
        image = None
        data = None
        w = 0
        h = 0
        
        if cache_key > 0 and cache_key in self._image_cache:
            # Use cached converted image
            try:
                image, data, w, h = self._image_cache[cache_key]
                # Refresh LRU position
                if cache_key in self._image_lru:
                    self._image_lru.remove(cache_key)
                self._image_lru.append(cache_key)
                
                if is_perf_metrics_enabled():
                    logger.debug("[PERF] [GL TEXTURE] Using cached image conversion (%dx%d)", w, h)
            except Exception as e:
                logger.debug("[GL TEXTURE] Exception suppressed: %s", e)
                image = None  # Fall through to conversion
        
        if image is None:
            # Convert to ARGB32 + GL_BGRA for correct channel ordering
            _convert_start = time.time()
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
            
            _convert_elapsed = (time.time() - _convert_start) * 1000.0
            if _convert_elapsed > 10.0 and is_perf_metrics_enabled():
                logger.debug(
                    "[PERF] [GL TEXTURE] Slow image conversion: %.2fms (%dx%d)",
                    _convert_elapsed, w, h
                )
            
            # Cache the converted image
            if cache_key > 0:
                try:
                    self._image_cache[cache_key] = (image, data, w, h)
                    self._image_lru.append(cache_key)
                    
                    # LRU eviction for image cache
                    while len(self._image_lru) > self.MAX_CACHED_IMAGES:
                        evict_key = self._image_lru.pop(0)
                        if evict_key != cache_key:
                            self._image_cache.pop(evict_key, None)
                except Exception as e:
                    logger.debug("[GL TEXTURE] Exception suppressed: %s", e)
        
        data_size = len(data)
        tex = gl.glGenTextures(1)
        tex_id = int(tex)
        
        # Try PBO upload for better performance
        use_pbo = False
        pbo_id = 0
        
        try:
            if hasattr(gl, 'GL_PIXEL_UNPACK_BUFFER') and data_size > 0:
                pbo_id = self._get_or_create_pbo(data_size)
                if pbo_id > 0:
                    gl.glBindBuffer(gl.GL_PIXEL_UNPACK_BUFFER, pbo_id)
                    try:
                        # Orphan buffer to avoid sync stalls
                        gl.glBufferData(gl.GL_PIXEL_UNPACK_BUFFER, data_size, None, gl.GL_STREAM_DRAW)
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
                        gl.glBufferData(gl.GL_PIXEL_UNPACK_BUFFER, data_size, data, gl.GL_STREAM_DRAW)
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
            try:
                gl.glDeleteTextures(int(tex_id))
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
        _upload_elapsed = (time.time() - _upload_start) * 1000.0
        if _upload_elapsed > 20.0 and is_perf_metrics_enabled():
            logger.warning("[PERF] [GL TEXTURE] Slow upload: %.2fms (%dx%d, pbo=%s)", 
                          _upload_elapsed, w, h, use_pbo)
        
        # Register texture with ResourceManager for VRAM leak prevention
        try:
            from core.resources.manager import ResourceManager
            rm = ResourceManager()
            rm.register_gl_texture(tex_id, description=f"GLTextureManager {w}x{h}")
        except Exception as e:
            logger.debug("[GL TEXTURE] Exception suppressed: %s", e)  # Non-critical - texture still usable
        
        return tex_id
    
    # -------------------------------------------------------------------------
    # Texture Caching
    # -------------------------------------------------------------------------
    
    def get_or_create_texture(self, pixmap: QPixmap) -> int:
        """Get cached texture or upload new one. Returns texture ID or 0."""
        if gl is None or pixmap is None or pixmap.isNull():
            return 0
        
        # Get cache key
        key = 0
        try:
            if hasattr(pixmap, "cacheKey"):
                key = int(pixmap.cacheKey())
        except Exception as e:
            logger.debug("[GL TEXTURE] Exception suppressed: %s", e)
            key = 0
        
        # Check cache
        if key > 0:
            tex_id = self._texture_cache.get(key, 0)
            if tex_id:
                # Refresh LRU position
                try:
                    if key in self._texture_lru:
                        self._texture_lru.remove(key)
                    self._texture_lru.append(key)
                except Exception as e:
                    logger.debug("[GL TEXTURE] Exception suppressed: %s", e)
                return int(tex_id)
        
        # Upload new texture
        tex_id = self.upload_pixmap(pixmap)
        if not tex_id:
            return 0
        
        # Add to cache with LRU eviction
        if key > 0:
            self._texture_cache[key] = tex_id
            try:
                self._texture_lru.append(key)
                while len(self._texture_lru) > self.MAX_CACHED_TEXTURES:
                    evict_key = self._texture_lru.pop(0)
                    if evict_key == key:
                        continue
                    old_tex = self._texture_cache.pop(evict_key, 0)
                    if old_tex:
                        try:
                            gl.glDeleteTextures(int(old_tex))
                        except Exception:
                            logger.debug("[GL TEXTURE] Failed to delete cached texture %s", 
                                        old_tex, exc_info=True)
            except Exception as e:
                logger.debug("[GL TEXTURE] Exception suppressed: %s", e)
        
        return tex_id
    
    # -------------------------------------------------------------------------
    # Transition Texture Management
    # -------------------------------------------------------------------------
    
    def prepare_transition_textures(self, old_pixmap: QPixmap, new_pixmap: QPixmap) -> bool:
        """Prepare old/new texture pair for transition. Returns success."""
        if old_pixmap is None or old_pixmap.isNull() or new_pixmap is None or new_pixmap.isNull():
            return False
        
        self.release_transition_textures()
        
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
    
    def release_transition_textures(self) -> None:
        """Release current transition texture references (keeps cache)."""
        self._old_tex_id = 0
        self._new_tex_id = 0
    
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
                return entry.pbo_id
        
        # Create new PBO
        try:
            pbo = gl.glGenBuffers(1)
            pbo_id = int(pbo)
            if pbo_id > 0:
                gl.glBindBuffer(gl.GL_PIXEL_UNPACK_BUFFER, pbo_id)
                gl.glBufferData(gl.GL_PIXEL_UNPACK_BUFFER, required_size, None, gl.GL_STREAM_DRAW)
                gl.glBindBuffer(gl.GL_PIXEL_UNPACK_BUFFER, 0)
                self._pbo_pool.append(PBOEntry(pbo_id, required_size, True))
                
                # Register PBO with ResourceManager for VRAM leak prevention
                try:
                    from core.resources.manager import ResourceManager
                    rm = ResourceManager()
                    rm.register_gl_vbo(pbo_id, description=f"GLTextureManager PBO {required_size}B")
                except Exception as e:
                    logger.debug("[GL TEXTURE] Exception suppressed: %s", e)  # Non-critical
                
                return pbo_id
        except Exception as e:
            logger.debug("[GL TEXTURE] Exception suppressed: %s", e)
        return 0
    
    def _release_pbo(self, pbo_id: int) -> None:
        """Mark PBO as available in pool."""
        for entry in self._pbo_pool:
            if entry.pbo_id == pbo_id:
                entry.in_use = False
                return
    
    def _cleanup_pbo_pool(self) -> None:
        """Delete all PBOs in pool."""
        if gl is None:
            return
        for entry in self._pbo_pool:
            try:
                gl.glDeleteBuffers(1, [entry.pbo_id])
            except Exception as e:
                logger.debug("[GL TEXTURE] Exception suppressed: %s", e)
        self._pbo_pool.clear()
    
    # -------------------------------------------------------------------------
    # Cleanup
    # -------------------------------------------------------------------------
    
    def cleanup_cache(self) -> None:
        """Delete all cached textures."""
        if gl is None:
            return
        
        try:
            ids = [int(t) for t in self._texture_cache.values() if t]
            if ids:
                arr = (ctypes.c_uint * len(ids))(*ids)
                gl.glDeleteTextures(len(ids), arr)
        except Exception:
            logger.debug("[GL TEXTURE] Failed to delete cached textures", exc_info=True)
        
        self._texture_cache.clear()
        self._texture_lru.clear()
    
    def cleanup(self) -> None:
        """Full cleanup - release all textures, PBOs, and image cache."""
        self.release_transition_textures()
        self.cleanup_cache()
        self._cleanup_pbo_pool()
        # Clear image conversion cache
        self._image_cache.clear()
        self._image_lru.clear()
        self._initialized = False
