"""
Tests for GL texture streaming and PBO optimization.

Tests cover:
- PBO pool management
- Texture upload performance
- ResourceManager GL handle tracking
"""
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
    
    def test_singleton_getter(self):
        """Test get_texture_manager returns singleton."""
        from rendering.gl_programs.texture_manager import get_texture_manager, cleanup_texture_manager
        
        # Clean up any existing singleton
        cleanup_texture_manager()
        
        manager1 = get_texture_manager()
        manager2 = get_texture_manager()
        
        assert manager1 is manager2
        
        # Clean up
        cleanup_texture_manager()
    
    def test_cleanup_resets_singleton(self):
        """Test cleanup_texture_manager resets singleton."""
        from rendering.gl_programs.texture_manager import get_texture_manager, cleanup_texture_manager
        
        manager1 = get_texture_manager()
        cleanup_texture_manager()
        manager2 = get_texture_manager()
        
        # Should be different instances
        assert manager1 is not manager2
        
        # Clean up
        cleanup_texture_manager()


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
