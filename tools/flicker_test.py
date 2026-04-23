"""Settings-dialog flicker reproduction and constructor-phase isolator.

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
  14  Plain dialog + main.py startup setup (DPI/GL/icon baseline)
  15  Full flags + main.py startup setup
  16  Full flags + stylesheet + main.py startup setup
  17  Actual SettingsDialog + main.py startup setup
  18  SettingsDialog shell-only profile (window setup only; UI/theme/post hooks disabled)
  19  SettingsDialog no-theme profile
  20  SettingsDialog no-post-init profile (skip post-UI hooks)
  21  SettingsDialog no-setup-window profile (leave default QDialog flags)
  22  SettingsDialog no-background-tab-hydration profile
  23  SettingsDialog no-tab-styling profile
  24  SettingsDialog no-global-font-apply profile
  25  SettingsDialog hydrate only Display tab
  26  SettingsDialog hydrate only Transitions tab
  27  SettingsDialog hydrate only Widgets tab
  28  SettingsDialog hydrate only Accessibility tab
  29  SettingsDialog hydrate only About tab
  30  SettingsDialog hydrate only Widgets tab + no tab styling
  31  SettingsDialog hydrate only Widgets tab (stub tab builder)
  32  SettingsDialog hydrate only Widgets tab (patched WidgetsTab: shell only)
  33  SettingsDialog hydrate only Widgets tab (patched WidgetsTab: setup_ui only)
  34  SettingsDialog initial tab forced to Widgets (no background hydration)
  35  SettingsDialog initial tab forced to Sources (no background hydration)
  36  SettingsDialog initial tab forced to Sources + hydrate all except Widgets
  37  SettingsDialog hydrate only Widgets tab (patched WidgetsTab: unstyled combos)
  38  SettingsDialog hydrate only Widgets tab (setup_ui only, no Clock section)
  39  SettingsDialog hydrate only Widgets tab (setup_ui only, no Weather section)
  40  SettingsDialog hydrate only Widgets tab (setup_ui only, no Media section)
  41  SettingsDialog hydrate only Widgets tab (setup_ui only, no Visualizers section)
  42  SettingsDialog hydrate only Widgets tab (setup_ui only, no Reddit section)
  43  SettingsDialog hydrate only Widgets tab (setup_ui only, no Defaults section)
  44  SettingsDialog hydrate only Widgets tab (setup_ui only, Defaults-only)
  45  SettingsDialog hydrate only Widgets tab (setup_ui only, Clock-only)
  46  SettingsDialog hydrate only Widgets tab (setup_ui only, Weather-only)
  47  SettingsDialog hydrate only Widgets tab (setup_ui only, Media-only)
  48  SettingsDialog hydrate only Widgets tab (setup_ui only, Visualizers-only)
  49  SettingsDialog hydrate only Widgets tab (setup_ui only, Reddit-only)
  50  SettingsDialog hydrate only Widgets tab (setup_ui only, Visualizers-only, no Technical groups)
  51  SettingsDialog hydrate only Widgets tab (setup_ui only, Visualizers-only, no Technical groups, unstyled combos)
  52  SettingsDialog hydrate only Widgets tab (setup_ui only, Visualizers-only, scaffold stub)
  53  SettingsDialog hydrate only Widgets tab (setup_ui only, Visualizers-only, no Technical groups, stub preset slider)
  54  Plain QDialog with six VisualizerPresetSlider widgets
  55  Plain QDialog with six VisualizerPresetSlider widgets (data-only, _build_ui no-op)
  56  Plain QDialog with six VisualizerPresetSlider widgets (QSlider instead of NoWheelSlider)
  57  Plain QDialog with six VisualizerPresetSlider widgets (QSlider + notch bar stub)
  58  Plain QDialog with six VisualizerPresetSlider widgets (NoWheelSlider + notch bar stub)
  59  Plain QDialog with six VisualizerPresetSlider widgets (labels + buttons only)
  60  Plain QDialog with six VisualizerPresetSlider widgets (slider-only row)
  61  Plain QDialog with six VisualizerPresetSlider widgets (buttons-only row)
  62  Plain QDialog with six VisualizerPresetSlider widgets (slider-only, original slider settings)
  63  Plain QDialog with six VisualizerPresetSlider widgets (buttons-only, original button style/handlers)
  64  Plain QDialog with six VisualizerPresetSlider widgets (full row static, no notch)
  65  Plain QDialog with six VisualizerPresetSlider widgets (full row static, with notch)
  66  Plain QDialog with six VisualizerPresetSlider widgets (full row static + original slot connections)
  67  Plain QDialog with six VisualizerPresetSlider widgets (full row static + lambda connections)
  68  Plain QDialog with six VisualizerPresetSlider widgets (full row static + real notch class)
  69  Plain QDialog with six VisualizerPresetSlider widgets (full row static + real notch + _PresetNoWheelSlider)
  70  Plain QDialog with six VisualizerPresetSlider widgets (variant 69 + explicit edit_btn.setVisible(True))

Press Enter in the console to show the dialog for each variant.

Optional env toggles:
  SRPSS_FLICKER_AUTO_CLOSE_S=10
  SRPSS_FLICKER_SKIP_PROMPT=1
  SRPSS_FLICKER_WINPROBE=1
  SRPSS_FLICKER_EXTERNAL_WINPROBE=1
  SRPSS_FLICKER_WINPROBE_ALL=1
  SRPSS_FLICKER_WINPROBE_SAMPLE_MS=5
"""

import sys
import time
import os
import ctypes
import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Callable, Dict, List

