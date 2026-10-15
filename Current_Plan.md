# SRPSS | Current Plan

Live actionable work only. Exact current source is authority; `Spec.md` and `Docs/Contracts.md` own durable behavior,
subsystem references own technical detail, and source control / `Docs/Historical_Bugs/` retain concluded investigations.
Do not copy this checklist into another plan. Close landed slices here; retain only their genuinely open acceptance debt.

## 0. Execution order and accepted baseline

**Current execution order (operator-authorized):** (1) finish Neon Lake visual corrections, real-music
reactivity investigation and any justified improvements, then deliver **six disposable experimental presets** and
close its V4A gate; (2) migrate **original Bubble** with proven response/render parity and close the entire Visualizer
Settings-spec migration; (3) prove the reusable **framed-camera, attachment/depth, transparent-compositing, shadow
and visually justified optics primitives** in §4A; (4) implement Extruded Bubble on those already-proven facilities.
Release media/cleanup (§3), unrelated deferred graphics, and operator builds are not implicit blockers or reasons to
start Extruded Bubble early. Continue between green checkpoints without routine stops, but do not skip each stage's
specific physical or recorded-audio evidence. Use reviewed Luna xHigh/Max or Sol 6.1 Medium agents for bounded work;
reserve one High Astra agent for visual parity audits after very significant work.

**Accepted by the operator, 2026-10-12:** Oscilloscope is fully validated; all landed transitions and Foundry tool buttons
are accepted. Dev Curve currently has no observed issue; its earlier replay-floor investigation is closed. Do not reopen
these as pending acceptance or tune their response. Existing Spectrum/Rainbow Ghost, Sphere and source-routing acceptance
stands. Monitor power/wake is a detailed **nonblocking watchlist** (§5), not a reason to request a costly diagnostic build.

**Protected execution rules:** preserve canonical Settings, capability, CUSTOM, render and lifecycle owners; no dormant
polling, new per-frame work, silent non-network fallback or duplicate runtime. Spectrum shaping remains descriptor-owned
(Spectrum, Extruded Spectrum, Shockwave only); Bubble temporal fidelity is binding. Preserve existing startup/reveal and
transition timings. Test the smallest production seam that can falsify the changed contract; no full suite or product
build unless the operator requests it. After each green slice: inspect diff, narrow commit, push, refresh this checklist.
Preserve unrelated local/user work. Agents do not run Nuitka, Build Runner or installers.

## 1. Saver-wide physical display selection | Source checkpoint complete

Physical selection, Settings/draft/import/reset authoring and zero-live-display lifecycle are implemented. Durable
behavior lives in `Docs/Contracts.md` → Geometry / CUSTOM; regression inventory lives in `Docs/TestSuite.md`.
Physical power-cycle observation remains only the nonblocking §5 watchlist.

## 2. FEEDS queued/busy and terminal failure | Source checkpoint complete

Terminal failure, queued NEWS settlement, cache-first admission and text/artwork bundle ownership are implemented at
existing owners. Provider backoff remains an absolute floor for manual requests. Durable behavior and regression inventory
live in `Docs/Reference/Feeds.md` and `Docs/TestSuite.md`; real contention/fairness remains only the §5 Awaiting Logs item.

## 2A. Visualizer spec migration | finish Neon Lake, then original Bubble V5

Oscilloscope, Sine Waves, Dev Curve, Extruded Spectrum, Spectrum and Voxel Sphere are migrated.
Neon Lake (`shockwave_grid`) now has its spec-owned Settings, framed camera, authored terrain,
Vertices/Glass parity, one retained Preset 1 plus Custom, and the simplified three-style control
catalog. The operator has confirmed no Settings crashes in the latest build and accepts the
main mountain skyline, star-glow appearance and broad terrain continuity. Starscape Beat's
entry floor was subsequently eased to **0.224** using the existing onset/clock authority,
three stars and gentle decay unchanged; visual acceptance remains open. No new DSP, timers or polling.

**Neon Lake open work after operator image review (2026-10-14):** The new screenshot
confirms the existing mountain skyline and lake outline are good, Settings no longer crashes,
and Starscape Beat is visible. Do **not** claim the distant horizon or musical glow
reactivity accepted merely because the previous source tests passed. Use the **current
operator-authored Preset 1** as the present visual comparison, not a protected or fixed
artistic artifact. It may be freely edited by the operator at any time; approved schema
migrations preserve the latest authored choices unless the operator explicitly requests a
change. Never restore an older copy or pin artistic values/hashes as test expectations.

**Operator size-specific correction (2026-10-14; do not conflate these failures):**
- **LARGE card sizes:** The only disappointingly weak glows are **Starscape/Starfield**
  (including at maximum Star Glow) and the **audio-driven Moon/Sun halo pulse**. The ordinary
  Moon/Sun halo appearance is already good; its *reactive modulation* lacks perceptible gain.
  Other terrain/shore/sky glow is **not** generally underpowered at large sizes. Correct only
  the relevant star brightness/shape and celestial reaction, never global glow gain.
