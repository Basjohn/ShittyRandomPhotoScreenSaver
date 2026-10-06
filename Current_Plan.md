# SRPSS | Current Plan

This is the **live forward checklist**. It contains open work and acceptance debt only. Durable product truth belongs in
`Spec.md`, `Docs/Contracts.md`, Architecture/Guardrail/Guide/Reference documents, and useful failure history belongs in
`Docs/Historical_Bugs/`.

Work top-to-bottom unless the operator redirects a slice. Significant slices return a superseding GODZIP.

---

## 1. Bubble tiny-radius judder | protect feel first

The first render-only release-envelope repair is accepted as the baseline. A second, deliberately tiny presentation-only
breath assist is implemented behind an exact negative control; it must earn acceptance without changing Bubble's authored
reaction, elasticity, attack, settling, loud-passage variation, motion, collision or cadence.

- [ ] **B1. Measure the candidate on the operator recordings.** Run the same clips with the tiny-breath seam forced OFF and
  ON; retain per-clip tiny-radius alternating-step counts and dot/outline-boundary crossings. If the visible defect is not
  concentrated in the eligible physical-radius band, change eligibility rather than audio/simulation gain.
- [ ] **B2. Re-run protected Bubble automation.** Existing golden/reactivity suites remain green with no golden rewrite;
  impulse/BPM/ramp/step/silence behavior remains within its existing tolerance; no attack/excursion/hot-passage regression.
- [ ] **B3. Physical acceptance on both displays.** Judge the same tracks at quiet breathing, strong hits, sustained loud
  sections, min/max size, pop/exit and CUSTOM extremes. Reject the candidate if it feels flatter/slower even when the metric
  improves.

Focused automation:

```powershell
python -m pytest tests/test_bubble_render_judder.py -q
python -m tools.visualizer_replay.bubble_judder --fixtures --clip broadband_noise --frozen --compare-tiny-assist --px-per-unit 300 --min-px 0.5
```

Real recordings:

```powershell
python -m tools.visualizer_replay.bubble_judder --compare-tiny-assist --px-per-unit 300 --min-px 0.5
```

Durable mechanism/negative controls: `Docs/Historical_Bugs/R-105_Bubble_Remaining_Small_Radius_Judder.md` and
`Docs/Guardrails/Bubble_Temporal_Fidelity.md`.

---

## 2. Shared presentation stalls

Treat Bubble/DevCurve as canaries for shared delivery. Do not retune a Visualizer to hide GUI/runtime stalls.

- [ ] **P1. FEEDS model updates.** Replace whole-model reset where practical with bounded row change/insert/remove
  notification so ordinary refresh does not rebuild the full delegate tree.
- [ ] **P2. Play-start audio capture.** Move expensive backend construction off the GUI thread while preserving one bounded
  capture owner and current wake/freshness semantics.
- [ ] **P3. GC freeze.** Measure `gc_policy.freeze_stable_generation` cadence/cost in the current runtime and either bound the
  owning work or prove it is no longer material.
- [ ] **P4. Re-trace after P1-P3.** Investigate native/swap/sync ownership only if unattributed presentation holes survive.
  Do not add a compositor timer or `frameSwapped -> requestUpdate()` loop.
- [ ] **P5. Physical bar.** Unattended two-display Bubble + DevCurve run with no Settings/mouse interaction; compare
  >25 / >33 / >50 ms gaps and owner classes before/after.


---

## 3. Visualizer dormancy and retirement

The binding invariant is count-independent: registry growth must not add recurring work to an unrelated active mode.

- [ ] **L1. Sine heartbeat active-mode ownership.** Resolve heartbeat work only while Sine is the active mode; inactive Sine
  performs zero heartbeat energy/transient/event queries regardless of persisted Custom values.
- [ ] **L2. One activation-resolved logical hook.** Replace accumulating common-tick early-return dispatches with one optional
  callable resolved at mode activation. The hot path must not grow one branch/call per registered mode.
- [ ] **L3. Registry-derived dormancy tests.** Repeated-switch, lazy-import/construction and negative-work coverage derives
  from the canonical Visualizer registry. Synthetic registry growth must not increase steady common-tick work for the one
  active owner.
- [ ] **L4. Terminal Python-owner timeout.** Find why `QuickDisplayUnit`, `QuickDisplayPresenter` and
  `QuickDisplayVisualizerOwner` can remain strongly reachable after Qt/resources/thread work have drained. Fix reference
  ownership/order rather than extending the destruction-barrier deadline; add normal-stop and replacement-generation bars.

Durable invariants: `Docs/Guardrails/Performance_Optimization_Contract.md` P5 and
`Docs/Guardrails/Visualizer_Presentation.md` 1A.

---

## 4. Extruded Spectrum polish

- [ ] **E1. Shape editor.** Give Extruded the Spectrum shape-editor experience while preserving one shaping authority and
  per-mode/preset ownership. Reuse the editor; do not fork its math or silently mutate an unrelated authored Spectrum preset.
- [ ] **E2. Optional shadow.** Add an off-by-default shadow through the canonical shadow-direction system/shared Scene3D
  primitive. Disabled/inactive owns no target/pass/resource; measure active CPU/GPU cost before acceptance.
- [ ] **E3. Physical acceptance.** Both displays; overflow on/off; extreme orbit; reflective/non-reflective presets; shadow
  directions; CUSTOM resize/reflow; wallpaper transition.


---

## 5. GitHub Release / README animated WebPs

Release/readme media only. Generated captures never enter runtime QRCs or normal GODZIPs.

