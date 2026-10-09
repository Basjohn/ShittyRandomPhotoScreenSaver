# SRPSS | Current Plan

This is a **live work checklist**, not a checkpoint chronicle. The current extracted Godzip is the working-tree authority for archive handoffs; product requirements belong in `Spec.md`, subsystem contracts in `Docs/Contracts.md`, and concluded investigations in `Docs/Historical_Bugs/`. Source changes do not silently change authored presets or golden reaction behavior.

## 0. CURRENT OWNER | R169 TEST AUTHORITY REVIEW / 3D + TRANSITIONS NEXT

**Operator acceptance, 2026-10-09:** R167's repaired Spectrum source-routing physically restores BOTH ordinary and Rainbow Ghost in Spectrum 2D. Extruded Rainbow Ghost was separately accepted in R166. R166's four focused Windows test files passed before the routing correction; R167 was then physically accepted. The manifest-fixed R167 archive is the superseded source base. Do not reopen these visuals absent a new symptom.

**Latest four-chunk result bundle (2026-10-09):** 7,105 outcomes: 7,075 passed, 29 failed, one skipped. Chunk failures 9 / 1 / 15 / 4. R168 contains **test/fixture-only** updates addressing 28 failures attributable to newly introduced ghost parameters, optionally missing keys in operator-editable curated preset files, R160 mode-owned DSP, R163 transition claims, and R165 reveal ownership. No production source, renderer, presets, defaults, audio DSP or animation was changed. The operator subsequently ran R168's focused Windows selection: **187 passed in 169.78 seconds (2026-10-09)**. That confirms the selected test repairs on R168, not a full chunk or physical acceptance. `tools.test_durability_audit.audit_tests()` reported zero findings locally; Python compilation passed.

**One genuinely open quality gate:** `tests/test_visualizer_replay.py::test_current_reactivity_passes_fixed_floors[gradual_ramp__devcurve]` reported `output_flux=18.61387083343637` against existing floor `19.269285559818062`. The versioned replay fixture/golden resources are *not included* in the Godzip. R168 intentionally does NOT reseed/recalibrate/relax this floor, claim a Dev Curve regression, or change runtime dynamics. The operator reran this single Windows case and it **still fails** (2026-10-09); compare the actual fixture/reference and R160's independent Dev Curve pre-AGC feed before deciding whether the floor is stale or there is a genuine behavior regression. Do **not** restore unused Spectrum shaper dependencies as a purported fix. Preserve the floor and document evidence before any calibration decision.

**R160 DO-NOT-REVERT audio rule:** Exactly Spectrum, Extruded Spectrum and Shockwave Grid own Spectrum visual shaping (the shared descriptor is the authority). Bubble, Sphere, Sine, Oscilloscope and Dev Curve use the shared FFT/pre-AGC/transient analysis **without shaping**. Dev Curve's *independent layer shaper* is not the Spectrum shaper. Sphere's R150 `KeyError('Treble')` exposed the invalid historical dependency. R168 explicitly turns on shaping only in synthetic Spectrum-specific DSP fixtures, while Bubble/nonshaper fixtures assert it stays OFF. Retain the 176-frame quantified Bubble upstream temporal parity proof and the accepted musical response of all modes.

**NEXT TRANCHE, with the independent Dev Curve replay investigation explicitly tracked, no full chunks or builds:** feature work is **shared 3D primitives plus transitions** (not another general cleanup). Sequence below: reusable inactive-cost-neutral 3D foundations for the first transition consumers, Jigsaw Piece Flip, Volumetric Dissolve, VHS Distortion and Edge Bloom Reveal; then subsequent transitions and broader shared 3D features. See §2 and §4.

