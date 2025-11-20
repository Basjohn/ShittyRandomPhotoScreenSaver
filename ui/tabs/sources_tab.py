"""
Sources configuration tab for settings dialog.

Allows users to configure image sources:
- Folder sources (browse and add)
- RSS feed sources (add/edit/remove)
"""
from typing import Optional
from pathlib import Path
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QListWidget,
    QPushButton, QLineEdit, QFileDialog, QGroupBox, QMessageBox, QCheckBox,
    QScrollArea,
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
        rss_group = QGroupBox("RSS Feed Sources")
        rss_layout = QVBoxLayout(rss_group)
        
        # Suggestion label
        suggestion_label = QLabel(
            "<i>Suggested: NASA Image of the Day - "
            "https://www.nasa.gov/feeds/iotd-feed</i>"
        )
        suggestion_label.setWordWrap(True)
        suggestion_label.setStyleSheet("color: #888888; padding: 5px;")
        rss_layout.addWidget(suggestion_label)
        
        # RSS list
        self.rss_list = QListWidget()
        self.rss_list.setMinimumHeight(150)
        rss_layout.addWidget(self.rss_list)
        
        # RSS input
        rss_input = QHBoxLayout()
        self.rss_input = QLineEdit()
        self.rss_input.setPlaceholderText("Enter RSS feed URL (e.g., https://www.nasa.gov/feeds/iotd-feed)...")
        self.add_rss_btn = QPushButton("Add Feed")
        self.add_rss_btn.clicked.connect(self._add_rss)
        rss_input.addWidget(self.rss_input)
        rss_input.addWidget(self.add_rss_btn)
        rss_layout.addLayout(rss_input)
        
        # RSS buttons
        rss_buttons = QHBoxLayout()
        self.remove_rss_btn = QPushButton("Remove Selected")
        self.remove_rss_btn.clicked.connect(self._remove_rss)
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
        self.rss_save_to_disk.setChecked(rss_save_enabled)
        
        rss_save_dir = self._settings.get('sources.rss_save_directory', '')
        if rss_save_dir:
            self.rss_save_dir_input.setText(rss_save_dir)
        
        # Show/hide save directory controls based on checkbox
        self.rss_save_dir_label.setVisible(rss_save_enabled)
        self.rss_save_dir_input.setVisible(rss_save_enabled)
        self.rss_save_dir_btn.setVisible(rss_save_enabled)
        
        logger.debug(f"Loaded {len(folders)} folders and {len(rss_feeds)} RSS feeds")
    
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
        url = self.rss_input.text().strip()
        
        if url:
            # Basic URL validation
            if not url.startswith(('http://', 'https://')):
                QMessageBox.warning(self, "Invalid URL", "RSS feed URL must start with http:// or https://")
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
