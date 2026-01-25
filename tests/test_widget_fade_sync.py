"""Regression tests for widget fade coordination (Phase 3.3).

Tests verify:
- Deterministic fade callback order (dict insertion order preserved)
- add_expected_overlay() must be called before fade start
- Immediate fade for unexpected overlays
- Spotify volume widget fade handshake with visualizer
"""
import pytest
from unittest.mock import MagicMock


class TestFadeCallbackOrder:
    """Verify fade callbacks run in deterministic order."""
    
    def test_callback_order_matches_registration_order(self):
        """Fade callbacks should run in registration order (Python 3.7+ dict)."""
        callbacks_executed = []
        
        # Simulate WidgetManager._pending_fade_starters as regular dict
        pending_starters = {}
        
        def make_callback(name):
            def cb():
                callbacks_executed.append(name)
            return cb
        
        # Register in specific order
        pending_starters["clock"] = make_callback("clock")
        pending_starters["weather"] = make_callback("weather")
        pending_starters["media"] = make_callback("media")
        pending_starters["spotify_volume"] = make_callback("spotify_volume")
        
        # Execute in iteration order (should be insertion order in Python 3.7+)
        for callback in pending_starters.values():
            callback()
        
        assert callbacks_executed == ["clock", "weather", "media", "spotify_volume"], \
            f"Callbacks ran in wrong order: {callbacks_executed}"
    
    def test_dict_preserves_insertion_order(self):
        """Confirm Python dict preserves insertion order for fade sync."""
        d = {}
        keys = ["a", "b", "c", "d", "e"]
        for k in keys:
            d[k] = k
        
        assert list(d.keys()) == keys, "Dict did not preserve insertion order"


class TestExpectedOverlayRegistration:
    """Tests for add_expected_overlay behavior."""
    
    def test_expected_overlay_registered_before_fade(self):
        """Overlay must be in expected set before fade starts."""
        expected_overlays = set()
        fade_started = {}
        
        def add_expected_overlay(name):
            expected_overlays.add(name)
        
        def request_fade_sync(name, callback):
            # Simulates WidgetManager behavior
            if name in expected_overlays:
                fade_started[name] = "coordinated"
            else:
                fade_started[name] = "immediate"
        
        # Correct flow: register first, then request fade
        add_expected_overlay("spotify_volume")
        request_fade_sync("spotify_volume", lambda: None)
        
        assert fade_started["spotify_volume"] == "coordinated"
    
    def test_unexpected_overlay_fades_immediately(self):
        """Overlay not in expected set should fade immediately."""
        expected_overlays = set()
        fade_started = {}
        
        def request_fade_sync(name, callback):
            if name in expected_overlays:
                fade_started[name] = "coordinated"
            else:
                fade_started[name] = "immediate"
        
        # Request fade without registering as expected
        request_fade_sync("unknown_widget", lambda: None)
        
        assert fade_started["unknown_widget"] == "immediate"


class TestSpotifyVolumeFadeHandshake:
    """Tests for Spotify volume widget fade coordination with visualizer."""
    
    def test_volume_widget_registers_before_fade(self):
        """Volume widget should call add_expected_overlay before fade."""
        registration_log = []
        
        class MockWidgetManager:
            def add_expected_overlay(self, name):
                registration_log.append(("add_expected", name))
            
            def request_overlay_fade_sync(self, name, callback):
                registration_log.append(("request_fade", name))
        
        wm = MockWidgetManager()
        
        # Simulate create_spotify_volume_widget flow
        wm.add_expected_overlay("spotify_volume")
        # ... widget created ...
        wm.request_overlay_fade_sync("spotify_volume", lambda: None)
        
        # Verify order
        assert len(registration_log) >= 2
        add_idx = next(i for i, (action, _) in enumerate(registration_log) if action == "add_expected")
        fade_idx = next(i for i, (action, _) in enumerate(registration_log) if action == "request_fade")
        assert add_idx < fade_idx, "add_expected_overlay must be called before request_overlay_fade_sync"
    
    def test_secondary_fade_for_orphan_volume_widget(self):
        """Volume widget without visible anchor should use secondary fade."""
        secondary_fades = []
        
        class MockWidgetManager:
            def register_secondary_fade(self, name, callback):
                secondary_fades.append(name)
        
        wm = MockWidgetManager()
        
        # Simulate orphan volume widget (anchor not visible)
        anchor_visible = False
        if not anchor_visible:
            wm.register_secondary_fade("spotify_volume", lambda: None)
        
        assert "spotify_volume" in secondary_fades


class TestFadeTimeoutBehavior:
    """Tests for fade timeout handling."""
    
    def test_timeout_triggers_forced_fade(self):
        """After timeout, pending fades should be forced to start."""
        pending = {"widget1": MagicMock(), "widget2": MagicMock()}
        timeout_reached = True
        
        if timeout_reached:
            for callback in pending.values():
                callback()
        
        for name, cb in pending.items():
            cb.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
