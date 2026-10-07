# SRPSS | Current Plan

This is the **live forward checklist**. It contains open work and acceptance debt only. Durable product truth belongs in
`Spec.md`, `Docs/Contracts.md`, Architecture/Guardrail/Guide/Reference documents, and useful failure history belongs in
`Docs/Historical_Bugs/`.

Work top-to-bottom unless the operator redirects a slice or a stated physical-evidence gate remains open.
Local checkouts make narrow validated checkpoints; archive handoffs return a superseding GODZIP under the handoff rules below.

---

## 1. Bubble tiny-radius judder | protect feel first

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

- [ ] **P2. Play-start audio capture.** Move expensive backend construction off the GUI thread while preserving one bounded
  capture owner and current wake/freshness semantics.
- [ ] **P4. Re-trace after P1-P3.** Investigate native/swap/sync ownership only if unattributed presentation holes survive.
  Do not add a compositor timer or `frameSwapped -> requestUpdate()` loop.
- [ ] **P5. Physical bar.** Unattended two-display Bubble + DevCurve run with no Settings/mouse interaction; compare
  >25 / >33 / >50 ms gaps and owner classes before/after.


---

## 3. Visualizer dormancy and retirement

The binding invariant is count-independent: registry growth must not add recurring work to an unrelated active mode.

- [~] **L4. Awaiting Validation / Logs: terminal owner release.** After P2, run normal MC stop and replacement-generation
  checks after the startup freeze. Confirm Python-owner release through the destruction barrier and the actual child process
  result. Investigate the observed diagnostic process exit of 1 despite a logged application exit of 0; the log is not the
  process result. The frozen signal-cycle repair has focused weakref/replacement proof; do not extend deadlines or force GC.

Durable invariants: `Docs/Guardrails/Performance_Optimization_Contract.md` P5 and
`Docs/Guardrails/Visualizer_Presentation.md` 1A.

---

## 3A. Visualizer CUSTOM geometry profiles | planar ↔ freeform 3D hot-swap

The current single Visualizer CUSTOM rectangle is the wrong semantic unit for hot-swapping between planar modes and
freeform 3D scenes: a placement/scale/viewport that suits one family can be actively bad for the other. Fix this **inside the
existing CUSTOM geometry authority**. Do not add parallel layout stores, per-mode X/Y keys or another editor/arranger.

The existing persistence key is already `(widget_id, display_identity, geometry_variant)` and Clock proves multiple variants
can coexist under one widget. Extend that same axis to Visualizer layout families. The split is by presentation behavior, not
by renderer dimensionality: a future 3D mode may deliberately choose planar geometry, and a future non-3D mode could opt into
a freeform profile if its interaction demands it.

- [ ] **G1. One owner, two saved poses.** Add registry/capability metadata selecting a Visualizer CUSTOM geometry profile.
  Canonical initial profiles are `planar` and `freeform_3d`. Spectrum, Oscilloscope, Sine Waves, Bubble and DevCurve use
  `planar`; Extruded Spectrum and Shockwave Grid use `freeform_3d`; Sphere joins `freeform_3d` as part of its promotion unless
  physical acceptance proves a different interaction contract. `QuickCustomLayoutOwner`, `CustomLayoutSession`,
  `custom_layout`, screen signatures, normalized rects and the existing commit/hydration path remain the **only** geometry
  authority. Do not create `custom_layout_2d`, `custom_layout_3d`, mode-owned rect settings or a second persistence service.
- [ ] **G2. Reuse `geometry_variant`, do not fork the schema.** Visualizer entries persist the complete existing
  `CustomLayoutEntry` independently under `planar` / `freeform_3d`: normalized outer rect plus the current Visualizer
  `size_payload`/viewport extent. No `custom_layout` version bump is justified merely to use a variant dimension the schema
  already supports. `geometry_variant_for_presentation()`/the Visualizer hydration seam must resolve the profile from the
  canonical mode descriptor rather than treating every non-Clock widget as `default`.
