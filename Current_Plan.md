# SRPSS | Current Plan

This is the **live forward checklist**. It intentionally omits closed archaeology. Durable accepted behaviour lives in the
Guardrails / Reference / Historical Bugs docs; this file answers **what we do next, why, and what proves it**.

Working authority for this refresh:

- GODZIP source head `ad96bb78a3aff5f26139e18377c4e901ed8fc81f` (2026-10-05).
- Runtime logs supplied 2026-10-05 through 12:37.
- Bubble judder fix commit `800bf70f185da0c55b4f38857bea70e703436b7c` is confirmed landed before the GODZIP.
- `Docs/Guardrails/Bubble_Temporal_Fidelity.md`, `Docs/Guardrails/Performance_Optimization_Contract.md`,
  `Docs/Guardrails/Visualizer_Presentation.md` and `Docs/Reference/Transitions.md` are binding.

Work top-to-bottom unless the operator redirects a slice. Significant slices get a superseding GODZIP checkpoint.

---

## 1. Bubble remaining radius judder | **FIRST**

Operator report (2026-10-05): the render-only 0.10 s release fix improved Bubble, but small bubbles can still look caught
between breathing states, moving only 1-2 physical pixels and visibly vibrating instead of completing a breath. Any cure that
weakens reaction, elasticity, attack, settling or loud-passage variation is worse than the remaining judder and is rejected.

### What is already proved

- [x] The first judder fix **is present**, not lost work. Commit `800bf70f18` added the render-only release envelope and
  `tests/test_bubble_render_judder.py`; `ad96bb78a3` followed it.
- [x] Position is not the primary defect. The replay tracker found alternating **radius** steps while x/y stayed near tracker
  noise.
- [x] The broad noisy render inputs were a real source: `size_gate_energy`, `_render_body_energy` and
  `_sustained_loud_energy` could chatter frame-to-frame. The drawn copies now rise immediately and fall over
  `RENDER_SIZE_RELEASE_S = 0.10 s`; simulation inputs remain raw.
- [x] Feeding that envelope back into Bubble simulation changed feel/reaction materially and was rejected. **Do not revive
  that route.**
- [x] Before B2, small bubbles differed from hero bubbles in one important way: non-big bubbles returned their target radius
  directly instead of owning a small-bubble display-radius presentation seam. B2 now inserts only the bounded tiny-breath
  experiment there; it does not reuse hero smoothing or change simulation authority.
- [x] Small visible radius still contains raw `bubble.pulse_energy`; that pulse integrates `gated_energy` before the
  render-only seam. The previous investigation explicitly left this as the remaining likely source.
- [x] The fragment shader changes representation below roughly **4 physical px radius**: tiny bubbles become filled dots;
  above it they become outline/specular bubbles. Remaining judder must be classified around this boundary instead of treating
  all small bubbles as one population.
- [x] Latest supplied trace does **not** make steady cadence/repeated frames the owner of this Bubble symptom: over ~434 s
  screen 1 ran ~90.5 Visualizer draws/s with ~1.3 repeats/s outside transitions; logical dt median 11.09 ms, p99 11.63 ms.
  System stalls still exist (section 2), but ordinary Bubble cadence is healthy enough that the remaining 1-2 px radius
  vibration must be investigated at the radius/render seam first.

### Current candidate and next investigation

- [x] **B1a. Add physical tiny-radius instrumentation without product hot-path cost.**
  `tools/visualizer_replay/bubble_judder.py` now reports alternating radius runs in a physical <=8 px band, separately
  identifies runs crossing the shader's ~4 px dot/outline boundary, can use committed replay fixtures (`--fixtures`) or
  local recordings, and can select a single clip (`--clip`). This remains offline tooling only.
- [ ] **B1b. Run the size-bin evidence on the operator recordings.** The supplied GODZIP intentionally excludes the large
  local recording fixtures, so run the comparison command below on the real tree and retain the per-song OFF/ON numbers.
  If the remaining visible defect is concentrated outside the <=8 px band, retune the *eligibility band*, not Bubble audio.
