# Current Plan

Update this after every significant change.

Rules:
- Keep this aligned with [Index.md](F:\Programming\Apps\ShittyRandomPhotoScreenSaver\Index.md), [Spec.md](F:\Programming\Apps\ShittyRandomPhotoScreenSaver\Spec.md), [Docs/Defaults_Guide.md](F:\Programming\Apps\ShittyRandomPhotoScreenSaver\Docs\Defaults_Guide.md), and [Docs/Visualizer_Debug.md](F:\Programming\Apps\ShittyRandomPhotoScreenSaver\Docs\Visualizer_Debug.md).
- Do not mark runtime or visual-feel issues as fixed without user confirmation.
- Treat `presets/visualizer_modes` as the only authored visualizer preset source tree.
- Treat `release/main_mc.dist/presets/visualizer_modes*` as generated artifacts only.
- Do not start riskier renderer/visual work until preset/runtime plumbing is green again.
- Keep checkboxes honest:
  - `[x]` landed and validated
  - `[~]` partially proven / still needs runtime eyes
  - `[ ]` not done

---

## Snapshot

- Date: `2026-04-03`
- Current status:
  - [x] Preset source tree recovered and re-stabilized after revert damage
  - [x] Shipped MC preset tree regeneration is working again
  - [x] Canonical runtime creator bridge is accepting the current authored Spectrum schema again
  - [x] Organs synthetic baseline now matches the actual authored `Preset 1`
  - [x] Canonical defaults now expose a normalized `widgets.spotify_visualizer` section with `enabled=True`, `mode=spectrum`, and `preset_spectrum=0`
  - [x] Fresh/default settings-manager startup now keeps `widgets.spotify_visualizer` repair-free in targeted probes/tests
  - [~] The user's live roaming `%APPDATA%` snapshot still contains older visualizer-era state from before this patch, so the log watch stays open until the user reruns defaults on the fixed build
- Immediate work order:
  - [x] Baseline stabilization and documentation
  - [x] Add conservative `--fresh` startup switch for script/log debugging
  - [x] Spectrum conservative cleanup task 1: reclaim side space in `BARS` / `SEGMENTS`
  - [x] Spectrum conservative cleanup task 3: rebuild Spectrum into real buckets
  - [x] Spectrum conservative cleanup task 2: replace `Single Piece Mode` with `SEGMENTS` / `BAR`
  - [ ] Commit after 1/2/3
  - [ ] Only then continue with border-colour participation, energy arrows, and final consolidation

---

## 0. Baseline Stabilization

Status:
- [x] Active stability pass complete

What was re-proven:
- [x] Curated preset audit is clean:
  - `python tools/visualizer_preset_repair.py --audit-curated`
- [x] Shipped preset artifacts regenerate from source:
  - `python tools/regenerate_visualizer_shipped_presets.py`
- [x] Canonical preset/default suites are green:
  - `python -m pytest tests/test_visualizer_presets.py tests/test_visualizer_preset_manifest.py tests/test_settings_defaults_parity.py tests/test_settings_dialog.py tests/test_visualizer_preset1_baselines.py -q`
  - `94 passed`
- [x] Runtime creator-bridge regression fence is green:
  - `python -m pytest tests/test_visualizer_settings_plumbing.py -k "CreatorKwargs or critical_settings_passed_through or canonical_spectrum_fields or LiveConfigGuard" -q`
  - `4 passed`

Latest concrete findings:
- [x] Latest visualizer logs show shader startup is healthy again:
  - `Loaded 5/5 shaders`
  - `Multi-shader pipeline ready`
  - no latest shader compile/link failure in the checked logs
- [x] Latest runtime logs show real mode application again instead of generic fallback-only behavior:
  - `mode=bubble`
  - `mode=spectrum`
  - `mode=oscilloscope`
  - `mode=sine_wave`
  - `mode=blob`
- [x] `Preset 1 (Organs)` in source is currently authored as `35` bars, not `33`
- [x] The old recorded Organs synthetic baseline was therefore stale and has been refreshed to the current authored source-of-truth
- [x] The settings-tab debug spam was not another preset failure:
  - root cause: `WidgetsTab._build_current_spotify_visualizer_config()` called `save_media_settings(self)` before lazy Media controls necessarily existed
  - landed fix: return the stored visualizer config unchanged when required Media/Visualizer controls do not exist yet
  - regression coverage added so this does not quietly come back

Still open / watch:
- [x] Latest pre-fix logs showed `Settings validation repaired 1 issues: ['widgets.spotify_visualizer']`
- [x] Root cause was split across two seams:
  - [x] startup default-merge seeded the visualizer section from a non-canonical nested defaults payload
  - [x] that nested payload omitted `enabled`, so the model resolved the Beat Visualizer to off on defaults
- [x] Landed repo fix:
  - [x] `core/settings/defaults.py` now returns a normalized visualizer default section
  - [x] `SettingsManager._ensure_widgets_defaults()` now canonicalizes fresh/default visualizer insertion without rewriting existing user-authored sections