- [ ] **G3. Cross-family hot-swap happens while hidden.** A 2D↔freeform-3D mode activation resolves the target profile before
  reveal and applies its committed rect/viewport at the fully-faded hidden activation boundary. The retained Visualizer owner
  stays the same; no window/item/runtime reconstruction is added solely for geometry. A `planar -> planar` or
  `freeform_3d -> freeform_3d` switch is an exact geometry no-op. Never reveal one frame of the target using the outgoing
  family's rect and then jump.
- [ ] **G4. Missing-profile fallback must not clone the bad pose.** Existing installations have one legacy `default`
  Visualizer variant. Treat it as interpretation-only compatibility input for the family of the currently authored active mode;
  canonical writes use the new family variant. If the opposite family has no saved pose, seed it from that family's normal
  authored/fitted Visualizer baseline on the current display, **not** by copying the outgoing family's CUSTOM rectangle. This
  preserves the one pose the user actually had while avoiding a permanent 2D↔3D clone. Do not keep `default` as a second live
  authority after canonical family data exists.
- [ ] **G5. Edit/Arrange/direct gestures remain one transaction system.** Edit Layout, Settings Arrange and Alt + right
  drag / Alt + wheel operate on the **currently active profile only** and commit through the existing session/save seam.
  Restore Size affects only that active profile. Cross-display transfer moves only the active variant and must preserve the
  dormant sibling profile on both displays. No inactive profile may become an Edit obstacle, snap target or live retained item.
- [ ] **G6. Do not mutate profile identity mid-transaction.** Same-profile mode changes may remain geometry-neutral while Edit
  is open. A cross-profile mode change must not rewrite a `CustomLayoutSessionItem.source_key` underneath an active resize/move
  transaction. Direct gestures may finish through their existing single Save boundary before activation; full Edit/Arrange
  must finish or use one explicit event-bound handoff before the target profile activates. No poller, retry timer or second
  pending-geometry queue.
- [ ] **G7. Orbit/view state stays mode/preset state, not layout geometry.** W/A/S/D and Alt + left drag currently persist
  Extruded/Shockwave turn+tilt through `resolve_visualizer_view_orbit`: a curated preset becomes that mode's Custom snapshot;
  Custom writes back into that mode's own settings. Keep that separation. `freeform_3d` stores placement/size/viewport only;
  camera/view angle remains mode/preset-authored so two 3D modes or presets may share a good outer pose without sharing an
  angle. Sphere promotion should gain the appropriate orbit capability through its descriptor rather than smuggling view
  angles into geometry payloads.
- [ ] **G8. Layout slots round-trip both profiles.** Slots already capture the whole `custom_layout` root and the active
  Visualizer `mode`. Preserve that architecture: both Visualizer variants travel with the slot, mode state is restored before
  the fenced retained rebuild/hydration chooses its profile, and per-mode tuning/presets remain outside slot geometry. Loading
  a 2D-authored slot while a 3D mode is currently visible must restore the slot's planar mode + planar pose, and vice versa.
- [ ] **G9. Reset/repair semantics remain unambiguous.** Normal active-profile Save must never erase the sibling variant.
  Corrupt/invalid one-profile data falls back only for that profile. Whole-family authored-layout reset may clear both through
  the existing family reset authority; ordinary Restore Size is profile-local. Display-signature alias repair/canonicalization
  applies identically to both variants and must not duplicate them under stale monitor keys.
- [ ] **G10. Required automated bars.** Add focused coverage for startup hydration into each family; planar↔freeform hot-swap
  on one retained owner; same-family geometry no-op; missing-profile fallback; legacy `default` interpretation; Save/Cancel;
  direct Alt placement/resize; Edit/Arrange; Restore Size; cross-display transfer preserving the sibling; layout-slot replay;
  monitor-signature alias repair; and repeated 2D→3D→2D cycles with no geometry drift or viewport-scale compounding.
