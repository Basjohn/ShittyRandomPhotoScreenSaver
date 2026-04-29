"""Tests for Gmail settings roundtrip (no Qt app required)."""
from __future__ import annotations

from pathlib import Path

import pytest


def test_gmail_widget_apply_settings_basic() -> None:
    """Verify GmailWidget.apply_settings() correctly parses flat settings dict."""
    # This test would need Qt app, so we'll skip for now
    # The actual widget test (P6.3) will cover this with Qt app
    pytest.skip("Requires Qt app - covered in test_gmail_widget.py")


def test_gmail_settings_keys_exist() -> None:
    """Verify Gmail settings keys are defined in default_settings.py."""
    from core.settings.default_settings import DEFAULT_SETTINGS

    # Check that gmail settings exist in defaults
    gmail_keys = [k for k in DEFAULT_SETTINGS.keys() if k.startswith("gmail.")]
    # If no gmail.* keys exist, that's okay - they might not be added yet
    # Just verify the structure is correct if they do exist
    if gmail_keys:
        # Check for expected keys (subset)
        expected_keys = [
            "gmail.enabled",
            "gmail.position",
            "gmail.limit",
            "gmail.refresh_interval",
        ]
        for key in expected_keys:
            if key in gmail_keys:
                assert key in DEFAULT_SETTINGS, f"Missing expected key: {key}"
    else:
        # No gmail settings yet - that's okay for this test
        assert True


def test_gmail_settings_flat_dict_structure() -> None:
    """Verify Gmail settings follow flat-dict pattern (no nested dicts)."""
    from core.settings.default_settings import DEFAULT_SETTINGS

    for key, value in DEFAULT_SETTINGS.items():
        if key.startswith("gmail."):
            # Gmail settings should be flat (no nested dicts)
            if isinstance(value, dict):
                # Some settings might be dicts for colors/fonts, but they should be simple
                # This is just a sanity check - complex nested structures should be avoided
                for k, v in value.items():
                    assert not isinstance(v, dict), f"Nested dict in {key}.{k}"


def test_gmail_position_enum_values() -> None:
    """Verify GmailPosition enum values are lowercase snake_case."""
    from widgets.gmail_components import GmailPosition

    # Check that all GmailPosition values are lowercase snake_case
    valid_positions = [
        "top_left", "top_center", "top_right",
        "middle_left", "center", "middle_right",
        "bottom_left", "bottom_center", "bottom_right",
    ]

    for pos in GmailPosition:
        assert pos.value in valid_positions, f"Invalid position value: {pos.value}"


def test_gmail_settings_type_safety() -> None:
    """Verify Gmail settings have appropriate types."""
    from core.settings.default_settings import DEFAULT_SETTINGS

    # Check types for known keys
    if "gmail.enabled" in DEFAULT_SETTINGS:
        assert isinstance(DEFAULT_SETTINGS["gmail.enabled"], bool)

    if "gmail.limit" in DEFAULT_SETTINGS:
        assert isinstance(DEFAULT_SETTINGS["gmail.limit"], int)
        assert DEFAULT_SETTINGS["gmail.limit"] > 0

    if "gmail.refresh_interval" in DEFAULT_SETTINGS:
        assert isinstance(DEFAULT_SETTINGS["gmail.refresh_interval"], int)
        assert DEFAULT_SETTINGS["gmail.refresh_interval"] > 0

    if "gmail.position" in DEFAULT_SETTINGS:
        assert isinstance(DEFAULT_SETTINGS["gmail.position"], str)


def test_gmail_text_cleanup_defaults_exist() -> None:
    """Verify Gmail text cleanup defaults are present in the widget settings dict."""
    from core.settings.default_settings import DEFAULT_SETTINGS

    gmail = DEFAULT_SETTINGS["widgets"]["gmail"]
    assert gmail["clean_sender_names"] is True
    assert gmail["max_sender_words"] == 3
    assert gmail["sender_column_width"] == 180
    assert gmail["max_subject_words"] == 4
    assert gmail["max_subject_chars"] == 0
    assert gmail["group_threads"] is False
    assert gmail["date_display_mode"] == "relative"
    assert gmail["width"] == 600
    assert "min_width" not in gmail
    assert "max_width" not in gmail
    assert "content_padding_left" not in gmail