- [x] **B2. Land a deliberately narrow physical-pixel micro-breath candidate.**
  `BubbleSimulation._apply_tiny_breath_assist()` is presentation-only and uses the cached committed viewport height. It:
  - affects only non-big, non-promoted bubbles whose displayed radius is <=8 physical px;
  - leaves `pulse_energy`, motion, collision authority, clocks and scheduling untouched;
  - requires an established raw target direction;
  - suppresses/attenuates the first <=2 px reversal and admits it on the second sample if it persists, while never
    allowing the drawn radius to sit more than 1 px from the authored target;
  - allows at most one extra physical pixel per established half-breath; if the raw target pauses on the next sample, raw
    authority resumes immediately so the assist cannot remain parked beyond a completed breath;
  - never lets the assist itself cross the shader's 4 px dot/outline representation boundary; only the authored raw target
    may cause that switch;
  - bypasses entirely at pulse endpoints (`<=0.08` / `>=0.92`), pop/exit/promotion, and >=2.5 px strong edges;
  - has an exact negative-control switch: `TINY_BREATH_ASSIST_PX = 0.0`.
  The focused synthetic contract proves OFF follows `[4,5,6,5.4,6.4,7.4]` px exactly while ON produces
  `[4,5,7,6.4,6.4,7.4]` px: one committed breath, no amplified one-frame reversal.
- [ ] **B3. Compare the candidate against the protected Bubble shape.** Required before physical acceptance:
  - existing Bubble golden/reactivity suites green with no golden rewrite;
  - clean impulse / 60 / 120 / 180 bpm / ramp / step / silence metrics remain within the existing tolerance;
  - no lower attack, excursion, elasticity or hot-passage variation;
  - remaining noisy radius judder improves beyond `800bf70f18`, not merely moves to another radius band;
  - no new dot/outline threshold oscillation;
  - added snapshot cost is negligible and mode-local.
  Focused bar from repo root:
  `python -m pytest tests/test_bubble_render_judder.py -q`

  Fixture A/B proof (product seam forced OFF, then ON in the same command):
  `python -m tools.visualizer_replay.bubble_judder --fixtures --clip broadband_noise --frozen --compare-tiny-assist --px-per-unit 300 --min-px 0.5`

  Real operator recordings (replace 300 with the Bubble content height in physical pixels if materially different):
  `python -m tools.visualizer_replay.bubble_judder --compare-tiny-assist --px-per-unit 300 --min-px 0.5`
- [ ] **B4. Physical acceptance on both displays with the same songs.** Explicitly judge tiny bubbles during breathing,
  strong hits, sustained loud sections, quiet settling, min/max size, pop/exit and CUSTOM viewport extremes. If the numbers are
  prettier but Bubble feels flatter/slower, reject the change.

Durable investigation notes: `Docs/Historical_Bugs/R-105_Bubble_Remaining_Small_Radius_Judder.md`.

---

## 2. Presentation stalls | shared-runtime cleanup, not Bubble retuning

DevCurve is currently visually much better and should remain a canary rather than be retuned to hide shared stalls.
The latest trace still contains real presentation holes while the 90 Hz logical clock stays healthy.

- [x] Latest combined trace (~434 s): 47 swap gaps >25 ms, max 249.4 ms. Classifier: **35 GUI-starved, 4 render,
  8 unattributed**. Fresh publish -> swap median 8.06 ms / p95 13.49 ms; logical cadence itself remains healthy.
- [x] GUI stall sampler continues to identify GUI-owned work rather than a general GIL-holder collapse (`sampler_late_ms`
  remains small in the supplied stacks).
- [x] Known owner still reproduced: FEEDS `replace_rows -> endResetModel()` appears in the new stall stacks.
- [ ] **P1. FEEDS model updates:** replace whole-model reset with bounded in-place row change / insert / remove notification so
  delegate reconstruction cannot freeze the GUI thread for refresh.
- [ ] **P2. Play-start audio capture:** move `pyaudio.PyAudio()` backend construction off the GUI thread while retaining a
  single bounded capture owner and current wake semantics.
- [ ] **P3. GC freeze:** measure `gc_policy.freeze_stable_generation` cadence/cost and either move/split/bound it at its owner
  or prove it is no longer a material stall in the next trace.
- [ ] **P4. Remaining native/unattributed gaps:** re-trace after P1-P3. Only investigate Qt/native swap/sync if the
  unattributed class survives; do not add a compositor timer or `frameSwapped -> requestUpdate()` loop.
