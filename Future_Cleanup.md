# Compatibility & Migration Register — protected until horizon, NOT a backlog

Last updated: 2026-09-17

**This is a defensive register, not a to-do list.** Its entries are the compatibility bridges that carry real old user data (profiles, presets, themes, layouts, credentials) into the current schema. They are isolated at input boundaries, cost ~nothing at runtime, and are **correct** — the healthiest state of this codebase is with them intact. This file exists to *stop* someone from mistaking a `*_input_compat.py` / migration seam for "legacy cruft" and deleting user-data protection.

- **Removal is horizon-gated and operator-initiated.** Nothing here is scheduled. A bridge is removed only after *you* declare its support horizon closed AND rules 1-8 below are met in one slice. Reading, indexing or cross-linking this file is not permission to start removing bridges.
- **Do not treat these as debt to "pay down soon."** Prematurely removing any of them is a data-loss / resurrection / credential-exposure disaster (see the BLOCKED clauses). Leaving them is not rot.
- Genuinely caller-dead residue (**READY**) is the only remove-now class, and there is currently none pending here — every live entry is horizon-gated compatibility.

Where each belongs otherwise: active product/bug work → `Current_Plan.md`; durable architecture → `Spec.md`, `Docs/Architecture/`, `Docs/Guardrails/`, Guides/Reference; root-cause history → `Docs/Historical_Bugs/`; ordinary chronology → source control. `Current_Plan.md` outranks this register when priorities conflict.

## Status vocabulary

```text
READY                  caller-proven residue; delete in one bounded slice
AUDIT                  ownership/callers or product intent still need proof
MIGRATION HORIZON      real persisted/import compatibility; keep until explicit support horizon + fixtures prove removal safe
KEEP / CURRENT INPUT   not cleanup debt; current compatibility/versioning contract
BLOCKED                a specific tempting shortcut that WILL cause a disaster; do the safe path or nothing
```

A compatibility seam is **not** automatically bad architecture. Some are the only safe bridge from real user data into the current schema. The goal is to make every surviving bridge explicit, one-way and removable when its support horizon closes.

## Cleanup admission rules

Before removing a runtime or persisted-data compatibility seam:

1. **Find every current caller and input source.** Search production, installers, import/export tools, settings snapshots, user-authored presets, layout slots, themes and helper processes, not only Python call sites.
2. **Name the current authority.** The old shape may be accepted only at an input boundary; current runtime/default/UI/output must use the canonical owner.
3. **Build/retain a representative old-input fixture before deletion.** Migration removal without a real old-profile/import fixture is not proof.
4. **Prove exact canonical output and idempotence.** First load/import may transform old state; second load must not re-run, drift, duplicate or re-emit the retired shape.
5. **Preserve user-authored state.** Visualizer presets, Custom layout/preset state, themes and saved slots must never be flattened to defaults merely to make migration code disappear.
6. **Remove one seam at a time.** Do not combine compatibility retirement with performance tuning, visual retuning, defaults changes or unrelated schema redesign.
7. **Do not resurrect retired architecture for stale tests.** Rehome still-valid behavior to the current owner, then remove the fossil.
8. **Update the whole test cascade in the SAME commit.** Every migration/rework item below lists the tests it will break. A slice is not done until those tests are rehomed/retired/re-floored in the same change. Leaving them for "the suite to find later" is the exact mistake that produced the 2026-09 red storm: tests asserting a migration-era shape/owner/threshold/default that production had already superseded, surfacing weeks later as expensive "why is this red" investigations that each ended in "production was right."

### Disaster-class seams — BLOCKED shortcuts

These are the removals that cause silent data resurrection, credential exposure or user-data loss. The tempting shortcut is spelled out so it can be refused on sight. None proceeds without rules 1-8 above.

## MIGRATION HORIZON — QSettings -> JSON profile bridge

`SettingsManager.__init__` runs `_run_initial_migration` whenever `not self._settings.exists()` (settings_manager.py). It imports the pre-JSON `QSettings` tree into the canonical JSON store, and on any migration exception it calls `self._settings.clear()` (falls back to defaults).

- [ ] Decide the supported pre-JSON profile horizon explicitly.
- [ ] Before removal, prove normal + MC fixtures migrate once into canonical structured JSON, preserve settings that still have current owners, and do not re-import on a second launch.
- [ ] If retired, remove `_run_initial_migration`, `_migrate_from_qsettings`, migration-backup plumbing **and** the installer QSettings-reset clauses in one bounded slice.

