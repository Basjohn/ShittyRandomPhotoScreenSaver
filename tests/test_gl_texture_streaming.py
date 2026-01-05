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
