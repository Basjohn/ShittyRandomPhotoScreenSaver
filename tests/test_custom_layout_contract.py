from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, QSize

from rendering.custom_layout_contract import (
    CustomLayoutEntry,
    CUSTOM_LAYOUT_TRANSFER_THRESHOLD_PX,
    NormalizedRect,
    build_default_custom_layout_map,
    canonicalize_screen_layout_bucket,
    clamp_local_rect_to_bounds,
    deserialize_custom_layout_entry,
    get_screen_layout_entries_for_screen,
    load_custom_layout_map,
    normalize_local_rect,
    resolve_snap_local_rect_for_edit,
    should_transfer_rect_to_screen,
    snap_local_rect_for_edit,
    set_screen_layout_entry,
)


def test_custom_layout_map_round_trips_entries():
    custom_map = build_default_custom_layout_map()
    entry = CustomLayoutEntry(
        widget_id="clock",
        rect=NormalizedRect(0.1, 0.2, 0.3, 0.4),
        size_payload={"font_size": 64},
        resize_mode="clock_font",
    )
    set_screen_layout_entry(custom_map, "screen:test", "clock", entry)

    widgets_map = {}
    widgets_map["custom_layout"] = custom_map
    loaded = load_custom_layout_map(widgets_map)
    restored = deserialize_custom_layout_entry(
        "clock",
        loaded["displays"]["screen:test"]["clock"],
    )

    assert restored is not None
    assert restored.rect == entry.rect
    assert restored.size_payload == {"font_size": 64}
    assert restored.resize_mode == "clock_font"


def test_normalize_and_clamp_rect_helpers_are_display_local():
    rect = QRect(100, 80, 220, 140)
    display_size = QSize(1000, 500)

    normalized = normalize_local_rect(rect, display_size)
    assert normalized == NormalizedRect(0.1, 0.16, 0.22, 0.28)

    snapped = resolve_snap_local_rect_for_edit(QRect(17, 25, 119, 81), display_size)
    assert snapped.rect == QRect(12, 24, 119, 81)

    clamped = clamp_local_rect_to_bounds(QRect(950, 470, 120, 80), display_size)
    assert clamped.right() <= display_size.width() - 1
    assert clamped.bottom() <= display_size.height() - 1


def test_snap_local_rect_for_edit_snaps_to_display_edges_and_grid():
    display_size = QSize(1000, 600)

    edge_rect = snap_local_rect_for_edit(QRect(8, 9, 180, 90), display_size)
    assert edge_rect.topLeft() == QPoint(12, 12)

    far_edge_rect = snap_local_rect_for_edit(QRect(813, 507, 180, 90), display_size)
    assert far_edge_rect.left() == 816
    assert far_edge_rect.top() == 504


def test_snap_local_rect_for_edit_snaps_to_peer_edges_and_grid():
    display_size = QSize(1000, 600)
    peer = QRect(300, 200, 180, 90)

    flush_right = snap_local_rect_for_edit(
        QRect(474, 204, 140, 70),
        display_size,
        peer_rects=[peer],
    )
    assert flush_right.left() == 480
    assert flush_right.top() == 204

    flush_left = snap_local_rect_for_edit(
        QRect(148, 284, 140, 70),
        display_size,
        peer_rects=[peer],
    )
    assert flush_left.left() == 144
    assert flush_left.top() == 288


def test_resolve_snap_local_rect_for_edit_reports_active_guides():
    display_size = QSize(1000, 600)
    peer = QRect(300, 200, 180, 90)

    snap = resolve_snap_local_rect_for_edit(
        QRect(474, 204, 140, 70),
        display_size,
        peer_rects=[peer],
    )

    assert snap.rect == QRect(480, 204, 140, 70)
    assert snap.vertical_guides
    assert snap.vertical_guides[0].position == 480
    assert snap.vertical_guides[0].kind == "grid"
    assert snap.horizontal_guides == ()


def test_resolve_snap_local_rect_for_edit_can_report_peer_guides_when_closer_than_grid():
    display_size = QSize(1000, 600)
    peer = QRect(301, 200, 180, 90)

    snap = resolve_snap_local_rect_for_edit(
        QRect(162, 210, 140, 70),
        display_size,
        peer_rects=[peer],
    )

    assert snap.rect.left() == 161
    assert snap.vertical_guides
    assert snap.vertical_guides[0].position == 301
    assert snap.vertical_guides[0].kind == "peer"


class _FakeScreen:
    def __init__(
        self,
        rect: QRect,
        *,
        serial: str = "",
        manufacturer: str = "",
        model: str = "",
        name: str = "",
    ) -> None:
        self._rect = QRect(rect)
        self._serial = serial
        self._manufacturer = manufacturer
        self._model = model
        self._name = name

    def geometry(self) -> QRect:
        return QRect(self._rect)

    def serialNumber(self) -> str:
        return self._serial

    def manufacturer(self) -> str:
        return self._manufacturer

    def model(self) -> str:
        return self._model

    def name(self) -> str:
        return self._name


def test_custom_layout_entries_resolve_legacy_signature_when_screen_geometry_drifts():
    custom_map = build_default_custom_layout_map()
    legacy_signature = "serial:abc|manufacturer:LG|model:TV|name:LG TV|geom:2560_0_2560x1440"
    custom_map["displays"][legacy_signature] = {
        "clock": {
            "rect": {"x": 0.2, "y": 0.1, "width": 0.15, "height": 0.3},
            "size_payload": {"font_size": 72},
            "resize_mode": "clock_font",
        }
    }
    live_screen = _FakeScreen(
        QRect(2560, 0, 2560, 1439),
        serial="abc",
        manufacturer="LG",
        model="TV",
        name="LG TV",
    )

    matched, entries = get_screen_layout_entries_for_screen(custom_map, live_screen)

    assert matched == legacy_signature
    assert "clock" in entries

    canonical = canonicalize_screen_layout_bucket(custom_map, live_screen)
    assert canonical == "serial:abc|manufacturer:LG|model:TV|name:LG TV"
    assert canonical in custom_map["displays"]
    assert legacy_signature not in custom_map["displays"]


def test_should_transfer_rect_to_screen_requires_deliberate_push_past_edge():
    screen0 = _FakeScreen(QRect(0, 0, 800, 600))
    screen1 = _FakeScreen(QRect(800, 0, 800, 600))

    near_edge = QRect(790, 100, 180, 90)
    assert should_transfer_rect_to_screen(
        near_edge,
        current_screen=screen1,
        candidate_screen=screen0,
        cursor_global=QPoint(795, 120),
    ) is False

    deliberate_push = QRect(760, 100, 180, 90)
    assert should_transfer_rect_to_screen(
        deliberate_push,
        current_screen=screen1,
        candidate_screen=screen0,
        cursor_global=QPoint(780, 120),
        threshold_px=CUSTOM_LAYOUT_TRANSFER_THRESHOLD_PX,
    ) is True
