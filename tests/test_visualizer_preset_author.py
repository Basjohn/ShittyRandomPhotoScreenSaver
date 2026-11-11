"""The preset author tool admits a mode's record keys (a shape...) through the spec's one record admission."""
from __future__ import annotations

import pytest

from core.settings.defaults import get_default_settings
from core.settings.visualizer_mode_settings import Custom, iter_mode_settings
from tools import visualizer_preset_author as author


def _record_keys_with_admission():
    """Every (mode, key) a spec's Custom row owns and admits through its own declared admission."""
    return [(spec.mode_id, key) for spec in iter_mode_settings() for entry in spec.entries
            if isinstance(entry, Custom) and entry.admit for key in entry.keys]


def test_some_spec_declares_an_admitted_record_key():
    assert _record_keys_with_admission()


@pytest.mark.parametrize(("mode", "key"), _record_keys_with_admission())
def test_the_tool_admits_a_record_key_the_spec_admits(mode, key):
    defaults = get_default_settings()["widgets"]["spotify_visualizer"]
    value = defaults[key]
    admitted = author._admitted(mode, {key: value})
    assert list(admitted) == [key]
    assert admitted[key] == value


def test_the_tool_refuses_a_record_value_the_spec_admits_differently():
    """A record value the spec's admission rewrites (repairs, clamps, falls back) is refused, never authored."""
    from core.settings.visualizer_mode_settings import require_mode_settings

    defaults = get_default_settings()["widgets"]["spotify_visualizer"]
    junk = "not a record"
    rewritten = [(mode, key) for mode, key in _record_keys_with_admission()
                 if require_mode_settings(mode).admit_custom(key, junk, defaults[key]) != junk]
    assert rewritten
    for mode, key in rewritten:
        with pytest.raises(ValueError, match="the spec admits"):
            author._admitted(mode, {key: junk})


def test_the_tool_still_refuses_a_key_the_spec_does_not_know():
    mode, _key = _record_keys_with_admission()[0]
    with pytest.raises(ValueError, match="has no Settings control"):
        author._admitted(mode, {f"{mode}_no_such_setting_anywhere": 1})
