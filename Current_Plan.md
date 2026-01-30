# Current Plan (Forward-Looking)

## 2. JSON Settings Migration & Compatibility Harness — **Status: In Progress**

- **Goal:** Replace the Windows-registry QSettings store with neat JSON profiles under `%APPDATA%/SRPSS/` (and `%APPDATA%/SRPSS_MC/` for the MC build), ensure one-shot migration for existing installs, and keep SST import/export + presets fully functional. Existing `.sst` bundles such as `F:/Programming/Apps/ShittyRandomPhotoScreenSaver2_5/2_5_SRPSS_Settings_Screensaver.sst` must import cleanly after the migration, while future exports use the new schema.
- **Progress snapshot (Jan 29):**
  - JSON schema + storage layout defined; `core/settings/json_store.py` implements atomic reads/writes, metadata, and structured sections.
  - SettingsManager now instantiates the JSON store, runs one-shot QSettings migration (with `.bak` backup + metadata), and exposes `storage_base_dir` for tests/tools.
  - Preset + SST flows now operate purely on the JSON snapshot: structured key helpers in `SettingsManager` keep `widgets`/`transitions` dotted access working, `_save_custom_backup()` captures nested JSON payloads, and MC adjustments mutate widget maps instead of flat keys. Legacy `display.refresh_sync`, `display.refresh_adaptive`, `display.render_backend_mode`, and `display.hw_accel` keys are now dropped during SST imports and preset/custom restores so old bundles can’t reintroduce timer caps.
  - **Planned execution (remaining work bolded):**
  1. **Schema + storage layout** *(done)*
     - Finalized `settings_v2.json` schema (top-level `{version, profile, metadata, snapshot}`) and documented sibling files (`custom_preset_backup.json`, `backups/qsettings_snapshot_*.json`) for both SRPSS and SRPSS_MC.
  2. **Migration pipeline polish** *(done)*
     - First-run detection now logs migration results and stamps `last_migration_completed`; missing/invalid JSON triggers a default regeneration with a warning instead of crashing.
  3. **JSON-backed SettingsManager** *(done)*
     - New JSON pipeline is live; focus now is on integrating presets/SST workflows with the JSON snapshot (no leftover registry reads).
  4. **SST + preset compatibility** *(code complete; needs tests)*
     - Export path now emits the JSON schema + metadata; import path normalizes legacy flat snapshots, keeps `custom_preset_backup`, and still skips retired display keys. Next up: extend presets/tests to cover these paths.
  5. **Runtime guards** *(done)*
     - JsonSettingsStore tracks load failures; SettingsManager regenerates defaults and logs recovery when corruption is detected.
  6. **Tests + validation (remaining work)**
     - JSON manager round-trip tests now cover get/set/cache/save/load. **New:** presets suite refreshed for JsonSettingsStore + MC-adjustment helpers (`python -m pytest tests/test_presets.py -q`).
     - Add migration + SST regression tests (include provided `.sst` sample) for the new schema/normalization logic.
     - Add an integration test that starts with a legacy QSettings store, runs migration, and asserts the JSON snapshot (widget counts, folders, metadata).
     - **Continue running/refreshing suites** after each major step and prune redundant QSettings assumptions.
  7. **Docs + rollout notes**
     - `Spec.md` now captures the schema + sibling files; update `Docs/TestSuite.md` and `/Docs/SETTINGS_MIGRATION.md` again once the new tests land, then refresh release notes before shipping Item 2.

- **Success criteria (unchanged):**
  - JSON files become the single source of truth with versioned schema + migration flag.
  - Legacy QSettings installs transparently migrate once; MC builds isolate their own file.
  - SST import/export, presets, and UI bindings operate against the new manager without manual registry access.

## 3. Media Card Controls & Spotify Overlay Reliability — **Status: In progress (runtime fixes outstanding)**

- **Why it matters:** The media/Spotify overlay set still drifts from the 2.6 UX and now shows three live regressions: (a) the Spotify volume slider previously left the card bounds (pixel shift isolation resolved, but needs regression tests), (b) the media card never enters its polling loop because the widget rarely receives a ThreadManager and therefore never refreshes metadata/does not emit `media_updated`, and (c) hardware/media-key presses only propagate through WM_APPCOMMAND; Qt key events never refresh the card, so visualizer/metadata stay stale. Controls also occupy too much vertical space; we need to shrink them ~20 % to match the design intent.
- **New observations (Jan 30 22:37):** Cross-display fade sync now leaves Reddit overlays inconsistent—`reddit2` on Display 0 fades immediately while the `reddit`/`reddit2` pair on Display 1 sit idle ~3 s before starting their fade, indicating fade-sync bookkeeping isn’t registering all expected overlays. Additionally, media key presses correctly trigger the visualizer + metadata refresh, but the play/pause glyph never flips when the Play/Pause key is used; the optimistic state override must run even when the controller command originates from media keys.

