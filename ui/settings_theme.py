"""Settings Dialog Theme Loading - Extracted from settings_dialog.py.

Contains the theme loading and QSS application logic.
"""

from __future__ import annotations

from pathlib import Path

from core.logging.logger import get_logger

logger = get_logger(__name__)


def load_theme(widget) -> None:
    """Load dark theme stylesheet."""
    try:
        theme_path = Path(__file__).parent.parent / "themes" / "dark.qss"
        if theme_path.exists():
            with open(theme_path, 'r', encoding='utf-8') as f:
                stylesheet = f.read()
                
                # Add custom styles for settings dialog
                custom_styles = """
                /* Settings Dialog Custom Styles */
                QDialog {
                    background-color: transparent;
                    border: 3px solid #ffffff;
                    border-radius: 12px;
                }
                
                #dialogContainer {
                    background-color: #2B2B2B;
                    border: 2px solid #9a9a9a;
                    border-radius: 10px;
                }
                
                #customTitleBar {
                    background-color: #1E1E1E;
                    border-top-left-radius: 10px;
                    border-top-right-radius: 10px;
                }
                
                #titleBarLabel {
                    color: #ffffff;
                    padding-left: 10px;
                }
                
                #titleBarButton {
                    background-color: transparent;
                    color: #ffffff;
                    border: none;
                    font-size: 16px;
                    font-weight: bold;
                }
                
                #titleBarButton:hover {
                    background-color: rgba(62, 62, 62, 0.8);
                    border-radius: 4px;
                }
                
                #titleBarCloseButton {
                    background-color: transparent;
                    color: #ffffff;
                    border: none;
                    font-size: 18px;
                    font-weight: bold;
                }
                
                #titleBarCloseButton:hover {
                    background-color: rgba(232, 17, 35, 0.8);
                    border-radius: 4px;
                }
                
                #sidebar {
                    background-color: #232323;
                    border-radius: 8px;
                }
                
                #tabButton {
                    background-color: #2B2B2B;
                    color: #cccccc;
                    border: none;
                    text-align: left;
                    padding: 10px 20px;
                    margin: 3px 5px 5px 3px; /* extra space for bottom-right shadow */
                    border-radius: 6px;
                    border-bottom: 2px solid rgba(0, 0, 0, 0.6);
                    border-right: 2px solid rgba(0, 0, 0, 0.7);
                }
                
                #tabButton:hover {
                    background-color: #3E3E3E;
                    color: #ffffff;
                }
                
                #tabButton:checked {
                    background-color: #3E3E3E;
                    color: #ffffff;
                    font-weight: bold;
                }
                
                #contentArea {
                    background-color: #1E1E1E;
                    border-radius: 8px;
                    padding: 20px;
                }
                
                /* Input fields and controls - dark theme, no bright white */
                QLineEdit {
                    background-color: rgba(45, 45, 45, 0.8);
                    color: #ffffff;
                    border: 1px solid rgba(90, 90, 90, 0.8);
                    border-radius: 4px;
                    padding: 6px;
                }
                
                QLineEdit:focus {
                    border: 1px solid rgba(200, 200, 200, 0.85);
                }
                
                QComboBox {
                    background-color: rgba(45, 45, 45, 0.8);
                    color: #ffffff;
                    border-radius: 4px;
                    padding: 6px;
                    border-top: 1px solid rgba(90, 90, 90, 0.75);
                    border-left: 1px solid rgba(90, 90, 90, 0.75);
                    border-right: 2px solid rgba(0, 0, 0, 0.7);
                    border-bottom: 2px solid rgba(0, 0, 0, 0.75);
                }
                
                QComboBox:hover,
                QComboBox:focus {
                    border-top: 1px solid rgba(200, 200, 200, 0.8);
                    border-left: 1px solid rgba(200, 200, 200, 0.8);
                    border-right: 2px solid rgba(0, 0, 0, 0.7);
                    border-bottom: 2px solid rgba(0, 0, 0, 0.75);
                }
                
                QComboBox::drop-down {
                    border: none;
                    background-color: rgba(62, 62, 62, 0.8);
                    border-radius: 2px;
                }
                
                QComboBox QAbstractItemView {
                    background-color: rgba(45, 45, 45, 0.95);
                    color: #ffffff;
                    border: 1px solid rgba(90, 90, 90, 0.8);
                    selection-background-color: rgba(80, 80, 80, 0.95);
                }
                QAbstractItemView::item:selected {
                    background-color: rgba(70, 70, 70, 0.9);
                    color: #ffffff;
                }
                QAbstractItemView::item:hover {
                    background-color: rgba(62, 62, 62, 0.9);
                }
                
                QSpinBox {
                    background-color: rgba(45, 45, 45, 0.8);
                    color: #ffffff;
                    border: 1px solid rgba(90, 90, 90, 0.8);
                    border-radius: 4px;
                    padding: 4px;
                }
                
                QSpinBox:focus {
                    border: 1px solid rgba(200, 200, 200, 0.85);
                }
                
                QListWidget {
                    background-color: rgba(35, 35, 35, 0.8);
                    color: #ffffff;
                    border: 1px solid rgba(90, 90, 90, 0.8);
                    border-radius: 4px;
                }
                
                QListWidget::item:selected {
                    background-color: rgba(70, 70, 70, 0.8);
                    border-left: 3px solid rgba(120, 120, 120, 0.9);
                }
                
                QListWidget::item:hover {
                    background-color: rgba(62, 62, 62, 0.8);
                }
                
                QPushButton {
                    background-color: rgba(60, 60, 60, 0.8);
                    color: #ffffff;
                    border-radius: 4px;
                    padding: 8px 16px;
                    border-top: 1px solid rgba(80, 80, 80, 0.7);
                    border-left: 1px solid rgba(80, 80, 80, 0.7);
                    border-right: 2px solid rgba(0, 0, 0, 0.65);
                    border-bottom: 2px solid rgba(0, 0, 0, 0.7);
                }
                
                QPushButton:hover {
                    background-color: rgba(75, 75, 75, 0.8);
                    border-top: 1px solid rgba(96, 96, 96, 0.8);
                    border-left: 1px solid rgba(96, 96, 96, 0.8);
                    border-right: 2px solid rgba(0, 0, 0, 0.7);
                    border-bottom: 2px solid rgba(0, 0, 0, 0.75);
                }
                
                QPushButton:pressed {
                    background-color: rgba(50, 50, 50, 0.8);
                    border-top: 1px solid rgba(60, 60, 60, 0.75);
                    border-left: 1px solid rgba(60, 60, 60, 0.75);
                    border-right: 1px solid rgba(0, 0, 0, 0.65);
                    border-bottom: 1px solid rgba(0, 0, 0, 0.65);
                    margin-top: 1px;
                    margin-left: 1px;
                }
                
                QGroupBox {
                    background-color: rgba(40, 40, 40, 0.8);
                    border: 1px solid rgba(90, 90, 90, 0.8);
                    border-radius: 6px;
                    margin-top: 15px;
                    margin-bottom: 10px;
                    padding: 15px 10px 10px 10px;
                    color: #ffffff;
                }
                
                QGroupBox::title {
                    subcontrol-origin: margin;
                    subcontrol-position: top left;
                    padding: 2px 8px;
                    margin-top: 5px;
                    color: #ffffff;
                }
                
                QCheckBox {
                    color: #ffffff;
                    spacing: 8px;
                }
                
                QCheckBox::indicator {
                    width: 18px;
                    height: 18px;
                    background-color: rgba(45, 45, 45, 0.8);
                    border-radius: 3px;
                    border-top: 1px solid rgba(90, 90, 90, 0.75);
                    border-left: 1px solid rgba(90, 90, 90, 0.75);
                    border-right: 2px solid rgba(0, 0, 0, 0.7);
                    border-bottom: 2px solid rgba(0, 0, 0, 0.75);
                }
                
                QCheckBox::indicator:checked {
                    background-color: rgba(210, 210, 210, 0.85);
                    border-top: 1px solid rgba(200, 200, 200, 0.8);
                    border-left: 1px solid rgba(200, 200, 200, 0.8);
                    border-right: 2px solid rgba(60, 60, 60, 0.7);
                    border-bottom: 2px solid rgba(60, 60, 60, 0.75);
                }
                
                QLabel {
                    color: #ffffff;
                }
                """
                
                widget.setStyleSheet(stylesheet + custom_styles)
                logger.debug("Theme loaded successfully")
        else:
            logger.warning(f"[FALLBACK] Theme file not found: {theme_path}")
    except Exception as e:
        logger.exception(f"Failed to load theme: {e}")

