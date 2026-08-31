# Remaining J — Final Installed / Physical Acceptance Decomposition

Status: **future acceptance phase; the H production cutover is already complete. Execute final J closure after the remaining post-cutover H gates re-close and I caller-proven residue cleanup is GREEN. Vision-capable agents may prepare/front-load the mandatory image-oracle parity tranche, but may not use J to hide an H correctness failure.**  
Work admission: `Current_Plan.md`  
Validation shape: `Docs/QtQuick_Migration/06_Build_Tooling_Validation.md`  
Test ownership/retirement: `Docs/TestSuite.md`

J is the final acceptance/sign-off phase for the production architecture. It is not another presenter migration and it is
not permission to redesign a GREEN destination because a physical gate is inconvenient.

Exact current source, `Current_Plan.md`, `Spec.md`, `Docs/Contracts.md`, and the focused subsystem contracts remain
architectural authority. This document owns the **acceptance matrix and evidence discipline** for final closure.

## 1. Required result

J must establish that the production build which will actually be shipped behaves correctly on real Windows/Qt/graphics
hardware after the Quick production cutover.

J closes only when the relevant deterministic, compiled/frozen, installed, physical-display, lifecycle, visual-fidelity and
performance gates have been run against an identified source/build checkpoint and their remaining debt is explicit.

A deterministic pass is not physical proof. A physical pass does not excuse a deterministic ownership defect.

If J finds a failure, reopen the **smallest demonstrated owning defect**, fix it, rerun the affected deterministic and
physical cells, and continue. Do not reopen migration architecture wholesale without evidence that the accepted owner model
itself is wrong.

## 2. Admission / sequencing

J begins after:

```text
H
-> normal production orchestration owns only the accepted Quick runtime chain
-> old physical-host production ownership is removed

I
-> post-cutover caller-dead adapters/aliases/tests/tools/comments/spikes are retired from exact source
-> no unresolved residue disguises a second runtime owner

then J
-> build + installed + physical acceptance + closure reconciliation
```

Do not use J as a parking lot for known deterministic H/I defects.

### Early mandatory visual-parity tranche

When the acting model/agent has reliable image inspection, front-load the family-by-family paired oracle under `images/migration/Ideal (PreMigration)/` versus `images/migration/Current (PostMigration)/`. For visible details the matching Ideal image is J's highest parity authority; the Current image is the explicit regression baseline. This pass is mandatory for Abandonment Issues, Achievement Pulse, Gmail, Media, Reddit and Weather. Clock is intentionally absent because its current Quick presentation is acceptable.

A model with weak/unreliable vision may **briefly defer** the eyes-on implementation to a vision-capable pass, but may not replace the oracle with prose, tests or aesthetic invention and may not close J without it. The same early parity tranche includes restoring the **missing CUSTOM/Edit alignment/snap guide lines** (centre/peer/edge/safe-gutter relationships) through the existing Python snap/layout authority.

**Current explicit Media exception:** preserve the post-migration transport/control bar; it is the only current Media visual treatment presently judged superior to the old implementation. Do not infer other exceptions from the Current Media screenshot. **Cross-family header parity is also mandatory:** logo + family/provider name must align and scale with the card/widget as one authored relationship; the current effectively fixed-size headers are a J regression.

### Why I has no standing prewritten decomposition

Phase I is intentionally source-driven residue cleanup. Its exact deletion list must be derived from the exact source after H re-closes; it is not safely predeclared here even though the production cutover has already changed
the production caller graph. At I entry:

1. inspect exact post-H source/callers;
2. classify surviving compatibility/adapters/tests/tools against the destination contracts;
3. delete caller-dead residue in bounded batches with focused tests;
4. update `Docs/TestSuite.md` / `Future_Cleanup.md` as ownership retires.

If post-H I unexpectedly becomes a cross-owner architectural task rather than residue, stop and create a bounded
source-specific decomposition **then**. Do not pre-author speculative filenames/owners now.

## 3. Evidence identity

Every J acceptance run must identify enough provenance to prevent evidence from floating between builds:

- source commit / exact worktree state;
- build target/type (source, standalone/onefile/MC as applicable);
- application version/build identity where available;
- Windows version/build;
- GPU + driver;
- display topology, resolution, refresh and DPR/scaling;
- relevant diagnostic mode/log family;
- whether the run is deterministic, synthetic/runtime-shaped, installed, or physical/operator eyes-on.