# Ensure project root is on sys.path for variant 13/14
_PROJECT_ROOT = str(Path(__file__).parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from PySide6.QtWidgets import (
    QApplication, QDialog, QLabel, QVBoxLayout, QHBoxLayout,
    QPushButton, QCheckBox, QComboBox, QGroupBox, QScrollArea, QWidget,
)
from PySide6.QtCore import Qt, QCoreApplication, QEvent
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

# Auto-close observation window per variant (seconds). Override with:
#   SRPSS_FLICKER_AUTO_CLOSE_S=15 python tools/flicker_test.py 13
AUTO_CLOSE_SECONDS = float(os.environ.get("SRPSS_FLICKER_AUTO_CLOSE_S", "10"))
SKIP_START_PROMPT = os.environ.get("SRPSS_FLICKER_SKIP_PROMPT", "0").strip() in {"1", "true", "True"}
WINPROBE_ENABLED = os.environ.get("SRPSS_FLICKER_WINPROBE", "1").strip().lower() in {"1", "true", "yes", "on"}
WINPROBE_ALL_PROCESSES = os.environ.get("SRPSS_FLICKER_WINPROBE_ALL", "0").strip().lower() in {"1", "true", "yes", "on"}
WINPROBE_SAMPLE_MS = max(1, int(os.environ.get("SRPSS_FLICKER_WINPROBE_SAMPLE_MS", "5")))
EXTERNAL_WINPROBE_ENABLED = os.environ.get("SRPSS_FLICKER_EXTERNAL_WINPROBE", "1").strip().lower() in {"1", "true", "yes", "on"}


if os.name == "nt":
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    GWL_STYLE = -16
    GWL_EXSTYLE = -20
    WS_CAPTION = 0x00C00000


    class _RECT(ctypes.Structure):
        _fields_ = [
            ("left", ctypes.c_long),
            ("top", ctypes.c_long),
            ("right", ctypes.c_long),
            ("bottom", ctypes.c_long),
        ]


def _get_win_pid(hwnd: int) -> int:
    if os.name != "nt":
        return 0
    pid = ctypes.c_ulong(0)
    user32.GetWindowThreadProcessId(ctypes.c_void_p(hwnd), ctypes.byref(pid))
    return int(pid.value)


def _get_win_text(hwnd: int) -> str:
    if os.name != "nt":
        return ""
    buf = ctypes.create_unicode_buffer(512)
    user32.GetWindowTextW(ctypes.c_void_p(hwnd), buf, 512)
    return buf.value


def _get_win_class(hwnd: int) -> str:
    if os.name != "nt":
        return ""
    buf = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(ctypes.c_void_p(hwnd), buf, 256)
    return buf.value


def _get_win_rect(hwnd: int) -> tuple[int, int, int, int]:
    if os.name != "nt":
        return (0, 0, 0, 0)
    rect = _RECT()
    ok = user32.GetWindowRect(ctypes.c_void_p(hwnd), ctypes.byref(rect))
    if not ok:
        return (0, 0, 0, 0)
    return (int(rect.left), int(rect.top), int(rect.right), int(rect.bottom))


def _get_win_styles(hwnd: int) -> tuple[int, int]:
    if os.name != "nt":
        return (0, 0)
    style = int(user32.GetWindowLongPtrW(ctypes.c_void_p(hwnd), GWL_STYLE)) & 0xFFFFFFFF
    exstyle = int(user32.GetWindowLongPtrW(ctypes.c_void_p(hwnd), GWL_EXSTYLE)) & 0xFFFFFFFF
    return (style, exstyle)


def _enum_visible_windows(include_all_processes: bool = False) -> List[Dict[str, Any]]:
    if os.name != "nt":
        return []
    current_pid = int(kernel32.GetCurrentProcessId())
    windows: List[Dict[str, Any]] = []
    enum_proc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

    @enum_proc
    def _cb(hwnd_raw, _lparam) -> bool:
        hwnd = int(ctypes.cast(hwnd_raw, ctypes.c_void_p).value)
        if not bool(user32.IsWindowVisible(ctypes.c_void_p(hwnd))):
            return True
        pid = _get_win_pid(hwnd)
        if not include_all_processes and pid != current_pid:
            return True
        left, top, right, bottom = _get_win_rect(hwnd)
        width = max(0, right - left)
        height = max(0, bottom - top)
        style, exstyle = _get_win_styles(hwnd)
        windows.append(
            {
                "hwnd": hwnd,
                "pid": pid,
                "class": _get_win_class(hwnd),
                "title": _get_win_text(hwnd),
                "left": left,
                "top": top,
                "right": right,
                "bottom": bottom,
                "width": width,
                "height": height,
                "style": style,
                "exstyle": exstyle,
            }
        )
        return True

    user32.EnumWindows(_cb, 0)
    return windows


def _start_external_winprobe(variant: int) -> tuple[subprocess.Popen[str] | None, Path | None]:
    if os.name != "nt" or not WINPROBE_ENABLED or not EXTERNAL_WINPROBE_ENABLED:
        return (None, None)
    observer_path = Path(__file__).with_name("winprobe_observer.py")
    if not observer_path.exists():
        return (None, None)

    duration_s = max(4.0, float(AUTO_CLOSE_SECONDS) + 4.0)
    out_path = Path(tempfile.gettempdir()) / f"srpss_flicker_winprobe_v{variant}_{int(time.time()*1000)}.json"
    cmd = [
        sys.executable,
        str(observer_path),
        "--out",
        str(out_path),
        "--duration-s",
        f"{duration_s:.3f}",
        "--sample-ms",
        str(WINPROBE_SAMPLE_MS),
    ]
    if WINPROBE_ALL_PROCESSES:
        cmd.append("--include-all")
    else:
        cmd.extend(["--pid", str(os.getpid())])
    try:
        proc = subprocess.Popen(cmd)
    except Exception as exc:
        print(f"  [winprobe v{variant}] failed to launch external observer: {exc}")
        return (None, None)
    return (proc, out_path)


def _finish_external_winprobe(
    proc: subprocess.Popen[str] | None,
    out_path: Path | None,
    *,
    variant: int,
) -> None:
    if proc is None or out_path is None:
        return
    try:
        proc.wait(timeout=max(3.0, float(AUTO_CLOSE_SECONDS) + 6.0))
    except Exception:
        try:
            proc.terminate()
            proc.wait(timeout=2.0)
        except Exception:
            pass

    if not out_path.exists():
        print(f"  [winprobe v{variant}] observer produced no output")
        return
    try:
        payload = json.loads(out_path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"  [winprobe v{variant}] failed to parse observer output: {exc}")
        return

    windows = payload.get("new_windows", [])
    if windows:
        rows = []
        for rec in windows:
            first_ts = float(rec.get("first_ts", 0.0))
            last_ts = float(rec.get("last_ts", first_ts))
            duration_ms = max(0.0, (last_ts - first_ts) * 1000.0)
            tiny_caption = bool(int(rec.get("style", 0)) & WS_CAPTION) and int(rec.get("width", 0)) <= 520 and int(rec.get("height", 0)) <= 360
            rows.append((tiny_caption, duration_ms, rec))
        rows.sort(key=lambda r: (not r[0], -r[1], int(r[2].get("pid", 0))))
        print(f"  [winprobe-ext v{variant}] new visible HWNDs during variant: {len(rows)}")
        for tiny_caption, duration_ms, rec in rows[:30]:
            marker = "TINY_CAPTION" if tiny_caption else "window"
            print(
                "    - "
                f"{marker} t+{float(rec.get('first_ts', 0.0))*1000.0:.1f}ms hwnd=0x{int(rec['hwnd']):x} "
                f"pid={int(rec.get('pid', 0))} class='{rec.get('class', '')}' "
                f"size={int(rec.get('width', 0))}x{int(rec.get('height', 0))} dur_ms={duration_ms:.1f} "
                f"style=0x{int(rec.get('style', 0)):08x} title='{rec.get('title', '')}'"
            )
        if len(rows) > 30:
            print(f"    - ... {len(rows) - 30} more")
    else:
        print(f"  [winprobe-ext v{variant}] no new visible HWNDs during variant")

    fg_events = payload.get("foreground_changes", [])
    if fg_events:
        print(f"  [winprobe-ext v{variant}] foreground changes: {len(fg_events)}")
        for ev in fg_events[:30]:
            print(
                "    - "
                f"t+{float(ev.get('ts', 0.0))*1000.0:.1f}ms hwnd=0x{int(ev.get('hwnd', 0)):x} "
                f"pid={int(ev.get('pid', 0))} class='{ev.get('class', '')}' title='{ev.get('title', '')}'"
            )
        if len(fg_events) > 30:
            print(f"    - ... {len(fg_events) - 30} more")
    else:
        print(f"  [winprobe-ext v{variant}] no foreground changes observed")

    try:
        out_path.unlink(missing_ok=True)
    except Exception:
        pass


def _observe_with_winprobe(
    app: QApplication,
    seconds: float,
    *,
    variant: int,
) -> None:
    if os.name != "nt":
        _pump_events(app, max(0, int(seconds * 1000)))
        return

    include_all = WINPROBE_ALL_PROCESSES
    baseline = {w["hwnd"] for w in _enum_visible_windows(include_all)}
    discovered: Dict[int, Dict[str, Any]] = {}
    fg_events: List[Dict[str, Any]] = []
    last_fg = int(user32.GetForegroundWindow())
    start = time.perf_counter()
    deadline = start + max(0.0, seconds)
    sleep_s = WINPROBE_SAMPLE_MS / 1000.0

    while time.perf_counter() < deadline:
        app.processEvents()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)

        now = time.perf_counter()
        visible = _enum_visible_windows(include_all)
        for win in visible:
            hwnd = int(win["hwnd"])
            if hwnd in baseline:
                continue
            rec = discovered.get(hwnd)
            if rec is None:
                rec = dict(win)
                rec["first_ts"] = now
                rec["last_ts"] = now
                rec["samples"] = 1
                discovered[hwnd] = rec
            else:
                rec["last_ts"] = now
                rec["samples"] += 1
                rec["width"] = max(int(rec.get("width", 0)), int(win["width"]))
                rec["height"] = max(int(rec.get("height", 0)), int(win["height"]))

        fg = int(user32.GetForegroundWindow())
        if fg and fg != last_fg:
            fg_events.append(
                {
                    "ts": now - start,
                    "hwnd": fg,
                    "pid": _get_win_pid(fg),
                    "class": _get_win_class(fg),
                    "title": _get_win_text(fg),
                }
            )
            last_fg = fg

        time.sleep(sleep_s)

    if discovered:
        rows = []
        for rec in discovered.values():
            duration_ms = max(0.0, (rec["last_ts"] - rec["first_ts"]) * 1000.0)
            tiny_caption = bool(rec.get("style", 0) & WS_CAPTION) and rec.get("width", 0) <= 520 and rec.get("height", 0) <= 360
            rows.append((tiny_caption, duration_ms, rec))
        rows.sort(key=lambda r: (not r[0], -r[1], r[2].get("pid", 0)))
        print(f"  [winprobe v{variant}] new visible HWNDs during observe: {len(rows)}")
        for tiny_caption, duration_ms, rec in rows[:20]:
            marker = "TINY_CAPTION" if tiny_caption else "window"
            print(
                "    - "
                f"{marker} hwnd=0x{int(rec['hwnd']):x} pid={rec['pid']} class='{rec['class']}' "
                f"size={rec['width']}x{rec['height']} dur_ms={duration_ms:.1f} "
                f"style=0x{int(rec['style']):08x} title='{rec['title']}'"
            )
        if len(rows) > 20:
            print(f"    - ... {len(rows) - 20} more")
    else:
        print(f"  [winprobe v{variant}] no new visible HWNDs during observe")

    if fg_events:
        print(f"  [winprobe v{variant}] foreground changes: {len(fg_events)}")
        for ev in fg_events[:20]:
            print(
                "    - "
                f"t+{ev['ts']*1000.0:.1f}ms hwnd=0x{ev['hwnd']:x} pid={ev['pid']} "
                f"class='{ev['class']}' title='{ev['title']}'"
            )
        if len(fg_events) > 20:
            print(f"    - ... {len(fg_events) - 20} more")
    else:
        print(f"  [winprobe v{variant}] no foreground changes observed")


