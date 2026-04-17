# Current Plan

Update this after every significant change.

## Guardrails

- Keep this aligned with [Index.md](F:\Programming\Apps\ShittyRandomPhotoScreenSaver\Index.md), [Spec.md](F:\Programming\Apps\ShittyRandomPhotoScreenSaver\Spec.md), [Docs/Defaults_Guide.md](F:\Programming\Apps\ShittyRandomPhotoScreenSaver\Docs\Defaults_Guide.md), [Docs/Visualizer_Debug.md](F:\Programming\Apps\ShittyRandomPhotoScreenSaver\Docs\Visualizer_Debug.md), and [Docs/Historical_Bugs.md](F:\Programming\Apps\ShittyRandomPhotoScreenSaver\Docs\Historical_Bugs.md).
- Do not mark runtime or visual-feel issues as fixed without user confirmation.
- Treat `presets/visualizer_modes` as the only authored visualizer preset source tree.
- Treat `release/main_mc.dist/presets/visualizer_modes*` as generated artifacts only.
- Do not treat passing tests as visual sign-off.
- Do not make global/shared math changes unless explicitly requested.
- Do not reduce FPS caps below current configured values.
- Do not revive retired visualizer sidecar toggles such as `_use_raw_energy`.
- Do not solve Bubble/Blob by merely swapping one failure family for the opposite one.
- Do not split Bubble directional boot fixes by axis family. Horizontal and vertical directional streams must rise or fall together; if the startup treatment is wrong for one, neither keeps the special case.
- Failures at fixing are to be kept summarised in an issue until the user states the issue is solved.
- Keep checkboxes honest:
  - `[x]` landed and validated by user if visual
  - `[~]` landed or partially proven, still needs runtime eyes
  - `[ ]` not done

---

## Recently Closed

### Visualizer Custom Settings Lost on Save / Navigation / Runtime Round-Trip

Closed from the live plan on 2026-04-16 after user-reported runtime confirmation that the issue now appears solved.

Historical detail remains in [Docs/Historical_Bugs.md](F:\Programming\Apps\ShittyRandomPhotoScreenSaver\Docs\Historical_Bugs.md) under:
- `2026-04-11 — Visualizer Preset Override Bug (MERGE Semantics + Cross-Mode Pollution + Call-Site MERGE)`
- `2026-04-13 — Visualizer Sine/Oscilloscope Lines 4-6 Settings Never Persisted (Resolved)`

Reason for pruning here: the active root-cause work is done, the sneaky multi-layer persistence/runtime bridge failure is now documented historically, and this live plan should stay focused on open validation and remaining Blob/Bubble work.

---

## Awaiting Validation

### 3. Visualizer Mode Isolation / Bleed Audit

**Status:** `[~]` Mostly landed, final runtime confirmation still open
**Priority:** High

**Landed:**
- [x] Dedicated Blob/Bubble/Spectrum/Oscilloscope/Sine renderer ownership audited
- [x] Dedicated visualizer math/helper ownership audited
- [x] Static isolation fences added for dedicated mode-owned modules
- [x] Shared visualizer change checklist established in [Docs/Visualizer_Change_Checklist.md](F:\Programming\Apps\ShittyRandomPhotoScreenSaver\Docs\Visualizer_Change_Checklist.md)
- [x] Preset/save/repair/regeneration paths aligned with current mode ownership
- [x] Shared beat-engine bar-count hitch fix moved onto one startup/runtime-parity rebuild path
- [x] Shared technical cache replay now no-ops when a mode entry is missing instead of silently borrowing foreign technical state
- [x] GPU extra kwargs now stay mode-local rather than carrying unrelated payload clutter

**Still open:**
- [~] Shared seams in `config_applier`, `spotify_visualizer_widget`, and `spotify_bars_gl_overlay` are much cleaner but remain the highest-risk bleed area
- [ ] Finish a live runtime spot-check across shaper-capable modes once Bubble/Blob validation is calmer

**Lesson:** The remaining bleed risk lives in the shared transport/reset/apply seams, not in the dedicated renderer files.

### 4. Shared Preset Install / Save Location Across SCR and MC

**Status:** `[~]` Landed in code, awaiting live coexistence validation
**Priority:** Medium

- [x] Frozen SCR and MC resolve active curated presets through the shared ProgramData tree
- [x] Packaged assets remain the replacement/bootstrap source rather than the active runtime root
- [x] Normal SCR uninstall no longer deletes the shared curated tree out from under MC
- [x] Focused tests for frozen shared-root resolution and replacement routing landed
- [ ] Validate install, upgrade, and coexistence behavior with both builds present on one machine

---

## Planned

### 5. Blob Program - Unshaped Redesign, Architecture Split, And Shaped Follow-On

**Status:** `[~]` Initial implementation started; architecture cleanup and runtime visual validation still open
**Priority:** High
**Primary driver:** Unshaped Blob remains visually wrong even after narrower fixes. Blob Shaper is architecturally healthier, but Blob as a mode family still needs clearer ownership boundaries and a better long-term plan.

**Program goals:**
- Make **unshaped Blob** a first-class, coherent runtime path rather than a circle with layered after-the-fact distortion.
- Preserve and clarify **Blob Shaper** as a separate authored-contour path instead of letting generic Blob controls silently fight it.
- Remove dead or misleading settings exposure so shaped Blob only shows controls it genuinely uses.
- Preserve a strongly **fluid / gel / liquid** motion identity across all new Blob work, including any local pocket retunes or new interior edge effects.
- Add a detailed follow-on plan for **better shaped Blob reactions** once unshaped Blob is stable and the architecture split is clean.
- Allow an explicit **unshaped-vs-shaped runtime split** if that is what it takes to stop the current shared scalar/body assumptions from poisoning both Blob types.
- If a split is needed before the redesign is fully validated, prefer a **temporary dev-gated rollout seam** over keeping one muddled runtime path that is hard to reason about and easy to regress.

**Landed so far on 2026-04-16:**
- [~] Unshaped Blob's late additive `organic_deform` patch is no longer the primary organic silhouette path; a seam-safe low-frequency organic base multiplier now participates in the base radius field instead.
- [~] Matching CPU helper coverage landed in `widgets/spotify_visualizer/blob_math.py` so unshaped wrap/shape tests can target the same conceptual field the shader is using.
- [x] Focused regression tests landed for unshaped wrap continuity, calm non-circular rest shape, and neighboring-angle smoothness.
- [~] Unshaped stretch/wobble composition has been retuned around the organic base field so broad low-frequency motion steers the body instead of layering back toward sharper star-like harmonics.
- [~] The anti-pinch floor now protects the fluid body against wedge collapse using the organic-body radius, not just the old staged circle, and first-pass regression coverage now checks energetic smoothness plus a bounded minimum radius.
- [~] Stage/body headroom regressions now pin down the "no hot baseline blowout" contract by checking that ordinary support stays well below full energetic saturation and that average unshaped body size remains near-neutral across stage levels.
- [~] Pocket reintegration has started: pocket families now bias slightly broader and longer-lived, the shader-side pocket lobe is softer and more shoulder-filled, and the motion system converts pocket pressure into rounded local lift instead of a sharper additive spike.
- [~] Pocket regressions now cover both local lift preservation and the intended broad-width / staggered-release family profile.
- [x] Shaped runtime bridges now zero unshaped-only motion controls in both creator kwargs and GPU extras payloads instead of letting shaped Blob silently inherit them.
- [x] Shared shaped-control row handles/tests landed so the builder now has explicit regression coverage for which controls remain visible when Blob Shaper is enabled.
- [~] A shared runtime normalizer now owns the shaped-vs-unshaped motion fence in `widgets/spotify_visualizer/config_applier.py`, reducing the chance that future call paths reintroduce the same bleed by hand.
- [~] Calmer body-sizing pass landed: unshaped Blob's baseline radius, pulse terms, and staged-growth ladder now leave visibly more room for deformation instead of starting from an almost full-card sphere.
- [~] Shader stage-progress math is now re-aligned with the CPU helper contract instead of using a drifted hotter ladder in the fragment path.
- [~] The liquid-readability pass landed in first form: the inward liquid band is broader/stronger, and the old sphere-like center brightening has been replaced with a softer elongated slime highlight so the body reads less like a shaded orb.
- [~] Unshaped Blob now has its own CPU-side runtime contour solver in `widgets/spotify_visualizer/blob_math.py`:
  - the solver builds a cyclic procedural target profile
  - applies containment/boundedness in profile space
  - smooths motion through the shared contour solver contract rather than relying on a scalar radius plus additive perturbations
- [~] `widgets/spotify_visualizer/renderers/blob.py` now uploads a solved runtime contour for unshaped Blob as well as Blob Shaper, so both Blob types render from the same class of GPU contour handoff even though their contour authorship is different.
- [~] `widgets/spotify_visualizer/shaders/blob.frag` no longer authors unshaped Blob's final silhouette from the old circle-plus-motion stack; it now renders the uploaded runtime contour directly and uses that same resolved contour for inward-liquid/highlight attachment.
- [~] Focused regression coverage now checks that the unshaped runtime profile stays non-flat, bounded, and persistent across frames instead of silently resetting toward a circle.
- [x] The 2026-04-17 workspace log review caught a real unshaped Blob fallback regression in the new contour path:
  - `logs/screensaver_spotify_vis.log` showed `Shader-based rendering failed (mode=blob)` during uniform upload
  - root cause was not GLSL compile failure but a Python runtime mismatch between flat pocket uniform payloads and the new CPU contour solver's expected shape
  - `compute_blob_pocket_component(...)` now accepts the real flat payload contract, and focused regression coverage was added so this exact upload-path fallback cannot silently recur
