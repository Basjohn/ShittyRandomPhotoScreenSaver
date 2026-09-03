"""Qt-free usability contracts for Theme Foundry's human-first authoring view."""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FOUNDRY = ROOT / "tools" / "theme_foundry.py"
MODEL = ROOT / "tools" / "theme_foundry_model.py"
SPEC = ROOT / "ui" / "settings_theme_spec.py"


def _ann_assignment_value(path: Path, name: str):
    module = ast.parse(path.read_text(encoding="utf-8"))
    for node in module.body:
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == name:
            return node.value
    raise AssertionError(f"{name} not found in {path}")


def _default_color_roles() -> set[str]:
    value = _ann_assignment_value(SPEC, "_DEFAULT_DARK_COLORS")
    assert isinstance(value, ast.Dict)
    return {ast.literal_eval(key) for key in value.keys if key is not None}


def test_everyday_view_is_curated_from_real_settings_roles_only() -> None:
    value = _ann_assignment_value(MODEL, "EVERYDAY_THEME_ROLE_GROUPS")
    groups = ast.literal_eval(value)
    roles = [role for _group, group_roles in groups for role in group_roles]

    assert 35 <= len(roles) <= 80  # human-first, not another complete schema dump
    assert len(roles) == len(set(roles))
    assert set(roles) <= _default_color_roles()
    assert {group for group, _roles in groups} == {
        "Surfaces & Panels",
        "Text",
        "Borders & Separators",
        "Accent & Selection",
        "Controls",
    }


def test_foundry_defaults_to_human_view_but_preserves_complete_advanced_schema() -> None:
    source = FOUNDRY.read_text(encoding="utf-8")
    assert 'self.role_view.addItems(["Everyday", "All Roles"])' in source
    assert 'self._prefs.get("role_view", "Everyday")' in source
    assert 'self.changed_opened_only = QCheckBox("Changed from Opened")' in source
    assert 'self.differs_default_only = QCheckBox("Differs from Default")' in source
    assert "everyday_theme_role_group(kind, token)" in source
    assert 'raw_entries += [("color", token) for token in self.draft.colors]' in source
    assert 'raw_entries += [("shadow", token) for token in self.draft.shadows]' in source
    assert 'raw_entries += [("gradient", token) for token in self.draft.gradients]' in source
    assert "self.tree.setColumnHidden(self.COL_OPENED, not advanced)" in source
    assert "self.tree.setColumnHidden(self.COL_DEFAULT, not advanced)" in source


def test_widget_foundry_usability_lessons_are_present_without_a_second_theme_schema() -> None:
    source = FOUNDRY.read_text(encoding="utf-8")
    assert "discover_settings_theme_files" in source
    assert 'self.open_selected_btn = QPushButton("OPEN SELECTED")' in source
    assert 'self.color_hex_edit.setPlaceholderText("#RRGGBB or #RRGGBBAA")' in source
    assert 'self.color_copy_rgba_btn = QPushButton("COPY RGBA")' in source
    assert "replace_matching_color_roles" in source
    assert "most_used_colors" in source
    assert '"SRPSSTheme.ico"' in source

    # Existing authority/safety stays intact.
    assert "save_settings_theme_file" in source
    assert "load_settings_theme_file" in source
    assert "settings_theme_to_json" in source
    assert "settings_theme_from_json" in source
    assert "class SettingsThemeSpec" not in source
    assert "_DEFAULT_DARK_COLORS" not in source


def test_relationship_jump_can_escape_everyday_view_instead_of_looking_broken() -> None:
    source = FOUNDRY.read_text(encoding="utf-8")
    assert 'if target is None and self.role_view.currentText() == "Everyday":' in source
    assert 'self.role_view.setCurrentText("All Roles")' in source