def _noop(*_args: Any, **_kwargs: Any) -> None:
    return None


_SETTINGS_DIALOG_PROFILE_PATCHES: Dict[str, Dict[str, Callable[..., Any]]] = {
    "full": {},
    "shell_only": {
        "_load_theme": _noop,
        "_setup_ui": _noop,
        "_apply_circle_checkbox_style": _noop,
        "_connect_signals": _noop,
        "_restore_geometry": _noop,
        "_restore_last_tab_selection": _noop,
    },
    "no_theme": {
        "_load_theme": _noop,
    },
    "no_post_init": {
        "_apply_circle_checkbox_style": _noop,
        "_connect_signals": _noop,
        "_restore_geometry": _noop,
        "_restore_last_tab_selection": _noop,
    },
    "no_setup_window": {
        "_setup_window": _noop,
    },
    "no_tab_hydration": {
        "_hydrate_remaining_tabs_async": _noop,
    },
    "no_tab_styling": {
        "_style_tab_widget": _noop,
    },
    "no_font_apply": {
        "_apply_application_font": _noop,
    },
}


def _hydrate_only_tab(tab_key: str) -> Callable[..., None]:
    """Patch helper: hydrate exactly one background tab for binary-search runs."""

    def _hydrate(self) -> None:
        idx = self._tab_index_for_key(tab_key)
        if idx < 0:
            return
        if idx in self._built_tab_indices:
            return
        self._background_tab_queue = [idx]
        self._schedule_next_background_build()

    return _hydrate


def _hydrate_only_tab_stub_builder(tab_key: str) -> Callable[..., None]:
    """Patch helper: hydrate one tab, but use a trivial QWidget builder."""

    def _hydrate(self) -> None:
        from PySide6.QtWidgets import QWidget

        idx = self._tab_index_for_key(tab_key)
        if idx < 0:
            return
        self._tab_builders[tab_key] = lambda: QWidget()
        self._background_tab_queue = [idx]
        self._schedule_next_background_build()

    return _hydrate


def _build_patched_widgets_tab(mode: str, settings_manager: Any, widget_defaults: Any) -> QWidget:
    """Build WidgetsTab with selective constructor patching for isolation."""
    from ui.tabs import widgets_tab as widgets_tab_mod

    cls = widgets_tab_mod.WidgetsTab
    patches: Dict[str, Callable[..., Any]] = {}
    class_patches: list[tuple[type, str, Callable[..., Any]]] = []
    function_patches: list[tuple[Any, str, Callable[..., Any]]] = []
    if mode == "shell_only":
        patches = {"_setup_ui": _noop, "_load_settings": _noop}
    elif mode == "setup_ui_only":
        patches = {"_load_settings": _noop}
    elif mode == "unstyled_combos":
        from PySide6.QtWidgets import QComboBox, QFontComboBox
        from ui.widgets import styled_combo_box as scb_mod
        from ui.widgets import styled_font_combo_box as sfcb_mod

        def _combo_init(
            self,
            parent: Any = None,
            *,
            popup_stylesheet: Any = None,
            size_variant: str = "regular",
        ) -> None:
            del popup_stylesheet, size_variant
            QComboBox.__init__(self, parent)

        def _font_combo_init(
            self,
            parent: Any = None,
            *,
            popup_stylesheet: Any = None,
            size_variant: str = "regular",
        ) -> None:
            del popup_stylesheet, size_variant
            QFontComboBox.__init__(self, parent)

        class_patches = [
            (scb_mod.StyledComboBox, "__init__", _combo_init),
            (sfcb_mod.StyledFontComboBox, "__init__", _font_combo_init),
        ]
    elif mode in {
        "setup_ui_only_no_clock",
        "setup_ui_only_no_weather",
        "setup_ui_only_no_media",
        "setup_ui_only_no_visualizers",
        "setup_ui_only_no_reddit",
        "setup_ui_only_no_defaults",
        "setup_ui_only_defaults_only",
        "setup_ui_only_clock_only",
        "setup_ui_only_weather_only",
        "setup_ui_only_media_only",
        "setup_ui_only_visualizers_only",
        "setup_ui_only_reddit_only",
        "setup_ui_only_visualizers_only_no_tech",
        "setup_ui_only_visualizers_only_no_tech_unstyled",
        "setup_ui_only_visualizers_only_scaffold_stub",
        "setup_ui_only_visualizers_only_no_tech_stub_preset",
    }:
        from PySide6.QtWidgets import QWidget
        from ui.tabs import widgets_tab_clock as clock_mod
        from ui.tabs import widgets_tab_weather as weather_mod
        from ui.tabs import widgets_tab_media as media_mod
        from ui.tabs import widgets_tab_reddit as reddit_mod
        from ui.tabs.media import builder_scaffold as scaffold_mod

        patches = {"_load_settings": _noop}
        keep_visualizers = mode in {
            "setup_ui_only_visualizers_only",
            "setup_ui_only_visualizers_only_no_tech",
            "setup_ui_only_visualizers_only_no_tech_unstyled",
            "setup_ui_only_visualizers_only_scaffold_stub",
            "setup_ui_only_visualizers_only_no_tech_stub_preset",
        }
        if mode == "setup_ui_only_no_clock":
            function_patches.append((clock_mod, "build_clock_ui", lambda tab, layout: QWidget()))
        elif mode == "setup_ui_only_no_weather":
            function_patches.append((weather_mod, "build_weather_ui", lambda tab, layout: QWidget()))
        elif mode == "setup_ui_only_no_media":
            function_patches.append((media_mod, "build_media_ui", lambda tab, layout: QWidget()))
        elif mode == "setup_ui_only_no_visualizers":
            function_patches.append((media_mod, "build_visualizers_ui", lambda tab, layout: QWidget()))
        elif mode == "setup_ui_only_no_reddit":
            function_patches.append((reddit_mod, "build_reddit_ui", lambda tab, layout: QWidget()))
        elif mode == "setup_ui_only_no_defaults":
            patches["_build_defaults_section"] = lambda self: QWidget()
        elif mode in {"setup_ui_only_visualizers_only_no_tech", "setup_ui_only_visualizers_only_no_tech_unstyled"}:
            function_patches.append((clock_mod, "build_clock_ui", lambda tab, layout: QWidget()))
            function_patches.append((weather_mod, "build_weather_ui", lambda tab, layout: QWidget()))
            function_patches.append((media_mod, "build_media_ui", lambda tab, layout: QWidget()))
            function_patches.append((reddit_mod, "build_reddit_ui", lambda tab, layout: QWidget()))
            patches["_build_defaults_section"] = lambda self: QWidget()
            function_patches.append(
                (scaffold_mod, "build_per_mode_technical_group", lambda tab, layout, mode_key: QWidget())
            )
            if mode == "setup_ui_only_visualizers_only_no_tech_unstyled":
                from PySide6.QtWidgets import QComboBox, QFontComboBox
                from ui.widgets import styled_combo_box as scb_mod
                from ui.widgets import styled_font_combo_box as sfcb_mod

                def _combo_init(
                    self,
                    parent: Any = None,
                    *,
                    popup_stylesheet: Any = None,
                    size_variant: str = "regular",
                ) -> None:
                    del popup_stylesheet, size_variant
                    QComboBox.__init__(self, parent)

                def _font_combo_init(
                    self,
                    parent: Any = None,
                    *,
                    popup_stylesheet: Any = None,
                    size_variant: str = "regular",
                ) -> None:
                    del popup_stylesheet, size_variant
                    QFontComboBox.__init__(self, parent)

                class_patches.extend(
                    [
                        (scb_mod.StyledComboBox, "__init__", _combo_init),
                        (sfcb_mod.StyledFontComboBox, "__init__", _font_combo_init),
                    ]
                )
        elif mode == "setup_ui_only_visualizers_only_no_tech_stub_preset":
            from ui.tabs.media import preset_slider as preset_slider_mod
            function_patches.append((clock_mod, "build_clock_ui", lambda tab, layout: QWidget()))
            function_patches.append((weather_mod, "build_weather_ui", lambda tab, layout: QWidget()))
            function_patches.append((media_mod, "build_media_ui", lambda tab, layout: QWidget()))
            function_patches.append((reddit_mod, "build_reddit_ui", lambda tab, layout: QWidget()))
            patches["_build_defaults_section"] = lambda self: QWidget()
            function_patches.append(
                (scaffold_mod, "build_per_mode_technical_group", lambda tab, layout, mode_key: QWidget())
            )

            class _DummySignal:
                def connect(self, *_args: Any, **_kwargs: Any) -> None:
                    return None

            class _DummyPresetSlider(QWidget):
                def __init__(self, _mode: str, parent: Any = None) -> None:
                    super().__init__(parent)
                    self.preset_changed = _DummySignal()
                    self.advanced_toggled = _DummySignal()

                def set_advanced_container(self, _container: Any) -> None:
                    return None

                def set_technical_container(self, _container: Any) -> None:
                    return None

                def set_preset_index(self, _index: int) -> None:
                    return None

                def preset_index(self) -> int:
                    return 0

            class_patches.append((preset_slider_mod.VisualizerPresetSlider, "__init__", _DummyPresetSlider.__init__))
            class_patches.append((preset_slider_mod.VisualizerPresetSlider, "set_advanced_container", _DummyPresetSlider.set_advanced_container))
            class_patches.append((preset_slider_mod.VisualizerPresetSlider, "set_technical_container", _DummyPresetSlider.set_technical_container))
            class_patches.append((preset_slider_mod.VisualizerPresetSlider, "set_preset_index", _DummyPresetSlider.set_preset_index))
            class_patches.append((preset_slider_mod.VisualizerPresetSlider, "preset_index", _DummyPresetSlider.preset_index))
        elif mode == "setup_ui_only_visualizers_only_scaffold_stub":
            function_patches.append((clock_mod, "build_clock_ui", lambda tab, layout: QWidget()))
            function_patches.append((weather_mod, "build_weather_ui", lambda tab, layout: QWidget()))
            function_patches.append((media_mod, "build_media_ui", lambda tab, layout: QWidget()))
            function_patches.append((reddit_mod, "build_reddit_ui", lambda tab, layout: QWidget()))
            patches["_build_defaults_section"] = lambda self: QWidget()
            patches["_update_vis_mode_sections"] = _noop

            class _DummySignal:
                def connect(self, *_args: Any, **_kwargs: Any) -> None:
                    return None

            class _DummyPreset:
                def __init__(self) -> None:
                    self.preset_changed = _DummySignal()
                    self.advanced_toggled = _DummySignal()

                def set_advanced_container(self, _container: Any) -> None:
                    return None

                def set_technical_container(self, _container: Any) -> None:
                    return None

                def set_preset_index(self, _index: int) -> None:
                    return None

                def preset_index(self) -> int:
                    return 0

            def _stub_build_mode_scaffold(
                tab_obj: Any,
                parent_layout: Any,
                *,
                mode_key: str,
                settings_container_attr: str,
                preset_slider_attr: str,
                normal_attr: str,
                advanced_host_attr: str,
                advanced_toggle_attr: str,
                advanced_helper_attr: str,
                advanced_attr: str,
            ) -> Any:
                from PySide6.QtWidgets import QVBoxLayout, QWidget

                container = QWidget()
                container_layout = QVBoxLayout(container)
                container_layout.setContentsMargins(0, 0, 0, 0)
                container_layout.setSpacing(12)
                setattr(tab_obj, settings_container_attr, container)

                preset_slider = _DummyPreset()
                setattr(tab_obj, preset_slider_attr, preset_slider)

                normal_widget = QWidget()
                normal_layout = QVBoxLayout(normal_widget)
                normal_layout.setContentsMargins(0, 0, 0, 0)
                normal_layout.setSpacing(12)
                setattr(tab_obj, normal_attr, normal_widget)
                container_layout.addWidget(normal_widget)

                advanced_host = QWidget()
                advanced_host_layout = QVBoxLayout(advanced_host)
                advanced_host_layout.setContentsMargins(0, 0, 0, 0)
                advanced_host_layout.setSpacing(12)
                setattr(tab_obj, advanced_host_attr, advanced_host)
                container_layout.addWidget(advanced_host)

                advanced_widget = QWidget()
                advanced_layout = QVBoxLayout(advanced_widget)
                advanced_layout.setContentsMargins(0, 0, 0, 0)
                advanced_layout.setSpacing(12)
                setattr(tab_obj, advanced_attr, advanced_widget)
                advanced_host_layout.addWidget(advanced_widget)

                setattr(tab_obj, advanced_toggle_attr, QWidget())
                setattr(tab_obj, advanced_helper_attr, QWidget())

                technical_host = QWidget()
                parent_layout.addWidget(container)

                return scaffold_mod.ModeScaffold(
                    container=container,
                    layout=container_layout,
                    preset_slider=preset_slider,
                    normal_widget=normal_widget,
                    normal_layout=normal_layout,
                    advanced_host=advanced_host,
                    advanced_layout=advanced_layout,
                    technical_host=technical_host,
                )

            function_patches.append((scaffold_mod, "build_mode_scaffold", _stub_build_mode_scaffold))
        else:
            # "only one section active" modes:
            # start from stubbing everything, then un-stub the chosen section.
            keep_clock = mode == "setup_ui_only_clock_only"
            keep_weather = mode == "setup_ui_only_weather_only"
            keep_media = mode == "setup_ui_only_media_only"
            keep_visualizers = keep_visualizers
            keep_reddit = mode == "setup_ui_only_reddit_only"
            keep_defaults = mode == "setup_ui_only_defaults_only"

            if not keep_clock:
                function_patches.append((clock_mod, "build_clock_ui", lambda tab, layout: QWidget()))
            if not keep_weather:
                function_patches.append((weather_mod, "build_weather_ui", lambda tab, layout: QWidget()))
            if not keep_media:
                function_patches.append((media_mod, "build_media_ui", lambda tab, layout: QWidget()))
            if not keep_visualizers:
                function_patches.append((media_mod, "build_visualizers_ui", lambda tab, layout: QWidget()))
            if not keep_reddit:
                function_patches.append((reddit_mod, "build_reddit_ui", lambda tab, layout: QWidget()))
            if not keep_defaults:
                patches["_build_defaults_section"] = lambda self: QWidget()
    else:
        raise ValueError(f"Unknown patched WidgetsTab mode: {mode}")

    originals: Dict[str, Callable[..., Any]] = {}
    class_originals: list[tuple[type, str, Callable[..., Any]]] = []
    function_originals: list[tuple[Any, str, Callable[..., Any]]] = []
    try:
        for method_name, replacement in patches.items():
            originals[method_name] = getattr(cls, method_name)
            setattr(cls, method_name, replacement)
        for target_mod, func_name, replacement in function_patches:
            original = getattr(target_mod, func_name)
            function_originals.append((target_mod, func_name, original))
            setattr(target_mod, func_name, replacement)
        for target_cls, method_name, replacement in class_patches:
            original = getattr(target_cls, method_name)
            class_originals.append((target_cls, method_name, original))
            setattr(target_cls, method_name, replacement)
        tab = cls(settings_manager, widget_defaults=widget_defaults)
    finally:
        for target_mod, func_name, original in function_originals:
            setattr(target_mod, func_name, original)
        for target_cls, method_name, original in class_originals:
            setattr(target_cls, method_name, original)
        for method_name, original in originals.items():
            setattr(cls, method_name, original)
    return tab


