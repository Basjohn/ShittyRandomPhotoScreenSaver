"""Minimal flicker reproduction — run each variant and report which flickers.

Usage:  python tools/flicker_test.py [variant]
Variants:
  1   Plain QDialog (no flags, no attributes)
  2   FramelessWindowHint only
  3   Frameless + WA_TranslucentBackground
  4   Frameless + WA_TranslucentBackground + stylesheet
  5   Full SettingsDialog flags (Dialog | Frameless + Translucent + stylesheet)
  6   Window | Frameless | WindowSystemMenuHint + Translucent (old flags)
  7   Tool | Frameless + Translucent
  8   Font registration (addApplicationFont)
  9   QGuiApplication.setFont() global font change
  10  Full flags + real dark.qss stylesheet
  11  Full flags + 200 child widgets
  12  All combined: font reg + global font + large QSS + 200 widgets
  13  Actual SettingsDialog import + construction

Press Enter in the console to show the dialog for each variant.
"""

import sys
import time
from pathlib import Path

# Ensure project root is on sys.path for variant 13/14
_PROJECT_ROOT = str(Path(__file__).parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from PySide6.QtWidgets import (
    QApplication, QDialog, QLabel, QVBoxLayout, QHBoxLayout,
    QPushButton, QCheckBox, QComboBox, QGroupBox, QScrollArea, QWidget,
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QFontDatabase, QGuiApplication

STYLESHEET = """
QDialog { background-color: transparent; }
QLabel { color: white; background: rgba(30,30,30,220); padding: 40px; }
"""

# Load the real dark.qss if available, to match real stylesheet size
_QSS_PATH = Path(__file__).parent.parent / "themes" / "dark.qss"
try:
    BIG_STYLESHEET = _QSS_PATH.read_text(encoding="utf-8") + STYLESHEET
except Exception:
    BIG_STYLESHEET = STYLESHEET * 50  # fallback: repeat small sheet


def _register_fonts():
    """Same font registration as shared_styles._ensure_jost_registered."""
    try:
        from ui.resources import assets_rc  # noqa: F401
    except Exception:
        pass
    paths = (
        ":/ui/assets/fonts/Jost-Regular.ttf",
        ":/ui/assets/fonts/Jost-SemiBold.ttf",
        ":/ui/assets/fonts/Jost-Bold.ttf",
    )
    for p in paths:
        QFontDatabase.addApplicationFont(p)


def _set_global_font():
    font = QFont("Jost", 11)
    font.setFamilies(["Jost", "Segoe UI", "Arial", "Sans Serif"])
    font.setWeight(QFont.Weight.Normal)
    QGuiApplication.setFont(font)


def _add_many_widgets(parent, count=200):
    scroll = QScrollArea(parent)
    scroll.setWidgetResizable(True)
    container = QWidget()
    lay = QVBoxLayout(container)
    for i in range(count):
        grp = QGroupBox(f"Group {i}", container)
        grp_lay = QHBoxLayout(grp)
        grp_lay.addWidget(QLabel(f"Label {i}"))
        grp_lay.addWidget(QPushButton(f"Button {i}"))
        grp_lay.addWidget(QCheckBox(f"Check {i}"))
        grp_lay.addWidget(QComboBox())
        lay.addWidget(grp)
    scroll.setWidget(container)
    main_lay = parent.layout() or QVBoxLayout(parent)
    main_lay.addWidget(scroll)


def make_dialog(variant: int) -> QDialog:
    d = QDialog()
    d.setWindowTitle(f"Variant {variant}")
    d.resize(1280, 700)

    if variant == 1:
        pass  # plain

    elif variant == 2:
        d.setWindowFlags(Qt.WindowType.FramelessWindowHint)

    elif variant == 3:
        d.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        d.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

    elif variant == 4:
        d.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        d.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        d.setStyleSheet(STYLESHEET)

    elif variant == 5:
        d.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        d.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        d.setStyleSheet(STYLESHEET)

    elif variant == 6:
        d.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowSystemMenuHint
        )
        d.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        d.setStyleSheet(STYLESHEET)

    elif variant == 7:
        d.setWindowFlags(Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint)
        d.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        d.setStyleSheet(STYLESHEET)

    elif variant == 8:
        d.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        d.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        _register_fonts()

    elif variant == 9:
        d.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        d.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        _register_fonts()
        _set_global_font()

    elif variant == 10:
        d.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        d.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        d.setStyleSheet(BIG_STYLESHEET)

    elif variant == 11:
        d.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        d.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        _add_many_widgets(d)

    elif variant == 12:
        d.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        d.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        _register_fonts()
        _set_global_font()
        d.setStyleSheet(BIG_STYLESHEET)
        _add_many_widgets(d)

    elif variant == 13:
        # Actual SettingsDialog
        from core.settings.settings_manager import SettingsManager
        from core.animation import AnimationManager
        from ui.settings_dialog import SettingsDialog
        settings = SettingsManager()
        animations = AnimationManager()
        return SettingsDialog(settings, animations)

    if variant <= 10:
        lay = QVBoxLayout(d)
        lay.addWidget(QLabel(f"Variant {variant} -- watch Display 0 title bars"))
    return d


def _apply_main_py_setup():
    """Reproduce the same setup main.py does before creating any dialogs."""
    from PySide6.QtCore import QCoreApplication
    from PySide6.QtGui import QSurfaceFormat, QImageReader, QIcon

    # DPI policy
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    # OpenGL attributes
    QCoreApplication.setAttribute(Qt.ApplicationAttribute.AA_UseDesktopOpenGL, True)
    QCoreApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts, True)
    # Surface format
    try:
        from rendering.gl_format import build_surface_format
        fmt, _ = build_surface_format(reason="flicker_test")
        QSurfaceFormat.setDefaultFormat(fmt)
    except Exception as e:
        print(f"  (surface format setup failed: {e})")
    return True


