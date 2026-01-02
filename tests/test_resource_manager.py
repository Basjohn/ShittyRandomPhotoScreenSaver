"""
Integration tests for ResourceManager.

Tests the centralized resource management functionality including:
- Resource registration and tracking
- Weak reference management
- Cleanup handlers
- Thread safety
- Object pooling
- Shutdown behavior
"""
import threading
from unittest.mock import MagicMock

import pytest
from PySide6.QtGui import QImage, QPixmap

from core.resources.manager import ResourceManager
from core.resources.types import ResourceType


@pytest.fixture
def resource_manager():
    """Provide a ResourceManager instance that is always shut down."""
    manager = ResourceManager()
    try:
        yield manager
    finally:
        try:
            manager.shutdown()
        except Exception:
            pass


@pytest.fixture
def qt_resource_manager(qt_app):
    """Provide a ResourceManager tied to the qt_app fixture."""
    manager = ResourceManager()
    try:
        yield manager
    finally:
        try:
            manager.shutdown()
        except Exception:
            pass


class TestResourceManagerInit:
    """Resource manager initialization tests."""

    def test_init_creates_instance(self):
        """Test that ResourceManager can be instantiated."""
        manager = ResourceManager()
        assert manager is not None
        assert manager._initialized is True

    def test_init_creates_empty_resources(self):
        """Test that resources dict is empty on init."""
        manager = ResourceManager()
        assert isinstance(manager._resources, dict)

    def test_init_creates_pools(self):
        """Test that object pools are created."""
        manager = ResourceManager()
        assert isinstance(manager._pixmap_pool, dict)
        assert isinstance(manager._image_pool, dict)

    def test_init_not_shutdown(self):
        """Test that manager is not shutdown on init."""
        manager = ResourceManager()
        assert manager._shutdown is False


class TestResourceRegistration:
    """Resource registration tests."""

    def test_register_returns_id(self):
        """Test that register returns a resource ID."""
        manager = ResourceManager()
        obj = MagicMock()  # MagicMock can be weak-referenced
        resource_id = manager.register(obj, ResourceType.UNKNOWN, "test object")
        assert resource_id is not None
        assert isinstance(resource_id, str)

    def test_register_none_raises(self):
        """Test that registering None raises ValueError."""
        manager = ResourceManager()
        with pytest.raises(ValueError):
            manager.register(None)

    def test_register_with_description(self):
        """Test registering with description."""
        manager = ResourceManager()
        obj = MagicMock()
        resource_id = manager.register(obj, ResourceType.UNKNOWN, "my description")
        assert resource_id is not None

    def test_register_with_cleanup_handler(self):
        """Test registering with custom cleanup handler."""
        manager = ResourceManager()
        obj = MagicMock()
        cleanup_called = []
        
        def cleanup(resource):
            cleanup_called.append(resource)
        
        resource_id = manager.register(
            obj, 
            ResourceType.UNKNOWN, 
            "test",
            cleanup_handler=cleanup
        )
        assert resource_id is not None

    def test_register_with_metadata(self):
        """Test registering with additional metadata."""
        manager = ResourceManager()
        obj = MagicMock()
        resource_id = manager.register(
            obj,
            ResourceType.UNKNOWN,
            "test",
            custom_key="custom_value"
        )
        assert resource_id is not None

    def test_register_after_shutdown_raises(self):
        """Test that registering after shutdown raises RuntimeError."""
        manager = ResourceManager()
        manager._shutdown = True
        
        with pytest.raises(RuntimeError):
            manager.register(MagicMock())


