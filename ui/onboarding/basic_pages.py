"""Welcome, sources, display selection and interaction: cheap Settings-only UI."""
from PySide6.QtCore import QRectF, QSignalBlocker, Signal, Qt
from PySide6.QtGui import QColor, QGuiApplication, QPainter, QPen
from PySide6.QtWidgets import (
    QButtonGroup, QCheckBox, QFileDialog, QHBoxLayout, QListWidget, QPushButton,
    QVBoxLayout, QWidget,
)

from ui.widgets.continuous_border import OutlinedListWidget
from core.sources.folder_paths import contains_folder, display_folder_path, without_folder
from core.sources.readiness import has_image_sources
from ui.onboarding.state import is_media_center_profile
from sources.rss.curated import apply_curated_wallpaper_feeds
from ui.onboarding.common import Page, ImagePanel, action, asset_path, checkbox, CheckList, silence_check, text_label, SILENCE_TEXT, font_with_point_delta
from ui.settings_theme_runtime import get_active_settings_theme
from ui.styled_popup import StyledPopup


MC_INTERACTION_TOOLTIP = "Media Center builds keep Interaction Mode always enabled."


class WelcomePage(Page):
    importCompleted = Signal()

    def __init__(self, settings, parent=None):
        super().__init__(settings, parent)
        row = QHBoxLayout()
        self.art = ImagePanel(asset_path("SRPSSWitch.png"))
        row.addWidget(self.art, 2)
        copy = QVBoxLayout()
        title = text_label("You're Inside A Wizard Harry!", heading=True)
        font = title.font(); font.setBold(True); font.setUnderline(True); title.setFont(font)
        copy.addStretch()
        copy.addWidget(title)
        copy.addWidget(text_label(
            "Your first time inside someone is special and confusing.\n"
            "The Wizard can help pick the right settings for you while you squirm inside without consent."
        ))
        importing = QHBoxLayout()
        self.import_button = action("Import Settings?", self.import_settings)
        self.import_button.setToolTip("Bring your settings from an SRPSS settings file. A successful import finishes Guided Setup.")
        importing.addWidget(self.import_button); importing.addStretch()
        copy.addSpacing(8)
        copy.addLayout(importing)
        copy.addStretch()
        row.addLayout(copy, 3)
        self.body.addLayout(row, 1)
        self.body.addWidget(silence_check(settings))
        self.body.addWidget(text_label(SILENCE_TEXT))

    def import_settings(self):
        """Import is an explicit save; success finishes Guided Setup."""
        from ui.settings_import import run_settings_import
        if run_settings_import(self, _real_settings(self.settings)):
            self.importCompleted.emit()


def _real_settings(settings):
    """Import is an explicit save: it writes the store itself, never the draft."""
    return getattr(settings, "real", settings)