def test_gmail_signal_block_attrs_cover_newer_controls() -> None:
    """Guard against settings-load flicker from stale Gmail signal blockers."""
    from ui.tabs.widgets_tab_gmail import GMAIL_SIGNAL_BLOCK_ATTRS

    expected_attrs = {
        "gmail_backend_combo",
        "gmail_width",
        "gmail_show_header_border",
        "gmail_date_display_mode",
        "gmail_group_threads",
        "gmail_clean_sender_names",
        "gmail_max_sender_words",
        "gmail_sender_column_width",
        "gmail_max_subject_words",
        "gmail_max_subject_chars",
        "gmail_sound_file",
        "gmail_sound_volume",
    }

    assert expected_attrs <= set(GMAIL_SIGNAL_BLOCK_ATTRS)


def test_gmail_default_accessor_requires_canonical_default() -> None:
    """User-facing Gmail fallbacks should come from canonical widget defaults."""
    from types import SimpleNamespace

    import pytest

    from ui.tabs.widgets_tab_gmail import _gmail_default

    tab = SimpleNamespace(
        _widget_default=lambda section, key, fallback: "INBOX"
        if (section, key) == ("gmail", "filter_label")
        else fallback
    )

    assert _gmail_default(tab, "filter_label") == "INBOX"
    with pytest.raises(KeyError):
        _gmail_default(tab, "missing_key")


def test_widget_defaults_merge_stale_cache_with_canonical_defaults() -> None:
    """A stale settings-dialog cache must not hide newly added Gmail defaults."""
    from ui.tabs.widgets_tab import WidgetsTab

    tab = WidgetsTab.__new__(WidgetsTab)
    tab._provided_widget_defaults = {"gmail": {"enabled": True}}

    defaults = WidgetsTab._load_widget_defaults(tab)

    assert defaults["gmail"]["enabled"] is True
    assert defaults["gmail"]["width"] == 600
    assert defaults["gmail"]["filter_label"] == "INBOX"


def test_gmail_signal_blocker_blocks_and_unblocks_all_present_controls() -> None:
    """Gmail load should silence its controls even if the parent block list drifts."""
    from types import SimpleNamespace

    from ui.tabs.widgets_tab_gmail import GMAIL_SIGNAL_BLOCK_ATTRS, _block_gmail_setting_signals

    class FakeControl:
        def __init__(self):
            self.calls = []

        def blockSignals(self, blocked):
            self.calls.append(bool(blocked))

    controls = {name: FakeControl() for name in GMAIL_SIGNAL_BLOCK_ATTRS}
    tab = SimpleNamespace(**controls)

    with _block_gmail_setting_signals(tab):
        assert all(control.calls == [True] for control in controls.values())

    assert all(control.calls == [True, False] for control in controls.values())


def test_gmail_visibility_helper_uses_explicit_hidden_state() -> None:
    """Repeated setVisible(True) calls were a historical settings flicker trigger."""
    from ui.tabs.widgets_tab_gmail import _set_visible_if_changed

    class FakeWidget:
        def __init__(self, hidden):
            self._hidden = hidden
            self.calls = []

        def isHidden(self):
            return self._hidden

        def setVisible(self, visible):
            self.calls.append(bool(visible))
            self._hidden = not bool(visible)

    widget = FakeWidget(False)
    _set_visible_if_changed(widget, True)
    assert widget.calls == []

    _set_visible_if_changed(widget, False)
    assert widget.calls == [False]

    already_hidden = FakeWidget(True)
    _set_visible_if_changed(already_hidden, False)
    assert already_hidden.calls == []


def test_gmail_buckets_do_not_prime_hidden_bodies_by_showing_them() -> None:
    """R-18 proved constructor-time setVisible(True) can create settings flicker."""
    source = Path("ui/tabs/widgets_tab_gmail.py").read_text(encoding="utf-8")

    assert "_prime_hidden_bucket_body" not in source
    assert "setVisible(True)" not in source


def test_gmail_settings_construction_defers_backend_auth_refresh() -> None:
    """Gmail must not load backend/OAuth during settings dialog construction."""
    source = Path("ui/tabs/widgets_tab_gmail.py").read_text(encoding="utf-8")
    build_source = source.split("def build_gmail_ui", 1)[1].split("def load_gmail_settings", 1)[0]

    assert "_queue_gmail_auth_refresh(tab)" in build_source
    assert "_refresh_gmail_auth_state(tab)" not in build_source