- **Areas of focus:**
  1. **Lifecycle + polling wiring**
     - [ ] Ensure `MediaWidget` always inherits the display ThreadManager (or falls back to a safe synchronous poll once) before `start()`/`activate()` so `_refresh_async` is actually scheduled and media_updated events fire. *Diagnostics (Jan 30 15:05)*: runtime logs show no `[OVERLAY_TIMER] MediaWidget smart poll` entries, proving `_ensure_timer()` exits before creating a timer because `_ensure_thread_manager()` still fails after activation. Need to make ThreadManager injection airtight (WidgetManager reuse path + parent inheritance) and ensure `_ensure_timer()` retries once TM exists.
     - [ ] Switch factory/WidgetManager startup to prefer the lifecycle hooks (`initialize`/`activate`) instead of the legacy `start()` path so `_enabled`/timers stay consistent with BaseOverlayWidget state. *Observation:* second-screen DisplayWidget reuse never re-injects the ThreadManager, so lifecycle hooks run without it. Patch WidgetManager to always call `set_thread_manager` when binding cached widgets and add logging when lifecycle kicks off without TM.

  2. **Layout + styling parity (from v2.6)**
     - [~] Reapply the matte glass gradient + divider treatment everywhere and shrink the control row footprint (~20 % smaller button rects/margins) while preserving hit targets. *Gradient renderer + tighter layout math landed, but runtime still shows legacy sizing because cached geometry never invalidates; need to flush `_controls_layout_cache` when font metrics change and verify against v2.6 screenshots.*
     - [ ] Match the rounded metrics/padding used in v2.6 so the card looks identical even when relocated.

  3. **Interaction feedback & media keys**
     - [x] Re-implement the bright rounded highlight + ~10 % scale pulse on the transport controls so both clicks and media-key events share the same flash logic.
     - [ ] Route Qt-level media keys through `_handle_media_key_feedback` → `_invoke_media_command(..., execute=False)` so keyboard media keys trigger the same optimistic updates even when WM_APPCOMMAND is not delivered.
     - [ ] Ensure play/pause glyph flips immediately when media keys fire—optimistic `_apply_pending_state_override` needs to run for those paths too.

  4. **Positioning & pixel shift rules**
     - [x] Remove Spotify volume widget from PixelShiftManager to keep it aligned with the media card.
     - [ ] Add regression tests to ensure grouped widgets (media + volume + visualizer) respect shared anchors even when pixel shift is enabled.

  5. **Metadata refresh & playback state**
     - [ ] Introduce a lightweight polling/refresh hook (and updated idle wake) so the media card updates artwork/track/state even without manual interaction, rate-limited to avoid GSMTC thrash. *First root cause identified: `_ensure_timer()` uses `_update_timer_handle` as the only guard, so once activation fails (no TM) the method never retries and the widget never enters the polling loop. Need to decouple the guard from `_update_timer_handle`, log failures, and add regression tests that assert timer creation is logged.*
     - [ ] Confirm media_updated/visualizer wake flows fire after the above lifecycle fixes. *Add runtime log assertions (media_updated + `[SPOTIFY_VIS] media_update …`) in the integration suite so media keys force refreshes.*

  6. **QA & diagnostics**
     - [ ] Add integration coverage that simulates playback state transitions + pixel shift to verify widgets stay within bounds and metadata updates without user interaction.
     - [ ] Document the finalized workflow (Spec/Docs/TestSuite) once the above land.
     - [ ] Add cross-display fade-sync regression coverage so `reddit`/`reddit2` pairs always enter fade simultaneously on every monitor.

---
**Execution Notes:** Revise this plan whenever ≥50 % of items are delivered so it always reflects current priorities. Attach instrumentation/scripts created for Item 1 to the audit repo once validated, then prune temporary logs to keep production builds lean.
ONLY remove completed items from this plan!