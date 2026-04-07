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
                /* Settings Dialog Custom Styles
                   NOTE: Qt QSS rgba() alpha MUST be integer 0-255.
                   Float values (e.g. 0.8) are truncated to 0! */
                QDialog {
                    background-color: transparent;
                    border: none;
                    border-radius: 12px;
                }
                
                #dialogContainer {
                    background-color: rgba(0, 0, 0, 10);
                    border: none;
                    border-radius: 10px;
                }
                
                #customTitleBar {
                    background-color: rgba(12, 12, 12, 209);
                    border-top-left-radius: 10px;
                    border-top-right-radius: 10px;
                }
                
                #titleBarLabel {
                    color: #ffffff;
                    padding-left: 10px;
                }
                
                #titleBarButton {
                    background-color: rgba(0, 0, 0, 0);
                    color: #ffffff;
                    border: none;
                    font-size: 16px;
                    font-weight: bold;
                }
                
                #titleBarButton:hover {
                    background-color: rgba(62, 62, 62, 204);
                    border-radius: 4px;
                }
                
                #titleBarCloseButton {
                    background-color: rgba(0, 0, 0, 0);
                    color: #ffffff;
                    border: none;
                    font-size: 18px;
                    font-weight: bold;
                }
                
                #titleBarCloseButton:hover {
                    background-color: rgba(232, 17, 35, 204);
                    border-radius: 4px;
                }
                
                #sidebar {
                    background-color: rgba(20, 20, 20, 150);
                    border: 1px solid #ffffff;
                    border-radius: 8px;
                }
                
                #tabButton {
                    background-color: rgba(43, 43, 43, 80);
                    color: #cccccc;
                    border: none;
                    text-align: left;
                    padding: 10px 20px;
                    margin: 3px 5px 5px 3px;
                    border-radius: 6px;
                    border-bottom: 2px solid rgba(0, 0, 0, 80);
                    border-right: 2px solid rgba(0, 0, 0, 100);
                    font-family: 'Jost', 'Segoe UI', 'Arial', 'Sans Serif';
                    font-weight: 600;
                    font-size: 13px;
                }
                
                #tabButton:hover {
                    background-color: rgba(62, 62, 62, 110);
                    color: #ffffff;
                }
                
                #tabButton:checked {
                    background-color: rgba(62, 62, 62, 130);
                    color: #ffffff;
                    font-weight: 700;
                }
                
                #contentArea {
                    background-color: transparent;
                    border: 1px solid #ffffff;
                    border-radius: 8px;
                    padding: 20px;
                }
                
                #contentArea > QWidget {
                    background: transparent;
                }
                
                QListWidget {
                    background-color: rgba(35, 35, 35, 204);
                    color: #ffffff;
                    border: 1px solid rgba(90, 90, 90, 204);
                    border-radius: 4px;
                }
                
                QListWidget::item:selected {
                    background-color: rgba(70, 70, 70, 204);
                    border-left: 3px solid rgba(120, 120, 120, 230);
                }
                
                QListWidget::item:hover {
                    background-color: rgba(62, 62, 62, 204);
                }
                
                QPushButton {
                    background-color: rgba(60, 60, 60, 204);
                    color: #ffffff;
                    border-radius: 4px;
                    padding: 8px 16px;
                    border-top: 1px solid rgba(80, 80, 80, 179);
                    border-left: 1px solid rgba(80, 80, 80, 179);
                    border-right: 2px solid rgba(0, 0, 0, 166);
                    border-bottom: 2px solid rgba(0, 0, 0, 179);
                }
                
                QPushButton:hover {
                    background-color: rgba(75, 75, 75, 204);
                    border-top: 1px solid rgba(96, 96, 96, 204);
                    border-left: 1px solid rgba(96, 96, 96, 204);
                    border-right: 2px solid rgba(0, 0, 0, 179);
                    border-bottom: 2px solid rgba(0, 0, 0, 191);
                }
                
                QPushButton:pressed {
                    background-color: rgba(50, 50, 50, 204);
                    border-top: 1px solid rgba(60, 60, 60, 191);
                    border-left: 1px solid rgba(60, 60, 60, 191);
                    border-right: 1px solid rgba(0, 0, 0, 166);
                    border-bottom: 1px solid rgba(0, 0, 0, 166);
                    margin-top: 1px;
                    margin-left: 1px;
                }
                
                QGroupBox {
                    background-color: rgba(60, 60, 60, 100);
                    border: 1px solid #ffffff;
                    border-radius: 18px;
                    margin-top: 20px;
                    margin-bottom: 12px;
                    padding: 18px 24px 18px 24px;
                    color: #ffffff;
                }
                
                QGroupBox::title {
                    subcontrol-origin: margin;
                    subcontrol-position: top left;
                    padding: 2px 10px;
                    margin-top: 5px;
                    color: #ffffff;
                    font-family: 'Jost', 'Segoe UI', 'Arial', 'Sans Serif';
                    font-weight: 800;
                    font-size: 15px;
                    letter-spacing: 0.5px;
                }
                
                QCheckBox {
                    color: #ffffff;
                    spacing: 8px;
                }
                
                QCheckBox::indicator {
                    width: 18px;
                    height: 18px;
                    background-color: rgba(45, 45, 45, 204);
                    border-radius: 3px;
                    border-top: 1px solid rgba(90, 90, 90, 191);
                    border-left: 1px solid rgba(90, 90, 90, 191);
                    border-right: 2px solid rgba(0, 0, 0, 179);
                    border-bottom: 2px solid rgba(0, 0, 0, 191);
                }
                
                QCheckBox::indicator:checked {
                    background-color: rgba(210, 210, 210, 217);
                    border-top: 1px solid rgba(200, 200, 200, 204);
                    border-left: 1px solid rgba(200, 200, 200, 204);
                    border-right: 2px solid rgba(60, 60, 60, 179);
                    border-bottom: 2px solid rgba(60, 60, 60, 191);
                }
                
                QLabel {
                    color: #ffffff;
                    background-color: rgba(0, 0, 0, 0);
                }
                """
                
                widget.setStyleSheet(stylesheet + custom_styles)
                logger.debug("Theme loaded successfully")
        else:
            logger.warning(f"[FALLBACK] Theme file not found: {theme_path}")
    except Exception as e:
        logger.exception(f"Failed to load theme: {e}")