- **SMALL card sizes:** Vertices and bloom **crowd and compound** as the rendering is condensed.
  Nearby vertex marks visually merge, while overlapping glow footprints obscure detail. This
  is **excessive screen-space overlap/density**, not a request for brighter glow or more points.
  Adapt effective vertex spacing/LOD, marker size and bloom footprint/coverage to physical
  card pixels and DPR, keeping independent features distinguishable and the terrain appearance
  coherent. Do not indiscriminately increase intensity at small sizes.

The false distant oval is removed; shoreline emission belongs only to authored lake
boundaries. Whole-window/card point-width amplification is corrected. The operator
clarified that oval removal alone does not close the horizon gate:
- [ ] **Continuous distant horizon and low celestial-body occlusion.** Continue the same
  real terrain to its visible horizon, keep distant land coverage/depth while fading
  detail, preserve the accepted mountain/lake contours, and inspect low/default/high
  angle, zoom, aspect and both turn limits. Low Moon/Sun must be partially obscured
  by that land boundary. Require actual GPU pixels and the single Astra visual audit.
- [~] **Moon halo integration, idle presence and non-tube shape — Awaiting Validation.**
  The current Moon texture/body is promising but still reads as an isolated sphere rather
  than a luminous part of Neon Lake's visual language. Keep the manually authored Moon Phase
  and single celestial shader authority, but reshape the halo so idle state has enough
  presence to belong in-scene without becoming a neon tube. The visible lit face may carry
  only a **slight same-colour feather**, which should build naturally into a softer exterior
  bloom just outside the illuminated rim. The dark hemisphere must never emit, but may retain
  restrained non-emissive earthshine. The body centre must not become a lamp blob at Full
  Moon. Validate using actual rendered pixels/diagnostic images and operator or local-agent
  review; do not close on source inspection, shader compilation or unit tests alone.
- [~] **Moon/Sun musical pulse presence (large-card weakness only) — Awaiting Validation.**
  Large cards still report weak celestial musical life even with maximum reactivity. Improve
  transient/midband-driven brightening so the Moon/Sun gain an obvious yet controlled pulse,
  without washing out the whole scene, flattening the lit face or boosting unrelated terrain,
  shoreline or global glow. Preserve existing DSP ownership, logical clock, dormancy and Glow
  bucket conditioning. Date/time and orbit still do **not** choose Moon phase.
- [~] **Celestial-body star occlusion — Awaiting Validation.**
  The Moon/Sun must fully own their screen coverage. Ordinary stars and beat-star glow must
  not punch bright points, black dots or other specks through the disc. Verify this with
  actual images/video, including cases where a bright beat star sits directly behind a New or
  Crescent Moon. Preserve a single depth/coverage authority rather than layering ad hoc masks.
- [~] **Starscape Beat admission and peak visibility — Awaiting Validation.**
  Implemented for the current pass, but **not accepted yet**: Starscape/Starfield beat entry
  is eased **another 20%** (0.28 -> **0.224**) using the same existing onset authority,
  keeping three spaced stars and gentle release. Maximum star output is intentionally stronger,
  with a **restrained star-shaped core/rays** rather than a washed-out bloom. Validate that
  entry is easier, peak glow is unmistakably more visible at maximum settings and the result
  still reads as elegant sky activity rather than a christmas-light spray. Use fixed clips and
  the real-music evidence path below.
- [ ] **Experimental optional Celestial Rim Vertices (default OFF).**
  Add a strictly optional, default-OFF **Celestial Rim Vertices** toggle as an experiment only,
  not as a crutch for the normal Moon. If enabled, it may place sparse antialiased glowing
  point marks along the **illuminated outer rim** of Moon and Sun so the body can optionally
  borrow some of Neon Lake's vertex language. Never create a full surface lattice, a second
  sphere/geometry, separate phase logic, separate glow authority or always-on vertex treatment.
  The standard textured Moon must still look good with this option OFF. Any Moon microrelief/
  bump-mapping follow-up remains optional and must be justified physically first; Sun is plasma,
  not lunar rock, so do not blindly share a bump treatment.
  The operator approved the default-OFF setting/schema on 2026-10-15; implement and
  validate it without making the ordinary Moon depend on the experiment.
