# Extruded Bubble | Physical Reactivity, Bead/Wake and Optics Failure Ledger

**STRONG RETENTION VALUE DOCUMENT**  
**Live, source-backed historical bug record.** All statuses below remain `[~]` until the operator expressly accepts a visual result.  
**Owner of requirements/physical acceptance:** [`../Reference/Extruded_Bubble_Target.md`](../Reference/Extruded_Bubble_Target.md) §§7–11A; sequencing: [`../../Current_Plan.md`](../../Current_Plan.md) §4B. This file holds attempted mechanisms, rejected outcomes, and still-unverified repairs. It does **not** replace the target checklist, weaken `Spec.md`, or become a chronological changelog.

**Classification key:** `COMPLETELY FUCKED` = operator-confirmed physical failure; `PARTIAL (BARELY)` = code path exists or a narrow defect changed, but the actual intended visual outcome has not passed. Both deliberately use `[~]`, not `[x]`; neither is clearance. A passing synthetic test is never evidence of displayed reactivity. Every preset is operator-authored and mutable; no retuning a preset simply to mask an implementation failure.

## 1. Live failure checklist: audio and motion

- [~] **COMPLETELY FUCKED | All observable reactivity, across all attempted slices, INCLUDING THE FULL-DYNAMIC 2D-BAND REWORK (operator retest 2026-10-19; `logs3a0d4fa1176.zip`).** Music is not creating convincing visible changes. No response component is accepted: large-bubble breathing, acceleration, drift/sway, idle-to-playback contrast, bead motion, ambient/surface animation, emission or musical light-ray energy. The source's connected followers, passing unit tests, deterministic phase-rate improvements **and latest shared-2D-band source changes did not fix the operator's display**. **Big and small bubbles remain visually unchanged at normal controls.** With maximum Sensitivity or Dynamic Floor, a **small, rapid, regular pulse** sometimes appears, but it **does not follow musical changes**. Treat this as a *failed* breathing response, never partially accepted or a reason to require a floor. All reactivity, not just breathing, is operator-confirmed failed in this run. Preserve target §10 D→B→C→A, §11 complaints and real recordings `F:\Programming\Apps\ShittyRandomPhotoScreenSaver\logs\visualizer_recordings` as the acceptance oracle.
- [~] **COMPLETELY FUCKED | Breathing: D.** Original measurements in target §10 D: large bubbles ~0.2–0.4 px/s, about 3–4% swell, sustained passages nearly flat, kick impact missing. The attempted integrated musical breathing cycle, sustain weighting, added visible kick swell and deterministic >4-px projected amplitude tests all **FAILED in actual rendering**. Source-level radius motion is not reliable evidence of what the card presents: projection, alpha, material, perceptual scale and music-input mapping must be traced together. Do not declare breathing partially corrected merely because the code has a nonconstant sine phase; do not blindly raise another multiplier or create a second clock.
- [~] **COMPLETELY FUCKED | Idle and live contrast.** Initial idle surface/bead speeds >2× desired, music often indistinguishable; the first `12*travel` / `8*travel` retime *failed* and was reported to make idle look **faster** than playback. Second attempt integrated `motion_phase` for water/sky/veils/shafts and reduced bead travel to `5*travel`. Measured *logical phase* quiet ~0.24 vs music ~1.72 units/s; bead ~0.25 vs ~0.86 units/s. Despite these code-side numbers the operator confirmed **the entire reactive rework failed**. Do not call this an improvement. Diagnose actual on-screen optical flow and source-through-snapshot-through-shader, not clocks alone; keep the intended gentle quiet motion, continuous loud acceleration and attack/release behavior.
- [~] **COMPLETELY FUCKED | Large/mid bubble stream, drift, sustained passages and transient response: C.** Speed envelope changed little within a track (target §10 C reports approximately ±10%); the prior motion-phase changes did not fix the visible problem. The simulation's own bubble movement still depends on raw elapsed logical `self._time` for sway/wander, unlike background phase; this is a concrete split in movement ownership. The inputs need a proven, inspectable mapping to rendered position, not another abstract follower-only test.
- [~] **COMPLETELY FUCKED | Rays, emission, population response.** Light-ray intensity, fan, shimmer and transient response are visually absent despite `state.rays`, `state.shimmer`, `ray_strength` and `ray_motion` wiring. Particles are *technically* wired: `ExtrudedBubbleControls.emission` reads the **Particles Range** (`extruded_bubble_particles`); the follower yields `state.emission`. `speck_amount(parameters, state.emission)` reads the **same Particles Range again** and uses the follower as interpolation position, squares speck density and also changes brightness; bead population separately reads the Bead Chains Range at `state.emission`; fizz is governed by live emitter count and detail tier, **not an independently music-driven emission rate**. This is a double application of one range on specks, with no validation of actual quiet/loud brightness/particle counts. **Source connected ≠ reactive success.** Do not silently repurpose existing handles or add a parallel DSP source; audit single authority and each consumer's range semantics with the operator.

## 2. Live failure checklist: visual population, continuity and optical parity

- [~] **PARTIAL (BARELY) | Artificial foreground shells removed; B still not accepted.** The originally fixed camera-space `near_giants()` were rejected. The attempted three independently simulated near-field replacements were also **rejected** as distracting and initially sharp. Both cohorts are now absent; that removal is operator-confirmed. Ordinary bubbles approach to near depth 2.8 and can enter the existing shared DoF layer by actual front-depth and aperture/focus; natural close-pass visual parity is not accepted. Do not reintroduce special giant cohorts. Original B requirement and camera/scene parallax evidence stay open.
- [~] **PARTIAL (BARELY) | Fused-cluster DoF gap remains OPEN.** The ordinary-shell depth test and `DefocusLayer` do not currently route `CLUSTER_VERTEX`/`CLUSTER_FRAGMENT` members through equivalent near-focus selection. Fused bubbles can therefore appear too sharp near the lens. **Explicit future action:** shared depth-selected defocus for fused clusters, with coherent cluster SDF union, no duplicated draw or extra clock and proof on camera orbit, aperture/focus and all presets. Do not bury or remove this limitation.
- [~] **PARTIAL (BARELY) | Bead-chain shimmer/flicker.** Operator: some traveling bead chains shimmer sharply, others remain stable. Likely root mechanisms: tiny bead size crosses the 1–2.5 px branch from a cheap glitter speck into full refractive `shadeBubble`; previous sparkles depended on changing world/projection radius `vSphere.w` and a discontinuous `fract > threshold` test. **Candidate 2026-10-19:** a bead-only stable seeded micro-glass branch samples a filtered scene probe and actual scene background, retains water tint/Fresnel/coverage/depth and OIT, with no unstable radius-dependent glint switch. This is not an unlit overlay. Need GPU playback/video before claiming relief; preserve tests for large-card and DPR shimmer, orbit and volume density.
- [~] **PARTIAL (BARELY) | Source-attached fizz/wakes detach when parent pops, fuses, exits or hits surface.** Original source indexed the compacted **currently visible shell SSBO** (`ebShell[owner*6]`), with no stable emitter identity or retiring record. After a parent leaves, fizz disappears or reads a different shell slot, which is consistent with the visible disconnect/fall. **Candidate 2026-10-19:** simulation-owned `wakes` snapshot records stable source IDs plus separate, bounded retiring emitters; renderer uploads a wake-only SSBO (not the shell buffer); shader freezes the last valid source and wipes opacity from the travel-facing head toward the tail over ~1.1 seconds, rather than generating a detached falling trail. No second logical clock. Physical continuity is not yet operator-tested. **Important distinction:** procedural *free bead chains* have no parent bubble and must not be described as attached wakes.
- [~] **PARTIAL (BARELY) | Whole-chain fade, curvature, 15% width.** Earlier `ceil(uChainFill)`/`vOpacity` fades, coherent sine arc and 1.15 lateral scaling compiled, but have not been accepted. Fractional draw-count changes can still remove whole integer chains abruptly because the shader cannot fade an instance it no longer draws; the source claim of whole-chain death fades must not be promoted to a proven fix. Preserve target §11.1 without shortening.
- [~] **COMPLETELY FUCKED | Coin-like clear giants / imperfect roundness, especially Preset 7.** Analytic sphere intersection does not establish believable spherical glass. Film/rim/interior/refraction/defocus can flatten it; no root cause conclusively isolated. Mock comparison and all relevant diagnostic views remain needed.
- [~] **PARTIAL (BARELY) | GPU shader crash (`vOpacity`) recovered, but native all-preset acceptance pending.** The prior clusters-vertex undeclared `vOpacity` stopped rendering; this was repaired, and operator ran **26 passing tests in 5.90s and confirmed rendering**. That is only crash recovery. The current micro-glass/wake candidate passes a GLSL 450 Mesa-compatible nine-pair compile/link gate; Windows NVIDIA OpenGL 4.6 revalidation is still required.
- [~] **PARTIAL (BARELY) | Settings Direction midline opt-in.** Source includes a stronger shared-midpoint guide via typed `Direction` option; native paint/DPR/operator review open. Separately, the sporadic **Settings lifecycle destruction barrier timeout remains unresolved**: collect owner-ref paths rather than relaxing barrier, retrying on timeout or blaming builder without evidence.
- [~] **COMPLETELY FUCKED | Mock fidelity A still incomplete.** Dense discrete bead rain, natural close-passing bubble softness, volume glints, trails, smoky wisps, copper/abyss scene art and all seven scene side-by-sides remain; preserve target §7 and §10 A findings, including explicit prohibitions on ribbon/sperm trails and a seabed.

