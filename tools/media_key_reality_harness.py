"""Observer-backed MC reality harness for U-05 media/key failures.

This harness does not treat synthetic key success as proof. It launches/focuses
MC, prepares the selected focused scenario, then watches real keyboard ingress
with a low-level Windows hook and correlates it with SRPSS logs.
"""

from __future__ import annotations

import argparse
import ctypes
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional


if os.name != "nt":
    raise SystemExit("This harness requires Windows.")


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from media_key_matrix_harness import (  # noqa: E402
    LogTail,
    WindowInfo,
    _apply_harness_safety_settings,
    _collect_tails,
    _evaluate_runtime_contract,
    _foreground_window,
    _force_foreground,
    _launch_runtime,
    _mirror_live_profile,
    _parse_log_hits,
    _parse_signal_counts,
    _scenario_cleanup,
    _scenario_prepare,
    _seed_profile_settings,
    _get_class,
    _get_pid,
    _get_rect,
    _get_text,
    _wait_for_log_file,
    _wait_for_optional_log_file,
    _wait_for_window,
)


user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

WH_KEYBOARD_LL = 13
WH_MOUSE_LL = 14
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
WM_SYSKEYDOWN = 0x0104
WM_SYSKEYUP = 0x0105
WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP = 0x0202
WM_RBUTTONDOWN = 0x0204
WM_RBUTTONUP = 0x0205
PM_REMOVE = 0x0001
LLKHF_INJECTED = 0x00000010
LLKHF_LOWER_IL_INJECTED = 0x00000002
LLMHF_INJECTED = 0x00000001
LLMHF_LOWER_IL_INJECTED = 0x00000002

VK_NAMES = {
    0x43: "C",
    0x53: "S",
    0xAD: "VOLUME_MUTE",
    0xAE: "VOLUME_DOWN",
    0xAF: "VOLUME_UP",
    0xB0: "MEDIA_NEXT_TRACK",
    0xB1: "MEDIA_PREV_TRACK",
    0xB2: "MEDIA_STOP",
    0xB3: "MEDIA_PLAY_PAUSE",
}


class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("vkCode", ctypes.c_ulong),
        ("scanCode", ctypes.c_ulong),
        ("flags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", ctypes.c_void_p),
    ]


class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


class MSG(ctypes.Structure):
    _fields_ = [
        ("hwnd", ctypes.c_void_p),
        ("message", ctypes.c_uint),
        ("wParam", ctypes.c_void_p),
        ("lParam", ctypes.c_void_p),
        ("time", ctypes.c_ulong),
        ("pt", POINT),
    ]


HOOKPROC = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p)

user32.CallNextHookEx.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p]
user32.CallNextHookEx.restype = ctypes.c_long
user32.SetWindowsHookExW.argtypes = [ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong]
user32.SetWindowsHookExW.restype = ctypes.c_void_p
user32.UnhookWindowsHookEx.argtypes = [ctypes.c_void_p]
user32.UnhookWindowsHookEx.restype = ctypes.c_bool
user32.WindowFromPoint.argtypes = [POINT]
user32.WindowFromPoint.restype = ctypes.c_void_p
if ctypes.sizeof(ctypes.c_void_p) == 8:
    _get_window_long_ptr = user32.GetWindowLongPtrW
else:
    _get_window_long_ptr = user32.GetWindowLongW
_get_window_long_ptr.argtypes = [ctypes.c_void_p, ctypes.c_int]
_get_window_long_ptr.restype = ctypes.c_longlong if ctypes.sizeof(ctypes.c_void_p) == 8 else ctypes.c_long

GWL_STYLE = -16
GWL_EXSTYLE = -20

WS_EX_ACCEPTFILES = 0x00000010
WS_EX_APPWINDOW = 0x00040000
WS_EX_NOACTIVATE = 0x08000000
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_TOPMOST = 0x00000008

WS_DISABLED = 0x08000000
WS_POPUP = 0x80000000
WS_VISIBLE = 0x10000000

