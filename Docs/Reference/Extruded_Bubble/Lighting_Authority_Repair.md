# Extruded Bubble | Physical lighting authority and BEAM/SCENE coverage repair

**Current repair contract | partial candidates, lighting acceptance remains open.** This is the detailed
architecture/evidence companion for the **single live** `Current_Plan.md` §4B
G05/G06/G27/G30/G32/G33 sequence, not a second checklist. Surface analytic
direction now shares refracted sunlight; the larger physical-field repair remains open. The operator explicitly requires BEAM restoration to the pre-regression artistic fan/axial footprint; the working-tree candidate is not yet checkpointed or visually accepted. The rejected cone/world replacement remains historical evidence (Investigation §58/§60). Physical-field experiments belong to SCENE (Investigation §63); shared positional intensity/falloff and moving art/cost acceptance stay open. Preserve the full
pre-existing EB-L/F/S/B/C/D/A/P failure inventories and the earlier R-series
investigation. An implementation, compilation, plausible still, or GPU benchmark
cannot become `[x]` without operator or capable local visual-agent acceptance.

## Current scope and protected BEAM behavior

Lighting Coverage is already an independent BEAM/SCENE choice. Restore BEAM's accepted broad artistic
fan and axial envelope from the pre-acceptance checkpoint; width1x must preserve that baseline, including
its selective fixed-depth shading approximation. Do not impose the later lateral cone, world-field march
or experimental attenuation on BEAM. Keep P1 in BEAM and preserve operator-authored presets/Custom.
SCENE owns further fixed-world Surface/Deep scattering and physical-optics experiments. Verify both choices
in real MC on the saved routes before claiming visual parity. Physical lighting remains active EB scope,
not deferred generic ray tracing or G2 shadow work.

## Source audit, corrected owners and remaining contradictions

| Existing behavior | Code evidence / underlying limitation | Explicit acceptance question |
| --- | --- | --- |
| **Sunlit Surface** uses a directional distant sunlight | `rendering/gl_programs/extruded_bubble_scene.py:scene_knobs` sets `sun`/`sun_below` from `light_direction`, `light_power=0`; analytic `spec_dir` now shares refracted `sun_below`, replacing the contradictory world-up lobe. `Light Source` coordinates are still authored | Does moving position falsely imply moving a positional sun? Provide honest control semantics; actual sun direction consistently illuminates surface, water, glints and shafts. Native directional diagnostics establish the narrow glass repair, not complete lighting acceptance. |
| **Deep Light** carries world-space Light Source, but its visible glow is primarily angular | In `extruded_bubble_scene.py:scene_knobs`, `light_source` is physical and Deep overrides `ray_source=light_source`; `rendering/gl_programs/extruded_bubble_program.py` evaluates visible glow from `dot(viewRay,normalize(uLightSource-uEye))` and high-power lobes, without true spatial falloff of an illuminated water field. Analytic glass now computes Source direction at each actual traced interface/matching lens exit; the former scene-wide authored path direction is removed from that positional consumer | Move emitter or a fixed camera: does brightness at known world samples decay with physical distance while visible light core and real glints agree? Source-point direction tests do not establish shared finite-emitter attenuation. |
| Rays have distinct Ray Source → Ray End authoring | `SHAFT_FRAGMENT` has `uRaySource`, `uRayEnd`; Surface allows a separate authored segment; Deep currently forcibly aligns the ray *start* with the Light Source while the ray end remains its authored destination | Ray controls may shape light/scattering extent, but cannot silently become a second emitter. Preserve existing authored choices and explicitly distinguish Surface/Deep semantics. |
| BEAM and SCENE are explicit independent lighting choices | BEAM restores a51aab8a fan/axial masks and matching uniforms. SCENE Surface backprojects to the water plane and adds sun-centred structure; Deep normalizes sample−Light Source to produce radial density. Both use the same half-resolution shader/blur owner; each executes one march | Preserve BEAM parity; verify SCENE fixed-source placement under camera movement, real music, all angles and bubble interaction. |
| Rejected lateral cone narrowed accepted BEAM coverage | The160d6a78 cone and b256036f world-field substitution changed accepted art. They are removed from BEAM by explicit operator request; unused cone/basis helpers are retired | Do not reapply physical-light experiments to BEAM. SCENE owns further finite-field work. |
| Direct illumination bypassed Light Strength in several consumers | Analytic glass/proxy/core gain already consumed strength; water glow/caustics, shaft compositing, particle scattering and small-shell/bead/snow sparkle now do so exactly once too. The shared particle vertex bypasses another gain for CPU-lit proxies. Deep particles use Source at the actual particle; ambient water/faint specks remain. Native linear-delta and exact prior-source comparisons are in §61 | Review moving authored art and bloom together; intensity coherence alone cannot establish finite-emitter appearance, small-shell visibility or shared positional falloff. |
| Attenuation is an approximation of four physical bubbles | BEAM retains the accepted fixed18 sample. SCENE uses the contributing density centroid and excludes Deep blockers behind Source. Both retain the bounded four-proxy/dust approximation | No claim of multiple scattering or complete volumetric shadowing; review moving soft bubble interaction. |

