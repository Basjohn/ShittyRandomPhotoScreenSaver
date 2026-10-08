# SRPSS | Current Plan

Live work and outstanding acceptance only. Source and product contracts live in `Spec.md`, `Docs/Contracts.md`, maintained subsystem references and guardrails. Closed checkpoint narratives and rejected methods live in `Docs/Historical_Bugs/`; the VCS and GODZIP provenance keep chronology.

## 0. Active sequence | R130 (Windows validation pending)

**Baseline:** R128 superseding handoff, source HEAD `8448717216`. The operator's latest **focused Windows gate passed: 140/140, 23.14 s**. R127's four-chunk run failed and is not a R129 result. Sphere shared camera/orbit was physically accepted. Extruded cast shadows are **rejected and hard-disabled** (Settings greyed, renderer and Edit bounds gated); never reactivate through a preset or a fixture. The historically rejected casting mechanisms are documented in `Docs/Historical_Bugs/R-125_to_R-128_Extruded_Cast_Shadow_Failure.md`.

- [x] **M1. Sphere momentum implementation:** release after Alt+drag adds a finite ease-out to the same presentation/logical clock. The shader's permanent base rotation remains independent and never stops because a drag stops. Mouse re-grab, held-key takeover and preset rebase retire a pending tail. One final logical pose persists when release occurs; intermediate pose does not generate Settings writes. No timer, poll, second camera or animation owner.
- [x] **B1. Ban Image plus R130 hot-path repair:** Images menu Ban Image / Clear Image Bans use the existing per-display owner. Hashed sentinels remain the only persistent exclusion authority; the in-memory SHA-256 digest set is hydrated once when `.active` exists (zero-ban installations do not enumerate). `ImageQueue` retains the full source metadata catalogue but holds **only eligible images** in its active local/RSS/combined queues. Index once on ban-store attachment and incrementally on explicit bans or added sources; selection/peek/preview and queue wraparound never compute ban identities, touch the filesystem, iterate a banned list or retry over banned candidates. All-banned exhausts immediately. Clearing bans re-enables original metadata without source-provider refresh. Source loading and deliberate ban/clear actions may still cost O(source count); memory grows with ban count; no new cadence/Settings list/GPU work. Existing transactional advance, multi-display rejection and history safety remain in place. R130 local isolated non-Qt tests: 33 passed, 1 Qt-only deselected; Windows acceptance pending.
- [x] **D1. Documentation authority sweep (source complete, references audited):** move dated audit records to Historical Bugs, replace the R119–R128 live changelog with current status and focused historical mechanism, consolidate rejected shadow and current Sphere + Ban Image owners, correct stale links and version conflict. This box is not runtime acceptance evidence.
- [ ] **M2/B2/D2. Windows focused tests and hands-on behaviors:** run command below. Verify momentum smoothly decays without stopping base rotation, works under Alt+left mouse drag on both displays, never snaps on rapid re-grab/Settings preset change; Ban Image advances the invoking display and cannot recur on either display after restart, including remote URL cache changes and all-banned source exhaustion. Check context-menu admission, persistent reload, zero-ban fast path, large mostly-banned catalogue, and clear; verify active queue index refresh after banning in flight. Verify docs/source/test authority against actual outputs.
- [ ] **C5. Shared visual parity:** compare framed Visualizer stencil radius/chrome, global border width on Media/News/Reddit/Gmail/Steam/Weather, and physically accepted Spectrum/Organs top edges and reaction on D0/D1. Do not destabilize the accepted Bubble temporal response or the Organs preset to make an unrelated test pass.
- [ ] **GATE. 100% full Windows chunk gate:** after M2/B2/D2, run the unchanged destination four-chunk suite, classify/fix every genuine failure (not blanket golden regeneration or weakened assertions), repeat until *every chunk* passes. R127 log findings included Oscilloscope native smoke timeout and a Sphere golden mismatch; neither is accepted as expected failure. Preserve test durability and physical evidence.
- [ ] **PY1–PY6. Migrate canonical CPython 3.14 only after the green gate**, then repeat the exact same full chunk/real-GL/durability gate at 100%, verify complete dependency wheel/ABI and all frozen products, and compare startup/exit/memory. Never run competing 3.11/3.13/3.14 runtime authorities. See §10.
- [ ] **System/Scene3D audit and remaining product/transition roadmap:** §1–§9 remain queued; user-directed priorities and acceptance gates take precedence over newly proposed effects. Extruded shadow redesign is deferred to `Future_Work.md` until a new visual target is approved.

