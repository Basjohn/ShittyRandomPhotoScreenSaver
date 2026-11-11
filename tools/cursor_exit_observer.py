"""What Windows itself shows as the cursor while the saver exits (operator-run, windowless).

A separate process that never imports SRPSS or Qt and opens no window. Every ~10 ms it reads, with Win32 only:

* ``GetCursorInfo``: the cursor Windows is DISPLAYING (flags + HCURSOR, named by comparing with the shared system
  cursors from ``LoadCursorW(0, IDC_*)``; anything else is ``custom:<handle>``, e.g. the Halo or a blank cursor);
* the mouse capture of the foreground thread and of the thread owning the window under the pointer
  (``GetGUIThreadInfo``), and ``GetClipCursor``;
* the foreground window and the window under the pointer (class, pid, process name);
* the mouse buttons (``GetAsyncKeyState``) and whether the pointer moved.

It writes one timestamped line on every change (pointer motion is logged once per quiet stretch, not per sample) to
a log under the evidence layout (``tools/artifact_paths.py``: ``evidence/input/cursor_exit/<date>_<label>/``) and
mirrors it to the console. An "exit" is the moment the saver's last window leaves the pointer: the window under the
pointer stops belonging to the saver process (a Qt window of a ``--process`` match), or that process ends. For each
exit it prints the one-line verdict, e.g.::

    cursor after exit: hand, changed to arrow after 1834 ms (after a click)
    cursor after exit: arrow, changed to arrow after 0 ms

How to run it (Windows): start this first, then start the saver, then exit it with the path under test; leave the
mouse still for two seconds after exiting before touching it, so the verdict tells "by itself" from "after a move"
or "after a click". Ctrl+C ends the run and prints a summary of every exit.

    .venv\\Scripts\\python.exe tools\\cursor_exit_observer.py [--label esc_exit] [--duration-s 600]

Diagnostic only: zero cost to the product, nothing in the product imports it.
"""

from __future__ import annotations

import argparse
import ctypes
import os
import sys
import time
from ctypes import wintypes
from dataclasses import dataclass, field
from pathlib import Path

if str(Path(__file__).resolve().parents[1]) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools import artifact_paths  # noqa: E402  (stdlib-only path owner; no product code)


# Standard system cursors (winuser.h IDC_*). ``LoadCursorW(NULL, IDC_*)`` returns the shared handle Windows
# displays, so a displayed HCURSOR equal to one of these IS that standard shape.
IDC_NAMES: dict[int, str] = {
    32512: "arrow",
    32513: "ibeam",
    32514: "wait",
    32515: "cross",
    32516: "uparrow",
    32642: "size_nwse",
    32643: "size_nesw",
    32644: "size_we",
    32645: "size_ns",
    32646: "size_all",
    32648: "no",
    32649: "hand",
    32650: "app_starting",
    32651: "help",
}

CURSOR_SHOWING = 0x1
CURSOR_SUPPRESSED = 0x2
_PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
_GA_ROOT = 2
_VK_BUTTONS = ((0x01, "left"), (0x02, "right"), (0x04, "middle"))


class CURSORINFO(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("flags", wintypes.DWORD),
                ("hCursor", wintypes.HANDLE), ("ptScreenPos", wintypes.POINT)]


class GUITHREADINFO(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("flags", wintypes.DWORD), ("hwndActive", wintypes.HWND),
                ("hwndFocus", wintypes.HWND), ("hwndCapture", wintypes.HWND), ("hwndMenuOwner", wintypes.HWND),
                ("hwndMoveSize", wintypes.HWND), ("hwndCaret", wintypes.HWND), ("rcCaret", wintypes.RECT)]