class SourcesPage(Page):
    readinessChanged = Signal()
    finishRequested = Signal()

    def __init__(self, settings, parent=None):
        super().__init__(settings, parent)
        from PySide6.QtWidgets import QLineEdit
        from ui.tabs.shared_styles import build_bucket_toggle
        self.body.addWidget(text_label(
            "You put on your robe and wizard hat.\n"
            "Sources matter the most. Where do you want your wallpapers from?", heading=True
        ))
        folders = list(settings.get("sources.folders") or [])
        feeds_open = bool(settings.get("sources.rss_feeds")) and not folders
        self.folders_toggle, _, folder_layout = build_bucket_toggle(self.body, "Folders", expanded=not feeds_open, large=True)
        folder_layout.addWidget(text_label("Picture folders on this computer or your network."))
        self.folders = OutlinedListWidget()
        self.folders.setMinimumHeight(110)
        folder_layout.addWidget(self.folders)
        row = QHBoxLayout()
        row.addWidget(action("Add folder…", self.add_folder))
        row.addWidget(action("Remove selected", self.remove_folder))
        row.addStretch()
        folder_layout.addLayout(row)
        self.feeds_toggle, _, feed_layout = build_bucket_toggle(self.body, "Online Wallpaper Feeds", expanded=feeds_open, large=True)
        feed_layout.addWidget(text_label("Wallpapers downloaded from the internet. They need a working connection."))
        self.feeds_enabled = checkbox("Online Wallpaper Feeds")
        self.feeds_enabled.setToolTip("Turn on SRPSS's curated online wallpaper feeds (requires internet).")
        self.feeds_enabled.toggled.connect(self.toggle_feeds)
        feed_layout.addWidget(self.feeds_enabled)
        self.feeds = CheckList()
        self.feeds.setMinimumHeight(150)
        self.feeds.itemChanged.connect(self.change_feed)
        feed_layout.addWidget(self.feeds)
        custom = QHBoxLayout()
        self.custom_feed = QLineEdit()
        self.custom_feed.setPlaceholderText("Add your own: paste a feed or site address…")
        self.custom_feed.setToolTip("An RSS/Atom feed, a Reddit subreddit address, or a site that publishes one.")
        self.custom_feed.returnPressed.connect(self.add_custom_feed)
        custom.addWidget(self.custom_feed, 1)
        custom.addWidget(action("Add feed", self.add_custom_feed))
        feed_layout.addLayout(custom)
        self.custom_message = text_label("")
        feed_layout.addWidget(self.custom_message)
        self._custom_feeds = []
        self.reason = text_label("")
        self.body.addWidget(self.reason)
        shortcuts = QHBoxLayout()
        shortcuts.addWidget(action("Just Make It Work", self.make_it_work))
        shortcuts.addStretch()
        self.body.addLayout(shortcuts)
        self.body.addStretch()
        self.refresh()

    def refresh(self):
        from sources.rss.constants import DEFAULT_RSS_FEEDS
        from PySide6.QtWidgets import QListWidgetItem
        self.folders.clear()
        self.folders.addItems([display_folder_path(folder) for folder in self.settings.get("sources.folders") or []])
        current = list(self.settings.get("sources.rss_feeds") or [])
        for url in current:
            if url not in DEFAULT_RSS_FEEDS.values() and url not in self._custom_feeds:
                self._custom_feeds.append(url)
        with QSignalBlocker(self.feeds_enabled):
            self.feeds_enabled.setChecked(bool(current))
        with QSignalBlocker(self.feeds):
            self.feeds.clear()
            names = {url: name for name, url in DEFAULT_RSS_FEEDS.items()}
            for url in dict.fromkeys([*DEFAULT_RSS_FEEDS.values(), *self._custom_feeds]):
                item = QListWidgetItem(names.get(url, url))
                item.setData(Qt.ItemDataRole.UserRole, url)
                item.setToolTip(url)
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(Qt.CheckState.Checked if url in current else Qt.CheckState.Unchecked)
                self.feeds.addItem(item)
        folders = self.folders.count()
        self.folders_toggle.setText(f"Folders  ·  {folders}" if folders else "Folders")
        self.feeds_toggle.setText(f"Online Wallpaper Feeds  ·  {len(current)} ON" if current else "Online Wallpaper Feeds")
        ready = self.can_continue()
        self.reason.setText("Ready to continue." if ready else "Add a folder or turn on an online wallpaper feed to continue.")
        self.readinessChanged.emit()

    def can_continue(self):
        return has_image_sources(self.settings)

    def add_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Choose wallpaper folder")
        if folder:
            folders = list(self.settings.get("sources.folders") or [])
            if not contains_folder(folders, folder):
                self.settings.set("sources.folders", [*folders, display_folder_path(folder)])
            self.refresh()

    def remove_folder(self):
        selected = self.folders.currentItem()
        if selected:
            self.settings.set("sources.folders", without_folder(self.settings.get("sources.folders") or [], selected.text()))
            self.refresh()

    def toggle_feeds(self, enabled):
        if enabled:
            apply_curated_wallpaper_feeds(self.settings)
        else:
            self.settings.set("sources.rss_feeds", [])
        self.refresh()

    def change_feed(self, item):
        url = item.data(Qt.ItemDataRole.UserRole)
        feeds = list(self.settings.get("sources.rss_feeds") or [])
        if item.checkState() == Qt.CheckState.Checked and url not in feeds:
            feeds.append(url)
        elif item.checkState() != Qt.CheckState.Checked:
            feeds = [value for value in feeds if value != url]
        self.settings.set("sources.rss_feeds", feeds)
        self.refresh()

    def add_custom_feed(self):
        raw = self.custom_feed.text().strip()
        if not raw:
            return
        from ui.tabs.sources_tab import autocorrect_feed_url
        url = raw if raw.startswith(("http://", "https://")) else autocorrect_feed_url(raw).strip()
        if not url.startswith(("http://", "https://")) or "." not in url.split("//", 1)[-1]:
            self.custom_message.setText("That doesn't look like a web address. Paste a full feed or site address.")
            return
        feeds = list(self.settings.get("sources.rss_feeds") or [])
        if url not in feeds:
            self.settings.set("sources.rss_feeds", [*feeds, url])
        if url not in self._custom_feeds:
            self._custom_feeds.append(url)
        self.custom_feed.clear()
        self.custom_message.setText(f"Added {url}" + ("" if url == raw else " (corrected from what you typed)."))
        self.refresh()

    def make_it_work(self):
        apply_curated_wallpaper_feeds(self.settings)
        self.refresh()
        popup = StyledPopup(self, "Guided Setup", "You're Lazy And So Am I! Skip The Rest?",
                            buttons=[("No, I Can Do It!", "continue"), ("Skip", "skip")], default_button_index=0)
        popup.exec()
        if popup.result_value == "skip":
            self.finishRequested.emit()


