# Current Plan (Forward-Looking)

## 1. Timer-Only Rendering Rollout — **Status: Completed**
- **Outcome:** Refresh-sync/adaptive toggles, settings keys, and tests have been removed. `DisplayWidget` now always derives `_target_fps` from detected Hz, and all GL surface descriptors request `swapInterval=0`.
- **Verification:**
  - `rendering/display_widget.py` hard-caps FPS via `_resolve_display_target_fps()` (adaptive ladder disabled).
  - `rendering/gl_format.py` and backend descriptors never re-enable driver VSync.
  - UI/tests/specs updated to remove references to the deprecated settings.
- **Next Steps:** Monitor logs for any regressions; if future telemetry demands expose VSync again, design a new strategy from scratch rather than resurrecting the legacy flags.

## 2. JSON Settings Migration & Compatibility Harness — **Status: In Progress**
- **Goal:** Replace the Windows-registry QSettings store with neat JSON profiles under `%APPDATA%/SRPSS/` (and `%APPDATA%/SRPSS_MC/` for the MC build), ensure one-shot migration for existing installs, and keep SST import/export + presets fully functional. Existing `.sst` bundles such as `F:/Programming/Apps/ShittyRandomPhotoScreenSaver2_5/2_5_SRPSS_Settings_Screensaver.sst` must import cleanly after the migration, while future exports use the new schema.
- **Progress snapshot (Jan 29):**
  - JSON schema + storage layout defined; `core/settings/json_store.py` implements atomic reads/writes, metadata, and structured sections.
  - SettingsManager now instantiates the JSON store, runs one-shot QSettings migration (with `.bak` backup + metadata), and exposes `storage_base_dir` for tests/tools.
  - Preset + SST flows now operate purely on the JSON snapshot: structured key helpers in `SettingsManager` keep `widgets`/`transitions` dotted access working, `_save_custom_backup()` captures nested JSON payloads, and MC adjustments mutate widget maps instead of flat keys. Legacy `display.refresh_sync`, `display.refresh_adaptive`, `display.render_backend_mode`, and `display.hw_accel` keys are now dropped during SST imports and preset/custom restores so old bundles can’t reintroduce timer caps.
  - `tests/test_presets.py` refactored to use per-test JSON storage roots; suite now passes (`python -m pytest tests/test_presets.py -q`).
  - `Spec.md`, `Index.md`, and `Docs/TestSuite.md` updated with the JSON workflow, and a new `Docs/SETTINGS_MIGRATION.md` spells out the migration + verification steps.

- **Planned execution (remaining work bolded):**
  1. **Schema + storage layout**
     - Define `settings_v2.json` structure (top-level `{version, preset, snapshot}`) with nested sections mirroring `core/settings/defaults.py` and typed dataclasses.
     - Reserve sibling files for `custom_preset_backup.json` and optional audit snapshots; document both SRPSS and SRPSS_MC paths.
  2. **Migration pipeline**
     - Build a migration helper that reads legacy QSettings, canonicalizes/normalizes values (coercions from `SettingsManager.to_bool`, enum fallbacks, removal of retired keys), and writes JSON + a `.bak` of the original registry blob.
     - On first run post-update, detect if JSON exists; if not, run migration, log summary, and mark completion flag.
  3. **JSON-backed SettingsManager** *(done)*
     - New JSON pipeline is live; focus now is on integrating presets/SST workflows with the JSON snapshot (no leftover registry reads).
  4. **SST + preset compatibility**
     - Update SST import to accept both legacy `.sst` (QSettings snapshot) and new JSON exports. For legacy files, parse into the canonical dict then reuse the new manager’s `set_many` path.
     - Update export to emit the JSON schema, retaining `settings_version` metadata so old builds can refuse gracefully.
     - Review `core/presets.py` to ensure preset application, custom backup, and MC adjustments operate on the JSON manager without flattening hacks. *(Done: presets/custom restore now skip legacy display backend/sync keys so toggles never regress timer-only mode.)*
  5. **Tooling & automation**
     - Provide CLI scripts: `python tools/migrate_settings.py --dry-run` (reports would-be changes) and `tools/export_settings.py` (forces JSON snapshot), plus an AppData cleanup helper for QA.
     - Add a guard that detects missing/invalid JSON and rehydrates from defaults instead of silently crashing.
  6. **Tests + validation**
     - JSON manager round-trip tests now cover get/set/cache/save/load. **New:** presets suite refreshed for JsonSettingsStore + MC-adjustment helpers (`python -m pytest tests/test_presets.py -q`).
     - Next: add migration + SST regression tests (include provided `.sst` sample) and refresh integration suites once presets/SST paths land.
     - Integration test that starts the app with a legacy QSettings store, runs migration, and asserts the resulting JSON matches expectations (widget counts, preserved folders, etc.).
     - **Continue running/refreshing suites** after each major step and prune redundant QSettings assumptions.
  7. **Docs + rollout notes**
     - Document the new storage layout in `Spec.md`, `Index.md`, `Docs/TestSuite.md`, and `/Docs/SETTINGS_MIGRATION.md` (steps, paths, troubleshooting).
     - Update Current_Plan once the JSON path is live and ensure release notes highlight the one-time reset behavior (legacy installs fall back to defaults where keys no longer exist).