- [ ] **G11. Truthful 3D Edit framing without a second geometry authority.** The persisted `freeform_3d` rectangle remains
  the one CUSTOM **stage/viewport** geometry. Do not auto-resize/re-save it as the camera or orbit changes. For 3D Edit chrome,
  additionally expose the renderer's existing CPU-side projected scene extent as a read-only **content envelope**. Reuse the
  same bounds/reach authority that protects rendering (`extruded_reach`, `shockwave_reach`, and a Sphere/shared-Scene3D
  equivalent during promotion); do not implement a second QML projection or sample live audio geometry. The envelope updates
  only when geometry-affecting authored state changes (orbit, shape/depth, viewport/profile/settings), never on every music
  frame. Draw the saved stage boundary as secondary/faint technical chrome and the projected content envelope/pivot as the
  primary visual cue, so an edge-on scene no longer appears to occupy a giant lying rectangle. A generic spherical frame is
  **not** the default: Extruded, Shockwave and Sphere have different projected shapes. If a mode can cheaply provide a stable
  projected hull, Edit may render it; otherwise a projected bounding rect plus pivot is the fallback. Sphere may naturally use
  a circular/elliptical envelope because its scene actually warrants one.
- [ ] **G12. Preserve the good manipulation model.** The new 3D Edit chrome is presentation only; existing stage placement,
  uniform resize, viewport sizing, snapping, display transfer and persistence continue through `CustomLayoutSession` and the
  current geometry owner. The content envelope is not saved, cannot become a snap/collision authority, and cannot write X/Y or
  size by itself. Moving/scaling through any 3D-specific chrome must translate into the same current-session operations as the
  rectangular controls, so there is one resulting rect and one Save/Cancel/undo history. Do not make orbit-dependent bounds the
  persisted geometry or let an orbit silently move widgets around it.
- [ ] **G13. Alt controls work while Edit is active through the existing owners.** CUSTOM currently blocks native pointer
  routing so ordinary product input cannot leak through its overlay; do **not** weaken that safety boundary. Instead route
  semantic Alt gestures admitted on the selected freeform-3D Visualizer through Edit's retained overlay/session: Alt + left
  drag uses the existing mode/preset orbit resolver, Alt + right drag moves the current `CustomLayoutSessionItem`, and Alt +
  wheel performs the same uniform Visualizer resize on that session. No parallel drag math or second direct-gesture session.
  Orbit remains mode/preset-authored state and commits on the existing orbit-finish boundary; Edit Cancel reverts geometry but
  does not pretend camera state is geometry. Alt move/resize remain part of Edit and therefore obey its Save/Cancel/undo. Keep
  W/A/S/D orbit behavior consistent with the same resolver.
- [ ] **G14. Optional fit is explicit, glyph-first, never ambient.** If physical acceptance shows users still need a one-shot
  way to bring a wildly edge-on/oversized scene back into a useful stage, add an explicit Edit-only **Fit Scene** action that
  computes a proposed stage rect from the same projected-envelope authority and writes it only into the active working session.
  If admitted, expose it as its own compact **unique glyph button in Edit chrome**, with the same hover/visibility language as
  the other Edit affordances; do not bury it in a context menu. It must be undoable/cancellable and must never run merely
  because orbit, music or mode changed. Do not overload Restore Size unless its existing authored-baseline semantics remain
  exact.
- [ ] **G15. Framing/gesture regression bars.** Add focused tests proving projected-envelope updates are event-driven by
  view/shape/profile state rather than audio frames; the saved stage rect is invariant under orbit alone; 3D envelope/hull data
  cannot enter snapping/collision/persistence; Alt-left/right/wheel in Edit use the existing orbit/session owners; geometry
  Save/Cancel remains exact; and repeated front/edge/front Extruded plus wide/tilted Shockwave views do not rebuild the retained
  owner or accumulate viewport scale.
- [ ] **G16. Physical acceptance.** On both displays, deliberately author a compact/off-widget planar pose and a substantially
  different freeform-3D pose. Repeatedly hot-swap Spectrum/Bubble ↔ Extruded/Shockwave (and Sphere after promotion), including
  preset changes and orbiting. Each family must return exactly to its own useful placement/size without covering the wrong
  widgets, inheriting the other family's proportions, visible one-frame jumps, lost orbit state or Edit/Arrange fluidity. In
  Edit, compare front-facing and near-edge-on 3D views: the primary content envelope must remain visually honest while the saved
  stage remains stable, and Alt orbit/move/scale must feel identical to their non-Edit counterparts except for Edit's deliberate
  Save/Cancel semantics.

