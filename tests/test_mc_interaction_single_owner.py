"""AC-22: Settings, Guided Setup and the runtime answer "is this the MC build" with the one product predicate.

The "MC forces Interaction Mode on" rule has one owner (``core.mc.interaction_mode_forced``); no surface compares the
store's application name with a literal. The tests decouple the two on purpose (an injected manager whose name says
the opposite of the predicate) and require every surface to follow the predicate.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from PySide6.QtWidgets import QApplication

from core.settings.settings_manager import SettingsManager

pytestmark = pytest.mark.qt


def _surfaces(manager):
    """(Display tab locked, Display tab shows on, Display tab saves, Guided Setup, onboarding summary, runtime)."""
    from engine.display_manager import DisplayManager
    from ui.onboarding.state import current_setup_summary, is_media_center_profile
    from ui.tabs.display_tab import DisplayTab

    manager.set("input.interaction_mode", False)
    tab = DisplayTab(manager)
    try:
        locked = not tab.interaction_mode_check.isEnabled()
        shown_on = tab.interaction_mode_check.isChecked()
        tab._save_settings()
        saved_on = manager.get("input.interaction_mode") is True
    finally:
        tab.deleteLater()
    manager.set("input.interaction_mode", False)
    summary = current_setup_summary(manager)
    runtime = DisplayManager._interaction_mode_enabled(SimpleNamespace(settings_manager=manager))
    return locked, shown_on, saved_on, is_media_center_profile(manager), bool(summary.get("interaction")), runtime


@pytest.mark.parametrize("mc_build, application", [(True, "Screensaver"), (False, "Screensaver_MC")])
def test_every_surface_follows_the_product_predicate_not_the_store_name(tmp_path, monkeypatch, mc_build, application):
    QApplication.instance() or QApplication([])
    import core.mc
    monkeypatch.setattr(core.mc, "is_mc_build", lambda: mc_build)
    manager = SettingsManager(application=application, storage_base_dir=tmp_path)
    assert _surfaces(manager) == (mc_build,) * 6
