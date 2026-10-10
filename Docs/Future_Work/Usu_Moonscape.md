# Usu Moonscape — long-horizon Visualizer vertical

**Status:** deferred vertical. Not admitted for runtime implementation; `Future_Work.md` routes it and `Current_Plan.md` owns
any promoted slice. The shared 3D foundations it needs are being **side-built by transitions and Visualizer modes first**
(Current_Plan §4, "S19–S27 character and world foundations"). This document is the single plan for the vertical: the
2026-10-02 snapshot (`Usu_Moonscape_Visualizer_Future_Plan_f104a29eec.md`) is superseded and removed; its still-valid intent
is carried here. The remaining **Blender** work (rig, clips, export preparation, how to preview Usu) is ordered in
[`Usu_Blender_Work.md`](Usu_Blender_Work.md); asset-authoring history lives in the Windows-local `assets/usu/README.md`
(never in Godzips).

Authored 2026-10-10 against HEAD `21880417`+. Re-orient from the then-current `Current_Plan.md`, `Spec.md`,
`Docs/Reference/Visualizer_Reference.md`, `Docs/Guides/Visualizer_Reactivity_Authoring.md`,
`Docs/Guardrails/Visualizer_Presentation.md`, `Docs/Reference/Scene3D_Resources.md` and the 3D foundation lessons in
`Docs/Reference/Transitions.md` before implementing any slice. Goals below may be **simplified** if a part proves infeasible
on the shared renderer; record the simplification here rather than silently dropping it.

---

## 1. Concept

A Visualizer mode in which **Usu**, the plush rabbit from the operator's novel, travels across a small **round moon** under a
**starscape**, driven by live music. The moon rotates beneath him from one logical `travel_distance`, so progression is
continuous without predicting the song. Quiet supported music walks; ordinary music jogs; strong sustained music runs; the
rare peak of a song becomes a full **Naruto run** at absolute top speed — and a sudden stop from that speed is not a cut but a
**skid, fall, and get-up**. In silence he slows, lies down facing the default camera, idly tips his back feet up bit by bit,
then rolls over and pushes himself back up when music returns. Because the moon is a sphere, the camera can **orbit**: behind
(default), to the side, or toward the oncoming direction, with the starscape and horizon making each angle read.

It is deliberately **not** Audiosurf: SRPSS only owns current/live audio; terrain never anticipates the music.

Success: after a minute the viewer reads "Usu is travelling across the moon *with* the music" — authored, charming, honest in
silence, with somewhere to go in loud passages — and the mode sits on the shared 3D/Visualizer substrate with no private engine.

---

## 2. Character and art direction (supersedes the 2026-10-02 "no fur" direction)

**Authority:** `assets/usu/Usu.blend` (approved static model, 2026-10-08) and `00_Original_Usu_Turnaround.png` in
`assets/usu/Usu_Rigging_Reference_Pack_REVISED.zip`. Preserve: oversized smooth head, long floppy ears, very large simple
eyes, compact body, short legs, dark mitten paws, stitched seams, clean far-away silhouette. **No mouth, no nose, no
anatomical eyelids or muzzle, no invented tail.**

**Surface:** stitched **plush felt** — warm ivory, matte, soft sheen, faint fibres, faint dirt patches (reworked 2026-10-10;
the earlier streaky "wood grain" albedo is retired). Running and chain stitches are part of the look and must follow the
skinned surface.

**Fur tips (new, optional):** a short soft fuzz at grazing angles, read as felt fibres catching light, never long fur,
hair cards or a fur simulation. The fuzz tips may **bloom**, tinted by the scene's chosen lighting tint or by the
**rainbow tint progress** (the same rainbow notion the Visualizers use). Bloom follows the shared emitted-light-only rule
(Transitions.md "Post effects work only from emitted light"): the fuzz tips write emitted light; the body never glows
broadly. Off by default and below High tier.

**Eyes:** open-eye components and independent closed strokes (`Usu_Eye_Closed_L/R`) switched per side; brows always
visible; wink possible.

---

## 3. Behaviour

### 3.1 States and clips