class _Win32:
    """The handful of read-only user32/kernel32 calls, typed once."""

    def __init__(self) -> None:
        self.user32 = ctypes.WinDLL("user32", use_last_error=True)
        self.kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        u, k = self.user32, self.kernel32
        for name, args, result in (
            ("GetCursorInfo", [ctypes.POINTER(CURSORINFO)], wintypes.BOOL),
            ("GetCursorPos", [ctypes.POINTER(wintypes.POINT)], wintypes.BOOL),
            ("LoadCursorW", [wintypes.HINSTANCE, wintypes.LPVOID], wintypes.HANDLE),
            ("GetGUIThreadInfo", [wintypes.DWORD, ctypes.POINTER(GUITHREADINFO)], wintypes.BOOL),
            ("GetClipCursor", [ctypes.POINTER(wintypes.RECT)], wintypes.BOOL),
            ("GetForegroundWindow", [], wintypes.HWND),
            ("WindowFromPoint", [wintypes.POINT], wintypes.HWND),
            ("GetAncestor", [wintypes.HWND, wintypes.UINT], wintypes.HWND),
            ("GetClassNameW", [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int], ctypes.c_int),
            ("GetWindowThreadProcessId", [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)], wintypes.DWORD),
            ("GetAsyncKeyState", [ctypes.c_int], ctypes.c_short),
            ("GetSystemMetrics", [ctypes.c_int], ctypes.c_int),
        ):
            function = getattr(u, name)
            function.argtypes, function.restype = args, result
        for name, args, result in (
            ("OpenProcess", [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD], wintypes.HANDLE),
            ("QueryFullProcessImageNameW",
             [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)], wintypes.BOOL),
            ("CloseHandle", [wintypes.HANDLE], wintypes.BOOL),
        ):
            function = getattr(k, name)
            function.argtypes, function.restype = args, result
        self.standard = {}
        for idc, name in IDC_NAMES.items():
            handle = u.LoadCursorW(None, ctypes.c_void_p(idc))
            if handle:
                self.standard[int(handle)] = name
        self._names: dict[int, str] = {}

    def cursor(self) -> tuple[str, int, int]:
        """(name, flags, handle) of the cursor Windows displays."""
        info = CURSORINFO()
        info.cbSize = ctypes.sizeof(CURSORINFO)
        if not self.user32.GetCursorInfo(ctypes.byref(info)):
            return "unreadable", 0, 0
        handle = int(info.hCursor or 0)
        if not handle:
            return "none", int(info.flags), 0
        return self.standard.get(handle, f"custom:{handle:#x}"), int(info.flags), handle

    def pointer(self) -> tuple[int, int]:
        point = wintypes.POINT()
        self.user32.GetCursorPos(ctypes.byref(point))
        return int(point.x), int(point.y)

    def thread_capture(self, thread_id: int) -> int:
        info = GUITHREADINFO()
        info.cbSize = ctypes.sizeof(GUITHREADINFO)
        if not self.user32.GetGUIThreadInfo(thread_id, ctypes.byref(info)):
            return 0
        return int(info.hwndCapture or 0)

    def clip(self) -> tuple[int, int, int, int] | None:
        """The ClipCursor rect, or None when it is the whole virtual desktop (no confinement)."""
        rect = wintypes.RECT()
        if not self.user32.GetClipCursor(ctypes.byref(rect)):
            return None
        left, top = self.user32.GetSystemMetrics(76), self.user32.GetSystemMetrics(77)
        desktop = (left, top, left + self.user32.GetSystemMetrics(78), top + self.user32.GetSystemMetrics(79))
        value = (int(rect.left), int(rect.top), int(rect.right), int(rect.bottom))
        return None if value == desktop else value

    def class_name(self, hwnd: int) -> str:
        if not hwnd:
            return ""
        buffer = ctypes.create_unicode_buffer(256)
        self.user32.GetClassNameW(hwnd, buffer, 256)
        return buffer.value

    def owner(self, hwnd: int) -> tuple[int, int]:
        """(thread id, pid) of ``hwnd``."""
        if not hwnd:
            return 0, 0
        pid = wintypes.DWORD(0)
        thread = self.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        return int(thread), int(pid.value)

    def process_name(self, pid: int) -> str:
        if pid <= 0:
            return ""
        cached = self._names.get(pid)
        if cached is not None:
            return cached
        name = "?"
        handle = self.kernel32.OpenProcess(_PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if handle:
            try:
                size = wintypes.DWORD(1024)
                buffer = ctypes.create_unicode_buffer(size.value)
                if self.kernel32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)):
                    name = os.path.basename(buffer.value)
            finally:
                self.kernel32.CloseHandle(handle)
        self._names[pid] = name
        return name

    def pid_alive(self, pid: int) -> bool:
        return artifact_paths._pid_alive(pid)

    def buttons(self) -> tuple[str, ...]:
        return tuple(name for vk, name in _VK_BUTTONS if self.user32.GetAsyncKeyState(vk) & 0x8000)

    def under_pointer(self, point: tuple[int, int]) -> int:
        hwnd = int(self.user32.WindowFromPoint(wintypes.POINT(*point)) or 0)
        root = int(self.user32.GetAncestor(hwnd, _GA_ROOT) or 0) if hwnd else 0
        return root or hwnd


