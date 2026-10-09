# USU MOONSCAPE VISUALIZER — DISTANT FUTURE IMPLEMENTATION PLAN

> **ARCHIVED CONCEPT/ART REFERENCE ONLY — NOT A LIVE IMPLEMENTATION PLAN**
>
> The staged implementation, test suggestions, language/tooling and architecture here are a snapshot from an older tree. Do not execute them as a roadmap, resurrect older mode-specific infrastructure, or treat older Blender/Maya commentary as a software choice. `Future_Work.md` is the only admission router; current shared Scene3D/Visualizer contracts are authoritative. Preserve the useful character look, moonscape and live-music intent.
> **Project HEAD when authored:** `f104a29eec`
> **Authored:** 2026-10-02
> **Status:** distant future concept / implementation handoff, **not current roadmap authority**
>
> Any agent reading this after `f104a29eec` must assume the renderer, Scene3D substrate, Visualizer registry, quality system, settings surface, asset pipeline, tests and roadmap may have changed substantially. **Re-orient from the then-current `Current_Plan.md`, `Future_Work.md`, GODZIP handoff and canonical Visualizer docs before implementing anything here.** Preserve the intent of this document, not stale file-level assumptions.

---

## 1. CONCEPT IN ONE PARAGRAPH

Create a future SRPSS Visualizer mode built around **Usu**, the user's simple smooth rabbit character from their novel. The camera follows from behind / slightly above while Usu appears to walk or run continuously across a rounded moonscape beneath a starfield. The curved moon surface supplies a strong feeling of forward progression without requiring future knowledge of the music. Live audio controls locomotion energy and secondary accents: quiet supported passages should read as walking, stronger sustained passages as running, and meaningful transients should add punch without repeatedly toggling the entire state. True idle/silence has its own authored state, with Usu able to slow, stop and end up collapsed/resting rather than being kept artificially active with fake music energy.

This mode is deliberately **not** Audiosurf. SRPSS only owns current/live audio. Terrain does not anticipate future music and must not pretend it can.

---

## 2. MODEL REFERENCE / ART DIRECTION

### Approved modelling guide

The generated turnaround approved by the user is located at:

`F:\Programming\Apps\ShittyRandomPhotoScreenSaver\tmp\UsuForModelling.png`

It contains front, side, back and 3/4 views at a consistent scale and is intended as the practical modelling guide.

The original drawings remain the identity/charm references where available. If the turnaround and original drawings disagree in a way that materially changes Usu's character, **ask for visual acceptance before continuing** rather than silently polishing the character into something generic.

### Usu's important design language

Usu succeeds through **simplicity and charm**, not detail density.

Preserve:

- oversized smooth rounded head;
- long floppy ears;
- very large simple eyes;
- compact rounded body;
- tiny/simple rounded limbs;
- dark tip accents where established by the references;
- slightly awkward/endearing proportions;
- clean silhouette readable from far away;
- minimal surface detail.

### Explicitly NOT required

Usu does **not** need a plush/furry material treatment.

Do not add:

- fur simulation;
- fuzzy shell geometry;
- hair cards;
- fabric weave merely because Usu is a stuffed-rabbit-like design;
- realistic animal anatomy;
- detailed paw/finger/toe geometry;
- unnecessary facial musculature.

The desired material direction is **smooth**. A clean stylized surface with good shading is preferable to expensive realism.

Do not invent a tail or other major silhouette feature simply because a generic rabbit would have one. The modelling guide/original art is the authority unless the user explicitly changes it.

---

## 3. ASSET CREATION WORKFLOW — DO NOT DISCOVER FAILURE AT HOUR NINETEEN

This character is simple enough that agent-assisted modelling is plausible, but the workflow must contain hard approval gates.

### Gate A — static model before rigging

