# SRPSS | Linux Plan

Live, ordered Linux compatibility work, kept separate from `Current_Plan.md` at the operator's request.
`[ ]` open, `[~]` candidate awaiting validation, `[x]` landed (one line, pruned once validated).
Durable rules: [`Docs/Guardrails/Linux_Compatibility.md`](Docs/Guardrails/Linux_Compatibility.md); how-to:
[`Docs/Guides/Linux_Guide.md`](Docs/Guides/Linux_Guide.md). Not a changelog.

**Goal:** the same codebase runs on Linux wherever the feature can exist there, while Windows stays the
unchanged reference product. Branch: `claude/eager-carson-5da6ge` (see §6 Merge / rebase).

## 0. How to run, use and build

[`Docs/Guides/Linux_Guide.md`](Docs/Guides/Linux_Guide.md) owns setup, installation, screensaver activation,
data locations, product builds (including from Windows) and the Linux test route. This plan keeps only live work.

## 1. Status by area

| Area | Linux status |
| --- | --- |
| Import graph | all app modules import (only a deliberately Windows-only utility refuses) |
| Settings (`/c`), Guided Setup, themes | renders; Glass/Acrylic use the opaque theme material underlay |
| Saver (`/s`): sources, transitions, widgets, visualizer | renders on GL 4.6 Core (real artwork checked) |
| Monitor hotplug (RandR add/remove) | generations reveal (churn harness) |
| Media widget (now playing + transport + seek + artwork) | MPRIS controller (jeepney) |
| Visualizer audio | default-sink monitor via `parec` sidecar |
| System volume / mute / OSD, app volume slider | `pactl` probe, sink-input controller and live listener |
| Links, Gmail setup, Open App Data | direct `QDesktopServices`; Gmail desktop check passes |
| Held-left orbit | Qt mouse grab (no cursor confinement) |
| Credentials | IMAP password `plain::` 0600; OAuth tokens and Steam not persisted (see §2) |
| `/p` preview, `.scr`, Reddit secure-desktop helper, Inno installer | Windows-only by nature |
| Product build | Nuitka standalone (≈480 MB folder, ≈190 MB tarball) + `install.sh`; local build + smoke pass; GitHub Actions runner |
| Background texture adoption (PR-04), Qt image-pool retention (R-97) | bound on Linux (Itanium exports) |

## 2. Ordered checklist

### Phase 1: boot

- [x] rcc from the interpreter's wheel layout; `core/platform_paths.py` owns per-OS roots.
- [x] Marked `requirements.txt`, `scripts/linux/setup.sh`, `.venv-linux`; headless env/runner/pytest wrapper; conftest isolates XDG.

### Phase 2: runtime correctness

- [x] Links open directly; Windows helper never scheduled/written; Gmail desktop check; Qt folder opening.
- [x] Theme material underlay for Glass/Acrylic; orbit Qt grab; folder spelling follows OS rules.
- [x] Owner-only `plain::` credential files; no-plaintext tests are strict xfail off Windows.
- [ ] **Operator decision: Linux credential encryption.** Secret Service via `secretstorage` (needs a keyring
  daemon; GNOME/KDE have one) would let Gmail OAuth tokens and Steam persist like DPAPI. Until decided,
  Gmail OAuth re-authorises each session and Steam stays unavailable on Linux.
- [x] Texture adoption and image-pool retention bound on Linux; app-volume live listener.
- [ ] Optional: KWin/picom blur-behind for Glass on desktops that offer it (refines the opaque underlay).

### Phase 3: test suite on Linux

- [x] Collection error fixed (live-check harness); `test_s_hotkey_workflow.py` abort was a stale stub on every OS (fixed).
- [x] Whole suite run on Linux (841 files): 765 pass; the 76 failing files all fail on pure `main` under Linux too.
  Fixed from the triage: Extruded Bubble vertex shaders used fragment-only `fwidth` (real cross-driver bug,
  66 tests), custom combo popups showed Fusion scroller strips, raw threads in sidecar readers, and
  Windows-only test assumptions (Steam storage, Task Scheduler harness, ClipCursor, Ctrl+Y redo, QFontInfo
  weight reporting).
