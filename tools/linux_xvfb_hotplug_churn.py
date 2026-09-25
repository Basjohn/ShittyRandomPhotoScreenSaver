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

Prerequisites (Ubuntu): ``xvfb x11-xserver-utils libgl1-mesa-dri libegl1
libxkbcommon-x11-0 libxcb-cursor0 libxcb-image0 libxcb-render-util0
libxcb-xkb1`` plus ``requirements.txt`` Python packages.

Example::

    python tools/linux_xvfb_hotplug_churn.py --cycles 3 --work-dir /tmp/srpss_churn

The work directory holds generated images, an isolated settings profile and
the run's logs (``<work-dir>/logs``). Only the child process gets the profile
and log locations; nothing outside the work directory is touched.
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
import tempfile
import time

REPO = Path(__file__).resolve().parents[1]
FIRST = ("MSI", "2560/677x1440/381+0+0", "none")
SECOND = ("LG", "2560/677x1440/381+2560+0", "none")
REVEALED = r"Coordinated retained reveal complete generation={generation}\b"

_PROFILE_SCRIPT = r"""
import sys
from PySide6.QtWidgets import QApplication
app = QApplication([])
from core.settings import SettingsManager
settings = SettingsManager()
settings.set("sources.folders", [sys.argv[1]])
settings.set("timing.interval", int(sys.argv[2]))
for widget in ("gmail", "reddit", "reddit2", "weather", "media", "system_audio_osd"):
    settings.set(f"widgets.{widget}.enabled", False)
"""


def _xrandr(display: str, *args: str, check: bool = True) -> None:
    subprocess.run(["xrandr", *args], env={**os.environ, "DISPLAY": display},
                   capture_output=True, check=check)


def _generate_images(folder: Path, count: int) -> None:
    import numpy as np
    from PIL import Image

    folder.mkdir(parents=True, exist_ok=True)
    if len(list(folder.iterdir())) >= count:
        return
    rng = np.random.default_rng(1)
    sizes = [(3840, 2160), (2560, 1440), (5000, 3000), (1920, 1080), (2880, 1620), (4000, 4000)]
    for index in range(count):
        width, height = sizes[index % len(sizes)]
        x = np.linspace(0, 1, width, dtype=np.float32)[None, :]
        y = np.linspace(0, 1, height, dtype=np.float32)[:, None]
        red = (np.sin(x * (3 + index) * 6.28) + 1) * 0.5 * np.ones_like(y)
        green = (np.cos(y * (2 + index % 5) * 6.28) + 1) * 0.5 * np.ones_like(x)
        pixels = np.stack([red, green, x * y], axis=-1)
        pixels = (pixels * 200 + rng.integers(0, 55, (height, width, 3))).clip(0, 255).astype(np.uint8)
        image = Image.fromarray(pixels)
        if index % 3 == 0:
            image.save(folder / f"img_{index:03d}.png")
        else:
            image.save(folder / f"img_{index:03d}.jpg", quality=88)


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
    parser.add_argument("--work-dir", type=Path, default=None, help="images, profile and logs (default: a new temp dir)")
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

    work = args.work_dir or Path(tempfile.mkdtemp(prefix="srpss_churn_"))
    images, profile, logs = work / "images", work / "profile", work / "logs"
    shutil.rmtree(logs, ignore_errors=True)
    logs.mkdir(parents=True)
    _generate_images(images, args.images)
    child_env = {
        **os.environ,
        "DISPLAY": args.display,
        "APPDATA": str(profile / "appdata"),
        "LOCALAPPDATA": str(profile / "local"),
        "SRPSS_FORCE_LOG_DIR": str(logs),
    }
    xvfb = subprocess.Popen(
        ["Xvfb", args.display, "-noreset", "-screen", "0", "5120x1440x24", "+extension", "GLX", "+extension", "RANDR"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    app = None
    try:
        time.sleep(1.0)
        # Qt reports RandR monitors as screens: one monitor over the left half
        # is the single-display start; the second is added/removed at runtime.
        _xrandr(args.display, "--setmonitor", *FIRST)
        if not args.covered_display:
            # Drops Xvfb's automatic full-width output monitor. xrandr then
            # fails to shrink the framebuffer to 0x0 (BadValue); the output is
            # still off, which is all this step needs.
            _xrandr(args.display, "--output", "screen", "--off", check=False)
        subprocess.run([sys.executable, "-c", _PROFILE_SCRIPT, str(images), str(args.interval)],
                       cwd=REPO, env=child_env, capture_output=True, check=True)
        entry = [str(args.entry)] if args.entry else ["main.py"]
        with (logs / "stdout.txt").open("w") as stdout:
            app = subprocess.Popen([sys.executable, *entry, "/s", "--debug"], cwd=REPO, env=child_env,
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
    raise SystemExit(main())
