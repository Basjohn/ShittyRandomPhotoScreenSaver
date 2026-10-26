"""Production Settings/UI seams for physical saver admission and durable authoring."""
import json
from types import SimpleNamespace

import pytest

from core.settings import SettingsManager
from core.settings import monitor_routes
from core.settings.display_selection import resolve_monitor_numbers, BINDINGS_KEY
from engine.display_manager import DisplayManager
from ui.tabs.display_tab import DisplayTab

pytestmark = pytest.mark.usefixtures('qt_app')
A, B, C = 'serial:one', 'serial:two', 'serial:three'


def make_manager(tmp_path, monkeypatch, screens=(A, B), profile='PhysicalSelectionTest'):
    live = [screens]
    monkeypatch.setattr(monitor_routes, 'current_screen_identities', lambda: live[0])
    manager = SettingsManager(application=profile, storage_base_dir=tmp_path)
    return manager, live


def admitted(manager, live):
    return DisplayManager._get_allowed_screen_indices(SimpleNamespace(settings_manager=manager), len(live[0]))


def test_durable_selection_returns_to_same_physical_monitor(tmp_path, monkeypatch):
    manager, live = make_manager(tmp_path, monkeypatch)
    manager.set('display.show_on_monitors', [2])
    assert admitted(manager, live) == {1}
    live[0] = (B,)
    assert admitted(manager, live) == {0}
    live[0] = (A,)
    assert admitted(manager, live) == set()
    manager.set('display.mode', 'fit')
    manager.save()
    reopened = SettingsManager(application='PhysicalSelectionTest', storage_base_dir=tmp_path)
    assert reopened.get(BINDINGS_KEY) == {'2': B}
    assert admitted(reopened, live) == set()
    live[0] = (B, A)
    assert admitted(reopened, live) == {0}
    live[0] = ()
    assert admitted(reopened, live) == set()
    live[0] = (A, C)
    assert admitted(reopened, live) == set()
    reopened.set('display.show_on_monitors', [2])  # same label, explicit new physical target
    assert reopened.get(BINDINGS_KEY) == {'2': C}
    assert admitted(reopened, live) == {1}


def test_legacy_capture_absent_target_and_all_none(tmp_path, monkeypatch):
    manager, live = make_manager(tmp_path, monkeypatch, screens=(A,))
    manager._settings.setValue('display.show_on_monitors', '[2]')
    manager._settings.setValue(BINDINGS_KEY, {})
    manager._clear_cache_locked()
    manager.ensure_display_monitor_bindings()
    assert manager.get(BINDINGS_KEY) == {'2': None}
    live[0] = (A, B)
    assert admitted(manager, live) == set()
    manager.set('display.show_on_monitors', 'ALL')
    live[0] = (C, B, A)
    assert admitted(manager, live) == {0, 1, 2}
    manager.set('display.show_on_monitors', 'NONE')
    assert admitted(manager, live) == set()


def test_profile_repair_reset_import_and_export(tmp_path, monkeypatch):
    manager, live = make_manager(tmp_path, monkeypatch, profile='Screensaver_MC')
    assert manager.get('display.show_on_monitors') == [2]
    assert manager.get(BINDINGS_KEY) == {'2': B}
    manager.set('display.show_on_monitors', 'broken')
    assert manager.get('display.show_on_monitors') == [2]
    manager.set('display.show_on_monitors', [1])
    path = tmp_path / 'selection.sst'
    assert manager.export_to_sst(str(path))
    live[0] = (B, A)
    manager.reset_to_defaults()
    assert manager.get(BINDINGS_KEY) == {'2': A}
    assert manager.import_from_sst(str(path))
    assert admitted(manager, live) == {1}
    # Import with numeric intent but no metadata authors today's display.
    incoming = tmp_path / 'numeric.sst'
    incoming.write_text(json.dumps({'display': {'show_on_monitors': [1]}}))
    assert manager.import_from_sst(str(incoming))
    assert manager.get(BINDINGS_KEY) == {'1': B}
    unrelated = tmp_path / 'style.sst'
    unrelated.write_text(json.dumps({'display': {'mode': 'fit'}}))
    live[0] = (A,)
    assert manager.import_from_sst(str(unrelated))
    assert manager.get(BINDINGS_KEY) == {'1': B}
    assert admitted(manager, live) == set()