STYLE_FLAGS = {
    "WS_DISABLED": WS_DISABLED,
    "WS_POPUP": WS_POPUP,
    "WS_VISIBLE": WS_VISIBLE,
}

EXSTYLE_FLAGS = {
    "WS_EX_ACCEPTFILES": WS_EX_ACCEPTFILES,
    "WS_EX_APPWINDOW": WS_EX_APPWINDOW,
    "WS_EX_NOACTIVATE": WS_EX_NOACTIVATE,
    "WS_EX_TOOLWINDOW": WS_EX_TOOLWINDOW,
    "WS_EX_TOPMOST": WS_EX_TOPMOST,
}


class MSLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("pt", POINT),
        ("mouseData", ctypes.c_ulong),
        ("flags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", ctypes.c_void_p),
    ]


def _message_name(message: int) -> str:
    return {
        WM_KEYDOWN: "WM_KEYDOWN",
        WM_KEYUP: "WM_KEYUP",
        WM_SYSKEYDOWN: "WM_SYSKEYDOWN",
        WM_SYSKEYUP: "WM_SYSKEYUP",
        WM_LBUTTONDOWN: "WM_LBUTTONDOWN",
        WM_LBUTTONUP: "WM_LBUTTONUP",
        WM_RBUTTONDOWN: "WM_RBUTTONDOWN",
        WM_RBUTTONUP: "WM_RBUTTONUP",
    }.get(message, f"MSG_{message:#x}")


def _vk_name(vk: int) -> str:
    return VK_NAMES.get(vk, f"VK_{vk:#04x}")


def _window_info_for_hwnd(hwnd: int) -> Optional[WindowInfo]:
    if not hwnd:
        return None


def _native_window_styles(hwnd: int) -> Dict[str, Any]:
    style = int(_get_window_long_ptr(ctypes.c_void_p(hwnd), GWL_STYLE))
    exstyle = int(_get_window_long_ptr(ctypes.c_void_p(hwnd), GWL_EXSTYLE))
    return {
        "style": style,
        "style_hex": f"0x{style & 0xFFFFFFFF:08x}",
        "exstyle": exstyle,
        "exstyle_hex": f"0x{exstyle & 0xFFFFFFFF:08x}",
        "style_flags": [name for name, bit in STYLE_FLAGS.items() if style & bit],
        "exstyle_flags": [name for name, bit in EXSTYLE_FLAGS.items() if exstyle & bit],
    }
    try:
        rect = _get_rect(hwnd)
        return WindowInfo(
            hwnd=int(hwnd),
            pid=_get_pid(hwnd),
            title=_get_text(hwnd),
            klass=_get_class(hwnd),
            left=int(rect.left),
            top=int(rect.top),
            right=int(rect.right),
            bottom=int(rect.bottom),
        )
    except Exception:
        return None


