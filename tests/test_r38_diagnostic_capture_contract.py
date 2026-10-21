"""Qt-free capture pixel and build-contract checks; no APPDATA/env writes."""
from datetime import datetime
from pathlib import Path

from core.diagnostic_capture_contract import capture_filename, crop_pixels, CaptureRect


def test_negative_monitor_origin_fractional_dpr_and_clipping():
    # Physical size, not assumed DPR, is the authority for the captured pixels.
    assert crop_pixels((-1500, 200, 400, 200), (-1600, 0),
                       (1600, 900), (2400, 1350)) == CaptureRect(150, 300, 600, 300)
    assert crop_pixels((-1800, -100, 500, 200), (-1600, 0),
                       (1600, 900), (2400, 1350)) == CaptureRect(0, 0, 450, 150)


def test_no_hover_falls_back_and_invalid_crops_are_rejected():
    assert crop_pixels(None, (0, 0), (2560, 1440), (2560, 1440)) is None
    assert crop_pixels((3000, 100, 50, 50), (0, 0), (2560, 1440), (2560, 1440)) is None
    assert crop_pixels((4, 5, 0, 20), (0, 0), (2560, 1440), (2560, 1440)) is None


def test_capture_names_are_unique_and_path_safe():
    when = datetime(2026, 10, 21, 22, 33, 44, 543210)
    name = capture_filename(moment=when, screen_index=1, region='../../Huge Bubble <+>', suffix=23)
    assert name.endswith('_display1_huge-bubble_17.png')
    assert '/' not in name and '\\' not in name
    assert capture_filename(moment=when, screen_index=1, region='Huge Bubble', suffix=24) != name


def test_capture_is_inert_except_on_a_manual_key_edge():
    root = Path(__file__).resolve().parents[1]
    source = (root/'rendering/quick/input_controller.py').read_text(encoding='utf-8')
    service = (root/'rendering/quick/diagnostic_capture.py').read_text(encoding='utf-8')
    runtime = (root/'rendering/quick/runtime.py').read_text(encoding='utf-8')
    assert 'event.key() == Qt.Key.Key_Backslash' in source
    assert 'if not event.isAutoRepeat()' in source
    assert 'self.diagnostic_capture_requested.emit()' in source
    assert 'return not is_compiled_runtime() or is_diagnostic_build()' in service
    assert 'QuickRuntimePhase.RETIRING, QuickRuntimePhase.RETIRED' in runtime
    assert 'screen.grabWindow(0)' in service
    assert 'Thread(target=_write_and_release' in service
    assert '_capture_busy.acquire(blocking=False)' in service
    assert '/captures/' in (root/'.gitignore').read_text(encoding='utf-8')
