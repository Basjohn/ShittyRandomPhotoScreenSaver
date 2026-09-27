"""Production Settings onboarding seams, using isolated settings and offscreen Qt."""
from copy import deepcopy
from types import SimpleNamespace

import pytest
from PySide6.QtCore import Qt

from core.settings.defaults import get_default_settings
from core.sources.readiness import has_image_sources
from ui.onboarding.basic_pages import SourcesPage, DisplaysPage, InteractionPage


class Settings:
    def __init__(self):
        self.values = deepcopy(get_default_settings())
        self.writes = []

    def get(self, key, default=None):
        value = self.values
        for part in key.split("."):
            if not isinstance(value, dict) or part not in value:
                return default
            value = value[part]
        return deepcopy(value)

    def set(self, key, value):
        self.writes.append(key)
        target = self.values
        parts = key.split(".")
        for part in parts[:-1]: target = target.setdefault(part, {})
        target[parts[-1]] = deepcopy(value)

    def save(self): pass


@pytest.fixture
def settings():
    result = Settings()
    result.values["sources"]["folders"] = []
    result.values["sources"]["rss_feeds"] = []
    return result


@pytest.mark.parametrize("sources,silenced,expected", [(False,False,"wizard"),(False,True,"popup"),(True,False,None),(True,True,None)])
def test_one_settings_no_source_decision(settings, sources, silenced, expected):
    from ui.settings_dialog import SettingsDialog
    settings.set("sources.folders", ["C:/Pictures"] if sources else [])
    settings.set("sources.guided_setup_silenced", silenced)
    calls = []
    host = SimpleNamespace(_closing=False, _settings=settings, isVisible=lambda: True,
                           _has_image_sources=lambda: has_image_sources(settings),
                           run_guided_setup=lambda: calls.append("wizard"),
                           _show_no_sources_popup=lambda: calls.append("popup"))
    SettingsDialog._decide_no_sources_after_show(host)
    assert calls == ([expected] if expected else [])


def test_sources_readiness_does_not_change_other_settings(qapp, settings):
    page = SourcesPage(settings)
    before = deepcopy(settings.values)
    assert not page.can_continue()
    assert not hasattr(page, "skip")  # Skip lives in the Guided Setup header only
    settings.set("sources.folders", ["C:/Pictures"])
    page.refresh()
    assert page.can_continue()
    assert page.folders_toggle.text() == "Folders  ·  1"
    before["sources"]["folders"] = ["C:/Pictures"]
    assert settings.values == before
    page.deleteLater()


def test_sources_page_is_two_large_buckets_and_adds_custom_feeds(qapp, settings):
    page = SourcesPage(settings)
    try:
        for toggle in (page.folders_toggle, page.feeds_toggle):
            assert toggle.property("bucketSize") == "large"
        assert page.feeds_toggle.text() == "Online Wallpaper Feeds"
        assert page.feeds_enabled.text() == "Online Wallpaper Feeds"
        page.custom_feed.setText("example.org/wallpapers.rss")
        page.add_custom_feed()
        assert settings.get("sources.rss_feeds") == ["https://example.org/wallpapers.rss"]
        assert page.can_continue()
        custom = next(page.feeds.item(i) for i in range(page.feeds.count())
                      if page.feeds.item(i).data(Qt.ItemDataRole.UserRole) == "https://example.org/wallpapers.rss")
        custom.setCheckState(Qt.CheckState.Unchecked)
        assert settings.get("sources.rss_feeds") == []
        # Unticked custom feeds stay listed so they can be ticked again.
        assert any(page.feeds.item(i).data(Qt.ItemDataRole.UserRole) == "https://example.org/wallpapers.rss"
                   for i in range(page.feeds.count()))
        page.custom_feed.setText("not a feed")
        page.add_custom_feed()
        assert settings.get("sources.rss_feeds") == []
        assert "web address" in page.custom_message.text().lower()
    finally:
        page.deleteLater()


def test_header_skip_replaces_close_and_leaves_settings_alone(qapp, settings):
    from PySide6.QtWidgets import QPushButton
    from ui.onboarding.wizard import GuidedSetupPanel
    wizard = GuidedSetupPanel(settings)
    before = deepcopy(settings.values)
    finished = []
    wizard.finished.connect(finished.append)
    try:
        texts = [button.text() for button in wizard.findChildren(QPushButton)]
        assert "Close" not in texts and texts.count("Skip") == 1
        wizard.skip.click()
        assert finished == [False]
        assert settings.values == before
    finally:
        wizard.deleteLater()