**Immediate focused Windows gate (from repository root):**

```powershell
python -m pytest tests/test_visualizer_view_orbit.py tests/test_image_bans.py tests/test_qtquick_context_menu.py tests/test_sphere_shared_scene3d_projection.py tests/test_qtquick_input_controller.py -q
```

**100% grouped gate (AFTER focused acceptance):**

```powershell
python tests/run_chunked.py --profile destination --chunks 4 --timeout-seconds 900 --log
```

---

## 1. Bubble tiny-radius judder | protect feel first. DEFER AND SKIP UNTIL LOCAL AGENT CAN MEASURE PRECISELY.

The accepted render-release envelope remains the baseline. The tiny-breath experiment was rejected by recorded-music and
fixture A/B evidence and removed completely; R-105 owns the failure mechanism. Small drawn radii follow each authored
target directly. There is no disabled candidate or fallback implementation.

- [~] **B1. Awaiting Validation / Logs: localize the remaining physical defect on the restored baseline.** Match the affected
  song passage to the canonical recording, mode/preset, CUSTOM viewport/uniform scale and display DPR. Identity-preserving
  replay found no alternating runs in the <=8px band at the supplied 300px projection. Establish the actual affected radius
  band and distinguish radius reversal from dot/outline representation chatter or shared delivery stalls before another repair.
- [ ] **B2. Evidence-led presentation repair.** Only after B1 reproduces the defect, fix the owning seam without changing audio,
  simulation gain or cadence. Pixel eligibility/bounds must use the actual renderer response-height projection plus scale/DPR,
  not logical viewport height. Retain per-clip frame-aligned radius differences, boundary crossings and extrema/excursion;
  verify isolated first response, attack, peak/turn timing and authored amplitude with existing golden/reactivity bars.
  Input-window first radius movement on already moving music is not proof of causal audio latency. No golden rewrite.
- [~] **B3. Awaiting Validation: physical acceptance on both displays.** Check the restored baseline and any subsequently admitted
  repair at quiet breathing, strong hits, sustained loud sections, min/max size, pop/exit and CUSTOM extremes. Reject a repair
  that feels flatter/slower even when the judder metric improves.

Until physical localization is available, proceed with the shared-runtime/lifecycle work below. Do not invent another Bubble filter.

The canonical local real-music corpus for B1-B3 is under `logs/visualizer_recordings/`: `balanced.jsonl`, `heavy1.jsonl`,
`quiet_intro.jsonl` and `quiet_intro2.jsonl`. These are operator-authored schema-2 captures and are intentionally local/large;
`*_vN` and `*_noevents` files are retained archived/derived takes, not additional canonical corpus members. The production
`recorded_clips()` selector excludes those suffixed takes automatically. Synthetic fixtures and committed goldens remain separate
negative-control/regression evidence and must not be substituted for the real-music corpus when B1-B3 require recorded music.

Focused automation:

```powershell
python -m pytest tests/test_bubble_render_judder.py tests/test_bubble_fidelity_report.py -q
python -m tools.visualizer_replay.bubble_judder --fixtures --clip broadband_noise --frozen --compare-release --px-per-unit 300 --min-px 0.5 --report logs/bubble_judder_acceptance/release_fixture.json
```

Real recordings:

```powershell
python -m tools.visualizer_replay.bubble_judder --compare-release --px-per-unit 300 --min-px 0.5 --report logs/bubble_judder_acceptance/release_recordings.json
```

Durable mechanism/negative controls: `Docs/Historical_Bugs/R-105_Bubble_Remaining_Small_Radius_Judder.md` and
`Docs/Guardrails/Bubble_Temporal_Fidelity.md`.

---

## 2. Shared presentation stalls

Treat Bubble/DevCurve as canaries for shared delivery. Do not retune a Visualizer to hide GUI/runtime stalls.

- [ ] **P4. Re-trace after P1-P3.** Investigate native/swap/sync ownership only if unattributed presentation holes survive.
  Do not add a compositor timer or `frameSwapped -> requestUpdate()` loop.
- [ ] **P5. Physical bar.** Unattended two-display Bubble + DevCurve run with no Settings/mouse interaction; compare
  >25 / >33 / >50 ms gaps and owner classes before/after.


---

## 3. Visualizer dormancy and retirement

The binding invariant is count-independent: registry growth must not add recurring work to an unrelated active mode.

