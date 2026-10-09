# SRPSS | Current Plan

This is a **live work checklist**, not a checkpoint chronicle. The current extracted Godzip is the working-tree authority for archive handoffs; product requirements belong in `Spec.md`, subsystem contracts in `Docs/Contracts.md`, and concluded investigations in `Docs/Historical_Bugs/`. Source changes do not silently change authored presets or golden reaction behavior.

## 0. Accepted state and immediate gate

**Accepted by the operator (2026-10-09):** R151 Steam-cache and Settings repairs (**106 focused Windows tests passed**); R150 Sphere analysis-only DSP isolation and Shockwave's intentionally authored Spectrum-shaped horizon (**96 focused tests passed**); both visualizer modes physically accepted. Earlier implemented/physically good visual and cache changes remain accepted unless an anomaly is reported. Ordinary transition desync **400 ms**, first-image startup **200 ms**. The earlier severe dual-display collapse recovered after a **Windows reboot**, not a proved SRPSS patch; its root cause remains unknown. Bubble's small-radius judder is **deferred watchlist-only**.

The repository runs on **standard-GIL CPython 3.14.8**, NumPy 2.x and **PySide6/Qt 6.11.2**. `.venv` is already recreated and the Python 3.11 install was removed. Do **not** rerun the destructive cutover. The last supplied four-chunk run (on the **pre-R151** tree) had chunks 1–3 passing and a single R149 Steam final-publication collision in chunk 4; R151 corrected it and its affected 106-test group subsequently passed. **Do not imply that a new full-suite run passed.**

## 1. Frozen-product validation | operator execution only

- [ ] **BUILD-1 | OPERATOR ONLY:** Operator runs Build Runner / Nuitka / installer compilation for **Standard, Diagnostic, Media Center, and Reddit Helper** under Python 3.14 + MSVC, then supplies build logs, Nuitka reports and packaging/footprint results. **Agents must not execute builds themselves**, including trial, smoke, quick or background builds. Inspect source, improve build scripts and analyze supplied reports without launching compilation.
- [ ] **BUILD-2 | OPERATOR ONLY:** Operator launches frozen products, validates two-monitor startup/exit, transitions, real audio (Sphere + Shockwave already physically accepted on source), widgets, image cache/prefetch, handles/threads, and installer behavior. Provide exact operator-run steps if requested; agents do not launch long runtime acceptance or take physical acceptance on the operator's behalf.
- [ ] **BUILD-3 | REPORT-DRIVEN:** Fix only failures in the operator's submitted logs. Use **relevant focused tests** for changed code; do not run or request another four-chunk suite or product build without explicit operator direction. When the operator chooses to perform a final complete gate and accepts the frozen products, promote Python 3.14 as release authority and checkpoint/commit the baseline.

**Preservation:** OpenBLAS one-thread before-NumPy import and Qt GUI image-pool thread retention remain binding footprint/churn improvements (R-99/R-97). Retain R144/R145 prefetch priority and cache-lock containment, bounded RAM and zero prefetch side-timers. New work must not recreate the previous Windows/DWM regression through speculative pacing changes.

## 2. New transitions | implementation queue

These transition concepts are promoted into the active roadmap rather than left as distant-future backlog. The current
visual mocks are local-repo references only and should be preserved for implementation review:

- `F:\Programming\Apps\ShittyRandomPhotoScreenSaver\tmp\mocks\TBlockPuzzle.png` — clean-room jigsaw/puzzle-piece
  flip replacement concept.
- `F:\Programming\Apps\ShittyRandomPhotoScreenSaver\tmp\mocks\TVolu.png` — Volumetric Dissolve concept.
- `F:\Programming\Apps\ShittyRandomPhotoScreenSaver\tmp\mocks\TVHS.png` — VHS Distortion concept.
- `F:\Programming\Apps\ShittyRandomPhotoScreenSaver\tmp\mocks\TLens.png` — Liquid Lens concept.
- `F:\Programming\Apps\ShittyRandomPhotoScreenSaver\tmp\mocks\TMemb.png` — Membrane Turnover concept.
- `F:\Programming\Apps\ShittyRandomPhotoScreenSaver\tmp\mocks\TGroup.png` — grouped second-batch concepts in
  this fixed order: Surface Tension Merge, Edge Bloom Reveal, Chromatic Shear, Depth Card Cascade, Capillary Bloom.

The local mocks are design references, not fidelity prisons. They establish the intended visual family and order of attack.

- [ ] **T1. Jigsaw Piece Flip (clean-room Block Puzzle replacement).** Implement this as a **new** transition rather than
  mutating the existing Block Puzzle Flip implementation. The goal is the originally intended behavior: puzzle outlines draw or
  fade in, then one piece at a time flips from Top Left / Top Right / Bottom Left / Bottom Right / Random ordered starts /
  fully unordered piece order, each flipped piece carrying its own portion of the destination image and clearing its local puzzle
  outline once landed. Useful existing architecture: canonical transition registry, per-display transition gating, retained Quick
  presentation ownership, current transition timing/identity plumbing, and any reusable shared 3D card-flip mesh/math that does
  **not** drag in old Block Puzzle behavior. New useful architecture: a shared transition-piece layout generator plus bounded
  per-piece scheduling/order-planning helper so future tiled/card effects can reuse the same geometry/order substrate. Leave the
  legacy Block Puzzle Flip installed for now; remove it only after this clean-room successor is accepted and the operator chooses
  retirement timing.