- [~] Live roaming AppData still needs one post-fix user run to prove the old repair line is gone for good

Validation history that matters:
- [x] `python tools/visualizer_preset_repair.py --audit-curated`
- [x] `python tools/regenerate_visualizer_shipped_presets.py`
- [x] `python -m pytest tests/test_visualizer_presets.py tests/test_visualizer_preset_manifest.py tests/test_settings_defaults_parity.py tests/test_settings_dialog.py tests/test_visualizer_preset1_baselines.py -q`
- [x] `python -m pytest tests/test_visualizer_settings_plumbing.py -k "CreatorKwargs or critical_settings_passed_through or canonical_spectrum_fields or LiveConfigGuard" -q`
- [x] `python -m pytest tests/test_settings_manager.py tests/test_settings_defaults_parity.py tests/test_visualizer_settings_plumbing.py -k "visualizer or defaults or CreatorKwargs or critical_settings_passed_through or canonical_spectrum_fields or LiveConfigGuard" -q`
- [x] Fresh settings-manager probe after the fix now reports:
  - [x] `enabled=True`
  - [x] `mode=spectrum`
  - [x] `preset_spectrum=0`
  - [x] `validate_and_repair() == {}`

---

## 1. Preset / Schema Lessons We Must Not Lose Again

Status:
- [x] Documented

These are the missing guardrails that caused the last disaster:
- [x] `presets/visualizer_modes` is the authored source-of-truth tree
- [x] `release/main_mc.dist/presets/visualizer_modes*` is generated output and can drift independently because it is not the authored git source
- [x] A hard git revert does **not** restore generated release artifacts or user AppData/cache state to the same moment as source code
- [x] Live `%APPDATA%/SRPSS/settings_v2.json` and settings-dialog cache can preserve stale visualizer schema even when the repo looks reverted/healthy
- [x] A baseline commit touching presets/settings must verify all of these together:
  - [x] source curated preset tree
  - [x] generated shipped preset tree regeneration
  - [x] canonical defaults snapshot parity
  - [x] creator/runtime apply bridge
  - [x] Organs synthetic feel fence
  - [ ] live roaming AppData drift status
- [x] General preset tests must stay structural:
  - schema hygiene
  - slot uniqueness
  - repair/reindex behavior
  - generated shipped-tree parity
  - authored preset names/content remain fluid outside the explicit synthetic fence

What has to remain true moving forward:
- [x] The build-linked regeneration path stays the standard path, not manual drift chasing
- [x] `tools/visualizer_preset_repair.py` must remain flexible with evolving authored schema
- [x] Curated preset names/content must not be hardcoded in tests beyond the explicit `Preset 1` feel fence
- [x] Runtime cache payloads such as `cache/reddit/*.json` are generated state, not authored repo content

---

## 1.1 Startup / Logging Guardrails

Status:
- [x] `--fresh` startup switch landed

Contract:
- [x] `--fresh` clears the resolved runtime log folder before `setup_logging()` attaches handlers
- [x] worker logs are preserved during `--fresh` cleanup:
  - [x] `worker_*.log`
- [x] `--fresh` coexists with other script/debug switches and is ignored by screensaver mode parsing
- [x] cleanup is startup-only and does not alter normal launches when the switch is absent

Validation:
- [x] `python -m pytest tests/test_fresh_start_logging.py -q`
- [x] `python -m py_compile main.py main_mc.py core/logging/logger.py tests/test_fresh_start_logging.py`

---

## 2. Spectrum Conservative Pass

Status:
- [ ] Next feature work

Approved order:

### 2.1 Width Reclaim For `BARS` / `SEGMENTS`

- [x] First prerequisite fixed before width work:
  - [x] defaults now actually start the Beat Visualizer on Spectrum `Preset 1` / slot `0`
  - [x] fresh startup no longer depends on post-merge repair to turn the visualizer back on
- [x] Reclaim wasted horizontal side space for `BARS`
- [x] Reclaim wasted horizontal side space for `SEGMENTS`
- [x] Do **not** overshoot into the border again
- [x] Keep Organs synthetic green before/after
- [x] Add a concrete non-visual regression for the layout math, not just a screenshot hope

Success criteria:
- [x] Spectrum uses more of the card width
- [x] Outer bars/segments sit naturally inside the frame
- [x] No half-bar overlap past the border

Historical notes:
- [x] First reclaim pass overshot by roughly half a bar per side
- [x] Final contract uses more of the card width without crossing the frame
- [x] Regression coverage now lives in `tests/test_spectrum_shaping.py`

### 2.2 Replace `Single Piece Mode`

- [x] Remove `Single Piece Mode`
- [x] Add two explicit toggle buttons:
  - [x] `SEGMENTS`
  - [x] `BAR`
- [x] `BAR` is default
- [x] `BAR` exactly matches old single-piece-on behavior
- [x] No render-path change is allowed here; this is a UI/settings contract change only
- [x] Migrate presets/settings safely through canonical model/schema instead of ad-hoc aliases where possible

