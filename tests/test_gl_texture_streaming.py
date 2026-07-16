"""
Tests for GL texture streaming and PBO optimization.

Tests cover:
- PBO pool management
- Texture upload performance
- ResourceManager GL handle tracking
"""
import pytest
from PySide6.QtGui import QImage


def test_image_upload_view_uses_direct_contiguous_qimage_buffer():
    from rendering.gl_programs.texture_manager import _prepare_image_upload_view

    image = QImage(8, 8, QImage.Format.Format_ARGB32)
    image.fill(0xFF336699)

    upload = _prepare_image_upload_view(image)

    assert upload.direct is True
    assert upload.address is not None and upload.address > 0
    assert upload.address_owner is not None
    assert upload.size == image.sizeInBytes()
    assert upload.data.nbytes == image.sizeInBytes()


def test_image_upload_view_falls_back_to_owned_bytes():
    from rendering.gl_programs.texture_manager import _prepare_image_upload_view

    class _FakeImage:
        def bits(self):
            raise TypeError("read-only binding")

        def constBits(self):
            return memoryview(b"\x01\x02\x03\x04")

        def sizeInBytes(self):
            return 4

    upload = _prepare_image_upload_view(_FakeImage())

    assert upload.direct is False
    assert upload.address is None
    assert upload.address_owner is None
    assert upload.data == b"\x01\x02\x03\x04"
    assert upload.size == 4


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
        assert entry.resource_id is None
    
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

    def test_larger_pbo_replaces_smaller_idle_buffer(self, monkeypatch):
        import rendering.gl_programs.texture_manager as texture_module

        class FakeGL:
            GL_PIXEL_UNPACK_BUFFER = 1
            GL_STREAM_DRAW = 2

            def __init__(self):
                self.next_id = 100
                self.deleted = []

            def glGenBuffers(self, _count):
                self.next_id += 1
                return self.next_id

            def glBindBuffer(self, _target, _handle):
                pass

            def glBufferData(self, *_args):
                pass

            def glDeleteBuffers(self, _count, handles):
                self.deleted.extend(handles)

        class FakeResourceManager:
            def __init__(self):
                self.registered = []
                self.released = []

            def register_gl_vbo(self, handle, description=""):
                resource_id = f"pbo_{handle}"
                self.registered.append(resource_id)
                return resource_id

            def unregister(self, resource_id, force=False, cleanup=True):
                self.released.append((resource_id, force, cleanup))
                return True

        from core.resources.manager import ResourceManager

        fake_gl = FakeGL()
        resource_manager = FakeResourceManager()
        monkeypatch.setattr(texture_module, "gl", fake_gl)
        monkeypatch.setattr(
            ResourceManager,
            "get_or_create_app_shared",
            classmethod(lambda _cls: resource_manager),
        )

        manager = texture_module.GLTextureManager()
        first = manager._get_or_create_pbo(1024)
        manager._release_pbo(first)
        second = manager._get_or_create_pbo(4096)

        assert second != first
        assert len(manager._pbo_pool) == manager.MAX_PBO_ENTRIES == 1
        assert manager._pbo_pool[0].pbo_id == second
        assert resource_manager.released == [(f"pbo_{first}", True, True)]
        assert manager.get_stats()["pbo_replacements"] == 1
        assert fake_gl.deleted == []

    def test_failed_pbo_creation_releases_partial_buffer(self, monkeypatch):
        import rendering.gl_programs.texture_manager as texture_module

        class FakeGL:
            GL_PIXEL_UNPACK_BUFFER = 1
            GL_STREAM_DRAW = 2

            def __init__(self):
                self.deleted = []

            def glGenBuffers(self, _count):
                return 101

            def glBindBuffer(self, _target, _handle):
                pass

            def glBufferData(self, *_args):
                raise RuntimeError("allocation failed")

            def glDeleteBuffers(self, _count, handles):
                self.deleted.extend(handles)

        fake_gl = FakeGL()
        monkeypatch.setattr(texture_module, "gl", fake_gl)
        manager = texture_module.GLTextureManager()

        assert manager._get_or_create_pbo(4096) == 0
        assert manager._pbo_pool == []
        assert fake_gl.deleted == [101]


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

    def test_cache_keeps_only_active_and_adjacent_transition_pairs(self, monkeypatch):
        import rendering.gl_programs.texture_manager as texture_module

        class FakePixmap:
            def __init__(self, key):
                self._key = key

            def isNull(self):
                return False

            def cacheKey(self):
                return self._key

        class FakeGL:
            def __init__(self):
                self.deleted = []

            def glDeleteTextures(self, texture_id):
                self.deleted.append(texture_id)

        class FakeResourceManager:
            def __init__(self):
                self.released = []

            def unregister(self, resource_id, force=False, cleanup=True):
                self.released.append((resource_id, force, cleanup))
                return True

        fake_gl = FakeGL()
        monkeypatch.setattr(texture_module, "gl", fake_gl)
        manager = texture_module.GLTextureManager()
        manager._resource_manager = FakeResourceManager()

        next_texture = 100

        def fake_upload(_pixmap):
            nonlocal next_texture
            next_texture += 1
            manager._texture_resource_ids[next_texture] = f"texture_{next_texture}"
            manager._texture_sizes[next_texture] = 4096
            return next_texture

        monkeypatch.setattr(manager, "upload_pixmap", fake_upload)

        for key in range(1, 6):
            manager.get_or_create_texture(FakePixmap(key))

        assert len(manager._texture_cache) == manager.MAX_CACHED_TEXTURES == 4
        assert manager._resource_manager.released == [("texture_101", True, True)]
        assert fake_gl.deleted == []

    def test_cleanup_releases_registered_textures_through_resource_manager(self, monkeypatch):
        import rendering.gl_programs.texture_manager as texture_module

        class FakeGL:
            def __init__(self):
                self.deleted = []

            def glDeleteTextures(self, texture_id):
                self.deleted.append(texture_id)

        class FakeResourceManager:
            def __init__(self):
                self.released = []

            def unregister(self, resource_id, force=False, cleanup=True):
                self.released.append((resource_id, force, cleanup))
                return True

        fake_gl = FakeGL()
        monkeypatch.setattr(texture_module, "gl", fake_gl)
        manager = texture_module.GLTextureManager()
        manager._resource_manager = FakeResourceManager()
        manager._texture_cache = {1: 44}
        manager._texture_lru = [1]
        manager._texture_resource_ids = {44: "texture_44"}
        manager._texture_sizes = {44: 1024}

        manager.cleanup_cache()

        assert manager._resource_manager.released == [("texture_44", True, True)]
        assert fake_gl.deleted == []
        assert manager._texture_cache == {}
        assert manager._texture_resource_ids == {}

    def test_abandon_forgets_handles_without_gl_cleanup(self):
        from rendering.gl_programs.texture_manager import GLTextureManager, PBOEntry

        class FakeResourceManager:
            def __init__(self):
                self.released = []

            def unregister(self, resource_id, force=False, cleanup=True):
                self.released.append((resource_id, force, cleanup))
                return True

        manager = GLTextureManager()
        manager._resource_manager = FakeResourceManager()
        manager._texture_cache = {1: 44}
        manager._texture_lru = [1]
        manager._texture_resource_ids = {44: "texture_44"}
        manager._texture_sizes = {44: 1024}
        manager._pbo_pool = [
            PBOEntry(55, 2048, resource_id="pbo_55"),
        ]

        manager.abandon()

        assert manager._resource_manager.released == [
            ("texture_44", True, False),
            ("pbo_55", True, False),
        ]
        assert manager._texture_cache == {}
        assert manager._pbo_pool == []


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


