"""Clock per-display mode persistence must select matching CUSTOM geometry."""
from __future__ import annotations

from PySide6.QtCore import QRect

from rendering.custom_layout_contract import get_screen_signature
from rendering.quick.custom_layout_hydration import (
    resolve_quick_committed_geometry,
    resolve_quick_committed_variant_state,
)


class _FakeScreen:
    def __init__(self, serial: str) -> None:
        self._serial = serial
        self._geometry = QRect(0, 0, 1000, 800)

    def serialNumber(self) -> str:
        return self._serial

    def manufacturer(self) -> str:
        return ""

    def model(self) -> str:
        return ""

    def name(self) -> str:
        return ""

    def geometry(self) -> QRect:
        return QRect(self._geometry)


def _entry(x: float, y: float, width: float, height: float) -> dict[str, object]:
    return {
        "rect": {"x": x, "y": y, "width": width, "height": height},
        "size_payload": {},
        "resize_mode": "clock_font",
    }


def test_per_display_analog_override_rehydrates_analog_custom_rect() -> None:
    screen = _FakeScreen("A")
    signature = get_screen_signature(screen)
    widgets = {
        "clock": {
            "position": "Custom",
            "display_mode": "digital",
            "display_mode_overrides": {signature: "analog"},
        },
        "custom_layout": {
            "version": 2,
            "displays": {
                signature: {
                    "clock": {
                        "digital": _entry(0.55, 0.10, 0.20, 0.15),
                        "analog": _entry(0.10, 0.25, 0.30, 0.40),
                    }
                }
            },
        },
    }

    geometry = resolve_quick_committed_geometry(widgets, screen, "clock")

    assert geometry is not None
    assert (geometry.x, geometry.y, geometry.width, geometry.height) == (
        100.0,
        200.0,
        300.0,
        320.0,
    )


def test_other_display_without_override_keeps_baseline_digital_variant() -> None:
    screen = _FakeScreen("B")
    signature = get_screen_signature(screen)
    widgets = {
        "clock": {
            "position": "Custom",
            "display_mode": "digital",
            "display_mode_overrides": {"serial:A": "analog"},
        },
        "custom_layout": {
            "version": 2,
            "displays": {
                signature: {
                    "clock": {
                        "digital": _entry(0.50, 0.20, 0.25, 0.20),
                        "analog": _entry(0.05, 0.10, 0.40, 0.45),
                    }
                }
            },
        },
    }

    geometry = resolve_quick_committed_geometry(widgets, screen, "clock")

    assert geometry is not None
    assert (geometry.x, geometry.y, geometry.width, geometry.height) == (
        500.0,
        160.0,
        250.0,
        160.0,
    )


def test_explicit_clock_variants_keep_independent_rect_and_font_scale() -> None:
    screen = _FakeScreen("A")
    signature = get_screen_signature(screen)
    analog = _entry(0.10, 0.25, 0.30, 0.40)
    analog["size_payload"] = {"font_size": 62}
    digital = _entry(0.55, 0.10, 0.20, 0.15)
    digital["size_payload"] = {"font_size": 39}
    widgets = {
        "clock": {
            "position": "Custom",
            "display_mode": "digital",
        },
        "custom_layout": {
            "version": 2,
            "displays": {
                signature: {
                    "clock": {"digital": digital, "analog": analog}
                }
            },
        },
    }

    analog_state = resolve_quick_committed_variant_state(
        widgets, screen, "clock", geometry_variant="analog"
    )
    digital_state = resolve_quick_committed_variant_state(
        widgets, screen, "clock", geometry_variant="digital"
    )

    assert analog_state is not None
    assert digital_state is not None
    analog_geometry, analog_payload = analog_state
    digital_geometry, digital_payload = digital_state
    assert (
        analog_geometry.x,
        analog_geometry.y,
        analog_geometry.width,
        analog_geometry.height,
    ) == (100.0, 200.0, 300.0, 320.0)
    assert analog_payload == {"font_size": 62}
    assert (
        digital_geometry.x,
        digital_geometry.y,
        digital_geometry.width,
        digital_geometry.height,
    ) == (550.0, 80.0, 200.0, 120.0)
    assert digital_payload == {"font_size": 39}


def test_missing_target_variant_derives_from_saved_opposite_center_and_scale() -> None:
    screen = _FakeScreen("A")
    signature = get_screen_signature(screen)
    digital = _entry(0.20, 0.30, 0.30, 0.20)
    digital["size_payload"] = {"font_size": 50}
    widgets = {
        "clock": {
            "position": "Custom",
            "display_mode": "analog",
        },
        "custom_layout": {
            "version": 2,
            "displays": {signature: {"clock": {"digital": digital}}},
        },
    }

    state = resolve_quick_committed_variant_state(
        widgets, screen, "clock", geometry_variant="analog"
    )

    assert state is not None
    geometry, payload = state
    # Saved digital centre is (350, 320). Analog natural width at font 50 is
    # 225 and height 292.5, so the replay keeps the centre (integer pixel input
    # means exact .5 output is legal in the retained logical coordinate space).
    assert geometry.x == 237.5
    assert geometry.y == 173.75
    assert geometry.width == 225.0
    assert geometry.height == 292.5
    assert payload == {"font_size": 50}