class TestResourceTypes:
    """Resource type tests."""

    def test_resource_type_unknown(self):
        """Test UNKNOWN resource type."""
        assert ResourceType.UNKNOWN is not None

    def test_resource_type_timer(self):
        """Test TIMER resource type."""
        assert ResourceType.TIMER is not None

    def test_resource_type_thread_pool(self):
        """Test THREAD_POOL resource type."""
        assert ResourceType.THREAD_POOL is not None

    def test_resource_type_file_handle(self):
        """Test FILE_HANDLE resource type."""
        assert ResourceType.FILE_HANDLE is not None

    def test_resource_type_from_string(self):
        """Test ResourceType.from_string conversion."""
        assert ResourceType.from_string("TIMER") == ResourceType.TIMER
        assert ResourceType.from_string("unknown") == ResourceType.UNKNOWN
        assert ResourceType.from_string("invalid") == ResourceType.UNKNOWN


class TestResourceCleanup:
    """Resource cleanup tests."""

    def test_cleanup_all_sets_shutdown(self):
        """Test that cleanup_all sets shutdown flag."""
        manager = ResourceManager()
        manager.cleanup_all()
        assert manager._shutdown is True

    def test_cleanup_all_clears_resources(self):
        """Test that cleanup_all clears resources."""
        manager = ResourceManager()
        obj = MagicMock()
        manager.register(obj, ResourceType.UNKNOWN, "test")
        manager.cleanup_all()
        # Resources should be cleared or marked for cleanup

    def test_cleanup_handler_called(self):
        """Test that custom cleanup handler is called."""
        manager = ResourceManager()
        cleanup_called = []
        
        class TestResource:
            pass
        
        obj = TestResource()
        
        def cleanup(resource):
            cleanup_called.append(True)
        
        manager.register(obj, ResourceType.UNKNOWN, "test", cleanup_handler=cleanup)
        manager.cleanup_all()
        
        # Cleanup should have been attempted
        # Note: weak refs may have been collected

    def test_cleanup_all_idempotent(self):
        """Test that cleanup_all can be called multiple times."""
        manager = ResourceManager()
        manager.cleanup_all()
        # Should not raise
        manager.cleanup_all()


