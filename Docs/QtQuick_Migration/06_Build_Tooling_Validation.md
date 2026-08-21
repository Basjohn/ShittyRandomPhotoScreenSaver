# 06 — Build, Tooling, Tests, Installed Validation and Cutover Evidence

Status: technical decomposition only  
Last updated: 2026-08-21

Cross-links:

- `Current_Plan.md`
- `Docs/TestSuite.md`
- `Docs/Harness_Index.md`
- `Future_Cleanup.md`

## 1. Build risk is handled early; build execution is deferred

During Phases C–G, update build scripts, packaging declarations, and `build_runner.py` as required and
validate with focused static/script tests.

Do not initiate a compiled/full product build merely as routine migration validation.

Executable/product validation runs after migration implementation is complete and the operator
explicitly schedules it, unless the operator explicitly asks for an earlier build.

## 2. Test/workflow environment

SRPSS source/document mutation occurs in the real local Git worktree.

Repository connectors/APIs are read/audit tools for this project, not normal file mutation.

SRPSS does not use GitHub Actions or another repository-hosted CI workflow as the normal migration
test path. Do not add hosted CI unless the operator explicitly requests it.

Use:

- current capable Windows worktree for ordinary deterministic tests;
- clean checkout when reproduction/isolation benefits from it;
- proper Windows/Qt/OpenGL environment for real Quick/GL;
- operator hardware for physical displays, refresh/DPR, GPU, PresentMon and eyes-on acceptance.

## 3. QML source packaging

Preferred repository shape:

```text
rendering/quick/qml/
    DisplayScene.qml
    components/*.qml
```

Load relative to package/runtime source location, not current working directory.

For Nuitka onefile/standalone include the QML directory explicitly, conceptually:

```text
--include-data-dir=rendering/quick/qml=rendering/quick/qml
```

Do not generate paths that only work from repository root.

A Qt resource `.qrc` is optional unless file packaging proves fragile.

Choose one packaging method and remove abandoned duplicates.

## 4. Nuitka Qt QML plugin

Make the required QML plugin family explicit:

```text
--include-qt-plugins=qml
```

while preserving required multimedia plugins.

Ensure Python imports make QtQml/QtQuick dependencies visible.

Do not use `--include-qt-plugins=all` unless a focused packaging failure earns it.

## 5. Build scripts to reconcile

Audit/update together as applicable:

```text
scripts/build_nuitka.ps1
scripts/venv/build_nuitka.ps1
scripts/venv/build_nuitka_diagnostic.ps1
scripts/build_nuitka_mc_onedir.ps1
scripts/venv/build_nuitka_mc_onedir.ps1
```

Also inspect shared build-runner/job definitions that duplicate expected assets/modules.

Keep publishing/layout behavior unchanged unless Quick packaging requires a change.

## 6. Deferred operator-scheduled compiled smoke

After migration implementation is complete and the operator schedules a build window, build the
smallest normal/diagnostic target that exercises:

- QQuickWindow;
- QtQml;
- QML component load;
- threaded render loop;
- OpenGL backend;
- custom render node;
- clean exit.

This is not an implementation gate for transition, visualizer, widget, or CUSTOM migration work.

A QML plugin/data packaging failure is a packaging defect, not a reason to return to QRhiWidget.

## 7. Production-shaped tools

Create only tools that directly reduce migration risk.

### Quick runtime smoke

Use production Quick classes to prove one/two windows, render-thread identity, base image, simple
transition, scene teardown and generation recreation.

### Quick widget gallery

Synthetic/offline models for widget families showing normal/extreme valid styling, shadows, borders,
artwork, controls, visualizer card and two-display focus stress.

After E2, include activated/deactivated family navigation/runtime cases without eagerly constructing
all settings pages.

### Lifecycle harness

Prefer adapting existing lifecycle harnesses rather than creating another lifecycle framework.

## 8. Existing P0 benchmark

Preserve P0 as architecture evidence.

Do not keep expanding it merely to reconfirm Quick.

Use production-shaped harnesses for migration regression.

## 9. Automated/focused tests

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
- GL-state restoration;
- no live QWidget access.

### widgets/settings

- model mapping;
- QML component load;
- visual style;
- CUSTOM;
- actions;
- E2 capability activation;
- lazy settings-page hydration safety.

### visualizer

- existing permanent gates + Quick snapshot/render ownership.

### build

- QML directory exists;
- build scripts include required data/plugin contract;
- build runner knows expected payload.

## 10. Test cadence

Every slice:

```text
focused pytest
```

At major phase boundaries, when useful:

```text
python tests/run_chunked.py --chunks 4 --timeout-seconds 900 --log
```

Do not run the entire suite after every small edit.

Do run the bounded suite before production cutover, major legacy deletion, and final migration closure
when the environment is appropriate.

## 11. Manual/installed gates

### Renderer/transition

- 60 Hz;
- high refresh;
- mixed refresh;
- all transitions;
- interruption/cycle;
- authored visual parity.

### visualizer

- all five modes;
- Bubble eyes-on/BTF;
- Pause/Play;
- Spectrum idle;
- CUSTOM.

### widgets/settings

- full widget composition;
- shadows/opacities/borders/sizing/stacking;
- interaction;
- E2 activation and pill navigation;
- no hidden family runtime work.

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

## 12. Physical cadence

Do not use internal frame callbacks as sole physical proof.

Final production Quick evidence may include:

- PresentMon phase-correlated;
- p95/p99/max;
- severe-gap counts;
- both displays;
- light/external heavy load.

Use the existing worker baseline from preserved evidence.

Do not ask for another manual worker-heavy baseline.

## 13. Heavy-load success

Quick was selected because heavy-load behavior already landed near the old-light presentation class.

If full feature parity adds load, attribute GUI sync, render-node cost, widget scene cost,
source/provider cost and texture upload before blaming the architecture.

Do not reduce authored visualizer cadence or widget fidelity to meet a benchmark.

## 14. Long soak

After final Quick architecture:

- ordinary/light telemetry;
- optional diagnostic comparison;
- memory/private commit;
- handles;
- threads;
- GL/render resources;
- topology wake;
- clean shutdown.

## 15. Git checkpoint discipline

Before local push:

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

Never use destructive Git to make the tree convenient.

Low-risk work may continue after green push.

High-risk/audit-required work stops after push for independent review.

## 16. Final cutover checklist

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

## 17. Documentation/tool closure

Update:

- `Docs/TestSuite.md`;
- `Docs/Harness_Index.md`;
- `Index.md`;
- build documentation;
- `Docs/Defaults_Guide.md`;
- `Future_Cleanup.md`.

Delete migration-only tools that no longer guard a live risk.

Keep cheap production-shaped regression harnesses.
