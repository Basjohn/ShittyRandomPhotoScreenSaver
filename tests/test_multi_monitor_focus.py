"""Tests for multi-monitor focus coordination."""
import pytest
from unittest.mock import MagicMock, PropertyMock
from PySide6.QtCore import QRect

from rendering.multi_monitor_coordinator import MultiMonitorCoordinator


@pytest.fixture
def coordinator():
    """Create a fresh coordinator for each test."""
    MultiMonitorCoordinator.reset()
    coord = MultiMonitorCoordinator.instance()
    yield coord
    MultiMonitorCoordinator.reset()


def _make_mock_display(screen_index: int, visible: bool = True, screen_valid: bool = True):
    """Create a mock DisplayWidget for testing."""
    mock = MagicMock()
    mock.screen_index = screen_index
    mock.isVisible.return_value = visible
    
    if screen_valid:
        mock_screen = MagicMock()
        mock_screen.geometry.return_value = QRect(0, 0, 1920, 1080)
        mock._screen = mock_screen
    else:
        mock._screen = None
    
    return mock


def test_first_display_claims_focus(coordinator):
    """Test that first display to call claim_focus gets it."""
    display1 = _make_mock_display(0)
    
    assert coordinator.claim_focus(display1) is True
    assert coordinator.focus_owner is display1


def test_second_display_cannot_claim_focus_normally(coordinator):
    """Test that second display cannot claim focus when first has it."""
    display1 = _make_mock_display(0)
    display2 = _make_mock_display(1)
    
    assert coordinator.claim_focus(display1) is True
    assert coordinator.claim_focus(display2) is False
    assert coordinator.focus_owner is display1


def test_display_can_reclaim_own_focus(coordinator):
    """Test that a display can re-claim its own focus."""
    display1 = _make_mock_display(0)
    
    assert coordinator.claim_focus(display1) is True
    assert coordinator.claim_focus(display1) is True  # Should still return True
    assert coordinator.focus_owner is display1


def test_focus_reclaimed_when_owner_not_visible(coordinator):
    """Test that focus can be reclaimed when current owner is not visible."""
    display1 = _make_mock_display(0, visible=False)
    display2 = _make_mock_display(1, visible=True)
    
    # Display 1 claims focus first
    assert coordinator.claim_focus(display1) is True
    
    # Display 2 should be able to reclaim because display 1 is not visible
    assert coordinator.claim_focus(display2) is True
    assert coordinator.focus_owner is display2


def test_focus_reclaimed_when_owner_screen_unavailable(coordinator):
    """Test that focus can be reclaimed when current owner's screen is unavailable.
    
    This is the key fix for MC mode - when display 1's monitor is off,
    display 2 should be able to claim focus.
    """
    display1 = _make_mock_display(0, visible=True, screen_valid=False)
    display2 = _make_mock_display(1, visible=True, screen_valid=True)
    
    # Display 1 claims focus first but has no valid screen
    assert coordinator.claim_focus(display1) is True
    
    # Display 2 should be able to reclaim because display 1 has no screen
    assert coordinator.claim_focus(display2) is True
    assert coordinator.focus_owner is display2


def test_focus_reclaimed_when_owner_screen_has_invalid_geometry(coordinator):
    """Test that focus can be reclaimed when owner's screen has invalid geometry."""
    display1 = _make_mock_display(0, visible=True)
    # Make display1's screen return invalid geometry
    display1._screen.geometry.return_value = QRect()  # Empty/invalid rect
    
    display2 = _make_mock_display(1, visible=True)
    
    # Display 1 claims focus first
    assert coordinator.claim_focus(display1) is True
    
    # Display 2 should be able to reclaim because display 1 has invalid geometry
    assert coordinator.claim_focus(display2) is True
    assert coordinator.focus_owner is display2


def test_release_focus(coordinator):
    """Test that focus can be released."""
    display1 = _make_mock_display(0)
    display2 = _make_mock_display(1)
    
    coordinator.claim_focus(display1)
    assert coordinator.focus_owner is display1
    
    coordinator.release_focus(display1)
    assert coordinator.focus_owner is None
    
    # Now display 2 can claim
    assert coordinator.claim_focus(display2) is True
    assert coordinator.focus_owner is display2


def test_release_focus_only_affects_owner(coordinator):
    """Test that release_focus only works for the actual owner."""
    display1 = _make_mock_display(0)
    display2 = _make_mock_display(1)
    
    coordinator.claim_focus(display1)
    
    # Display 2 trying to release should have no effect
    coordinator.release_focus(display2)
    assert coordinator.focus_owner is display1


def test_is_focus_owner(coordinator):
    """Test is_focus_owner method."""
    display1 = _make_mock_display(0)
    display2 = _make_mock_display(1)
    
    coordinator.claim_focus(display1)
    
    assert coordinator.is_focus_owner(display1) is True
    assert coordinator.is_focus_owner(display2) is False