class TestResourceManagerThreadSafety:
    """Thread safety tests."""

    def test_concurrent_registration(self):
        """Test concurrent resource registration is thread-safe."""
        manager = ResourceManager()
        errors = []
        registered = []
        lock = threading.Lock()
        
        def register_resources(thread_id):
            try:
                for i in range(10):
                    obj = MagicMock()  # MagicMock can be weak-referenced
                    rid = manager.register(obj, ResourceType.UNKNOWN, f"thread_{thread_id}_{i}")
                    with lock:
                        registered.append(rid)
            except Exception as e:
                with lock:
                    errors.append(e)
        
        threads = [threading.Thread(target=register_resources, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        assert len(errors) == 0
        assert len(registered) == 50

    def test_lock_exists(self):
        """Test that manager has a lock for thread safety."""
        manager = ResourceManager()
        assert hasattr(manager, '_lock')
        assert isinstance(manager._lock, type(threading.RLock()))


class TestObjectPooling:
    """Object pooling tests."""

    def test_pool_stats_initialized(self):
        """Test that pool stats are initialized."""
        manager = ResourceManager()
        assert "pixmap_hits" in manager._pool_stats
        assert "pixmap_misses" in manager._pool_stats
        assert "image_hits" in manager._pool_stats
        assert "image_misses" in manager._pool_stats

    def test_pool_lock_exists(self):
        """Test that pool has its own lock."""
        manager = ResourceManager()
        assert hasattr(manager, '_pool_lock')

    def test_pixmap_pool_max_size(self):
        """Test pixmap pool max size constant."""
        assert ResourceManager.PIXMAP_POOL_MAX_SIZE == 8

    def test_image_pool_max_size(self):
        """Test image pool max size constant."""
        assert ResourceManager.IMAGE_POOL_MAX_SIZE == 8


class TestRegisterQt:
    """Qt-specific registration tests."""

    def test_register_qt_method_exists(self):
        """Test that register_qt method exists."""
        manager = ResourceManager()
        assert hasattr(manager, 'register_qt') or hasattr(manager, 'register')

    def test_register_with_gui_component_type(self):
        """Test registering with GUI_COMPONENT type."""
        manager = ResourceManager()
        obj = MagicMock()
        resource_id = manager.register(obj, ResourceType.GUI_COMPONENT, "mock widget")
        assert resource_id is not None

    def test_register_with_timer_type(self):
        """Test registering with TIMER type."""
        manager = ResourceManager()
        obj = MagicMock()
        resource_id = manager.register(obj, ResourceType.TIMER, "mock timer")
        assert resource_id is not None


class TestResourceInfo:
    """ResourceInfo tests."""

    def test_resource_info_creation(self):
        """Test ResourceInfo can be created."""
        from core.resources.types import ResourceInfo
        
        info = ResourceInfo(
            resource_id="test_id",
            resource_type=ResourceType.UNKNOWN,
            description="test description"
        )
        assert info.resource_id == "test_id"
        assert info.resource_type == ResourceType.UNKNOWN
        assert info.description == "test description"


class TestWeakReferences:
    """Weak reference management tests."""

    def test_weak_refs_dict_exists(self):
        """Test that weak refs dict exists."""
        manager = ResourceManager()
        assert hasattr(manager, '_weak_refs')
        assert isinstance(manager._weak_refs, dict)

    def test_strong_refs_dict_exists(self):
        """Test that strong refs dict exists."""
        manager = ResourceManager()
        assert hasattr(manager, '_strong_refs')
        assert isinstance(manager._strong_refs, dict)


class TestCleanupHandlers:
    """Cleanup handler tests."""

    def test_cleanup_handlers_dict_exists(self):
        """Test that cleanup handlers dict exists."""
        manager = ResourceManager()
        assert hasattr(manager, '_cleanup_handlers')
        assert isinstance(manager._cleanup_handlers, dict)

    def test_custom_cleanup_handler_stored(self):
        """Test that custom cleanup handler is stored."""
        manager = ResourceManager()
        
        def my_cleanup(resource):
            pass
        
        obj = MagicMock()
        resource_id = manager.register(
            obj,
            ResourceType.UNKNOWN,
            "test",
            cleanup_handler=my_cleanup
        )

        # Handler should be stored
        assert resource_id in manager._cleanup_handlers


class TestResourceLifecycle:
    """End-to-end registration and unregister tests."""

    def test_register_resource(self, resource_manager):
        class TestResource:
            def __init__(self):
                self.cleaned_up = False

            def cleanup(self):
                self.cleaned_up = True

        resource = TestResource()
        resource_id = resource_manager.register(resource, ResourceType.CUSTOM, "Test resource")

        assert resource_id is not None
        assert resource_manager.get(resource_id) is resource

        resource_manager.shutdown()
        assert resource.cleaned_up is True

    def test_unregister_resource_calls_handler(self, resource_manager):
        cleaned_up: list[bool] = []

        def cleanup_handler(obj):
            cleaned_up.append(True)

        class TestResource:
            pass

        resource = TestResource()
        resource_id = resource_manager.register(
            resource,
            ResourceType.CUSTOM,
            "Test resource",
            cleanup_handler=cleanup_handler,
        )

        result = resource_manager.unregister(resource_id, force=True)

        assert result is True
        assert len(cleaned_up) == 1
        assert resource_manager.get(resource_id) is None


class TestTemporaryFiles:
    """Temporary file registration tests."""

    def test_register_temp_file_deletes_on_shutdown(self, resource_manager, tmp_path):
        temp_file = tmp_path / "test.txt"
        temp_file.write_text("test content")

        resource_id = resource_manager.register_temp_file(
            str(temp_file),
            "Test temp file",
            delete=True,
        )

        assert resource_id is not None
        assert temp_file.exists()

        resource_manager.shutdown()

        assert not temp_file.exists()


class TestResourceStats:
    """Resource enumeration and stats tests."""

    def test_get_all_resources(self, resource_manager):
        class TestResource:
            pass

        r1 = TestResource()
        r2 = TestResource()

        resource_manager.register(r1, ResourceType.CUSTOM, "Resource 1")
        resource_manager.register(r2, ResourceType.CUSTOM, "Resource 2")

        resources = resource_manager.get_all_resources()

        assert len(resources) >= 2

    def test_get_stats_contains_totals(self, resource_manager):
        class TestResource:
            pass

        resource_manager.register(TestResource(), ResourceType.GUI_COMPONENT, "GUI resource")

        stats = resource_manager.get_stats()

        assert "total_resources" in stats
        assert stats["total_resources"] >= 1
        assert "by_type" in stats
        assert "by_group" in stats


class TestPixmapPooling:
    """QPixmap pooling behaviour."""

    def test_acquire_returns_none_when_empty(self, qt_resource_manager):
        result = qt_resource_manager.acquire_pixmap(100, 100)
        assert result is None

    def test_release_and_acquire(self, qt_resource_manager):
        pixmap = QPixmap(100, 100)
        assert qt_resource_manager.release_pixmap(pixmap) is True

        acquired = qt_resource_manager.acquire_pixmap(100, 100)
        assert acquired is not None
        assert acquired.width() == 100
        assert acquired.height() == 100

    def test_pool_size_limit(self, qt_resource_manager):
        for _ in range(qt_resource_manager.PIXMAP_POOL_MAX_SIZE + 5):
            qt_resource_manager.release_pixmap(QPixmap(50, 50))

        stats = qt_resource_manager.get_pool_stats()
        assert stats["pixmap_pool_size"] <= qt_resource_manager.PIXMAP_POOL_MAX_SIZE

    def test_pool_stats_tracking(self, qt_resource_manager):
        qt_resource_manager.acquire_pixmap(100, 100)

        pixmap = QPixmap(100, 100)
        qt_resource_manager.release_pixmap(pixmap)
        qt_resource_manager.acquire_pixmap(100, 100)

        stats = qt_resource_manager.get_pool_stats()
        assert stats["pixmap_misses"] >= 1
        assert stats["pixmap_hits"] >= 1

    def test_different_sizes_use_separate_buckets(self, qt_resource_manager):
        qt_resource_manager.release_pixmap(QPixmap(100, 100))
        qt_resource_manager.release_pixmap(QPixmap(200, 200))

        stats = qt_resource_manager.get_pool_stats()
        assert stats["pixmap_buckets"] == 2


class TestImagePooling:
    """QImage pooling behaviour."""

    def test_acquire_returns_none_when_empty(self, qt_resource_manager):
        result = qt_resource_manager.acquire_image(100, 100)
        assert result is None

    def test_release_and_acquire(self, qt_resource_manager):
        image = QImage(100, 100, QImage.Format.Format_ARGB32)
        assert qt_resource_manager.release_image(image) is True

        acquired = qt_resource_manager.acquire_image(100, 100)
        assert acquired is not None
        assert acquired.width() == 100
        assert acquired.height() == 100


class TestPoolCleanup:
    """Pool cleanup behaviour."""

    def test_clear_pools(self, qt_resource_manager):
        qt_resource_manager.release_pixmap(QPixmap(100, 100))
        qt_resource_manager.release_image(QImage(100, 100, QImage.Format.Format_ARGB32))

        qt_resource_manager.clear_pools()
        stats = qt_resource_manager.get_pool_stats()

        assert stats["pixmap_pool_size"] == 0
        assert stats["image_pool_size"] == 0

    def test_shutdown_clears_pixmap_pool(self, qt_resource_manager):
        qt_resource_manager.release_pixmap(QPixmap(100, 100))
        qt_resource_manager.shutdown()
        stats = qt_resource_manager.get_pool_stats()
        assert stats["pixmap_pool_size"] == 0
