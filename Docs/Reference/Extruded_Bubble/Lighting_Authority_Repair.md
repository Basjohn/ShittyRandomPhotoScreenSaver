# Extruded Bubble | Physical lighting authority and BEAM/SCENE coverage repair

**22 October 2026 | SOURCE-AUDITED DESIGN / PARTIAL CANDIDATES, ALL UNACCEPTED.** This is the detailed
architecture/evidence companion for the **single live** `Current_Plan.md` §4B
G05/G06/G27/G30/G32/G33 sequence, not a second checklist. Surface analytic
direction now shares refracted sunlight; the larger physical-field repair remains open. Preserve the full
pre-existing EB-L/F/S/B/C/D/A/P failure inventories and the earlier R-series
investigation. An implementation, compilation, plausible still, or GPU benchmark
cannot become `[x]` without operator or capable local visual-agent acceptance.

## Why this precedes another lighting setting

Do **physical-light authority → world-space shaft/optics correction → lighting
BEAM/SCENE coverage → native all-angle and GPU acceptance**. Do not add coverage
choices to a scene whose light, visible glow, reflections and scattering volume
currently disagree. Keep the existing artistic range controls; repair their
physical consumers rather than suppressing the effects that make the art valuable.
This is an **EB prerequisite**, not deferred generic ray tracing or G2 shadow work.

## Source audit, exact current contradictions

| Existing behavior | Code evidence / underlying limitation | Explicit acceptance question |
| --- | --- | --- |
| **Sunlit Surface** uses a directional distant sunlight | `rendering/gl_programs/extruded_bubble_scene.py:scene_knobs` sets `sun`/`sun_below` from `light_direction`, `light_power=0`; analytic `spec_dir` now shares refracted `sun_below`, replacing the contradictory world-up lobe. `Light Source` coordinates are still authored | Does moving position falsely imply moving a positional sun? Provide honest control semantics; actual sun direction consistently illuminates surface, water, glints and shafts. Native directional diagnostics establish the narrow glass repair, not complete lighting acceptance. |
| **Deep Light** carries world-space Light Source, but its visible glow is primarily angular | In `extruded_bubble_scene.py:scene_knobs`, `light_source` is physical and Deep overrides `ray_source=light_source`; `rendering/gl_programs/extruded_bubble_program.py` evaluates visible glow from `dot(viewRay,normalize(uLightSource-uEye))` and high-power lobes, without true spatial falloff of an illuminated water field | Move emitter or a fixed camera: does brightness at known world samples decay with physical distance while visible light core and real glints agree? |
| Rays have distinct Ray Source → Ray End authoring | `SHAFT_FRAGMENT` has `uRaySource`, `uRayEnd`; Surface allows a separate authored segment; Deep currently forcibly aligns the ray *start* with the Light Source while the ray end remains its authored destination | Ray controls may shape light/scattering extent, but cannot silently become a second emitter. Preserve existing authored choices and explicitly distinguish Surface/Deep semantics. |
| Surface shafts are view-fan dominated | `MODES["surface"]["shaft_fan"]=1.0`; `SHAFT_FRAGMENT:main` mixes marched volume with `labShaftFan(viewRay,...)`, with a fixed pair of points along each camera ray for extent | Holding the light/volume fixed while orbiting and looking downward must **not** move or reverse the beam volume; anisotropic scattering may vary brightness by view angle, but not physical placement. |
| A finite length is mistaken for a finite 3D beam | `SHAFT_FRAGMENT:beamExtent(p)` projects onto Source→End and gates only longitudinal `along` distance; it never calculates perpendicular separation from the line | Use a bounded radial (or directionally widening conical) cross-section with soft edges, not the infinite slab between two planes. |
| Attenuation is an approximation of four physical bubbles | `uBlock0..uBlock3` and `sceneTransmittance()` use at most four proxy blockers plus aggregate particles, currently sampling one representative point for the fan output | Verify coherent attenuation along **the actual field**. Bounded selective occlusion can remain; no demand for expensive shadow maps or full multiple scattering, but no false claim of complete volumetric shadowing. |

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
3. **World-space illumination remains fixed as the observer moves.** Evaluate
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
   A separate, **proposed and not implemented** `Lighting Coverage` setting
   introduces **BEAM** (physically localized shafts / underwater spotlight)
   versus **SCENE** (broad environmental illumination with coherent scattering)
   *under each existing Light Type*. It is independent of **Motion → Emission
   Geometry: BEAM/SCENE**: one governs light coverage, the other governs where
   physical bubble/particle cohorts are admitted. Do not couple or auto-switch.
   Reuse one emitter/shader authority. Preserve existing effective behavior,
   mutable preset values, current Custom, defaults and reset semantics; no
   automated preset rewrite or protected/frozen artistic golden. Decide/verify
   any new persisted default explicitly before implementation, rather than
   silently assuming the emission default dictates light coverage.

## Delivery sequence and gates (not another task queue)

**Step A — G05: authority map, instrumentation, disagreement A/B.** Trace Settings
→ normalized world coordinates → uniform upload → water background → light core
→ per-bubble glints → shaft field → attenuation → HDR/bloom output. Take fixed
world samples and projected native screen positions. Vary Light Type, Light
Source/End and Ray Source/End individually. Record the current contradictory
results and source ownership before patching. Check Surface directional versus
Deep positional semantics at extreme poses and P1/P7. Verify a source shift
changes all *intended* consumers and none of the unintended ones.

**Step B — G05/G06/G27: physical authority and optical correction.** Move the
consumers to the shared physical light; replace view-anchored placement with
world-space field samples; implement lateral beam envelope and mode-appropriate
attenuation. Keep ray style/softness/reactivity controls working. Compare a fixed
physical source and the *same world-space illuminated region* from under-surface
looking up, looking **down**, side, along source axis, and oblique/rotated
views, same frame/audio/settings. Accept view-dependent scattering intensity
only when the geometry stays anchored. Check blocker and glint continuity.

**Step C — G05/G27/G30: lighting coverage after repair.** Introduce Light Type
× Lighting Coverage (Surface BEAM / Surface SCENE / Deep BEAM / Deep SCENE)
only when Steps A and B demonstrate coherence. BEAM must be spatially bounded;
SCENE must illuminate a broad authored water volume, with coherent volumetric
response and stable world limits. Reuse existing passes and authoritative
settings, avoid mixed emitters and retain user-authored presets. Test every
combination with emission BEAM and emission SCENE independently.

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

**Status:** lighting authority/optics [ ] (partial Surface analytic-direction/radiance candidates only);
lighting coverage [ ] (proposed only); SCENE clustering [~] (operator visually
rejected); inherited-cohort explanation [ ] (test hypothesis); surface exit [ ]
(open independent regression); all legacy EB visual failures remain unchanged.
