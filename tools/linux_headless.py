"""Shared Linux headless launch environment for SRPSS development harnesses.

Linux only, development only. One owner for how a harness runs the unmodified
``main.py`` on Xvfb with Mesa software OpenGL:

* **Profile isolation.** Only the child process gets XDG base directories under
  the harness work directory, so ``core.platform_paths`` resolves settings,
  data, curated trees and diagnostic logs there. ``SRPSS_FORCE_LOG_DIR`` keeps
  the main log directory beside them. Nothing outside the work directory is touched.
* **OpenGL 4.6 Core floor.** Production refuses anything below 4.6 Core
  (``rendering/quick/bootstrap.py``). Mesa's llvmpipe implements the features
  SRPSS uses but advertises 4.5, so the child alone gets Mesa's version
  override. Real Linux GPU drivers (NVIDIA, radeonsi, iris) expose 4.6 natively;
  this override is a test-environment knob, never product configuration.

Evidence from this path covers lifecycle, correctness and rendered pixels.
It is never performance, frame pacing or Windows evidence.

Prerequisites (Ubuntu/Debian): see ``scripts/linux/setup.sh --headless``.
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

PROFILE_SCRIPT = r"""
import sys
from PySide6.QtWidgets import QApplication
app = QApplication([])
from core.settings import SettingsManager
settings = SettingsManager()
settings.set("sources.folders", [sys.argv[1]])
settings.set("timing.interval", int(sys.argv[2]))
for widget in sys.argv[3].split(",") if sys.argv[3] else ():
    settings.set(f"widgets.{widget}.enabled", False)
"""

# Lets Mesa llvmpipe create the production OpenGL 4.6 Core context (see module docstring).
MESA_GL46_OVERRIDE = {"MESA_GL_VERSION_OVERRIDE": "4.6", "MESA_GLSL_VERSION_OVERRIDE": "460"}

# Network/credential widgets have no meaning in an isolated headless profile.
DEFAULT_DISABLED_WIDGETS = ("gmail", "reddit", "reddit2", "weather", "media", "system_audio_osd")


def require_linux() -> None:
    if not sys.platform.startswith("linux"):
        raise SystemExit("Linux/Xvfb only")


def child_env(display: str, profile: Path, logs: Path) -> dict[str, str]:
    """Return the isolated environment for one headless SRPSS child process."""

    env = {
        **os.environ,
        "DISPLAY": display,
        "XDG_CONFIG_HOME": str(profile / "config"),
        "XDG_DATA_HOME": str(profile / "data"),
        "XDG_STATE_HOME": str(profile / "state"),
        "SRPSS_FORCE_LOG_DIR": str(logs),
        **MESA_GL46_OVERRIDE,
    }
    # Windows-shaped variables must not leak in from a parent shell.
    for name in ("APPDATA", "LOCALAPPDATA", "PROGRAMDATA", "QT_QPA_PLATFORM"):
        env.pop(name, None)
    return env


def start_xvfb(display: str, geometry: str = "1920x1080x24", *extra: str) -> subprocess.Popen:
    xvfb = subprocess.Popen(
        ["Xvfb", display, "-noreset", "-screen", "0", geometry, "+extension", "GLX", "+extension", "RANDR", *extra],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    time.sleep(1.0)
    if xvfb.poll() is not None:
        raise SystemExit(f"Xvfb failed to start on {display} (is it installed / is the display free?)")
    return xvfb


# Real repository artwork with authored detail and edges (transitions judged on these, not swatches).
REPO_IMAGES = (
    "ui/assets/onboarding/source/transition_source.png",
    "ui/assets/onboarding/source/transition_destination.png",
    "ui/assets/onboarding/source/SRPSSWitch.png",
    "Docs/Reference/Extruded_Bubble/Targets/Originals/Preset1Goal.png",
    "Docs/Reference/Extruded_Bubble/Targets/Originals/Preset5Goal.png",
    "Docs/Reference/Images/Waveform_Ribbon_Material_Baseline_20261103.png",
)


def copy_repo_images(folder: Path) -> None:
    """Fill *folder* with the real repository artwork listed in ``REPO_IMAGES``."""

    import shutil

    folder.mkdir(parents=True, exist_ok=True)
    for relative in REPO_IMAGES:
        source = REPO / relative
        if source.is_file():
            shutil.copy2(source, folder / source.name)


def generate_images(folder: Path, count: int) -> None:
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


def seed_profile(env: dict[str, str], images: Path, interval: int,
                 disabled_widgets: tuple[str, ...] = DEFAULT_DISABLED_WIDGETS) -> None:
    """Write the isolated profile's folder source, interval and disabled widgets.

    Runs on the harness's own (already started) display: saving Settings records
    per-widget monitor bindings to the current screens' identities, so seeding on
    another platform (e.g. ``offscreen``) would bind every widget to a screen the
    run never has and suppress them all.
    """

    subprocess.run(
        [sys.executable, "-c", PROFILE_SCRIPT, str(images), str(interval), ",".join(disabled_widgets)],
        cwd=REPO,
        env=env,
        capture_output=True,
        check=True,
    )


def grab_screen(display: str, target: Path) -> None:
    from PIL import ImageGrab

    ImageGrab.grab(xdisplay=display).save(target)
