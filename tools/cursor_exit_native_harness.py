"""Native reproduction of "the cursor keeps its changed shape after exit" (opt-in, Windows, agent/operator-run).

Not part of any test run. Each trial starts a child process that drives the PRODUCTION Quick display owners
(``QuickDisplayRuntime``: input controller, cursor controller, auxiliary Halo admission, QML ``cursorShape`` items,
``close_runtime`` -> ``QuickDisplayWindow.queue_close``) on one small real window, while this parent process reads
with Win32 only (``tools/cursor_exit_observer.py``) what Windows DISPLAYS as the cursor, before, during and for
1.5 s after the window is gone.

Limits (binding, Docs/Historical_Bugs/R-183): the window is at most 320x200 device px, created centred on the
current pointer position (the pointer is never moved: no ``SetCursorPos``/``SendInput``, no synthesized OS input;
Qt events are delivered in-process with ``sendEvent``), never fullscreen, non-activating
(``QuickWindowPolicy(always_on_top=False, accepts_focus=False)``: Frameless | SplashScreen |
WindowDoesNotAcceptFocus), alive at most 2 s, at most 20 trials per run (``--trials`` is capped), and a trial
is discarded when the pointer moved between "shape shown" and the end of observation (``GetCursorPos``). A trial
starts only after the pointer has been still for ``--still-s`` seconds.

Exit paths (``--path``; ``all`` runs each once):

* ``esc_hand``   interaction mode, pointer over a link (QML ``HoverHandler { cursorShape: PointingHandCursor }``),
                 Esc through ``QuickDisplayWindow.keyPressEvent`` -> input controller -> ``exit_requested``.
* ``esc_halo``   interaction mode, pointer over the scene (the native Halo from ``QuickCursorController``), Esc.
* ``link_hand``  interaction mode, press + release on a link ``MouseArea`` whose ``onClicked`` runs the product
                 action ``dispatch_feed_url_product_action`` (browser launch STUBBED, never opened) and its
                 ``request_saver_exit``; Qt's implicit press capture is taken/released exactly as Qt's Windows
                 pointer handler does (before the press, before the release).
* ``click_blank`` non-interaction mode, left press exit while Qt's press capture is held (blank cursor).
* ``move_blank`` non-interaction mode, motion beyond the exit threshold.
* ``stay_hand`` / ``stay_halo``  the runtime retires but the process keeps running (Settings open, Edit exit,
                 Media Center exit: ``engine_lifecycle.stop(exit_app=False)`` retires the generation the same way).

Every path ends in the production retire sequence (``DisplayManager.cleanup``'s ``quiesce()`` then ``retire()``:
``QuickDisplayRuntime.quiesce_for_runtime_pause()`` then ``close_runtime()``); process-exit paths then quit the
application once ``retirement_completed`` arrives (``request_application_quit`` after the terminal barrier), and
the child process ends.

Options:

* ``--production-flags``: the production window policy (Frameless | SplashScreen | WindowStaysOnTopHint, accepts
  focus) and activation, still 320x200 at most. It takes the keyboard focus for at most 2 s.
* priming (default): Windows does not re-hit-test a still pointer when a window appears under it, so the child
  takes and releases its own window's mouse capture once (Qt's own SetCapture/ReleaseCapture) to make Windows
  re-hit-test where the pointer is; ``--no-prime`` skips it. With a non-activating window priming is unreliable
  (it works only while that window may take capture); an activating window is hit-tested on activation anyway.
* ``--qt-leave``: post one WM_MOUSELEAVE to the child's own window after the shape shows, so Qt believes the
  pointer left while Windows still shows the shape: the state in which ``QWindow.setCursor`` stops reaching
  Windows (R-183).
* ``--verbose``: the child's Qt edges (enter/leave/cursor change/hide), each with what Windows displayed then.

Each result line reads ``STUCK`` when the shape Windows shows at the end is one the saver window displayed (not
the arrow, not what was there before it appeared).

    .venv\\Scripts\\python.exe tools\\cursor_exit_native_harness.py --path all --verbose
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import cursor_exit_observer as observer  # noqa: E402  (ctypes only)

PATHS = ("esc_hand", "esc_halo", "link_hand", "click_blank", "move_blank", "stay_hand", "stay_halo")
MAX_TRIALS = 20
MAX_WINDOW_DEVICE_PX = (320, 200)
WINDOW_LIFE_S = 2.0
OBSERVE_AFTER_S = 1.5


# --------------------------------------------------------------------------------------------- child (Qt) side


_LINK_QML = b"""
import QtQuick
Item {
    id: root
    signal linkClicked()
    Rectangle { anchors.fill: parent; color: "#1d2b38"; border.color: "#5a7da0"; border.width: 2 }
    MouseArea {
        anchors.fill: parent
        hoverEnabled: true
        acceptedButtons: Qt.LeftButton
        cursorShape: Qt.PointingHandCursor
        onClicked: root.linkClicked()
    }
}
"""

_SCENE_QML = b"""
import QtQuick
Item { Rectangle { anchors.fill: parent; color: "#1d2b38"; border.color: "#5a7da0"; border.width: 2 } }
"""


def _emit(event: str, **fields) -> None:
    fields.update(event=event, t_ns=time.perf_counter_ns())
    sys.stdout.write(json.dumps(fields) + "\n")
    sys.stdout.flush()


def _child(path: str, production_flags: bool = False, prime_pointer: bool = True, qt_leave: bool = False) -> int:
    from rendering.quick.bootstrap import configure_quick_graphics

    configure_quick_graphics(reason="cursor-exit-native-harness")
    from PySide6.QtCore import QEvent, QObject, QPointF, QRect, Qt, QTimer, QUrl
    from PySide6.QtGui import QCursor, QGuiApplication, QKeyEvent, QMouseEvent
    from PySide6.QtQml import QQmlComponent, qmlEngine
    from PySide6.QtWidgets import QApplication

    from core.widget_product_actions import dispatch_feed_url_product_action
    from rendering.quick.runtime import QuickDisplayRuntime
    from rendering.quick.scene_controller import QuickSceneFactory
    from rendering.quick.state import QuickWindowPolicy

    api = observer._Win32()
    app = QApplication(sys.argv[:1])
    shape = path.rsplit("_", 1)[1]
    interaction = shape in ("hand", "halo")
    stays = path.startswith("stay_")
    pos = QCursor.pos()
    screen = QGuiApplication.screenAt(pos) or app.primaryScreen()
    dpr = float(screen.devicePixelRatio())
    width = int(MAX_WINDOW_DEVICE_PX[0] / dpr) - 2
    height = int(MAX_WINDOW_DEVICE_PX[1] / dpr) - 2
    factory = QuickSceneFactory()
    runtime = QuickDisplayRuntime(
        screen_index=0, runtime_generation=1830, screen=screen, scene_factory=factory,
        window_policy=(QuickWindowPolicy() if production_flags
                       else QuickWindowPolicy(always_on_top=False, accepts_focus=False, blank_cursor=True)),
        interaction_mode_enabled=interaction,
    )
    window = runtime.window
    window.setGeometry(QRect(pos.x() - width // 2, pos.y() - height // 2, width, height))
    component = QQmlComponent(qmlEngine(runtime.scene_controller.scene_root))
    component.setData(_LINK_QML if shape == "hand" else _SCENE_QML, QUrl())
    item = component.create()
    if item is None:
        _emit("abort", why="qml: " + "; ".join(e.toString() for e in component.errors()))
        return 2
    item.setParentItem(window.contentItem())
    item.setWidth(width)
    item.setHeight(height)
    hwnd = int(window.winId())
    state = {"triggered": False, "gone": False}

    def exit_chain() -> None:
        # Production: exit_requested -> DisplayManager._on_exit_requested -> ScreensaverEngine.stop() ->
        # teardown_display_runtime: DisplayManager.quiesce_all() and then DisplayManager.cleanup(), which per
        # unit runs quiesce() (QuickDisplayRuntime.quiesce_for_runtime_pause) and retire()
        # (QuickDisplayRuntime.close_runtime), synchronously (direct connections, no event-loop turn).
        _emit("exit_requested")
        runtime.quiesce_for_runtime_pause()
        runtime.close_runtime()
        _emit("close_runtime_returned", capture=int(api.user32.GetCapture() or 0), native=api.cursor()[0])

    def on_retired(*_args) -> None:
        state["gone"] = True
        _emit("retired")
        if stays:
            QTimer.singleShot(int(OBSERVE_AFTER_S * 1000) + 100, app.quit)
        else:
            app.quit()

    def link_clicked() -> None:
        _emit("link_clicked")
        dispatch_feed_url_product_action(
            "https://example.invalid/srpss-cursor-harness",
            opener=lambda _url: True,          # the browser launch is stubbed: nothing is opened
            request_saver_exit=exit_chain,
            interactive_build=False,
        )

    class _Spy(QObject):
        """Harness-only: report the Qt pointer/cursor edges this window receives, with the native cursor."""

        _KINDS = {QEvent.Type.Enter: "enter", QEvent.Type.Leave: "leave", QEvent.Type.CursorChange: "cursor_change",
                  QEvent.Type.Hide: "hide", QEvent.Type.MouseButtonPress: "press",
                  QEvent.Type.MouseButtonRelease: "release", QEvent.Type.UngrabMouse: "ungrab"}

        def __init__(self) -> None:
            super().__init__()
            self.moves = 0

        def eventFilter(self, watched, event):
            kind = event.type()
            if kind == QEvent.Type.MouseMove:
                self.moves += 1
                if self.moves <= 3:
                    _emit("qt_move", native=api.cursor()[0])
            elif kind in self._KINDS:
                _emit("qt_" + self._KINDS[kind], native=api.cursor()[0], qt=str(watched.cursor().shape().name),
                      capture=int(api.user32.GetCapture() or 0))
            return False

    spy = _Spy()
    window.installEventFilter(spy)                # runs before the window's own filter; never consumes
    runtime.exit_requested.connect(exit_chain)
    runtime.retirement_completed.connect(on_retired)
    window.visibleChanged.connect(lambda visible: _emit("visible", value=bool(visible)))
    window.destroyed.connect(lambda *_: _emit("window_destroyed"))
    if shape == "hand":
        item.linkClicked.connect(link_clicked)

    local = QPointF(width / 2.0, height / 2.0)

    def mouse(kind, local_pos, button, buttons):
        return QMouseEvent(kind, local_pos, QPointF(window.mapToGlobal(local_pos.toPoint())),
                           button, buttons, Qt.KeyboardModifier.NoModifier)

    def trigger() -> None:
        state["triggered"] = True
        _emit("trigger", path=path)
        if path in ("esc_hand", "esc_halo"):
            QGuiApplication.sendEvent(window, QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Escape,
                                                         Qt.KeyboardModifier.NoModifier))
        elif path == "link_hand":
            window.setMouseGrabEnabled(True)               # Qt's AutoMouseCapture before delivering the press
            QGuiApplication.sendEvent(window, mouse(QEvent.Type.MouseButtonPress, local, Qt.MouseButton.LeftButton,
                                                    Qt.MouseButton.LeftButton))
            window.setMouseGrabEnabled(False)              # ... and released before delivering the release
            QGuiApplication.sendEvent(window, mouse(QEvent.Type.MouseButtonRelease, local, Qt.MouseButton.LeftButton,
                                                    Qt.MouseButton.NoButton))
        elif path == "click_blank":
            window.setMouseGrabEnabled(True)
            QGuiApplication.sendEvent(window, mouse(QEvent.Type.MouseButtonPress, local, Qt.MouseButton.LeftButton,
                                                    Qt.MouseButton.LeftButton))
        elif path == "move_blank":
            for dx in (0.0, 10.0, 40.0, 80.0):
                if runtime.describe_runtime_state()["phase"] == "retiring":
                    break
                QGuiApplication.sendEvent(window, mouse(QEvent.Type.MouseMove, QPointF(local.x() + dx, local.y()),
                                                        Qt.MouseButton.NoButton, Qt.MouseButton.NoButton))
        elif stays:
            exit_chain()

    shown_ns = [0]

    def wait_for_shape() -> None:
        if state["triggered"]:
            return
        name, _flags, _handle = api.cursor()
        expected = {"hand": name == "hand", "halo": name.startswith("custom:"), "blank": name.startswith("custom:")}
        waited = (time.perf_counter_ns() - shown_ns[0]) / 1e9
        if expected[shape] and waited >= 0.25:
            _emit("ready", cursor=name)
            if qt_leave:
                # Diverge Qt's belief from Windows': Qt's pointer handler clears its window-under-mouse on
                # WM_MOUSELEAVE (qwindowspointerhandler.cpp), while Windows keeps displaying the shape. Every
                # QWindow.setCursor() is then stored but not applied (qwindowswindow.cpp applyNewCursor).
                api.user32.PostMessageW(hwnd, 0x02A3, 0, 0)
            # Let the shape settle for one beat, then exit.
            QTimer.singleShot(150, trigger)
            return
        if waited > 0.6 and not prime_pointer:
            # Unprimed: exit whatever Windows shows (the saver came up under a still pointer).
            _emit("ready", cursor=name, unprimed=True)
            QTimer.singleShot(150, trigger)
            return
        if waited > 0.9:
            _emit("abort", why=f"shape {shape!r} never displayed (cursor={name})")
            runtime.close_runtime()
            QTimer.singleShot(50, app.quit)
            return
        QTimer.singleShot(10, wait_for_shape)

    def deadline() -> None:
        if not state["gone"]:
            _emit("deadline")
            runtime.close_runtime()
            window.destroy()
            app.quit()

    runtime.auxiliary_controller.resume()     # QuickDisplayRuntime.show_on_screen's admission edge
    window.show()                             # not show_on_screen(): that applies the full-screen geometry
    if production_flags:
        window.requestActivate()              # the saver window is the foreground window, as in production
    shown_ns[0] = time.perf_counter_ns()
    rect = observer.wintypes.RECT()
    api.user32.GetWindowRect.argtypes = [observer.wintypes.HWND, observer.ctypes.POINTER(observer.wintypes.RECT)]
    api.user32.GetWindowRect(hwnd, observer.ctypes.byref(rect))
    _emit("shown", hwnd=hwnd, rect=[rect.left, rect.top, rect.right, rect.bottom])

    def prime() -> None:
        # Windows does not re-hit-test a still pointer when a window appears under it (no WM_MOUSEMOVE,
        # no WM_SETCURSOR; a TME_LEAVE request is answered with an immediate WM_MOUSELEAVE), so neither
        # Windows nor Qt learns that the pointer is over this window. Taking and releasing this window's
        # own mouse capture (Qt's own SetCapture/ReleaseCapture, as on every press) makes Windows re-hit-
        # test the pointer where it is: the window then gets WM_MOUSEMOVE + WM_SETCURSOR like after a
        # real motion. No OS input is synthesized and the pointer does not move.
        window.setMouseGrabEnabled(True)
        window.setMouseGrabEnabled(False)
        _emit("primed", native=api.cursor()[0])

    if prime_pointer:
        QTimer.singleShot(60, prime)
    QTimer.singleShot(10, wait_for_shape)
    QTimer.singleShot(int(WINDOW_LIFE_S * 1000) - 50, deadline)
    app.exec()
    _emit("exec_returned")
    return 0


# --------------------------------------------------------------------------------------------- parent (observer)


def _wait_still(api, still_s: float, max_wait_s: float) -> tuple[int, int] | None:
    start = time.monotonic()
    last = api.pointer()
    since = time.monotonic()
    while time.monotonic() - start < max_wait_s:
        time.sleep(0.02)
        now = api.pointer()
        if now != last:
            last, since = now, time.monotonic()
        elif time.monotonic() - since >= still_s:
            return now
    return None


def _trial(path: str, api, *, still_s: float, max_wait_s: float, production_flags: bool = False,
           prime: bool = True, qt_leave: bool = False) -> dict:
    point = _wait_still(api, still_s, max_wait_s)
    if point is None:
        return {"path": path, "status": "skipped", "why": f"pointer never still for {still_s}s"}
    events: list[dict] = []
    command = [sys.executable, str(Path(__file__).resolve()), "--child", path]
    if production_flags:
        command.append("--production-flags")
    if not prime:
        command.append("--no-prime")
    if qt_leave:
        command.append("--qt-leave")
    child = subprocess.Popen(command,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd=str(ROOT))

    def read() -> None:
        for line in child.stdout:
            line = line.strip()
            if line.startswith("{"):
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    pass

    reader = threading.Thread(target=read, daemon=True)
    reader.start()
    samples: list[tuple[int, str, tuple[int, int]]] = []
    ended_ns = None
    hard_stop = time.monotonic() + 30.0
    while time.monotonic() < hard_stop:
        name, _flags, _handle = api.cursor()
        samples.append((time.perf_counter_ns(), name, api.pointer()))
        if ended_ns is None and child.poll() is not None:
            ended_ns = time.perf_counter_ns()
        if ended_ns is not None and time.perf_counter_ns() - ended_ns > OBSERVE_AFTER_S * 1e9 + 0.2e9:
            break
        time.sleep(0.005)
    if child.poll() is None:
        child.kill()
    reader.join(timeout=2.0)
    stderr = child.stderr.read() if child.stderr else ""
    return _summarise(path, point, events, samples, ended_ns, stderr)


def _summarise(path, point, events, samples, ended_ns, stderr) -> dict:
    by = {}
    for event in events:
        by.setdefault(event["event"], event)
    result = {"path": path, "events": [(e["event"], e["t_ns"]) for e in events]}
    hidden = next((e for e in events if e["event"] == "visible" and e.get("value") is False), None)
    origin = hidden["t_ns"] if hidden else (samples[0][0] if samples else 0)
    result["child_events"] = [
        f"{(e['t_ns'] - origin) / 1e6:.1f} {e['event']}"
        + "".join(f" {k}={e[k]}" for k in ("native", "qt", "capture", "cursor", "why") if k in e)
        for e in events]
    first_move = next((s for s in samples if s[2] != point), None)
    result["pointer_first_moved_ms"] = None if first_move is None else round((first_move[0] - origin) / 1e6, 1)
    if "abort" in by or "ready" not in by:
        timeline, last = [], None
        for t_ns, name, _p in samples:
            if name != last:
                timeline.append((round((t_ns - origin) / 1e6, 1), name))
                last = name
        result.update(status="invalid", why=by.get("abort", {}).get("why", "no ready event"),
                      stderr=stderr[-1500:], timeline_ms_from_hide=timeline)
        return result
    ready_ns = by["ready"]["t_ns"]
    gone_event = by.get("window_destroyed") or by.get("retired")
    hidden_ns = hidden["t_ns"] if hidden else (gone_event or {}).get("t_ns", ended_ns)
    end_ns = (ended_ns or samples[-1][0])
    observed = [s for s in samples if s[0] >= ready_ns]
    moved = any(s[2] != point for s in observed)
    timeline = []
    last = None
    for t_ns, name, _p in samples:
        if name != last:
            timeline.append((round((t_ns - (hidden_ns or ready_ns)) / 1e6, 1), name))
            last = name
    final_name = samples[-1][1]
    trigger_ns = by.get("trigger", {}).get("t_ns", ready_ns)
    after_hidden = [s for s in samples if hidden_ns and s[0] >= hidden_ns]
    first_arrow = next((s for s in after_hidden if s[1] == "arrow"), None)
    process_end_rel = None if ended_ns is None else round((ended_ns - hidden_ns) / 1e6, 1) if hidden_ns else None
    result.update(
        status="discarded" if moved else "valid",
        why="pointer moved during the trial" if moved else "",
        cursor_ready=by["ready"]["cursor"],
        cursor_at_trigger=next((s[1] for s in samples if s[0] >= trigger_ns), None),
        cursor_final=final_name,
        arrow_after_hidden_ms=None if first_arrow is None else round((first_arrow[0] - hidden_ns) / 1e6, 1),
        process_end_after_hidden_ms=process_end_rel,
        observed_after_hidden_ms=round((samples[-1][0] - hidden_ns) / 1e6, 1) if hidden_ns else None,
        # Stuck: what Windows shows at the end is a shape this saver window displayed (seen while it was up,
        # and not what was shown before it appeared), not the arrow or the shape of the window now underneath.
        stuck=final_name != "arrow" and final_name in _saver_shapes(samples, by, hidden_ns),
        timeline_ms_from_hide=timeline,
    )
    return result


def _saver_shapes(samples, by, hidden_ns) -> set[str]:
    shown_ns = by.get("shown", {}).get("t_ns")
    if shown_ns is None or hidden_ns is None:
        return set()
    before = [s[1] for s in samples if s[0] < shown_ns]
    baseline = before[-1] if before else None
    return {s[1] for s in samples if shown_ns <= s[0] < hidden_ns} - {"arrow", baseline}


def _format(result: dict, *, verbose: bool = False) -> str:
    extra = ""
    if verbose and result.get("child_events"):
        extra = ("\n             child (ms from hide): " + "; ".join(result["child_events"])
                 + f"\n             pointer first moved at {result.get('pointer_first_moved_ms')} ms from hide")
    if result["status"] == "skipped":
        return f"{result['path']:12s} SKIPPED: {result.get('why', '')}"
    if result["status"] == "invalid":
        timeline = " -> ".join(f"{name}@{ms}" for ms, name in result.get("timeline_ms_from_hide", []))
        return (f"{result['path']:12s} INVALID: {result.get('why', '')}\n             native timeline: {timeline}"
                + extra)
    state = "STUCK" if result["stuck"] else "ok"
    arrow = result["arrow_after_hidden_ms"]
    text = (f"{result['path']:12s} {result['status']:9s} {state:5s} before={result['cursor_ready']} "
            f"after={result['cursor_final']} arrow_after_hide="
            f"{'never' if arrow is None else str(arrow) + ' ms'} "
            f"process_end_after_hide={result['process_end_after_hidden_ms']} ms "
            f"observed={result['observed_after_hidden_ms']} ms")
    timeline = " -> ".join(f"{name}@{ms}" for ms, name in result["timeline_ms_from_hide"])
    return text + "\n             timeline (ms from hide): " + timeline + extra


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Native cursor-at-exit reproduction (opt-in, Windows only).")
    parser.add_argument("--path", default="all", choices=("all",) + PATHS)
    parser.add_argument("--trials", type=int, default=1, help=f"trials per path (session cap {MAX_TRIALS})")
    parser.add_argument("--still-s", type=float, default=2.0, help="pointer stillness required before a trial")
    parser.add_argument("--max-wait-s", type=float, default=120.0, help="give up waiting for stillness after this")
    parser.add_argument("--verbose", action="store_true", help="print the child's Qt edges with the native cursor")
    parser.add_argument("--production-flags", action="store_true",
                        help="the production window policy (Frameless|SplashScreen|StaysOnTop, accepts focus) and "
                             "activation; the window is still 320x200 at most")
    parser.add_argument("--no-prime", action="store_true",
                        help="do not re-hit-test the still pointer after show (the saver appearing under an idle "
                             "pointer); the exit then runs on whatever Windows displays")
    parser.add_argument("--qt-leave", action="store_true",
                        help="after the shape shows, post WM_MOUSELEAVE to the harness's own window: Qt then "
                             "believes the pointer left while Windows still shows the shape")
    parser.add_argument("--child", default=None, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.child:
        return _child(args.child, production_flags=args.production_flags, prime_pointer=not args.no_prime,
                      qt_leave=args.qt_leave)
    if sys.platform != "win32":
        print("cursor_exit_native_harness reads the Windows cursor; nothing to do on this platform.")
        return 0
    api = observer._Win32()
    paths = PATHS if args.path == "all" else (args.path,)
    plan = [p for p in paths for _ in range(max(1, args.trials))][:MAX_TRIALS]
    print(f"{len(plan)} trial(s); keep the mouse still (each waits for {args.still_s:g}s of stillness)")
    results = []
    for path in plan:
        result = _trial(path, api, still_s=args.still_s, max_wait_s=args.max_wait_s,
                        production_flags=args.production_flags, prime=not args.no_prime, qt_leave=args.qt_leave)
        results.append(result)
        print(_format(result, verbose=args.verbose), flush=True)
        if result["status"] == "invalid" and result.get("stderr"):
            print(result["stderr"])
    valid = [r for r in results if r["status"] == "valid"]
    stuck = [r["path"] for r in valid if r["stuck"]]
    print(f"\nvalid trials: {len(valid)}/{len(results)}; stuck after exit: {', '.join(stuck) or 'none'}")
    return 1 if stuck else 0


if __name__ == "__main__":
    raise SystemExit(main())
