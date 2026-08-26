# Defaults Guide

Last updated: 2026-08-26

Canonical guidance for defaults, reset behavior, snapshots, import safety and runtime application.

## Sources of truth

Canonical defaults: `core/settings/default_settings.py`; MC differences:
`core/settings/default_profile_overrides.py`; normalization/preserve-on-reset: `core/settings/defaults.py`;
generated snapshot/SST artifacts are derived; persistent profile store is `JsonSettingsStore` through
`SettingsManager`.

Regenerate derived artifacts with project tooling rather than hand-editing. Normal/Screensaver defaults are
base authority; MC is base plus compact differences.

## Storage / durability

Use public SettingsManager APIs. UI does not reach backing store directly. Public mutation is authoritative
in memory, invalidates relevant caches and publishes canonical notification. Routine saves use process-owned
ordered writer; explicit flush is durability acknowledgement where required. Failed writes remain dirty/
retryable. SST export is explicit sync transport; import mutates canonical settings then uses normal
persistence ownership.

## Capability activation defaults

```text
widgets.family_activation.<family_id>
transitions.activation.<canonical transition name>
```

Family activation != ordinary widget enabled. Transition activation != Random pool/manual selection.
Missing activation keys resolve compatibly to activated. Current migration compatibility defaults remain
activated; H settings epoch owns final Quick-era default/reset choices.

Deactivation is not reset: preserve detailed settings, ordinary enabled, CUSTOM geometry and transition
pool preferences unless explicit schema/default migration says otherwise.

Canonical dependency: `media=false -> visualizers=false`; Media reactivation does not silently reactivate
Visualizers.

Transition repair is canonical settings repair, never renderer substitution: zero activated transitions
repairs Crossfade activation; Random + empty effective saved pool disables Random and persists deterministic
activated manual selection while preserving saved pool membership; final runtime admission revalidates.

## Reset / import safety

Hidden/unbuilt/deactivated Settings page never overwrites preserved detail values with controls it did not
hydrate. Checked-in SST defaults are generated canonical artifacts, not installed-machine snapshots and must
not leak private/machine-local state.

## Retired migration-era schema

Modern defaults/exports do not emit retired schema as current authority:

- old global preset/custom-preset-backup keys are migration input only where compatibility still reads;
- legacy `transitions.type="Random"` is migration input only; `random_always` is live;
- `widgets.shadows.offset`, Intense shadow mode and text blur are retired;
- `shadowtuning.json` is retired;
- deprecated Imgur product/default surface was removed in F0 and must not be recreated;
- retired visualizer growth/card-height fields are not Quick presentation geometry and are removed/ignored
  at explicit settings-epoch/caller-cleanup boundary rather than copied forward.

## Safe default change

Update canonical source -> typed models/normalizers -> UI load/save -> regenerate snapshot/SST -> parity
tests -> migration/import coverage when installed settings affected -> current docs when contract changes.
Tests guard contract; they are not second authority.

## Runtime application / no-op safety

Identical effective values no-op before invalidation. Hydration is not runtime change. Building Settings
page does not contact providers/start workers. Do not replay whole subtree for one leaf or recreate full
runtime when local owner suffices. Do not use broad persisted replay as Cancel for preview-only state.
Family deactivation and ordinary enabled=False remain distinct.

## Defaults Foundry

`tools/default_settings_editor.py` edits canonical defaults/profile differences and regenerates artifacts.
It remains import-safe: capability leaves do not require heavy widget/transition runtime imports. Imports
strip private/machine-local state and do not mutate installed user settings merely because defaults are being
edited.

## Visualizer / CUSTOM defaults

Visualizer default changes require registry/field-spec, curated preset and import/export review plus
runtime-shaped validation when visible behavior changes. Identical resolved config is no-op. Viewport aspect
1.5; 420×280 is internal reference only.

Authored widget defaults remain baseline under CUSTOM; committed CUSTOM geometry overlays them. Layout slots
start empty in checked-in defaults. Family deactivation preserves saved layout/detail. Preview Cancel restores
prior live state when not committed.

## H settings epoch

H chooses final Quick-era family/transition activation defaults, Random/pool defaults, retired presentation
schema ignore/removal, regenerated artifacts and old-installed-settings migration/import handling. Do not move
this reset policy earlier merely to simplify F/G.
