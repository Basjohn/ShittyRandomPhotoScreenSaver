# Visualizer visual regression recovery

Last updated: 2026-09-05

Original operator rejection of `2f221905`: Bubble aspect response remains wrong and outlines remain too
thin; all modes show aliasing/washed glow/wrong colours (Organs must have black bars over a rainbow
backdrop); Sphere is tiny and apparently static, including after Edit Layout scaling. This supersedes
the earlier prototype acceptance. `FWPlan.md` owns the live repair sequence. Preserve the sole logical
clock, event-driven ownership, source/generation fences and native float32 transport.

Evidence copied before any test can rotate logs: `logs/evidence_chest/fw_visual_regression_2026_09_05`.
The previous injected-frame/canonical-geometry tests missed the persisted profile and production
configuration route. They remain narrow oracles, not proof that the rejected runtime works.

## R1 — shared appearance and actual geometry

- [x] Archive current run logs; inspect exact source and distinguish live/idle/recreation epochs.
- [x] Trace curated Organs -> resolved runtime config -> logical common style -> GL uniforms, preserving
  opaque black, alpha, rainbow backdrop, authored fill/border and glow parameters.
- [x] Reproduce with real curated configuration; correct the first failing boundary. Configuration preserves black fill; the subpixel glow
  core exceeded spread and inverted smoothstep, washing bar interiors grey.
- [x] Trace AA/stroke/glow dimensions against actual resolved content and DPR, including a huge logical
  extent displayed at small uniform scale. Make shader pixel coverage depend on framebuffer derivatives,
  not a possibly subpixel authored-scale alias. Preserve visual thickness separately from AA coverage.
- [x] Real GL colour/coverage proof for Organs and representative line/Bubble modes at the logged geometry.

Live Bubble domain reaches `19.618 x 5.639` (about `8240 x 1579` authored extent), while B8 reports
content height about 268 logical pixels. Thus uniform scale is about 0.17: a shader that interprets
`u_visual_scale / content_height` as an AA pixel produces much less than one device pixel. This is a
representation-sensitive rendering problem, not permission to lower cadence or DSP gain.

## R2 — Bubble aspect response and outlines

- [x] Replace the rejected height-only shape coupling with a documented shape-independent response
  reference anchored at canonical 420x280. User's renewed request deliberately corrects this product
  mapping; do not claim unchanged height-normalized pixels are acceptance of the reported symptom.
- [x] Evaluate equal-area canonical-height geometry (`sqrt(content_width * content_height / canonical_aspect)`)
  as the size reference: canonical shape stays exact, widening/shortening no longer suppresses a same-area
  response and narrowing/heightening no longer exaggerates it. Keep the full temporal waveform, attack,
  overshoot and settling; no cap/clip/energy retune to conceal a failed mapping.
- [x] Use current physical size for thicker large/extreme outlines and modestly thinner small outlines;
  keep a real device-pixel AA footprint. Ghost/ripple geometry must use a coherent local metric.
- [ ] Test the actual curated Bubble preset across mild/extreme aspect variants, waveform deltas and
  rendered outlines. Inspect visual captures at representative persisted extents/scales.
- [x] Update durable geometry contracts to state the deliberate operator-authorized correction. Retain
  the R-69 lesson against arbitrary viewport compression that destroys response.

## R3 — Sphere production behavior and size

- [x] Prove source -> sole logical runtime -> capture -> immutable publication -> Quick time/energy
  progression using production-owned configuration, not injected SphereFrame alone.
- [x] Correct genuine source/activation admission defects, including valid generation/activation zero.
- [x] Make Edit Layout enlargement visibly enlarge the Sphere at the actual persisted geometry. Baseline
  280 * 0.28 * ~0.17 gives only ~13px radius in this run despite a large assigned viewport.
- [x] Retain a frameless surface with deformation space; prove material motion and band-separated
  deformation at visible runtime size, and canonical/large/small resize behavior.
- [x] Keep GPU retirement/source identity tests and avoid a second timer or simulation owner.

## R4 — logs, verification and checkpoint

- [x] Summarize Bubble cadence/source-age/tail evidence from the supplied run without conflating Settings,
  CUSTOM recreation or other modes with steady Bubble. User did not notice a hitch in this run.
- [ ] Run focused falsifying production-route and pixel tests, then relevant shared visualizer gates.
- [ ] Update live plans, inspect source/diff, commit and push narrow validated slices.
- [ ] Physical acceptance: actual Organs colours/backdrop, other modes' glow/AA, Bubble rectangular versus
  wide/narrow response/outline, and Sphere enlarge/spin/deform. Keep this open until the operator accepts.

No global GC/cadence change, polling loop, mutable cross-thread payload or legacy renderer resurrection.

## Evidence interpretation

At logged geometry, Organs bar centers were (161,161,161,230) with the old glow and dark after
correcting its falloff. Sine/Osc/DevCurve AA now uses framebuffer derivatives separately from authored
style scale. Sphere uses 0.28 * min(content width, content height), giving ~75px radius rather than
~13px at the 8240x1579 saved extent. Real GL tests prove time/bass pixel changes at that geometry;
valid source identity zero is admitted through the existing exact identity fence.

Archived Bubble steady HUD medians: 59.87 draw fps, 89.89 revision Hz, 25.76ms state age. All 27
nonzero cadence reports integrated every requested tick (ratio 1.0, failures 0). Integration median
2.20ms, snapshot 0.59ms; rare tick spikes reached 76.53ms and reported latency reached 109.8ms.
Recreation caused separate multi-second stale intervals. These do not prove a perceptible steady
hitch; the operator did not notice one. Keep any further attribution on matching intervals, without
reopening accepted GC or reducing cadence.

Awaiting contact validation: equal-area response can expand displayed heads beyond canonical collision
admission at some aspects. Collision was already an authored unit-content policy, not literal pixel
packing. Before changing it, compare same-seed rendered pair overlap and collision/impulse/pop events
at canonical/wide/tall. Preserve protected BTF trajectories until a dedicated contact test justifies it.

Bubble outline pixel proof after the requested one-pixel reduction: effective single-ring widths
are 0.718, 0.957 and 10.039 pixels at 210x140, 420x280 and 1260x840 (r=.08), including the
minimum subpixel-coverage floor. Same-area circle/highlight captures are inspected in
`logs/evidence_chest/fw_geo_material_2026_09_05/bubble_equal_area_outlines.png`.
