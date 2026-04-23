"""External Win32 window/foreground observer for flicker investigations.

Usage:
  python tools/winprobe_observer.py --out <path.json> --duration-s 8 --sample-ms 5 [--include-all|--pid N]
"""

from __future__ import annotations

import argparse
import ctypes
import json
import time
from pathlib import Path
from typing import Any, Dict, List


user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
GWL_STYLE = -16
GWL_EXSTYLE = -20


class _RECT(ctypes.Structure):
    _fields_ = [
        ("left", ctypes.c_long),
        ("top", ctypes.c_long),
        ("right", ctypes.c_long),
        ("bottom", ctypes.c_long),
    ]


def _get_pid(hwnd: int) -> int:
    pid = ctypes.c_ulong(0)
    user32.GetWindowThreadProcessId(ctypes.c_void_p(hwnd), ctypes.byref(pid))
    return int(pid.value)


def _get_title(hwnd: int) -> str:
    buf = ctypes.create_unicode_buffer(512)
    user32.GetWindowTextW(ctypes.c_void_p(hwnd), buf, 512)
    return buf.value


def _get_class(hwnd: int) -> str:
    buf = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(ctypes.c_void_p(hwnd), buf, 256)
    return buf.value


def _get_rect(hwnd: int) -> tuple[int, int, int, int]:
    rect = _RECT()
    ok = user32.GetWindowRect(ctypes.c_void_p(hwnd), ctypes.byref(rect))
    if not ok:
        return (0, 0, 0, 0)
    return (int(rect.left), int(rect.top), int(rect.right), int(rect.bottom))


def _get_styles(hwnd: int) -> tuple[int, int]:
    style = int(user32.GetWindowLongPtrW(ctypes.c_void_p(hwnd), GWL_STYLE)) & 0xFFFFFFFF
    exstyle = int(user32.GetWindowLongPtrW(ctypes.c_void_p(hwnd), GWL_EXSTYLE)) & 0xFFFFFFFF
    return (style, exstyle)


def _enum_visible_windows(*, include_all: bool, pid_filter: int) -> List[Dict[str, Any]]:
    windows: List[Dict[str, Any]] = []
    enum_proc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

    @enum_proc
    def _cb(hwnd_raw, _lparam) -> bool:
        hwnd = int(ctypes.cast(hwnd_raw, ctypes.c_void_p).value)
        if not bool(user32.IsWindowVisible(ctypes.c_void_p(hwnd))):
            return True
        pid = _get_pid(hwnd)
        if not include_all and pid != pid_filter:
            return True
        left, top, right, bottom = _get_rect(hwnd)
        windows.append(
            {
                "hwnd": hwnd,
                "pid": pid,
                "class": _get_class(hwnd),
                "title": _get_title(hwnd),
                "left": left,
                "top": top,
                "right": right,
                "bottom": bottom,
                "width": max(0, right - left),
                "height": max(0, bottom - top),
                "style": _get_styles(hwnd)[0],
                "exstyle": _get_styles(hwnd)[1],
            }
        )
        return True

    user32.EnumWindows(_cb, 0)
    return windows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True, help="Output JSON path")
    parser.add_argument("--duration-s", type=float, default=8.0)
    parser.add_argument("--sample-ms", type=int, default=5)
    parser.add_argument("--include-all", action="store_true")
    parser.add_argument("--pid", type=int, default=0)
    args = parser.parse_args()

    pid_filter = int(args.pid) if int(args.pid) > 0 else int(kernel32.GetCurrentProcessId())
    include_all = bool(args.include_all)
    sample_s = max(0.001, float(args.sample_ms) / 1000.0)
    duration_s = max(0.0, float(args.duration_s))

    baseline = {w["hwnd"] for w in _enum_visible_windows(include_all=include_all, pid_filter=pid_filter)}
    discovered: Dict[int, Dict[str, Any]] = {}
    fg_events: List[Dict[str, Any]] = []
    start = time.perf_counter()
    deadline = start + duration_s
    last_fg = int(user32.GetForegroundWindow())

    while time.perf_counter() < deadline:
        now = time.perf_counter()
        visible = _enum_visible_windows(include_all=include_all, pid_filter=pid_filter)
        for win in visible:
            hwnd = int(win["hwnd"])
            if hwnd in baseline:
                continue
            rec = discovered.get(hwnd)
            if rec is None:
                rec = dict(win)
                rec["first_ts"] = now - start
                rec["last_ts"] = now - start
                rec["samples"] = 1
                discovered[hwnd] = rec
            else:
                rec["last_ts"] = now - start
                rec["samples"] += 1
                rec["width"] = max(int(rec.get("width", 0)), int(win["width"]))
                rec["height"] = max(int(rec.get("height", 0)), int(win["height"]))

        fg = int(user32.GetForegroundWindow())
        if fg and fg != last_fg:
            fg_events.append(
                {
                    "ts": now - start,
                    "hwnd": fg,
                    "pid": _get_pid(fg),
                    "class": _get_class(fg),
                    "title": _get_title(fg),
                }
            )
            last_fg = fg
        time.sleep(sample_s)

    output = {
        "include_all": include_all,
        "pid_filter": pid_filter,
        "duration_s": duration_s,
        "sample_ms": int(args.sample_ms),
        "baseline_visible_count": len(baseline),
        "new_windows": sorted(discovered.values(), key=lambda r: (r.get("first_ts", 0.0), r.get("pid", 0))),
        "foreground_changes": fg_events,
    }

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(output, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()