These are **source findings**, not proofs that every bright/clumped pixel comes from
lighting. Keep physical emission clumping, premature bubble disappearance, actual
occupancy, bloom/glow bias and camera projection as independently testable problems.

## Authoritative physical-light contract (repair design)

1. **Single physical emitter definition, mode-specific interpretation.** Sunlit
   Surface is directional illumination from above the water: world-space sunlight
   direction and surface transmission are authoritative; position handles must
   either be honestly non-positional for sunlight or explicitly edit a different
   physical ray-volume feature, with clear UI/help. Deep Light has a positional
   emitter with range/attenuation. The same physical definition feeds medium/water
   illumination, visible emitter/glow, shell glints, volumetric scattering, and
   attenuation. Remove contradictory independent directions/origins, but do not
   erase authored controls or overwrite saved values during migration.
2. **Rays describe the scattering/illuminated region, not another inconsistent
   light.** Map existing Ray Source/End, Ray Fan Spread, reach, softness, colour,
   shimmer, music/range controls to honest physical functions; preserve editable
   artistic intent and distinguish actual beam length from angular fan spread.
   For Deep Light, the physical emitter and ray origin must agree; Surface may
   shape the region that sunlight enters without claiming a local physical sun.
3. **SCENE world-space illumination remains fixed as the observer moves.** Evaluate
   bounded shaft density/scattering at world samples with genuine lateral
   extent, smooth radial boundary, appropriate longitudinal reach and
   scene-consistent source attenuation (positional distance falloff for Deep,
   depth/transmission for Surface). Use camera-dependent phase/scattering *gain*
   only, never camera-anchored *beam placement*. Downward views from below the
   surface must still see the descending illuminated region when geometrically
   in view. Avoid artificial repeated fan seams, direction flips or hard planes.
4. **Bounded optics and cost.** Keep the existing half-resolution shaft + blur
   pipeline initially; prefer finite marching, soft analytical geometry and
   selective physically grounded occlusion. Do not mandate full volumetric
   shadow maps, ray tracing, new render scheduling, worker/timer or simulation
   authority. Measure actual GL4.6 cost before extending passes or blockers.
5. **Settings compatibility.** `Light Type` remains `Sunlit Surface / Deep Light`.
   The independent `Lighting Coverage` setting (default **BEAM**)
   provides **BEAM** (the accepted artistic fan and axial Source→End envelope)
   versus **SCENE** (broad environmental illumination with coherent scattering)
   *under each existing Light Type*. It is independent of **Motion → Emission
   Geometry: BEAM/SCENE**: one governs light coverage, the other governs where
   physical bubble/particle cohorts are admitted. Do not couple or auto-switch.
   Beam Width is a0.25–3x footprint multiplier, default1x; it and the Ray path
   controls are shown only for enabled BEAM rays. Ray Fan Spread is a Surface-only control; hiding its currently
   ineffective Deep row remains open in the live plan. SCENE ignores the beam path/width
   controls and uses fixed-world scattering with the selected physical emitter.
   Reuse one emitter/shader authority. Preserve existing effective behavior,
   mutable preset values, current Custom, defaults and reset semantics; no
   automated preset rewrite or protected/frozen artistic golden. Decide/verify
   any new persisted default explicitly before implementation, rather than
   silently assuming the emission default dictates light coverage.

## Delivery boundaries and acceptance

**Latest operator override:** restore BEAM from the pre-acceptance checkpoint, isolate subsequent experiments
to SCENE, and preserve saved MC display routes. This supersedes the earlier shared-cone/world-field delivery
approach below; the earlier attempts and failures remain evidence, not current BEAM behavior. See §63–64.


BEAM defaults and width1x preserve existing presets, specifically P1. Broad coverage, internal variation and
soft bubble interaction are the visual reference. BEAM intentionally retains its accepted two-depth fan masks
and fixed18-unit selective attenuation; physical replacements must not silently alter that baseline. SCENE
illuminates the fixed tank independently of stream emission and authored beam End/width. Its Surface/Deep
source interpretation remains mode-specific. SCENE attenuation must use actual contributing medium, including
fan-only light when procedural density is zero; the current binary-support/eye-sample defect remains open.
A selector, plausible still or shader match is not full finite-emitter/falloff/art compliance.

