"""
Tests for GL texture streaming and PBO optimization.

Tests cover:
- PBO pool management
- Texture upload performance
- ResourceManager GL handle tracking
"""
import ctypes
import logging

import pytest


class TestPBOPoolManagement:
    """Tests for PBO pool management in GLTextureManager."""
    
    def test_pbo_pool_initialization(self):
        """Test PBO pool starts empty."""
        from rendering.gl_programs.texture_manager import GLTextureManager
        
        manager = GLTextureManager()
        assert len(manager._pbo_pool) == 0
    
    def test_pbo_entry_dataclass(self):
        """Test PBOEntry dataclass structure."""
        from rendering.gl_programs.texture_manager import PBOEntry
        
        entry = PBOEntry(pbo_id=1, size=1024, in_use=False)
        assert entry.pbo_id == 1
        assert entry.size == 1024
        assert entry.in_use is False
    
    def test_pbo_entry_default_in_use(self):
        """Test PBOEntry defaults to not in use."""
        from rendering.gl_programs.texture_manager import PBOEntry
        
        entry = PBOEntry(pbo_id=2, size=2048)
        assert entry.in_use is False
    
    def test_pbo_release_marks_available(self):
        """Test _release_pbo marks PBO as available."""
        from rendering.gl_programs.texture_manager import GLTextureManager, PBOEntry
        
        manager = GLTextureManager()
        # Manually add a PBO entry
        manager._pbo_pool.append(PBOEntry(pbo_id=100, size=4096, in_use=True))
        
        # Release it
        manager._release_pbo(100)
        
        # Should be marked as not in use
        assert manager._pbo_pool[0].in_use is False
    
    def test_pbo_release_nonexistent(self):
        """Test _release_pbo handles nonexistent PBO gracefully."""
        from rendering.gl_programs.texture_manager import GLTextureManager
        
        manager = GLTextureManager()
        # Should not raise
        manager._release_pbo(999)


class TestTextureCache:
    """Tests for texture caching in GLTextureManager."""
    
    def test_texture_cache_initialization(self):
        """Test texture cache starts empty."""
        from rendering.gl_programs.texture_manager import GLTextureManager
        
        manager = GLTextureManager()
        assert len(manager._texture_cache) == 0
        assert len(manager._texture_lru) == 0
    
    def test_max_cached_textures_constant(self):
        """Test MAX_CACHED_TEXTURES is reasonable."""
        from rendering.gl_programs.texture_manager import GLTextureManager
        
        assert GLTextureManager.MAX_CACHED_TEXTURES >= 4
        assert GLTextureManager.MAX_CACHED_TEXTURES <= 32
    
    def test_transition_texture_ids_default(self):
        """Test transition texture IDs default to 0."""
        from rendering.gl_programs.texture_manager import GLTextureManager
        
        manager = GLTextureManager()
        assert manager.old_tex_id == 0
        assert manager.new_tex_id == 0


class TestGLTextureManagerLifecycle:
    """Tests for GLTextureManager lifecycle."""
    
    def test_initialization_state(self):
        """Test manager starts uninitialized."""
        from rendering.gl_programs.texture_manager import GLTextureManager
        
        manager = GLTextureManager()
        assert manager._initialized is False
    
    def test_is_initialized_method(self):
        """Test is_initialized returns correct state."""
        from rendering.gl_programs.texture_manager import GLTextureManager
        
        manager = GLTextureManager()
        assert manager.is_initialized() is False
    
    def test_managers_are_explicit_independent_owners(self):
        """Each compositor must construct its own texture/PBO owner."""
        from rendering.gl_programs.texture_manager import GLTextureManager

        manager1 = GLTextureManager(owner="display:0")
        manager2 = GLTextureManager(owner="display:1")

        assert manager1 is not manager2
        assert manager1._owner != manager2._owner


