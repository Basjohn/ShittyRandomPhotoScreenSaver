# SRPSS | Linux Plan

Live, ordered Linux compatibility work, kept separate from `Current_Plan.md` at the operator's request.
`[ ]` open, `[~]` candidate awaiting validation, `[x]` landed (collapsed to one line, pruned once validated).
Durable rules: [`Docs/Guardrails/Linux_Compatibility.md`](Docs/Guardrails/Linux_Compatibility.md). Not a changelog.

**Goal:** the same codebase runs on Linux wherever the feature can exist there, while Windows stays the
unchanged reference product. Branch: `claude/eager-carson-5da6ge` (see §6 Merge / rebase).

## 0. Quick start (Linux)

```bash
scripts/linux/setup.sh --system-deps          # .venv-linux, pinned requirements, rcc packs
.venv-linux/bin/python main.py /c             # Settings
.venv-linux/bin/python main.py /s             # Saver (needs an image source)
.venv-linux/bin/python tools/linux_run_headless.py --shots 6,14     # Xvfb run + screenshots + log findings
.venv-linux/bin/python tools/linux_pytest.py -q tests/test_platform_paths.py
```

Data roots on Linux: settings/data/cache `~/.config/SRPSS`, curated presets/themes/sounds `~/.local/share/SRPSS`,
diagnostic logs `~/.local/state/SRPSS` (`core/platform_paths.py`).

## 1. Status by area

| Area | Linux status |
| --- | --- |
| Import graph | all app modules import (sweep: 1 deliberate Windows-only utility) |
| Settings window (`/c`), Guided Setup | renders on Xvfb/llvmpipe |
| Saver (`/s`): folder source, retained background, transitions | renders; GL 4.6 Core validated |
| Monitor hotplug (RandR add/remove/re-add) | generations reveal (churn harness) |
| Settings/data/log/curated paths | XDG roots via `core/platform_paths.py` |
| Settings backdrop (Acrylic/Glass) | Windows-only DWM; see §2 Theming |
| Media widget (now playing) | unavailable: no MPRIS controller yet |
| Visualizer audio | sounddevice backend exists; device selection ignores Pulse/PipeWire monitors |
| Volume / mute / OSD | unavailable (pycaw is Windows-only) |
| Links from widgets (Reddit/Gmail/Steam) | broken: routed into the Windows secure-desktop queue |
| Gmail setup / credential storage | blocked (desktop check) / plaintext |
| Orbit drag (held-left camera) | pointer capture is Windows-only; logs a traceback |
| `/p` preview, `.scr` integration, Reddit helper, installer | Windows-only by nature |
| Frozen build | `scripts/linux/build.sh` planned (§4) |

## 2. Ordered checklist

### Phase 1: boot

- [x] `tools/regen_qrc.py` resolves `rcc` from the interpreter's wheel layout.
- [x] `core/platform_paths.py` owns the per-OS roots; settings/data/logs/presets/themes/sounds derive from it.
- [x] `requirements.txt` platform markers; `scripts/linux/setup.sh`; `.venv-linux`.
- [x] Headless harness env (`tools/linux_headless.py`), runner (`tools/linux_run_headless.py`), pytest wrapper (`tools/linux_pytest.py`); conftest isolates XDG roots.

### Phase 2: runtime correctness (silent misbehaviour first)

- [ ] **Links:** `core/windows/secure_url_launcher.open_url` must not enqueue to the Windows helper on Linux
  (it currently creates `./C:\ProgramData/...` in the working directory and reports success). Open through
  `QDesktopServices` on Linux.
- [ ] **Stray ProgramData writes:** `reddit_helper_runtime.clear_session_ticket/refresh_session_ticket` and the
  helper installer breadcrumb must be Windows-only (called from `engine_lifecycle`).
- [ ] **Gmail desktop check:** `core/windows/desktop_context.is_interactive_user_desktop()` is False on Linux and
  blocks setup with Windows-specific wording; a Linux user session is interactive.
- [ ] **"Open App Data" button** (`ui/tabs/widgets_tab_gmail.py`): `explorer` subprocess raises on Linux;
  use `QDesktopServices`.
- [ ] **Orbit drag:** `rendering/quick/pointer_capture.py` raises on non-Windows and `window.py` logs a traceback per
  press; give Linux a Qt-level grab or a single loud "unavailable".
- [ ] **Credentials:** `core/windows/dpapi.py` stores `plain::` text on Linux with a warning per save; Steam storage is
  disabled outright. Decide: Secret Service (`keyring`) vs. owner-only file permissions.