- [ ] Remaining Linux failures, all also failing on `main` under Linux, none a known product defect:
  - software GL (llvmpipe) pixel bounds / missing GL functions (~30 tests: Waveform floor and infinite floor,
    Scene3D reflection/target/trails/stream/compute, Neon Lake, native image lifetime, burn, shockwave):
    judge on a real GPU, never loosen;
  - container environment: proxy variables and no IPv6 (`test_network_*`, `test_feed_dns_stall`), PID 1 does
    not reap zombies (`test_worker_parent_death`);
  - a failed real-window test followed by another real window can segfault under llvmpipe
    (`test_visualizer_plain_orbit.py`, `test_extruded_bubble_tiny_temporal.py`; reproduces on `main`).
  Full per-test table: rerun the suite (`tools/linux_pytest.py --chunked --isolated`) and diff against `main`.

### Phase 4: Linux backends

- [x] MPRIS media controller; parec monitor capture; pactl system/app volume.

### Phase 5: build and desktop integration

- [x] `tools/linux_build.py` / `scripts/linux/build.sh` product + `install.sh`; local build and `tools/linux_smoke_dist.py` pass.
- [~] `.github/workflows/linux-build.yml`: awaiting its first GitHub run (operator: `-Mode Tag` or after merge).
- [~] `scripts/linux/build_from_windows.ps1` (parses; guards verified). Awaiting a first operator run.
- [x] Idle activation documented (guide §3); exit-on-input verified on Linux.

### Phase 6: keep up with the default branch

- [ ] Each time the default branch moves: merge it in, then import sweep, headless run and its changed tests
  on Linux; port new Windows-only couplings.

## 3. Awaiting validation (needs a real Linux machine)

- [ ] Real GPU (NVIDIA/AMD/Intel) performance, vsync and pacing; X11 vs Wayland (XWayland) behaviour.
- [ ] Physical multi-monitor and mixed DPI; real players (Spotify, Firefox) over MPRIS; PipeWire desktops.
- [ ] Settings look on a real desktop (underlay vs. taste); fonts available on common distros.
- [ ] Display power (`core/display_power.py`): on GNOME, a real blank (`PowerSaveMode` != 0) parks the Visualizer and
  stops rotation, and unblank resumes it; on KDE/other desktops or without a session bus the inert backend logs
  `[PLATFORM]` once and everything keeps running. Only the selection is tested (`tests/test_linux_display_power.py`).

## 4. Windows regression gates

Shared files touched for Linux and the focused Windows tests that cover them. Run on Windows from the repo
`.venv` before merging; failures block the merge.

```text
tests/test_platform_selection.py tests/test_platform_paths.py tests/test_storage_paths.py
tests/test_storage_root_isolation.py tests/test_logging_config.py tests/test_notification_sound_paths.py
tests/test_settings_theme_system.py tests/test_steam_credentials.py tests/test_widget_theme_link_and_asset_contract.py
tests/test_visualizer_presets.py tests/test_qrc_regeneration.py tests/test_python314_migration_contract.py
tests/test_build_layout.py tests/test_build_runner.py tests/test_clock_timezone_resolution.py
tests/test_secure_url_launcher.py tests/test_main_reddit_helper_preload.py tests/test_reddit_helper_runtime.py
tests/test_desktop_context.py tests/test_onboarding_flow.py tests/test_settings_polish_round.py
tests/test_visualizer_plain_orbit.py tests/test_gmail_oauth.py tests/test_audio_event_session.py
tests/test_media_volume_runtime.py tests/test_native_thread_pools.py tests/test_qtquick_native_texture_handoff.py
tests/test_s_hotkey_workflow.py tests/test_visualizer_live_check.py tests/test_core_audio_callback_probe.py
tests/test_scene3d_spheres.py tests/test_scene3d_spheres_mirrors.py tests/test_extruded_bubble_renderer.py
tests/test_extruded_bubble_world_gpu.py tests/test_qt611_shader_admission.py tests/test_combo_popup_single_outline.py
tests/test_theme_typography.py tests/test_neon_lake_camera_editor.py tests/test_account_setup_controllers.py
tests/test_reddit_helper_task_harness.py tests/test_waveform_studio_lifecycle.py
```