@pytest.mark.parametrize("choice,finishes", [("skip",True),("continue",False)])
def test_curated_action_shared_and_both_followups(qapp, settings, monkeypatch, choice, finishes):
    from sources.rss.constants import DEFAULT_RSS_FEEDS
    import ui.onboarding.basic_pages as module
    captured = {}
    class Popup:
        def __init__(self, parent, title, message, **kwargs):
            captured.update(message=message, **kwargs)
            self.result_value = choice
        def exec(self): pass
    monkeypatch.setattr(module, "StyledPopup", Popup)
    page = SourcesPage(settings)
    finished = []
    page.finishRequested.connect(lambda: finished.append(True))
    before = deepcopy(settings.values)
    page.make_it_work()
    before["sources"]["rss_feeds"] = list(DEFAULT_RSS_FEEDS.values())
    assert settings.values == before
    assert bool(finished) is finishes
    assert captured["message"] == "You're Lazy And So Am I! Skip The Rest?"
    assert captured["buttons"] == [("No, I Can Do It!", "continue"), ("Skip", "skip")]
    page.deleteLater()


def test_media_center_keeps_interaction_on_and_greys_the_other_choice(qapp, settings):
    settings.get_application_name = lambda: "Screensaver_MC"
    page = InteractionPage(settings)
    try:
        assert page.group.button(1).isChecked()
        assert not page.group.button(0).isEnabled()
        assert "Media Center" in page.group.button(0).toolTip()
        page.demonstrate()
        assert "secure link handoff" in page.demo.text().lower()
    finally:
        page.deleteLater()


def test_interaction_changes_only_interaction_setting(qapp, settings):
    page = InteractionPage(settings)
    settings.writes.clear()
    page.group.button(1).click()
    assert settings.writes == ["input.interaction_mode"]
    page.demonstrate()
    assert settings.writes == ["input.interaction_mode"]
    page.deleteLater()


def test_display_selection_keeps_one_connected_screen_and_hydration_is_read_only(qapp, settings, monkeypatch):
    from PySide6.QtCore import QRect
    from ui.onboarding import basic_pages
    screens = [SimpleNamespace(name=lambda: "Left", geometry=lambda: QRect(0, 0, 1920, 1080)),
               SimpleNamespace(name=lambda: "Right", geometry=lambda: QRect(1920, 0, 1280, 1024))]
    monkeypatch.setattr(basic_pages.QGuiApplication, "screens", staticmethod(lambda: screens))
    settings.set("display.show_on_monitors", [3])
    settings.writes.clear()
    page = DisplaysPage(settings)
    try:
        assert settings.writes == []
        assert not page.can_continue()
        page.checks[1].setChecked(True)
        assert settings.get("display.show_on_monitors") == [2]
        assert page.can_continue()
        page.checks[1].setChecked(False)
        assert page.checks[1].isChecked()
        assert settings.get("display.show_on_monitors") == [2]
        page.all.setChecked(True)
        assert settings.get("display.show_on_monitors") == "ALL"
    finally:
        page.deleteLater()


def test_display_diagram_click_toggles_a_display(qapp, settings, monkeypatch):
    from PySide6.QtCore import QRect
    from ui.onboarding import basic_pages
    screens = [SimpleNamespace(name=lambda: "Left", geometry=lambda: QRect(0, 0, 1920, 1080)),
               SimpleNamespace(name=lambda: "Right", geometry=lambda: QRect(1920, 0, 1920, 1080))]
    monkeypatch.setattr(basic_pages.QGuiApplication, "screens", staticmethod(lambda: screens))
    settings.set("display.show_on_monitors", "ALL")
    page = DisplaysPage(settings)
    try:
        page.diagram.resize(400, 170)
        assert page.diagram.active == {1, 2}
        right = page.diagram._rects()[1].center()
        assert page.diagram._hit(right) == 2
        page.diagram.displayClicked.emit(2)
        assert settings.get("display.show_on_monitors") == [1]
        assert page.diagram.active == {1} and not page.all.isChecked()
        page.diagram.displayClicked.emit(1)  # the last active display stays on
        assert settings.get("display.show_on_monitors") == [1]
        page.diagram.displayClicked.emit(2)
        assert settings.get("display.show_on_monitors") == [1, 2]
    finally:
        page.deleteLater()