- [ ] **Unavailable features log once, loudly** (`[PLATFORM]`): media controller, volume, DWM backdrop, native
  thread-pool retention (`core/native_threads.py`), native texture adoption.
- [ ] **Theming:** Settings backdrop styles that rely on DWM Acrylic/Glass must present an honest Linux state
  (plain themed surface, option marked unavailable) instead of a silently different look. Audit Theme tab,
  `ui/settings_dialog.py` backdrop path and theme previews on Linux.
- [ ] Folder-source path normalisation (`core/sources/folder_paths.py`): confirm no Windows casefolding of POSIX paths.

### Phase 3: test suite on Linux

- [ ] Fix the one collection error (`tests/test_visualizer_live_check.py` uses `ctypes.windll` at import).
- [ ] Run the chunked suite through `tools/linux_pytest.py`; classify failures as Linux bug / Windows-only test
  needing an explicit skip or fixture / pre-existing (also fails on Windows).

### Phase 4: Linux backends

- [ ] Media: MPRIS controller (QtDBus) behind `create_media_controller`.
- [ ] Visualizer audio: prefer PulseAudio/PipeWire "Monitor of …" sources in `utils/audio_capture.py`.
- [ ] Volume/mute/OSD: Pulse/PipeWire backend (pactl/wpctl or libpulse).

### Phase 5: build and desktop integration

- [ ] `scripts/linux/build.sh`: Nuitka standalone tarball, curated presets/themes deployed to `~/.local/share/SRPSS`.
- [ ] `scripts/linux/build_from_windows.ps1`: run the Linux build inside WSL2 (or Docker) from Windows.
- [ ] `.desktop` entry; optional xscreensaver/XSS idle hook.

## 3. Awaiting validation (needs a real Linux machine)

- [ ] Real GPU (NVIDIA/AMD/Intel) performance, vsync and frame pacing; X11 vs. Wayland (XWayland) behaviour.
- [ ] Physical multi-monitor and mixed DPI; real audio devices; desktop look and feel of Settings.

## 4. Windows regression gates

Shared files touched for Linux, with the focused Windows tests that cover them. Run on Windows from the repo
`.venv` after merging; failures block the merge.

```text
tests/test_platform_paths.py tests/test_storage_paths.py tests/test_storage_root_isolation.py
tests/test_logging_config.py tests/test_notification_sound_paths.py tests/test_settings_theme_system.py
tests/test_steam_credentials.py tests/test_widget_theme_link_and_asset_contract.py tests/test_visualizer_presets.py
tests/test_qrc_regeneration.py tests/test_python314_migration_contract.py tests/test_build_layout.py
tests/test_build_runner.py tests/test_clock_timezone_resolution.py
```

Also: `tools/regen_qrc.py` on Windows must still report `current`, and one `main.py /c` + `/s` launch.

## 5. Verification (Linux)

- Import sweep: import every module under `core engine rendering sources ui widgets utils weather helpers`;
  only deliberately Windows-only utilities may fail.
- `tools/linux_run_headless.py --shots …`: exit 0, screenshots show images/transitions, log findings reviewed.
- `tools/linux_xvfb_hotplug_churn.py --cycles 1`: every generation reveals.
- Focused tests through `tools/linux_pytest.py`.

## 6. Merge / rebase

- Linux work lands only on its branch in narrow commits prefixed `linux:`; Windows-side work continues on the
  default branch untouched.
- Rebase onto the default branch frequently: `git fetch origin && git rebase origin/main`. Conflicts concentrate
  in docs (`Current_Plan.md`, `Index.md`, `Spec.md`), `requirements.txt` and `tests/conftest.py`; the Linux
  side of each is deliberately small (one pointer line, markers, one guarded block). Resolve by keeping the
  operator's content and re-applying the Linux line.
- If a Windows commit adds a new direct `%APPDATA%`/`%PROGRAMDATA%` read, route it through
  `core/platform_paths.py` during the rebase (guardrail §4).
- Before merging: Windows gates in §4 green on Windows; Linux verification in §5 green.

## 7. Unrelated findings (not Linux work)

- `tests/test_visualizer_presets.py`: 3 failures on HEAD independent of platform (Waveform preset JSON lacks
  `mode`; Sine pill disabled).
- `tests/test_build_runner.py::test_preflight_passes_a_complete_release_tree`: missing Waveform floor textures.
- `SRPSS_FORCE_LOG_DIR` (logger) is an environment-variable configuration hook used by harnesses; a CLI/sidecar
  equivalent would match the no-env-var preference.
- Headless churn run: main-process RSS grew ~490 → 780 MB over three hotplug generations under llvmpipe;
  not investigated (software GL, may not reproduce on hardware).