class TestGLGeometryManagerLifecycle:
    def test_partial_handle_registration_remains_owned_for_cleanup(
        self,
        monkeypatch,
    ):
        import rendering.gl_programs.geometry_manager as geometry_module
        from core.resources.manager import ResourceManager

        class FakeGL:
            GL_ARRAY_BUFFER = 1
            GL_STATIC_DRAW = 2
            GL_FLOAT = 3
            GL_FALSE = 0

            def __init__(self):
                self.deleted_buffers = []
                self.deleted_arrays = []

            def glGenVertexArrays(self, _count):
                return 11

            def glGenBuffers(self, _count):
                return 12

            def glBindVertexArray(self, _handle):
                pass

            def glBindBuffer(self, _target, _handle):
                pass

            def glBufferData(self, *_args):
                pass

            def glEnableVertexAttribArray(self, _index):
                pass

            def glVertexAttribPointer(self, *_args):
                pass

            def glDeleteBuffers(self, _count, handles):
                self.deleted_buffers.extend(handles)

            def glDeleteVertexArrays(self, _count, handles):
                self.deleted_arrays.extend(handles)

        class FakeResourceManager:
            def __init__(self):
                self.released = []

            def register_gl_vao(self, _handle, description=""):
                return "quad_vao"

            def register_gl_vbo(self, _handle, description=""):
                raise RuntimeError("registration failed")

            def unregister(self, resource_id, force=False, cleanup=True):
                self.released.append((resource_id, force, cleanup))
                return True

        fake_gl = FakeGL()
        resource_manager = FakeResourceManager()
        monkeypatch.setattr(geometry_module, "gl", fake_gl)
        monkeypatch.setattr(
            ResourceManager,
            "get_or_create_app_shared",
            classmethod(lambda _cls: resource_manager),
        )

        manager = geometry_module.GLGeometryManager()
        assert manager._create_quad_geometry() is True
        assert manager._quad_vao_rid == "quad_vao"
        assert manager._quad_vbo_rid is None

        manager.cleanup()

        assert resource_manager.released == [("quad_vao", True, True)]
        assert fake_gl.deleted_buffers == [12]
        assert fake_gl.deleted_arrays == []

    def test_partial_initialization_releases_created_geometry(self, monkeypatch):
        import rendering.gl_programs.geometry_manager as geometry_module

        class FakeGL:
            def __init__(self):
                self.deleted_buffers = []
                self.deleted_arrays = []

            def glDeleteBuffers(self, _count, handles):
                self.deleted_buffers.extend(handles)

            def glDeleteVertexArrays(self, _count, handles):
                self.deleted_arrays.extend(handles)

        class FakeResourceManager:
            def __init__(self):
                self.released = []

            def unregister(self, resource_id, force=False, cleanup=True):
                self.released.append((resource_id, force, cleanup))
                return True

        monkeypatch.setattr(geometry_module, "gl", FakeGL())
        manager = geometry_module.GLGeometryManager()
        manager._resource_manager = FakeResourceManager()

        def create_quad():
            manager._quad_vao = 11
            manager._quad_vbo = 12
            manager._quad_vao_rid = "quad_vao"
            manager._quad_vbo_rid = "quad_vbo"
            return True

        monkeypatch.setattr(manager, "_create_quad_geometry", create_quad)
        monkeypatch.setattr(manager, "_create_box_geometry", lambda: False)

        assert manager.initialize() is False
        assert manager._resource_manager.released == [
            ("quad_vbo", True, True),
            ("quad_vao", True, True),
        ]
        assert manager.quad_vao == 0
        assert manager.quad_vbo == 0

    def test_cleanup_releases_registered_geometry_through_resource_manager(self, monkeypatch):
        import rendering.gl_programs.geometry_manager as geometry_module

        class FakeGL:
            def __init__(self):
                self.deleted_buffers = []
                self.deleted_arrays = []

            def glDeleteBuffers(self, _count, handles):
                self.deleted_buffers.extend(handles)

            def glDeleteVertexArrays(self, _count, handles):
                self.deleted_arrays.extend(handles)

        class FakeResourceManager:
            def __init__(self):
                self.released = []

            def unregister(self, resource_id, force=False, cleanup=True):
                self.released.append((resource_id, force, cleanup))
                return True

        fake_gl = FakeGL()
        monkeypatch.setattr(geometry_module, "gl", fake_gl)
        manager = geometry_module.GLGeometryManager()
        manager._resource_manager = FakeResourceManager()
        manager._quad_vao = 11
        manager._quad_vbo = 12
        manager._box_vao = 13
        manager._box_vbo = 14
        manager._quad_vao_rid = "quad_vao"
        manager._quad_vbo_rid = "quad_vbo"
        manager._box_vao_rid = "box_vao"
        manager._box_vbo_rid = "box_vbo"
        manager._initialized = True

        manager.cleanup()

        assert manager._resource_manager.released == [
            ("quad_vbo", True, True),
            ("quad_vao", True, True),
            ("box_vbo", True, True),
            ("box_vao", True, True),
        ]
        assert fake_gl.deleted_buffers == []
        assert fake_gl.deleted_arrays == []
        assert manager.is_initialized() is False