- [x] **R168 focused regression:** operator's Windows `.venv` selection completed, **187 passed**; no affected runtime source files changed in R168/R169.
- [ ] **Dev Curve replay:** one rerun confirmed the exact failure; inspect the real installed fixture, frozen test settings, reference metadata/history and Dev Curve independent output path. Do not recalibrate without evidence and never route Dev Curve through Spectrum shaping.
- [ ] **Next graphics readiness:** inspect the existing Scene3D, `CompactedPopulation`, material/transition owners and reusable card/particle paths **without enabling unused passes or duplicating the engine**. This short audit immediately precedes T1/T2 implementation.
- [ ] **T1–T4 as first transitions:** use exact locally stored mock references, retain legacy Block Puzzle Flip until the independently named Jigsaw successor is accepted, and avoid accidental feature scope creep.

---

## 0. Accepted state and immediate gate

**Accepted by the operator (2026-10-09):** R151 Steam-cache and Settings repairs (**106 focused Windows tests passed**); R150 Sphere analysis-only DSP isolation and Shockwave's intentionally authored Spectrum-shaped horizon (**96 focused tests passed**); both visualizer modes physically accepted. Earlier implemented/physically good visual and cache changes remain accepted unless an anomaly is reported. Ordinary transition desync **400 ms**, first-image startup **200 ms**. The earlier severe dual-display collapse recovered after a **Windows reboot**, not a proved SRPSS patch; its root cause remains unknown. Bubble's small-radius judder is **deferred watchlist-only**. Diagnostic frame-trace bins were confirmed restored by the operator; do not reopen R156 or request another diagnostic build on that basis.

The repository runs on **standard-GIL CPython 3.14.8**, NumPy 2.x and **PySide6/Qt 6.11.2**. The operator's existing `.venv` and cutover are accepted; do **not** repeat destructive version migrations. R160's capability-owned DSP design remains active and protected (§0). The R166/R167 2D and Extruded Rainbow Ghost implementation has operator physical acceptance; the R168 test-only repair is operator-verified by its 187-test focused Windows selection. R169 updates test-authority documentation and this live plan only. The detailed defect and accepted architecture live in `Docs/Historical_Bugs/R-167_Spectrum_2D_Ghost_Control_Source_Projection.md`, not a second pending checklist.

**R165 startup reveal:** Relative to R164, hold the coordinated retained widget/Visualizer reveal for another **300 ms after the existing readiness milestone**, then run its existing InOutCubic fade for **2,500 ms (1,800 + 700)**. Desktop wallpaper staging remains 1,300 ms, and ordinary transitions are unchanged. One Qt unified sequential animation timeline; no new timer, poller or owner. FEEDS queued/busy UX explicitly unchanged.

## 0A. Refresh/transition contention | targeted gate

- [ ] **R164 AUDIT / R163 REAL RUNTIME:** Operator's R163 log `logsbcd85cd4dd2.zip` is **19:53:39–19:58:42**, source head `bcd85cd4dd4348a08d28dd18501298479a8a56e1`; this is post-R163 evidence. The R163 focused Windows suite **112 passed**. FEEDS submitted 67 family jobs in the capture; the cross-family gate reported repeated waits/resumes, manual transitions delayed about 1–7 s, and one stale generation-0 UI callback was rejected at Settings retirement. Neither that rejected callback nor the existing source-anonymous gate messages proves a stranded FEEDS claim. R164 repairs the **proven code-level missing `False` GUI-dispatch result** in FEEDS, and adds event-only family-labeled queue/claim/transition durations without logging private source identities or adding timers. Check focused Windows tests and later attribution. Historical R-65/R-75/R-83/R-110 are the relevant ownership/fairness precedents. No new Historical Bug entry.
- [ ] **FEEDS QUEUED/BUSY CONTRACT / WORKER FAILURE:** The operator explicitly requires a refresh to show **busy as soon as the request is accepted, including queue time**. Never defer, suppress, or split the user-visible busy indicator merely because a job is waiting for family/transition admission. Independently audit worker-error paths that publish no normal `FeedRefreshResult` and may fail to clear busy after terminal failure; do not conflate queued work with a stranded claim. Preserve NEWS' startup-settlement barrier, 2.5-second source staggering, source backoff, retained cache content and event-driven dormancy.

