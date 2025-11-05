"""
Sources configuration tab for settings dialog.

Allows users to configure image sources:
- Folder sources (browse and add)
- RSS feed sources (add/edit/remove)
"""
from typing import Optional, List
from pathlib import Path
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QListWidget,
    QPushButton, QLineEdit, QFileDialog, QGroupBox, QMessageBox
)
from PySide6.QtCore import Signal

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
        layout = QVBoxLayout(self)
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
        
        # RSS list
        self.rss_list = QListWidget()
        self.rss_list.setMinimumHeight(150)
        rss_layout.addWidget(self.rss_list)
        
        # RSS input
        rss_input = QHBoxLayout()
        self.rss_input = QLineEdit()
        self.rss_input.setPlaceholderText("Enter RSS feed URL...")
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
        
        layout.addWidget(rss_group)
        
        layout.addStretch()
    
    def _load_sources(self) -> None:
        """Load sources from settings."""
        # Load folders
        folders = self._settings.get('sources', {}).get('folders', [])
        self.folder_list.clear()
        for folder in folders:
            self.folder_list.addItem(folder)
        
        # Load RSS feeds
        rss_feeds = self._settings.get('sources', {}).get('rss_feeds', [])
        self.rss_list.clear()
        for feed in rss_feeds:
            self.rss_list.addItem(feed)
        
        logger.debug(f"Loaded {len(folders)} folders and {len(rss_feeds)} RSS feeds")
    
    def _add_folder(self) -> None:
        """Add folder source."""
        folder = QFileDialog.getExistingDirectory(
            self,
            "Select Image Folder",
            str(Path.home())
        )
        
        if folder:
            # Get current folders
            folders = self._settings.get('sources', {}).get('folders', [])
            
            if folder not in folders:
                folders.append(folder)
                self._settings.set('sources', {'folders': folders})
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
            
            # Remove from settings
            folders = self._settings.get('sources', {}).get('folders', [])
            if folder in folders:
                folders.remove(folder)
                self._settings.set('sources', {'folders': folders})
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
            
            # Get current RSS feeds
            rss_feeds = self._settings.get('sources', {}).get('rss_feeds', [])
            
            if url not in rss_feeds:
                rss_feeds.append(url)
                self._settings.set('sources', {'rss_feeds': rss_feeds})
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
            
            # Remove from settings
            rss_feeds = self._settings.get('sources', {}).get('rss_feeds', [])
            if url in rss_feeds:
                rss_feeds.remove(url)
                self._settings.set('sources', {'rss_feeds': rss_feeds})
                self._settings.save()
                self.rss_list.takeItem(self.rss_list.currentRow())
                self.sources_changed.emit()
                logger.info(f"Removed RSS feed: {url}")