1. Give the modelling agent the approved turnaround **and** original Usu drawings.
2. Create the unrigged model first.
3. Produce a neutral turntable or front/side/back/3/4 renders.
4. Verify silhouette, head/body ratio, ear proportions and limb placement.
5. **Do not proceed to rigging until the static model is visually accepted.**

A technically impressive wrong Usu is still wrong.

### Gate B — minimal rig before animation polish

The initial rig should be intentionally modest. Candidate hierarchy:

- root / world;
- pelvis or body root;
- torso/head;
- left/right legs;
- left/right arms;
- simple ear chains, probably a few bones per ear if needed for floppy motion;
- eyes as simple objects/materials unless later evidence justifies more.

Do not start with:

- production-game facial rigs;
- elaborate IK networks;
- ragdoll systems;
- cloth/fur solvers;
- dozens of corrective bones.

### Gate C — prove the three essential locomotion states

Before SRPSS integration, prove at least:

- **rest/collapsed idle**;
- **walk**;
- **run**.

Useful extras only after the essentials look good:

- stand/rise transition;
- run-to-walk transition;
- small transient accent pose;
- ear recoil/bounce;
- dust-step marker timing.

The locomotion clips must look good **at normal playback before audio is connected**. Audio cannot rescue a weak animation.

### Blender vs Maya

Maya may be excellent for a human artist, but this project must not assume an agent can reliably automate Maya merely because Maya is a stronger traditional DCC in some pipelines.

For agent-assisted creation:

- **prefer Blender unless the actual agent/tooling available at implementation time demonstrably supports Maya well**;
- do not choose Maya on reputation alone;
- do not choose Blender as a permanent artistic requirement either;
- export through whatever stable asset format the then-current SRPSS Scene3D pipeline actually owns.

At `f104a29eec`, this document intentionally does **not** freeze an asset format. Re-check the future Scene3D asset path first.

---

## 4. SCENE COMPOSITION

### Camera

Primary composition:

- camera behind Usu;
- slightly elevated so the ears/body silhouette and moon horizon remain readable;
- Usu roughly central or slightly below center;
- enough forward view to sell travel;
- stable camera by default.

Do not turn camera shake into the main reactivity channel. Excessive camera response will make the scene annoying rather than musical.

### Moon surface

The core trick is **continuous implied travel without prediction**.

Preferred architectural direction:

- keep Usu close to a stable local tangent point;
- move/rotate a curved moon shell or curved terrain strip underneath;
- derive world travel from one logical `travel_distance` accumulated from authored locomotion speed;
- generate/recycle crater detail deterministically from stable distance/seed coordinates;
- let the curved horizon create the impression of traversal.

A large rolling moon/spherical segment is particularly attractive because it gives progression almost for free: the character can remain near the same world position while the moon rotates beneath them.

### Craters / terrain

The moonscape should be inexpensive and readable:

- bounded crater population;
- deterministic placement from stable seed + terrain cell/arc identity;
- shallow geometry, decals, normal/material variation or instanced crater assets as appropriate to the then-current shared renderer;
- no CPU object per crater;
- no rerandomisation at render cadence.

Do not require full character IK just because craters exist. The safest visual cheat is a primarily smooth locomotion surface with crater detail that reads visually without constantly changing foot-contact height. If later terrain displacement genuinely improves the result, add it only after the simple locomotion scene is accepted.

### Sky

Start simple:

- starfield;
- restrained parallax or depth if cheap;
- optional distant celestial object only if composition benefits;
- no giant secondary system competing with Usu.

The character and forward movement are the scene.

---

## 5. REACTIVITY CONTRACT — BINDING DESIGN GUIDANCE

Before implementation, re-read the then-current:

- `Docs/Guides/Visualizer_Reactivity_Authoring.md`
- `Docs/Reference/Visualizer_Reference.md`
- `Docs/Guardrails/Visualizer_Presentation.md`

The guidance below captures the important intent as it existed at HEAD `f104a29eec`, but those canonical documents win if they have evolved.

### 5.1 Do not make one scalar control the entire mode

