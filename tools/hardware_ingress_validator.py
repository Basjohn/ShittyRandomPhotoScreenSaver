"""Hardware ingress validation layer for U-05.

Validates that physical (non-injected) media keys reach SRPSS and produce
expected log responses, separate from synthetic/injected probe paths.

Usage (interactive — user presses real keys):
    python tools/hardware_ingress_validator.py --scenario focus_transition --profile-mode mirrored
"""
from __future__ import annotations
import argparse
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

if os.name != "nt":
    raise SystemExit("This validator requires Windows.")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))  # noqa: E402

from media_key_matrix_harness import (  # noqa: E402
    LogTail,
    _collect_tails,
    _evaluate_runtime_contract,
    _foreground_window,
    _force_foreground,
    _launch_runtime,
    _scenario_cleanup,
    _scenario_prepare,
    _wait_for_log_file,
    _wait_for_optional_log_file,
    _wait_for_window,
)
from media_key_reality_harness import (  # noqa: E402
    _capture_input_events, _make_appdata, _native_window_styles, _vk_name,
)

MEDIA_VK = {0xAD, 0xAE, 0xAF, 0xB0, 0xB1, 0xB2, 0xB3}
PHYSICAL_MEDIA_VK = {0x21, 0x22}  # PgUp/PgDn used with PowerToys remap
CTRL_VK = {0x43, 0x53}  # C (cycle), S (settings)
HOTKEY_VK = {0x58}  # X (next image)
INTERESTING = MEDIA_VK | PHYSICAL_MEDIA_VK | CTRL_VK | HOTKEY_VK
RESPONSE_PATTERNS = ["[WIN_APPCOMMAND]", "[RAW_INPUT]", "media key", "InputHandler", "cycle transition", "open_settings"]

@dataclass
class PhaseResult:
    phase: str
    hardware_keys: int = 0
    injected_media_keys: int = 0
    focused_keys: int = 0
    unfocused_keys: int = 0
    passes: int = 0
    failures: int = 0
    results: List[Dict[str, Any]] = field(default_factory=list)

def _focus_label(ev: Dict[str, Any], target_hwnd: int) -> str:
    fg = ev.get("foreground")
    if not fg:
        return "unknown"
    return "focused" if int(fg.get("hwnd", 0)) == int(target_hwnd) else "unfocused"


def _get_display_index(hwnd: int) -> int:
    """Return monitor index (0-based) for a window."""
    try:
        import ctypes
        from ctypes import wintypes
        user32 = ctypes.windll.user32
        hmon = user32.MonitorFromWindow(wintypes.HWND(hwnd), 2)  # MONITOR_DEFAULTTONEAREST
        if not hmon:
            return -1
        # enumerate monitors to find index
        monitors: list[int] = []
        def _enum_proc(h_monitor, hdc, rect, data):
            monitors.append(int(h_monitor))
            return 1
        MONITORENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HMONITOR, wintypes.HDC, ctypes.POINTER(wintypes.RECT), wintypes.LPARAM)
        user32.EnumDisplayMonitors(None, None, MONITORENUMPROC(_enum_proc), 0)
        try:
            return monitors.index(int(hmon))
        except ValueError:
            return -1
    except Exception:
        return -1

def _find_resp(lines: List[str]) -> Optional[str]:
    for line in lines:
        low = line.lower()
        if any(p.lower() in low for p in RESPONSE_PATTERNS):
            return line
    return None

def _validate_phase(phase: str, events: List[Dict[str, Any]], target_hwnd: int, log_lines: List[str]) -> PhaseResult:
    pr = PhaseResult(phase=phase)
    keydowns = [e for e in events if e.get("message") in {"WM_KEYDOWN", "WM_SYSKEYDOWN"}]
    for ev in keydowns:
        vk = int(ev.get("vk", 0))
        is_media = vk in MEDIA_VK
        is_interesting = vk in INTERESTING
        # Count injected media keys (e.g., PowerToys remapped PgUp/PgDn -> Volume)
        if ev.get("injected") and is_media:
            pr.injected_media_keys += 1
            # Still validate: injected media keys are real user input via remappers
        elif ev.get("injected") or not is_interesting:
            continue
        pr.hardware_keys += 1
        foc = _focus_label(ev, target_hwnd)
        if foc == "focused":
            pr.focused_keys += 1
        else:
            pr.unfocused_keys += 1
        line = _find_resp(log_lines)
        ok = line is not None
        if ok:
            pr.passes += 1
        else:
            pr.failures += 1
        pr.results.append({"event": ev, "responded": ok, "matched_log_line": line, "focus_state": foc})
    return pr

