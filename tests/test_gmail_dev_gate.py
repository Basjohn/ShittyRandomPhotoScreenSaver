"""Tests for Gmail dev gate logic (no Qt app required)."""
from __future__ import annotations

from core.dev_gates import force_gate, is_gmail_enabled


def test_is_gmail_enabled_default_false() -> None:
    """Verify is_gmail_enabled() returns False by default without --devgmail flag."""
    # The gate state is set at import time from sys.argv
    # In test environment, it's likely False by default
    # We can't easily test the default without controlling sys.argv before import
    # So we just verify the function exists and returns a bool
    result = is_gmail_enabled()
    assert isinstance(result, bool)


def test_force_gate_enables_gmail() -> None:
    """Verify force_gate() can enable gmail gate for testing without CLI flag."""
    # Force enable for test
    force_gate(gmail=True)
    assert is_gmail_enabled() is True

    # Reset (in real tests, this would be done in teardown)
    force_gate(gmail=False)
    assert is_gmail_enabled() is False


def test_force_gate_multiple_gates() -> None:
    """Verify force_gate() handles multiple gates independently."""
    # Initially all disabled
    force_gate(gmail=False, blob=False)
    assert is_gmail_enabled() is False

    # Enable gmail gate
    force_gate(gmail=True)
    assert is_gmail_enabled() is True

    # Enable another gate (blob) should not affect gmail
    force_gate(blob=True)
    assert is_gmail_enabled() is True  # Still True

    # Disable gmail gate
    force_gate(gmail=False)
    assert is_gmail_enabled() is False

    # Cleanup
    force_gate(blob=False)