- [~] **COMPLETELY FUCKED | Camera-dependent world-space wrapping; sudden bubbles at oblique camera angles.** `extruded_bubble_scene._wrapped_turn` rotates ordinary shell, cluster and wake *world locations* in response to the camera, while GPU beads/snow replicate `wrapTurn`. This "endless field" was asserted safe by an old full-turn *screen* test; the operator rejects the camera deception and observes suddenly entering bubbles. New read-only probe over 361 yaw samples exposes up to 29.49 world-units relocation (single yaw step 28.95). This is a source-level physical violation, not proof every jump is onscreen. Replace with fixed physical world objects and stable stream through orbit/tilt. Do not merely turn off the wrap and accept an empty 180° view. See target §12.
- [~] **COMPLETELY FUCKED | Bubble fade material disconnected; alpha changes size instead of transparency.** The logical simulator tracks 0.6-s birth / 0.9-s retirement alpha, yet renderer packs `r * sqrt(alpha)` and **no alpha attribute** for ordinary shells. Existing test explicitly demands this rejected behavior. Camera wrapping can additionally introduce already opaque bubbles without any transition; clusters do not share proper material lifetime opacity. Respect physical radius, material fade, cluster fusion and near DoF independently; operator/visual capture required.
- [~] **COMPLETELY FUCKED | Depth and perspective cancel, making bubbles visually flat.** World radius is calculated as snapshot radius × view depth × tanY × sqrt(alpha). Its perspective projection then divides by view depth; equal base radii at 2.8 and 32 depth project to the same size. Old renderer test accepts "same share of view at any depth", which contradicts target T4. Restore true world-size perspective and stable camera independently of the still-failed breathing. Prove actual pixel displacement of *matched identities*, not follower amplitude.
- [~] **COMPLETELY FUCKED | Bead paths split directions during orbit.** Operator screenshot contains distinct orientations. GPU procedural chains are born in turn-zero camera space and then rotated by camera-dependent `wrapTurn` per chain; ordinary bubbles and wakes use a different wrapped volume path. This supplies a strong mechanism for inconsistent headings, distinct from benign curved transverse drift. All flow families must use the same fixed world vector and preserve stable identity while camera turns.
- [~] **PARTIAL (BARELY) | Read-only source audit available, no renderer cure claimed.** `tools/extruded_bubble_source_audit.py` reproduces camera relocation, perspective cancellation, fake fades and double application of the Particles Range without Qt or GPU. It deliberately **does not** patch production motion, camera or shader. All assertions that a fix *looks* better require the operator or a visually capable agent with an actual offscreen render/capture. Never use these numbers as visual acceptance.
- [~] **PARTIAL (BARELY) | Micro-glass GPU budget unproven.** Stable micro-glass beads/wakes sample filtered probe and background, still lit/refractive enough for the scene. Before claiming success, a capture-capable agent must measure bead-pass GPU median/p90 and full frame at matched real music, quality tier, card size/DPR, and preserved presets, compared to the **pre-micro-glass** baseline; include 1672×941 and 2560×1440 and dense chain settings. Source-only performance estimates are not measurements. See target §12.

## 3. Negative controls and future admission

- [~] Do not treat `test_extruded_bubble_motion_contract.py`, shader compilation, EGL compatibility, idle phase calculations or a music follower changing as acceptance. The operator's **confirmed opposite visual result** supersedes them. This ledger records known failed attempts so they are not accidentally repeated as recommendations.
- [~] New work must declare which reactive layer owns **each** Range low/high, which logical audio driver and time integral it uses, the outgoing immutable snapshot field, renderer uniforms, expected scene-space/pixel motion and baseline quiet/music change. Record actual captured quiet→onset→sustained→silence output on the seven mutable presets. No secondary clock, redundant floor, driver or renderer simulation.
- [~] Retire an item or shorten its target description **only after explicit operator instruction**. A code fix not yet visually proven remains `[~]`, regardless of test pass. The actual unsuccessful approaches must stay accessible here even after future acceptance, without converting the live checklist into a changelog.


## 4. Live open regression inventory: full-dynamic source and Settings owner (2026-10-19)

