from __future__ import annotations

from PySide6.QtCore import QRect

from rendering.custom_layout_session import (
    CustomLayoutKey,
    CustomLayoutSession,
    CustomLayoutSessionItem,
)


def _item(
    key: CustomLayoutKey,
    rect: QRect,
    *,
    enabled: bool = True,
    duplicate: bool = False,
) -> CustomLayoutSessionItem:
    return CustomLayoutSessionItem(
        source_key=key,
        model_identity=f"model:{key.widget_id}:{key.geometry_variant}",
        baseline_global_rect=rect,
        current_global_rect=rect,
        baseline_size_payload={"font_size": 48},
        current_size_payload={"font_size": 48},
        baseline_enabled=enabled,
        current_enabled=enabled,
        is_duplicate=duplicate,
    )


def test_clock_geometry_variants_keep_independent_exact_rects_without_drift():
    session = CustomLayoutSession()
    digital_key = CustomLayoutKey("clock", "display:a", "digital")
    analog_key = CustomLayoutKey("clock", "display:a", "analogue")
    digital_rect = QRect(80, 60, 360, 150)
    analog_rect = QRect(145, 85, 280, 280)
    session.add_item(_item(digital_key, digital_rect))
    session.add_item(_item(analog_key, analog_rect))

    for _ in range(20):
        assert session.item(digital_key).current_global_rect == digital_rect
        assert session.item(analog_key).current_global_rect == analog_rect

    assert analog_key.geometry_variant == "analog"
    assert session.item(digital_key).source_key != session.item(analog_key).source_key


def test_same_variant_is_independent_per_display_and_transfer_updates_current_key_only():
    session = CustomLayoutSession()
    source_key = CustomLayoutKey("clock", "display:a", "digital")
    other_key = CustomLayoutKey("clock", "display:b", "digital")
    source_rect = QRect(40, 50, 320, 140)
    other_rect = QRect(900, 70, 300, 130)
    source = _item(source_key, source_rect)
    other = _item(other_key, other_rect)
    session.add_item(source)
    session.add_item(other)

    transferred_rect = QRect(880, 120, 320, 140)
    source.transfer_to_display("display:b", transferred_rect)

    assert source.source_key == source_key
    assert source.current_key == CustomLayoutKey("clock", "display:b", "digital")
    assert source.current_global_rect == transferred_rect
    assert other.current_global_rect == other_rect


def test_remove_action_marks_duplicate_removed_but_disables_ordinary_singleton():
    duplicate = _item(
        CustomLayoutKey("clock", "display:b", "digital"),
        QRect(900, 70, 300, 130),
        duplicate=True,
    )
    singleton = _item(
        CustomLayoutKey("weather", "display:a"),
        QRect(60, 80, 420, 220),
    )

    duplicate.apply_remove_action()
    singleton.apply_remove_action()

    assert duplicate.removed is True
    assert duplicate.current_enabled is True
    assert singleton.removed is False
    assert singleton.current_enabled is False


def test_cancel_restores_geometry_payload_display_enabled_and_removed_working_state():
    session = CustomLayoutSession()
    key = CustomLayoutKey("weather", "display:a")
    baseline_rect = QRect(60, 80, 420, 220)
    item = _item(key, baseline_rect)
    session.add_item(item)

    item.set_geometry(
        QRect(980, 120, 510, 280),
        size_payload={"font_size": 24, "icon_size": 42},
        resize_scale=1.25,
    )
    item.transfer_to_display("display:b", item.current_global_rect)
    item.current_monitor_route = "2"
    item.current_enabled = False
    item.removed = True

    session.restore_baseline()

    assert item.current_key == key
    assert item.current_monitor_route == "ALL"
    assert item.current_global_rect == baseline_rect
    assert item.current_size_payload == {"font_size": 48}
    assert item.current_enabled is True
    assert item.resize_scale == 1.0
    assert item.removed is False


def test_session_copies_mutable_geometry_and_payload_inputs():
    rect = QRect(10, 20, 300, 120)
    payload = {"font_size": 48}
    item = CustomLayoutSessionItem(
        source_key=CustomLayoutKey("clock", "display:a", "digital"),
        model_identity="clock-model",
        baseline_global_rect=rect,
        current_global_rect=rect,
        baseline_size_payload=payload,
        current_size_payload=payload,
        baseline_enabled=True,
        current_enabled=True,
    )

    rect.moveTo(999, 999)
    payload["font_size"] = 12

    assert item.baseline_global_rect == QRect(10, 20, 300, 120)
    assert item.current_global_rect == QRect(10, 20, 300, 120)
    assert item.baseline_size_payload == {"font_size": 48}
    assert item.current_size_payload == {"font_size": 48}