@dataclass(frozen=True)
class Sample:
    """One read of everything that decides what the pointer looks like. ``key()`` omits position and time."""

    t_ns: int
    cursor: str
    flags: int
    pointer: tuple[int, int]
    buttons: tuple[str, ...]
    capture: tuple[tuple[int, str, int], ...]      # (hwnd, class, pid) of each captured window seen
    clip: tuple[int, int, int, int] | None
    foreground: tuple[int, str, int, str]           # hwnd, class, pid, process
    under: tuple[int, str, int, str]

    def key(self) -> tuple:
        return (self.cursor, self.flags, self.buttons, self.capture, self.clip, self.foreground, self.under)


def read_sample(api: _Win32) -> Sample:
    name, flags, _handle = api.cursor()
    point = api.pointer()
    foreground = int(api.user32.GetForegroundWindow() or 0)
    under = api.under_pointer(point)
    fg_thread, fg_pid = api.owner(foreground)
    under_thread, under_pid = api.owner(under)
    captures = []
    for thread in dict.fromkeys(t for t in (fg_thread, under_thread) if t):
        hwnd = api.thread_capture(thread)
        if hwnd:
            captures.append((hwnd, api.class_name(hwnd), api.owner(hwnd)[1]))
    return Sample(
        t_ns=time.perf_counter_ns(), cursor=name, flags=flags, pointer=point, buttons=api.buttons(),
        capture=tuple(captures), clip=api.clip(),
        foreground=(foreground, api.class_name(foreground), fg_pid, api.process_name(fg_pid)),
        under=(under, api.class_name(under), under_pid, api.process_name(under_pid)),
    )


def describe_flags(flags: int) -> str:
    if flags & CURSOR_SHOWING:
        return "showing"
    if flags & CURSOR_SUPPRESSED:
        return "suppressed"
    return "hidden"


def describe(sample: Sample) -> str:
    def window(value: tuple[int, str, int, str]) -> str:
        hwnd, cls, pid, process = value
        return f"{hwnd:#x} {cls or '-'} pid={pid} {process or '-'}" if hwnd else "none"

    capture = ", ".join(f"{hwnd:#x} {cls} pid={pid}" for hwnd, cls, pid in sample.capture) or "none"
    clip = "none" if sample.clip is None else "x".join(str(v) for v in sample.clip)
    return (f"cursor={sample.cursor} ({describe_flags(sample.flags)}) buttons={'+'.join(sample.buttons) or '-'} "
            f"capture={capture} clip={clip} under=[{window(sample.under)}] "
            f"foreground=[{window(sample.foreground)}] at={sample.pointer[0]},{sample.pointer[1]}")


DEFAULT_PROCESSES = ("srpss", "shittyrandomphotoscreensaver", "python", "pythonw")


def is_saver_window(value: tuple[int, str, int, str], processes: tuple[str, ...]) -> bool:
    """A Qt top-level window of a process whose image name starts with one of ``processes``."""
    _hwnd, cls, _pid, process = value
    stem = process.lower()
    return cls.startswith("Qt") and "QWindow" in cls and any(stem.startswith(p) for p in processes)


@dataclass
class ExitWatch:
    """One exit edge and what the displayed cursor did after it."""

    t_ns: int
    reason: str
    cursor_at_exit: str
    moved: bool = False
    clicked: bool = False
    arrow_ns: int | None = None
    cause: str = ""

    def verdict(self) -> str:
        if self.arrow_ns is None:
            return f"cursor after exit: {self.cursor_at_exit}, never changed to arrow while observed"
        ms = (self.arrow_ns - self.t_ns) / 1e6
        if self.cause == "click":
            return f"cursor after exit: {self.cursor_at_exit}, changed to arrow only after click ({ms:.0f} ms)"
        suffix = " (after a pointer move, no click)" if self.cause == "move" else ""
        return f"cursor after exit: {self.cursor_at_exit}, changed to arrow after {ms:.0f} ms{suffix}"