- [ ] **Viewport-size/DPR adaptive glow and vertex legibility — local-agent implementation + physical acceptance.**
  The same authored Neon Lake preset can look excellent at one framed-card size and disastrously
  overbloomed/overcrowded at another. **This is a render-presentation scaling defect, not an
  artistic-preset defect.** A local Windows agent must implement effective physical-viewport
  scaling for glow footprint/coverage and point/vertex appearance and validate actual GPU
  captures with the operator or a local agent with visual access. At **small cards**, overlapping
  glows compound and dense marks merge; at **large cards**, existing general surface/lake/sky
  glow must retain presence, while specifically weak Starscape peaks and Moon/Sun *musical pulse*
  stay separate acceptance tasks above. Never globally increase glow to solve small-card issues.

  **Two observed, mutable calibration examples (NOT presets to copy, rewrite or assert):**
  - **Preset 1 (Synthwave), approx. 2100x1200 widget viewport:** Saved Surface Glow
    `shockwave_grid_glow=0.55`, Vertex Density `density=0.55`, Glass Strength `0.55`, Water
    Reflection `0.77`, Light Rays Strength `0.50`, Horizon `0.68`, Sky Strength `0.80`.
    Its saved payload **omits** Celestial Halo Intensity/Reactivity and Starscape Glow
    Intensity/Reactivity; the present canonical default values are **1.0 each**, which must
    be resolved through the spec/default authority rather than treated as authored zero.
  - **Operator-supplied Preset 2 (Example), approx. 1300x750 widget viewport:** Saved Surface
    Glow `0.29`, Vertex Density `0.55`, Glass Strength `0.55`, Water Reflection `0.77`, Light
    Rays Strength `0.31`, Horizon `0.45`, Sky Strength `0.90`; Celestial Halo enabled with
    Intensity `0.66` / Reactivity `1.54`; Starscape Beat enabled with Star Glow Intensity
    `1.23` / Reactivity `1.91`. Both examples use **Glass + Vertices** and the same saved
    vertex/accent/outline RGBA colours. Preset 2 is a diagnostic export supplied separately,
    **not an instruction to install it or replace an operator slot**.
  - Sizes are reported widget dimensions, not proven physical pixels; the agent must measure
    the actual render-target dimensions and DPR (including supersampling/MSAA as relevant).
    These two observations are **guides to the size sensitivity**, not a two-point glow formula,
    not a fixed 1300/2100 breakpoint, not approved artistic defaults and **never golden tests**.
    Both presets remain freely editable; the current operator-authored versions always win.

  **Implementation and visual acceptance checklist (all remain open):**
  - [ ] Inspect existing scene-target bloom/compositing and mode-owned point shader contracts;
    distinguish **emission radiance/strength**, bloom blur radius/footprint in physical pixels,
    coverage/overlap, antialiasing and effective visible vertex count. Do not collapse them into
    one multiplier or a second Settings/preset owner.
  - [ ] Derive bounded smooth **effective presentation scale** from the actual framed content
    viewport in physical pixels and DPR, with aspect, internal zoom and the shared scene fit
    accounted for. Control bloom spread/energy conservatively and apply marker size, antialiasing,
    separation and LOD only where useful; preserve authored `glow` and `density` as semantic
    inputs. Keep land, water, shoreline, Glass and Vertices on their existing shared geometry,
    depth and DSP/simulation authorities; do not fake missing vertices by overwriting user data.
  - [ ] Resize a **single unchanged** authored configuration live between **1300x750** and
    **2100x1200**, plus substantially smaller/large, narrow/tall and zoomed/rotated framed
    cards. Check both Preset 1 and the separately supplied Preset 2 export *as editable current
    examples*. At comparable DPR and authored values, no blown-out point carpet at the smaller
    size, no underlit/diffuse loss at the larger size, no popping at size thresholds. Check
    DPR **1/1.25/1.5/2**, both displays, idle/beat/sustained passages, Glass-only, Vertices-only
    and Glass + Vertices. Capture matched before/after real GPU frames and moving clips.
  - [ ] Prove resize/reopen/dormancy ownership: Qt Quick scheduling remains sovereign; no new
    polling/timers, per-frame static geometry/resource rebuilding, surprise extra render targets,
    duplicate bloom owner or unrelated-mode cost. GPU work should scale predictably with viewport
    size, without stalling dual-1440p presentations. Tests use **synthetic test-owned configs**
    for invariants, never freeze mutable artistic values or preset bytes. Use explicit project-venv
    test commands and **no environment-variable mutation**. Mark complete only after actual
    operator or local-agent image and performance acceptance.
- [~] **Terrain reactivity rework — source implemented, Awaiting Validation.** Eight
  preallocated, atomically committed regional contrast factors now condition the existing
  shaped targets without another FFT, raw-spectrum copy, clock or per-frame container.
  Review actual quiet/onset/sustained real-music motion for differentiated response,
  restrained bass and non-jelly land; retain the existing growth timing and shaper authority.
  Preserve whatever Preset 1 terrain/appearance the operator
  has authored **at the time of the change**, unless a separate artistic edit is approved;
  do not freeze an older baseline or treat these numbers as regression oracles. Validate deterministic clips and the
  operator's **real-music recordings** at
  `F:\Programming\Apps\ShittyRandomPhotoScreenSaver\logs\visualizer_recordings`.
  A local agent may execute real-music replays; no new per-frame allocation, timers,
  environment-variable mutation or unrelated-mode cost. Require physical reaction review.

- [ ] **Neon Lake reactivity audit and evidence-led improvements.** After the visual corrections above,
  have a local agent replay deterministic quiet/onset/sustained/busy clips **and real music** from
  `F:\Programming\Apps\ShittyRandomPhotoScreenSaver\logs\visualizer_recordings`. Compare actual
  audible events, raw source/band/onset levels, eight terrain-growth envelopes, water events, star admissions,
  celestial halo output and screen-visible result at low/high reactivity. Identify missed attacks, saturated
  responses, bass/transient washout, flat sustained passages and delayed release. Improve only evidenced
  weaknesses, re-run the same clips, document before/after measurements and capture actual motion (not just
  static shader checks). Use the existing DSP/shaper and logical clock; preserve shared consumers and unrelated
  modes. This is an **explicit closure gate** in addition to the terrain, star and celestial items above; do
  not declare Neon complete simply because tests report valid values.
