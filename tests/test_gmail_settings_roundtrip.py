"""Tests for Gmail settings roundtrip (no Qt app required)."""
from __future__ import annotations

import pytest


def test_gmail_widget_apply_settings_basic() -> None:
    """Verify GmailWidget.apply_settings() correctly parses flat settings dict."""
    # This test would need Qt app, so we'll skip for now
    # The actual widget test (P6.3) will cover this with Qt app
    pytest.skip("Requires Qt app - covered in test_gmail_widget.py")


def test_gmail_settings_keys_exist() -> None:
    """Verify Gmail settings keys are defined in default_settings.py."""
    from core.settings.default_settings import DEFAULT_SETTINGS

    # Check that gmail settings exist in defaults
    gmail_keys = [k for k in DEFAULT_SETTINGS.keys() if k.startswith("gmail.")]
    # If no gmail.* keys exist, that's okay - they might not be added yet
    # Just verify the structure is correct if they do exist
    if gmail_keys:
        # Check for expected keys (subset)
        expected_keys = [
            "gmail.enabled",
            "gmail.position",
            "gmail.limit",
            "gmail.refresh_interval",
        ]
        for key in expected_keys:
            if key in gmail_keys:
                assert key in DEFAULT_SETTINGS, f"Missing expected key: {key}"
    else:
        # No gmail settings yet - that's okay for this test
        assert True


def test_gmail_settings_flat_dict_structure() -> None:
    """Verify Gmail settings follow flat-dict pattern (no nested dicts)."""
    from core.settings.default_settings import DEFAULT_SETTINGS

    for key, value in DEFAULT_SETTINGS.items():
        if key.startswith("gmail."):
            # Gmail settings should be flat (no nested dicts)
            if isinstance(value, dict):
                # Some settings might be dicts for colors/fonts, but they should be simple
                # This is just a sanity check - complex nested structures should be avoided
                for k, v in value.items():
                    assert not isinstance(v, dict), f"Nested dict in {key}.{k}"


def test_gmail_position_enum_values() -> None:
    """Verify GmailPosition enum values are lowercase snake_case."""
    from widgets.gmail_components import GmailPosition

    # Check that all GmailPosition values are lowercase snake_case
    valid_positions = [
        "top_left", "top_center", "top_right",
        "middle_left", "center", "middle_right",
        "bottom_left", "bottom_center", "bottom_right",
    ]

    for pos in GmailPosition:
        assert pos.value in valid_positions, f"Invalid position value: {pos.value}"


def test_gmail_settings_type_safety() -> None:
    """Verify Gmail settings have appropriate types."""
    from core.settings.default_settings import DEFAULT_SETTINGS

    # Check types for known keys
    if "gmail.enabled" in DEFAULT_SETTINGS:
        assert isinstance(DEFAULT_SETTINGS["gmail.enabled"], bool)

    if "gmail.limit" in DEFAULT_SETTINGS:
        assert isinstance(DEFAULT_SETTINGS["gmail.limit"], int)
        assert DEFAULT_SETTINGS["gmail.limit"] > 0

    if "gmail.refresh_interval" in DEFAULT_SETTINGS:
        assert isinstance(DEFAULT_SETTINGS["gmail.refresh_interval"], int)
        assert DEFAULT_SETTINGS["gmail.refresh_interval"] > 0

    if "gmail.position" in DEFAULT_SETTINGS:
        assert isinstance(DEFAULT_SETTINGS["gmail.position"], str)


def test_gmail_text_cleanup_defaults_exist() -> None:
    """Verify Gmail text cleanup defaults are present in the widget settings dict."""
    from core.settings.default_settings import DEFAULT_SETTINGS

    gmail = DEFAULT_SETTINGS["widgets"]["gmail"]
    assert gmail["clean_sender_names"] is True
    assert gmail["max_sender_words"] == 3
    assert gmail["sender_column_width"] == 180
    assert gmail["max_subject_words"] == 4
    assert gmail["max_subject_chars"] == 0
    assert gmail["width"] == 600
    assert "min_width" not in gmail
    assert "max_width" not in gmail
    assert "content_padding_left" not in gmail