Separate these jobs:

1. **acoustic presence** — is real current sound present enough to author music-driven locomotion?
2. **sustained locomotion pressure** — how fast should Usu generally move through the current passage?
3. **discrete transient admission** — did a meaningful kick/onset/etc. happen?
4. **transient reward** — how much accent should that admitted event receive?
5. **slow passage weight** — should the scene feel calmly active or intensely driven across a phrase?
6. **presentation interpolation** — how do animation/camera/material changes reach the screen smoothly?
7. **idle behavior** — what does Usu do when music is not currently supporting live motion?

A source useful for one job must not silently become authority for all the others.

### 5.2 Presence is not playback state

`playing=True` is not proof of current sound.

Use current acoustic presence with hysteresis so:

- a silent gap does not keep authoring new musical accents;
- tiny threshold noise does not chatter between walk/rest;
- existing locomotion can settle naturally;
- true idle is authored honestly rather than by injecting fake music energy.

### 5.3 Proposed locomotion mapping

The exact thresholds must be tuned from real evidence, not copied blindly from another mode, but the intended semantics are:

- **true idle / sustained silence:** Usu slows to rest and may end in the collapsed/resting animation;
- **quiet supported passage:** walk;
- **ordinary passage:** faster walk / blend toward run as appropriate;
- **strong sustained passage:** run;
- **exceptional transients:** brief stride/body/ear/dust accents, **not** a complete locomotion-state rewrite every time.

Walk/run should be a continuous or hysteretic blend, not a binary switch that chatters on every frame.

The locomotion speed should generally use a bounded, locally normalized continuous lane with useful headroom. Do not hard-clamp ordinary loud music to maximum run speed.

### 5.4 Preserve loud-passage contrast

A hot chorus must still contain visible variation.

Do not do:

```text
raw energy -> early clamp to 1.0 -> locomotion speed
```

That produces a permanently pinned rabbit once the song gets loud.

Prefer:

```text
current useful signal
+ slower observed floor/peak or local baseline
-> normalized continuous pressure with headroom
-> response shaping
-> final bounded locomotion target
```

Inspect occupancy in real songs. Maximum run/sprint behavior should be relatively rare, not the normal state of every loud master.

### 5.5 Discrete events are consumed once

Typed/onset events are excellent for accents such as:

- stronger footfall;
- short forward lean;
- ear recoil/bounce;
- small lunar dust puff;
- a brief stride emphasis.

But consume one-shot events once at the logical owner. Never poll/replay one recent event for its entire max-age window.

Admission and reward are separate:

```text
qualifying transient -> admit one accent
admitted accent + continuous/local evidence -> accent strength
```

Do not let “event happened” automatically mean “maximum visual explosion.”

### 5.6 Different timescales use different math

- **transient accents:** fast, consume-once;
- **locomotion speed:** short asymmetric attack/release, typically faster rise and slower relaxation;
- **walk/run state blending:** hysteretic and smooth enough not to chatter;
- **slow scene intensity:** slower envelope if used at all;
- **render interpolation:** presentation-only and must not change authored event timing.

Do not add audio smoothing to hide delivery/cadence defects.

### 5.7 Travel distance is logical state

`travel_distance` must advance from authored Visualizer logical time/revision, not render cadence and not wall-clock rendering.

Re-rendering the same logical revision must **not** move the moon again.

The same input snapshot/replay must produce the same:

- travel distance;
- locomotion state;
- animation phase/state;
- deterministic terrain/crater identities;
- admitted transient accents;
- dust-event identities.

### 5.8 Geometry must not become hidden gain

Custom viewport width/height/aspect must not silently weaken or amplify reactivity.

The character may be reframed/rescaled spatially, but the same authored musical event should remain the same authored event. Do not “fix” an extreme viewport by damping locomotion/audio response.

---

## 6. IDLE / REST STATE

