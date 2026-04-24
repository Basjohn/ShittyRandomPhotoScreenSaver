"""Media/input matrix harness for MC/normal runtime key-routing investigations.

This harness is designed for the U-05 bug family:
- focused MC window loses media/normal key behavior after click,
- context-menu or external focus changes behavior,
- runtime variants diverge.

It automates:
1) optional isolated-profile launch (MC/normal),
2) deterministic focus-state transitions,
3) safe key probes (volume step + transition key),
4) evidence collection (foreground snapshots, volume deltas, log deltas),
5) JSON + Markdown report output.

Usage examples:
  python tools/media_key_matrix_harness.py --launch mc
  python tools/media_key_matrix_harness.py --launch run
  python tools/media_key_matrix_harness.py --launch none --pid 12345
"""

from __future__ import annotations

import argparse
import ctypes
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


if os.name != "nt":
    raise SystemExit("This harness requires Windows.")


ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.settings.settings_manager import SettingsManager


user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
winmm = ctypes.windll.winmm

SW_RESTORE = 9
SW_SHOW = 5
SW_MINIMIZE = 6
WM_CLOSE = 0x0010
WM_APPCOMMAND = 0x0319
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101

VK_VOLUME_DOWN = 0xAE
VK_VOLUME_UP = 0xAF
VK_C = 0x43
VK_ESCAPE = 0x1B
VK_MENU = 0x12

HWND_TOPMOST = -1
HWND_NOTOPMOST = -2
SWP_NOMOVE = 0x0002
SWP_NOSIZE = 0x0001
SWP_NOACTIVATE = 0x0010
SWP_SHOWWINDOW = 0x0040
SMTO_ABORTIFHUNG = 0x0002

APPCOMMAND_VOLUME_MUTE = 0x0008
APPCOMMAND_VOLUME_DOWN = 0x0009
APPCOMMAND_VOLUME_UP = 0x000A

INPUT_KEYBOARD = 1
INPUT_MOUSE = 0
KEYEVENTF_KEYUP = 0x0002
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010