Do not carry a pass forward across a code/build change that touches the tested owner without classifying whether the evidence
still applies.


## 3A. Lesson from the first post-cutover production-source run

The first real source-mode Quick run is preserved at
`logs/evidence_chest/08_30_RuntimeSwap_03_37/` with source head
`427eafed8cff8b932bc64efee964764ce3f02260`.

It demonstrated an important acceptance rule: **cross-layer milestones are not
substitutes for the visible/product consequence they are meant to support.** In
particular:

```text
logical Visualizer cadence is healthy != retained pixels visibly evolve
render/draw calls are high             != successive snapshots were synchronized
context-menu model accepted/opened     != the QML menu was visible/usable
fade/reveal milestone fired            != the operator saw a clean gentle fade
```

The deterministic defects exposed by that run are routed back to H before I/J;
J must not inherit them as accepted debt. The remaining observations become
named J cells: black flashes on startup/focus/transition edges, actual widget
fade quality, ordinary-widget content sizing, refresh-spiral consistency and
transition visual stability.

## 4. Deterministic preflight before expensive physical work

Before operator-heavy acceptance, run the bounded relevant suite and reconcile obvious stale tests first.

At minimum prove current destination ownership for:

- one Quick production runtime/window per selected display;
- one intended widget/provider/service owner chain per display/generation;
- generation fencing and legal teardown/recreation;
- image + transition routing through destination APIs;
- ordinary widget family admission/actions/activation;
- Visualizer logical cadence and immutable/latest-state render admission;
- G CUSTOM/input/auxiliary/context ownership;
- independent visualizer uniform scale vs viewport extent;
- Bubble BTF/replay/cadence and viewport-domain regressions;
- no legacy physical presenter or fallback being silently re-admitted.

`Docs/TestSuite.md` owns the exact current inventory. Do not recreate a second permanent test manifest here.

The maintained H destination profile may intentionally exclude test cells whose assertion depends on the operator's real
physical `QScreen` set. Retained source-mode physical identity/topology smoke cells are useful **J evidence**, not missing H
deterministic coverage. Run them in isolated subprocesses when appropriate so one Qt/scene-graph teardown cannot contaminate an
unrelated acceptance result.

## 5. Compiled / frozen / packaging gate

Use the current supported build tooling and `06_Build_Tooling_Validation.md`; do not invent a new packaging architecture in J.

Validate the actual supported deliverable forms that remain product-relevant, including normal screensaver/runtime and MC
where applicable.

Required packaging proof includes as applicable:

- QML source/resource availability outside repository-root CWD assumptions;
- required Qt Quick/QML plugins;
- selected graphics backend configuration before first Quick scene graph;
- custom render-node imports/resources;
- themes/shaders/images/icons/other declared data inputs;
- helper/secure-desktop entrypoints and their required payloads;
- clean startup and clean exit from the built artifact;
- no fallback to a retired presenter when a QML/plugin/resource error occurs.

Start with the smallest compiled smoke that can expose packaging failure, then run the broader installed matrix. A packaging
failure is a packaging defect, not permission to restore the old presenter.

## 6. Physical display / topology matrix

Exercise the real production runtime across the hardware combinations available to the operator.

At minimum cover:

```text
1 display
2 displays
N displays when hardware is available/relevant

60 Hz
high refresh
mixed refresh

uniform DPR/scaling
mixed DPR/scaling when available

display add/remove/reorder or equivalent topology replacement
monitor off -> wake
late-return / unavailable configured display paths
runtime generation replacement
```

For each relevant cell verify:

- exactly one intended window/runtime per selected physical display;
- correct QScreen/display identity and geometry;
- no stale old-generation scene/action callback;
- no duplicate provider/widget/visualizer owner;
- no black/stale/previous-generation reveal in place of explicit readiness;
- focus/click A -> B -> A does not blank either retained scene or replay a
  black base frame;
- correct recovery/recreation without moving live render resources illegally between windows.

If hardware cannot exercise a matrix cell, record the cell as unrun rather than converting synthetic coverage into a
physical pass. A source-mode physical smoke timing miss before the production Quick authority flip is not automatically a
migration blocker; rerun/classify the corresponding cell against the post-H/I production-authoritative chain before changing
architecture.

