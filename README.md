# ShittyRandomPhotoScreenSaver (SRPSS)

ShittyRandomPhotoScreenSaver (SRPSS) is a modern Windows screensaver that displays your wallpapers (and optional RSS/JSON feeds) with high‑quality transitions, multi‑monitor support, and overlay widgets (clock, weather, Spotify media, Reddit, etc.), all configurable via a dark-themed settings dialog.

---

## Features

- **Random photo slideshow**
  - Local folders (recursive) as primary source
  - Optional RSS/JSON image feeds (e.g. curated Reddit wallpaper feeds)
  - Mixed mode (folders + RSS) support

- **Display & transitions**
  - Display modes: **Fill**, **Fit**, **Shrink**
  - High‑quality scaling with optional sharpening
  - Transitions:
    - Crossfade
    - Slide
    - Wipe
    - Diffuse
    - Block Puzzle Flip
    - Blinds (GL‑only)
  - Pan & scan (Ken Burns effect) coordinated with the image interval
  - Multi‑monitor aware: same image on all screens or independent images per screen

- **Overlay widgets**
  - **Clock widgets** (up to three): 12h/24h, multiple time zones, analogue or digital
  - **Weather widget** using Open‑Meteo (no API key) with location autodetect on first run
  - **Media widget** (Spotify now‑playing) with optional controls and artwork
  - **Spotify beat visualizer** paired with the media widget
  - **Reddit widget** showing top posts from a configured subreddit
  - Shared shadow/theming for all overlays

- **Settings dialog (config mode)**
  - Dark, frameless UI with custom title bar
  - Tabs:
    - **Sources** – folders + RSS/JSON feeds
    - **Display** – mode, interval, sharpen, pan & scan, monitor selection
    - **Transitions** – transition type, duration, directions, per‑type tuning
    - **Widgets** – clock(s), weather, media, Spotify visualizer, Reddit
    - **About** – version and credits
  - All settings are persisted via a centralized SettingsManager

- **Hard‑exit mode & interaction gating**
  - Optional "hard‑exit" mode: mouse movement/clicks no longer exit; only keyboard exits
  - Ctrl‑driven halo to interact with overlays (e.g. media controls, Reddit links) while the screensaver stays active

---

## Keyboard & Mouse Controls

### While the screensaver is running

- **Hotkeys (do not exit)**
  - `Z` – Previous image
  - `X` – Next image
  - `C` – Cycle transition type
  - `S` – Open settings dialog (stops the saver, shows the config UI)

- **Exit keys (always exit)**
  - `Esc` – Exit screensaver
  - `Q` – Exit screensaver

- **Other keys**
  - **Normal mode** (hard‑exit OFF, Ctrl not held):
    - *Any other key* exits the screensaver (e.g. Space, Enter, arrows, letters, numbers).
  - **Hard‑exit mode** (hard‑exit ON) or **Ctrl interaction mode**:
    - Non‑hotkey keys are ignored; only `Esc`/`Q` exit and `Z/X/C/S` perform their actions.

- **Mouse**
  - **Normal mode** (hard‑exit OFF):
    - Move the mouse beyond a small threshold → exits the screensaver.
    - Any mouse button click → exits the screensaver.
  - **Hard‑exit mode** (hard‑exit ON):
    - Mouse movement and clicks **do not exit**; use `Esc` or `Q` to exit.

- **Ctrl halo interaction**
  - Hold `Ctrl` to show a halo/cursor proxy over the active display.
  - While Ctrl/halo is active, mouse clicks can interact with overlay widgets
    (e.g. media controls, Reddit links) without immediately exiting.

---

## Settings Dialog

You can open the settings dialog in two ways:

- From Windows Screen Saver Settings, by clicking **Settings...** for SRPSS (see below).
- From the running screensaver itself by pressing `S`.

The settings dialog lets you:

- Configure image sources (folders + RSS/JSON feeds)
- Change display mode, interval, sharpen, and pan & scan
- Choose the active transition and per‑type options
- Enable/disable and style each overlay widget
- Enable **Hard Exit** mode (input.hard_exit)

All changes are applied immediately and persisted between runs.

---

## Installation & Usage (Windows 10 / 11)

> These instructions assume you have already built or received `SRPSS.exe` from the project.

### 1. Turn the executable into a screensaver

1. Rename the built executable from `SRPSS.exe` to `SRPSS.scr`.
2. Right-click `SRPSS.scr` and choose **Install**.

Windows will copy the screensaver to the appropriate location and open the **Screen Saver Settings** dialog with SRPSS selected.

If you prefer to place it manually, you can also copy `SRPSS.scr` to a standard location such as `C:\Windows\System32`, then select it from the dropdown as described below.

### 2. Set SRPSS as your screensaver

On **Windows 10** and **Windows 11** you can reach Screen Saver Settings via either:

- **Settings route**:
  1. Open **Settings** → **Personalization** → **Lock screen**.
  2. Scroll down and click **Screen saver settings**.

- **Search route**:
  1. Press `Win` and type `Change screen saver`.
  2. Click the **Change screen saver** control panel entry.

In the **Screen Saver Settings** dialog:

1. Open the **Screen saver** dropdown.
2. Select **SRPSS** (this is the name of the `SRPSS.scr` file).
3. Optionally adjust **Wait** time and **On resume, display logon screen**.
4. Click **Apply** and **OK**.

### 3. Using Settings and Preview in the Screen Saver dialog

- **Settings...**
  - Windows launches the screensaver with the `/c` argument.
  - SRPSS handles `/c` by opening its full settings dialog (`SettingsDialog`).
  - Any optional window handle that Windows passes (e.g. `/c 12345`) is ignored safely; the first `/c` argument is enough to enter config mode.

- **Preview**
  - Windows launches the screensaver with `/p <hwnd>`.
  - SRPSS treats `/p` the same as a normal run and starts the full-screen saver, ignoring the small preview host window.
  - This keeps behaviour simple and predictable: Preview shows the real saver, just like it would appear when activated normally.

---

## Behaviour of the .scr under Windows

- **Will SRPSS.scr show up as a screensaver?**
  - Yes. Any `.scr` placed in a standard location (e.g. `C:\Windows\System32`) will appear in the Screen saver dropdown. SRPSS builds to `SRPSS.exe`; once renamed to `SRPSS.scr`, it will show up as **SRPSS**.

- **Will it be named correctly?**
  - Windows generally uses the base filename (`SRPSS.scr` → `SRPSS`) and, if present, the embedded file description from the EXE. Since the build script names the executable `SRPSS`, the entry will be labelled accordingly.

- **Does the Settings button open the SRPSS settings GUI?**
  - Yes. SRPSS implements Windows’ `/c` (config) argument and routes it to `run_config()`, which launches the Qt `SettingsDialog`.

- **Does Preview launch the screensaver correctly?**
  - **Partially.** `/p <hwnd>` is parsed and recognised as **PREVIEW** mode, but the preview host window is currently logged as "not yet implemented" and no embedded preview is shown.
  - Normal run mode (`/s` or no arguments) is fully implemented and should be used to view the saver.

---

## Versioning

Version information is centralised in `versioning.py` and used by both runtime and build tooling.

- Application name: `ShittyRandomPhotoScreenSaver`
- Executable name: `SRPSS`
- Version string: `APP_VERSION`

This README focuses on runtime behaviour and usage; see `Docs/` for deeper architectural and testing details.
