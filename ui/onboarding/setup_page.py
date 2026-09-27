"""Conditional user-invoked setup. Secrets stay in inputs and account owners."""
import re
import threading
import weakref

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QCheckBox, QLineEdit
from shiboken6 import isValid

from core.windows.desktop_context import is_interactive_user_desktop
from ui.onboarding.common import Page, action, checkbox, text_label
from ui.tabs.shared_styles import build_bucket_toggle

ACCOUNT_DESKTOP_MESSAGE = (
    "For your protection, account setup is turned off on this desktop. "
    "Open SRPSS from Windows Screen Saver Settings (Settings button) on your "
    "normal Windows desktop to connect Steam or Gmail."
)


class SetupPage(Page):
    def __init__(self, settings, parent=None):
        super().__init__(settings, parent)
        from ui.onboarding.state import selected_setup_dependencies
        self._retired = threading.Event()
        self._manager = None
        self._owns_manager = False
        self._steam_session = None
        self._identity = None
        self._completer = None
        self._password_inputs = []
        self.body.addWidget(text_label("A few finishing touches", heading=True))
        self.body.addWidget(text_label("Open a section to configure the widgets you chose. Accounts are optional; you can finish them later in Settings."))
        self.dependencies = selected_setup_dependencies(settings)
        titles = {"reddit": "Reddit", "reddit2": "Reddit 2", "feeds": "Feeds"}
        if {"steam", "gmail"} & set(self.dependencies):
            # Non-secret storage presence only (never decrypts or connects).
            from ui.onboarding.state import saved_account_states
            for account, saved in saved_account_states(settings).items():
                if saved:
                    titles[account] = f"{account.title()}  ·  CONNECTED"
        for dependency in self.dependencies:
            toggle, container, layout = build_bucket_toggle(self.body, titles.get(dependency, dependency.title()), expanded=False, large=True)
            built = [False]
            def build(checked, dep=dependency, target=layout, marker=built):
                if checked and not marker[0]:
                    marker[0] = True
                    getattr(self, f"_build_{dep}")(target)
            toggle.toggled.connect(build)
        self.body.addStretch()

    def _worker(self, work, done):
        """Admit one explicit action; stale page completion never touches widgets."""
        from core.threading.manager import ThreadManager
        if self._manager is None:
            self._manager = ThreadManager.get_app_shared()
            self._owns_manager = self._manager is None
            if self._manager is None:
                self._manager = ThreadManager.create_helper_manager()
        alive = self._retired
        owner_ref = weakref.ref(self)
        def completed(result):
            def publish():
                owner = owner_ref()
                if not alive.is_set() and owner is not None and isValid(owner):
                    done(result)
            ThreadManager.run_on_ui_thread(publish)
        self._manager.submit_io_task(work, callback=completed, category="guided_account_setup")

    def retire(self):
        if self._retired.is_set():
            return
        self._retired.set()
        for field in self._password_inputs:
            if isValid(field):
                field.clear()
        if self._steam_session is not None:
            self._steam_session.close()
            self._steam_session = None
        steam = getattr(self, "_steam_host", None)
        if steam is not None:
            # The shared Steam flow drops completions from older generations and
            # skips labels it cannot find, so late results never touch this page.
            steam._steam_connection_generation = int(getattr(steam, "_steam_connection_generation", 0)) + 1
            session = getattr(steam, "_steam_openid_session", None)
            if session is not None:
                session.close()
            for name in ("steam_identity_check", "steam_api_key_check", "steam_saved_connection_feedback",
                         "steam_access_status", "steam_connection_status"):
                setattr(steam, name, None)
        if self._completer is not None:
            self._completer.retire()
            self._completer.deleteLater()
            self._completer = None
        if self._owns_manager and self._manager is not None:
            self._manager.shutdown(wait=False)
        self._manager = None

    def _account_admitted(self, layout):
        if is_interactive_user_desktop():
            return True
        layout.addWidget(text_label(ACCOUNT_DESKTOP_MESSAGE))
        return False

    def _build_clocks(self, layout):
        from PySide6.QtWidgets import QButtonGroup, QHBoxLayout
        from ui.widgets.styled_combo_box import StyledComboBox
        from widgets.timezone_utils import get_common_timezones, get_local_timezone
        widgets = self.settings.get("widgets") or {}
        layout.addWidget(text_label("Clock face, shared by every clock:"))
        faces = QButtonGroup(layout.parentWidget())
        faces.setExclusive(True)
        current = str((widgets.get("clock") or {}).get("display_mode") or "analog").lower()
        face_row = QHBoxLayout()
        for mode, title in (("analog", "Analogue"), ("digital", "Digital")):
            choice = checkbox(title)
            choice.setChecked(mode == current)
            choice.toggled.connect(lambda checked, value=mode: checked and self._set_clock_face(value))
            faces.addButton(choice)
            face_row.addWidget(choice)
        face_row.addStretch()
        layout.addLayout(face_row)
        zones = get_common_timezones()
        for widget_id, name in (("clock", "Clock 1"), ("clock2", "Clock 2"), ("clock3", "Clock 3")):
            section = widgets.get(widget_id) or {}
            if not section.get("enabled"):
                continue
            row = QHBoxLayout()
            label = text_label(f"{name} timezone")
            label.setMinimumWidth(130)
            row.addWidget(label)
            combo = StyledComboBox()
            combo.setMinimumWidth(220)
            for display_name, zone in zones:
                combo.addItem(display_name, zone)
            zone = str(section.get("timezone") or "local")
            if combo.findData(zone) < 0:
                combo.addItem(zone, zone)
            combo.setCurrentIndex(combo.findData(zone))
            combo.currentIndexChanged.connect(
                lambda _index, box=combo, key=f"widgets.{widget_id}.timezone": self.settings.set(key, box.currentData()))
            row.addWidget(combo)
            def detect(box=combo):
                detected = get_local_timezone()
                if box.findData(detected) < 0:
                    box.addItem(f"Detected: {detected}", detected)
                box.setCurrentIndex(box.findData(detected))
            row.addWidget(action("Detect", detect))
            row.addStretch()
            layout.addLayout(row)

    def _set_clock_face(self, mode):
        """An explicit wizard choice applies everywhere, so per-display flips reset."""
        widgets = self.settings.get("widgets")
        for widget_id in ("clock", "clock2", "clock3"):
            section = widgets.get(widget_id)
            if isinstance(section, dict):
                section.pop("display_mode_overrides", None)
        widgets["clock"]["display_mode"] = mode
        self.settings.set("widgets", widgets)

    def _build_weather(self, layout):
        from ui.widgets.geocode_completer import GeocodeCompleter
        layout.addWidget(text_label("Start typing a city. Suggestions use Open-Meteo only when you type."))
        field = QLineEdit(str(self.settings.get("widgets.weather.location")))
        field.setPlaceholderText("City name…")
        field.editingFinished.connect(lambda: self.settings.set("widgets.weather.location", field.text().strip()))
        self._completer = GeocodeCompleter(field)
        layout.addWidget(field)

    def _build_reddit(self, layout):
        self._build_subreddit(layout, "reddit")

    def _build_reddit2(self, layout):
        self._build_subreddit(layout, "reddit2")

    def _build_subreddit(self, layout, widget_id):
        layout.addWidget(text_label("Choose a subreddit, for example wallpapers, pcgaming or cats. No live lookup is made."))
        field = QLineEdit(str(self.settings.get(f"widgets.{widget_id}.subreddit", "")))
        field.setPlaceholderText("wallpapers")
        message = text_label("")
        def save():
            name = re.sub(r"^/?r/", "", field.text().strip(), flags=re.IGNORECASE)
            if not re.fullmatch(r"[A-Za-z0-9_]{2,21}", name):
                message.setText("Use 2–21 letters, numbers or underscores, with no spaces.")
                return
            self.settings.set(f"widgets.{widget_id}.subreddit", name)
            field.setText(name)
            message.setText("Saved.")
        field.editingFinished.connect(save)
        layout.addWidget(field); layout.addWidget(message)

    def _build_feeds(self, layout):
        from core.feeds.news import NEWS_CATEGORIES
        layout.addWidget(text_label("Choose your News cards. Their current publisher selections are kept. Custom feed addresses live in full Settings."))
        for category in NEWS_CATEGORIES:
            check = checkbox(category.label)
            key = f"widgets.{category.widget_id}.enabled"
            check.setChecked(bool(self.settings.get(key)))
            check.toggled.connect(lambda checked, setting=key: self.settings.set(setting, checked))
            layout.addWidget(check)

    def _build_steam(self, layout):
        """The same two connections, popups and saved-state checks as Settings → Steam."""
        from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget
        from ui.tabs import widgets_tab_steam as steam
        from ui.widgets.styled_combo_box import StyledComboBox
        layout.addWidget(text_label("SRPSS sends you to Steam's own sign-in and API-key pages. Your Steam password never enters SRPSS. Both connections are stored encrypted for your Windows account."))
        if not self._account_admitted(layout):
            return
        host = QWidget()
        self._steam_host = host
        body = QVBoxLayout(host); body.setContentsMargins(0, 0, 0, 0); body.setSpacing(10)

        def connection_row(title, button_text, handler, check_name):
            row = QHBoxLayout()
            label = text_label(title); label.setMinimumWidth(140)
            row.addWidget(label)
            row.addWidget(action(button_text, lambda: handler(host)))
            check = text_label("Not connected")
            setattr(host, check_name, check)
            row.addWidget(check); row.addStretch()
            body.addLayout(row)

        connection_row("Steam Identity", "Connect ID", steam._on_steam_connect_id, "steam_identity_check")
        connection_row("Steam API Key", "Connect API Key", steam._on_steam_connect_api_key, "steam_api_key_check")
        actions = QHBoxLayout()
        actions.addWidget(action("Check Saved Connection", lambda: steam._on_steam_check_saved_connection(host)))
        actions.addWidget(action("Disconnect", lambda: steam._on_steam_disconnect(host)))
        host.steam_saved_connection_feedback = text_label("")
        host.steam_saved_connection_feedback.hide()
        actions.addWidget(host.steam_saved_connection_feedback); actions.addStretch()
        body.addLayout(actions)
        privacy = QHBoxLayout()
        label = text_label("Privacy Mode"); label.setMinimumWidth(140)
        privacy.addWidget(label)
        mode = StyledComboBox(); mode.addItems(["Strict", "Balanced", "Rich"]); mode.setMinimumWidth(150)
        mode.setCurrentText(str(self.settings.get("widgets.steam.privacy_mode") or "Rich"))
        mode.currentTextChanged.connect(lambda text: self.settings.set("widgets.steam.privacy_mode", text))
        privacy.addWidget(mode); privacy.addStretch()
        body.addLayout(privacy)
        host.steam_access_status = text_label("")
        host.steam_connection_status = text_label("")
        body.addWidget(host.steam_access_status); body.addWidget(host.steam_connection_status)
        layout.addWidget(host)
        # Reads only the encrypted-storage status: never decrypts or contacts Steam.
        steam._hydrate_saved_connection_status(host)

    def _build_gmail(self, layout):
        layout.addWidget(text_label("Use a Google App Password, not your normal Google password. SRPSS tests the connection directly with Gmail and stores the credential encrypted for your Windows account."))
        if self._account_admitted(layout):
            self._build_gmail_account(layout)
        self._build_gmail_sound(layout)

    def _build_gmail_account(self, layout):
        from core.windows.secure_url_launcher import open_url
        from core.gmail.gmail_backend import GmailBackend
        backend = GmailBackend.instance()
        connection = text_label("Checking your saved Gmail connection…")
        layout.addWidget(connection)
        layout.addWidget(action("Create a Google App Password", lambda: open_url("https://myaccount.google.com/apppasswords", prefer_direct=True, source="gmail_settings") if is_interactive_user_desktop() else None))
        email = QLineEdit(); email.setPlaceholderText("you@gmail.com")
        password = QLineEdit(); password.setPlaceholderText("App Password"); password.setEchoMode(QLineEdit.EchoMode.Password)
        self._password_inputs.append(password)
        layout.addWidget(email); layout.addWidget(password)
        status = text_label("OAuth remains available in full Settings.")

        def show_saved_state():
            # Status text and address only: the stored password is never read back.
            if self._retired.is_set() or not isValid(connection):
                return
            if backend.is_authenticated:
                connection.setText("CONNECTED  ·  " + backend.status_text)
                saved_email = getattr(backend, "_imap_email", None)
                if saved_email and not email.text():
                    email.setText(saved_email)
                password.setPlaceholderText("Saved (hidden). Paste a new App Password only to replace it.")
            else:
                connection.setText("NOT CONNECTED  ·  " + backend.status_text)

        if getattr(backend, "is_initialized", True):
            show_saved_state()
        else:
            backend.ensure_initialized(backend.get_bootstrap_thread_manager(), lambda _ok: show_saved_state())

        def save_credentials():
            if not is_interactive_user_desktop():
                status.setText(ACCOUNT_DESKTOP_MESSAGE); return
            if not email.text().strip() or not password.text().strip():
                status.setText("Enter both your Gmail address and App Password."); return
            from core.account_setup.controllers import GmailConnectionController
            from core.gmail.gmail_backend import GmailBackendMode
            save.setEnabled(False); status.setText("Preparing encrypted storage…")
            def initialized(success):
                if self._retired.is_set() or not isValid(self): return
                if not success:
                    save.setEnabled(True); status.setText("Could not prepare Gmail. Please try again."); return
                entered_email, entered_password = email.text().strip(), password.text().strip()
                status.setText("Testing a secure connection to Gmail…")
                def done(result):
                    save.setEnabled(True)
                    operation = result.result if result.success else None
                    if operation is None or not operation.success:
                        status.setText("Gmail did not accept the connection. Check your address and App Password."); return
                    try:
                        GmailConnectionController().save_verified_imap(backend, entered_email, entered_password, operation)
                        backend.mode = GmailBackendMode.IMAP
                    except RuntimeError:
                        status.setText("Encrypted Gmail storage failed. Please try again."); return
                    password.clear(); status.setText(operation.message)
                    show_saved_state()
                self._worker(lambda: GmailConnectionController().test_imap(backend, entered_email, entered_password), done)
            backend.ensure_initialized(backend.get_bootstrap_thread_manager(), initialized)
        save = action("Save && Test", save_credentials)
        layout.addWidget(save); layout.addWidget(status)

    def _build_gmail_sound(self, layout):
        """New-mail sound: most users would never find it in full Settings."""
        from PySide6.QtWidgets import QHBoxLayout, QSlider
        from ui.tabs import widgets_tab_gmail as gmail
        from ui.tabs.widgets_tab import NoWheelSlider
        play = checkbox("Play Sound on New Mail")
        play.setChecked(bool(self.settings.get("widgets.gmail.play_sound_on_new_mail")))
        play.toggled.connect(lambda checked: self.settings.set("widgets.gmail.play_sound_on_new_mail", checked))
        layout.addWidget(play)
        # The Settings helpers read these two attribute names from their owner.
        self.gmail_sound_file = QLineEdit(str(self.settings.get("widgets.gmail.sound_file_path") or ""))
        self.gmail_sound_file.setPlaceholderText("Path to .ogg/.wav/.mp3")
        self.gmail_sound_file.textChanged.connect(lambda text: self.settings.set("widgets.gmail.sound_file_path", text))
        row = QHBoxLayout()
        row.addWidget(self.gmail_sound_file, 1)
        row.addWidget(action("Browse…", lambda: gmail._on_gmail_browse_sound(self)))
        row.addWidget(action("Test", lambda: gmail._on_gmail_test_sound(self)))
        layout.addLayout(row)
        volume_row = QHBoxLayout()
        label = text_label("Sound Volume"); label.setMinimumWidth(140)
        volume_row.addWidget(label)
        self.gmail_sound_volume = NoWheelSlider(Qt.Orientation.Horizontal)
        self.gmail_sound_volume.setRange(0, 100)
        self.gmail_sound_volume.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.gmail_sound_volume.setTickInterval(10)
        self.gmail_sound_volume.setValue(int(self.settings.get("widgets.gmail.sound_volume_percent") or 0))
        value = text_label(f"{self.gmail_sound_volume.value()}%")
        self.gmail_sound_volume.valueChanged.connect(lambda v: (value.setText(f"{v}%"), self.settings.set("widgets.gmail.sound_volume_percent", int(v))))
        volume_row.addWidget(self.gmail_sound_volume, 1); volume_row.addWidget(value)
        layout.addLayout(volume_row)
