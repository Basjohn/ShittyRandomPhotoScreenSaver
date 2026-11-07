"""Drive the real SRPSS runtime through monitor hotplug on Linux/Xvfb (RandR monitors).

Development harness, Linux only. It starts ``Xvfb`` with one wide screen split
into two RandR monitors, runs the unmodified ``main.py /s`` (real PySide6/Qt
Quick on xcb with Mesa's threaded OpenGL), then adds and removes the second
monitor and waits for every replacement generation's coordinated reveal. Each
step reports the reveal latency and main-process memory; a generation that
never reveals is reported as a hang, with a ``py-spy`` stack dump when
``py-spy`` is installed.

It is not evidence of Windows behaviour (native topology, drivers, DWM): it is
the automated path for the engine/display lifecycle across real Qt screen
add/remove edges.

Environment, profile isolation and the Mesa OpenGL 4.6 override come from
``tools/linux_headless.py``; prerequisites from ``scripts/linux/setup.sh --headless``.

Example::

    python tools/linux_xvfb_hotplug_churn.py --cycles 3

The run's logs are published to ``--out`` (``tools/artifact_paths.py``); generated images and the isolated
settings profile live in the run's owner scratch (or ``--work-dir``), deleted on success and kept on failure.
Only the child process gets the profile and log locations.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))

import linux_headless as lh  # noqa: E402
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools import artifact_paths, evidence_media  # noqa: E402

REPO = lh.REPO
FIRST = ("MSI", "2560/677x1440/381+0+0", "none")
SECOND = ("LG", "2560/677x1440/381+2560+0", "none")
REVEALED = r"Coordinated retained reveal complete generation={generation}\b"

def _xrandr(display: str, *args: str, check: bool = True) -> None:
    subprocess.run(["xrandr", *args], env={**os.environ, "DISPLAY": display},
                   capture_output=True, check=check)


def _memory(pid: int) -> str:
    try:
        rollup: dict[str, int] = {}
        for line in Path(f"/proc/{pid}/smaps_rollup").read_text().splitlines()[1:]:
            key, value = line.split(":", 1)
            rollup[key.strip()] = int(value.split()[0])
        status = Path(f"/proc/{pid}/status").read_text()
        threads = int(re.search(r"Threads:\s+(\d+)", status).group(1))
        fds = len(os.listdir(f"/proc/{pid}/fd"))
    except (OSError, AttributeError, ValueError):
        return "memory=unavailable"
    private = (rollup.get("Private_Clean", 0) + rollup.get("Private_Dirty", 0)) / 1024.0
    return f"rss_mb={rollup.get('Rss', 0) / 1024.0:.0f} private_mb={private:.0f} threads={threads} fds={fds}"


class _LogWatch:
    """Follows one log file; waits for a line (bounded wait for an external process)."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.position = 0
        self.lines: list[str] = []

    def _read(self) -> None:
        if not self.path.exists():
            return
        with self.path.open("r", encoding="utf-8", errors="replace") as handle:
            handle.seek(self.position)
            data = handle.read()
            self.position = handle.tell()
        self.lines.extend(data.splitlines())

    def wait_for(self, pattern: str, timeout: float, *, since: int = 0) -> bool:
        expression = re.compile(pattern)
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            self._read()
            if any(expression.search(line) for line in self.lines[since:]):
                return True
            time.sleep(0.1)
        return False


