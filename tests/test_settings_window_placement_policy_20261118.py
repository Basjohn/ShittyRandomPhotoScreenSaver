"""Import-free Settings placement tests: no Qt dependency or render-thread work."""
from __future__ import annotations

import importlib.util
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_PATH = _ROOT / "ui/settings_window_placement.py"
_spec = importlib.util.spec_from_file_location("_settings_window_placement_test", _PATH)
assert _spec is not None and _spec.loader is not None
_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_module)
settle = _module.settle_settings_rect


def test_interior_position_and_size_are_preserved() -> None:
    assert settle((120, 140, 1300, 800), (0, 0, 1920, 1040), (1280, 760)) == (120, 140, 1300, 800)


def test_snap_all_four_edges_only_within_twelve_logical_pixels() -> None:
    work = (0, 0, 1920, 1040)
    minimum = (1280, 760)
    assert settle((11, 12, 1300, 800), work, minimum) == (0, 0, 1300, 800)
    assert settle((621, 241, 1300, 800), work, minimum) == (620, 240, 1300, 800)
    assert settle((13, 13, 1300, 800), work, minimum) == (13, 13, 1300, 800)
    assert settle((607, 227, 1300, 800), work, minimum) == (607, 227, 1300, 800)


def test_taskbar_work_area_is_honoured() -> None:
    assert settle((690, 360, 1300, 800), (0, 0, 1920, 1040), (1280, 760)) == (620, 240, 1300, 800)


def test_monitor_to_left_of_origin_is_supported() -> None:
    assert settle((-1910, -20, 1300, 800), (-1920, 0, 1920, 1040), (1280, 760)) == (-1920, 0, 1300, 800)


def test_monitor_to_right_can_receive_an_existing_dialog() -> None:
    assert settle((1770, 40, 1300, 800), (1920, 0, 2560, 1400), (1280, 760)) == (1920, 40, 1300, 800)


def test_dragged_window_outside_far_edges_is_clamped_to_accessible_bounds() -> None:
    assert settle((-1500, -900, 1500, 900), (0, 0, 1920, 1040), (1280, 760)) == (0, 0, 1500, 900)


def test_large_window_downsizes_only_to_declared_minimum() -> None:
    assert settle((50, 50, 3000, 2000), (0, 0, 1600, 900), (1280, 760)) == (0, 0, 1600, 900)


def test_small_screen_keeps_layout_minimum_and_title_bar_reachable() -> None:
    assert settle((99, 99, 1400, 900), (0, 0, 1024, 720), (1280, 760)) == (0, 0, 1280, 760)


def test_saved_geometry_can_clamp_without_proximity_snapping() -> None:
    assert settle((11, 12, 1300, 800), (0, 0, 1920, 1040), (1280, 760), snap_distance=0) == (11, 12, 1300, 800)


def test_no_per_frame_placement_or_new_timer_contract() -> None:
    source = (_ROOT / "ui/settings_dialog.py").read_text(encoding="utf-8")
    assert "def moveEvent(" not in source
    dialog = source.split("class SettingsDialog(QDialog):", 1)[1]
    title = source.split("class CustomTitleBar(QWidget):", 1)[1].split("class _SettingsTabVectorIcon", 1)[0]
    grip = source.split("class CornerSizeGrip(QSizeGrip):", 1)[1].split("class SettingsDialog(QDialog):", 1)[0]
    assert "def _settle_window_placement(self)" in dialog
    for section in (title, grip, dialog):
        assert "def mouseReleaseEvent(" in section
        assert "_settle_window_placement" in section
    assert "return screen.availableGeometry() if screen is not None else self.geometry()" in dialog
    assert "content_layout.setContentsMargins(10, 10, 12, 9)" in dialog
    assert "layout.setContentsMargins(10, 10, 12, 9)" in dialog
    assert "QTimer.singleShot" not in dialog.split("def _settle_window_placement(self)", 1)[1].split("def _save_geometry(self)", 1)[0]