def _capture_input_events(seconds: float, target_hwnd: int, phase: str) -> Dict[str, List[Dict[str, Any]]]:
    keyboard_events: List[Dict[str, Any]] = []
    mouse_events: List[Dict[str, Any]] = []

    @HOOKPROC
    def _hook(code: int, wparam: ctypes.c_void_p, lparam: ctypes.c_void_p) -> int:
        if code >= 0:
            data = ctypes.cast(lparam, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
            flags = int(data.flags)
            fg = _foreground_window()
            keyboard_events.append(
                {
                    "phase": phase,
                    "monotonic_s": round(time.monotonic(), 6),
                    "message": _message_name(int(wparam)),
                    "vk": int(data.vkCode),
                    "vk_name": _vk_name(int(data.vkCode)),
                    "scan_code": int(data.scanCode),
                    "flags": flags,
                    "injected": bool(flags & LLKHF_INJECTED),
                    "lower_il_injected": bool(flags & LLKHF_LOWER_IL_INJECTED),
                    "foreground_is_target": bool(fg and int(fg.hwnd) == int(target_hwnd)),
                    "foreground": fg.to_dict() if fg else None,
                }
            )
        return int(user32.CallNextHookEx(None, code, wparam, lparam))

    @HOOKPROC
    def _mouse_hook(code: int, wparam: ctypes.c_void_p, lparam: ctypes.c_void_p) -> int:
        if code >= 0:
            data = ctypes.cast(lparam, ctypes.POINTER(MSLLHOOKSTRUCT)).contents
            flags = int(data.flags)
            hwnd = int(user32.WindowFromPoint(data.pt) or 0)
            under_cursor = _window_info_for_hwnd(hwnd)
            fg = _foreground_window()
            mouse_events.append(
                {
                    "phase": phase,
                    "monotonic_s": round(time.monotonic(), 6),
                    "message": _message_name(int(wparam)),
                    "x": int(data.pt.x),
                    "y": int(data.pt.y),
                    "flags": flags,
                    "injected": bool(flags & LLMHF_INJECTED),
                    "lower_il_injected": bool(flags & LLMHF_LOWER_IL_INJECTED),
                    "window_under_cursor_is_target": bool(under_cursor and int(under_cursor.hwnd) == int(target_hwnd)),
                    "window_under_cursor": under_cursor.to_dict() if under_cursor else None,
                    "foreground_is_target": bool(fg and int(fg.hwnd) == int(target_hwnd)),
                    "foreground": fg.to_dict() if fg else None,
                }
            )
        return int(user32.CallNextHookEx(None, code, wparam, lparam))

    keyboard_hook = user32.SetWindowsHookExW(WH_KEYBOARD_LL, _hook, None, 0)
    if not keyboard_hook:
        raise RuntimeError(f"SetWindowsHookExW failed: {kernel32.GetLastError()}")
    mouse_hook = user32.SetWindowsHookExW(WH_MOUSE_LL, _mouse_hook, None, 0)
    if not mouse_hook:
        user32.UnhookWindowsHookEx(keyboard_hook)
        raise RuntimeError(f"SetWindowsHookExW(mouse) failed: {kernel32.GetLastError()}")

    deadline = time.time() + max(1.0, seconds)
    msg = MSG()
    try:
        while time.time() < deadline:
            while user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, PM_REMOVE):
                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))
            time.sleep(0.01)
    finally:
        user32.UnhookWindowsHookEx(keyboard_hook)
        user32.UnhookWindowsHookEx(mouse_hook)

    return {"keyboard_events": keyboard_events, "mouse_events": mouse_events}


def _make_appdata(args: argparse.Namespace, timestamp: str) -> tuple[Optional[Path], Dict[str, Any]]:
    appdata_root: Optional[Path] = None
    profile_status: Dict[str, Any] = {"mode": args.profile_mode}
    if args.profile_mode == "mirrored":
        appdata_root = (Path(tempfile.gettempdir()) / f"srpss_media_reality_{timestamp}").resolve()
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
    elif args.profile_mode == "isolated":
        appdata_root = (Path(tempfile.gettempdir()) / f"srpss_media_reality_{timestamp}").resolve()
        _seed_profile_settings(appdata_root, (ROOT / "images").resolve())
        if args.safe_click_guards:
            _apply_harness_safety_settings(appdata_root)
        profile_status = {
            "mode": "isolated",
            "copied": True,
            "source": "seeded-defaults",
            "dest": str(appdata_root / "SRPSS"),
        }
        if args.safe_click_guards:
            profile_status["safe_click_guards"] = True
    else:
        profile_status = {
            "mode": "live",
            "copied": False,
            "source": str(Path(os.environ.get("APPDATA", "")) / "SRPSS"),
            "dest": None,
            "safe_click_guards": "live_profile_not_mutated",
        }
    return appdata_root, profile_status


