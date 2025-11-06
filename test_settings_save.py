"""Test settings save/load with dot notation."""
from core.settings.settings_manager import SettingsManager
from core.logging.logger import setup_logging, get_logger

setup_logging(debug=True)
logger = get_logger(__name__)

# Create settings manager
settings = SettingsManager()

# Test folder path
test_folder = r"C:/Users/Basjohn/Documents/[4] WALLPAPERS/PERSONALSET"

# Get current folders
logger.info("Current folders:")
folders = settings.get('sources.folders', [])
logger.info(f"  {folders}")

# Add test folder
logger.info(f"\nAdding folder: {test_folder}")
folders.append(test_folder)
settings.set('sources.folders', folders)
settings.save()

# Verify it was saved
logger.info("\nVerifying save:")
folders_check = settings.get('sources.folders', [])
logger.info(f"  Folders: {folders_check}")
logger.info(f"  Contains test folder: {test_folder in folders_check}")

# Create NEW settings manager to test persistence
logger.info("\nCreating new SettingsManager to test persistence:")
settings2 = SettingsManager()
folders_loaded = settings2.get('sources.folders', [])
logger.info(f"  Folders loaded: {folders_loaded}")
logger.info(f"  Contains test folder: {test_folder in folders_loaded}")

if test_folder in folders_loaded:
    logger.info("\n✅ SUCCESS! Settings are being saved and loaded correctly!")
else:
    logger.error("\n❌ FAIL! Settings not persisted!")
