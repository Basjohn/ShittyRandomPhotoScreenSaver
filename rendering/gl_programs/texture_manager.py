"""GLTextureManager - Centralized texture management for GL compositor.

Handles texture upload, caching, PBO pooling, and cleanup.
"""

from __future__ import annotations

import ctypes
import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from PySide6.QtGui import QImage, QPixmap

try:
    from OpenGL import GL as gl
except ImportError:
    gl = None

from core.logging.logger import is_perf_metrics_enabled
from rendering.gl_programs.context_identity import (
    current_share_group_identity,
    qt_object_is_valid,
)
from rendering.gl_programs.shared_texture_registry import (
    InvalidShareGroupError,
    RegistryOperationInProgressError,
    ShareGroupIdentity,
    SharedTextureRegistry,
    TextureAllocation,
    TextureLease,
    TextureLifecycleCallbacks,
    get_shared_texture_registry,
)
from rendering.image_upload_payload import ImageUploadPayload

logger = logging.getLogger(__name__)

TextureCacheKey = int | tuple[str, str]

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
    resource_id: str | None = None


@dataclass(slots=True)
class ImageUploadView:
    """Keep an image buffer and any ctypes address owner alive for one upload."""

    data: Any
    size: int
    address: int | None
    address_owner: Any | None
    direct: bool


@dataclass(slots=True)
class _SharedTextureRegistration:
    """Resource ownership retained by one share-group registry entry."""

    resource_manager: Any | None
    resource_id: str | None
    ready_sync: Any | None


