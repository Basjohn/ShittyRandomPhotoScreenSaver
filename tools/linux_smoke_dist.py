"""Smoke-test a built Linux product folder: install it, then run the saver and Settings headless.

Linux only. Used by ``.github/workflows/linux-build.yml`` and after local builds::

    python tools/linux_smoke_dist.py release/linux/SRPSS-<version>-linux-x86_64

Everything happens under a temporary HOME: the product's own ``install.sh`` deploys
the binary and the curated presets/themes/sounds (exercising the installer), then the
*installed* ``srpss`` runs ``/s`` on Xvfb with real repository artwork and must exit 0
after reaching a ready display with a validated OpenGL 4.6 context and no ERROR/CRITICAL
log entries; ``/c`` must stay up until terminated. Environment notes: ``tools/linux_headless.py``.
"""
from __future__ import annotations

import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import linux_headless as lh  # noqa: E402

READY = "Quick startup display ready"
GL_OK = "[QUICK_GL] validated"


def _fail(message: str, log: Path | None = None) -> int:
    print(f"[SMOKE] FAIL: {message}")
    if log is not None and log.is_file():
        print("".join(log.read_text(encoding="utf-8", errors="replace").splitlines(True)[-60:]))
    return 1


def main(argv: list[str]) -> int:
    lh.require_linux()
    if len(argv) != 1:
        raise SystemExit(__doc__)
    product = Path(argv[0]).resolve()
    if not (product / "srpss").is_file() or not (product / "install.sh").is_file():
        return _fail(f"{product} is not a built SRPSS Linux product folder")

    work = Path(tempfile.mkdtemp(prefix="srpss_smoke_"))
    home, profile, logs = work / "home", work / "profile", work / "logs"
    home.mkdir()
    display = ":95"
    env = lh.child_env(display, profile, logs)
    env["HOME"] = str(home)
    subprocess.run([str(product / "install.sh")], env=env, check=True)
    installed = home / ".local" / "opt" / "srpss" / "srpss"
    data = profile / "data" / "SRPSS"
    for required in (installed, data / "themes", data / "presets" / "visualizer_modes", data / "sounds"):
        if not required.exists():
            return _fail(f"install.sh did not produce {required}")

    # Frozen release builds log nothing by default; the product's own sidecar switch enables it.
    (installed.parent / "srpss.logging.cfg").write_text("1", encoding="utf-8")

    xvfb = lh.start_xvfb(display)
    try:
        lh.copy_repo_images(work / "images")
        lh.seed_profile(env, work / "images", 4)

        run = subprocess.run([str(installed), "/s", "--exit-after", "20"], env=env,
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=90)
        log = logs / "screensaver.log"
        text = log.read_text(encoding="utf-8", errors="replace") if log.is_file() else ""
        if run.returncode != 0:
            print(run.stdout.decode(errors="replace")[-4000:])
            return _fail(f"/s exited {run.returncode}", log)
        for marker in (READY, GL_OK):
            if marker not in text:
                return _fail(f"/s log lacks {marker!r}", log)
        errors = [line for line in text.splitlines() if re.search(r"\b(ERROR|CRITICAL)\b", line)]
        if errors:
            return _fail("ERROR/CRITICAL in /s log:\n" + "\n".join(errors[:20]), log)

        settings = subprocess.Popen([str(installed), "/c"], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
        time.sleep(12)
        alive = settings.poll() is None
        settings.terminate()
        try:
            settings.wait(15)
        except subprocess.TimeoutExpired:
            settings.kill()
        if not alive:
            return _fail(f"/c exited early with {settings.returncode}", log)
    finally:
        xvfb.terminate()
    print(f"[SMOKE] OK: installed product ran /s and /c (work dir {work})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