**BLOCKED — silent resurrection of retired state.** The migration re-fires on *any* absence of `settings_v2.json`, including after Reset. Do NOT: (a) remove the bridge while leaving the installer's `deletekey` QSettings-clear clause, or vice versa; (b) change Reset to delete only the JSON; (c) treat the `except -> clear()` path as harmless — a buggy migration silently wipes to defaults, so it must fail loud, not clear. Any of these lets an old QSettings tree become authority again and re-import schema the rest of the system no longer sanitizes.
**Existing guard:** `test_installer_v5_reset_policy.py::test_selected_reset_clears_json_and_matching_legacy_qsettings_tree` fails if the installer stops clearing the registry tree — keep it.
**Test cascade (same commit):** `test_settings_manager.py` (migration + missing-key repair + reset), `test_settings_profile_separation.py` (per-profile JSON paths), `test_installer_v5_reset_policy.py`, `test_defaults_schema_authority.py`, `test_build_closeout_contract.py`, `test_godzip_foundry_core.py`, `test_settings_dialog.py`. Add a QSettings old-profile fixture (normal + MC) proving one-time import + second-launch no-op + reset-does-not-resurrect; then delete migration-path assertions and keep the reset-fail-safe pointed at JSON-only authority.

**Do not** replace this with another fallback settings backend. JSON/default schema remains the sole current authority.

## MIGRATION HORIZON — Gmail plaintext OAuth token cleanup

`core/gmail/gmail_bootstrap.py` reads legacy plaintext `gmail_credentials.json`, converts valid OAuth credentials to encrypted storage, and deletes/retries deletion of the plaintext file.

- [ ] Keep this migration while an installed supported release may have emitted the plaintext token.
- [ ] Before retirement, prove successful conversion, failed-conversion safety, and deferred plaintext deletion from a real fixture.

**BLOCKED — permanent plaintext credential persistence.** Do NOT remove the read/convert/delete path while any supported release could still have written `gmail_credentials.json`: the token would never be encrypted or deleted and would sit in cleartext on disk indefinitely. Never add a plaintext *read fallback* on retirement; encrypted-credential failure must stay explicit.
**Test cascade (same commit):** `test_gmail_backend_bootstrap.py`, `test_gmail_oauth.py`, `test_gmail_backend_smoke.py`, `test_cache_maintenance.py`. Requires a real plaintext-token fixture proving conversion + failed-conversion safety + deferred deletion before removal; retirement deletes only the read/migrate assertions and keeps the no-plaintext-fallback guard.

## AUDIT — non-Windows DPAPI plaintext fallback

The shared DPAPI helper (`core/windows/dpapi.py`) uses a `plain::` fallback on non-Windows; Steam credentials (`core/steam/credentials.py`) deliberately refuse it. SRPSS production is Windows, but tests/development may rely on the shared helper.

- [ ] Decide the supported non-Windows development/test contract explicitly before changing this.

**BLOCKED — plaintext credentials where encryption is assumed.** This is a credential/platform-contract change, not incidental cleanup. Do NOT alter it without Gmail + Steam fixture coverage in the same slice, and never weaken Windows encrypted storage or the Steam refusal.
**Test cascade (same commit):** `test_steam_credentials.py`, `test_gmail_oauth.py`, `test_gmail_backend_smoke.py`.

## MIGRATION HORIZON — old Visualizer persisted-schema / preset inputs (sequence LAST, in small groups)

Current runtime authority is the mode registry + per-mode settings/preset contracts (see the KEEP block below). The migration layer is intentionally broader because old profiles and user-authored preset files predate the current schema. Surviving compatibility: `enabled_modes` -> `mode_activation`; persisted visualizer schema versioning (v9); retired/global technical + shared visual keys; retired mode/key stripping; Bubble gradient direction migration; Spectrum legacy notch layout promotion; Sphere finish/control/material key migration; old snapshot wrappers accepted only at explicit import/preset boundaries.

- [ ] Build TWO separate fixture matrices — **profile migration** and **user-authored preset migration**. They have different ownership and must never be conflated.
- [ ] Prove old inputs migrate to current per-mode ownership once, while current defaults/model/UI/runtime never write retired global forms.
- [ ] Retire migration functions in small groups only after the matching fixture family is outside the support horizon.

**BLOCKED — user-authored preset/enabled-mode data loss.** Do NOT use shipped manifests or defaults to overwrite authored preset files; do NOT flatten sparse/arbitrary authored preset numbering; do NOT retain `enabled_modes` as a second dormancy representation. This family has the widest test cascade and touches irreplaceable user data — it is the item most likely to re-create a red storm, so do it dead last and in the smallest possible groups.
**Test cascade (same commit — widest in the repo):** `test_visualizer_mode_activation_schema_current.py`, `test_visualizer_mode_dormancy.py`, `test_visualizer_mode_enable_resolver.py`, `test_visualizer_request_admission.py`, `test_visualizer_settings_plumbing.py`, `test_visualizer_retired_modes.py`, `test_spectrum_shaping_current.py`, `test_sphere_voxel_audio_contract.py`, `test_visualizer_presets.py`, `test_visualizer_settings_lazy_bodies_current.py`, `test_settings_manager.py` (schema-migration cases). Separate profile-migration fixtures from authored-preset fixtures; prove migrate-once + current-writers-never-emit-retired-forms; delete only the retired-list/global-key assertions.

