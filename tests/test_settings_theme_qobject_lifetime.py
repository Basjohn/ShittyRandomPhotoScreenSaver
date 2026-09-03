"""PySide6 regression for deleted Settings root wrappers in live theme refresh.

Runs only in the normal user/Qt environment. The Qt-free companion test covers
transaction semantics without PySide; this test proves the real Shiboken lifetime
edge that produced ``Internal C++ object (SettingsDialog) already deleted``.
"""
from __future__ import annotations

from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtWidgets import QApplication, QWidget
from shiboken6 import Shiboken

import ui.settings_theme as settings_theme
from ui.settings_theme_spec import DEFAULT_DARK_SETTINGS_THEME


def test_deleted_qwidget_wrapper_is_pruned_before_root_qss_refresh() -> None:
    _app = QApplication.instance() or QApplication([])
    stale = QWidget()
    live = QWidget()

    settings_theme._THEMED_WIDGETS.clear()
    settings_theme._THEMED_WIDGETS.add(stale)
    settings_theme._THEMED_WIDGETS.add(live)

    stale.deleteLater()
    QCoreApplication.sendPostedEvents(stale, QEvent.Type.DeferredDelete)
    QCoreApplication.processEvents()
    assert not Shiboken.isValid(stale)
    assert Shiboken.isValid(live)

    # Must not raise from the stale wrapper. The live root still receives QSS.
    settings_theme._refresh_registered_widgets(DEFAULT_DARK_SETTINGS_THEME)
    assert stale not in settings_theme._THEMED_WIDGETS
    assert live in settings_theme._THEMED_WIDGETS
    assert live.styleSheet()

    live.deleteLater()
    QCoreApplication.sendPostedEvents(live, QEvent.Type.DeferredDelete)
    QCoreApplication.processEvents()
    settings_theme._THEMED_WIDGETS.clear()