- [ ] **M1. Transition captures.** Enumerate the canonical transition registry at capture time and render each admitted
  identity plus curated appearance variants that materially differ. Do not maintain a hand-counted transition list in the
  harness/docs.
- [ ] **M2. Visualizer captures.** Enumerate the canonical Visualizer registry and each mode's curated presets, replaying a
  deterministic recorded-music clip through the production logical/capture/render path.
- [ ] **M3. Encoding.** Capture high quality first; prefer reducing dimensions/fps before crushing image quality. Loop forever,
  strip metadata, stay under release-host limits.
- [ ] **M4. Manifest.** Emit mode/transition ID + preset/variant -> file, clip, duration, dimensions and source revision so only
  stale media needs regeneration.

---

## 6. Test durability and unattended acceptance tooling

- [ ] **Windows durability gate after each tranche.** Run `tools/test_durability_audit.py`,
  `tests/test_test_suite_durability.py` and the touched Settings/preset/registry suites on the real PySide tree. Treat missing
  dependencies as environment-blocked, but resolve any product/test RED before accepting the tranche.
- [ ] Continue the **manual** pass over `tools/default_pin_scan.py` review candidates. The blocking audit owns only
  high-confidence smells: copied canonical defaults (including transitive aliases), named shipped-preset dependencies, fixed
  extensible-registry counts/catalog copies and authored-Markdown prose used as a behavior oracle. Convert accidental authority
  copies; preserve fixture round trips, schema/range checks, compatibility mappings, goldens, geometry/state oracles and negative
  controls.
- [ ] Review **source-string tests** separately. Preserve high-value forbidden-import/call/ownership negative bars where no
  practical runtime seam exists; replace tests that merely pin human-facing copy, incidental implementation spelling or source
  layout when behavior can be exercised directly. Do not turn this into a blanket ban on static architecture tests.
- [ ] Reconcile remaining stale test-side expectations unrelated to authored defaults, including Media I/O-starvation stubs
  against the controller's current work-loop entry point.
- [ ] Add a small external **run-matrix harness** over the accepted `--exit-after` terminal-shutdown CLI. Cases should be
  declarative, run sequentially by default, capture exit/fault/log artifact paths and never own a second shutdown mechanism or
  force-kill the parent Foundry process. Use it for repeatable startup/teardown, diagnostic-flag, display and selected mode/effect
  acceptance matrices without adding product-runtime scheduling.

---

## 7. Voxel Sphere promotion

- [ ] Prove which technical controls materially change Sphere's consumed analysis seams; expose no dead controls.
- [ ] Replace hidden whole-Spectrum technical-profile borrowing with Sphere-owned descriptor/capability metadata while
  preserving compatibility for missing persisted keys.
- [ ] Move Sphere per-frame values into the shared uniform block instead of individual uniform traffic across its programs.
- [ ] Finish shared Scene3D lifecycle/dormancy migration and remove superseded Sphere-local low-level plumbing after parity.
- [ ] Physical/golden acceptance: behavioral vocabulary preserved or stronger; Mirror Ball / Mirror Cubes, tier AA, overflow
  and wallpaper reflection on bright/dark images and both displays.

---

## 8. Shared 3D primitives and next consumers

Resume only after the immediate Bubble/shared-runtime/lifecycle work above is under control.

- [ ] **S17 remaining active-only scene facilities:** demand-created normal/material/depth/history attachments, reusable real
  3D shadows, GTAO only if justified, weighted blended OIT/depth-aware transparency, thickness/depth refraction, Fresnel,
  rough transmission and restrained dispersion.
- [ ] **S18 primitives:** sprite/streak/ribbon particles over `CompactedPopulation`, collision/OIT where justified, lightning,
  then bounded reduced-resolution smoke/fog/fire volumes with advection/vorticity/depth raymarch/temporal reprojection.
  Measure each primitive independently before combinations.
- [ ] **Visualizer vertical sequence:** Reactive Particle Field -> Spectrum Terrain/Skyline/Tunnel -> Waveform Ribbon ->
  Deformable Blob Sphere -> Bubble Depth Field under Bubble Temporal Fidelity.
- [ ] Only after primitives are accepted: electrical storm terrain, smoke-lit voxel fracture, ember/dust destruction,
  refractive glass lit by bolts, volumetric shockwaves and photo-colour IBL combinations.

---

## Cross-cutting acceptance for every slice

- [ ] **Dormancy/count invariance:** inactive registry entries add no recurring runtime work; only admitted owners may prepare,
  with the documented single reserved-next-transition exception.
- [ ] **Performance:** measure CPU submit/GPU cost and Python GL-call pressure for new render passes.
- [ ] **Time:** no second simulation clock, catch-up queue or hidden recurring timer.
- [ ] **State:** touched GL state is fence-restored on success and failure.
- [ ] **Memory:** targets/buffers/volumes/history are bounded, consumer-owned and retired deterministically.
- [ ] **Settings:** canonical defaults/descriptor resolution happen before admission; renderers do not read Settings per frame.
- [ ] **Physical:** both displays, cold/warm use, switching, CUSTOM, Play/Pause/Resume, real photos and representative music.

## Handoff rules

The supplied/latest GODZIP is the working-tree authority. Significant slices return a full-file superseding GODZIP, never a
partial patch. Do not include oversized generated media, recordings, frame traces, build outputs or unchanged giant assets/tests.
GODZIP manifests are produced/validated with `tools/godzip_foundry_core.py`; `.godzip/*` is archive metadata, never a repository
replacement target. No environment-variable feature gates. Rejected experiments are removed rather than retained as fallback
architecture.