- [~] **COMPLETELY FUCKED | Original all-controls scalar pipeline.** An earlier operator run showed **zero perceptible big or small bubble breathing, no reliable idle/music contrast anywhere and no meaningful reactive rays or emission**, even though all prior logical tests passed. Switching on Dynamic Floor made small rapid continuously oscillating breathing, unrelated to notes; this is an unacceptable dependency. The new log disproves the previously suggested always-low energy assumption: the 01:11:33 recreation edge reports `energy_level=1.000` (bars/waveform zero only at that edge). Previous continuous-phase/sine, kick-envelope and idle-rate multiplier approaches are confirmed FAILURES; keep the earlier attempts above and the original detailed target §§10–12.
- [~] **COMPLETELY FUCKED | Full-dynamic 2D band-source candidate RETESTED AND FAILED (`logs3a0d4fa1176.zip`; operator 2026-10-19).** This is **not** an unverified partial. After the source rewire, large and small bubbles **still do not visibly grow/shrink with the music**. At maximum Sensitivity or with Dynamic Floor enabled, the only detectable motion is a **weak, rapid, repeating pulse with no musical correlation**; ordinary settings look static. Idle versus playback, water/ambient, streams/drift, rays, beads, emission and every other attempted reactive feature remain wholly rejected. The runtime values and passing tests therefore cannot be presented as a successful music path. **Preserve the attempted source mechanics for diagnosis:** `logical_frame_capture` now reads original Bubble's `get_bubble_energy_bands()` **only when Extruded Bubble is playing**, through the existing generation-fenced capture. Simulation owns separate bass/body and mid/high delta+support followers, without extra clocks/floors. Big and mid sizes use their own authored low/high Ranges; the synthetic periodic radius oscillator does not run on production's band path. This is a source-backed candidate, **not evidence it looks any better**. Tests keep scalar 1.000 while driving changing bands and assert source-side changes/suppression of the production sine; **the real display contradicts any interpretation that these constitute visible musical breathing**. The older scalar-only tests remain numerical historical fixtures, not a passing pixel oracle. **Investigate the first broken stage**, including actual captured band tuples, control/Ranges, simulation radius, logical snapshots, projection/camera depth, material and tracked-id on-screen pixels across the *same real clip*. Compare Dynamic Floor OFF versus ON and low versus maximum Sensitivity only as diagnostics, not as accepted workarounds. Demand operator or full-resolution 2D/3D comparative offscreen rendering agent with real recorded music.
- [~] **COMPLETELY FUCKED | Emission/rays/stream MUSIC RESPONSE; single-Range SOURCE CHANGE ALSO FAILED VISUAL RETEST.** Earlier: Particle Range → smoothed emission → same Particle Range again → squared GPU density. Current `speck_amount` removes the second interpolation, preserving author-defined endpoints and squared count curve. Even after the full-dynamic candidate, the operator **again confirmed ALL reactivity failed**; rays, bead-chain fill, fizz and visual speck emission all remain failed until recorded frames demonstrate correct changes. The source mapping correction may still be structurally sensible, but **is not an observable fix**. Do not downgrade these to merely awaiting first operator validation.
- [~] **COMPLETELY FUCKED | Settings handoff owner survivor, not a barrier bug.** `logs3a0d4fa1175.zip`: 01:11:35 Settings queued, generation retired; 941 QObjects/3 Python owners initially in barrier; by 01:11:43 all QObjects, resources, thread work, subscriptions and other owners were gone, but `QuickDisplayVisualizerOwner:1` prevented closure. Neon Lake had a similar symptom, but its strong signal lambdas were a *different* identified cause; **not proven here**. Keep strict fail-closed barrier, preserve whole report. Runtime owner reference capture from diagnostic product (failure only) is the next falsifiable proof. Only fix the exact retaining reference. `extruded_bubble_builder.py` currently delegates generically and is not *yet* established as the retaining root, despite mode-specific reproduction.
- [~] **COMPLETELY FUCKED | Camera wraps, material fade, perspective, free-chain direction and fused near DoF are NOT addressed by this candidate.** Keep their full existing source-audit numbers and visual acceptance. Need a world that exists independently of the camera, real geometric view-distance and genuine transparent birth/death without suddenly introducing already-opaque instances at orbit angles. No camera-relative replacements. These remain independent of any improved musical audio feature lane.
- [~] **PARTIAL (BARELY) | Micro-glass GPU cost NOT measured.** Preserve same scene lighting and require offscreen visual agent's before/after pass GPU timings and 2560×1440/1672×941 comparison. Added band-feature capture also requires mode CPU tick-cost and source-call attribution; does not authorize always-on diagnostic polling.

## 5. Live evidence gate: full Settings sweep + binary frame trace (`logs3a0d4fa1177.zip`; 2026-10-19)

**Every item below stays `[~]`.** This supplements sections 1–4 and target §§10–14; it neither excuses nor retires a failure or converts this ledger into a chronological changes list.

- [~] **COMPLETELY FUCKED | All reactivity, despite substantial operator `--set` experiments.** Visual result unchanged: no music-correlated large/small breathing, idle/live speeds wrong, rays/emission/beads/stream/drift still do not react convincingly. High Sensitivity or Dynamic Floor gives a tiny fast unmusical pulse, not a successful baseline. The 02:25–02:30 Settings sweep in `[VIS_TECH_CONFIG]` includes Sensitivity `2.160 → 0.910 → 0.770 → 2.070` and a Dynamic Floor-on trial (`02:30:40`), so “try higher Sensitivity” is a repeated failed suggestion. These are owner-configuration entries, not proof the final renderer consumed any Range.
- [~] **PARTIAL (BARELY) | Presentation trace studied; root cause NOT established.** `screensaver_frame_trace.bin` is a 22,117,120-byte binary trace; the repository's decoder reads 614,364 events/348.70-s timestamp span. Counts: logical publish 15,012; Quick sync 12,693; draw/swap 12,245 each; audio analysis 11,572. Screen-1 lifecycle-aware steady swap median 11.503 ms, p99 19.202 ms, 23 >25 ms, max 124.832 ms (separately excludes lifecycle/not-rendering gaps). This disproves a generally dead renderer but includes **no** per-bubble output, bass/mid/high or GPU appearance data; no “input proven good” conclusion. Edge `energy_level` samples of 0.045 and 1.000 occur in different playback/recreation contexts and cannot substitute for synchronized input tracing.
- [~] **COMPLETELY FUCKED | Breathing source/measurement blind spots.** Current production `_snapshot` radii are nonnegative `base*(1+swell+pop)`; `body*0.38 + positive delta*2.7` plus smoothing can favor a held expansion rather than real growth/relaxation. The `snapshot.breath` field is *not* the same as actual big/small `swell` at bubble record index 5. `tools/visualizer_replay/extruded_bubble_traces.py` omits `body_bands`; the frame runtime substitutes `(0,0,0)`, so its scalar/breath plots **cannot** prove full-dynamic production breathing. The offscreen GL capture tool has real images but lacks synchronized per-ID feature/instance/pixel evidence in `capture.json`. Existing passing synthetic tests targeted the wrong acceptance boundary.
- [~] **COMPLETELY FUCKED | First response-loss point remains unknown.** Need same-sequence record of actual 2D Bubble-derived bass/mid/high, onset and source identity → authored low/high Ranges and smoothed simulation envelopes → SAME bubble identity (base radius, swell, alpha) → packed renderer instance/cluster, camera depth, projected pixel radius/DoF and material opacity → matching captured frames. Make the equivalent layer-by-layer measurement for ray-only pixels, chain/stream direction, motion speed, water-phase optical flow and counted/lit emission. Do not recommend additional blind multipliers, floors, timers, fake scene wrapping or preset edits. Follow target §14 and TestSuite's capture matrix.
- [~] **PARTIAL (BARELY) | Agent-only measurement gates unchanged.** Require operator physical acceptance or full-resolution Windows OpenGL offscreen/capture-capable visual agent; benchmark micro-glass GPU passes against the previous stable bead shader at 1672×941 and 2560×1440, plus logical CPU source-read cost. Fused cluster near DoF, camera wrapping, false perspective, true fade, bead wake/direction/shimmer, seven-preset fidelity and Settings lifecycle owner survivor remain explicitly open as previously detailed, including the strict barrier's unchanged ownership requirement.