Landed contract:
- [x] Spectrum UI now authors canonical `spectrum_render_mode`
- [x] Runtime bridge still translates that canonical mode into the older widget boolean seam, so renderer behavior stays stable
- [x] `spectrum_unique_colors` remains the canonical unique-colour key; the existing checkbox now edits that key instead of reviving `spectrum_rainbow_per_bar`

Validation:
- [x] `python -m pytest tests/test_widgets_tab.py tests/test_visualizer_settings_plumbing.py tests/test_spectrum_shaping.py -k "spectrum" -q`
- [x] `43 passed, 1 skipped`

### 2.3 Proper Spectrum Buckets

- [x] Replace loose section headings with real collapsible buckets
- [x] Order buckets intelligently for Spectrum
- [x] Keep row alignment consistent with the shared settings chrome
- [x] Keep Organs behavior unchanged while reorganizing controls

Landed bucket order:
- [x] Normal surface:
  - [x] `Appearance`
  - [x] `Shape`
- [x] Advanced surface:
  - [x] `Render`
  - [x] `Audio`
  - [x] `Ghost`

Validation:
- [x] `python -m pytest tests/test_widgets_tab.py -k "spectrum_builder_uses_real_bucket_order or blob_builder_uses_real_bucket_order or visualizer_bucket_toggles" -q`
- [x] `python -m pytest tests/test_visualizer_preset1_baselines.py tests/test_visualizer_settings_plumbing.py -k "preset1 or spectrum" -q`

### 2.4 Commit Gate

- [ ] After 2.1 / 2.2 / 2.3 are complete and validated, make a git commit

Guardrails for 2.1–2.4:
- [ ] Use the Organs synthetic just before changes and again after changes
- [ ] Do not introduce Curve again
- [ ] Do not change render methods or move Spectrum to a non-GL path
- [ ] Do not treat passing tests as visual sign-off

---

## 3. Spectrum Follow-On Tasks

Status:
- [ ] Waiting for 2.1 / 2.2 / 2.3 commit

### 3.1 Border Colour Participation

- [ ] Audit why bar borders are left out of the Taste The Rainbow / Unique Colours path in current practice
- [ ] Add a user-facing adjustable switch for whether borders participate
- [ ] Make the implementation safe and deterministic in presets/runtime
- [ ] Keep the default behavior explicit and documented

### 3.2 Energy-Directed Vertical Strength Arrows

- [ ] Replace truly redundant Spectrum energy-strength sliders with vertical strength arrows above the energy lanes/sound types
- [ ] Arrow length controls energy contribution strength only
- [ ] This does **not** replace all Spectrum controls
- [ ] Preserve Organs behavior by measuring against the synthetic fence before/after
- [ ] Record the planning/mental-model rationale in docs when this starts

Known design guardrails already agreed:
- [x] This is not a Blob transplant
- [x] Spatial ownership stays in the Spectrum editor
- [x] Time-behavior controls still belong outside the editor
- [x] The goal is to replace only controls that become truly redundant

### 3.3 Consolidation / Redundancy Pass

- [ ] Prepare an exact proposed list of Spectrum control merges/removals
- [ ] Confirm each merge/removal with the user before editing
- [ ] Preserve Organs behavior either directly or through automatic remapping that reproduces it
- [ ] Focus especially on the shimmer-at-mid-height problem as a future tuning target, not by gut feel

Open design note retained from discussion:
- [ ] Mid-height shimmer is not the same as quiet-floor jitter
- [ ] `drop_speed` alone is not the right blunt instrument because Spectrum wants big rises and big falls
- [ ] The later likely fix area is smarter gating/hysteresis once bars are materially elevated, while preserving big up/down motion

---

## 4. Runtime / Log Watchlist

Status:
- [~] Ongoing

Keep watching for:
- [ ] roaming AppData visualizer normalization repair line repeating indefinitely
- [ ] creator bridge drift between canonical settings model and widget kwargs
- [ ] source curated tree vs generated shipped tree drift
- [ ] stale defaults snapshot drift
- [ ] UI preview/live-config helper paths throwing misleading exceptions that look like preset/runtime failures

Current known watch item:
- [~] `%APPDATA%/SRPSS/settings_v2.json` still appears to contain older visualizer-era state that SettingsManager heals on load
- [ ] Confirm whether a user-side save or reset/replace permanently clears that repair path

---

## 5. Baseline Commit Prep

Status:
- [~] In progress

Before `Baseline Pre-Spectrum Clean`:
- [x] Preset audit green
- [x] Shipped-tree regeneration green
- [x] Organs synthetic green against current authored source
- [x] Runtime creator bridge fixed for current schema
- [x] Settings-tab live-config guard fixed
- [ ] Rewrite/align living docs with the recovery lessons and the conservative Spectrum focus
- [ ] Remove tracked personal/runtime junk from the commit
  - [x] `cache/reddit/*.json` removed from tracked repo content and ignored going forward
- [ ] Stage only repo-relevant files
- [ ] Create commit: `Baseline Pre-Spectrum Clean`
