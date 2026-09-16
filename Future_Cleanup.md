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
- [x] early JSON profile containing retired dotted aliases / structured-root members;
- [ ] pre-current **Visualizer** profile: old `enabled_modes`, global technical/shared visual keys, retired modes/keys, old Bubble gradient semantics and current Custom/preset preservation;
- [ ] old user-authored Visualizer preset payloads, especially Sphere finish/control aliases and sparse preset numbering;
- [ ] old **SST** flat/nested snapshots and older `settings_version` input;
- [ ] **layout-slot v1** payload -> current v2 semantics without inheriting newer per-display Clock overrides;
- [x] legacy Settings bucket full-boolean/multi-open maps + retired Reddit bucket identities -> current sparse one-open-per-scope form (fixture landed; alias retirement horizon still open);
- [x] Settings Theme **schema v5 -> v6** user theme fixture/proof + explicit input-boundary owner (support horizon remains open);
- [ ] Widget Theme **schema v1/v2 -> v3** / abandoned material-field state;
- [ ] old Clock separator key and old ordinary-family colour persistence;
- [ ] legacy Gmail plaintext OAuth token -> encrypted storage + plaintext removal;
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

The retired dotted-name registry is now explicitly an **input-boundary** concern, not a normal Settings API feature. The only current alias is `input.hard_exit` -> `input.interaction_mode`. Existing JSON/QSettings profiles are promoted during startup and SST import promotes the same nested/flat old input before coercion. Ordinary `get`/`contains` no longer map the old name, and `set` rejects it so current code cannot silently recreate retired schema.

- [x] Inventory the dotted alias registry: only `input.hard_exit` remains. Fixture the old profile key and prove promotion to current `input.interaction_mode`, sibling preservation, current-name precedence and SST flat/nested import projection.
- [x] Rehome the existing SettingsManager test away from permanent runtime-alias semantics: it now proves one-time persisted migration, old-key removal, sibling preservation and explicit rejection of retired-key writes.
- [ ] Define the supported old-profile/QSettings/SST horizon before deleting `LEGACY_DOTTED_SETTING_ALIASES`, `_migrate_legacy_setting_aliases()` and SST alias promotion.
- [x] Audit **structured dotted-member expansion** separately within this family. Old JSON/QSettings/SST flattened members now share `core/settings/structured_input_compat.py` as an explicit input-only owner; canonical nested members win, current JsonStore persistence keeps declared roots nested, and the old SettingsManager-wide repair methods are retired. A distinguishing fixture proves both historical shapes, sibling preservation, nested semantic dotted-key preservation and durable second-load idempotence.
- [ ] Define the structured-shape support horizon before deleting `structured_input_compat.py`. Old JSON/QSettings/SST data can still plausibly enter through supported import/startup paths, so CHK37 isolates the bridge rather than gambling with persisted user state.

## KEEP / CURRENT INPUT — current Visualizer settings / preset architecture

The current Visualizer settings and preset system is **not cleanup debt**. Keep the canonical mode registry, current mode activation/one-active-mode behavior, shared/global technical settings, per-mode settings, Bubble/Spectrum current semantics, isolated Sphere settings, current Settings UI/Reset/SST behavior, runtime reactivity/freshness, current preset selection/compaction, Custom state, and arbitrary/sparse user-authored preset files. Shipped preset manifests are never authority over the authored catalogue.

Cleanup in this area applies only to **old input bridges** that translate representations no current writer emits. If a current caller ever depends on one of those bridges for ordinary current-format behavior, promote that behavior to its proper canonical owner before deleting the bridge. Do not redesign, flatten, merge or weaken the current Visualizer architecture under this program.

## MIGRATION HORIZON — old Visualizer persisted-schema / preset inputs only

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

### READY AFTER PROFILE PROOF — retired Visualizer `enabled_modes` persisted-list bridge

Current enabled-mode product behavior is protected. `widgets.spotify_visualizer.mode_activation.<stable_mode_id>` is the sole current persisted/runtime authority for that behavior; only the retired persisted `enabled_modes` **list representation** is cleanup debt, surviving as a pre-default compatibility signature.

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

## KEEP / CURRENT INPUT — canonical Settings bucket normalization

Bucket state is canonically sparse true-only on disk, fully enumerated/fail-loud in memory, and limited to at most one open bucket per local scope. `core.settings.ui_bucket_state.normalize_single_open_bucket_states()` is the current canonical loader/repair operation: the same projection naturally ignores false members in both old full boolean maps and current sparse maps, drops unknown identities, and deterministically resolves impossible multi-open state. That behavior is not a separate migration branch and should not be made more complex merely to reject harmless old false members.

A persisted legacy full-map fixture now proves old input -> exact sparse current projection -> second-load fixed point. Fresh runtime-store projection, Reset, and SST replace-import no longer materialize the all-false maps, so current writers do not immediately depend on the compatibility reader. Startup still performs no rewrite of an existing old profile; its in-memory projection is canonical and the next real interaction writes the sparse form through the canonical setter.

## MIGRATION HORIZON — retired Settings Widget bucket identities

The bounded one-time bucket bridge is the old Reddit Widget-bucket identity set: `reddit:primary`, `reddit:feed`, `reddit:layout`, and `reddit:appearance`. Current defaults/UI/writers emit only `reddit:reddit1`, `reddit:interaction`, `reddit:shared_layout`, and `reddit:shared_appearance`. The bridge is now isolated beside the canonical bucket persistence normalizer instead of living in `WidgetsTab`.

