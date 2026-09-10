# Visualizer Preset Sparse Catalog + Failed Settings Body Leak — 2026-09-10

## Failure

A Sphere preset consolidation exposed two independent bad assumptions:

1. the preset loader required authored preset numbers to be contiguous, so a valid user catalogue such as `1, 2, 5` aborted application startup;
2. lazy Settings-body construction was not transactional, so a hydration exception could leave a partially built mode body attached to the Visualizers page. Retrying appended another preset/Advanced block.

## Binding contracts

Visualizer preset files are user-authored state. Counts may grow or shrink freely and authored numbers may be sparse. Runtime slider positions are compact presentation positions; they never authorize renaming/deleting a user's backing files. Edit Preset must retain the real source path and Save-As must choose a non-colliding authored number.

A lazy Settings-body factory must either return one fully hydrated body or leave no body attached. Failed construction is removed before the exception propagates. A preset-one body must not transiently expose Custom/Advanced controls while hydration is pending.

Shipped preset manifests are packaging/reconciliation metadata, not runtime authority over the user's authored catalogue.

## Regression shape

Keep coverage for at least:

- authored slots `1, 5` compacting to two runtime presets plus Custom;
- only `preset_20_*.json` surviving;
- Save-As choosing the next non-colliding authored number;
- failed lazy-body construction cleaning its partially attached QWidget before retry.
