"""
Tests for MediaKeyLLHook low-level keyboard hook.

These tests verify:
1. Hook can be started and stopped
2. Media keys are detected correctly
3. Hook passes through all keys (anti-cheat safety)
4. Zero performance impact when disabled
5. Thread safety
"""
import pytest
import threading
import time
from unittest.mock import Mock, patch

from PySide6.QtCore import QCoreApplication

from core.windows.media_key_ll_hook import (
    MediaKeyLLHook,
    MEDIA_KEY_CODES,
    VK_MEDIA_PLAY_PAUSE,
    VK_VOLUME_UP,
    VK_VOLUME_DOWN,
)


class TestMediaKeyLLHook:
    """Test suite for MediaKeyLLHook."""
    
    @pytest.fixture
    def app(self):
        """Create Qt application for signal testing."""
        app = QCoreApplication.instance()
        if app is None:
            app = QCoreApplication([])
        return app
    
    @pytest.fixture
    def hook(self, app):
        """Create a MediaKeyLLHook instance."""
        hook = MediaKeyLLHook()
        yield hook
        # Cleanup
        hook.stop()
    
    def test_initial_state(self, hook):
        """Test that hook is not running initially."""
        assert not hook.is_running()
        assert hook._hHook is None
        assert hook._hook_thread is None
    
    def test_start_stop_cycle(self, hook):
        """Test that hook can be started and stopped."""
        # Mock SetWindowsHookExW to simulate successful installation
        with patch.object(hook._user32, 'SetWindowsHookExW', return_value=12345):
            # Start hook
            result = hook.start()
            assert result is True
            time.sleep(0.2)  # Let thread initialize
            assert hook.is_running()
            assert hook._hook_thread is not None
            assert hook._hook_thread.is_alive()
            
            # Stop hook
            hook.stop()
            assert not hook.is_running()
            assert hook._hHook is None
    
    def test_double_start(self, hook):
        """Test that starting an already running hook returns True."""
        hook.start()
        result = hook.start()  # Should return True (already running)
        assert result is True
        hook.stop()
    
    def test_stop_when_not_running(self, hook):
        """Test that stopping a non-running hook doesn't error."""
        hook.stop()  # Should not raise
        assert not hook.is_running()
    
    def test_media_key_detection(self, hook, app):
        """Test that media keys are detected and signal emitted."""
        # Mock the signal
        mock_slot = Mock()
        hook.media_key_detected.connect(mock_slot)
        
        # Start hook
        hook.start()
        time.sleep(0.1)  # Let hook initialize
        
        # Simulate media key press via callback
        # Create mock LPARAM pointing to KBDLLHOOKSTRUCT
        class MockKBD:
            def __init__(self, vk_code):
                self.vkCode = vk_code
                
        mock_lparam = MockKBD(VK_MEDIA_PLAY_PAUSE)
        
        # Call callback directly (simulating Windows calling it)
        result = hook._hook_callback(0, 0x0100, mock_lparam)
        
        # Process events to allow signal to be emitted
        app.processEvents()
        time.sleep(0.1)
        app.processEvents()
        
        # Signal should have been emitted
        mock_slot.assert_called_once()
        args = mock_slot.call_args[0]
        assert args[0] == VK_MEDIA_PLAY_PAUSE
        assert args[1] == "play_pause"
        
        hook.stop()
    
    def test_non_media_key_ignored(self, hook, app):
        """Test that non-media keys don't emit signal."""
        mock_slot = Mock()
        hook.media_key_detected.connect(mock_slot)
        
        hook.start()
        time.sleep(0.1)
        
        # Simulate regular key (not media key)
        class MockKBD:
            def __init__(self, vk_code):
                self.vkCode = vk_code
                
        mock_lparam = MockKBD(0x41)  # 'A' key
        
        hook._hook_callback(0, 0x0100, mock_lparam)
        app.processEvents()
        
        # Signal should NOT have been emitted
        mock_slot.assert_not_called()
        
        hook.stop()
    
    def test_callback_always_calls_next_hook(self, hook):
        """Test that callback always calls CallNextHookEx (anti-cheat safety)."""
        # Manually set hHook to simulate installed hook
        hook._hHook = 12345  # Fake handle
        
        with patch.object(hook._user32, 'CallNextHookEx') as mock_call_next:
            mock_call_next.return_value = 0
            
            # Simulate any key press
            class MockKBD:
                def __init__(self, vk_code):
                    self.vkCode = vk_code
                    
            mock_lparam = MockKBD(VK_MEDIA_PLAY_PAUSE)
            
            hook._hook_callback(0, 0x0100, mock_lparam)
            
            # CallNextHookEx MUST be called
            mock_call_next.assert_called_once()
        
        hook._hHook = None  # Cleanup
    
    def test_all_media_keys_recognized(self, hook, app):
        """Test that all defined media keys are recognized."""
        mock_slot = Mock()
        hook.media_key_detected.connect(mock_slot)
        
        hook.start()
        time.sleep(0.1)
        
        # Test each media key
        class MockKBD:
            def __init__(self, vk_code):
                self.vkCode = vk_code
        
        detected_keys = set()
        for vk_code in MEDIA_KEY_CODES:
            mock_lparam = MockKBD(vk_code)
            hook._hook_callback(0, 0x0100, mock_lparam)
            app.processEvents()
            
            if mock_slot.called:
                detected_keys.add(vk_code)
                mock_slot.reset_mock()
        
        # All media keys should be detected
        assert detected_keys == MEDIA_KEY_CODES
        
        hook.stop()
    
    def test_key_name_mapping(self):
        """Test that all media keys have proper names."""
        for vk_code in MEDIA_KEY_CODES:
            assert vk_code in MediaKeyLLHook.KEY_NAMES, f"VK code 0x{vk_code:02X} missing name"
            name = MediaKeyLLHook.KEY_NAMES[vk_code]
            assert isinstance(name, str)
            assert len(name) > 0
    
    def test_thread_safety(self, hook):
        """Test that hook operations are thread-safe."""
        errors = []
        
        def start_stop_cycle():
            try:
                for _ in range(5):
                    hook.start()
                    time.sleep(0.05)
                    hook.stop()
                    time.sleep(0.05)
            except Exception as e:
                errors.append(e)
        
        # Run from multiple threads
        threads = []
        for _ in range(3):
            t = threading.Thread(target=start_stop_cycle)
            threads.append(t)
            t.start()
        
        for t in threads:
            t.join(timeout=10.0)
        
        # No errors should have occurred
        assert len(errors) == 0, f"Thread safety errors: {errors}"
    
    def test_zero_performance_when_disabled(self):
        """Test that disabled hook has zero performance impact."""
        # Create hook but don't start it
        hook = MediaKeyLLHook()
        
        # Verify no thread, no hook handle
        assert hook._hook_thread is None
        assert hook._hHook is None
        assert not hook.is_running()
        
        # No resources should be allocated
        # This test documents the "zero performance" guarantee
    
    def test_cleanup_on_stop(self, hook):
        """Test that stop() properly cleans up all resources."""
        with patch.object(hook._user32, 'SetWindowsHookExW', return_value=12345):
            hook.start()
            time.sleep(0.2)
            
            assert hook.is_running()
            assert hook._hook_thread is not None
            
            hook.stop()
            
            # All resources should be released
            assert not hook.is_running()
            assert hook._hHook is None
            # Thread may still exist but should not be alive
            if hook._hook_thread:
                assert not hook._hook_thread.is_alive()


class TestMediaKeyConstants:
    """Test media key constants."""
    
    def test_media_key_codes_defined(self):
        """Test that all expected media key codes are defined."""
        expected_codes = {
            0xAD,  # VK_VOLUME_MUTE
            0xAE,  # VK_VOLUME_DOWN
            0xAF,  # VK_VOLUME_UP
            0xB0,  # VK_MEDIA_NEXT_TRACK
            0xB1,  # VK_MEDIA_PREV_TRACK
            0xB2,  # VK_MEDIA_STOP
            0xB3,  # VK_MEDIA_PLAY_PAUSE
        }
        assert MEDIA_KEY_CODES == expected_codes
    
    def test_windows_constants_defined(self):
        """Test Windows constants are correct."""
        from core.windows.media_key_ll_hook import (
            WH_KEYBOARD_LL,
            WM_KEYDOWN,
            PM_REMOVE,
        )
        assert WH_KEYBOARD_LL == 13
        assert WM_KEYDOWN == 0x0100
        assert PM_REMOVE == 0x0001


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
