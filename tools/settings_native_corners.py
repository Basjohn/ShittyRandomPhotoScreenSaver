"""Capture the real Windows Settings HWND over controlled light/dark native backgrounds.

Uses desktop pixels from ImageGrab after DwmFlush, never QWidget.grab/PrintWindow/offscreen rendering.
Profiles and evidence are task-owned; no live profile or desktop wallpaper is modified.
"""
from __future__ import annotations

import argparse
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools import artifact_paths


def _pump(app, duration):
    until = time.monotonic() + duration
    while time.monotonic() < until:
        app.processEvents()
        time.sleep(0.005)
    ctypes.windll.dwmapi.DwmFlush()


def _rect(hwnd):
    rect = wintypes.RECT()
    if not ctypes.windll.user32.GetWindowRect(wintypes.HWND(hwnd), ctypes.byref(rect)):
        raise ctypes.WinError()
    return rect.left, rect.top, rect.right, rect.bottom


def _native_region(hwnd, width, height):
    """Read actual HWND region membership, independently of QWidget.mask()."""
    gdi = ctypes.windll.gdi32
    gdi.CreateRectRgn.restype = wintypes.HRGN
    gdi.GetRgnBox.argtypes = [wintypes.HRGN, ctypes.POINTER(wintypes.RECT)]
    gdi.PtInRegion.argtypes = [wintypes.HRGN, ctypes.c_int, ctypes.c_int]
    gdi.DeleteObject.argtypes = [wintypes.HANDLE]
    ctypes.windll.user32.GetWindowRgn.argtypes = [wintypes.HWND, wintypes.HRGN]
    region = gdi.CreateRectRgn(0, 0, 0, 0)
    try:
        kind = ctypes.windll.user32.GetWindowRgn(wintypes.HWND(hwnd), region)
        bounds = wintypes.RECT()
        gdi.GetRgnBox(region, ctypes.byref(bounds))
        points = {}
        for corner, cx, cy, sx, sy in (("top_left", 0, 0, 1, 1), ("top_right", width-1, 0, -1, 1),
                ("bottom_left", 0, height-1, 1, -1), ("bottom_right", width-1, height-1, -1, -1)):
            points[corner] = ["".join("1" if gdi.PtInRegion(region, cx+sx*x, cy+sy*y) else "0"
                                      for x in range(12)) for y in range(12)]
        return {"kind": kind, "bounds": [bounds.left, bounds.top, bounds.right, bounds.bottom], "corners": points}
    finally:
        gdi.DeleteObject(region)


def _themes(material):
    from ui.settings_theme_io import load_settings_theme_file
    from ui.theme_semantics import settings_theme_is_light

    choices = {}
    for path in sorted((ROOT / "themes").glob("*.srtheme")):
        theme = load_settings_theme_file(path)
        if theme.backdrop.mode == material:
            choices.setdefault("light" if settings_theme_is_light(theme) else "dark", path)
    if set(choices) != {"light", "dark"}:
        raise RuntimeError(f"native corner capture requires both a light and dark {material} theme")
    return choices


def analyze_pixels(delta, width, height, pad, radius):
    """Measure rounded-corner residue separately from native exterior shadow pixels."""
    import numpy as np

    corners = {}
    n = int(np.ceil(radius))
    yy, xx = np.indices((n, n))
    outside = (xx + 0.5-radius)**2 + (yy + 0.5-radius)**2 > radius**2
    for corner, cx, cy, sx, sy in (("top_left", pad, pad, 1, 1),
            ("top_right", pad+width-1, pad, -1, 1), ("bottom_left", pad, pad+height-1, 1, -1),
            ("bottom_right", pad+width-1, pad+height-1, -1, -1)):
        measured = delta[cy + sy*yy, cx + sx*xx]
        corners[corner] = {"outside_rounded_pixels_changed_gt3": int(((measured > 3) & outside).sum()),
                           "maximum_outside_delta": int(measured[outside].max(initial=0))}
    outside_hwnd = np.ones(delta.shape, bool)
    outside_hwnd[pad:pad+height, pad:pad+width] = False
    border = np.concatenate((delta[0], delta[-1], delta[:, 0], delta[:, -1]))
    return {"corners": corners, "changed_pixels_outside_hwnd_gt3": int(((delta > 3) & outside_hwnd).sum()),
            "capture_perimeter_delta": int(border.max(initial=0))}