- [~] Blob runtime ownership is now cleaner in code:
  - `widgets/spotify_visualizer/renderers/blob_shaper_runtime.py` owns the shaped authored-contour runtime helpers
  - `widgets/spotify_visualizer/renderers/blob_unshaped_runtime.py` owns the procedural unshaped runtime helper
  - `widgets/spotify_visualizer/renderers/blob.py` is now primarily the shared GL upload facade plus compatibility re-export surface
- [~] The first retained-limiter pass landed:
  - inward liquid now clamps to a nonzero retained band during retreat instead of collapsing toward invisibility
  - the shader and CPU helper now share that retained-band floor contract
  - focused inward-liquid tests now assert retained-band behavior directly
- [ ] Runtime visual sign-off is still open. These changes are landed and partially proven, not visually closed.

**Current diagnosis to preserve:**
- Unshaped Blob is still built around a preserved circular `staged_r` in `widgets/spotify_visualizer/shaders/blob.frag`, then modified by several additive layers (`stretch`, `wobble`, pockets, late `organic_deform`, safety floors). This is the core reason the eye still reads a circle underneath the deformation.
- The seam problem is not just "Blob uses `atan()`". The more specific trap is the late organic layer using irrational angular frequencies directly on raw `angle`; integer-frequency cyclic terms wrap cleanly, but irrational multipliers on `atan()` space can produce a visible left-edge discontinuity.
- Blob Shaper is now the healthier path architecturally: `widgets/spotify_visualizer/renderers/blob.py` solves one CPU-side contour, and the shader renders that contour. Unshaped Blob should not be allowed to remain the messier legacy cousin forever.
- Blob still has split/duplicated stage knowledge between `widgets/spotify_visualizer/blob_math.py`, `widgets/spotify_bars_gl_overlay.py`, and `widgets/spotify_visualizer/shaders/blob.frag`. Even where runtime currently prefers CPU-fed overrides, that duplication is long-term drift debt.
- Runtime evidence from 2026-04-17 01:13-01:14 confirms the issue is now architectural rather than transport:
  - Blob compiles and renders again (`Compiled shader program: blob` in `logs/screensaver_spotify_vis.log`)
  - the on-screen result still reads as a contained sphereoid with uniform scalar swelling
  - the user screenshot confirms the body is still effectively a circle with presentation layered on top rather than a fluid contour
- The current unshaped motion amplitudes are still too subordinate relative to the scalar body radius and preserved floors:
  - `staged_r` remains the dominant author of silhouette
  - stretch/wobble/pocket terms are visually secondary perturbations
  - when energy rises, the viewer mostly sees whole-body growth instead of contour-specific fluid reaction
- The inward liquid is currently implemented as a shallow interior colour mix over the same solid fill, which means it can be mathematically "active" while remaining visually absent against a strong fill colour.
- The inward liquid currently fails the intended limiter contract:
  - it can become visually absent under hot/small-radius states
  - it is not guaranteed to maintain a persistent interior edge presence
  - this lets the blob read like gross scalar growth instead of pressure against a liquid boundary
- The limiter requirement is now stricter than "visible most of the time":
  - the inward liquid may retract under pressure, and should
  - but it must never fully disappear as a band/front while enabled
  - the reactive read must become "local retreat with preserved presence", not "full collapse then return"
- The current highlight/specular path is still presentation-first:
  - it shades the body after the fact
  - it is not a contour-attached vector/slime highlight driven by the same resolved fluid form
  - this is why the result still reads as a lit orb instead of viscous material
- Blob Shaper currently has too little apparent reactivity relative to its promise:
  - authored contours are healthier than old unshaped Blob architecturally
  - but live response is still too uniform / too subtle
  - if the shared runtime keeps blocking stronger shaped reactions, that is now justification for a cleaner shaped-vs-unshaped split rather than more compromise tuning
- The current Blob tests are proving helper/math invariants, not user-visible rendered outcomes:
  - they do not meaningfully fail when Blob still looks like a circle
  - they currently over-protect implementation contracts that are not sufficient for the desired visual result

**Non-negotiable visual goals for unshaped Blob:**
- The body must no longer read as "obvious circle plus star spikes".
- Valleys must feel like soft `)` / `(` curves, not sharp `V` dents.
- The left edge must not show a seam, cut, or angle-wrap scar.
- Calm passages must still look organic, but not blown out.
- Strong passages may stretch and pocket, but must not collapse inward into pinched wedges.
- The overall motion language should read as **gel / fluid / liquid**, not brittle spikes or rigid star geometry. This is intentionally close to the current mode identity, so the redesign should evolve the existing feel rather than replacing Blob with a totally different visual family.
- The body must stay meaningfully contained within the visualizer card in ordinary operation:
  - small overshoots may exist only as rare, liquid-feeling excursions
  - the main read must never be "a giant pulse that simply outgrows the card"
- The inward liquid must be plainly visible when enabled:
  - not as a barely-there tint
  - as a readable inner band/front with its own motion and retreat language
  - it must never disappear completely, even under strong volume or hot-state response
  - the extreme case should be "blob nearly meeting the limiter" rather than "limiter vanished and the blob filled everything"
  - it must remain reactive while preserving that presence:
    - stronger body pressure should locally pull it back
    - calmer passages should let it creep forward again
    - but a nonzero retained band/front must remain throughout
- The highlight/specular must read like **vector slime / ooze / oblong wet streaking** attached to the fluid body:
  - not a spherical center brightening
  - not a sharp static cap/slice near the top

**Non-goals / guardrails:**
- Do **not** revive `_use_raw_energy` or invent Blob-only persisted signal toggles.
- Do **not** fix unshaped Blob by regressing Blob Shaper back toward generic wobble/shell tricks.
- Do **not** expose settings in the UI just because a legacy runtime field still exists; shaped Blob must only surface controls it actually uses.
- Do **not** create separate startup-vs-runtime code paths for Blob deformation. Cold start and hot runtime must use the same authoritative logic.
- Do **not** declare success from tests alone; this remains a visual/runtime sign-off area.
- Do **not** keep trying to solve this primarily by retuning the current circle-SDF scalar growth path. At this point the failure mode is structural, not just numeric.

**Success criteria before this issue is considered closed:**
- [ ] Unshaped Blob no longer shows a visible circular core on the current antagonistic presets/screenshots.
- [ ] Unshaped Blob has no visible left-edge seam under slow drift or strong motion.
- [ ] Unshaped Blob remains organic at rest without needing a late additive "fake deform" patch.
- [ ] Unshaped Blob pockets still contribute useful local reactions after the redesign.
- [ ] Blob Shaper keeps its current authored-contour advantages and does not inherit generic unshaped controls again.
- [ ] Shaped Blob UI only shows controls that materially affect the shaped runtime path.
- [ ] Unshaped Blob remains substantially inside the card under ordinary playback instead of reading as a giant scalar pulse.
- [ ] The inward liquid is clearly visible when enabled and visibly retreats/yields under body pressure.
- [ ] The Blob highlight reads as an attached slime/ooze streak, not a sphere specular.
- [~] Regression tests cover the new wrap continuity / no-circle-dominance / settings-ownership contracts where practical.

**Program structure:**

#### 5A. Blob Ownership / Architecture Split

**Intent:** Make the code reflect the product truth that Blob is really two related but different runtimes:
- **Unshaped Blob** = procedural freeform body deformation
- **Blob Shaper** = authored contour with routed energy-driven reaction

**Why this matters:**
- Right now the product concept is split correctly in the UI/spec, but the runtime still shares enough fields and legacy assumptions that Blob can feel like one mode with hidden branches instead of two explicitly-owned paths.
- The separation should become more explicit so future edits do not accidentally reintroduce shaped/unshaped control bleed.

**Architecture checklist:**
- [ ] Define the authoritative boundary between **unshaped** and **shaped** Blob in code comments and `Spec.md` language before refactoring behavior.
- [ ] Audit `widgets/spotify_visualizer/renderers/blob.py`, `widgets/spotify_visualizer/shaders/blob.frag`, `widgets/spotify_bars_gl_overlay.py`, and `ui/tabs/media/blob_builder.py` for fields that are genuinely:
  - unshaped-only
  - shaped-only
  - shared across both Blob types
- [ ] Keep pockets explicitly unshaped-only. Blob Shaper must not read or react to pocket state.
- [ ] Keep contour solving explicitly shaped-only. Unshaped Blob must not become "fake shaper lite".
- [ ] Reduce reliance on "hidden legacy fields that happen to still do something" as the ownership boundary.
- [~] Shared runtime normalization now hard-fences shaped Blob away from unshaped motion controls in both apply and export paths.
- [ ] Decide whether unshaped Blob deserves its own helper module(s), likely one of:
  - `widgets/spotify_visualizer/blob_unshaped_math.py`
  - `widgets/spotify_visualizer/blob_unshaped_contract.py`
  - `widgets/spotify_visualizer/renderers/blob_unshaped.py`
- [ ] Decide whether shaped Blob should also be isolated more explicitly, likely one of:
  - `widgets/spotify_visualizer/blob_shaped_runtime.py`
  - `widgets/spotify_visualizer/renderers/blob_shaped.py`
  - a shaped-only contour reaction helper separate from the current shared file