def _prepare_image_upload_view(image: QImage) -> ImageUploadView:
    """Expose converted QImage bytes without a full Python copy when possible."""
    size = int(image.sizeInBytes())
    try:
        data = image.bits()
        address_owner = (ctypes.c_ubyte * size).from_buffer(data)
        return ImageUploadView(
            data=data,
            size=size,
            address=ctypes.addressof(address_owner),
            address_owner=address_owner,
            direct=True,
        )
    except Exception:
        ptr = image.constBits()
        if hasattr(ptr, "setsize"):
            ptr.setsize(size)
            data = bytes(ptr)
        else:
            data = ptr.tobytes()
        return ImageUploadView(
            data=data,
            size=len(data),
            address=None,
            address_owner=None,
            direct=False,
        )


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
    # A transition needs two textures. Retaining one adjacent pair preserves
    # seamless back-to-back transitions without keeping a slideshow's worth of
    # full-resolution images resident in every display context.
    MAX_CACHED_TEXTURES = 4
    # Uploads are serialized on the UI/GL thread, so one grow-only PBO is
    # sufficient. Smaller superseded buffers only waste dedicated VRAM.
    MAX_PBO_ENTRIES = 1
    
    def __init__(
        self,
        *,
        shared_registry: SharedTextureRegistry | None = None,
    ):
        self._initialized: bool = False
        
        # Texture cache: pixmap.cacheKey() -> texture_id
        self._texture_cache: Dict[TextureCacheKey, int] = {}
        self._texture_lru: List[TextureCacheKey] = []
        self._texture_resource_ids: Dict[int, str] = {}
        self._texture_sizes: Dict[int, int] = {}
        self._resource_manager: Any | None = None
        self._shared_registry = shared_registry or get_shared_texture_registry()
        self._shared_manager_token = object()
        self._shared_group_identity: ShareGroupIdentity | None = None
        self._shared_texture_leases: Dict[TextureCacheKey, TextureLease] = {}
        self._shared_acquisitions = 0
        self._shared_reuses = 0
        
        # Current transition textures
        self._old_tex_id: int = 0
        self._new_tex_id: int = 0
        # The last successfully presented destination remains pinned while it
        # is the compositor's idle base. Its QPixmap metadata may change later;
        # native residency must not depend on rediscovering a mutable cacheKey.
        self._committed_tex_id: int = 0
        self._committed_cache_key: TextureCacheKey | None = None
        
        # PBO pool for async uploads
        self._pbo_pool: List[PBOEntry] = []
        self._cache_hits = 0
        self._cache_misses = 0
        self._uploads = 0
        self._evictions = 0
        self._managed_releases = 0
        self._pbo_replacements = 0
        
    @property
    def old_tex_id(self) -> int:
        """Current old texture ID for transitions."""
        return self._old_tex_id
    
    @property
    def new_tex_id(self) -> int:
        """Current new texture ID for transitions."""
        return self._new_tex_id

    @property
    def committed_tex_id(self) -> int:
        """Texture currently pinned as the successfully presented base."""
        return self._committed_tex_id
    
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

    def upload_payload(self, payload: ImageUploadPayload) -> int:
        """Upload immutable, tightly packed RGBA8 bytes without Qt conversion."""
        if gl is None or not isinstance(payload, ImageUploadPayload):
            return 0
        if payload.pixel_format != "rgba8" or payload.stride != payload.width * 4:
            return 0

        upload_start = time.perf_counter()
        tex_id = int(gl.glGenTextures(1))
        pbo_id = 0
        use_pbo = False
        try:
            if hasattr(gl, "GL_PIXEL_UNPACK_BUFFER") and payload.byte_size > 0:
                pbo_id = self._get_or_create_pbo(payload.byte_size)
                if pbo_id > 0:
                    gl.glBindBuffer(gl.GL_PIXEL_UNPACK_BUFFER, pbo_id)
                    gl.glBufferData(
                        gl.GL_PIXEL_UNPACK_BUFFER,
                        payload.byte_size,
                        None,
                        gl.GL_STREAM_DRAW,
                    )
                    try:
                        gl.glBufferSubData(
                            gl.GL_PIXEL_UNPACK_BUFFER,
                            0,
                            payload.byte_size,
                            payload.data,
                        )
                    except Exception:
                        gl.glBufferData(
                            gl.GL_PIXEL_UNPACK_BUFFER,
                            payload.byte_size,
                            payload.data,
                            gl.GL_STREAM_DRAW,
                        )
                    use_pbo = True

            gl.glBindTexture(gl.GL_TEXTURE_2D, tex_id)
            gl.glPixelStorei(gl.GL_UNPACK_ALIGNMENT, 1)
            gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MIN_FILTER, gl.GL_LINEAR)
            gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MAG_FILTER, gl.GL_LINEAR)
            gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_S, gl.GL_CLAMP_TO_EDGE)
            gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_T, gl.GL_CLAMP_TO_EDGE)
            gl.glTexImage2D(
                gl.GL_TEXTURE_2D,
                0,
                gl.GL_RGBA8,
                payload.width,
                payload.height,
                0,
                gl.GL_RGBA,
                gl.GL_UNSIGNED_BYTE,
                None if use_pbo else payload.data,
            )
        except Exception:
            logger.debug("[GL TEXTURE] Immutable payload upload failed", exc_info=True)
            try:
                gl.glDeleteTextures(tex_id)
            except Exception:
                pass
            return 0
        finally:
            try:
                gl.glBindTexture(gl.GL_TEXTURE_2D, 0)
            except Exception:
                pass
            if pbo_id > 0:
                try:
                    gl.glBindBuffer(gl.GL_PIXEL_UNPACK_BUFFER, 0)
                    self._release_pbo(pbo_id)
                except Exception:
                    logger.debug("[GL TEXTURE] Failed to release upload PBO", exc_info=True)

        try:
            from core.resources.manager import ResourceManager

            rm = ResourceManager.get_or_create_app_shared()
            resource_id = rm.register_gl_texture(
                tex_id,
                description=f"GLTextureManager {payload.width}x{payload.height}",
                estimated_bytes=payload.byte_size,
                usage_bucket="texture_cache",
            )
            if resource_id:
                self._resource_manager = rm
                self._texture_resource_ids[tex_id] = resource_id
        except Exception as e:
            logger.debug("[GL TEXTURE] Exception suppressed: %s", e)
        self._texture_sizes[tex_id] = payload.byte_size
        self._uploads += 1
        elapsed_ms = (time.perf_counter() - upload_start) * 1000.0
        if elapsed_ms > 20.0 and is_perf_metrics_enabled():
            logger.warning(
                "[PERF] [GL TEXTURE] Slow immutable upload: %.2fms (%dx%d, pbo=%s)",
                elapsed_ms,
                payload.width,
                payload.height,
                use_pbo,
            )
        return tex_id
    
    def upload_pixmap(self, pixmap: QPixmap) -> int:
        """Upload a QPixmap as a GL texture and return its ID.
        
        Returns 0 on failure. Uses PBO for async DMA transfer when available.
        """
        if gl is None or pixmap is None or pixmap.isNull():
            return 0
        
        _upload_start = time.perf_counter()
        
        # Convert to ARGB32 + GL_BGRA for correct channel ordering
        image = pixmap.toImage().convertToFormat(QImage.Format.Format_ARGB32)
        _convert_ms = (time.perf_counter() - _upload_start) * 1000.0
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
        _copy_start = time.perf_counter()
        try:
            upload_view = _prepare_image_upload_view(image)
        except Exception:
            logger.debug("[GL TEXTURE] Failed to access image bits", exc_info=True)
            return 0
        _copy_ms = (time.perf_counter() - _copy_start) * 1000.0
        
        data_size = upload_view.size
        tex = gl.glGenTextures(1)
        tex_id = int(tex)
        
        # Try PBO upload for better performance
        use_pbo = False
        pbo_id = 0
        _pbo_stage_start = time.perf_counter()
        
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
                            source = (
                                upload_view.address
                                if upload_view.address is not None
                                else upload_view.data
                            )
                            try:
                                ctypes.memmove(mapped_ptr, source, data_size)
                            finally:
                                gl.glUnmapBuffer(gl.GL_PIXEL_UNPACK_BUFFER)
                            use_pbo = True
                        else:
                            try:
                                gl.glBufferSubData(
                                    gl.GL_PIXEL_UNPACK_BUFFER,
                                    0,
                                    data_size,
                                    upload_view.data,
                                )
                            except Exception:
                                gl.glBufferSubData(
                                    gl.GL_PIXEL_UNPACK_BUFFER,
                                    0,
                                    data_size,
                                    bytes(upload_view.data),
                                )
                            use_pbo = True
                    except Exception as e:
                        logger.debug("[GL TEXTURE] Exception suppressed: %s", e)
                        fallback_data = (
                            upload_view.data
                            if isinstance(upload_view.data, bytes)
                            else bytes(upload_view.data)
                        )
                        gl.glBufferData(
                            gl.GL_PIXEL_UNPACK_BUFFER,
                            data_size,
                            fallback_data,
                            gl.GL_STREAM_DRAW,
                        )
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
        _pbo_stage_ms = (time.perf_counter() - _pbo_stage_start) * 1000.0
        
        # Upload texture - bind once, set all parameters in batch
        _tex_upload_start = time.perf_counter()
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
                fallback_data = (
                    upload_view.data
                    if isinstance(upload_view.data, bytes)
                    else bytes(upload_view.data)
                )
                gl.glTexImage2D(
                    gl.GL_TEXTURE_2D, 0, gl.GL_RGBA8, w, h, 0,
                    gl.GL_BGRA, gl.GL_UNSIGNED_BYTE, fallback_data
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
        _tex_upload_ms = (time.perf_counter() - _tex_upload_start) * 1000.0
        
        # Log slow uploads
        _upload_elapsed = (time.perf_counter() - _upload_start) * 1000.0
        if _upload_elapsed > 20.0 and is_perf_metrics_enabled():
            logger.warning(
                "[PERF] [GL TEXTURE] Slow upload: %.2fms "
                "(%dx%d, pbo=%s, convert=%.2fms, copy=%.2fms, "
                "pbo_stage=%.2fms, tex_upload=%.2fms, direct=%s)",
                _upload_elapsed,
                w,
                h,
                use_pbo,
                _convert_ms,
                _copy_ms,
                _pbo_stage_ms,
                _tex_upload_ms,
                upload_view.direct,
            )
        
        # Register texture with ResourceManager for VRAM leak prevention
        try:
            from core.resources.manager import ResourceManager
            rm = ResourceManager.get_or_create_app_shared()
            resource_id = rm.register_gl_texture(
                tex_id,
                description=f"GLTextureManager {w}x{h}",
                estimated_bytes=data_size,
                usage_bucket="texture_cache",
            )
            if resource_id:
                self._resource_manager = rm
                self._texture_resource_ids[tex_id] = resource_id
        except Exception as e:
            logger.debug("[GL TEXTURE] Exception suppressed: %s", e)  # Non-critical - texture still usable

        self._texture_sizes[tex_id] = data_size
        self._uploads += 1
        return tex_id
    
    # -------------------------------------------------------------------------
    # Texture Caching
    # -------------------------------------------------------------------------

    def _delete_texture(self, tex_id: int) -> None:
        """Release one texture through its registered owner when available."""
        tex_id = int(tex_id or 0)
        if tex_id <= 0:
            return

        if tex_id == self._committed_tex_id:
            self.clear_committed_texture()

        self._texture_sizes.pop(tex_id, None)
        resource_id = self._texture_resource_ids.pop(tex_id, None)
        if resource_id and self._resource_manager is not None:
            try:
                if self._resource_manager.unregister(resource_id, force=True):
                    self._managed_releases += 1
                    return
                # A missing registration means ResourceManager already released it.
                return
            except Exception:
                logger.debug(
                    "[GL TEXTURE] Managed texture release failed for %s",
                    tex_id,
                    exc_info=True,
                )
                try:
                    self._resource_manager.unregister(
                        resource_id,
                        force=True,
                        cleanup=False,
                    )
                except Exception:
                    pass

        if gl is None:
            return
        try:
            gl.glDeleteTextures(int(tex_id))
        except Exception:
            logger.debug(
                "[GL TEXTURE] Failed to delete texture %s",
                tex_id,
                exc_info=True,
            )

    @staticmethod
    def _current_shared_identity() -> ShareGroupIdentity | None:
        key, wrapper = current_share_group_identity()
        if wrapper is None or not qt_object_is_valid(wrapper):
            return None
        return ShareGroupIdentity(key, wrapper, qt_object_is_valid)

    @staticmethod
    def _same_shared_identity(
        first: ShareGroupIdentity | None,
        second: ShareGroupIdentity | None,
    ) -> bool:
        return bool(
            first is not None
            and second is not None
            and first.stable_key == second.stable_key
            and first.wrapper is second.wrapper
        )

    def _create_shared_texture(
        self,
        payload: ImageUploadPayload,
    ) -> TextureAllocation:
        """Upload once and publish completion through a shareable GL fence."""

        texture_id = int(self.upload_payload(payload) or 0)
        if texture_id <= 0:
            raise RuntimeError("immutable texture upload failed")

        resource_id = self._texture_resource_ids.pop(texture_id, None)
        self._texture_sizes.pop(texture_id, None)
        registration = _SharedTextureRegistration(
            resource_manager=self._resource_manager if resource_id else None,
            resource_id=resource_id,
            ready_sync=None,
        )
        try:
            if gl is None or not all(
                hasattr(gl, name)
                for name in ("glFenceSync", "glFlush", "glWaitSync", "glDeleteSync")
            ):
                raise RuntimeError("cross-context GL synchronization is unavailable")
            ready_sync = gl.glFenceSync(gl.GL_SYNC_GPU_COMMANDS_COMPLETE, 0)
            if ready_sync is None:
                raise RuntimeError("cross-context publication fence creation failed")
            registration.ready_sync = ready_sync
            gl.glFlush()
        except Exception:
            try:
                self._delete_shared_texture(texture_id)
            finally:
                self._abandon_shared_registration(registration)
            raise

        return TextureAllocation(
            texture_id,
            registration_token=registration,
            publication_token=registration.ready_sync,
        )

    @staticmethod
    def _validate_shared_texture(allocation: TextureAllocation) -> bool:
        """Queue a GPU-side publication wait in the consuming context."""

        if gl is None:
            return False
        try:
            if not gl.glIsTexture(int(allocation.texture_id)):
                return False
            ready_sync = allocation.publication_token
            if ready_sync is not None:
                gl.glWaitSync(ready_sync, 0, gl.GL_TIMEOUT_IGNORED)
            return True
        except Exception:
            logger.debug(
                "[GL TEXTURE] Shared texture validation/publication wait failed",
                exc_info=True,
            )
            return False

    @staticmethod
    def _delete_shared_texture(texture_id: int) -> None:
        if gl is None or int(texture_id or 0) <= 0:
            return
        gl.glDeleteTextures(int(texture_id))

    def _unregister_shared_texture(self, token: object | None) -> None:
        if not isinstance(token, _SharedTextureRegistration):
            return
        if token.ready_sync is not None and gl is not None:
            try:
                gl.glDeleteSync(token.ready_sync)
            except Exception:
                logger.debug(
                    "[GL TEXTURE] Failed to delete publication fence",
                    exc_info=True,
                )
        self._abandon_shared_registration(token)

    def _abandon_shared_registration(self, token: object | None) -> None:
        """Drop ResourceManager metadata without touching an invalid context."""

        if not isinstance(token, _SharedTextureRegistration):
            return
        if token.resource_manager is None or not token.resource_id:
            return
        try:
            if token.resource_manager.unregister(
                token.resource_id,
                force=True,
                cleanup=False,
            ):
                self._managed_releases += 1
        except Exception:
            logger.debug(
                "[GL TEXTURE] Failed to unregister shared texture ownership",
                exc_info=True,
            )

    def _shared_callbacks(self) -> TextureLifecycleCallbacks:
        return TextureLifecycleCallbacks(
            create_upload=self._create_shared_texture,
            validate=self._validate_shared_texture,
            delete=self._delete_shared_texture,
            unregister=self._unregister_shared_texture,
            abandon_unregister=self._abandon_shared_registration,
        )

    def _retire_shared_leases(self, *, abandon: bool) -> None:
        for key, lease in list(self._shared_texture_leases.items()):
            if abandon:
                self._shared_registry.abandon(lease)
            else:
                identity = self._current_shared_identity()
                if self._same_shared_identity(identity, self._shared_group_identity):
                    try:
                        self._shared_registry.release(lease, identity)
                    except InvalidShareGroupError:
                        self._shared_registry.abandon(lease)
                else:
                    self._shared_registry.abandon(lease)
            self._shared_texture_leases.pop(key, None)
            texture_id = self._texture_cache.pop(key, 0)
            if texture_id == self._committed_tex_id:
                self.clear_committed_texture()
            try:
                self._texture_lru.remove(key)
            except ValueError:
                pass
        self._shared_group_identity = None

    def _release_shared_lease(
        self,
        key: TextureCacheKey,
        *,
        abandon: bool = False,
    ) -> bool:
        lease = self._shared_texture_leases.pop(key, None)
        if lease is None:
            return False
        identity = self._current_shared_identity()
        try:
            if (
                not abandon
                and self._same_shared_identity(identity, self._shared_group_identity)
            ):
                self._shared_registry.release(lease, identity)
            else:
                self._shared_registry.abandon(lease)
        except InvalidShareGroupError:
            self._shared_registry.abandon(lease)
        if not self._shared_texture_leases:
            self._shared_group_identity = None
        return True

    def _acquire_shared_payload_texture(
        self,
        key: TextureCacheKey,
        payload: ImageUploadPayload,
    ) -> int:
        identity = self._current_shared_identity()
        if identity is None:
            return 0
        if (
            self._shared_group_identity is not None
            and not self._same_shared_identity(identity, self._shared_group_identity)
        ):
            logger.error(
                "[GL TEXTURE][SHARE GROUP] Texture manager changed GL ownership; "
                "abandoning stale leases"
            )
            self._retire_shared_leases(abandon=True)

        uploads_before = self._uploads
        try:
            lease = self._shared_registry.acquire(
                identity,
                self._shared_manager_token,
                payload,
                self._shared_callbacks(),
            )
        except RegistryOperationInProgressError:
            logger.warning(
                "[GL TEXTURE][SHARE GROUP] Concurrent immutable upload refused; "
                "using compositor-local residency"
            )
            return 0
        except Exception:
            logger.warning(
                "[GL TEXTURE][SHARE GROUP] Shared residency unavailable; "
                "using compositor-local residency",
                exc_info=True,
            )
            return 0

        self._shared_group_identity = identity
        self._shared_texture_leases[key] = lease
        self._shared_acquisitions += 1
        if self._uploads == uploads_before:
            self._shared_reuses += 1
        return int(lease.texture_id)

    def _release_cached_texture(
        self,
        key: TextureCacheKey,
        texture_id: int,
        *,
        abandon: bool = False,
    ) -> None:
        if self._release_shared_lease(key, abandon=abandon):
            return
        if abandon:
            return
        self._delete_texture(texture_id)

    def _evict_excess_textures(self) -> None:
        """Keep the bounded LRU while never evicting the active transition pair."""
        protected = {
            self._old_tex_id,
            self._new_tex_id,
            self._committed_tex_id,
        }
        while len(self._texture_lru) > self.MAX_CACHED_TEXTURES:
            evict_index = next(
                (
                    index
                    for index, candidate_key in enumerate(self._texture_lru)
                    if self._texture_cache.get(candidate_key, 0) not in protected
                ),
                None,
            )
            if evict_index is None:
                return
            evict_key = self._texture_lru.pop(evict_index)
            old_tex = self._texture_cache.pop(evict_key, 0)
            if old_tex:
                self._release_cached_texture(evict_key, old_tex)
                self._evictions += 1
    
    @staticmethod
    def _payload_cache_key(payload: ImageUploadPayload) -> tuple[str, str]:
        return ("payload", payload.content_id)

    def get_or_create_texture(
        self,
        pixmap: QPixmap | ImageUploadPayload | None = None,
        *,
        payload: ImageUploadPayload | None = None,
    ) -> int:
        """Get cached texture or upload new one. Returns texture ID or 0."""
        if isinstance(pixmap, ImageUploadPayload):
            if payload is not None:
                return 0
            payload = pixmap
            pixmap = None
        if payload is not None:
            if not isinstance(payload, ImageUploadPayload):
                return 0
            cached_texture = self.get_cached_texture(payload=payload)
            if cached_texture:
                return cached_texture
            self._cache_misses += 1
            key = self._payload_cache_key(payload)
            tex_id = self._acquire_shared_payload_texture(key, payload)
            if not tex_id:
                tex_id = self.upload_payload(payload)
            if tex_id:
                self._texture_cache[key] = tex_id
                if key in self._texture_lru:
                    self._texture_lru.remove(key)
                self._texture_lru.append(key)
                self._evict_excess_textures()
            return tex_id
        if gl is None or pixmap is None or pixmap.isNull():
            return 0

        cached_texture = self.get_cached_texture(pixmap)
        if cached_texture:
            return cached_texture
        
        # Get cache key
        key = 0
        try:
            if hasattr(pixmap, "cacheKey"):
                key = int(pixmap.cacheKey())
        except Exception as e:
            logger.debug("[GL TEXTURE] Exception suppressed: %s", e)
            key = 0
        
        # Upload new texture
        self._cache_misses += 1
        tex_id = self.upload_pixmap(pixmap)
        if not tex_id:
            return 0
        
        # Add to cache with LRU eviction
        cache_key = key if key > 0 else -int(tex_id)
        self._texture_cache[cache_key] = tex_id
        try:
            if cache_key in self._texture_lru:
                self._texture_lru.remove(cache_key)
            self._texture_lru.append(cache_key)
            self._evict_excess_textures()
        except Exception as e:
            logger.debug("[GL TEXTURE] Exception suppressed: %s", e)
        
        return tex_id

    def get_cached_texture(
        self,
        pixmap: QPixmap | ImageUploadPayload | None = None,
        *,
        payload: ImageUploadPayload | None = None,
        touch: bool = True,
    ) -> int:
        """Return an already-resident texture without uploading on the paint path."""
        if isinstance(pixmap, ImageUploadPayload):
            if payload is not None:
                return 0
            payload = pixmap
            pixmap = None
        if payload is not None:
            if not isinstance(payload, ImageUploadPayload):
                return 0
            key = self._payload_cache_key(payload)
        else:
            if pixmap is None or pixmap.isNull():
                return 0
            try:
                key = int(pixmap.cacheKey())
            except Exception:
                return 0
            if key <= 0:
                return 0
        tex_id = int(self._texture_cache.get(key, 0) or 0)
        if tex_id <= 0:
            return 0
        if touch:
            try:
                if key in self._texture_lru:
                    self._texture_lru.remove(key)
                self._texture_lru.append(key)
            except Exception:
                logger.debug("[GL TEXTURE] Failed to refresh cached texture LRU", exc_info=True)
        self._cache_hits += 1
        return tex_id

    def commit_cached_texture(
        self,
        pixmap: QPixmap | ImageUploadPayload | None = None,
        *,
        payload: ImageUploadPayload | None = None,
        texture_id: int | None = None,
    ) -> int:
        """Pin one already-resident texture as the compositor's idle base."""
        if isinstance(pixmap, ImageUploadPayload):
            if payload is not None:
                self.clear_committed_texture()
                return 0
            payload = pixmap
            pixmap = None
        if payload is not None:
            if not isinstance(payload, ImageUploadPayload):
                self.clear_committed_texture()
                return 0
            key = self._payload_cache_key(payload)
        else:
            if pixmap is None or pixmap.isNull():
                self.clear_committed_texture()
                return 0
            try:
                key = int(pixmap.cacheKey())
            except Exception:
                self.clear_committed_texture()
                return 0
            if key <= 0:
                self.clear_committed_texture()
                return 0

        resident = int(self._texture_cache.get(key, 0) or 0)
        requested = int(texture_id or resident or 0)
        if requested <= 0 or resident != requested:
            self.clear_committed_texture()
            return 0

        self._committed_tex_id = requested
        self._committed_cache_key = key
        try:
            if key in self._texture_lru:
                self._texture_lru.remove(key)
            self._texture_lru.append(key)
        except Exception:
            logger.debug(
                "[GL TEXTURE] Failed to refresh committed texture LRU",
                exc_info=True,
            )
        return requested

    def get_committed_texture(self) -> int:
        """Return the pinned idle-base texture without consulting QPixmap state."""

        texture_id = int(self._committed_tex_id or 0)
        if texture_id <= 0:
            return 0
        if texture_id not in self._texture_cache.values():
            self.clear_committed_texture()
            return 0
        return texture_id

    def clear_committed_texture(self) -> None:
        """Release the residency pin without deleting the cached texture."""

        self._committed_tex_id = 0
        self._committed_cache_key = None
    
    # -------------------------------------------------------------------------
    # Transition Texture Management
    # -------------------------------------------------------------------------
    
    def prepare_transition_textures(
        self,
        old_pixmap: QPixmap | None,
        new_pixmap: QPixmap | None,
        *,
        old_payload: ImageUploadPayload | None = None,
        new_payload: ImageUploadPayload | None = None,
    ) -> bool:
        """Prepare old/new texture pair for transition. Returns success."""
        payload_authoritative = old_payload is not None or new_payload is not None
        if payload_authoritative:
            if not isinstance(old_payload, ImageUploadPayload) or not isinstance(
                new_payload, ImageUploadPayload
            ):
                return False
        elif old_pixmap is None or old_pixmap.isNull() or new_pixmap is None or new_pixmap.isNull():
            return False
        
        self.release_transition_textures()
        
        try:
            if payload_authoritative:
                self._old_tex_id = self.get_or_create_texture(payload=old_payload)
                self._new_tex_id = self.get_or_create_texture(payload=new_payload)
            else:
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
        pbo_id = 0
        entry: PBOEntry | None = None
        try:
            pbo = gl.glGenBuffers(1)
            pbo_id = int(pbo)
            if pbo_id > 0:
                gl.glBindBuffer(gl.GL_PIXEL_UNPACK_BUFFER, pbo_id)
                gl.glBufferData(gl.GL_PIXEL_UNPACK_BUFFER, required_size, None, gl.GL_STREAM_DRAW)
                entry = PBOEntry(pbo_id, required_size, True)

                # Register PBO with ResourceManager for VRAM leak prevention
                try:
                    from core.resources.manager import ResourceManager
                    rm = ResourceManager.get_or_create_app_shared()
                    resource_id = rm.register_gl_vbo(
                        pbo_id,
                        description=f"GLTextureManager PBO {required_size}B",
                        estimated_bytes=required_size,
                        usage_bucket="texture_pbo",
                    )
                    if resource_id:
                        self._resource_manager = rm
                        entry.resource_id = resource_id
                except Exception as e:
                    logger.debug("[GL TEXTURE] Exception suppressed: %s", e)  # Non-critical

                self._pbo_pool.append(entry)
                self._prune_idle_pbos(keep_id=pbo_id)
                return pbo_id
        except Exception as e:
            logger.debug("[GL TEXTURE] Exception suppressed: %s", e)
            if entry is not None:
                try:
                    self._pbo_pool.remove(entry)
                except ValueError:
                    pass
                self._delete_pbo(entry)
            elif pbo_id > 0:
                try:
                    gl.glDeleteBuffers(1, [pbo_id])
                except Exception:
                    logger.debug(
                        "[GL TEXTURE] Failed to release partially created PBO %s",
                        pbo_id,
                        exc_info=True,
                    )
        finally:
            try:
                gl.glBindBuffer(gl.GL_PIXEL_UNPACK_BUFFER, 0)
            except Exception:
                pass
        return 0
    
    def _release_pbo(self, pbo_id: int) -> None:
        """Mark PBO as available in pool."""
        for entry in self._pbo_pool:
            if entry.pbo_id == pbo_id:
                entry.in_use = False
                return

    def _delete_pbo(self, entry: PBOEntry) -> None:
        resource_id = entry.resource_id
        if resource_id and self._resource_manager is not None:
            try:
                if self._resource_manager.unregister(resource_id, force=True):
                    self._managed_releases += 1
                    return
                return
            except Exception:
                logger.debug(
                    "[GL TEXTURE] Managed PBO release failed for %s",
                    entry.pbo_id,
                    exc_info=True,
                )
                try:
                    self._resource_manager.unregister(
                        resource_id,
                        force=True,
                        cleanup=False,
                    )
                except Exception:
                    pass

        if gl is None:
            return
        try:
            gl.glDeleteBuffers(1, [entry.pbo_id])
        except Exception as e:
            logger.debug("[GL TEXTURE] Exception suppressed: %s", e)

    def _prune_idle_pbos(self, *, keep_id: int) -> None:
        if len(self._pbo_pool) <= self.MAX_PBO_ENTRIES:
            return
        retained: List[PBOEntry] = []
        for entry in self._pbo_pool:
            if entry.pbo_id == keep_id or entry.in_use:
                retained.append(entry)
                continue
            self._delete_pbo(entry)
            self._pbo_replacements += 1
        self._pbo_pool = retained

    def _cleanup_pbo_pool(self) -> None:
        """Delete all PBOs in pool."""
        for entry in list(self._pbo_pool):
            self._delete_pbo(entry)
        self._pbo_pool.clear()

    def abandon(self) -> None:
        """Drop registrations after the owning GL context is already invalid."""
        self._retire_shared_leases(abandon=True)
        if self._resource_manager is not None:
            resource_ids = list(self._texture_resource_ids.values())
            resource_ids.extend(
                entry.resource_id for entry in self._pbo_pool if entry.resource_id
            )
            for resource_id in resource_ids:
                try:
                    self._resource_manager.unregister(
                        resource_id,
                        force=True,
                        cleanup=False,
                    )
                except Exception:
                    logger.debug(
                        "[GL TEXTURE] Failed to abandon registration %s",
                        resource_id,
                        exc_info=True,
                    )
        self.release_transition_textures()
        self.clear_committed_texture()
        self._texture_cache.clear()
        self._texture_lru.clear()
        self._texture_resource_ids.clear()
        self._texture_sizes.clear()
        self._pbo_pool.clear()
        self._initialized = False
    
    # -------------------------------------------------------------------------
    # Cleanup
    # -------------------------------------------------------------------------

    def get_stats(self) -> Dict[str, float | int]:
        texture_bytes = sum(self._texture_sizes.values())
        pbo_bytes = sum(entry.size for entry in self._pbo_pool)
        shared_entries = 0
        shared_bytes = 0
        shared_managers = 0
        shared_group_key = None
        if self._shared_group_identity is not None:
            shared_group_key = self._shared_group_identity.stable_key
            shared_stats = self._shared_registry.stats(shared_group_key)
            shared_entries = shared_stats.entries
            shared_bytes = shared_stats.texture_bytes
            shared_managers = shared_stats.live_managers
        return {
            "textures": len(self._texture_cache),
            "texture_mb": texture_bytes / (1024.0 * 1024.0),
            "shared_leases": len(self._shared_texture_leases),
            "shared_group_textures": shared_entries,
            "shared_group_texture_mb": shared_bytes / (1024.0 * 1024.0),
            "shared_group_managers": shared_managers,
            "pbo_count": len(self._pbo_pool),
            "pbo_mb": pbo_bytes / (1024.0 * 1024.0),
            "hits": self._cache_hits,
            "misses": self._cache_misses,
            "uploads": self._uploads,
            "evictions": self._evictions,
            "managed_releases": self._managed_releases,
            "shared_acquisitions": self._shared_acquisitions,
            "shared_reuses": self._shared_reuses,
            "pbo_replacements": self._pbo_replacements,
            "committed_texture": self._committed_tex_id,
            "registrations": (
                len(self._texture_resource_ids)
                + sum(1 for entry in self._pbo_pool if entry.resource_id)
            ),
        }
    
    def cleanup_cache(self) -> None:
        """Delete all cached textures."""
        self.clear_committed_texture()
        cached_texture_ids = set(self._texture_cache.values())
        for key, tex_id in list(self._texture_cache.items()):
            self._release_cached_texture(key, tex_id)
        orphaned_texture_ids = (
            set(self._texture_resource_ids) | set(self._texture_sizes)
        ) - cached_texture_ids
        for tex_id in orphaned_texture_ids:
            self._delete_texture(tex_id)
        self._texture_cache.clear()
        self._texture_lru.clear()
        self._texture_sizes.clear()
    
    def cleanup(self) -> None:
        """Full cleanup - release all textures and PBOs."""
        if is_perf_metrics_enabled():
            stats = self.get_stats()
            logger.info(
                "[PERF] [GL TEXTURE CACHE] cleanup textures=%d texture_mb=%.1f "
                "pbo_count=%d pbo_mb=%.1f hits=%d misses=%d uploads=%d "
                "evictions=%d managed_releases=%d pbo_replacements=%d registrations=%d "
                "shared_leases=%d shared_group_textures=%d shared_group_texture_mb=%.1f "
                "shared_group_managers=%d shared_acquisitions=%d shared_reuses=%d",
                stats["textures"],
                stats["texture_mb"],
                stats["pbo_count"],
                stats["pbo_mb"],
                stats["hits"],
                stats["misses"],
                stats["uploads"],
                stats["evictions"],
                stats["managed_releases"],
                stats["pbo_replacements"],
                stats["registrations"],
                stats["shared_leases"],
                stats["shared_group_textures"],
                stats["shared_group_texture_mb"],
                stats["shared_group_managers"],
                stats["shared_acquisitions"],
                stats["shared_reuses"],
            )
        self.release_transition_textures()
        self.cleanup_cache()
        self._cleanup_pbo_pool()
        self._initialized = False
