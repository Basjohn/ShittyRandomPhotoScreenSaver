# Documentation Maintenance

Last updated: 2026-08-19

Rules for keeping SRPSS docs useful to coding agents instead of preserving obsolete architecture by
accident.

## 1. Stable Paths

Edit canonical files in place. Do not create “v2/new/proposed” duplicates or rename/move existing
paths without explicit user instruction.

A focused guardrail may be added only when it owns a distinct durable policy rather than duplicating
an active plan. Current focused guardrails include visualizer presentation and runtime efficiency /
change safety.

## 2. Roles / Authority

| Document | Owns |
|---|---|
| `Current_Plan.md` | active unfinished execution order |
| `Spec.md` | durable stable architecture/product behaviour |
| `Docs/Guardrails.md` + focused guardrails | durable prohibitions/stop rules |
| `Index.md`, `Docs/Contracts.md` | current owner/navigation map |
| focused architecture docs | current subsystem design |
| active phase report | accepted current evidence + limits |
| old phase reports | frozen checkpoint evidence only |
| specialized audit references | optional detail only; never active task order |
| `Future_Cleanup.md` | deferred cleanup/debt |
| historical bug records | incident evidence/negative controls only |

Exact current `main` is always implementation truth when an old evidence document names a class/path
that no longer has the same role.

## 3. Architecture Epoch Rule

A major architecture migration must reconcile the entire small core-doc set in the same sweep:

- `Spec.md`
- `Docs/Guardrails.md`
- relevant focused guardrail
- `Docs/Compositor_Architecture.md`
- `Docs/Contracts.md`
- `Index.md`
- relevant visualizer/transition checklist/reference
- any still-referenced specialized audit documents

Do not leave “future target” prose in one document after that target has landed.

## 4. Evidence Documents Are Not Owner Maps

Phase reports and Historical_Bugs deliberately preserve old implementation names because those names
matter to the evidence.

Therefore:

- do not rewrite old evidence merely to use current class names;
- do not cite an old owner table as current architecture;
- do not infer a compatibility requirement from an old `QOpenGLWidget`, overlay, timer or context
  name;
- current owner questions route to `Index.md`, `Docs/Contracts.md` and exact source.

`Docs/phase_reports/README.md` states this rule for that folder.

## 5. Volatile Measurements / Named Baselines

Do not duplicate current FPS/gap counts/raw log paths across stable docs. The active owning phase
report keeps detailed evidence. Roadmap/stable docs keep only the durable conclusion and route to
that report.

After a major architecture/performance improvement, name one installed baseline in the active plan
and owning phase report. The baseline exists to:
- preserve rollback/fidelity evidence;
- catch future widget/settings/minor changes that silently spend recovered headroom;
- provide a comparison point for later architectural work.

It is not a permanent ceiling and should not be copied into every stable document.

The 2026-08-19 / 4.7.2 baseline is the current example.

## 6. Drift Searches

After presentation/visualizer architecture changes, search at minimum:

```powershell
rg -n "QOpenGLWidget|QRhiWidget|SpotifyBarsGLOverlay|AdaptiveTimerStrategy|paintGL|grabFramebuffer|Phase 8|one.surface|pending.*paint" \
  Index.md Spec.md Current_Plan.md Docs
```

Interpret results by document role. Historical records may legitimately match. Core/stable docs may
not contradict current architecture.

Also verify current owner paths:

```powershell
rg -n "CompositorVisualizerLayer|ExternalOpenGLRhiWidget|GLCompositorWidget" Index.md Spec.md Docs
```

After runtime-efficiency/settings/widget changes also search for accidental duplicate technical
work or old broad-replay guidance, for example:

```powershell
rg -n "reapply|replay|refresh|invalidate|rebuild|QTimer|schedule_recurring|submit_.*task" \
  Docs/Guardrails.md Docs/Guardrails Docs/10_WIDGET_GUIDELINES.md Docs/Defaults_Guide.md Current_Plan.md
```

Interpret those results by owner; the terms are not forbidden, duplicate or ownerless use is.

## 7. Avoid Mechanism Fossils

A failed mechanism remains documented as a negative control, but phrase the **scope of the
rejection**. Do not convert “this use of AdaptiveTimer on a separate transition-scoped visualizer
surface failed” into “the display compositor can never use its adaptive timer for physical
presentation.”

Likewise, do not generalize:

- one bad QPainter path into “QPainter never allowed”;
- one bad latest-state coalescer into “presentation must equal publication”;
- one failed child surface into “never use QRhi”;
- one lifecycle incident into hide/reuse compatibility requirements;
- one run dominated by a particular visualizer mode into “that mode is the CPU problem”;
- one successful worker migration into “all work should move off GUI.”

Keep the proven lesson at the correct owner level.

## 8. Closure

Before marking a large task done:

- core docs agree on current owner/type;
- no active doc says a landed architecture is still future/deferred;
- no current navigation doc routes to retired presentation owners;
- old reports/history are clearly evidence-scoped;
- Current_Plan retains only unfinished work;
- Future_Cleanup remains deferred only;
- a newly named installed baseline is recorded once in the owning evidence/plan, not duplicated
  across stable docs;
- future-change guardrails capture the durable lesson when a run reveals a new general anti-pattern.

## 9. Retiring Duplicate Planning Documents

When a live-plan/audit document has been fully absorbed into `Current_Plan.md`, `Spec.md`, focused
architecture/guardrail docs and phase evidence, deletion is preferable to maintaining a second
"current" copy. Preserve dated evidence reports; retire duplicate live-planning owner maps.

The 2026-08-18 QRhi/single-surface reconciliation deliberately retires roadmap `00`-`06` and the
roadmap manifest. Their useful current rules were moved into canonical owners; their continued
existence was causing architecture time-travel.