def test_display_ui_preserves_absence_none_and_fixed_all(tmp_path, monkeypatch):
    manager, live = make_manager(tmp_path, monkeypatch)
    import ui.tabs.display_tab as display_ui
    monkeypatch.setattr(display_ui, 'get_screen_count', lambda: len(live[0]))
    manager.set('display.show_on_monitors', [2])
    live[0] = (A,)
    tab = DisplayTab(manager)
    try:
        assert not tab.show_all_check.isChecked()
        assert not any(check.isChecked() for check in tab.monitor_checks)
        tab.same_image_check.setChecked(True)
        assert manager.get('display.show_on_monitors') == [2]
        assert manager.get(BINDINGS_KEY) == {'2': B}
        # Explicit checkbox authoring captures a current target, then fixed both.
        tab.monitor_checks[0].setChecked(True)
        assert manager.get(BINDINGS_KEY) == {'1': A}
        live[0] = (A, B)
        tab._load_settings()
        tab.monitor_checks[1].setChecked(True)
        assert manager.get('display.show_on_monitors') == [1, 2]
        assert not tab.show_all_check.isChecked()
        manager.set('display.show_on_monitors', 'NONE')
        tab._load_settings()
        tab.same_image_check.setChecked(False)
        assert manager.get('display.show_on_monitors') == 'NONE'
        assert not any(check.isChecked() for check in tab.monitor_checks)
    finally:
        tab.deleteLater()


def test_display_ui_rows_follow_topology_beyond_four_without_rebinding(tmp_path, monkeypatch, qt_app):
    from PySide6.QtCore import QCoreApplication, QEvent
    from PySide6.QtGui import QImage
    from PySide6.QtWidgets import QWidget
    import ui.tabs.display_tab as display_ui

    screens = tuple(f"serial:capacity-{number}" for number in range(1, 7))
    manager, live = make_manager(tmp_path, monkeypatch, screens=screens)
    monkeypatch.setattr(display_ui, 'get_screen_count', lambda: len(live[0]))
    manager.set('display.show_on_monitors', [6])
    tab = DisplayTab(manager)
    try:
        assert len(tab.monitor_checks) == 6
        assert tab.monitor_checks[5].isChecked()
        tab.resize(1100, 900)
        tab.ensurePolished()
        for widget in reversed([tab, *tab.findChildren(QWidget)]):
            if widget.layout() is not None:
                widget.layout().activate()
        qt_app.processEvents()
        image = QImage(tab.size(), QImage.Format.Format_ARGB32_Premultiplied)
        image.fill(0)
        tab.render(image)
        assert image.save(str(tmp_path / "six_display_rows.png"))
        assert all(first.geometry().bottom() < second.geometry().top()
                   for first, second in zip(tab.monitor_checks, tab.monitor_checks[1:]))
        original = manager.get(BINDINGS_KEY)
        live[0] = screens[:3]
        qt_app.screenRemoved.emit(qt_app.primaryScreen())
        assert len(tab.monitor_checks) == 3
        assert not any(check.isChecked() for check in tab.monitor_checks)
        tab.same_image_check.setChecked(not tab.same_image_check.isChecked())
        assert manager.get('display.show_on_monitors') == [6]
        assert manager.get(BINDINGS_KEY) == original
        live[0] = (screens[5], *screens[:5])
        qt_app.screenAdded.emit(qt_app.primaryScreen())
        assert len(tab.monitor_checks) == 6
        assert tab.monitor_checks[0].isChecked() and not tab.monitor_checks[5].isChecked()
        assert manager.get(BINDINGS_KEY) == original
        tab.monitor_checks[1].setChecked(True)
        assert manager.get('display.show_on_monitors') == [1, 2]
        assert manager.get(BINDINGS_KEY) == {'1': screens[5], '2': screens[0]}
        live[0] = ()
        qt_app.screenRemoved.emit(qt_app.primaryScreen())
        assert not tab.monitor_checks
        assert manager.get('display.show_on_monitors') == [1, 2]
    finally:
        tab.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    # Topology observation ends with the Settings page's QObject lifetime.
    qt_app.screenAdded.emit(qt_app.primaryScreen())