Windows visual checks for the shared fixes: Extruded Bubble presets look unchanged (vertex shaders only lost an
unused fragment-only overload); custom combo popups still open as the same rounded list; Studio open/close still
hides and restores Settings.

`tests/test_linux_*.py` never run on Windows (selection, directory collection and explicit runs all skip them).

Also on Windows: `tools/regen_qrc.py` reports current; one `main.py /c` and `/s` launch; Settings Glass/Acrylic
unchanged; media widget, app volume slider, mute/OSD and visualizer audio unchanged.

## 5. Verification (Linux)

- Import sweep: import every module under `core engine rendering sources ui widgets utils weather helpers`.
- `tools/linux_run_headless.py --shots …` (real artwork): exit 0, transitions/widgets visible, findings reviewed.
- `tools/linux_xvfb_hotplug_churn.py --cycles 1`: every generation reveals.
- Focused tests through `tools/linux_pytest.py`; product: `tools/linux_smoke_dist.py <product dir>`.
- Real services when touched: MPRIS against a session-bus player, capture/volume against a PulseAudio null sink.

## 6. Merge / rebase

- Linux work lands on its branch in narrow `linux:` commits; Windows work continues on the default branch.
- Bring the default branch in with a merge (`git fetch origin main && git merge origin/main`); the branch is
  shared through pushes, so it is never rewritten or force-pushed. Conflicts concentrate in docs
  (`Current_Plan.md`, `Index.md`, `Spec.md`), `requirements.txt`, `tests/conftest.py` and the few shared
  owners listed in §4; the Linux side of each is small (a pointer line, markers, one guarded branch). Keep the
  operator's content and re-apply the Linux line.
- A new direct `%APPDATA%`/`%PROGRAMDATA%` read, `ctypes.windll` at import, `explorer`/`os.startfile`, or a new
  Windows-only dependency without a marker is ported during the rebase (guardrail §2-§5).
- Before merging: §4 green on Windows, §5 green on Linux.

## 7. Unrelated findings (not Linux work)

- `tests/test_visualizer_presets.py`: 3 failures on HEAD (Waveform preset JSON lacks `mode`; Sine pill disabled — Sine since retired).
- Stale tests failing on every OS (seen in the Linux suite, not Linux work): authored preset/content drift
  (`test_visualizer_preset_completeness` 13, `test_defaults_schema_authority`, `test_onboarding_selection` missing
  `visualizer_waveform_ribbon.png`, Sine-disabled dormancy/enable/technical-sync tests, Waveform/Shockwave pose and
  range tests, missing frozen-settings fixture for newer modes in `test_qt611_shader_admission`); stale stubs
  (`test_input_gain`, `test_monitor_replay_admission`, `test_transition_distribution` 3,
  `test_startup_source_onboarding_resume`, `test_settings_theme_lifetime_contract`,
  `test_qtquick_custom_layout_owner` 8 raw musical replay); source-text assertions (`test_feed_f2_contract`,
  `test_frame_trace`, `test_bubble_ambient_glow_contract`, `test_test_suite_durability`, `test_release_media`).
- `tests/test_build_runner.py::test_preflight_passes_a_complete_release_tree`: missing Waveform floor textures.
- `SRPSS_FORCE_LOG_DIR` (logger) is an environment-variable hook used by harnesses; a CLI/sidecar equivalent
  would match the no-env-var preference.
- Reddit cards display raw `requests` exception text (proxy/connection errors) to the user.
- Headless churn: main-process RSS ~490 → 780 MB over three hotplug generations under llvmpipe; not investigated.
