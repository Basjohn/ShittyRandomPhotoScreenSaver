"""Capture the real Windows Settings or Studio HWND over controlled light/dark native backgrounds.

Uses desktop pixels from ImageGrab after DwmFlush, never QWidget.grab/PrintWindow/offscreen rendering.
Profiles and evidence are task-owned; no live profile or desktop wallpaper is modified.
Optional wallpaper backgrounds use an aspect-preserving centered cover transform. Acceptance compares against
the matching captured desktop pixels, preserving texture and blur differences rather than assuming uniform RGB.

Unobtrusive by construction (this is the one measurement that needs a visible native window): the controlled
background covers only the measured window plus its capture perimeter and a small margin, never the display; both
windows sit in the available-area corner farthest from the pointer, are non-activating, and stay on screen at most
``MAX_ON_SCREEN_S`` per case; the pointer is never moved and no input is synthesized. A case whose capture rectangle
is overlapped by another process's window above ours is invalid (``occluders``), is closed at once and retried later
instead of raising our window over the operator's work.

Measurement-only parameters (never product settings, never environment variables):

* ``--extra-border-device-px`` (one or more widths, DEVICE pixels): the edge owner
  (``ui.settings_window_edge.paint_forged_window_edge``) widens its border by that many device pixels;
  every width is captured from the same shown window. ``--border-growth centre|outward``.
* ``--region-before-accent``: a native rounded region (``CreateRoundRectRgn``, nominal radius) is set on the measured
  HWND immediately BEFORE its AccentPolicy call, so Accent is enabled on an already-regioned window.
* ``--qt-scale-factor``: Qt rasterises at ``screen DPR x factor`` (Qt's own high-DPI scale) to emulate another DPR on
  the real monitor; the painted corner pixels are Qt's at that DPR, while DWM (shadow, blur kernel) stays at the
  monitor's real DPI. Reported as emulated, never as a measured monitor.
"""
from __future__ import annotations

import argparse
import ctypes
from ctypes import wintypes
import json
import hashlib
import math
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools import artifact_paths
from tools import evidence_media

OWNER = "settings_native_corners"
TOPIC = "native_corners"
WINDOW_LOGICAL_SIZE = (1280, 760)      # Settings' minimum size; the Studio is opened at the same size
CAPTURE_PAD = 48                       # device px of capture perimeter around the HWND (native shadow)
BACKGROUND_MARGIN = 16                 # device px of controlled background beyond the capture perimeter
SCREEN_EDGE_GAP = 24                   # device px between the background and the available-area edge
MAX_ON_SCREEN_S = 3.0
CHANGED = 3                            # channel levels ignored as capture noise
CORNERS = ("top_left", "top_right", "bottom_left", "bottom_right")
GW_HWNDPREV = 3
GWL_EXSTYLE = -20
WS_EX_TRANSPARENT = 0x20
DWMWA_CLOAKED = 14


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
        if kind == 0:
            return {"kind": 0, "meaning": "no explicit HWND region", "bounds": None, "corners": {}}
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


def _set_rounded_region(hwnd, radius_px):
    """SetWindowRgn(hwnd, CreateRoundRectRgn(...)) at the nominal radius (device px); the system owns the region."""
    gdi, user32 = ctypes.windll.gdi32, ctypes.windll.user32
    gdi.CreateRoundRectRgn.restype = wintypes.HRGN
    user32.SetWindowRgn.argtypes = [wintypes.HWND, wintypes.HRGN, wintypes.BOOL]
    left, top, right, bottom = _rect(hwnd)
    diameter = max(2, int(round(radius_px * 2)))
    region = gdi.CreateRoundRectRgn(0, 0, right - left + 1, bottom - top + 1, diameter, diameter)
    ok = bool(user32.SetWindowRgn(wintypes.HWND(hwnd), region, True))
    if not ok:
        gdi.DeleteObject(region)
    return {"set_window_rgn": ok, "diameter_px": diameter, "size": [right - left, bottom - top]}


def occluders(hwnd, rect):
    """Visible, uncloaked windows of other processes above ``hwnd`` in z-order that overlap ``rect``."""
    user32 = ctypes.windll.user32
    user32.GetWindow.restype = wintypes.HWND
    user32.GetWindow.argtypes = [wintypes.HWND, wintypes.UINT]
    user32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
    found = []
    ours = os.getpid()
    current = user32.GetWindow(wintypes.HWND(hwnd), GW_HWNDPREV)
    while current:
        if user32.IsWindowVisible(current) and not user32.IsIconic(current):
            cloaked = wintypes.DWORD(0)
            ctypes.windll.dwmapi.DwmGetWindowAttribute(current, DWMWA_CLOAKED, ctypes.byref(cloaked),
                                                       ctypes.sizeof(cloaked))
            pid = wintypes.DWORD(0)
            user32.GetWindowThreadProcessId(current, ctypes.byref(pid))
            if not cloaked.value and pid.value != ours:
                left, top, right, bottom = _rect(int(current))
                if left < rect[2] and right > rect[0] and top < rect[3] and bottom > rect[1]:
                    name = ctypes.create_unicode_buffer(128)
                    user32.GetClassNameW(current, name, 128)
                    found.append({"hwnd": int(current), "pid": pid.value, "class": name.value,
                                  "rect": [left, top, right, bottom],
                                  "click_through": bool(user32.GetWindowLongW(current, GWL_EXSTYLE)
                                                        & WS_EX_TRANSPARENT)})
        current = user32.GetWindow(current, GW_HWNDPREV)
    return found


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


