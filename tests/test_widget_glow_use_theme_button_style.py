from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DISPLAY_TAB = ROOT / "ui" / "tabs" / "display_tab.py"
SHARED_STYLES = ROOT / "ui" / "tabs" / "shared_styles.py"


def test_widget_glow_use_theme_uses_canonical_compact_action_style() -> None:
    source = DISPLAY_TAB.read_text(encoding="utf-8")
    anchor = 'self.widget_glow_use_theme_btn = OutlinedButton("Use Theme", role="secondary")'
    start = source.index(anchor)
    block = source[start : start + 900]

    # The secondary OutlinedButton role is the compact action style with a
    # seam-free painted border (ui/widgets/outlined_button.py).
    from ui.widgets.outlined_button import _ROLES
    assert _ROLES["secondary"][0] == "COMPACT_ACTION_BUTTON_STYLE"
    assert "self.widget_glow_use_theme_btn.setFixedHeight(30)" in block


def test_compact_action_style_is_shared_theme_backed_button_contract() -> None:
    source = SHARED_STYLES.read_text(encoding="utf-8")
    assert "COMPACT_ACTION_BUTTON_STYLE = _build_compact_action_button_style()" in source
    assert "'control.button.surface'" in source
    assert "'control.button.text'" in source
    assert "'control.button.border'" in source
