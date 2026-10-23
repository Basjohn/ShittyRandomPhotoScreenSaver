"""Record every top-level window this process creates/shows while Settings opens.

Opens the real ``SettingsDialog`` against an isolated copy of a saved profile
(``SettingsManager(storage_base_dir=...)``) and installs an out-of-context
WinEvent hook for this process only. Unlike polling observers, WinEvent
callbacks catch single-frame flashes. The dialog is shown on screen.

``--launch`` instead starts the real Settings process (``main.py /c``) and
hooks that child process from outside, covering startup before the dialog.
The saved profile file is backed up first and restored afterwards, because
closing Settings may persist UI state.

Usage:
  python tools/settings_window_probe.py --launch --out <report.json> [--launch-s 12]
  python tools/settings_window_probe.py --out <report.json>
      [--profile-settings <settings_v2.json>] [--opens 2] [--tabs]
      [--dwell-ms 1500]

The report lists each top-level CREATE/SHOW/HIDE/DESTROY with class, title,
rect and the probe phase it occurred in, plus a per-open summary of shown
top-levels other than the dialog itself.
"""
from __future__ import annotations

import argparse
import ctypes
import json
import os
import shutil
import sys
import tempfile
import time
from ctypes import wintypes
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

EVENT_OBJECT_CREATE = 0x8000
EVENT_OBJECT_DESTROY = 0x8001
EVENT_OBJECT_SHOW = 0x8002
EVENT_OBJECT_HIDE = 0x8003
WINEVENT_OUTOFCONTEXT = 0x0000
OBJID_WINDOW = 0
GA_ROOT = 2
_EVENT_NAMES = {
    EVENT_OBJECT_CREATE: "create",
    EVENT_OBJECT_DESTROY: "destroy",
    EVENT_OBJECT_SHOW: "show",
    EVENT_OBJECT_HIDE: "hide",
}

WinEventProc = ctypes.WINFUNCTYPE(
    None,
    wintypes.HANDLE,
    wintypes.DWORD,
    wintypes.HWND,
    wintypes.LONG,
    wintypes.LONG,
    wintypes.DWORD,
    wintypes.DWORD,
)
user32.SetWinEventHook.restype = wintypes.HANDLE
user32.SetWinEventHook.argtypes = [
    wintypes.DWORD, wintypes.DWORD, wintypes.HMODULE, WinEventProc,
    wintypes.DWORD, wintypes.DWORD, wintypes.DWORD,
]
user32.UnhookWinEvent.argtypes = [wintypes.HANDLE]
user32.GetAncestor.restype = wintypes.HWND
user32.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]


def _text(fn, hwnd, size=256) -> str:
    buf = ctypes.create_unicode_buffer(size)
    fn(hwnd, buf, size)
    return buf.value


def _rect(hwnd) -> list[int]:
    rect = wintypes.RECT()
    if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
        return [0, 0, 0, 0]
    return [rect.left, rect.top, rect.right, rect.bottom]


class Recorder:
    """``pid=0`` hooks every process; events then carry their owning pid."""

    def __init__(self, pid: int | None = None) -> None:
        self.pid = os.getpid() if pid is None else pid
        self.phase = "init"
        self.t0 = time.perf_counter()
        self.events: list[dict] = []
        self._proc = WinEventProc(self._callback)
        self._hook = None

    def _callback(self, _hook, event, hwnd, id_object, id_child, _thread, _time) -> None:
        if id_object != OBJID_WINDOW or id_child != 0 or not hwnd:
            return
        if event != EVENT_OBJECT_DESTROY and user32.GetAncestor(hwnd, GA_ROOT) != hwnd:
            return
        owner = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
        self.events.append({
            "pid": int(owner.value),
            "t_ms": round((time.perf_counter() - self.t0) * 1000.0, 2),
            "phase": self.phase,
            "event": _EVENT_NAMES.get(event, hex(event)),
            "hwnd": int(hwnd),
            "class": _text(user32.GetClassNameW, hwnd),
            # InternalGetWindowText never sends WM_GETTEXT, which can block
            # inside this callback on a window owned by another thread.
            "title": _text(user32.InternalGetWindowText, hwnd),
            "rect": _rect(hwnd),
        })

    def start(self) -> None:
        self._hook = user32.SetWinEventHook(
            EVENT_OBJECT_CREATE, EVENT_OBJECT_HIDE, None, self._proc,
            self.pid, 0, WINEVENT_OUTOFCONTEXT,
        )
        if not self._hook:
            raise OSError("SetWinEventHook failed")

    def stop(self) -> None:
        if self._hook:
            user32.UnhookWinEvent(self._hook)
            self._hook = None