def _hydrate_widgets_with_patched_builder(mode: str) -> Callable[..., None]:
    """Patch helper: hydrate only widgets tab with a patched real WidgetsTab."""

    def _hydrate(self) -> None:
        from ui.settings_dialog_cache import get_settings_dialog_cache

        cache = get_settings_dialog_cache()
        self._tab_builders["widgets"] = lambda: _build_patched_widgets_tab(
            mode,
            self._settings,
            cache.widget_defaults,
        )
        idx = self._tab_index_for_key("widgets")
        if idx < 0:
            return
        self._background_tab_queue = [idx]
        self._schedule_next_background_build()

    return _hydrate


def _force_initial_tab(index: int) -> Callable[..., None]:
    """Patch helper: force a specific initial SettingsDialog tab index."""

    def _set_initial_tab(self) -> None:
        self._initial_tab_index = int(index)

    return _set_initial_tab


def _hydrate_without_widgets() -> Callable[..., None]:
    """Patch helper: hydrate every lazy tab except Widgets."""

    def _hydrate(self) -> None:
        remaining = [
            i
            for i in range(len(self._tab_keys))
            if i not in self._built_tab_indices and self._tab_key_for_index(i) != "widgets"
        ]
        if not remaining:
            return
        self._background_tab_queue.extend(remaining)
        self._schedule_next_background_build()

    return _hydrate


