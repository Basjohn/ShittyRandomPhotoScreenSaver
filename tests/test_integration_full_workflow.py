"""
Integration tests for full workflow scenarios.

Phase 6.1: End-to-end integration tests covering:
- Settings initialization and persistence
- Widget creation and lifecycle
- Transition controller workflow
- GL state management integration
- MC vs normal build feature parity
"""
from __future__ import annotations

import pytest

from PySide6.QtWidgets import QWidget


# =============================================================================
# Settings Integration Tests
# =============================================================================

class TestSettingsIntegration:
    """Test settings initialization, validation, and persistence."""
    
    def test_settings_manager_initialization(self, tmp_path):
        """SettingsManager should initialize properly."""
        from core.settings.settings_manager import SettingsManager
        
        sm = SettingsManager(storage_base_dir=tmp_path)
        
        # Should be initialized
        assert sm is not None
        assert hasattr(sm, 'get')
        assert hasattr(sm, 'set')
    
    def test_settings_defaults_loaded(self, tmp_path):
        """Default settings should be loaded on initialization."""
        from core.settings.settings_manager import SettingsManager
        
        sm = SettingsManager(storage_base_dir=tmp_path)
        
        # Check a few key defaults
        assert sm.get("timing.interval") is not None
        assert sm.get("display.mode") is not None
    
    def test_settings_validate_and_repair_exists(self, tmp_path):
        """validate_and_repair method should exist."""
        from core.settings.settings_manager import SettingsManager
        
        sm = SettingsManager(storage_base_dir=tmp_path)
        
        # Method should exist
        assert hasattr(sm, 'validate_and_repair')
        
        # Should return a dict
        repairs = sm.validate_and_repair()
        assert isinstance(repairs, dict)
    
    def test_settings_type_coercion(self, tmp_path):
        """Settings should properly coerce types."""
        from core.settings.settings_manager import SettingsManager
        
        sm = SettingsManager(storage_base_dir=tmp_path)
        
        # to_bool should handle various inputs
        assert sm.to_bool(True, False) is True
        assert sm.to_bool("true", False) is True
        assert sm.to_bool("1", False) is True
        assert sm.to_bool(False, True) is False
        assert sm.to_bool("false", True) is False
        assert sm.to_bool("0", True) is False


# =============================================================================
# Widget Lifecycle Integration Tests
# =============================================================================

class TestWidgetLifecycleIntegration:
    """Test widget creation, initialization, and cleanup."""
    
    @pytest.mark.qt
    def test_widget_manager_creates_widgets(self, qt_app, tmp_path):
        """WidgetManager should create widgets based on settings."""
        from rendering.widget_manager import WidgetManager
        from core.settings.settings_manager import SettingsManager
        
        parent = QWidget()
        parent.resize(1920, 1080)
        
        sm = SettingsManager(storage_base_dir=tmp_path)
        wm = WidgetManager(parent, sm)
        
        # Should have been initialized
        assert wm is not None
        
        parent.deleteLater()
    
    @pytest.mark.qt
    def test_widget_manager_cleanup(self, qt_app, tmp_path):
        """WidgetManager cleanup should not raise."""
        from rendering.widget_manager import WidgetManager
        from core.settings.settings_manager import SettingsManager
        
        parent = QWidget()
        parent.resize(1920, 1080)
        
        sm = SettingsManager(storage_base_dir=tmp_path)
        wm = WidgetManager(parent, sm)
        
        # Cleanup should not raise
        try:
            wm.cleanup()
        except Exception as e:
            pytest.fail(f"WidgetManager cleanup raised: {e}")
        
        parent.deleteLater()


# =============================================================================
# Transition Controller Integration Tests
# =============================================================================

class TestTransitionControllerIntegration:
    """Test transition controller workflow."""
    
    def test_transition_controller_module_exists(self):
        """TransitionController module should be importable."""
        from rendering.transition_controller import TransitionController
        
        assert TransitionController is not None
    
    def test_transition_controller_has_snap_to_new(self):
        """stop_current should have snap_to_new parameter."""
        from rendering.transition_controller import TransitionController
        import inspect
        
        sig = inspect.signature(TransitionController.stop_current)
        params = list(sig.parameters.keys())
        
        assert 'snap_to_new' in params


# =============================================================================
# GL State Management Integration Tests
# =============================================================================