- [~] **Six disposable experimental Neon Lake presets — delivered; inspection/closure pending.** Inspect the
  six new editable source candidates in authored slots 4–9, their low/high native-music captures and
  canonical Settings round-trip. Refresh Moon captures after its selected material change. They are
  **temporary candidates**, not approved final art:
  the operator may reject all six without reopening accepted renderer architecture. **All presets, including
  Preset 1 and the six experiments, are operator-authored and freely mutable at any time.** Use the current
  Preset 1 only as the present visual comparison, not a locked identity, frozen copy or fixed test oracle.
  Creating experiments must not silently overwrite any existing operator-authored slot or discard its current
  edits; intentionally authorized schema migrations may update authored files while preserving the operator's
  latest artistic intent. Never pin preset values, visuals or hashes in regression tests. Keep Custom distinct,
  keep camera/view pose out of art presets, and update the one canonical slot catalog/selection/migration
  together. The six additions are experimental candidates, not immutable snapshots.
  Close Neon Lake only when **all live visual/reactivity/viewport tasks above**, including the
  optional default-OFF rim-vertices experimental decision, and the recorded-audio review
  have their specified agent/operator acceptance, source regressions pass, and six experiments have been delivered and
  inspected as experiments. Their eventual aesthetic rejection is not a blocker to structural closure.

The completed implementation trail, rejected experiments and previously detailed V4A
checklists are archived in `Docs/Audits/Neon_Lake_V4A_Historical_Checkpoints_2026-10-14.md`.
The durable technical contract remains `Docs/Reference/Neon_Lake_Basin.md`. Do not reopen
accepted architecture or settings simply because old historical checkboxes were unchecked.

- [ ] **V5 — original Bubble, immediately after Neon Lake closure and BEFORE shared-primitive/Extruded Bubble work.**
  Save a current frozen-settings recorded-clip baseline, migrate controls, then compare
  `python -m tools.visualizer_replay.mode_audit --modes bubble --compare <saved run>`. The existing local baseline is
  `logs/bubble_readings_baseline.json`; verify its inputs before reuse. All readings remain x1.00 unless a separately
  authorized reaction change is intended. Do not use mutable curated presets as goldens or compensate with DSP retuning.
  Preserve the one-key Swirl composite, versioned gradient-direction input migration, live ghost conditions and external
  Rainbow/Bar Appearance/Technical owners. Declare current UI/storage versus runtime range differences explicitly:
  stream reactivity and pulse controls have tighter runtime caps, stream-speed minimum differs, and contraction admits
  a wider runtime range than its slider. Preserve current hydration quantization and the actual simulation/render
  consumers of ghost enablement, with one canonical authored intent. Retire promoted model/binding/applier tables
  atomically; do not invent controls in the currently empty Layout bucket or introduce Spectrum shaping. Prove real-body
  round-trip, Swirl/gradient migration, one application per consumer, dormancy and fixed-clip full-output equality.

- [ ] **Close the Settings-spec migration as a separate gate.** Verify all registered original Visualizer modes,
  including Bubble, use the single typed spec and canonical defaults without a parallel model/builder/applier
  authority; compare Bubble visual/physical audio replay against its frozen baseline and confirm dormant-mode
  neutrality and persisted Custom/preset parity. Record complete mode coverage, not only passing schema tests.

Each slice ends in focused proof, refreshed owner docs and a checkpoint before the next. New modes use the spec from
first implementation. **Do not start the shared-primitive programme or Extruded Bubble until original Bubble V5
and the spec-migration gate are closed.** Neon Lake conversion is already in V4A, not a duplicate §4 project.

## 3. Release media and bounded source cleanup | Independent, nonblocking work

This section is **not** a dependency between Bubble V5 and the shared-architecture gate in §4; perform it at a
stable checkpoint or when separately authorized, without delaying or bypassing the explicit §0 order.
The release capture tool is already landed. `Docs/Reference/Release_Media.md` is the single source for input paths,
encoding and manifest policy: genuine UsuScene1–4 originals, transition loops at 480 px wide / 24 fps / authored speed,
high quality and no arbitrary 10 MB cap. Outputs remain outside runtime QRCs and normal Godzips.

- [ ] **RM1 — Reconcile the catalogue at a stable checkpoint.** Enumerate the current registry/meaningful appearance
  variants and compare existing manifest/source hashes. Generate missing or stale entries only; preserve the accepted
  exclusions (Warp Dissolve, Particle, Blinds Flat) unless changed by the operator. Review each new/visually changed
  transition WebP before closing its implementation. Do not fabricate missing local originals or recapture merely
  because the Git revision changed when source inputs did not.
- [ ] **RM2 — Visualizer showcases.** Once the migration/geometry source is stable, capture registered modes' curated
  presets with canonical schema-2 real-music clips through production replay/capture/render ownership. Keep the authored
  reaction, photograph backdrop and reflection inputs; fail loudly for unavailable inputs.
- [ ] **RM3 — Catalogue proof.** Inspect motion/endpoints, loop seams, dimensions, metadata and quality; retain outputs
  and manifests. Verify unchanged inputs skip regeneration, changed source/preset/clip inputs regenerate appropriately,
  and mixed-revision captures are rejected. This is media proof, not another product visual acceptance gate.