| State | Clip(s) | Loop | Notes |
| --- | --- | --- | --- |
| Lying idle | `IdleLie` | yes | prone/side-lying facing the default camera; back feet tip up bit by bit (slow additive), ears settle |
| Idle fidget | `IdleLieFootTap` | additive | occasional slower foot tipping/ear twitch; logical-time seeded, never a timer |
| Roll and rise | `RollOver` → `PushUp` → `Stand` | no | from lying: roll onto the front, plant mittens, push up, regain the rest silhouette and ear drape |
| Standing idle | `Idle` | yes | breathing, mild ear sway (brief, between rise and walk, or quiet but present music) |
| Walk | `Walk` | yes | in place; consistent foot contacts |
| Jog | `Jog` | yes | in place; balanced head |
| Run | `Run` | yes | in place; stronger lean, ears trailing |
| Naruto run | `NarutoRun` | yes | absolute top speed: deep forward lean, arms trailing, ears streaming |
| Jump | `Jump` (markers `takeoff`, `apex`, `land`) | no | a reward on a strong admitted transient while jogging/running (see §3.2); crouch, push-off, tuck, apex, reach, land, squash, recover; the runtime may stretch takeoff..land and scale the arc between them |
| Sudden stop | `Skid` → `Fall` → `GetUp` | no | only from Naruto/high run on an abrupt pressure collapse; contiguous performance |
| Settle down | `SitDown` → `LieDown` | no | from standing/walking into the lying idle when silence persists |
| Blink | `Blink` (L/R/both) | overlay | over every clip; wink possible |
| Accents | `StrideAccent`, `EarRecoil`, `DustStep` | additive | consumed-once transient rewards |

**Ears move together.** Both ears answer the head's vertical motion (one bob per footfall, the jump's rise, fall and
landing) in phase, with a slight lag and one overshoot; they never alternate left/right, which reads busy and is wrong for
floppy felt. The runtime springs (S23) may give each ear a few percent different stiffness so they drift apart a hair
instead of moving as one rigid pair.

Locomotion clips are **in place**; the engine owns travel (moon rotation). Non-loop clips that move the body (skid slide,
fall, roll) declare a **root-motion contract**: either the engine reads the clip's root delta and converts it into travel,
or the clip is authored in place with travel slowed by the engine — one owner, never both.

### 3.2 Music mapping (binding reactivity rules carried from the old snapshot)

Re-read `Docs/Guides/Visualizer_Reactivity_Authoring.md`; it wins if it has evolved. Separate jobs:

1. **acoustic presence** (hysteretic; `playing=True` is not proof of sound);
2. **sustained locomotion pressure** — locally normalized, continuous, with headroom (no early clamp; a hot chorus must
   still vary; Naruto speed is rare, not the default for every loud master);
3. **discrete transient admission** — consume-once at the logical owner, never replayed over an event's max age;
4. **transient reward** — separate from admission;
5. **slow passage weight**;
6. **presentation interpolation** (presentation only; never changes authored timing);
7. **idle behaviour** (honest: no fake energy in silence).

**Jump admission:** only from Jog/Run/NarutoRun, on a consumed strong transient (consume-once at the logical owner,
never replayed), with a logical-time cooldown so jumps stay occasional; jump height and airtime come from the transient
reward (the arc between `takeoff` and `land` scaled and stretched, capped), never from raw loudness; a jump never chains
into another and always lands back into the current gait. Sustained pressure keeps choosing the gait underneath.

State selection is a **hysteretic blend** over pressure: walk ↔ jog ↔ run ↔ Naruto with overlapping enter/exit bands and
cross-fades, never per-frame chatter. **Sudden-stop detection**: entering Skid requires (a) Naruto/high run held for a
minimum logical time and (b) pressure falling below the walk band faster than a release threshold; otherwise the gait just
decelerates. **Silence**: presence lost → decelerate → SitDown/LieDown after a logical settling interval → lying idle; on
return, RollOver/PushUp/Stand then walk. All timing uses the Visualizer **logical time/revision**; re-rendering a revision
moves nothing. Same replay ⇒ same travel, states, clip phases, crater identities, accents and dust identities. Viewport
geometry never changes reaction strength.

### 3.3 Camera

Authored orbit presets around the character on the sphere: **Behind** (default, slightly elevated), **Side**, **Oncoming**
(in front, looking back along travel), plus an operator orbit angle/elevation within safe bounds. Changes interpolate in
logical time. No camera shake as the main musical channel; restrained accent nudges only.

---

## 4. Scene

- **Moon:** a sphere of authored radius (horizon close enough to sell curvature). Deterministic crater field from stable
  seed + spherical cell identity: shallow analytic normal/height perturbation in the shader at low tiers, instanced crater
  meshes or decals at high tiers; no CPU object per crater; nothing re-randomised at render cadence. The character stands
  at a fixed tangent point; the moon rotates by `travel_distance / radius`.
- **Foot contact:** smooth locomotion surface; craters read visually without changing contact height. Foot IK on terrain
  only after the simple scene is accepted.
- **Starscape:** instanced point stars with magnitude/colour classes and slow parallax shells; optional distant planet/sun
  only if composition benefits. Orbiting must show stars wheel correctly.