- [~] **L4. Awaiting Validation / Logs: replacement-generation terminal owner release.** Ordinary and traced MC stop beyond
  startup freeze now match actual child exit 0 with current-session Qt/QML clean. Exercise replacement generations after
  freeze and confirm Python-owner release through the destruction barrier, not just a logged application exit. If the earlier
  diagnostic actual-exit-1/logged-exit-0 discrepancy recurs, preserve and investigate it. Keep the focused weakref/replacement
  proof; do not extend deadlines or force GC.

Durable invariants: `Docs/Guardrails/Performance_Optimization_Contract.md` P5 and
`Docs/Guardrails/Visualizer_Presentation.md` 1A.

---

## 3A. Visualizer CUSTOM geometry profiles | mode-compatible 3D stage hot-swap

The old `geometry_profile = planar | freeform_3d` abstraction was too coarse because it made one metadata value own both
interaction mechanics and persisted stage identity. Physical authoring proved Extruded, Shockwave and Sphere can all require
`freeform_3d` mechanics while needing radically different useful stage position/size. The repair keeps one CUSTOM geometry
SSOT but separates those concerns: `geometry_kind` selects mechanics; descriptor-owned `layout_profile` selects the existing
CUSTOM variant slot. Camera/material/preset state remains outside layout geometry. Durable incident: R-111.

- [~] **G17. IMPLEMENTED, AWAITING GROUPED/PHYSICAL: split mechanics from persisted layout identity.** Current canonical
  mapping is `planar` for all planar modes, `3d:extruded_spectrum`, `3d:shockwave_grid`, and `3d:sphere` for the three current
  freeform modes. These are compatibility-group IDs, not a mandate for one slot per mode: future modes may deliberately share
  a `layout_profile` only when their authored stage geometry is genuinely compatible. There is still one Visualizer widget, one
  `custom_layout` map, one `CustomLayoutSession`, one hydration path and one commit path. No per-mode X/Y settings or second
  3D layout store exist.
- [~] **G18. IMPLEMENTED, AWAITING GROUPED/PHYSICAL: hidden target-profile selection + one-way legacy migration.** A
  2D↔3D or 3D↔3D mode switch resolves the target `layout_profile` while the target is hidden and never lends outgoing geometry.
  A missing profile starts from the authored baseline. Legacy `default` / `freeform_3d` records are interpretation-only input: an
  explicitly authored/current claimant may promote one legacy record into its canonical profile, but sibling 3D modes never clone
  that ambiguous pose. Save, Cancel, display transfer, slot replay and alias merge preserve all sibling profiles.
- [~] **G19. IMPLEMENTED, AWAITING GROUPED/PHYSICAL: camera/view-pose SSOT is explicitly outside presets.** Extruded/Shockwave
  turn+tilt remain in canonical persistent mode-owned view settings (NOT presets), using their existing orbit publication path; Sphere keeps its own mode
  presentation contract. `layout_profile` stores only CUSTOM stage position/size/viewport intent. It must never serialize, reset,
  shadow or infer turn, tilt, camera, material, response or preset values. A complete visible 3D pose is the composition of the
  target layout profile and the target mode's own presentation state.
- [~] **G20. IMPLEMENTED, AWAITING PHYSICAL: projected 3D Edit bounds cage.** The flat projected-envelope rectangle is
  upgraded to derivative wireframe cage paint for freeform 3D modes: eight renderer-consistent projected vertices, twelve edges at
  ~90% opacity, and a white vector `N` with thin black outline drawn directly inside the projected world -Z north-face quad. Its four face corners own the full tilt/perspective deformation, not an independent 2D text rotation. The persisted stage rectangle
  remains visible as secondary chrome. Cage vertices/north marker are read-only paint derived from the renderer projection and
  may never become snapping, collision, Fit Scene, movement, resize or persistence authority. No second 3D render scene exists.
- [~] **G21. IMPLEMENTED, AWAITING GROUPED/PHYSICAL: remove one-publication geometry transaction mismatches.** Latest logs
  showed isolated `viz_geometry_mismatches` exactly at Edit Save / mode-profile transaction boundaries, not a continuing geometry
  corruption loop. Hidden profile switches now discard one unread outgoing snapshot after logical production is stopped; CUSTOM
  Save atomically drops an unread snapshot only if its presentation is stale; already-coherent snapshots and their protected
  edges remain untouched. No snapshot's immutable geometry is rewritten after composition. The bridge's normal
  stale-presentation rejection remains binding everywhere else. Regression coverage must prove these explicit transaction helpers
  do not increment mismatch count; the atomic comparison may drop a *stale* unread frame but never relabel a snapshot or discard a coherent one.