- [ ] **SC1 — Retire unused root transitions.direction.** Confirm current caller absence, then forward-strip the root key
  without changing each transition's own direction setting. This changes the operator's defaults: undertake only with
  explicit defaults-change authorization. Prove import/default merge/save cannot resurrect it.
- [ ] **SC2 — Blinds Flat endpoint discrepancy, nonblocking.** Reproduce the prior capture endpoint mismatch at the exact
  production endpoint before deciding whether the defect is in capture or rendering. Landed transitions are accepted;
  do not reopen broad appearance work, change authored behavior or demand another build absent a reproduced defect.
- [ ] **SC3 — Retire unused Spectrum fill/border-link state.** Current source finds `spectrum_link_fill_border` only in
  defaults/model serialization and authored preset/fixture payloads, with no UI or renderer consumer. After the Settings
  migration checkpoint, confirm caller absence and forward-strip it at canonical input/save boundaries without linking
  the independent fill/border controls. Preserve frozen historical fixtures; prove current import/save cannot resurrect it.


### SC4. Just Make It Work Pools | provider selection, independently scoped

**Do not infer completion from discovery:** The existing Just Make It Work action currently replaces the wallpaper
feed URL list with four fixed entries and Guided Setup calls that same action. Pool UI, provider rotation and new NASA
selection have not yet been implemented. Technical design, site validation and acceptance gates live in
`Docs/Reference/Wallpaper_Pool_Selection.md`. Scope as separately authorized source work, not an implicit blocker
of §0 Neon Lake → Bubble migration → shared 3D → Extruded Bubble. Retain SC1–SC3 and the §5 wallpaper-RSS
runtime-replacement audit as independent work.

- [ ] **SC4.1 — Source eligibility and exact resolution.** Verify current public listing, metadata and original-image
  access with bounded live requests for each candidate. Wallhaven's public JSON API is already the implemented
  feed. Group NASA Sun/Mars/Solar System/Universe behind one `Space` choice, rather than exposing each as an
  individual consumer-facing NASA checkbox; replace the current NASA-wide Image of the Day and legacy JPL listing
  in the curated choice. NASA's Solar System is a *group* of several official Photojournal topic feeds, not an
  assumed single URL. Keep Minitokyo experimental until anonymous original access, site availability, permission
  and respectful request costs can actually be demonstrated. Consider Konachan.net (wallpaper-oriented SFW), then
  Safebooru/Zerochan with stricter admission; include Yande.re and E-Shuushuu in comparison with stronger SFW,
  wallpaper and API-access caveats. Distinguish published API documentation from **actual, authorized, successful
  original-image retrieval**; no board is a public default until bounded live probes pass.
- [ ] **SC4.2 — One provider-selection authority, no new shuffle.** Create a canonical typed selection for named
  Just Make It Work Pools, including **named Wallhaven thematic search pools** rather than its three coarse
  General/Anime/People flags as user-facing choices. Give the entire popup **one global discovery-order preference**
  (Random, Latest, Popular, Today/Week/Month/Year), translated only for providers with real support; unsupported
  providers keep their native discovery order with no simulated ranking or second shuffle. Define stable, validated
  provider query templates and a bounded number of distinct feed documents **per acquisition pass**, rather than
  fetching a document for every checked search. Existing wallpaper coordinator,
  conditional-request/backoff, image-attempt, per-host pacing, session-replacement, cache and display-size header
  admission remain owners. Source sorting filters what the RSS wallpaper pool may discover; the final wallpaper
  rotation and display shuffle remain entirely in the existing engine. Persist fair pool rotation/retry without
  creating a scheduler, timer, competing shuffle or per-feed continuous worker. Prove behavior with pool=full,
  offline source, 429/backoff, settings restart and zero active displays.
- [ ] **SC4.3 — Shared themed popup and Guided Setup.** Existing **Just Make It Work** buttons in Sources Settings and
  Guided Setup invoke the *same* popup, Save/Cancel and settings owner. Popup title `Just Make It Work Pools`;
  source-family groups with **Wallhaven themed-search checkboxes** (Nature & Landscapes, Space, Cities &
  Architecture, Fantasy, Science Fiction, Cyberpunk, Abstract, Minimalism, Anime Scenery, Dark Wallpapers),
  one NASA Space checkbox (the four subject families), and optional approved board pools. Offer **one discovery-order
  selector at popup level**, not per Wallhaven/source group. Keep `purity=100` and coarse category bits as adapter
  internals only, and keep provider-specific ranking semantics out of the wallpaper shuffle. Use the
  established StyledPopup/shared dark-glass theme, sizing, keyboard, scrolling and bucket components. Guided Setup
  must keep its draft/Finish/Skip lifecycle and readiness authoritative and must not silently overwrite custom feed
  authoring when toggling pool availability. Validate fresh, existing-custom, empty and disabled-feed states, and
  source-list add/remove/edit across both surfaces.
- [ ] **SC4.4 — Safe migration, metadata and physical acceptance.** Migrate the existing curated NASA/Wallhaven URL
  entries into selected pool identities at canonical persisted-input boundaries once, without repeated legacy
  branches; never misclassify user-authored custom URLs as curated. Preserve independently authored RSS/Atom/JSON
  feeds, folders, source ratio, cache and nonblocking 3D roadmap. Use test-owned configs for persistence/selection
  and fake feed documents for fair per-pass admission, backed by opt-in provider probes and operator review.

