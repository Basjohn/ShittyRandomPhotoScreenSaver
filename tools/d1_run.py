"""Display 1 run: the real saver from source on ONE named display, bounded, with grabbed frames, logs and the trace.

The lead's verification harness (Current_Plan 1B.14; operator, 11 Nov: bounded runs on Display 1 are permitted,
Display 0 is rare: the lead only, through ``--allow-primary``, never in a test, recipe or automated run, and agents never take it). It starts ``main_mc.py`` (or ``main.py``) with the product's own RUN-only flags
``--only-display <index>`` and ``--exit-after <seconds>``, from a COPY of a profile, and brings back:

* **frames**: at the requested times after the first reveal, the saver window's own content on that display (the
  next frame it renders, read back from its swap chain through QRhi on its render thread at the window's device
  pixels, on OpenGL and Vulkan; the image is made and encoded on a writer thread, PNG;
  ``QQuickWindow.grabWindow`` deadlocks against the saver's Python render nodes), cropped around named points of a
  named scene item (default the Visualizer card's frame) and zoomed nearest-neighbour; ``screen`` steps also grab the
  composited desktop of that display (what DWM shows), visible runs only;
* **no live network** unless ``--updates``: the saver runs with ``--noupdates`` (cached feeds, mail and weather);
* **input** driven only by messages posted to the saver's own window on that display (``PostMessageW``: key, move,
  click, right click, double click at device-pixel client coordinates or at a named item's centre); never global
  input, and the system cursor is never moved; an event filter records what the window received;
* **logs and the frame trace** (``--frame-trace`` is always on) in the run folder, ``d1_state.json`` (reveal, every
  step and its result, the self-exit), ``summary.json`` and a verdict.

Fail closed, everything torn down on every path:

* refused before anything starts (exit 2): not Windows; fewer than two displays; an index no display has; the
  chosen display is the primary (Qt's or Windows') unless ``--allow-primary`` (the lead's, rarely, for a specific check nothing else can make; never in tests or automated runs; agents never pass it); its Windows
  monitor cannot be matched; a step after the self-exit; a ``screen`` step in a ``--hidden`` run; an unknown setting;
* a guard checks the saver's visible windows four times a second and kills the run (exit 5) if one lies on another
  display (``--hidden``: if one could show a pixel at all, ``visualizer_live_check``'s guard);
* a watchdog kills the process tree (exit 4) if ``--exit-after`` has not ended it ``--startup-grace`` +
  ``--teardown-grace`` seconds after its deadline;
* any failure (no reveal, a step that failed, no self-exit, a non-zero exit, a native fault line in the logs, no
  frame trace) is exit 3. The profile copy is deleted on every path (its settings files are kept beside the results).

Output goes through ``tools/artifact_paths.py`` + ``tools/evidence_media.py``: the run writes into owner scratch and
is published to ``.artifacts/evidence/display/d1_run/<YYYYMMDD>_<label>/`` on success; a failed run's scratch is kept
and its path printed. ``--hidden`` (agents): the same run with the saver's windows presented but invisible
(``visualizer_live_check.install_invisible_windows``): it proves the plumbing, not what the panel shows.
"""
from __future__ import annotations

import argparse
import atexit
import contextlib
import ctypes
import json
import os
import re
import runpy
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from functools import partial
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from tools import artifact_paths, evidence_media  # noqa: E402
from tools import visualizer_live_check as live_check  # noqa: E402
from tools.live_check_settings_roundtrip import EXIT_AFTER_REASON  # noqa: E402
from tools.run_matrix import FAULT_RE, SAFE_FLAGS  # noqa: E402

ENTRIES = {"mc": ("main_mc.py", "Screensaver_MC", "SRPSS_MC"), "main": ("main.py", "Screensaver", "SRPSS")}
# --frame-trace is always on; --fresh is pointless (logs go to the run's own folder); the short aliases are left out.
DIAG_FLAGS = frozenset(flag for flag in SAFE_FLAGS - {"--fresh", "--frame-trace"} if flag.startswith("--"))


def parse_diag(text: str) -> str:
    """``perf`` (or ``--perf`` in the ``--diag=--perf`` form) -> ``--perf``; only ``run_matrix``'s safe flags."""
    flag = "--" + str(text).lstrip("-")
    if flag not in DIAG_FLAGS:
        raise argparse.ArgumentTypeError(f"--diag takes one of {', '.join(sorted(f[2:] for f in DIAG_FLAGS))}")
    return flag
CROP_NAMES = ("left-mid", "right-mid", "top-mid", "bottom-mid", "top-left", "top-right", "bottom-left", "bottom-right",
              "center")
DEFAULT_ITEM = "visualizerCardFrame"
MAX_SECONDS = 600.0
STATE_NAME = "d1_state.json"

RECIPE = r"""
Recipe: Spline Curve's bar border at the card edge (1B.14 first use). The operator sees the mode's white lines reach
about one pixel past the card border at the left edge (mid height), the bottom edge and both bottom corners; no
off-screen render reproduces it. From the main checkout, on Display 1, with a COPY of the operator's profile (a folder
holding SRPSS and SRPSS_MC, as %APPDATA% does: theme Amethyst Night [Single] [Glass], CUSTOM layout, the mode's white
bar border on; the run copies it again and edits only that copy):

  .venv\Scripts\python.exe tools\d1_run.py --display 1 --profile <profile copy> --mode devcurve
      --setting widgets.global.card_border_width_px=5
      --setting widgets.spotify_visualizer.expanded_display_requested=false
      --clip logs\visualizer_recordings\anything_mixed2.jsonl --seconds 30 --label devcurve_card_edge
      --step 12:grab:steady_a --step 16:grab:steady_b
      --crop left-mid --crop bottom-mid --crop bottom-left --crop bottom-right --zoom 4

and the display-wide card: the same line with expanded_display_requested=true and --label devcurve_display_wide.

Recipe: a Visualizer display move toward Display 1 (Current_Plan 1C.2). Display 0 joins the run with its window ALWAYS
invisible (--with-hidden-display 0: presented, empty region, the guard kills the run if it could show a pixel); the
Visualizer starts display-wide on Display 0 and its up-right glyph, pressed in process, moves it to Display 1 as one
fade-through. Frames on Display 1 across the move; one hidden frame on Display 0 (read back from its back buffer):

  .venv\Scripts\python.exe tools\d1_run.py --display 1 --with-hidden-display 0 --profile <profile copy>
      --mode extruded_bubble --setting widgets.spotify_visualizer.monitor=\"1\"
      --setting widgets.spotify_visualizer.expanded_display_requested=true
      --clip logs\visualizer_recordings\anything_mixed2.jsonl --seconds 40 --label 1c2_move_to_d1
      --step 12:hover@0:@visualizerCardFrame --step 13.5:press@0:@visualizerExpandRightGlyph
      --step 13.6:grab@0:d0_fading --step 13.7:grab:d1_a --step 13.9:grab:d1_b --step 14.1:grab:d1_c
      --step 14.3:grab:d1_d --step 14.6:grab:d1_e --step 15.0:grab:d1_f --step 16.0:grab:d1_g --step 20:grab:d1_steady

Recipe: the Fullscreen Visualizer's display styles (Current_Plan 1D.2). One run per style on Display 1, the
Visualizer display-wide from the reveal, the card frame's edges read at native pixels as in R-192 (``--setting`` and
``set`` take a member of a mapping setting as a dotted key). For STYLE in default, borders_to_edge, hide_borders:

  .venv\Scripts\python.exe tools\d1_run.py --display 1 --profile <profile copy> --mode extruded_bubble
      --setting widgets.spotify_visualizer.monitor=\"1\"
      --setting widgets.spotify_visualizer.expanded_display_requested=true
      --setting widgets.spotify_visualizer.fullscreen_overlays.display_style=\"STYLE\"
      --clip logs\visualizer_recordings\anything_mixed2.jsonl --seconds 30 --label 1d2_STYLE
      --step 12:grab:steady_a --step 16:grab:steady_b
      --crop top-left --crop left-mid --crop right-mid --crop bottom-mid --crop bottom-right --zoom 4

(the same with --mode devcurve for a 2D mode). Then a switch while expanded: the ``set`` steps write the style
through the running saver's own SettingsManager, as Settings would; the product's settings route retargets the card
in place with one fade-through (0.25 s out, 0.25 s in; nothing rebuilt):

  .venv\Scripts\python.exe tools\d1_run.py --display 1 --profile <profile copy> --mode extruded_bubble
      --setting widgets.spotify_visualizer.monitor=\"1\"
      --setting widgets.spotify_visualizer.expanded_display_requested=true
      --setting widgets.spotify_visualizer.fullscreen_overlays.display_style=\"default\"
      --clip logs\visualizer_recordings\anything_mixed2.jsonl --seconds 40 --label 1d2_switch
      --step 12:grab:default_steady
      --step 13:set:widgets.spotify_visualizer.fullscreen_overlays.display_style=\"borders_to_edge\"
      --step 13.1:grab:edge_out --step 13.25:grab:edge_swap --step 13.4:grab:edge_in --step 15:grab:edge_steady
      --step 17:set:widgets.spotify_visualizer.fullscreen_overlays.display_style=\"hide_borders\"
      --step 17.25:grab:hide_swap --step 19:grab:hide_steady
      --step 21:set:widgets.spotify_visualizer.fullscreen_overlays.display_style=\"default\"
      --step 21.25:grab:back_swap --step 23:grab:back_steady
      --crop top-left --crop right-mid --crop bottom-mid --zoom 4

Agents prove it only with --hidden added (every window invisible); never without it, and never with --allow-primary.
Frames land in frames/: <step>.png (the whole window), <step>__<crop>_x4.png, and d1_state.json records each item's
exact scene rectangle (logical and device pixels), the window's DPR and screen. List the displays first:
  .venv\Scripts\python.exe tools\d1_run.py --list-displays
"""