**R-113 follow-up grouped gate (2026-10-08):** previous R-113 operator test run 738 pass / 16 fail. Repair tracks: remove pose keys from seven shipped Extruded/Shockwave preset JSON snapshots; keep strict planar scaling while allowing independent 3D stage/world ratios in both Edit and Arrange; preserve logical viewport during freeform-3D stage growth so mesh scales; normalize cage projection into QML-compatible lists; repair missing-Edit-owner display transfer; correct obsolete empty-source / graphite test oracles. **Windows test and physical recheck still required; no G17–G21 closure yet.**

Existing accepted Edit ergonomics remain binding: neutral graphite chrome, HIDE / SHOW wedge, the compact Orbit glyph beside
Restore, Alt-left orbit, Alt-right move, signed Alt-wheel scale, Fit Scene as an explicit undoable action, and renderer-derived
content framing that performs no continuing work outside selected Edit. G14 and G15 remain accepted.

- [x] **G14. ACCEPTED: Optional fit is explicit, glyph-first, never ambient.** Fit Scene uses the renderer-derived envelope only
  when explicitly invoked inside Edit; it is undoable/cancellable and never runs merely because orbit, music or mode changed.
- [x] **G15. ACCEPTED: native/Edit gestures and graphite chrome.** Signed wheel movement, reversible scaling, Alt-right move,
  Orbit, overflow ingress, Save/Cancel, HIDE / SHOW and stable bottom-left parent glyph placement are physically accepted.
  Arrange must use the selected mode's layout profile through the same committed resolver, preserve dormant siblings,
  and never write profile state into presets. Edit must refuse cross-profile mode switches until Save/Cancel,
  preserve sibling profiles when committing, and not mutate preset selection when view-orbit changes.
- [~] **G16. REOPENED/EXPANDED PHYSICAL ACCEPTANCE FOR MODE-SCOPED PROFILES.** On both displays deliberately author
  obviously incompatible poses for Spectrum/Bubble, Extruded, Shockwave and Sphere. Give the 3D modes different position/size
  and, where supported, different turn/tilt through their persistent mode view/orbit authority, never presets. Hammer 2D↔3D and 3D↔3D hot-swaps,
  curated↔Custom, Save/Cancel, Settings reinit, display transfer and a layout-slot round trip. Every target must restore its exact
  own stage profile plus its independent camera state with no outgoing-pose borrowing, one-frame jumps, profile loss or new
  `viz_geometry_mismatches`. Confirm the projected cage follows orbit/perspective, the `N` remains readable/useful, and neither
  cage nor projected content envelope perturbs the persisted stage.


---

## 4. 3D Visualizer authoring parity | Extruded and Shockwave

Each mode owns its complete technical, source-shaper,
bar/ghost families where consumed, smoothing and bar-height stabilization; shared UI/evaluation remains one implementation.
Curated snapshots are explicit and self-contained, and the before-default-fill migration preserves old borrowed values once.
Direct fill-swatch and independent border-swatch alpha are the live render contract. Cast shadows are *not* admitted; their greyed Settings values remain only for persisted compatibility. The source/history owner is `Docs/Historical_Bugs/R-125_to_R-128_Extruded_Cast_Shadow_Failure.md`.

- [ ] **E8. Physical historical-response and material parity:** Compare Extruded's mode-owned effective response and retained Custom state with the accepted Organs-derived historical reaction profile without re-reading mutable Organs as a golden. Verify Preset 1 → Custom, all curated finishes, sensitivity/AGC/audio block/ghost/floor response, opaque versus translucent fill and independent edge alpha, Mirror Faces under bright/dark wallpaper, Dynamic Floor, Edit/CUSTOM scale and both display orientations. Do not re-enable or test for visible Extruded cast-shadow pixels. Settings Shape keeps Mirrored Layout and Shape Editor together. Source repair and migration background live in `Docs/Historical_Bugs/R-112_Extruded_Historical_Response_Must_Not_Use_Mutable_Organs_Oracle.md`.

---

## 5. GitHub Release / README animated WebPs

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
  This is future media work only; do not develop/capture transitions before the full test gate and Python migration.
- [ ] **M2. Generate Visualizer media.** After the authoring/geometry source checkpoints are stable, capture every registered
  mode's curated presets with the canonical schema-2 recorded-music clip through the production replay/capture/render path.
