# Visualizer Preset Repair: data ownership and safety

`tools/visualizer_preset_repair.py` is the Foundry/CLI repair owner. It does not maintain a separate list of
Visualizer controls: `visualizer_presets.preset_artwork_keys()` reads the typed mode spec, and missing controls
come from canonical defaults. New drift gains, ray controls and camera metadata therefore follow the same path
as existing artwork. Experimental values belonging to disabled authoring choices remain stored.

## Admission and migration

- Shared preset section extraction reads direct `settings`, dotted SST settings, `spotify_visualizer`, and
  canonical `snapshot.widgets.spotify_visualizer`. Import and repair use the same extraction and migrations.
- Repair retains every output key of the shared migration, rather than a second hand-written rename list.
  In particular, old cosmetic Ray Flicker becomes Ray Shimmer with its authored value; defaults fill only missing
  values. An already authored Shimmer takes precedence over the old alias.
- Existing flat settings are repaired in place, without creating a second snapshot authority. A legacy
  backup-only payload migrates into one live snapshot section before its retired backup block is removed.
- Explicit preset mode mismatches are rejected before mutation. Starting-view metadata must pass its shared
  validator. Names, descriptions, starting views, unrelated widgets and operator metadata remain authored data.
  Reindex and Swap change filename slots and index/name metadata only; they do not sanitize artwork.

## Mutation and recovery

Repair serializes and validates before replacing the source. It keeps its recoverable backup outside the curated
tree and compares source bytes before and after backup creation, refusing an observed newer edit. This is an
optimistic check, not a claim of cross-process compare-and-swap locking. Replacement uses the shared sibling-temp
atomic writer, so failure cannot leave a partially written source. Undo-history persistence uses the same writer.

Undo preflights every backup and expected destination hash, refuses a newly occupied original filename, and
reads all before-images before writing. It atomically restores complete backup bytes before deleting obsolete
destinations, retaining any path which is also another row's restored source. A failed multi-file action rolls
back its before-images; rollback failures are reported with retained backups required for recovery. Byte writes
preserve original line endings. Ordinary repair retains its existing two-backup rotation; paired transactions
keep unique backups referenced by Undo.

An existing source manifest may be regenerated. An absent manifest stays absent. Manifest retirement and the
release/installer ownership audit remain separately queued; this tool audit does not authorize deleting or
rewriting operator presets or release mirrors.

## Focused proof

`tests/test_visualizer_preset_repair_eb.py` crosses real repair/import/reindex/swap/Undo boundaries with test-owned
data: all newly added fields, default fill, rename precedence, payload shape, metadata, backups, idempotence,
failed atomic promotion, concurrent-edit rejection, wrong-mode rejection and multi-file Undo recovery.
`tests/test_visualizer_preset_repair_integrity.py` retains slot/collision/paired-Undo guards.

Read-only prospective repair of all80 current curated files preserved effective settings and starting views,
with zero source writes (`tmp/eb28_preset_repair_audit/readonly_catalog_receipt.json`). This receipt identifies
that audited source state; tests never pin mutable operator preset values. `--audit-curated` is the tool's
non-mutating structural audit; `--repair-all` is explicitly mutating and is not an audit substitute.