def _dump_stacks(pid: int, target: Path) -> str:
    if shutil.which("py-spy") is None:
        return "py-spy not installed; no stack dump"
    dump = subprocess.run(["py-spy", "dump", "--pid", str(pid), "--native"],
                          capture_output=True, text=True, check=False)
    target.write_text(dump.stdout + dump.stderr)
    return f"stacks in {target}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--work-dir", type=artifact_paths.evidence_arg, default=None,
                        help="images and profile (default: this run's owner scratch, deleted on success)")
    parser.add_argument("--out", type=artifact_paths.evidence_arg,
                        default=artifact_paths.default_evidence("display", "linux_hotplug_churn"),
                        help="the run's logs")
    parser.add_argument("--display", default=":98")
    parser.add_argument("--cycles", type=int, default=1, help="remove/re-add cycles after the first add")
    parser.add_argument("--hold", type=float, default=15.0, help="seconds with both monitors before removal")
    parser.add_argument("--gap", type=float, default=5.0, help="seconds with one monitor before re-adding")
    parser.add_argument("--timeout", type=float, default=30.0, help="seconds each generation has to reveal")
    parser.add_argument("--images", type=int, default=24)
    parser.add_argument("--interval", type=int, default=5, help="rotation interval in seconds")
    parser.add_argument("--entry", type=Path, default=None, help="alternative entry script wrapping main.py")
    parser.add_argument(
        "--covered-display", action="store_true",
        help="keep Xvfb's full-width output as an extra display; once both monitors exist its window is "
             "fully covered, never exposed and never ready, which exercises the stalled-sibling reveal "
             "(expect [STARTUP_REVEAL][FALLBACK] in screensaver.log)",
    )
    args = parser.parse_args()
    if not sys.platform.startswith("linux"):
        print("Linux/Xvfb only")
        return 2

    out = evidence_media.redirect_output(args, "out", "linux_xvfb_hotplug_churn")
    work = args.work_dir or out.parent / "work"
    images, profile, logs = work / "images", work / "profile", out / "logs"
    shutil.rmtree(logs, ignore_errors=True)
    logs.mkdir(parents=True)
    lh.generate_images(images, args.images)
    child_env = lh.child_env(args.display, profile, logs)
    xvfb = lh.start_xvfb(args.display, "5120x1440x24")
    app = None
    try:
        # Qt reports RandR monitors as screens: one monitor over the left half
        # is the single-display start; the second is added/removed at runtime.
        _xrandr(args.display, "--setmonitor", *FIRST)
        if not args.covered_display:
            # Drops Xvfb's automatic full-width output monitor. xrandr then
            # fails to shrink the framebuffer to 0x0 (BadValue); the output is
            # still off, which is all this step needs.
            _xrandr(args.display, "--output", "screen", "--off", check=False)
        lh.seed_profile(child_env, images, args.interval)
        entry = [str(args.entry)] if args.entry else ["main.py"]
        with (logs / "stdout.txt").open("w") as stdout:
            app = subprocess.Popen([sys.executable, *entry, "/s", "--debug", lh.log_dir_arg(logs)], cwd=REPO, env=child_env,
                                   stdout=stdout, stderr=subprocess.STDOUT)
        watch = _LogWatch(logs / "screensaver_verbose.log")
        if not watch.wait_for(REVEALED.format(generation=0), 60.0):
            print(f"cold start never revealed; {_dump_stacks(app.pid, logs / 'stacks.txt')}")
            return 1
        print(f"cold start revealed {_memory(app.pid)}", flush=True)
        steps = [("add", ("--setmonitor", *SECOND), args.hold)]
        for _ in range(args.cycles):
            steps += [("remove", ("--delmonitor", SECOND[0]), args.gap), ("add", ("--setmonitor", *SECOND), args.hold)]
        for generation, (name, command, settle) in enumerate(steps, start=1):
            mark = len(watch.lines)
            _xrandr(args.display, *command)
            started = time.monotonic()
            revealed = watch.wait_for(REVEALED.format(generation=generation), args.timeout, since=mark)
            elapsed = time.monotonic() - started
            print(f"step={name} generation={generation} revealed={revealed} reveal_s={elapsed:.1f} "
                  f"{_memory(app.pid)}", flush=True)
            if not revealed:
                print(f"HANG: {_dump_stacks(app.pid, logs / 'stacks.txt')}")
                return 1
            time.sleep(settle)
        print(f"ok logs={logs}")
        return 0
    finally:
        if app is not None:
            app.send_signal(signal.SIGTERM)
            try:
                app.wait(10)
            except subprocess.TimeoutExpired:
                app.kill()
        xvfb.terminate()


if __name__ == "__main__":
    raise SystemExit(evidence_media.finish(main()))