- [ ] **M3. Inspect the generated catalogue.** Confirm motion/endpoints, photograph-backed Visualizers, loop/metadata/dimensions
  and release size limits; reduce dimensions/fps before lowering quality when needed. Retain the real outputs and manifest.
- [ ] **M4. Verify incremental regeneration.** Re-run the stable catalogue to prove unchanged items stay current and changed
  source/preset/clip inputs regenerate only affected/stale media. The source guard must refuse mixed-revision captures.

---

## 6. Run-matrix acceptance harness

- [~] **Awaiting Validation / Logs: remaining configuration/replacement cases.** The short MC and ordinary/traced 55-second
  post-freeze cases passed actual process/current-session checks; evidence is under `logs/run_matrix/mc_rss_fixed_20261007/`
  and `logs/run_matrix/mc_after_freeze_20261007/`. Repeat the relevant cases after the final authoring/geometry checkpoints
  and operator-selected display/mode/effect configurations, including L4 replacement generations. The harness exercises saved
  settings; it cannot substitute interactive single-display evidence for P5's unattended two-display canary run.

The declarative input, evidence scoping and source attribution contract lives in
`Docs/Reference/Harness_Index.md` → Bounded self-terminating RUN sessions. Raw logs remain the evidence authority.

---

## 7. Voxel Sphere promotion | settings parity-plus

Sphere's move from experimental/private plumbing to a standard Visualizer is also its authoring-surface graduation. Do not
promote the renderer while leaving it dependent on hidden Spectrum settings or a thinner Settings contract than older modes.

The consumed analysis inventory, mode-owned technical profile, selected frequency splits, direct RGBA alpha and Rainbow
speed/extent have source, PCM and real-GL proof. Startup, legacy Custom-cache and SST promotion preserve RAW Spectrum values
once before defaults, while curated Sphere looks restore complete owned snapshots. `Docs/Reference/Sphere_Visualizer.md`
owns current controls and migration details. Remaining product admission and acceptance:

- [x] **S5. COMPLETE: standard promotion semantics.** Sphere presents as **Voxel Sphere** rather than an Experimental product, uses the registry's normal Guided Setup offer path, and retains the same canonical `mode_activation`, preset catalogue, Custom-cache and Reset owners proven by E7. The promotion gate ran in the subsequent Windows 203-test 3D/S5 cluster; its sole failure was the now-obsolete Extruded preset-shape inequality oracle after the operator deliberately requested one Organs-derived Extruded shape. All S5-specific activation/onboarding/dormancy coverage passed. Lazy Settings/capture/runtime/renderer imports, prepared reveal, independent disablement and inactive resource dormancy remain unchanged.
- [~] **S6. Awaiting Validation: loaded-desktop GPU tail.** The shared per-frame uniform block, ring/resource/lifecycle
  migration has focused driver, retirement and unchanged-golden proof. Investigate the measured whole-host GPU p90 increase
  under actual loaded display use before claiming performance neutrality; the lower CPU submit/GL-call count and near-neutral
  isolated draw time do not close that gate. `Docs/Reference/Sphere_Visualizer.md` owns the scoped measurements.
- [~] **S7. Awaiting Validation: physical/golden acceptance.** Behavioral vocabulary preserved or stronger; Mirror Ball / Mirror Cubes, tier AA,
  overflow, wallpaper reflection, opaque/translucent looks, Rainbow, particle/fragment extremes and distinct preset-owned
  reactions on bright/dark images and both displays. The promotion must not regress current Sphere goldens merely to satisfy a
  generic Settings layout.

---

## 8. Transition expansion tranche (after test gate and interpreter migration)

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

## 9. Shared 3D primitives and next consumers

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

## 10. Queued side quest: canonical CPython 3.14 migration

**Not started.** Start only after Momentum, Ban Image and the documentation sweep are validated; the complete
pre-migration four-chunk gate is 100% green, the remedial work is committed, and a clean pre-migration checkpoint exists. Once admitted, this operator-directed migration takes precedence
over new feature expansion. Physical acceptance cannot be inferred from test results. Git owns rollback; an untenable
migration is reverted rather than retained as competing Python authorities or compatibility scaffolding.

- [ ] **PY1. Admission and baseline.** Close the prerequisite remedial gates; run the full relevant chunky/durability gate,
  commit/push a clean pre-migration checkpoint, and retain exact interpreter/dependency/tool versions, product artifact sizes
  and bounded startup/exit evidence for comparison.
