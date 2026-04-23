from __future__ import annotations

import pytest
from PySide6.QtWidgets import QWidget

from widgets.mute_button_widget import MuteButtonWidget


@pytest.mark.qt
def test_mute_button_waits_for_secondary_stage_before_reveal(qt_app):
    parent = QWidget()
    parent.resize(640, 480)
    parent.show()

    anchor = QWidget(parent)
    anchor.setGeometry(100, 80, 240, 120)
    anchor.show()

    mute = MuteButtonWidget(parent)
    mute._available = True
    mute.set_anchor(anchor)
    mute.set_enabled(True)
    mute._spotify_secondary_stage_registered = True

    try:
        mute.sync_visibility_with_anchor()
        assert mute.isVisible() is False
        assert mute._has_faded_in is False

        calls: list[str] = []

        def _fake_update_position() -> None:
            calls.append("update")
            mute.move(123, 77)

        def _fake_start_fade(_duration_ms=None) -> None:
            calls.append("fade")
            mute.show()
            mute._has_faded_in = True

        mute.update_position = _fake_update_position  # type: ignore[method-assign]
        mute._start_widget_fade_in = _fake_start_fade  # type: ignore[method-assign]

        mute.begin_spotify_secondary_stage()

        assert mute._spotify_secondary_stage_started is True
        assert mute.isVisible() is True
        assert mute.pos().x() == 123
        assert mute.pos().y() == 77
        assert calls
        assert calls[0] == "update"
        assert "fade" in calls
    finally:
        mute.deleteLater()
        anchor.deleteLater()
        parent.deleteLater()