def _corner_blocks(array, width, height, pad, n):
    """Each corner's n x n block, oriented so index [0, 0] is the HWND's outermost corner pixel."""
    for corner, cx, cy, sx, sy in (("top_left", pad, pad, 1, 1),
            ("top_right", pad+width-1, pad, -1, 1), ("bottom_left", pad, pad+height-1, 1, -1),
            ("bottom_right", pad+width-1, pad+height-1, -1, -1)):
        import numpy as np
        yy, xx = np.indices((n, n))
        yield corner, array[cy + sy*yy, cx + sx*xx]


def analyze_pixels(delta, width, height, pad, radius):
    """Measure rounded-corner residue separately from native exterior shadow pixels."""
    import numpy as np

    corners = {}
    n = int(np.ceil(radius))
    yy, xx = np.indices((n, n))
    outside = (xx + 0.5-radius)**2 + (yy + 0.5-radius)**2 > radius**2
    for corner, measured in _corner_blocks(delta, width, height, pad, n):
        corners[corner] = {"outside_rounded_pixels_changed_gt3": int(((measured > 3) & outside).sum()),
                           "maximum_outside_delta": int(measured[outside].max(initial=0))}
    outside_hwnd = np.ones(delta.shape, bool)
    outside_hwnd[pad:pad+height, pad:pad+width] = False
    border = np.concatenate((delta[0], delta[-1], delta[:, 0], delta[:, -1]))
    return {"corners": corners, "changed_pixels_outside_hwnd_gt3": int(((delta > 3) & outside_hwnd).sum()),
            "capture_perimeter_delta": int(border.max(initial=0))}


def painted_silhouette(dpr, extra_border_device_px=0.0, border_growth="centre"):
    """The border stroke's outer edge in device px: its corner circle (centre offset from the HWND corner,
    radius) and the 'edge leg' (how far from the corner the silhouette leaves the window edge; the nominal arc's leg
    is its radius, a square corner's is 0)."""
    from ui.settings_window_edge import SETTINGS_OUTER_CORNER_RADIUS, forged_edge_geometry

    inset, radius, border_width = forged_edge_geometry(dpr, extra_border_device_px, border_growth)
    centre = (inset + radius) * dpr
    outer = (radius + border_width * 0.5) * dpr
    leg = centre - math.sqrt(outer*outer - centre*centre) if outer > centre else centre
    nominal = SETTINGS_OUTER_CORNER_RADIUS * dpr
    return {"centre_px": centre, "outer_radius_px": outer, "edge_leg_px": max(0.0, leg),
            "nominal_radius_px": nominal, "nominal_edge_leg_px": nominal,
            "border_width_logical": border_width, "border_width_device": border_width * dpr}


def analyze_silhouette(delta, image, width, height, pad, silhouette, painted_rgb=None):
    """Corner pixels outside the PAINTED silhouette (the border's outer edge) that differ from the desktop: the
    visible escape. Each is classed as a painted colour (within 24 levels of ``painted_rgb``) or other
    (material, antialiasing). Also lists every changed pixel outside the nominal arc, as corner-local (x, y)."""
    import numpy as np

    centre, outer = silhouette["centre_px"], silhouette["outer_radius_px"]
    nominal = silhouette["nominal_radius_px"]
    n = int(math.ceil(max(centre, nominal)))
    yy, xx = np.indices((n, n))
    px, py = xx + 0.5, yy + 0.5
    in_corner = (px < centre) & (py < centre)
    beyond = in_corner & ((px - centre)**2 + (py - centre)**2 > outer**2)
    nominal_outside = (px < nominal) & (py < nominal) & ((px - nominal)**2 + (py - nominal)**2 > nominal**2)
    colours = dict(_corner_blocks(np.asarray(image, dtype=np.int16), width, height, pad, n))
    corners = {}
    for corner, measured in _corner_blocks(delta, width, height, pad, n):
        changed = measured > CHANGED
        escape = changed & beyond
        forged = np.zeros_like(escape)
        if painted_rgb is not None:
            forged = (np.abs(colours[corner] - np.asarray(painted_rgb[:3], dtype=np.int16)).max(2) <= 24) & escape
        corners[corner] = {
            "silhouette_pixels": int(beyond.sum()),
            "escape_pixels_changed_gt3": int(escape.sum()),
            "escape_maximum_delta": int(measured[beyond].max(initial=0)),
            "escape_painted_colour_pixels": int(forged.sum()),
            "escape_positions": [[int(x), int(y)] for y, x in zip(*np.nonzero(escape))],
            "nominal_outside_changed_positions": [[int(x), int(y)] for y, x in zip(*np.nonzero(changed & nominal_outside))],
        }
    return corners