def _write_report(path: Path, payload: Dict[str, Any]) -> None:
    lines: List[str] = []
    lines.append("# MC Media/Key Reality Harness Report")
    lines.append("")
    lines.append(f"- Timestamp: `{payload['timestamp']}`")
    lines.append(f"- Scenario: `{payload['scenario']}`")
    lines.append(f"- Profile mode: `{payload['profile_mode']}`")
    lines.append(f"- MC window flags: `{payload.get('mc_window_flags', 'default')}`")
    lines.append(f"- Observe seconds: `{payload['observe_seconds']}`")
    lines.append(f"- Runtime contract pass: `{bool((payload.get('runtime_contract') or {}).get('passed'))}`")
    lines.append(f"- Focus OK: `{bool(payload.get('focus_ok'))}`")
    lines.append(f"- Hardware keydown events while focused: `{payload['summary']['hardware_keydown_focused']}`")
    lines.append(f"- Hardware keydown events while unfocused: `{payload['summary']['hardware_keydown_unfocused']}`")
    lines.append(f"- Injected keydown events while focused: `{payload['summary']['injected_keydown_focused']}`")
    lines.append(f"- App media log hits: `{payload['summary']['app_media_hits']}`")
    lines.append(f"- App transition log hits: `{payload['summary']['app_transition_hits']}`")
    lines.append(f"- App appcommand log hits: `{payload['summary']['appcommand_hits']}`")
    styles = payload.get("target_native_styles") or {}
    lines.append(f"- Native style: `{styles.get('style_hex', '')}` `{', '.join(styles.get('style_flags', []))}`")
    lines.append(f"- Native ex-style: `{styles.get('exstyle_hex', '')}` `{', '.join(styles.get('exstyle_flags', []))}`")
    lines.append("")
    lines.append("## Observed Key Events")
    lines.append("")
    lines.append("| Phase | Time | Message | VK | Injected | Foreground Target | Foreground |")
    lines.append("|---|---:|---|---|---:|---:|---|")
    for event in payload.get("keyboard_events", []):
        fg = event.get("foreground") or {}
        fg_label = f"{fg.get('title') or ''} / {fg.get('class') or ''}".strip()
        lines.append(
            f"| `{event.get('phase', '')}` | `{event['monotonic_s']}` | `{event['message']}` | `{event['vk_name']}` | "
            f"{'yes' if event['injected'] else 'no'} | "
            f"{'yes' if event['foreground_is_target'] else 'no'} | `{fg_label}` |"
        )
    if payload.get("mouse_events"):
        lines.append("")
        lines.append("## Observed Mouse Events")
        lines.append("")
        lines.append("| Phase | Time | Message | Injected | Under Target | Foreground Target | Window Under Cursor |")
        lines.append("|---|---:|---|---:|---:|---:|---|")
        for event in payload.get("mouse_events", []):
            under = event.get("window_under_cursor") or {}
            under_label = f"{under.get('title') or ''} / {under.get('class') or ''}".strip()
            lines.append(
                f"| `{event.get('phase', '')}` | `{event['monotonic_s']}` | `{event['message']}` | "
                f"{'yes' if event['injected'] else 'no'} | "
                f"{'yes' if event['window_under_cursor_is_target'] else 'no'} | "
                f"{'yes' if event['foreground_is_target'] else 'no'} | `{under_label}` |"
            )
    lines.append("")
    lines.append("## Log Signals")
    lines.append("")
    lines.append("```text")
    for line in payload.get("log_excerpt", []):
        lines.append(line)
    lines.append("```")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_reality_harness(args: argparse.Namespace) -> Dict[str, Any]:
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    out_dir = Path(args.output_dir).resolve() / f"media_reality_{timestamp}"
    out_dir.mkdir(parents=True, exist_ok=True)
    log_dir = out_dir / "runtime_logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    appdata_root, profile_status = _make_appdata(args, timestamp)
    proc: Optional[subprocess.Popen[str]] = None
    launch_io_handles: List[Any] = []
    prep: Dict[str, Any] = {}

    try:
        prev_flag_mode = os.environ.get("SRPSS_MC_WINDOW_FLAGS")
        if args.mc_window_flags != "default":
            os.environ["SRPSS_MC_WINDOW_FLAGS"] = args.mc_window_flags
        proc, launch_io_handles = _launch_runtime("mc", appdata_root, log_dir)
        target_pid = int(proc.pid)
        target_window = _wait_for_window(target_pid, timeout_s=args.launch_timeout_s)
        if target_window is None:
            raise RuntimeError(f"Failed to locate MC window for pid={target_pid}; logs={log_dir}")

        log_file = _wait_for_log_file(log_dir, timeout_s=12.0)
        if log_file is None:
            raise RuntimeError(f"Failed to locate screensaver.log in {log_dir}")
        verbose_log_file = _wait_for_optional_log_file(log_dir, "screensaver_verbose.log", timeout_s=8.0)
        tails = [LogTail(log_file)]
        if verbose_log_file is not None:
            tails.append(LogTail(verbose_log_file))

        if args.scenario == "manual_focus":
            print("[REALITY] Manual focus mode: click/focus the real SRPSS MC window now.")
            print(f"[REALITY] Waiting {args.manual_focus_seconds:.1f}s before capture...")
            time.sleep(max(0.0, args.manual_focus_seconds))
            prep = {"scenario": args.scenario, "focus_ok": True}
        elif args.scenario == "focus_transition":
            prep = {"scenario": args.scenario, "focus_ok": True}
        else:
            prep = _scenario_prepare(args.scenario, target_window.hwnd, args.focus_policy)
        if args.refocus_before_observe and args.scenario not in {"manual_focus", "focus_transition"}:
            _force_foreground(target_window.hwnd)
        focus_ok = bool(prep.get("focus_ok")) and bool(
            (fg := _foreground_window()) and int(fg.hwnd) == int(target_window.hwnd)
        )
        foreground_before = _foreground_window()

        keyboard_events: List[Dict[str, Any]] = []
        mouse_events: List[Dict[str, Any]] = []
        if args.scenario == "focus_transition":
            print("[REALITY] Phase 1: leave SRPSS unfocused. Press the real keys now.")
            print("[REALITY] Suggested: one media key, then C.")
            phase1 = _capture_input_events(args.observe_seconds, target_window.hwnd, "unfocused_before_click")
            keyboard_events.extend(phase1["keyboard_events"])
            mouse_events.extend(phase1["mouse_events"])
            print("[REALITY] Phase 2 setup: click/focus SRPSS exactly like the failing MC path.")
            print(f"[REALITY] Waiting {args.manual_focus_seconds:.1f}s before focused capture...")
            setup = _capture_input_events(args.manual_focus_seconds, target_window.hwnd, "focus_setup")
            keyboard_events.extend(setup["keyboard_events"])
            mouse_events.extend(setup["mouse_events"])
            focus_ok = bool((fg := _foreground_window()) and int(fg.hwnd) == int(target_window.hwnd))
            if not focus_ok:
                print("[REALITY] WARNING: SRPSS is still not foreground for phase 2.")
            print("[REALITY] Phase 2: press the same real keys again while SRPSS should be focused.")
            phase2 = _capture_input_events(args.observe_seconds, target_window.hwnd, "focused_after_click")
            keyboard_events.extend(phase2["keyboard_events"])
            mouse_events.extend(phase2["mouse_events"])
        else:
            if not focus_ok:
                print("[REALITY] WARNING: SRPSS is not foreground. This capture will be marked invalid.")
            print("[REALITY] Capture window started. Press the real keys now:")
            print("[REALITY] Suggested: Volume Up/Down once, then C once.")
            print(f"[REALITY] Capturing for {args.observe_seconds:.1f}s...")
            captured = _capture_input_events(args.observe_seconds, target_window.hwnd, args.scenario)
            keyboard_events = captured["keyboard_events"]
            mouse_events = captured["mouse_events"]

        lines = _collect_tails(tails, 1.2, poll_s=0.12)
        hits = _parse_log_hits(lines)
        signals = _parse_signal_counts(lines)

        keydowns = [e for e in keyboard_events if e["message"] in {"WM_KEYDOWN", "WM_SYSKEYDOWN"}]
        hardware_keydown_focused = [
            e for e in keydowns if not e["injected"] and e["foreground_is_target"]
        ]
        hardware_keydown_unfocused = [
            e for e in keydowns if not e["injected"] and not e["foreground_is_target"]
        ]
        injected_keydown_focused = [
            e for e in keydowns if e["injected"] and e["foreground_is_target"]
        ]

        payload: Dict[str, Any] = {
            "timestamp": timestamp,
            "scenario": args.scenario,
            "profile_mode": args.profile_mode,
            "profile_status": profile_status,
            "focus_policy": args.focus_policy,
            "mc_window_flags": args.mc_window_flags,
            "observe_seconds": args.observe_seconds,
            "target_pid": target_pid,
            "target_hwnd": target_window.hwnd,
            "target_window": target_window.to_dict(),
            "target_native_styles": _native_window_styles(target_window.hwnd),
            "focus_ok": focus_ok,
            "foreground_before_observe": foreground_before.to_dict() if foreground_before else None,
            "foreground_after_observe": _foreground_window().to_dict() if _foreground_window() else None,
            "scenario_prepare": {
                key: value
                for key, value in prep.items()
                if key not in {"helper_proc", "_helper_proc", "minimized_hwnds"}
            },
            "runtime_contract": _evaluate_runtime_contract("mc", target_window, log_file),
            "log_file": str(log_file),
            "verbose_log_file": str(verbose_log_file) if verbose_log_file is not None else None,
            "output_dir": str(out_dir),
            "keyboard_events": keyboard_events,
            "mouse_events": mouse_events,
            "log_hits": hits,
            "signal_counts": signals,
            "summary": {
                "hardware_keydown_focused": len(hardware_keydown_focused),
                "hardware_keydown_unfocused": len(hardware_keydown_unfocused),
                "injected_keydown_focused": len(injected_keydown_focused),
                "app_media_hits": int(hits.get("media_info", 0)),
                "app_transition_hits": int(hits.get("transition_cycle", 0)),
                "appcommand_hits": int(hits.get("appcommand", 0)),
                "raw_input_hits": int(hits.get("media_raw_input", 0)),
            },
            "log_excerpt": lines[-30:],
        }

        json_path = out_dir / "reality_report.json"
        md_path = out_dir / "reality_report.md"
        json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        _write_report(md_path, payload)
        return payload
    finally:
        if prep:
            try:
                _scenario_cleanup(args.scenario, prep)
            except Exception:
                pass
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
        if "prev_flag_mode" in locals():
            if prev_flag_mode is None:
                os.environ.pop("SRPSS_MC_WINDOW_FLAGS", None)
            else:
                os.environ["SRPSS_MC_WINDOW_FLAGS"] = prev_flag_mode


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="MC physical-key reality harness for U-05.")
    parser.add_argument("--profile-mode", choices=("isolated", "live", "mirrored"), default="mirrored")
    parser.add_argument("--focus-policy", choices=("strict", "realistic"), default="realistic")
    parser.add_argument("--mc-window-flags", choices=("default", "splash"), default="default")
    parser.add_argument(
        "--scenario",
        choices=("focused_idle", "focused_clicked", "manual_focus", "focus_transition"),
        default="focused_clicked",
    )
    parser.add_argument("--observe-seconds", type=float, default=12.0)
    parser.add_argument("--launch-timeout-s", type=float, default=45.0)
    parser.add_argument("--output-dir", default=str(ROOT / "logs" / "media_key_reality"))
    parser.add_argument("--safe-click-guards", action="store_true", default=True)
    parser.add_argument("--no-safe-click-guards", dest="safe_click_guards", action="store_false")
    parser.add_argument("--refocus-before-observe", action="store_true", default=True)
    parser.add_argument("--no-refocus-before-observe", dest="refocus_before_observe", action="store_false")
    parser.add_argument("--manual-focus-seconds", type=float, default=6.0)
    return parser


def main() -> int:
    payload = run_reality_harness(build_parser().parse_args())
    print("[REALITY] Completed MC reality capture")
    print(f"[REALITY] Report JSON: {Path(payload['output_dir']) / 'reality_report.json'}")
    print(f"[REALITY] Report MD:   {Path(payload['output_dir']) / 'reality_report.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
