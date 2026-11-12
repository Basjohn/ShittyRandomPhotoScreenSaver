"""Retired Widget Theme colour roles: the load bridge and the absence of every declaration.

A role the schema no longer declares (``RETIRED_WIDGET_THEME_COLOR_ROLES``) may still sit in a
user's theme file or stored Custom snapshot. The loader drops it silently; nothing declares,
generates or edits it again (Docs/Architecture/Persisted_Input_Compatibility.md).
"""

from __future__ import annotations

import json
from pathlib import Path
import shutil

from tools.generate_widget_theme_mirrors import (
    drop_retired_widget_theme_roles,
    mirrored_widget_theme,
)
from tools.widget_theme_foundry_model import all_widget_theme_roles
from ui.settings_theme_io import load_settings_theme_file
from ui.widget_theme_io import (
    RETIRED_WIDGET_THEME_COLOR_ROLES,
    load_widget_theme_file,
    load_widget_theme_or_default,
    widget_theme_from_payload,
    widget_theme_to_json,
)
from ui.widget_theme_spec import DEFAULT_DARK_WIDGET_THEME, WIDGET_THEME_CORE_COLOR_ROLES
from ui.widget_visual_roles import WIDGET_THEME_OPTIONAL_COLOR_ROLES, WIDGET_VISUAL_ROLE_PARENTS


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "widget_theme_retired_context_menu_arrow.srwtheme"


def _raw_colors(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))["colors"]


def test_a_theme_file_carrying_a_retired_role_loads_and_drops_it() -> None:
    raw = _raw_colors(FIXTURE)
    carried = set(raw) & RETIRED_WIDGET_THEME_COLOR_ROLES
    assert carried, "the fixture is the old file shape: it must carry a retired role"

    result = load_widget_theme_or_default(FIXTURE)
    assert result.loaded_from_file and result.error is None
    theme = result.theme
    assert not set(theme.colors) & RETIRED_WIDGET_THEME_COLOR_ROLES
    # Every other role is kept exactly.
    assert {role: color.as_list() for role, color in theme.colors.items()} == {
        role: value for role, value in raw.items() if role not in RETIRED_WIDGET_THEME_COLOR_ROLES
    }

    # Nothing writes it again, and a second load is a no-op.
    text = widget_theme_to_json(theme)
    assert not set(json.loads(text)["colors"]) & RETIRED_WIDGET_THEME_COLOR_ROLES
    payload = json.loads(text)
    assert widget_theme_from_payload(payload) == theme


def test_a_stored_custom_snapshot_carrying_a_retired_role_loads_and_drops_it() -> None:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    payload["theme_id"] = "custom"
    theme = widget_theme_from_payload(payload)
    assert not set(theme.colors) & RETIRED_WIDGET_THEME_COLOR_ROLES


def test_no_retired_role_is_declared_generated_or_shipped() -> None:
    retired = RETIRED_WIDGET_THEME_COLOR_ROLES
    assert retired
    assert not retired & WIDGET_THEME_CORE_COLOR_ROLES
    assert not retired & WIDGET_THEME_OPTIONAL_COLOR_ROLES
    assert not retired & (set(WIDGET_VISUAL_ROLE_PARENTS) | set(WIDGET_VISUAL_ROLE_PARENTS.values()))
    assert not retired & set(DEFAULT_DARK_WIDGET_THEME.colors)
    assert not retired & set(all_widget_theme_roles()), "the Theme Foundry must not offer a retired role"
    for settings_path in sorted((ROOT / "themes").glob("*.srtheme")):
        mirror = mirrored_widget_theme(
            load_settings_theme_file(settings_path),
            settings_theme_id=f"file:{settings_path.name}",
            widget_theme_id=f"mirror:file:{settings_path.name}",
        )
        assert not retired & set(mirror.colors), settings_path.name
    for widget_path in sorted((ROOT / "themes" / "widgets").glob("*.srwtheme")):
        assert not retired & set(_raw_colors(widget_path)), widget_path.name


def test_the_generator_drops_retired_roles_from_files_once(tmp_path: Path) -> None:
    widgets = tmp_path / "widgets"
    widgets.mkdir()
    target = widgets / "Old.srwtheme"
    shutil.copyfile(FIXTURE, target)
    expected = widget_theme_to_json(load_widget_theme_file(FIXTURE))

    assert drop_retired_widget_theme_roles(tmp_path) == (target,)
    assert target.read_bytes().decode("utf-8").replace("\r\n", "\n") == expected
    assert drop_retired_widget_theme_roles(tmp_path) == ()