class Refusal(Exception):
    """The run must not start (exit 2)."""


# -- displays ---------------------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class Display:
    index: int                 # the 0-based screen index the product's logs use (``--only-display``)
    name: str
    primary: bool
    x: int                     # Qt geometry (logical size, native top-left)
    y: int
    width: int
    height: int
    dpr: float

    @property
    def device_size(self) -> tuple[int, int]:
        return round(self.width * self.dpr), round(self.height * self.dpr)

    def describe(self) -> str:
        w, h = self.device_size
        return (f"Display {self.index}: {w} × {h} · {round(self.dpr * 100)}%  {self.name}"
                f"{'  (primary)' if self.primary else ''}")


def enumerate_displays() -> list[Display]:
    """The screens as the saver numbers them: Qt's screen list, with the saver's DPI policy (no window is created)."""
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QGuiApplication

    if QGuiApplication.instance() is None:
        QGuiApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
        enumerate_displays._app = QGuiApplication([sys.argv[0]])        # kept alive for the parent's lifetime
    primary = QGuiApplication.primaryScreen()
    displays = []
    for index, screen in enumerate(QGuiApplication.screens()):
        geometry = screen.geometry()
        displays.append(Display(index, screen.name(), screen is primary, geometry.x(), geometry.y(), geometry.width(),
                                geometry.height(), float(screen.devicePixelRatio())))
    return displays


def check_display_choice(displays: list[Display], index: int, *, allow_primary: bool = False) -> Display:
    """The chosen display, or ``Refusal``: two or more displays, the index present, not the primary."""
    if len(displays) < 2:
        raise Refusal(f"only {len(displays)} display present; a D1 run needs a second display")
    chosen = next((display for display in displays if display.index == index), None)
    if chosen is None:
        raise Refusal(f"no display {index} (present: {', '.join(str(d.index) for d in displays)})")
    if chosen.primary and not allow_primary:
        raise Refusal(f"display {index} is the primary display; pass --allow-primary only for a rare lead check nothing else can make")
    return chosen


@dataclass(frozen=True)
class Monitor:
    left: int
    top: int
    right: int
    bottom: int
    primary: bool
    device: str


def win32_monitors() -> list[Monitor]:
    """Every Windows monitor (physical pixels: the parent is per-monitor DPI aware once Qt is up)."""
    from ctypes import wintypes

    class MONITORINFOEXW(ctypes.Structure):
        _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT), ("rcWork", wintypes.RECT),
                    ("dwFlags", wintypes.DWORD), ("szDevice", wintypes.WCHAR * 32)]

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    found: list[Monitor] = []
    proc_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HMONITOR, wintypes.HDC, ctypes.POINTER(wintypes.RECT),
                                   wintypes.LPARAM)

    def collect(hmonitor, _hdc, _rect, _lparam):
        info = MONITORINFOEXW()
        info.cbSize = ctypes.sizeof(info)
        if user32.GetMonitorInfoW(hmonitor, ctypes.byref(info)):
            r = info.rcMonitor
            found.append(Monitor(r.left, r.top, r.right, r.bottom, bool(info.dwFlags & 1), info.szDevice))
        return True

    user32.EnumDisplayMonitors(None, None, proc_type(collect), 0)
    return found


def match_monitor(display: Display, monitors: list[Monitor], *, allow_primary: bool = False) -> Monitor:
    """The Windows monitor showing ``display``: its native top-left and device size (2 px tolerance), exactly one."""
    width, height = display.device_size
    matches = [m for m in monitors if (m.left, m.top) == (display.x, display.y)
               and abs((m.right - m.left) - width) <= 2 and abs((m.bottom - m.top) - height) <= 2]
    if len(matches) != 1:
        raise Refusal(f"display {display.index} matches {len(matches)} Windows monitors "
                      f"({display.describe()}; monitors {[asdict(m) for m in monitors]})")
    if matches[0].primary and not allow_primary:
        raise Refusal(f"display {display.index} is Windows' primary monitor ({matches[0].device})")
    return matches[0]


# -- steps ------------------------------------------------------------------------------------------------------------

_VK = {"ESC": 0x1B, "ESCAPE": 0x1B, "SPACE": 0x20, "RETURN": 0x0D, "ENTER": 0x0D, "TAB": 0x09, "LEFT": 0x25,
       "UP": 0x26, "RIGHT": 0x27, "DOWN": 0x28, **{f"F{n}": 0x6F + n for n in range(1, 13)}}
POINTER_KINDS = ("move", "click", "rclick", "dblclick")
# In-process input (1C.2): delivered to the window through Qt's own event queue (QCoreApplication.postEvent), the
# route for the always-invisible window of --with-hidden-display, whose empty region makes Qt drop posted pointers.
IN_PROCESS_KINDS = ("hover", "press")
# A live setting change (1D.2): ``set:DOTTED.KEY=JSON`` writes one persisted setting through the running saver's own
# SettingsManager (the copied profile's), as a Settings write would, so the product's live settings route reacts.
SETTING_KIND = "set"
STEP_KINDS = ("grab", "screen", "key", *POINTER_KINDS, *IN_PROCESS_KINDS, SETTING_KIND)


@dataclass(frozen=True)
class Step:
    at: float                  # seconds after the first reveal
    kind: str
    arg: str
    display: int | None = None  # ``KIND@N``: the step acts on display N (the run's --with-hidden-display); None: --display

    def text(self) -> str:
        kind = self.kind if self.display is None else f"{self.kind}@{self.display}"
        return f"{self.at:g}:{kind}:{self.arg}"


def virtual_key(name: str) -> int:
    token = name.strip().upper()
    if len(token) == 1 and token.isalnum():
        return ord(token)
    if token in _VK:
        return _VK[token]
    raise ValueError(f"unknown key {name!r} (a letter, a digit or one of {', '.join(sorted(_VK))})")


def parse_target(text: str) -> tuple[str, int, int] | tuple[str, str]:
    """``X,Y`` (device-pixel client coordinates) or ``@objectName`` (the centre of that scene item)."""
    if text.startswith("@") and len(text) > 1:
        return ("item", text[1:])
    match = re.fullmatch(r"\s*(\d+)\s*,\s*(\d+)\s*", text)
    if not match:
        raise ValueError(f"a pointer target is X,Y (device pixels) or @objectName, got {text!r}")
    return ("point", int(match.group(1)), int(match.group(2)))


def parse_step(text: str) -> Step:
    """``AT:KIND:ARG``: AT seconds after the first reveal; grab/screen take a label, key a key name, move/click/rclick/
    dblclick (posted) and hover/press (in process) a target. ``KIND@N`` acts on display N (--with-hidden-display)."""
    parts = str(text).split(":", 2)
    if len(parts) != 3:
        raise argparse.ArgumentTypeError(f"a step is AT:KIND:ARG, got {text!r}")
    at_text, kind, arg = parts
    display: int | None = None
    if "@" in kind:
        kind, _at, index = kind.partition("@")
        if not index.isdigit():
            raise argparse.ArgumentTypeError(f"a step's display is KIND@N (N a display index), got {parts[1]!r}")
        display = int(index)
    try:
        at = float(at_text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"step time must be seconds, got {at_text!r}") from None
    if not at > 0.0 or at != at:
        raise argparse.ArgumentTypeError(f"step time must be positive, got {at_text!r}")
    if kind not in STEP_KINDS:
        raise argparse.ArgumentTypeError(f"step kind must be one of {', '.join(STEP_KINDS)}, got {kind!r}")
    try:
        if kind in ("grab", "screen"):
            arg = artifact_paths.slug(arg)
        elif kind == "key":
            virtual_key(arg)
        elif kind == SETTING_KIND:
            parse_key_value(arg)
        else:
            parse_target(arg)
    except (ValueError, artifact_paths.ArtifactPathError) as exc:
        raise argparse.ArgumentTypeError(str(exc)) from None
    return Step(at, kind, arg, display)