## 6. Native recorded-audio forensic report (2026-10-20; investigation only)

**Tree examined:** `e599387303e282a16953f2d88fab62a854f74efd`, initially clean. No production code, presets,
Settings, accepted 2D Bubble or lifecycle policy changed. No agents delegated. Evidence is retained locally at
`logs/eb_forensics_20261020/`; these ignored artifacts are not bundled into source control. Reproduction tooling
is in `tools/visualizer_replay/{extruded_bubble_forensics,bubble_reference_capture,extruded_bubble_log_inventory}.py`.
Current work and acceptance remain in `Current_Plan.md` §4B. This report supersedes the earlier *unknown first
response-loss stage* for the measured offline cases only; it does not erase the operator's failed live retests.

### 6.1 Correct target: collapsed idle, strong musical excursions

Operator clarification 2026-10-20: **idle is a slow, gently collapsed resting state**, as in accepted 2D Bubble;
music reopens the response. This applies to size, drift, stream, beads/wakes, rays, emission and ambient/surface
motion. Nothing should remain remotely fast in idle. An autonomous periodic idle size oscillator is **not** the
requirement. Earlier mentions of missing "idle breathing" must not be read as a request to restore a sine.
`anything_mixed2.jsonl` should give impressive response immediately; accepted 2D Bubble supplies the minimum
response-scale reference, without becoming EB's simulation/settings owner.

### 6.2 Evidence and fidelity checks

- Native production GL host ran successfully on **NVIDIA GeForce RTX 4090/PCIe/SSE2**, with full-resolution
  1672×941 and 2560×1440 captures. This was not the earlier GLSL 450 compatibility substitute.
- `anything_p1/` and `anything_2d_full/`: the same first 12 seconds of `anything_mixed2.jsonl`, 1,091 recorded
  logical inputs, 144 captured frames each at 12 fps, unchanged curated preset 1. `comparison/` contains paired
  native frames, contact sheet and silent motion GIF. The final 2D comparator uses canonical CUSTOM viewport
  admission plus the production presentation resize resolver. **Discard `anything_2d/` for pixel comparison:**
  that initial tool run drew the canonical 420×280 card into the larger target; it was caught and corrected.
- `ragdoll_p1/`, `ragdoll_p7/`, `heavy_p1/`: full-minute real recordings (5,455 inputs each), including quiet,
  changing and heavy material. `p1_pixels/` and `p7_pixels_1440/`: native 30–36-second sequences from Ragdoll.
- `custody.jsonl` records actual production capture arguments (bands, scalar, playback, generation/activation,
  onsets and typed controls), private simulation followers read without mutation, stable logical IDs/base radii,
  alpha/swell/cluster/pop state, packed ordinary shell instances, view depth and projected centre/radius estimates.
  The radius estimates are first-order geometry, **not segmented pixel-radius measurements**. Clustered, popping
  and nonopaque births/deaths are excluded from the stable ordinary-shell size summaries.
- Each GPU sample also renders a **same-frame zero-swell counterfactual**, preserving time, world, camera,
  alpha, population, lighting and the pop expansion. Native `zero_swell_*.png` and `swell_difference_*.png`
  demonstrate that changed logical radius reaches actual pixels. Whole-frame differences include changed
  refraction/probe lighting; they are not isolated silhouette sizes or proof of musical quality.
- `controls/control_probe.json` compares real-input production captures, changing only Sustained Response or
  idle admission/control. Parameter echo is excluded when comparing evolved mode state.

### 6.3 Measured response loss: input varies, size transfer is much too restricted

For `anything_mixed2`'s opening 12 seconds, recorded Bubble bands have bass p05/median/p95
**0.0063 / 0.4556 / 0.7153**, mid **0.00085 / 0.3747 / 0.5148**, high
**0.00011 / 0.1473 / 0.3133**. These are not flat or missing in this replay.

| Same source interval, authored preset 1 | Median tracked large radius excursion | Median tracked small radius excursion |
| --- | ---: | ---: |
| Accepted original Bubble | **183.76%** | **117.42%** |
| Extruded Bubble | **12.56%** | **5.90%** |

Excursion is `(maximum - minimum) / minimum` within each observed mature, nonpop identity, then the median
across identities. The two modes have different populations/lifetimes; this is a response-scale comparison,
not a claim of identical geometry or lifetimes. 2D's radius comes from its final position payload; EB's statistic
uses its per-ID swell and fixed base, excluding alpha/cluster/pop confounds. Native captures visibly support the
scale difference. Example accepted 2D ID 1 spans **25.04–98.57 estimated px** over 1.507–3.488 s; EB ID 1
never exceeds **13.07%** musical expansion over its measured mature lifetime. No preset was retuned.

A stricter **same-ID, same-window** comparison (1.507–3.147 s) removes the differing-lifetime explanation:
2D ID 1's final radius/base moves **0.7068 → 2.7819**, while EB ID 1 stays within **1.0384–1.1307**.
This directly shows the absent collapsed state and restricted expansion, rather than relying solely on a
population median or different base sizes.

The source mechanisms are specific:

1. `extruded_bubble_frame_runtime.py` scales the full Breathing control by **0.35**, Small Pulse by **0.15**.
   Thus even a maximum high handle is only a 35%/15% expansion ceiling, before any follower attenuation.
   Preset 1's authored `[0.15,0.6]` becomes `[0.0525,0.21]`; Small Pulse `[0.15,0.8]` becomes `[0.0225,0.12]`.
2. `ExtrudedBubbleSimulation.advance` combines bands into another slow shared `level`, then the body lane
   into `min(1, body*0.38 + positive_delta*2.7)`, followed by attack/release smoothing. Both the Range
   interpolation and that envelope attenuate the same size excursion. On held body energy the delta vanishes,
   leaving a mostly held 0.38×body support component.
3. `_snapshot` applies `radius = base * (1 + swell + pop_expansion)` with nonnegative swell. There is no
   independent musically collapsed radius below base. Accepted 2D's `_big_render_pulse_factor`, in contrast,
   has explicit quiet contraction plus much wider musical pulse authority. Copying its equations is not required;
   preserving EB's present tiny positive-only transfer is not an adequate target.
4. At default smoothing, the extra shared level takes approximately **0.313 s attack / 1.5 s release**;
   the body follower approximately **0.094 / 0.413 s**; stream speed **0.438 / 3.75 s**. These are separate
   stages, not a single "quick attack" guarantee. Ragdoll's stream p05–p95 is **0.1319–0.1588 units/s**,
   Heavy's **0.1341–0.1500**, consistent with the reported weak within-song speed contrast.

Across the Ragdoll full-minute ordinary population at 1672×941, the music-added first-order radius is median
**0.449 px**, p95 **4.228 px**; the small population dominates that median. The same-frame GPU interventions
change the native image, so **a renderer that universally drops radius changes is falsified for these cases**.
Camera/depth/fade defects remain real, but depth cancellation does not mathematically cancel the *relative*
musical swell: do not attribute every reactivity failure to projection alone.

### 6.4 Two control failures and the actual idle violation

