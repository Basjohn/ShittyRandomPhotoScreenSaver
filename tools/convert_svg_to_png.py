#!/usr/bin/env python3
"""Convert SVG files to PNG with transparency using Qt (Windows-compatible).

Generic version: accepts source directory, optional target directory, and size.
Usage:
    python tools/convert_svg_to_png.py images/ --size 32
    python tools/convert_svg_to_png.py images/ --output images/ --size 16 --keep-svg
"""
import argparse
import sys
from pathlib import Path


def convert_svgs_to_pngs(source_dir: Path, output_dir: Path | None, size: int, keep_svg: bool) -> int:
    """Convert all SVG files in *source_dir* to PNGs.

    Returns the number of successfully converted files.
    """
    if not source_dir.exists():
        print(f"Error: Source directory not found: {source_dir}")
        sys.exit(1)

    svg_files = sorted(source_dir.glob("*.svg"))
    if not svg_files:
        print("No SVG files found.")
        return 0

    print(f"Found {len(svg_files)} SVG file(s) to convert...")

    # Qt SVG support (bundled with PySide6)
    from PySide6.QtCore import Qt
    from PySide6.QtSvg import QSvgRenderer
    from PySide6.QtGui import QImage, QPainter

    converted = 0
    failed = []

    for svg_file in svg_files:
        png_file = (output_dir or source_dir) / svg_file.with_suffix(".png").name

        try:
            renderer = QSvgRenderer(str(svg_file))
            if not renderer.isValid():
                print(f"  ✗ Failed to parse SVG: {svg_file.name}")
                failed.append(svg_file.name)
                continue

            image = QImage(size, size, QImage.Format.Format_ARGB32)
            image.fill(Qt.GlobalColor.transparent)

            painter = QPainter(image)
            renderer.setAspectRatioMode(Qt.AspectRatioMode.KeepAspectRatio)
            renderer.render(painter)
            painter.end()

            if not image.save(str(png_file), "PNG"):
                print(f"  ✗ Failed to save PNG: {png_file.name}")
                failed.append(svg_file.name)
                continue

            if png_file.exists() and png_file.stat().st_size > 0:
                print(f"  ✓ Converted: {svg_file.name} -> {png_file.name} ({size}x{size})")
                converted += 1
                if not keep_svg:
                    svg_file.unlink()
                    print(f"    Deleted: {svg_file.name}")
            else:
                print(f"  ✗ PNG empty: {png_file.name}")
                failed.append(svg_file.name)

        except Exception as e:
            print(f"  ✗ Error converting {svg_file.name}: {e}")
            failed.append(svg_file.name)

    print(f"\n{'='*50}")
    print(f"Converted: {converted}/{len(svg_files)}")
    if failed:
        print(f"Failed: {len(failed)}")
        for name in failed:
            print(f"  - {name}")
    else:
        print("All SVGs converted successfully!")
    return converted


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert SVG files to PNG using Qt.")
    parser.add_argument("source", type=Path, help="Directory containing SVG files")
    parser.add_argument("--output", "-o", type=Path, default=None, help="Output directory (default: same as source)")
    parser.add_argument("--size", "-s", type=int, default=64, help="Output PNG size in pixels (default: 64)")
    parser.add_argument("--keep-svg", action="store_true", help="Keep original SVG files after conversion")
    args = parser.parse_args()

    output_dir = args.output or args.source
    output_dir.mkdir(parents=True, exist_ok=True)

    convert_svgs_to_pngs(args.source.resolve(), output_dir.resolve(), args.size, args.keep_svg)


if __name__ == "__main__":
    main()