def parse_key_value(text: str) -> tuple[str, object]:
    key, sep, raw = str(text).partition("=")
    if not sep or not key.strip():
        raise argparse.ArgumentTypeError(f"expected KEY=JSON, got {text!r}")
    try:
        return key.strip(), json.loads(raw)
    except json.JSONDecodeError:
        raise argparse.ArgumentTypeError(f"{key}: the value must be JSON (e.g. 5, true, \"text\"), got {raw!r}") from None


def setting_target(key: str, application: str) -> tuple[str, tuple[str, ...]] | None:
    """``(persisted key, member path)`` for a ``set`` step's key: the key itself, or a member inside a mapping-valued
    setting (``widgets.spotify_visualizer.fullscreen_overlays.display_style``); None when it is neither."""
    from collections.abc import Mapping

    from core.settings.default_contract import require_canonical_default

    parts = str(key).split(".")
    for cut in range(len(parts), 0, -1):
        try:
            default = require_canonical_default(".".join(parts[:cut]), application)
        except KeyError:
            continue
        members = tuple(parts[cut:])
        node = default
        for member in members:
            if not isinstance(node, Mapping) or member not in node:
                return None
            node = node[member]
        return ".".join(parts[:cut]), members
    return None


def write_setting(manager, key: str, value: object) -> tuple[object, object]:
    """Write one setting, or one member of a mapping-valued setting merged into a copy of it, through ``manager``;
    returns (before, after) of what ``key`` names, read back."""
    from copy import deepcopy

    target = setting_target(key, manager.get_application_name())
    if target is None:
        raise KeyError(f"{key} is neither a persisted setting nor a member of one")
    persisted, members = target

    def member_of(stored):
        for member in members:
            stored = stored[member] if isinstance(stored, dict) and member in stored else None
        return stored

    stored = manager.get(persisted)
    before = member_of(stored)
    written = value
    if members:
        written = deepcopy(dict(stored)) if isinstance(stored, dict) else {}
        node = written
        for member in members[:-1]:
            node = node.setdefault(member, {})
        node[members[-1]] = value
    manager.set(persisted, written)
    return before, member_of(manager.get(persisted))


def check_plan(args) -> None:
    """Refusals that need no display: the steps fit inside the self-exit, ``screen`` only when visible, known keys."""
    for step in args.step:
        if step.at + 3.0 > args.seconds:
            raise Refusal(f"step {step.text()} is not at least 3 s before the self-exit (--seconds {args.seconds:g}; "
                          "step times count from the first reveal, which comes after the engine starts)")
        if step.kind == "screen" and args.hidden:
            raise Refusal("a screen step grabs the desktop of that display; a --hidden run would grab what lies "
                          "beneath its invisible window")
        if step.display is not None and step.display != args.display:
            if step.display != getattr(args, "with_hidden_display", None):
                raise Refusal(f"step {step.text()} names display {step.display}, which is neither --display nor "
                              "--with-hidden-display")
            if step.kind not in ("grab", *IN_PROCESS_KINDS):
                raise Refusal(f"step {step.text()}: the always-invisible display takes only grab, hover and press "
                              "(posted input is dropped by its empty region; its desktop shows something else)")
        if step.kind == SETTING_KIND:
            key, _value = parse_key_value(step.arg)
            if setting_target(key, ENTRIES[args.entry][1]) is None:
                raise Refusal(f"step {step.text()}: {key} is neither a persisted setting nor a member of one")
    if args.crop and not any(step.kind in ("grab", "screen") for step in args.step):
        raise Refusal("--crop needs a grab or screen step")
    application = ENTRIES[args.entry][1]
    for key, _value in args.setting:
        if setting_target(key, application) is None:
            raise Refusal(f"--setting {key}: not a persisted setting of {application} (nor a member of one)")
        if key.startswith("widgets.spotify_visualizer.") and args.mode and key.split(".")[-1].startswith(f"{args.mode}_"):
            raise Refusal(f"--setting {key}: a {args.mode} mode setting goes through --viz-set (the curated preset "
                          "would overwrite it at activation)")


# -- crops (pure; tested on synthetic images) --------------------------------------------------------------------------

def anchor_point(rect: tuple[float, float, float, float], name: str) -> tuple[float, float]:
    """A named point of ``rect`` (x, y, width, height): its edges' middles, its corners or its centre."""
    x, y, w, h = rect
    columns = {"left": x, "mid": x + w / 2.0, "right": x + w}
    rows = {"top": y, "mid": y + h / 2.0, "bottom": y + h}
    if name == "center":
        return columns["mid"], rows["mid"]
    first, second = name.split("-")
    if first in ("left", "right"):              # left-mid / right-mid
        return columns[first], rows[second]
    if second == "mid":                         # top-mid / bottom-mid
        return columns["mid"], rows[first]
    return columns[second], rows[first]         # top-left, bottom-right ...


def crop_rect(rect: tuple[float, float, float, float], name: str, size: int, bounds: tuple[int, int]
              ) -> tuple[int, int, int, int]:
    """The ``size``-pixel square centred on the named point, kept inside ``bounds`` (image width, height)."""
    if name not in CROP_NAMES:
        raise ValueError(f"unknown crop {name!r}")
    px, py = anchor_point(rect, name)
    width, height = bounds
    side = max(1, min(int(size), width, height))
    left = min(max(0, int(round(px - side / 2.0))), width - side)
    top = min(max(0, int(round(py - side / 2.0))), height - side)
    return left, top, side, side


def zoom_crop(image, rect: tuple[int, int, int, int], zoom: int):
    """``rect`` of a QImage, scaled ``zoom`` times with nearest-neighbour (every source pixel a zoom x zoom block)."""
    from PySide6.QtCore import QRect, Qt

    x, y, w, h = rect
    crop = image.copy(QRect(x, y, w, h))
    crop.setDevicePixelRatio(1.0)
    return crop.scaled(w * zoom, h * zoom, Qt.AspectRatioMode.IgnoreAspectRatio,
                       Qt.TransformationMode.FastTransformation)


# -- settings on the copy -----------------------------------------------------------------------------------------------

def apply_settings(settings: list[tuple[str, object]], *, application: str, storage_base_dir: Path | None = None
                   ) -> dict:
    """Write ``settings`` through the real ``SettingsManager`` of the copied profile; read each back (fail closed).

    In the runner the profile paths already point at the copy (``isolate_profile_paths``), so ``storage_base_dir``
    stays ``None``; tests pass their own folder.
    """
    from core.settings import SettingsManager
    from core.settings.default_contract import require_canonical_default

    manager = SettingsManager(application=application, storage_base_dir=storage_base_dir)
    applied = {}
    for key, value in settings:
        if setting_target(key, application) is None:
            require_canonical_default(key, application)          # the refusal names the key
        before, after = write_setting(manager, key, value)
        if after != value:
            raise ValueError(f"setting {key}={value!r} read back as {after!r}")
        applied[key] = {"before": before, "after": after}
    manager.save()
    if not manager.flush(timeout=10.0):
        raise RuntimeError("the copied profile's settings did not reach disk")
    applied["_path"] = str(manager.get_storage_path())
    return applied


# -- runner (child process) ---------------------------------------------------------------------------------------------

class _InputReceipt:
    """Counts the input events the saver's window received (posted messages arrive as ordinary Qt events)."""

    def __init__(self) -> None:
        from PySide6.QtCore import QEvent, QObject

        names = {QEvent.Type.MouseMove: "mouse_move", QEvent.Type.MouseButtonPress: "mouse_press",
                 QEvent.Type.MouseButtonRelease: "mouse_release", QEvent.Type.MouseButtonDblClick: "mouse_dblclick",
                 QEvent.Type.KeyPress: "key_press", QEvent.Type.KeyRelease: "key_release"}
        self.counts = {name: 0 for name in names.values()}
        receipt = self

        class Filter(QObject):
            def eventFilter(self, _watched, event):        # noqa: N802 (Qt override)
                name = names.get(event.type())
                if name is not None:
                    receipt.counts[name] += 1
                return False

        self.filter = Filter()


def client_size(window) -> tuple[int, int]:
    """The window's client area in device pixels, as Windows sizes it (the swap chain's size)."""
    from ctypes import wintypes

    rect = wintypes.RECT()
    if not ctypes.WinDLL("user32").GetClientRect(ctypes.c_void_p(int(window.winId())), ctypes.byref(rect)):
        raise OSError("GetClientRect failed")
    return rect.right - rect.left, rect.bottom - rect.top