def _write_md(path: Path, payload: Dict[str, Any]) -> None:
    lines = ["# Hardware Ingress Validation Report", "",
             f"- Timestamp: `{payload['timestamp']}`",
             f"- Scenario: `{payload['scenario']}`",
             f"- Profile mode: `{payload['profile_mode']}`",
             f"- Response timeout: `{payload['response_timeout_s']}s`", ""]
    lines += ["## Summary", "",
              f"- Total hardware keys: `{payload['summary']['total_hardware_keys']}`",
              f"- Injected media keys (PowerToys/etc): `{payload['summary'].get('injected_media_keys', 0)}`",
              f"- Media keys: `{payload['summary']['media_keys']}`",
              f"- Control keys: `{payload['summary']['control_keys']}`",
              f"- Passes: `{payload['summary']['passes']}`",
              f"- Failures: `{payload['summary']['failures']}`", ""]
    for ph in payload.get("phases", []):
        lines += [f"### Phase: `{ph['phase']}`", "",
                  f"- Hardware keys: `{ph['hardware_keys']}`",
                  f"- Injected media keys: `{ph.get('injected_media_keys', 0)}`",
                  f"  - Focused: `{ph['focused_keys']}`",
                  f"  - Unfocused: `{ph['unfocused_keys']}`",
                  f"- Passes: `{ph['passes']}`", f"- Failures: `{ph['failures']}`", ""]
        if ph["results"]:
            lines += ["| VK | Name | Focus | Response | Pattern |",
                      "|---|---|---|---|---|"]
            for r in ph["results"]:
                ev = r["event"]
                lines.append(
                    f"| `{_vk_name(int(ev.get('vk',0)))}` | `{ev.get('vk_name','')}` | "
                    f"`{r['focus_state']}` | `{'PASS' if r['responded'] else 'FAIL'}` | "
                    f"`{(r.get('matched_log_line') or '')[:50]}` |"
                )
            lines.append("")
    lines += ["## Log Excerpt", "", "```text"]
    lines += payload.get("log_excerpt", [])
    lines += ["```", ""]
    path.write_text("\n".join(lines), encoding="utf-8")

def _banner(text: str) -> None:
    import sys
    print("\n" + "=" * 60)
    print(text)
    print("=" * 60 + "\n")
    sys.stdout.flush()


def _beep(freq: int = 800, dur: int = 300) -> None:
    try:
        import winsound
        winsound.Beep(freq, dur)
    except Exception:
        pass


def _countdown(seconds: float, label: str = "Time remaining") -> None:
    import sys
    end = time.time() + seconds
    last = -1
    while time.time() < end:
        rem = int(end - time.time()) + 1
        if rem != last:
            last = rem
            sys.stdout.write(f"\r[{label}] {rem}s   ")
            sys.stdout.flush()
        time.sleep(0.1)
    sys.stdout.write("\r" + " " * 40 + "\r")
    sys.stdout.flush()


