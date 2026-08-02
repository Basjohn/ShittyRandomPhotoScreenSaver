from __future__ import annotations

from transitions import overlay_manager


def test_overlay_readiness_poll_is_owned_by_display_generation(
    qt_app,
    monkeypatch,
):
    from PySide6.QtWidgets import QWidget

    scheduled: list[tuple[int, object]] = []
    monkeypatch.setattr(
        overlay_manager.ThreadManager,
        "single_shot",
        lambda delay_ms, callback: scheduled.append((int(delay_ms), callback)),
    )
    display = QWidget()
    display._runtime_generation = 63
    overlay = QWidget(display)
    overlay.is_ready_for_display = lambda: False
    try:
        overlay_manager.schedule_raise_when_ready(display, overlay)

        assert len(scheduled) == 1
        assert scheduled[0][0] == 0
        assert scheduled[0][1]._srpss_runtime_generation == 63
    finally:
        overlay.close()
        display.close()
