# Visualizer Edit Layout geometry and Sphere materials

Last updated: 2026-09-05

The operator accepts recovered colours/glows and confirms Sphere now animates. This is the next
explicitly authorized slice; `FWPlan.md` owns sequencing. Preserve one logical clock, immutable
publication, independent CUSTOM extent/whole-scale intents, source fences and context retirement.
Latest operator logs archived before testing: `logs/evidence_chest/fw_geo_material_2026_09_05`.

## E1 — all six modes, source-to-visible geometry

- [x] Archive the latest `--geo` run before tests rotate logs.
- [x] Trace pointer edge -> working CUSTOM rect/extent/scale -> scene controller -> retained presenter
  -> actual renderer content, comparing drag preview, release, save, cancel and recreation.
- [x] Find the first seam that moves the opposite edge, double-applies a scale/screen-fit, reuses stale
  content geometry or changes the viewport while pretending to perform uniform scaling.
- [x] Correct the owning seam once for all six modes; no mode-specific hidden caps, extent compression,
  delayed preview, extra clock, polling or cosmetic gain fix for an ownership defect.
- [x] Bubble: reduce nominal full outline width by one logical pixel; retain minimal pixel coverage for
  tiny heads. Use the same visible-area size/stroke contract during live adjustment and after save.
- [x] Falsifying production-chain tests for left/right/top/bottom, whole-scale and move; opposite-edge
  anchoring, stable position, round geometry, extreme saved extents at small scale, and cancel/save.
- [x] Compare renderer-specific geometry in Spectrum/Osc/Sine/Bubble/DevCurve/Sphere. Audit amplitude,
  stroke/glow and screen-fit independently; do not hide large/extreme errors with arbitrary damping.
- [ ] Awaiting physical validation — inspect actual Quick preview captures and document remaining physical validation.

### Reopened live-edit failure and extreme main outlines

- [x] Geometry-only Save now promotes the live retained rectangle/extent and keeps the visualizer running in the same
  generation; the operator reports this UX path is working extremely well. No teardown is used as a geometry crutch.
- [x] Cross-display Visualizer drag/Save is operator-accepted in the current authority: the retained scene plus runtime/frame
  pacer/lifecycle ownership transfers live and Save does not rebuild or tear down that successful transfer. Numbered layout-slot
  **load** remains the explicit fenced reconstruction/hot-swap boundary. Preserve this distinction as a hard UX contract.
- [~] One extreme transfer gesture still produced an incoherent 439x960 rectangle against a 9520.87x25548.02 logical
  extent. Keep the coherence rejection; do not hide it by relaxing uniform-scale math. Revisit viewport scaling/reactivity
  in the next geometry session unless the transfer repair removes the reproduction.
- [x] Historical extreme-outline thinning was corrected again in Checkpoint 1: the large/extreme viewport ramp may add
  positive firmness protection but no longer participates in a subtractive main-head stroke term. Extreme wide/tall shape
  alone therefore cannot make Bubble thinner than its canonical contract.
- [~] Extreme-wide Bubble presentation compensation is source-landed: only a wide-tail ramp beyond ordinary card shapes
  reaches +1 big / +3 small bubbles and +20% stream baseline/cap (full at the observed 1174x187 / 6.28:1 viewport). No
  radius, Ghost/history, reaction amplitude, drift or logical cadence compression is used. Await physical validation.

## E2 — richer customizable Sphere

- [x] Inventory five material presets, current energy transfer/defaults/maxima and existing mesh/shader
  constraints. Identify why current live bands produce barely visible displacement.
- [x] Define stronger independent bass/mid/high and vocal-range deformation, preserving a quiet/idle state and controls
  that can return to restraint. Derive a finite maximum envelope and fit/framing contract explicitly.
- [x] Add independently adjustable whole-body transient growth/contraction, base bump and bump reactivity.
- [~] Whole-body size response follow-up: `SphereFrameRuntime` owns one bounded near-critical spring on the sole authored
  logical cadence. Checkpoint 2 raises Size Response to 0..3 and the maximum target to +0.90 radius; render still consumes
  only immutable `SphereFrame.size_pulse`. Deformation is 0..4.5, preserving the complete <=3.0 domain and softening only
  the newly-added negative tail enough to prevent radius inversion. Defaults are unchanged. Await eyes-on amplitude acceptance.