### READY AFTER PROFILE PROOF — retired `enabled_modes` persisted-list bridge
`mode_activation.<stable_mode_id>` is the sole current persisted/runtime authority; only the retired `enabled_modes` **list representation** is debt. Remove `migrate_legacy_enabled_modes_to_activation`, its pre-default hook and warning only after the profile fixture proves the bridge is unused. Never retain `enabled_modes` as a second dormancy representation.

## MIGRATION HORIZON — SST import versions / flat snapshots

`core/settings/sst_io.py` admits older `settings_version` inputs and coerces legacy flat SST snapshots into the canonical nested schema. Import compatibility, not runtime authority.

- [ ] Define which historical SST versions remain user-supported.
- [ ] Prove older accepted snapshots import to exact current canonical leaves, reject runtime-owned/retired keys, and do not recreate retired global Visualizer preset state.

**BLOCKED — forward-version fail-safe is not debt.** Keep newer-version warnings/fail-safe even after old-version migration is narrowed. Do NOT delete forward-version rejection because it "mentions schema versions." SST is also a **privacy boundary** (Steam secret stripping) — never weaken stripping to simplify import.
**Test cascade (same commit):** `test_settings_manager.py`, `test_settings_profile_separation.py`, `test_default_settings_editor.py`, `test_regenerate_defaults_artifacts.py`, `test_visualizer_presets.py`, `test_steam_credentials.py` (privacy).

## MIGRATION HORIZON — persisted Settings aliases / structured-root normalization

The only current alias is `input.hard_exit` -> `input.interaction_mode`, promoted at startup/SST-import and rejected by `set`. Structured dotted-member expansion is isolated in `core/settings/structured_input_compat.py` (input-only owner; canonical nested members win; declared roots persist nested).

- [ ] Define the supported old-profile/QSettings/SST horizon before deleting `LEGACY_DOTTED_SETTING_ALIASES`, `_migrate_legacy_setting_aliases()` and SST alias promotion.
- [ ] Define the structured-shape support horizon before deleting `structured_input_compat.py`.

This family is already the correct shape (explicit input-boundary owner + distinguishing fixtures). Removal is low-risk once the horizon closes: delete owner + fixture assertions, keep the `set`-rejects-retired-key guard.
**Test cascade (same commit):** `test_settings_legacy_alias_input_compat.py` (+ `fixtures/settings_legacy_hard_exit_profile.json`), `test_settings_structured_input_compat.py`, `test_settings_manager.py`, `test_defaults_schema_authority.py`.

## MIGRATION HORIZON — Settings Theme schema v5 -> v6

User-authored v5 `.srtheme` files are admitted only through `ui.settings_theme_input_compat.promote_legacy_settings_theme_payload()`; current runtime/authoring is v6 only.

- [ ] Keep the explicit v5 input bridge while v5 user themes are supported; define that external-file horizon before deleting it.
- [ ] When the horizon closes, remove `settings_theme_input_compat.py` and the v5 fixture assertions together.

**BLOCKED — do NOT default-merge incomplete old themes.** Never weaken strict v6 validation to tolerate ancient/incomplete theme files; that silently corrupts a user theme into a defaults blend.
**Test cascade (same commit):** `test_settings_theme_input_compat.py`, `test_settings_theme_system.py`, `test_theme_foundry_model.py`, `test_about_art_theme.py`, `test_theme_expansion_light_metal_contract.py`.

## MIGRATION HORIZON — Widget Theme v1/v2 -> v3 material-state rewrite

Old material state is admitted only through `core.settings.widget_theme_input_compat.promote_legacy_widget_theme_state()`; current selection/runtime/file I/O is colour-only v3.

- [ ] Remove `widget_theme_input_compat.py` and its old-input fixture assertions only after supported old profiles/QSettings/SSTs can no longer contain those schemas.

**BLOCKED — never reintroduce card-material runtime ownership** to make old state meaningful. Runtime card Glass/Acrylic/material is rejected historical architecture; resurrecting its owners as "cleanup compatibility" is forbidden.
**Test cascade (same commit):** `test_widget_theme_input_compat.py` (+ `fixtures/widget_theme_legacy_material_state_profile.json`), `test_widget_theme_no_material_contract.py`, `test_widget_theme_mirror_pack.py`, `test_theme_expansion_light_metal_contract.py`.

## DELETE AFTER HORIZON — ordinary Widget family colour bridge

