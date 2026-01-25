"""Sources configuration tab for settings dialog.

Allows users to configure image sources:
- Folder sources (browse and add)
- RSS/JSON feed sources (add/edit/remove)
"""
from pathlib import Path
import tempfile
from typing import Optional
from urllib.parse import urlparse, urlunparse

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QListWidget,
    QPushButton, QLineEdit, QFileDialog, QGroupBox, QCheckBox,
    QScrollArea, QDialog, QFrame, QSlider,
)
from PySide6.QtCore import Signal, Qt

from ui.styled_popup import StyledPopup

from core.settings.settings_manager import SettingsManager
from core.threading import get_thread_manager
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

    def load_from_settings(self) -> None:
        """Reload all UI controls from settings manager (called after preset change)."""
        self._load_sources()
        logger.debug("[SOURCES_TAB] Reloaded from settings")

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

        # Usage Ratio control (between folder and RSS groups)
        # Only interactable when both source types are configured
        self.ratio_frame = QFrame()
        self.ratio_frame.setObjectName("ratioFrame")
        self.ratio_frame.setStyleSheet("""
            #ratioFrame {
                background-color: #2a2a2a;
                border: 1px solid #3a3a3a;
                border-radius: 6px;
                padding: 8px;
            }
        """)
        ratio_layout = QHBoxLayout(self.ratio_frame)
        ratio_layout.setContentsMargins(12, 8, 12, 8)
        ratio_layout.setSpacing(10)

        self.ratio_label = QLabel("Usage Ratio:")
        self.ratio_label.setStyleSheet("color: #cccccc; font-weight: bold;")
        ratio_layout.addWidget(self.ratio_label)

        # Local percentage display label (read-only)
        self.local_ratio_label = QLabel("60% Local")
        self.local_ratio_label.setStyleSheet("color: #aaaaaa; min-width: 70px;")
        self.local_ratio_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        ratio_layout.addWidget(self.local_ratio_label)

        # Slider is the ONLY control for adjusting ratio
        self.ratio_slider = QSlider(Qt.Orientation.Horizontal)
        self.ratio_slider.setRange(0, 100)
        self.ratio_slider.setMinimumWidth(200)
        self.ratio_slider.setToolTip("Drag to adjust the balance between local and RSS sources")
        self.ratio_slider.valueChanged.connect(self._on_ratio_slider_changed)
        ratio_layout.addWidget(self.ratio_slider)

        # RSS percentage display label (read-only)
        self.rss_ratio_label = QLabel("40% RSS")
        self.rss_ratio_label.setStyleSheet("color: #aaaaaa; min-width: 70px;")
        self.rss_ratio_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        ratio_layout.addWidget(self.rss_ratio_label)

        ratio_layout.addStretch()

        layout.addWidget(self.ratio_frame)

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
        self.remove_all_rss_btn = QPushButton("Remove All")
        self.remove_all_rss_btn.setToolTip("Remove every RSS/JSON feed from the list.")
        self.remove_all_rss_btn.clicked.connect(self._remove_all_rss)
        rss_buttons.addWidget(self.clear_rss_cache_btn)
        rss_buttons.addWidget(self.just_make_it_work_btn)
        rss_buttons.addWidget(self.remove_rss_btn)
        rss_buttons.addWidget(self.remove_all_rss_btn)
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

        self._folder_section = folder_group
        self._rss_section = rss_group

        scroll.setWidget(content)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

    def _load_sources(self) -> None:
        """Load sources from settings.

        Phase 2.2: Display priority numbers for each source.
        Priority = list order (1 = highest priority).
        """
        # Load folders using dot notation
        folders = self._settings.get('sources.folders', [])
        self.folder_list.clear()
        for idx, folder in enumerate(folders, 1):
            self.folder_list.addItem(f"[{idx}] {folder}")

        # Load RSS feeds using dot notation
        rss_feeds = self._settings.get('sources.rss_feeds', [])
        self.rss_list.clear()
        for idx, feed in enumerate(rss_feeds, 1):
            self.rss_list.addItem(f"[{idx}] {feed}")

        # Load and display usage ratio
        local_ratio = self._settings.get('sources.local_ratio', 60)
        try:
            local_ratio = int(local_ratio)
        except (ValueError, TypeError):
            local_ratio = 60
        local_ratio = max(0, min(100, local_ratio))

        # Block signals to prevent save loops during load
        self.ratio_slider.blockSignals(True)
        self.ratio_slider.setValue(local_ratio)
        self.ratio_slider.blockSignals(False)

        # Update display labels
        self.local_ratio_label.setText(f"{local_ratio}% Local")
        self.rss_ratio_label.setText(f"{100 - local_ratio}% RSS")

        # Update ratio control visibility/enabled state
        self._update_ratio_control_state()

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

    def _strip_priority_prefix(self, text: str) -> str:
        """Phase 2.2: Strip priority prefix like '[1] ' from list item text."""
        import re
        match = re.match(r'^\[\d+\]\s*', text)
        if match:
            return text[match.end():]
        return text

    def _refresh_list_priorities(self) -> None:
        """Phase 2.2: Refresh priority numbers after add/remove."""
        # Refresh folder list
        folders = self._settings.get('sources.folders', [])
        self.folder_list.clear()
        for idx, folder in enumerate(folders, 1):
            self.folder_list.addItem(f"[{idx}] {folder}")

        # Refresh RSS list
        rss_feeds = self._settings.get('sources.rss_feeds', [])
        self.rss_list.clear()
        for idx, feed in enumerate(rss_feeds, 1):
            self.rss_list.addItem(f"[{idx}] {feed}")

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
                # Phase 2.2: Add with priority number
                idx = len(folders)
                self.folder_list.addItem(f"[{idx}] {folder}")
                self._update_ratio_control_state()
                self.sources_changed.emit()
                logger.info(f"Added folder source: {folder}")
            else:
                StyledPopup.show_info(self, "Duplicate", "This folder is already added.")

    def _remove_folder(self) -> None:
        """Remove selected folder source."""
        current_item = self.folder_list.currentItem()
        if current_item:
            # Phase 2.2: Strip priority prefix to get actual folder path
            folder = self._strip_priority_prefix(current_item.text())

            # Get current folders using dot notation
            folders = self._settings.get('sources.folders', [])

            if folder in folders:
                folders.remove(folder)
                self._settings.set('sources.folders', folders)
                self._settings.save()
                # Phase 2.2: Refresh to update priority numbers
                self._refresh_list_priorities()
                self._update_ratio_control_state()
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
                StyledPopup.show_warning(self, "Invalid URL", "Could not autocorrect feed URL.\nPlease enter a full http:// or https:// address.")
                return

        # Get current RSS feeds using dot notation
        rss_feeds = self._settings.get('sources.rss_feeds', [])

        if url not in rss_feeds:
            rss_feeds.append(url)
            self._settings.set('sources.rss_feeds', rss_feeds)
            self._settings.save()
            # Phase 2.2: Add with priority number
            idx = len(rss_feeds)
            self.rss_list.addItem(f"[{idx}] {url}")
            self.rss_input.clear()
            self._update_ratio_control_state()
            self.sources_changed.emit()
            logger.info(f"Added RSS feed: {url}")
        else:
            StyledPopup.show_info(self, "Duplicate", "This RSS feed is already added.")

    def _remove_rss(self) -> None:
        """Remove selected RSS feed source."""
        current_item = self.rss_list.currentItem()
        if current_item:
            # Phase 2.2: Strip priority prefix to get actual URL
            url = self._strip_priority_prefix(current_item.text())

            # Get current RSS feeds using dot notation
            rss_feeds = self._settings.get('sources.rss_feeds', [])

            if url in rss_feeds:
                rss_feeds.remove(url)
                self._settings.set('sources.rss_feeds', rss_feeds)
                self._settings.save()
                # Phase 2.2: Refresh to update priority numbers
                self._refresh_list_priorities()
                self._update_ratio_control_state()
                self.sources_changed.emit()
                logger.info(f"Removed RSS feed: {url}")

    def _remove_all_rss(self) -> None:
        """Remove all RSS feeds in a single action."""
        if self.rss_list.count() == 0:
            return

        if not StyledPopup.question(
            self,
            "Remove All RSS Feeds",
            "This will remove every RSS/JSON feed from the list.\n\nContinue?",
        ):
            return

        self.rss_list.clear()
        self._settings.set('sources.rss_feeds', [])
        self._settings.save()
        self._update_ratio_control_state()
        self.sources_changed.emit()
        logger.info("Removed all RSS feeds via SourcesTab button.")

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
        except Exception as e:
            logger.debug("[MISC] Exception suppressed: %s", e)
            return text

    def _on_clear_rss_cache_clicked(self) -> None:
        """Clear downloaded RSS/JSON images from the shared cache.

        Phase 2.1: Uses ThreadManager IO pool for async file operations.
        Shows a confirmation dialog before deleting to prevent accidental data loss.
        """
        # Disable button during operation
        self.clear_rss_cache_btn.setEnabled(False)
        self.clear_rss_cache_btn.setText("Counting...")

        def _count_files() -> int:
            """Count cache files on IO thread."""
            cache_dir = Path(tempfile.gettempdir()) / "screensaver_rss_cache"
            try:
                if cache_dir.exists() and cache_dir.is_dir():
                    return sum(1 for f in cache_dir.glob('*') if f.is_file())
            except Exception as e:
                logger.debug("[MISC] Exception suppressed: %s", e)
            return 0

        def _on_count_done(result) -> None:
            """Handle file count result - must run on UI thread."""
            def _ui_update():
                self.clear_rss_cache_btn.setText("Clear RSS Cache")
                self.clear_rss_cache_btn.setEnabled(True)

                file_count = result.result if result and result.success else 0

                if file_count == 0:
                    StyledPopup.show_info(
                        self,
                        "Cache Empty",
                        "The RSS image cache is already empty.",
                    )
                    return

                # Confirm before deleting
                if not StyledPopup.question(
                    self,
                    "Clear RSS Cache",
                    f"This will delete {file_count} cached RSS images.\n\n"
                    "The images will be re-downloaded on the next refresh.\n\n"
                    "Continue?",
                    yes_text="Clear Cache",
                    no_text="Cancel",
                ):
                    return

                # Proceed with async deletion
                self._clear_rss_cache_async()
            get_thread_manager().invoke_in_ui_thread(_ui_update)

        # Run file count on IO thread
        get_thread_manager().submit_io_task(_count_files, callback=_on_count_done)

    def _clear_rss_cache_async(self) -> None:
        """Phase 2.1: Async cache clear using ThreadManager."""
        self.clear_rss_cache_btn.setEnabled(False)
        self.clear_rss_cache_btn.setText("Clearing...")

        def _do_clear() -> int:
            """Delete cache files on IO thread."""
            return self._clear_rss_cache()

        def _on_clear_done(result) -> None:
            """Handle clear result - must run on UI thread."""
            def _ui_update():
                self.clear_rss_cache_btn.setText("Clear RSS Cache")
                self.clear_rss_cache_btn.setEnabled(True)

                removed = result.result if result and result.success else 0
                logger.info(f"RSS cache cleared via SourcesTab button: {removed} files removed")

                StyledPopup.show_info(
                    self,
                    "Cache Cleared",
                    f"Successfully removed {removed} cached images.",
                )
            get_thread_manager().invoke_in_ui_thread(_ui_update)

        get_thread_manager().submit_io_task(_do_clear, callback=_on_clear_done)

    def _on_just_make_it_work_clicked(self) -> None:
        """Reset RSS feeds to a curated, known-good set.

        Phase 2.1: Uses async cache clear to prevent UI blocking.
        This clears the on-disk RSS cache, wipes the current RSS feed
        list, and replaces it with a curated set of image feeds.

        Feed order is important:
        1. Non-Reddit sources first (NASA, Bing) - no rate limits
        2. Reddit sources last - aggressive rate limiting requires delays
        """
        # Disable button during operation
        self.just_make_it_work_btn.setEnabled(False)
        self.just_make_it_work_btn.setText("Setting up...")

        def _do_clear() -> int:
            """Clear cache on IO thread."""
            return self._clear_rss_cache()

        def _on_clear_done(result) -> None:
            """Apply curated feeds after cache clear - must run on UI thread."""
            def _ui_update():
                self.just_make_it_work_btn.setText("Just Make It Work")
                self.just_make_it_work_btn.setEnabled(True)
                self._apply_curated_feeds()
            get_thread_manager().invoke_in_ui_thread(_ui_update)

        get_thread_manager().submit_io_task(_do_clear, callback=_on_clear_done)

    def _apply_curated_feeds(self) -> None:
        """Apply curated RSS feeds after cache is cleared."""

        # Non-Reddit sources first (no rate limiting, faster cache building)
        # Then Reddit sources (rate limited, processed with delays)
        curated_feeds = [
            # === HIGH-PRIORITY FLICKR SOURCES (ranked first) ===
            "https://api.flickr.com/services/feeds/photos_public.gne?tags=cityscape&format=rss2",
            "https://api.flickr.com/services/feeds/photos_public.gne?tags=city,night&format=rss2",
            "https://api.flickr.com/services/feeds/photos_public.gne?tags=rain,street&format=rss2",
            # === NON-REDDIT SOURCES (processed before rate-limited feeds) ===
            "https://www.bing.com/HPImageArchive.aspx?format=rss&idx=0&n=8&mkt=en-US",  # Bing daily (high quality)
            "https://www.nasa.gov/feeds/iotd-feed",  # NASA Image of the Day
            # === REDDIT SOURCES (processed last with staggered delays) ===
            "https://www.reddit.com/r/EarthPorn/top/.json?t=day&limit=25",
            "https://www.reddit.com/r/SpacePorn/top/.json?t=day&limit=25",
            "https://www.reddit.com/r/CityPorn/top/.json?t=day&limit=25",
            "https://www.reddit.com/r/ArchitecturePorn/top/.json?t=day&limit=25",
            "https://www.reddit.com/r/WaterPorn/top/.json?t=day&limit=25",
            "https://www.reddit.com/r/WQHD_Wallpaper/top/.json?t=day&limit=25",
            "https://www.reddit.com/r/4kwallpaper/top/.json?t=day&limit=25",
            "https://www.reddit.com/r/AbandonedPorn/top/.json?t=day&limit=25",
        ]

        self._settings.set('sources.rss_feeds', curated_feeds)
        self._settings.save()

        self.rss_list.clear()
        for feed in curated_feeds:
            self.rss_list.addItem(feed)

        self.rss_input.clear()
        self._update_ratio_control_state()
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

    def _update_ratio_control_state(self) -> None:
        """Update ratio control enabled state based on source availability."""
        folders = self._settings.get('sources.folders', [])
        rss_feeds = self._settings.get('sources.rss_feeds', [])

        has_folders = len(folders) > 0
        has_rss = len(rss_feeds) > 0
        both_available = has_folders and has_rss

        # Only enable slider when both source types are configured
        self.ratio_slider.setEnabled(both_available)

        # Update styling to indicate disabled state
        if both_available:
            self.ratio_frame.setStyleSheet("""
                #ratioFrame {
                    background-color: #2a2a2a;
                    border: 1px solid #3a3a3a;
                    border-radius: 6px;
                    padding: 8px;
                }
            """)
            self.ratio_label.setStyleSheet("color: #cccccc; font-weight: bold;")
            self.local_ratio_label.setStyleSheet("color: #aaaaaa; min-width: 70px;")
            self.rss_ratio_label.setStyleSheet("color: #aaaaaa; min-width: 70px;")
        else:
            self.ratio_frame.setStyleSheet("""
                #ratioFrame {
                    background-color: #1a1a1a;
                    border: 1px solid #2a2a2a;
                    border-radius: 6px;
                    padding: 8px;
                }
            """)
            self.ratio_label.setStyleSheet("color: #666666; font-weight: bold;")
            self.local_ratio_label.setStyleSheet("color: #555555; min-width: 70px;")
            self.rss_ratio_label.setStyleSheet("color: #555555; min-width: 70px;")

    def _on_ratio_slider_changed(self, value: int) -> None:
        """Handle ratio slider change - the only control for adjusting ratio."""
        # Update display labels
        self.local_ratio_label.setText(f"{value}% Local")
        self.rss_ratio_label.setText(f"{100 - value}% RSS")

        # Save immediately
        self._save_ratio(value)

    def _save_ratio(self, local_ratio: int) -> None:
        """Save the local ratio setting."""
        self._settings.set('sources.local_ratio', local_ratio)
        self._settings.save()
        logger.info(f"Usage ratio saved: {local_ratio}% local, {100 - local_ratio}% RSS")
        self.sources_changed.emit()

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