@dataclass(frozen=True)
class RawFrame:
    """A swap chain read-back as the render thread hands it over: Qt's bytes, not yet an image (``frame_image``)."""
    data: object                 # QByteArray, rows of ``width * 4`` bytes
    texture_format: object       # QRhiTexture.Format
    width: int
    height: int
    y_up: bool                   # rows run bottom-up (OpenGL)


def read_back_frame(window) -> RawFrame:
    """Render thread, inside ``afterRendering``: the frame just rendered into the window's swap chain, through QRhi.

    Backend-neutral (OpenGL and Vulkan; N2.8): the read-back of the swap chain's current back buffer is recorded on
    the frame's own command buffer after the scene's pass (``afterRendering`` is outside it), and ``QRhi.finish``
    submits and waits for it, as Qt Quick's own ``grabWindow`` does on its render thread, without blocking the GUI
    thread. Only the read-back runs here; turning the bytes into an image (copy, row flip) is ``frame_image``'s, on the
    writer thread (1C.2: those copies on the render thread cost the other display a frame per 4K grab).
    """
    from PySide6.QtCore import QByteArray
    from PySide6.QtGui import QRhiReadbackDescription, QRhiReadbackResult

    rhi, swap_chain = window.rhi(), window.swapChain()
    if rhi is None or swap_chain is None:
        raise RuntimeError("the window has no QRhi swap chain in afterRendering")
    batch = rhi.nextResourceUpdateBatch()
    if batch is None:
        raise RuntimeError("QRhi has no free resource update batch")
    result = QRhiReadbackResult()
    batch.readBackTexture(QRhiReadbackDescription(), result)   # no texture: the current swap chain's back buffer
    swap_chain.currentFrameCommandBuffer().resourceUpdate(batch)
    rhi.finish()
    size = result.pixelSize
    # ``result.data`` wraps the member of ``result`` (gone with it): a QByteArray copy shares the bytes, no deep copy.
    return RawFrame(QByteArray(result.data), result.format, size.width(), size.height(), rhi.isYUpInFramebuffer())


def frame_image(frame):
    """Writer thread: a ``RawFrame`` as a top-down QImage that owns its bytes; anything else is returned unchanged.

    Alpha is ignored (the window is opaque; the panel shows RGB). The bytes are copied (and OpenGL's bottom-up rows
    turned over) row band by row band in Python, so the writer thread never holds the GIL for long (the saver's
    Python render nodes need it on the render threads): one 4K ``bytes()`` plus ``QImage.flipped`` held it 16 ms
    in one piece. The QImage is made over the new buffer without another copy (PySide keeps the buffer alive).
    """
    if not isinstance(frame, RawFrame):
        return frame
    from PySide6.QtGui import QImage, QRhiTexture

    formats = {QRhiTexture.Format.RGBA8: QImage.Format.Format_RGBX8888,
               QRhiTexture.Format.BGRA8: QImage.Format.Format_RGB32}      # BGRA bytes: 0xffRRGGBB little-endian
    image_format = formats.get(frame.texture_format)
    if image_format is None:
        raise RuntimeError(f"no image format for the swap chain's {frame.texture_format}")
    source = memoryview(frame.data)
    stride = frame.width * 4
    if len(source) != stride * frame.height:
        raise RuntimeError(f"read {len(source)} bytes for {frame.width}x{frame.height}")
    pixels = bytearray(len(source))
    if frame.y_up:
        last = (frame.height - 1) * stride
        for row in range(0, len(source), stride):
            pixels[row:row + stride] = source[last - row:last - row + stride]
    else:
        band = stride * 64
        for start in range(0, len(source), band):
            pixels[start:start + band] = source[start:start + band]
    return QImage(pixels, frame.width, frame.height, stride, image_format)


class _FrameGrab:
    """One frame of a window, read back on its render thread (``afterRendering``) and handed to the GUI thread.

    ``QQuickWindow.grabWindow`` cannot be used on the live saver: it blocks the GUI thread (holding the GIL) until the
    render thread renders, and the saver's Python render nodes need the GIL on that thread (the first hidden run hung
    there until the watchdog ended it). This waits for nothing: the next frame the window renders anyway is read.
    ``render_thread_ms`` is how long the read-back held the render thread (the image is made on the writer thread).
    """

    def __init__(self, window, on_done, timeout_ms: int = 5000) -> None:
        from PySide6.QtCore import QObject, Qt, QTimer, Signal

        class Relay(QObject):
            ready = Signal(object)

        self.window, self.on_done, self.pending = window, on_done, True
        self.render_thread_ms: float | None = None
        self.relay = Relay()
        self.relay.ready.connect(self._deliver, Qt.ConnectionType.QueuedConnection)
        window.afterRendering.connect(self._after_rendering, Qt.ConnectionType.DirectConnection)
        QTimer.singleShot(timeout_ms, self.relay, self._timeout)
        window.update()

    def _after_rendering(self) -> None:                # render thread
        if not self.pending:
            return
        self.pending = False
        began = time.perf_counter()
        try:
            result = read_back_frame(self.window)
        except Exception as exc:                      # handed over and recorded as the step's failure
            result = exc
        self.render_thread_ms = (time.perf_counter() - began) * 1000.0
        self.relay.ready.emit(result)

    def _deliver(self, result) -> None:                # GUI thread
        with contextlib.suppress(RuntimeError, TypeError):
            self.window.afterRendering.disconnect(self._after_rendering)
        callback, self.on_done = self.on_done, None
        if callback is not None:
            callback(result)

    def _timeout(self) -> None:
        if self.on_done is not None:
            self.pending = False
            self._deliver(TimeoutError("the window rendered no frame within the grab timeout"))


class _FrameWriter:
    """PNG encodes on one worker thread; each completion is handed back to the GUI thread.

    Encoding on the saver's GUI thread stalled the run it measured (1C.2, 12 Nov): a 3840x2160 frame takes 2.0-2.3 s to
    encode, no window renders while the GUI thread is busy (the threaded render loop renders after a GUI sync), and
    the product's own edges (a display move's bound, fade and hop) were sampled seconds late, so a 1.85 s move took 7 s.
    ``QImage.save`` releases the GIL (measured), so a worker thread leaves the GUI thread and the render threads free.
    Created on the GUI thread (the relay's affinity); ``drain`` (at exit) waits for and delivers what is still pending.
    """

    def __init__(self) -> None:
        from concurrent.futures import ThreadPoolExecutor

        from PySide6.QtCore import QObject, Qt, Signal

        class Relay(QObject):
            ready = Signal(object)

        self.relay = Relay()
        self.relay.ready.connect(self._deliver, Qt.ConnectionType.QueuedConnection)
        self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="d1-frame-writer")
        self.pending: list = []

    def submit(self, work, on_done) -> None:
        future = self.pool.submit(work)
        entry = (future, on_done)
        self.pending.append(entry)
        future.add_done_callback(lambda _future, e=entry: self.relay.ready.emit(e))

    def _deliver(self, entry) -> None:                # GUI thread (or the exit drain)
        if entry not in self.pending:
            return
        self.pending.remove(entry)
        future, on_done = entry
        error = future.exception()
        on_done(error if error is not None else future.result())

    def drain(self) -> None:
        self.pool.shutdown(wait=True)
        for entry in list(self.pending):
            self._deliver(entry)


