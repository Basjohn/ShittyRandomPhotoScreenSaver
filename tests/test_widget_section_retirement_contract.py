from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _text(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_custom_resize_notice_refresh_rejects_deleted_qobject_wrappers() -> None:
    source = _text("ui/tabs/widgets_tab.py")

    assert "from shiboken6 import isValid as _is_valid_qobject" in source

    start = source.index("    def _ensure_custom_resize_lock_notice(")
    end = source.index("\n    def ", start + 10)
    ensure_block = source[start:end]
    assert "_is_valid_qobject(existing)" in ensure_block
    assert "self._custom_resize_lock_notice_labels.pop(section_id, None)" in ensure_block

    start = source.index("    def _refresh_custom_resize_lock_state(")
    end = source.index("\n    def ", start + 10)
    refresh_block = source[start:end]
    assert "control is not None and _is_valid_qobject(control)" in refresh_block
    assert "if not _is_valid_qobject(notice):" in refresh_block
    assert "self._custom_resize_lock_notice_labels.pop(section_id, None)" in refresh_block

    assert "anchor_control is None or not _is_valid_qobject(anchor_control)" in ensure_block

    position_start = source.index("    def _refresh_custom_position_option_state(")
    position_end = source.index("\n    def ", position_start + 10)
    position_block = source[position_start:position_end]
    assert "combo is None or not _is_valid_qobject(combo)" in position_block

    active_start = source.index("    def _is_custom_resize_lock_active(")
    active_end = source.index("\n    def ", active_start + 10)
    active_block = source[active_start:active_end]
    assert "_is_valid_qobject(combo)" in active_block