- **Lighting:** key (sun) + cool rim + faint moon-bounce ambient; one shadow-casting light (real shadow map, S17) so Usu
  shadows the regolith and himself at High/Balanced; contact darkening fallback at Performance; none at KAK.
- **Dust:** lunar dust puffs from consumed footfall/transient events, a `CompactedPopulation` consumer, bounded per tier.

---

## 5. Architecture required — what does not exist yet

Existing and reusable (see Transitions.md/Scene3D_Resources.md): `SceneTarget` (MSAA), bloom/motion-blur post chain,
GGX `SceneMaterial`/`SceneLight`, photo environment, `CompactedPopulation`, stream ring, compute seam, bendable grid,
planar rigid-piece soft shadows, 3D tiers, gradual warm-up, the Visualizer host/lifecycle/logical-snapshot path and the
reactivity lanes. **Missing**, each a shared foundation slice (no Usu-private engine):

| # | Foundation | Purpose | Notes / contract |
| --- | --- | --- | --- |
| S19 | **Asset import + bake pipeline** | load authored meshes, skins, morphs, clips, materials | offline `tools/` exporter from Blender → glTF 2.0 (validated) → a packed SRPSS binary asset; runtime reads only the packed form (no glTF parser at runtime unless measured cheaper); procedural Blender materials baked to texture maps; deterministic, versioned, provenance-stamped; assets stay outside normal Godzips like other private art |
| S20 | **Static mesh renderer** | draw imported static meshes with shared materials | instanced draws, per-object UBO via stream ring, depth, tier-aware LOD; first consumer can be a transition |
| S21 | **GPU skinning** | deform skinned meshes | linear-blend skinning (dual-quaternion only if the ears/arms prove it necessary), joint palette in a streamed block/SSBO, ≤4 influences, skinned stitches bound to their surface owner; dormant when unused |
| S22 | **Animation clips + graph** | play, blend and layer clips on logical time | clip sampling (CPU, cheap, deterministic), state machine with hysteretic cross-fades, additive layers (blink, ears, accents), per-channel masks (body/head/eyes/ears), root-motion contract, morph/visibility tracks for eye states; no wall clock, no worker, no per-frame Settings |
| S23 | **Deterministic secondary motion** | ear follow-through, body jiggle | critically damped springs advanced per logical step from clip motion; no physics engine, no soft-body sim |
| S24 | **Felt/plush material + fuzz shells** | Usu's surface and fur tips | Charlie/sheen lobe added to `SceneMaterial`; few fur shells or fins with noise alpha at grazing angles, emitted-light tips feeding the shared bloom, tint from lighting tint or rainbow progress; tier-gated |
| S25 | **Real shadow maps** (part of S17) | character/terrain shadows | one directional cascade (or a single fitted map), PCF/PCSS soft edges, demand-created depth attachment; replaces nothing that already works |
| S26 | **Sphere world + crater field + starscape** | the moon and sky | analytic sphere with seeded crater perturbation, instanced craters/stars, rotation from logical travel; reusable by transitions/Visualizers |
| S27 | **Perspective orbit camera** | free 3D framing | view/projection matrices independent of the photo-plane camera (`sceneProjectCamera` stays for transitions), authored presets + logical interpolation, overscan rules where a photo is visible |

**Authoring cost is not runtime cost.** Cycles path tracing of the procedural felt takes ~30 s a frame offline; the runtime
never runs those node graphs. S19 bakes them once into ordinary maps (albedo, normal, roughness/sheen), so per frame Usu
costs a few texture samples per pixel on a modest skinned mesh (cages ~13k vertices before any LOD). Authoring materials must therefore stay bakeable:
no Blender hair/particle fur (tried 2026-10-10: ~10 min per frame and nothing to bake); fuzz is authored as sheen and
delivered at runtime as S24 shells/fins.

Each slice obeys the shared rules: lazy, demand-created, released at park/retirement, count-invariant dormancy, one
measured consumer at a time (TIME_ELAPSED + per-frame flush, median/p90), warm-up lists every program/resource a first
frame would create, CPU mirrors for shader maths, quality tiers decide optional cost.

### 5.1 Suggested side-building consumers (proposals; operator chooses)

| Slice | Candidate consumer before Usu |
| --- | --- |
| S26 + S27 + S25 | **Moon Turn** transition: the old photo wraps a small moon that rotates/orbits away against a starscape, revealing the new photo on its far side (sphere, orbit camera, starfield, shadow map) |
| S19 + S20 | **Paper Lantern / Origami** transition using an authored static mesh (proves the bake pipeline, materials, instancing) |
| S21 + S22 | **Usu cameo** transition or a test-only Visualizer harness: Usu walks across pulling the new photo like a curtain (skinning, clip graph, blink overlay, in-place clip + engine travel) |
| S24 | **Felt Press** transition (the photo turns to felt and the fibres catch light) or the Visualizer cameo |
| S23 | ear/ribbon follow-through in the Usu cameo or Membrane Turnover's sheet edge |