def write_corner_sheet(out, cases):
    from PIL import Image, ImageDraw

    sheet = Image.new("RGB", (1120, len(cases)*300), (210, 210, 210))
    draw = ImageDraw.Draw(sheet)
    for row, case in enumerate(cases):
        draw.text((5, row*300+2), case["case"], fill="black")
        for col, corner in enumerate(CORNERS):
            crop = Image.open(out / f"{case['case']}_{corner}.png").convert("RGB")
            sheet.paste(crop.resize((260, 260), Image.Resampling.NEAREST), (col*280, row*300+36))
            draw.text((col*280+5, row*300+18), corner, fill="black")
    sheet.save(out / "native_corner_contact_sheet.png")


def write_width_comparison(out, base_name, variants):
    """Per case: 4x corner crops, one row per corner, one column per variant (before, +1, +2 ... side by side)."""
    from PIL import Image, ImageDraw

    cell, gap, head = 260, 12, 34
    sheet = Image.new("RGB", (len(variants)*(cell+gap)+gap, len(CORNERS)*(cell+head)+head), (210, 210, 210))
    draw = ImageDraw.Draw(sheet)
    draw.text((gap, 4), base_name, fill="black")
    for col, variant in enumerate(variants):
        for row, corner in enumerate(CORNERS):
            crop = Image.open(out / f"{variant['case']}_{corner}.png").convert("RGB")
            x, y = gap + col*(cell+gap), head + row*(cell+head) + head
            draw.text((x, y-16), f"{variant['variant']}  {corner}", fill="black")
            sheet.paste(crop.resize((cell, cell), Image.Resampling.NEAREST), (x, y))
    sheet.save(out / f"{base_name}_width_comparison.png")


def cover_transform(source_size, target_size):
    """Centered aspect-preserving cover; source crop is expressed in original image pixels."""
    sw, sh = source_size
    tw, th = target_size
    if min(sw, sh, tw, th) <= 0:
        raise ValueError("cover dimensions must be positive")
    scale = max(tw/sw, th/sh)
    cw, ch = tw/scale, th/scale
    return {"source_size": [sw, sh], "target_size": [tw, th], "scale": scale,
            "source_crop": [(sw-cw)/2, (sh-ch)/2, cw, ch],
            "scaled_offset": [(tw-sw*scale)/2, (th-sh*scale)/2]}


def matching_wallpaper_reference(desktop_image, capture_rect, desktop_rect):
    """Map physical virtual-desktop coordinates to the matching captured wallpaper pixels."""
    if desktop_image.size != (desktop_rect[2]-desktop_rect[0], desktop_rect[3]-desktop_rect[1]):
        raise ValueError("captured wallpaper dimensions do not match native desktop bounds")
    x0, y0, x1, y1 = capture_rect
    if x0 < desktop_rect[0] or y0 < desktop_rect[1] or x1 > desktop_rect[2] or y1 > desktop_rect[3]:
        raise ValueError("native capture extends beyond the captured wallpaper")
    return desktop_image.crop((x0-desktop_rect[0], y0-desktop_rect[1], x1-desktop_rect[0], y1-desktop_rect[1]))


def source_provenance():
    import subprocess

    names = ("ui/settings_theme_spec.py", "ui/settings_surface_composition.py", "ui/settings_dialog.py",
             "ui/settings_theme_runtime.py", "ui/settings_theme.py", "ui/settings_window_edge.py",
             "core/windows/dwm_blur.py", "core/settings/surface_opacity.py",
             "ui/settings_material_underlay.py", "ui/tabs/shared_styles.py", "ui/studio/surface.py",
             "ui/studio/chrome.py", "ui/studio/theme.py", "tools/settings_native_corners.py")
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, timeout=15, check=True)
    return {"git_head": head.stdout.strip(), "working_source_sha256": {
        name: hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in names}}


def window_placement(available, cursor, size, dpr):
    """Logical top-left of a ``size`` window in the corner of ``available`` (x, y, w, h) farthest from ``cursor``,
    leaving room for the capture perimeter, the background margin and a gap to the available-area edge."""
    inset = math.ceil((CAPTURE_PAD + BACKGROUND_MARGIN + SCREEN_EDGE_GAP) / dpr)
    ax, ay, aw, ah = available
    candidates = [(ax + inset, ay + inset), (ax + aw - size[0] - inset, ay + inset),
                  (ax + inset, ay + ah - size[1] - inset), (ax + aw - size[0] - inset, ay + ah - size[1] - inset)]
    def distance(point):
        cx, cy = point[0] + size[0] / 2, point[1] + size[1] / 2
        return (cx - cursor[0])**2 + (cy - cursor[1])**2
    return max(candidates, key=distance)