This slice is geometry-state separation plus truthful 3D Edit chrome. It is **not** permission to create orbit-driven persisted
geometry, change Visualizer reaction, renderer scaling semantics, authored stacking, Media adjacency, screen identity, CUSTOM
snapping, viewport math or the global Edit/Arrange transaction model.

---

## 4. 3D Visualizer authoring parity | Extruded Spectrum first

The 3D renderers are ahead of their Settings surfaces. Fix that as shared architecture rather than growing a second class of
Visualizer that looks richer but can only be authored through hidden Spectrum borrowing. **Shared controls means shared
implementation, not shared authored values.** Each participating mode owns its canonical persisted profile and each preset may
author a different profile.

- [ ] **E1. Registry-derived shared authoring substrate.** Replace the old hard-coded 2D-only technical/profile membership
  assumptions with descriptor/capability-driven ownership for the setting families a mode actually consumes. Extract/reuse the
  existing Spectrum shaper, shared bar appearance, Rainbow, response/technical and ghost authoring widgets/schema helpers; do
  not clone their math, validation or persistence logic into 3D builders. A mode that exposes a family owns its own namespace,
  defaults, Reset behavior and preset values. No Settings widget reads another mode's current preset as hidden mutable state.
- [ ] **E2. Extruded full Spectrum-facing controls.** Extruded must expose the meaningful Spectrum controls that drive the bars
  it actually renders: bar count/layout, fill + border colours/alpha, Rainbow controls where applicable, response/technical
  shaping, mirrored layout, the visual shape editor/notches/lane strengths, smoothing/falloff and ghost controls. Keep the
  existing 3D-only controls (Depth, Tilt, Turn, Colouring, Hue Drift, Gloss, Mirror Faces, floor Reflection, Smooth Edges and
  Allow Overflow). Do not expose dead controls merely for checkbox parity.
- [ ] **E3. Preset-local Extruded shapes are mandatory.** Every shipped or Custom Extruded preset may define a unique shaper
  profile: nodes, notches, lane strengths, mirrored state and the relevant response/layout values. Switching Spectrum presets
  must not alter Extruded, and switching Extruded presets must restore the complete Extruded-owned shape/profile. Reuse one
  `SpectrumShapeEditor`/shape-evaluation authority underneath; separate the stored per-mode/per-preset data. Include migration
  from today's borrowed Spectrum values so existing users do not get a visually arbitrary first run.
- [ ] **E4. Direct material axes, no material enum.** Do **not** resurrect an Extruded Finish/material selector. Gloss, colour,
  alpha/opacity, Mirror Faces and reflection are the authored axes. Make body opacity/alpha genuinely consumable so glassy or
  matte looks are combinations of direct controls rather than named material modes. If translucent solid bars require a shared
  depth-aware transparency/OIT facility, build that reusable Scene3D primitive rather than a transition-local or Extruded-only
  hack.
- [ ] **E5. Optional shadow.** Add an off-by-default shadow through the canonical shadow-direction system/shared Scene3D
  primitive. Disabled/inactive owns no target/pass/resource; measure active CPU/GPU cost before acceptance.
- [ ] **E6. Shockwave Grid parity follow-through.** Audit the other current standard 3D Visualizer with the same rule. Any
  Spectrum-derived bar/analysis family Shockwave actually consumes should be authorable in Shockwave and preset-local rather
  than silently changing when Spectrum changes; preserve its own Waves/Look controls. Do not manufacture controls for data the
  renderer does not consume.
- [ ] **E7. Preset/default/reset contract.** Shipped presets, user-authored Custom state, canonical defaults, runtime repair and
  Reset must all use the same per-mode owner. Shared UI components are allowed; shared mutable preset state is not. Add tests
  proving two Extruded presets can carry visibly different shapes/colours/response, and that Spectrum/Extruded/Shockwave preset
  switches cannot cross-mutate one another.