_SETTINGS_DIALOG_PROFILE_PATCHES.update(
    {
        "hydrate_display_only": {"_hydrate_remaining_tabs_async": _hydrate_only_tab("display")},
        "hydrate_transitions_only": {"_hydrate_remaining_tabs_async": _hydrate_only_tab("transitions")},
        "hydrate_widgets_only": {
            "_determine_initial_tab": _force_initial_tab(0),
            "_restore_last_tab_selection": _noop,
            "_hydrate_remaining_tabs_async": _hydrate_only_tab("widgets"),
        },
        "hydrate_accessibility_only": {"_hydrate_remaining_tabs_async": _hydrate_only_tab("accessibility")},
        "hydrate_about_only": {"_hydrate_remaining_tabs_async": _hydrate_only_tab("about")},
        "hydrate_widgets_only_no_tab_styling": {
            "_determine_initial_tab": _force_initial_tab(0),
            "_restore_last_tab_selection": _noop,
            "_hydrate_remaining_tabs_async": _hydrate_only_tab("widgets"),
            "_style_tab_widget": _noop,
        },
        "hydrate_widgets_only_stub": {
            "_determine_initial_tab": _force_initial_tab(0),
            "_restore_last_tab_selection": _noop,
            "_hydrate_remaining_tabs_async": _hydrate_only_tab_stub_builder("widgets"),
        },
        "hydrate_widgets_patched_shell_only": {
            "_determine_initial_tab": _force_initial_tab(0),
            "_restore_last_tab_selection": _noop,
            "_hydrate_remaining_tabs_async": _hydrate_widgets_with_patched_builder("shell_only"),
        },
        "hydrate_widgets_patched_setup_ui_only": {
            "_determine_initial_tab": _force_initial_tab(0),
            "_restore_last_tab_selection": _noop,
            "_hydrate_remaining_tabs_async": _hydrate_widgets_with_patched_builder("setup_ui_only"),
        },
        "hydrate_widgets_patched_unstyled_combos": {
            "_determine_initial_tab": _force_initial_tab(0),
            "_restore_last_tab_selection": _noop,
            "_hydrate_remaining_tabs_async": _hydrate_widgets_with_patched_builder("unstyled_combos"),
        },
        "hydrate_widgets_patched_setup_no_clock": {
            "_determine_initial_tab": _force_initial_tab(0),
            "_restore_last_tab_selection": _noop,
            "_hydrate_remaining_tabs_async": _hydrate_widgets_with_patched_builder("setup_ui_only_no_clock"),
        },
        "hydrate_widgets_patched_setup_no_weather": {
            "_determine_initial_tab": _force_initial_tab(0),
            "_restore_last_tab_selection": _noop,
            "_hydrate_remaining_tabs_async": _hydrate_widgets_with_patched_builder("setup_ui_only_no_weather"),
        },
        "hydrate_widgets_patched_setup_no_media": {
            "_determine_initial_tab": _force_initial_tab(0),
            "_restore_last_tab_selection": _noop,
            "_hydrate_remaining_tabs_async": _hydrate_widgets_with_patched_builder("setup_ui_only_no_media"),
        },
        "hydrate_widgets_patched_setup_no_visualizers": {
            "_determine_initial_tab": _force_initial_tab(0),
            "_restore_last_tab_selection": _noop,
            "_hydrate_remaining_tabs_async": _hydrate_widgets_with_patched_builder("setup_ui_only_no_visualizers"),
        },
        "hydrate_widgets_patched_setup_no_reddit": {
            "_determine_initial_tab": _force_initial_tab(0),
            "_restore_last_tab_selection": _noop,
            "_hydrate_remaining_tabs_async": _hydrate_widgets_with_patched_builder("setup_ui_only_no_reddit"),
        },
        "hydrate_widgets_patched_setup_no_defaults": {
            "_determine_initial_tab": _force_initial_tab(0),
            "_restore_last_tab_selection": _noop,
            "_hydrate_remaining_tabs_async": _hydrate_widgets_with_patched_builder("setup_ui_only_no_defaults"),
        },
        "hydrate_widgets_patched_setup_defaults_only": {
            "_determine_initial_tab": _force_initial_tab(0),
            "_restore_last_tab_selection": _noop,
            "_hydrate_remaining_tabs_async": _hydrate_widgets_with_patched_builder("setup_ui_only_defaults_only"),
        },
        "hydrate_widgets_patched_setup_clock_only": {
            "_determine_initial_tab": _force_initial_tab(0),
            "_restore_last_tab_selection": _noop,
            "_hydrate_remaining_tabs_async": _hydrate_widgets_with_patched_builder("setup_ui_only_clock_only"),
        },
        "hydrate_widgets_patched_setup_weather_only": {
            "_determine_initial_tab": _force_initial_tab(0),
            "_restore_last_tab_selection": _noop,
            "_hydrate_remaining_tabs_async": _hydrate_widgets_with_patched_builder("setup_ui_only_weather_only"),
        },
        "hydrate_widgets_patched_setup_media_only": {
            "_determine_initial_tab": _force_initial_tab(0),
            "_restore_last_tab_selection": _noop,
            "_hydrate_remaining_tabs_async": _hydrate_widgets_with_patched_builder("setup_ui_only_media_only"),
        },
        "hydrate_widgets_patched_setup_visualizers_only": {
            "_determine_initial_tab": _force_initial_tab(0),
            "_restore_last_tab_selection": _noop,
            "_hydrate_remaining_tabs_async": _hydrate_widgets_with_patched_builder("setup_ui_only_visualizers_only"),
        },
        "hydrate_widgets_patched_setup_reddit_only": {
            "_determine_initial_tab": _force_initial_tab(0),
            "_restore_last_tab_selection": _noop,
            "_hydrate_remaining_tabs_async": _hydrate_widgets_with_patched_builder("setup_ui_only_reddit_only"),
        },
        "hydrate_widgets_patched_setup_visualizers_only_no_tech": {
            "_determine_initial_tab": _force_initial_tab(0),
            "_restore_last_tab_selection": _noop,
            "_hydrate_remaining_tabs_async": _hydrate_widgets_with_patched_builder("setup_ui_only_visualizers_only_no_tech"),
        },
        "hydrate_widgets_patched_setup_visualizers_only_no_tech_unstyled": {
            "_determine_initial_tab": _force_initial_tab(0),
            "_restore_last_tab_selection": _noop,
            "_hydrate_remaining_tabs_async": _hydrate_widgets_with_patched_builder("setup_ui_only_visualizers_only_no_tech_unstyled"),
        },
        "hydrate_widgets_patched_setup_visualizers_only_scaffold_stub": {
            "_determine_initial_tab": _force_initial_tab(0),
            "_restore_last_tab_selection": _noop,
            "_hydrate_remaining_tabs_async": _hydrate_widgets_with_patched_builder("setup_ui_only_visualizers_only_scaffold_stub"),
        },
        "hydrate_widgets_patched_setup_visualizers_only_no_tech_stub_preset": {
            "_determine_initial_tab": _force_initial_tab(0),
            "_restore_last_tab_selection": _noop,
            "_hydrate_remaining_tabs_async": _hydrate_widgets_with_patched_builder("setup_ui_only_visualizers_only_no_tech_stub_preset"),
        },
        "force_widgets_initial_no_hydration": {
            "_determine_initial_tab": _force_initial_tab(3),
            "_hydrate_remaining_tabs_async": _noop,
            "_restore_last_tab_selection": _noop,
        },
        "force_sources_initial_no_hydration": {
            "_determine_initial_tab": _force_initial_tab(0),
            "_hydrate_remaining_tabs_async": _noop,
            "_restore_last_tab_selection": _noop,
        },
        "force_sources_hydrate_without_widgets": {
            "_determine_initial_tab": _force_initial_tab(0),
            "_hydrate_remaining_tabs_async": _hydrate_without_widgets(),
            "_restore_last_tab_selection": _noop,
        },
    }
)


def _build_settings_dialog(profile: str = "full") -> QDialog:
    """Build a real SettingsDialog, optionally patching constructor phases."""
    from core.settings.settings_manager import SettingsManager
    from core.animation import AnimationManager
    from ui import settings_dialog as settings_dialog_mod

    patches = _SETTINGS_DIALOG_PROFILE_PATCHES.get(profile)
    if patches is None:
        raise ValueError(f"Unknown SettingsDialog profile: {profile}")

    settings = SettingsManager()
    animations = AnimationManager()
    dialog_cls = settings_dialog_mod.SettingsDialog

    originals: Dict[str, Callable[..., Any]] = {}
    try:
        for method_name, replacement in patches.items():
            if not hasattr(dialog_cls, method_name):
                raise AttributeError(f"SettingsDialog has no method '{method_name}'")
            originals[method_name] = getattr(dialog_cls, method_name)
            setattr(dialog_cls, method_name, replacement)
        dialog = dialog_cls(settings, animations)
    finally:
        for method_name, original in originals.items():
            setattr(dialog_cls, method_name, original)

    dialog.setWindowTitle(f"{dialog.windowTitle()} [profile={profile}]")
    return dialog


def _configure_local_appdata_for_harness() -> Path:
    """Force APPDATA to a local writable path for deterministic harness runs."""
    local_appdata = Path(_PROJECT_ROOT) / "tests_tmp_appdata" / "flicker_test_appdata"
    local_appdata.mkdir(parents=True, exist_ok=True)
    os.environ["APPDATA"] = str(local_appdata)
    try:
        from core.settings import storage_paths as storage_paths_mod
        storage_paths_mod.reset_module_cache()
    except Exception:
        pass
    return local_appdata