class DisplayDiagram(QWidget):
    """The Windows display arrangement; click a display to switch it on or off."""

    displayClicked = Signal(int)  # 1-based display number

    def __init__(self, screens, parent=None):
        super().__init__(parent)
        self.screens = screens
        self.active = set()
        self._hover = 0
        self.setMinimumHeight(170)
        self.setMouseTracking(True)

    def set_active(self, numbers):
        self.active = set(numbers)
        self.update()

    def _rects(self):
        if not self.screens:
            return []
        bounds = QRectF(self.screens[0].geometry())
        for screen in self.screens[1:]:
            bounds = bounds.united(QRectF(screen.geometry()))
        scale = min((self.width()-24) / bounds.width(), (self.height()-24) / bounds.height())
        left = (self.width() - bounds.width() * scale) / 2
        top = (self.height() - bounds.height() * scale) / 2
        rects = []
        for screen in self.screens:
            g = screen.geometry()
            rects.append(QRectF(left+(g.x()-bounds.x())*scale, top+(g.y()-bounds.y())*scale,
                                g.width()*scale, g.height()*scale).adjusted(3, 3, -3, -3))
        return rects

    def _hit(self, point):
        for number, rect in enumerate(self._rects(), 1):
            if rect.contains(point):
                return number
        return 0

    def paintEvent(self, event):
        if not self.screens:
            return
        theme = get_active_settings_theme()
        def color(token, alpha=None):
            value = QColor(*theme.color(token).as_tuple())
            if alpha is not None:
                value.setAlpha(alpha)
            return value
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        font = font_with_point_delta(self, 4); font.setBold(True)
        painter.setFont(font)
        for number, rect in enumerate(self._rects(), 1):
            on = number in self.active
            hovered = number == self._hover
            fill = color("control.list.selected_accent", 150 if hovered else 120) if on else color("control.button.hover_surface" if hovered else "control.button.surface", 110)
            border = color("control.list.selected_accent") if on else color("control.button.border", 225 if hovered else 165)
            painter.setBrush(fill)
            painter.setPen(QPen(border, 3.0 if on else 2.0))
            painter.drawRoundedRect(rect, 6, 6)
            painter.setPen(color("panel.group.text"))
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, str(number) + ("" if on else "\nOFF"))

    def mouseMoveEvent(self, event):
        hover = self._hit(event.position())
        if hover != self._hover:
            self._hover = hover
            self.setCursor(Qt.CursorShape.PointingHandCursor if hover else Qt.CursorShape.ArrowCursor)
            self.setToolTip(f"Display {hover}: click to switch it on or off" if hover else "")
            self.update()
        super().mouseMoveEvent(event)

    def leaveEvent(self, event):
        self._hover = 0
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        number = self._hit(event.position()) if event.button() == Qt.MouseButton.LeftButton else 0
        if number:
            self.displayClicked.emit(number)
            event.accept()
            return
        super().mousePressEvent(event)


