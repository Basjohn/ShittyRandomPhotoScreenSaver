# Persisted-Input Compatibility Bridges

## What this is

SRPSS accepts real old user data — profiles, presets, themes, layouts,
credentials — that predates the current schema. A small set of
**input-boundary bridges** migrate that old shape, once, into the current
canonical owner. They are isolated at the input seam, cost ~nothing at runtime,
and are **correct**: the healthiest state of this codebase is with them intact.

They are **not** legacy cruft, and there is **no cleanup backlog** behind them.
This document exists so that an agent working near a `*_input_compat.py` seam or
a `_migrate_*` function recognizes it as user-data protection *before* "tidying"
it away. Genuinely caller-dead residue is deleted outright during ordinary work
(with its test cascade in the same commit) — it is never parked in a register,
and reading or cross-linking this file is not permission to start removing a
bridge.

## The invariant every bridge holds

- **One-way.** The old shape is accepted only at the input boundary; current
  runtime / default / UI / export always uses the canonical owner and never
  writes the retired form.
- **Idempotent.** First load may transform old state; a second load must not
  re-run, drift, duplicate or re-emit the retired shape.
- **Horizon-gated.** A bridge is removed only after the operator explicitly
  declares its support horizon closed — never as a side effect of encountering
  the code. Premature removal is a data-loss / silent-resurrection /
  credential-exposure event, not hygiene.

## Current bridges and the shortcut that turns each into a disaster

The blocked shortcut is spelled out so it can be refused on sight; none proceeds
without the safe path below.

- **QSettings → JSON profile** (`core/settings/settings_manager.py`:
  `_run_initial_migration` / `_migrate_from_qsettings`). Fires whenever
  `settings_v2.json` is absent, including after Reset.
  *Blocked:* removing the bridge while the installer still clears the QSettings
  tree (or vice versa); making Reset delete only the JSON; treating the
  migration `except → clear()` as harmless. Any of these lets a retired
  QSettings tree become authority again. The migration must **fail loud**, not
  silently clear to defaults. Do not replace it with a second settings backend.
- **Gmail plaintext OAuth token** (`core/gmail/gmail_bootstrap.py` reads/converts/
  deletes legacy `gmail_credentials.json`).
  *Blocked:* removing read/convert/delete while any supported release could have
  written the plaintext token — it would sit in cleartext forever. Never add a
  plaintext *read* fallback; encrypted-credential failure stays explicit. Token
  writes refuse any non-`dpapi::` output (mirrors Steam).
- **Non-Windows DPAPI `plain::` fallback** (`core/windows/dpapi.py`; Steam
  refuses it in `core/steam/credentials.py`). Production is Windows.
  *Blocked:* altering it without Gmail + Steam fixtures in the same slice; never
  weaken Windows encrypted storage or the Steam refusal to simplify dev/test.
- **Old Visualizer persisted schema / preset inputs** (`enabled_modes` →
  `mode_activation`, v9 schema versioning, retired global/technical keys, Bubble
  gradient direction, Spectrum notch layout, Sphere finish/material keys, old
  snapshot wrappers). Current authority is the mode registry + per-mode
  settings/preset contracts.
  *Blocked:* using shipped manifests or defaults to overwrite authored preset
  files; flattening sparse/arbitrary authored preset numbering; retaining
  `enabled_modes` as a second dormancy representation. Widest cascade in the
  repo and touches irreplaceable user data — retire dead last, in the smallest
  groups, and keep **profile-migration** fixtures separate from
  **authored-preset** fixtures.
- **SST import versions / flat snapshots** (`core/settings/sst_io.py`).
  *Blocked:* deleting forward/newer-version rejection because it "mentions schema
  versions"; weakening Steam-secret stripping (SST is a privacy boundary) to
  simplify import.
- **Settings aliases / structured-root normalization**
  (`input.hard_exit` → `input.interaction_mode`;
  `core/settings/structured_input_compat.py`). Already the correct shape
  (explicit input owner + distinguishing fixtures); low-risk to retire once the
  horizon closes — keep the `set`-rejects-retired-key guard.
- **Settings Theme v5 → v6** (`ui/settings_theme_input_compat.py`).
  *Blocked:* weakening strict v6 validation to tolerate incomplete old themes —
  that silently corrupts a user theme into a defaults blend.
- **Widget Theme v1/v2 → v3 material-state rewrite**
  (`core/settings/widget_theme_input_compat.py`).
  *Blocked:* reintroducing card-material runtime ownership to make old state
  meaningful. Runtime card Glass/Acrylic/material is rejected historical
  architecture, not "cleanup compatibility."
- **Ordinary Widget family colour bridge** (old per-family colour persistence,
  superseded by Widget Theme `header.*` + Style Overrides → Header Fill).
  *Blocked:* flattening durable per-family colour customization to make the
  bridge disappear. `Reset All Colours to Theme` stays a user-invoked action,
  never startup normalization.

### Not debt — current input contracts (do not "simplify")

- **Custom layout version handling.** `CUSTOM_LAYOUT_VERSION = 2` is enforced by
  hard rejection (`load_custom_layout_map` drops any `version != 2`); there is
  **no** v1 migration path to remove, and adding one would *widen* compatibility.
  `CUSTOM_LAYOUT_RESTORE_VERSION = 1` is current, not debt.
- **Settings bucket normalization.** Sparse-true on disk, fully enumerated /
  fail-loud in memory, one open bucket per scope
  (`core.settings.ui_bucket_state.normalize_single_open_bucket_states()`). Do
  not complicate it to reject harmless old `false` members.

## Removing a bridge safely (only when the operator closes its horizon)

1. Find every current caller and input source — production, installers,
   import/export tools, settings snapshots, authored presets, layout slots,
   themes, helper processes — not just Python call sites.
2. Name the current canonical authority; confirm the old shape is accepted only
   at input.
3. Build/retain a representative **old-input fixture** before deletion.
4. Prove exact canonical output **and** idempotence (second load is a no-op).
5. Preserve user-authored state; never flatten presets/layouts/themes to
   defaults to make migration code disappear.
6. Remove **one seam at a time**; never combine with perf tuning, visual
   retuning, defaults changes or unrelated schema redesign.
7. Do not resurrect retired architecture to satisfy a stale test — rehome the
   still-valid behavior to the current owner, then delete the fossil.

## Enforcement

Each bridge owns its own input-compat test (and an old-input fixture); the seam
descriptions above name the wider **same-commit cascade** each retirement must
rehome/retire/re-floor. A bridge cannot be removed without updating its whole
named cascade in that one change. Leaving the cascade "for the suite to find
later" is exactly what produced the 2026-09 broad-suite red storm — tests
asserting a migration-era shape/owner/threshold/default that production had
already superseded, surfacing weeks later as expensive "why is this red" work
that always ended in "production was right."