## 7. Visual parity / presentation matrix

Eyes-on acceptance must inspect the production Quick pixels, not a compatibility presenter or isolated mock.

### Background / transitions

Check representative and edge-case image content plus every supported transition family as currently admitted:

- ordinary progression;
- interruption/cycle/replacement, including a second manual Next while the
  first transition is active;
- fade/opacity ownership;
- geometry/crop/scaling;
- no flash/black/stale-frame handoff;
- no presentation cadence coupling back into authored logical work.

Use `Docs/Transition_Change_Checklist.md` for current transition-specific fidelity criteria.

### Ordinary widgets

Check enabled substantive families and representative styling extremes:

- geometry/stacking;
- text/image fidelity;
- borders/corners;
- opacity;
- shadows including direction/spread/blur;
- loading/refresh indicators (including spiral placement/visibility) are
  consistent with the authored family surface rather than appearing on only an
  arbitrary subset;
- action hit regions and one-shot semantic actions;
- capability/ordinary ON/OFF behavior;
- provider/model dormancy where relevant;
- CUSTOM move/resize/duplicate/X/Save/Cancel/layout slots.

When sizing is under investigation, capture one bounded startup/recreation
layout snapshot rather than polling: widget/instance id, effective display
route, preferred content size, final outer rect, committed CUSTOM override if
any, DPR and clamp result/reason. The diagnostic must not become per-frame
geometry feedback.

Do not require every possible provider/account to be live if a production-shaped deterministic/synthetic model proves the
presentation contract; do require real provider/lifecycle checks where network/account ownership itself is the acceptance
subject.

### Visualizer — all modes

Physically inspect all five current modes under representative music/source conditions:

```text
Spectrum
Oscilloscope
Sine
Bubble
DevCurve
```

Check authored feel, geometry, shell/clip, shadows and transition coexistence.
Require visible evolution of successive retained states; logical ~90 Hz cadence
or render-call counts alone do not prove this. Bubble Temporal Fidelity remains
binding.

### Deferred G4 viewport gate

This is where the deferred physical G4 acceptance debt closes:

```text
Spectrum      canonical / wide / tall
Oscilloscope  canonical / wide / tall
Sine          canonical / wide / tall
Bubble        canonical / wide / tall / representative shrink
DevCurve      canonical / wide / tall
```

At constant uniform scale verify viewport extent changes available world/layout rather than anisotropically stretching
finished pixels. For Bubble verify especially:

- circles remain circles;
- apparent physical bubble size remains coherent;
- speed/drift/collision personality is not aspect-retuned;
- authored big/small counts are not silently area-scaled;
- wider/taller domains are allowed to be visually less dense;
- trails remain attached and correctly projected;
- specular/highlight placement remains coherent;
- shrink does not leave an obviously dead/invisible population;
- canonical appearance/feel remains the accepted BTF baseline.

A physical failure here may reopen the smallest G4 defect even though deterministic G4 was previously GREEN.

## 8. Input / MC / screensaver product surfaces

Exercise real product entrypoints rather than only injected Qt events.

### MC

Verify at minimum:

- intended topmost/window-role behavior;
- no ordinary taskbar/Alt-Tab presence where the product contract forbids it;
- A -> B -> A focus switching on multi-display;
- Ctrl/interaction state does not stick;
- single/double-click exclusivity;
- context menu open/dismiss/action paths, including operator-visible retained
  QML presence rather than model-only admission;
- cursor halo/inactivity behavior;
- Settings/CUSTOM transitions;
- Clock/media/widget semantic interactions;
- physical media/hardware-key behavior where applicable.

Synthetic `SendInput`/Qt-event coverage is supportive, not a substitute where historical evidence showed physical ingress can
differ.

### Screensaver / secure-desktop path

Exercise the supported screensaver/helper/secure-desktop behavior that remains part of the product contract, including clean
entry/exit and correct URL/action restrictions. Do not broaden privilege/helper behavior merely to make a test convenient.

## 9. Lifecycle / recreation matrix

Run repeated lifecycle sequences, not only cold start:

