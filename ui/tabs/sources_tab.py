"""Sources configuration tab for settings dialog.

Allows users to configure image sources:
- Folder sources (browse and add)
- RSS/JSON feed sources (add/edit/remove)
"""
from typing import Optional
from pathlib import Path
import tempfile
from urllib.parse import urlparse, urlunparse
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QListWidget,
    QPushButton, QLineEdit, QFileDialog, QGroupBox, QMessageBox, QCheckBox,
    QScrollArea, QDialog, QFrame,
)
from PySide6.QtCore import Signal, Qt

from core.settings.settings_manager import SettingsManager
from core.logging.logger import get_logger

logger = get_logger(__name__)


class SourcesTab(QWidget):
    """Sources configuration tab."""
    
    # Signals
    sources_changed = Signal()
    
    def __init__(self, settings: SettingsManager, parent: Optional[QWidget] = None):
        """
        Initialize sources tab.
        
        Args:
            settings: Settings manager
            parent: Parent widget
        """
        super().__init__(parent)
        
        self._settings = settings
        self._setup_ui()
        self._load_sources()
        
        logger.debug("SourcesTab created")
    
    def _setup_ui(self) -> None:
        """Setup tab UI."""
        # Use a scroll area so this tab behaves consistently with the other
        # tabs when the settings dialog is resized to smaller heights.
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setStyleSheet(
            """
            QScrollArea { border: none; background: transparent; }
            QScrollArea > QWidget > QWidget { background: transparent; }
            QScrollArea QWidget { background: transparent; }
            """
        )
        
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # Title
        title = QLabel("Image Sources")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #ffffff;")
        layout.addWidget(title)
        
        # Folder sources group
        folder_group = QGroupBox("Folder Sources")
        folder_layout = QVBoxLayout(folder_group)
        
        # Folder list
        self.folder_list = QListWidget()
        self.folder_list.setMinimumHeight(150)
        folder_layout.addWidget(self.folder_list)
        
        # Folder buttons
        folder_buttons = QHBoxLayout()
        self.add_folder_btn = QPushButton("Add Folder...")
        self.add_folder_btn.clicked.connect(self._add_folder)
        self.remove_folder_btn = QPushButton("Remove Selected")
        self.remove_folder_btn.clicked.connect(self._remove_folder)
        folder_buttons.addWidget(self.add_folder_btn)
        folder_buttons.addWidget(self.remove_folder_btn)
        folder_buttons.addStretch()
        folder_layout.addLayout(folder_buttons)
        
        layout.addWidget(folder_group)
        
        # RSS sources group
        rss_group = QGroupBox("RSS / JSON Feed Sources")
        rss_layout = QVBoxLayout(rss_group)
        
        # Suggestion label (session-local; updated by "Just Make It Work")
        self.rss_suggestion_label = QLabel(
            "<i>Suggested: Add high-quality RSS/JSON image feeds here.</i>"
        )
        self.rss_suggestion_label.setWordWrap(True)
        self.rss_suggestion_label.setStyleSheet("color: #888888; padding: 5px;")
        rss_layout.addWidget(self.rss_suggestion_label)
        
        # RSS list
        self.rss_list = QListWidget()
        self.rss_list.setMinimumHeight(150)
        rss_layout.addWidget(self.rss_list)
        
        # RSS input
        rss_input = QHBoxLayout()
        self.rss_input = QLineEdit()
        self.rss_input.setPlaceholderText("Enter RSS/JSON feed URL (e.g., https://www.reddit.com/r/CityPorn/top/.json?t=day&limit=100)...")
        self.add_rss_btn = QPushButton("Add Feed")
        self.add_rss_btn.clicked.connect(self._add_rss)
        rss_input.addWidget(self.rss_input)
        rss_input.addWidget(self.add_rss_btn)
        rss_layout.addLayout(rss_input)
        
        # RSS buttons
        rss_buttons = QHBoxLayout()
        self.clear_rss_cache_btn = QPushButton("Clear Cache")
        self.clear_rss_cache_btn.clicked.connect(self._on_clear_rss_cache_clicked)
        self.just_make_it_work_btn = QPushButton("Just Make It Work")
        self.just_make_it_work_btn.setToolTip("This will clean the section and add working shit to it.")
        self.just_make_it_work_btn.clicked.connect(self._on_just_make_it_work_clicked)
        self.remove_rss_btn = QPushButton("Remove Selected")
        self.remove_rss_btn.clicked.connect(self._remove_rss)
        rss_buttons.addWidget(self.clear_rss_cache_btn)
        rss_buttons.addWidget(self.just_make_it_work_btn)
        rss_buttons.addWidget(self.remove_rss_btn)
        rss_buttons.addStretch()
        rss_layout.addLayout(rss_buttons)
        
        # RSS save to disk option
        self.rss_save_to_disk = QCheckBox("Save RSS Images To Disk")
        self.rss_save_to_disk.setToolTip("Hope you have space! All RSS feed images will be permanently saved to a folder of your choosing.")
        self.rss_save_to_disk.stateChanged.connect(self._on_rss_save_toggled)
        rss_layout.addWidget(self.rss_save_to_disk)
        
        # RSS save directory (hidden by default)
        self.rss_save_dir_layout = QHBoxLayout()
        self.rss_save_dir_label = QLabel("Save Directory:")
        self.rss_save_dir_input = QLineEdit()
        self.rss_save_dir_input.setReadOnly(True)
        self.rss_save_dir_input.setPlaceholderText("No directory selected...")
        self.rss_save_dir_btn = QPushButton("Browse...")
        self.rss_save_dir_btn.clicked.connect(self._browse_rss_save_dir)
        self.rss_save_dir_layout.addWidget(self.rss_save_dir_label)
        self.rss_save_dir_layout.addWidget(self.rss_save_dir_input)
        self.rss_save_dir_layout.addWidget(self.rss_save_dir_btn)
        rss_layout.addLayout(self.rss_save_dir_layout)
        
        # Hide save directory controls initially
        self.rss_save_dir_label.setVisible(False)
        self.rss_save_dir_input.setVisible(False)
        self.rss_save_dir_btn.setVisible(False)
        
        layout.addWidget(rss_group)
        
        layout.addStretch()
        
        scroll.setWidget(content)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)
    
    def _load_sources(self) -> None:
        """Load sources from settings."""
        # Load folders using dot notation
        folders = self._settings.get('sources.folders', [])
        self.folder_list.clear()
        for folder in folders:
            self.folder_list.addItem(folder)
        
        # Load RSS feeds using dot notation
        rss_feeds = self._settings.get('sources.rss_feeds', [])
        self.rss_list.clear()
        for feed in rss_feeds:
            self.rss_list.addItem(feed)
        
        # Load RSS save-to-disk settings with boolean normalization
        rss_save_enabled = self._settings.get_bool('sources.rss_save_to_disk', False)

        block = self.rss_save_to_disk.blockSignals(True)
        self.rss_save_to_disk.setChecked(rss_save_enabled)
        self.rss_save_to_disk.blockSignals(block)
        
        rss_save_dir = self._settings.get('sources.rss_save_directory', '')
        if rss_save_dir:
            self.rss_save_dir_input.setText(rss_save_dir)
        
        # Show/hide save directory controls based on checkbox
        self.rss_save_dir_label.setVisible(rss_save_enabled)
        self.rss_save_dir_input.setVisible(rss_save_enabled)
        self.rss_save_dir_btn.setVisible(rss_save_enabled)
        
        logger.debug(f"Loaded {len(folders)} folders and {len(rss_feeds)} RSS feeds")

    def _load_settings(self) -> None:
        self._load_sources()

    def _add_folder(self) -> None:
        """Add folder source."""
        folder = QFileDialog.getExistingDirectory(
            self,
            "Select Image Folder",
            str(Path.home())
        )
        
        if folder:
            # Get current folders using dot notation
            folders = self._settings.get('sources.folders', [])
            
            if folder not in folders:
                folders.append(folder)
                self._settings.set('sources.folders', folders)
                self._settings.save()
                self.folder_list.addItem(folder)
                self.sources_changed.emit()
                logger.info(f"Added folder source: {folder}")
            else:
                QMessageBox.information(self, "Duplicate", "This folder is already added.")
    
    def _remove_folder(self) -> None:
        """Remove selected folder source."""
        current_item = self.folder_list.currentItem()
        if current_item:
            folder = current_item.text()
            
            # Get current folders using dot notation
            folders = self._settings.get('sources.folders', [])
            
            if folder in folders:
                folders.remove(folder)
                self._settings.set('sources.folders', folders)
                self._settings.save()
                self.folder_list.takeItem(self.folder_list.currentRow())
                self.sources_changed.emit()
                logger.info(f"Removed folder source: {folder}")
    
    def _add_rss(self) -> None:
        """Add RSS feed source."""
        raw_url = self.rss_input.text().strip()

        if not raw_url:
            return

        url = raw_url

        if not url.startswith(("http://", "https://")):
            # Offer to autocorrect common mistakes such as missing
            # scheme or malformed hosts using a styled subsettings
            # dialog that follows our QSS design.
            dlg = RssAutocorrectDialog(self)
            dlg.exec()
            if not dlg.accepted:
                return

            url = self._autocorrect_feed_url(raw_url).strip()
            if not url or not url.startswith(("http://", "https://")):
                QMessageBox.warning(self, "Invalid URL", "Could not autocorrect feed URL. Please enter a full http:// or https:// address.")
                return

        # Get current RSS feeds using dot notation
        rss_feeds = self._settings.get('sources.rss_feeds', [])

        if url not in rss_feeds:
            rss_feeds.append(url)
            self._settings.set('sources.rss_feeds', rss_feeds)
            self._settings.save()
            self.rss_list.addItem(url)
            self.rss_input.clear()
            self.sources_changed.emit()
            logger.info(f"Added RSS feed: {url}")
        else:
            QMessageBox.information(self, "Duplicate", "This RSS feed is already added.")
    
    def _remove_rss(self) -> None:
        """Remove selected RSS feed source."""
        current_item = self.rss_list.currentItem()
        if current_item:
            url = current_item.text()
            
            # Get current RSS feeds using dot notation
            rss_feeds = self._settings.get('sources.rss_feeds', [])
            
            if url in rss_feeds:
                rss_feeds.remove(url)
                self._settings.set('sources.rss_feeds', rss_feeds)
                self._settings.save()
                self.rss_list.takeItem(self.rss_list.currentRow())
                self.sources_changed.emit()
                logger.info(f"Removed RSS feed: {url}")
    
    def _on_rss_save_toggled(self, state: int) -> None:
        """Handle RSS save-to-disk checkbox toggle."""
        enabled = state == 2  # Qt.CheckState.Checked
        
        # Show/hide directory controls
        self.rss_save_dir_label.setVisible(enabled)
        self.rss_save_dir_input.setVisible(enabled)
        self.rss_save_dir_btn.setVisible(enabled)
        
        # If enabling and no directory set, prompt for one
        if enabled and not self.rss_save_dir_input.text():
            self._browse_rss_save_dir()
        
        # Save setting
        self._settings.set('sources.rss_save_to_disk', enabled)
        self._settings.save()
        self.sources_changed.emit()
        logger.info(f"RSS save-to-disk {'enabled' if enabled else 'disabled'}")
    
    def _browse_rss_save_dir(self) -> None:
        """Browse for RSS save directory."""
        directory = QFileDialog.getExistingDirectory(
            self,
            "Select RSS Image Save Directory",
            self.rss_save_dir_input.text() or str(Path.home())
        )
        
        if directory:
            self.rss_save_dir_input.setText(directory)
            self._settings.set('sources.rss_save_directory', directory)
            self._settings.save()
            self.sources_changed.emit()
            logger.info(f"RSS save directory set to: {directory}")

    def _autocorrect_feed_url(self, url: str) -> str:
        """Best-effort autocorrect for common RSS/JSON URL mistakes.

        - Adds missing ``http://`` / ``https://``
        - Normalizes obviously broken hosts such as ``.reddit.com``
          to ``www.reddit.com``
        - Leaves the rest of the URL intact so that backend
          source-specific handling remains centralized in
          ``RSSSource``.
        """
        text = (url or "").strip()
        if not text:
            return text

        if not text.startswith(("http://", "https://")):
            # Default to https for safety; backend can still decide
            # whether to switch to JSON endpoints, etc.
            text = "https://" + text.lstrip("/")

        try:
            parsed = urlparse(text)
            scheme = parsed.scheme or "https"
            netloc = parsed.netloc
            path = parsed.path or "/"
            query = parsed.query

            # Handle inputs like "reddit.com/..." where host ended up
            # in the path instead of netloc.
            if not netloc and path:
                parts = path.lstrip("/").split("/", 1)
                candidate_host = parts[0]
                rest = "/" + parts[1] if len(parts) > 1 else "/"
                if "." in candidate_host:
                    netloc = candidate_host
                    path = rest or "/"

            host = (netloc or "").lower()
            # Fix obviously broken reddit hosts like ".reddit.com".
            if host in (".reddit.com", "reddit.com") or host.endswith(".reddit.com") and host.startswith("."):
                netloc = "www.reddit.com"

            rebuilt = urlunparse((scheme, netloc, path, "", query, ""))
            return rebuilt
        except Exception:
            return text

    def _on_clear_rss_cache_clicked(self) -> None:
        """Clear downloaded RSS/JSON images from the shared cache."""
        removed = self._clear_rss_cache()
        logger.info(f"RSS cache cleared via SourcesTab button: {removed} files removed")

    def _on_just_make_it_work_clicked(self) -> None:
        """Reset RSS feeds to a curated, known-good JSON set.

        This clears the on-disk RSS cache, wipes the current RSS feed
        list, and replaces it with a curated set of Reddit JSON feeds
        suitable for high-quality wallpapers.
        """
        self._clear_rss_cache()

        curated_feeds = [
            "https://www.reddit.com/r/CityPorn/top/.json?t=day&limit=100",
            "https://www.reddit.com/r/WaterPorn/top/.json?t=day&limit=100",
            "https://www.reddit.com/r/ArchitecturePorn/top/.json?t=day&limit=100",
            "https://www.reddit.com/r/EarthPorn/top/.json?t=day&limit=100",
            "https://www.reddit.com/r/WQHD_Wallpaper/top/.json?t=day&limit=100",
            "https://www.reddit.com/r/4kwallpaper/top/.json?t=day&limit=100",
            "https://www.reddit.com/r/SpacePorn/top/.json?t=day&limit=100",
            "https://www.reddit.com/r/AbandonedPorn/top/.json?t=day&limit=100",
        ]

        self._settings.set('sources.rss_feeds', curated_feeds)
        self._settings.save()

        self.rss_list.clear()
        for feed in curated_feeds:
            self.rss_list.addItem(feed)

        self.rss_input.clear()
        self.sources_changed.emit()

        # Update suggestion label for this session to reduce confusion.
        self.rss_suggestion_label.setText("<i>YES THESE ACTUALLY ARE SAFE FOR WORK!</i>")
        logger.info("RSS feeds reset to curated JSON defaults via 'Just Make It Work'.")

    def _clear_rss_cache(self) -> int:
        """Delete all files from the shared RSS cache directory.

        Uses the same cache location as ``RSSSource`` so that cached
        images can be cleared instantly from the settings UI.
        """
        cache_dir = Path(tempfile.gettempdir()) / "screensaver_rss_cache"
        removed = 0
        try:
            if not cache_dir.exists() or not cache_dir.is_dir():
                return 0
            for f in cache_dir.glob('*'):
                try:
                    if f.is_file():
                        f.unlink()
                        removed += 1
                except Exception as e:
                    logger.warning(f"Failed to remove RSS cache file {f}: {e}")
        except Exception as e:
            logger.error(f"RSS cache clear failed: {e}")
        return removed


