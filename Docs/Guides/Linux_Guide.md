# Linux Guide

How to run, use, build and test SRPSS on Linux. Windows remains the reference product; Linux runs the same
source. Binding rules for keeping it that way: [Linux Compatibility](../Guardrails/Linux_Compatibility.md).
Open Linux work and known gaps: [`Linux_Plan.md`](../../Linux_Plan.md).

## 1. Requirements

- x86-64 Linux with glibc 2.35 or newer (Ubuntu 22.04+, Debian 12+, Fedora 36+, Arch, …).
- An **OpenGL 4.6 Core** driver: NVIDIA proprietary, AMD/Intel Mesa (radeonsi, iris) all qualify. SRPSS
  refuses lower versions by design (no renderer fallback).
- X11 or Wayland (Qt uses XWayland or native Wayland).
- For media and audio features: a D-Bus session bus (every desktop session has one) and
  PulseAudio or PipeWire with `pactl`/`parec` (`pulseaudio-utils`; PipeWire serves them through pipewire-pulse).

## 2. Install a built product

```bash
tar xzf SRPSS-<version>-linux-x86_64.tar.gz
SRPSS-<version>-linux-x86_64/install.sh          # per user; nothing needs root
srpss /c                                          # Settings (also in the app menu)
srpss /s                                          # the saver itself
```

`install.sh` puts the program in `~/.local/opt/srpss`, links `~/.local/bin/srpss`, adds two menu entries and
replaces the curated presets, themes and sounds in `~/.local/share/SRPSS` (the counterpart of the Windows
installer's ProgramData step). `install.sh --uninstall` removes all of that and keeps your settings.

Release builds write no log by default. To enable the main log, create `srpss.logging.cfg` containing `1`
next to the installed `srpss` binary; logs then go to `~/.local/opt/srpss/logs`.

## 3. Use it as a screensaver

Linux has no common screensaver API, so an idle daemon starts the saver after a timeout, and SRPSS exits on
mouse or keyboard input as on Windows:

| Session | Add to the session's autostart |
| --- | --- |
| X11 (most desktops, i3, Openbox) | `xset s 600` and `xss-lock -- srpss /s &` |
| Wayland: sway, niri, river | `swayidle -w timeout 600 'srpss /s'` |
| Wayland: Hyprland | a `hypridle` listener with `on-timeout = srpss /s` |

GNOME and KDE lock screens are separate and keep working. `/p` (preview inside the Windows screensaver
dialog) does not exist on Linux.

## 4. Where things live

| Data | Linux | Windows counterpart |
| --- | --- | --- |
| Settings, caches, state | `~/.config/SRPSS` | `%APPDATA%\SRPSS` |
| Curated presets, themes, sounds | `~/.local/share/SRPSS` | `%ProgramData%\SRPSS` |
| Diagnostic logs | `~/.local/state/SRPSS` | `%LOCALAPPDATA%\SRPSS` |

Absolute `XDG_CONFIG_HOME`, `XDG_DATA_HOME` and `XDG_STATE_HOME` values are honoured (the OS location
contract; SRPSS itself is never configured through environment variables). One owner resolves all of these:
`core/platform_paths.py`.

## 5. What differs from Windows

| Feature | On Linux |
| --- | --- |
| Settings Glass/Acrylic | an opaque underlay derived from each theme replaces the Windows blur |
| Media widget | MPRIS (Spotify, browsers, most players); same provider settings |
| Visualizer audio | the default output's monitor (what is playing), never the microphone |
| Volume slider, mute, volume OSD | PulseAudio/PipeWire through `pactl` |
| Held-left orbit | works; the cursor is not confined to the card (Wayland forbids it) |
| Links from widgets | open directly in the default browser |
| Gmail OAuth / Steam credentials | not persisted yet (no Linux keyring decision); IMAP password stored owner-only |
| Reddit secure-desktop helper, `.scr`, installer, `/p` | Windows-only |

Anything unavailable says so once in the log with a `[PLATFORM]` line.

## 6. Run from source (development)

```bash
scripts/linux/setup.sh --system-deps              # apt packages, .venv-linux, pinned requirements, rcc packs
.venv-linux/bin/python main.py /c
.venv-linux/bin/python main.py /s
```

`setup.sh --python /path/to/python3.14` selects the interpreter (CPython 3.14, 64-bit, standard GIL; without
it the script uses `python3.14` or a uv-managed 3.14). The venv is `.venv-linux`, so a checkout shared with
Windows never touches the Windows `.venv`. Requirements come from the one `requirements.txt`; Windows-only
pins carry `sys_platform == "win32"` markers.

## 7. Build the Linux product

On Linux:

```bash
scripts/linux/setup.sh --system-deps --build
scripts/linux/build.sh                            # release/linux/SRPSS-<version>-linux-x86_64(.tar.gz)
.venv-linux/bin/python tools/linux_smoke_dist.py release/linux/SRPSS-<version>-linux-x86_64
```

The build reads its Nuitka declarations and Qt size exclusions from the Windows build scripts, so new
Windows includes reach Linux automatically. A local build takes about an hour on four cores.

From Windows (no WSL, Hyper-V or Docker; needs only the GitHub CLI, `winget install GitHub.cli` then
`gh auth login`): the Build Runner's optional **Linux** job, or directly

```powershell
.\scripts\linux\build_from_windows.ps1            # -Mode Auto: dispatch if possible, else a temporary tag
```

Both run `.github/workflows/linux-build.yml` on a GitHub Ubuntu 22.04 runner (build, smoke test) and download
the tarball into `release\linux`. The branch must be pushed; GitHub builds the pushed commit.

## 8. Develop and test on Linux

```bash
.venv-linux/bin/python tools/linux_run_headless.py --shots 8,15     # Xvfb run with real artwork, screenshots
.venv-linux/bin/python tools/linux_pytest.py -q tests/test_platform_paths.py
.venv-linux/bin/python tools/linux_pytest.py --chunked --isolated --jobs 3
.venv-linux/bin/python tools/linux_xvfb_hotplug_churn.py --cycles 1
```

The headless tools give only their child process an isolated profile, a private Xvfb display and Mesa's
OpenGL 4.6 override for llvmpipe (`tools/linux_headless.py`); the child's main log directory is redirected with the
product argument `--log-dir=<path>`, not an environment variable. Software rendering proves correctness and
pixels, never performance.

Tests: Linux-only tests live in `tests/test_linux_*.py` and are never collected on Windows; a test pinning a
Windows contract on any OS uses the `windows_platform` fixture or a stated skip
(guardrail §7, `Docs/TestSuite.md` §3.5.1).

## 9. Troubleshooting

| Symptom | Cause / fix |
| --- | --- |
| Exits at start, log says `OpenGL 4.6 Core production requirement was not met` | driver lacks GL 4.6 Core: install the vendor/Mesa driver; check with `glxinfo -B` |
| `Qt resource pack is missing` (source runs) | run `scripts/linux/setup.sh` or `tools/regen_qrc.py` |
| `[PLATFORM] Linux media control (MPRIS) unavailable` | no session bus (e.g. started outside the desktop session) |
| `[PLATFORM] Visualizer audio capture needs parec` | install `pulseaudio-utils` |
| Qt `xcb` plugin errors | `scripts/linux/setup.sh --system-deps` installs the xcb libraries |
| Settings looks flat/opaque | expected: Linux has no Glass/Acrylic compositor primitive (§5) |