- [ ] Regression bar: unattended two-display run, Bubble + DevCurve, no Settings/mouse interaction for the measurement
  window; compare >25 / >33 / >50 ms gaps and owner classes before/after.

---

## 3. Dormancy and lifecycle corrections | fix before adding many more modes

The new count-invariance guardrails are binding. The audit found the architecture is broadly lazy/retiring correctly, but two
hot-path smells and one shutdown smell need cleanup before the registry grows further.

- [ ] **L1. Sine heartbeat must be active-mode-only.** `process_heartbeat()` is called from the common logical tick and only
  checks heartbeat amount/engine, not `mode == sine_wave`. A Custom Sine heartbeat value can therefore keep querying energy,
  transient state and the scheduler while another mode is active. Gate/resolve it at active-mode ownership so inactive Sine
  contributes zero recurring work.
- [ ] **L2. Replace accumulating mode dispatches with one activation-resolved logical hook.** The common tick currently calls
  Bubble and DevCurve dispatch helpers unconditionally and relies on them to return when inactive. Cost is tiny today but grows
  linearly if copied for future modes. Resolve one optional active logical-step callable at mode activation; call that owner or
  `None`, not one branch/function per registered mode.
- [ ] **L3. Registry-scaled dormancy tests.** Repeated-switch/retirement and negative dormancy coverage must derive from the
  canonical Visualizer registry. Add a stress case where inactive modes carry deliberately expensive/non-default settings and
  assert they are not imported/constructed/advanced/queried/allocated. Target invariant: 100 registered modes + one active
  mode remains approximately the runtime cost of one active mode.
- [ ] **L4. Investigate the supplied shutdown barrier timeout.** At 12:37:36 the destruction barrier timed out with
  `qobjects={}`, `resources=[]`, `thread_work=[]`, `global_subscriptions=[]`, but Python owners still listed one each of
  `QuickDisplayUnit`, `QuickDisplayPresenter`, `QuickDisplayVisualizerOwner`. This looks like late/retained Python ownership,
  not surviving GPU/thread resources. Find the strong-reference/retirement ordering that keeps those three owners alive past
  the terminal barrier; fix at the consumer boundary and add a shutdown/recreation bar. Do not mask it by lengthening the
  timeout.
- [~] **L5. Contain and separate the intermittent CPython `memoryview.tp_clear` startup failure.** The exception text is
  `Exception ignored in tp_clear of: <class 'memoryview'>` / `BufferError: memoryview has 1 exported buffer`; the Python frame
  shown with it is not trustworthy attribution. CPython issue #110408 demonstrates the same unraisable with apparently random
  traceback frames under debugger/multiprocessing timing. The supplied 2026-10-05 run was explicitly launched with
  `--frame-trace` and wrote 2,245,565 trace records. Its writer unnecessarily wrapped each owned `bytes` batch in a
  `memoryview` and exported slices through buffered file I/O. Remove that diagnostic-side memoryview entirely while preserving
  rolling trace bytes/retention; regression coverage must prove the writer contains no `memoryview(` path and still crosses
  segment boundaries correctly. Shared-image-memory accounting in the same supplied run ended at `segments_live=0`,
  `close_failures=0`, `unlink_failures=0`, so do not accuse that transport without new evidence. **Physical acceptance remains
  open:** repeated startup with the same `--frame-trace` command must stop reproducing the unraisable/startup abort. If the
  exception appears in a run with no frame trace, split that as a second branch and record whether a Python debugger is attached
  and whether the lazy FEEDS `ProcessPoolExecutor` was admitted; do not hide the error, force GC, or disable workers globally.

Durable dormancy/lifecycle note: `Docs/Historical_Bugs/R-106_Visualizer_Dormancy_And_Shutdown_Ownership_Followup.md`.

---

## 4. Extruded Spectrum polish

- [x] **E1. Reflective wallpaper crossfade timing parity verified; no separate work.** Sphere and Extruded both call the
  same `BackdropEnvironment.textures(backdrop, logical_timestamp, backdrop_blend_s)` owner and both upload that returned
  `blend` directly to `uBackdropBlend`. The owner supplies one transition duration at the same incoming-photo boundary. There
  is therefore no mode-specific timing difference to fix unless a future live capture disproves the shared path.
