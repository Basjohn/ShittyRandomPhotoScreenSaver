# SRPSS Performance Evidence — Rules and Usage

This folder is an append-only engineering evidence history.

Its purpose is to stop installed performance evidence from disappearing when `Current_Plan.md`,
phase reports, or agent theories are rewritten.

## Rules

1. **Every installed acceptance run that changes an engineering conclusion gets a new immutable record.**
2. Do not rewrite an older record to match a newer theory.
3. A later record may explicitly supersede or falsify an older conclusion.
4. Record the exact `[SOURCE_HEAD]` line when available.
5. If the raw log predates `[SOURCE_HEAD]`, say **SHA not embedded**. A contemporaneous reviewed source
   anchor may be listed separately, with that distinction preserved.
6. Preserve operator-visible behavior. Installed perception is evidence, not anecdotal decoration.
7. Preserve the important numeric evidence:
   - logical cadence / skipped deadlines / failures;
   - completed presentation FPS;
   - request acceptance;
   - frame-gap and dt tails;
   - delivery-stage attribution;
   - widget/media costs when relevant;
   - CPU/GPU context when relevant.
8. Record what hypothesis the run supported, weakened, or falsified.
9. Do not commit full raw log packs by default. Record their filename and SHA-256 in
   `Raw_Log_Manifest.md` so a retained external/conversation copy can be verified.
10. `Current_Plan.md` may reference these records. It must not rewrite history in their place.

## Evidence confidence labels

- **PRIMARY RAW** — derived directly from the retained raw logs.
- **PRIMARY OPERATOR** — direct installed perceptual report tied to that run.
- **CONTEMPORANEOUS REVIEW** — a findings document written from the raw run at the time.
- **HISTORICAL SECONDARY** — prior project documentation; useful but raw run not retained here.
- **INFERENCE** — clearly labelled interpretation from the above evidence.

## Read order

For current P2 work:

1. `P2_Performance_Ledger.md`
2. newest `Acceptance-*` record
3. any hypothesis record directly relevant to the subsystem being changed
4. `Raw_Log_Manifest.md` if raw-pack provenance is needed
5. older acceptance records only when comparing a regression timeline

Do not read every historical record on every task.