- [~] Magma fissure relief follow-up: major fissures are now genuine inward vertex-radius displacement, including the six
  lower-hemisphere liquid vents; fine branching remains filtered bump/emissive detail. Await eyes-on depth acceptance.
- [~] Magma/Water attached-liquid follow-up: six fixed instanced meshes now derive real rotating/deforming body anchors. The
  body forms a matching local bulge while each liquid mesh keeps an embedded neck/cap through roughly the first half of its
  life, then pinches off and falls under gravity. Magma is slower/narrower/viscous and its anchors are part of the fissure
  network; Water is rounder/more elastic. The old Water side lanes are gone. Await physical proof that attachment reads
  clearly rather than as intersecting detached particles.
- [~] Optional Sphere local AA and lighting-derived cast shadow are persisted/preset-aware. AA is derivative-based and
  Sphere-local; shadow is one analytical quad opposite the configured light direction with adjustable darkness. Await
  physical edge/shadow-direction/strength acceptance.
- [x] Chrome/Silver/Obsidian: detailed material-specific relief with readable light on stronger deformation.
- [x] Keep topology static and GPU-owned. Reuse authored time/energy for bounded analytical motion and
  any fixed-count instanced secondary geometry; no per-frame CPU topology, simulation timer or jobs.
- [x] Add only settings with a real user-visible effect, shared through canonical schema, lazy builder,
  immutable frame/uniforms and curated preset/Custom round-trip. Preserve default dormancy.
- [x] Historical real GL/Quick captures cover quiet/active/transient states and small/large/extreme extents.
- [ ] Checkpoint 2 requires fresh GL/Quick captures for attached liquid, macro-fissure geometry, optional AA/shadow and the
  4.5 Deformation / 3.0 Size Response extremes before those new visual contracts can be called automatically validated.
- [x] Source/identity, zero controls, settings persistence, GL fence/retirement and amplitude tests.

## E3 — checkpoints and acceptance

- [x] Update Spec/Index and focused contracts alongside landed geometry/material changes.
- [ ] Focused tests and relevant shared destination gates; classify unrelated debris in Future_Cleanup.
- [ ] Commit/push each validated slice. Keep physical 60/165Hz, mixed-DPR and installed tests explicit.
- [ ] Awaiting operator validation: Bubble extreme-wide response, attached Water/Magma origin/neck/pinch-off, Magma macro
  fissure depth, Sphere AA on/off, cast-shadow direction/darkness, 4.5 Deformation/3.0 Size Response extremes, and layout-slot
  active-mode restoration. Automatic source contracts cannot close these perception gates.

## Discovered follow-ups (after active geometry/material work)

- [~] Sine/Oscilloscope missing visualizer glow: trace actual frozen parameters and shader coverage at
  different scales. Restore glow independently of the current AA line core; add falsifying GL evidence.
- [x] Geometry-only Edit Save no longer tears down the runtime: retained state is promoted before CUSTOM clears. A successful
  Visualizer cross-display transaction is also a no-teardown Save path because scene + runtime/pacer/lifecycle ownership has
  already moved atomically. Ordinary family topology changes still reconcile; numbered layout-slot **load** deliberately
  reconstructs because it may alter ordinary enabled/layout state and now the active Visualizer mode.
- [~] Sine/Spline pulse coverage: operator sees improved AA but jagged edges during pulses in Wobble
  Groove. Reproduce with the actual curated preset and strong pulse; inspect signed-distance footprint
  before any amplitude or temporal filtering change. Signed-distance derivatives now avoid cusp
  cancellation; curated Wobble Groove coverage and line gates pass (27 tests). Physical pulse acceptance
  remains open; the current pixel gate does not independently prove the reported pulse shimmer gone.
- [x] Slide timing correction: replaced the proven 1-to-10 velocity discontinuity at Elastic arrival with
  quintic travel/rebound and zero endpoint-velocity Wobble/Flex envelopes. 106 focused tests pass.
  Awaiting physical timing acceptance; exact endpoints, sealed coverage and the sole transition clock remain.