The user's concept specifically allows Usu to be **collapsed on the floor in idle**. Treat that as an authored scene state, not an accident.

Recommended behavior:

- playback absent or sustained real acoustic silence -> locomotion pressure releases;
- Usu decelerates rather than teleporting from run to corpse;
- after the authored logical settling transition, enter rest/collapsed pose;
- if audio meaningfully returns, rise/transition back into locomotion cleanly.

Do not require a new timer. Use the Visualizer logical owner/time already available to the mode.

The collapsed state should remain charming and readable, not look like a rendering failure.

---

## 7. SECONDARY MOTION / POLISH

Useful secondary motion, in priority order:

1. **ear motion tied to gait**;
2. small body bob/lean tied to locomotion clip;
3. bounded transient ear/stride accents;
4. lunar dust puffs from meaningful steps/transients;
5. restrained material/light response if it improves readability.

Ear motion is a particularly valuable charm multiplier because Usu's ears occupy a large portion of the silhouette.

Prefer baked animation plus small deterministic logical secondary motion over a complex real-time soft-body simulation.

Do not make every element react to the same beat. The rabbit should look like it is moving *through music*, not being electrocuted by it.

---

## 8. SHARED ARCHITECTURE — EXPERIMENTAL IS A STATUS, NOT A SECOND ENGINE

At HEAD `f104a29eec`, the project direction was explicit: **Sphere is the legacy exception. New experimental modes must join shared architecture from day one.**

Usu must therefore use the then-current canonical equivalents of:

- Visualizer mode registry / descriptor;
- enabled-mode admission;
- logical snapshot/cadence owner;
- shared Scene3D resources;
- shared compute/material/light facilities where useful;
- shared quality resolver;
- shared lifecycle, retirement and dormancy;
- canonical presets/settings ownership.

It may remain default-off and labelled Experimental until accepted.

It must **not** gain:

- a private presentation window;
- its own scheduler;
- a second simulation clock;
- a render-rate simulation loop;
- a permanent worker simply because it is 3D;
- a separate low-level GPU engine intended to be “promoted later.”

Promotion should eventually be an acceptance/status decision, not a renderer rewrite.

---

## 9. TECHNICAL CONTROLS / SETTINGS

Do not blindly expose every technical Visualizer control.

At implementation time, inventory the actual analysis seams the mode consumes and use descriptor/capability metadata so only meaningful controls appear.

Candidate useful controls may include shared source/capture controls such as input gain, sensitivity/noise-floor handling, or other lanes actually feeding the locomotion/event model.

Do **not** manufacture dead sliders for bar count, AGC, dynamic range or transient controls that the mode does not consume.

### Mode-owned artistic controls should remain small

Likely candidates, only if genuinely useful:

- moon/sky palette or preset identity;
- camera distance/height within safe authored bounds;
- crater/detail density if not fully delegated to quality tier;
- perhaps dust amount;
- perhaps locomotion intensity/sensitivity as an authored artistic control separate from technical DSP sensitivity.

Avoid turning this simple mode into a Settings spreadsheet.

---

## 10. SHARED 3D QUALITY SETTINGS

This mode must consume the project's existing shared 3D quality vocabulary:

`AUTO -> HIGH -> BALANCED -> PERFORMANCE -> KAK`

Do not create a private Usu quality system.

Possible tier-controlled facilities:

- shadow quality / shadow disable;
- crater geometric density;
- starfield density;
- dust particle count;
- AO/contact treatment;
- material/light complexity;
- optional post effects;
- antialiasing strategy where the shared renderer exposes one.

`KAK` must remain a true minimum viable scene: Usu, basic moon, basic stars/background and the essential locomotion effect, with expensive optional decoration effectively off.

Manual user-authored feature overrides must survive profile switching according to the shared 3D Settings contract.

---

## 11. PERFORMANCE / RESOURCE CONTRACT

The mode must scale visual capability without becoming permanent tax.

Binding expectations:

- inactive/disabled mode owns no meaningful GPU buffers, targets, particle pools, animation worker or forced frames;
- no Python object per crater/particle;
- bounded instance/particle populations;
- stable seeded identities;
- no new poller/timer for visuals or diagnostics;
- use shared persistent-stream/SSBO/compute/indirect infrastructure when it exists and materially helps;
- release renderer resources deterministically on retirement;
- re-rendering the same logical revision does not advance animation/simulation;
- count CPU submit work/GL calls when introducing new passes;
- do not regress existing modes merely because Usu capability exists.

A simple smooth rabbit should not require an absurd renderer budget.

---

## 12. WHAT TO AVOID

### Architectural traps

- isolated experimental renderer that must later be migrated;
- private scheduler or render-time simulation;
- wall-clock animation ownership independent of Visualizer logical time;
- per-frame Settings reads;
- CPU loops submitting individual craters/dust particles;
- allocation churn during ordinary locomotion;
- keeping 3D resources alive while the mode is dormant.

### Reactivity traps

- one scalar controlling speed, gait, ears, dust, camera and lighting;
- `playing=True` treated as proof of current sound;
- early clamp causing every chorus to become maximum run;
- absolute loudness used as transient strength;
- stale event replay across many frames;
- transient events switching walk/run directly on every kick;
- fake audio energy to keep idle visually alive;
- extra smoothing used to hide cadence/presentation bugs;
- viewport/aspect scaling changing musical strength.

### Visual/asset traps

- fur/plush obsession;
- over-detailed anatomy;
- complex terrain physics before the basic scene works;
- full game-style locomotion AI;
- predictive terrain based on unavailable future audio;
- camera shake as primary musical response;
- dynamic IK/physics complexity before baked locomotion proves the concept;
- star/particle spectacle that visually demotes Usu.

### Scope traps

Do not begin this mode merely because the modelling image exists. At `f104a29eec` it is a **distant post-foundation idea**. The shared 3D roadmap and more important consumers come first.

---

## 13. IMPLEMENTATION STAGES / ACCEPTANCE GATES

### Stage 0 — reorientation

Before touching code:

- inspect current HEAD/GODZIP;
- read current plan/future work;
- read current Visualizer reactivity/presentation docs;
- identify the current shared 3D quality/resource APIs;
- determine the current asset/animation format;
- check whether another mode has already established a canonical animated-character path.

### Stage 1 — asset proof

Acceptance:

- static model looks like Usu;
- smooth material, no unwanted fur treatment;
- user approves silhouette/turntable;
- walk/run/rest clips are visually convincing before audio integration.

### Stage 2 — static SRPSS scene

Acceptance:

- Usu renders in canonical Visualizer lifecycle;
- moon curvature sells progression;
- starfield/background works;
- no audio yet;
- resize/custom geometry remains sane;
- disabled mode owns no meaningful runtime resources.

### Stage 3 — deterministic locomotion

Acceptance:

- logical travel distance drives moon movement;
- walk/run/rest blending works from synthetic control values;
- same logical replay produces identical state;
- rerendering one revision does not advance travel.

### Stage 4 — real audio reactivity

Use the canonical minimum evidence set:

- true silence;
- quiet song;
- ordinary material;
- hot/dense chorus;
- isolated strong kick/onset over a loud bed;
- release back toward calm.

Acceptance:

- quiet supported music reads as walking rather than dead;
- loud music increases drive without pinning permanently;
- transients create accents without event replay;
- silence produces authored rest, not fake movement;
- viewport changes do not alter reaction strength;
- no evidence of source/cadence delivery being “fixed” by arbitrary gain.

### Stage 5 — polish

Only after the reaction model is accepted:

- ear secondary motion;
- dust;
- improved materials/lighting;
- quality-tier tuning;
- presets;
- optional extra environmental accents.

### Stage 6 — promotion

Promotion from Experimental should require:

