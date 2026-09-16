# Future Cleanup — Active Debt / Compatibility / Schema-Migration Ledger

Last updated: 2026-09-16

This is the single forward register for **cleanup, compatibility residue, persisted-data/schema migration debt, deprecated shims and caller-proven retirement work**. It is not a changelog and it is not a museum of completed work.

- Active product/bug work belongs in `Current_Plan.md`.
- Durable current architecture belongs in `Spec.md`, `Docs/Architecture/`, `Docs/Guardrails/`, Guides or Reference.
- Root-cause / failed-method history belongs in `Docs/Historical_Bugs/`.
- Ordinary chronology belongs in source control.
- The separate full-suite/stale-test pass may add cleanup items here after it classifies failures; it must not turn this file into a test-results dump.

`Current_Plan.md` outranks this ledger when priorities conflict.

## Status vocabulary

```text
READY                  caller-proven residue; delete in one bounded slice
AUDIT                  ownership/callers or product intent still need proof
MIGRATION HORIZON      real persisted/import compatibility; keep until explicit support horizon + fixtures prove removal safe
KEEP / CURRENT INPUT   not cleanup debt; current compatibility/versioning contract
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

## Near-term persisted-data migration cleanup program

This is real migration work and should be tackled soon, but **only as evidence-driven compatibility retirement**, not as a blanket purge of the word `legacy`.

### Proof corpus to establish before major migration retirement

Maintain a small fixture corpus covering the actual surviving input families below. The goal is not to preserve every historical version forever; it is to know exactly which ones are still supported before deleting bridges.

- [ ] pre-JSON **QSettings** profile -> canonical `settings_v2.json`;
- [ ] early JSON profile containing retired dotted aliases / structured-root members;
- [ ] pre-current **Visualizer** profile: old `enabled_modes`, global technical/shared visual keys, retired modes/keys, old Bubble gradient semantics and current Custom/preset preservation;
- [ ] old user-authored Visualizer preset payloads, especially Sphere finish/control aliases and sparse preset numbering;
- [ ] old **SST** flat/nested snapshots and older `settings_version` input;
- [ ] **layout-slot v1** payload -> current v2 semantics without inheriting newer per-display Clock overrides;
- [ ] legacy Settings bucket full-boolean/multi-open maps -> current sparse one-open-per-scope form;
- [ ] Settings Theme **schema v5 -> v6** user theme;
- [ ] Widget Theme **schema v1/v2 -> v3** / abandoned material-field state;
- [ ] old Clock separator key and old ordinary-family colour persistence;
- [ ] legacy Weather/cache-storage locations;
- [ ] legacy Gmail plaintext OAuth token -> encrypted storage + plaintext removal;
- [ ] legacy Reddit helper startup artifacts (old task names / HKCU Run entry);
- [ ] installer migration-reset path so a reset cannot silently re-import retired QSettings state.

For each fixture, record whether the support horizon is **KEEP**, **remove after next major release**, or **already caller/input-dead**. Do not guess the horizon from code age.

## MIGRATION HORIZON — QSettings -> JSON profile bridge

`SettingsManager` still imports pre-JSON `QSettings` on first creation of the canonical JSON store. Both installers also know how to clear the old QSettings tree during the optional migration-reset flow so reset does not immediately re-import retired state.

- [ ] Decide the supported pre-JSON profile horizon explicitly.
- [ ] Before removal, prove normal + MC fixtures migrate once into canonical structured JSON, preserve user settings that still have current owners, and do not re-import on a second launch.
- [ ] If the bridge is retired, remove `_run_initial_migration`, `_migrate_from_qsettings`, migration-backup-only plumbing and installer QSettings reset clauses in the same bounded slice.
- [ ] Keep reset semantics fail-safe: deleting only `settings_v2.json` must never cause an unexpected older store to become authority.

**Do not** replace this with another fallback settings backend. JSON/default schema remains the sole current authority.

## MIGRATION HORIZON — persisted Settings aliases / structured-root normalization

`SettingsManager` still accepts a narrow set of retired dotted names (currently including `input.hard_exit`) and compatibility members embedded in structured mappings, then rewrites/removes them into current canonical shape.

- [ ] Inventory `_LEGACY_KEY_ALIASES` plus structured dotted-member expansion as one input-boundary migration family.
- [ ] Add representative old JSON fixtures and prove canonical keys win when both old and new names exist.
- [ ] Remove aliases only after the supported old-profile horizon closes; current UI/default/SST output must never emit them while retained.
- [ ] Treat `_OBSOLETE_KEYS` / retired shadow keys separately: drop-only sanitation is not a reason to recreate a migration value.

## MIGRATION HORIZON — Visualizer persisted schema / preset compatibility

Current runtime authority is the mode registry + per-mode settings/preset contracts. The migration layer is intentionally broader because old profiles and user-authored preset files can predate the current schema.

Surviving compatibility includes:

- `widgets.spotify_visualizer.enabled_modes` -> `mode_activation`;
- persisted visualizer schema versioning (currently v9);
- retired/global technical and shared visual keys;
- retired mode/key stripping;
- Bubble gradient direction semantics migration;
- Spectrum legacy notch layout promotion;
- Sphere finish/control/material key migration;
- old snapshot wrappers / global preset remnants accepted only at import/preset boundaries.

- [ ] Build one fixture matrix that proves **profile migration and user-authored preset migration separately**. They have different ownership and must not be conflated.
- [ ] Preserve arbitrary/sparse authored preset files and Custom state exactly; never use shipped manifests/defaults to overwrite authored data.
- [ ] Verify old inputs migrate to current per-mode ownership once, while current defaults/model/UI/runtime never write retired global forms.
- [ ] Retire migration functions in small groups only after the matching fixture family is outside the support horizon.

### READY AFTER PROFILE PROOF — Visualizer `enabled_modes` bridge

`widgets.spotify_visualizer.mode_activation.<stable_mode_id>` is the sole current persisted/runtime authority. The old `enabled_modes` list survives only as a pre-default compatibility signature.

- [ ] Remove `migrate_legacy_enabled_modes_to_activation`, the SettingsManager pre-default hook and warning path only after the profile fixture proves the bridge is no longer required.
- [ ] Never retain `enabled_modes` as a second dormancy representation.

## MIGRATION HORIZON — SST import versions / flat snapshots

`core/settings/sst_io.py` still admits older `settings_version` inputs and coerces legacy flat SST snapshots into the canonical nested schema. That is import compatibility, not runtime settings authority.

- [ ] Define which historical SST versions remain user-supported.
- [ ] Prove older accepted snapshots import to exact current canonical leaves, reject runtime-owned/retired keys, and do not recreate retired global Visualizer preset state.
- [ ] Remove flat/version compatibility only when the import support horizon is explicitly closed.
- [ ] Keep newer-version warnings/fail-safe handling even after old-version migration is narrowed; forward-version detection is not historical debt.

## MIGRATION HORIZON — layout-slot payload v1 -> v2

Current layout-slot payload version is v2. v1 predates explicit per-display Clock `display_mode_overrides`; replay intentionally clears newer overrides so the saved v1 baseline wins deterministically.

- [ ] Keep v1 replay until saved-layout support horizon is explicitly closed.
- [ ] Before removal, prove v1 slots cannot still be produced/imported by any supported release/tool.
- [ ] Do not simplify this by inheriting current runtime overrides into old slots; that changes the saved layout's meaning.

## MIGRATION HORIZON — Settings bucket persistence shape

Bucket state is canonically sparse true-only with at most one open bucket per local scope. The normalizer still accepts old full boolean maps and resolves old multi-open state deterministically.

- [ ] Treat this as cheap input compatibility until old settings-profile support is narrowed.
- [ ] If retired, keep canonical in-memory enumeration/fail-loud getters; remove only the old persisted-shape accommodation.
- [ ] No startup write loop/poller is needed merely to normalize bucket state.

## MIGRATION HORIZON — Settings Theme schema v5 -> v6

`.srtheme` schema v6 adds `about.art.liquid`; v5 user themes are upgraded deterministically from their existing primary accent instead of failing whole-theme load.

- [ ] Keep v5 acceptance while v5 user-authored themes are supported.
- [ ] Before retiring v5, prove Theme Foundry/current export produces v6 and define the user-theme compatibility horizon explicitly.
- [ ] Do not replace strict schema validation with default-merging just to keep arbitrary ancient/incomplete theme files alive.

## MIGRATION HORIZON — Widget Theme v1/v2 material-state rewrite

`ui.widget_theme_selection.read_widget_theme_state()` still upgrades abandoned material-bearing Widget Theme state to v3, removing only the retired material field while preserving identity/link metadata/semantic colours.

- [ ] Prove persisted v1/v2 fixture -> exact v3 state and second-load idempotence.
- [ ] Remove the rewrite only after supported old profiles can no longer contain those schemas.
- [ ] Never reintroduce card-material runtime ownership to make the old state meaningful.

## DELETE AFTER HORIZON — Clock separator compatibility key

Current ownership is `widgets.clock.show_separator` + `widgets.clock.separator_thickness`. `widgets.clock.show_digital_separator` survives only as a read compatibility input for older saved configs.

- [ ] After profile-horizon proof, remove the legacy fallback from Clock presentation/settings loading and its compatibility tests.

## DELETE AFTER HORIZON — ordinary Widget family colour bridge

Branded-header family colour controls are retired in favour of Widget Theme `header.*` semantics plus `Widgets -> General -> Style Overrides -> Header Fill`. `Reset All Colours to Theme` is deliberately user-invoked, never startup normalization.

Temporarily retained compatibility is limited to old per-family colour persistence/value reads needed for old profiles/imports. This is compatibility plumbing, not a supported hidden palette.

- [ ] After the old-profile/SST-import horizon closes, remove retired header-colour persistence/value fields that no surviving import contract needs.
- [ ] Audit remaining non-header family colour fields individually: keep only genuine durable customization; retire invisible precedence.
- [ ] Keep `Reset All Colours to Theme` if it remains a useful permanent action; delete only obsolete compatibility plumbing.

## MIGRATION HORIZON — storage/cache path imports

`core.settings.storage_paths.run_all_migrations()` still copies old TEMP-based RSS/feed-health/weather state into the canonical `%APPDATA%/SRPSS...` tree, and Weather separately admits the old `~/.srpss_last_weather.json` widget cache.

- [ ] Inventory which legacy files can still exist from a supported installed release.
- [ ] Prove migration is non-destructive, target-wins, idempotent and cannot overwrite newer canonical cache/state.
- [ ] Once the horizon closes, remove old TEMP/home probes and then prune generic migration helpers if no current caller remains.
- [ ] Cache migration retirement must not change the last-good cache contract or trigger synchronous startup I/O on the GUI thread.

## MIGRATION HORIZON — Gmail plaintext OAuth token cleanup

Gmail bootstrap still recognizes the old plaintext `gmail_credentials.json`, converts valid OAuth credentials to encrypted storage, and deletes/retries deletion of the plaintext file.

- [ ] Keep this migration while an installed supported release may have emitted the plaintext token.
- [ ] Before retirement, prove successful conversion, failed-conversion safety, and deferred plaintext deletion behavior from a real fixture.
- [ ] When the horizon closes, remove the plaintext read/migration path but keep encrypted credential failure explicit; never add a plaintext fallback.

## MIGRATION HORIZON — Reddit helper startup artifact cleanup

Current helper startup ownership is the canonical scheduled task. Runtime still removes the old HKCU Run entry and recognizes historical scheduled-task names during cleanup.

- [ ] Establish which installer/helper versions can still leave each old task/Run entry behind.
- [ ] Remove legacy task names and HKCU Run cleanup only after that installed-base horizon closes.
- [ ] Do not remove the current task owner or reintroduce helper polling/startup duplication.

## AUDIT — Visualizer diagnostic subset CLI aliases

`--viz-diagnostics` / `--viz-diag` still have live meaning: they enable the visualizer diagnostic subset without the full `--viz` bundle. They are therefore **not** parser fossils. The proven no-op/parser-only tokens (`--devcurve`, `--devstats`, `--diag-pair-warm-finish`, `--diag-p4-stages`, `--diag-p4-no-perf-hud`, `--qsg-render-timing`) have been retired.

- [ ] Decide whether the subset aliases still have an external operator/script use worth preserving.
- [ ] If retired later, remove both aliases from logging bootstrap + Foundry together and update any Historical Bug runbook that still recommends them.
- Keep `--viz` and `--frame-trace`; this is not permission to reduce current diagnostic authority.

## AUDIT — GPU timing CLI versus Quick ownership

- [ ] Reconcile `main.py`/logging's advertised `--gpu-timing` owner-context query capability with current Quick production: exact search finds no Quick GL timer-query consumer. Preserve useful PERF logging; remove stale claims or deliberately implement measured, bounded owner-context diagnostics when a real attribution task needs them. Do not restore the retired compositor to make this switch truthful.

## AUDIT — non-Windows DPAPI plaintext fallback

The shared DPAPI helper uses a `plain::` fallback on non-Windows, while Steam credentials deliberately refuse that fallback. SRPSS production is Windows, but tests/development may rely on the shared helper behavior.

- [ ] Decide the supported non-Windows development/test contract explicitly before changing this.
- [ ] If plaintext fallback is retired, do so as a credential/platform-contract change with Gmail + Steam fixture coverage, not incidental cleanup.
- [ ] Never weaken Windows encrypted storage or reintroduce plaintext Windows credential persistence.

## TEST-REPORT INTAKE — broad-suite stale-owner reconciliation

A separate full-suite agent/report owns the immediate red-suite archaeology. Feed only **classified cleanup conclusions** back here; do not paste hundreds of failing test names into this ledger.

Typical cleanup class remains caller/test residue naming retired owners such as `DisplayWidget`, `GLCompositorWidget`, `spotify_bars_gl_overlay` and `SpotifyVisualizerWidget`, plus expectation drift in current Media, Weather/Achievement, Widget Theme, Visualizer-doc-reference and tooling-ownership tests.

When that report lands:

- [ ] Rehome still-valid behavioural assertions to current Quick/presentation-neutral owners.
- [ ] Delete implementation-detail assertions that only prove retired pixels/owners.
- [ ] Resolve caller-proven quarantine/debris without restoring removed tools.
- [ ] Restore broad-suite signal by classification, never by resurrecting museum architecture.

A previously isolated S-hotkey native fault did not reproduce in focused reruns and is not cleanup debt. A future reproduction belongs in runtime bug tracking/Historical Bugs, not in stale-test cleanup.

## Permanent cleanup guardrails

- `R-72`: production never imports operator analysis tools.
- R-69/R-76 Visualizer response/freshness contracts are not cleanup targets.
- Bubble is a protected GOLDEN reaction contract; schema cleanup may not alter cadence, freshness, authored amplitude, motion/ghost behavior, attack/settle or reactive delivery.
- Stable RSS/VRAM/thread/handle/cache counts are not deletion targets merely because they are large.
- Runtime card Glass/Acrylic experiments are rejected historical material; never resurrect their Loader/capture/mask/cadence owners as “cleanup compatibility”.
- Product-neutral provider/model/settings/runtime logic stays unless exact current callers prove it dead.
- Version checks that reject **future/newer** unsupported data are not historical debt merely because they mention schema versions.
- User-authored presets/themes/layouts are data, not debris. Migration cleanup must preserve them or fail explicitly.