The resize screenshot (`codex-clipboard-a5504cf1-1088-44ef-bbcc-ab5f0094f651.png`) shows a roughly
1842x585 edit rectangle but only ~533x163 of rendered Spectrum at its top-left. Source tracing found
normal snapshots refresh committed dimensions while drag position remains live; the shared temporary
projection must derive scale from the active session rectangle instead.

## E1 implementation evidence

The actual Quick scene/session/owner test now exercises all six modes through each edge operation,
normal presentation interleaving, wheel scaling, Cancel, and saved geometry. 55 focused geometry tests
pass. The temporary size comes from the active session rectangle; incoming committed geometry cannot
replace it at the dragged origin. Independently rounded X/Y dimensions are validated by intersecting
possible uniform-scale intervals, so narrow/tall integer rounding does not spuriously reject a valid edit.
The per-mode geometry audit (87 focused checks) found no additional duplicate scale or hidden extent cap.
Physical live-preview acceptance remains open against the supplied Spectrum screenshot.

## Missing Sine/Oscilloscope glow — active source-to-visible correction

The later screenshot shows bright cores with almost no broad halo in both ordinary playback and editing.
The short 03:16:49–03:17:09 run is archived in `fw_missing_line_glow_2026_09_05`; resolved playing bands are
substantial (~0.45–0.50), so absence of audio is not the cause. Settings retain enabled, opaque glow colours.
QColor is correctly frozen into RGBA tuples; do not add an unreachable conversion fallback to the renderer.

Source identifies two spatial losses. Gaussian glow uses vertical distance from the curve, so its width measured
perpendicular to a steep segment collapses. Its width also follows the tiny authored uniform scale even when a
huge saved world fills a large visible viewport (the inspected profile resolves ~8239.7x5861.8 to 894x636 at
0.1085 scale). The AA core has independent fragment coverage, making that narrow halo still harder to distinguish.

- [x] Preserve user screenshot/logs; trace settings -> frozen snapshot -> actual GL output separately from line AA.
- [x] Project glow distance in framebuffer-normal coordinates using the signed-distance gradient. Leave core
  coverage and amplitude equations intact; a glow-on test cannot substitute for the glow-off AA oracle.
- [x] Derive glow style width from the actual content footprint relative to the canonical 420x280 area,
  preserving canonical style, DPR and whole-widget scaling. Do not replace it with a fixed device-pixel radius.
  Equal visible footprints must not get different glow widths because their saved world encoding differs.
- [x] Review canonical flat-segment math (8 logical-pixel sigma) and prove whole 2x resize, DPR 1.5,
  steep-segment halo pixels and huge saved-world geometry on an opaque background. Before/after captures at
  the actual primary profile geometry are inspected; 14 focused GL/glow/coverage tests pass.
- [x] Focused checks and durable contract update. The operator confirms visible glows; final large-scale
  balance remains Awaiting Physical Validation.

## 2026-09-05 operator follow-up

- Cross-display Save/slot-load failures were lifecycle ownership, not legacy geometry-slot format. Manager/unit retirement
  authority now follows the retained Visualizer scene to the target display.
- The extreme incoherent rect/extent rejection remains deliberately fail-loud and is deferred to the next geometry pass; do
  not widen tolerance to hide a genuine anisotropic owner split.
- Sphere's elastic whole-body size response is physically reported as substantially better. Vocal Response remains at its
  expanded 3.0 ceiling; Checkpoint 2 further raises Deformation 3.0 -> 4.5 and Size Response 2.0 -> 3.0/+0.90 target, with
  unchanged defaults and explicit negative-tail radius safety.
- Geometry slots now persist the active Visualizer `mode` while deliberately excluding per-mode tuning/preset values. Slot
  load remains the fenced rebuild boundary so the authored visible mode is reconstructed.
- Claude's deterministic 1px discrete display-hop drift was real and pre-existing: integer `QRect.center()` biases even-size
  rectangles one pixel. The discrete projection now uses a floating geometric centre; drag transfer math is unchanged.