## 4. Graphics decomposition | after original Bubble spec-migration closure

**Dependency, not a parallel workstream:** §2A Neon Lake closure -> original Bubble V5 parity/spec closure ->
§4A preflight/shared substrate acceptance -> §4B Extruded Bubble. **No EB2/EB3 renderer work before G0,
G1, framed-camera sharing, G3's depth-aware transparent compositor and G2's justified shadow foundation
are proved.** An EB visual target may inform G0's requirements, but EB production implementation begins only
when the shared-gate checklist is complete. Do not build speculative full optics, particle or volume engines.

Other admitted mode order remains Reactive Particle Field -> Terrain/Skyline/Tunnel -> Waveform Ribbon ->
Deformable Blob Sphere. Usu remains deferred under `Docs/Future_Work/Usu_Moonscape.md`; a foundation can be
proven without admitting its downstream consumer. `Docs/Reference/Scene3D_Resources.md` defines the shared
contracts, ownership and measurement requirements. The source remains the implementation authority.

### 4A. Shared facilities | required pre-Extruded Bubble gates

Reusable scene GPU facilities remain opt-in within the retained Qt Quick Scene3D owner. Reuse current mesh,
instancing, stream rings, compute/population, emission, bloom, trails, GGX/Fresnel materials, and optional planar
shadow helpers; inventory before adding anything. **Primitive green means measured actual GPU pixels, GL state,
resize/retirement and dormant-zero-cost tests**, not only shader compilation or a source-string assertion.

- [ ] **G0 — Inventory, target contract and baselines (first).** Inventory renderer owners, existing primitives,
  cost and validation gaps, and approved Extruded Bubble depth/overlap/translucency/shadow goals *without starting
  EB implementation*. Record current CPU/GPU, GL calls, memory and dual-1440p/card-size baselines. Run
  `tools/overhead_baseline.py` before/after every shared change. Do not implement a primitive whose missing
  capability cannot be demonstrated; existing modes must not load/allocate the optional extension.
- [ ] **G1 / S17 — Attachments, depth and temporal ownership.** Define required normal/material/depth/history
  attachment formats, targets, clears, reuse, size keys, context and generation invalidation, multisample resolve,
  near-plane/depth tests, transparent versus opaque ordering and inherited GL-state restoration. Prove actual
  backdrop/card alpha pixels (including glass, star/celestial occlusion), mixed-DPR resize and no stale-history
  sampling. Implement only demanded targets and release them at park/context teardown. G1 precedes G2 and G3.
- [ ] **FC — Promote Neon Lake's bounded framed camera into ONE shared opt-in capability.** Neon Lake is the
  reference for **internal** WASD/Alt-left orbit, Alt-right pan, Alt-wheel zoom, retained border/card clipping,
  camera/view-pose persistence outside art and layout, composition-aware limits and homogeneous near-plane safety.
  Consolidate *existing* descriptor/view-orbit/scene-transform/projection helpers, not a new pose store, clock,
  controller or universal orbit policy. Each **framed 3D Visualizer** declares its own safe bounds, fit, pivot and
  content envelope; Neon Lake's landscape angles are not defaults for bubbles, ribbons or cubes. Exclude current
  unframed Sphere/Extruded Spectrum from forced clamping. Prove identical Neon Lake input/visual behavior after
  sharing, retained card/Edit/CUSTOM SSOT, persistence, no exposure of world edges, small-card/DPR adaptation,
  multi-display view isolation and dormant-zero-cost. Record reusable contract in `Docs/Reference/Visualizer_Reference.md`.
- [ ] **G3A / S17 — Shared depth-aware transparency and compositing (before EB renderer).** Provide a proven
  opt-in weighted-blended OIT or equivalently correct bounded order-independent layering for overlapping transparent
  bubble surfaces; keep depth, opaque objects, overlay-card alpha, emission/bloom and GL state coherent. Compare
  overlapping spheres in opposite draw orders, near-plane/camera crossings, depth-tested backgrounds, resize,
  context loss and performance tiers. **Do not fall back to locally sorted, manually composited EB-only glass**
  or duplicate SceneTargets. Existing GGX/Fresnel material helpers remain authoritative.
- [ ] **G2 / S25 — Shared real shadow-map foundation.** After G1, prove one fitted directional depth map with
  bounded soft PCF/bias, caster/receiver admission, resizing, lazy allocation/teardown and tier-specific GPU cost
  on a test scene. This is the *same* shadow foundation referenced by Usu S25; do not resurrect the rejected
  Extruded Spectrum cast-shadow experiment. Extruded Bubble uses it only where EB's approved receiver/lighting
  target demonstrably improves; absence of a receiver is not permission to invent one.
- [ ] **G3B / S17 — Measured optical enhancements before EB if its target needs them.** After G3A,
  evaluate bubble-shell Fresnel/rough transmission, thickness/depth-aware refraction and restrained dispersion
  against actual overlapping-bubble target images. Prove only the useful variants as reusable primitives **before**
  EB3/EB4; explicitly record which are unnecessary and leave them deferred, rather than inventing an EB-local
  replacement or building a general optics stack without a consumer. GTAO is not implicitly admitted.