def _dump_top_levels(app: QApplication, label: str) -> None:
    widgets = list(app.topLevelWidgets())
    print(f"  [{label}] top-level widgets: {len(widgets)}")
    grouped: Dict[str, int] = {}
    highlighted = []
    for widget in widgets:
        try:
            flags_raw = int(widget.windowFlags())
            title = widget.windowTitle()
            cls = widget.__class__.__name__
            visible = widget.isVisible()
            key = f"{cls} flags=0x{flags_raw:x}"
            grouped[key] = grouped.get(key, 0) + 1
            if visible or title:
                highlighted.append((cls, visible, flags_raw, title))
        except Exception:
            key = "<uninspectable>"
            grouped[key] = grouped.get(key, 0) + 1

    for key, count in sorted(grouped.items(), key=lambda kv: (-kv[1], kv[0])):
        print(f"    - {key}: {count}")
    if highlighted:
        print("    highlighted (visible/title):")
        for cls, visible, flags_raw, title in highlighted[:12]:
            print(f"      * {cls} visible={visible} flags=0x{flags_raw:x} title='{title}'")
        if len(highlighted) > 12:
            print(f"      * ... and {len(highlighted) - 12} more")


def _pump_events(app: QApplication, duration_ms: int = 1200) -> None:
    """Process events for a short period to mimic real --s startup work."""
    deadline = time.perf_counter() + (duration_ms / 1000.0)
    while time.perf_counter() < deadline:
        app.processEvents()
        # Ensure deleteLater() queues are drained between variants.
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        time.sleep(0.01)