- [ ] **T2. Volumetric Dissolve.** Use the mock as the target feeling: the outgoing image disintegrates into colored particles,
  mist and shallow volume while the incoming image resolves behind/through it. Useful existing architecture: Scene3D lifecycle,
  shared uniform/state ownership, retained presentation control, and any particle infrastructure admitted by the shared 3D
  primitives work. New useful architecture: bounded reduced-resolution smoke/fog volume support, color-carrying image emitters,
  depth-aware compositing/OIT where justified, and reusable transition-side particle emission masks.
- [ ] **T3. VHS Distortion.** Treat this as a deliberate stylized transition, not a joke/glitch throwaway: horizontal tearing,
  scanline interference, chroma drift, dropout bands and unstable tracking carrying the source toward the destination. Useful
  existing architecture: fullscreen material/post passes, transition registry/timing, retained Quick presentation authority and
  the current transition harness/capture path. New useful architecture: a reusable distortion/noise primitive set (scanline,
  dropout, luma wobble, chroma offset, line displacement) so VHS can ship cleanly without becoming a bespoke hard-coded pile.
- [ ] **T4. Edge Bloom Reveal.** Promote the grouped mock's second concept into the first-wave batch: strong edges from the
  destination image appear as luminous structural lines over the source, thicken, and fill into full image regions. Useful
  existing architecture: fullscreen shader passes, existing mask/reveal sequencing, transition registry and capture harness. New
  useful architecture: a shared edge/gradient-mask generation pass and controllable region-growth/fill helper that later reveal
  transitions can reuse.
- [ ] **T5. Liquid Lens.** The destination image is seen first through a moving/refractive lens that expands and distorts until
  it consumes the frame. Useful existing architecture: current transition timing/identity plumbing, fullscreen distortion passes,
  retained presentation authority. New useful architecture: shared restrained refraction/thickness/dispersion helpers from the
  3D primitives program, kept bounded and consumer-owned.
- [ ] **T6. Membrane Turnover.** A taut glossy sheet deforms, stretches and turns through itself to reveal the destination
  image. Useful existing architecture: any shared mesh deformation/card surface math admitted by Scene3D primitives plus current
  transition sequencing. New useful architecture: a reusable deformable-sheet or low-resolution transition mesh substrate rather
  than a one-off transition-only simulation.
- [ ] **T7. Surface Tension Merge.** Source and destination behave like two fluids separated by a moving meniscus boundary;
  rounded pools swell, merge and take territory. Useful existing architecture: fullscreen passes, mask/reveal sequencing,
  transition registry. New useful architecture: a shared organic-boundary/meniscus field helper that can also serve capillary or
  liquid-family effects.
- [ ] **T8. Chromatic Shear.** A clean prismatic transition where the source image splits into offset spectral layers and broad
  shear slices before reconverging as the destination. Useful existing architecture: fullscreen post/material passes and timing
  plumbing. New useful architecture: shared chromatic-channel displacement/spectral-slice helpers so the effect stays elegant
  rather than duplicating ad-hoc RGB math.
- [ ] **T9. Depth Card Cascade.** The outgoing image separates into a small number of large shallow-Z cards that tilt/slide past
  the viewer, exposing the destination behind them. Useful existing architecture: retained presentation authority, Scene3D
  lifecycle, per-display gating, and any shared flip/card primitive introduced by Jigsaw Piece Flip. New useful architecture: a
  reusable card/depth-layer primitive with stable ordering, shadows only where justified, and transition-owned parallax rather
  than bespoke transition-local geometry.
- [ ] **T10. Capillary Bloom.** The destination image spreads through the source like dye moving through wet fibres: branching
  tendrils, joins and bloom fronts, but the final destination image resolves cleanly. Useful existing architecture: fullscreen
  material passes, reveal/mask sequencing. New useful architecture: a shared organic propagation field / capillary-front helper,
  preferably compatible with Surface Tension Merge rather than an isolated solver.

Implementation order inside this tranche is deliberate: **Jigsaw Piece Flip, Volumetric Dissolve, VHS Distortion and Edge Bloom
Reveal first; then Liquid Lens, Membrane Turnover, Surface Tension Merge, Chromatic Shear, Depth Card Cascade and Capillary
Bloom.**

---


## 3. Release / README media production

The capture/encode/manifest tool and its focused smoke proof are implemented in the working tree, awaiting checkpoint and
full catalogue output. Release/readme media stays outside runtime QRCs and normal GODZIPs. `Docs/Reference/Release_Media.md`
owns the tool's registry, source-attribution, capture and encoding contract.

