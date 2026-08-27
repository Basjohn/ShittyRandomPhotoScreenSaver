"""Sources configuration tab for settings dialog.

Allows users to configure image sources:
- Folder sources (browse and add)
- RSS/JSON feed sources (add/edit/remove)
"""
from typing import Optional
from pathlib import Path
from urllib.parse import urlparse, urlunparse
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QListWidget,
    QPushButton, QLineEdit, QFileDialog, QGroupBox, QCheckBox,
    QScrollArea, QFrame, QSizePolicy,
)
from PySide6.QtGui import QPainter, QPen, QPalette
from ui.tabs import shared_styles
from ui.tabs.shared_styles import (
    NoWheelSlider,
    add_aligned_row,
    style_group_box,
    create_inline_label,  # Added missing import
)
from PySide6.QtCore import Signal, Qt

from core.settings.settings_manager import SettingsManager
from core.logging.logger import get_logger
from ui.styled_popup import StyledPopup

logger = get_logger(__name__)


class _RatioNotchBar(QWidget):
    _H_MARGIN = 14

    def __init__(self, notch_count: int = 5, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._notch_count = max(0, notch_count)
        self.setFixedHeight(10)
        policy = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setSizePolicy(policy)

    def set_notch_count(self, count: int) -> None:
        count = max(0, count)
        if count == self._notch_count:
            return
        self._notch_count = count
        self.update()

    def paintEvent(self, event) -> None:  # type: ignore[override]
        if self._notch_count <= 1:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        palette = self.palette()
        color = palette.color(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text)
        pen = QPen(color)
        pen.setWidth(2)
        painter.setPen(pen)
        total_width = max(1, self.width() - 1)
        span = self._notch_count - 1
        usable = max(0, total_width - 2 * self._H_MARGIN)
        height = self.height()
        for i in range(self._notch_count):
            if span <= 0:
                x = self._H_MARGIN
            else:
                x = self._H_MARGIN + round((i / span) * usable)
            painter.drawLine(x, 0, x, height)
        painter.end()


class SourcesTab(QWidget):
    """Sources configuration tab."""
    
    # Signals
    sources_changed = Signal()
    _LABEL_WIDTH = 160
    
    def __init__(self, settings: SettingsManager, parent: Optional[QWidget] = None):
        """
        Initialize sources tab.
        
        Args:
            settings: Settings manager
            parent: Parent widget
        """
        super().__init__(parent)
        
        self._settings = settings
        self._suppress_source_change_signals = False
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
        scroll.setStyleSheet(shared_styles.SCROLL_AREA_STYLE)
        shared_styles.bind_shared_styles(scroll, "SLIDER_STYLE")

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)
        
        # Title
        title = QLabel("Image Sources")
        shared_styles.apply_shared_label_style(title, "PAGE_TITLE_STYLE")
        layout.addWidget(title)
        
        # Folder sources group
        folder_group = QGroupBox("Folder Sources")
        style_group_box(folder_group)
        folder_layout = QVBoxLayout(folder_group)
        folder_layout.setContentsMargins(0, 12, 0, 0)
        folder_layout.setSpacing(12)
        
        # Folder list
        self.folder_list = QListWidget()
        self.folder_list.setMinimumHeight(150)
        folder_layout.addWidget(self.folder_list)
        
        # Folder buttons
        folder_buttons = QHBoxLayout()
        self.add_folder_btn = QPushButton("Add Folder...")
        shared_styles.bind_shared_styles(
            self.add_folder_btn, "SOURCE_ACTION_BUTTON_STYLE", base_style=""
        )
        self.add_folder_btn.clicked.connect(self._add_folder)
        self.remove_folder_btn = QPushButton("Remove Selected")
        shared_styles.bind_shared_styles(
            self.remove_folder_btn, "SOURCE_ACTION_BUTTON_STYLE", base_style=""
        )
        self.remove_folder_btn.clicked.connect(self._remove_folder)
        folder_buttons.addWidget(self.add_folder_btn)
        folder_buttons.addWidget(self.remove_folder_btn)
        folder_buttons.addStretch()
        folder_layout.addLayout(folder_buttons)
        
        layout.addWidget(folder_group)
        
        # Usage Ratio control (between folder and RSS groups)
        # Only interactable when both source types are configured
        ratio_row, self.ratio_label = add_aligned_row(
            layout,
            "Usage Ratio:",
            label_width=self._LABEL_WIDTH,
        )
        self.ratio_label.setContentsMargins(0, 16, 0, 0)

        self.ratio_frame = QFrame()
        self.ratio_frame.setObjectName("ratioFrame")
        shared_styles.bind_shared_styles(
            self.ratio_frame,
            "SOURCE_RATIO_ACTIVE_STYLE",
            base_style="",
        )
        frame_layout = QHBoxLayout(self.ratio_frame)
        frame_layout.setContentsMargins(0, 0, 0, 0)
        frame_layout.setSpacing(12)

        self.local_ratio_label = create_inline_label("70% Local")
        self.local_ratio_label.setMinimumWidth(100)
        self.local_ratio_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        frame_layout.addWidget(self.local_ratio_label)

        slider_column = QVBoxLayout()
        slider_column.setContentsMargins(0, 3, 0, 0)
        slider_column.setSpacing(2)

        self.ratio_slider = NoWheelSlider(Qt.Orientation.Horizontal)
        self.ratio_slider.setRange(0, 100)
        self.ratio_slider.setObjectName("presetModeSlider")
        self.ratio_slider.setToolTip("Drag to adjust the balance between local and RSS sources")
        self.ratio_slider.valueChanged.connect(self._on_ratio_slider_changed)
        slider_column.addWidget(self.ratio_slider)

        self._ratio_notch_bar = _RatioNotchBar(5)
        slider_column.addWidget(self._ratio_notch_bar)
        frame_layout.addLayout(slider_column, 1)

        self.rss_ratio_label = create_inline_label("40% RSS")
        self.rss_ratio_label.setMinimumWidth(100)
        self.rss_ratio_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        frame_layout.addWidget(self.rss_ratio_label)

        ratio_row.addWidget(self.ratio_frame, 1)

        
        # RSS sources group
        rss_group = QGroupBox("RSS / JSON Feed Sources")
        style_group_box(rss_group)
        rss_layout = QVBoxLayout(rss_group)
        rss_layout.setContentsMargins(0, 12, 0, 0)
        rss_layout.setSpacing(12)
        
        # Suggestion label (session-local; updated by "Just Make It Work")
        self.rss_suggestion_label = QLabel(
            "<i>Suggested: Add high-quality RSS/JSON image feeds here.</i>"
        )
        self.rss_suggestion_label.setWordWrap(True)
        shared_styles.bind_shared_styles(
            self.rss_suggestion_label,
            "INFO_LABEL_STYLE",
            base_style="padding: 5px;",
        )
        rss_layout.addWidget(self.rss_suggestion_label)
        
        # RSS list
        self.rss_list = QListWidget()
        self.rss_list.setMinimumHeight(150)
        rss_layout.addWidget(self.rss_list)
        
        # RSS input
        rss_input = QHBoxLayout()
        rss_input.setContentsMargins(0, 8, 0, 0)
        self.rss_input = QLineEdit()
        self.rss_input.setObjectName("rssFeedInput")
        self.rss_input.setPlaceholderText(
            "Enter RSS/JSON feed URL (e.g., https://www.reddit.com/r/CityPorn/top/.json?t=day&limit=100)..."
        )
        shared_styles.bind_shared_styles(
            self.rss_input, "RSS_INPUT_STYLE", base_style=""
        )
        self.add_rss_btn = QPushButton("Add Feed")
        shared_styles.bind_shared_styles(
            self.add_rss_btn, "SOURCE_ACTION_BUTTON_STYLE", base_style=""
        )
        self.add_rss_btn.clicked.connect(self._add_rss)
        rss_input.addWidget(self.rss_input)
        rss_input.addWidget(self.add_rss_btn)
        rss_layout.addLayout(rss_input)
        
        # RSS buttons
        rss_buttons = QHBoxLayout()
        self.clear_rss_cache_btn = QPushButton("Clear Cache")
        shared_styles.bind_shared_styles(
            self.clear_rss_cache_btn, "SOURCE_ACTION_BUTTON_STYLE", base_style=""
        )
        self.clear_rss_cache_btn.clicked.connect(self._on_clear_rss_cache_clicked)
        self.just_make_it_work_btn = QPushButton("Just Make It Work")
        shared_styles.bind_shared_styles(
            self.just_make_it_work_btn, "SOURCE_ACTION_BUTTON_STYLE", base_style=""
        )
        self.just_make_it_work_btn.setToolTip("Reset to robust default feeds (Flickr, Wikimedia, Bing, NASA)")
        self.just_make_it_work_btn.clicked.connect(self._on_just_make_it_work_clicked)
        self.remove_rss_btn = QPushButton("Remove Selected")
        shared_styles.bind_shared_styles(
            self.remove_rss_btn, "SOURCE_ACTION_BUTTON_STYLE", base_style=""
        )
        self.remove_rss_btn.clicked.connect(self._remove_rss)
        self.remove_all_rss_btn = QPushButton("Remove All")
        shared_styles.bind_shared_styles(
            self.remove_all_rss_btn, "SOURCE_ACTION_BUTTON_STYLE", base_style=""
        )
        self.remove_all_rss_btn.clicked.connect(self._remove_all_rss)
        rss_buttons.addWidget(self.clear_rss_cache_btn)
        rss_buttons.addWidget(self.just_make_it_work_btn)
        rss_buttons.addWidget(self.remove_rss_btn)
        rss_buttons.addWidget(self.remove_all_rss_btn)
        rss_buttons.addStretch()
        rss_layout.addLayout(rss_buttons)
        
        # RSS save to disk option
        self.rss_save_to_disk = QCheckBox("Save RSS Images To Disk")
        self.rss_save_to_disk.setProperty("circleIndicator", True)
        shared_styles.bind_shared_styles(
            self.rss_save_to_disk,
            "CIRCLE_CHECKBOX_STYLE",
            base_style="",
        )
        self.rss_save_to_disk.setToolTip("Hope you have space! All RSS feed images will be permanently saved to a folder of your choosing.")
        self.rss_save_to_disk.stateChanged.connect(self._on_rss_save_toggled)
        rss_layout.addWidget(self.rss_save_to_disk)
        
        # RSS save directory (hidden by default)
        save_dir_row, self.rss_save_dir_label = add_aligned_row(
            rss_layout,
            "Save Directory:",
            label_width=self._LABEL_WIDTH,
        )
        self.rss_save_dir_input = QLineEdit()
        self.rss_save_dir_input.setReadOnly(True)
        self.rss_save_dir_input.setPlaceholderText("No directory selected...")
        self.rss_save_dir_btn = QPushButton("Browse...")
        self.rss_save_dir_btn.clicked.connect(self._browse_rss_save_dir)
        save_dir_row.addWidget(self.rss_save_dir_input)
        save_dir_row.addWidget(self.rss_save_dir_btn)
        
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
        
        # Load and display usage ratio
        local_ratio = self._settings.get('sources.local_ratio', 70)
        try:
            local_ratio = int(local_ratio)
        except (ValueError, TypeError):
            local_ratio = 70
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

    def _emit_sources_changed(self) -> None:
        if self._suppress_source_change_signals:
            return
        self.sources_changed.emit()

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
                self._update_ratio_control_state()
                self._emit_sources_changed()
                logger.info(f"Added folder source: {folder}")
            else:
                StyledPopup.show_info(self, "Duplicate", "This folder is already added.")
    
    def _remove_folder(self) -> None:
        """Remove selected folder source.

        Robust against settings returning None, non-list types, or the
        folder text being desynchronised from the persisted list.
        """
        current_item = self.folder_list.currentItem()
        if not current_item:
            return

        folder = current_item.text()
        row = self.folder_list.currentRow()

        try:
            folders = self._settings.get('sources.folders', [])
            if not isinstance(folders, list):
                folders = list(folders) if folders else []

            if folder in folders:
                folders.remove(folder)
            self._settings.set('sources.folders', folders)
            self._settings.save()
        except Exception as e:
            logger.warning(f"Failed to update settings while removing folder: {e}")

        # Always remove from UI regardless of settings state
        self.folder_list.takeItem(row)
        self._update_ratio_control_state()
        self._emit_sources_changed()
        logger.info(f"Removed folder source: {folder}")
    
    def _add_rss(self) -> None:
        """Add RSS feed source."""
        raw_url = self.rss_input.text().strip()

        if not raw_url:
            return

        url = raw_url

        if not url.startswith(("http://", "https://")):
            # Use the same themed confirmation surface as the rest of Settings.
            if not StyledPopup.question(
                self,
                "Invalid RSS/JSON",
                "Invalid RSS/JSON - Try Autocorrect?",
                yes_text="Try Autocorrect",
                no_text="Fuck This (No)",
                default_to_yes=True,
            ):
                return

            url = self._autocorrect_feed_url(raw_url).strip()
            if not url or not url.startswith(("http://", "https://")):
                StyledPopup.show_warning(
                    self,
                    "Invalid URL",
                    "Could not autocorrect feed URL. Please enter a full "
                    "http:// or https:// address.",
                )
                return

        # Get current RSS feeds using dot notation
        rss_feeds = self._settings.get('sources.rss_feeds', [])

        if url not in rss_feeds:
            rss_feeds.append(url)
            self._settings.set('sources.rss_feeds', rss_feeds)
            self._settings.save()
            self.rss_list.addItem(url)
            self.rss_input.clear()
            self._update_ratio_control_state()
            self._emit_sources_changed()
            logger.info(f"Added RSS feed: {url}")
        else:
            StyledPopup.show_info(self, "Duplicate", "This RSS feed is already added.")
    
    def _remove_rss(self) -> None:
        """Remove selected RSS feed source.

        Robust against settings returning None, non-list types, or the
        URL text being desynchronised from the persisted list.
        """
        current_item = self.rss_list.currentItem()
        if not current_item:
            return

        url = current_item.text()
        row = self.rss_list.currentRow()

        try:
            rss_feeds = self._settings.get('sources.rss_feeds', [])
            if not isinstance(rss_feeds, list):
                rss_feeds = list(rss_feeds) if rss_feeds else []

            if url in rss_feeds:
                rss_feeds.remove(url)
            self._settings.set('sources.rss_feeds', rss_feeds)
            self._settings.save()
        except Exception as e:
            logger.warning(f"Failed to update settings while removing RSS feed: {e}")

        # Always remove from UI regardless of settings state
        self.rss_list.takeItem(row)
        self._update_ratio_control_state()
        self._emit_sources_changed()
        logger.info(f"Removed RSS feed: {url}")
    
    def _remove_all_rss(self) -> None:
        """Remove all RSS feed sources."""
        if self.rss_list.count() == 0:
            return
        
        # Confirm with user using styled popup
        confirmed = StyledPopup.question(
            self,
            "Remove All Feeds",
            f"Remove all {self.rss_list.count()} RSS feeds?",
            yes_text="Yes",
            no_text="No",
            default_to_yes=False
        )
        
        if confirmed:
            self._settings.set('sources.rss_feeds', [])
            self._settings.save()
            self.rss_list.clear()
            self._update_ratio_control_state()
            self._emit_sources_changed()
            logger.info("Removed all RSS feeds")
    
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
        self._emit_sources_changed()
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
            self._emit_sources_changed()
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
        
        Shows a confirmation dialog before deleting to prevent accidental data loss.
        """
        # Count files before asking
        from core.settings.storage_paths import get_rss_cache_dir
        cache_dir = get_rss_cache_dir()
        file_count = 0
        try:
            if cache_dir.exists() and cache_dir.is_dir():
                file_count = sum(1 for f in cache_dir.glob('*') if f.is_file())
        except Exception as e:
            logger.debug("[MISC] Exception suppressed: %s", e)
        
        if file_count == 0:
            StyledPopup.show_info(
                self,
                "Cache Empty",
                "The RSS image cache is already empty.",
            )
            return

        # Confirm before deleting using the central themed popup.
        if not StyledPopup.question(
            self,
            "Clear RSS Cache",
            f"This will delete {file_count} cached RSS images.<br><br>"
            "The images will be re-downloaded on the next refresh.<br><br>"
            "Continue?",
            yes_text="Yes",
            no_text="No",
            default_to_yes=False,
        ):
            return
        
        removed = self._clear_rss_cache()
        logger.info(f"RSS cache cleared via SourcesTab button: {removed} files removed")
        
        StyledPopup.show_success(
            self,
            "Cache Cleared",
            f"Successfully removed {removed} cached images.",
        )

    def _on_just_make_it_work_clicked(self) -> None:
        """Reset RSS feeds to a curated, known-good set.

        This replaces the current RSS feed list with robust defaults without
        deleting cached images.  Cache clearing remains an explicit action via
        the Clear Cache button; doing it here causes a settings-exit download
        storm and throws away still-useful wallpaper candidates.
        
        Uses DEFAULT_RSS_FEEDS from sources/rss_source.py:
        - Flickr (7 feeds): No rate limits, diverse content
        - Wikimedia (2 feeds): High quality, curated
        - Bing: Daily wallpapers
        - NASA: Space/science imagery
        
        NO Reddit feeds (cross-process rate limit issues with MC build).
        Users can manually add Reddit feeds if desired.
        """
        # Import DEFAULT_RSS_FEEDS from modular RSS package
        from sources.rss.constants import DEFAULT_RSS_FEEDS
        curated_feeds = list(DEFAULT_RSS_FEEDS.values())

        self._suppress_source_change_signals = True
        try:
            self._settings.set('sources.rss_feeds', curated_feeds)
            self._settings.save()

            self.rss_list.clear()
            for feed in curated_feeds:
                self.rss_list.addItem(feed)

            self.rss_input.clear()
            self._update_ratio_control_state()
        finally:
            self._suppress_source_change_signals = False
        self._emit_sources_changed()

        # Update suggestion label for this session to reduce confusion.
        self.rss_suggestion_label.setText("<i>YES THESE ACTUALLY ARE SAFE FOR WORK!</i>")
        logger.info("RSS feeds reset to curated JSON defaults via 'Just Make It Work' (cache preserved).")

    def _clear_rss_cache(self) -> int:
        """Delete all files from the shared RSS cache directory.

        Uses the same cache location as ``RSSSource`` so that cached
        images can be cleared instantly from the settings UI.
        Skips files locked by other processes (e.g. active RSS downloads).
        """
        from core.settings.storage_paths import get_rss_cache_dir
        cache_dir = get_rss_cache_dir()
        removed = 0
        skipped = 0
        try:
            if not cache_dir.exists() or not cache_dir.is_dir():
                return 0
            for f in cache_dir.glob('*'):
                try:
                    if f.is_file():
                        f.unlink()
                        removed += 1
                except PermissionError:
                    skipped += 1
                except Exception as e:
                    logger.debug(f"Failed to remove RSS cache file {f}: {e}")
                    skipped += 1
            if skipped:
                logger.debug(f"RSS cache clear: removed {removed}, skipped {skipped} locked files")
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
            shared_styles.bind_shared_styles(
                self.ratio_frame, "SOURCE_RATIO_ACTIVE_STYLE", base_style=""
            )
            shared_styles.apply_shared_label_style(
                self.ratio_label, "SECTION_HEADING_STYLE"
            )
        else:
            shared_styles.bind_shared_styles(
                self.ratio_frame, "SOURCE_RATIO_DISABLED_STYLE", base_style=""
            )
            shared_styles.apply_shared_label_style(
                self.ratio_label, "SECTION_HEADING_STYLE_DISABLED"
            )
        self.local_ratio_label.setEnabled(both_available)
        self.rss_ratio_label.setEnabled(both_available)
    
    def _on_ratio_slider_changed(self, value: int) -> None:
        """Handle ratio slider change - the only control for adjusting ratio."""
        # Update display labels
        self.local_ratio_label.setText(f"{value}% Local")
        self.rss_ratio_label.setText(f"{100 - value}% RSS")
        
        # Save immediately
        self._save_ratio(value)
    
    def _save_ratio(self, local_ratio: int) -> None:
        """Save the local ratio setting."""
        current = self._settings.get('sources.local_ratio', None)
        try:
            current = int(current)
        except (TypeError, ValueError):
            current = None
        if current == int(local_ratio):
            return
        self._settings.set('sources.local_ratio', local_ratio)
        self._settings.save()
        logger.info(f"Usage ratio saved: {local_ratio}% local, {100 - local_ratio}% RSS")
        self._emit_sources_changed()