- [ ] **R163 SHARED ADMISSION / WINDOWS GATE:** R161's FEEDS/transition gate now wakes only one waiting source when a transition ends and resumes the next after its GUI publication completes. Gmail's live fetch and Reddit's provider fetch join FEEDS under this event-driven admission, with manual Reddit intent preserved and source retirement/cancellation fenced. FEEDS startup/cache/artwork work stays covered. Test the gate and affected Gmail/Reddit/FEEDS/transition suites on Windows. No application builds or four-chunk suite. The six R161 transition-distribution failures were repaired as R162 fixture omissions and await operator test.
- [ ] **UNPROVEN SERVICES / NEXT EVIDENCE:** Steam, Weather, Friend Pulse, other services and Gmail/Reddit startup-cache readers remain outside cross-family claims. Do not attach until their worker, GUI publication and retirement/cancel paths have been audited and focused gates written. No shared refresh timer or scheduler migration. Check transition fairness and verify no post-transition stampede with a fresh dual-display operator trace after R163 focused acceptance.
- [x] **R160/R161 source-policy fixes preserved:** Descriptor-owned shaping and R161 focused fixture repairs are retained. R168 owns the newest 2026-10-09 chunk failures; do not reopen the former R160 gate or relax Bubble parity.

## 1. Frozen-product validation | operator execution only

- [ ] **BUILD-1 | OPERATOR ONLY:** Operator runs Build Runner / Nuitka / installer compilation for **Standard, Diagnostic, Media Center, and Reddit Helper** under Python 3.14 + MSVC, then supplies build logs, Nuitka reports and packaging/footprint results. **Agents must not execute builds themselves**, including trial, smoke, quick or background builds. Inspect source, improve build scripts and analyze supplied reports without launching compilation.
- [ ] **BUILD-2 | OPERATOR ONLY:** Operator launches frozen products, validates two-monitor startup/exit, transitions, real audio (Sphere + Shockwave already physically accepted on source), widgets, image cache/prefetch, handles/threads, and installer behavior. Provide exact operator-run steps if requested; agents do not launch long runtime acceptance or take physical acceptance on the operator's behalf.
- [ ] **BUILD-3 | REPORT-DRIVEN:** Fix only failures in the operator's submitted logs. Use **relevant focused tests** for changed code; do not run or request another four-chunk suite or product build without explicit operator direction. When the operator chooses to perform a final complete gate and accepts the frozen products, promote Python 3.14 as release authority and checkpoint/commit the baseline.

**Frozen-product update (operator accepted):** The fresh Standard and Media Center evidence bundles showed Ban Image compiled and consistent frozen Python/data/native inventories. Operator subsequently confirmed **Ban Image now works in the Standard SCR**, as it already did in Media Center and source. Close the missing-action investigation; preserve R153's build evidence receipts as release infrastructure. No speculative rebuild or runtime menu diagnostics.

**Preservation:** OpenBLAS one-thread before-NumPy import and Qt GUI image-pool thread retention remain binding footprint/churn improvements (R-99/R-97). Retain R144/R145 prefetch priority and cache-lock containment, bounded RAM and zero prefetch side-timers. New work must not recreate the previous Windows/DWM regression through speculative pacing changes.

## 1A. Settings callback burst reduction | focused acceptance

- [ ] **SETTINGS WARM PAGES:** R158 narrows deferred hidden-tab construction to Display and Transitions. Themes activate before UI creation; all other nonselected pages build on visit. Confirm focused Settings hydration, tab navigation, reset/import, theme and Display backend tests in Windows `.venv`; no builds or chonky suite.
- [ ] **CENTRAL OPENGL INVARIANT:** Only SettingsManager may repair retired backend/acceleration values. DisplayTab may not rewrite either key merely because it was opened. Verify seeded `software`/disabled-hardware values are repaired by the manager even when Display is never visited.