def _configure_qt(qt_scale_factor):
    """Qt's public OpenGL selection (as the product's Quick bootstrap) before the application exists."""
    from PySide6.QtCore import QCoreApplication

    if QCoreApplication.instance() is not None:
        if qt_scale_factor:
            raise RuntimeError("--qt-scale-factor must be set before the Qt application exists")
        return
    if qt_scale_factor:
        # Qt's own high-DPI scale (read once at application start): Qt then rasterises at screen DPR x factor.
        os.environ["QT_SCALE_FACTOR"] = repr(float(qt_scale_factor))
    # The product's own Quick bootstrap: render loop, OpenGL, surface format (the Studio window needs all three).
    from rendering.quick.bootstrap import configure_quick_graphics
    configure_quick_graphics(reason="native-corner-evidence")


class _StudioStore:
    """The Studio's canonical store for one mode's resolved preset (a capture never commits anything back)."""

    def __init__(self, mode):
        from core.settings.visualizer_presets import resolve_visualizer_activation_payload
        self.values = dict(resolve_visualizer_activation_payload({"mode": mode, f"preset_{mode}": 0},
                                                                 mode=mode).resolved_config)

    def snapshot(self):
        return dict(self.values)

    def commit(self, values, changed):
        self.values.update(values)
        return dict(self.values)

    def preset_label(self):
        return "Preset"


class _NoSettingsPresence:
    concealed = False

    def conceal(self, **_kwargs):
        pass

    def reveal(self, **_kwargs):
        pass