def _visible_bucket_toggles(container):
    from PySide6.QtWidgets import QToolButton

    return [
        button for button in container.findChildren(QToolButton)
        if getattr(button, "_srpss_bucket_body", None) is not None and button.isVisible()
    ]


def _open_bucket_path(dialog, app) -> list[str]:
    """Expand one top-level bucket and one nested bucket on the current tab."""
    opened: list[str] = []
    container = dialog.content_stack.currentWidget()
    for _depth in range(2):
        toggles = _visible_bucket_toggles(container)
        if not toggles:
            if not opened:
                key = dialog._tab_keys[dialog.content_stack.currentIndex()]
                opened.append(f"<no visible bucket on tab {key!r}>")
            break
        toggle = toggles[0]
        if not toggle.isChecked():
            toggle.click()
        _pump(app, 300)
        opened.append(toggle.text())
        container = toggle._srpss_bucket_body
    return opened


def _pump(app, ms: int) -> None:
    deadline = time.perf_counter() + ms / 1000.0
    while time.perf_counter() < deadline:
        app.processEvents()
        time.sleep(0.005)


def _pump_native(seconds: float) -> None:
    """Out-of-context WinEvent callbacks arrive through this thread's queue."""
    msg = wintypes.MSG()
    deadline = time.perf_counter() + seconds
    while time.perf_counter() < deadline:
        while user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 1):
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))
        time.sleep(0.002)


def _visible_toplevels(pid: int) -> list[int]:
    found: list[int] = []
    enum_proc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def _visit(hwnd, _lparam):
        owner = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
        if owner.value == pid and user32.IsWindowVisible(hwnd):
            found.append(int(hwnd))
        return True

    user32.EnumWindows(enum_proc(_visit), 0)
    return found


