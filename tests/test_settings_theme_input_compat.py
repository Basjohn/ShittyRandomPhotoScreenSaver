from __future__ import annotations

import json
from pathlib import Path

import pytest

from ui.settings_theme_input_compat import (
    ABOUT_ART_LIQUID_TOKEN,
    LEGACY_SETTINGS_THEME_SCHEMA_VERSION,
    LegacySettingsThemeInputError,
    promote_legacy_settings_theme_payload,
)
from ui.settings_theme_io import (
    SettingsThemeFileError,
    settings_theme_from_json,
    settings_theme_from_payload,
    settings_theme_to_payload,
)
from ui.settings_theme_spec import (
    DEFAULT_DARK_SETTINGS_THEME,
    Rgba,
    SETTINGS_THEME_SCHEMA_VERSION,
)


_FIXTURE = Path(__file__).parent / "fixtures" / "settings_theme_v5_user_theme.srtheme"


def _fixture_payload() -> dict[str, object]:
    return json.loads(_FIXTURE.read_text(encoding="utf-8"))


def test_v5_fixture_is_distinguishing_historical_user_input() -> None:
    payload = _fixture_payload()
    assert payload["schema_version"] == LEGACY_SETTINGS_THEME_SCHEMA_VERSION
    assert ABOUT_ART_LIQUID_TOKEN not in payload["colors"]
    assert payload["colors"]["chrome.outer_border"] == [12, 34, 56, 180]


def test_v5_promotion_adds_only_current_liquid_role_and_schema() -> None:
    payload = _fixture_payload()
    original = json.loads(json.dumps(payload))

    promoted, changed = promote_legacy_settings_theme_payload(payload)

    assert changed is True
    assert payload == original
    assert promoted["schema_version"] == SETTINGS_THEME_SCHEMA_VERSION
    assert promoted["colors"][ABOUT_ART_LIQUID_TOKEN] == [12, 34, 56, 255]

    expected = json.loads(json.dumps(original))
    expected["schema_version"] = SETTINGS_THEME_SCHEMA_VERSION
    expected["colors"][ABOUT_ART_LIQUID_TOKEN] = [12, 34, 56, 255]
    assert promoted == expected


def test_v5_promotion_is_idempotent_after_first_boundary_pass() -> None:
    promoted, changed = promote_legacy_settings_theme_payload(_fixture_payload())
    second, changed_again = promote_legacy_settings_theme_payload(promoted)

    assert changed is True
    assert changed_again is False
    assert second == promoted


def test_strict_file_input_accepts_v5_via_boundary_and_returns_current_spec() -> None:
    theme = settings_theme_from_json(_FIXTURE.read_text(encoding="utf-8"))

    assert theme.schema_version == SETTINGS_THEME_SCHEMA_VERSION
    assert theme.name == "Legacy V5 Ocean Ink"
    assert theme.color(ABOUT_ART_LIQUID_TOKEN) == Rgba(12, 34, 56, 255)
    assert theme.color("chrome.outer_border") == Rgba(12, 34, 56, 180)


def test_v5_compatibility_does_not_default_merge_incomplete_old_theme() -> None:
    payload = _fixture_payload()
    payload["colors"].pop("window.dialog_glass")

    with pytest.raises(LegacySettingsThemeInputError, match="missing semantic roles"):
        promote_legacy_settings_theme_payload(payload)
    with pytest.raises(SettingsThemeFileError, match="missing semantic roles"):
        settings_theme_from_payload(payload)


def test_current_v6_payload_bypasses_compatibility_unchanged() -> None:
    payload = settings_theme_to_payload(DEFAULT_DARK_SETTINGS_THEME)
    promoted, changed = promote_legacy_settings_theme_payload(payload)

    assert changed is False
    assert promoted is payload
    assert settings_theme_from_payload(payload) == DEFAULT_DARK_SETTINGS_THEME


def test_current_io_has_no_embedded_v5_transform_owner() -> None:
    io_source = Path("ui/settings_theme_io.py").read_text(encoding="utf-8")
    compat_source = Path("ui/settings_theme_input_compat.py").read_text(encoding="utf-8")

    assert "_PREVIOUS_SETTINGS_THEME_SCHEMA_VERSION" not in io_source
    assert "migrated_liquid" not in io_source
    assert "LEGACY_SETTINGS_THEME_SCHEMA_VERSION = 5" in compat_source
    assert "chrome.outer_border" in compat_source