- **Sustained Response is dead in production evolution.** `controls.sustained` only scales a local `shimmer`
  term consumed by the legacy scalar-only snapshot branch. Production always supplies a band tuple. Over 728
  real inputs, Sustained Response **0 versus 1 gives identical evolved mode state** after removing only the
  expected Settings parameter echo. This is a reproduced owner-to-consumer disconnect.
- With playback off, Idle Energy **0 versus 1 gives identical bubble records** and zero swell. The output stays
  at the uncontracted base radius; it does **not** approach 2D's musically collapsed radius. Meanwhile the ambient
  phase endpoint over the 8-second probe changes **0.9598 → 2.8794**, a 3× rate increase. Stream travel still
  comes from the low Stream Speed handle and the ordinary sway sinusoid still uses raw logical time.
  Therefore fixing idle means **slow settling and collapse across all reactive lanes**, not adding oscillation.
  The operator's specific *idle faster than playback* optical-flow inversion is not yet reproduced/attributed.
- Rays, emission and most motion share the compressed `level`/onset followers. Ray strength then maps another
  authored low/high Range; free-chain counts use `state.emission`, whereas attached fizz count uses wake owners
  and quality. These are distinct populations, not one proven music-driven emission system. Separate ray-only,
  water-motion and particle-count pixel interventions are still required; the radius intervention does not prove them.

### 6.5 Settings/log forensics and the limits of PCM reanalysis

`extruded_bubble_log_inventory` read 15 ZIPs in `F:/Programming/Apps` without extracting or changing them,
hashing each and retaining EB-only Settings/configuration receipts. Eight archives have EB technical receipts;
overlapping retained logs mean counts are **not independent runs**. No receipts in an older archive is not
proof EB never ran. All selected Settings records parsed without errors, including logged Qt reprs elsewhere
in widgets (the tool lexically selects the top-level Visualizer section before evaluating numeric leaves).

The latest `logs3a0d4fa1177.zip` has 14 Settings snapshots with `mode=extruded_bubble`. These show actual
authored values in addition to the previously documented technical sweep:

| Control | Distinct retained EB Settings values |
| --- | --- |
| Breathing | `[0.06,0.89]`, `[0.15,0.6]`, `[0.48,0.84]` |
| Small Pulse | `[0.15,0.8]`, `[0.15,0.94]` |
| Stream Speed | `[0.07,0.8]`, `[0.25,0.8]` |
| Sustained Response / Idle Energy | `0.55,0.6` / `0.22,0.5` |
| Rays / Particles | `[0.1,0.2]`, `[0.6,0.8]` / `[0.1,0.35]`, `[0.85,1.0]` |

These prove authored changes were saved/logged, **not their eventual native uniforms**. Recommending another
blind sensitivity/Range sweep is not a diagnosis. The local binary frame trace reproduces the previous
**614,364 events / 15,012 logical publications / 12,245 draws / 11,572 audio analyses** result; it still contains
no band tuples or per-object radii.

`provenance.json` confirms the local binary trace is SHA-256-identical to the retained latest ZIP's trace and
records source/tool hashes. `git diff` over production directories/presets was empty throughout this investigation.

Ordinary replay uses **recorded post-DSP bands**; changing Sensitivity/Floor there cannot test how live DSP
produces those bands. `--reanalyze-pcm` is a separately labelled *hybrid diagnostic*: native recorded PCM tails
through the current production body-band DSP/getter, requested block size, retained recorded onsets/loudness
and sampled source cadence. It cannot recover skipped native callbacks, negotiated Auto block sizes or the
original recorder's complete configuration/history. Ragdoll at requested 512/manual floor shows bass/mid
plateaus near **0.770648 / 0.9712** even at sensitivity 0.4; 2.07 does not reopen those plateaus. Dynamic Floor
changes support but still holds bass near **0.728936**. This demonstrates a plausible upstream flattening
mechanism under controlled inputs, **not proof those tuples were present in the operator's failing live run**.
Do not change accepted/shared DSP based on this hybrid experiment.

### 6.6 Independent geometry, optics, lifecycle and performance findings

- Current `source_audit.json` reproduces **29.4868 world-unit displacement / 28.9467-unit single jump** with
  camera yaw. Near depth 2.8 and far depth 32 have identical projected normalized radius. Alpha 0.25 produces
  radius ratio 0.5, with ordinary shell material opacity hardcoded to 1. Clusters ignore equivalent logical fade
  and bypass ordinary near DoF. These are concrete independent ownership/representation defects, not cures for
  the restricted musical transfer. Camera tilt/zoom also enter volume construction; physical world invariance
  must cover the complete pose, not yaw alone.
- Native Preset 7 still shows clear/coin-like shells and dense bright particulate. Sphere-ray maths alone does
  not establish convincing glass. The ordinary shell's screen-facing ray convention and fused-cluster optics
  require separate normals/coverage/reflection/transmission diagnostic views before naming the dominant cause.
- Every inspected archive lacks `[PYTHON_OWNER_REFS*]` receipts. The 01:11:43 survivor remains precisely one
  `QuickDisplayVisualizerOwner`, all other retirement categories clear. Current source has a **Diagnostic-build-only,
  failure-only** referrer path; debug/trace flags alone do not activate it. No retaining strong edge is proved.
  Keep **Awaiting Logs** for an actual failure with that receipt; never soften the barrier or blame the typed builder.
- Current offscreen observations (36 frames; first cold compile excluded) are P1 **5.67/7.54 ms median/p90** at
  1672×941 and P7 **15.79/18.59 ms** at 2560×1440. These sampled paired-intervention runs are not controlled
  product cadence or a before/after benchmark. P1 serial draw queries at 1440p give shells **1.913 ms**, OIT
  resolve **1.594**, backdrop **1.569**, beads **0.271**. Serial query shares cannot establish frame totals or
  exonerate micro-glass. Pre-micro-glass comparison, dense chains, both resolutions/presets, GL/Python call counts,
  CPU band-read cost and idle/dormant neutrality remain unmeasured acceptance debt.

**Result:** reproduced response compression and two control/rest-state contract failures; verified changing
radius reaches native pixels; independently reproduced world/perspective/fade defects. No repair or physical
acceptance is claimed. Native live input values, component-specific optical flow, coin-like material root,
fused near DoF, wake/chain continuity and the strong Settings-owner retaining edge remain open.

## 7. First recovery candidate and native minimum-size/ray attribution (2026-10-20)

This is source and native offscreen evidence, **not complete EB acceptance**. The operator subsequently reports
that most idle motions improved tremendously, but attached beads scale strangely and stream/emission/surface
water can appear stopped. The live follow-up order and exact requirements remain in `Current_Plan.md` §4B.

### 7.1 Owning-boundary changes

The frame runtime carries authored Breathing/Small Pulse strengths directly rather than reducing them to
35%/15% first. Only the existing full-dynamic bass/mid/high feed and weighted onsets drive the simulation.
The obsolete scalar-only sine branch is removed; runtime callers must supply bands, and playing production
capture requires the canonical getter rather than substituting pre-AGC or zero bands on a missing interface.

Large body support uses bass with limited mid/high support; small body support uses mid/high with limited bass
support. Onset accents retain headroom. Sustained Response now strengthens actual body/motion state instead of
a discarded branch. At default smoothing the body follower has 75 ms attack, 250 ms musical release and
1.875 s silence release. The renderer still consumes immutable logical snapshots; no DSP, clock, polling,
renderer simulation or authored preset change was added. Original 2D Bubble is untouched.