def test_widget_setup_clocks_section_sets_face_and_timezones(qapp, settings, monkeypatch):
    import ui.onboarding.state as state
    from PySide6.QtWidgets import QCheckBox, QToolButton
    from ui.onboarding.setup_page import SetupPage
    from ui.widgets.styled_combo_box import StyledComboBox
    settings.values["widgets"]["clock"]["enabled"] = True
    settings.values["widgets"]["clock2"]["enabled"] = True
    settings.values["widgets"]["clock2"]["display_mode_overrides"] = {"screen": "digital"}
    assert state.selected_setup_dependencies(settings)[0] == "clocks"
    monkeypatch.setattr(state, "selected_setup_dependencies", lambda _settings: ("clocks",))
    page = SetupPage(settings)
    try:
        toggle = page.findChildren(QToolButton)[0]
        assert toggle.text() == "Clocks" and toggle.property("bucketSize") == "large"
        toggle.setChecked(True)
        combos = page.findChildren(StyledComboBox)
        assert len(combos) == 2  # Clock 1 and Clock 2 are on; Clock 3 is not
        combos[1].setCurrentIndex(combos[1].findData("Asia/Tokyo") if combos[1].findData("Asia/Tokyo") >= 0 else 1)
        assert settings.get("widgets.clock2.timezone") == combos[1].currentData()
        digital = next(box for box in page.findChildren(QCheckBox) if box.text() == "Digital")
        digital.setChecked(True)
        assert settings.get("widgets.clock.display_mode") == "digital"
        assert "display_mode_overrides" not in settings.get("widgets.clock2")
    finally:
        page.retire(); page.deleteLater()


def test_wizard_lazy_rerun_and_manual_launch_ignores_silence(qapp, settings):
    from ui.onboarding.wizard import GuidedSetupPanel
    settings.set("sources.guided_setup_silenced", True)
    settings.set("sources.folders", ["C:/Current"])
    settings.writes.clear()
    wizard = GuidedSetupPanel(settings)
    assert set(wizard.pages) == {"welcome"}
    wizard.go_next()
    sources = wizard.pages["sources"][0]
    assert sources.folders.item(0).text() == r"C:\Current"  # shown with Windows separators, stored as-is
    assert settings.writes == []
    wizard.close_setup(False); wizard.deleteLater()


def test_quick_start_arrange_is_lazy(qapp, settings, monkeypatch):
    import ui.onboarding.quick_start as module
    monkeypatch.setattr(module, "current_setup_summary", lambda _settings: {"sources":False,"families":0,"transitions":0})
    page = module.QuickStartPage(settings, lambda: None)
    assert page.arrange is None
    assert not settings.writes
    page.deleteLater()


def test_account_sections_fail_closed_without_importing_backends(qapp, settings, monkeypatch):
    import ui.onboarding.setup_page as module
    import ui.onboarding.state as state
    from PySide6.QtWidgets import QLineEdit
    monkeypatch.setattr(state, "selected_setup_dependencies", lambda _settings: ("steam","gmail"))
    monkeypatch.setattr(module, "is_interactive_user_desktop", lambda: False)
    page = module.SetupPage(settings)
    from PySide6.QtWidgets import QToolButton
    for toggle in page.findChildren(QToolButton): toggle.setChecked(True)
    # No account inputs on a non-interactive desktop (the Gmail sound path is not one).
    assert not [field for field in page.findChildren(QLineEdit)
                if field.echoMode() == QLineEdit.EchoMode.Password or "@" in field.placeholderText()]
    assert page._manager is None
    page.retire(); page.deleteLater()


def test_retired_setup_page_drops_gmail_verification_completion(qapp, settings, monkeypatch):
    """The UI commit following Gmail verification must not outlive its page."""

    import ui.onboarding.state as state
    from ui.onboarding.setup_page import SetupPage
    from core.threading.manager import ThreadManager

    monkeypatch.setattr(state, "selected_setup_dependencies", lambda _settings: ())
    callbacks = []

    class Manager:
        def submit_io_task(self, _work, *, callback, category):
            assert category == "guided_account_setup"
            callbacks.append(callback)

    manager = Manager()
    monkeypatch.setattr(ThreadManager, "get_app_shared", classmethod(lambda _cls: manager))
    monkeypatch.setattr(ThreadManager, "run_on_ui_thread", staticmethod(lambda callback: callback()))
    page = SetupPage(settings)
    received = []
    try:
        page._worker(lambda: SimpleNamespace(success=True), received.append)
        page.retire()
        callbacks.pop()(SimpleNamespace(success=True))
        assert received == []
    finally:
        page.deleteLater()


def test_deselecting_last_setup_dependency_can_still_advance(qapp, settings, monkeypatch):
    from ui.onboarding.wizard import GuidedSetupPanel
    from ui.onboarding import state
    dependencies = ["feeds"]
    monkeypatch.setattr(state, "selected_setup_dependencies", lambda _settings: tuple(dependencies))
    wizard = GuidedSetupPanel(settings)
    try:
        wizard.show_page("setup")
        dependencies.clear()
        wizard.go_next()
        assert wizard.current_key == "visualizer"
        assert "setup" not in wizard.pages
    finally:
        wizard.close_setup(False); wizard.deleteLater()