def test_onboarding_and_arrange_use_effective_physical_selection(tmp_path, monkeypatch):
    from PySide6.QtCore import QRect, QSize
    from ui.onboarding import basic_pages, arrange
    from ui.onboarding.state import route_widgets_to_single_display
    manager, live = make_manager(tmp_path, monkeypatch)
    manager.set('display.show_on_monitors', [2])
    live[0] = (B, A)
    screens = [SimpleNamespace(name=lambda value=identity: value, geometry=lambda: QRect(0, 0, 100, 100),
                               devicePixelRatio=lambda: 1.0) for identity in live[0]]
    monkeypatch.setattr(basic_pages.QGuiApplication, 'screens', staticmethod(lambda: screens))
    monkeypatch.setattr(arrange, 'get_screen_signature', lambda screen: B if screen is screens[0] else A)
    monkeypatch.setattr(arrange, 'get_screen_signature_aliases', lambda screen: ())
    monkeypatch.setattr(arrange, 'screen_device_size', lambda screen: (100, 100))
    page = basic_pages.DisplaysPage(manager)
    try:
        assert page.checks[0].isChecked() and not page.checks[1].isChecked()
        assert manager.get('display.show_on_monitors') == [2]
        displays = arrange.ArrangePage._live_displays(SimpleNamespace(settings=manager))
        assert len(displays) == 1 and displays[0].monitor_route == '1'
        assert route_widgets_to_single_display(manager)
        assert manager.get('widgets.clock.monitor') == '1'
        assert manager.get('widgets.monitor_bindings')['clock']['screen'] == B
    finally:
        page.deleteLater()



def test_actual_gui_zero_screens_captures_unresolved_migration(tmp_path, monkeypatch):
    manager, live = make_manager(tmp_path, monkeypatch, screens=(), profile='Screensaver_MC')
    assert manager.get(BINDINGS_KEY) == {'2': None}
    live[0] = (A, B)
    assert admitted(manager, live) == set()
    manager.set('display.show_on_monitors', [2])
    assert admitted(manager, live) == {1}


def test_bulk_authoring_and_binding_only_import_remain_coherent(tmp_path, monkeypatch):
    manager, live = make_manager(tmp_path, monkeypatch)
    manager.set('display', {'show_on_monitors': [2], 'mode': 'fit'})
    assert manager.get(BINDINGS_KEY) == {'2': B}
    live[0] = (B, A)
    manager.set_many({'display.mode': 'fill', 'display.show_on_monitors': [2]})
    assert manager.get(BINDINGS_KEY) == {'2': A}
    incoming = tmp_path / 'bindings.sst'
    incoming.write_text(json.dumps({'display': {'monitor_bindings': {'99': C, '2': B}}}))
    assert manager.import_from_sst(str(incoming))
    assert manager.get(BINDINGS_KEY) == {'2': B}
    assert admitted(manager, live) == {0}
    manager.set_section('display', {'show_on_monitors': 'NONE'})
    assert manager.get(BINDINGS_KEY) == {}


def test_without_gui_legacy_capture_is_deferred(tmp_path, monkeypatch):
    from PySide6.QtGui import QGuiApplication
    manager, live = make_manager(tmp_path, monkeypatch)
    manager._settings.setValue('display.show_on_monitors', [2])
    manager._settings.setValue(BINDINGS_KEY, {})
    manager._clear_cache_locked()
    live[0] = ()
    with monkeypatch.context() as context:
        context.setattr(QGuiApplication, 'instance', staticmethod(lambda: None))
        manager.ensure_display_monitor_bindings()
        assert manager.get(BINDINGS_KEY) == {}
    live[0] = (A, B)
    manager.ensure_display_monitor_bindings()
    assert manager.get(BINDINGS_KEY) == {'2': B}


def test_bulk_selection_observers_see_coherent_imported_binding(tmp_path, monkeypatch):
    manager, live = make_manager(tmp_path, monkeypatch)
    observed = []
    manager.settings_changed.connect(lambda key, value: observed.append(resolve_monitor_numbers(manager))
                                     if key == 'display.show_on_monitors' else None)
    manager.set_many({'display.show_on_monitors': [1], 'display.monitor_bindings': {'1': B}})
    assert observed == [frozenset({2})]