def capture(label, material, dark_theme=None, light_theme=None, text_evidence=False, page="sources",
            single_theme=None, dark_background=None, light_background=None, background_pole="both",
            window="settings", extra_border_device_px=(0.0,), border_growth="centre", region_before_accent=False,
            qt_scale_factor=None, studio_mode="waveform_ribbon", retry_wait_s=20.0):
    if sys.platform != "win32":
        raise RuntimeError("this gate requires a native Windows interactive desktop")
    if window not in ("settings", "studio"):
        raise ValueError("--window is settings or studio")
    if text_evidence and window != "settings":
        raise ValueError("--text-evidence reads Settings QLabels only")
    widths = tuple(float(value) for value in extra_border_device_px)
    if not widths or any(value < 0 for value in widths):
        raise ValueError("--extra-border-device-px takes one or more non-negative device-pixel widths")
    _configure_qt(qt_scale_factor)
    import numpy as np
    from PIL import ImageGrab
    from PySide6.QtCore import QCoreApplication, QEvent, QRect, QRectF, Qt
    from PySide6.QtGui import QColor, QCursor, QImage, QPainter, QPalette
    from PySide6.QtWidgets import QApplication, QLabel, QWidget
    from core.animation import AnimationManager
    from core.settings.settings_manager import SettingsManager
    from ui.settings_dialog import SettingsDialog
    from ui.settings_theme_catalog import activate_persisted_settings_theme
    from ui.settings_theme_runtime import get_active_settings_theme, set_active_settings_theme
    import ui.settings_window_edge as edge_owner
    from ui.styled_popup import StyledPopup

    class WallpaperBackground(QWidget):
        def __init__(self, path):
            super().__init__(None, Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint
                             | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.WindowDoesNotAcceptFocus)
            self.image = QImage(str(path))
            if self.image.isNull():
                raise ValueError(f"cannot decode supplied wallpaper: {path}")

        def paintEvent(self, event):
            del event
            transform = cover_transform((self.image.width(), self.image.height()), (self.width(), self.height()))
            painter = QPainter(self)
            try:
                painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
                painter.drawImage(QRectF(self.rect()), self.image, QRectF(*transform["source_crop"]))
            finally:
                painter.end()

    app = QApplication.instance() or QApplication([])
    screens = [s for s in app.screens() if s.availableGeometry().width() >= WINDOW_LOGICAL_SIZE[0] + 200
               and s.availableGeometry().height() >= WINDOW_LOGICAL_SIZE[1] + 200]
    if not screens:
        raise RuntimeError("no native screen can display all four corners at the minimum window size")
    screen = max(screens, key=lambda s: s.availableGeometry().width() * s.availableGeometry().height())
    dpr_screen = float(screen.devicePixelRatio())
    out = artifact_paths.evidence_dir("settings", TOPIC, label)
    profile = artifact_paths.run_scratch(OWNER, label)
    previous_theme = get_active_settings_theme()
    user32 = ctypes.windll.user32
    user32.GetForegroundWindow.restype = wintypes.HWND
    old_popup = StyledPopup.exec
    StyledPopup.exec = lambda popup: setattr(popup, "_result_value", None)
    cursor = QCursor.pos()
    available = screen.availableGeometry()
    placement = window_placement((available.x(), available.y(), available.width(), available.height()),
                                 (cursor.x(), cursor.y()), WINDOW_LOGICAL_SIZE, dpr_screen)
    report = {"provider": "native_windows_desktop_ImageGrab_DwmFlush", "pid": os.getpid(), "window": window,
              "screen": screen.name(), "dpr": dpr_screen, "page": page, "cases": [], "invalid_attempts": [],
              "dpr_emulation": ({"qt_scale_factor": float(qt_scale_factor), "note": "Qt rasterisation at the "
                                 "emulated DPR on the real monitor; DWM shadow/blur stay at the monitor's DPI"}
                                if qt_scale_factor else None),
              "parameters": {"extra_border_device_px": list(widths), "border_growth": border_growth,
                             "region_before_accent": bool(region_before_accent),
                             "studio_mode": studio_mode if window == "studio" else None},
              "placement_logical": list(placement), "cursor_logical": [cursor.x(), cursor.y()],
              "window_captures": 0, "background_captures": 0,
              "shadow_boundary": "Product outer-shadow coverage is zero. Native DWM shadow is measured separately "
                  "outside the HWND; the 48px capture perimeter must return to the background."}
    shown = {"window": None, "background": None, "controller": None}
    probe_hwnds = []
    report["source_before"] = source_provenance()
    report["composition_control"] = ("region_before_accent" if region_before_accent else "current_shared_product_only")
    import core.windows.dwm_blur as native_backdrop
    import ui.studio.surface as studio_surface
    original_accent_policy = native_backdrop._apply_accent_policy
    original_edge = edge_owner.paint_forged_window_edge
    original_geometry = studio_surface.initial_geometry
    report["accent_policy_calls"] = []
    edge_state = {"extra": widths[0], "forged": None, "region": {}, "measured_hwnd": None, "dpr": dpr_screen}

    def record_accent_policy(hwnd, *, accent_state, accent_flags=0, gradient_color=0):
        region = None
        if region_before_accent and accent_state != 0 and int(hwnd) not in edge_state["region"]:
            region = _set_rounded_region(int(hwnd), edge_owner.SETTINGS_OUTER_CORNER_RADIUS * edge_state["dpr"])
            edge_state["region"][int(hwnd)] = region
        ok = original_accent_policy(hwnd, accent_state=accent_state, accent_flags=accent_flags,
                                    gradient_color=gradient_color)
        report["accent_policy_calls"].append({"hwnd": int(hwnd), "state": accent_state,
                                               "flags": accent_flags, "gradient_abgr": gradient_color,
                                               "applied": ok, "region_set_before": region})
        return ok

    def measured_edge(painter, outer_rect, dpr, **kwargs):
        edge_state["forged"] = list(QColor(kwargs["outer_border"]).getRgb())
        kwargs.setdefault("extra_border_device_px", edge_state["extra"])
        kwargs.setdefault("border_growth", border_growth)
        return original_edge(painter, outer_rect, dpr, **kwargs)

    def close_shown():
        if shown["controller"] is not None:
            shown["controller"].close()
            shown["controller"] = None
        elif shown["window"] is not None:
            shown["window"].close()
            shown["window"].deleteLater()
        shown["window"] = None
        if shown["background"] is not None:
            shown["background"].close()
            shown["background"].deleteLater()
            shown["background"] = None
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        _pump(app, 0.1)

    native_backdrop._apply_accent_policy = record_accent_policy
    edge_owner.paint_forged_window_edge = measured_edge
    try:
        with evidence_media.evidence_workspace(OWNER, out) as work:
            work.mkdir(parents=True, exist_ok=True)
            if bool(dark_background) != bool(light_background):
                raise ValueError("wallpaper capture requires both --dark-background and --light-background")
            wallpapers = {"dark": Path(dark_background), "light": Path(light_background)} if dark_background else {}
            if any(not path.is_file() for path in wallpapers.values()):
                raise ValueError("every supplied wallpaper must exist at its exact literal path")
            if single_theme:
                if dark_theme or light_theme:
                    raise ValueError("--theme cannot be combined with the explicit theme pair")
                from ui.settings_theme_io import load_settings_theme_file
                from ui.theme_semantics import settings_theme_is_light
                path = ROOT / "themes" / single_theme
                if not path.is_file() or path.parent != ROOT / "themes":
                    raise ValueError("--theme must name an existing canonical theme file")
                theme = load_settings_theme_file(path)
                themes = {"light" if settings_theme_is_light(theme) else "dark": path}
            elif dark_theme or light_theme:
                if not dark_theme or not light_theme:
                    raise ValueError("explicit theme capture requires both --dark-theme and --light-theme")
                themes = {"dark": ROOT / "themes" / dark_theme, "light": ROOT / "themes" / light_theme}
                if any(not path.is_file() or path.parent != ROOT / "themes" for path in themes.values()):
                    raise ValueError("explicit themes must name existing canonical theme files")
            else:
                themes = _themes(material)
            pending = [(tone, theme_path, background_tone, rgb) for tone, theme_path in themes.items()
                       for background_tone, rgb in (("dark", (18, 18, 18)), ("light", (244, 244, 244)))
                       if background_pole in ("both", background_tone)]
            attempts = 0
            while pending:
                tone, theme_path, background_tone, rgb = pending.pop(0)
                attempts += 1
                if attempts > len(themes) * 2 * 3:
                    raise RuntimeError("the capture area stayed occluded by other windows; try again later")
                base_name = f"{window}_{tone}_theme_{background_tone}_background"
                settings = SettingsManager(application="native_settings_corner_evidence", storage_base_dir=profile)
                settings.set("sources.folders", [str(profile)])
                settings.set("ui.last_tab_key", page)
                settings.set("ui.settings_theme_selection", f"file:{theme_path.name}")
                selected = activate_persisted_settings_theme(settings, ROOT / "themes").resolution
                if selected.used_fallback:
                    raise RuntimeError("the selected native capture theme was not admitted")
                edge_state["extra"] = widths[0]
                edge_state["region"] = {}
                animations = None
                window_rect = QRect(placement[0], placement[1], *WINDOW_LOGICAL_SIZE)
                margin = math.ceil((CAPTURE_PAD + BACKGROUND_MARGIN) / dpr_screen)
                # Build the measured window first (not shown): the background goes up only right before it.
                deferred_show = []
                if window == "settings":
                    animations = AnimationManager(owner="settings:native-corner-evidence")
                    measured = SettingsDialog(settings, animations)
                    measured.resize(*WINDOW_LOGICAL_SIZE)
                    measured.move(window_rect.topLeft())
                    measured.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
                    measured.setWindowFlag(Qt.WindowType.WindowDoesNotAcceptFocus, True)
                    measured.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
                    shown["window"] = measured
                    deferred_show.append(measured.show)
                else:
                    from ui.studio.controller import StudioController
                    from ui.studio.registry import create_adapter
                    from ui.studio.theme import studio_theme
                    adapter = create_adapter(studio_mode)
                    adapter.recorded_clips = lambda: ()
                    surfaces = []

                    def factory(controller):
                        # Topmost only (above the topmost background); never QQuickWindow.grabWindow() here: with
                        # the threaded render loop it deadlocks against the GIL (as hide() does, surface.py retire).
                        surface = studio_surface.StudioWindowSurface(controller)
                        surface.window.setFlags(surface.window.flags() | Qt.WindowType.WindowStaysOnTopHint)
                        # The controller shows the real window at the end of open(); the tool runs that very
                        # show once the controlled background is up.
                        deferred_show.append(surface.show)
                        surface.show = lambda: None
                        surfaces.append(surface)
                        return surface

                    studio_surface.initial_geometry = lambda anchor: QRect(window_rect)
                    controller = StudioController(adapter, _StudioStore(studio_mode), _NoSettingsPresence(),
                                                  factory, theme_provider=studio_theme)
                    shown["controller"] = controller
                    if not controller.open():
                        raise RuntimeError("the real Studio window could not be built")
                    shown["window"] = surfaces[0].window
                background_path = wallpapers.get(background_tone)
                background = (WallpaperBackground(background_path) if background_path else
                              QWidget(None, Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint
                                      | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.WindowDoesNotAcceptFocus))
                background.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
                background.setWindowTitle("SRPSS Native Corner Evidence Background")
                palette = background.palette()
                palette.setColor(QPalette.ColorRole.Window, QColor(*rgb))
                background.setPalette(palette)
                background.setAutoFillBackground(True)
                background.setGeometry(window_rect.adjusted(-margin, -margin, margin, margin))
                shown["background"] = background
                background.show()
                on_screen_since = time.monotonic()
                _pump(app, 0.1)
                deferred_show[0]()
                if window == "settings":
                    _pump(app, 0.55)
                    hwnd = int(measured.winId())
                    dpr = float(measured.devicePixelRatioF())
                    repaint = measured._forged_edge.update
                    backdrop_mode = measured._native_backdrop_mode
                else:
                    presented = []
                    surfaces[0].window.frameSwapped.connect(lambda: presented.append(time.monotonic()))
                    until = time.monotonic() + 1.8
                    while len(presented) < 3 and time.monotonic() < until:
                        _pump(app, 0.05)
                    _pump(app, 0.2)
                    report.setdefault("studio_frames_swapped_before_capture", []).append(len(presented))
                    hwnd = int(surfaces[0].window.winId())
                    dpr = float(surfaces[0].window.effectiveDevicePixelRatio())
                    from PySide6.QtQuick import QQuickItem
                    edges = [item for item in surfaces[0].host.root.findChildren(QQuickItem)
                             if item.objectName() == "studioWindowEdge"]
                    if len(edges) != 1:
                        raise RuntimeError("the Studio shell has no single forged window edge item")
                    repaint = edges[0].update
                    backdrop_mode = surfaces[0].material if surfaces[0].backdrop_applied else "off"
                edge_state["measured_hwnd"] = hwnd
                probe_hwnds.extend((hwnd, int(background.winId())))
                if not user32.IsWindowVisible(wintypes.HWND(hwnd)):
                    raise RuntimeError(f"the real {window} HWND is not visible")
                desktop_rect = _rect(int(background.winId()))
                native = _rect(hwnd)
                pad = CAPTURE_PAD
                capture_rect = (native[0]-pad, native[1]-pad, native[2]+pad, native[3]+pad)
                if (capture_rect[0] < desktop_rect[0] or capture_rect[1] < desktop_rect[1]
                        or capture_rect[2] > desktop_rect[2] or capture_rect[3] > desktop_rect[3]):
                    raise RuntimeError("the native window plus shadow perimeter does not fit the controlled background")
                blocking = [item for item in occluders(hwnd, capture_rect) if not item["click_through"]]
                if blocking:
                    report["invalid_attempts"].append({"case": base_name, "occluders": blocking,
                                                       "foreground": int(user32.GetForegroundWindow() or 0)})
                    print(f"{base_name}: occluded by {blocking}; retrying later", flush=True)
                    close_shown()
                    if animations is not None:
                        animations.stop()
                    pending.append((tone, theme_path, background_tone, rgb))
                    time.sleep(retry_wait_s)
                    continue
                width, height = native[2]-native[0], native[3]-native[1]
                # On screen: only grabs. Analysis and every file write happen after the windows are closed.
                grabbed = []
                for index, extra in enumerate(widths):
                    if index:
                        edge_state["extra"] = extra
                        repaint()
                        _pump(app, 0.25)
                    if time.monotonic() - on_screen_since > MAX_ON_SCREEN_S:
                        raise RuntimeError("a capture window exceeded its on-screen budget")
                    image = ImageGrab.grab(bbox=capture_rect, all_screens=True).convert("RGB")
                    report["window_captures"] += 1
                    late = [item for item in occluders(hwnd, capture_rect) + occluders(int(background.winId()),
                                                                                        capture_rect)
                            if not item["click_through"]]
                    if late:
                        raise RuntimeError(f"another process's window covered the capture: {late}")
                    grabbed.append((extra, image, late, list(edge_state["forged"] or []),
                                    _native_region(hwnd, width, height)))
                if text_evidence:
                    _text_evidence(app, measured, native, capture_rect, work, f"{base_name}_today", QLabel, ImageGrab)
                    report["window_captures"] += 1
                accent_calls = [call for call in report["accent_policy_calls"] if call["hwnd"] == hwnd]
                # The window closes first; the controlled background alone is then the desktop reference.
                if shown["controller"] is not None:
                    shown["controller"].close()
                    shown["controller"] = None
                else:
                    shown["window"].close()
                    shown["window"].deleteLater()
                shown["window"] = None
                _pump(app, 0.25)
                background_pixels = ImageGrab.grab(bbox=desktop_rect, all_screens=True).convert("RGB")
                report["background_captures"] += 1
                late_background = [item for item in occluders(int(background.winId()), desktop_rect)
                                   if not item["click_through"]]
                if background_path:
                    background_info = {"mode": "wallpaper_cover", "path": str(background_path.resolve()),
                                       "sha256": hashlib.sha256(background_path.read_bytes()).hexdigest(),
                                       "logical_cover": cover_transform((background.image.width(), background.image.height()),
                                                                        (background.width(), background.height())),
                                       "physical_cover": cover_transform((background.image.width(), background.image.height()),
                                                                         (desktop_rect[2]-desktop_rect[0], desktop_rect[3]-desktop_rect[1]))}
                else:
                    background_info = {"mode": "solid", "rgb": rgb}
                report.setdefault("on_screen_seconds", []).append(round(time.monotonic() - on_screen_since, 3))
                close_shown()
                if animations is not None:
                    animations.stop()
                settings.flush(timeout=5.0)
                if late_background:
                    # Something of another process covered the background: its pixels are not ours to keep.
                    report["invalid_attempts"].append({"case": base_name, "reference_occluders": late_background})
                    print(f"{base_name}: reference occluded; retrying later", flush=True)
                    pending.append((tone, theme_path, background_tone, rgb))
                    time.sleep(retry_wait_s)
                    continue
                background_pixels.save(work / f"{base_name}_desktop_reference.png")
                reference = matching_wallpaper_reference(background_pixels, capture_rect, desktop_rect)
                reference.save(work / f"{base_name}_background_reference.png")
                variants = []
                for extra, image, late, forged_rgba, region_info in grabbed:
                    variant = f"plus{extra:g}px".replace(".", "_") if extra else "today"
                    name = f"{base_name}_{variant}"
                    image.save(work / f"{name}.png")
                    a, b = np.asarray(image, dtype=np.int16), np.asarray(reference, dtype=np.int16)
                    delta = np.abs(a-b).max(2)
                    radius = edge_owner.SETTINGS_OUTER_CORNER_RADIUS * dpr
                    for corner, cx, cy in (("top_left", pad, pad), ("top_right", pad+width-1, pad),
                            ("bottom_left", pad, pad+height-1), ("bottom_right", pad+width-1, pad+height-1)):
                        image.crop((cx-32, cy-32, cx+33, cy+33)).save(work / f"{name}_{corner}.png")
                    silhouette = painted_silhouette(dpr, extra, border_growth)
                    case = {"case": name, "variant": variant, "window": window, "theme": theme_path.name,
                            "theme_tone": tone, "background_tone": background_tone, "hwnd": hwnd,
                            "native_rect": native, "extra_border_device_px": extra, "border_growth": border_growth,
                            "theme_sha256": hashlib.sha256(theme_path.read_bytes()).hexdigest(),
                            "capture_rect": capture_rect, "dpr": dpr, "radius_physical_px": radius,
                            "native_backdrop_mode": backdrop_mode, "background": background_info,
                            "outer_border_rgba": forged_rgba, "painted_silhouette": silhouette,
                            "occluded_after_capture": late, "background_occluded_at_reference": late_background,
                            "accent_policy_calls": accent_calls,
                            **analyze_pixels(delta, width, height, pad, radius)}
                    case["silhouette_corners"] = analyze_silhouette(delta, image, width, height, pad, silhouette,
                                                                    forged_rgba or None)
                    active_theme = get_active_settings_theme()
                    material_tint = active_theme.material_tint()
                    request_mode, request_tint = active_theme.native_backdrop_request()
                    case["material_semantics"] = {"material": active_theme.backdrop.mode,
                                                  "material_tint_rgba": material_tint.as_tuple() if material_tint else None,
                                                  "window_surface_rgba": active_theme.window_surface().as_tuple(),
                                                  "native_request_mode": request_mode,
                                                  "native_request_tint_rgba": request_tint.as_tuple() if request_tint else None}
                    case["native_region"] = region_info
                    # Content sanity: a window that never presented its own pixels shows only material here.
                    border_band = delta[pad:pad+height, pad:pad+width].copy()
                    border_band[12:-12, 12:-12] = 0
                    case["edge_band_changed_fraction"] = round(float((border_band > 24).sum())
                                                               / max(1, int((border_band >= 0).sum())
                                                                     - (height-24)*(width-24)), 4)
                    report["cases"].append(case)
                    variants.append(case)
                    print(json.dumps({key: case[key] for key in ("case", "dpr", "corners")}), flush=True)
                if len(variants) > 1:
                    write_width_comparison(work, base_name, variants)
            report["probe_windows_closed"] = all(not user32.IsWindowVisible(wintypes.HWND(hwnd)) for hwnd in probe_hwnds)
            report["source_after"] = source_provenance()
            report["source_stable_during_capture"] = (report["source_before"]["working_source_sha256"]
                                                      == report["source_after"]["working_source_sha256"])
            (work / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
            if report["cases"]:
                write_corner_sheet(work, report["cases"])
    finally:
        close_shown()
        StyledPopup.exec = old_popup
        native_backdrop._apply_accent_policy = original_accent_policy
        edge_owner.paint_forged_window_edge = original_edge
        studio_surface.initial_geometry = original_geometry
        set_active_settings_theme(previous_theme)
    print(f"Native evidence: {out}", flush=True)
    scratch_owner = artifact_paths.scratch_root(OWNER).resolve()
    if profile.resolve().parent != scratch_owner:
        raise RuntimeError("refusing cleanup outside this capture's named scratch owner")
    artifact_paths.discard_run_scratch(OWNER)
    return out


def _text_evidence(app, dialog, native, capture_rect, work, name, QLabel, ImageGrab):
    labels = []
    original_label_styles = []
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
        original_label_styles.append((widget, widget.styleSheet()))
        widget.setStyleSheet(widget.styleSheet() + "; color: transparent;")
    _pump(app, 0.15)
    ImageGrab.grab(bbox=capture_rect, all_screens=True).convert("RGB").save(work / f"{name}_ink_off.png")
    (work / f"{name}_labels.json").write_text(json.dumps(labels, indent=2), encoding="utf-8")
    for widget, style in original_label_styles:
        widget.setStyleSheet(style)
    _pump(app, 0.1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--label", required=True)
    parser.add_argument("--material", choices=("glass", "acrylic", "mica", "frosted", "smoked", "off"), required=True)
    parser.add_argument("--window", choices=("settings", "studio"), default="settings")
    parser.add_argument("--dark-theme")
    parser.add_argument("--light-theme")
    parser.add_argument("--theme", help="One canonical theme for a focused native capture")
    parser.add_argument("--dark-background", help="Exact image path for the controlled dark background")
    parser.add_argument("--light-background", help="Exact image path for the controlled light background")
    parser.add_argument("--text-evidence", action="store_true", help="Capture actual QLabel metadata and a matched transparent-ink frame")
    parser.add_argument("--background-pole", choices=("both", "dark", "light"), default="both")
    parser.add_argument("--page", choices=("sources", "themes", "accessibility"), default="sources")
    parser.add_argument("--extra-border-device-px", type=float, nargs="+", default=[0.0],
                        help="Extra border width(s) in DEVICE px, each captured from the same shown window")
    parser.add_argument("--border-growth", choices=("centre", "outward"), default="centre")
    parser.add_argument("--region-before-accent", action="store_true",
                        help="Experiment: native rounded region set immediately before the AccentPolicy call")
    parser.add_argument("--qt-scale-factor", type=float, help="Emulate DPR = monitor DPR x factor (Qt rasterisation)")
    parser.add_argument("--studio-mode", default="waveform_ribbon")
    args = parser.parse_args()
    capture(args.label, args.material, dark_theme=args.dark_theme, light_theme=args.light_theme,
            text_evidence=args.text_evidence, page=args.page, single_theme=args.theme,
            dark_background=args.dark_background, light_background=args.light_background,
            background_pole=args.background_pole, window=args.window,
            extra_border_device_px=args.extra_border_device_px, border_growth=args.border_growth,
            region_before_accent=args.region_before_accent,
            qt_scale_factor=args.qt_scale_factor, studio_mode=args.studio_mode)