- [ ] **E2. Extruded Spectrum shape editor.** Give Extruded the same usable node/notch/lane shape editor experience as normal
  Spectrum. The UI currently only says the shape follows Spectrum and exposes no editor. Preserve one shaping authority and
  preset ownership: editing Extruded must not silently mutate an unrelated authored Spectrum preset. Decide/land the resolved
  per-mode ownership before wiring the UI, then reuse `SpectrumShapeEditor` rather than forking it.
- [ ] **E3. Optional Extruded shadow.** Add an off-by-default shadow using the existing canonical shadow-direction system.
  It must follow the 3D bar footprint/orbit, remain tier/active-mode bounded, own no resources when disabled/inactive, and be
  measured before/after. Reuse shared Scene3D shadow primitives if they are ready; do not invent an Extruded-only shadow engine.
- [ ] Physical: both displays, overflow on/off, extreme tilt/turn, reflective and non-reflective presets, shadow directions,
  CUSTOM resize/reflow and transition into a new wallpaper.

---

## 5. GitHub Release / README animated WebPs | local-agent media work

Goal: small, high-quality animated WebPs showing the **real product renderer reacting to recorded audio**, not Guided Setup
previews. These are release/readme media only and never become startup/runtime assets.

- [ ] **M1. Transition WebPs.** Reuse/extend `tools/transition_contact_sheet.py --animate`, which already renders a real
  two-second/60-frame WebP. Batch every canonical transition and each curated preset/variant that materially changes its look;
  use representative source/destination photos and authored duration so real-time motion is honest.
- [ ] **M2. Visualizer WebPs.** Add a local capture harness that runs every canonical Visualizer mode through each curated
  preset while replaying one of the existing recorded songs through the production logical/capture/render path. Cycle long
  enough to show reaction rather than a static beauty shot; deterministic clip/preset selection makes regeneration repeatable.
- [ ] **M3. Encoding policy.** Capture losslessly/high quality first, then encode animated WebP with an adaptive size target
  (start around 720p, 24-30 fps, 6-8 s for Visualizers; transitions may stay ~2 s). Prefer quality over frame count, strip
  metadata, loop forever, and reduce dimensions/fps before crushing image quality. Keep generated media outside runtime QRCs
  and outside normal GODZIPs.
- [ ] **M4. Manifest/index.** Emit a simple release-media manifest mapping mode/transition + preset -> file, clip, duration,
  dimensions and source commit so README/release automation can regenerate only stale captures.

---

## 6. Test-input hygiene | finish the remaining stale-default sweep

The large preset/default decoupling slice is already mostly landed. Do not reopen completed work.

- [x] Visualizer replay/golden tests use frozen test-owned settings instead of mutable curated presets where behaviour is the
  subject.
- [x] Known Visualizer default-pin candidates reviewed; most were set-then-read round trips.
- [ ] Finish the **non-Visualizer** `tools/default_pin_scan.py` candidates. Only change assertions that pin an unset canonical
  default; explicit payload round trips and tests whose subject really is the defaults/preset machinery stay as-is.
- [ ] Reconcile the two stale reds noted previously: Foundry button wording must not be pinned; media I/O starvation stub must
  follow the controller's current work-loop entry point.

---

## 7. S19 | finish Voxel Sphere promotion

- [ ] Prove which technical controls actually change Sphere's five consumed analysis seams; expose no dead sliders.
- [ ] Replace hidden whole-Spectrum technical-profile borrowing with Sphere-owned descriptor/capability metadata while
  preserving missing-key compatibility with today's resolved behaviour.
- [ ] Move Sphere's per-frame values into the shared uniform block instead of ~60 individual uniform sets across two programs.
- [ ] Finish shared Scene3D lifecycle/dormancy migration and delete superseded Sphere-local low-level plumbing after acceptance.
- [ ] Physical/golden acceptance: behavioural vocabulary preserved or stronger; visual parity is a floor, not a ceiling;
  Mirror Ball / Mirror Cubes, tier AA, overflow and wallpaper reflection on bright/dark images and both displays.

---

## 8. S17 / S18 / future 3D consumers