class TestResourceManagerGLTracking:
    """Tests for ResourceManager GL handle tracking."""
    
    def test_gl_stats_empty(self):
        """Test get_gl_stats returns zeros when empty."""
        from core.resources.manager import ResourceManager
        
        rm = ResourceManager()
        stats = rm.get_gl_stats()
        
        assert stats["total"] == 0
        assert stats["vao"] == 0
        assert stats["vbo"] == 0
        assert stats["texture"] == 0
        assert stats["program"] == 0
    
    def test_register_gl_handle_generic(self):
        """Test generic GL handle registration."""
        from core.resources.manager import ResourceManager
        
        rm = ResourceManager()
        
        # Register a mock handle
        rid = rm.register_gl_handle(
            handle=123,
            handle_type="test",
            cleanup_func=lambda h: None,
            description="Test handle"
        )
        
        assert rid is not None
        assert len(rid) > 0
    
    def test_register_gl_vao(self):
        """Test VAO registration."""
        from core.resources.manager import ResourceManager
        
        rm = ResourceManager()
        
        # This will fail without OpenGL context, but should not raise
        rid = rm.register_gl_vao(456, description="Test VAO")
        
        # Should return empty string without GL context
        # or valid ID with GL context
        assert isinstance(rid, str)
    
    def test_register_gl_vbo(self):
        """Test VBO registration."""
        from core.resources.manager import ResourceManager
        
        rm = ResourceManager()
        
        rid = rm.register_gl_vbo(789, description="Test VBO")
        assert isinstance(rid, str)
    
    def test_register_gl_texture(self):
        """Test texture registration."""
        from core.resources.manager import ResourceManager
        
        rm = ResourceManager()
        
        rid = rm.register_gl_texture(101, description="Test texture")
        assert isinstance(rid, str)
    
    def test_register_gl_program(self):
        """Test program registration."""
        from core.resources.manager import ResourceManager
        
        rm = ResourceManager()
        
        rid = rm.register_gl_program(202, description="Test program")
        assert isinstance(rid, str)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])