class D1Driver:
    """Runner side: at the first reveal, schedule the steps on the GUI thread; record everything in ``d1_state.json``."""

    def __init__(self, steps, *, display: int, out: Path, crops=(), item: str = DEFAULT_ITEM, crop_size: int = 32,
                 zoom: int = 4) -> None:
        self.steps = list(steps)
        self.display = int(display)
        self.out = Path(out)
        self.crops, self.item, self.crop_size, self.zoom = tuple(crops), item, int(crop_size), int(zoom)
        self.began = time.monotonic()
        self.events: list[dict] = []
        self.results: list[dict] = []
        self._engine = None
        self._scheduled = False
        self._receipt: _InputReceipt | None = None
        self._receipt_window = None
        self._grabs: list[_FrameGrab] = []
        self._writer: _FrameWriter | None = None
        self._step_timers: list = []

    def install(self, *, engine_class=None, patch=setattr) -> None:
        if engine_class is None:
            from engine.screensaver_engine import ScreensaverEngine as engine_class
        driver = self
        initialize, stop, reveal = engine_class.initialize, engine_class.stop, engine_class._freeze_revealed_generation

        def recorded_initialize(engine, *args, **kwargs):
            result = initialize(engine, *args, **kwargs)
            driver._engine = engine
            driver._event("initialized", ok=bool(result))
            return result

        def recorded_stop(engine, *args, **kwargs):
            try:
                return stop(engine, *args, **kwargs)
            finally:
                driver._event("stop", reason=kwargs.get("reason"))
                if kwargs.get("reason") == EXIT_AFTER_REASON:
                    driver._event("exit_after_stop")

        def recorded_reveal(engine, *args, **kwargs):
            try:
                return reveal(engine, *args, **kwargs)
            finally:
                driver._on_reveal(engine)

        patch(engine_class, "initialize", recorded_initialize)
        patch(engine_class, "stop", recorded_stop)
        patch(engine_class, "_freeze_revealed_generation", recorded_reveal)
        atexit.register(self.finish)

    def _on_reveal(self, engine) -> None:
        self._event("reveal", generation=getattr(engine, "_runtime_generation", None),
                    windows=self._window_census(engine))
        if self._scheduled:
            return
        self._scheduled = True
        from PySide6.QtCore import Qt, QTimer

        # Precise: Qt's default coarse single-shot may fire 5 % early or late (about 1 s at 22 s), which reordered
        # steps a tenth of a second apart (12 Nov: a grab planned 0.6 s after a press fired before it).
        for index, step in enumerate(self.steps):
            timer = QTimer(engine)                       # parented: lives as long as the engine
            timer.setSingleShot(True)
            timer.setTimerType(Qt.TimerType.PreciseTimer)
            timer.timeout.connect(partial(self.fire, index))
            timer.start(int(round(step.at * 1000.0)))
            self._step_timers.append(timer)
        self._event("armed", steps=[step.text() for step in self.steps])

    def _window_census(self, engine) -> list[dict]:
        rows = []
        for unit in tuple(getattr(getattr(engine, "display_manager", None), "displays", ()) or ()):
            try:
                window = unit.runtime.window
                geometry = window.geometry()
                rows.append({"screen_index": unit.screen_index, "screen": window.screen().name(),
                             "geometry": [geometry.x(), geometry.y(), geometry.width(), geometry.height()],
                             "dpr": window.devicePixelRatio(), "hwnd": int(window.winId())})
            except Exception as exc:                      # a retired unit: recorded, never fatal
                rows.append({"screen_index": getattr(unit, "screen_index", None), "error": repr(exc)})
        return rows

    def _window(self, display: int | None = None):
        engine = self._engine
        manager = getattr(engine, "display_manager", None)
        wanted = self.display if display is None else int(display)
        units = [unit for unit in tuple(getattr(manager, "displays", ()) or ())
                 if unit.screen_index == wanted and not unit.is_retired]
        if len(units) != 1:
            raise RuntimeError(f"{len(units)} live display units on screen {wanted}")
        return units[0].runtime.window

    def fire(self, index: int) -> None:
        step = self.steps[index]
        record = {"index": index, "step": step.text(), "fired_at": self._now()}
        try:
            if step.kind == SETTING_KIND:
                record.update(self._set_setting(step.arg))
                record["ok"] = True
                self._complete(record)
                return
            window = self._window(step.display)
            if step.kind in IN_PROCESS_KINDS:
                record.update(self._send_pointer(window, step.kind, parse_target(step.arg)))
                record["ok"] = True
                self._complete(record)
                return
            if step.kind == "grab":
                # The scene geometry is read now, on the GUI thread; the pixels come from the next rendered frame.
                record.update(self._frame_facts(window))
                grab = _FrameGrab(window, lambda result: self._grabbed(window, step, record, result,
                                                                       grab.render_thread_ms))
                self._grabs.append(grab)
                return
            if step.kind == "screen":
                record.update(self._frame_facts(window))
                screen = window.screen()
                dpr = record["window_dpr"]
                offset = ((window.x() - screen.geometry().x()) * dpr, (window.y() - screen.geometry().y()) * dpr)
                self._write_frame(screen.grabWindow(0), step, record, offset)
                return
            elif step.kind == "key":
                record.update(self._post_key(window, virtual_key(step.arg)))
            else:
                record.update(self._post_pointer(window, step.kind, parse_target(step.arg)))
            record["ok"] = True
        except Exception as exc:
            record.update(ok=False, error=repr(exc))
        self._complete(record)

    def _grabbed(self, window, step: Step, record: dict, result, render_thread_ms: float | None = None) -> None:
        if render_thread_ms is not None:
            record["render_thread_ms"] = round(render_thread_ms, 3)
        if isinstance(result, Exception):
            record.update(ok=False, error=repr(result))
            self._complete(record)
            return
        record["frame_at"] = self._now()
        self._write_frame(result, step, record, (0.0, 0.0))

    def _write_frame(self, image, step: Step, record: dict, offset: tuple[float, float]) -> None:
        """Encode on the writer thread (never the saver's GUI thread: ``_FrameWriter``); complete on the GUI thread."""
        if self._writer is None:
            self._writer = _FrameWriter()

        def written(result) -> None:
            if isinstance(result, Exception):
                record.update(ok=False, error=repr(result))
            else:
                record.update(result)
                record["ok"] = True
            self._complete(record)

        self._writer.submit(partial(self._save_frame, image, step, record, offset), written)

    def _complete(self, record: dict) -> None:
        record["done_at"] = self._now()
        self.results.append(record)
        self._flush()

    # grabs --------------------------------------------------------------------------------------------------------

    def _item_rects(self, window) -> list[dict]:
        """Every visible scene item named ``self.item``: its scene rectangle in logical and in device pixels."""
        found, stack = [], [window.contentItem()]
        while stack:
            item = stack.pop()
            if item is None:
                continue
            if item.objectName() == self.item and item.isVisible() and item.width() > 0 and item.height() > 0:
                scene = item.mapRectToScene(item.boundingRect())
                found.append({"logical": [scene.x(), scene.y(), scene.width(), scene.height()]})
            stack.extend(item.childItems())
        return found

    def _frame_facts(self, window) -> dict:
        """GUI thread, when the step fires: the window, its screen, the Visualizer and the crop item's rectangle."""
        facts = {"client_px": list(client_size(window)), "window_dpr": float(window.devicePixelRatio()),
                 "window_geometry": [window.x(), window.y(), window.width(), window.height()],
                 "screen": window.screen().name(), "visualizer": self._visualizer_facts()}
        if self.crops:
            items = self._item_rects(window)
            if items:
                largest = max(items, key=lambda row: row["logical"][2] * row["logical"][3])
                facts["item"] = {"name": self.item, "logical": largest["logical"], "matches": len(items)}
        return facts

    def _save_frame(self, image, step: Step, record: dict, offset: tuple[float, float]) -> dict:
        image = frame_image(image)                      # a grab's read-back becomes an image here, off the render thread
        if image is None or image.isNull():
            raise RuntimeError(f"{step.kind} returned an empty image")
        frames = self.out / "frames"
        frames.mkdir(parents=True, exist_ok=True)
        path = frames / f"{step.arg}.png"
        if not image.save(str(path)):
            raise RuntimeError(f"could not write {path}")
        saved = {"frame": path.name, "image_size": [image.width(), image.height()]}
        if not self.crops:
            return saved
        item = record.get("item")
        if item is None:
            raise RuntimeError(f"no visible scene item named {self.item!r} (frame kept: {path.name})")
        dpr = record["window_dpr"]
        lx, ly, lw, lh = item["logical"]
        device = (lx * dpr + offset[0], ly * dpr + offset[1], lw * dpr, lh * dpr)
        item["device"] = list(device)
        saved["crops"] = {}
        for name in self.crops:
            rect = crop_rect(device, name, self.crop_size, (image.width(), image.height()))
            crop_path = frames / f"{step.arg}__{name}_x{self.zoom}.png"
            if not zoom_crop(image, rect, self.zoom).save(str(crop_path)):
                raise RuntimeError(f"could not write {crop_path}")
            saved["crops"][name] = {"file": crop_path.name, "source_rect": list(rect)}
        return saved

    def _visualizer_facts(self) -> dict:
        manager = getattr(self._engine, "display_manager", None)
        owner = getattr(manager, "_quick_visualizer_owner", None)
        facts = {"mode": None, "expanded_requested": None, "covered_screen": None}
        with contextlib.suppress(Exception):
            facts["mode"] = str(owner.controller.mode_id)
        with contextlib.suppress(Exception):
            facts["expanded_requested"] = bool(manager._expanded_display_requested())
        with contextlib.suppress(Exception):
            facts["covered_screen"] = manager._expanded_display_coordinator.covered_unit.screen_index
        return facts

    # live settings -----------------------------------------------------------------------------------------------

    def _set_setting(self, text: str) -> dict:
        """``set`` (1D.2): one setting written through the running saver's own SettingsManager (the copied profile),
        a member of a mapping-valued setting merged into a copy of it; read back (fail closed)."""
        manager = getattr(self._engine, "settings_manager", None)
        if manager is None:
            raise RuntimeError("the saver has no settings manager")
        key, value = parse_key_value(text)
        before, after = write_setting(manager, key, value)
        if after != value:
            raise RuntimeError(f"setting {key}={value!r} read back as {after!r}")
        return {"setting": key, "before": before, "value": value}

    # posted input -------------------------------------------------------------------------------------------------

    def _receive(self, window) -> None:
        if self._receipt_window is not window:
            self._receipt = self._receipt or _InputReceipt()
            window.installEventFilter(self._receipt.filter)
            self._receipt_window = window

    def _post(self, window, message: int, wparam: int, lparam: int) -> None:
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        user32.PostMessageW.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_size_t, ctypes.c_ssize_t]
        if not user32.PostMessageW(int(window.winId()), message, wparam, lparam):
            raise OSError(ctypes.get_last_error(), f"PostMessageW {message:#x} failed")

    def _post_key(self, window, vk: int) -> dict:
        self._receive(window)
        scan = ctypes.WinDLL("user32").MapVirtualKeyW(vk, 0)
        self._post(window, 0x0100, vk, 1 | (scan << 16))                              # WM_KEYDOWN
        self._post(window, 0x0101, vk, 1 | (scan << 16) | (1 << 30) | (1 << 31))      # WM_KEYUP
        return {"vk": vk}

    def _target_point(self, window, target) -> tuple[float, float]:
        """The target in the window's logical scene coordinates (an item's centre, or device pixels / DPR)."""
        dpr = float(window.devicePixelRatio())
        if target[0] == "item":
            self.item, wanted = target[1], self.item
            try:
                items = self._item_rects(window)
            finally:
                self.item = wanted
            if not items:
                raise RuntimeError(f"no visible scene item named {target[1]!r}")
            lx, ly, lw, lh = max(items, key=lambda row: row["logical"][2] * row["logical"][3])["logical"]
            return lx + lw / 2.0, ly + lh / 2.0
        return target[1] / dpr, target[2] / dpr

    def _send_pointer(self, window, kind: str, target) -> dict:
        """In-process input (``hover``: a move; ``press``: a move, a left press and its release), queued to the
        window through Qt's event queue, the route a real pointer's events take into the scene (``--with-hidden-
        display``'s invisible window drops posted pointers: its region is empty)."""
        from PySide6.QtCore import QCoreApplication, QEvent, QPointF, Qt
        from PySide6.QtGui import QMouseEvent

        self._receive(window)
        x, y = self._target_point(window, target)
        local = QPointF(x, y)
        global_point = QPointF(window.mapToGlobal(local))
        none, left = Qt.MouseButton.NoButton, Qt.MouseButton.LeftButton
        modifiers = Qt.KeyboardModifier.NoModifier
        events = [(QEvent.Type.MouseMove, none, none)]
        if kind == "press":
            events += [(QEvent.Type.MouseButtonPress, left, left), (QEvent.Type.MouseButtonRelease, left, none)]
        for event_type, button, buttons in events:
            QCoreApplication.postEvent(window, QMouseEvent(event_type, local, global_point, button, buttons, modifiers))
        return {"logical": [x, y], "in_process": True}

    def _post_pointer(self, window, kind: str, target) -> dict:
        self._receive(window)
        dpr = float(window.devicePixelRatio())
        lx, ly = self._target_point(window, target)
        if target[0] == "item":
            x, y = int(round(lx * dpr)), int(round(ly * dpr))
        else:
            x, y = target[1], target[2]
        lparam = (y & 0xFFFF) << 16 | (x & 0xFFFF)
        self._post(window, 0x0200, 0, lparam)                                         # WM_MOUSEMOVE
        down, up, button = {"click": (0x0201, 0x0202, 0x1), "dblclick": (0x0201, 0x0202, 0x1),
                            "rclick": (0x0204, 0x0205, 0x2)}.get(kind, (None, None, 0))
        if down is not None:
            self._post(window, down, button, lparam)
            self._post(window, up, 0, lparam)
        if kind == "dblclick":
            self._post(window, 0x0203, button, lparam)                                # WM_LBUTTONDBLCLK
            self._post(window, up, 0, lparam)
        return {"client_px": [x, y]}

    # state --------------------------------------------------------------------------------------------------------

    def _now(self) -> float:
        return round(time.monotonic() - self.began, 3)

    def _event(self, name: str, **fields) -> None:
        self.events.append({"event": name, "at": self._now(), "wall": time.time(), **fields})
        self._flush()

    def state(self) -> dict:
        return {"display": self.display, "steps": [step.text() for step in self.steps], "events": self.events,
                "results": self.results, "received": self._receipt.counts if self._receipt else None}

    def finish(self) -> None:
        if self._writer is not None:
            self._writer.drain()                       # frames still encoding at exit are written and recorded
        self._event("finish")

    def _flush(self) -> None:
        (self.out / STATE_NAME).write_text(json.dumps(self.state(), indent=1), encoding="utf-8")


