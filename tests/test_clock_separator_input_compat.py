from __future__ import annotations

import json
from pathlib import Path

from core.settings.sst_io import _normalize_widgets_mapping
from core.settings.widget_input_compat import promote_legacy_clock_separator


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "clock_separator_legacy_profile.json"


def _legacy_widgets() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))["widgets"]


def test_legacy_clock_separator_promotes_before_default_can_mask_false() -> None:
    widgets = _legacy_widgets()

    promoted, changed = promote_legacy_clock_separator(widgets)

    assert changed is True
    assert promoted == {
        "clock": {
            "enabled": True,
            "show_separator": False,
            "separator_thickness": 3,
            "timezone": "local",
        },
        "clock2": {"enabled": True, "timezone": "UTC"},
    }
    assert "show_digital_separator" in widgets["clock"]  # non-mutating input boundary


def test_current_clock_separator_wins_over_retired_key() -> None:
    promoted, changed = promote_legacy_clock_separator(
        {
            "clock": {
                "show_separator": False,
                "show_digital_separator": True,
                "separator_thickness": 5,
            }
        }
    )

    assert changed is True
    assert promoted["clock"]["show_separator"] is False
    assert promoted["clock"]["separator_thickness"] == 5
    assert "show_digital_separator" not in promoted["clock"]


def test_clock_separator_promotion_is_idempotent() -> None:
    first, first_changed = promote_legacy_clock_separator(_legacy_widgets())
    second, second_changed = promote_legacy_clock_separator(first)

    assert first_changed is True
    assert second_changed is False
    assert second == first


def test_current_widgets_shape_is_a_noop() -> None:
    current = {
        "clock": {"show_separator": True, "separator_thickness": 4},
        "media": {"enabled": True},
    }
    promoted, changed = promote_legacy_clock_separator(current)

    assert changed is False
    assert promoted == current
    assert promoted is not current


def test_runtime_and_settings_ui_no_longer_read_retired_clock_key() -> None:
    presentation = (ROOT / "rendering" / "quick" / "widgets" / "clock.py").read_text(
        encoding="utf-8"
    )
    settings_ui = (ROOT / "ui" / "tabs" / "widgets_tab_clock.py").read_text(
        encoding="utf-8"
    )

    assert "show_digital_separator" not in presentation
    assert "show_digital_separator" not in settings_ui


def test_startup_promotes_clock_separator_before_default_merge() -> None:
    manager_source = (ROOT / "core" / "settings" / "settings_manager.py").read_text(
        encoding="utf-8"
    )

    migration_call = "self._migrate_legacy_clock_separator_before_defaults()"
    defaults_call = "self._set_defaults()"
    assert migration_call in manager_source
    assert manager_source.index(migration_call) < manager_source.index(defaults_call)


def test_sst_import_uses_same_clock_separator_promotion_boundary() -> None:
    normalized = _normalize_widgets_mapping(
        {"clock": {"show_digital_separator": False, "separator_thickness": 2}}
    )

    assert normalized["clock"] == {"show_separator": False, "separator_thickness": 2}