class TestSpotifyOverlayGLLifecycle:
    def test_cleanup_releases_registered_overlay_handles_once(self):
        from types import SimpleNamespace

        from widgets.spotify_bars_gl_overlay import SpotifyBarsGLOverlay

        class FakeState:
            @staticmethod
            def is_ready():
                return True

        class FakeResourceManager:
            def __init__(self):
                self.released = []

            def unregister(self, resource_id, force=False, cleanup=True):
                self.released.append((resource_id, force, cleanup))
                return True

        resource_manager = FakeResourceManager()
        fake_overlay = SimpleNamespace(
            _gl_state=FakeState(),
            makeCurrent=lambda: None,
            doneCurrent=lambda: None,
            _gl_program_warm_timer=None,
            _gl_program_warm_queue=["spectrum"],
            _gl_programs={"bubble": 101, "spectrum": 102},
            _gl_program_rids={"bubble": "program_101", "spectrum": "program_102"},
            _gl_uniforms={"bubble": {}, "spectrum": {}},
            _gl_program=101,
            _gl_mask_program=103,
            _gl_mask_program_rid="mask_103",
            _gl_mask_uniforms={"u_card_rect": 1, "u_radius": 2},
            _gl_vbo=201,
            _gl_vao=202,
            _gl_vbo_rid="vbo_201",
            _gl_vao_rid="vao_202",
            _gl_resource_manager=resource_manager,
        )

        SpotifyBarsGLOverlay.cleanup_gl(fake_overlay)

        assert resource_manager.released == [
            ("program_101", True, True),
            ("program_102", True, True),
            ("mask_103", True, True),
            ("vbo_201", True, True),
            ("vao_202", True, True),
        ]
        assert fake_overlay._gl_programs == {}
        assert fake_overlay._gl_mask_program is None
        assert fake_overlay._gl_mask_uniforms == {}
        assert fake_overlay._gl_vbo is None
        assert fake_overlay._gl_vao is None


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