def install_display_pair(display: int, hidden_display: int, *, manager_class=None) -> None:
    """Runner side: the saver's windows go on exactly ``display`` and ``hidden_display`` (those present), whatever
    the profile selects; never any other screen (the run fails closed if one would show)."""
    if manager_class is None:
        from engine.display_manager import DisplayManager as manager_class
    pair = {int(display), int(hidden_display)}

    def allowed(self, screen_count: int) -> set[int]:
        return {index for index in pair if 0 <= index < int(screen_count)}

    manager_class._get_allowed_screen_indices = allowed


def _runner(args) -> int:
    from tools import eb_live_phases as phases

    os.chdir(ROOT)
    out = Path(args.out)
    entry, application, _folder = ENTRIES[args.entry]
    live_check.isolate_profile_paths(out)
    phases.production_startup()          # before anything below can import OpenGL
    if args.setting:
        try:
            applied = apply_settings(args.setting, application=application)
        except (KeyError, ValueError, RuntimeError) as exc:
            (out / "settings_refused.txt").write_text(str(exc), encoding="utf-8")
            print(f"REFUSED setting: {exc}", file=sys.stderr)
            return 6
        (out / "applied_settings.json").write_text(json.dumps(applied, indent=1, default=str), encoding="utf-8")
    hidden_display = getattr(args, "with_hidden_display", None)
    if hidden_display is None:
        only = ["--only-display", str(args.display)]
    else:
        # Two displays (1C.2): the product's RUN flag names one screen, so the runner narrows the manager's own
        # selection to exactly these two; the second one's window is always invisible (below).
        only = []
        install_display_pair(args.display, hidden_display)
    sys.argv = [str(ROOT / entry), *args.diag, "--frame-trace", "--exit-after", f"{args.seconds:g}",
                *only, *args.app_arg, "/s"]
    if args.hidden:
        live_check.install_invisible_windows()
    elif hidden_display is not None and not getattr(args, "second_display_visible", False):
        live_check.install_invisible_windows({int(hidden_display)})
    driver = D1Driver(args.step, display=args.display, out=out, crops=args.crop, item=args.item,
                      crop_size=args.crop_size, zoom=args.zoom)
    driver.install()
    with contextlib.ExitStack() as stack:
        if args.clip != "none":
            live_check.install_recorded_music(stack, Path(args.clip), clip_start=args.clip_start,
                                              seconds=args.seconds, app_args=args.app_arg)
        runpy.run_path(str(ROOT / entry), run_name="__main__")
    return 0


# -- parent: launch, guard, watchdog, teardown, verdict -----------------------------------------------------------------

def runner_command(args, out: Path) -> list[str]:
    """The child's command line: the runner with every option it needs, forwarded as given."""
    command = [sys.executable, str(Path(__file__).resolve()), "--runner", "--display", str(args.display),
               "--entry", args.entry, "--seconds", f"{args.seconds:g}", "--out", str(out), "--clip", str(args.clip),
               "--clip-start", f"{args.clip_start:g}", "--item", args.item, "--crop-size", str(args.crop_size),
               "--zoom", str(args.zoom)]
    command += ["--hidden"] if args.hidden else []
    if getattr(args, "with_hidden_display", None) is not None:
        command += ["--with-hidden-display", str(args.with_hidden_display)]
    if getattr(args, "second_display_visible", False):
        command += ["--second-display-visible", "--allow-primary"]
    command += [f"--diag={flag}" for flag in args.diag]
    command += [f"--app-arg={token}" for token in args.app_arg]
    command += [f"--step={step.text()}" for step in args.step]
    command += [f"--crop={name}" for name in args.crop]
    command += [f"--setting={key}={json.dumps(value)}" for key, value in args.setting]
    return command