- [ ] If the file split happens, keep the write surface disjoint:
  - shaped contour/routing logic remains with current shaper helpers
  - unshaped radius-field logic moves into clearly named unshaped helpers
- [ ] If the split happens in stages, allow a temporary dev gate for the new unshaped and/or shaped runtime paths:
  - gate only Blob-internal implementation choice, never mode identity
  - do not let the gate bleed into other modes
  - remove the gate once the new path is validated rather than carrying it indefinitely
- [ ] Keep shared stage helpers in one canonical place rather than letting shader/CPU math quietly drift apart again.

**Preferred architectural direction:**
- Unshaped Blob should own a clearly named **radius-field contract**.
- Blob Shaper should own a clearly named **contour-solver contract**.
- Shared state should be limited to genuine cross-type concepts such as:
  - body pulse / release
  - shared color / glow / ghost presentation
  - stage/live band transport where truly shared
- Shared presentation helpers, if retained, should be explicitly presentation-only:
  - inward liquid
  - highlight/specular
  - ghost/glow/outline colour handling
  - never generic body-shape authorship

**Current preferred implementation direction:**
- [ ] If the next fluid-state pass still needs large Blob-type conditionals inside shared files, split the runtime more aggressively instead of adding another compromise layer.
- [ ] Favor a world where:
  - unshaped Blob can radically improve fluid motion without worrying about shaped regression
  - shaped Blob can gain stronger contour reactions without inheriting unshaped deformation logic
  - settings/presets remain explicit about which Blob type they belong to

#### 5B. Unshaped Blob Geometry Redesign

**Intent:** Replace the current "circle + additive deformation stack" with one coherent procedural silhouette.

**Current failure to preserve:**
- Current order in the shader is effectively:
  1. build circular/staged body radius
  2. add stretch
  3. add wobble
  4. add pockets
  5. add late `organic_deform`
  6. clamp with multiple floors
- This guarantees the circle remains the dominant shape language, and the late organic layer has to fight a silhouette that was already authored as circular.

**Target shape model:**
- The base silhouette itself should already be non-circular.
- Stretch/wobble/pockets should modulate that base silhouette rather than trying to rescue it afterward.
- The deformation field must be **cyclic by construction** so the left-edge seam cannot exist.
- Motion should feel viscous and elastic, with rounded follow-through, rather than behaving like sharp mechanical radial teeth.

**Concrete corrective direction after the 2026-04-17 runtime review:**
- [~] Stop treating the current unshaped Blob as "circle SDF plus offsets" for the final design.
- [~] Move unshaped Blob onto the same class of solution Blob Shaper already benefits from:
  - solve one explicit cyclic contour/profile each frame
  - render that solved contour in the shader
  - let liquid/highlight layers read from that resolved contour instead of from a scalar circle baseline
- [~] Introduce an **unshaped runtime profile** separate from the shaped authored profile:
  - generated procedurally rather than user-authored
  - still represented as a cyclic angular contour/profile array
  - likely `64` or `96` samples to start
- [~] Make the unshaped solver own:
  - calm rest profile
  - audio pressure
  - tangential redistribution
  - local pocket lift
  - containment / no-contact / anti-pinch rules
- [ ] Add an explicit solved-envelope contract to the unshaped path:
  - `body_outer_profile` stays within the card envelope except for tiny liquid-style overshoot
  - `inner_liquid_profile` remains present whenever the effect is enabled
  - `minimum_gap_profile` between body and inward liquid never reaches zero
  - `retained_limiter_profile` enforces a nonzero visible/reachable inward-liquid band even under the strongest retreat state
- [~] Reduce global pulse to a secondary body-breath/volume bias, not the main source of visible growth.
- [~] Add an explicit card-containment contract for unshaped Blob:
  - ordinary passages must stay within a conservative contour envelope
  - extreme passages may approach the edge but should not routinely dominate the whole card
- [~] Build the body so "growth" is mostly perceived through contour flow and local pressure movement rather than gross radius expansion.

**What landed in this corrective pass on 2026-04-17:**
- [x] A new procedural unshaped contour solve path was added to `widgets/spotify_visualizer/blob_math.py` instead of trying to rescue the old shader-authored scalar silhouette.
- [x] Unshaped Blob now persists runtime contour state (`_blob_unshaped_runtime_profile`, velocity, target, solver timestamp/seed) so the body can carry shape memory frame to frame.
- [x] Renderer upload now resolves unshaped Blob contour on the CPU and uploads it through `u_blob_runtime_profile`, matching the healthier shaper architecture class.
- [x] Shader silhouette ownership now comes from the uploaded runtime contour for both Blob types; the old unshaped final-radius motion stack is no longer the active silhouette author.
- [~] The inward-liquid/front and slime highlight are now attached to the resolved contour rather than a generic centered orb read, but this still needs runtime eyes.
- [ ] Runtime verification is still needed to confirm the new contour actually reads as fluid/contained on live presets rather than just being architecturally correct.

**High-detail next-pass checklist for unshaped fluid state:**
- [ ] Remove the remaining `staged_r` dominance from the final silhouette contract:
  - the solved contour should author the body
  - scalar stage radius should only define bounded support/headroom
  - any residual circular minimum must be small enough that it cannot visually reassert a pulsing disk
- [ ] Replace "reactivity by size growth" with "reactivity by contour pressure movement":
  - more local contour travel
  - less global whole-body inflation
  - stronger contour-memory carry between frames
- [ ] Reframe pockets as local fluid pressure zones:
  - broader shoulders
  - longer rounded release
  - no spear / spike read
- [ ] Add a hard containment rule in solver space:
  - ordinary playback cannot outgrow the card
  - extreme excursions are tiny, rare, and liquid-feeling
  - test this with hot synthetic frames rather than eyeballing only after runtime
- [ ] Add a retained-limiter rule in solver/presentation space:
  - inward liquid always has a minimum visible/front thickness while enabled
  - retreat can thin and pull back the front, but not collapse it to zero
  - the body/limiter gap remains positive at every sample

**Preferred redesign direction:**
- [~] Replace late additive `organic_deform` with an **organic base-shape multiplier** or equivalent cyclic radius field that is part of the base silhouette, not a late patch.
- [ ] Use a periodic basis that is seam-safe by construction:
  - wrapped `angle_frac`
  - integer-frequency harmonics
  - unit-circle directional dot/cos/sin combinations
  - or a precomputed cyclic profile
- [ ] Do **not** use irrational multipliers directly on raw `atan()` angle for the base organic field.
- [ ] Compose the unshaped silhouette in this order conceptually:
  1. base scalar body size / stage radius
  2. organic base silhouette field
  3. motion modulation (wobble/stretch)
  4. local pocket modulation
  5. safety floors / anti-pinch constraints
- [ ] Ensure the modulation layers are framed as "change the organic body" rather than "add star spikes to a circle".

**Geometry checklist:**
- [~] Design a seam-safe organic base field and document its intended visual language before coding it.
- [ ] Keep the base field low-frequency enough that the silhouette reads as one body, not many teeth.
- [ ] Make valleys broad and curved; protrusions should feel grown, not stapled on.
- [ ] Bias all modulation choices toward fluid continuity and soft momentum so the body reads as gel/liquid under motion.
- [ ] Rework stretch so it amplifies or steers the organic field rather than simply adding signed radial spikes.
- [ ] Rework wobble so it lives inside the same shape system rather than acting as an unrelated second shell.
- [ ] Re-test how pockets interact once the base silhouette is no longer circular; pockets should enrich local reaction, not reintroduce hard spear-like lobes.
- [ ] Replace the current "small offsets on top of scalar radius" motion model with a contour-space solver/update rule:
  - contour samples advect/slew under bounded pressure
  - neighboring samples smooth each other like viscous material
  - volume/headroom is preserved globally so local lift does not become card-filling scalar growth
- [ ] Derive the final rendered contour from the solved profile directly, not from scalar radius plus post hoc highlight tricks.

**Safety-floor redesign checklist:**
- [ ] Keep anti-pinch protection, but make it the final protection layer rather than the main thing preserving silhouette readability.
- [ ] Replace the current "many preservation clamps fighting many additive layers" feel with one clear minimum-radius contract.
- [ ] Add a continuity check around the wrap point so floors cannot hide a seam until a louder passage reveals it again.
- [ ] Validate that the floor still allows soft `)` / `(` valleys.

#### 5C. Blob Stage / Signal / Runtime Cleanup

**Intent:** Keep the signal-contract fixes while reducing Blob-specific drift and hidden complexity.

**Current risk:**
- Blob already needed careful work to escape the dead-vs-blowout trap.
- Unshaped redesign must not accidentally re-open that family by making the body size, stage ladder, or glow path much hotter again.

**Signal/runtime checklist:**
- [ ] Keep the existing Blob/Bubble signal-contract guardrails from `Docs/Historical_Bugs.md` intact.
- [ ] Preserve the separation between:
  - calmer live bands for whole-body size
  - hotter stage-driving support
  - transient/event assists
- [ ] Re-scope whole-body size so it is intentionally weaker than local contour pressure:
  - whole-body size should provide body presence
  - local contour motion should provide the fluid read
- [ ] Audit whether unshaped Blob still needs all current technical stage controls as true runtime knobs, or whether some are now just implementation residue.
- [ ] Reduce stage drift debt:
  - either the CPU helper becomes the authoritative stage contract and the shader only renders the override
  - or the duplicated shader math is intentionally mirrored and tested as such