class TestPassiveGLAccounting:
    """Mocked accounting checks; no real GL context is used."""

    def test_pbo_registration_records_exact_requested_bytes(self, monkeypatch):
        from unittest.mock import MagicMock
        from core.resources.manager import ResourceManager
        from rendering.gl_programs import texture_manager as module

        fake_gl = MagicMock()
        fake_gl.glGenBuffers.return_value = 41
        fake_gl.GL_PIXEL_UNPACK_BUFFER = 1
        fake_gl.GL_STREAM_DRAW = 2
        registry = MagicMock()
        registry.register_gl_vbo.return_value = "pbo-rid"
        monkeypatch.setattr(module, "gl", fake_gl)
        monkeypatch.setattr(ResourceManager, "get_or_create_app_shared", classmethod(lambda cls: registry))
        manager = module.GLTextureManager(owner="compositor:4", generation=4)

        assert manager._get_or_create_pbo(4097) == 41

        kwargs = registry.register_gl_vbo.call_args.kwargs
        assert kwargs["owner"] == "compositor:4"
        assert kwargs["generation"] == 4
        assert kwargs["format"] == "PIXEL_UNPACK_BUFFER"
        assert kwargs["tracked_bytes"] == 4097
        assert manager._pbo_pool[0].resource_id == "pbo-rid"
        fake_gl.glBufferData.assert_not_called()
        fake_gl.glBindBuffer.assert_not_called()

    def test_quad_vbo_registration_records_exact_requested_bytes(self, monkeypatch):
        from unittest.mock import MagicMock
        from core.resources.manager import ResourceManager
        from rendering.gl_programs import geometry_manager as module

        fake_gl = MagicMock()
        fake_gl.glGenVertexArrays.return_value = 3
        fake_gl.glGenBuffers.return_value = 4
        fake_gl.GL_ARRAY_BUFFER = 1
        fake_gl.GL_STATIC_DRAW = 2
        fake_gl.GL_FLOAT = 3
        fake_gl.GL_FALSE = 0
        registry = MagicMock()
        registry.register_gl_vao.return_value = "vao-rid"
        registry.register_gl_vbo.return_value = "vbo-rid"
        monkeypatch.setattr(module, "gl", fake_gl)
        monkeypatch.setattr(ResourceManager, "get_or_create_app_shared", classmethod(lambda cls: registry))
        manager = module.GLGeometryManager(owner="compositor:3", generation=3)

        assert manager._create_quad_geometry() is True

        vao_kwargs = registry.register_gl_vao.call_args.kwargs
        vbo_kwargs = registry.register_gl_vbo.call_args.kwargs
        assert vao_kwargs["tracked_bytes"] is None
        assert vbo_kwargs["owner"] == "compositor:3"
        assert vbo_kwargs["generation"] == 3
        assert vbo_kwargs["dimensions"] == (4, 4)
        assert vbo_kwargs["tracked_bytes"] == 4 * 4 * 4

    def test_texture_registration_records_requested_rgba8_bytes(self, monkeypatch):
        from unittest.mock import MagicMock
        from core.resources.manager import ResourceManager
        from rendering.gl_programs import texture_manager as module

        fake_gl = MagicMock()
        fake_gl.glGenTextures.return_value = 55
        fake_gl.GL_TEXTURE_2D = 1
        fake_gl.GL_UNPACK_ALIGNMENT = 2
        fake_gl.GL_TEXTURE_MIN_FILTER = 3
        fake_gl.GL_TEXTURE_MAG_FILTER = 4
        fake_gl.GL_LINEAR = 5
        fake_gl.GL_TEXTURE_WRAP_S = 6
        fake_gl.GL_TEXTURE_WRAP_T = 7
        fake_gl.GL_CLAMP_TO_EDGE = 8
        fake_gl.GL_RGBA8 = 9
        fake_gl.GL_BGRA = 10
        fake_gl.GL_UNSIGNED_BYTE = 11
        registry = MagicMock()
        registry.register_gl_texture.return_value = "texture-rid"
        image = MagicMock()
        image.convertToFormat.return_value = image
        image.width.return_value = 13
        image.height.return_value = 7
        image.constBits.return_value.tobytes.return_value = b"x" * (13 * 7 * 4)
        pixmap = MagicMock()
        pixmap.isNull.return_value = False
        pixmap.toImage.return_value = image
        monkeypatch.setattr(module, "gl", fake_gl)
        monkeypatch.setattr(ResourceManager, "get_or_create_app_shared", classmethod(lambda cls: registry))
        manager = module.GLTextureManager(owner="compositor:8", generation=8)
        monkeypatch.setattr(manager, "_get_or_create_pbo", lambda size: 0)

        assert manager.upload_pixmap(pixmap) == 55

        kwargs = registry.register_gl_texture.call_args.kwargs
        assert kwargs["dimensions"] == (13, 7)
        assert kwargs["format"] == "RGBA8"
        assert kwargs["tracked_bytes"] == 13 * 7 * 4
        assert manager._texture_resource_ids[55] == "texture-rid"

    def test_native_bgra_image_formats_expose_direct_upload_storage(self):
        from PySide6.QtGui import QColor, QImage
        from rendering.gl_programs.texture_manager import (
            _image_upload_buffer,
            _prepare_pixmap_upload_image,
        )

        class _PixmapImage:
            def __init__(self, image):
                self._image = image

            def toImage(self):
                return self._image

        for image_format, expected_label in (
            (QImage.Format.Format_RGB32, "rgb32"),
            (QImage.Format.Format_ARGB32, "argb32"),
        ):
            source = QImage(3, 2, image_format)
            source.fill(QColor(12, 34, 56, 78))

            image, format_label = _prepare_pixmap_upload_image(_PixmapImage(source))
            data, data_size, data_address, bits_path = _image_upload_buffer(image)

            assert image is source
            assert format_label == expected_label
            assert bits_path == "direct_const_view"
            assert isinstance(data, memoryview)
            assert data_size == source.sizeInBytes() == 3 * 2 * 4
            assert data_address > 0
            assert ctypes.string_at(data_address, data_size) == source.constBits().tobytes()

    def test_non_native_upload_format_retains_explicit_argb32_conversion(self):
        from PySide6.QtGui import QColor, QImage
        from rendering.gl_programs.texture_manager import _prepare_pixmap_upload_image

        class _PixmapImage:
            def __init__(self, image):
                self._image = image

            def toImage(self):
                return self._image

        source = QImage(2, 1, QImage.Format.Format_RGBA8888)
        source.fill(QColor(12, 34, 56, 78))

        image, format_label = _prepare_pixmap_upload_image(_PixmapImage(source))

        assert image.format() == QImage.Format.Format_ARGB32
        assert format_label == "converted_argb32"
        assert image.pixelColor(0, 0) == source.pixelColor(0, 0)

    def test_upload_buffer_copied_fallback_preserves_bytes(self, monkeypatch):
        from PySide6.QtGui import QColor, QImage
        from rendering.gl_programs import texture_manager as module

        image = QImage(3, 2, QImage.Format.Format_ARGB32)
        image.fill(QColor(12, 34, 56, 78))

        def _reject_pointer(_data):
            raise TypeError("address export unavailable")

        monkeypatch.setattr(module, "VoidPtr", _reject_pointer)

        data, data_size, data_address, bits_path = module._image_upload_buffer(image)

        assert bits_path == "copied_fallback"
        assert isinstance(data, bytes)
        assert data_size == image.sizeInBytes()
        assert data_address == 0
        assert data == image.constBits().tobytes()

    def test_upload_phase_probe_is_perf_only_and_reports_named_spans(
        self,
        monkeypatch,
        caplog,
    ):
        from unittest.mock import MagicMock
        from core.resources.manager import ResourceManager
        from rendering.gl_programs import texture_manager as module

        fake_gl = MagicMock()
        fake_gl.glGenTextures.return_value = 55
        fake_gl.GL_TEXTURE_2D = 1
        fake_gl.GL_UNPACK_ALIGNMENT = 2
        fake_gl.GL_TEXTURE_MIN_FILTER = 3
        fake_gl.GL_TEXTURE_MAG_FILTER = 4
        fake_gl.GL_LINEAR = 5
        fake_gl.GL_TEXTURE_WRAP_S = 6
        fake_gl.GL_TEXTURE_WRAP_T = 7
        fake_gl.GL_CLAMP_TO_EDGE = 8
        fake_gl.GL_RGBA8 = 9
        fake_gl.GL_BGRA = 10
        fake_gl.GL_UNSIGNED_BYTE = 11
        registry = MagicMock()
        registry.register_gl_texture.return_value = "texture-rid"
        image = MagicMock()
        image.convertToFormat.return_value = image
        image.width.return_value = 13
        image.height.return_value = 7
        image.constBits.return_value.tobytes.return_value = b"x" * (13 * 7 * 4)
        pixmap = MagicMock()
        pixmap.isNull.return_value = False
        pixmap.toImage.return_value = image
        monkeypatch.setattr(module, "gl", fake_gl)
        monkeypatch.setattr(
            ResourceManager,
            "get_or_create_app_shared",
            classmethod(lambda cls: registry),
        )

        clock_calls: list[float] = []

        def _clock() -> float:
            value = 0.001 * (len(clock_calls) + 1)
            clock_calls.append(value)
            return value

        monkeypatch.setattr(module.time, "perf_counter", _clock)
        monkeypatch.setattr(module, "is_perf_metrics_enabled", lambda: False)
        manager = module.GLTextureManager(owner="compositor:8", generation=8)
        monkeypatch.setattr(manager, "_get_or_create_pbo", lambda size: 0)

        assert manager.upload_pixmap(pixmap) == 55
        assert len(clock_calls) == 2

        clock_calls.clear()
        caplog.clear()
        caplog.set_level(logging.INFO, logger=module.__name__)
        monkeypatch.setattr(module, "is_perf_metrics_enabled", lambda: True)
        manager = module.GLTextureManager(owner="compositor:8", generation=8)
        monkeypatch.setattr(manager, "_get_or_create_pbo", lambda size: 0)

        assert manager.upload_pixmap(pixmap) == 55
        assert len(clock_calls) == 7
        message = next(
            record.getMessage()
            for record in caplog.records
            if "[PERF][GL TEXTURE][UPLOAD]" in record.getMessage()
        )
        assert "owner=compositor:8" in message
        assert "path=direct" in message
        assert "image_prepare_ms=" in message
        assert "bits_copy_ms=" in message
        assert "pbo_stage_ms=" in message
        assert "texture_submit_ms=" in message

    def test_failed_upload_reconciles_texture_allocation_and_delete_bytes(
        self,
        monkeypatch,
    ):
        from unittest.mock import MagicMock
        from rendering.gl_programs import texture_manager as module

        fake_gl = MagicMock()
        fake_gl.glGenTextures.return_value = 55
        fake_gl.glTexImage2D.side_effect = RuntimeError("upload failed")
        fake_gl.GL_TEXTURE_2D = 1
        fake_gl.GL_UNPACK_ALIGNMENT = 2
        fake_gl.GL_TEXTURE_MIN_FILTER = 3
        fake_gl.GL_TEXTURE_MAG_FILTER = 4
        fake_gl.GL_LINEAR = 5
        fake_gl.GL_TEXTURE_WRAP_S = 6
        fake_gl.GL_TEXTURE_WRAP_T = 7
        fake_gl.GL_CLAMP_TO_EDGE = 8
        fake_gl.GL_RGBA8 = 9
        fake_gl.GL_BGRA = 10
        fake_gl.GL_UNSIGNED_BYTE = 11
        image = MagicMock()
        image.convertToFormat.return_value = image
        image.width.return_value = 13
        image.height.return_value = 7
        image.constBits.return_value.tobytes.return_value = b"x" * (13 * 7 * 4)
        pixmap = MagicMock()
        pixmap.isNull.return_value = False
        pixmap.toImage.return_value = image
        monkeypatch.setattr(module, "gl", fake_gl)
        manager = module.GLTextureManager()
        monkeypatch.setattr(manager, "_get_or_create_pbo", lambda size: 0)

        assert manager.upload_pixmap(pixmap) == 0

        stats = manager.get_stats()
        assert stats["texture_allocations"] == 1
        assert stats["texture_allocation_bytes"] == 13 * 7 * 4
        assert stats["texture_upload_failures"] == 1
        assert stats["texture_deletions"] == 1
        assert stats["texture_deleted_bytes"] == 13 * 7 * 4
        assert stats["texture_uploads"] == 0
        assert stats["upload_bytes"] == 0
        fake_gl.glDeleteTextures.assert_called_once_with(55)

    def test_owner_delete_releases_tracking_only_after_success(self, monkeypatch):
        from unittest.mock import MagicMock
        from core.resources.manager import ResourceManager
        from rendering.gl_programs import texture_manager as module

        fake_gl = MagicMock()
        registry = MagicMock()
        monkeypatch.setattr(module, "gl", fake_gl)
        monkeypatch.setattr(ResourceManager, "get_app_shared", classmethod(lambda cls: registry))
        manager = module.GLTextureManager()
        manager._pbo_pool.append(module.PBOEntry(9, 256, resource_id="rid-ok"))

        manager._cleanup_pbo_pool()

        registry.release_tracking.assert_called_once_with("rid-ok")

    def test_failed_owner_delete_does_not_release_tracking(self, monkeypatch):
        from unittest.mock import MagicMock
        from core.resources.manager import ResourceManager
        from rendering.gl_programs import texture_manager as module

        fake_gl = MagicMock()
        fake_gl.glDeleteBuffers.side_effect = RuntimeError("delete failed")
        registry = MagicMock()
        monkeypatch.setattr(module, "gl", fake_gl)
        monkeypatch.setattr(ResourceManager, "get_app_shared", classmethod(lambda cls: registry))
        manager = module.GLTextureManager()
        manager._pbo_pool.append(module.PBOEntry(9, 256, resource_id="rid-live"))

        manager._cleanup_pbo_pool()

        registry.release_tracking.assert_not_called()

    def test_strict_cleanup_deletes_retained_texture_and_pbo_and_counts(
        self,
        monkeypatch,
    ):
        from unittest.mock import MagicMock, call
        from core.resources.manager import ResourceManager
        from rendering.gl_programs import texture_manager as module

        fake_gl = MagicMock()
        registry = MagicMock()
        monkeypatch.setattr(module, "gl", fake_gl)
        monkeypatch.setattr(
            ResourceManager,
            "get_app_shared",
            classmethod(lambda cls: registry),
        )
        manager = module.GLTextureManager()
        manager._initialized = True
        manager._texture_cache = {1: 11}
        manager._texture_lru = [1]
        manager._texture_bytes_by_id = {11: 128}
        manager._current_texture_bytes = 128
        manager._texture_resource_ids = {11: "texture-retained"}
        manager._pbo_pool = [
            module.PBOEntry(9, 256, resource_id="pbo-retained")
        ]

        manager.cleanup(strict=True)

        assert manager.is_initialized() is False
        assert manager.get_stats()["texture_count"] == 0
        assert manager.get_stats()["pbo_count"] == 0
        assert manager.get_stats()["texture_deletions"] == 1
        assert manager.get_stats()["texture_deleted_bytes"] == 128
        assert manager.get_stats()["pbo_deletions"] == 1
        assert manager.get_stats()["pbo_deleted_bytes"] == 256
        fake_gl.glDeleteTextures.assert_called_once()
        fake_gl.glDeleteBuffers.assert_called_once_with(1, [9])
        registry.release_tracking.assert_has_calls(
            [call("texture-retained"), call("pbo-retained")]
        )

    def test_strict_cleanup_retains_failed_pbo_ownership_and_initialized_state(
        self,
        monkeypatch,
    ):
        from unittest.mock import MagicMock
        from core.resources.manager import ResourceManager
        from rendering.gl_programs import texture_manager as module

        fake_gl = MagicMock()
        fake_gl.glDeleteBuffers.side_effect = RuntimeError("delete failed")
        registry = MagicMock()
        monkeypatch.setattr(module, "gl", fake_gl)
        monkeypatch.setattr(
            ResourceManager,
            "get_app_shared",
            classmethod(lambda cls: registry),
        )
        manager = module.GLTextureManager()
        manager._initialized = True
        retained = module.PBOEntry(9, 256, resource_id="pbo-live")
        manager._pbo_pool = [retained]

        with pytest.raises(RuntimeError, match="GLTextureManager cleanup incomplete"):
            manager.cleanup(strict=True)

        assert manager.is_initialized() is True
        assert manager._pbo_pool == [retained]
        assert manager.get_stats()["pbo_deletions"] == 0
        assert manager.get_stats()["pbo_deleted_bytes"] == 0
        registry.release_tracking.assert_not_called()


