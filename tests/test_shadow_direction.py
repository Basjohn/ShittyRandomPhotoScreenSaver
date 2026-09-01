"""E4 gates: canonical eight-direction shadow authority and its resolver.

These cross the real seams: the presentation-neutral resolver, the canonical
settings default/model round-trip, and the rule that QML consumes signed offsets
only (it never parses the direction token or reads settings).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from core.settings.defaults import CANONICAL_DEFAULTS
from core.settings.models._core import ShadowSettings
from core.settings.shadow_direction import (
    DEFAULT_SHADOW_DIRECTION,
    SHADOW_DIRECTION_SETTING_KEY,
    ShadowDirection,
    get_shadow_direction,
    resolve_shadow_direction,
    resolve_shadow_offsets,
    resolve_directional_extensions,
    resolve_signed_offset,
    shadow_direction_signs,
)


ROOT = Path(__file__).resolve().parents[1]
QML_ROOT = ROOT / "rendering" / "quick" / "qml"

_EXPECTED_SIGNS = {
    ShadowDirection.NW: (-1, -1),
    ShadowDirection.N: (0, -1),
    ShadowDirection.NE: (1, -1),
    ShadowDirection.W: (-1, 0),
    ShadowDirection.E: (1, 0),
    ShadowDirection.SW: (-1, 1),
    ShadowDirection.S: (0, 1),
    ShadowDirection.SE: (1, 1),
}


def test_all_eight_directions_map_authored_magnitude_to_signed_offsets() -> None:
    mx, my = 4.0, 6.0
    for direction, (sx, sy) in _EXPECTED_SIGNS.items():
        assert shadow_direction_signs(direction) == (sx, sy)
        assert resolve_signed_offset(direction, mx, my) == (sx * mx, sy * my)


def test_axis_only_directions_zero_the_perpendicular_axis() -> None:
    assert resolve_signed_offset(ShadowDirection.N, 4.0, 6.0) == (0.0, -6.0)
    assert resolve_signed_offset(ShadowDirection.S, 4.0, 6.0) == (0.0, 6.0)
    assert resolve_signed_offset(ShadowDirection.E, 4.0, 6.0) == (4.0, 0.0)
    assert resolve_signed_offset(ShadowDirection.W, 4.0, 6.0) == (-4.0, 0.0)


def test_default_direction_is_se() -> None:
    assert DEFAULT_SHADOW_DIRECTION is ShadowDirection.SE
    assert resolve_signed_offset(ShadowDirection.SE, 4.0, 6.0) == (4.0, 6.0)


def test_direction_owns_orientation_only_not_magnitude() -> None:
    # Magnitude is treated as magnitude regardless of incoming sign; direction
    # applies orientation. A negative authored value cannot flip the direction.
    assert resolve_signed_offset(ShadowDirection.SE, -4.0, -6.0) == (4.0, 6.0)
    assert resolve_signed_offset(ShadowDirection.NW, 4.0, 6.0) == (-4.0, -6.0)


@pytest.mark.parametrize(
    "token,expected",
    [
        ("SE", ShadowDirection.SE),
        ("nw", ShadowDirection.NW),
        ("  n  ", ShadowDirection.N),
        (ShadowDirection.W, ShadowDirection.W),
    ],
)
def test_resolve_accepts_canonical_and_case_insensitive_tokens(token, expected) -> None:
    assert resolve_shadow_direction(token) is expected


@pytest.mark.parametrize(
    "token",
    ["", "center", "middle", "diagonal", "NORTHWEST", None, 5, [], object()],
)
def test_malformed_or_unknown_token_resolves_to_default_se(token) -> None:
    assert resolve_shadow_direction(token) is ShadowDirection.SE


def test_resolve_shadow_offsets_preserves_distinct_class_magnitudes() -> None:
    # card/text/header carry distinct authored magnitudes; one direction applies
    # to all, and the per-class distinction survives resolution.
    magnitudes = {
        "card": (4.0, 6.0),
        "text": (3.0, 3.0),
        "header": (2.0, 2.0),
    }
    resolved = resolve_shadow_offsets(ShadowDirection.NW, magnitudes)
    assert resolved == {
        "card": (-4.0, -6.0),
        "text": (-3.0, -3.0),
        "header": (-2.0, -2.0),
    }
    # Distinct magnitudes stay distinct.
    assert len({resolved["card"], resolved["text"], resolved["header"]}) == 3


def test_get_shadow_direction_reads_canonical_key_with_default_fallback() -> None:
    class _Settings:
        def __init__(self, store):
            self._store = store

        def get(self, key, default=None):
            return self._store.get(key, default)

    assert get_shadow_direction(_Settings({SHADOW_DIRECTION_SETTING_KEY: "NW"})) is (
        ShadowDirection.NW
    )
    # Missing key -> canonical default.
    assert get_shadow_direction(_Settings({})) is ShadowDirection.SE
    # Malformed stored token -> canonical default.
    assert get_shadow_direction(_Settings({SHADOW_DIRECTION_SETTING_KEY: "??"})) is (
        ShadowDirection.SE
    )
    # Non-settings object -> canonical default.
    assert get_shadow_direction(object()) is ShadowDirection.SE


def test_shadow_settings_model_round_trips_direction() -> None:
    assert ShadowSettings().direction == "SE"
    assert ShadowSettings().to_dict()[SHADOW_DIRECTION_SETTING_KEY] == "SE"

    class _Settings:
        def get(self, key, default=None):
            return "NW" if key == SHADOW_DIRECTION_SETTING_KEY else default

    loaded = ShadowSettings.from_settings(_Settings())
    assert loaded.direction == "NW"
    assert loaded.to_dict()[SHADOW_DIRECTION_SETTING_KEY] == "NW"


def test_canonical_defaults_expose_direction_se() -> None:
    assert CANONICAL_DEFAULTS["widgets"]["shadows"]["direction"] == "SE"


def _qml_code_without_comments(path: Path) -> str:
    lines = []
    for line in path.read_text(encoding="utf-8").splitlines():
        marker = line.find("//")
        lines.append(line if marker < 0 else line[:marker])
    return "\n".join(lines)


def test_direction_authority_is_not_duplicated_in_qml() -> None:
    # QML consumes signed offsets only. The primitives must not parse the token,
    # read settings, or map the direction themselves. Scan code only so comments
    # that reference the concept do not trip the check.
    for filename in ("OverlayWidget.qml", "OverlayCard.qml", "ShadowedText.qml", "Separator.qml"):
        lowered = _qml_code_without_comments(QML_ROOT / filename).lower()
        assert "direction" not in lowered, filename
        assert "shadowdirection" not in lowered, filename
        assert "settingsmanager" not in lowered, filename
        assert "widgets.shadows" not in lowered, filename


def test_directional_extensions_grow_only_selected_far_edges() -> None:
    assert resolve_directional_extensions("SE", 6) == (0.0, 0.0, 6.0, 6.0)
    assert resolve_directional_extensions("NW", 6) == (6.0, 6.0, 0.0, 0.0)
    assert resolve_directional_extensions("E", 6) == (0.0, 0.0, 6.0, 0.0)
    assert resolve_directional_extensions("N", 6) == (0.0, 6.0, 0.0, 0.0)
    assert resolve_directional_extensions("SE", -4) == (0.0, 0.0, 0.0, 0.0)