---

## 6. Asset pipeline and gates

| Gate | Requirement | Status |
| --- | --- | --- |
| A — static model | silhouette/proportions match the turnaround | approved 2026-10-08 |
| A2 — surface | soft felt, no wood grain, faint dirt; parity with the turnaround | felt v4 2026-10-10: fibre/stain/relief node group on rest-pose coordinates (no swimming under the rig), charcoal felt mittens, darker iris, tan thread, sheen-only fuzz; rebuilt by `assets/usu/source/usu_felt_materials.py`; bake at S19 |
| B — rig | rig copy (`Usu_Rig.blend`) per the reference pack: root, pelvis/spine/chest/neck/head, shoulders/elbows/wrists, hips/knees/ankles + foot pivots, 3–5 bones per ear, Blink_L/Blink_R/Blink controls; stitches bound to their owners | rough rig 2026-10-10 in `assets/usu/Usu_Rig.blend` (procedural weights, blended ear root, ear pivots on the root edge, bone-scale blink); see `Usu_Blender_Work.md` |
| B2 — pose tests | A-pose, extreme head turns, arms forward, stride, Naruto lean, skid, prone, hands planted, push to stand, ear fold; no seam drift, detached ears, clipping, collapse or foot penetration | first pass 2026-10-10 (now in `assets/usu/archive/Usu_history_2026-10.zip`); superseded as the working gate by the per-frame BVH scan of every clip (gate C) |
| C — rough clips | every clip in §3.1 roughly blocked, loops seamless, contacts readable | done for the rough stage 2026-10-10: 23 clips incl. Jump and the accents, grounded, in place, exact hand-offs, no interpenetration in any frame (BVH scan); previews `assets/usu/review/clips_webp/`; hand polish later (`Usu_Blender_Work.md` B4b) |
| C2 — export proof | clips, skins, eye states and materials survive export into the SRPSS path (S19), not just Blender | blocked on S19 |
| D — runtime | S19–S27 accepted through other consumers, then the mode is admitted | deferred |

Blender is the authoring tool (live MCP available); the runtime format is decided at S19, not assumed. The open Blender
items behind gates B–C2 (B1 rig refinement through B6 export proof) are in [`Usu_Blender_Work.md`](Usu_Blender_Work.md).

---

## 7. Settings, quality and resources

- Mode-owned controls stay few: camera preset/orbit, moon/sky palette, lighting tint, rainbow-tint fuzz bloom toggle,
  dust amount, locomotion intensity (artistic, separate from DSP sensitivity). Technical DSP controls appear only for lanes
  actually consumed (descriptor/capability metadata).
- Shared 3D tiers `Auto → High → Balanced → Performance → KAK`; no private quality system. KAK = Usu, basic moon, basic
  stars, the locomotion effect; everything optional off.
- Inactive mode owns no GPU buffers, targets, pools, joint palettes or clips; no worker, timer, poller or forced frame.
  Joint palette and clip sampling run only while the mode presents. No Python object per crater/star/particle.

---

## 8. Tests before acceptance

Pure/logical: presence hysteresis; gait bands do not chatter; headroom in hot passages; Naruto occupancy is rare on real
music; sudden-stop detection fires only from sustained high speed; consume-once accents; admission ≠ reward; travel advances
exactly once per revision; deterministic craters/stars/dust; idle/lie-down/roll/rise use logical time; replay determinism.
Runtime: no allocation while disabled; retirement releases skinning/clip/terrain resources; repeated activate/retire does
not accumulate; no render-cadence advance. Presentation: viewport geometry invariance, framing per camera preset, tiers keep
the core scene, KAK truly minimal. Asset: exported clips match Blender sample poses within tolerance (offscreen render
compare), eye states and stitches survive export. Physical acceptance is a bounded operator step after these.

---

## 9. Traps (carried forward)

Isolated experimental renderer; private scheduler or render-time simulation; wall-clock animation; per-frame Settings reads;
CPU loops per crater/star/particle; allocation churn while running; resources kept while dormant; one scalar driving speed,
gait, ears, dust, camera and light; early clamp pinning max speed; stale event replay; transients flipping gait directly;
fake idle energy; smoothing hiding cadence bugs; viewport scaling reaction strength; full physics/IK before baked locomotion
proves the scene; star/particle spectacle demoting Usu; long fur or hair simulation.