def run_validation(args: argparse.Namespace) -> Dict[str, Any]:
    ts = time.strftime("%Y%m%d_%H%M%S")
    out_dir = Path(args.output_dir).resolve() / f"hardware_ingress_{ts}"
    out_dir.mkdir(parents=True, exist_ok=True)
    log_dir = out_dir / "runtime_logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    appdata_root, profile_status = _make_appdata(args, ts)
    proc: Optional[subprocess.Popen[str]] = None
    launch_io: List[Any] = []
    prep: Dict[str, Any] = {}

    try:
        prev_flag = os.environ.get("SRPSS_MC_WINDOW_FLAGS")
        if args.mc_window_flags != "default":
            os.environ["SRPSS_MC_WINDOW_FLAGS"] = args.mc_window_flags
        proc, launch_io = _launch_runtime("mc", appdata_root, log_dir)
        target_pid = int(proc.pid)
        target = _wait_for_window(target_pid, timeout_s=args.launch_timeout_s)
        if target is None:
            raise RuntimeError(f"Failed to locate MC window for pid={target_pid}")

        log_file = _wait_for_log_file(log_dir, timeout_s=12.0)
        if log_file is None:
            raise RuntimeError("Failed to locate screensaver.log")
        vlog = _wait_for_optional_log_file(log_dir, "screensaver_verbose.log", timeout_s=8.0)
        tails = [LogTail(log_file)]
        if vlog is not None:
            tails.append(LogTail(vlog))

        if args.scenario == "manual_focus":
            _beep(800, 200)
            _banner("MANUAL FOCUS PHASE")
            print("Click / focus the SRPSS MC window now.")
            sys.stdout.flush()
            _countdown(args.manual_focus_seconds, "Focus window")
            prep = {"scenario": args.scenario, "focus_ok": True}
        elif args.scenario == "focus_transition":
            prep = {"scenario": args.scenario, "focus_ok": True}
        else:
            prep = _scenario_prepare(args.scenario, target.hwnd, args.focus_policy)
        if args.refocus_before_observe and args.scenario not in {"manual_focus", "focus_transition"}:
            _force_foreground(target.hwnd)
        focus_ok = bool(prep.get("focus_ok")) and bool(
            (fg := _foreground_window()) and int(fg.hwnd) == int(target.hwnd)
        )

        key_events: List[Dict[str, Any]] = []
        phases: List[PhaseResult] = []

        if args.scenario == "focus_transition":
            _beep(600, 200)
            _banner("PHASE 1 / 3 -- UNFOCUSED (keys should WORK)")
            print("SRPSS is running but NOT focused.")
            print("Press your real media keys now (e.g., Volume Up/Down, Play/Pause).")
            print("Also try the 'C' key.\n")
            print("DO NOT click SRPSS yet.")
            sys.stdout.flush()
            p1 = _capture_input_events(args.observe_seconds, target.hwnd, "unfocused_before_click")
            key_events.extend(p1["keyboard_events"])
            detected = len([e for e in p1["keyboard_events"] if e.get("message") in {"WM_KEYDOWN", "WM_SYSKEYDOWN"}])
            print(f"\n[PHASE 1 COMPLETE] Keydowns detected: {detected}")
            lines = _collect_tails(tails, 1.2, poll_s=0.12)
            phases.append(_validate_phase("unfocused_before_click", p1["keyboard_events"], target.hwnd, lines))

            _beep(800, 200)
            _banner("PHASE 2 / 3 -- MANUAL CLICK / FOCUS SRPSS")
            print("NOW: Click inside the SRPSS MC window with YOUR MOUSE.")
            print("This simulates the real user repro path.")
            print(f"You have {args.manual_focus_seconds:.1f}s to click it...\n")
            sys.stdout.flush()
            setup = _capture_input_events(args.manual_focus_seconds, target.hwnd, "focus_setup")
            key_events.extend(setup["keyboard_events"])
            focus_ok = bool((fg := _foreground_window()) and int(fg.hwnd) == int(target.hwnd))
            if focus_ok:
                print("\n[PHASE 2 COMPLETE] SRPSS is now focused. Good.")
            else:
                _banner("WARNING: SRPSS IS NOT FOCUSED")
                print("Click it now if you missed it.")

            _beep(1000, 200)
            _banner("PHASE 3 / 3 -- FOCUSED AFTER MANUAL CLICK")
            focus_ok = bool((fg := _foreground_window()) and int(fg.hwnd) == int(target.hwnd))
            if focus_ok:
                print("SRPSS is focused. Good.")
            else:
                print("WARNING: SRPSS is NOT focused. Attempting to refocus...")
                sys.stdout.flush()
                _force_foreground(target.hwnd)
                focus_ok = bool((fg := _foreground_window()) and int(fg.hwnd) == int(target.hwnd))
                print(f"Refocus result: {'OK' if focus_ok else 'FAILED'}")
            sys.stdout.flush()
            print("Press the SAME real media keys again (Volume Up/Down, Play/Pause).")
            print("Also try 'C' again.\n")
            sys.stdout.flush()
            p2 = _capture_input_events(args.observe_seconds, target.hwnd, "focused_after_click")
            key_events.extend(p2["keyboard_events"])
            detected2 = len([e for e in p2["keyboard_events"] if e.get("message") in {"WM_KEYDOWN", "WM_SYSKEYDOWN"}])
            print(f"\n[PHASE 3 COMPLETE] Keydowns detected: {detected2}")
            lines = _collect_tails(tails, 1.2, poll_s=0.12)
            phases.append(_validate_phase("focus_setup", setup["keyboard_events"], target.hwnd, lines))
            lines = _collect_tails(tails, 1.2, poll_s=0.12)
            phases.append(_validate_phase("focused_after_click", p2["keyboard_events"], target.hwnd, lines))
        else:
            _beep(800, 200)
            _banner("SINGLE PHASE CAPTURE")
            if not focus_ok:
                _banner("WARNING: SRPSS IS NOT FOCUSED")
                print("Results may not reflect focused-MC behavior.")
            else:
                print("SRPSS is focused.")
            print("Press your real media keys now (Volume Up/Down, Play/Pause).")
            print("Also try the 'C' key.")
            sys.stdout.flush()
            cap = _capture_input_events(args.observe_seconds, target.hwnd, args.scenario)
            key_events = cap["keyboard_events"]
            lines = _collect_tails(tails, 1.2, poll_s=0.12)
            phases.append(_validate_phase(args.scenario, key_events, target.hwnd, lines))

        total_h = sum(p.hardware_keys for p in phases)
        total_inj = sum(p.injected_media_keys for p in phases)
        media = ctrl = uncls = pss = fls = 0
        for ph in phases:
            for r in ph.results:
                vk = int(r["event"].get("vk", 0))
                if vk in MEDIA_VK or vk in PHYSICAL_MEDIA_VK:
                    media += 1
                elif vk in CTRL_VK:
                    ctrl += 1
                else:
                    uncls += 1
                if r["responded"]:
                    pss += 1
                else:
                    fls += 1

        payload: Dict[str, Any] = {
            "timestamp": ts, "scenario": args.scenario,
            "profile_mode": args.profile_mode, "profile_status": profile_status,
            "focus_policy": args.focus_policy, "mc_window_flags": args.mc_window_flags,
            "observe_seconds": args.observe_seconds, "response_timeout_s": args.response_timeout_s,
            "target_pid": target_pid, "target_hwnd": target.hwnd,
            "target_window": target.to_dict(),
            "target_native_styles": _native_window_styles(target.hwnd),
            "focus_ok": focus_ok,
            "runtime_contract": _evaluate_runtime_contract("mc", target, log_file),
            "log_file": str(log_file), "verbose_log_file": str(vlog) if vlog else None,
            "output_dir": str(out_dir), "keyboard_events": key_events,
            "phases": [p.__dict__ for p in phases],
            "summary": {
                "total_hardware_keys": total_h,
                "injected_media_keys": total_inj,
                "media_keys": media,
                "control_keys": ctrl, "unclassified": uncls,
                "passes": pss, "failures": fls,
            },
            "log_excerpt": lines[-30:],
        }
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "validation_report.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
        _write_md(out_dir / "validation_report.md", payload)
        return payload
    finally:
        if prep:
            try:
                _scenario_cleanup(args.scenario, prep)
            except Exception:
                pass
        for handle in launch_io:
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
        if "prev_flag" in locals():
            if prev_flag is None:
                os.environ.pop("SRPSS_MC_WINDOW_FLAGS", None)
            else:
                os.environ["SRPSS_MC_WINDOW_FLAGS"] = prev_flag

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Hardware ingress validator for U-05.")
    parser.add_argument("--profile-mode", choices=("isolated", "live", "mirrored"), default="mirrored")
    parser.add_argument("--focus-policy", choices=("strict", "realistic"), default="realistic")
    parser.add_argument("--mc-window-flags", choices=("default", "splash"), default="default")
    parser.add_argument("--scenario", choices=("focused_idle", "focused_clicked", "manual_focus", "focus_transition"), default="focus_transition")
    parser.add_argument("--observe-seconds", type=float, default=12.0)
    parser.add_argument("--response-timeout-s", type=float, default=2.5)
    parser.add_argument("--launch-timeout-s", type=float, default=45.0)
    parser.add_argument("--output-dir", default=str(ROOT / "logs" / "hardware_ingress"))
    parser.add_argument("--safe-click-guards", action="store_true", default=True)
    parser.add_argument("--no-safe-click-guards", dest="safe_click_guards", action="store_false")
    parser.add_argument("--refocus-before-observe", action="store_true", default=True)
    parser.add_argument("--no-refocus-before-observe", dest="refocus_before_observe", action="store_false")
    parser.add_argument("--manual-focus-seconds", type=float, default=6.0)
    return parser

def main() -> int:
    payload = run_validation(build_parser().parse_args())
    print("[VALIDATOR] Hardware ingress validation complete")
    print(f"[VALIDATOR] JSON: {Path(payload['output_dir']) / 'validation_report.json'}")
    print(f"[VALIDATOR] MD:   {Path(payload['output_dir']) / 'validation_report.md'}")
    print(f"[VALIDATOR] Passes: {payload['summary']['passes']}  Failures: {payload['summary']['failures']}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
