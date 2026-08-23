# Defaults Guide

Last updated: 2026-08-23

Canonical guidance for defaults, reset behavior, snapshots, import safety and runtime application.

For performance/runtime side effects of settings changes also read
`Docs/Guardrails/Runtime_Efficiency.md`. For application-level capability activation read
`Docs/QtQuick_Migration/07_Settings_Capability_Activation.md`.

## 1. Sources of truth

- Canonical defaults: `core/settings/default_settings.py`.
- MC-only differences: `core/settings/default_profile_overrides.py`.
- Defaults API, normalization and preserve-on-reset rules: `core/settings/defaults.py`.
- Generated parity artifacts: `core/settings/defaults_snapshot.py`, `defaults_snapshot.json` and
  `defaults_generated.py` where current source still uses them.
- Generated distribution artifacts: `Docs/SRPSS_Settings_Screensaver.sst` and
  `Docs/SRPSS_Settings_Screensaver_MC.sst`.
- Persistent settings store: `JsonSettingsStore` through `SettingsManager`.

Generated artifacts are derived outputs. Regenerate them with project tooling instead of hand-editing
them.

Normal/Screensaver defaults are the authoritative base, not an override layer. The MC profile resolves
that base plus only the compact MC differences in `default_profile_overrides.py`.

Any descriptive list of MC differences in documentation is not a competing authority. The canonical
source + parity tests define the actual changed leaf set.

## 2. Storage shape

- Standard profile settings file: `%APPDATA%/SRPSS/settings_v2.json`.
- MC profile settings file: `%APPDATA%/SRPSS_MC/settings_v2.json`.
- Storage-path ownership: `core/settings/json_store.py` and `core/settings/storage_paths.py`.
- Structured roots include `widgets`, `transitions` and `ui`; older flat/dotted keys may remain
  accepted through public `SettingsManager` compatibility APIs where needed.

Use public `SettingsManager` accessors for active settings paths. Do not reach into the backing store
from UI code.

### Persistence and durability

- A public mutation becomes authoritative in memory immediately, invalidates relevant same-profile
  caches and publishes notifications through the canonical route.
- Routine mutation/`save()` requests persistence; explicit `flush(timeout=...)` is the durability
  acknowledgement where the current store contract requires one.
- One process-scoped ordered writer owns routine JSON serialization/temp write/fsync/atomic replace for
  a profile path; do not create a second routine writer.
- Startup migration/repair, Settings-dialog completion, reload and shutdown use canonical bounded
  durability boundaries.
- A failed write remains dirty/retryable rather than silently reporting durable success.
- SST export is explicit synchronous user transport; SST import mutates canonical settings and then
  follows normal persistence ownership.

## 3. Application capability activation defaults — E2 LANDED

Canonical application-level activation state is landed:

```text
widgets.family_activation.<family_id>
transitions.activation.<canonical transition setting name>
```

This is distinct from ordinary feature configuration:

```text
family activation != per-instance widget enabled
transition activation != Random-pool membership
transition activation != manual selection
```

The operator-facing E2 `SETUP`/lazy-navigation UI is already landed. Current compatibility defaults
remain intentionally all activated so introducing the capability schema did not silently change
existing installations. A missing activation key also resolves compatibly to activated.

**H0 owns the final Quick-era default/reset choices.** Do not describe E2 as still waiting to expose
activation, and do not pre-empt H0 merely because E2 UI exists.

Deactivation is **not reset**. It preserves detailed saved configuration, including per-instance
`enabled` values, CUSTOM layout and saved transition pool preferences, unless an explicit reset/H0/
schema migration says otherwise.

### 3.1 Widget dependency normalization

Canonical family dependency state includes:

```text
media = false
    -> visualizers = false
```

Reactivating Media does not silently reactivate Visualizers.

Generated defaults snapshots/SST artifacts derive activation state from canonical defaults rather than
maintaining a second family list.

### 3.2 Transition capability normalization

Canonical repair includes:

- all transitions deactivated -> activate Crossfade in canonical settings and persist repair;
- Random on + empty activated saved pool -> turn Random off, persist deterministic activated manual
  selection, preserve saved pool membership;
- stale/deactivated manual/Random selections must still pass normal admission after repair.

That is state repair, not renderer/factory substitution.

## 4. Reset and import preservation

- Preserve-on-reset keys live in `core/settings/defaults.py`.
- Reset/import flows reuse shared preservation and normalization contracts.
- SST import/export is a transport layer over current JSON settings architecture.
- Root `widgets` writes, widgets-map helpers and SST imports must share visualizer/capability
  normalization behavior.
- Checked-in default SSTs are generated canonical artifacts, not snapshots of one installed machine.
- User/runtime exports may contain operational metadata according to current transport rules; checked-in
  defaults must not leak credentials/private/machine-local state.

Capability deactivation must not cause a hidden/unbuilt Settings page to overwrite detailed values with
defaults. Activation state can be changed/saved without hydrating the detailed page.

## 5. Migration-era / legacy policy

Use the forward-obsolescence labels from `Docs/Documentation_Maintenance.md`.

### 5.1 Presentation-era keys

- Retired global preset keys such as `preset` / `custom_preset_backup` are migration inputs only.
- Legacy `transitions.type="Random"` is migration input only; `random_always` is the live Random
  authority.
- Modern defaults/exports must not emit retired schema keys as current authority.
- Persisted visualizer schema migration is version-gated and converges to current payloads rather than
  rerunning old normalization forever.

### 5.2 Visualizer growth/card-height controls

Pre-Quick per-mode visualizer growth/card-height settings are **CURRENT-LEGACY — WILL BE OBSOLETE at
H0/I caller cleanup**:

```text
spectrum_growth
osc_growth
sine_wave_growth
bubble_growth
devcurve_growth
```

They are not Quick-era presentation defaults and must not be copied into new Quick models/presets/
geometry merely because old Settings/runtime callers still exist.

### 5.3 Imgur

Imgur is **CURRENT-LEGACY — WILL BE REMOVED in Phase F0**. Do not perpetuate its defaults/settings
surface into Quick-era tooling.

## 6. Safe default change workflow

When changing a user-facing default:

- update `core/settings/default_settings.py` directly or use `tools/default_settings_editor.py`;
- update typed models/normalization helpers where applicable;
- update UI load/save behavior;
- regenerate defaults snapshot/SST artifacts;
- run defaults parity tests;
- add migration/import coverage if existing user settings are affected;
- update `Docs/TestSuite.md` if test inventory/authority changes;
- refresh `Spec.md`, `Index.md`, `Docs/Contracts.md` or focused docs when live contracts changed.

A successful Defaults Foundry **Save and Regenerate Defaults** establishes the new authoritative Normal
base and MC differential. Tests/artifacts/policy text follow that saved authority and reject it only when
a reproducible runtime/safety/migration/compatibility defect proves it harmful.

Tests guard the defaults contract; they are not a second defaults authority.

## 7. Runtime application / no-op safety

Persistence correctness is not sufficient. Applying settings must not create unnecessary runtime work.

Rules:

- applying the same effective value is a no-op before cache/shadow/raster/runtime invalidation;
- hydrating controls with persisted values is not a runtime change;
- constructing/hydrating a settings section must not contact providers/start workers/rebuild live
  caches merely because the page exists;
- do not replay an entire settings subtree when one leaf owner changed;
- do not manufacture a visualizer activation/generation for an identical resolved activation;
- do not rebuild widget shadow/card/static caches when their identity is unchanged;
- do not trigger full runtime recreation when a safe local owner exists;
- do not use broad “reapply saved settings” as Cancel semantics for preview-only state;
- family **deactivation** and instance `enabled=False` remain distinct runtime changes;
- transition activation changes must not leave a deactivated transition effectively selected through a
  stale/manual/random resolution path.

When runtime recreation is genuinely required, use the one ordered lifecycle boundary rather than a
partial teardown/rebuild side path.

Add/retain focused tests for:

- unchanged-value no-op behavior;
- no provider/work dispatch during hydration;
- no persisted-state loss from unbuilt lazy sections;
- activation toggles preserving detailed stored values;
- correct narrow live application owner;
- generation/lifecycle correctness when full recreation is necessary.

## 8. Defaults Foundry

- Run `python tools/default_settings_editor.py` for the standalone styled editor.
- The tree recursively discovers editable leaves in the canonical base; new ordinary settings do not
  require a handwritten duplicate Foundry form.
- Normal edits rewrite the canonical base. MC edits serialize only values that intentionally differ
  from resolved Normal defaults.
- Type-aware controls remain responsible for boolean/integer/decimal/JSON/font/RGBA domains.
- **Import SST / JSON Into Selected Profile** merges an external snapshot into the selected Foundry
  model before Save according to import-safety rules.
- Imports strip credentials/private/machine-local state and do not mutate the currently installed user
  profile merely because defaults are being edited.
- Save/undo/regeneration must be transactional across canonical base, MC overlay and generated
  artifacts.
- Default artifact generation must not inspect/migrate/reset/rewrite installed `%APPDATA%/SRPSS*`
  settings files.
- Regenerate current defaults artifacts with canonical project tools after intentional source changes
  and keep deterministic/parity tests green.
- Retired compatibility payloads remain hidden compatibility data only while their migration contract
  requires them.

The Foundry consumes capability activation as ordinary canonical schema data. It must not import heavy
widget/transition runtime implementations merely to expose/edit activation leaves.

J/final tooling must understand the final activation schema without becoming a second activation
catalog.

## 9. Visualizer defaults

Visualizer default changes also require:

- mode-registry/grouped field-spec review;
- curated preset expectations where authored payloads rely on changed values;
- preset repair/import/export coverage when schema shape changes;
- runtime-shaped validation when visible behavior changes.

An identical resolved visualizer configuration remains a technical no-op. Do not reset unrelated
visualizer history/GL state merely because a setting was touched.

The default visualizer viewport aspect is 1.5; literal 420x280 is an internal reference coordinate,
not a required user-visible size or default resolution.

## 10. CUSTOM and widget defaults

- Authored defaults remain the baseline/default authority even when a widget uses `Custom`.
- Committed CUSTOM geometry overlays authored defaults; it is not a replacement defaults surface.
- Canonical `widgets.layout_slots` starts empty. Saved slots belong to an installation profile and must
  not become checked-in defaults.
- If a control becomes derived/locked under `Custom`, lock it in UI rather than inventing a hidden
  alternate default.
- Preview-only Cancel preserves existing live widget/content state when the live owner was never
  mutated; persisted replay is not automatically required.
- Family deactivation preserves CUSTOM/detail settings; it does not erase a family's saved layout
  merely because its runtime ownership is dormant.

## 11. H0 settings epoch

H0 is the deliberate boundary for final Quick-era presentation/default state. It may intentionally
retire incompatible pre-Quick presentation state rather than carrying it forward indefinitely.

H0 must be explicit about:

- final family activation defaults;
- final transition activation/Random/pool defaults;
- retired presentation schema removal/ignore rules;
- generated snapshots/SST regeneration;
- migration/import behavior for old installed settings.

Do not move this reset policy earlier merely to simplify E1/E3/E4/F implementation.
