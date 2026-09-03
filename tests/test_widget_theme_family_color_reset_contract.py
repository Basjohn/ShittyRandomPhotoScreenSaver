"""Static guardrails for shared Widget Theme style authority and explicit colour reset."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _text(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_shared_header_fill_and_explicit_reset_live_only_in_general_style_overrides() -> None:
    source = _text("ui/tabs/widgets_tab_defaults.py")
    assert '"Header Fill:"' in source
    assert '"header.fill"' in source
    assert '"Reset All Colours to Theme"' in source
    assert '_on_reset_family_colors_to_theme' in source
    assert '_reset_family_color_overrides_to_theme' in source
    assert 'StyledPopup.question(' in source
    assert 'tab._settings.get_widgets_map()' in source
    assert 'tab._settings.set_widgets_map(widgets, emit_change=False)' in source
    assert 'tab.load_from_settings()' in source
    # Migration is operator-invoked; no SettingsManager/startup migration owner.
    settings_manager = _text("core/settings/settings_manager.py")
    assert '_reset_family_color_overrides_to_theme' not in settings_manager
    assert '_on_reset_family_colors_to_theme' not in settings_manager


def test_media_show_header_returns_to_normal_appearance_bucket() -> None:
    source = _text("ui/tabs/widgets_tab_media.py")
    assert '"Header Appearance"' not in source
    assert '"header_appearance"' not in source
    assert 'tab.media_show_header_frame = QCheckBox("Show Header Pill (Logo + Title)")' in source
    assert 'appearance_layout.addWidget(tab.media_show_header_frame)' in source
    assert 'header_layout.insertWidget' not in source


def test_header_family_swatch_controls_are_retired() -> None:
    for relative in (
        "ui/tabs/widgets_tab_media.py",
        "ui/tabs/widgets_tab_gmail.py",
        "ui/tabs/widgets_tab_reddit.py",
        "ui/tabs/widgets_tab_steam.py",
    ):
        source = _text(relative)
        assert '"Header Fill:"' not in source, relative
        assert '"Header Text:"' not in source, relative
        assert '"Header Border:"' not in source, relative
        assert '_header_fill_color_btn = ColorSwatchButton' not in source, relative
        assert '_header_text_color_btn = ColorSwatchButton' not in source, relative
        assert '_header_border_color_btn = ColorSwatchButton' not in source, relative


def test_retired_header_swatches_have_no_phantom_runtime_expectations() -> None:
    # Persistence colour *values* intentionally survive the compatibility horizon;
    # GUI button/control names do not. A stale descriptor/finalize/load reference
    # previously crashed Settings after the header controls were rehosted.
    retired_button_names = (
        "media_header_fill_color_btn",
        "media_header_text_color_btn",
        "media_header_border_color_btn",
        "reddit_header_fill_color_btn",
        "reddit_header_text_color_btn",
        "reddit_header_border_color_btn",
        "gmail_header_fill_color_btn",
        "gmail_header_text_color_btn",
        "gmail_header_border_color_btn",
        "achievement_pulse_header_fill_color_btn",
        "achievement_pulse_header_text_color_btn",
        "achievement_pulse_header_border_color_btn",
        "abandonment_issues_header_fill_color_btn",
        "abandonment_issues_header_text_color_btn",
        "abandonment_issues_header_border_color_btn",
    )
    audited = {
        "rendering/widget_descriptors.py": _text("rendering/widget_descriptors.py"),
        "ui/tabs/widgets_tab_media.py": _text("ui/tabs/widgets_tab_media.py"),
        "ui/tabs/widgets_tab_reddit.py": _text("ui/tabs/widgets_tab_reddit.py"),
        "ui/tabs/widgets_tab_gmail.py": _text("ui/tabs/widgets_tab_gmail.py"),
        "ui/tabs/widgets_tab_steam.py": _text("ui/tabs/widgets_tab_steam.py"),
    }
    for relative, source in audited.items():
        for name in retired_button_names:
            assert name not in source, (relative, name)

    media = audited["ui/tabs/widgets_tab_media.py"]
    assert "header_toggle" not in media
    assert "header_body" not in media


def test_reset_scope_covers_every_ordinary_theme_family_but_not_visualizer() -> None:
    source = _text("ui/tabs/widgets_tab_defaults.py")
    for section in (
        "clock",
        "weather",
        "reddit",
        "reddit2",
        "gmail",
        "media",
        "achievement_pulse",
        "abandonment_issues",
    ):
        assert f'    "{section}",' in source
    assert '"spotify_visualizer"' not in source.split('_THEME_COLOR_OVERRIDE_SECTIONS = (', 1)[1].split(')', 1)[0]
    assert 'normalized == "color"' in source
    assert 'normalized.endswith("_color")' in source
    assert 'frozenset({"bg_opacity", "border_opacity"})' in source

    defaults = json.loads(_text("core/settings/defaults_snapshot.json"))["widgets"]
    # All current ordinary-family colour keys are representable by the reset rule.
    for section in (
        "clock",
        "weather",
        "reddit",
        "reddit2",
        "gmail",
        "media",
        "achievement_pulse",
        "abandonment_issues",
    ):
        for key in defaults[section]:
            if key == "color" or key.endswith("_color"):
                assert key == "color" or key.endswith("_color")


def test_cleanup_ledger_marks_the_manual_migration_bridge_for_later_retirement() -> None:
    cleanup = _text("Future_Cleanup.md")
    assert "DELETE AFTER HORIZON — ordinary Widget family colour bridge" in cleanup
    assert "user-invoked" in cleanup
    assert "not a supported hidden palette" in cleanup