def off_display_violates(hwnd, window_monitor: tuple[int, int, int, int], monitor: Monitor, *,
                         unseen_ok: bool) -> bool:
    """A visible saver window on ``window_monitor`` breaks the run: it is on another monitor than the chosen one, and
    (with ``unseen_ok``, the always-invisible display's run) it could show a pixel or take a click."""
    if window_monitor == (monitor.left, monitor.top, monitor.right, monitor.bottom):
        return False
    return not (unseen_ok and live_check.window_could_show(hwnd) is None)


@dataclass(frozen=True)
class VisibleWindow:
    """One visible window of the saver's process tree, as one scan saw it."""

    hwnd: int
    monitor: tuple[int, int, int, int]      # the rcMonitor of its nearest monitor
    description: str


def visible_windows(pids: set[int]) -> list[VisibleWindow]:
    """Every visible top-level window of ``pids`` with its monitor: one ``EnumWindows`` scan."""
    from ctypes import wintypes

    user32 = ctypes.WinDLL("user32", use_last_error=True)

    class MONITORINFO(ctypes.Structure):
        _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT), ("rcWork", wintypes.RECT),
                    ("dwFlags", wintypes.DWORD)]

    user32.MonitorFromWindow.restype = wintypes.HMONITOR
    found: list[VisibleWindow] = []

    def collect(hwnd, _lparam):
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value in pids and user32.IsWindowVisible(hwnd):
            info = MONITORINFO()
            info.cbSize = ctypes.sizeof(info)
            user32.GetMonitorInfoW(user32.MonitorFromWindow(hwnd, 2), ctypes.byref(info))     # NEAREST
            r = info.rcMonitor
            rect = wintypes.RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(rect))
            name = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(hwnd, name, 256)
            monitor_rect = (r.left, r.top, r.right, r.bottom)
            found.append(VisibleWindow(
                int(hwnd), monitor_rect,
                f"hwnd {hwnd} class {name.value} rect {(rect.left, rect.top, rect.right, rect.bottom)} "
                f"on monitor {monitor_rect}"))
        return True

    user32.EnumWindows(live_check._EnumWindowsProc(collect), 0)
    return found


def windows_off_monitors(windows: list[VisibleWindow], monitors: tuple[Monitor, ...], *,
                         unseen_ok: bool = False) -> list[str]:
    """The windows of one scan that are on none of ``monitors`` (``off_display_violates`` against each), by handle."""
    return [window.description for window in windows
            if all(off_display_violates(window.hwnd, window.monitor, monitor, unseen_ok=unseen_ok)
                   for monitor in monitors)]


def off_display_windows(pids: set[int], monitor: Monitor, *, unseen_ok: bool = False,
                        scan=visible_windows) -> list[str]:
    """Visible windows of ``pids`` whose monitor is not ``monitor`` (``unseen_ok``: except those that cannot show a
    pixel or take a click, ``visualizer_live_check.window_could_show``: the always-invisible display's window)."""
    return windows_off_monitors(scan(pids), (monitor,), unseen_ok=unseen_ok)


def two_display_guard(monitor: Monitor, second: Monitor, *, scan=visible_windows):
    """The lead's two-display run (``--second-display-visible``): a window violates only when it is on neither named
    monitor. Each check is one scan, each window judged against both monitors by its handle in that scan (two scans
    compared as strings missed a window that moved, or changed its rect, between them)."""
    def guard(pids: set[int]) -> list[str]:
        return windows_off_monitors(scan(pids), (monitor, second))
    return guard


def supervise(command: list[str], *, log_path: Path, deadline_s: float, guard=None, poll_s: float = 0.25,
              kill=None, tree=None) -> dict:
    """Run ``command``; end it on a guard violation or at the deadline; always leave nothing running.

    ``guard(pids) -> list[str]`` names violations; ``kill(pid)`` ends a process tree (``taskkill /T /F``).
    """
    kill = kill or live_check._kill_tree
    tree = tree or live_check._process_tree
    started = time.monotonic()
    with open(log_path, "w", encoding="utf-8") as log:
        process = subprocess.Popen(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
        ended, violation = "exited", None
        try:
            while process.poll() is None:
                if time.monotonic() - started > deadline_s:
                    ended = "watchdog"
                    break
                if guard is not None:
                    found = guard(tree(process.pid))
                    if found:
                        ended, violation = "guard", found
                        break
                time.sleep(poll_s)
        finally:
            if process.poll() is None:
                kill(process.pid)
                try:
                    process.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=15)
    return {"ended": ended, "returncode": process.returncode, "violation": violation, "pid": process.pid,
            "seconds": round(time.monotonic() - started, 1)}


def analyse_run(out: Path, outcome: dict, steps: list[Step], *, hidden: bool = False) -> dict:
    """The verdict from the runner's state, the logs and how the process ended.

    Posted input that never reached the window as a Qt event fails a visible run. A ``--hidden`` run only notes it:
    its window has an empty region, so Qt finds another window under a posted pointer position and drops the event
    (seen in the first hidden run); delivery is the visible run's to prove.
    """
    failures: list[str] = []
    notes: list[str] = []
    if outcome["ended"] == "watchdog":
        failures.append("the watchdog ended the run: --exit-after did not end it in time")
    elif outcome["ended"] == "guard":
        failures.append("a saver window left the chosen display: " + "; ".join(outcome["violation"] or ()))
    elif outcome["returncode"] != 0:
        failures.append(f"the saver process exited with code {outcome['returncode']}")
    state_path = out / STATE_NAME
    state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else None
    events = [event["event"] for event in (state or {}).get("events", [])]
    if state is None or "reveal" not in events:
        failures.append("the saver never revealed (it exited or was ended before its first frame)")
    results = {row["index"]: row for row in (state or {}).get("results", [])}
    for index, step in enumerate(steps):
        row = results.get(index)
        if row is None:
            failures.append(f"step {step.text()} never ran")
        elif not row.get("ok"):
            failures.append(f"step {step.text()} failed: {row.get('error')}")
    received = (state or {}).get("received") or {}
    for kinds, label in ((POINTER_KINDS, "mouse"), (("key",), "key")):
        posted = [step for step in steps if step.kind in kinds]
        if posted and state is not None and not any(count for name, count in received.items()
                                                     if name.startswith(label)):
            message = (f"{len(posted)} posted {label} step(s) and the window received no {label} event "
                       f"({received or 'no receipt'})")
            (notes if hidden else failures).append(message)
    if state is not None and "exit_after_stop" not in events:
        failures.append("the process ended without the --exit-after terminal stop")
    logs = out / "logs"
    faults = []
    for log in sorted(logs.glob("*.log*")) if logs.exists() else ():
        faults += [f"{log.name}: {line.strip()[:200]}"
                   for line in log.read_text(encoding="utf-8", errors="replace").splitlines() if FAULT_RE.search(line)]
    if faults:
        failures.append(f"{len(faults)} native fault line(s) in the logs")
    if not (logs / "screensaver_frame_trace.bin").exists() and "reveal" in events:
        failures.append("no frame trace in the run's logs")
    return {"outcome": outcome, "failures": failures, "notes": notes, "faults": faults[:20],
            "frames": sorted(path.name for path in (out / "frames").glob("*.png")) if (out / "frames").exists() else [],
            "received": (state or {}).get("received"), "results": (state or {}).get("results", [])}