@pytest.mark.qt
def test_texture_upload_native_bgra_paths_preserve_pixels_in_real_context(
    qt_app,
    monkeypatch,
):
    """Exercise the installed PyOpenGL upload wrappers and exact pixel bytes."""

    from unittest.mock import MagicMock

    from PySide6.QtGui import (
        QColor,
        QImage,
        QOffscreenSurface,
        QOpenGLContext,
        QSurfaceFormat,
    )

    from core.resources.manager import ResourceManager
    from rendering.gl_programs import texture_manager as module

    fmt = QSurfaceFormat()
    fmt.setRenderableType(QSurfaceFormat.OpenGL)
    fmt.setProfile(QSurfaceFormat.CoreProfile)
    fmt.setVersion(3, 3)
    fmt.setSwapBehavior(QSurfaceFormat.SingleBuffer)

    context = QOpenGLContext()
    context.setFormat(fmt)
    if not context.create():
        pytest.skip("OpenGL 3.3 context unavailable on this runner")

    surface = QOffscreenSurface()
    surface.setFormat(fmt)
    surface.create()
    if not surface.isValid() or not context.makeCurrent(surface):
        pytest.skip("Unable to make an offscreen OpenGL context current")

    from OpenGL import GL as gl

    if not hasattr(gl, "glGetTexImage"):
        context.doneCurrent()
        pytest.skip("Desktop texture readback unavailable")

    registry = MagicMock()
    registry.register_gl_texture.return_value = ""
    registry.register_gl_vbo.return_value = ""
    monkeypatch.setattr(
        ResourceManager,
        "get_or_create_app_shared",
        classmethod(lambda cls: registry),
    )
    monkeypatch.setattr(
        ResourceManager,
        "get_app_shared",
        classmethod(lambda cls: registry),
    )

    class _PixmapImage:
        def __init__(self, image, key):
            self._image = image
            self._key = key

        def isNull(self):
            return False

        def toImage(self):
            return self._image

        def cacheKey(self):
            return self._key

    cases = (
        (
            QImage.Format.Format_RGB32,
            (
                QColor(255, 0, 0),
                QColor(0, 255, 0),
                QColor(0, 0, 255),
                QColor(12, 34, 56),
            ),
            [
                255, 0, 0, 255,
                0, 255, 0, 255,
                0, 0, 255, 255,
                12, 34, 56, 255,
            ],
        ),
        (
            QImage.Format.Format_ARGB32,
            (
                QColor(255, 0, 0, 64),
                QColor(0, 255, 0, 96),
                QColor(0, 0, 255, 128),
                QColor(12, 34, 56, 160),
            ),
            [
                255, 0, 0, 64,
                0, 255, 0, 96,
                0, 0, 255, 128,
                12, 34, 56, 160,
            ],
        ),
    )

    manager = module.GLTextureManager(owner="real-upload-test", generation=1)
    try:
        assert manager.initialize() is True
        for key, (image_format, colors, expected) in enumerate(cases, start=1):
            image = QImage(2, 2, image_format)
            for index, color in enumerate(colors):
                image.setPixelColor(index % 2, index // 2, color)

            texture_id = manager.get_or_create_texture(_PixmapImage(image, key))
            assert texture_id > 0
            gl.glBindTexture(gl.GL_TEXTURE_2D, texture_id)
            result = (ctypes.c_ubyte * 16)()
            gl.glGetTexImage(
                gl.GL_TEXTURE_2D,
                0,
                gl.GL_RGBA,
                gl.GL_UNSIGNED_BYTE,
                result,
            )
            assert list(result) == expected
        assert manager.get_stats()["pbo_uploads"] == len(cases)
        assert manager.get_stats()["direct_uploads"] == 0
        gl.glBindTexture(gl.GL_TEXTURE_2D, 0)
    finally:
        manager.cleanup(strict=True)
        context.doneCurrent()
        if hasattr(surface, "destroy"):
            surface.destroy()
