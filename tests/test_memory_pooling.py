"""
Tests for ResourceManager object pooling efficiency.

Tests cover:
- QPixmap/QImage pool management
- Pool statistics tracking
- Pool size limits and eviction
"""
import pytest


class TestPixmapPoolManagement:
    """Tests for QPixmap pool management in ResourceManager."""
    
    def test_pixmap_pool_initialization(self):
        """Test pixmap pool starts empty."""
        from core.resources.manager import ResourceManager
        
        rm = ResourceManager()
        assert len(rm._pixmap_pool) == 0
    
    def test_pixmap_pool_max_size_constant(self):
        """Test PIXMAP_POOL_MAX_SIZE is reasonable."""
        from core.resources.manager import ResourceManager
        
        assert ResourceManager.PIXMAP_POOL_MAX_SIZE >= 4
        assert ResourceManager.PIXMAP_POOL_MAX_SIZE <= 32
    
    def test_pool_stats_initialization(self):
        """Test pool stats start at zero."""
        from core.resources.manager import ResourceManager
        
        rm = ResourceManager()
        assert rm._pool_stats["pixmap_hits"] == 0
        assert rm._pool_stats["pixmap_misses"] == 0
        assert rm._pool_stats["image_hits"] == 0
        assert rm._pool_stats["image_misses"] == 0


class TestImagePoolManagement:
    """Tests for QImage pool management in ResourceManager."""
    
    def test_image_pool_initialization(self):
        """Test image pool starts empty."""
        from core.resources.manager import ResourceManager
        
        rm = ResourceManager()
        assert len(rm._image_pool) == 0
    
    def test_image_pool_max_size_constant(self):
        """Test IMAGE_POOL_MAX_SIZE is reasonable."""
        from core.resources.manager import ResourceManager
        
        assert ResourceManager.IMAGE_POOL_MAX_SIZE >= 4
        assert ResourceManager.IMAGE_POOL_MAX_SIZE <= 32


class TestPoolLocking:
    """Tests for pool thread safety."""
    
    def test_pool_lock_exists(self):
        """Test pool lock is initialized."""
        from core.resources.manager import ResourceManager
        import threading
        
        rm = ResourceManager()
        assert hasattr(rm, '_pool_lock')
        assert isinstance(rm._pool_lock, type(threading.Lock()))


class TestResourceManagerLifecycle:
    """Tests for ResourceManager lifecycle."""
    
    def test_initialization(self):
        """Test ResourceManager initializes correctly."""
        from core.resources.manager import ResourceManager
        
        rm = ResourceManager()
        assert rm._initialized is True
        assert rm._shutdown is False
    
    def test_resources_dict_empty(self):
        """Test resources dict starts empty."""
        from core.resources.manager import ResourceManager
        
        rm = ResourceManager()
        assert len(rm._resources) == 0
    
    def test_weak_refs_dict_empty(self):
        """Test weak refs dict starts empty."""
        from core.resources.manager import ResourceManager
        
        rm = ResourceManager()
        assert len(rm._weak_refs) == 0
    
    def test_strong_refs_dict_empty(self):
        """Test strong refs dict starts empty."""
        from core.resources.manager import ResourceManager
        
        rm = ResourceManager()
        assert len(rm._strong_refs) == 0
    
    def test_cleanup_handlers_dict_empty(self):
        """Test cleanup handlers dict starts empty."""
        from core.resources.manager import ResourceManager
        
        rm = ResourceManager()
        assert len(rm._cleanup_handlers) == 0


class TestResourceRegistration:
    """Tests for resource registration."""
    
    def test_register_returns_id(self):
        """Test register returns a resource ID."""
        from core.resources.manager import ResourceManager
        
        rm = ResourceManager()
        
        class TestResource:
            pass
        
        resource = TestResource()
        rid = rm.register(resource, description="Test resource")
        
        assert rid is not None
        assert len(rid) > 0
        assert "unknown" in rid.lower()
    
    def test_register_none_raises(self):
        """Test registering None raises ValueError."""
        from core.resources.manager import ResourceManager
        
        rm = ResourceManager()
        
        with pytest.raises(ValueError, match="Cannot register None"):
            rm.register(None)
    
    def test_register_qt_returns_id(self):
        """Test register_qt returns a resource ID."""
        from core.resources.manager import ResourceManager
        from PySide6.QtCore import QObject
        
        rm = ResourceManager()
        obj = QObject()
        
        rid = rm.register_qt(obj, description="Test Qt object")
        
        assert rid is not None
        assert len(rid) > 0
    
    def test_register_temp_file_returns_id(self):
        """Test register_temp_file returns a resource ID."""
        from core.resources.manager import ResourceManager
        import tempfile
        import os
        
        rm = ResourceManager()
        
        # Create a temp file
        fd, path = tempfile.mkstemp()
        os.close(fd)
        
        try:
            rid = rm.register_temp_file(path, description="Test temp file")
            assert rid is not None
            assert len(rid) > 0
        finally:
            # Clean up
            if os.path.exists(path):
                os.remove(path)


class TestResourceRetrieval:
    """Tests for resource retrieval."""
    
    def test_get_nonexistent_returns_none(self):
        """Test get returns None for nonexistent resource."""
        from core.resources.manager import ResourceManager
        
        rm = ResourceManager()
        result = rm.get("nonexistent_id")
        
        assert result is None
    
    def test_get_all_resources_empty(self):
        """Test get_all_resources returns empty list initially."""
        from core.resources.manager import ResourceManager
        
        rm = ResourceManager()
        resources = rm.get_all_resources()
        
        assert isinstance(resources, list)
        assert len(resources) == 0


class TestResourceTypes:
    """Tests for resource type handling."""
    
    def test_resource_type_from_string(self):
        """Test ResourceType.from_string conversion."""
        from core.resources.types import ResourceType
        
        assert ResourceType.from_string("FILE_HANDLE") == ResourceType.FILE_HANDLE
        assert ResourceType.from_string("gui_component") == ResourceType.GUI_COMPONENT
        assert ResourceType.from_string("unknown_type") == ResourceType.UNKNOWN
    
    def test_native_handle_type_exists(self):
        """Test NATIVE_HANDLE resource type exists."""
        from core.resources.types import ResourceType
        
        assert hasattr(ResourceType, "NATIVE_HANDLE")
        assert ResourceType.NATIVE_HANDLE is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