- [ ] **E8. Physical acceptance.** Both displays; overflow on/off; extreme orbit; reflective/non-reflective; opaque/translucent
  authored looks; unique preset shapes; Rainbow/colour edits; ghosting; shadow directions; CUSTOM resize/reflow; wallpaper
  transition. Verify the now-polished Mirror Faces remain free of vertical procedural grain on bright and dark photographs.

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

## 6. Run-matrix acceptance harness

- [ ] Add a small external **run-matrix harness** over the accepted `--exit-after` terminal-shutdown CLI. Cases are
  declarative and run sequentially by default, capture exit/fault/log artifact paths, and never own a second shutdown mechanism
  or force-kill the parent Foundry process.
- [ ] Use the harness for repeatable startup/teardown, diagnostic-flag, display and selected mode/effect acceptance matrices
  without adding product-runtime scheduling or another cadence owner.
- [ ] Keep matrix output compact and machine-readable enough for later agent comparison while preserving the underlying logs as
  the evidence source. A matrix runner coordinates existing product entry points; it does not become a new runtime authority.

---

## 7. Voxel Sphere promotion | settings parity-plus

Sphere's move from experimental/private plumbing to a standard Visualizer is also its authoring-surface graduation. Do not
promote the renderer while leaving it dependent on hidden Spectrum settings or a thinner Settings contract than older modes.

- [ ] **S1. Prove consumed controls first.** Inventory every analysis/reaction/material/presentation value Sphere actually
  consumes and prove which controls materially change those seams. Expose the useful controls; remove/avoid dead controls. Refresh the stale smooth/Magma/Water Sphere paragraph in
  `Docs/Contracts.md` against the current Voxel owners rather than restoring retired controls.
- [ ] **S2. Sphere-owned technical/analysis profile.** Replace hidden whole-Spectrum technical-profile borrowing with
  Sphere-owned descriptor/capability metadata and canonical persisted values, using the same registry-derived shared authoring
  substrate from §4. Preserve compatibility for missing persisted keys by seeding from the currently accepted behavior once,
  not by continuing a live dependency on Spectrum's active preset.
- [ ] **S3. Standard-mode Settings parity.** Sphere gets the normal per-mode guarantees: its own technical response controls
  where consumed, direct fill/edge colour **and alpha**, proper Rainbow controls (including speed/extent where meaningful),
  complete preset/Custom/default/Reset persistence, and lazy Settings-body ownership. Keep and organize its richer 3D-specific
  controls for voxel variation, lighting, mirror, particle intake/outtake, fragmentation, size/vocal response, rotation, shadow,
  depth shading, tracer/cel effects and overflow. Parity is a floor; Sphere-specific useful controls are the plus.
- [ ] **S4. Presets are self-contained authored looks.** Each Sphere preset must restore all values that materially define its
  look/reaction without depending on whichever Spectrum preset happens to be active. User-authored Custom survives preset
  round-trips. No preset may rely on a hidden lender value that is absent from its own resolved snapshot.
- [ ] **S5. Standard promotion semantics.** Remove the experimental-only product treatment once acceptance lands: standard
  registry/preset/reset behavior, normal enable/selection semantics and Guided Setup eligibility as appropriate, without losing
  lazy import/construction or inactive dormancy.
- [ ] **S6. Shared Scene3D migration.** Move Sphere per-frame values into the shared uniform block, finish shared
  Scene3D lifecycle/resource/dormancy migration, and remove superseded Sphere-local low-level plumbing after parity. Prefer new
  reusable primitives (transparency, shadows, refraction/lighting helpers) where they also benefit Extruded, Shockwave or the
  transition tranche.
- [ ] **S7. Physical/golden acceptance.** Behavioral vocabulary preserved or stronger; Mirror Ball / Mirror Cubes, tier AA,
  overflow, wallpaper reflection, opaque/translucent looks, Rainbow, particle/fragment extremes and distinct preset-owned
  reactions on bright/dark images and both displays. The promotion must not regress current Sphere goldens merely to satisfy a
  generic Settings layout.

---

## 8. Transition expansion tranche (immediately after Sphere)

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