- [ ] Keep startup/runtime parity: no special seeding path that makes Blob look "correct only after a few frames".
- [ ] Reconfirm ghost behavior against the redesigned body so the ghost remains a retained-peak sibling, not a second dominant blob.
- [ ] Remove the remaining runtime assumption that the main user-visible energetic response should come from scalar radius growth.

**Tests to add or strengthen in this phase:**
- [x] Wrap continuity regression for unshaped Blob radius logic.
- [x] A bounded "non-circular at rest" regression that proves the base silhouette still varies even when motion is calm.
- [~] Anti-pinch regression proving valleys remain soft without center collapse.
- [~] Stage/body regression confirming the redesign does not reintroduce hot baseline blowout.
- [~] Pocket regression confirming local pocket reactions still function after the new radius-field composition.
- [ ] Add rendered-outcome regressions instead of math-only proxies where practical:
  - silhouette occupancy / containment checks against the card
  - visible non-circularity checks against rasterized/profile samples, not just scalar helper outputs
  - inward-liquid visible-band checks that fail if the layer is mathematically active but visually negligible
  - highlight shape checks that fail if the highlight collapses back into center-bright sphere shading
  - limiter-presence checks that fail if the inward liquid ever fully disappears while enabled

#### 5D. Blob Settings Exposure Audit And UI Cleanup

**Intent:** Shaped Blob should only show settings it genuinely uses. Unshaped Blob should own the generic freeform motion controls. This must be explicit in UI, binding, model, runtime, presets, and docs.

**Current reality to preserve:**
- Some current Blob controls are already intentionally hidden in shaper mode.
- Some legacy technical/runtime fields still exist even though they are not part of the canonical authored surface.
- `blob_reactive_deformation` appears especially suspicious for shaped Blob because the current shaped runtime zeros the generic wobble/stretch path, which means this control may be effectively dead there.

**Shared settings that shaped Blob genuinely appears to use and should stay visible if confirmed in implementation:**
- [ ] `blob_pulse` / Body Response
- [ ] `blob_pulse_release_ms` / Body Release
- [ ] shared appearance controls (color / edge / glow / ghost) that still feed the shaped render path
- [ ] optional inward-border liquid controls if the implementation is kept as a true contour-following shared Blob-family presentation effect rather than as an unshaped-only deformation trick
- [ ] `blob_topology`
- [ ] `blob_ring_thickness` when ring topology is active
- [ ] `blob_shaper_react_strength`
- [ ] `blob_shaper_idle_motion`
- [ ] `blob_shaper_audio_motion`
- [ ] Blob Shape Editor entrypoint / authored node controls

**Controls that should remain unshaped-only unless a future implementation genuinely uses them in shaped mode:**
- [ ] `blob_reactive_deformation`
- [ ] `blob_constant_wobble`
- [ ] `blob_reactive_wobble`
- [ ] `blob_stretch`
- [ ] any pocket-related surface

**Controls that should stay hidden/pinned/retired unless a deliberate design change revives them:**
- [ ] `blob_shaper_base_strength` as a meaningful user-facing authored control
- [ ] retired authored technical blob keys already called out in `Spec.md`

**Settings/UI checklist:**
- [ ] Audit the full path for each Blob control:
  - builder visibility
  - settings binding collect/load
  - model/defaults
  - runtime config apply
  - actual shader/solver/runtime use
  - preset authoring/repair
- [ ] Mark every Blob control as:
  - shared
  - unshaped-only
  - shaped-only
  - technical-only hidden runtime support
- [~] Remove or hide any control that is dead in shaped mode.
- [ ] If shaped Blob genuinely needs a control that is currently hidden, expose it explicitly rather than letting it remain an invisible dependency.
- [x] Add a regression test or static audit that shaped Blob does not accidentally consume unshaped-only controls again.

#### 5E. Implementation Order For The Unshaped Blob Redesign

**This is the intended execution order once coding starts:**
- [~] Lock down the ownership audit first so settings/UI/runtime separation does not move under our feet mid-redesign.
- [ ] Introduce or extract the unshaped Blob helper layer/module before large behavior changes if that will make the redesign cleaner.
- [~] Replace the unshaped base silhouette model first.
- [~] Re-tune stretch/wobble against the new base silhouette second.
- [~] Reintegrate pockets against the new silhouette third.
- [ ] Only then prune/hide dead shaped/unshaped settings and update bindings/presets/docs.
- [ ] Finish with tests and runtime eyes, not the other way around.

**Immediate corrective implementation order after the latest runtime review:**
- [ ] Decide whether the next pass stays in shared Blob files or moves to an explicit unshaped/shaped split first.
- [ ] If split-first wins, isolate the files/helpers before changing behavior again and optionally dev-gate the new path until visual validation catches up.
- [ ] Freeze further scalar-radius-only tuning except where needed to keep runtime usable during the transition.
- [ ] Define the unshaped runtime profile contract in code and tests:
  - sample count
  - rest profile generation
  - fluid pressure update inputs
  - smoothing / slew / containment rules
  - explicit `body_outer_profile`, `inner_liquid_profile`, and `minimum_gap_profile` terminology
- [ ] Extend that contract with limiter-presence semantics:
  - retreat floor
  - visible-band floor
  - positive gap floor
- [ ] Add a solved-envelope regression that fails if the body can exceed the intended containment envelope by more than a tiny overshoot margin.
- [ ] Add a limiter-persistence regression that fails if inward liquid visibility or body/liquid gap falls to zero under synthetic hot frames.
- [ ] Rebuild inward liquid as a persistent contour-following limiter, not a tint mix.
- [ ] Rebuild the highlight/specular as a contour-attached slime streak rather than orb shading.
- [ ] Only after those contracts hold, retune pockets and remaining body response against the new contour solver.

**Likely code touchpoints when implementation begins:**
- `widgets/spotify_visualizer/shaders/blob.frag`
- `widgets/spotify_visualizer/renderers/blob.py`
- `widgets/spotify_visualizer/blob_math.py`
- `widgets/spotify_bars_gl_overlay.py`
- `ui/tabs/media/blob_builder.py`
- `ui/tabs/media/blob_settings_binding.py`
- `core/settings/models.py`
- `core/settings/defaults.py`
- `core/settings/visualizer_presets.py`
- `tools/visualizer_preset_repair.py`
- Blob-focused tests under `tests/`
- `Spec.md`, `Docs/TestSuite.md`, and possibly `Docs/Visualizer_Reference.md`

#### 5F. Shaped Blob Follow-On Plan - Better Reactions Without Breaking The Contour Solver

**Status of this sub-track:** `[ ]` Follow-on, but now promoted in urgency because shaped Blob currently reads as under-reactive in live use

**Goal:** Give Blob Shaper richer live response while preserving its authored-contour identity.

**Important constraint:** Shaped Blob must become more alive through **contour-space reaction**, not by importing generic unshaped wobble/stretch/pocket behavior wholesale.

**Current shaped-Blob strengths to preserve:**
- authored base contour owns rest shape
- authored reaction contour defines local travel envelope
- routed energy field defines local ownership
- one CPU-solved contour feeds fill/ring/glow/outline consistently

**Main weakness to improve:**
- In practice the shaped path can still feel too uniform or too "one contour simply expands/contracts everywhere", especially compared to how expressive the editor suggests the shape could become.
- Live expectation has now been made explicit by user feedback:
  - shaped Blob should have noticeably better reactions than today
  - those reactions must stay contour-authored and fluid
  - if the present shared runtime blocks that, splitting shaped ownership further is now preferred over keeping shaped response timid

**Shaped reaction ideas worth planning explicitly:**
- [ ] **Node-lane ripple / wobble**
  - When a node's attached energy type becomes active, add a small contour-space ripple centered on that authored ownership region.
  - This should travel along the contour locally, not detach into a second shell.
- [ ] **Directional residual pull**
  - Let active routed regions retain short-lived contour momentum after the immediate hit so the response has follow-through instead of only reach-and-release.
- [ ] **Neighbor spill**
  - A strongly driven node region may lend a smaller delayed influence to adjacent sectors so the contour reads as one living body rather than isolated bins.
- [ ] **Local overshoot with decay**
  - Strong positive drive may briefly overshoot the reaction contour slightly in the owning region, then settle back.
  - This must stay softer and more local than unshaped Blob's freeform deformation.
- [ ] **Edge-travel ripple**
  - Strong hits could launch a short-lived contour ripple that rides along the authored outline from the energized region.
- [ ] **Pressure memory per authored lane**
  - Keep a tiny per-region decay memory so repeated hits on the same routed node feel cumulative rather than identical one-offs.

**Shaped follow-on checklist:**
- [ ] Decide whether shaped Blob can be improved safely inside the current shared runtime, or whether it should get a more explicit shaped-only runtime/helper surface first.
- [ ] If needed, split shaped reaction ownership behind a Blob-internal dev gate before tuning stronger reactions.
- [ ] Decide whether the first new reaction feature lives:
  - inside the contour solver
  - as a post-solve contour-space residual
  - or as a tiny per-region memory field consumed by the solver
- [ ] Prefer contour-space residuals over fragment-space shell tricks.
- [ ] Keep the authored base contour readable even during strong reactions.
- [ ] Keep the reaction contour as the dominant local target; new motion should enrich it, not replace it.
- [ ] Ensure ring mode uses the same enriched contour without repainting the hollow center.
- [ ] Expose only the shaped-specific controls that are truly needed after the first reaction feature lands.
- [ ] Do not add five new shaped controls before proving one reaction family is worth keeping.