def test_retired_geocoder_drops_delayed_fetch_and_queued_results(qapp, monkeypatch):
    from PySide6.QtWidgets import QLineEdit
    from ui.widgets.geocode_completer import GeocodeCompleter, ThreadManager
    work = []
    monkeypatch.setattr(ThreadManager, "get_app_shared", classmethod(lambda _cls: SimpleNamespace(submit_io_task=lambda *args: work.append(args))))
    field = QLineEdit()
    completer = GeocodeCompleter(field)
    before = completer._model.stringList()
    completer._pending_query = "Paris"
    completer.retire()
    completer._fire_fetch("Paris")
    completer._on_results(["Late result"])
    assert work == []
    assert completer._model.stringList() == before
    field.deleteLater()


def test_wizard_never_saves_until_finish(qapp, settings):
    """Moving through every page, including Ready, writes nothing; Finish commits."""
    from ui.onboarding.wizard import GuidedSetupPanel
    settings.set("sources.folders", ["C:/Pictures"])
    settings.writes.clear()
    wizard = GuidedSetupPanel(settings)
    try:
        wizard.go_next()  # Sources
        wizard.pages["sources"][0].custom_feed.setText("https://example.org/feed.rss")
        wizard.pages["sources"][0].add_custom_feed()
        wizard.settings.set("widgets.weather.location", "Cape Town")
        for key in ("displays", "interaction", "transitions", "ready"):
            wizard.show_page(key)
        assert settings.writes == []
        assert settings.get("sources.rss_feeds") == []
        assert wizard.settings.get("sources.rss_feeds") == ["https://example.org/feed.rss"]
        assert wizard.has_unsaved_changes()
        wizard.finish()
        assert settings.get("sources.rss_feeds") == ["https://example.org/feed.rss"]
        assert settings.get("widgets.weather.location") == "Cape Town"
        assert not wizard.settings.pending
    finally:
        wizard.deleteLater()


@pytest.mark.parametrize("answer,saved,left", [("keep", True, True), ("discard", False, True),
                                               ("stay", False, False), (None, False, False)])
def test_skip_with_changes_asks_keep_or_discard(qapp, settings, monkeypatch, answer, saved, left):
    from ui.onboarding.wizard import GuidedSetupPanel
    from ui.styled_popup import StyledPopup
    shown = []
    def fake_exec(popup):
        shown.append([label for label, _value in popup._buttons])
        popup._result_value = answer
    monkeypatch.setattr(StyledPopup, "exec", fake_exec)
    settings.writes.clear()
    wizard = GuidedSetupPanel(settings)
    finished = []
    wizard.finished.connect(finished.append)
    try:
        wizard.settings.set("input.interaction_mode", True)
        wizard.skip.click()
        assert shown == [["Keep Changes", "Discard Changes", "Stay In Setup"]]
        assert finished == ([False] if left else [])
        assert (settings.writes == ["input.interaction_mode"]) is saved
        if not left:
            assert wizard.settings.pending  # staying keeps the draft
    finally:
        wizard.deleteLater()


def test_discarded_theme_preview_restores_the_live_theme(qapp, settings):
    from ui.onboarding.draft import SettingsDraft
    from ui.settings_theme_catalog import build_settings_theme_catalog
    from ui.settings_theme_runtime import get_active_settings_theme
    from ui.settings_theme_selection import apply_settings_theme_selection
    catalog = build_settings_theme_catalog("themes")
    before = get_active_settings_theme()
    other = next(entry for entry in catalog.entries if entry.theme != before)
    settings.values["widget_theme"]["keep_synced"] = False  # no Widget-theme catalog in this test
    draft = SettingsDraft(settings)
    settings.writes.clear()
    apply_settings_theme_selection(draft, catalog, other.theme_id)
    assert get_active_settings_theme() == other.theme  # live preview
    assert settings.writes == []
    draft.discard()
    assert get_active_settings_theme() == before