## 1A. Targeted overnight diagnostic follow-up | operator tests only

- [ ] **LIFECYCLE:** R154 removes the strong `QuickDisplayUnit` bound-method connection to `retirement_completed`, which the diagnostic referrer snapshots identified as the only outstanding Python owner on monitor topology/application exit. Run only `tests/test_qtquick_display_unit.py tests/test_runtime_destruction.py tests/test_terminal_runtime_destruction.py` on Windows; request no overnight rerun or builds. `Docs/Historical_Bugs/R-154_Quick_Display_Terminal_Callback_And_Sphere_Slot_Collision.md` has the evidence and constraints.
- [ ] **CROSS-DISPLAY MEDIA SHORTCUTS (R155):** Shortcut transport now chooses one live Media owner across the active Quick displays (focused one first), and Previous sends the Media model's canonical `previous` action. Await focused Windows shortcut tests and a quick physical check with the Media widget on the *other* display; do not start a new build solely for this gate.
- [ ] **DIAGNOSTIC PRESET ROOT (R155):** Frozen Diagnostic now uses exactly the same machine-wide `%ProgramData%\SRPSS\presets` curated and explicit override trees as Standard and Media Center. Old diagnostic-onefile curated copies are no longer read or migrated; R154's temporary read-only audit utility has been retired. Await focused Windows path tests; preserve actual authored ProgramData files unchanged.
- [ ] **Scope restriction:** The 90 Hz versus 60 Hz observation remains expressly **off limits**. With R168 focused tests passed and the separate Dev Curve floor explicitly still open, proceed to the shared 3D/transition tranche of §0/§2/§4; do not revive old runtime-performance investigations to delay it.

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


## 4. Shared 3D primitives | immediate foundation for T1/T2, expand after first-wave acceptance

Admit one measured, inactive-cost-neutral consumer at a time. **Before T1/T2**, inspect and reuse existing Scene3D resource ownership, `CompactedPopulation` and tested 3D flip/particle facilities so Jigsaw Piece Flip and Volumetric Dissolve do not grow parallel engines. This is architectural preparation only: do not pre-allocate or execute S17/S18 facilities with no active consumer.

After T1–T4 implementation and focused/physical acceptance, expand S17/S18 in independently measured slices. Bubble temporal fidelity remains binding. OpenGL 4.6 core remains the graphics API; no speculative Vulkan/QRhi backend migration or HDR.

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
- [ ] **Other lifecycle/long-duration metrics:** Reopen only for new operator-observed regressions. The specific R154 teardown retention and authored-preset-local inspection are tracked under §1A; unrelated frame-rate efficiency work is off limits.

## Execution and handoff guardrails

- No build/installer execution by agents. The **operator runs expensive builds** and provides results; the agent may review scripts, run bounded non-build static/focused tests where available and supply exact commands when asked.
- The operator also controls *when* to repeat the multi-thousand-test chunk suite. For a new change, return **only relevant focused tests**, never an automatic chonky rerun.
- PowerShell commands given to the operator must be **single-line, semicolon-separated, direct-copy commands** (with correct quoting and explicit `.venv\Scripts\python.exe`); no multi-line RUN SCRIPT assumptions.
- Preserve dormancy, Qt's presentation clock, latest-wins admission, no standby render loops, native GL ownership and exact per-mode authored musical reaction. No retired QWidget/QRhiWidget presenter or silent preset reseed.
- Significant archive handoffs return a **whole-file superseding Godzip**, manifest regenerated from final bytes and checked for SHA-256, sizes, statuses, CRC and payload membership. No partial patches; no unrelated assets/bulk logs inserted into normal Godzips.
- New transition/3D primitives remain event- or activation-owned, bounded and inert when unused. Targeted tests must use test-owned deterministic data, not operator-authored mutable presets as immutable expected values.