def write_corner_sheet(out, cases):
    from PIL import Image, ImageDraw

    corners = ("top_left", "top_right", "bottom_left", "bottom_right")
    sheet = Image.new("RGB", (1120, len(cases)*300), (210, 210, 210))
    draw = ImageDraw.Draw(sheet)
    for row, case in enumerate(cases):
        draw.text((5, row*300+2), case["case"], fill="black")
        for col, corner in enumerate(corners):
            crop = Image.open(out / f"{case['case']}_{corner}.png").convert("RGB")
            sheet.paste(crop.resize((260, 260), Image.Resampling.NEAREST), (col*280, row*300+36))
            draw.text((col*280+5, row*300+18), corner, fill="black")
    sheet.save(out / "native_corner_contact_sheet.png")


def capture(label, material, dark_theme=None, light_theme=None, physical_region=False, qt_region=False,
            text_evidence=False, page="sources"):
    if sys.platform != "win32":
        raise RuntimeError("this gate requires a native Windows interactive desktop")
    import numpy as np
    from PIL import ImageGrab
    from PySide6.QtCore import QCoreApplication, QEvent, QRectF, Qt
    from PySide6.QtGui import QColor, QPainterPath, QPalette, QRegion
    from PySide6.QtWidgets import QApplication, QLabel, QWidget
    from core.animation import AnimationManager
    from core.settings.settings_manager import SettingsManager
    from ui.settings_dialog import SettingsDialog
    from ui.settings_theme_catalog import activate_persisted_settings_theme
    from ui.settings_theme_runtime import get_active_settings_theme, set_active_settings_theme
    from ui.settings_window_edge import SETTINGS_OUTER_CORNER_RADIUS
    from ui.styled_popup import StyledPopup

    app = QApplication.instance() or QApplication([])
    screens = [s for s in app.screens() if s.availableGeometry().width() >= 1280
               and s.availableGeometry().height() >= 760]
    if not screens:
        raise RuntimeError("no native screen can display all four Settings corners at its minimum size")
    screen = max(screens, key=lambda s: s.availableGeometry().width() * s.availableGeometry().height())
    out = artifact_paths.evidence_dir("settings", "native_outer_border", label)
    out.mkdir(parents=True, exist_ok=True)
    profile = artifact_paths.run_scratch("settings_native_corners", label)
    previous_theme = get_active_settings_theme()
    user32 = ctypes.windll.user32
    user32.GetForegroundWindow.restype = wintypes.HWND
    previous_foreground = user32.GetForegroundWindow()
    old_popup = StyledPopup.exec
    StyledPopup.exec = lambda popup: setattr(popup, "_result_value", None)
    report = {"provider": "native_windows_desktop_ImageGrab_DwmFlush", "pid": os.getpid(),
              "screen": screen.name(), "dpr": screen.devicePixelRatio(), "page": page, "cases": [],
              "shadow_boundary": "Product outer-shadow coverage is zero. Native DWM shadow is measured separately "
                  "outside the HWND; the 48px capture perimeter must return to the background."}
    dialog = None
    background = None
    probe_hwnds = []
    try:
        if dark_theme or light_theme:
            if not dark_theme or not light_theme:
                raise ValueError("explicit theme capture requires both --dark-theme and --light-theme")
            themes = {"dark": ROOT / "themes" / dark_theme, "light": ROOT / "themes" / light_theme}
            if any(not path.is_file() or path.parent != ROOT / "themes" for path in themes.values()):
                raise ValueError("explicit themes must name existing canonical theme files")
        else:
            themes = _themes(material)
        for tone, theme_path in themes.items():
            for background_tone, rgb in (("dark", (18, 18, 18)), ("light", (244, 244, 244))):
                name = f"{tone}_theme_{background_tone}_background"
                background = QWidget(None, Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint
                                     | Qt.WindowType.WindowStaysOnTopHint)
                background.setWindowTitle("SRPSS Native Corner Evidence Background")
                palette = background.palette()
                palette.setColor(QPalette.ColorRole.Window, QColor(*rgb))
                background.setPalette(palette)
                background.setAutoFillBackground(True)
                background.setGeometry(screen.geometry())
                background.show()
                background.raise_()
                _pump(app, 0.15)
                desktop_rect = _rect(int(background.winId()))
                background_pixels = ImageGrab.grab(bbox=desktop_rect, all_screens=True).convert("RGB")

                settings = SettingsManager(application="native_settings_corner_evidence", storage_base_dir=profile)
                settings.set("sources.folders", [str(profile)])
                settings.set("ui.last_tab_key", page)
                settings.set("ui.settings_theme_selection", f"file:{theme_path.name}")
                selected = activate_persisted_settings_theme(settings, ROOT / "themes").resolution
                if selected.used_fallback:
                    raise RuntimeError("the selected native capture theme was not admitted")
                animations = AnimationManager(owner="settings:native-corner-evidence")
                dialog = SettingsDialog(settings, animations)
                dialog.resize(1280, 760)
                dialog.move(screen.geometry().center() - dialog.rect().center())
                dialog.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
                if qt_region:
                    path = QPainterPath()
                    path.addRoundedRect(QRectF(dialog.rect()), SETTINGS_OUTER_CORNER_RADIUS, SETTINGS_OUTER_CORNER_RADIUS)
                    dialog.setMask(QRegion(path.toFillPolygon().toPolygon()))
                dialog.show()
                dialog.raise_()
                dialog.activateWindow()
                _pump(app, 0.55)
                hwnd = int(dialog.winId())
                probe_hwnds.extend((hwnd, int(background.winId())))
                if not user32.IsWindowVisible(wintypes.HWND(hwnd)) or not dialog.isVisible():
                    raise RuntimeError("the real Settings HWND is not visible")
                native = _rect(hwnd)
                if physical_region:
                    gdi = ctypes.windll.gdi32
                    gdi.CreateRoundRectRgn.restype = wintypes.HRGN
                    gdi.DeleteObject.argtypes = [wintypes.HANDLE]
                    user32.SetWindowRgn.argtypes = [wintypes.HWND, wintypes.HRGN, wintypes.BOOL]
                    diameter = round(2 * SETTINGS_OUTER_CORNER_RADIUS * dialog.devicePixelRatioF())
                    region = gdi.CreateRoundRectRgn(0, 0, native[2]-native[0]+1, native[3]-native[1]+1,
                                                    diameter, diameter)
                    if not user32.SetWindowRgn(wintypes.HWND(hwnd), region, True):
                        gdi.DeleteObject(region)
                        raise ctypes.WinError()
                    _pump(app, 0.25)
                pad = 48
                capture_rect = (native[0]-pad, native[1]-pad, native[2]+pad, native[3]+pad)
                if (capture_rect[0] < desktop_rect[0] or capture_rect[1] < desktop_rect[1]
                        or capture_rect[2] > desktop_rect[2] or capture_rect[3] > desktop_rect[3]):
                    raise RuntimeError("the native window plus shadow perimeter does not fit this screen")
                image = ImageGrab.grab(bbox=capture_rect, all_screens=True).convert("RGB")
                image.save(out / f"{name}.png")
                if text_evidence:
                    labels = []
                    window_origin = dialog.mapToGlobal(dialog.rect().topLeft())
                    dpr = float(dialog.devicePixelRatioF())
                    for widget in dialog.findChildren(QLabel):
                        if not widget.isVisible() or not widget.text():
                            continue
                        origin = widget.mapToGlobal(widget.rect().topLeft())
                        font = widget.font()
                        ink = widget.palette().color(widget.foregroundRole())
                        labels.append({"text": widget.text(), "object_name": widget.objectName(),
                                       "global_logical_rect": [origin.x(), origin.y(), widget.width(), widget.height()],
                                       "native_pixel_rect": [native[0] + round((origin.x()-window_origin.x())*dpr),
                                                             native[1] + round((origin.y()-window_origin.y())*dpr),
                                                             round(widget.width()*dpr), round(widget.height()*dpr)],
                                       "palette_ink_rgba": list(ink.getRgb()), "font_family": font.family(),
                                       "point_size": font.pointSizeF(), "pixel_size": font.pixelSize(),
                                       "weight": font.weight(), "bold": font.bold()})
                        widget.setStyleSheet(widget.styleSheet() + "; color: transparent;")
                    _pump(app, 0.15)
                    ImageGrab.grab(bbox=capture_rect, all_screens=True).convert("RGB").save(out / f"{name}_ink_off.png")
                    (out / f"{name}_labels.json").write_text(json.dumps(labels, indent=2), encoding="utf-8")
                reference = background_pixels.crop((capture_rect[0]-desktop_rect[0], capture_rect[1]-desktop_rect[1],
                                                     capture_rect[2]-desktop_rect[0], capture_rect[3]-desktop_rect[1]))
                a, b = np.asarray(image, dtype=np.int16), np.asarray(reference, dtype=np.int16)
                delta = np.abs(a-b).max(2)
                width, height = native[2]-native[0], native[3]-native[1]
                dpr = float(dialog.devicePixelRatioF())
                radius = SETTINGS_OUTER_CORNER_RADIUS * dpr
                for corner, cx, cy in (("top_left", pad, pad), ("top_right", pad+width-1, pad),
                        ("bottom_left", pad, pad+height-1), ("bottom_right", pad+width-1, pad+height-1)):
                    crop = image.crop((cx-32, cy-32, cx+33, cy+33))
                    crop.save(out / f"{name}_{corner}.png")
                case = {"case": name, "theme": theme_path.name, "hwnd": hwnd, "native_rect": native,
                        "capture_rect": capture_rect, "dpr": dpr, "radius_physical_px": radius,
                        "native_backdrop_mode": dialog._native_backdrop_mode,
                        **analyze_pixels(delta, width, height, pad, radius)}
                case["native_region"] = _native_region(hwnd, width, height)
                report["cases"].append(case)
                print(json.dumps(case), flush=True)
                dialog.close()
                dialog.deleteLater()
                dialog = None
                animations.stop()
                settings.flush(timeout=5.0)
                background.close()
                background.deleteLater()
                background = None
                QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
                _pump(app, 0.05)
    finally:
        if dialog is not None:
            dialog.close()
        if background is not None:
            background.close()
        StyledPopup.exec = old_popup
        set_active_settings_theme(previous_theme)
        if previous_foreground:
            user32.SetForegroundWindow(previous_foreground)
        report["probe_windows_closed"] = all(not user32.IsWindowVisible(wintypes.HWND(hwnd)) for hwnd in probe_hwnds)
        (out / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        if report["cases"]:
            write_corner_sheet(out, report["cases"])
    print(f"Native evidence: {out}", flush=True)
    scratch_owner = artifact_paths.scratch_root("settings_native_corners").resolve()
    if profile.resolve().parent != scratch_owner:
        raise RuntimeError("refusing cleanup outside this capture's named scratch owner")
    artifact_paths.discard_run_scratch("settings_native_corners")
    return out


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--label", required=True)
    parser.add_argument("--material", choices=("glass", "acrylic", "mica", "frosted", "smoked", "off"), required=True)
    parser.add_argument("--dark-theme")
    parser.add_argument("--light-theme")
    parser.add_argument("--physical-region", action="store_true", help="Tool-only post-Accent physical region experiment")
    parser.add_argument("--qt-region", action="store_true", help="Tool-only reproduction of rejected logical Qt mask")
    parser.add_argument("--text-evidence", action="store_true", help="Capture actual QLabel metadata and a matched transparent-ink frame")
    parser.add_argument("--page", choices=("sources", "themes", "accessibility"), default="sources")
    args = parser.parse_args()
    capture(args.label, args.material, args.dark_theme, args.light_theme, args.physical_region, args.qt_region,
            args.text_evidence, args.page)