**Bounded Step B intensity candidate (§61), before distance.** Existing Light Strength now reaches analytic glass,
glint proxies, visible Deep core/probe sun, water glow/caustics, shaft compositing, particle direct scattering
and tiny-shell/bead/snow glints. Ambient water and particles'0.3 ambient phase survive at zero strength.
Proxies are already lit on the CPU and bypass another strength factor in the shared particle vertex. Deep
particle phase uses Source at each physical particle. P1 authors strength1 and remains the frozen nonregression
control; P7 is still materially unaccepted. Distance/finite emitter remain a separate required slice:
the shared `scenePointLight` inverse-square-like law describes received
illumination; multiplying it into a finite emitter's shrinking angular radiance would double-count dilution.
Do not claim shared falloff or finite-source compliance from the intensity correction alone.

**Step A — G05: authority map, instrumentation, disagreement A/B.** Trace Settings
→ normalized world coordinates → uniform upload → water background → light core
→ per-bubble glints → shaft field → attenuation → HDR/bloom output. Take fixed
world samples and projected native screen positions. Vary Light Type, Light
Source/End and Ray Source/End individually. Record the current contradictory
results and source ownership before patching. Check Surface directional versus
Deep positional semantics at extreme poses and P1/P7. Verify a source shift
changes all *intended* consumers and none of the unintended ones.

**SCENE physical authority and optical correction.** Align its consumers with the physical light and
world-space field samples, bounded tank support and mode-appropriate attenuation. Preserve BEAM's restored
equations. Keep ray style/softness/reactivity controls working. Compare a fixed
physical source and the *same world-space illuminated region* from under-surface
looking up, looking **down**, side, along source axis, and oblique/rotated
views, same frame/audio/settings. Accept view-dependent scattering intensity
only when the geometry stays anchored. Check blocker and glint continuity.

**Independent coverage validation.** Exercise Surface BEAM / Surface SCENE / Deep BEAM / Deep SCENE
with emission BEAM and emission SCENE independently. SCENE must illuminate a broad authored water volume,
with coherent volumetric response and stable world limits. Reuse existing passes and authoritative settings,
avoid mixed emitters and retain user-authored presets. Do not make coverage validation a reason to replace
the accepted BEAM footprint.

**Step D — G06/G27/G32/G33: native acceptance and cost.** Compare old/new with
fixed camera/light/audio/preset; then view all angles without touching sources.
Capture native GL4.6 full-frame scene, a shafts-only view, glints, light core,
water/haze, pre-/post-bloom and full composite. Record GPU frame p50/p95/p99,
CPU logical tick age, source age, DPR/card sizes, dual-display, first activation,
dormancy and rapid Settings/mode churn. Reject hard slab planes, camera-frozen
shafts, view-dependent emitter positions, disappeared downward shafts,
excessive bloom masking the geometry, stale shader uniforms and regressed P7
art. No blanket visual acceptance from tests or a still. Keep every previous
failure open if not specifically signed off.

## Separate and higher-confidence SCENE-cluster evidence (G07/G08/G09/G32)

**22 October user screenshot, newer than the R45 source candidate:** ([original submitted image](Evidence/2026-10-22_SCENE_operator_rejected_clustering.png), preserved in this godzip). While
emission is reported as SCENE, bright specks remain in concentrated islands
across the lower water volume, with wide gaps and sparse visible larger shells.
This is an **operator-rejected visible result [~]**, not an unperformed visual
check. The screenshot by itself does **not** identify individual particle IDs,
prove the exact deployed binary/revision, or distinguish true world-space
concentration from glow/rejection masks, lifetime/occlusion, or projection.
Preserve source-capture provenance if the operator later supplies it.

**Do not repeat the population-count explanation as a clustering diagnosis.**
Low authored counts can leave the tank sparse; they cannot by themselves
explain narrow concentrations *when source locations are actually distributed*.
Check these independent, falsifiable alternatives:

- **Cold-start SCENE only** vs **BEAM → SCENE at runtime** vs **SCENE → BEAM → SCENE**, same
  authored camera, lighting and counts. `ExtrudedBubbleSimulation` preserves
  `_bubbles` and their world positions across ordinary per-capture control
  changes, and `_spawn` reads the *current* emission geometry for **new** IDs;
  already-live BEAM cohorts are not automatically redistributed. Tag each
  live bubble's birth mode, admission tick, current stable ID, positions and
  age without changing its motion/identity. A former BEAM cloud may remain
  until natural retirement. This is plausible **only** in switch histories,
  **not** a universal explanation for a direct-cold SCENE launch.