def _observe_then_autoclose(app: QApplication, seconds: float, *, variant: int) -> None:
    """Keep the window alive long enough for visual observation, then return."""
    if WINPROBE_ENABLED and not EXTERNAL_WINPROBE_ENABLED:
        _observe_with_winprobe(app, seconds, variant=variant)
        return
    duration_ms = max(0, int(seconds * 1000))
    _pump_events(app, duration_ms)


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
        return _build_settings_dialog("full")
    elif variant == 54:
        from ui.tabs.media.preset_slider import VisualizerPresetSlider

        lay = QVBoxLayout(d)
        lay.setContentsMargins(20, 20, 20, 20)
        lay.setSpacing(12)
        lay.addWidget(QLabel("V54: plain dialog + six VisualizerPresetSlider instances"))
        for mode_id in ("spectrum", "oscilloscope", "blob", "sine_wave", "bubble", "devcurve"):
            lay.addWidget(VisualizerPresetSlider(mode_id))
        return d
    elif variant in {55, 56, 57, 58, 59, 60, 61, 62, 63, 64, 65, 66, 67, 68, 69, 70}:
        from PySide6.QtWidgets import QSlider
        from ui.tabs.media import preset_slider as preset_slider_mod

        VisualizerPresetSlider = preset_slider_mod.VisualizerPresetSlider
        original_build_ui = VisualizerPresetSlider._build_ui
        original_no_wheel = getattr(preset_slider_mod, "NoWheelSlider", None)
        original_notch = preset_slider_mod._PresetNotchBar

        class _NotchStub(QWidget):
            def __init__(self, _notch_count: int, parent: QWidget | None = None) -> None:
                super().__init__(parent)
                self.setFixedHeight(10)

            def set_notch_count(self, _count: int) -> None:
                return None

        def _build_ui_data_only(self) -> None:
            root = QVBoxLayout(self)
            root.setContentsMargins(0, 0, 0, 0)
            root.setSpacing(0)
            root.addWidget(QLabel("data-only slider shell"))

        def _build_ui_labels_buttons_only(self) -> None:
            from ui.tabs.shared_styles import add_section_label, apply_section_heading_style, FORM_LABEL_HEIGHT
            from PySide6.QtCore import Qt
            from PySide6.QtWidgets import QHBoxLayout, QPushButton

            layout = QVBoxLayout(self)
            layout.setContentsMargins(0, 2, 0, 2)
            layout.setSpacing(2)
            row = QHBoxLayout()
            row.setSpacing(6)
            row.setContentsMargins(0, 0, 0, 0)
            row.setAlignment(Qt.AlignmentFlag.AlignVCenter)
            add_section_label(row, "Preset:", 48)
            self._value_label = QLabel(self._preset_names[0] if self._preset_names else "Preset")
            self._value_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            self._value_label.setMinimumWidth(140)
            apply_section_heading_style(self._value_label)
            self._value_label.setMinimumHeight(FORM_LABEL_HEIGHT)
            row.addWidget(self._value_label, 1)
            self._edit_btn = QPushButton("Edit Preset")
            self._custom_action_btn = QPushButton("Move To Custom")
            row.addWidget(self._edit_btn)
            row.addWidget(self._custom_action_btn)
            layout.addLayout(row)

        def _build_ui_slider_only(self) -> None:
            from PySide6.QtCore import Qt
            from PySide6.QtWidgets import QHBoxLayout

            layout = QVBoxLayout(self)
            layout.setContentsMargins(0, 2, 0, 2)
            layout.setSpacing(2)
            row = QHBoxLayout()
            row.setContentsMargins(0, 0, 0, 0)
            row.setSpacing(6)
            self._slider = QSlider(Qt.Orientation.Horizontal)
            self._slider.setMinimum(0)
            self._slider.setMaximum(max(0, self._preset_count - 1))
            self._slider.setValue(0)
            row.addWidget(self._slider, 1)
            layout.addLayout(row)

        def _build_ui_buttons_only(self) -> None:
            from PySide6.QtWidgets import QHBoxLayout, QPushButton

            layout = QVBoxLayout(self)
            layout.setContentsMargins(0, 2, 0, 2)
            layout.setSpacing(2)
            row = QHBoxLayout()
            row.setContentsMargins(0, 0, 0, 0)
            row.setSpacing(6)
            self._edit_btn = QPushButton("Edit Preset")
            self._custom_action_btn = QPushButton("Move To Custom")
            row.addWidget(self._edit_btn)
            row.addWidget(self._custom_action_btn)
            layout.addLayout(row)

        def _build_ui_slider_only_original_settings(self) -> None:
            from PySide6.QtCore import Qt
            from PySide6.QtWidgets import QHBoxLayout, QSlider
            from ui.tabs.shared_styles import FORM_LABEL_HEIGHT

            layout = QVBoxLayout(self)
            layout.setContentsMargins(0, 2, 0, 2)
            layout.setSpacing(2)
            row = QHBoxLayout()
            row.setContentsMargins(0, 0, 0, 0)
            row.setSpacing(6)
            self._slider = QSlider(Qt.Orientation.Horizontal)
            self._slider.setObjectName("presetModeSlider")
            self._slider.setMinimum(0)
            self._slider.setMaximum(max(0, self._preset_count - 1))
            self._slider.setValue(0)
            self._slider.setTickPosition(QSlider.TickPosition.TicksBelow)
            self._slider.setTickInterval(1)
            self._slider.setPageStep(1)
            self._slider.setSingleStep(1)
            self._slider.setMinimumHeight(FORM_LABEL_HEIGHT)
            self._slider.setToolTip("Choose a visualizer preset. Custom (rightmost) shows all settings.")
            row.addWidget(self._slider, 1)
            layout.addLayout(row)

        def _build_ui_buttons_only_original_settings(self) -> None:
            from PySide6.QtWidgets import QHBoxLayout, QPushButton

            layout = QVBoxLayout(self)
            layout.setContentsMargins(0, 2, 0, 2)
            layout.setSpacing(2)
            row = QHBoxLayout()
            row.setContentsMargins(0, 0, 0, 0)
            row.setSpacing(6)
            self._edit_btn = QPushButton("Edit Preset")
            self._edit_btn.setToolTip("Open this preset's JSON file in your default editor.")
            self._edit_btn.setFixedHeight(22)
            self._edit_btn.setFixedWidth(90)
            self._edit_btn.setStyleSheet("QPushButton { font-size: 9pt; padding: 2px 8px; }")
            self._edit_btn.clicked.connect(lambda: None)
            row.addWidget(self._edit_btn)
            self._custom_action_btn = QPushButton("Move To Custom")
            self._custom_action_btn.setFixedHeight(22)
            self._custom_action_btn.setFixedWidth(130)
            self._custom_action_btn.setStyleSheet("QPushButton { font-size: 9pt; padding: 2px 8px; }")
            self._custom_action_btn.clicked.connect(lambda: None)
            row.addWidget(self._custom_action_btn)
            layout.addLayout(row)

        def _build_ui_full_static(
            self,
            *,
            with_notch: bool,
            connect_original_slots: bool = False,
            connect_lambda_slots: bool = False,
            use_real_notch: bool = False,
        ) -> None:
            from ui.tabs.shared_styles import add_section_label, apply_section_heading_style, FORM_LABEL_HEIGHT
            from PySide6.QtCore import Qt
            from PySide6.QtWidgets import QHBoxLayout, QSlider, QPushButton

            layout = QVBoxLayout(self)
            layout.setContentsMargins(0, 2, 0, 2)
            layout.setSpacing(2)

            row = QHBoxLayout()
            row.setSpacing(6)
            row.setContentsMargins(0, 0, 0, 0)
            row.setAlignment(Qt.AlignmentFlag.AlignVCenter)
            add_section_label(row, "Preset:", 48)

            self._value_label = QLabel(self._preset_names[0] if self._preset_names else "Preset 1")
            self._value_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            self._value_label.setMinimumWidth(140)
            apply_section_heading_style(self._value_label)
            self._value_label.setMinimumHeight(FORM_LABEL_HEIGHT)
            row.addWidget(self._value_label)

            slider_column = QVBoxLayout()
            slider_column.setSpacing(2)
            slider_column.setContentsMargins(0, 3, 0, 0)
            self._slider = QSlider(Qt.Orientation.Horizontal)
            self._slider.setObjectName("presetModeSlider")
            self._slider.setMinimum(0)
            self._slider.setMaximum(max(0, self._preset_count - 1))
            self._slider.setValue(0)
            self._slider.setTickPosition(QSlider.TickPosition.TicksBelow)
            self._slider.setTickInterval(1)
            self._slider.setPageStep(1)
            self._slider.setSingleStep(1)
            self._slider.setMinimumHeight(FORM_LABEL_HEIGHT)
            self._slider.setToolTip("Choose a visualizer preset. Custom (rightmost) shows all settings.")
            slider_column.addWidget(self._slider)
            if with_notch:
                if use_real_notch:
                    self._notch_bar = original_notch(self._preset_count)
                else:
                    self._notch_bar = _NotchStub(self._preset_count)
                slider_column.addWidget(self._notch_bar)
            row.addLayout(slider_column, 1)

            self._edit_btn = QPushButton("Edit Preset")
            self._edit_btn.setToolTip("Open this preset's JSON file in your default editor.")
            self._edit_btn.setFixedHeight(22)
            self._edit_btn.setFixedWidth(90)
            self._edit_btn.setStyleSheet("QPushButton { font-size: 9pt; padding: 2px 8px; }")
            row.addWidget(self._edit_btn)

            self._custom_action_btn = QPushButton("Move To Custom")
            self._custom_action_btn.setFixedHeight(22)
            self._custom_action_btn.setFixedWidth(130)
            self._custom_action_btn.setStyleSheet("QPushButton { font-size: 9pt; padding: 2px 8px; }")
            row.addWidget(self._custom_action_btn)

            if connect_original_slots:
                self._slider.valueChanged.connect(self._on_slider_changed)
                self._edit_btn.clicked.connect(self._open_preset_json)
                self._custom_action_btn.clicked.connect(self._on_custom_action_clicked)
            elif connect_lambda_slots:
                self._slider.valueChanged.connect(lambda _value: None)
                self._edit_btn.clicked.connect(lambda: None)
                self._custom_action_btn.clicked.connect(lambda: None)
            layout.addLayout(row)

        try:
            if variant == 55:
                VisualizerPresetSlider._build_ui = _build_ui_data_only  # type: ignore[assignment]
            elif variant == 56:
                if original_no_wheel is not None:
                    preset_slider_mod.NoWheelSlider = QSlider
            elif variant == 57:
                if original_no_wheel is not None:
                    preset_slider_mod.NoWheelSlider = QSlider
                preset_slider_mod._PresetNotchBar = _NotchStub
            elif variant == 58:
                preset_slider_mod._PresetNotchBar = _NotchStub
            elif variant == 59:
                VisualizerPresetSlider._build_ui = _build_ui_labels_buttons_only  # type: ignore[assignment]
            elif variant == 60:
                VisualizerPresetSlider._build_ui = _build_ui_slider_only  # type: ignore[assignment]
            elif variant == 61:
                VisualizerPresetSlider._build_ui = _build_ui_buttons_only  # type: ignore[assignment]
            elif variant == 62:
                VisualizerPresetSlider._build_ui = _build_ui_slider_only_original_settings  # type: ignore[assignment]
            elif variant == 63:
                VisualizerPresetSlider._build_ui = _build_ui_buttons_only_original_settings  # type: ignore[assignment]
            elif variant == 64:
                VisualizerPresetSlider._build_ui = lambda self: _build_ui_full_static(self, with_notch=False)  # type: ignore[assignment]
            elif variant == 65:
                VisualizerPresetSlider._build_ui = lambda self: _build_ui_full_static(self, with_notch=True)  # type: ignore[assignment]
            elif variant == 66:
                VisualizerPresetSlider._build_ui = lambda self: _build_ui_full_static(  # type: ignore[assignment]
                    self,
                    with_notch=True,
                    connect_original_slots=True,
                )
            elif variant == 67:
                VisualizerPresetSlider._build_ui = lambda self: _build_ui_full_static(  # type: ignore[assignment]
                    self,
                    with_notch=True,
                    connect_lambda_slots=True,
                )
            elif variant == 68:
                VisualizerPresetSlider._build_ui = lambda self: _build_ui_full_static(  # type: ignore[assignment]
                    self,
                    with_notch=True,
                    connect_original_slots=True,
                    use_real_notch=True,
                )
            elif variant == 69:
                preset_slider_class = getattr(preset_slider_mod, "_PresetNoWheelSlider", QSlider)

                def _build_ui_full_static_nowheel(self) -> None:
                    from ui.tabs.shared_styles import add_section_label, apply_section_heading_style, FORM_LABEL_HEIGHT
                    from PySide6.QtCore import Qt
                    from PySide6.QtWidgets import QHBoxLayout, QPushButton, QVBoxLayout

                    layout = QVBoxLayout(self)
                    layout.setContentsMargins(0, 2, 0, 2)
                    layout.setSpacing(2)
                    row = QHBoxLayout()
                    row.setSpacing(6)
                    row.setContentsMargins(0, 0, 0, 0)
                    row.setAlignment(Qt.AlignmentFlag.AlignVCenter)
                    add_section_label(row, "Preset:", 48)
                    self._value_label = QLabel(self._preset_names[0] if self._preset_names else "Preset 1")
                    self._value_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                    self._value_label.setMinimumWidth(140)
                    apply_section_heading_style(self._value_label)
                    self._value_label.setMinimumHeight(FORM_LABEL_HEIGHT)
                    row.addWidget(self._value_label)
                    slider_column = QVBoxLayout()
                    slider_column.setSpacing(2)
                    slider_column.setContentsMargins(0, 3, 0, 0)
                    self._slider = preset_slider_class(Qt.Orientation.Horizontal)
                    self._slider.setObjectName("presetModeSlider")
                    self._slider.setMinimum(0)
                    self._slider.setMaximum(max(0, self._preset_count - 1))
                    self._slider.setValue(0)
                    self._slider.setTickPosition(QSlider.TickPosition.TicksBelow)
                    self._slider.setTickInterval(1)
                    self._slider.setPageStep(1)
                    self._slider.setSingleStep(1)
                    self._slider.setMinimumHeight(FORM_LABEL_HEIGHT)
                    self._slider.setToolTip("Choose a visualizer preset. Custom (rightmost) shows all settings.")
                    self._slider.valueChanged.connect(self._on_slider_changed)
                    slider_column.addWidget(self._slider)
                    self._notch_bar = original_notch(self._preset_count)
                    slider_column.addWidget(self._notch_bar)
                    row.addLayout(slider_column, 1)
                    self._edit_btn = QPushButton("Edit Preset")
                    self._edit_btn.setToolTip("Open this preset's JSON file in your default editor.")
                    self._edit_btn.setFixedHeight(22)
                    self._edit_btn.setFixedWidth(90)
                    self._edit_btn.setStyleSheet("QPushButton { font-size: 9pt; padding: 2px 8px; }")
                    self._edit_btn.clicked.connect(self._open_preset_json)
                    row.addWidget(self._edit_btn)
                    self._custom_action_btn = QPushButton("Move To Custom")
                    self._custom_action_btn.setFixedHeight(22)
                    self._custom_action_btn.setFixedWidth(130)
                    self._custom_action_btn.setStyleSheet("QPushButton { font-size: 9pt; padding: 2px 8px; }")
                    self._custom_action_btn.clicked.connect(self._on_custom_action_clicked)
                    row.addWidget(self._custom_action_btn)
                    layout.addLayout(row)

                VisualizerPresetSlider._build_ui = _build_ui_full_static_nowheel  # type: ignore[assignment]
            elif variant == 70:
                preset_slider_class = getattr(preset_slider_mod, "_PresetNoWheelSlider", QSlider)

                def _build_ui_full_static_nowheel_visible(self) -> None:
                    from ui.tabs.shared_styles import add_section_label, apply_section_heading_style, FORM_LABEL_HEIGHT
                    from PySide6.QtCore import Qt
                    from PySide6.QtWidgets import QHBoxLayout, QPushButton, QVBoxLayout

                    layout = QVBoxLayout(self)
                    layout.setContentsMargins(0, 2, 0, 2)
                    layout.setSpacing(2)
                    row = QHBoxLayout()
                    row.setSpacing(6)
                    row.setContentsMargins(0, 0, 0, 0)
                    row.setAlignment(Qt.AlignmentFlag.AlignVCenter)
                    add_section_label(row, "Preset:", 48)
                    self._value_label = QLabel(self._preset_names[0] if self._preset_names else "Preset 1")
                    self._value_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                    self._value_label.setMinimumWidth(140)
                    apply_section_heading_style(self._value_label)
                    self._value_label.setMinimumHeight(FORM_LABEL_HEIGHT)
                    row.addWidget(self._value_label)
                    slider_column = QVBoxLayout()
                    slider_column.setSpacing(2)
                    slider_column.setContentsMargins(0, 3, 0, 0)
                    self._slider = preset_slider_class(Qt.Orientation.Horizontal)
                    self._slider.setObjectName("presetModeSlider")
                    self._slider.setMinimum(0)
                    self._slider.setMaximum(max(0, self._preset_count - 1))
                    self._slider.setValue(0)
                    self._slider.setTickPosition(QSlider.TickPosition.TicksBelow)
                    self._slider.setTickInterval(1)
                    self._slider.setPageStep(1)
                    self._slider.setSingleStep(1)
                    self._slider.setMinimumHeight(FORM_LABEL_HEIGHT)
                    self._slider.setToolTip("Choose a visualizer preset. Custom (rightmost) shows all settings.")
                    self._slider.valueChanged.connect(self._on_slider_changed)
                    slider_column.addWidget(self._slider)
                    self._notch_bar = original_notch(self._preset_count)
                    slider_column.addWidget(self._notch_bar)
                    row.addLayout(slider_column, 1)
                    self._edit_btn = QPushButton("Edit Preset")
                    self._edit_btn.setToolTip("Open this preset's JSON file in your default editor.")
                    self._edit_btn.setFixedHeight(22)
                    self._edit_btn.setFixedWidth(90)
                    self._edit_btn.setStyleSheet("QPushButton { font-size: 9pt; padding: 2px 8px; }")
                    self._edit_btn.clicked.connect(self._open_preset_json)
                    self._edit_btn.setVisible(True)
                    row.addWidget(self._edit_btn)
                    self._custom_action_btn = QPushButton("Move To Custom")
                    self._custom_action_btn.setFixedHeight(22)
                    self._custom_action_btn.setFixedWidth(130)
                    self._custom_action_btn.setStyleSheet("QPushButton { font-size: 9pt; padding: 2px 8px; }")
                    self._custom_action_btn.clicked.connect(self._on_custom_action_clicked)
                    row.addWidget(self._custom_action_btn)
                    layout.addLayout(row)

                VisualizerPresetSlider._build_ui = _build_ui_full_static_nowheel_visible  # type: ignore[assignment]

            lay = QVBoxLayout(d)
            lay.setContentsMargins(20, 20, 20, 20)
            lay.setSpacing(12)
            lay.addWidget(QLabel(f"V{variant}: preset slider micro-isolation"))
            for mode_id in ("spectrum", "oscilloscope", "blob", "sine_wave", "bubble", "devcurve"):
                lay.addWidget(VisualizerPresetSlider(mode_id))
            return d
        finally:
            VisualizerPresetSlider._build_ui = original_build_ui  # type: ignore[assignment]
            if original_no_wheel is not None:
                preset_slider_mod.NoWheelSlider = original_no_wheel
            preset_slider_mod._PresetNotchBar = original_notch

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
    variants = [int(sys.argv[1])] if len(sys.argv) > 1 else range(1, 71)
    settings_dialog_variants = {13, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53}

    # Variants 14-17 reproduce the main.py pre-QApplication setup.
    main_setup_variants = {14, 15, 16, 17}
    need_main_setup = any(v in main_setup_variants for v in variants)
    if any(v in settings_dialog_variants for v in variants):
        harness_appdata = _configure_local_appdata_for_harness()
        print(f"  (flicker harness APPDATA forced to {harness_appdata})")
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
        if not SKIP_START_PROMPT:
            input(f"\n>>> Press Enter to show variant {v} ...")
        else:
            print(f"\n>>> Auto-running variant {v} ...")
        probe_proc, probe_out = _start_external_winprobe(v)
        _dump_top_levels(app, f"before construct v{v}")
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
            d = _build_settings_dialog("full")
        elif v == 18:
            d = _build_settings_dialog("shell_only")
        elif v == 19:
            d = _build_settings_dialog("no_theme")
        elif v == 20:
            d = _build_settings_dialog("no_post_init")
        elif v == 21:
            d = _build_settings_dialog("no_setup_window")
        elif v == 22:
            d = _build_settings_dialog("no_tab_hydration")
        elif v == 23:
            d = _build_settings_dialog("no_tab_styling")
        elif v == 24:
            d = _build_settings_dialog("no_font_apply")
        elif v == 25:
            d = _build_settings_dialog("hydrate_display_only")
        elif v == 26:
            d = _build_settings_dialog("hydrate_transitions_only")
        elif v == 27:
            d = _build_settings_dialog("hydrate_widgets_only")
        elif v == 28:
            d = _build_settings_dialog("hydrate_accessibility_only")
        elif v == 29:
            d = _build_settings_dialog("hydrate_about_only")
        elif v == 30:
            d = _build_settings_dialog("hydrate_widgets_only_no_tab_styling")
        elif v == 31:
            d = _build_settings_dialog("hydrate_widgets_only_stub")
        elif v == 32:
            d = _build_settings_dialog("hydrate_widgets_patched_shell_only")
        elif v == 33:
            d = _build_settings_dialog("hydrate_widgets_patched_setup_ui_only")
        elif v == 34:
            d = _build_settings_dialog("force_widgets_initial_no_hydration")
        elif v == 35:
            d = _build_settings_dialog("force_sources_initial_no_hydration")
        elif v == 36:
            d = _build_settings_dialog("force_sources_hydrate_without_widgets")
        elif v == 37:
            d = _build_settings_dialog("hydrate_widgets_patched_unstyled_combos")
        elif v == 38:
            d = _build_settings_dialog("hydrate_widgets_patched_setup_no_clock")
        elif v == 39:
            d = _build_settings_dialog("hydrate_widgets_patched_setup_no_weather")
        elif v == 40:
            d = _build_settings_dialog("hydrate_widgets_patched_setup_no_media")
        elif v == 41:
            d = _build_settings_dialog("hydrate_widgets_patched_setup_no_visualizers")
        elif v == 42:
            d = _build_settings_dialog("hydrate_widgets_patched_setup_no_reddit")
        elif v == 43:
            d = _build_settings_dialog("hydrate_widgets_patched_setup_no_defaults")
        elif v == 44:
            d = _build_settings_dialog("hydrate_widgets_patched_setup_defaults_only")
        elif v == 45:
            d = _build_settings_dialog("hydrate_widgets_patched_setup_clock_only")
        elif v == 46:
            d = _build_settings_dialog("hydrate_widgets_patched_setup_weather_only")
        elif v == 47:
            d = _build_settings_dialog("hydrate_widgets_patched_setup_media_only")
        elif v == 48:
            d = _build_settings_dialog("hydrate_widgets_patched_setup_visualizers_only")
        elif v == 49:
            d = _build_settings_dialog("hydrate_widgets_patched_setup_reddit_only")
        elif v == 50:
            d = _build_settings_dialog("hydrate_widgets_patched_setup_visualizers_only_no_tech")
        elif v == 51:
            d = _build_settings_dialog("hydrate_widgets_patched_setup_visualizers_only_no_tech_unstyled")
        elif v == 52:
            d = _build_settings_dialog("hydrate_widgets_patched_setup_visualizers_only_scaffold_stub")
        elif v == 53:
            d = _build_settings_dialog("hydrate_widgets_patched_setup_visualizers_only_no_tech_stub_preset")
        else:
            d = make_dialog(v)

        construct_ms = (time.perf_counter() - t0) * 1000
        print(f"  constructed in {construct_ms:.1f} ms")
        _dump_top_levels(app, f"after construct v{v}")
        t1 = time.perf_counter()
        d.show()
        _pump_events(app, 1200)
        show_ms = (time.perf_counter() - t1) * 1000
        print(f"  show() in {show_ms:.1f} ms")
        _dump_top_levels(app, f"after show/pump v{v}")
        print(f"  observing for {AUTO_CLOSE_SECONDS:.1f}s (auto-close)...")
        _observe_then_autoclose(app, AUTO_CLOSE_SECONDS, variant=v)
        d.close()
        d.deleteLater()
        _pump_events(app, 200)
        _finish_external_winprobe(probe_proc, probe_out, variant=v)

    print("\nDone -- compare which variants flickered.")


if __name__ == "__main__":
    main()
