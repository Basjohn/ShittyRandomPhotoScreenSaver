# Documentation Maintenance

Last updated: 2026-08-19

Rules for keeping SRPSS docs useful to coding agents instead of preserving obsolete architecture by
accident.

## 1. Stable paths

Edit canonical files in place.

Do not create `v2/new/proposed` duplicates or rename/move canonical paths without explicit user
instruction.

Focused guardrails may exist only when they own distinct durable policy. Current examples:

- visualizer presentation;
- runtime efficiency/change safety;
- Bubble Temporal Fidelity (**BTF**).

## 2. Roles / authority

| Document | Owns |
|---|---|
| `Current_Plan.md` | active unfinished execution order |
| `Spec.md` | durable stable architecture/product behaviour |
| `Docs/Guardrails.md` + focused guardrails | durable prohibitions/stop rules |
| `Index.md`, `Docs/Contracts.md` | current owner/navigation map |
| focused architecture/reference docs | current subsystem design |
| current installed evidence checkpoint | current volatile measurements/evidence |
| old phase reports | frozen checkpoint evidence |
| specialized audit references | optional detail only; never task order |
| `Future_Cleanup.md` | deferred cleanup |
| Historical_Bugs | incident evidence / negative controls |

Exact current `main` is implementation truth.

## 3. Architecture epoch reconciliation

After a major owner migration reconcile this small current-authority set in the same sweep:

- `Current_Plan.md`
- `Spec.md`
- `Index.md`
- `Docs/Contracts.md`
- `Docs/Guardrails.md`
- relevant focused guardrails
- `Docs/Compositor_Architecture.md`
- visualizer/reference/checklist where relevant
- `Docs/TestSuite.md`
- `Docs/Harness_Index.md`
- any “stable architecture/reference” audit that directly names the changed owner
- `Future_Cleanup.md` if a former future target landed

Do not leave “future target” prose after the target has landed.

## 4. Reorientation documents

A reorientation file is handoff/orientation doctrine only.

It is not a second `Current_Plan.md`.

Prefer keeping reorientation files outside the repository or in an explicit handoff package unless
the user asks to store one in-repo.

Do not add root clutter merely to make an agent read it.

## 5. Evidence is not an owner map

Phase reports and Historical_Bugs preserve old implementation names intentionally.

Do not rewrite them merely to use current class names.

Do not infer current ownership from old:

- QOpenGLWidget;
- separate overlay;
- GUI timer;
- old scheduler;
- old context owner.

Current owner questions route to `Index.md`, `Docs/Contracts.md` and source.

## 6. Volatile measurements

Do not duplicate current FPS/gap/raw-log counts across stable docs.

Keep detailed volatile numbers in:

- `Current_Plan.md` while actively relevant;
- current installed evidence checkpoint.

Stable docs keep durable conclusions and routes.

## 7. Mandatory drift search after visualizer/presentation changes

Search current docs for architecture fossils:

```powershell
rg -n "GUI-QTimer|gui timer|schedule_recurring|_bars_timer|VisualizerLogicalRuntime|Event\.wait|dedicated logical runtime|future logical runtime|presentation_ready|reactive_source_ready|fresh.frame|source generation|source activation|SpotifyBarsGLOverlay|QOpenGLWidget|QRhiWidget|pending.*paint|paint acknowledgement|AdaptiveTimerStrategy" `
  Index.md Spec.md Current_Plan.md Future_Cleanup.md Docs
```

Interpret by document role.

Historical evidence may legitimately match.

Current-authority docs may not contradict exact `main`.

### Generation identity drift

Also search identity code/docs when generation ownership changes:

```powershell
rg -n "runtime_generation|generation.*or -1|activation.*or -1|int\(.*or -1" widgets rendering engine tests Docs
```

Do not global-replace blindly. The purpose is to catch identity fields where valid zero can be lost.

## 8. Avoid mechanism fossils

Keep the proven lesson at the correct owner level.

Examples:

- failed adaptive timer on a separate visualizer surface does **not** ban adaptive physical display
  presentation;
- failed GUI-QTimer logical cadence does **not** mean all Qt timers are forbidden;
- successful dedicated visualizer worker does **not** mean all work belongs on workers;
- failed non-zero Spectrum test means “non-zero data is not visible-output proof,” not “all test
  doubles are useless”;
- Bubble exposing a timing defect does not make Bubble the cause.

## 9. Closure

Before marking a large architecture task done:

- current core docs agree on current owner/type;
- no current doc says landed architecture is future/deferred;
- no current navigation routes to a retired owner as current evidence;
- active plan contains only unfinished work;
- Future_Cleanup contains only deferred work;
- focused guardrails capture durable lessons;
- historical reports remain evidence-scoped;
- current test/harness guides describe the current runtime owner.

## 10. Retiring duplicate planning docs

When a live-plan/audit document has been fully absorbed into current canonical owners, deletion is
preferable to maintaining a second current task list.

Do not delete evidence reports.

If a specialized audit is retained as “stable architecture/reference,” it must be reconciled when
the owner it describes changes.
