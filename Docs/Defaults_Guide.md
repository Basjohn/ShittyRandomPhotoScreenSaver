# Defaults Guide

Last updated: 2026-09-06

Canonical guidance for defaults, reset behavior, snapshots, import safety and runtime application.

## Sources of truth

Canonical defaults: `core/settings/default_settings.py`; MC differences:
`core/settings/default_profile_overrides.py`; normalization/preserve-on-reset: `core/settings/defaults.py`;
generated snapshot/SST artifacts are derived; persistent profile store is `JsonSettingsStore` through
`SettingsManager`. `core/settings/default_contract.py` is the lightweight read seam for code that must
resolve a product default without importing Settings UI/runtime owners; `core/settings/structured_roots.py`
owns structured-root repair membership; `core/settings/defaults_authority_audit.py` is the permanent
anti-fragmentation audit.

Regenerate derived artifacts with project tooling rather than hand-editing. Normal/Screensaver defaults are
base authority; MC is base plus compact differences.


## Canonical-default authority rules

A user-facing product default exists in exactly one place: `core/settings/default_settings.py` (plus the
small MC differential where behavior truly differs). UI builders, previews, registries, runtime recovery,
tools and tests may **project or validate** that authority; they do not own a second literal.

Forbidden patterns include:

- local `dict.get(key, <product literal>)` / `to_bool(..., <product literal>)` recovery for a canonical key;
- copied widget/transition default tables in descriptors, preview helpers or runtime owners;
- treating a Settings-session capture, runtime history, recovery metadata or user `Custom` snapshot as a
  fresh-install product default;
- hand-editing `defaults_snapshot.json` or checked-in SST defaults;
- allowing tooling/root entrypoints to escape the same authority audit as production packages.

Use `require_canonical_default(...)`, `get_default_settings(...)`, typed-model default projection, or the
resolved config already passed into a runtime owner. If a missing value is genuinely algorithmic/session/
presentation policy rather than a user-facing product setting, keep it local and name it as such.

`None` is a real persisted value when the schema permits it; it is not interchangeable with a missing key.
Fresh Settings bucket-expansion state is canonical under `ui.*_bucket_states` and currently starts collapsed.

## Approved fresh-profile baseline (2026-09-06)

The reviewed standard/Screensaver baseline is intentionally conservative about screen space and capability cost:

- Settings theme: `Default Dark [Single] [Glass]`; Widget Theme remains linked to `default_dark`;
- all persisted Settings bucket state starts collapsed;
- every ordinary/Visualizer widget monitor route in the standard profile starts on **Display 1**; changing a route does not change that widget's `enabled` state;
- MC is a deliberate profile exception and preserves its established monitor routes through `default_profile_overrides.py` (including existing Display-2 and `ALL` routes);
- Weather remains enabled with blank location (`""`), leaving location discovery/onboarding user-specific rather than baking a city into product defaults;
- Gmail remains enabled and starts on Display 1;
- Spotify Visualizer remains enabled and starts in **Bubble**; its existing Media/now-playing admission keeps it dormant when there is nothing to visualize, while its enabled-mode pool excludes experimental Sphere so Sphere stays dormant until explicitly enabled;
- Transitions start in Random mode through canonical `transitions.random_always=True`; `transitions.type` remains the remembered manual selection and must not be rewritten to the retired `"Random"` sentinel.

Do not infer ordinary widget enablement from monitor routing. The standard profile may place disabled families on Display 1 so future activation has a sane single-monitor destination without consuming fresh-install screen space.

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
For every **known** family/transition, a missing persisted activation member resolves through the canonical
product default. Callers must not invent `True`/`False` fallbacks. Unknown external/compatibility identities
remain a separate admission concern. Any change to activation defaults is an intentional product/schema
decision.

Deactivation is not reset: preserve detailed settings, ordinary enabled, CUSTOM geometry and transition
pool preferences unless explicit schema/default migration says otherwise.

Canonical dependency: `media=false -> visualizers=false`; Media reactivation does not silently reactivate
Visualizers.

Transition repair is canonical settings repair, never renderer substitution: zero activated transitions
repairs Crossfade activation; Random + empty effective saved pool disables Random and persists deterministic
activated manual selection while preserving saved pool membership; final runtime admission revalidates.


## Adding/removing capability defaults without losing dormancy

### Widget family

`core/settings/widget_family_catalog.py` owns stable family membership/dependencies.
`rendering/widget_descriptors.py` owns factory/settings/runtime capability metadata. A new family therefore
adds one canonical `widgets.family_activation.<family_id>` default and its ordinary member defaults, then
extends descriptor/catalog truth instead of adding handwritten Settings/runtime branches. A deactivated
family preserves its detailed settings, ordinary enabled state and committed CUSTOM data, but must not
construct providers/services/workers or drag heavy family implementation imports through common Quick
infrastructure. Dependencies are catalog-owned (`visualizers` requires `media`); never scatter special-case
dependency checks.