class RECT(ctypes.Structure):
    _fields_ = [
        ("left", ctypes.c_long),
        ("top", ctypes.c_long),
        ("right", ctypes.c_long),
        ("bottom", ctypes.c_long),
    ]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", ctypes.c_ushort),
        ("wScan", ctypes.c_ushort),
        ("dwFlags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", ctypes.c_long),
        ("dy", ctypes.c_long),
        ("mouseData", ctypes.c_ulong),
        ("dwFlags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]


class INPUT_UNION(ctypes.Union):
    _fields_ = [
        ("ki", KEYBDINPUT),
        ("mi", MOUSEINPUT),
    ]


class INPUT(ctypes.Structure):
    _fields_ = [
        ("type", ctypes.c_ulong),
        ("union", INPUT_UNION),
    ]


@dataclass
class WindowInfo:
    hwnd: int
    pid: int
    title: str
    klass: str
    left: int
    top: int
    right: int
    bottom: int

    @property
    def width(self) -> int:
        return max(0, self.right - self.left)

    @property
    def height(self) -> int:
        return max(0, self.bottom - self.top)

    @property
    def area(self) -> int:
        return self.width * self.height

    def to_dict(self) -> Dict[str, Any]:
        return {
            "hwnd": self.hwnd,
            "pid": self.pid,
            "title": self.title,
            "class": self.klass,
            "left": self.left,
            "top": self.top,
            "right": self.right,
            "bottom": self.bottom,
            "width": self.width,
            "height": self.height,
            "area": self.area,
        }


class LogTail:
    def __init__(self, path: Path):
        self.path = path
        self.offset = 0
        self._prime()

    def _prime(self) -> None:
        if not self.path.exists():
            return
        try:
            with self.path.open("r", encoding="utf-8", errors="ignore") as handle:
                handle.seek(0, os.SEEK_END)
                self.offset = handle.tell()
        except Exception:
            self.offset = 0

    def read_new_lines(self) -> List[str]:
        if not self.path.exists():
            return []
        try:
            with self.path.open("r", encoding="utf-8", errors="ignore") as handle:
                handle.seek(self.offset, os.SEEK_SET)
                chunk = handle.read()
                self.offset = handle.tell()
        except Exception:
            return []
        if not chunk:
            return []
        return [line.rstrip("\n") for line in chunk.splitlines()]

    def collect_for(self, seconds: float, poll_s: float = 0.15) -> List[str]:
        deadline = time.time() + max(0.0, seconds)
        lines: List[str] = []
        while time.time() < deadline:
            lines.extend(self.read_new_lines())
            time.sleep(poll_s)
        lines.extend(self.read_new_lines())
        return lines


def _get_pid(hwnd: int) -> int:
    pid = ctypes.c_ulong(0)
    user32.GetWindowThreadProcessId(ctypes.c_void_p(hwnd), ctypes.byref(pid))
    return int(pid.value)


def _get_text(hwnd: int) -> str:
    buf = ctypes.create_unicode_buffer(512)
    user32.GetWindowTextW(ctypes.c_void_p(hwnd), buf, 512)
    return buf.value


def _get_class(hwnd: int) -> str:
    buf = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(ctypes.c_void_p(hwnd), buf, 256)
    return buf.value


def _get_rect(hwnd: int) -> RECT:
    rect = RECT()
    user32.GetWindowRect(ctypes.c_void_p(hwnd), ctypes.byref(rect))
    return rect


def _enum_visible_windows() -> List[WindowInfo]:
    windows: List[WindowInfo] = []
    enum_proc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

    @enum_proc
    def _cb(hwnd_raw, _lparam) -> bool:
        hwnd = int(ctypes.cast(hwnd_raw, ctypes.c_void_p).value)
        if not hwnd:
            return True
        if not bool(user32.IsWindowVisible(ctypes.c_void_p(hwnd))):
            return True
        rect = _get_rect(hwnd)
        info = WindowInfo(
            hwnd=hwnd,
            pid=_get_pid(hwnd),
            title=_get_text(hwnd),
            klass=_get_class(hwnd),
            left=int(rect.left),
            top=int(rect.top),
            right=int(rect.right),
            bottom=int(rect.bottom),
        )
        if info.area <= 0:
            return True
        windows.append(info)
        return True

    user32.EnumWindows(_cb, 0)
    return windows


def _find_best_window_for_pid(pid: int) -> Optional[WindowInfo]:
    candidates = [w for w in _enum_visible_windows() if w.pid == pid]
    if not candidates:
        return None
    candidates.sort(
        key=lambda w: (
            w.area,
            len(w.title or ""),
        ),
        reverse=True,
    )
    return candidates[0]


def _wait_for_window(pid: int, timeout_s: float = 25.0) -> Optional[WindowInfo]:
    deadline = time.time() + max(1.0, timeout_s)
    while time.time() < deadline:
        info = _find_best_window_for_pid(pid)
        if info is not None and info.area > 0:
            return info
        time.sleep(0.25)
    return None


def _foreground_window() -> Optional[WindowInfo]:
    hwnd = int(user32.GetForegroundWindow() or 0)
    if not hwnd:
        return None
    rect = _get_rect(hwnd)
    return WindowInfo(
        hwnd=hwnd,
        pid=_get_pid(hwnd),
        title=_get_text(hwnd),
        klass=_get_class(hwnd),
        left=int(rect.left),
        top=int(rect.top),
        right=int(rect.right),
        bottom=int(rect.bottom),
    )


def _force_foreground(hwnd: int) -> bool:
    if not hwnd:
        return False
    for attempt in range(6):
        if int(user32.GetForegroundWindow() or 0) == hwnd:
            return True

        fg = int(user32.GetForegroundWindow() or 0)
        current_tid = int(kernel32.GetCurrentThreadId())
        target_tid = int(user32.GetWindowThreadProcessId(ctypes.c_void_p(hwnd), None))
        fg_tid = int(user32.GetWindowThreadProcessId(ctypes.c_void_p(fg), None)) if fg else 0
        attached: List[int] = []
        try:
            # Best-effort foreground unlock sequence used in Windows UI automation.
            try:
                user32.AllowSetForegroundWindow(-1)
                user32.LockSetForegroundWindow(2)  # LSFW_UNLOCK
            except Exception:
                pass

            for tid in (fg_tid, target_tid):
                if tid and tid != current_tid:
                    if bool(user32.AttachThreadInput(current_tid, tid, True)):
                        attached.append(tid)

            user32.ShowWindow(ctypes.c_void_p(hwnd), SW_RESTORE if attempt == 0 else SW_SHOW)
            user32.BringWindowToTop(ctypes.c_void_p(hwnd))
            try:
                user32.SetWindowPos(
                    ctypes.c_void_p(hwnd),
                    HWND_TOPMOST,
                    0,
                    0,
                    0,
                    0,
                    SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW,
                )
                user32.SetWindowPos(
                    ctypes.c_void_p(hwnd),
                    HWND_NOTOPMOST,
                    0,
                    0,
                    0,
                    0,
                    SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW | SWP_NOACTIVATE,
                )
            except Exception:
                pass
            _tap_key(VK_MENU, hold_s=0.01)
            user32.SetForegroundWindow(ctypes.c_void_p(hwnd))
            user32.SetActiveWindow(ctypes.c_void_p(hwnd))
            user32.SetFocus(ctypes.c_void_p(hwnd))
        finally:
            for tid in attached:
                try:
                    user32.AttachThreadInput(current_tid, tid, False)
                except Exception:
                    pass

        time.sleep(0.12)
        if int(user32.GetForegroundWindow() or 0) == hwnd:
            return True

    return int(user32.GetForegroundWindow() or 0) == hwnd


def _force_foreground_soft(hwnd: int) -> bool:
    if not hwnd:
        return False
    try:
        user32.ShowWindow(ctypes.c_void_p(hwnd), SW_RESTORE)
        user32.BringWindowToTop(ctypes.c_void_p(hwnd))
        user32.SetForegroundWindow(ctypes.c_void_p(hwnd))
    except Exception:
        return False
    time.sleep(0.12)
    return int(user32.GetForegroundWindow() or 0) == hwnd


def _send_key(vk: int, *, key_up: bool = False) -> None:
    key = KEYBDINPUT(
        wVk=vk,
        wScan=0,
        dwFlags=KEYEVENTF_KEYUP if key_up else 0,
        time=0,
        dwExtraInfo=None,
    )
    data = INPUT(type=INPUT_KEYBOARD, union=INPUT_UNION(ki=key))
    user32.SendInput(1, ctypes.byref(data), ctypes.sizeof(INPUT))


def _tap_key(vk: int, hold_s: float = 0.035) -> None:
    _send_key(vk, key_up=False)
    time.sleep(max(0.0, hold_s))
    _send_key(vk, key_up=True)


def _send_mouse_click(button: str) -> None:
    if button == "left":
        down_flag, up_flag = MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP
    elif button == "right":
        down_flag, up_flag = MOUSEEVENTF_RIGHTDOWN, MOUSEEVENTF_RIGHTUP
    else:
        raise ValueError(f"Unsupported button: {button}")
    down = INPUT(
        type=INPUT_MOUSE,
        union=INPUT_UNION(mi=MOUSEINPUT(0, 0, 0, down_flag, 0, None)),
    )
    up = INPUT(
        type=INPUT_MOUSE,
        union=INPUT_UNION(mi=MOUSEINPUT(0, 0, 0, up_flag, 0, None)),
    )
    user32.SendInput(1, ctypes.byref(down), ctypes.sizeof(INPUT))
    time.sleep(0.03)
    user32.SendInput(1, ctypes.byref(up), ctypes.sizeof(INPUT))


def _click_window_center(hwnd: int, button: str = "left") -> None:
    _click_window_point(hwnd, 0.5, 0.5, button=button)


def _click_window_point(hwnd: int, x_ratio: float, y_ratio: float, button: str = "left") -> None:
    rect = _get_rect(hwnd)
    x_ratio = min(0.98, max(0.02, float(x_ratio)))
    y_ratio = min(0.98, max(0.02, float(y_ratio)))
    width = max(1, int(rect.right - rect.left))
    height = max(1, int(rect.bottom - rect.top))
    x = int(rect.left + (width * x_ratio))
    y = int(rect.top + (height * y_ratio))
    user32.SetCursorPos(x, y)
    time.sleep(0.05)
    _send_mouse_click(button)


def _click_window_stable(hwnd: int) -> Dict[str, Any]:
    """Click inside target window while avoiding interactive overlays that steal focus."""
    # Probe edges/corners first to avoid interactive center overlays (e.g., browser launch regions).
    points = [
        (0.03, 0.03),
        (0.97, 0.03),
        (0.03, 0.97),
        (0.97, 0.97),
        (0.50, 0.03),
        (0.50, 0.97),
        (0.03, 0.50),
        (0.97, 0.50),
        (0.15, 0.15),
        (0.85, 0.15),
        (0.15, 0.85),
        (0.85, 0.85),
        (0.50, 0.50),
    ]
    attempts: List[Dict[str, Any]] = []
    for x_ratio, y_ratio in points:
        _click_window_point(hwnd, x_ratio, y_ratio, button="left")
        time.sleep(0.25)
        fg = _foreground_window()
        attempts.append(
            {
                "point_ratio": [x_ratio, y_ratio],
                "foreground_after_click": fg.to_dict() if fg else None,
            }
        )
        if fg is not None and int(fg.hwnd) == int(hwnd):
            return {
                "clicked": True,
                "point_ratio": [x_ratio, y_ratio],
                "foreground_after_click": fg.to_dict(),
                "attempts": attempts,
            }
    fg = _foreground_window()
    return {
        "clicked": False,
        "point_ratio": None,
        "foreground_after_click": fg.to_dict() if fg else None,
        "attempts": attempts,
    }


def _wave_volume_raw() -> Optional[int]:
    volume = ctypes.c_uint(0)
    result = winmm.waveOutGetVolume(0xFFFFFFFF, ctypes.byref(volume))
    if result != 0:
        return None
    return int(volume.value)


def _set_wave_volume_raw(raw: int) -> bool:
    try:
        result = int(winmm.waveOutSetVolume(0xFFFFFFFF, int(raw) & 0xFFFFFFFF))
        return result == 0
    except Exception:
        return False


def _wave_volume_pair() -> tuple[int, int]:
    raw = _wave_volume_raw()
    if raw is None:
        return (0, 0)
    return (raw & 0xFFFF, (raw >> 16) & 0xFFFF)


def _volume_level() -> int:
    left, right = _wave_volume_pair()
    return int((left + right) / 2)


def _seed_profile_settings(appdata_root: Path, image_dir: Path) -> None:
    appdata_root.mkdir(parents=True, exist_ok=True)
    prev_appdata = os.environ.get("APPDATA")
    try:
        os.environ["APPDATA"] = str(appdata_root)
        mc = SettingsManager(application="Screensaver_MC")
        mc.set("sources.folders", [str(image_dir)])
        mc.set("sources.rss_feeds", [])
        mc.set("input.hard_exit", True)
        mc.save()

        normal = SettingsManager(application="Screensaver")
        normal.set("sources.folders", [str(image_dir)])
        normal.set("sources.rss_feeds", [])
        normal.set("input.hard_exit", True)
        normal.save()
    finally:
        if prev_appdata is None:
            os.environ.pop("APPDATA", None)
        else:
            os.environ["APPDATA"] = prev_appdata


def _apply_harness_safety_settings(appdata_root: Path) -> None:
    """Disable interactive click surfaces in harness-owned profiles."""
    appdata_root.mkdir(parents=True, exist_ok=True)
    prev_appdata = os.environ.get("APPDATA")
    try:
        os.environ["APPDATA"] = str(appdata_root)
        for app in ("Screensaver_MC", "Screensaver"):
            sm = SettingsManager(application=app)
            sm.set("widgets.reddit.enabled", False)
            sm.set("widgets.reddit.exit_on_click", False)
            sm.set("widgets.reddit2.enabled", False)
            sm.save()
    finally:
        if prev_appdata is None:
            os.environ.pop("APPDATA", None)
        else:
            os.environ["APPDATA"] = prev_appdata


def _mirror_live_profile(appdata_root: Path) -> Dict[str, Any]:
    """Copy live %APPDATA%\\SRPSS into harness temp APPDATA for realistic parity."""
    result: Dict[str, Any] = {"mode": "mirrored", "copied": False, "source": None, "dest": None, "error": None}
    source_root = Path(os.environ.get("APPDATA", "")).expanduser()
    source_profile = source_root / "SRPSS"
    dest_profile = appdata_root / "SRPSS"
    result["source"] = str(source_profile)
    result["dest"] = str(dest_profile)
    try:
        appdata_root.mkdir(parents=True, exist_ok=True)
        if source_profile.exists():
            shutil.copytree(source_profile, dest_profile, dirs_exist_ok=True)
            result["copied"] = True
        else:
            result["error"] = f"Source profile missing: {source_profile}"
    except Exception as exc:
        result["error"] = str(exc)
    return result


def _wait_for_log_file(log_dir: Path, timeout_s: float = 15.0) -> Optional[Path]:
    deadline = time.time() + max(1.0, timeout_s)
    candidate = log_dir / "screensaver.log"
    while time.time() < deadline:
        if candidate.exists():
            return candidate
        time.sleep(0.2)
    return candidate if candidate.exists() else None


def _wait_for_optional_log_file(log_dir: Path, filename: str, timeout_s: float = 6.0) -> Optional[Path]:
    deadline = time.time() + max(0.5, timeout_s)
    candidate = log_dir / filename
    while time.time() < deadline:
        if candidate.exists():
            return candidate
        time.sleep(0.15)
    return candidate if candidate.exists() else None


def _launch_runtime(
    launch: str,
    appdata_root: Optional[Path],
    log_dir: Path,
) -> tuple[subprocess.Popen[str], List[Any]]:
    env = os.environ.copy()
    env["SRPSS_FORCE_LOGS"] = "1"
    env["SRPSS_FORCE_LOG_DIR"] = str(log_dir)
    if appdata_root is not None:
        env["APPDATA"] = str(appdata_root)

    if launch == "mc":
        cmd = [sys.executable, "main_mc.py", "--debug", "/s"]
    elif launch == "run":
        cmd = [sys.executable, "main.py", "--debug", "/s"]
    else:
        raise ValueError(f"Unsupported launch mode: {launch}")
    stdout_path = log_dir / "launcher_stdout.log"
    stderr_path = log_dir / "launcher_stderr.log"
    out_handle = stdout_path.open("w", encoding="utf-8", errors="ignore")
    err_handle = stderr_path.open("w", encoding="utf-8", errors="ignore")
    proc = subprocess.Popen(
        cmd,
        cwd=str(ROOT),
        env=env,
        text=True,
        stdout=out_handle,
        stderr=err_handle,
    )
    return proc, [out_handle, err_handle]


def _parse_log_hits(lines: Iterable[str]) -> Dict[str, int]:
    hit_map = {
        "media_info": 0,
        "media_raw_input": 0,
        "appcommand": 0,
        "transition_cycle": 0,
    }
    for line in lines:
        lowered = line.lower()
        if "media key detected" in lowered or "media key pressed" in lowered:
            hit_map["media_info"] += 1
        if "[raw_input]" in lowered or "wm_input" in lowered:
            hit_map["media_raw_input"] += 1
        if "[win_appcommand]" in lowered or "wm_appcommand" in lowered:
            hit_map["appcommand"] += 1
        if "cycle transition requested" in lowered:
            hit_map["transition_cycle"] += 1
    return hit_map


def _parse_signal_counts(lines: Iterable[str]) -> Dict[str, int]:
    counts = {
        "input_handler_media": 0,
        "input_handler_transition_c": 0,
        "win_appcommand": 0,
        "raw_input": 0,
        "wm_input": 0,
    }
    for line in lines:
        lowered = line.lower()
        if "[input_handler] media key detected" in lowered:
            counts["input_handler_media"] += 1
        if "c key pressed - cycle transition requested" in lowered:
            counts["input_handler_transition_c"] += 1
        if "[win_appcommand]" in lowered:
            counts["win_appcommand"] += 1
        if "[raw_input]" in lowered:
            counts["raw_input"] += 1
        if "wm_input" in lowered:
            counts["wm_input"] += 1
    return counts


def _drain_tails(tails: List[LogTail]) -> None:
    for tail in tails:
        tail.read_new_lines()


def _collect_tails(tails: List[LogTail], seconds: float, poll_s: float = 0.12) -> List[str]:
    deadline = time.time() + max(0.0, seconds)
    lines: List[str] = []
    while time.time() < deadline:
        for tail in tails:
            lines.extend(tail.read_new_lines())
        time.sleep(poll_s)
    for tail in tails:
        lines.extend(tail.read_new_lines())
    return lines


def _capture_foreground_timeline(seconds: float, interval_s: float = 0.1) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    deadline = time.time() + max(0.0, seconds)
    while time.time() < deadline:
        fg = _foreground_window()
        out.append(
            {
                "t_ms": int(time.time() * 1000),
                "hwnd": int(fg.hwnd) if fg else 0,
                "pid": int(fg.pid) if fg else 0,
                "title": fg.title if fg else "",
                "class": fg.klass if fg else "",
            }
        )
        time.sleep(max(0.02, interval_s))
    return out


def _post_appcommand(hwnd: int, command: int, device: int = 0) -> bool:
    if not hwnd:
        return False
    lparam = int(((command & 0xFFFF) << 16) | (device & 0xFFFF))
    try:
        result = ctypes.c_ulong(0)
        ok = int(
            user32.SendMessageTimeoutW(
                ctypes.c_void_p(hwnd),
                WM_APPCOMMAND,
                ctypes.c_void_p(hwnd),
                ctypes.c_void_p(lparam),
                SMTO_ABORTIFHUNG,
                800,
                ctypes.byref(result),
            )
            or 0
        )
        return ok != 0
    except Exception:
        return False


def _post_key_message(hwnd: int, vk: int, message: int) -> bool:
    if not hwnd:
        return False
    try:
        return bool(user32.PostMessageW(ctypes.c_void_p(hwnd), int(message), int(vk), 0))
    except Exception:
        return False


def _ensure_target_focus(
    target_hwnd: int,
    minimized_hwnds: Optional[List[int]] = None,
    focus_policy: str = "strict",
) -> bool:
    if focus_policy == "realistic":
        if _force_foreground_soft(target_hwnd):
            return True
    else:
        if _force_foreground(target_hwnd):
            return True

    if focus_policy == "realistic":
        # Avoid aggressive blocker minimization in realistic mode.
        try:
            _click_window_center(target_hwnd, "left")
        except Exception:
            pass
        time.sleep(0.2)
        return _force_foreground_soft(target_hwnd)

    if _force_foreground(target_hwnd):
        return True

    blocker = _foreground_window()
    if blocker is not None and blocker.hwnd != target_hwnd:
        try:
            user32.ShowWindow(ctypes.c_void_p(blocker.hwnd), SW_MINIMIZE)
            if minimized_hwnds is not None:
                minimized_hwnds.append(int(blocker.hwnd))
            time.sleep(0.25)
            if _force_foreground(target_hwnd):
                return True
        except Exception:
            pass

    # Fallback: click target once, then try foreground acquisition again.
    try:
        _click_window_center(target_hwnd, "left")
    except Exception:
        pass
    time.sleep(0.2)
    return _force_foreground(target_hwnd)


def _scenario_prepare(name: str, target_hwnd: int, focus_policy: str) -> Dict[str, Any]:
    context: Dict[str, Any] = {"scenario": name, "focus_ok": False, "minimized_hwnds": []}
    if name == "focused_idle":
        context["focus_ok"] = _ensure_target_focus(target_hwnd, context["minimized_hwnds"], focus_policy)
    elif name == "focused_clicked":
        context["focus_ok_before_click"] = _ensure_target_focus(target_hwnd, context["minimized_hwnds"], focus_policy)
        time.sleep(0.2)
        click_result = _click_window_stable(target_hwnd)
        context["stable_click"] = click_result
        context["focus_ok"] = bool(context.get("focus_ok_before_click") and click_result.get("clicked"))
        if not click_result.get("clicked"):
            context["focus_invalid_reason"] = "focused_clicked_unstable_focus_or_overlay_focus_steal"
        time.sleep(0.25)
    elif name == "focused_context_menu":
        context["focus_ok"] = _ensure_target_focus(target_hwnd, context["minimized_hwnds"], focus_policy)
        time.sleep(0.2)
        _click_window_center(target_hwnd, "right")
        time.sleep(0.35)
    elif name == "unfocused_notepad":
        note = subprocess.Popen(["notepad.exe"])
        context["helper_pid"] = int(note.pid)
        note_window = _wait_for_window(int(note.pid), timeout_s=8.0)
        if note_window is not None:
            context["focus_ok"] = _force_foreground(note_window.hwnd)
        context["_helper_proc"] = note
        time.sleep(0.25)
    else:
        raise ValueError(f"Unknown scenario: {name}")
    context["fg_after_prepare"] = _foreground_window().to_dict() if _foreground_window() else None
    return context


def _scenario_cleanup(name: str, context: Dict[str, Any]) -> None:
    if name == "focused_context_menu":
        try:
            target_hwnd = int(context.get("fg_after_prepare", {}).get("hwnd") or 0)
            if target_hwnd:
                _click_window_center(target_hwnd, "left")
        except Exception:
            pass
        time.sleep(0.1)
    helper = context.get("_helper_proc") or context.get("helper_proc")
    if helper is not None:
        try:
            helper.wait(timeout=0.1)
        except Exception:
            pass
        pid = context.get("helper_pid")
        if isinstance(pid, int):
            win = _find_best_window_for_pid(pid)
            if win is not None:
                try:
                    user32.PostMessageW(ctypes.c_void_p(win.hwnd), WM_CLOSE, 0, 0)
                except Exception:
                    pass
        try:
            helper.terminate()
            helper.wait(timeout=2.0)
        except Exception:
            try:
                helper.kill()
            except Exception:
                pass

    for hwnd in context.get("minimized_hwnds", []) or []:
        try:
            user32.ShowWindow(ctypes.c_void_p(int(hwnd)), SW_RESTORE)
        except Exception:
            pass


def _run_media_probe(tails: List[LogTail]) -> Dict[str, Any]:
    baseline_raw = _wave_volume_raw()
    baseline = _volume_level()
    _drain_tails(tails)
    if baseline > 64000:
        first, second = VK_VOLUME_DOWN, VK_VOLUME_UP
    elif baseline < 1000:
        first, second = VK_VOLUME_UP, VK_VOLUME_DOWN
    else:
        first, second = VK_VOLUME_UP, VK_VOLUME_DOWN

    fg_before = _foreground_window()
    _tap_key(first)
    time.sleep(0.28)
    mid = _volume_level()
    _tap_key(second)
    time.sleep(0.28)
    final = _volume_level()
    restored = final
    restored_ok = None
    if baseline_raw is not None:
        restored_ok = _set_wave_volume_raw(baseline_raw)
        time.sleep(0.1)
        restored = _volume_level()
    fg_timeline = _capture_foreground_timeline(0.6, interval_s=0.1)
    lines = _collect_tails(tails, 0.9, poll_s=0.12)
    hits = _parse_log_hits(lines)
    signals = _parse_signal_counts(lines)
    changed_first = mid != baseline
    changed_second = final != mid
    passed = bool(changed_first or changed_second or hits["media_info"] or hits["appcommand"] or hits["media_raw_input"])
    return {
        "probe": "media_volume_step",
        "path": "qt_key_input",
        "foreground_before": fg_before.to_dict() if fg_before else None,
        "baseline_volume": baseline,
        "mid_volume": mid,
        "final_volume": final,
        "restored_volume": restored,
        "restored_ok": restored_ok,
        "first_key": first,
        "second_key": second,
        "changed_first": changed_first,
        "changed_second": changed_second,
        "log_hits": hits,
        "signal_counts": signals,
        "foreground_timeline": fg_timeline,
        "log_excerpt": lines[-12:],
        "passed": passed,
    }


def _run_native_appcommand_probe(tails: List[LogTail], target_hwnd: int) -> Dict[str, Any]:
    baseline_raw = _wave_volume_raw()
    baseline = _volume_level()
    _drain_tails(tails)
    fg_before = _foreground_window()

    sent_down = _post_appcommand(target_hwnd, APPCOMMAND_VOLUME_DOWN)
    time.sleep(0.25)
    mid = _volume_level()
    sent_up = _post_appcommand(target_hwnd, APPCOMMAND_VOLUME_UP)
    time.sleep(0.25)
    final = _volume_level()

    restored = final
    restored_ok = None
    if baseline_raw is not None:
        restored_ok = _set_wave_volume_raw(baseline_raw)
        time.sleep(0.1)
        restored = _volume_level()

    fg_timeline = _capture_foreground_timeline(0.6, interval_s=0.1)
    lines = _collect_tails(tails, 0.9, poll_s=0.12)
    hits = _parse_log_hits(lines)
    signals = _parse_signal_counts(lines)
    changed_first = mid != baseline
    changed_second = final != mid
    passed = bool(
        (sent_down and sent_up)
        and (hits["appcommand"] > 0 or changed_first or changed_second)
    )
    return {
        "probe": "native_appcommand_volume_pair",
        "path": "wm_appcommand_injected",
        "foreground_before": fg_before.to_dict() if fg_before else None,
        "target_hwnd": int(target_hwnd),
        "sent_down": bool(sent_down),
        "sent_up": bool(sent_up),
        "baseline_volume": baseline,
        "mid_volume": mid,
        "final_volume": final,
        "restored_volume": restored,
        "restored_ok": restored_ok,
        "log_hits": hits,
        "signal_counts": signals,
        "foreground_timeline": fg_timeline,
        "log_excerpt": lines[-12:],
        "changed_first": changed_first,
        "changed_second": changed_second,
        "passed": passed,
    }


def _run_transition_probe(tails: List[LogTail]) -> Dict[str, Any]:
    _drain_tails(tails)
    fg_before = _foreground_window()
    _tap_key(VK_C)
    fg_timeline = _capture_foreground_timeline(0.6, interval_s=0.1)
    lines = _collect_tails(tails, 0.9, poll_s=0.12)
    hits = _parse_log_hits(lines)
    signals = _parse_signal_counts(lines)
    passed = hits["transition_cycle"] > 0
    return {
        "probe": "transition_cycle_c",
        "foreground_before": fg_before.to_dict() if fg_before else None,
        "log_hits": hits,
        "signal_counts": signals,
        "foreground_timeline": fg_timeline,
        "log_excerpt": lines[-12:],
        "passed": passed,
    }


def _run_native_keymsg_c_probe(tails: List[LogTail], target_hwnd: int) -> Dict[str, Any]:
    _drain_tails(tails)
    fg_before = _foreground_window()
    sent_down = _post_key_message(target_hwnd, VK_C, WM_KEYDOWN)
    time.sleep(0.05)
    sent_up = _post_key_message(target_hwnd, VK_C, WM_KEYUP)
    fg_timeline = _capture_foreground_timeline(0.6, interval_s=0.1)
    lines = _collect_tails(tails, 0.9, poll_s=0.12)
    hits = _parse_log_hits(lines)
    signals = _parse_signal_counts(lines)
    passed = bool(sent_down and sent_up and hits["transition_cycle"] > 0)
    return {
        "probe": "native_keymsg_c",
        "path": "wm_keydown_up_injected",
        "foreground_before": fg_before.to_dict() if fg_before else None,
        "target_hwnd": int(target_hwnd),
        "sent_down": bool(sent_down),
        "sent_up": bool(sent_up),
        "log_hits": hits,
        "signal_counts": signals,
        "foreground_timeline": fg_timeline,
        "log_excerpt": lines[-12:],
        "passed": passed,
    }


def _write_markdown_report(path: Path, payload: Dict[str, Any]) -> None:
    lines: List[str] = []
    lines.append("# Media/Input Matrix Harness Report")
    lines.append("")
    lines.append(f"- Timestamp: `{payload.get('timestamp')}`")
    lines.append(f"- Launch mode: `{payload.get('launch_mode')}`")
    lines.append(f"- Profile mode: `{payload.get('profile_mode')}`")
    lines.append(f"- Focus policy: `{payload.get('focus_policy')}`")
    contract = payload.get("runtime_contract") or {}
    lines.append(f"- Runtime contract pass: `{bool(contract.get('passed'))}`")
    lines.append(f"- Target PID: `{payload.get('target_pid')}`")
    lines.append(f"- Target HWND: `{payload.get('target_hwnd')}`")
    lines.append("")
    lines.append("## Scenario Matrix")
    lines.append("")
    lines.append("| Scenario | Focus Prepared | Scenario Valid | Qt Media Probe | Native AppCmd Probe | Native KeyMsg C | Transition Probe | Notes |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---|")
    for row in payload.get("scenarios", []):
        blocked = bool(row.get("blocked_no_focus"))
        note = row.get("blocked_reason") or ""
        lines.append(
            f"| `{row.get('scenario')}` | "
            f"{'yes' if row.get('focus_ok') else 'no'} | "
            f"{'no' if blocked else 'yes'} | "
            f"{'pass' if row.get('media_probe', {}).get('passed') else 'fail'} | "
            f"{'pass' if row.get('native_appcommand_probe', {}).get('passed') else 'fail'} | "
            f"{'pass' if row.get('native_keymsg_probe', {}).get('passed') else 'fail'} | "
            f"{'pass' if row.get('transition_probe', {}).get('passed') else 'fail'} | "
            f"{note} |"
        )
    lines.append("")
    lines.append("## Notes")
    lines.append("")
    lines.append("- Qt media probe validates synthetic key route (`SendInput` -> app key handling).")
    lines.append("- Native appcommand probe validates WM_APPCOMMAND dispatch route separately.")
    lines.append("- Transition pass requires `C key pressed - cycle transition requested` in log delta.")
    if contract:
        lines.append("- Runtime contract checks: " + ", ".join(contract.get("checks", [])))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _evaluate_runtime_contract(launch: str, target_window: WindowInfo, log_file: Path) -> Dict[str, Any]:
    checks: List[str] = []
    missing: List[str] = []
    details: Dict[str, Any] = {
        "launch": launch,
        "target_window_class": target_window.klass,
        "target_window_title": target_window.title,
    }

    log_text = ""
    try:
        log_text = log_file.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        log_text = ""

    def _must(name: str, condition: bool) -> None:
        checks.append(name)
        if not condition:
            missing.append(name)

    if launch == "mc":
        _must("target class indicates Qt Tool/Splash MC window", "Tool" in target_window.klass or "Splash" in target_window.klass)
        _must("log has MC window flag mode", "[DISPLAY_WIDGET] MC window flag mode=" in log_text)
        _must("log has display widget creation", "DisplayWidget created for screen" in log_text)
        _must("log has GL compositor creation", "[GL COMPOSITOR] Created shared compositor" in log_text)
        _must("log has show_on_screen", "Showing on screen " in log_text)
    else:
        _must("log has display widget creation", "DisplayWidget created for screen" in log_text)
        _must("log has show_on_screen", "Showing on screen " in log_text)

    details["passed"] = not missing
    details["checks"] = checks
    details["missing"] = missing
    return details


def run_harness(args: argparse.Namespace) -> Dict[str, Any]:
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    out_dir = Path(args.output_dir).resolve() / f"media_matrix_{timestamp}"
    out_dir.mkdir(parents=True, exist_ok=True)
    log_dir = out_dir / "runtime_logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    appdata_root: Optional[Path] = None
    profile_status: Dict[str, Any] = {"mode": args.profile_mode}
    isolate_appdata = bool(args.isolate_appdata)
    if args.profile_mode == "live":
        isolate_appdata = False
    if args.profile_mode == "mirrored":
        appdata_root = (Path(tempfile.gettempdir()) / f"srpss_media_harness_{timestamp}").resolve()
        profile_status = _mirror_live_profile(appdata_root)
        if not profile_status.get("copied"):
            raise RuntimeError(
                "Mirrored profile setup failed.\n"
                f"source={profile_status.get('source')}\n"
                f"dest={profile_status.get('dest')}\n"
                f"error={profile_status.get('error')}"
            )
        if args.safe_click_guards:
            _apply_harness_safety_settings(appdata_root)
            profile_status["safe_click_guards"] = True
    elif isolate_appdata:
        appdata_root = (Path(tempfile.gettempdir()) / f"srpss_media_harness_{timestamp}").resolve()
        image_dir = (ROOT / "images").resolve()
        _seed_profile_settings(appdata_root, image_dir)
        if args.safe_click_guards:
            _apply_harness_safety_settings(appdata_root)
        profile_status = {"mode": "isolated", "copied": True, "source": "seeded-defaults", "dest": str(appdata_root / "SRPSS")}
        if args.safe_click_guards:
            profile_status["safe_click_guards"] = True
    else:
        profile_status = {"mode": "live", "copied": False, "source": str(Path(os.environ.get("APPDATA", "")) / "SRPSS"), "dest": None}
        if args.safe_click_guards:
            profile_status["safe_click_guards"] = "live_profile_not_mutated"

    proc: Optional[subprocess.Popen[str]] = None
    launch_io_handles: List[Any] = []
    target_pid: Optional[int] = args.pid
    target_window: Optional[WindowInfo] = None

    if args.launch != "none":
        proc, launch_io_handles = _launch_runtime(args.launch, appdata_root, log_dir)
        target_pid = int(proc.pid)
    elif target_pid is None:
        raise RuntimeError("--launch none requires --pid")

    assert target_pid is not None
    target_window = _wait_for_window(target_pid, timeout_s=args.launch_timeout_s)
    if target_window is None:
        exit_code = None
        if proc is not None:
            try:
                exit_code = proc.poll()
            except Exception:
                exit_code = None
        startup_log = log_dir / "screensaver.log"
        tail_lines: List[str] = []
        if startup_log.exists():
            try:
                raw = startup_log.read_text(encoding="utf-8", errors="ignore").splitlines()
                tail_lines = raw[-20:]
            except Exception:
                tail_lines = []
        detail = [
            f"Failed to locate visible target window for pid={target_pid}",
            f"launch_mode={args.launch}",
            f"profile_mode={args.profile_mode}",
            f"focus_policy={args.focus_policy}",
            f"process_exit_code={exit_code}",
            f"log_dir={log_dir}",
        ]
        if tail_lines:
            detail.append("startup_log_tail:")
            detail.extend(tail_lines)
        raise RuntimeError("\n".join(detail))

    log_file = _wait_for_log_file(log_dir, timeout_s=12.0)
    if log_file is None:
        raise RuntimeError(f"Failed to locate screensaver.log in {log_dir}")
    verbose_log_file = _wait_for_optional_log_file(log_dir, "screensaver_verbose.log", timeout_s=8.0)
    tails: List[LogTail] = [LogTail(log_file)]
    if verbose_log_file is not None:
        tails.append(LogTail(verbose_log_file))

    scenarios = [s.strip() for s in args.scenarios.split(",") if s.strip()]
    rows: List[Dict[str, Any]] = []

    try:
        for scenario in scenarios:
            row: Dict[str, Any] = {"scenario": scenario}
            prep = _scenario_prepare(scenario, target_window.hwnd, args.focus_policy)
            row.update(
                {
                    key: value
                    for key, value in prep.items()
                    if key not in {"helper_proc", "_helper_proc", "minimized_hwnds"}
                }
            )
            row["foreground_before_probes"] = _foreground_window().to_dict() if _foreground_window() else None
            focus_required = scenario.startswith("focused")
            blocked_reason = ""
            blocked_no_focus = bool(focus_required and not bool(row.get("focus_ok")) and args.require_focus_for_focused)
            if scenario == "focused_clicked":
                click_ok = bool((row.get("stable_click") or {}).get("clicked"))
                if args.require_focus_for_focused and not click_ok:
                    blocked_no_focus = True
                    blocked_reason = str(
                        row.get("focus_invalid_reason")
                        or "focused_clicked_unstable_focus_or_overlay_focus_steal"
                    )
            if blocked_no_focus and not blocked_reason:
                blocked_reason = "focused_scenario_target_not_foreground"
            row["blocked_no_focus"] = blocked_no_focus
            if blocked_reason:
                row["blocked_reason"] = blocked_reason
            if blocked_no_focus:
                row["media_probe"] = {"probe": "media_volume_step", "path": "qt_key_input", "passed": False, "blocked": True}
                row["native_appcommand_probe"] = {"probe": "native_appcommand_volume_pair", "path": "wm_appcommand_injected", "passed": False, "blocked": True}
                row["native_keymsg_probe"] = {"probe": "native_keymsg_c", "path": "wm_keydown_up_injected", "passed": False, "blocked": True}
                row["transition_probe"] = {"probe": "transition_cycle_c", "passed": False, "blocked": True}
            else:
                row["media_probe"] = _run_media_probe(tails)
                row["native_appcommand_probe"] = _run_native_appcommand_probe(tails, target_window.hwnd)
                row["native_keymsg_probe"] = _run_native_keymsg_c_probe(tails, target_window.hwnd)
                row["transition_probe"] = _run_transition_probe(tails)
            row["foreground_after_probes"] = _foreground_window().to_dict() if _foreground_window() else None
            _scenario_cleanup(scenario, prep)
            rows.append(row)
            time.sleep(0.2)
    finally:
        for handle in launch_io_handles:
            try:
                handle.flush()
                handle.close()
            except Exception:
                pass
        if proc is not None:
            try:
                proc.terminate()
                proc.wait(timeout=5.0)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass

    payload = {
        "timestamp": timestamp,
        "launch_mode": args.launch,
        "profile_mode": args.profile_mode,
        "focus_policy": args.focus_policy,
        "target_pid": target_pid,
        "target_hwnd": target_window.hwnd,
        "target_window": target_window.to_dict(),
        "appdata_root": str(appdata_root) if appdata_root is not None else None,
        "profile_status": profile_status,
        "output_dir": str(out_dir),
        "log_file": str(log_file),
        "verbose_log_file": str(verbose_log_file) if verbose_log_file is not None else None,
        "scenarios": rows,
    }
    runtime_contract = _evaluate_runtime_contract(args.launch, target_window, log_file)
    payload["runtime_contract"] = runtime_contract
    if args.require_runtime_contract and not runtime_contract.get("passed"):
        raise RuntimeError(
            "Runtime contract failed: "
            + ", ".join(runtime_contract.get("missing", []))
        )

    json_path = out_dir / "matrix_report.json"
    md_path = out_dir / "matrix_report.md"
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    _write_markdown_report(md_path, payload)
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Media/input matrix harness for U-05.")
    parser.add_argument(
        "--launch",
        choices=("mc", "run", "none"),
        default="mc",
        help="Launch runtime variant or attach to existing pid.",
    )
    parser.add_argument(
        "--pid",
        type=int,
        default=None,
        help="Existing target PID (required when --launch none).",
    )
    parser.add_argument(
        "--isolate-appdata",
        action="store_true",
        default=True,
        help="Seed and use isolated APPDATA (default: enabled).",
    )
    parser.add_argument(
        "--no-isolate-appdata",
        dest="isolate_appdata",
        action="store_false",
        help="Use current APPDATA profile.",
    )
    parser.add_argument(
        "--launch-timeout-s",
        type=float,
        default=28.0,
        help="Timeout for target window discovery.",
    )
    parser.add_argument(
        "--focus-policy",
        choices=("strict", "realistic"),
        default="strict",
        help="Focus handling strategy. 'realistic' avoids aggressive foreground coercion.",
    )
    parser.add_argument(
        "--scenarios",
        default="focused_idle,focused_clicked",
        help="Comma-separated scenario list.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(ROOT / "logs"),
        help="Directory root for harness reports.",
    )
    parser.add_argument(
        "--profile-mode",
        choices=("isolated", "live", "mirrored"),
        default="isolated",
        help="APPDATA mode: isolated (seeded), live (direct), mirrored (copy live profile into temp).",
    )
    parser.add_argument(
        "--safe-click-guards",
        action="store_true",
        default=True,
        help="Disable interactive Reddit surfaces in harness-owned profiles to prevent accidental external clicks (default: enabled).",
    )
    parser.add_argument(
        "--no-safe-click-guards",
        dest="safe_click_guards",
        action="store_false",
        help="Do not modify harness profile widget safety settings.",
    )
    parser.add_argument(
        "--require-focus-for-focused",
        action="store_true",
        default=True,
        help="Block focused_* probes unless SRPSS focus was actually acquired (default: enabled).",
    )
    parser.add_argument(
        "--allow-probe-without-focus",
        dest="require_focus_for_focused",
        action="store_false",
        help="Allow focused_* probes even when SRPSS did not acquire focus.",
    )
    parser.add_argument(
        "--require-runtime-contract",
        action="store_true",
        default=True,
        help="Fail run if launch-specific runtime contract checks are missing (default: enabled).",
    )
    parser.add_argument(
        "--no-require-runtime-contract",
        dest="require_runtime_contract",
        action="store_false",
        help="Do not fail run when runtime contract checks are missing.",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    payload = run_harness(args)
    print("[HARNESS] Completed media/input matrix run")
    print(f"[HARNESS] Report JSON: {Path(payload['output_dir']) / 'matrix_report.json'}")
    print(f"[HARNESS] Report MD:   {Path(payload['output_dir']) / 'matrix_report.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