- **Physical large/small shells vs procedural specks/free bead chains/marine
  snow/parent fizz.** For each category separately, compare complete world
  inlet X/Z (and other face coordinates) distributions, simulated occupancy,
  rejected spawn attempts, per-seed face and lifetime progression, vertex
  discard/mask probability, shader brightness, HDR and post-bloom pixels.
  Verify that R45's decorrelated face coordinates and SCENE speck eligibility
  change are running in the actual native build, not merely present in the
  godzip source. Do not conflate luminous islands with physical birth density.
- **Transition policy**: identity and camera-independent physical continuity
  take priority. No forced teleport, hidden relocalization, deletion or respawn
  of live BEAM bubbles to make a screenshot uniform. If transitional grouping
  is confirmed, propose a bounded perceptual/occupancy evolution policy that
  naturally allows distributed new SCENE admissions to replace old cohorts;
  quantify time to convergence and obtain operator approval before changing
  behavior. Do not raise global caps or alter authored counts to camouflage it.
- **Early surface disappearance remains a separate G04/G09 failure**: trace
  world Y, true water-plane projection, individual IDs, alpha, camera frustum,
  pop/contact/outside/reach/EOL reason. No collision or population-size
  explanation without evidence. Never mark this resolved with a clump fix.

**Acceptance**: whole-face SCENE distribution and *perceived* coverage with
fixed camera/light, steady music, cold launch, transition history, different
light coverage, P1/P7 and large/small cards. No narrow patch arrays, no camera
following, no unexplained bubble loss, stable per-ID fades and native GPU
p95/p99 within measured budget. A corrected RNG histogram alone is not enough.

**Status:** lighting authority/optics [ ] (partial Surface/Deep analytic-direction and emitter/proxy-radiance candidates only);
BEAM restoration [~] (working-tree shader comparison; historical mapping/full-backdrop and moving parity still open);
SCENE world shaft density [~] (source/radial helper proof; continuous support, fan-only attenuation and moving art/cost still open);
lighting coverage [~] (implemented independent selector/width; moving art and complete optics unaccepted); SCENE clustering [~] (operator visually
rejected); inherited-cohort explanation [ ] (test hypothesis); surface exit [ ]
(open independent regression); all legacy EB visual failures remain unchanged.


## SCENE controller geometry and remaining physical-light work

**SCENE light extent (2026-10-24).** SCENE no longer ignores the Ray path: `scene_light_support`
(`rendering/gl_programs/extruded_bubble_scene.py`) is the one owner of its extent for the shaft shader and both
Settings editors, and the Ray Source → End editor is shown for SCENE as well as BEAM.
- *Sunlit Surface* (directional, open water): sunlight enters only through the water surface along the refracted sun,
  which the path cannot re-aim; Ray End's depth below the surface is how deep it reaches (fade from 0.9x to 1.3x).
  Walls admit nothing in open water, so no wall face is offered. The editors draw the surface as the inlet face.
- *Deep Light* (positional): the emitter stays at Light Source; Light Source → Ray End is its range (fade from 0.5x to
  1.1x) and aim (brightest toward End, 35% behind). It has no entry face; the editors draw its range round the
  emitter instead.
- The tank boundary is soft (last 6%), fixing the binary-coverage defect; where the pattern is momentarily empty the
  shadow centroid falls back to the lit medium (the zero-density centroid defect). A zero range leaves the light
  unshaped, and the uniforms default to that, so BEAM and any program that never sets them are unchanged.
- Measured on presets 1 (Surface) and 5 (Deep) with their default paths against the previous tree: preset 1 matches
  (mean 0.69/765 per pixel, none above 24), preset 5 changes gently (its range now ends near the floor, aimed down).
  Natively verified by `tests/test_extruded_bubble_scene_light_extent_gpu.py`; moving all-angle visual acceptance is
  still open.

`SceneVolumeMapper` owns the common oblique projection, path handles, boundary guides and camera/aim cues.
The Settings builder supplies each editor's own path and coverage: Motion uses Emission Geometry; Light/Rays
use Lighting Coverage. Selector changes and lazy hydration refresh built controls without opening other buckets.
SCENE guides mark the authored Source/End boundary regions; BEAM omits those guides. The same coordinate
editing and save boundary is retained in both Light Types. No new setting, renderer path or preset rewrite.
If Deep's linked Ray Source meets its independent End, the effective empty path has no face direction or
boundary guide. The editor preserves the authored path and does not turn that legal linkage into an exception.

These shared guides establish controller parity, not a new light-volume crop: Surface remains directional and
Deep has a located emitter. Motion's particle birth policy must not become light admission. SCENE light extent,
source-consistent all-angle scattering and actual visual coverage remain physical-light work in the live plan.
Native Qt verification covers reverse lazy construction, Surface/Deep, painted guides, handle drag and save/hydration;
moving rendered coverage and subjective lighting acceptance remain open.