For strength Range `q,l`, envelope `d` and expansion authority `g` (large 4, mid 3), the candidate is:

```text
s = clamp(max(q,l), 0, 1)
rest = max(0.13, 1 - 1.45*s)
radius / nominal = rest + (1-rest)*d + g*lerp(q,l,d)*d
```

Thus zero strength disables size reaction; normal strengths permit 0.13× nominal rest. Signed `swell` is this
factor minus 1. An initial candidate's 0.49× big rest was rejected during the minimum-size audit: 2D's large
formula permits 0.22× before its additional contraction bias, about 0.132× with the accepted preset's 0.4 bias.
The actual opening 2D capture already contains a mature big identity at 0.2256× nominal. Minimum size is a
separate requirement from peak size or percentage excursion.

The simulation now integrates very slow resting motion/shimmer, uses musical phase for sway, and releases
stream/drift/emission toward low activity. Wakes carry the reacted parent radius to keep their source aligned.
The latter also exposed excessive attached-bead scaling; that is a confirmed follow-up, not accepted behavior.
Collision broadphase/reach/fuse/bounce still use nominal radii and need the physical-world correction; they must
not be mistaken for matching the newly expanded size range.

### 7.2 Evidence and measured limits

Local evidence is under `logs/eb_reactivity_20261020/` (ignored media/custody; retained on this workstation):

- `minimum_p1`: opening 12 s of real `anything_mixed2`, 1,091 logical inputs, 360 native 1672×941 frames at
  30 fps, same-frame zero-swell controls, silent GIF/MP4, contact sheet, per-ID custody and source hashes.
- `minimum_p7_1440`: opening 4 s, 120 native 2560×1440 frames at 30 fps, same production path/interventions.
- `ragdoll_current`, `heavy_current`, `soft_current`: full-minute CPU custody from the real recordings.
- `pause_resume_p1`: actual first 4 s, an explicitly constructed 12 s playback-off interval holding the last
  recorded frame, then the remaining real input with shifted logical timestamps. 96 native frames at 4 fps;
  useful for long settling, **not** high-frequency judder or live audio reconnection proof.
- `ray_interventions` / `ray_interventions_p7_complete`: identical recorded state with only ray driver and
  Ray Softness changed, native PNGs plus actual mapped values. Reproducer: `extruded_bubble_ray_probe`.

Relevant source hashes are recorded before the latest forensic runs and checked unchanged afterward. UI tooltip
wording changed between the P1/P7 captures; simulation/render source is identical. Earlier `candidate_p1`,
`response_p1` and `final_p1` are superseded candidate runs, not current minimum-size evidence.

Mature, unclustered, nonpopping stable identities (same exclusions as §6):

| Evidence | Median per-ID large excursion | Median per-ID small excursion |
| --- | ---: | ---: |
| old EB, opening 12 s | 12.56% | 5.90% |
| accepted 2D, opening 12 s | 183.76% | 117.42% |
| candidate EB, opening 12 s | 959.55% | 655.86% |
| candidate Ragdoll, full minute | 151.00% | 158.80% |
| candidate Heavy, full minute | 199.40% | 113.57% |
| candidate soft/acoustic, full minute | 144.87% | 112.04% |

The very large opening percentages include the newly available tiny silent rest; **they do not prove musical
parity inside an active phrase**. In the stricter ID-1 1.507–3.147 s window, old EB was 1.038–1.131×,
candidate EB is **0.975–2.086×**, and accepted 2D is **0.707–2.782×**. Main response is substantially restored,
but this tighter minimum/peak comparison still falls short of 2D and remains actionable. Do not tune against a
single identity/window alone or use the opening percentage to close the gate.

Mature ordinary projected minimum radii in the candidate P1 opening are approximately **4.74 px large / 1.59 px
small**. These are first-order projection estimates, not segmented silhouettes; the native images and paired
interventions establish delivery, while optics/DoF still require their own appearance judgment. During the
controlled pause, 6 large and 20 small records remain near 0.132× / 0.131× at 15.9 s, then expand again on real
bands after 16 s without resetting the integrated phase. Stream/drift/emission remain numerically nonzero but
the operator's apparent-stop report requires pixel-speed/count verification. Rays remain visually bright in
silence because their Range consumer retains an authored floor: see below.

Final focused response/minimum-size gates: **42 passed**. Native renderer/resource/shader/wake gate:
**36 passed** (a bounded Qt fixture supplies the production graphics policy without the global environment-
rewriting conftest). Missing fixtures in an initial `--noconftest` run were harness setup errors, not product
failures. Legacy false perspective/fade oracles within the renderer suite remain explicitly excluded from
physical acceptance. No full suite or product build was run.

Sampled offscreen GPU observations are P1 **5.97/8.08 ms median/p90** and P7 at 1440p **16.61/21.02 ms**;
first compile excluded. These paired readback/PNG runs are not controlled product performance comparisons.
Recordings contain lossless PCM histories but several adjacent nonzero overlaps are ambiguous; no guessed
continuous soundtrack was labelled synchronized. Silent captures retain actual recorded feature timestamps.

### 7.3 Rays: dead softness consumer and compressed visible response

Native same-state interventions establish two different mechanisms:

1. **Preset 7 / Deep Light Ray Softness is dead.** `scene_knobs` changes fan frequency/contrast, but Deep Light
   uses the marched shaft pattern. Its `uShaftSoft` stays at the renderer default 0. For every tested driver
   (0, 0.5, 1), softness 0 versus 1 produces **byte-identical native RGB output**. Sunlit Surface does change:
   the same comparison gives mean absolute RGB differences about 23.8–28.9. Do not call the whole setting dead;
   connect it to the actual consumer in both light types.
2. **The ray driver cannot collapse the authored quiet floor.** P1's actual Range is `[0.6,0.8]`; driver 0
   still uploads 0.6. At softness 0, the full 0→1 driver sweep changes central RGB mean only
   **111.50→116.63** in the fixed native probe. At normal recorded variation it is narrower still. This is a
   reproduced weak delivery contrast, not absence of a changing simulation field. P7's Range is `[0.1,0.2]`.

The half-resolution blur uses fixed taps, independent of Ray Softness and resolution; fan softness changes
frequency/contrast rather than a common beam-edge profile. Repair the dead consumer first, then verify native
driver/softness endpoints and actual real-passage ray ROIs at both resolutions. Quiet music, playback-off rest,
continuous phase, broad shafts and authored surface/light appearance require distinct checks. No light fix is
claimed in this checkpoint.

## 8. Ray consumer correction (2026-10-20 candidate)

`scene_knobs` now sends Ray Softness to `shaft_soft` for **both** light types, retaining fan controls.
This repairs Deep Light's proved dead consumer without another program, pass, target or clock. Native P7
softness 0/1 mean absolute RGB difference is now **11.75** at full driver (previously exactly 0), and the same
probe was repeated at 2560×1440. Source mapping plus the native regression test fail if this consumer is removed.

Ray strength now resolves its authored Range once, then opens with `0.03 + 0.97*driver` resting activity.
At driver 0 P1 uploads 0.018 rather than 0.6; at driver 1 it still reaches its authored 0.8. P7 similarly spans
0.003–0.2. This is a deliberate resting-activity contract, not a changed preset or additional audio floor.
Continuous simulation followers preserve release/phase; disabled rays remain off.

