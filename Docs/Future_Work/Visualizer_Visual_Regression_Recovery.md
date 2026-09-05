# Visualizer visual regression recovery

Last updated: 2026-09-05

Active operator rejection of `2f221905`: Bubble aspect response remains wrong and outlines remain too
thin; all modes show aliasing/washed glow/wrong colours (Organs must have black bars over a rainbow
backdrop); Sphere is tiny and apparently static, including after Edit Layout scaling. This supersedes
the earlier prototype acceptance. `FWPlan.md` owns the live repair sequence. Preserve the sole logical
clock, event-driven ownership, source/generation fences and native float32 transport.

Evidence copied before any test can rotate logs: `logs/evidence_chest/fw_visual_regression_2026_09_05`.
The previous injected-frame/canonical-geometry tests missed the persisted profile and production
configuration route. They remain narrow oracles, not proof that the rejected runtime works.

## R1 — shared appearance and actual geometry

- [x] Archive current run logs; inspect exact source and distinguish live/idle/recreation epochs.
- [ ] Trace curated Organs -> resolved runtime config -> logical common style -> GL uniforms, preserving
  opaque black, alpha, rainbow backdrop, authored fill/border and glow parameters.
- [ ] Reproduce with real curated configuration; correct the first boundary that loses values.
- [ ] Trace AA/stroke/glow dimensions against actual resolved content and DPR, including a huge logical
  extent displayed at small uniform scale. Make shader pixel coverage depend on framebuffer derivatives,
  not a possibly subpixel authored-scale alias. Preserve visual thickness separately from AA coverage.
- [ ] Real GL colour/coverage proof for Organs and representative line/Bubble modes at the logged geometry.

Live Bubble domain reaches `19.618 x 5.639` (about `8240 x 1579` authored extent), while B8 reports
content height about 268 logical pixels. Thus uniform scale is about 0.17: a shader that interprets
`u_visual_scale / content_height` as an AA pixel produces much less than one device pixel. This is a
representation-sensitive rendering problem, not permission to lower cadence or DSP gain.

## R2 — Bubble aspect response and outlines

- [ ] Replace the rejected height-only shape coupling with a documented shape-independent response
  reference anchored at canonical 420x280. User's renewed request deliberately corrects this product
  mapping; do not claim unchanged height-normalized pixels are acceptance of the reported symptom.
- [ ] Evaluate equal-area canonical-height geometry (`sqrt(content_width * content_height / canonical_aspect)`)
  as the size reference: canonical shape stays exact, widening/shortening no longer suppresses a same-area
  response and narrowing/heightening no longer exaggerates it. Keep the full temporal waveform, attack,
  overshoot and settling; no cap/clip/energy retune to conceal a failed mapping.
- [ ] Use current physical size for thicker large/extreme outlines and modestly thinner small outlines;
  keep a real device-pixel AA footprint. Ghost/ripple geometry must use a coherent local metric.
- [ ] Test the actual curated Bubble preset across mild/extreme aspect variants, waveform deltas and
  rendered outlines. Inspect visual captures at representative persisted extents/scales.
- [ ] Update durable geometry contracts to state the deliberate operator-authorized correction. Retain
  the R-69 lesson against arbitrary viewport compression that destroys response.

## R3 — Sphere production behavior and size

- [ ] Prove source -> sole logical runtime -> capture -> immutable publication -> Quick time/energy
  progression using production-owned configuration, not injected SphereFrame alone.
- [ ] Correct genuine source/activation admission defects, including valid generation/activation zero.
- [ ] Make Edit Layout enlargement visibly enlarge the Sphere at the actual persisted geometry. Baseline
  280 * 0.28 * ~0.17 gives only ~13px radius in this run despite a large assigned viewport.
- [ ] Retain a frameless surface with deformation space; prove material motion and band-separated
  deformation at visible runtime size, and canonical/large/small resize behavior.
- [ ] Keep GPU retirement/source identity tests and avoid a second timer or simulation owner.

## R4 — logs, verification and checkpoint

- [ ] Summarize Bubble cadence/source-age/tail evidence from the supplied run without conflating Settings,
  CUSTOM recreation or other modes with steady Bubble. User did not notice a hitch in this run.
- [ ] Run focused falsifying production-route and pixel tests, then relevant shared visualizer gates.
- [ ] Update live plans, inspect source/diff, commit and push narrow validated slices.
- [ ] Physical acceptance: actual Organs colours/backdrop, other modes' glow/AA, Bubble rectangular versus
  wide/narrow response/outline, and Sphere enlarge/spin/deform. Keep this open until the operator accepts.

No global GC/cadence change, polling loop, mutable cross-thread payload or legacy renderer resurrection.