@dataclass
class Observer:
    """Pure state machine over samples (testable without Win32)."""

    processes: tuple[str, ...] = DEFAULT_PROCESSES
    lines: list[str] = field(default_factory=list)
    exits: list[ExitWatch] = field(default_factory=list)
    _last: Sample | None = None
    _saver_pid: int = 0
    _moving: bool = False
    _start_ns: int = 0
    _pending: ExitWatch | None = None

    def _emit(self, sample: Sample, text: str) -> str:
        line = f"{(sample.t_ns - self._start_ns) / 1e6:10.1f} ms  {text}"
        self.lines.append(line)
        return line

    def feed(self, sample: Sample, *, saver_alive: bool | None = None) -> list[str]:
        out: list[str] = []
        if self._last is None:
            self._start_ns = sample.t_ns
            out.append(self._emit(sample, "start  " + describe(sample)))
        else:
            last = self._last
            if sample.pointer != last.pointer:
                if not self._moving:
                    self._moving = True
                    out.append(self._emit(sample, f"pointer moving  at={sample.pointer[0]},{sample.pointer[1]}"))
                if self._pending is not None:
                    self._pending.moved = True
            else:
                self._moving = False
            if sample.buttons and not last.buttons and self._pending is not None:
                self._pending.clicked = True
            if sample.key() != last.key():
                out.append(self._emit(sample, describe(sample)))

        # Exit edges: the saver's window leaves the pointer, or the saver process ends.
        if is_saver_window(sample.under, self.processes):
            self._saver_pid = sample.under[2]
            if self._pending is not None and self._pending.arrow_ns is None:
                self._pending = None              # the pointer went back over a saver window (multi-display)
        elif self._saver_pid and self._pending is None and (
                self._last is not None and is_saver_window(self._last.under, self.processes)):
            self._start_exit(sample, "saver window left the pointer", out)
        if self._saver_pid and saver_alive is False:
            if self._pending is None:
                self._start_exit(sample, "saver process ended", out)
            self._saver_pid = 0

        watch = self._pending
        if watch is not None and watch.arrow_ns is None and sample.cursor == "arrow":
            watch.arrow_ns = sample.t_ns
            watch.cause = "click" if watch.clicked else ("move" if watch.moved else "")
            out.append(self._emit(sample, "VERDICT  " + watch.verdict()))
            self._pending = None
        self._last = sample
        return out

    def _start_exit(self, sample: Sample, reason: str, out: list[str]) -> None:
        watch = ExitWatch(t_ns=sample.t_ns, reason=reason, cursor_at_exit=sample.cursor)
        self.exits.append(watch)
        self._pending = watch
        out.append(self._emit(sample, f"EXIT ({reason}) cursor={sample.cursor}"))

    def finish(self, sample: Sample | None) -> list[str]:
        out = []
        if self._pending is not None and sample is not None:
            out.append(self._emit(sample, "VERDICT  " + self._pending.verdict()))
            self._pending = None
        return out


def _parse(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("--label", default="run", help="slug for the evidence folder name")
    parser.add_argument("--out", type=artifact_paths.evidence_arg, default=None,
                        help="evidence folder (default: evidence/input/cursor_exit/<date>_<label>_<time>/)")
    parser.add_argument("--duration-s", type=float, default=600.0, help="stop after this many seconds")
    parser.add_argument("--interval-ms", type=float, default=10.0, help="sampling interval")
    parser.add_argument("--process", action="append", default=None,
                        help="saver process image-name prefix (repeatable); default: "
                             + ", ".join(DEFAULT_PROCESSES))
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    if sys.platform != "win32":
        print("cursor_exit_observer reads the Windows cursor; nothing to observe on this platform.")
        return 0
    args = _parse(argv)
    folder = artifact_paths.output_dir(args.out, "input", "cursor_exit", artifact_paths.run_label(args.label))
    log_path = folder / "cursor_exit_observer.log"
    api = _Win32()
    observer = Observer(processes=tuple(p.lower() for p in (args.process or DEFAULT_PROCESSES)))
    winmm = ctypes.WinDLL("winmm")
    winmm.timeBeginPeriod(1)
    interval = max(0.001, args.interval_ms / 1000.0)
    deadline = time.monotonic() + max(0.0, args.duration_s)
    print(f"observing the displayed cursor every {args.interval_ms:g} ms; log: {log_path}  (Ctrl+C ends)")
    sample = None
    try:
        with open(log_path, "w", encoding="utf-8") as log:
            try:
                while time.monotonic() < deadline:
                    sample = read_sample(api)
                    pid = observer._saver_pid
                    alive = api.pid_alive(pid) if pid else None
                    for line in observer.feed(sample, saver_alive=alive):
                        print(line)
                        log.write(line + "\n")
                    log.flush()
                    time.sleep(interval)
            except KeyboardInterrupt:
                pass
            for line in observer.finish(sample):
                print(line)
                log.write(line + "\n")
            summary = ["", f"exits observed: {len(observer.exits)}"]
            summary += [f"  {index + 1}. {watch.reason}: {watch.verdict()}"
                        for index, watch in enumerate(observer.exits)]
            for line in summary:
                print(line)
                log.write(line + "\n")
    finally:
        winmm.timeEndPeriod(1)
    print(f"log: {log_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
