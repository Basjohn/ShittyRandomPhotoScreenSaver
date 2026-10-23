"""Theme Sorter tests use ONLY test-owned theme pairs in tmp_path."""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import pytest

from tools.theme_sorter_model import (
    ThemeSorterError, delete_theme_pair, list_theme_pairs, rename_theme_pair,
)
from tools.generate_widget_theme_mirrors import widget_counterpart_for_settings_theme
from ui.settings_theme_io import load_settings_theme_file, save_settings_theme_file
from ui.settings_theme_spec import DEFAULT_DARK_SETTINGS_THEME, Rgba
from ui.widget_theme_io import load_widget_theme_file, save_widget_theme_file


def _pair(root: Path, name: str, *, widget: bool = True):
    colors = dict(DEFAULT_DARK_SETTINGS_THEME.colors)
    colors['panel.border'] = Rgba(31, 47, 63, 91)  # fixture-owned distinguishable role
    settings = replace(DEFAULT_DARK_SETTINGS_THEME, name=name, colors=colors)
    source = save_settings_theme_file(settings, root / f'{name}.srtheme')
    if widget:
        counterpart = widget_counterpart_for_settings_theme(settings, settings_theme_id=f'file:{source.name}')
        save_widget_theme_file(counterpart, root / 'widgets' / f'{name}.srwtheme')
    return source


def test_listing_discovers_actual_authored_pair_and_missing_counterpart(tmp_path):
    _pair(tmp_path, 'Original')
    _pair(tmp_path, 'Solo', widget=False)
    pairs = list_theme_pairs(tmp_path)
    assert {p.name for p in pairs} == {'Original', 'Solo'}
    assert next(p for p in pairs if p.name == 'Original').widget_path is not None
    assert next(p for p in pairs if p.name == 'Solo').widget_path is None


def test_rename_relinks_existing_widget_without_replacing_authored_roles(tmp_path):
    src = _pair(tmp_path, 'Copper')
    old_widget = load_widget_theme_file(tmp_path / 'widgets' / 'Copper.srwtheme')
    updated = rename_theme_pair(tmp_path, src.name, 'Sea Glass [Glass]')
    assert not src.exists()
    assert not (tmp_path / 'widgets' / 'Copper.srwtheme').exists()
    assert updated.settings_path.name == 'Sea Glass [Glass].srtheme'
    assert updated.widget_path.name == 'Sea Glass.srwtheme'
    setting = load_settings_theme_file(updated.settings_path)
    widget = load_widget_theme_file(updated.widget_path)
    assert setting.name == 'Sea Glass [Glass]'
    assert widget.linked_settings_theme_id == 'file:Sea Glass [Glass].srtheme'
    assert widget.theme_id == 'mirror:file:Sea Glass [Glass].srtheme'
    assert widget.colors == old_widget.colors  # no regeneration of existing authored counterpart
    assert setting.color('panel.border') == Rgba(31, 47, 63, 91)


def test_rename_missing_widget_creates_valid_linked_counterpart(tmp_path):
    src = _pair(tmp_path, 'Unpaired', widget=False)
    updated = rename_theme_pair(tmp_path, src.name, 'New One')
    widget = load_widget_theme_file(updated.widget_path)
    assert widget.linked_settings_theme_id == 'file:New One.srtheme'
    assert widget.colors['card.border'] == Rgba(31, 47, 63, 91)


def test_delete_removes_only_selected_linked_pair(tmp_path):
    one = _pair(tmp_path, 'One')
    two = _pair(tmp_path, 'Two')
    removed = delete_theme_pair(tmp_path, one.name)
    assert len(removed) == 2
    assert not one.exists()
    assert not (tmp_path / 'widgets' / 'One.srwtheme').exists()
    assert two.exists()
    assert (tmp_path / 'widgets' / 'Two.srwtheme').exists()


def test_delete_unpaired_theme_is_safe(tmp_path):
    src = _pair(tmp_path, 'Solo', widget=False)
    removed = delete_theme_pair(tmp_path, src.name)
    assert removed == (src,)
    assert not src.exists()


def test_refuses_conflicts_and_unsafe_names_without_mutation(tmp_path):
    src = _pair(tmp_path, 'First')
    other = _pair(tmp_path, 'Second')
    with pytest.raises(ThemeSorterError):
        rename_theme_pair(tmp_path, src.name, 'Second')
    for candidate in ('', '../escape', 'illegal|name', 'A'*151, 'bad.'):
        with pytest.raises(ThemeSorterError):
            rename_theme_pair(tmp_path, src.name, candidate)
    assert src.exists() and other.exists()


def test_refuses_ambiguous_widget_links(tmp_path):
    src = _pair(tmp_path, 'First')
    spec = load_widget_theme_file(tmp_path / 'widgets' / 'First.srwtheme')
    spec = replace(spec, theme_id='custom:duplicate')
    save_widget_theme_file(spec, tmp_path / 'widgets' / 'Alternative.srwtheme')
    with pytest.raises(ThemeSorterError, match='Ambiguous'):
        rename_theme_pair(tmp_path, src.name, 'Elsewhere')
    assert src.exists()


def test_builtin_default_mirror_is_not_a_deletable_authored_theme(tmp_path):
    save_settings_theme_file(DEFAULT_DARK_SETTINGS_THEME, tmp_path / 'Default Dark.srtheme')
    assert list_theme_pairs(tmp_path) == ()
    with pytest.raises(ThemeSorterError):
        delete_theme_pair(tmp_path, 'Default Dark.srtheme')


def test_failed_second_file_commit_rolls_back_original_pair(tmp_path, monkeypatch):
    source = _pair(tmp_path, 'Original')
    widget = tmp_path / 'widgets' / 'Original.srwtheme'
    before_source = source.read_bytes()
    before_widget = widget.read_bytes()
    real_replace = Path.replace

    def fail_one_staged_commit(self, target):
        if self.name == 'new-1':
            raise OSError('Injected failure writing linked Widget file')
        return real_replace(self, target)

    monkeypatch.setattr(Path, 'replace', fail_one_staged_commit)
    with pytest.raises(ThemeSorterError, match='rolled back'):
        rename_theme_pair(tmp_path, source.name, 'Renamed')
    assert source.read_bytes() == before_source
    assert widget.read_bytes() == before_widget
    assert not (tmp_path / 'Renamed.srtheme').exists()
    assert not list(tmp_path.glob('.theme-sorter-transaction-*'))
