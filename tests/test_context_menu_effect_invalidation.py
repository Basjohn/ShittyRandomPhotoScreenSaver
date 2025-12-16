from __future__ import annotations

from typing import List, Tuple

import pytest

from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QWidget, QGraphicsDropShadowEffect

from rendering.display_widget import DisplayWidget
from widgets.context_menu import ScreensaverContextMenu


@pytest.mark.qt
def test_context_menu_invalidates_effects_before_popup(qt_app, qtbot, settings_manager, monkeypatch):
    widget = DisplayWidget(screen_index=0, display_mode=None, settings_manager=settings_manager)
    qtbot.addWidget(widget)
    widget.resize(640, 360)

    dummy = QWidget(widget)
    dummy.resize(20, 20)
    dummy.show()

    eff = QGraphicsDropShadowEffect(dummy)
    dummy.setGraphicsEffect(eff)

    events: List[Tuple[str, object]] = []

    orig_invalidate = widget._invalidate_overlay_effects  # type: ignore[attr-defined]

    def _spy_invalidate(reason: str) -> None:
        events.append(("invalidate", reason))
        orig_invalidate(reason)

    monkeypatch.setattr(widget, "_invalidate_overlay_effects", _spy_invalidate)

    last_popup_menu: List[object] = []

    def _spy_popup(self, pos):  # type: ignore[no-untyped-def]
        last_popup_menu.clear()
        last_popup_menu.append(self)
        events.append(("popup", pos))
        assert any(e[0] == "invalidate" for e in events)

    monkeypatch.setattr(ScreensaverContextMenu, "popup", _spy_popup)

    widget.clock_widget = dummy  # type: ignore[assignment]

    effect_ids: List[int] = []

    for i in range(25):
        events.clear()
        widget._show_context_menu(QPoint(10 + i, 10))  # type: ignore[attr-defined]
        qt_app.processEvents()
        assert events

        try:
            active_eff = dummy.graphicsEffect()
        except Exception:
            active_eff = None
        assert isinstance(active_eff, QGraphicsDropShadowEffect)
        effect_ids.append(id(active_eff))

        invalidate_idx = next(idx for idx, e in enumerate(events) if e[0] == "invalidate")
        popup_idx = next(idx for idx, e in enumerate(events) if e[0] == "popup")
        assert invalidate_idx < popup_idx

        menu = last_popup_menu[0] if last_popup_menu else None
        assert menu is not None
        try:
            menu.aboutToHide.emit()
        except Exception:
            pass
        qt_app.processEvents()

        assert any(
            e[0] == "invalidate" and str(e[1]).startswith("menu_after_hide")
            for e in events
        )

    assert len(set(effect_ids)) >= 2
