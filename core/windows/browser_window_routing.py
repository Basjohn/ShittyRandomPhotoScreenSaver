"""Best-effort browser window foreground helpers.

Centralizes the "prefer display 0, then fall back cleanly" policy used by
SCR helper launches and MC direct-open flows. This layer intentionally does
not launch browsers or manipulate browser internals; it only ranks existing
top-level windows and attempts a foreground/restore on a matching candidate.
"""
from __future__ import annotations

import ctypes
import sys
from ctypes import wintypes
from typing import Callable, Iterable
from urllib.parse import urlparse

from core.logging.logger import get_logger

logger = get_logger(__name__)


def build_url_title_keywords(url: str, *, fallback_keywords: Iterable[str] = ()) -> list[str]:
    """Build browser-window title keywords for *url*.

    The result is intentionally heuristic and low-risk: prefer recognizable
    domain/app tokens, then append caller-provided fallback hints such as
    ``reddit`` for known surfaces.
    """

    keywords: list[str] = []
    host = ""
    try:
        parsed = urlparse(url)
        host = (parsed.netloc or "").lower()
        if host:
            host = host.split("@")[-1]
            host = host.split(":")[0]
            tokens = [part for part in host.replace("-", ".").split(".") if part]
            keywords.extend(token for token in tokens if token not in ("www", "m", "com"))
    except Exception as exc:
        logger.debug("[BROWSER-ROUTING] Failed to parse URL keywords for %s: %s", url, exc)

    if "mail.google.com" in host:
        keywords.append("gmail")

    for keyword in fallback_keywords:
        text = str(keyword or "").strip().lower()
        if text:
            keywords.append(text)

    seen: set[str] = set()
    deduped: list[str] = []
    for keyword in keywords:
        if keyword and keyword not in seen:
            deduped.append(keyword)
            seen.add(keyword)

    return deduped


def select_preferred_hwnd(
    candidates: Iterable[int],
    *,
    preferred_monitor: int | None,
    monitor_for_hwnd: Callable[[int], int | None],
) -> int | None:
    """Return the preferred candidate hwnd.

    Candidates on the preferred monitor win first; otherwise preserve original
    enumeration order.
    """

    candidate_list = [int(hwnd) for hwnd in candidates]
    if not candidate_list:
        return None
    if preferred_monitor is None:
        return candidate_list[0]

    def _rank(hwnd: int) -> tuple[int, int]:
        monitor = monitor_for_hwnd(hwnd)
        return (0 if monitor == preferred_monitor else 1, candidate_list.index(hwnd))

    return min(candidate_list, key=_rank)


def try_bring_browser_window_to_front(
    url: str,
    *,
    preferred_display_index: int = 0,
    fallback_keywords: Iterable[str] = (),
) -> bool:
    """Best-effort foreground of a browser window matching *url*."""

    keywords = build_url_title_keywords(url, fallback_keywords=fallback_keywords)
    return try_bring_browser_window_to_front_by_keywords(
        keywords,
        preferred_display_index=preferred_display_index,
    )