def main():
    variants = [int(sys.argv[1])] if len(sys.argv) > 1 else range(1, 18)

    # Variants 14-17 need main.py-style setup BEFORE QApplication
    need_main_setup = any(v >= 14 for v in variants)
    if need_main_setup:
        _apply_main_py_setup()

    app = QApplication(sys.argv)

    # Apply window icon like main.py does
    if need_main_setup:
        from PySide6.QtGui import QIcon
        icon_path = Path(__file__).parent.parent / "SRPSS.ico"
        if icon_path.exists():
            app.setWindowIcon(QIcon(str(icon_path)))
            print(f"  (app icon set from {icon_path})")

    for v in variants:
        input(f"\n>>> Press Enter to show variant {v} ...")
        t0 = time.perf_counter()

        # Variants 14-17: simple dialogs with main.py setup already applied
        if v == 14:
            # Plain dialog + main.py setup (already applied above)
            d = QDialog()
            d.resize(1280, 700)
            QVBoxLayout(d).addWidget(QLabel("V14: plain + main.py setup"))
        elif v == 15:
            # Full flags + main.py setup
            d = QDialog()
            d.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
            d.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
            d.resize(1280, 700)
            QVBoxLayout(d).addWidget(QLabel("V15: full flags + main.py setup"))
        elif v == 16:
            # Full flags + stylesheet + main.py setup
            d = QDialog()
            d.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
            d.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
            d.setStyleSheet(BIG_STYLESHEET)
            d.resize(1280, 700)
            _add_many_widgets(d)
        elif v == 17:
            # Actual SettingsDialog + main.py setup
            from core.settings.settings_manager import SettingsManager
            from core.animation import AnimationManager
            from ui.settings_dialog import SettingsDialog
            settings = SettingsManager()
            animations = AnimationManager()
            d = SettingsDialog(settings, animations)
        else:
            d = make_dialog(v)

        construct_ms = (time.perf_counter() - t0) * 1000
        print(f"  constructed in {construct_ms:.1f} ms")
        t1 = time.perf_counter()
        d.show()
        show_ms = (time.perf_counter() - t1) * 1000
        print(f"  show() in {show_ms:.1f} ms")
        input("  Did Display 0 flicker? (note it, then press Enter to close)")
        d.close()
        d.deleteLater()
        app.processEvents()

    print("\nDone -- compare which variants flickered.")


if __name__ == "__main__":
    main()