class DisplaysPage(Page):
    readinessChanged = Signal()

    def __init__(self, settings, parent=None):
        super().__init__(settings, parent)
        self.body.addWidget(text_label("Where should the screensaver appear?", heading=True))
        self.body.addWidget(text_label("Click a display to switch it on or off. The diagram follows their arrangement in Windows."))
        self.screens = QGuiApplication.screens()
        self.diagram = DisplayDiagram(self.screens)
        self.diagram.displayClicked.connect(self.toggle_display)
        self.body.addWidget(self.diagram)
        self.all = checkbox("All displays, including displays connected later")
        self.body.addWidget(self.all)
        self.checks = []
        from core.windows.monitor_resolution import describe_screen_resolution

        for index, screen in enumerate(self.screens, 1):
            # The resolution Windows shows (device pixels) and its scale.
            check = checkbox(f"{index} · {screen.name()} · {describe_screen_resolution(screen)}")
            check.toggled.connect(self.save_selection)
            self.body.addWidget(check)
            self.checks.append(check)
        self.all.toggled.connect(self.save_selection)
        self.reason = text_label("")
        self.body.addWidget(self.reason)
        self.body.addStretch()
        self.refresh()

    def refresh(self):
        selected = self.settings.get("display.show_on_monitors")
        with QSignalBlocker(self.all):
            self.all.setChecked(selected == "ALL")
        for index, check in enumerate(self.checks, 1):
            with QSignalBlocker(check):
                check.setChecked(selected == "ALL" or index in (selected if isinstance(selected, list) else []))
                check.setEnabled(selected != "ALL")
        self.diagram.set_active(i for i, check in enumerate(self.checks, 1) if check.isChecked())
        self.reason.setText("" if self.can_continue() else "Select at least one connected display to continue.")
        self.readinessChanged.emit()

    def toggle_display(self, number):
        """Diagram click: flip one display, leaving "All displays" when needed."""
        active = {i for i, check in enumerate(self.checks, 1) if check.isChecked()}
        active ^= {number}
        if not active:
            self.reason.setText("At least one display has to stay on.")
            return
        self.settings.set("display.show_on_monitors", sorted(active))
        self.refresh()

    def can_continue(self):
        return self.all.isChecked() or any(check.isChecked() for check in self.checks)

    def leave(self):
        # One selected display: every widget goes there (routing is only
        # committed when the selection is, never while it is being toggled).
        from ui.onboarding.state import route_widgets_to_single_display

        route_widgets_to_single_display(self.settings)
        return True

    def save_selection(self):
        selected = [i for i, check in enumerate(self.checks, 1) if check.isChecked()]
        if not self.all.isChecked() and not selected:
            self.refresh()
            return
        self.settings.set("display.show_on_monitors", "ALL" if self.all.isChecked() else selected)
        self.refresh()


