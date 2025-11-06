"""Test script to debug folder scanning issue."""
import sys
from pathlib import Path
from core.logging.logger import setup_logging, get_logger
from sources.folder_source import FolderSource

# Setup logging
setup_logging(debug=True)
logger = get_logger(__name__)

# Test the folder from the screenshot
test_folder = r"C:/Users/Basjohn/Documents/[4] WALLPAPERS/PERSONALSET"

logger.info(f"Testing folder: {test_folder}")
logger.info(f"Folder exists: {Path(test_folder).exists()}")
logger.info(f"Is directory: {Path(test_folder).is_dir()}")

# Try to list some files manually
try:
    folder = Path(test_folder)
    files = list(folder.glob("*"))
    logger.info(f"Files in folder (non-recursive): {len(files)}")
    
    # Show first 5 files
    for i, f in enumerate(files[:5]):
        logger.info(f"  {i+1}. {f.name} (is_file={f.is_file()}, suffix={f.suffix})")
    
    # Try recursive
    files_recursive = list(folder.glob("**/*"))
    logger.info(f"Files in folder (recursive): {len(files_recursive)}")
    
except Exception as e:
    logger.exception(f"Error listing files: {e}")

# Now try with FolderSource
logger.info("\n" + "="*60)
logger.info("Testing FolderSource")
logger.info("="*60)

try:
    source = FolderSource(test_folder, recursive=True)
    logger.info(f"FolderSource created: {source}")
    logger.info(f"Is available: {source.is_available()}")
    
    # Get images
    images = source.get_images()
    logger.info(f"Images found: {len(images)}")
    
    # Show first 5
    for i, img in enumerate(images[:5]):
        logger.info(f"  {i+1}. {img.title} ({img.format}, {img.file_size} bytes)")
        
except Exception as e:
    logger.exception(f"Error with FolderSource: {e}")