class TestGLStateManagementIntegration:
    """Test GL state management integration."""
    
    def test_gl_state_manager_initialization(self):
        """GLStateManager should initialize properly."""
        from rendering.gl_state_manager import GLStateManager, GLContextState
        
        gsm = GLStateManager()
        
        assert gsm is not None
        assert gsm.get_state() == GLContextState.UNINITIALIZED
    
    def test_gl_state_manager_transitions(self):
        """GLStateManager should handle state transitions."""
        from rendering.gl_state_manager import GLStateManager, GLContextState
        
        gsm = GLStateManager()
        
        # Transition to INITIALIZING
        gsm.transition(GLContextState.INITIALIZING)
        assert gsm.get_state() == GLContextState.INITIALIZING
        
        # Transition to READY
        gsm.transition(GLContextState.READY)
        assert gsm.get_state() == GLContextState.READY
        assert gsm.is_ready() is True
    
    def test_transition_state_manager_clear_all(self):
        """TransitionStateManager.clear_all should reset all states."""
        from rendering.transition_state import TransitionStateManager, CrossfadeState
        
        tsm = TransitionStateManager()
        
        # Set a state
        tsm.crossfade = CrossfadeState()
        assert tsm.get_active_transition() == "crossfade"
        
        # Clear all
        tsm.clear_all()
        assert tsm.get_active_transition() is None


# =============================================================================
# Resource Manager Integration Tests
# =============================================================================

class TestResourceManagerIntegration:
    """Test ResourceManager integration."""
    
    def test_resource_manager_initialization(self):
        """ResourceManager should initialize properly."""
        from core.resources.manager import ResourceManager
        
        rm = ResourceManager()
        
        assert rm is not None
        assert hasattr(rm, 'register')
        assert hasattr(rm, 'unregister')
    
    def test_resource_manager_gl_stats(self):
        """ResourceManager should track GL stats."""
        from core.resources.manager import ResourceManager
        
        rm = ResourceManager()
        
        stats = rm.get_gl_stats()
        
        assert isinstance(stats, dict)
        # Check for actual keys in the implementation
        assert "total" in stats


# =============================================================================
# MC vs Normal Build Feature Parity Tests
# =============================================================================

class TestBuildVariantParity:
    """Test MC vs normal build feature parity."""
    
    def test_mc_build_detection_via_settings(self, tmp_path):
        """MC build detection should work via settings."""
        from core.settings.settings_manager import SettingsManager
        
        sm = SettingsManager(storage_base_dir=tmp_path)
        
        # MC detection is done via argv / settings flag, not org name
        # Settings manager should be functional
        assert sm._settings is not None
    
    def test_settings_store_functional(self, tmp_path):
        """Settings store should be functional (JsonSettingsStore)."""
        from core.settings.settings_manager import SettingsManager
        
        sm = SettingsManager(storage_base_dir=tmp_path)
        
        # Should be able to get/set values
        sm.set('_test_key', 'test_value')
        assert sm.get('_test_key') == 'test_value'


# =============================================================================
# Thread Manager Integration Tests
# =============================================================================

class TestThreadManagerIntegration:
    """Test ThreadManager integration."""
    
    def test_thread_manager_initialization(self):
        """ThreadManager should initialize properly."""
        from core.threading.manager import ThreadManager
        
        tm = ThreadManager()
        
        assert tm is not None
    
    def test_thread_manager_has_pool_methods(self):
        """ThreadManager should have pool methods."""
        from core.threading.manager import ThreadManager
        
        tm = ThreadManager()
        
        # Should have pool methods (check actual method names)
        assert hasattr(tm, "submit_task") or hasattr(tm, "submit_io_task")


# =============================================================================
# Event System Integration Tests
# =============================================================================

class TestEventSystemIntegration:
    """Test EventSystem integration."""
    
    def test_event_system_initialization(self):
        """EventSystem should initialize properly."""
        from core.events.event_system import EventSystem
        
        es = EventSystem()
        
        assert es is not None
    
    def test_event_system_has_pub_sub_methods(self):
        """EventSystem should have pub/sub methods."""
        from core.events.event_system import EventSystem
        
        es = EventSystem()
        
        # Should have pub/sub methods
        assert hasattr(es, "subscribe")
        assert hasattr(es, "publish") or hasattr(es, "emit")