**High-detail shaped reaction program:**
- [ ] Phase 1: establish stronger local ownership without adding new public controls:
  - region-local reaction gain
  - residual follow-through per authored lane
  - gentle neighbor spill
  - contour-safe damping so the shape does not become sector-blocky
- [ ] Phase 2: add visible fluid response features:
  - node-lane ripple/wobble
  - short-lived overshoot with recovery
  - tangential travel along the contour instead of pure radial expand/contract
- [ ] Phase 3: evaluate whether any of that deserves a user-facing control:
  - only expose controls that clearly matter
  - keep shaped UI lean
  - prefer good authored defaults over a forest of knobs

**Shaped visual validation checklist:**
- [ ] A driven node region should visibly react more than unrelated regions.
- [ ] Adjacent contour motion should feel connected, not sector-blocky.
- [ ] Rest shape must still match the editor's authored base contour.
- [ ] Strong reactions must not create shell peel, seam wedges, or hollow-center repaint bugs.
- [ ] Shaped Blob should feel more expressive than today without becoming "unshaped Blob wearing a contour mask".
- [ ] Even when reactions become richer, the contour motion should still read as fluid/gel-like rather than as hard segmented mechanical articulation.

#### 5G. Optional Inward Border Liquid Layer

**Status of this sub-track:** `[~]` Planning locked, settings/runtime plumbing landed, conservative contour-following render path landed, fluid retreat/pressure-balancing pass still pending

**Goal:** Add an optional Blob-family interior edge-liquid effect that looks like fluid is advancing inward from the border while the Blob body continues animating underneath it.

**User intent to preserve:**
- The effect should feel like **liquid coming inward from all edges**, not like a second blob, glow shell, or fog overlay.
- It should be visibly reactive, but it must remain **contained**.
- The inward flows must **never touch each other**. Treat this as a hard visual rule, not a tuning suggestion.
- The color should respond to **Taste The Rainbow** the same way other Blob color surfaces do.
- The overall read should remain fluid/gel-like and should help reinforce the Blob family identity rather than compete with it.

**Recommended ownership model:**
- Treat this as a **shared Blob-family presentation layer** if implemented cleanly:
  - it follows the active Blob contour
  - it works for shaped and unshaped Blob without importing unshaped deformation controls into shaped mode
  - it is visually downstream of the contour/body solution, not a new contour-authoring system
- Do **not** implement it as a second independent body SDF that can visually overtake the main Blob.
- Do **not** let it become another stage/blowout path.

**First implementation scope recommendation:**
- [ ] Support **filled Blob** first.
- [ ] For **Blob Shaper**, only enable it if the layer can follow the CPU-solved contour cleanly without introducing contour ownership bleed.
- [ ] For **ring topology**, decide explicitly before implementation:
  - either support only the outer contour advancing inward toward the ring wall
  - or disable the feature in ring mode for v1 if keeping the "never touch" rule cleanly is too risky
- [ ] Document the v1 scope clearly in `Spec.md` once chosen; do not leave ring behavior ambiguous.

**Mandatory visual rules:**
- [ ] The inward liquid front must always leave a visible interior gap; opposite sides may approach but never meet.
- [ ] The inward liquid front must never disappear completely while the feature is enabled.
- [ ] Retraction is allowed and required under pressure, but the rule is now:
  - retreat yes
  - complete collapse no
  - reactivity must be visible without sacrificing continuous presence
- [ ] The layer must stay thinner and more secondary than the main Blob body.
- [ ] The inward front must follow the Blob contour organically instead of ignoring shape and reading as a rectangular/card-space wipe.
- [ ] The layer must remain visibly attached to the border source; it should look emitted from the contour, not spawned in the middle.
- [ ] The front must not flatten the Blob into a uniformly filled center or create a fake "the whole Blob is hot" read.
- [ ] The effect must still look fluid under both calm drift and strong passages.

**Hard safety constraints:**
- [ ] The inward liquid has a strict maximum depth derived from local contour thickness/body radius, not just a free scalar.
- [ ] The cap must guarantee non-contact between opposing fronts even at max reactivity and max size.
- [ ] The cap must be local enough that narrow contour regions do not suddenly bridge first.
- [ ] If the contour/body becomes too thin locally, the inward liquid must shrink there instead of clipping, crossing, or creating hard seams.
- [ ] The effect must never become the dominant explanation for body size growth; it is an interior edge effect, not a support/stage amplifier.

**Settings surface to plan now:**
- [ ] `blob_inward_liquid_enabled`
- [ ] `blob_inward_liquid_reactivity`
  - user-facing label: `Inward Liquid Reactivity`
  - meaning: how strongly the liquid front responds to energy
- [ ] `blob_inward_liquid_max_size`
  - user-facing label: `Inward Liquid Maximum Size`
  - meaning: the maximum inward travel/depth before hard safety clamps stop it
- [ ] `blob_inward_liquid_color`
  - user-facing label: `Inward Liquid Color`
  - must route through Taste The Rainbow hue shifting the same way other Blob colors do

**Settings/UI guidance:**
- [ ] Keep the feature optional and clearly labeled as an interior Blob effect, not as glow.
- [ ] Put the controls in Blob appearance/advanced space, not in technical unless the v1 implementation needs hidden support knobs.
- [ ] Do not expose extra hidden tuning sliders for edge falloff, turbulence, bridge prevention, etc. in v1.
- [ ] If the effect is shared across shaped and unshaped Blob, the same three visible controls should drive both.
- [ ] If shaped/ring support must differ in v1, the builder must gate visibility honestly instead of silently ignoring the controls.

**Preferred technical direction:**
- [ ] Build the layer from the **resolved Blob contour/body distance field**, not from card-space edges.
- [ ] Compute an inward-front mask from the interior side of the Blob SDF so the effect is contour-following by construction.
- [ ] Drive the front depth from a bounded reactive field that never exceeds the local no-contact limit.
- [ ] Prefer a soft advecting/rippling liquid read over static inner outlining.
- [ ] Reuse the Blob color pipeline so Taste The Rainbow affects the liquid color consistently.
- [ ] Keep the effect downstream of shaped/unshaped contour ownership:
  - unshaped Blob still owns body deformation
  - shaped Blob still owns contour solving
  - inward liquid only shades/animates along the already-resolved interior edge
- [ ] Stop treating visible liquid as "tint the same solid fill near the edge":
  - give the layer its own readable band/front
  - allow it to darken/displace the base fill locally so the eye can actually see it
  - make visibility resilient even when the fill colour is strong and saturated

**No-contact rule implementation ideas to evaluate:**
- [ ] Derive a local maximum inward distance from the local body radius/contour thickness and clamp the liquid front to a strict fraction of that span.
- [ ] Consider a conservative hard cap such as "never exceed 35-40% of local inward span" if that reads well visually.
- [ ] Add an additional soft fade before the hard cap so the front visually thins before reaching its maximum.
- [ ] For ring mode, if supported, compute the cap against the wall thickness rather than against the full Blob radius.
- [ ] Add a regression check that opposing fronts still leave a positive gap under max settings.

**Motion language ideas worth keeping in scope:**
- [ ] The front can wobble/ripple slightly with energy, but only tangentially/organically along the contour.
- [ ] The front should thicken and advance under stronger passages, then recede smoothly.
- [ ] The interior motion should feel like viscous liquid pressure, not striped marching bands or sawtooth pulses.
- [ ] Local contour irregularities should subtly influence the liquid front so it feels attached to the body shape.

**Recommended reaction-source contract:**
- [ ] The inward liquid should be driven by a layered motion model rather than by a single loudness scalar.
- [ ] The primary always-on source should be a **calm base drift**:
  - a low-amplitude contour-following crawl so the layer never looks frozen when audio is quiet
  - this should provide living fluid presence without reading as random jitter
- [ ] The primary reactive source should be **bounded audio pressure**:
  - mostly overall/support energy plus a meaningful amount of mid energy
  - only a smaller bass contribution so the layer does not behave like a second whole-body expansion path
  - enough local variation that different stretches of the contour do not all breathe identically
- [ ] **Transient** should be treated as a subordinate accent, not the main driver:
  - useful for launching a brief ripple, adding a temporary edge-thickening accent, or sharpening the first moment of retreat
  - not suitable as the main depth source because it will read too flickery and too event-led on its own
- [ ] The most important local source should be **body-proximity retreat**:
  - if the live Blob body expansion threatens to consume the interior gap, the inward liquid should yield locally
  - that retreat should happen where the body is nearest so the viewer reads a pressure interaction rather than a global size reduction
  - the result should be a reactive gap that opens where contact would otherwise be threatened
- [ ] Retreat should prefer **tangential sliding** over hard popping:
  - the threatened segment can pull back while neighboring contour stretches continue drifting
  - some of that displaced pressure can travel sideways along the border as a soft ripple/wave
  - this should help the layer feel like one continuous liquid rather than many disconnected slots
- [ ] Include **pressure balancing** so strong retreat in one region can gently redistribute motion to adjacent regions:
  - this should be subtle and damped
  - the goal is to create fluid continuity, not a full circulation simulation
