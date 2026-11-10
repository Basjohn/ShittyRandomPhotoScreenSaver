"""Smoke-test an installed frozen Linux screensaver or MC build without enabling release logging.

Runs the actual installed binary on isolated Xvfb, verifies that Mesa exposes the
required GL 4.6 Core context, and proves that a materially detailed scene appears
in the framebuffer. The executable must exit cleanly via --exit-after, while /c
must remain open. Qt/QML and child output are printed when a test fails.

No logging configuration is written beside the frozen executable. Production
logging remains disabled, as authored.
"""
from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

from PIL import Image, ImageChops, ImageStat

sys.path.insert(0, str(Path(__file__).resolve().parent))

import linux_headless as lh  # noqa: E402
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools import artifact_paths, evidence_media  # noqa: E402

# Dedicated Xvfb with one virtual display. Enough time for first-use Qt/QML
# initialization, without relying on the production logger's startup messages.
SHOT_SECONDS = (6, 11, 16)


def _has_rendered_scene(blank: Path, shot: Path) -> tuple[bool, str]:
    """Reject black/flat frames and small incidental X11 cursor/OSD changes.

    The fixture seeds actual, detailed artwork. Its rendered screen should
    differ substantially from a blank Xvfb framebuffer and exhibit detail.
    Normalize resolution so the thresholds are independent of runner DPI.
    """
    with Image.open(blank) as before, Image.open(shot) as after:
        size = (192, 108)
        background = before.convert("RGB").resize(size, Image.Resampling.BILINEAR)
        rendered = after.convert("RGB").resize(size, Image.Resampling.BILINEAR)
    difference = ImageChops.difference(background, rendered).convert("L")
    changed = sum(difference.histogram()[16:]) / (size[0] * size[1])
    detail = ImageStat.Stat(rendered.convert("L")).stddev[0]
    return (changed >= 0.05 and detail >= 10.0,
            f"changed={changed:.1%} detail_stddev={detail:.1f}")