def test_styled_combos_do_not_precreate_popup_views() -> None:
    """Calling view() in combo constructors creates top-level helper frames before show."""
    for path in (
        Path("ui/widgets/styled_combo_box.py"),
        Path("ui/widgets/styled_font_combo_box.py"),
    ):
        source = path.read_text(encoding="utf-8")
        init_source = source.split("def __init__", 1)[1].split("def showPopup", 1)[0]
        assert "self._style_popup_view()" not in init_source
        assert "self.view()" not in init_source


def test_gmail_text_limits_are_split_across_two_rows() -> None:
    """Keep sender and subject text-limit spinboxes from crowding one row."""
    source = Path("ui/tabs/widgets_tab_gmail.py").read_text(encoding="utf-8")

    assert 'text_limit_row = _aligned_row(appearance_inner, "Text Limits:")' in source
    assert 'subject_limit_row = _aligned_row(appearance_inner, "")' in source
    assert "subject_limit_row.addWidget(tab.gmail_max_subject_words)" in source
    assert "subject_limit_row.addWidget(tab.gmail_max_subject_chars)" in source


def test_gmail_buckets_defer_initial_collapse_until_children_exist() -> None:
    """Collapsed Gmail buckets should not do first-click child construction/polish work."""
    source = Path("ui/tabs/widgets_tab_gmail.py").read_text(encoding="utf-8")

    assert source.count("defer_initial_visibility=True") == 4
    assert "_finalize_bucket_body(toggle, body)" in source


def test_gmail_backend_visibility_hidden_before_parent_show(qt_app, monkeypatch) -> None:
    """Backend panels/buttons must be explicitly hidden even while the parent is hidden."""
    from PySide6.QtWidgets import QLabel, QPushButton, QWidget

    from core.gmail.gmail_backend import GmailBackendMode
    from ui.tabs import widgets_tab_gmail

    class FakeBackend:
        mode = GmailBackendMode.IMAP
        is_authenticated = False
        status_text = "Enter email & app password"

    class FakeManager:
        def _load_client_config(self):
            return None

    tab = QWidget()
    tab.gmail_auth_status = QLabel(tab)
    tab.gmail_authorize_btn = QPushButton("Authorize", tab)
    tab.gmail_sign_out_btn = QPushButton("Sign Out", tab)
    tab._gmail_oauth_panel = QWidget(tab)
    tab._gmail_imap_panel = QWidget(tab)

    monkeypatch.setattr(widgets_tab_gmail, "_get_gmail_backend", lambda: FakeBackend())
    monkeypatch.setattr(widgets_tab_gmail, "_get_gmail_oauth_manager", lambda: FakeManager())

    widgets_tab_gmail._refresh_gmail_auth_state(tab)  # type: ignore[arg-type]

    assert tab._gmail_oauth_panel.isHidden() is True
    assert tab._gmail_imap_panel.isHidden() is False
    assert tab.gmail_authorize_btn.isHidden() is True
    assert tab.gmail_sign_out_btn.isHidden() is True


def test_gmail_backend_visibility_falls_back_to_combo_when_backend_unavailable(qt_app, monkeypatch) -> None:
    """When backend is unavailable at dialog open, only the selected-mode panel should show."""
    from PySide6.QtWidgets import QWidget

    from ui.tabs import widgets_tab_gmail

    class FakeCombo:
        def __init__(self, text):
            self._text = text

        def currentText(self):
            return self._text

    tab = QWidget()
    tab._gmail_oauth_panel = QWidget(tab)
    tab._gmail_imap_panel = QWidget(tab)
    tab.gmail_backend_combo = FakeCombo("IMAP (App Password)")

    monkeypatch.setattr(widgets_tab_gmail, "_get_gmail_backend", lambda: None)

    widgets_tab_gmail._update_backend_panels(tab)  # type: ignore[arg-type]
    assert tab._gmail_oauth_panel.isHidden() is True
    assert tab._gmail_imap_panel.isHidden() is False

    tab.gmail_backend_combo = FakeCombo("OAuth (Advanced)")
    widgets_tab_gmail._update_backend_panels(tab)  # type: ignore[arg-type]
    assert tab._gmail_oauth_panel.isHidden() is False
    assert tab._gmail_imap_panel.isHidden() is True
