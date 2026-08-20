# 06 — Build, Tooling, Tests, Installed Validation and Cutover Evidence

Status: technical decomposition only
Last updated: 2026-08-20

Cross-links:

- `Current_Plan.md`
- `Docs/TestSuite.md`
- `Docs/Harness_Index.md`
- `Future_Cleanup.md`

## 1. Build risk is an early migration concern

Current Nuitka build scripts include:

- shaders;
- images;
- themes;
- multimedia plugins/modules.

They do not yet explicitly package SRPSS QML files or select QML plugins.

Do not discover this only after production cutover.

## 2. QML source packaging

Recommended simple repository shape:

```text
rendering/quick/qml/
    DisplayScene.qml
    components/*.qml
```

Load relative to package/runtime source location, not current working directory.

For Nuitka onefile/standalone, include the directory explicitly, e.g. conceptually:

```text
--include-data-dir=rendering/quick/qml=rendering/quick/qml
```

Do not generate paths that only work from the repository root.

A Qt resource `.qrc` is optional, not required unless file packaging proves fragile.

Choose one packaging method and remove the abandoned one.

## 3. Nuitka Qt QML plugin

Nuitka's PySide6 plugin supports the `qml` Qt plugin family and detects QtQuick/QtQml usage, but SRPSS
should make the requirement explicit for deterministic builds.

Update the relevant build scripts with:

```text
--include-qt-plugins=qml
```

while preserving existing required multimedia plugins.

Ensure Python imports make QtQml/QtQuick dependencies visible.

Do not use `--include-qt-plugins=all` unless a focused packaging failure proves necessary; it can add
large unrelated dependencies.

## 4. Build scripts to reconcile

Audit/update together:

```text
scripts/build_nuitka.ps1
scripts/venv/build_nuitka.ps1
scripts/venv/build_nuitka_diagnostic.ps1
scripts/build_nuitka_mc_onedir.ps1
scripts/venv/build_nuitka_mc_onedir.ps1
```

Also inspect any shared build runner/job definitions that duplicate expected assets/modules.

Keep build layout/publishing behaviour unchanged unless Quick packaging actually requires a change.

## 5. Early compiled smoke

After the first production Quick render-node foundation exists:

Build the smallest normal/diagnostic target that exercises:

- QQuickWindow;
- QtQml;
- QML component load;
- threaded render loop;
- OpenGL backend;
- custom render node;
- clean exit.

This gate occurs **before** mass widget migration.

If QML plugin/data packaging fails, fix packaging then continue. That is not a reason to return to
QRhiWidget.

## 6. New production-shaped tools

Create only tools that directly reduce migration risk.

### `tools/quick_runtime_smoke.py`

Uses production Quick classes.

Proves:

- one/two windows;
- render-thread identity;
- base image;
- simple transition;
- scene teardown;
- generation recreation.

No provider/network dependency.

### `tools/quick_widget_gallery.py`

Synthetic/offline models for all widget families.

Shows:

- ordinary positions;
- custom styles;
- extreme but valid opacity;
- shadows;
- text/header shadows;
- borders/radii;
- artwork;
- progress controls;
- visualizer card placeholder/real deterministic mode;
- two-display focus stress.

Supports deterministic screenshot capture where practical.

### lifecycle harness

Prefer adapting an existing lifecycle harness to instantiate the production Quick runtime rather than
creating another unrelated lifecycle framework.

## 7. Existing P0 benchmark

Preserve P0 as architecture evidence.

Do not keep expanding it.

It may be left unchanged even if equivalent pacing code moves into production; evidence
reproducibility is more important than eliminating a small tool duplicate.

Use new production-shaped harnesses for migration regression.

## 8. Automated tests

Add/update focused tests for:

### bootstrap

- render loop configured before Quick creation;
- graphics API OpenGL;
- no QQuickWidget.

### runtime

- display generation;
- readiness;
- multi-display;
- teardown.

### render nodes

- immutable sync state;
- resource lifecycle;
- transition parameters;
- no live QWidget access.

### widgets

- model mapping;
- QML component load;
- visual style mapping;
- CUSTOM;
- actions.

### visualizer

- existing permanent gates + Quick snapshot/render ownership.

### build

- QML directory exists;
- build scripts include the required data/plugin contract;
- build runner knows expected payload.

## 9. Test cadence

Every slice:

```text
focused pytest
```

At major phase boundaries:

```text
python tests/run_chunked.py --chunks 4 --timeout-seconds 900
```

Do not run the entire suite after every three-line edit.

Do run the full bounded suite before:

- production cutover;
- major legacy deletion;
- final migration closure.

## 10. Manual/installed gates

### Renderer/transition

- 60 Hz;
- 165 Hz/high refresh;
- mixed refresh;
- all transitions;
- transition interruption/cycle.

### visualizer

- all five modes;
- Bubble eyes-on/BTF;
- Pause/Play;
- Spectrum idle;
- CUSTOM.

### widgets

- full widget composition;
- shadows;
- opacities;
- borders;
- sizing;
- stacking;
- interaction.

### lifecycle

- Settings;
- CUSTOM;
- monitor off/wake;
- topology change;
- repeated restart;
- clean exit.

### MC

- focus switching;
- click interaction;
- taskbar/Alt+Tab;
- context menu;
- shadow-corruption stress.

## 11. Physical cadence

Do not use internal frame callbacks as sole physical proof.

Final production Quick evidence:

- PresentMon phase-correlated;
- p95/p99/max;
- severe-gap counts;
- both displays;
- light;
- external heavy load.

Use the existing worker baseline from preserved evidence.

Do not ask for another manual worker-heavy run.

## 12. Heavy-load success

The architecture was selected because Quick heavy already landed near the old-light performance
class.

Final migrated production should not throw that away.

If full feature parity adds load:

- attribute GUI sync;
- render-node cost;
- widget scene cost;
- source/provider cost;
- texture upload;

before blaming the architecture.

Do not reduce authored visualizer cadence or widget fidelity to meet the benchmark.

## 13. Long soak

After final Quick architecture:

- ordinary/light telemetry;
- optional diagnostic comparison;
- memory;
- private commit;
- handles;
- threads;
- GL/render resources;
- topology wake;
- clean shutdown.

The old retention signal remains separate until reproduced on final architecture.

## 14. Git checkpoint discipline

Every successful slice is pushed.

Before each push:

```text
git status
git diff --check
focused tests
```

Then:

```text
git add <intended files>
git commit -m "<specific landed slice>"
git push
```

Never use destructive git to make the tree convenient.

Do not wait for operator approval after a green checkpoint unless the next step requires a genuinely
unavailable manual observation.

## 15. Final cutover checklist

Production owner is Quick only.

Verify absence of active imports/callers for:

```text
DisplayWidget runtime presenter
GLCompositorWidget
ExternalOpenGLRhiWidget
CompositorVisualizerLayer
GUI present_tick physical owner
QQuickWidget
```

Historical evidence/tests may still name them.

After caller proof, remove dead production files through `Future_Cleanup.md`.

## 16. Documentation/tool closure

Update:

- `Docs/TestSuite.md`;
- `Docs/Harness_Index.md`;
- `Index.md`;
- build documentation if any;
- `Future_Cleanup.md`.

Delete migration-only tools that no longer guard a live risk.

Keep cheap production-shaped regression harnesses.