- [ ] **Shared-gate closure before Extruded Bubble.** Real-driver pixel/reference tests, dual-display and
  extreme size/DPR/zoom cases, owner-state restoration under failure, warmed-demand paths, disabled-feature
  allocations, resource retirement and measured before/after CPU/GPU cost all pass. Update Spec/Scene3D/Visualizer
  reference and TestSuite contracts. Only then begin EB1/EB2. Do not require unrelated G4/G5 primitives.

**Later demand-driven foundation (not prerequisites for Extruded Bubble):**

- [ ] **G4 / S18 — Particle/ribbon extensions.** Extend existing CompactedPopulation and sprite/streak helpers
  only when a chosen mode needs ribbons, bounded lifetimes, collision or indirect draws. Retain deterministic
  admission and retirement; use G3A for transparency when appropriate. If EB target *specifically* needs trails,
  promote only the needed small G4 primitive into its shared preflight, not a parallel EB-owned implementation.
- [ ] **G5 / S18 — Lightning, then volumes.** Bounded procedural geometry/light first; reduced-resolution
  smoke/fog/fire, advection and reprojection only after an actual admitted consumer and independent cost/quality
  evidence. No permanent volume targets or separate cadence.

### 4B. Extruded Bubble | begins only after §4A shared-gate closure

Extruded Bubble is a **bordered/framed internal 3D** successor that reuses the original Bubble logical
simulation/reactivity rather than modifying it. Read current fixed loudness; never add independent floors,
clocks, DSP, polling or renderer-owned simulation. Preserve original Bubble Temporal Fidelity and distinct
mode/preset/CUSTOM authorities. Use §4A's shared FC camera, G1 targets, G3A compositor and applicable
G2/G3B facilities **from the initial renderer**, not as deferred post-launch rewrites.

- [ ] **EB1 — Concrete visual target and measured comparison.** With foundation green, capture representative
  quiet/transient/sustained-loud Bubble replay and define static/motion bubble depth, translucency, overlap,
  lighting, bloom and framed-camera goals. Distinguish useful G2 shadow receivers and optional G3B optics from
  merely decorative demand; do not expand the shared architecture without evidence.
- [ ] **EB2 — Descriptor, spec and frame admission.** Declare one canonical mode/capability and presentation
  Settings path; consume Bubble logical state or a clearly mode-owned projection, not a second clock/capture/DSP.
  Assert original Bubble replay equality and zero inactive import/GL/resource work.
- [ ] **EB3 — Bordered 3D renderer on proven primitives.** Instanced geometry, correct overlapping transparency,
  depth/card clipping, lighting/materials and **shared FC bounded orbit/pan/zoom** with Bubble-specific limits.
  The outer card, Edit/CUSTOM rectangle and independent camera view pose never become competing geometry authorities.
  Verify perspective fit, near clipping, glass layering, small/large card/DPR, dual displays and context retirement.
- [ ] **EB4 — Material and quality shaping.** Tune useful, already-proven shared reflection/Fresnel, refraction,
  glow, and G2 shadows when visually justified. Tier-bounded instances/targets and first-frame warm admission;
  do not add an EB-specific OIT, shadow, new SceneTarget or orbit implementation to compensate for a weak shared
  primitive. New genuinely needed substrate goes back through a measured §4A gate.
- [ ] **EB5 — Reactivity, presets and physical acceptance.** Author spec-owned controls and experimental art,
  compare recorded quiet/onset/sustained passages with original Bubble baseline, and verify both displays,
  aspect/DPR, frame timing, latency, dormancy and audio-reactive fidelity before operator acceptance. Capture
  release media only after renderer and musical behavior are stable.

### 4C. Remaining modes and character/world substrate

- [ ] **Reactive Particle Field:** compose G4 with recorded musical controls; establish lifetime/capacity and response
  target before adding collision. **Terrain/Skyline/Tunnel:** one bounded geometry/camera slice at a time, preserving
  fixed loudness semantics. **Waveform Ribbon:** require G4 ribbon proof and real waveform history. **Deformable Blob
  Sphere:** establish deformation/normal/geometry bounds and independent cost before layering materials/effects.
- [ ] **S19 → S20:** deterministic validated Blender/glTF bake into provenance-stamped packed assets, then imported
  static-mesh rendering on shared materials/instancing. Runtime reads packed data, not authoring node graphs.
- [ ] **S21 → S22 → S23:** bounded GPU joint palettes/skinning, then logical-time clip sampling/cross-fades/masked
  additive layers/root-motion/eye tracks, then deterministic secondary-motion springs. Prove each in its own offscreen
  harness before combining; no physics engine or separate animation clock.
- [ ] **S24:** opt-in felt/sheen and bounded fuzz shells with emitted-light tips; prove unchanged existing shader variants
  and tier-specific cost. **S25:** reuse G2, never a duplicate shadow implementation.