class _PracticeStoryCard(QWidget):
    """A painted mock story row (D9): no network, browser, handoff or feed widget."""

    clicked = Signal(bool)  # True when Ctrl was held

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(96)
        self.setMaximumWidth(620)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        from PySide6.QtGui import QPixmap
        self._art = QPixmap(str(asset_path("onboarding/transition_destination.png")))
        self._scaled_art = QPixmap()
        self._scaled_key = None
        self._pressed = False

    def paintEvent(self, _event):
        theme = get_active_settings_theme()
        color = lambda token: QColor(*theme.color(token).as_tuple())
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect()).adjusted(1.5, 1.5, -1.5, -1.5)
        painter.setPen(QPen(color("panel.border"), 2.5 if self.underMouse() else 2.0))
        painter.setBrush(color("panel.subsection.surface"))
        painter.drawRoundedRect(rect, 10.0, 10.0)
        art = QRectF(rect.left() + 12, rect.top() + 12, (rect.height() - 24) * 16 / 9, rect.height() - 24)
        if not self._art.isNull():
            from PySide6.QtGui import QPainterPath
            from ui.widgets.dpr_pixmap import scale_pixmap_for_dpr
            key = (round(art.width()), round(art.height()), self.devicePixelRatioF())
            if key != self._scaled_key:
                # Smooth, DPR-aware scale once per size change (never per paint).
                self._scaled_key = key
                self._scaled_art = scale_pixmap_for_dpr(self._art, art.width(), art.height(), key[2])
            clip = QPainterPath(); clip.addRoundedRect(art, 6.0, 6.0)
            painter.save(); painter.setClipPath(clip)
            painter.drawPixmap(art.topLeft(), self._scaled_art)
            painter.restore()
        text = QRectF(art.right() + 14, rect.top() + 14, rect.right() - art.right() - 26, rect.height() - 28)
        font = font_with_point_delta(self, 1.5); font.setBold(True)
        painter.setFont(font); painter.setPen(color("panel.group.text"))
        painter.drawText(text, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap,
                         "A Practice Story: The Lighthouse Keeper's Last Night")
        font = font_with_point_delta(self, -1.0); font.setBold(False); painter.setFont(font)
        painter.setPen(color("control.button.text"))
        painter.drawText(text, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom, "PRACTICE WIRE  ·  2H AGO")

    def enterEvent(self, event):
        super().enterEvent(event); self.update()

    def leaveEvent(self, event):
        super().leaveEvent(event); self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier))
            event.accept()
            return
        super().mousePressEvent(event)


class InteractionPage(Page):
    def __init__(self, settings, parent=None):
        super().__init__(settings, parent)
        self.body.addWidget(text_label("Look, or interact?", heading=True))
        self.body.addWidget(text_label("Use widgets to open stories and control media. On the screensaver, external links use SRPSS's secure handoff and may close the saver. Hold Ctrl for temporary interaction when it is off."))
        self.media_center = is_media_center_profile(settings)
        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        for enabled, title, detail in (
            (False, "Let it be a screensaver", "Hold Ctrl when you want to interact."),
            (True, "Keep interaction on", "Use widgets without holding Ctrl."),
        ):
            choice = checkbox(f"{title}\n{detail}")
            choice.setMinimumHeight(64)
            choice.toggled.connect(lambda checked, value=enabled: checked and self.settings.set("input.interaction_mode", value))
            self.group.addButton(choice, int(enabled))
            self.body.addWidget(choice)
        if self.media_center:
            # MC builds keep Interaction Mode always on (engine and Display tab agree).
            screensaver = self.group.button(0)
            screensaver.setEnabled(False)
            screensaver.setToolTip(MC_INTERACTION_TOOLTIP)
            self.group.button(1).setToolTip(MC_INTERACTION_TOOLTIP)
        self.body.addSpacing(8)
        self.body.addWidget(text_label("Try it on a practice story", heading=False))
        self.card = _PracticeStoryCard()
        self.card.clicked.connect(self.demonstrate)
        self.body.addWidget(self.card)
        self.demo = text_label("Click the card, with and without Ctrl. Nothing opens and the screensaver is not running.")
        self.body.addWidget(self.demo)
        self.body.addStretch()
        self.refresh()

    def _interaction_on(self):
        return self.media_center or bool(self.settings.get("input.interaction_mode"))

    def refresh(self):
        button = self.group.button(int(self._interaction_on()))
        with QSignalBlocker(button):
            button.setChecked(True)

    def demonstrate(self, ctrl_held: bool = False):
        if self._interaction_on() or ctrl_held:
            self.demo.setText("On the saver, this click would open the story in your browser through the secure link handoff.")
        else:
            self.demo.setText("Nothing happens: the saver treats a plain click as 'wake up'. Hold Ctrl while clicking to open the story.")
