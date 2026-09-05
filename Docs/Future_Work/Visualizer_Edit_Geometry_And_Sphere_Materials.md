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

- [~] Fix the operator's Bubble freeze during Edit and after Save. The archived 03:24–03:26 run in
  `logs/evidence_chest/fw_bubble_edit_freeze_2026_09_05_new` keeps advancing fresh logical Bubble states
  through 03:26:59, but rejects incoherent working rectangle/extent pairs during resizing. Trace repeated
  moves within one gesture, integer rounding and interleaved publication; preserve independent extent/scale.
- [ ] Prove visible snapshot revisions continue through repeated drag updates and Save, with unchanged
  generation/source ownership. Do not hide projection rejection by relaxing coherence or restarting Bubble.
- [x] Reduce full main-outline width by one additional logical pixel at extreme visible sizes. Reuse the
  existing area-based large-stroke ramp (zero through 1.75x canonical linear scale, full at 2.5x) for a
  continuous reduction. Keep Ghost and small/canonical widths; retain derivative coverage and radius response.
- [ ] Awaiting physical validation of freeze recovery and requested extreme-size outline weight.

## E2 — richer customizable Sphere

- [x] Inventory five material presets, current energy transfer/defaults/maxima and existing mesh/shader
  constraints. Identify why current live bands produce barely visible displacement.
- [x] Define stronger independent bass/mid/high and vocal-range deformation, preserving a quiet/idle state and controls
  that can return to restraint. Derive a finite maximum envelope and fit/framing contract explicitly.
- [x] Add independently adjustable whole-body transient growth/contraction, base bump and bump reactivity.
- [x] Magma: flowing detailed emissive fissures, diffuse smoke-like fire, smoke/ash and downward lava drips.
- [x] Water: translucent depth/edge treatment, rolling detail and rounded irregular falling 3D blobs (no drip neck).
- [x] Chrome/Silver/Obsidian: detailed material-specific relief with readable light on stronger deformation.
- [x] Keep topology static and GPU-owned. Reuse authored time/energy for bounded analytical motion and
  any fixed-count instanced secondary geometry; no per-frame CPU topology, simulation timer or jobs.
- [x] Add only settings with a real user-visible effect, shared through canonical schema, lazy builder,
  immutable frame/uniforms and curated preset/Custom round-trip. Preserve default dormancy.
- [x] Real GL/Quick captures at quiet/active/transient states and small/large/extreme extents; inspect
  transparency, deformation, detached effects and material identity. Profile bounded draw cost.
- [x] Source/identity, zero controls, settings persistence, GL fence/retirement and amplitude tests.

## E3 — checkpoints and acceptance

- [x] Update Spec/Index and focused contracts alongside landed geometry/material changes.
- [ ] Focused tests and relevant shared destination gates; classify unrelated debris in Future_Cleanup.
- [ ] Commit/push each validated slice. Keep physical 60/165Hz, mixed-DPR and installed tests explicit.
- [ ] Awaiting operator validation: live adjustment stability, Bubble outline/response, stronger Sphere
  reactivity and the requested material appearance. Automatic tests cannot close this perception gate.

## Discovered follow-ups (after active geometry/material work)

- [~] Sine/Oscilloscope missing visualizer glow: trace actual frozen parameters and shader coverage at
  different scales. Restore glow independently of the current AA line core; add falsifying GL evidence.
- [~] Edit exit teardown assessment: inventory its current owners/resets, source freshness and stale-frame
  evidence. Decompose and implement ordinary Save/Cancel without teardown if those contracts can be retained.
  Preserve activation/disable/transfer retirement where identities or actual render ownership change.
  Source audit confirms stale committed rectangles are currently concealed by replacement. Implementation:
  `Docs/Future_Work/Edit_Layout_Live_Commit.md`.
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