def default_out(args) -> Path:
    label = args.label or artifact_paths.run_label(f"d{args.display}", args.mode or "profile")
    return artifact_paths.evidence_dir("display", "d1_run", artifact_paths.slug(label))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, epilog=RECIPE,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--display", type=int, help="the display index, as the saver's logs number screens (1 = D1)")
    parser.add_argument("--list-displays", action="store_true", help="print the displays and exit")
    parser.add_argument("--allow-primary", action="store_true",
                        help="permit the primary display (rare: the lead only, for a specific check nothing else can make; never in a test, recipe or automated run; agents never pass it)")
    parser.add_argument("--seconds", type=float, default=30.0, help="--exit-after for the saver (default 30, max 600)")
    parser.add_argument("--entry", choices=sorted(ENTRIES), default="mc",
                        help="mc (main_mc.py, interaction mode; default) or main (main.py: input exits the saver)")
    parser.add_argument("--profile", type=Path,
                        help="a folder holding SRPSS and SRPSS_MC (as %%APPDATA%% does); copied, never edited "
                             "(default: %%APPDATA%% itself, copied)")
    parser.add_argument("--mode", help="Visualizer mode id written into the copy (e.g. devcurve = Spline Curve)")
    parser.add_argument("--preset", type=int, help="curated preset, 1-based (default: the profile's own)")
    parser.add_argument("--viz-set", action="append", default=[], type=parse_key_value, metavar="KEY=JSON",
                        help="a Visualizer mode setting (needs --mode; the copy's preset becomes its Custom)")
    parser.add_argument("--setting", action="append", default=[], type=parse_key_value, metavar="DOTTED.KEY=JSON",
                        help="any persisted setting, written to the copy through SettingsManager and read back")
    parser.add_argument("--clip", default="none", help="recorded-music JSONL replayed as the loopback, or none")
    parser.add_argument("--clip-start", type=float, default=0.0, help="seconds into the recording")
    parser.add_argument("--diag", action="append", default=[], type=parse_diag, metavar="NAME",
                        help="a diagnostic flag for the saver without its dashes (repeat): "
                             f"{', '.join(sorted(flag[2:] for flag in DIAG_FLAGS))}; --frame-trace is always on")
    parser.add_argument("--updates", action="store_true",
                        help="let the saver fetch feeds, mail and weather (default: --noupdates, cached data only)")
    parser.add_argument("--app-arg", action="append", default=[], type=live_check.parse_app_arg, metavar="=TOKEN",
                        help="an experiment-flag token for the saver's argv, e.g. --app-arg=--viz-in-process")
    parser.add_argument("--step", action="append", default=[], type=parse_step, metavar="AT:KIND:ARG",
                        help="AT s after the first reveal: grab:LABEL, screen:LABEL, key:NAME, move|click|rclick|"
                             "dblclick:X,Y (device px) or :@objectName, set:DOTTED.KEY=JSON (a setting, or a member "
                             "of a mapping setting, written live through the saver's own SettingsManager)")
    parser.add_argument("--crop", action="append", default=[], choices=CROP_NAMES,
                        help="crop every grab around this point of --item (repeat)")
    parser.add_argument("--item", default=DEFAULT_ITEM, help="scene item objectName the crops follow")
    parser.add_argument("--crop-size", type=int, default=32, help="crop side in device pixels (default 32)")
    parser.add_argument("--zoom", type=int, default=4, help="nearest-neighbour zoom of each crop (default 4)")
    parser.add_argument("--hidden", action="store_true",
                        help="agents: the saver's windows presented but invisible (proves plumbing, not pixels)")
    parser.add_argument("--with-hidden-display", type=int, metavar="N",
                        help="a second display in the run whose window is ALWAYS invisible (presented, empty region, "
                             "the guard kills the run if it could show a pixel): a Visualizer can move between it and "
                             "--display; steps reach it as KIND@N with grab, hover or press (in process)")
    parser.add_argument("--second-display-visible", action="store_true",
                        help="the lead's two-display run: the --with-hidden-display window is shown, not invisible "
                             "(always needs --with-hidden-display and --allow-primary, never --hidden; never in tests, "
                             "recipes or automated runs; agents never pass it)")
    parser.add_argument("--startup-grace", type=float, default=90.0, help="watchdog: seconds allowed before the "
                                                                          "self-exit countdown starts (default 90)")
    parser.add_argument("--teardown-grace", type=float, default=45.0, help="watchdog: seconds allowed after it")
    parser.add_argument("--out", type=artifact_paths.evidence_arg,
                        help="output folder (default .artifacts/evidence/display/d1_run/<YYYYMMDD>_<label>)")
    parser.add_argument("--label", help="run label for the default output folder")
    parser.add_argument("--runner", action="store_true", help=argparse.SUPPRESS)
    return parser


def parse_args(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.list_displays:
        return args
    if args.display is None or args.display < 0:
        parser.error("--display <index> is required (0 = the first screen the saver lists; D1 = 1)")
    if not 0.0 < args.seconds <= MAX_SECONDS:
        parser.error(f"--seconds must be in (0, {MAX_SECONDS:g}]")
    if args.zoom < 1 or args.crop_size < 4:
        parser.error("--zoom must be >= 1 and --crop-size >= 4")
    if args.viz_set and not args.mode:
        parser.error("--viz-set needs --mode")
    if args.app_arg and any(token.startswith("--only-display") for token in args.app_arg):
        parser.error("the display is --display, not an --app-arg")
    if args.with_hidden_display is not None and (args.with_hidden_display < 0
                                                 or args.with_hidden_display == args.display):
        parser.error("--with-hidden-display names another display than --display")
    if args.second_display_visible and (args.with_hidden_display is None or not args.allow_primary or args.hidden):
        parser.error("--second-display-visible needs --with-hidden-display and --allow-primary, and not --hidden")
    if not args.updates and not args.runner:
        args.diag.append("--noupdates")          # no live network unless asked: feeds, mail and weather stay cached
    args.diag = list(dict.fromkeys(args.diag))
    args.crop = list(dict.fromkeys(args.crop))
    args.step = sorted(args.step, key=lambda step: step.at)
    if args.clip != "none":
        args.clip = str(Path(args.clip).resolve())
    return args


def main(argv=None) -> int:
    args = parse_args(argv)
    if args.runner:
        return _runner(args)
    if sys.platform != "win32":
        print("REFUSED: the D1 run harness is Windows-only (posted window messages, the Windows monitor guard)")
        return 2
    try:
        if args.list_displays:
            for display in enumerate_displays():
                print(display.describe())
            return 0
        check_plan(args)
        if args.clip != "none" and not Path(args.clip).is_file():
            raise Refusal(f"recording not found: {args.clip}")
        displays = enumerate_displays()
        chosen = check_display_choice(displays, args.display, allow_primary=args.allow_primary)
        monitor = match_monitor(chosen, win32_monitors(), allow_primary=args.allow_primary)
        if args.with_hidden_display is not None and not any(
                display.index == args.with_hidden_display for display in displays):
            raise Refusal(f"no display {args.with_hidden_display} for --with-hidden-display "
                          f"(present: {', '.join(str(d.index) for d in displays)})")
    except Refusal as exc:
        print(f"REFUSED: {exc}")
        return 2
    print(chosen.describe())
    destination = artifact_paths.checked_output(args.out) if args.out is not None else default_out(args)
    args.out = destination
    out = evidence_media.redirect_output(args, "out", "d1_run")
    out.mkdir(parents=True, exist_ok=True)
    profile_root = args.profile.resolve() if args.profile else None
    entry_folder = ENTRIES[args.entry][2]
    if args.hidden:
        guard = live_check._visible_window_violations
    elif args.second_display_visible:
        # The lead's two-display run: a window violates only when it is on neither of the two named monitors.
        second = match_monitor(next(d for d in displays if d.index == args.with_hidden_display), win32_monitors(),
                               allow_primary=True)
        guard = two_display_guard(monitor, second)
    else:
        # With --with-hidden-display, a window off the chosen monitor is admitted only while it cannot show a pixel.
        guard = partial(off_display_windows, monitor=monitor,
                        unseen_ok=args.with_hidden_display is not None)
    try:
        viz = dict(args.viz_set)
        live_check._prepare_profile(out, args.mode, args.preset, viz, appdata_root=profile_root,
                                    settings_folder=entry_folder)
        plan = {"display": asdict(chosen), "monitor": asdict(monitor), "entry": args.entry, "mode": args.mode,
                "preset": args.preset, "viz_set": viz, "setting": dict(args.setting), "seconds": args.seconds,
                "steps": [step.text() for step in args.step], "crops": args.crop, "item": args.item,
                "hidden": args.hidden, "with_hidden_display": args.with_hidden_display,
                "diag": args.diag, "app_arg": args.app_arg, "clip": args.clip,
                "destination": str(destination)}
        (out / "plan.json").write_text(json.dumps(plan, indent=1), encoding="utf-8")
        outcome = supervise(runner_command(args, out), log_path=out / "runner.txt",
                            deadline_s=args.startup_grace + args.seconds + args.teardown_grace, guard=guard)
    finally:
        kept = live_check.retire_profile_copy(out)
        print(f"profile copy deleted; kept {', '.join(path.name for path in kept) or 'no settings'}")
    summary = analyse_run(out, outcome, args.step, hidden=args.hidden)
    (out / "summary.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
    print(f"ended={outcome['ended']} returncode={outcome['returncode']} seconds={outcome['seconds']}")
    for row in summary["results"]:
        print(f"step {row['step']}: {'ok' if row.get('ok') else 'FAILED ' + str(row.get('error'))}")
    print(f"frames: {len(summary['frames'])}  received: {summary['received']}")
    for note in summary["notes"]:
        print(f"NOTE {note}")
    for failure in summary["failures"]:
        print(f"FAIL {failure}")
    if outcome["ended"] == "guard":
        return 5
    if outcome["ended"] == "watchdog":
        return 4
    return 3 if summary["failures"] else 0


if __name__ == "__main__":
    raise SystemExit(evidence_media.finish(main()))