- [ ] **RM1. Land the tool and generate transition media.** Review/checkpoint `tools/release_media.py` and its focused tests,
  then capture every admitted canonical registry identity plus meaningful curated appearance variants on a stable source tree.
  **Current transition-WebP source/size directive (local paths, not bundled):** Every transition WebP must be composed
  from combinations of the following FOUR operator-owned scene originals (supersedes the former Paper1/Paper2 pair):
  `F:\Programming\Apps\ShittyRandomPhotoScreenSaver\assets\usu\scenes\UsuScene1.png`,
  `F:\Programming\Apps\ShittyRandomPhotoScreenSaver\assets\usu\scenes\UsuScene2.png`,
  `F:\Programming\Apps\ShittyRandomPhotoScreenSaver\assets\usu\scenes\UsuScene3.png`,
  `F:\Programming\Apps\ShittyRandomPhotoScreenSaver\assets\usu\scenes\UsuScene4.png`.
  Keep a pleasant loop, approximate **480p** output (preserve aspect and derive width from approximately 480px-high
  source composition), high-quality WebP, and each individual WebP **strictly under 10,000,000 bytes** (10 MB,
  not 10 MiB). Aim close to this per-file cap where quality benefits, without padding or fabricating detail.
  Reduce fps/duration/dimensions carefully to obey the cap before sacrificing important edges or gradients.
  These four paths exist **only on the operator's Windows tree** and must be loaded at capture time, never
  invented, substituted, embedded in a normal Godzip, or assumed accessible in Linux/CI. Capture/encoding tool
  defaults and release registry must be adapted to this exact source/size directive when M1 is executed.
  Generate media only when the operator has supplied the four originals and selected a stable source tree. Do not fabricate or substitute unavailable local originals.
- [ ] **M2. Generate Visualizer media.** After the authoring/geometry source checkpoints are stable, capture every registered
  mode's curated presets with the canonical schema-2 recorded-music clip through the production replay/capture/render path.
- [ ] **M3. Inspect the generated catalogue.** Confirm motion/endpoints, photograph-backed Visualizers, loop/metadata/dimensions
  and release size limits; reduce dimensions/fps before lowering quality when needed. Retain the real outputs and manifest.
- [ ] **M4. Verify incremental regeneration.** Re-run the stable catalogue to prove unchanged items stay current and changed
  source/preset/clip inputs regenerate only affected/stale media. The source guard must refuse mixed-revision captures.

---


## 4. Shared 3D primitives | after priority transitions and their physical acceptance

Admit one measured, inactive-cost-neutral consumer at a time. Wait for the operator's frozen-product gate and first-wave transition results. Bubble temporal fidelity remains binding.

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

## 5. Optional acceptance and symptom-triggered watchlist

These items **do not block** the accepted source implementation or the next feature tranche. Reopen only when the operator reports a relevant symptom or explicitly requests the corresponding investigation.

- [ ] **Bubble small-radius judder (deferred):** Current physical reaction is good. No further filter, smoothing or cadence experiments without real-music, scale/DPR and renderer-radius evidence. Preserve Bubble's temporal golden. `Docs/Historical_Bugs/R-105_Bubble_Remaining_Small_Radius_Judder.md` owns previous failed approaches.
- [ ] **Dual-display reboot incident (historical):** If it returns, collect DWM/driver/Qt swap-state evidence **before reboot**, compare same workload, then investigate. Do not assert that R144/R145 patches caused the recovery. See R-134–R-145 history.
- [ ] **3D CUSTOM / Extruded authoring:** Previously implemented profile isolation, projected cage, hot-swap and Edit gestures are accepted. If an actual anomaly appears, use `Docs/Guides/Visualizer_Change_Checklist.md` and R-111–R-113; do not rewrite the source or resurrect a separate CUSTOM store. Extruded shadow rendering remains disabled (R-125–R-128). Historical Organs resemblance must never make mutable Organs presets a golden.
- [ ] **Lifecycle/long-duration metrics:** Investigate replacement-generation leak, unexpected driver GPU tail, Qt negative point-size warning, OpenBLAS/Qt thread re-creation, memory/handle slope or schema mismatch only upon reproducible operator logs. A separate old historical observation is not an active engineering task.

## Execution and handoff guardrails

- No build/installer execution by agents. The **operator runs expensive builds** and provides results; the agent may review scripts, run bounded non-build static/focused tests where available and supply exact commands when asked.
- The operator also controls *when* to repeat the multi-thousand-test chunk suite. For a new change, return **only relevant focused tests**, never an automatic chonky rerun.
- PowerShell commands given to the operator must be **single-line, semicolon-separated, direct-copy commands** (with correct quoting and explicit `.venv\Scripts\python.exe`); no multi-line RUN SCRIPT assumptions.
- Preserve dormancy, Qt's presentation clock, latest-wins admission, no standby render loops, native GL ownership and exact per-mode authored musical reaction. No retired QWidget/QRhiWidget presenter or silent preset reseed.
- Significant archive handoffs return a **whole-file superseding Godzip**, manifest regenerated from final bytes and checked for SHA-256, sizes, statuses, CRC and payload membership. No partial patches; no unrelated assets/bulk logs inserted into normal Godzips.
- New transition/3D primitives remain event- or activation-owned, bounded and inert when unused. Targeted tests must use test-owned deterministic data, not operator-authored mutable presets as immutable expected values.