- [ ] **S27 → S26:** prove 3D world-view/projection distinct from the existing photo-plane camera, then
  seeded sphere/crater/star geometry and logical travel. Reuse §4A FC's view/orbit/input/persistence authority
  **where the scene is a bordered Visualizer**; a deliberately unframed/world-travel camera may have different
  projection and motion semantics, but not a duplicate framed-camera controller. Asset/rig/clip acceptance
  stays with the existing Usu plan and local asset README; foundations do not admit the deferred full mode.
- [ ] **Combinations only after component proof:** electrical terrain, smoke-lit fracture, ember/dust destruction,
  refractive glass lit by bolts, volumetric shockwaves and photo-colour IBL. Choose one promoted effect at a time.

## 5. Nonblocking watchlist and operator-owned evidence

These items never hold source work waiting for a diagnostic build. Observe during normal use or an operator-chosen
build/capture; reopen only from the listed symptom/evidence. Record Awaiting Logs/Validation without turning it into
an instruction to rebuild, poll or repeat the full suite.

- [ ] **Monitor power/wake — watchlist, Awaiting Validation when convenient.** During an existing/new operator build,
  observe either display off, >30 seconds on one screen, rapid off/on, reordered return and both selected screens absent.
  Widgets must stay on physical assignments and return with original CUSTOM geometry; no spillover, duplicate owner,
  phantom window or frozen input. Include Settings reassignment and Arrange/Edit/Reset if those paths are exercised.
  First upgraded legacy numeric routes need their intended displays connected unless a unique saved CUSTOM home supplies
  identity. Capture timestamps, remaining physical screen, product flavor and Interaction Mode if an anomaly appears.
  `diagnosticmonitoroffonrapid.zip` demonstrated renumbering/old Visualizer relocation plus a 13:02:16–13:02:30 binding-loss
  stall; source fixes and focused proof are landed (R-79 contains evidence). It showed six completed replacements and
  orderly explicit exit, not a general wake-exit failure. For recurrence, record exact wake/exit input; Interaction Mode
  deliberately suppresses mouse-motion exit. Do not request a full diagnostic build solely for this watchlist.
- [ ] **Refresh contention — Awaiting Logs on recurrence.** Use a naturally available dual-display trace to attribute
  accepted/queued/claimed/published/retired FEEDS/Gmail/Reddit work and transition delays. Existing R163 capture reported
  1–7 second manual delays, but no stranded FEEDS claim was proved. R164 fixed missing False dispatch handling and added
  event-only family attribution. Check fairness/no post-transition stampede; never hide busy during queue time.
  Steam/Weather/Friend Pulse and startup cache readers join no shared gate until their publication/retirement is audited.
- [ ] **Wallpaper RSS after runtime replacement — source audit required.** `engine_lifecycle.stop(exit_app=False)`
  permanently sets the existing RSSCoordinator stop event, while topology replacement reuses that coordinator and does
  not restore its refresh timer. Audit Settings/CUSTOM/topology generation ownership and pending IO drain before deciding
  whether this session owner should resume or be rebuilt. Prove refresh resumes once, with no stale queue publication,
  duplicated session rotation or acquisition while selected displays are absent; keep this separate from FEEDS widgets.
- [ ] **Display Settings scalability — deferred UI cleanup.** The Display tab currently exposes four numbered monitor
  checkboxes. Resolver/persistence and ALL support larger topologies; replace that fixed UI capacity with current-screen
  rows before claiming full explicit selection authoring for more than four displays. Preserve unavailable choices and
  physical bindings through the same authoring boundary; no runtime/provider changes are needed.
- [ ] **Cross-display Media shortcuts — Awaiting Validation when used.** Media on the other display should receive each
  shortcut once; source regression is green. Do not build solely for this check.
- [ ] **Music recorder — Awaiting Validation of capture, not its accepted launch buttons.** When recording is needed,
  capture a named 60-second real-music clip; check signal, file/result, cancellation and mixed-DPR window behavior.
  Use full-history/schema-2 recordings for waveform proof; format/commands live in `Docs/Reference/Harness_Index.md`.
- [ ] **Frozen release gate — operator scheduled.** Operator chooses when to build Standard (+ Diagnostic from the same
  compile), Media Center and Reddit Helper, then checks installed startup/exit, Settings/widgets/cache/audio and installer
  behavior. Agents analyze supplied logs and fix concrete failures with focused tests; no speculative builds or automatic
  four-chunk rerun. Python 3.14/Qt 6.11 cutover and accepted Ban Image behavior are not reopened absent a new defect.
- [ ] **Bubble small-radius judder:** reopen only on new recorded musical/scale/DPR evidence; R-105 holds failed methods.
  **Dual-display reboot incident:** capture DWM/driver/Qt swap evidence before reboot if it recurs; don't attribute prior
  recovery to an unproved patch. **CUSTOM/Extruded or long-duration lifecycle:** reopen only from a concrete new symptom.
  The unrelated 90 Hz versus 60 Hz investigation remains off limits.

## Handoff rules

Use single-line, direct-copy PowerShell commands with explicit `.venv\Scripts\python.exe` when providing operator
commands. For an explicitly requested archive handoff, supply a whole-file superseding Godzip with final-byte manifest
validation; ordinary commits do not require an archive. Keep user assets, bulk logs and release media out of normal
Godzips. No memory updates without an explicit user request.