Only resume these after the immediate Bubble/shared-runtime/lifecycle work above is under control.

- [ ] **S17 remaining active-only scene features:** demanded normal/material/depth/history attachments, reusable real 3D
  shadows, GTAO only if justified, weighted blended OIT/depth-aware transparency, thickness/depth refraction, Fresnel,
  rough transmission and restrained dispersion. Every attachment exists only for an admitted consumer.
- [ ] **S18 primitives:** sprite/streak/ribbon particles over `CompactedPopulation`, collision/OIT where justified,
  lightning, then bounded half/quarter-res smoke/fog/fire volume work with advection/vorticity/depth raymarch/temporal
  reprojection. Measure each primitive independently before combinations.
- [ ] **Visualizer vertical order:** Reactive Particle Field -> Spectrum Terrain/Skyline/Tunnel -> Waveform Ribbon ->
  Deformable Blob Sphere -> Bubble Depth Field under Bubble Temporal Fidelity.
- [ ] Only after primitives are accepted: electrical storm terrain, smoke-lit voxel fracture, ember/dust destruction,
  refractive glass lit by bolts, volumetric shockwaves and photo-colour IBL combinations.

---

## Accepted baseline | do not reopen without evidence

- [x] Qt Quick is the sole presentation/scheduling authority; no QWidget/QPixmap runtime fallback, mixed presentation owner or
  `frameSwapped -> requestUpdate()` loop.
- [x] Strict OpenGL 4.6 Core / GLSL 460 shared Scene3D foundation, S1-S16 substrate, S17 material/light block, persistent mapped
  stream, compute seam, GPU population/indirect draw, bounded targets, bloom/motion blur/trails/photo reflection and gradual
  next-transition warm-up are baseline contracts.
- [x] S20 transition verticals (Page Curl, Disintegrate, Accordion Fold, Relief Rise, Cube Turn and existing transition set)
  are implementation-complete; remaining work there is physical acceptance or an evidence-backed defect, not another general
  transition expansion wave.
- [x] Packaging/debloat/QRC/timezone/WebEngine work is closed unless a measured regression reopens it. `PySide6.QtOpenGL`
  remains a required QtQuick binding dependency even though application source does not import it directly.
- [x] FEEDS parser isolation/durable artwork and Media/GSMTC query-context handle-churn fixes are durable baseline; P1 above is
  a separate GUI-model-update presentation stall.
- [x] Bubble's authored 90 Hz class, latest-wins publication, latency/elasticity/reaction/ghost/tail semantics and accepted
  amplitude are protected. Do not trade them away to make a graph look smoother.

---

## Cross-cutting acceptance

- [ ] **Dormancy/count invariance:** inactive effects own zero recurring work; only the active effect and the explicitly
  reserved next-transition warm-up may own effect-specific runtime preparation.
- [ ] **Performance:** count Python GL calls and measure CPU submit/GPU cost for new passes. Render-thread Python GL calls hold
  the GIL; visual quality is not permission to starve logical/presentation freshness.
- [ ] **Time:** no second simulation clock, catch-up queue or hidden timer. Visualizers use authored logical time; transition
  real-time rates use real seconds.
- [ ] **State:** touched GL state is fence-restored, including failure paths.
- [ ] **Memory:** new buffers/targets/volumes/history are active-consumer-owned, bounded and measured on both displays.
- [ ] **Settings:** canonical defaults/descriptor resolution happen before admission; renderers never read Settings directly.
- [ ] **Physical:** both displays, first use and warm use, mode/transition switching, CUSTOM resize/reflow, Play/Pause/Resume,
  real photos and representative music.

## Handoff rules

The supplied/latest GODZIP is the working-tree authority. Significant slices return a full-file superseding GODZIP, never a
partial patch. Omission from a GODZIP does not mean deletion. Do not include oversized generated media, recordings, frame traces,
build outputs or giant pre-existing assets/tests unless they are themselves the changed deliverable. GODZIP v2 manifests must be
produced/validated against `tools/godzip_foundry_core.py`: `.godzip/*` is reserved archive metadata and must never appear as a
repository replacement target in `files[]`; include `debris` explicitly even when empty. No environment-variable feature gates.
Rejected experiments are removed rather than retained as fallback architecture.
