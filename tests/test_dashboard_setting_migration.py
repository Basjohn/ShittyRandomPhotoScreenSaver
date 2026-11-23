import json
from core.settings.json_store import JsonSettingsStore
from core.settings.sst_io import normalize_sst_snapshot


def test_old_json_dashboard_setting_promotes_and_persists(tmp_path):
    path = tmp_path / 'settings.json'
    path.write_text(json.dumps({'snapshot': {'mc': {'always_on_top': False}}}), encoding='utf-8')
    store = JsonSettingsStore(storage_path=path, profile='Dashboard')
    assert store.value('dashboard.always_on_top') is False
    assert not store.contains('mc.always_on_top')
    assert store.flush(timeout=5)
    saved = json.loads(path.read_text(encoding='utf-8'))['snapshot']
    assert saved['dashboard']['always_on_top'] is False
    assert 'mc' not in saved

    conflict = tmp_path / 'conflict.json'
    conflict.write_text(json.dumps({'snapshot': {'mc': {'always_on_top': False},
                                                 'dashboard': {'always_on_top': True}}}), encoding='utf-8')
    current = JsonSettingsStore(storage_path=conflict, profile='Dashboard')
    assert current.value('dashboard.always_on_top') is True
    assert not current.contains('mc.always_on_top')


def test_sst_import_promotes_legacy_and_current_value_wins(tmp_path):
    assert normalize_sst_snapshot({'mc': {'always_on_top': False}})['dashboard']['always_on_top'] is False
    result = normalize_sst_snapshot({'mc': {'always_on_top': False}, 'dashboard': {'always_on_top': True}})
    assert result['dashboard']['always_on_top'] is True
    assert 'mc' not in result

    from core.settings.settings_manager import SettingsManager
    from core.settings.default_contract import require_canonical_default
    manager = SettingsManager(application='Dashboard', storage_base_dir=tmp_path / 'profile')
    path = tmp_path / 'old.sst'
    path.write_text(json.dumps({'snapshot': {'mc': {'always_on_top': False}}}), encoding='utf-8')
    assert manager.import_from_sst(str(path))
    assert manager.get('dashboard.always_on_top') is False
    assert not manager._settings.contains('mc.always_on_top')
    manager.reset_to_defaults()
    assert manager.get('dashboard.always_on_top') == require_canonical_default('dashboard.always_on_top', 'Dashboard')


def test_old_qsettings_values_are_promoted(tmp_path, monkeypatch):
    from types import SimpleNamespace
    import core.settings.settings_manager as module
    class OldSettings:
        def __init__(self, organization, application):
            pass
        def allKeys(self):
            return ['mc.always_on_top']
        def value(self, key):
            return False
    monkeypatch.setattr(module, 'QSettings', OldSettings)
    store = JsonSettingsStore(storage_path=tmp_path / 'settings.json', profile='Dashboard')
    manager = SimpleNamespace(_settings=store, _to_plain_value=lambda value: value,
                              _write_migration_backup=lambda data: None)
    assert module.SettingsManager._migrate_from_qsettings(manager, 'Org', 'Screensaver_MC')
    assert store.value('dashboard.always_on_top') is False
    assert not store.contains('mc.always_on_top')
