"""
Tests for ResourceManager.
"""
import pytest
from core.resources import ResourceManager, ResourceType


def test_resource_manager_initialization():
    """Test ResourceManager initialization."""
    manager = ResourceManager()
    
    assert manager is not None
    assert manager._initialized is True
    
    manager.shutdown()


def test_register_resource():
    """Test registering a resource."""
    manager = ResourceManager()
    
    class TestResource:
        def __init__(self):
            self.cleaned_up = False
        
        def cleanup(self):
            self.cleaned_up = True
    
    resource = TestResource()
    resource_id = manager.register(
        resource,
        ResourceType.CUSTOM,
        "Test resource"
    )
    
    assert resource_id is not None
    assert manager.get(resource_id) is resource
    
    manager.shutdown()
    assert resource.cleaned_up is True


def test_unregister_resource():
    """Test unregistering a resource."""
    manager = ResourceManager()
    
    cleaned_up = []
    
    def cleanup_handler(obj):
        cleaned_up.append(True)
    
    class TestResource:
        pass
    
    resource = TestResource()
    resource_id = manager.register(
        resource,
        ResourceType.CUSTOM,
        "Test resource",
        cleanup_handler=cleanup_handler
    )
    
    result = manager.unregister(resource_id, force=True)
    
    assert result is True
    assert len(cleaned_up) == 1
    assert manager.get(resource_id) is None
    
    manager.shutdown()


def test_register_temp_file(tmp_path):
    """Test registering a temporary file."""
    manager = ResourceManager()
    
    # Create a temp file
    temp_file = tmp_path / "test.txt"
    temp_file.write_text("test content")
    
    assert temp_file.exists()
    
    resource_id = manager.register_temp_file(
        str(temp_file),
        "Test temp file",
        delete=True
    )
    
    assert resource_id is not None
    
    # Shutdown should delete the file
    manager.shutdown()
    
    assert not temp_file.exists()


def test_get_all_resources():
    """Test getting all resources."""
    manager = ResourceManager()
    
    class TestResource:
        pass
    
    r1 = TestResource()
    r2 = TestResource()
    
    manager.register(r1, ResourceType.CUSTOM, "Resource 1")
    manager.register(r2, ResourceType.CUSTOM, "Resource 2")
    
    resources = manager.get_all_resources()
    
    assert len(resources) >= 2
    
    manager.shutdown()


def test_get_stats():
    """Test getting resource statistics."""
    manager = ResourceManager()
    
    class TestResource:
        pass
    
    r1 = TestResource()
    manager.register(r1, ResourceType.GUI_COMPONENT, "GUI resource")
    
    stats = manager.get_stats()
    
    assert 'total_resources' in stats
    assert stats['total_resources'] >= 1
    assert 'by_type' in stats
    assert 'by_group' in stats
    
    manager.shutdown()
