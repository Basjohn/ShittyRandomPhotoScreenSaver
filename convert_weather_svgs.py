#!/usr/bin/env python3
"""Convert SVG weather icons to PNG with transparency using Qt (Windows-compatible)."""
import sys
from pathlib import Path

def convert_svgs_to_pngs():
    """Convert all SVG files in weather directory to PNG with transparency."""
    weather_dir = Path("F:/Programming/Apps/ShittyRandomPhotoScreenSaver2_5/images/weather")
    
    if not weather_dir.exists():
        print(f"Error: Directory not found: {weather_dir}")
        sys.exit(1)
    
    svg_files = list(weather_dir.glob("*.svg"))
    
    if not svg_files:
        print("No SVG files found.")
        return
    
    print(f"Found {len(svg_files)} SVG files to convert...")
    
    # Use Qt's SVG support (already installed via PySide6)
    from PySide6.QtCore import Qt
    from PySide6.QtSvg import QSvgRenderer
    from PySide6.QtGui import QImage, QPainter
    
    converted = 0
    failed = []
    
    for svg_file in svg_files:
        png_file = svg_file.with_suffix(".png")
        
        try:
            # Load SVG using Qt's renderer
            renderer = QSvgRenderer(str(svg_file))

            if not renderer.isValid():
                print(f"✗ Failed to parse SVG: {svg_file.name}")
                failed.append(svg_file.name)
                continue

            # Create transparent image at 250x250 for high-res display
            target_size = 250
            image = QImage(target_size, target_size, QImage.Format.Format_ARGB32)
            image.fill(Qt.GlobalColor.transparent)

            # Render SVG to image scaled to target size
            painter = QPainter(image)
            renderer.setAspectRatioMode(Qt.AspectRatioMode.KeepAspectRatio)
            renderer.render(painter)
            painter.end()

            # Save as PNG
            image.save(str(png_file), "PNG")
            
            # Verify PNG was created
            if png_file.exists() and png_file.stat().st_size > 0:
                print(f"✓ Converted: {svg_file.name} -> {png_file.name}")
                # Delete SVG on success
                svg_file.unlink()
                print(f"  Deleted: {svg_file.name}")
                converted += 1
            else:
                print(f"✗ Failed to create PNG for: {svg_file.name}")
                failed.append(svg_file.name)
                
        except Exception as e:
            print(f"✗ Error converting {svg_file.name}: {e}")
            failed.append(svg_file.name)
    
    print(f"\n{'='*50}")
    print(f"Converted: {converted}/{len(svg_files)}")
    if failed:
        print(f"Failed: {len(failed)}")
        for name in failed:
            print(f"  - {name}")
    else:
        print("All SVGs converted and deleted successfully!")

if __name__ == "__main__":
    convert_svgs_to_pngs()