_HOVER_PROBE = r"""
import sys, tempfile
from pathlib import Path
from PySide6.QtCore import QPoint
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
app = QApplication(["hover-probe"]); app.setStyle("windows11")
assert app.platformName() == "offscreen"
from core.animation import AnimationManager
from core.settings.settings_manager import SettingsManager
from ui.settings_dialog import SettingsDialog
settings = SettingsManager(application="hoverprobe", storage_base_dir=Path(tempfile.mkdtemp()))
settings.set("sources.folders", ["C:/Pictures"])
dialog = SettingsDialog(settings, AnimationManager()); dialog.resize(1280, 820); dialog.show()
for _ in range(20): app.processEvents()
dialog.run_guided_setup(); panel = dialog._guided_setup_panel; panel.show_page("transitions")
for _ in range(20): app.processEvents()
rows = panel.pages["transitions"][0].rows; viewport = rows.viewport()
before = (rows.currentRow(), rows.verticalScrollBar().value())
for y in range(5, viewport.height() - 5, 7):
    QTest.mouseMove(viewport, QPoint(60, y)); app.processEvents()
print("RESULT", before, (rows.currentRow(), rows.verticalScrollBar().value()), flush=True)
import os; os._exit(0)  # skip Qt teardown; the probe's answer is already out
"""


def test_hovering_transition_rows_inside_settings_does_not_scroll(tmp_path):
    """Offscreen subprocess (never a visible window): hover alone must not move the list."""
    import os, subprocess, sys
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen", QT_QPA_FONTDIR="C:/Windows/Fonts", PYTHONPATH=str(root))
    completed = subprocess.run([sys.executable, "-c", _HOVER_PROBE], cwd=root, env=env,
                               capture_output=True, text=True, timeout=180)
    line = next((l for l in completed.stdout.splitlines() if l.startswith("RESULT")), None)
    assert line is not None, completed.stderr[-3000:]
    before, after = line.split(" ", 1)[1].split(") (")
    assert before + ")" == "(" + after, line


def test_widget_setup_shows_saved_steam_connection_through_the_settings_flow(qapp, settings, monkeypatch):
    """Parity with Settings → Steam: same controller, same connected checks, no secrets read."""
    import ui.onboarding.setup_page as module
    import ui.onboarding.state as state
    import ui.tabs.widgets_tab_steam as steam
    from PySide6.QtWidgets import QLineEdit, QToolButton
    from core.steam.credentials import SteamCredentialStorageStatus
    monkeypatch.setattr(state, "selected_setup_dependencies", lambda _settings: ("steam",))
    monkeypatch.setattr(state, "saved_account_states", lambda _settings: {"steam": True, "gmail": False})
    monkeypatch.setattr(module, "is_interactive_user_desktop", lambda: True)
    monkeypatch.setattr(steam, "get_storage_status", lambda: SteamCredentialStorageStatus(True, True, "Saved."))
    page = module.SetupPage(settings)
    try:
        toggle = page.findChildren(QToolButton)[0]
        assert toggle.text() == "Steam  ·  CONNECTED"
        toggle.setChecked(True)
        host = page._steam_host
        assert host.steam_identity_check.text() == "Connected"
        assert host.steam_api_key_check.text() == "Connected"
        assert "access is ready" in host.steam_access_status.text().lower()
        assert not page.findChildren(QLineEdit)  # keys are pasted in Steam's own popup, never here
        assert settings.writes == []
    finally:
        page.retire(); page.deleteLater()
    assert host.steam_identity_check is None  # retired: late completions find nothing to touch


def test_widget_setup_gmail_bucket_offers_the_notification_sound(qapp, settings, monkeypatch):
    import ui.onboarding.setup_page as module
    import ui.onboarding.state as state
    from PySide6.QtWidgets import QCheckBox, QPushButton, QToolButton
    monkeypatch.setattr(state, "selected_setup_dependencies", lambda _settings: ("gmail",))
    monkeypatch.setattr(state, "saved_account_states", lambda _settings: {"steam": False, "gmail": False})
    monkeypatch.setattr(module, "is_interactive_user_desktop", lambda: False)  # sound needs no account
    played = []
    import core.audio.notification_sound as sound
    monkeypatch.setattr(sound.NotificationSoundPlayer, "instance", classmethod(lambda _cls: type("P", (), {
        "set_file_path": lambda self, path: played.append(path), "set_volume": lambda self, v: played.append(v),
        "play": lambda self: played.append("play")})()))
    page = module.SetupPage(settings)
    try:
        page.findChildren(QToolButton)[0].setChecked(True)
        play = next(box for box in page.findChildren(QCheckBox) if box.text() == "Play Sound on New Mail")
        play.setChecked(True)
        page.gmail_sound_volume.setValue(40)
        assert settings.get("widgets.gmail.play_sound_on_new_mail") is True
        assert settings.get("widgets.gmail.sound_volume_percent") == 40
        next(b for b in page.findChildren(QPushButton) if b.text() == "Test").click()
        assert played[-1] == "play" and 40 in played
    finally:
        page.retire(); page.deleteLater()