def run_launch(args) -> int:
    import subprocess

    profile = Path(os.environ["APPDATA"]) / args.profile_folder / "settings_v2.json"
    backup = profile.read_bytes() if profile.exists() else None
    import psutil

    # Hook all processes: a venv python.exe is a redirector whose child runs
    # the real interpreter, so the launched pid alone owns no windows.
    recorder = Recorder(0)
    recorder.phase = "launch"
    recorder.start()
    command = ([sys.executable, str(Path(args.launch_script).resolve())] if args.launch_script
               else [sys.executable, str(ROOT / "main.py"), "/c"])
    child = subprocess.Popen(command, cwd=str(ROOT))
    tree = {child.pid}
    try:
        deadline = time.perf_counter() + args.launch_s
        while time.perf_counter() < deadline:
            _pump_native(0.25)
            try:
                tree |= {proc.pid for proc in psutil.Process(child.pid).children(recursive=True)}
            except psutil.Error:
                pass
        visible = [hwnd for pid in tree for hwnd in _visible_toplevels(pid)]
        recorder.phase = "close"
        for hwnd in visible:
            user32.PostMessageW(hwnd, 0x0010, 0, 0)  # WM_CLOSE
        _pump_native(3.0)
    finally:
        recorder.stop()
        if child.poll() is None:
            child.kill()
        child.wait(timeout=10)
        if backup is not None:
            profile.write_bytes(backup)

    recorder.events = [event for event in recorder.events if event["pid"] in tree]
    shows = [event for event in recorder.events if event["event"] == "show"]
    report = {"mode": "launch", "pid": child.pid, "process_tree": sorted(tree), "visible_at_close": visible,
              "shows": shows, "events": recorder.events}
    Path(args.out).write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"launch pid={child.pid} top-level shows={len(shows)} visible at close={len(visible)}")
    for event in shows:
        print(f"  {event['t_ms']:9.1f}ms {event['class']:<36} {event['title']!r} {event['rect']}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", required=True)
    parser.add_argument("--profile-settings", default=None,
                        help="settings_v2.json to copy (default: the real SRPSS profile)")
    parser.add_argument("--opens", type=int, default=2)
    parser.add_argument("--tabs", action="store_true", help="visit every tab after opening")
    parser.add_argument("--tab", default=None, help="switch to this tab key before --open-bucket")
    parser.add_argument("--open-bucket", action="store_true",
                        help="in each open, expand the first visible bucket and its first nested "
                             "bucket so the next open restores an expanded editing path")
    parser.add_argument("--dwell-ms", type=int, default=1500)
    parser.add_argument("--launch", action="store_true",
                        help="hook a real `main.py /c` child process instead")
    parser.add_argument("--launch-s", type=float, default=12.0)
    parser.add_argument("--launch-script", default=None,
                        help="python script to launch instead of `main.py /c` (e.g. an MC run "
                             "script that requests Settings in the running saver)")
    parser.add_argument("--profile-folder", default="SRPSS",
                        help="AppData folder whose settings_v2.json is backed up/restored")
    parser.add_argument("--self-test", action="store_true",
                        help="first flash one unparented QWidget; the probe must record it")
    parser.add_argument("--hang-dump-s", type=float, default=90.0,
                        help="dump all thread stacks and exit if the probe exceeds this")
    args = parser.parse_args()

    import faulthandler

    faulthandler.dump_traceback_later(args.hang_dump_s, exit=True)
    if args.launch:
        try:
            return run_launch(args)
        finally:
            faulthandler.cancel_dump_traceback_later()

    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication(sys.argv)
    recorder = Recorder()
    recorder.start()

    self_test = None
    if args.self_test:
        from PySide6.QtWidgets import QWidget

        recorder.phase = "self-test"
        flash = QWidget()
        flash.resize(24, 24)
        flash.setVisible(True)
        _pump(app, 50)
        flash.hide()
        flash.deleteLater()
        _pump(app, 50)
        caught = [e for e in recorder.events if e["phase"] == "self-test" and e["event"] == "show"]
        self_test = {"caught_shows": len(caught)}
        print(f"self-test: unparented QWidget show events recorded={len(caught)}", flush=True)
        if not caught:
            raise SystemExit("self-test failed: the hook did not record a known top-level show")

    source = Path(args.profile_settings) if args.profile_settings else (
        Path(os.environ["APPDATA"]) / "SRPSS" / "settings_v2.json"
    )
    base = Path(tempfile.mkdtemp(prefix="srpss_settings_probe_"))
    (base / "SRPSS").mkdir(parents=True)
    if source.exists():
        shutil.copy2(source, base / "SRPSS" / "settings_v2.json")

    from core.animation.animator import AnimationManager
    from core.settings import SettingsManager
    from ui.settings_dialog import SettingsDialog

    opens = []
    try:
        for index in range(max(1, args.opens)):
            settings = SettingsManager(application="Screensaver", storage_base_dir=base)
            animations = AnimationManager(owner="settings:probe")
            recorder.phase = f"open{index}:construct"
            mark = len(recorder.events)
            dialog = SettingsDialog(settings, animations)
            recorder.phase = f"open{index}:show"
            dialog.show()
            _pump(app, args.dwell_ms)
            dialog_hwnd = int(dialog.winId())
            if args.tab:
                dialog._resolve_leaving_widget_page = lambda: True
                recorder.phase = f"open{index}:tab:{args.tab}"
                dialog._switch_tab(dialog._tab_keys.index(args.tab), animate=False)
                _pump(app, 600)
            if args.open_bucket:
                recorder.phase = f"open{index}:open-bucket"
                print(f"[probe] {recorder.phase}: {_open_bucket_path(dialog, app)}", flush=True)
            if args.tabs:
                dialog._resolve_leaving_widget_page = lambda: True
                for tab_index, key in enumerate(dialog._tab_keys):
                    recorder.phase = f"open{index}:tab:{key}"
                    print(f"[probe] {recorder.phase}", flush=True)
                    dialog._switch_tab(tab_index, animate=False)
                    _pump(app, 600)
            recorder.phase = f"open{index}:close"
            dialog.close()
            dialog.deleteLater()
            animations.stop()
            _pump(app, 400)
            shown = [
                event for event in recorder.events[mark:]
                if event["event"] == "show" and event["hwnd"] != dialog_hwnd
            ]
            opens.append({"dialog_hwnd": dialog_hwnd, "other_toplevel_shows": shown})
    finally:
        recorder.stop()
        shutil.rmtree(base, ignore_errors=True)

    report = {"pid": recorder.pid, "self_test": self_test, "source_settings": str(source), "opens": opens,
              "events": recorder.events}
    faulthandler.cancel_dump_traceback_later()
    Path(args.out).write_text(json.dumps(report, indent=2), encoding="utf-8")
    for index, entry in enumerate(opens):
        print(f"open{index}: dialog={entry['dialog_hwnd']} other top-level shows={len(entry['other_toplevel_shows'])}")
        for event in entry["other_toplevel_shows"]:
            print(f"  {event['t_ms']:9.1f}ms {event['phase']:<28} {event['class']:<36} "
                  f"{event['title']!r} {event['rect']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
