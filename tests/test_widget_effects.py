from __future__ import annotations

from types import SimpleNamespace

import pytest
from PySide6.QtWidgets import QWidget, QGraphicsOpacityEffect


class _UpdateSpyWidget(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.update_calls = 0

    def update(self, *args, **kwargs):  # type: ignore[override]
        self.update_calls += 1
        return super().update(*args, **kwargs)


@pytest.mark.qt
def test_invalidate_overlay_effects_refreshes_live_opacity_effect_without_recreation(qtbot):
    from rendering.widget_effects import invalidate_overlay_effects

    widget = _UpdateSpyWidget()
    qtbot.addWidget(widget)
    widget.resize(40, 20)
    widget.show()

    effect = QGraphicsOpacityEffect(widget)
    effect.setOpacity(0.5)
    widget.setGraphicsEffect(effect)

    mgr = SimpleNamespace(
        _parent=SimpleNamespace(screen_index=0),
        _widgets={"spy": widget},
    )

    invalidate_overlay_effects(mgr, "menu_before_popup")

    assert widget.graphicsEffect() is effect
    assert effect.opacity() == pytest.approx(0.5)
    assert widget.update_calls == 1


@pytest.mark.qt
def test_invalidate_overlay_effects_ignores_widgets_without_opacity_effect(qtbot):
    from rendering.widget_effects import invalidate_overlay_effects

    widget = _UpdateSpyWidget()
    qtbot.addWidget(widget)
    widget.resize(40, 20)
    widget.show()

    mgr = SimpleNamespace(
        _parent=SimpleNamespace(screen_index=0),
        _widgets={"spy": widget},
    )

    invalidate_overlay_effects(mgr, "menu_before_popup")

    assert widget.update_calls == 0