- [ ] The effect should prioritize **smoothness without imposed lag**:
  - avoid artificial hold/delay stages if possible
  - prefer immediate response with critically damped smoothing and bounded velocity so motion feels responsive but never crunchy
  - if a tradeoff is required, smoothness wins over raw snap, but the response should still feel present in the same beat rather than obviously late
- [ ] The same reaction contract may be offered to shaped Blob only if it remains a **true contour-following presentation layer**:
  - no importing unshaped wobble/stretch controls
  - no shaped ownership bleed
  - the layer should simply read the solved shaped contour and animate inward from that boundary
- [ ] The inward liquid should keep a **gel/fluid identity** at every energy level:
  - calm passages = slow creep, tiny pressure ripples, living edge drift
  - active passages = deeper advance, more visible tangential ripple, local retreat under pressure
  - extreme passages = stronger retreat and safety clamping before any chance of opposing-front contact

**Recommended technical decomposition for the motion field:**
- [ ] Build the final inward-depth driver from four bounded terms:
  - base drift term
  - audio pressure term
  - body-proximity retreat term
  - tangential ripple / pressure-redistribution term
- [ ] Treat retreat as subtractive priority logic:
  - no-contact preservation outranks decorative advance
  - if advance and retreat conflict, retreat wins locally
- [~] Add a separate retained-band floor after retreat:
  - not enough to look static
  - enough to prevent visual disappearance
  - must work in both colour-strong and colour-weak presets
- [ ] Keep the ripple/redistribution term secondary so it enriches the contour instead of causing detached traveling bands.
- [ ] If shaped Blob support is enabled, consume the same shared inward-liquid settings but derive proximity/retreat from the solved shaped contour thickness/gap field rather than from unshaped deformation internals.

**Implementation checklist:**
- [ ] Decide v1 scope: filled only vs filled + shaped vs filled + shaped + ring.
- [ ] Define the no-contact cap mathematically before writing the shader.
- [~] Add settings/model/defaults/preset plumbing for the three visible controls and enable toggle.
- [x] Add builder rows and visibility gating.
- [x] Route runtime config through the full creator/config apply/overlay path:
  - creator/model apply must pass the fields
  - config apply must store them on the live widget
  - GPU extra payload build must include them
  - `SpotifyBarsGLOverlay.set_state(...)` now accepts and stores them without frame-push failure
  - the shader/runtime side now uploads the matching uniforms intentionally
- [~] Implement the contour-following inward mask in `blob.frag`.
- [x] Ensure Taste The Rainbow hue rotation is applied to the liquid color output.
- [~] Add focused tests for:
  - persistence round-trip
  - shaped/unshaped/ring visibility gating
  - no-contact cap math where practical
  - color pipeline / rainbow interaction contract where practical
  - nonzero retained-band behavior under hot retreat states
- [ ] Validate visually that the effect remains secondary to the Blob body.
- [ ] Validate visually that the effect is actually visible at all on strong authored fill colours.
- [~] Add a regression that fails if enabled inward liquid can become visually zeroed or mathematically gapless under hot synthetic frames.
- [x] Add synthetic-audio Blob interaction regressions for the retreat/pressure-balancing pass:
  - drive staged body expansion and inward liquid response together from authored synthetic band envelopes
  - prove the inward layer reacts in the same scenario as the body instead of lagging behind it
  - prove the front yields or thins when body pressure threatens the interior gap
  - prove the body and inward layer can both stay active without center contact / blowout
  - prove a pressured peak can retreat first and then relax smoothly on the release phrase without losing the protected gap
  - prove redistribution remains active as part of the fluid interaction path rather than collapsing into a pure depth-only rule

**Landed so far for this sub-track:**
- [x] Added canonical settings/model/defaults/runtime fields for:
  - `blob_inward_liquid_enabled`
  - `blob_inward_liquid_reactivity`
  - `blob_inward_liquid_max_size`
  - `blob_inward_liquid_color`
- [x] Added Blob builder controls for the inward liquid layer and honest UI gating so the detail rows only appear when the feature is enabled.
- [x] Kept the controls shared across shaped and unshaped Blob at the settings/runtime level without importing unshaped deformation controls into shaped mode.
- [x] Carried the new fields through settings binding, live widget defaults, config apply, model apply, GPU extra payload transport, overlay state storage, and blob uniform upload.
- [x] Added focused regressions for settings persistence/round-trip, builder visibility gating, and creator/runtime plumbing.
- [x] Finished the final overlay handoff seam:
  - `SpotifyBarsGLOverlay.set_state(...)` accepts the new inward-liquid kwargs
  - the overlay stores them safely on live state
  - blob-mode uniform lookup/upload now includes the inward-liquid fields
  - a focused regression now mirrors the real frame-push contract so new Blob extras cannot silently break runtime again
- [x] Added a first shader-side filled-Blob inward liquid pass that:
  - follows the resolved Blob contour instead of card-space edges
  - stays disabled for ring mode for now
  - keeps the effect secondary to the main body
  - drives the front from calm drift plus bounded audio pressure
  - applies Taste The Rainbow to the inward-liquid color path
- [~] Added the first true fluid-interaction pass for the inward liquid:
  - shared math helper now defines the advance / retreat / redistribution contract
  - strong body pressure can locally pull the front back instead of only letting it thicken forward
  - thinner regions retreat proportionally more than roomy regions
  - the shader now mirrors that same contract instead of using a separate one-off interaction rule
- [~] Runtime research on 2026-04-17 shows the current pass is still not visually honoring the limiter goal:
  - the inward liquid can still read as missing on strong real presets/custom-slot runs
  - the next pass must add a hard visibility floor and a stricter body/liquid gap contract, not just more tint strength
- [~] Updated limiter rule after the latest runtime clarification:
  - the front already retracts, which is desirable
  - the remaining failure is that the reactive contract does not preserve enough continuous presence/readability
  - the next pass must therefore keep the retreat logic but layer in a retained-band floor rather than simply reducing retreat
- [~] First retained-band implementation landed in code/tests:
  - retreat still wins locally under pressure
  - the inward front now clamps to a nonzero retained band instead of collapsing fully
  - unshaped support-floor/body-radius math was also cooled further so the contour solver can visually matter more
- [x] Added focused inward-liquid regressions covering:
  - disabled/ring-off behavior
  - positive-gap preservation
  - energetic advance plus pressure-driven retreat
  - narrow-region yielding
  - synthetic body + inward-liquid co-reaction under one authored envelope
  - stronger body-threat retreat at a shared size cap
  - rise/release phrase behavior with preserved gap and active redistribution
- [ ] The more advanced no-contact retreat / pressure-balancing / body-threat gap behavior is no longer merely conceptual, but it still needs further visual tuning and likely one more pass before this can be considered final-quality fluid motion.

#### 5G.1. Blob Highlight / Specular Redesign

**Status of this sub-track:** `[ ]` Newly promoted after the 2026-04-17 runtime review proved the current highlight still reads as sphere shading

**Problem statement:**
- The user wants a white vector-like slime/ooze/oblong specular that moves with the fluid body.
- The current runtime still reads as "solid orb with highlight" because the highlight is layered after the body and is not truly attached to the resolved contour language.

**Concrete direction:**
- [ ] Replace center/depth brightening with one or more elongated contour-attached highlight streaks.
- [ ] Drive highlight placement from the resolved unshaped contour field, not just raw `uv`.
- [ ] Let highlight streaks drift/warp with the same fluid solver or local contour-space offsets that move the body.
- [ ] Keep highlights broad and soft:
  - avoid sharp wedge caps
  - avoid a single static top slice
  - avoid symmetric orb shading
- [ ] Use at least one "bloblet" or secondary short streak so the highlight reads like wet material rather than a single plastic shine.
- [ ] Validate against screenshots that the highlight still reads correctly when the body deforms off-round.

**Guardrails:**
- [ ] Do not reintroduce a generic radial white center under a new name.
- [ ] Do not let highlight placement become detached from the blob contour and hover in card space.
- [ ] Do not let highlight strength wash out the inward liquid band or the body silhouette.

**Likely code touchpoints for this sub-track:**
- `widgets/spotify_visualizer/shaders/blob.frag`
- `widgets/spotify_visualizer/blob_math.py`
- `widgets/spotify_visualizer/config_applier.py`
- `rendering/spotify_widget_creators.py`
- `widgets/spotify_bars_gl_overlay.py`
- `ui/tabs/media/blob_builder.py`
- `ui/tabs/media/blob_settings_binding.py`
- `core/settings/models.py`
- `core/settings/defaults.py`
- `core/settings/visualizer_presets.py`
- `tools/visualizer_preset_repair.py`
- Blob-focused tests under `tests/`

**Guardrails specific to this feature:**
- [ ] Do not fake this with a stronger glow; glow and inward liquid must remain distinct concepts.
- [ ] Do not let the inward liquid hide seam bugs or anti-pinch problems that still need solving in the body itself.
- [ ] Do not add separate saved settings for shaped-vs-unshaped inward liquid unless the first shared design proves impossible.
- [ ] Do not let the effect revive the signal-contract bug family by introducing a new uncapped hot-reactivity path.
- [ ] Do not let the inward liquid visually "touch across the center" even momentarily on strong hits.

**Long-term documentation checklist for the whole Blob program:**
- [ ] Update `Spec.md` once the ownership split is real, not speculative.
- [ ] Update `Docs/TestSuite.md` with the new Blob regression fence descriptions.
- [ ] Add a short "Blob mode family mental model" note somewhere stable once the redesign settles:
  - unshaped Blob = procedural body language
  - Blob Shaper = authored contour language
  - shared settings = presentation/body pulse only where genuinely common
  - inward border liquid = optional contour-following interior presentation layer if implemented

