from __future__ import annotations

import json
from pathlib import Path

from core.settings.legacy_setting_aliases import (
    LEGACY_DOTTED_SETTING_ALIASES,
    promote_legacy_section_aliases,
)
from core.settings.sst_io import _project_import_state, normalize_sst_snapshot


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "settings_legacy_hard_exit_profile.json"


class _FakeStore:
    def allKeys(self):
        return []

    def value(self, key):
        raise AssertionError(f"unexpected store read for {key}")


class _FakeManager:
    _settings = _FakeStore()

    @staticmethod
    def _coerce_import_value(key, value):
        return value

    @staticmethod
    def _canonicalize_key(key):
        return str(key)


def test_alias_registry_is_narrow_and_explicit() -> None:
    assert LEGACY_DOTTED_SETTING_ALIASES == {
        "input.hard_exit": "input.interaction_mode",
    }


def test_nested_sst_legacy_alias_promotes_to_current_key() -> None:
    projected = _project_import_state(
        _FakeManager(),
        {"input": {"hard_exit": True}},
        merge=True,
    )
    assert projected == {"input.interaction_mode": True}




def test_flat_sst_alias_reaches_same_current_projection() -> None:
    normalized = normalize_sst_snapshot({"input.hard_exit": True})
    projected = _project_import_state(_FakeManager(), normalized, merge=True)
    assert projected == {"input.interaction_mode": True}

def test_nested_sst_current_key_wins_when_both_are_present() -> None:
    projected = _project_import_state(
        _FakeManager(),
        {"input": {"hard_exit": True, "interaction_mode": False}},
        merge=True,
    )
    assert projected == {"input.interaction_mode": False}


def test_section_alias_promotion_is_idempotent() -> None:
    first, changed = promote_legacy_section_aliases("input", {"hard_exit": True})
    second, changed_again = promote_legacy_section_aliases("input", first)
    assert changed is True
    assert changed_again is False
    assert first == second == {"interaction_mode": True}


def test_fixture_uses_distinguishing_retired_profile_key() -> None:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert payload == {
        "input.hard_exit": True,
        "display.image_interval": 47,
    }
    assert "input.interaction_mode" not in payload


def test_runtime_api_no_longer_maps_retired_alias() -> None:
    source = (ROOT / "core" / "settings" / "settings_manager.py").read_text(
        encoding="utf-8"
    )
    canonicalizer = source[source.index("def _canonicalize_key"):source.index("def _migrate_legacy_setting_aliases")]
    assert "if is_legacy_setting_alias(text):" in canonicalizer
    assert "raise KeyError" in canonicalizer
    assert "return text" in canonicalizer
