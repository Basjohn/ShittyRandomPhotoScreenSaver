# Post-Material-Rollback Documentation Reconciliation — 2026-09-03

Status: **docs-only architecture audit complete for the current slice**

## Scope

Reconcile live/durable documentation after rejection/removal of Qt Quick runtime card backdrop materials, completion of colour-only Widget Themes, COM/native-fault repairs, current Visualizer mode-modularization plans, and the latest operator performance logs.

This audit does not authorize production refactors by itself. `Current_Plan.md` remains sequence authority.

## Findings / corrections

### Runtime card materials

- Current authority consistently defines runtime cards as ordinary retained Qt Quick RGBA surface/border/shadow presentation.
- Widget Themes are colour-only schema-v3 bundles; Settings native Glass/Acrylic remains a separate QWidget/HWND concern.
- The ordinary-widget authoring guide still contained two live-looking remnants (`Widget Theme/card-material` wording and `optional shared display card-material participation`). Those were removed.
- The old J Parity+ reference contains historical section-10 material plans in the repository history. It is intentionally treated as historical evidence and explicitly superseded by `Docs/QtQuick_Migration/J_Runtime_Card_Material_Supersession_2026-09-03.md`; the binding anti-resurrection record is `Docs/Historical_Bugs/Runtime_Card_Backdrop_Materials_Rejected_2026-09-02.md`.
- The rejected method ledger remains `Docs/QtQuick_Migration/Rejected_Card_Material_Experiments_2026-09-02.md` and is not active architecture.

### Widget Themes / light themes

- `Settings_Theme_Architecture.md` no longer calls Widget Themes future work; they are landed.
- The curated theme record is 58 Settings + 58 colour-only Widget mirrors.
- `Tungsten Brass` is corrected to the user-facing `Tungsten Blues` name while stable Settings filename/identity remains intentionally unchanged.
- Light Widget counterparts require their own wallpaper-aware contrast rule. Settings-window contrast over a native backdrop and runtime-card contrast over arbitrary wallpaper are different composition problems.
- Clock/card-text guidance now distinguishes dark-theme near-neutral text from light-theme dark text rather than claiming every generated `card.text` is near-white.

### Visualizer performance / Spectrum

- R-76 remains valid and should not be reverted merely because extreme-tall Spectrum visibly flickered again.
- Latest logs show a global delivery-hitch class capable of reproducing large visible jumps despite correct per-mode smoothing.
- Bubble and tall Spectrum are co-primary physical oracles.
- A focused P0 plan now owns attribution/order: `Docs/QtQuick_Migration/Visualizer_Hitch_Attribution_And_Optimization_Plan_2026-09-03.md`.
- Mode modularization order is clarified against the canonical V0-V8 decomposition: baseline attribution first; V0-V4 behavior-floor/authority/dormancy before deep active-path optimization; V5-V8 Settings extraction/rehosting/dependency/future-mode proof after dormancy/hitch stability.

### Lifecycle / native diagnostics

- Latest supplied run contains no native fault dump and no Qt/QML warnings/errors/criticals.
- GSMTC retained observation stays on the explicit affinity lane through recreation in the latest evidence.
- The COM/native-fault fixes remain permanent architecture and are not part of Visualizer optimization.


### Phase/status and startup-document drift

- `Spec.md` and the top of `Docs/TestSuite.md` still described Phase I as active even though the project is now post-cutover. They are refreshed so `Current_Plan.md` remains the live sequencing authority and the old section-10 test inventory is explicitly a migration reconciliation snapshot, not a second current tree authority.
- `Docs/Contracts.md` still carried the pre-fix statement that desktop->wallpaper startup crossfade and coordinated reveal had failed physical validation. That contradicted the later accepted startup-fade correction and was updated to the healthy retained startup contract.
- The Visualizer modularization document's canonical phase numbering places dormancy proof at **V4**, not V3. Current planning/checklists now consistently use V0-V4 before deep active-path optimization and V5-V8 for Settings rehosting/dependency/future-mode proof.

## Remaining deliberate historical wording

Historical phase/bug/evidence documents may describe superseded mechanisms. They remain valid as history only when current authority/supersession records explicitly fence them. Do not rewrite historical evidence merely to make it sound current; add a current supersession/anti-resurrection record when a historical section would otherwise be dangerous to execute.

## Current sequencing conclusion

The next project-quality blocker is recurring Visualizer delivery hitching, not a Spectrum-only smoothing retune and not more cosmetic widget polish. Complete attribution + V0-V4 dormancy + active-owner optimization first; then finish V5-V8 Settings rehosting/dependency/future-mode proof and resume remaining J visual parity/cleanup with a healthier cadence baseline.