- [ ] **PY2. Exact dependency audit.** Verify current stable standard-GIL CPython 3.14 x64 and the complete requirements/build
  dependency set against Windows cp314 wheels. Preserve PySide6/Qt 6.11.2 and compatible pins; change only incompatible
  dependencies and required coupled packages. Identify exact blockers before considering a workaround.
- [ ] **PY3. One build authority and immutable inputs.** Migrate every real bootstrap/venv/build/helper/prerequisite path to
  3.14; remove 3.11 fallback behavior. Detect and clearly rebuild/refuse an old-interpreter root `.venv`. Reuse a bounded local
  immutable wheel/input cache keyed by exact Python/ABI, Windows architecture and locked dependencies; keep large inputs out
  of normal Git. Checkpoint the coherent new authority early. End users still require no installed Python.
- [ ] **PY4. NumPy 2 and native-contract migration.** Audit removed APIs, dtype/ABI/buffer/contiguity/structured-layout assumptions
  in production and tests, especially audio, GL uploads, Scene3D packing and transition geometry. Preserve numerical/rendering
  behavior, goldens, cadence and lifecycle; fix at the owning boundary.
- [ ] **PY5. Complete acceptance.** Create a clean environment using canonical scripts; install the complete locked dependency
  set; pass the full test suite/chonky chunks, durability/policy, Visualizer/audio/NumPy and real-GL/Scene3D gates. Build and
  launch Standard, Diagnostic, Media Center and Reddit/helper frozen products without system-Python participation. Verify
  startup/exit/multiprocessing and compare sizes plus obvious startup/runtime regressions with PY1. Record useful checkpoints.
- [ ] **PY6. Accepted baseline and cleanup.** Record exact known-good Python/dependency/build-tool versions in the canonical
  build docs; leave 3.11 only as historical context. If fundamentally incompatible, revert the migration to PY1 and retain
  the exact blocker evidence instead of dead fallback code.

---

## Cross-cutting acceptance for every slice

- [ ] **Dormancy/count invariance:** inactive registry entries add no recurring runtime work; only admitted owners may prepare,
  with the documented single reserved-next-transition exception.
- [ ] **Performance:** measure CPU submit/GPU cost and Python GL-call pressure for new render passes.
- [ ] **Time:** no second simulation clock, catch-up queue or hidden recurring timer.
- [ ] **State:** touched GL state is fence-restored on success and failure.
- [ ] **Memory:** targets/buffers/volumes/history are bounded, consumer-owned and retired deterministically.
- [ ] **Settings:** canonical defaults/descriptor resolution happen before admission; renderers do not read Settings per frame.
- [ ] **3D authoring parity:** shared editor/schema/runtime helpers may be reused across modes, but authored values, Custom
  state and preset snapshots are per-mode. A 3D mode must not silently inherit another mode's currently selected preset merely
  because it shares analysis/render machinery. Expose only settings with a proven consumer; richer 3D modes may exceed 2D
  parity where their renderer has meaningful extra axes.
- [ ] **Test authority:** the blocking durability audit stays green for touched areas. Tests derive defaults, preset/catalog
  membership and other mutable authorities from their current canonical owner unless an exact literal is itself the contract.
  Advisory pin/source-copy queues are review aids, not automatic project debt.
- [ ] **Unattended evidence:** do not skip, xfail or deselect a test merely because it exposes a window. Preserve the evidence and
  move it offscreen/non-intrusive where the same native Qt/GL/input contract can be retained. Keep `Docs/TestSuite.md` aligned
  with material test-infrastructure changes.
- [ ] **Physical:** both displays, cold/warm use, switching, CUSTOM, Play/Pause/Resume, real photos and representative music.

## Handoff rules

For remote/archive handoffs, the supplied/latest GODZIP is the working-tree authority. Significant handed-off slices return a
full-file superseding GODZIP, never a partial patch. Do not include oversized generated media, recordings, frame traces, build
outputs or unchanged giant assets/tests. GODZIP manifests are produced/validated with `tools/godzip_foundry_core.py`; every
generated archive also carries `.godzip/workflow.md` with transfer rules for that archive-handoff workflow. Those transfer rules
do **not** govern Codex, Claude or another local-repository application that is already operating directly in the checked-out
repo; local repo agents follow the operator's workspace/repository instructions and should not switch themselves into GODZIP
mode merely because `.godzip/workflow.md` exists. `.godzip/*` is archive metadata, never a repository replacement target, and
`ui/assets/` is a hard normal-GODZIP exclusion rather than optional handoff payload. No environment-variable feature gates.
Rejected experiments are removed rather than retained as fallback architecture.