Removing a family is the inverse operation: caller-proof it, remove member/runtime/settings descriptor and
catalog ownership, remove the canonical activation/default subtree when no persisted compatibility contract
requires it, retire packaging/tests/docs, and prove common imports stay clean. Do not leave a dead default key
or a dormant-looking UI branch as a hidden second registry.

### Transition

`rendering/transition_registry.py` owns canonical identity/labels/aliases/cycle/hardware metadata.
`rendering/quick/transitions/implementation_registry.py` owns lazy renderer import paths. Canonical defaults
own activation, Random-pool membership, duration and effect parameters. A deactivated transition is excluded
from manual/Random admission and its renderer implementation is not resolved merely because the application
started; saved pool/manual preferences remain data, not execution permission. If persisted state leaves zero
activated transitions, canonical repair explicitly reactivates Crossfade rather than bypassing activation.

Adding/removing a transition updates those authorities together and keeps registry/implementation/default
parity tests green. Dynamic import dormancy does **not** exempt the implementation module/resources from
frozen-build packaging visibility.

## 5.0.0 installer migration reset

For the 5.0.0 migration release only, the Standard and MC installer `resetsettings` task defaults ON. A selected reset must remove both the current `settings_v2.json` snapshot and that profile's pre-JSON Qt `QSettings` registry tree; deleting JSON alone is not a reset because first launch can import the legacy registry state again. Diagnostic deliberately remains opt-in because it consumes the ordinary Screensaver profile.

If reset is not selected, valid legacy state is intentionally migrated, canonical missing leaves are filled, known aliases/schema are normalized, and validation repairs known invalid values. Malformed JSON or a non-mapping snapshot is treated as a load failure and regenerates canonical defaults. A syntactically valid historical value outside known migration/validation rules can survive by design, so v5's default-checked installer reset is the safe mass-migration baseline rather than a substitute for ongoing schema validation.

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

Update canonical source -> profile override only for genuine profile differences -> typed models/normalizers -> UI load/save -> regenerate derived artifacts -> parity tests -> migration/import coverage when installed settings are affected -> current docs when the contract changes. Tests guard contract; they are not second authority.

The deterministic in-repo regeneration/check path is:

```powershell
python -m core.settings.defaults_snapshot_builder --write-all
python -m core.settings.defaults_snapshot_builder --check-all
pytest tests/test_defaults_schema_authority.py -q --tb=short
python tools/check_defaults_authority.py
```

`--write-all` owns `core/settings/defaults_snapshot.json` plus the checked-in Normal/MC SST defaults documents. Curated Visualizer presets and user Custom snapshots are deliberately outside this regeneration path.

## Runtime application / no-op safety

Identical effective values no-op before invalidation. Hydration is not runtime change. Building Settings
page does not contact providers/start workers. Do not replay whole subtree for one leaf or recreate full
runtime when local owner suffices. Do not use broad persisted replay as Cancel for preview-only state.
Family deactivation and ordinary enabled=False remain distinct.

## Defaults Foundry

A Defaults Foundry/editor may edit canonical defaults/profile differences, but it is an authoring surface rather than authority. The supplied tree does not require an in-repo editor to regenerate artifacts: `core.settings.defaults_snapshot_builder --write-all` is the deterministic derivative path. Any external/optional Foundry must remain import-safe, must not carry its own product-default literals, must strip private/machine-local state on import, and must never mutate installed user settings merely because defaults are being edited. Generated snapshot/SST artifacts must remain exact projections of canonical source.

## Visualizer / CUSTOM defaults

Visualizer default changes require registry/field-spec, curated preset and import/export review plus
runtime-shaped validation when visible behavior changes. Curated preset JSON is a separate authored overlay
authority and must not be regenerated as a side effect of changing product defaults. User Custom snapshots
are persisted user state, not product defaults. Identical resolved config is no-op. Viewport aspect
1.5; 420×280 is internal reference only.

Authored widget defaults remain baseline under CUSTOM; committed CUSTOM geometry overlays them. Layout slots
start empty in checked-in defaults. Family deactivation preserves saved layout/detail. Preview Cancel restores
prior live state when not committed.

## Post-sanitization settings authority

The Quick-era family/transition activation defaults, Random/pool defaults and retired-presentation schema handling are
landed destination behavior. The 2026-09-06 defaults-authority sweep removed duplicate/shadow product-default owners
and installed a whole-first-party-Python anti-fragmentation gate. Future cleanup may delete caller-dead residue only
after exact use/caller proof; it must not silently redefine reset/default behavior. Any future default change follows
the safe-default workflow above and regenerates derived artifacts deliberately.