- [x] Fixture exact old names, canonical-name precedence, multi-open collapse, unknown-key drop, sparse output and second-load idempotence.
- [ ] Define the old-profile support horizon before deleting these four persisted-key rewrites.
- [ ] When that horizon closes, remove only the alias table/rewrite; keep canonical sparse/full in-memory normalization, schema enumeration, fail-loud getters and scope rules.
- [ ] No startup write loop/poller is needed merely to normalize bucket state.

## MIGRATION HORIZON — Settings Theme schema v5 -> v6

Current Settings Theme runtime/authoring is schema v6 only. User-authored schema-v5 `.srtheme` files are admitted only through `ui.settings_theme_input_compat.promote_legacy_settings_theme_payload()`, which requires the exact historical v5 colour-role set, seeds `about.art.liquid` from `chrome.outer_border` RGB at full alpha, and hands a v6 payload to the strict current parser.

- [x] Land a distinguishing real-file fixture and prove exact v5 -> v6 promotion, current-role preservation, alpha rule, idempotence and strict rejection of incomplete v5 themes.
- [x] Prove Theme Foundry/current serialization emits schema v6 including `about.art.liquid`; remove the stale Foundry-owned v5 migration test and rehome that proof to the file-input boundary.
- [ ] Keep the explicit v5 input bridge while v5 user-authored themes are supported; define that external-file compatibility horizon before deleting it.
- [ ] When the horizon closes, remove `settings_theme_input_compat.py` and the v5 fixture assertions together. Do not weaken strict current v6 validation or default-merge arbitrary ancient/incomplete theme files.

## MIGRATION HORIZON — Widget Theme v1/v2 material-state rewrite

Current Widget Theme selection/runtime/file I/O is colour-only schema v3 and has no material-state compatibility. Old profile/QSettings/SST state is admitted only through `core.settings.widget_theme_input_compat.promote_legacy_widget_theme_state()`, which removes the retired root-level `card_material_override` and upgrades schema-v1/v2 Custom payloads by dropping `default_card_material_mode` and setting schema v3 while preserving identity/link metadata/semantic colours.

- [x] Prove distinguishing persisted v1/v2 material state -> exact v3 state, no semantic-colour loss, SST promotion and durable JSON second-load idempotence.
- [x] Remove material-key/schema-migration knowledge from current `ui.widget_theme_selection`; rehome the old no-material test expectation to the explicit persisted-input compatibility owner.
- [ ] Remove `widget_theme_input_compat.py` and its old-input fixture assertions only after supported old profiles/QSettings/SSTs can no longer contain those schemas.
- [ ] Never reintroduce card-material runtime ownership to make the old state meaningful.

## MIGRATION HORIZON — Clock separator persisted-key promotion

Current ownership is `widgets.clock.show_separator` + `widgets.clock.separator_thickness`. The retired `widgets.clock.show_digital_separator` name is now admitted only at persisted-input boundaries: startup promotes it **before** current defaults can mask an old `False` value, and SST import applies the same promotion. Current UI and Quick presentation consume `show_separator` only.

- [x] Fixture a real distinguishing old value (`show_digital_separator=False` while the current canonical default is `True`), prove exact promotion, current-key precedence, legacy-key removal and second-pass idempotence.
- [x] Remove duplicate legacy reads from Clock Settings loading and Quick presentation after promotion became the canonical input seam.
- [x] Retire the old presentation-layer compatibility test; it targeted the wrong owner and its positive case accidentally matched the canonical default, so it did not prove the legacy path. Rehome the proof to the persistence/import boundary.
- [ ] Define the old-profile/SST support horizon. When it closes, remove `promote_legacy_clock_separator`, the startup pre-default hook, the SST promotion and the legacy fixture assertions together; keep current `show_separator` UI/presentation/default tests.

## DELETE AFTER HORIZON — ordinary Widget family colour bridge

Branded-header family colour controls are retired in favour of Widget Theme `header.*` semantics plus `Widgets -> General -> Style Overrides -> Header Fill`. `Reset All Colours to Theme` is deliberately user-invoked, never startup normalization.

Temporarily retained compatibility is limited to old per-family colour persistence/value reads needed for old profiles/imports. This is compatibility plumbing, not a supported hidden palette.

- [ ] After the old-profile/SST-import horizon closes, remove retired header-colour persistence/value fields that no surviving import contract needs.
- [ ] Audit remaining non-header family colour fields individually: keep only genuine durable customization; retire invisible precedence.
- [ ] Keep `Reset All Colours to Theme` if it remains a useful permanent action; delete only obsolete compatibility plumbing.

## MIGRATION HORIZON — Gmail plaintext OAuth token cleanup

Gmail bootstrap still recognizes the old plaintext `gmail_credentials.json`, converts valid OAuth credentials to encrypted storage, and deletes/retries deletion of the plaintext file.

- [ ] Keep this migration while an installed supported release may have emitted the plaintext token.
- [ ] Before retirement, prove successful conversion, failed-conversion safety, and deferred plaintext deletion behavior from a real fixture.
- [ ] When the horizon closes, remove the plaintext read/migration path but keep encrypted credential failure explicit; never add a plaintext fallback.

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