def _xvfb_gl46_available(env: dict[str, str]) -> tuple[bool, str]:
    """Check the test X server's GL capability, not production log messages.

    This probes the same isolated DISPLAY/Mesa environment as the frozen app;
    visible pixels from the app are checked separately. A glxinfo capability
    probe alone does not claim the app initialized the correct GL context.
    """
    import re

    try:
        probe = subprocess.run(["glxinfo", "-B"], env=env,
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                               timeout=15, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, f"glxinfo unavailable: {exc}"
    output = probe.stdout.decode(errors="replace")
    match = re.search(r"OpenGL core profile version string:\s*(\d+)\.(\d+)", output)
    version = tuple(map(int, match.groups())) if match else None
    return (probe.returncode == 0 and version is not None and version >= (4, 6),
            f"glxinfo exit={probe.returncode}, core={version}; {output[-800:]}")


def _fail(message: str, log: Path | None = None, *, stdout: bytes = b"") -> int:
    print(f"[SMOKE] FAIL: {message}", flush=True)
    if log is not None:
        if log.is_file():
            lines = log.read_text(encoding="utf-8", errors="replace").splitlines()
            print(f"[SMOKE] Main log: {log} ({len(lines)} lines)")
            print("\n".join(lines[-60:]))
        else:
            print(f"[SMOKE] Main log missing: {log}")
        available = sorted(path.name for path in log.parent.glob("*.log"))
        print(f"[SMOKE] Available log files: {available}")
    if stdout:
        print("[SMOKE] Child stdout/stderr tail:")
        print(stdout.decode(errors="replace")[-4000:])
    return 1


def main(argv: list[str]) -> int:
    lh.require_linux()
    if len(argv) != 1:
        raise SystemExit(__doc__)
    product = Path(argv[0]).resolve()
    binary = "srpss-mc" if "-linux-mc-" in product.name else "srpss"
    app_profile = "Screensaver_MC" if binary == "srpss-mc" else "Screensaver"
    if not (product / binary).is_file() or not (product / "install.sh").is_file():
        return _fail(f"{product} lacks expected {binary} or install.sh")

    # Logs are published as evidence; home, profile and images stay in the scratch run (deleted on success).
    from types import SimpleNamespace

    out = evidence_media.redirect_output(
        SimpleNamespace(out=artifact_paths.evidence_dir("display", "linux_smoke_dist", artifact_paths.run_label("run"))),
        "out", "linux_smoke_dist")
    work = out.parent / "work"
    work.mkdir(parents=True)
    home, profile, logs = work / "home", work / "profile", out / "logs"
    home.mkdir()
    display = ":95"
    env = lh.child_env(display, profile, logs)
    env["HOME"] = str(home)
    subprocess.run([str(product / "install.sh")], env=env, check=True)
    installed = home / ".local" / "opt" / binary / binary
    data = profile / "data" / "SRPSS"
    for required in (installed, data / "themes", data / "presets" / "visualizer_modes", data / "sounds"):
        if not required.exists():
            return _fail(f"install.sh did not produce {required}")

    xvfb = lh.start_xvfb(display)
    child = None
    log = logs / "screensaver.log"  # Optional. Do not enable frozen logging.
    frozen_output = out / "frozen_stdout.txt"
    try:
        lh.copy_repo_images(work / "images")
        lh.seed_profile(env, work / "images", 4, application=app_profile)
        gl_ok, gl_fact = _xvfb_gl46_available(env)
        if not gl_ok:
            return _fail(f"Xvfb lacks required GL 4.6 Core support: {gl_fact}", log)

        # Xvfb is a dedicated, otherwise empty display. Capture it before
        # starting the frozen application, so a drawn scene is unmistakable.
        blank = work / "blank_xvfb.png"
        lh.grab_screen(display, blank)
        shots = out / "shots"
        shots.mkdir(exist_ok=True)
        diagnostics = []
        rendered_scene = False
        with frozen_output.open("wb") as stdout_file:
            child = subprocess.Popen(
                [str(installed), "/s", "--exit-after", "20", lh.log_dir_arg(logs)],
                env=env, stdout=stdout_file, stderr=subprocess.STDOUT,
            )
            started = time.monotonic()
            for second in SHOT_SECONDS:
                time.sleep(max(0.0, started + second - time.monotonic()))
                if child.poll() is not None:
                    diagnostics.append(f"process exited before {second}s screenshot")
                    break
                shot = shots / f"scene_{second:02d}s.png"
                lh.grab_screen(display, shot)
                visible, result = _has_rendered_scene(blank, shot)
                diagnostics.append(f"{second}s: {result}")
                rendered_scene |= visible
            try:
                exit_code = child.wait(timeout=50)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()
                return _fail("/s failed to honour --exit-after", log,
                             stdout=frozen_output.read_bytes())
        stdout = frozen_output.read_bytes()
        if exit_code != 0:
            return _fail(f"/s exited {exit_code}; " + "; ".join(diagnostics), log, stdout=stdout)
        if not rendered_scene:
            return _fail("/s never produced a detailed Xvfb framebuffer; " + "; ".join(diagnostics),
                         log, stdout=stdout)
        print(f"[SMOKE] /s rendered: {'; '.join(diagnostics)}; Xvfb GL: {gl_fact.splitlines()[0]}")

        settings = subprocess.Popen([str(installed), "/c", lh.log_dir_arg(logs)],
                                    env=env, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
        try:
            time.sleep(12)
            alive = settings.poll() is None
        finally:
            if settings.poll() is None:
                settings.terminate()
            try:
                settings.wait(15)
            except subprocess.TimeoutExpired:
                settings.kill()
                settings.wait()
        if not alive:
            return _fail(f"/c exited early with {settings.returncode}", log)
    finally:
        if child is not None and child.poll() is None:
            child.kill()
            child.wait()
        xvfb.terminate()
    print(f"[SMOKE] OK: installed {binary} rendered /s and opened /c without frozen logging")
    return 0


if __name__ == "__main__":
    raise SystemExit(evidence_media.finish(main(sys.argv[1:])))
