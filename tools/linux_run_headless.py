"""Run SRPSS headless on Linux (Xvfb + Mesa) and capture screenshots and log findings.

Linux only, development only. The smallest end-to-end Linux check: it seeds an
isolated profile with a generated image folder, runs the unmodified ``main.py``
in the requested mode, grabs the virtual screen at the requested seconds and
prints every WARNING/ERROR/CRITICAL headline from the run's log. Environment and
evidence limits: ``tools/linux_headless.py``.

Examples::

    python tools/linux_run_headless.py --work-dir /tmp/srpss_run --seconds 25 --shots 6,14,24
    python tools/linux_run_headless.py --mode /c --seconds 15 --shots 10
    python tools/linux_run_headless.py --keep-widgets -- --debug

Arguments after ``--`` are passed to ``main.py`` unchanged.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
import tempfile
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import linux_headless as lh  # noqa: E402

_HEADLINE = re.compile(r"(WARNING|ERROR|CRITICAL)")


def _log_findings(log: Path) -> list[tuple[int, str]]:
    """Return (count, headline) for each distinct WARNING/ERROR/CRITICAL entry."""

    if not log.is_file():
        return []
    lines = log.read_text(encoding="utf-8", errors="replace").splitlines()
    found: Counter[str] = Counter()
    for index, line in enumerate(lines):
        if not _HEADLINE.search(line):
            continue
        if "│" in line and line.count("│") >= 3:
            # Single-line record: "time │ LEVEL │ logger │ message".
            message = line.split("│", 3)[-1].strip()
        else:
            # Boxed record: the first body line after the header rows holds the message.
            body = [text.strip(" │") for text in lines[index + 1:index + 6] if text.startswith("│")]
            message = body[1] if len(body) > 1 else (body[0] if body else line)
        level = _HEADLINE.search(line).group(1)
        found[f"{level}: {message[:200]}"] += 1
    return [(count, text) for text, count in found.most_common()]


def main() -> int:
    lh.require_linux()
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--work-dir", type=Path, default=None, help="images, profile, logs, shots (default: new temp dir)")
    parser.add_argument("--display", default=":97")
    parser.add_argument("--geometry", default="1920x1080x24")
    parser.add_argument("--mode", default="/s", help="main.py mode argument: /s or /c")
    parser.add_argument("--seconds", type=int, default=20, help="run length; passed as --exit-after")
    parser.add_argument("--shots", default="", help="comma-separated seconds at which to grab the screen")
    parser.add_argument("--images", type=int, default=8)
    parser.add_argument("--interval", type=int, default=5, help="rotation interval in seconds")
    parser.add_argument("--keep-widgets", action="store_true", help="do not disable network/credential widgets")
    parser.add_argument("--no-seed", action="store_true", help="reuse the work dir's existing profile untouched")
    parser.add_argument("main_args", nargs="*", help="extra main.py arguments (after --)")
    args = parser.parse_args()

    work = (args.work_dir or Path(tempfile.mkdtemp(prefix="srpss_linux_"))).resolve()
    images, profile, logs, shots = work / "images", work / "profile", work / "logs", work / "shots"
    for folder in (logs, shots):
        folder.mkdir(parents=True, exist_ok=True)
        for stale in folder.iterdir():
            if stale.is_file():
                stale.unlink()
    env = lh.child_env(args.display, profile, logs)
    shot_times = sorted(int(value) for value in args.shots.split(",") if value.strip())
    xvfb = lh.start_xvfb(args.display, args.geometry)
    app = None
    try:
        if not args.no_seed:
            lh.generate_images(images, args.images)
            lh.seed_profile(env, images, args.interval, () if args.keep_widgets else lh.DEFAULT_DISABLED_WIDGETS)
        command = [sys.executable, "main.py", args.mode, "--exit-after", str(args.seconds), *args.main_args]
        with (logs / "stdout.txt").open("w") as stdout:
            app = subprocess.Popen(command, cwd=lh.REPO, env=env, stdout=stdout, stderr=subprocess.STDOUT)
        started = time.monotonic()
        for second in shot_times:
            time.sleep(max(0.0, started + second - time.monotonic()))
            if app.poll() is not None:
                print(f"app exited before shot at {second}s")
                break
            target = shots / f"shot_{second:03d}s.png"
            lh.grab_screen(args.display, target)
            print(f"shot {target}")
        try:
            code = app.wait(args.seconds + 30)
        except subprocess.TimeoutExpired:
            app.kill()
            code = "killed (did not honour --exit-after)"
        print(f"exit={code} work={work}")
    finally:
        if app is not None and app.poll() is None:
            app.kill()
        xvfb.terminate()

    findings = _log_findings(logs / "screensaver.log")
    print(f"log findings: {len(findings)} distinct")
    for count, text in findings:
        print(f"  {count:>3}x {text}")
    return 0 if code == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
