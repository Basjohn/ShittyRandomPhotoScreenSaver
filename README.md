# ShittyRandomPhotoScreenSaver (SRPSS)
<img width="625" height="202" alt="How dare you hover your cursor here!" src="https://github.com/user-attachments/assets/cbc989a9-a057-49ae-a23a-750d92f6f37c" />

ShittyRandomPhotoScreenSaver (SRPSS) is a modern Windows (W10/W11) screensaver that is suprisingly less shit than the majority of ancient decrepid screensavers around today.
![ShittyRandomPhotoScreenSaverS](https://github.com/user-attachments/assets/41e1e70f-1bfa-4934-b470-3753aaebfc96)

---

Shitty Showcase where I cut off the Spotify controls in recording.

## Features

- **Random Image Slideshow**
  - Local folders (recursive) as primary source
  - Optional RSS/JSON image feeds (e.g. curated Reddit wallpaper feeds)
  - Mixed mode (folders + RSS) support
  - High‑quality scaling with optional sharpening
  - Transitions:
    - Crossfade
    - Slide
    - Wipe
    - Diffuse
    - Block Puzzle Flip
    - Blinds (GL‑only)
  - Pan & scan (Ken Burns effect) coordinated with the image interval, but don't use it, please, it fucks everything up.
  - Multi‑monitor aware: same image on all screens or independent images per screen

- **Overlay widgets**
  - **Clock widgets** (up to three): 12h/24h, multiple time zones, analogue or digital
  - **Weather widget** using Open‑Meteo (no API key) with location autodetect on first run
  - **Media widget** (Spotify now‑playing) with optional controls and artwork
  - **Spotify beat visualizer** paired with the media widget
  - **Reddit widget** showing top posts from a configured subreddit
  Widget requests are welcome, the engine is robust enough to handle all sorts of your weird kinky shit.

- **Settings dialog (config mode)**
  - Dark, frameless UI.r
  - Tabs:
    - **Sources** – folders + RSS/JSON feeds
    - **Display** – mode, interval, sharpen, pan & scan, monitor selection
    - **Transitions** – transition type, duration, directions, per‑type tuning
    - **Widgets** – clock(s), weather, media, Spotify visualizer, Reddit (You'll need to configure these to your liking! Geolocation is kinda shit.)
    - **About** – version, credits and emergency defaults button
    
- **Hard‑exit mode & interaction gating**
  - Optional "hard‑exit" mode: mouse movement/clicks no longer exit; only keyboard exits
  - Ctrl‑driven halo to interact with overlays (e.g. media controls, Reddit links) while the screensaver stays active.

  Why? Because you can actually click those reddit links! You can actually control Spotify through its controls in the widget! I never clicked the clock or weather though, you probably shouldn't     try it.

  Cntrl holding gives you a temporary interaction mode that makes you able to move/see/click the mouse without exiting (but if you click a reddit link we're going to exit and take you to the         comments so you can join everyone else in not reading the article/source)  

  Hard Exit on the other hand makes nothing except ESC close the screensaver. (This is replicated in the SRPSS_MC release version)
  While seeming strange at first, if you have multiple monitors you can pick one or two of them, leave it running 24/7 with widgets of your choice. Your image will change reducing any burn worries   and you have pretty widgets.

  (If you have an OLED nothing is gonna stop burn in except a black screen but you know that already)  
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

Download a version, ideally the setup version if you want it to actually work.

### 1. Run the installer.

1. Yeah that's literally it.
2. Really.

### 2. Set SRPSS as your screensaver

Find the Configure ShittyRandomScreenSaver on your desktop or Start Menu, it will take you to Windows Screen Saver Settings, select SRPSS, configure the settings by clicking well, settings and you're set. 

If you're super lazy just set it and it'll freak out on the first start asking you to configure it.

Alternative Route:
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

### 3. Settings
  - Set your sources! Either a folder (or multiple) on your system with your wallpapers or RSS/JSON feeds or....both, yeah, both actually works.
  - If you are exceptionally lazy about your sources just click the "Just Make It Work" button at the bottom of the sources tab. It will just work.
  
  - Clock does a decent job figuring out your timezone, you can have multiple timezones and up to 3 clocks, optionally digital or analogue and with different regions per display.
  - Weather does a really bad job of figuring out where you are but has awesome autocomplete so just start typing your City name and click the suggestion.
  - Reddit can be set to any subreddit you want.
  - Pro tip, don't set widgets to appear at the same location on the same screen. By default they don't.

## Versioning

Version information is centralised in `versioning.py` and used by both runtime and build tooling and Inno installer is used for this to actually fucking work.

- Application name: `ShittyRandomPhotoScreenSaver`
- Executable name: `SRPSS`
- Version string: `APP_VERSION`

## Credits

- Weather icons: [Basmilius Weather Icons – Line](https://basmilius.github.io/weather-icons/index-line.html)

This README focuses on wasting your time.