Evidence: `logs/eb_reactivity_20261020/rays_fixed_p1`, `rays_fixed_p7`, `rays_fixed_p7_1440`, plus the real opening
12-second `light_passage_p1` native sequence. Fixed-state central RGB mean at softness 0 now spans
**93.36–114.66** for P1, compared with **111.50–116.63** before. At softness 1 P1 spans **95.27–161.16**.
P7's scene is intentionally dominated by other light/particulate, so its central-region average remains a weak
ray-isolation measure; retain the full native grids and inspect shaft regions rather than declaring global
brightness a musical oracle. No authored Range, palette, particle count or surface-light setting was changed.

**30 focused renderer checks pass**, including actual GL Deep Light softness pixels, driver ownership and
prepared-frame allocation/resource retirement. The shader source is unchanged. These checks establish restored
consumer behavior, not full broad-shaft/reference or operator listening acceptance. Fixed blur footprint,
real-passage profile/ROI response, world/camera optics and all non-light EB defects remain in the live plan.
Next operator-requested slice: constrain free/attached bead size to roughly ±10%, always strictly below the
current parent, and restore visibly very slow nonzero idle stream/emission/water without losing improved settling.

## 9. Bounded bead size and visible slow rest (2026-10-20 candidate)

The operator's retest identifies attached wakes scaling excessively with a reacting parent, and idle
stream/emission/surface appearing stopped despite much improved settling. The correction keeps the existing
8-float wake transport, giving its unused final leaf a **nominal parent radius**. Live/retiring records retain
both nominal and reacted radii; the world mapper scales both consistently. The attachment follows reacted
radius; bead size, trail reach and width derive from nominal size. Musical bead sizing uses 0.9–1.1× for both
free chains and attached wakes. Static per-bead variety/tail taper and lifetime opacity remain separate.

Attached nominal bead fractions are kept below the parent's supported resting scale. A GPU visibility guard
also requires the rendered bead footprint (including half-pixel radius) to stay strictly smaller than its
current fading parent. Unsupported tiny beads fade/hide rather than grow to parent size. Retirement retains
its own last source and nominal radius, without slot rebinding. No new buffer, transport stride, draw, clock,
poller or simulation owner was introduced.

Idle motion now targets 0.03–0.09 phase units/s across Idle Energy (normal 0.06; previous candidate 0.025),
still far below music and the old 0.24 resting rate. Sway's **velocity amplitude** now settles with the existing
motion follower: slowing a sine's phase alone had left a near-constant fast lateral velocity. Emission retains
one-quarter of its authored quiet strength at rest, independently of the smaller motion activity; the old
0.025 factor was squared again by particle density. P1's 0.1 quiet strength thus supports roughly 135 requested
specks before quality scaling, rather than roughly one. Zero authored amount remains zero; this is resting
visual activity, not an audio/DSP floor.

Evidence: `beads_rest_p1` (controlled pause/resume, 96 native frames), `beads_rest_p7_1440` (36 native frames
across late rest/resume), and `beads_idle_final_p1` (final sway-amplitude correction, 16 native frames).
The final idle surface-region image changes over a second (mean absolute RGB about 8.62), but this is an image
difference, not an isolated water optical-flow measurement. Source/identity traces separately establish slow
nonzero motion. Pixel-speed/count/appearance and physical acceptance remain open.

**44 focused response/simulation/wake checks pass.** Native renderer/shader/generated-bead geometry group:
**34 passed**; the strengthened free-chain assertions also passed separately. The GPU contract executes the
actual production `beadInstance()` and reads its output, rather than repeating its equations in Python. It
checks parent scales 0.13–5×, low/full alpha, ±10% size inputs, strict physical/projected parent bounds, and free
chain bounds. The ray-only image test now explicitly isolates free/attached beads, since their legitimate
level-driven size changes must not be misattributed to rays. No full suite or product build was run.

## 10. Latest log, population limits and sustained small-size comparison (2026-10-20)

`F:/Programming/Apps/logs324fd07064.zip` is the new archive. Inventory now covers 16 ZIPs; this archive contains
66 retained EB technical receipts and 12 selected Settings snapshots, including older rotations. The current
15:10:40/15:16:31 Settings receipts confirm **Large [0,4], Small [20,50]**, Small Pulse [0.15,0.8], Sustained 0.6,
Particles [0.85,1], Bead Chains [2,4], and Ray Softness 0.53 then 0.81. This proves saved authoring, not each
rendered class count. Its four retained lifecycle timeouts are dated October 18–19, **not new October 20
failures**; no owner-referrer receipt is present. Do not conflate retained history with a reproduced new crash.

### 10.1 Two separate count-admission defects

The opening reference replay with Large [0,4] stays at four or fewer large identities, while some small-class
shells look large. That did not exonerate admission in other passages. Two bounded falsifiers established:

- With each source band within [0,1], the weighted small-body mix could reach 1.05. Its shared level then
  extrapolated population Ranges: a 20–50 Small setting admitted **51**. The normalized mix is now bounded
  before it can drive Range interpolation.
- In a 0–4 Large test (3 s high → 0.35 s low → high), retiring records were excluded from target accounting
  while still visible. Admission reached **five** while the old pair faded. Retiring records now retain their
  authored ceiling slots; replacement waits until space exists. Lowering a previous higher setting still
  lets old identities retire rather than teleport/delete them. Logical retirement is preserved; the separately
  documented material-alpha/radius defect remains open, so this is not acceptance of current visible fades.

### 10.2 Real-passage scale versus controlled held support

The full real Heavy comparison before the small-lane correction shows why simply reducing all small gain
would be misleading: accepted 2D small median radius is **21.05 px**, EB **20.47 px** at the matched 1672×941
viewport. Their nominal small radii differ (medians 9.89 versus 20.17 px), while their response factors differ
(medians 2.08 versus 1.02). The whole-passage averages can look similar while EB has the wrong held-body behavior.

The first held-frame attempt was **invalid as a steady-body probe**: copying a real feature also repeated its
recorded snare every 11 ms. `held_hot_comparison.json` / `held_hot_actual_feature.jsonl` are rejected for this
claim. Corrected `held_bands_baseline_corrected.json` / `held_bands_candidate_corrected.json` explicitly clear
new onsets, scheduler events and transient lanes while holding the real recorded band tuple
**(0.500531, 0.971323, 0.587140)** for 13.2 s. This is a controlled hold, not continuous music or a live tuple receipt.
The baseline uses a process-local simulation-source override from `3c63d31e`, with compiled-source SHA recorded;
it does not check out, revert or mutate the worktree.

| Mature ordinary small radius at held bands | Median | Maximum |
| --- | ---: | ---: |
| accepted 2D | 24.53 px | 40.47 px |
| previous EB | 50.79 px | 83.00 px |
| final candidate EB | 24.31 px | 41.43 px |

The small lane now separates positive **changes in existing vocal/body energy** from restrained held support,
using a simulation-owned visual reference follower; weighted onset accents remain separate. No new DSP, audio
floor, capture or clock is added. Big response remains independent. The recorded hot-hold test protects class
separation without depending on current rendered radius to identify a class. Transient small peaks remain
strong and require native review; the hold result does not close every small-size/hierarchy question.