- **Success criteria (unchanged):**
  - JSON files become the single source of truth with versioned schema + migration flag.
  - Legacy QSettings installs transparently migrate once; MC builds isolate their own file.
  - SST import/export, presets, and UI bindings operate against the new manager without manual registry access.

## 3. Media Card Controls (2.6 Parity) — **Status: Needs parity pass**
- **Why it matters:** The Spotify/Media card in current builds still drifts from the 2.6 reference (layout, control feedback, positioning). QA relies on the card for interaction cues, so we need pixel + behavior parity before pushing any refreshed UI.
- **Reference capture:**
  - Pull historical assets from the Git history (tag/branch `v2_6` in `Basjohn/ShittyRandomPhotoScreenSaver`) for `widgets/media_widget.py`, relevant QML/QSS, and transitional overlays. Document the canonical geometry, colors, and interaction timing.
  - When visual capture is impractical, rely on code diffs (layout constants, gradients, animations) to drive parity decisions.
- **Work items:**
  1. **Layout + styling**
     - [ ] Anchor the card Bottom Left (`OverlayPosition.BOTTOM_LEFT`) using the exact paddings and rounded-rectangle metrics from 2.6.
     - [ ] Reapply the matte glass gradient + divider treatment, matching font families/sizes/weights.
     - [ ] Verify background color/opacity constants match the reference implementation.
  2. **Control feedback**
     - [ ] Re-implement the bright rounded highlight and ~10 % scale pulse used in 2.6.
     - [ ] Ensure both mouse clicks and media-key events trigger the feedback path.
     - [ ] Cross-check `_controls_feedback` timing constants against the 2.6 commit history.
  3. **Positioning rules**
     - [ ] Audit monitor selection logic; preserve 2.6 cross-monitor behavior (affinity + context-menu overrides).
     - [ ] Add regression tests that instantiate the widget for every `WidgetPosition` and assert geometry calculations.
  4. **QA checklist:**
     - Compare current vs 2.6 behavior by diffing code-derived layout metrics and logging control events (no screenshots required).
     - Exercise control clicks + media keys while logging `[MEDIA] play_pause` outputs to confirm event propagation.
     - Validate theming across light/dark backgrounds and with both GL/software backends.
- **Deliverables:** Updated widget code/stylesheets and a short write-up summarizing differences vs 2.6 and how they were resolved (include git commit references for traceability).

## 4. Spotify Visualizer & Volume Visibility — **Status: Active root-cause audit**
- **Issue:** Live runs still never instantiate the Spotify widgets—logs show “Widget setup complete: 5 widgets” with no `[SPOTIFY_*] Created …` lines, so visibility fixes never run. The saved config pins the media card to monitor `2` while the active media card renders on Display 0/1, so WidgetManager skips Spotify creation entirely. Need to audit the whole pipeline (settings → WidgetManager filters → fade sync) for additional blockers.
- **Audit / resolution plan:**
  1. Dump current runtime settings + `settings_v2.json` to confirm monitor selections, and trace WidgetManager’s `_show_on_this_monitor` checks versus actual `screen_index`. Force Spotify creation even when monitor IDs drift (e.g., treat “monitor” mismatches as warnings and fall back to `ALL`).
  2. Once creation is guaranteed, ensure the visibility replay + secondary fade registration we added actually runs in live builds (add verbose logs or perf counters on `_queue_spotify_visibility_sync`, `_register_spotify_secondary_fade`).
  3. If legacy/dead settings still gate Spotify (e.g., hidden `software_visualizer_enabled`, pixel-shift prefs), document and remove them from the runtime path.
  4. Update integration tests to cover monitor-specific scenarios (DisplayWidget on screen 0 while media monitor=2) so we detect this regression earlier.
  5. After fixes, rerun both `python -m pytest tests/test_display_integration.py -k spotify` and the perf cycle (`$env:SRPSS_PERF_METRICS=1; python main.py --debug`) to capture logs proving Spotify widgets instantiate + fade automatically.
- **Deliverables:** Audited settings notes, code fixes for monitor selection + creation, expanded tests/logging, and live-run logs showing `[SPOTIFY_VIS]/[SPOTIFY_VOL] Created …` plus successful fades.

---
**Execution Notes:** Revise this plan whenever ≥50 % of items are delivered so it always reflects current priorities. Attach instrumentation/scripts created for Item 1 to the audit repo once validated, then prune temporary logs to keep production builds lean.
ONLY remove completed items from this plan!