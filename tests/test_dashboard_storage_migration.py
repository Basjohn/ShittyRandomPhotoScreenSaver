from core.settings.json_store import determine_storage_path


def test_dashboard_migrates_old_directory_and_preserves_contents(tmp_path):
    old = tmp_path / 'SRPSS_MC'
    (old / 'backups').mkdir(parents=True)
    (old / 'settings_v2.json').write_text('settings', encoding='utf-8')
    (old / 'backups' / 'copy').write_text('backup', encoding='utf-8')
    path = determine_storage_path('Dashboard', base_dir=tmp_path)
    assert path == tmp_path / 'SRPSS_Dashboard' / 'settings_v2.json'
    assert path.read_text(encoding='utf-8') == 'settings'
    assert (path.parent / 'backups' / 'copy').read_text(encoding='utf-8') == 'backup'
    assert not old.exists()


def test_dashboard_conflict_keeps_both_directories_and_uses_destination(tmp_path, caplog):
    old = tmp_path / 'SRPSS_MC'
    new = tmp_path / 'SRPSS_Dashboard'
    old.mkdir()
    new.mkdir()
    (old / 'settings_v2.json').write_text('old', encoding='utf-8')
    (new / 'settings_v2.json').write_text('new', encoding='utf-8')
    path = determine_storage_path('Dashboard', base_dir=tmp_path)
    assert path.read_text(encoding='utf-8') == 'new'
    assert (old / 'settings_v2.json').read_text(encoding='utf-8') == 'old'
    assert 'migration' in caplog.text.lower()


def test_dashboard_migration_failure_is_logged_and_does_not_select_old_path(tmp_path, monkeypatch, caplog):
    import pytest
    import core.settings.json_store as store
    if store.os.name != 'nt':
        pytest.skip('Windows rename failure path')
    old = tmp_path / 'SRPSS_MC'
    old.mkdir()
    def denied(*args):
        raise PermissionError('denied')
    monkeypatch.setattr(store.os, 'rename', denied)
    with pytest.raises(PermissionError):
        store.determine_storage_path('Dashboard', base_dir=tmp_path)
    assert old.exists()
    assert 'migration failed' in caplog.text.lower()