#### 5H. Blob Cleanup / De-Legacy Pass

**Status of this sub-track:** `[~]` Legacy Blob forward-migration cleanup started; broader source-authoritative preset/tool sweep still pending

**Intent:** Blob should end this redesign with a clean authored settings/preset surface. We do not want compatibility shims, retired keys, or repair tooling that silently reintroduces old Blob fields and causes regressions later.

**Non-negotiable rule:**
- [ ] Prefer removal/migration over indefinite backward compatibility for retired Blob keys unless a very narrow transitional step is absolutely necessary.
- [ ] Do not leave "legacy but still half-live" Blob fields in settings JSON, curated presets, shipped preset mirrors, or repair tooling once the new contract is established.

**Blob key cleanup checklist:**
- [ ] Produce the final canonical Blob authored-key list after the redesign stabilizes:
  - shared Blob-family keys
  - unshaped-only keys
  - shaped-only keys
  - technical-only hidden runtime support
- [ ] Explicitly retire old Blob authored/runtime keys that should no longer survive in saved state or curated presets, including at minimum:
  - `blob_pulse_cap`
  - `blob_stage2_release_ms`
  - `blob_stage3_release_ms`
  - any shaped-dead authored key we decide to fully remove rather than merely hide
- [~] Keep current active unshaped runtime-authored keys preserved in normalization until the redesign truly replaces them:
  - `blob_stage_gain`
  - `blob_core_scale`
  - `blob_core_floor_bias`
  - `blob_stage_bias`
  - `blob_stretch_tendency`
  - `blob_stretch_inner`
  - `blob_stretch_outer`
  - these are active today and must not be treated as deprecated by settings/custom-slot/preset tooling
- [ ] Decide whether `blob_reactive_deformation`, `blob_constant_wobble`, `blob_reactive_wobble`, and `blob_stretch` remain authored unshaped controls or are replaced by cleaner fluid-language controls later in the redesign.
- [ ] Once the final decision is made, remove any superseded Blob controls from:
  - live settings serialization
  - preset authoring
  - preset repair
  - preset regeneration
  - docs/spec references

**Settings JSON cleanup checklist:**
- [~] Add an explicit settings-normalization step for Blob-owned settings that drops retired Blob keys instead of preserving them indefinitely.
- [ ] Ensure saving current settings writes only canonical Blob keys.
- [ ] Ensure loading a modern settings file does not recreate removed Blob keys as defaults or hidden runtime leftovers.
- [ ] Clean existing local settings JSON fixtures/tests so they reflect the new canonical contract instead of mixed old/new Blob eras.

**Curated preset cleanup checklist:**
- [x] Remove retired Blob keys from authored presets under `presets/visualizer_modes`.
- [ ] Add the new inward-liquid keys only where they are intentionally authored; do not bulk-backfill them everywhere unless they are part of the desired authored preset language.
- [ ] If shaped and unshaped preset families need different inward-liquid defaults, author that intentionally instead of relying on hidden runtime fallback behavior.
- [ ] Regenerate shipped preset mirrors only after the authored source tree is clean.
- [ ] Verify no generated preset tree resurrects removed Blob keys.

**Preset-tooling cleanup checklist:**
- [~] Update `core/settings/visualizer_presets.py` so Blob repair/normalization removes retired Blob keys instead of carrying them forward, while preserving active unshaped keys still used by runtime.
- [~] Update `tools/visualizer_preset_repair.py` so repair/audit only targets truly retired Blob keys and does not misclassify active unshaped keys as deprecated.
- [ ] Audit any preset migration helpers or snapshot normalizers that currently preserve old Blob fields "just in case".
- [~] Keep the source-tree-authority rule intact: authored presets define Blob keys, tools do not invent them.

**Documentation cleanup checklist:**
- [ ] Update `Spec.md` with the final Blob key surface once the redesign is stable enough.
- [ ] Update `Docs/TestSuite.md` with Blob regression coverage expectations, including inward-liquid interaction tests.
- [ ] Add or extend `Docs/Historical_Bugs.md` if the de-legacy pass closes a known regression family such as hidden Blob runtime keys causing preset/settings drift.

**Tests to require before closing this sub-track:**
- [x] A preset normalization test proving retired Blob keys are removed rather than silently preserved.
- [ ] A settings serialization test proving saved Blob configs only contain canonical keys.
- [x] A repair-tooling regression proving `tools/visualizer_preset_repair.py` does not resurrect removed Blob keys.
- [ ] A curated preset round-trip regression proving authored Blob presets survive repair/regeneration without key creep.
- [x] A synthetic-audio Blob interaction regression proving the main body and inward liquid can both react in the same authored scenario without contact or blowout.

**Execution order for this cleanup pass:**
- [x] Finish the core inward-liquid fluid interaction pass first so the final authored surface is known.
- [ ] Then lock the canonical Blob key set.
- [ ] Then clean settings serialization and preset normalization.
- [ ] Then clean curated presets and shipped mirrors.
- [ ] Then clean repair/regeneration tooling.
- [ ] Finish by updating docs and adding the anti-resurrection tests.

**Landed so far for this sub-track:**
- [x] Removed Blob legacy forward-migration behavior from preset normalization for retired stage/stretch keys instead of translating them into modern authored keys.
- [x] Expanded Blob legacy retirement coverage in preset repair/audit so the old `blob_stretch_x_bias` / `blob_stretch_y_bias` pair is treated as deprecated too.
- [x] Added normalization/settings validation regressions proving retired Blob keys are dropped from live settings payloads rather than silently preserved or translated forward.
- [x] Added preset repair/migration regressions proving deprecated Blob keys are removed instead of being used to synthesize new authored Blob values.
- [x] Moved the curated preset repair tool to a source-authoritative stance for optional authored keys:
  - sanitize keeps authored keys plus deliberate alias promotions
  - sanitize no longer backfills missing optional authored visualizer keys from defaults
- [x] Ran batch repair across the curated preset tree and removed retired Blob keys from shipped authored Blob presets.
- [x] Ran curated preset reindex after the tool cleanup, which resolved the sine-wave duplicate preset index issue through the supported tool path.
- [~] 2026-04-17 custom-slot/runtime research uncovered a second cleanup bug:
  - custom-slot normalization was silently dropping active unshaped Blob keys because `SpotifyVisualizerSettings` did not serialize them
  - preset migration/repair language had drifted into calling those same active keys "retired"
  - model serialization and preset normalization are now corrected, and repair/audit has been aligned to the same contract
- [ ] The remaining cleanup is now the broader canonical-surface pass:
  - deciding the final authored unshaped Blob key set
  - ensuring saved settings write only that canonical set
  - auditing any remaining normalization/migration seams for hidden Blob key preservation
  - regenerating shipped mirrors once the authored source tree is considered final
   
### 6. Preset Tooling Source-Tree Authority

**Status:** `[ ]` Planned, not started
**Priority:** Medium

**Goal:** Prevent repair/regenerate tooling from overwriting authored presets or resurrecting retired presets.

**Known issues:**
- `tools/visualizer_preset_repair.py --repair-all` backfills keys that may have been intentionally omitted
- Regenerate tooling can resurrect retired presets if source tree was cleaned but generated tree wasn't
- No guard prevents adding back explicitly removed keys

**Plan:**
- [ ] Audit `_sanitize_settings` for backfill logic that adds keys not present in authored payload
- [ ] Add `--source-authoritative` mode (or make default) — remove junk but never add missing keys
- [ ] Ensure `regenerate_visualizer_shipped_presets.py` only mirrors source tree — no resurrection
- [ ] Add a test that authored presets survive a repair round-trip without gaining new keys

### 7. Cross-Mode Custom-Slot / Preset / Settings Sync Audit

**Status:** `[ ]` Planned, not started
**Priority:** Medium

**Goal:** Prevent the Blob custom-slot normalization failure family from existing in any other visualizer mode.

**Why this is now a planned program:**
- Blob exposed a specific class of bug that is easy to miss:
  - runtime actively uses keys
  - model serialization silently drops them
  - custom-slot normalization therefore strips them
  - preset repair/migration may simultaneously misclassify them as retired
- That exact drift pattern can exist in other modes even when the runtime "mostly works", so it deserves a deliberate repo-wide audit instead of waiting for more mode-specific surprises.

**Modes to cover explicitly:**
- [ ] Spectrum
- [ ] Bubble
- [ ] Blob
- [ ] Sine Wave
- [ ] Oscilloscope

**Audit checklist per mode:**
- [ ] Build the canonical active-key list from runtime ownership, not just settings docs.
- [ ] Compare that list against:
  - `core/settings/models.py`
  - defaults
  - settings normalization
  - custom-slot snapshot normalization
  - preset migration
  - preset repair/audit tooling
  - preset regeneration
  - builder visibility/binding collection
  - runtime config apply / creator handoff
- [ ] Identify keys that are:
  - active but not serialized
  - serialized but never used
  - wrongly treated as deprecated
  - preserved in one path but dropped in another
- [ ] Record any discovered drift in `Docs/Historical_Bugs.md` if it represents a real regression family rather than a one-off typo.