class RssAutocorrectDialog(QDialog):
    """Small, styled dialog for RSS/JSON URL autocorrection.

    Uses the ``subsettingsDialog`` QSS block so it matches the rest of
    the application's dark, frameless dialogs.
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:  # type: ignore[name-defined]
        super().__init__(parent)
        self.setObjectName("subsettingsDialog")
        self.setModal(True)
        self._accepted: bool = False
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        title_frame = QFrame(self)
        title_frame.setObjectName("titleFrame")
        title_layout = QHBoxLayout(title_frame)
        title_layout.setContentsMargins(12, 8, 12, 8)
        title_layout.setSpacing(8)

        title_label = QLabel("Invalid RSS/JSON", title_frame)
        title_label.setObjectName("titleLabel")
        title_layout.addWidget(title_label)
        title_layout.addStretch()

        close_label = QLabel("×", title_frame)
        close_label.setObjectName("closeButton")
        close_label.setCursor(Qt.CursorShape.PointingHandCursor)

        def _on_close(event):  # type: ignore[override]
            self.reject()
        close_label.mousePressEvent = _on_close  # type: ignore[assignment]

        title_layout.addWidget(close_label)
        layout.addWidget(title_frame)

        content_frame = QFrame(self)
        content_frame.setObjectName("settingsContentFrame")
        content_layout = QVBoxLayout(content_frame)
        content_layout.setContentsMargins(20, 20, 20, 20)
        content_layout.setSpacing(12)

        text_label = QLabel("Invalid RSS/JSON - Try Autocorrect?", content_frame)
        text_label.setWordWrap(True)
        content_layout.addWidget(text_label)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        yes_btn = QPushButton("Try Autocorrect", content_frame)
        no_btn = QPushButton("Fuck This (No)", content_frame)
        yes_btn.clicked.connect(self._on_accept)
        no_btn.clicked.connect(self.reject)
        btn_row.addWidget(yes_btn)
        btn_row.addWidget(no_btn)
        content_layout.addLayout(btn_row)

        layout.addWidget(content_frame)
        self.adjustSize()

    def _on_accept(self) -> None:
        self._accepted = True
        self.accept()

    @property
    def accepted(self) -> bool:
        return self._accepted