Latest candidate evidence: `vocal_recovery_p1` (real opening 12 s, 96 paired native frames),
`vocal_heavy_current` (full-minute CPU custody using latest saved EB settings), and
`vocal_heavy_p7_pixels` (24 paired native 1440p frames). The later slot-admission guard is covered by its focused
reversal test. **47 focused simulation/recording/motion/wake checks pass.** Native physical acceptance and the
camera/geometry/collision work remain open; saved settings and a screenshot alone do not identify each shell.
`held_bands_final_verified.json` repeats the corrected protocol after the retiring-slot guard; its small
population median differs slightly from the earlier 25.35 px because admitted identities differ. The underlying
held small-envelope factor is unchanged. Both corrected artifacts retain their source hash and intervention scope.

## 11. Lower-left distortion: independent native coverage audit

One operator-requested Sol 6.1 Medium agent performed the read-only source audit and a bounded native
falsifier; the primary inspected its source, images and metadata. The still cannot establish the original
offending shell's cluster membership, but the renderer discrepancy is independently reproduced.

`logs/eb_reactivity_20261020/distortion_audit/` compares unmodified production ordinary/cluster shaders with
`uDiag=5` at a fixed camera. A radius-0.6 sphere at depth 6 is compared at center and (-4,-2.4,-6). A coincident
radius-1e-6 second member admits the cluster path without changing the SDF silhouette. Direct RGBA32F OIT
readback isolates coverage from lighting/refraction/post effects. All four native RTX 4090 draws return GL error 0.

| Position | Ordinary axis ratio | Cluster axis ratio |
| --- | ---: | ---: |
| center | 1.0000 | 1.0000 |
| edge | 1.0005 | **1.2692** |

The cluster result matches the analytic rectilinear perspective ratio 1.2691. Ordinary shells deliberately use
screen-round bounds/rays; clusters use true view rays/bounds, producing radial off-axis elongation. Refraction
can deform the interior but cannot by itself explain this independently captured outer-coverage difference.
Fix common projection/ray/depth conventions with the physical-world work; reducing the cluster quad alone
would clip the defect rather than repair it.

The same audit quantifies collision/world mismatch: normalized centers z=.20/.29 with nominal radii .05/.05
meet the present .095 collision threshold, yet render with a **2.0299-world-unit surface gap** and only .05078
blend. Thus Fuse can create disconnected members. Existing missing fused fade and near DoF are separate.
Near-bound/eye-inside guard discrepancies also remain, but are a weaker explanation for this particular still.
The operator's requested view-aware overlap policy must manage visible crossings continuously without forcing
distant surfaces into such a disconnected fusion or teleporting geometry; its fixed-camera/Auto-Rotate gates
remain in the live plan.

## 12. Emission/Range and quality audit: concrete next consumer defects

The same single reviewer traced canonical UI/model/capture and production consumers. Authoring reaches the
frame; downstream semantics are the defects:

| Population | Existing consumer before correction |
| --- | --- |
| main large/small | normalized musical level and their own count Ranges; independent of Particles |
| free chains | Bead Chains Range read at **Particles-resolved emission**, with 12 chains per displayed unit |
| attached fizz | wake owners ×64×quality, truncated to whole-owner groups; no emission input |
| marine snow | fixed 2500×quality, no emission input; full opacity |
| glowing particles | resolved emission² for allocation, emission×2.4 for brightness |

Therefore Particles [0,0] currently suppresses glowing particles but leaves snow/fizz, and disables the free
chain Range's musical modulation through cross-Range coupling. At Balanced, two wake sources can be reduced
to one entire trail; prefix budgeting can drop retiring tails because live records precede tombstones.
Free-chain ceil allocation **already has fractional opacity** and stable local identities: the earlier blanket
claim that integer chain removal necessarily pops was not established. Glowing speck integer prefixes lack
equivalent entry opacity, but their perceptual significance still requires a pixel boundary test.

The bounded correction should resolve chain authoring independently from the normalized simulation level;
snow/fizz should consume already-resolved emission with fractional allocation opacity, and every stable wake
should receive a per-owner quality budget. Snow's fragment branch must actually multiply the generated opacity;
changing only its vertex output would be a dead consumer. Preserve identity/local seed, zero-budget safety,
nominal/reacted radius separation, and the existing parent-size safeguard. This section records diagnosis,
not an implemented or accepted emission repair.

## 13. Emission consumer candidate and depth-first overlap clarification

The bounded correction in §12 is now implemented. `_procedural_fill` is the renderer's sole continuous
allocation helper: Bead Chains resolves its own Range at normalized simulation level, while snow and each
attached wake consume the already-resolved emission multiplied by the quality share. Ceil allocation preserves
the fractional final mote through opacity. The snow fragment now consumes that opacity; it previously ignored
the varying entirely. Wake allocation uses a per-owner stride, keeping both live and retiring owners at lower
quality rather than truncating the prefix to whole 64-mote owners. Local seeds remain source ID + mote index;
zero budget avoids division and draws, with owner bounds checked before SSBO reads. Existing nominal/reacted
radius separation, ±10% bead sizing and strict parent-size safeguards remain unchanged.

**43 focused native renderer/generator/shader/wake checks pass.** Actual production renderer uniform/draw
observations cover two reduced-quality wake owners and zero emission. Generator readback covers both owners,
including a retiring source and fractional last-mote opacity. An isolated production snow-fragment/OIT draw at
opacity 0/.25/1 proves zero output and increasing fractional output, rejecting the old ignored-varying defect.
This is a consumer correction, not an independent musical particle-birth model. Integer glowing-speck allocation
and density/lifetime appearance remain distinct open measurements.

Actual `anything_mixed2.jsonl` native captures use unmodified preset activation:
`logs/eb_reactivity_20261020/emission_final_p1` contains 16 paired frames over the opening 4 s at 1672×941;
`emission_final_p7_1440` contains 12 paired frames over 3 s at 2560×1440. Each retains source hashes, clip/settings
receipts, stable-ID custody and actual same-frame zero-swell controls. The primary inspected both contact
sheets: onset opens the shell/particulate field, but P7's competing fine bright detail and limited depth hierarchy
remain visibly short of the mock. These short 4-fps sequences cannot accept musical timing, birth/death, physical
idle, or cadence/performance. They preserve the real recorded features, not reconstructed synchronized audio.
No preset files, clocks, DSP, buffers or continuous instrumentation were added. At full emission High retains
the former maximum per-owner budget; lower emission reduces work. Reduced tiers can allocate one fractional
extra mote per owner due to ceil rather than discarding whole sources; fixed wake SSBO capacity is unchanged.

The operator's subsequent copper mock/product pair refines overlap policy. The mock has legitimate crossings
that remain readable through softer large foreground forms, sharper smaller distant forms and restrained
competing interior detail. The product shows stacks of similarly sharp rims and bright interiors. This visual
comparison supports depth/source/material causes; it cannot identify the exact depth or membership of every
shell in the still. Correct fixed-world placement, physical perspective, ordinary/fused projection, material
alpha, depth attenuation and near DoF before adding screen-space reactions. Preserve convincing overlaps;
projected intersection alone must not automatically pop, bounce or fuse. The subsequent view-aware policy
targets persistent unreadable crossings, preserving stable identity, continuous geometry and extremely gentle
opacity retirement. Auto Rotate remains the later challenge. No overlap-policy implementation is claimed here.