- accepted physical reactivity;
- deterministic replay tests;
- dormancy/resource tests;
- no independent architecture;
- no meaningful idle tax when disabled;
- quality-tier acceptance;
- visual quality judged against the character reference and intended charm.

Promotion must **not** require rewriting the renderer if this document's shared-architecture rule was followed.

---

## 14. TESTS THAT SHOULD EXIST BEFORE CALLING IT DONE

Names will depend on the future tree, but coverage should include:

### Pure/logical tests

- silence presence gate and hysteresis;
- walk/run blend thresholds do not chatter;
- sustained pressure preserves headroom in hot passages;
- transient consume-once semantics;
- transient admission separate from reward magnitude;
- travel distance advances exactly once per logical revision;
- deterministic crater/world identity from stable travel/seed;
- idle/rest transition uses logical time, not a new timer;
- same replay -> same locomotion/terrain/accents.

### Runtime/lifecycle tests

- mode disabled -> no renderer/resource allocation;
- mode retirement releases its Scene3D resources;
- repeated activate/retire does not accumulate handles/resources;
- quality switching does not create parallel ownership;
- no scheduler/render-clock duplication;
- no render-frame simulation advance when logical revision is unchanged.

### Presentation tests

- extreme viewport/aspect does not stretch final rendered pixels incorrectly;
- character remains readable and framed;
- reaction magnitude is invariant to viewport geometry;
- quality tiers preserve the core scene;
- `KAK` genuinely disables expensive optional facilities rather than merely lowering them slightly.

### Physical acceptance

Physical acceptance is required for charm/animation/reactivity, but it must be a **bounded acceptance step**, not a substitute for automated tests or a request for long soaks.

---

## 15. WHY THIS MODE FITS LIVE AUDIO BETTER THAN A PREDICTIVE TUNNEL

A Tunnel/terrain visualizer can look spectacular when a system knows the song ahead of time and can construct enormous future dips/elevations from upcoming audio. SRPSS's Visualizer contract is based on current/live audio and should not fake prediction.

Usu Moonscape avoids that weakness:

- terrain can remain deterministic and musically neutral;
- forward progress comes from locomotion speed + curved-world travel;
- the listener perceives continuous journey even though the mode knows nothing about the next ten seconds of music;
- musical reactivity remains local and honest: speed, gait, accents, ears, dust and scene intensity respond to what is happening now.

That is the conceptual advantage of the mode.

---

## 16. SUCCESS CRITERIA

The mode succeeds if, after a minute of watching it, the user reads:

> “Usu is travelling across the moon *with* the music.”

not:

> “A rabbit model is playing one of three animations while random audio numbers shake the scene.”

The character should remain simple, smooth and charming. The reactivity should feel authored rather than frantic. Loud passages should have somewhere to go. Silence should be honest. The moon should sell progression without pretending SRPSS can predict future audio. And the entire mode should sit naturally on the shared 3D/Visualizer substrate rather than becoming another architecture that has to be migrated later.

---

## 17. DOCUMENT AGE / FUTURE-AGENT WARNING

This document was written against **HEAD `f104a29eec`**.

At that point in the project:

- the next shared-GPU work was the persistent-mapped-stream / SSBO foundation and subsequent compute/indirect/material/particle programme;
- Sphere was the legacy experimental migration case;
- the project had explicitly adopted the rule that future experimental modes join shared architecture from day one;
- shared future 3D quality vocabulary was planned as `Auto / High / Balanced / Performance / KAK`;
- `Docs/Guides/Visualizer_Reactivity_Authoring.md` captures the hard-won separation between presence, event admission, event reward, sustained response, presentation smoothing and idle motion.

**Do not assume any of those implementation details are still current when this mode is finally built.** Reconcile this concept with the current tree first. The durable intent is Usu, the rounded moonscape, honest live-audio locomotion, strong reactivity discipline, shared architecture, smooth/simple art direction and staged approval that prevents late-project disappointment.