def try_bring_browser_window_to_front_by_keywords(
    keywords: Iterable[str],
    *,
    preferred_display_index: int = 0,
) -> bool:
    """Best-effort foreground of a browser window matching *keywords*."""

    if sys.platform != "win32":  # pragma: no cover - platform guard
        return False

    keyword_list = [str(keyword or "").strip().lower() for keyword in keywords if str(keyword or "").strip()]
    if not keyword_list:
        return False

    try:
        user32 = ctypes.windll.user32  # type: ignore[attr-defined]
    except Exception as exc:
        logger.debug("[BROWSER-ROUTING] Failed to acquire user32: %s", exc)
        return False

    try:
        EnumWindowsProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        MonitorEnumProc = ctypes.WINFUNCTYPE(
            wintypes.BOOL,
            wintypes.HMONITOR,
            wintypes.HDC,
            ctypes.POINTER(wintypes.RECT),
            wintypes.LPARAM,
        )
    except Exception as exc:
        logger.debug("[BROWSER-ROUTING] Failed to prepare Win32 callbacks: %s", exc)
        return False

    class MONITORINFO(ctypes.Structure):
        _fields_ = [
            ("cbSize", wintypes.DWORD),
            ("rcMonitor", wintypes.RECT),
            ("rcWork", wintypes.RECT),
            ("dwFlags", wintypes.DWORD),
        ]

    try:
        user32.EnumWindows.argtypes = [EnumWindowsProc, wintypes.LPARAM]
        user32.IsWindowVisible.argtypes = [wintypes.HWND]
        user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
        user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
        user32.MonitorFromWindow.argtypes = [wintypes.HWND, wintypes.DWORD]
        user32.GetMonitorInfoW.argtypes = [wintypes.HMONITOR, ctypes.POINTER(MONITORINFO)]
        user32.EnumDisplayMonitors.argtypes = [wintypes.HDC, ctypes.c_void_p, MonitorEnumProc, wintypes.LPARAM]
    except Exception as exc:
        logger.debug("[BROWSER-ROUTING] Failed to assign Win32 argtypes: %s", exc)

    display_monitors: list[int] = []

    @MonitorEnumProc
    def _monitor_enum_proc(hmonitor, _hdc, _rect, _lparam):  # noqa: ANN001
        try:
            display_monitors.append(int(hmonitor))
        except Exception:
            pass
        return True

    preferred_monitor: int | None = None
    try:
        user32.EnumDisplayMonitors(None, None, _monitor_enum_proc, 0)
        if 0 <= int(preferred_display_index) < len(display_monitors):
            preferred_monitor = display_monitors[int(preferred_display_index)]
    except Exception as exc:
        logger.debug("[BROWSER-ROUTING] Failed to enumerate display monitors: %s", exc)
        preferred_monitor = None

    MONITOR_DEFAULTTONEAREST = 2
    candidates: list[int] = []

    @EnumWindowsProc
    def _enum_proc(hwnd, _lparam):  # noqa: ANN001
        try:
            if not user32.IsWindowVisible(hwnd):
                return True
            length = user32.GetWindowTextLengthW(hwnd)
            if length <= 0:
                return True
            buf = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buf, length + 1)
            title = (buf.value or "").lower()
            if any(keyword in title for keyword in keyword_list):
                candidates.append(int(hwnd))
        except Exception as exc:
            logger.debug("[BROWSER-ROUTING] Exception while enumerating windows: %s", exc)
        return True

    try:
        user32.EnumWindows(_enum_proc, 0)
    except Exception as exc:
        logger.debug("[BROWSER-ROUTING] EnumWindows failed: %s", exc)
        return False

    def _monitor_for_hwnd(hwnd: int) -> int | None:
        try:
            hmonitor = user32.MonitorFromWindow(int(hwnd), MONITOR_DEFAULTTONEAREST)
            return int(hmonitor) if hmonitor else None
        except Exception:
            return None

    hwnd = select_preferred_hwnd(
        candidates,
        preferred_monitor=preferred_monitor,
        monitor_for_hwnd=_monitor_for_hwnd,
    )
    if hwnd is None:
        return False

    try:
        if hasattr(user32, "AllowSetForegroundWindow"):
            user32.AllowSetForegroundWindow(0xFFFFFFFF)

        SW_RESTORE = 9
        SW_SHOW = 5
        SW_SHOWMAXIMIZED = 3

        is_iconic = bool(user32.IsIconic(hwnd))
        show_cmd = 0
        try:
            placement = WINDOWPLACEMENT()
            placement.length = ctypes.sizeof(placement)
            if user32.GetWindowPlacement(hwnd, ctypes.byref(placement)):
                show_cmd = placement.showCmd
        except Exception:
            show_cmd = 0

        if is_iconic:
            user32.ShowWindow(hwnd, SW_RESTORE)
        elif show_cmd == SW_SHOWMAXIMIZED:
            user32.ShowWindow(hwnd, SW_SHOWMAXIMIZED)
        else:
            user32.ShowWindow(hwnd, SW_SHOW)

        return bool(user32.SetForegroundWindow(hwnd))
    except Exception as exc:
        logger.debug("[BROWSER-ROUTING] Failed to foreground hwnd=%s: %s", hwnd, exc)
        return False


class WINDOWPLACEMENT(ctypes.Structure):
    _fields_ = [
        ("length", wintypes.UINT),
        ("flags", wintypes.UINT),
        ("showCmd", wintypes.UINT),
        ("ptMinPosition", wintypes.POINT),
        ("ptMaxPosition", wintypes.POINT),
        ("rcNormalPosition", wintypes.RECT),
    ]