Branded-header family colour controls are retired in favour of Widget Theme `header.*` + `Widgets -> General -> Style Overrides -> Header Fill`. Temporarily retained: old per-family colour persistence/value reads for old profiles/imports.

- [ ] After the old-profile/SST-import horizon closes, remove retired header-colour persistence/value fields no surviving import needs.
- [ ] Audit remaining non-header family colour fields individually: keep genuine durable customization, retire invisible precedence.

**BLOCKED — do NOT flatten durable per-family colour customization** to make the bridge disappear. Keep `Reset All Colours to Theme` as a user-invoked action (never startup normalization).
**Test cascade (same commit):** family colour-read tests + the Widget Theme header tests above.

## KEEP / CURRENT INPUT — not cleanup debt

- **Current Visualizer settings / preset architecture.** Canonical mode registry, one-active-mode behavior, shared/global technical settings, per-mode settings, Bubble/Spectrum semantics, isolated Sphere settings, current Settings UI/Reset/SST behavior, runtime reactivity/freshness, preset selection/compaction, Custom state, arbitrary/sparse authored preset files. Shipped manifests are never authority over the authored catalogue. Cleanup here applies only to old input bridges no current writer emits; promote any depended-on behavior to its canonical owner before deleting a bridge.
- **Canonical Settings bucket normalization.** Sparse true-only on disk, fully enumerated/fail-loud in memory, at most one open bucket per local scope. `core.settings.ui_bucket_state.normalize_single_open_bucket_states()` is the canonical loader/repair; the same projection ignores false members in old full maps and current sparse maps, drops unknown identities, resolves multi-open deterministically. A persisted full-map fixture proves old -> sparse -> second-load fixed point. Do not make this more complex to reject harmless old false members.
- **Custom layout / restore-size version handling.** `CUSTOM_LAYOUT_VERSION = 2` is enforced by hard rejection: `load_custom_layout_map` drops any payload whose `version != 2` (returns the default empty map) — there is **no** v1 acceptance/migration path to remove, and adding one would *widen* compatibility, not clean it. The separate `CUSTOM_LAYOUT_RESTORE_VERSION = 1` restore-size map is current, not debt. (This corrects the former "layout-slot v1 -> v2 migration" item, which described a bridge the code does not have; the trap was touching restore-map version handling while chasing a non-existent v1 migration.) Guarded by `test_layout_slots.py`, `test_qtquick_resize_normalization.py` and the clock-variant/geometry suites — do not weaken the version-mismatch rejection.

## Broad-suite red reconciliation — closed 2026-09-17

The 2026-09 broad-suite stale-test archaeology is resolved: the reds were test-side drift against current architecture (stale fakes/owners/paths, V6a Settings bodies, event-driven prefetch/resume, single-flight scaled prefetch, DSP source-config, replay capture timestamps, hand-tuned Bubble/QSG pixel oracles) — production was correct in every case. Fixes were test/harness-only; no production runtime code changed and no reviewed golden/floor was weakened. Detailed archaeology lives in git history, not here.

The migration-retirement gate is now the **per-item safe path + test cascade above**, not a global "run the suite first" freeze. Each seam is removable when its horizon closes and rules 1-8 are met in one slice.

## Permanent cleanup guardrails

- **Treat behaviour-quality REDs as real signal first.** Bubble reaction/replay/viewport, 3D Blockflip pixels, image-prefetch ordering, custom-layout retained-runtime, credential/SST/export privacy and preset transfer: investigate against current owners/floors before changing any assertion. Never auto-green by weakening a protected contract; production correctness wins. When current behaviour is confirmed correct, protect it as a **floor** rather than deleting the canary.
- **`R-72`:** production never imports operator analysis tools.
- **R-69 / R-76** Visualizer response/freshness contracts are not cleanup targets.
- **Bubble is a protected GOLDEN reaction contract;** schema cleanup may not alter cadence, freshness, authored amplitude, motion/ghost behavior, attack/settle or reactive delivery. Bubble viewport response is hand-tuned per extreme — do not "linearize" it.
- **Protected QSG/clip optimizations** (CHK26 lineage): never retune production or move a reviewed pixel golden/floor to satisfy a render_node/clip_smoke oracle; fix the oracle instead. Real per-pixel rotation/projection geometry is a real-GPU/eyes-on destination concern, not a headless one.
- Stable RSS/VRAM/thread/handle/cache counts are not deletion targets merely because they are large.
- Runtime card Glass/Acrylic experiments are rejected historical material; never resurrect their Loader/capture/mask/cadence owners as "cleanup compatibility".
- Product-neutral provider/model/settings/runtime logic stays unless exact current callers prove it dead.
- Version checks that reject **future/newer** unsupported data are not historical debt.
- User-authored presets/themes/layouts are data, not debris. Migration cleanup must preserve them or fail explicitly.