def test_silent_display_section_write_preserves_notification_contract(tmp_path, monkeypatch):
    manager, live = make_manager(tmp_path, monkeypatch)
    observed = []
    manager.settings_changed.connect(lambda key, value: observed.append(key))
    manager.set_section('display', {'show_on_monitors': [2], 'mode': 'fit'}, emit_change=False)
    assert observed == []
    assert manager.get('display.mode') == 'fit'
    assert manager.get(BINDINGS_KEY) == {'2': B}


@pytest.mark.parametrize('number', [1, 2])
def test_draft_authoring_preview_routes_and_commit_keep_one_physical_target(tmp_path, monkeypatch, number):
    from PySide6.QtCore import QRect
    from ui.onboarding import basic_pages, arrange
    from ui.onboarding.draft import SettingsDraft
    from ui.onboarding.state import current_setup_summary, route_widgets_to_single_display
    manager, live = make_manager(tmp_path, monkeypatch)
    manager.set('display.show_on_monitors', [2])
    live[0] = (B, A)
    draft = SettingsDraft(manager)
    draft.set('display.show_on_monitors', [number])
    target = live[0][number - 1]
    assert draft.get(BINDINGS_KEY) == {str(number): target}
    assert manager.get(BINDINGS_KEY) == {'2': B}
    screens = [SimpleNamespace(name=lambda value=identity: value, geometry=lambda: QRect(0, 0, 100, 100),
                               devicePixelRatio=lambda: 1.0) for identity in live[0]]
    monkeypatch.setattr(basic_pages.QGuiApplication, 'screens', staticmethod(lambda: screens))
    monkeypatch.setattr(arrange, 'get_screen_signature', lambda screen: B if screen is screens[0] else A)
    monkeypatch.setattr(arrange, 'get_screen_signature_aliases', lambda screen: ())
    monkeypatch.setattr(arrange, 'screen_device_size', lambda screen: (100, 100))
    page = basic_pages.DisplaysPage(draft)
    try:
        assert page.checks[number - 1].isChecked()
        displayed = arrange.ArrangePage._live_displays(SimpleNamespace(settings=draft))
        assert [screen.identity for screen in displayed] == [target]
        assert current_setup_summary(draft)['displays'] == [number]
        route_widgets_to_single_display(draft)
        assert draft.get('widgets.monitor_bindings')['clock']['screen'] == target
        live[0] = (A,) if target == B else (B,)
        assert resolve_monitor_numbers(draft) == set()
        assert current_setup_summary(draft)['displays'] == []
        assert current_setup_summary(draft)['unavailable_displays'] == 1
        draft.commit()
        assert manager.get(BINDINGS_KEY) == {str(number): target}
        assert manager.get('widgets.monitor_bindings')['clock']['screen'] == target
        assert admitted(manager, live) == set()
        live[0] = (target,)
        assert resolve_monitor_numbers(manager) == {1}
    finally:
        page.deleteLater()


def test_ready_summary_reports_current_and_missing_displays(tmp_path, monkeypatch):
    from ui.onboarding.selection_pages import ReadyPage
    manager, live = make_manager(tmp_path, monkeypatch)
    manager.set('display.show_on_monitors', [2])
    text = []
    owner = SimpleNamespace(settings=manager, summary=SimpleNamespace(setText=text.append))
    live[0] = (B, A)
    ReadyPage.refresh(owner)
    assert text[-1].splitlines()[0] == 'Displays: 1'
    live[0] = (A,)
    ReadyPage.refresh(owner)
    assert text[-1].splitlines()[0] == 'Displays: Selected displays unavailable'
    manager.set('display.show_on_monitors', 'NONE')
    ReadyPage.refresh(owner)
    assert text[-1].splitlines()[0] == 'Displays: No displays'
    manager.set('display.show_on_monitors', 'ALL')
    ReadyPage.refresh(owner)
    assert text[-1].splitlines()[0] == 'Displays: All displays'