**Tests to require from this audit:**
- [ ] One normalization-survival regression per mode for representative active keys.
- [ ] One settings round-trip regression per mode for representative authored keys.
- [ ] One preset repair/regeneration anti-resurrection regression per mode where applicable.
- [ ] One custom-slot regression proving runtime-active keys survive save/load/normalize for each mode.

**Execution order:**
- [ ] Finish the current Blob redesign-critical work first.
- [ ] Then run the audit mode by mode, not all at once:
  1. Bubble
  2. Spectrum
  3. Sine Wave
  4. Oscilloscope
  5. final Blob recheck after the canonical Blob surface is locked
- [ ] Update docs/tests/tooling immediately as each mode is audited so the program creates lasting guardrails rather than one giant late cleanup.

---

## Deferred

## Historical Reference — Preset Override Bug Investigation (Failed Fixes)

These fixes were attempted for the settings-loss bug (Tasks 1 & 2 above) but **did not resolve the core issue**. Kept as context to avoid re-treading the same ground.

**Documentation:** [Docs/Visualizer_Preset_Override_Bug_Investigation.md](F:\Programming\Apps\ShittyRandomPhotoScreenSaver\Docs\Visualizer_Preset_Override_Bug_Investigation.md)
**History:** [Docs/Historical_Bugs.md](F:\Programming\Apps\ShittyRandomPhotoScreenSaver\Docs\Historical_Bugs.md) → `2026-04-11 — Visualizer Preset Override Bug`

- **BUG #1:** `apply_preset_to_config()` used merge overlay → Fixed with CLEAR-then-APPLY
- **BUG #2:** `save_media_settings()` collected all modes → Fixed to current mode only
- **BUG #3:** Call-site `.update()` left stale keys → Fixed to use `restore_visualizer_snapshot()`
  - Files: `ui/tabs/widgets_tab.py`, `rendering/widget_manager.py`
  - Tests: `tests/test_visualizer_preset_cycling_runtime.py`
- **BUG #4:** Technical keys lost when switching presets → `TECHNICAL_CONTROL_KEYS` preservation added
  - Files: `core/settings/visualizer_presets.py`
- **BUG #5:** Technical keys from ALL modes leaked into saves → `current_mode` parameter added
  - Files: `core/settings/visualizer_presets.py`
- **BUG #6:** `_save_settings_now()` replaced entire `spotify_visualizer` section with fresh current-mode-only data → Fixed to merge into existing config before normalizing
  - Files: `ui/tabs/widgets_tab.py`
  - Secondary: `ui/tabs/media/sine_wave_builder.py` — 10 color button lambdas converted to `bind_color_button()`
- **BUG #7:** `SpotifyVisualizerSettings.from_mapping()`, `from_settings()`, and `to_dict()` omitted all sine/osc lines 4-6 keys → normalization silently dropped them
  - Files: `core/settings/models.py` — added ~40 missing keys across all three methods
- **BUG #8:** `apply_spotify_vis_model_config()` only forwarded lines 2-3 kwargs to the runtime widget → lines 4-6 always used defaults at runtime
  - Files: `rendering/spotify_widget_creators.py`, `rendering/widget_manager.py`
- **BUG #9:** Shift updaters wrote `_sine_lineN_horizontal_shift` (wrong attr name) + shift rows used untracked `_aligned_row()` so visibility function couldn't hide them
  - Files: `ui/tabs/media/sine_wave_builder.py`
- **BUG #10:** `SpotifyBarsGLOverlay.set_state()` accepted `sine_line4/5/6_shift` and `sine_travel_line4/5/6` as parameters but **never stored them to `self`** → always used default 0 at GL level despite model and widget having correct values
  - Files: `widgets/spotify_bars_gl_overlay.py`
  - Full detail: [Docs/Historical_Bugs.md](F:\Programming\Apps\ShittyRandomPhotoScreenSaver\Docs\Historical_Bugs.md) → `2026-04-13`

**Status:** BUGs #6-#10 all fixed. #6 = cross-mode save wipe, #7 = model serialization gap, #8 = runtime config bridge gap, #9 = shift updater attr name + row visibility, #10 = overlay set_state dropped shift/travel for lines 4-6. Awaiting user runtime validation.

---

### 3. Bubble Bounce Physics

**Status:** `[ ]` Not started — promoted from Idea Box

**Goal:** Bubbles should bounce gently off each other instead of overlapping. This should be an adjustable setting. The existing `_apply_soft_separation()` in `bubble_simulation.py` already pushes overlapping bubbles apart with class-based strength — but it uses a pure position-correction approach (no velocity reflection). The result is that overlapping bubbles separate but don't visually *bounce*.

**Proposed Architecture:**

The bounce system replaces `_apply_soft_separation()` with `_apply_bounce_physics()`. On collision, each bubble pair has its velocity reflected along the collision normal (elastic collision), scaled by a bounce strength factor. Bubbles that don't bounce (governed by the Bounce % slider) fall through to the existing soft-push behavior so they still separate gently without bouncing.

**Settings to add:**

| Setting key | Type | Range | Default | Description |
|---|---|---|---|---|
| `bubble_bounce_big_pct` | int (slider) | 0–100 | 70 | % of big bubble collisions that bounce (rest overlap/soft-push) |
| `bubble_bounce_small_pct` | int (slider) | 0–100 | 30 | % of small bubble collisions that bounce |
| `bubble_bounce_big_speed` | float (slider) | 0.0–2.0 | 0.8 | Bounce speed multiplier for big bubbles (0 = no rebound, 2 = full elastic) |
| `bubble_bounce_small_speed` | float (slider) | 0.0–2.0 | 0.5 | Bounce speed multiplier for small bubbles |

**Files to touch:**

1. **`widgets/spotify_visualizer/bubble_simulation.py`**
   - Add `bounce_big_pct`, `bounce_small_pct`, `bounce_big_speed`, `bounce_small_speed` to `tick()` settings read
   - Replace `_apply_soft_separation(dt)` with `_apply_bounce_physics(dt, settings)` or extend it
   - Collision logic: for each overlapping pair, determine if this collision bounces (RNG seeded per-pair per-frame against the appropriate % slider). If bounce: reflect velocity components along collision normal, scale by speed multiplier. If not: apply existing soft-push.
   - `BubbleState` already has `vx`, `vy` — these drive stream velocity. Bounce should add to them as impulse, then let existing damping/stream logic decay the impulse over subsequent frames.

2. **`widgets/spotify_visualizer/config_applier.py`**
   - Add `_bubble_bounce_big_pct`, `_bubble_bounce_small_pct`, `_bubble_bounce_big_speed`, `_bubble_bounce_small_speed` to the bubble kwargs in `apply_vis_mode_config`
   - Add to `_append_bubble_visual_extras()` so they flow into the `build_gpu_push_extra_kwargs` pipeline (not needed for GPU but needed for sim settings)

3. **`widgets/spotify_visualizer/tick_pipeline.py`**
   - Add `bubble_bounce_big_pct`, `bubble_bounce_small_pct`, `bubble_bounce_big_speed`, `bubble_bounce_small_speed` to `sim_settings` dict in `dispatch_bubble_simulation()`

4. **`core/settings/models.py`**
   - Add 4 new fields to `SpotifyVisualizerSettings` dataclass
   - Add to `from_mapping()`, `from_settings()`, `to_dict()`

5. **`core/settings/defaults.py`**
   - Add defaults for the 4 new keys

6. **`ui/tabs/media/bubble_builder.py`**
   - Add a new collapsible bucket "Bounce" in the normal layout (after Motion)
   - 4 sliders: Big Bounce %, Small Bounce %, Big Bounce Speed, Small Bounce Speed
   - Wire with `bind_setting_signal`

7. **`ui/tabs/media/bubble_settings_binding.py`**
   - Add the 4 keys to `collect_bubble_mode_settings()`

8. **`rendering/spotify_widget_creators.py`** + **`rendering/widget_manager.py`**
   - Add the 4 kwargs to `apply_spotify_vis_model_config()` and fallback

9. **`widgets/spotify_bars_gl_overlay.py`**
   - Add the 4 fields to `__init__`, `set_state` signature and body

10. **`tools/visualizer_preset_repair.py`**
    - Run `--repair-all` after implementation to update curated presets

**Checklist:**
- [ ] Implement `_apply_bounce_physics()` in `bubble_simulation.py`
- [ ] Add 4 settings to model, defaults, and serialization
- [ ] Add Bounce bucket to `bubble_builder.py`
- [ ] Wire settings collection in `bubble_settings_binding.py`
- [ ] Wire runtime config bridge (config_applier, widget_creators, widget_manager, overlay)
- [ ] Wire tick pipeline `sim_settings`
- [ ] Run preset repair
- [ ] Test: big bubbles at 100% bounce + high speed → visible elastic rebounds
- [ ] Test: 0% bounce → same as current behavior
- [ ] Test: persistence round-trip

---

## Runtime Watchlist

- [ ] `%APPDATA%/SRPSS/settings_v2.json` repair line repeating indefinitely
- [ ] Source curated tree vs generated shipped tree drift
- [ ] Misleading helper/UI preview exceptions
- [ ] Bubble/Blob slipping back into the signal-contract trap documented in [Docs/Historical_Bugs.md](F:\Programming\Apps\ShittyRandomPhotoScreenSaver\Docs\Historical_Bugs.md)

---

## Idea Box

1. Add a shimmer/flicker regression test for Spectrum once the actual shimmer task is active using synthetic audio that shows it, then adjust it to user results until a solution is found.
