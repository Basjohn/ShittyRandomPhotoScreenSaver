# SRPSS Performance Evidence — Rules and Usage

Last updated: 2026-08-23

This folder is an append-only engineering evidence history.

Its purpose is to stop installed performance evidence from disappearing when `Current_Plan.md`, phase
reports, or agent theories are rewritten.

## Rules

1. **Every installed acceptance run that changes an engineering conclusion gets a new immutable record.**
2. Do not rewrite an older record to match a newer theory.
3. A later record may explicitly supersede or falsify an older conclusion.
4. Record the exact `[SOURCE_HEAD]` line when available.
5. If the raw log predates `[SOURCE_HEAD]`, say **SHA not embedded**. A contemporaneous reviewed source
   anchor may be listed separately, with that distinction preserved.
6. Preserve operator-visible behavior. Installed perception is evidence, not anecdotal decoration.
7. Preserve important numeric evidence as relevant:
   - logical cadence / skipped deadlines / failures;
   - completed presentation FPS;
   - request acceptance;
   - frame-gap and dt tails;
   - delivery-stage attribution;
   - widget/media costs;
   - CPU/GPU context.
8. Record what hypothesis the run supported, weakened, or falsified.
9. Do not commit full raw log packs by default. Record filename and SHA-256 in `Raw_Log_Manifest.md` so
   a retained external/conversation copy can be verified.
10. `Current_Plan.md` may reference these records. It must not rewrite history in their place.

## Evidence confidence labels

- **PRIMARY RAW** — derived directly from retained raw logs.
- **PRIMARY OPERATOR** — direct installed perceptual report tied to that run.
- **CONTEMPORANEOUS REVIEW** — findings written from the raw run at the time.
- **HISTORICAL SECONDARY** — prior project documentation; useful but raw run not retained here.
- **INFERENCE** — clearly labelled interpretation from the above evidence.

## Architecture-epoch rule

Evidence records may correctly discuss QOpenGLWidget, QRhiWidget, GLCompositor, GUI presentation
callbacks, old widget paint cost or old Phase/P-number sequencing because those were real at collection
time.

Those references are **evidence**, not destination authority. Current accepted presentation is Qt Quick;
old presenter owners are CURRENT-LEGACY until H/I deletion.

Do not edit an old measurement to make it look as though Quick generated it.

## Read order for current work

There is no longer a generic “current P2 work” mode.

Use:

1. `Current_Plan.md` to identify the active owner/question;
2. newest acceptance record directly relevant to that owner/question;
3. any hypothesis record that distinguishes the current alternatives;
4. `Raw_Log_Manifest.md` when raw-pack provenance is needed;
5. older P2/P5/other records only when comparing a regression timeline or mechanism.

`P2_Performance_Ledger.md` remains useful historical visualizer/presentation evidence; it is not active
sequencing.

Do not read every historical record on every task.