- start -> reveal -> close;
- repeated restart;
- Settings open/close and any runtime hide/recreate path;
- CUSTOM enter/Save/Cancel/exit;
- transition active during permitted lifecycle operations;
- Visualizer active during permitted lifecycle operations;
- capability deactivate/reactivate;
- provider/service switch where relevant;
- monitor off/wake;
- topology replacement;
- generation replacement;
- process exit after ordinary and stressed runs.

Require:

- admission closes before retirement;
- logical/runtime workers retire or remain process-scoped only by explicit contract;
- scene/render resources retire on legal owner/thread/context;
- stale callbacks cannot affect the replacement generation;
- no destruction-barrier hang hidden by increasing timeouts;
- process actually terminates;
- shutdown timing is attributed by phase so unrelated post-teardown work (for
  example explicit cache/pycache cleanup) is not misdiagnosed as a Quick
  destruction-barrier hang.

## 10. Performance / physical cadence

Do not infer panel delivery solely from internal render/frame callbacks.

Use the established production evidence approach where relevant, including PresentMon or the current equivalent, and report
per display/context:

- p50/p90/p95/p99/max or the currently accepted tail metrics;
- severe-gap counts;
- physical cadence under light and representative external-heavy load;
- CPU/GPU usage/context;
- visualizer logical cadence/source age separately from physical presentation cadence;
- relevant render/sync/provider timings when attribution is needed.

Compare against the preserved accepted reference/evidence; do not manufacture a new worker-heavy baseline merely because J
has arrived.

If parity features add cost, attribute the cost to GUI sync, render node, widget scene, texture upload, source/provider or
other measured owner before changing architecture. Do not reduce authored Visualizer cadence or visible fidelity simply to
improve a benchmark.

## 11. Long soak / resource stability

After short physical cells are GREEN, run a representative long soak with ordinary/light telemetry and diagnostic detail only
where needed.

Track as applicable:

- private memory/commit;
- handles;
- threads/processes;
- provider workers;
- GL/Quick render resource accounting;
- texture/image retention;
- repeated topology/off-wake;
- repeated generation replacement;
- clean shutdown at the end of the soak.

A stable average with steadily growing resource counts is not GREEN.

## 12. Failure classification

For every failed acceptance cell, classify before editing:

```text
deterministic ownership/logic defect
packaging/frozen-resource defect
physical presentation/focus/topology defect
performance/resource-tail defect
subjective visual parity defect with reproducible condition
unrelated pre-existing/product issue
```

Then fix the owning seam. Do not:

- add sleeps/rescue timers/repaint loops as generic acceptance repairs;
- restore QWidget/QRhi/CPU fallback presentation;
- weaken BTF/goldens/tests to match a bad physical result;
- remove shadows/effects/fidelity to hide timing problems;
- convert an unrun physical cell into PASS;
- carry a demonstrated deterministic defect as “J debt”.

## 13. Closure reconciliation

Before declaring the migration/product acceptance closed:

1. reconcile `Docs/TestSuite.md` against the exact final tree;
2. remove or rehome tests/tools/harnesses whose migration-only owners are now gone;
3. reconcile `Future_Cleanup.md` and remove debt that was actually completed;
4. reconcile `Current_Plan.md`, `Index.md`, migration README/status and any living architecture docs so they describe the
   production architecture rather than an active migration;
5. move truly historical evidence/phase narrative to historical locations rather than rewriting it as current authority;
6. preserve permanent architecture/guardrail/fidelity contracts that remain useful after migration;
7. record any genuinely deferred physical cell or product issue explicitly rather than implying universal acceptance.

Do not delete useful regression tests merely because the migration phase number has ended.

## 14. J GREEN definition

J is GREEN when:

- current deterministic destination suites are GREEN;
- supported build/frozen packaging is proven;
- the relevant installed/physical display, focus, lifecycle and visual-parity matrices are accepted;
- the deferred G4 all-five-mode viewport gate is physically accepted;
- performance/tail/resource behavior is acceptable without reducing authored fidelity;
- clean shutdown/restart/recreation are proven;
- test/debt/document routing is reconciled against the final production tree;
- every unrun or deferred acceptance item is explicit rather than silently converted to PASS.

At J GREEN, the Qt Quick work stops being an active migration and becomes ordinary production architecture governed by the
permanent contracts/guardrails.
