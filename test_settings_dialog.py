"""Test script for settings dialog."""
import sys
from PySide6.QtWidgets import QApplication
from ui.settings_dialog import SettingsDialog
from core.settings.settings_manager import SettingsManager
from core.animation import AnimationManager


def main():
    """Run settings dialog test."""
    app = QApplication(sys.argv)
    
    # Create managers
    settings = SettingsManager()
    animations = AnimationManager()
    
    # Create and show dialog
    dialog = SettingsDialog(settings, animations)
    dialog.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
