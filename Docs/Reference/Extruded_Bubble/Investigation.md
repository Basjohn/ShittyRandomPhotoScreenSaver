# Extruded Bubble | Physical Reactivity, Bead/Wake and Optics Failure Ledger

**STRONG RETENTION VALUE DOCUMENT**  
**Live, source-backed historical bug record.** All statuses below remain `[~]` until the operator expressly accepts a visual result.  
**Owner of requirements/physical acceptance:** [`Target.md`](Target.md) §§7–11A; sequencing: [`../../../Current_Plan.md`](../../../Current_Plan.md) §4B. This file holds attempted mechanisms, rejected outcomes, and still-unverified repairs. It does **not** replace the target checklist, weaken `Spec.md`, or become a chronological changelog.

**Classification key:** `COMPLETELY FUCKED` = operator-confirmed physical failure; `PARTIAL (BARELY)` = code path exists or a narrow defect changed, but the actual intended visual outcome has not passed. Both deliberately use `[~]`, not `[x]`; neither is clearance. A passing synthetic test is never evidence of displayed reactivity. Every preset is operator-authored and mutable; no retuning a preset simply to mask an implementation failure.


## 38. All-angle world lighting audit and agent-first validation protocol (unaccepted)

**Question:** At a physical camera position just beneath Sunlit Surface, if the camera turns to look *down* along the underwater sun shafts, will shafts occupy the same world space as when observed looking upward or from the side? **Source answer: partial true 3D plus a deliberate view-direction approximation; native all-angle behavior not verified.**

- `rendering/gl_programs/extruded_bubble_scene.py::physical_camera` supplies world eye, rotation and unchanged projection/FOV; the surface-bound camera eye is clipped beneath `SURFACE_Y - 0.5`. The backdrop in `rendering/gl_programs/extruded_bubble_program.py::basinWater` intersects view rays with `SURFACE_Y` for positive ray Y, shading an actual fixed *plane* with noisy/rippled surface normals. It is not separate polygonal displaced water geometry. Changing the normals can shift the apparent glint/bright patch; don't confuse that view appearance with a different physical Y plane.
- The shaft pass `labShafts` ray-marches **world positions** `uEye + ray*s`, checks each against the authored `surfaceY`, samples water/shaft patterns in world X/Z and fades below the surface. `beamExtent` uses the physical Ray Source→End segment, and the renderer receives the same eye from the physical camera contract. This gives a real physical basis for a downward view, but does not prove the final pixel appearance.
- In the **same shader**, `labShaftFan` builds an angular sun-relative pattern from `ray`, not a ray-marched 3D scatterer; its visibility is gated by `max(beamExtent(uEye+ray*12), beamExtent(uEye+ray*23))`. The march also has the view weight `(0.25 + pow(max(dot(ray,uSunBelow),0),2))`; the backdrop additionally applies an even stronger look-toward-light factor through `uRayFocus`. The fan may strongly diminish when looking *away* from the light. Both masks can make physically present shafts appear absent, alter their apparent direction or follow the camera view more than the scene. This is a **known approximation, not cleared geometry parity**.
- In **Sunlit Surface**, distant sun illumination and independently authored `Ray Source→End` are two different semantics, so do not assume a real positional lamp at Light Source. In **Deep Light**, renderer explicitly links its shaft origin to authored Light Source and leaves Ray End independent. The earlier operator Light/Ray mismatch remains an active source/UI/renderer parity check, despite this intended distinction.
- The renderer's `sceneTransmittance` attenuates shafts with at most four dominant shell proxies and a bounded **aggregate** dust term; this is not full per-shell or per-particle path tracing. Do not call it correct geometry simply because a GL program links or one screenshot looks plausible.

**Mandatory falsifier G06:** hold scene, song instant, 3D rays, Light/End path, FOV and ray Range fixed. Capture from four eye poses (below sun facing upward, same eye looking downward, near the surface looking down, oblique/cross-axis) and project Ray Source/End and any occluding bubble to the actual rendered frame. Separate and, if necessary, temporarily isolate march-only and fan-only terms using test-owned diagnostic shader arguments **without introducing a second production lighting path**. Verify that brightness/visibility can vary naturally with scattering angle while the underlying physical shaft region does **not** teleport, vanish unreasonably or flip direction. Report time-coded final HDR pixels and cost. A proper downward render is **unproven** until visually compared at the same world points.

**Queue and validation mapping:** `Current_Plan.md` G00–G33 and `Acceptance_Runbook.md` are the sole execution order and evidence protocol. This section only adds concrete source findings and does **not** replace old investigations or revise any acceptance state. No runtime/shader change was made during this audit.

## 37. Three cumulative log archives and R37 source candidates (2026-10-21; ALL UNACCEPTED)

The user supplied `logs814d70270a.zip`, `logs814d70270a2.zip`, and `logs814d70270a3.zip`. The latter archives extend the earlier logs: the distinct errors in the final cumulative `screensaver_lifecycle.log` are at 01:38:41, 02:48:48, 02:50:37 and 02:55:10 (four distinct Settings barrier failures, not 2+3+4=9). The newest run includes multiple `screensaver_spotify_vis.log` entries `loopback frame: samples=512`; neither pixel brightness nor per-ID physical vs displayed radii are logged, and the user earlier observed ~80% better judder at 256 on Ragdoll. Therefore no faithful quantitative within-song reactivity improvement/worsening can be deduced from these logs. Periodic callback/tick spikes do not prove the cause of continuous body-size judder. Recorded music comparison remains necessary.

Across those four failures the destruction barrier has no surviving Qt objects, tracked resources, work or subscriptions; precisely one `QuickDisplayUnit` and one `QuickDisplayVisualizerOwner` survive; `QuickDisplayPresenter` has retired. This reproduces a Python strong-reference problem at the strict 8s deadline, **not** a demonstrated slow Settings bucket construction. No failure-only `[PYTHON_OWNER_REFS]` attribution appears because the supplied production logs did not enable diagnostic ownership snapshots. Trace true referrers in a diagnostic build on failing barriers, then repair the smallest strong edge. No timeout increase, forced collection, bypass or eager Settings fallback.

R37 source candidate details and acceptance implications:
- Camera `extruded_bubble_scene_scale` now admits 0.2..5.0, not 0.5..2.0; its real camera distance changes, `tan` and projection/FOV remain constant. A surface-bound eye still has its ceiling clip. Extreme proximity increases need for verified near-culling, outside/inside-lens behavior and fused near DoF. No preset JSON was retuned.
- Count-target reduction used to immediately set arbitrary farthest-downstream bubbles `leaving = True` and alpha fall 0.9 seconds even if they were midstream. R37 instead freezes new admission and lets existing stable identities travel to the authored End plane (ordinary bubbles) or existing domain boundary, then start alpha fade; wake state follows the normal retirement path. In a stopped stream, the physical count can stay above the target until flow resumes. Reconcile with the user's desire to show reactivity through speed/drift rather than count deletion. Normal bounds/MAX_BUBBLES remain. Check actual EOL/fade alignment and whether source path changes cause abrupt release; separate this from procedural particle birth-age gaps.
- Surface backdrop `window` previously gated nearly all lighting below upward ray Y=.56. R37 adds a continuous dim baseline (30%) to make the *entire* upward-facing surface region perceptible, while keeping strong highlights local. Test shader visually under multiple angles and presets, with total reflection and haze; current GL appearance is unknown.
- Contact logic only fires after physical overlaps. Pop has a slow 2.4s fade with no explicit conspicuous impulse, Fuse builds multi-sphere cluster, Bounce corrects penetration weakly after contact begins. An operator seeing visible joins but neither pops nor obvious bounces fits this implementation, yet the actual selected action mix is unmeasured. Need native highlighted pair/action diagnostics and no fake screen-space collisions.
- The 1.5px CoC switch is still present for ordinary large and fused near-layer draws. Inside or lens-filling giant bubble behavior has NOT been demonstrated as proper DoF or reliable culling. Camera proximity change increases the test's relevance, not its validity.

**Work ordering:** use `Current_Plan.md` EB-R37 P0..P7. All older failures and acceptance gates remain `[~]`/`[ ]`; do not rewrite the live checklist into a change log or touch authored presets. R37 tests are source-level and do not make visual claims. No EB Lab bulk was added to the Godzip.

## 36. Live Settings tooltip inventory and explicit audit markers (2026-10-21; no behavioral acceptance)

**Source and scope:** Extracted R35 GODZIP. EB Settings uses one declarative spec in `core/settings/visualizer_mode_settings.py`; `ui/tabs/media/spec_mode_builder.py` consumes `control.tooltip` on real widgets and colour swatches, now additionally on EB row/label hover. The closed-bucket lazy builder remains unchanged. No preset, Settings default, audio/DSP/AGC, renderer, camera transformation or admission policy changed.

**Inventory:** 57 visible EB bucket entries; 21 previously had nonempty tooltip strings and 36 had none. All 57 now contain intended-effect descriptions. Exactly 23 display `[NEEDS AUDIT]` after the initial human-readable explanation, to prevent declaring visually rejected or source-disputed controls working merely because they are wired. These markers are permanent *until relevant visual verification*, not permanent judgments. Hidden view-pose configuration entries (no bucket) are not part of the user-visible control inventory. The existing shared two-node editor remains reusable.

**Disputed quiet→loud semantics:** All nine music-driven Ranges are marked: `rays`, `large_bubbles`, `mid_bubbles`, `bead_chains`, `stream_speed`, `drift`, `breathing`, `small_pulse`, `particles`. This flags actual source findings from R33: activity attenuation after interpolation, capped ray driver, population admission/response, sustained/rest-radius coupling and one-band chain saturation. A text change does not change the underlying curve or fulfill the R34 individual repairs.

**Additional flagged controls:** `light_direction`, `light_strength`, `ray_path`, `ray_flicker`, `stream_direction`, `sustained`, `smoothing`, `camera_position`, `clarity`, `rim_glow`, `sparkle`, `particle_glow_reactivity`, `focus`, `aperture`. These represent already-open Deep Light location/brightness parity, ray musical and physical transport, stream alignment and lifetime, temporal smoothing/plateaus, physical camera/native editing, glass highlights, optional glow modulation and near-focus visual fidelity. Do not infer a new cause or new shader capability solely from the tooltip wording.

**Verification:** Qt-free tooltip-model contract covers every visible control, explains first/marker second and checks all nine Ranges. Native bucket-expansion test now explicitly checks each editor/swatch widget AND its row/label tooltip. Qt-free coverage does not verify hover on the operator's Windows version. The narrow native test requires PySide6, no-env fixture and the user's repo-root `.venv`; no environment variables, giant suite or build needed. No operator visual issue was accepted, closed, collapsed or rewritten by this documentation-and-tooltip pass.

## 34. EB oblique camera look direction, light-emitter coherence and physical spread candidates (2026-10-21, all [~])

**Source audit.** Existing Deep Light used a physically authored `light_source` for its visible emitter and glint proxies, but `ray_source` came from a second authored path, with the backdrop/shaft directional term using `sun_below`. Distinct path origins could place glow and shafts on opposing sides without any perspective/FOV error. R34 candidates: a Deep-only light-source→shaft-origin link, keep independent Ray End, derive deep ray direction toward the actual source from `eye`, and reflect linked origin in the oblique UI with a drag feeding the single Light Source owner. There is no hidden shader shadow subsystem and the surface case remains independent. Inspect final pixels for visual alignment; matching uniforms alone cannot prove alignment of bright bloom, fog or exposure.

**Camera ownership.** The three-quarter volume controller's existing camera diamond is the physical eye. Add a small draggable look dot plus paired guide rays; the dot edits the existing renderer `turn`/`tilt`, by calculating direction from physical eye to dragged world point, not lens FOV. `camera_only=False/True` cases share exact geometry. No new camera owner/timer/control class; the original two-node shared `ScenePathMapper` remains. Settings must persist final pose without rewriting curated preset JSON, reload without double-binding, and match renderer/capture pose. The oblique editor is deliberately an orientation aid, not a perspective preview. Angle estimation from a flattened image plane is **not full independent 3D target manipulation**; further depth affordance may be needed after operator evaluation. Pixel/capture parity is mandatory.

**Spread and camera ceiling.** `Columns` configures lane preference, not physical volume breadth. Ordinary bubble Source patches were fixed ±0.55 `WORLD_UNIT` per transverse axis; specks, bead chains and snow use their own distinct physical half widths. New independent 0..4 multipliers, default 1.0, keep initial operator-authored visual balance; no change to attached fizz's parent geometry or stream speed. The camera Y ceiling formerly applied even when there was no surface in Deep Light; render path now gates that ceiling on `light_type == Sunlit Surface`. Surface-bound movement still needs a native no-hidden-accumulation check because the logical free-flight pose and clamped rendered eye are separate computations. A real no-breach policy should gate flight target admission as well if telemetry exposes accumulation.

**Actionable nine-range backlog.** `Current_Plan.md` R34 expands every R33 discrepancy into its own [ ] source-to-pixel task with recorded-music falsifiers. R34 DOES NOT change those nine energy transfer functions, does not close historical issues and does not rewrite the seven authored presets. Small reported improvement in untouched P1 after camera fixes is operator observation only.

**Verification and limits.** New R34 Qt-free tests cover canonical spread defaults, emitted-bubble source geometry with zero and widened spread, distinct surface/deep ceiling, Deep Light logical source parity and shader wiring. Native PySide6 Settings interaction, shader compilation/link/draw on GL4.6, frame times, ray pixel alignment, historical test triage and operator artistic acceptance are pending. The R33 synthetic audit remains [~].

## 33. Nine EB music-linked Range handles: source-to-pixel authority audit (2026-10-21; all [~])

- [~] **All nine declared EB `Range` controls have a musical data path, but their displayed left/right bounds do not share a literal quiet/loud semantics.** Reviewed descriptor → authored persistence → simulation/renderer consumer. `Range.admit` correctly sorts and clamps two values, but it cannot guarantee downstream musical reach. This non-invasive audit adds `tools/visualizer_replay/extruded_bubble_range_energy_audit.py` and `tests/test_extruded_bubble_range_energy_audit.py`; it does not modify DSP, smoothing, engine, shader, UI limits or any operator-authored preset. The exact complete table and sample outputs are in `Current_Plan.md` EB-R33.
- [~] **Count ranges vs chain range:** Large and Small counts use weighted band-breadth occupancy with easing; Bead Chains uses `state.level` from max normalized band and detail-tier factors, so can saturate on very different content. Spawning and GPU quantization delay/distort apparent density. Counts may be correctly *requested* but not visibly realized within a finite recording. No visual acceptance.
- [~] **Nonliteral quiet/loud:** Stream/Drift/Particles interpolate with composite `change_drive`, then multiply/add activity/sustain/flash, so controls are not output bounds. Ray Strength's separate `state.rays` driver is capped at 0.9, and the render-side 3%-to-100% activity multiplier means the left/right values are NOT raw endpoints. Breathing and Small Pulse compute their rest contraction from the **high handle** even at zero drive; this is a distinct, especially actionable mismatch. Their music response remains per-lane and displayed per ID, but maximum Smoothing cannot repair ill-defined low/high semantics.
- [~] **Synthetic settled readout (90 Hz for 10 s, all-band=1.0, no events, handles .20 to .80):** normalized stream .65707, drift .66907, particles .62109, ray output .12657; silence .01320/.01320/.05000/.00600 respectively. Big/small count target reaches 16/48 under all-band full input with authored synthetic count handles 4→16 and 12→48; bead fill resolves 8 from 2→8. No temporal music sections, no HDR/bloom sampling, no actual Ragdoll, and none of these are proof of source quality or operator acceptance.
- [ ] **Follow-ups (not implemented):** clarify whether "quiet" is musical silence or soft playing, ensure low/high endpoints have meaningful reach without flattening expressions, preserve musical lane separation and attack/release, retain 2D Bubble established temporal fidelity, and measure native rendered pixel variation using recorded slow→fast→slow input. Avoid adding another AGC, global floor, timer or per-renderer state. No checklist item closed.

## 32. Framed camera input expansion and recurrent native Settings crash (2026-10-21; all [~])

- [~] **Traceback line-number fingerprint suggests a different source revision, but actual launch provenance is not yet established:** the operator's failing `spec_mode_builder.py:361` corresponds exactly to the previous R30 Godzip; R31 moved that exact label statement to line 363 and gave the volume mapper both `widget.setValue(value)` and `describe=control.text`. Operator subsequently observed unusual Foundry selection behavior; establish the launched source/build fingerprint instead of assuming a particular tree or attributing fault to user deployment. R32 uses unconditional formatter initialization before any control-type branch, and keeps the mode/bucket lazy construction system intact. Test the launch/build with the actual source path and subsequent Qt application entry before accepting it.
- [~] **Native failure mechanism and test truth:** a signal-slot callback that throws during bucket opening can print a traceback while a test continues. A direct `_build_visual_control` constructor test for every EB visual-control descriptor catches `UnboundLocalError` and wrong initial label. A full `VisualizersTab` test expands all sections and verifies each newly built bucket's membership and all control rows, so swallowed Qt callback failures are red. Earlier R31 isolated two-control and source-text checks were insufficient coverage. No change to the destruction barrier or eager-loading policy.
- [~] **Flight semantics:** ordinary WASD physically translates relative to current orientation; Shift+W/S pitches and Shift+A/D yaws, equivalent to Q/E. Q/E remains yaw when EB admitted, never global-exit. Modifier transitions while keys are held reassign the same intent without introducing a new logical step clock or affecting Sphere/Spectrum freeform WASD orbit. Native held-key, release/focus loss, Shift state, settings persistence, and no unwanted FOV/zoom changes still need operator/native validation.
- [ ] **Test recommendation (focused only):** from repo/Godzip root, `py -3.14 -m pytest -q tests/test_extruded_bubble_flight_keyboard_native.py tests/test_extruded_bubble_lazy_bucket_ui.py`; no env variables, slow build or chunked run. If Settings traceback remains old line 361 after the test, determine which source/build the *launched* app actually uses. Keep the Qt-only result distinct from app launch and visual acceptance. All past EB temporal, optical, ray, particle, population and lifecycle failures remain open.

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
`Docs/Reference/Extruded_Bubble/Evidence/2026-10-20/forensics/`; these ignored artifacts are not bundled into source control. Reproduction tooling
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

**2026-10-22 operator comparator refinement (NOT an accepted EB outcome):** specifically compare visually
confirmed 2D Bubble **Dynamic Floor ON** to EB **Dynamic Floor OFF** on the same recording and musical moments.
EB should ideally match or exceed 2D's audible-phrase-linked size response at ordinary controls even without
its own automatic floor. Dynamic Floor may worsen a song's responsiveness once its dynamic tracking engages,
so the target is meaningful musical breathing across changing passages, not imitation of 2D floor excursions or
a claim that an adaptive floor is required. Capture both settings separately with native synchronized pixels,
large/small stable-ID radius histories and actual floor state; retain all existing FAILED reactivity verdicts.

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

Local evidence is under `Docs/Reference/Extruded_Bubble/Evidence/2026-10-20/recovery/` (ignored media/custody; retained on this workstation):

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

Evidence: `Docs/Reference/Extruded_Bubble/Evidence/2026-10-20/recovery/rays_fixed_p1`, `rays_fixed_p7`, `rays_fixed_p7_1440`, plus the real opening
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

`Docs/Reference/Extruded_Bubble/Evidence/2026-10-20/recovery/distortion_audit/` compares unmodified production ordinary/cluster shaders with
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
`Docs/Reference/Extruded_Bubble/Evidence/2026-10-20/recovery/emission_final_p1` contains 16 paired frames over the opening 4 s at 1672×941;
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

## 14. Next geometry boundary: fixed metric, population domain and depth readability

The same single Sol 6.1 Medium reviewer performed a bounded read-only sequencing audit; the primary re-read
the production seams. No new probes or geometry edits were used for this architectural finding.

The present mismatch starts before rendering: `_spawn`, upstream entry, `_outside`, motion and cluster offsets
in `extruded_bubble_simulation.py` operate in normalized view-like coordinates. `_collide` runs before `_snapshot`,
where reacted radius is currently calculated; its fixed .25 cells search only immediate neighbors and use nominal
radii. `_fuse` can move centers directly to nominal touching distance and stores fixed offsets. Thus changing
contact reach alone would neither establish a physical metric nor keep fused surfaces coherent as radii change.
The first correction must move current physical radius resolution before contacts and share the result with
snapshot/render/wake attachment. Nominal radius remains separate where it intentionally controls mass or bead
dimensions. Broadphase must cover the largest admitted reacted extents without missing pairs or unbounded work.

`extruded_bubble_scene.py::_volume_points` constructs a depth-scaled wedge from camera FOV/aspect/tilt;
`_wrapped_turn` then moves it with yaw. `bubble_instances`, `wake_instances` and `cluster_instances` inherit
this placement. GPU free chains/snow independently reconstruct the camera-relative wedge and `wrapTurn` in
`extruded_bubble_program.py`; uniforms come from the renderer's current camera. Correct all these paths to one
fixed domain and world stream convention in the same coherent checkpoint. The existing simulation remains
the population/lifetime owner; a pure mode geometry definition shared with packing/GPU uniforms is sufficient.
No new world manager, camera-following populations, sector copies or silent count multiplier is justified.
Simply removing wraps leaves the old forward wedge and fails all-angle coverage. Distribute the authored
population within a fixed domain, test actual sparse/dense authoring and make the visibility consequences
explicit; sparse settings need not fabricate populated views in every direction.

After the metric is stable, lifetime/projection/near-depth consumers must agree. Ordinary shells currently
shrink by `sqrt(alpha)`; fused packing discards alpha. `_POP_SECONDS=.35` and snapshot pop-only expansion up to
25% of nominal are additional violations to review against extremely gentle opacity-only retirement. Union
opacity needs a coherent surface rule rather than copying the first member. Parent/bead projected-size guards
currently account for shrinking alpha and must follow the corrected physical silhouette. Ordinary/fused rays,
bounds and depth must share a convention; clusters currently draw only into OIT while the shared near pass
draws only ordinary shells. A near union needs one consistent front-depth/layer decision, without split members
or duplicate rendering. These are active depth-readability work, not deferred fidelity polish.

Required falsifiers for implementation: frozen-ID world positions/radii invariant under yaw/tilt/pan/zoom/aspect;
equal physical radii at two depths project differently; a large contracting/expanding contact pair spanning
multiple broadphase cells agrees with rendered surfaces and wake attachment; fused members stay coherent
without center teleportation; retiring wakes keep their exact world anchor during camera motion/compaction;
fixed-seed native full orbit retains continuous world geometry and useful actual-count coverage. Subsequent
opacity and near-layer checks need ordinary/fused entry/pop/exit, center/edge/near-plane silhouettes, shared
focus/aperture response and convincing depth-separated crossings. Compare against the latest copper mock;
screen-space intervention must not conceal these failures. Physical musical-response acceptance remains open
alongside this geometry work.

## 15. Fixed physical world checkpoint and bounded native evidence

The geometry boundary described in §14 is now corrected at its production owners. The pure
`extruded_bubble_geometry.py` definition supplies a camera-independent domain centred at the world origin,
with half extents (18, 8, 18), water plane y=9 and a one-time length calibration of 9. This preserves nominal
scale near the former 15-unit reference distance, not constant screen size at every depth. The existing logical
simulation owns physical positions, radii, travel and lifetime. Authored counts remain global; no sector copies,
camera-following cohorts, hidden multipliers, alternate clock or new scene manager were introduced.

Initial fill occupies the fixed volume. Subsequent sources select real upstream faces weighted by face area
times inward stream component. Column placement uses the canonical transverse world basis and re-intersects
the actual upstream boundary; impossible column admission fails loudly after bounded sampling. Shells, stable
wakes and union members pack physical xyz/radius directly. GPU free chains, snow, attached fizz and glowing
specks share the world stream/domain rather than a camera wedge or azimuth wrap. Their physical sizes do not
depend on view depth, aspect or pixels. Camera rotation observes those identities; zoom changes projection.
Pan is still a lens shift, not a translated camera or independently authored orbit pivot.

An intermediate native capture exposed a remaining radial speck cloud concentrated around the world origin:
fixed physical sizing made its excessive foreground population obvious. Specks now use seeded anchors in the
same fixed box, world advection and an opacity/brightness fade at domain boundaries before wrapping. The cloud
mask follows stable world anchors and the stream basis. Authored glow, particle controls and preset files were
not retuned to conceal the placement defect. Minimum raster footprints remain rendering coverage, not physical
radius or source placement; native art acceptance still needs to assess their visible effect.

Current reacted radius is resolved before movement/contacts, then shared with snapshot and wake attachment.
The broadphase searches extents covered by the largest current diameter, rather than assuming fixed .25 cells
cover expanded bodies. Contact response is chosen once per contact episode with separation hysteresis. Union
admission preserves exact centres and a connected edge layout; existing smoothed radii drive connected offsets
around a nominal-mass centre. Third-member addition/removal keeps the graph coherent; removing its bridge only
reconnects the two survivors if they physically touch. Bounce separates gradually with a dt-bound and moves an
existing union as a group. These are mechanism proofs; dense-motion jitter/cost still require observation.

Lifetime now travels as material opacity: ordinary instances carry 7 floats and unions 19, including three
member opacities blended by surface weights. Pops use a 2.4 s smoothstep opacity retirement, retain the starting
opacity without brightening and add no pop-only radius expansion. Musical radius remains independent. Ordinary
and union fragments use the same pinhole rays and conservative physical bounds, including near-plane crossings
and an eye inside a body. Near/inside shading traces the forward exit surface; the shared hollow-shell tracer
starts in the actual outside/wall/core medium. Near unions use the existing DefocusLayer once, with the same
front-depth admission as ordinary shells. The near circle now responds to aperture and uses surface depth in
its denominator; the prepared/composite budget is resolution-based so camera gestures do not reallocate it.
Off-axis physical spheres can project as ellipses: consistency with pinhole geometry does not approve objectionable
artistic distortion or establish foreground softness.

**116 focused checks pass against this source.** They cover physical face/column admission, steep-stream basis,
reacted broadphase reach, contracted noncontacts, exact union admission, connected contraction and third-member
removal, gradual repeated bounce, opacity-only pops, immutable world uploads under camera gestures, procedural
position/radius invariance, and removal of the origin-biased speck halo. Native GL guards exercise ordinary/union
centre/edge silhouettes, near-plane and inside starts, finite reflected/transmitted output, per-member alpha,
exclusive normal/near routing and actual aperture consumption. Prepared yaw/tilt/zoom renders compile and allocate
nothing. Shared optics exterior regressions and analytic core/wall Fresnel starts are included. The migrated lab
also completed an ExBubble6Diagonal smoke render at 836×470; its authored placements and 23,721 instances are not
production population, performance or fidelity acceptance. The same single Sol 6.1 Medium read-only reviewer
checked the boundary and the final speck change; no additional agents were used.

Final-source native artifacts (ignored local evidence, with source/clip/settings receipts):

- `Docs/Reference/Extruded_Bubble/Evidence/2026-10-20/recovery/world_final_p7`: 15 frozen real-recorded-snapshot views at 1672×941,
  unmodified P7, 54 global bubble identities; ordinary yaw-view frustum candidates range 4–22.
- `Docs/Reference/Extruded_Bubble/Evidence/2026-10-20/recovery/world_final_p1_1440`: 15 equivalent views at 2560×1440, unmodified P1,
  56 global identities; ordinary yaw-view candidates range 2–9. Both include twelve yaw angles, two tilt views
  and a zoom/pan view. No simulation advance occurs between views. Candidate counts are conservative ordinary
  frustum estimates, not segmented pixels or procedural/union counts. The primary inspected both contact sheets.
- `Docs/Reference/Extruded_Bubble/Evidence/2026-10-20/recovery/world_final_operator_ranges`: 10 paired frames at 2560×1440 from
  `anything_mixed2`, 227 selected logical inputs over approximately 1.5–4 s. P7 is activated with selected retained
  controls in memory: Large [0,4], Small [20,50], Particles [.85,1], Bead Chains [2,4], Ray Softness .81. This is
  not an exact live-operator configuration reproduction. All logical records, including retirement, stay within
  Large 0–4 and Small 24–45. This short cold-start interval has **zero mature, fully-forward ordinary large
  frustum records**, so it cannot validate visible large-class response. A projected large-looking shape must
  not be classified as a large owner. The primary inspected the contact sheet; excessive point detail remains.

The frozen native views prove a real surrounding population and reveal legitimately sparse directions; they do
not justify repopulating views around the camera. P7 still lacks the target's restrained glow, convincing glass
depth, differentiated debris/gas/wisps and foreground/background hierarchy. P1 remains visibly far from target
parity too. Source-correct physical geometry is a foundation, not appearance acceptance. The operator subsequently
judged the result significantly better while explicitly retaining the remaining fidelity/reactivity work.

Evidence qualification matters. `world_first_p7` failed metadata serialization and is rejected as a verified run.
`world_verified_*`, `world_response_p1` and `world_response_p7_1440` belong to earlier producer hashes before the
last speck correction; retain them for their scoped geometry/reaction evidence, not final-source art acceptance.
The old first-order projected-radius observer generated meaningless eye-plane extrema: reject those values.
It now labels projection regimes and limits mature radius aggregates to fully-forward ordinary frustum candidates;
the archived `projection_validated.json` qualifies the older P1 custody without rewriting it. First-order radius
estimates still do not measure glass/DoF silhouettes. Captures contain recorded post-DSP features; silent GIFs
do not supply verified synchronized sound. Cold compile/readback/query timings are not cadence or performance
benchmarks, and offscreen native output is not operator/display acceptance.

Cost boundary: camera remapping/trigonometric population reconstruction is removed. Fixed shell/union capacities
gain 1,920 bytes total for lifetime attributes; a lazy near-union program/pass remains with the existing resource
and DefocusLayer owners. No permanent diagnostics, new timer, DSP/floor changes or authored preset mutations were
added. Contact work remains bounded by the existing 192-body ceiling, but that bound is not a measured speedup.

Remaining actionable work stays in Current_Plan: water-plane source clearance and gentle breach retirement
(the current exit waits for the whole sphere to pass); translated camera/pivot and authored source regions;
dead `near_bubbles` transport cleanup; same-ID big/small native silhouettes on the same sound as 2D, including
idle/onset/sustain/release and sparse-range visibility; depth/material/near softness and restrained glow;
fire/smoke/fog/debris architecture and centralized preset/mock provenance; only then a justified persistent
unreadable-crossing policy, with Auto Rotate later. Keep physical musical, lifecycle and operator gates open.

### 15.1 Follow-up audit and obsolete-path retirement

A read-only follow-up by the same reviewer found no live camera-dependent population constructor. It identified
two dead remnants: the always-empty `near_bubbles` snapshot/frame/capture transport and an unreachable kind-2
defocused flat-speck branch (production emits ordinary 0, snow 1 and micro-glass 3). Both are removed rather
than preserved as alternate schemas or shaders. Redundant empty-field assertions are removed; physical world
upload/procedural and count/lifetime checks remain the real falsifiers. Initial focused execution caught the
obsolete positional empty tuple in the snapshot constructor; it was removed before rerunning the gate.
The resulting focused immutable-frame, recorded-response, motion, shader and native world-GL gate is **26 passed**.

Free chains still use fixed finite seeded world segments with opacity at their ends; oblique segment endpoints
can be interior emitters. This is not camera spawning, but it is not proof of actual upstream-boundary source
authoring for every family. Source/region unification remains active work. Raster coverage floors and defocus
can also limit apparent pixel contraction below resolution; record those alongside physical reaction measurements.

The operator identified `Docs/Reference/Extruded_Bubble/Lab/2026-10-18/presets_sheet.png` as valuable target evidence. The primary inspected it:
mock/product pairs show a substantial remaining gap in depth hierarchy, dense fine bubble streams, near softness,
coherent light and the diagonal scene's glowing particulate/wisps. Preserve the full `Docs/Reference/Extruded_Bubble/Lab/2026-10-18` provenance,
especially `scenes.json`, `scenes.py`, lab/scenes/presets outputs and comparison/pair PNGs, alongside original
`Docs/Reference/Extruded_Bubble/Targets/Originals` assets in the later canonical target organization. Specks remain an important target element;
neither removal nor disabling is a substitute for correct placement, glow, depth and reachability.

## 16. Clean-body phrase correction and fresh matched comparison

**Pending, uncommitted response attempt; latest operator feedback rejects its native appearance and requires
further passage-role work before landing.** This is bounded source/native evidence, **not 2D response parity or visual acceptance**. The fixed
world made response measurement more truthful but did not fix the remaining transfer. Fresh paired replay
reproduced the first-window large deficit: mature EB identities had median minima/maxima 0.975–2.086× nominal
against accepted 2D's 0.707–2.750× (individual 2D ID 1 reaches 2.782×). A later active 4–8 s window exposed a
different small-body weakness: EB only spanned approximately 0.287–1.036×, despite impressive percentages when
the recording's initial tiny rest was included. This is why opening-rest excursion alone cannot close the gate.

The primary and the same single read-only reviewer identified the owning mechanisms:

- Large body used `max(bass, .28*mid+.10*high)`, discarding vocal changes whenever bass won, then attenuated the
  continuous term by .75. Unlike the small lane, it had no clean-body change reference.
- Size was partly restored using kick→breath→kick-swell→body followers and a snare pulse in the small lane.
  These discrete event tails could hold bodies inflated between attacks; accepted 2D's size authority uses
  continuous body plus its clean delta, reserving transient event excitement for motion.
- At default smoothing the active release was 250 ms but abruptly became 1.875 s below intensity .01, including
  quiet gaps inside playing music. The hard switch created a discontinuity without establishing musical minima.

The EB-local correction retains its own simulation/Settings/clock and the existing recorded/live body feed.
Large support is bass plus limited vocal energy, with a slow clean-body reference and positive change authority.
Small support is vocal/high energy plus a modest .25 bass contribution; stronger changing-body authority restores
active phrase peaks while keeping the former restrained held support. Both additive mixtures are bounded before
delta extraction. Large/small change gains are 3/5; final authored strength/rest/expansion mapping is unchanged.
The first candidate removed events but retained insufficient small active span; its receipt is
`matched_phrase_candidate`. The subsequent actual small-body contribution/change correction is the current source.
No periodic pulse, preset retune or final-radius workaround was added.

The two obsolete event-size followers are removed. Events still drive existing flash/light/motion. The remaining
`breath` kick follower is diagnostic transport only, not a size or actual event-motion authority; its retirement
and tool migration are a bounded cleanup task in Current_Plan. Population/motion intensity is algebraically the
same normalized driver as before, so this correction does not redefine count Range interpolation. Active body
attack is still 75 ms at default smoothing; active release is now 125 ms and blends continuously toward the
1.875 s very-quiet/paused release below intensity .1. Near-silence remains gentle; the change does not mean rapidly
collapsing an idle scene. Sustained Response still supports actual held body and motion.

`bubble_response_comparison` records both modes at identical source timestamps through production capture,
including actual 2D clean pulse payload and actual EB body tuples, settings/preset paths, source hashes and
stable-ID final-radius/nominal ratios. It excludes promoted 2D bodies and fused/popping/leaving EB records.
Window identities must be mature on at least 80% of the selected input samples. Each identity's own extrema
are aggregated by class: their times can differ across identities/modes. These are windowed distributions,
not identical geometry, synchronized pixel extrema or auditory timing. Empty classes remain explicit coverage gaps.

Current `anything_mixed2` results, unmodified authored P1 in each mode (median per-ID minimum → maximum):

| Source window | Class | Accepted 2D | EB before this correction | EB clean-body candidate |
| --- | --- | ---: | ---: | ---: |
| 1.507184–3.146924 s | Large | 0.707 → 2.750 | 0.975 → 2.086 | 1.223 → 3.258 |
| 1.507184–3.146924 s | Small | 1.738 → 3.948 | 0.623 → 2.585 | 1.390 → 3.385 |
| 4–8 s | Large | 0.792 → 2.294 | 0.697 → 2.338 | 0.392 → 2.864 |
| 4–8 s | Small | 1.608 → 3.879 | 0.287 → 1.036 | 0.284 → 2.353 |

The first window now has larger large-body peaks but **still has an elevated minimum and lower relative
excursion than 2D** (median 166% versus 294%). Do not declare parity from the roughly similar absolute span.
Both minimum observations occur at the window's first sample, so this is not proof of a remaining hard size floor.
At identical source times, 2D ID 1 / EB ID 1 ratios are 0.707/1.223 at 1.507184 s, 2.457/2.591 at 1.8046 s,
2.741/2.932 at 2.0022 s, 2.261/1.904 at 2.4971 s and 2.003/1.615 at 3.146924 s. EB ID 1 is a mature
logical large identity but behind the current camera, so these are transfer/timing observations, not its visible
silhouette. Distinguish earlier onset growth from an inflated valley before making another response change.
The 4–8 s small span is substantially restored; its lower nominal ratios are not themselves proof of the same
visible size. 2D eligibility there is only one large/three small IDs versus five/twenty in EB, and no 2D large
identity meets the 80% rule across 8–12 s. This is insufficient coverage for a blanket cross-song or full-population
claim. Current EB first-window eligibility is three large/seventeen small; the comparator has three/fourteen.

Evidence under `Docs/Reference/Extruded_Bubble/Evidence/2026-10-20/recovery/`:

- `matched_phrase_before` owns the pre-change paired distributions. `matched_body_final` owns the current
  paired twelve-second result and actual two-seam input custody. `matched_body_soft` and `matched_body_ragdoll`
  extend it to the soft recording and Ragdoll's full minute with explicit opening/50–54/54–58 s windows.
  All three current actual-body comparisons have **zero mismatching tuples**. `matched_body_heavy` supplies the
  heavy opening comparison from the earlier observer version (recorded inputs, before the independent actual-2D
  payload observation was added). Preserve that qualification. Ragdoll's late windows have no eligible 2D IDs;
  they do not establish late-section cross-mode parity.
- `held_bands_clean_body_qualified.json` holds an actual hot vocal tuple for 13.2 s with new events/transients
  cleared. Mature ordinary large/small ratios settle to **1.204 / 1.523×**. A progress update estimated the small
  value as 1.43×; the exact custody supersedes that approximation. The projected observer now excludes near-plane
  and off-frustum cases; earlier positive-depth-only extrema are not valid visible field measurements. Held
  support remains restrained, but a hold does not test how long changing vocals stay near the soft knee.
- `clean_body_native_p1`: **360 paired native frames at 30 fps**, opening 12 s at 1672×941, 1,091 actual inputs,
  unmodified P1, source/clip/settings receipts and same-frame zero-swell images.
- `clean_body_native_p7_1440`: **120 paired native frames at 30 fps**, opening 4 s at 2560×1440, 364 inputs,
  unmodified P7 with equivalent receipts/interventions.
- `clean_body_2d_reference`: fresh **360 native accepted-2D frames at 30 fps** over the same opening 12 s.
  The primary inspected all three contact sheets and sampled full frames. The EB response reaches actual shells;
  P7 still shows excessive bright speck detail, large foreground forms and bright interiors with weak depth
  hierarchy. The latter failures remain art/source/optics tasks, not reasons to suppress specks or size response.
  `frame_0090.png` also exposes regular dot/lattice patches near P7's upper-right light; identify the responsible
  procedural family/source before changing density. This new visible side-defect is retained in Current_Plan.

**61 focused checks pass**: event-present/absent identical-band radius equality while event light/shimmer differ;
vocal changes under held bass; continuous release around the former .01 threshold; gentle silence/pause;
absolute SAME-ID span strictly within the active 4–8 s passage; held hot-small restraint, tiny rest, controls,
source/activation/onset fencing, motion and reacted-world contacts. The old event-size expectation was replaced
with a clean-body onset case because that behavior is intentionally removed; its red was not hidden. This gate
protects absolute active excursion, not the remaining first-window minimum/relative-excursion failure. Native
30-fps replay samples logical states; it does not measure installed display judder, onset-to-audible latency or
physical cadence. GIFs remain silent. The two later native processes overlapped, so their timings are especially
unsuitable as controlled performance benchmarks.

Cost/ownership: one constant-size clean reference replaces two event-size followers; no extra band read, DSP,
floor, timer, per-body observer, resource or renderer simulation. Existing world/contact/radius ownership remains.
Before broadening fidelity work, inspect same-time target/reference/envelope/radius and native ordinary silhouettes
around the unresolved first-window minimum and release. Challenge mixture clipping and long near-maximum small
passages rather than selecting only peak frames. Complete physical quiet/onset/sustain/pause/resume and count/density
acceptance at normal controls; retain all world/camera/source, water-plane, material, speck/debris/fog and target
organization work from Current_Plan. This checkpoint does not retire any of those requirements.

## 17. Latest operator rejection, passage roles and central organization

The operator rejected the latest two native screenshots as awful and supplied the original diagonal target and
the blue/copper annotated mocks again. These are byte-identical to the originals now in `Targets/Originals`;
`asset_manifest.json` records attachment hashes and canonical paths. Their broad curved highlights, front/back
wall structure, background distortion, spherical volume, soft depth hierarchy and natural microbubble trails
remain the visual requirements. Physical pinhole projection alone does not meet them.

The clarified response role is precise: **large bubbles breathe significantly, especially downward, in softer
music; they carry sustained body in sustained/loud passages.** Small bubbles and emission/drift/speed/rays must
keep expressing changes within loud passages. Do not produce a shared bass/transient-held small field or a
generic large-bubble hold at every energy. Controls/presets may be changed where needed to remain valuable;
do not protect ineffective tuning or require users to compensate for broken transfers.

The primary checked accepted 2D's exact current source. It does not feed transient/event excitement directly
into ordinary size. It keeps a bass running average and a separate mid/high average; ordinary smalls use vocal
body plus bounded hot-field/bass/body support, clean positive delta, perceptual sustained knees and separate
attack/release. Thus the implementation is not literally bass-free. Promoted smalls temporarily use the big
lane with scaled-down authority; the paired tool excludes those when comparing ordinary smalls. The design
lesson is distinct passage/change authority and bounded support, not one common loudness hold. EB's pending
direct .25 bass addition, .50 held-small term, stronger delta and shared level consumers require re-evaluation
against the clarified role. Its 61 passing checks and §16 numeric spans do not close that requirement.

One user-authorized Astra High reviewer inspected the targets and native evidence. Full findings and owning
source locations are in [Visual_Audit_2026-10-20.md](Visual_Audit_2026-10-20.md). The strongest lead is the P7
regular dot lattice: actual bright pixels align to the exact 8-pixel near-defocus highlight sampling grid, rather
than proving a flat particle source. Other concrete discrepancies are opposing background/light lens conventions,
background capture before rear bubbles/trails, tangent-sphere union optics, analytic specular ignoring Light
Strength and plausible shared-proxy interior blobs. Perform bounded native interventions with specks retained.

Organization is now implemented, not deferred. This folder contains the 9 original/annotated targets, all 85
historical lab files (including `presets_sheet.png` and both scene recipes), the target contract, this investigation,
the visual audit and both complete native evidence trees: 1,029 forensic files and 8,009 recovery files. The former
two log roots refused a directory rename on Windows despite access rights; moving their children within the same
volume succeeded and the former roots were removed. No evidence was deleted or overwritten. Target/lab SHA-256
values were checked before/after; evidence file counts/byte totals were checked across the move. Original capture
receipts retain their historic path strings and producer hashes. Live document/tool routes now use this canonical
home. The large raw evidence archive remains ignored locally beside the versioned images/documents.

The live plan retains passage-role rework and all world/source/camera, near-defocus/material, depth, important
specks, gas/debris/fog and preset-parity work. Use the registry here; do not scatter another set of investigation
or target images into temporary/log directories.

## 18. Passage-role source candidate after the clarification

This supersedes the **response mechanism**, not the rejected visual result, in §16. Large size uses bass plus
limited vocal support and a clean change reference. Its steady support is `.25 + .75*sustain`, where sustain
develops in a loud passage and is scaled by Sustained Response. Softer passages retain strong change-driven
growth and deep downward breathing, rather than a generic large-body hold. Spectral mixtures use the existing
soft top instead of a hard unit ceiling.

Small size removes the pending candidate's direct .25 bass addition and .50 held-body term. It uses vocal/high
body, a separate reference that resets after falls, restrained .18 steady support and strong positive-change
authority. Sustained Response increases responsiveness to changes within loud passages; it does not add a held
small-size floor. Discrete onsets remain with event light/motion. The unused kick `breath` follower, immutable
field and capture/replay/plot consumers are removed. Onset serial/fence checks observe the actual `flash` consumer.

Maximum passage level remains the count driver. Flow/emission/light instead derive a changing driver from
occupancy, the existing small-body envelope and event flash, retaining headroom under held bass. No new band
read, DSP, clock or follower owner is introduced. Stream acceleration stays gentle; active release follows
passage changes while speed/drift/emission/rays blend into their long quiet release. Movement stays integrated.
The Sustained Response tooltip now describes large loud-passage support and change responsiveness. Authored
preset files are unchanged; meaningful endpoint/preset revisions remain authorized when evidence calls for them.

**99 focused checks pass**, including native renderer/shader checks. New falsifiers cover soft large downward
breathing with no loud sustain acquired; large sustained support without held-small inflation; and changing
vocals beneath fixed .9 bass driving small size, speed, drift, emission and rays while maximum level stays
unchanged, with no onset events supplied. Existing slow idle/pause, tiny minima, controls, active SAME-ID span,
source/activation fences, physical contacts and prepared renderer checks remain green. An initially faster speed
attack violated the retained per-frame smoothness bound and was repaired without weakening that bar. Migration
also caught the replay metric's obsolete `breath` read.
The forensic observer now saves exact producer source beside its hashes (including shared defocus), avoiding
loss of rejected uncommitted implementations. Both new native cases also retain the exact 11 originally hashed
producer files, verified against their capture receipts before archival; that is a source-custody improvement,
not a regenerated or silently relabelled capture.

Evidence in `Evidence/2026-10-20/recovery/`:

- `passage_roles_final`: identical recorded inputs over 12 s; **zero actual body-tuple mismatches**. Median per-ID
  4–8 s large extrema are **.349–2.774×**, small **.294–2.277×**. First-window large extrema remain
  **1.088–3.192×** versus 2D **.707–2.750×**; smalls span **.709–3.336×**. Eligibility/timing caveats from §16
  still apply. Do not infer acceptance from tiny-rest percentages or ignore the first-window timing question.
- `passage_roles_native_p1`: **240 paired frames at 30 fps**, 728 recorded inputs over 8 s at 1672×941.
- `passage_roles_native_p7_1440`: **48 paired frames at 12 fps**, 364 inputs over 4 s at 2560×1440. Both retain
  authored preset activation, source/clip/settings receipts and same-frame zero-swell controls. The primary
  inspected both contact sheets: strong response reaches shells, but white/busy interiors, flat-looking depth,
  near forms and glowing point detail remain unacceptable against the targets. P7's sampling cannot establish
  temporal smoothness. Captures overlapped; their readback timings are not product benchmarks. GIFs are silent.

A bounded DefocusLayer intervention was attempted. Exact baseline pixels differed; follow-up found only 1-LSB
noise and an ineffective threshold change in the newly frozen scene. Cached reuse was initially suspected, but
current renderer source does not establish a skipped draw. Pass execution and actual small-circle content were
not observed, and this is not the old failed producer's exact scene. The result does **not** confirm or falsify
the highlight-grid lead. Retain `defocus_highlight_ab*` as unsuccessful intervention evidence; establish the
conditions with explicit pass observation and a meaningful primitive test. No particle suppression or product
defocus correction is claimed here.

This is a role/consumer correction with scoped proof, not physical reactivity or visual acceptance. Next isolate
the near-defocus lattice with important specks retained, then the exact optics/light/probe defects from the
visual audit. Preserve soft/held large separation and small change response in all subsequent comparisons.

## 19. Latest live rejection — overshoot, judder and near-field pixels

The operator reports that reactivity remains poor with new, specific failures: large bubbles overinflate on start
or preset swap, then get yanked down; large and small bubbles judder/vibrate and appear to sit between states;
approaching bubbles do not always receive proper DoF and can become pixel-like. This is authoritative live
failure, overriding any implication of acceptance from §18's 99 checks or amplitude statistics. Proper close
defocus is preferred; if a form is too close to represent, coherent occlusion is allowed rather than malformed
pixels. Separately active speck glow is estimated approximately **50% too strong**. That is a visual estimate,
not a measured linear-light gain. Spherical/rounded glass and readable depth when bubbles overlap are more
pressing than reducing speck glow. Preserve the important speck population.

Investigation order: establish latest log/producer/settings provenance; separate hot activation/preset swap from
quiet→onset; trace body-reference/sustain/radius initialization and subsequent release. Zero-seeded positive
change references are a concrete startup-overshoot hypothesis, not yet causal proof. Then compare stable-ID
body target/current radius and native cadence against accepted 2D's historical judder repairs, final displayed
radius smoothing and gate release. Distinguish simulation chatter from source/draw timing and from the near
layer changing as size varies. Strong soft breathing must remain, especially downward; sustained loud large
support must not replace it. Do not repair this with weaker reactivity or a second clock/presentation simulation.

A meaningful native primitive falsifier is now red in `test_scene3d_defocus`: a uniform bright strip with 2px
circles under a 54px maximum budget becomes separated 8px-grid discs. Its middle profile alternates zero light
with peaks approximately 64.5/84.4; relative standard deviation is **1.018** instead of a continuous strip's
required <.03. This independently proves an unresolved-small-circle sampling defect in the shared primitive,
including lost continuity; it does not alone attribute every pixel in the failed P7 scene. A proper correction
must capture small circles and retain their energy, while preserving resolved large bokeh and resource ownership.
Merely diverting small highlights into the old wide sparse gather can lose their light, so that is not a repair.

Every one of these failures and its required falsifiers is now actionable in Current_Plan. Keep all new captures,
logs summaries and investigation artifacts under this canonical folder. The existing numerical/physical-world
mechanism proofs remain scoped facts, not acceptance of the latest live behavior.


## 20. Godzip `54cac99a6a` independent follow-up: startup reference overshoot (2026-10-20)

**Scope:** source inspection and synthetic logical execution against the **supplied Godzip**; no EB Lab, recorded
clip, Windows native scene, graphics driver or actual visual acceptance. No production source or authored presets
were changed. Reproducer: `py -3.14 tools/visualizer_replay/extruded_bubble_startup_probe.py` (optional `--json`).
A deliberately red, opt-in fail gate is available with `--gate`; it is **not** a passing test on this baseline.

**Source ownership and causal mechanism are now stronger than an untested guess:**

1. `ExtrudedBubbleFrameRuntime.advance` resets the simulation when the activation/source identity changes and
   advances the first frame with `dt=0`. Simulation `reset` sets both body-change references to zero.
2. `ExtrudedBubbleSimulation.advance` follows these references on 0.45/0.55-second attack times. Its targets add
   `3.0 * positive_big_delta` and `(6.0+2.0*sustain) * positive_small_delta` to held body support, then `_soft_top`.
   The body envelopes attack in 0.06×soft seconds but the positive delta takes much longer to disappear. Thus an
   **unchanged sustained band** can briefly look like an onset, grow excessively, then contract while sound stays
   unchanged. A frame-rate-correct pure simulation reproduces this without any shader or DoF.
3. Crucially, `BeatEngine._get_play_ramp_factor` (`beat_engine.py`) applies an **existing one-second quadratic
   playback ramp**; the full-dynamic Bubble feed multiplies band outputs by that factor. A controlled one-second
   quadratic input ramp creates the same logical bulge even if both references were primed to the first sample.
   Consequently **simply seeding references at activation does not repair the actual playback-ramp case**.

Controlled 60-Hz, 5-second simulation with 0.7/0.5/0.3 held bands, the actual mutable P1/P7 Settings values as
supplied in this Godzip, a first capture at `dt=0`, and no preset modifications:

| Controlled input and counterfactual | Large peak / final radius ÷ nominal | Small peak / final radius ÷ nominal |
| --- | --- | --- |
| Already hot at activation, existing code | 3.365 / 1.254 (**2.68×** peak-to-final) | 3.373 / 0.256 |
| Already hot, references *manually seeded for probe only* | 1.253 / 1.253 | 0.251 / 0.251 |
| Quadratic one-second band ramp, existing code | 3.373 / 1.243 (**2.71×**) | 3.381 / 0.263 |
| Quadratic ramp, references seeded at first zero sample | 3.373 / 1.243 (**2.71×**) | 3.381 / 0.263 |
| Real quiet (one second) → step to same held input | 3.365 / 1.242 | 3.373 / 0.270 |

These P1/P7 logical radius ratios match because those presets currently author the same Breathing, Small Pulse,
Sustained Response and Smoothing values. They **do not** establish same projection/glass appearance, nor assert
that the user's actual bands have these amplitudes. The separate quiet→hot case deliberately remains distinct:
true musical changes must retain strong visible upward and especially downward response; indiscriminately
removing positive deltas would suppress useful musical response.

**Next discriminating native capture**, before touching the musical transfer: compare (a) swapping presets during
already-playing audio with no new engine ramp, (b) resuming music with the actual 1-second engine ramp, and
(c) a genuine quiet→onset after established playback. Capture per logical frame: generation/activation/source
IDs, playback ramp factor, actual already-shaped Bubble bands, big/small references, positive deltas, envelope
target/current, sustain, first and last SAME-ID radius/alpha and shader/near-pass branch. Align logical ticks
with product presentation and the existing 2D Bubble's very same sound section. Then decide whether to handle
activation readiness/ramp semantics at the existing data/size owner, not with a timer, clamp, reduced global
reactivity or renderer-side smoothing. The probe's strong output is **source-derived mechanism proof** only;
operator-rejected live overshoot and size judder remain `[~]` and completely unaccepted.

**Independent near-defocus caution:** `DefocusLayer._CIRCLE_BANDS` in this snapshot gives a 2px CoC a
`fineShare` of 1.0 and a `spriteShare` of 0 under a 54px budget at mip level 3. Thus the 2px uniform-strip
regression **should not** be explained *solely* as 8px-spaced highlight sprites in the current source: the
full-resolution 32-tap fine gather handles that case. The reported red native uniform-strip test is important,
but the exact pass/output needs direct GPU instrumentation before blaming the sprite split or making another
speculative threshold-only fix. For larger CoCs the sprite/grid lead remains viable; preserve both observations.
Check pass outputs and actual circles/sprite shares at the failed pixels, verify a continuous strip survives the
layer and clip passes, and then restore energy with a measured, separately benchmarked correction. Missing
OpenGL/PySide6 here precludes this native A/B; no GPU validation is claimed.

**Independent static material finding:** in `_glass`, `uSpecColour = light_rgb * 300` bypasses `light_strength`,
while `scene_knobs` applies strength to background/glints (`light_power` and `glint_power`). P7 authors
`light_strength=0.12` against P1's `1.0`; the unscaled analytic spec term therefore occupies a much larger share
of P7's illumination than the other light consumers. This is a **confirmed control-consumer inconsistency**,
not causal proof for all bright interior blobs or excess glow. Use an isolated Light Strength sweep with fixed
shell/scene/probe before making a uniform multiplier change. Spherical glass and overlap remain prioritized.

**Packaging custody:** input Godzip's `.godzip/manifest.json` listed 85 historical
`Docs/Reference/Extruded_Bubble/Lab/2026-10-18/` members not present in its physical ZIP (approximately 96 MB
uncompressed). The outgoing full Godzip retains the intentional lab omission and regenerates its manifest from
**actually included members**, leaving `omission_means_delete=false`. The local canonical EB Lab collection
and the 11.6 GB evidence archive are not re-created, overwritten or declared deleted.


## 21. Camera projection, judder branches and other-lane attribution (2026-10-20; source-level only)

**Latest operator requirement:** EB orbiting left/right visibly stretches spheres into unwanted oblongs.
The camera must look honest and natural; eliminating visible orbit distortion is the **highest visual priority
immediately after restoring musical response**. All rejected items remain live in `Current_Plan.md` §4B;
no operator/agent pixel acceptance or source-level production repair is claimed by this section.

### 21.1 Intentional projection choices versus an actual postprocess lens warp

`rendering/gl_programs/extruded_bubble_scene.py`: `FOV_Y_DEGREES = 62.0`, `camera()` supplies a
rectilinear perspective/pinhole matrix and `lens_shift()` supplies a two-axis off-centre projection for
Scene Pan. `extruded_bubble_program.py` uses the corresponding `ndc - uLensShift` ray for backdrop,
ordinary shells and cluster silhouettes, with a shared perspective matrix for projection/depth.
The common `scene3d_spheres.py` documentation itself says the rectilinear camera makes spheres at
large off-axis angles oval. The current path contains **no separate barrel/fisheye lens-distortion pass**;
the existing off-axis frustum and field of view are deliberately coded choices, not requirements of
spherical geometry. Refraction *inside* bubble glass is a separate optical mechanism and must be audited
independently of the camera's outer silhouettes.

An import-free tangent-cone/pinhole reproduction at 1600×900, using a physically spherical radius-0.4
object ten world units from the eye and the production 62° vertical FOV, gives outer-outline pixel
width/height ratios:

| Sphere direction off the optical axis | Projected silhouette width ÷ height |
| --- | ---: |
| 0° | 1.0000 |
| 15° | 1.0353 |
| 30° | 1.1550 |
| 40° | 1.3061 |

A side orbit pushes previously centred world spheres toward off-axis positions. This mechanism alone
can produce **~31% horizontal stretch at 40°**, with no malformed sphere or special barrel shader.
Those are mathematical projected-silhouette bounds, **not measured frames**; location, optical materials,
pan, depth and clips determine the actual artifact on the user's display.

**Do not fix by merely deleting “lens distortion”:** there is no isolated camera-distortion toggle to
remove. Prefer a controlled narrower-FOV real-camera move/dolly-back and independently authored camera
pivot/translation versus the existing wide-FOV lens shift. Maintain the actual framed 3D scene, depth
parallax and real world/identity, and match composition before judging. An orthographic shortcut would
lose natural size-with-depth, while a custom nonrectilinear ray projection would burden all depth, shell,
cluster and near optics. Compare centre/edge/orbit and world-contact renderings at both native resolutions.
Operator/agent visual judgment decides whether proposed optics are genuinely natural, not a mathematical
ratio alone. Current camera implementation and material appearance **remain visually rejected**.

### 21.2 A hard 1.5px branch in near-focus appearance

`BUBBLE_VERTEX` performs `near_ = aExtra.y < 0.5 && sceneNearCircle(frontDepth, uFocus,
uAperture, uNearCoc) > 1.5`; `CLUSTER_VERTEX` uses the same **strict >1.5** gate. One pass
accepts a sphere, the other excludes it: near and ordinary optical composition are not continuously
cross-faded, and there is no hysteresis. When actual breathing moves the sphere's front face back and
forth across that threshold, one physical bubble can change appearance mode on consecutive frames even
with perfectly continuous physical radius. This must be distinguished from producer-target chatter,
discrete projected pixel-size changes, Qt scheduling and the separate unresolved defocus lattice.

Controlled counterexample from the existing user-mutable P1/P7 focus/aperture values at a 941px-tall card,
scale 1 and constant physical centre distance (test-only choice close to each focus threshold):

| Preset | Focus / aperture | Critical front depth for CoC 1.5px | CoC at 0.98 / 1.00 / 1.02 radius |
| --- | --- | --- | --- |
| P1 | 4.000 / 1.380 | 3.4836 | 1.4337 / 1.5000 / 1.5671px |
| P7 | 3.400 / 1.488 | 2.9891 | 1.4175 / 1.5000 / 1.5836px |

These cases demonstrate **branch fragility at small ±2% radius changes**, not recurring passage
oscillation on the real scene, nor proof of the exact source of the operator's live vibration. The
strict equality rows are on the floating-point boundary; the unequivocal .98 and 1.02 states are
ordinary and defocus respectively. `ExtrudedBubbleSimulation.advance` calculates a single big/small
size envelope, then assigns `b.current_radius = b.radius * scale` to each ID at each logical tick;
that owner does not separately filter individual displayed silhouettes. It also doesn't prove that
those envelopes actually alternate in the supplied real recording.

**Next falsifier:** sample the *same* stable IDs and matched sound, retaining their logical timestamp,
true base/radius/XYZ, body reference/target/envelope, projection depth, CoC, near/pass flag and the
actual composited bounding mask and frame-present cadence. Correlate 1–2px reversals with
(a) true world-radius target changes, (b) the >1.5px branch or budget/mip change, (c) Qt scheduling,
and (d) time-varying glass/glint. Only then choose an owner-correct smoothing, continuous presentation
or near-layer solution. No per-ID presentation clock or loss of intended downward soft breathing.

### 21.3 The other reactions still share saturating driver paths

The simulation's `level` is followed from `max(bass, 0.70*mid + 0.35*high)`, while `change_drive` blends
this level, the small-body envelope and flash through `_soft_top`. Population counts, stream speed,
drift, emission and rays all consume some combination of these aggregate/follower signals. In
particular, `activity = min(1, idle_rate + 1.6*level)` saturates before `level` is 1; the emission
target retains `max(0.25, activity)`, and `ray_motion()` retains 30% of authored flicker scale even
when its reactive `rays` argument is zero. Those are **specific source facts to test**, not proof of
rendered speed or glow. A fixed-loud-bass recording with changing vocals must demonstrate meaningful
small bubbles, stream, drift, emission and ray changes, rather than being pinned by the shared floor.
Trace actual recorded band tuple → individual uncompressed/compressed drivers → Ranges → eased value
→ uniform/instance → native visual motion. Include silence, held loud, changes inside loud and release
on P1/P7 and two card sizes. No lane's acceptance status changes until the operator or a capable
local agent has visually validated the output.

### 21.4 Offscreen capability correction and reproducer

`tools/visualizer_replay/extruded_bubble_projection_gate_probe.py` is a standalone **Qt-free**, source-
checked diagnostic that reproduces the declared silhouette geometry, projection and near layer gate,
reads the real mutable authored P1/P7 focus/aperture and prints numeric reproduction. Optional `--json`.
It does not use real recorded input or produce accepted full native frames.

This container successfully initialized an offscreen EGL **Mesa llvmpipe OpenGL 4.5 core** context
(`4.5 (Core Profile) Mesa 25.0.7-2`). Thus GPU/offscreen projection and primitive experiments ARE
possible here: the previous blanket statement that no rendering check was possible was incorrect.
But the shipped EB shaders use **GLSL 460** and the Qt Quick product framebuffer stack is not present;
a 4.5 software-context diagnostic would need carefully described shader-version adaptation and remains
distinct from native Windows RTX/driver shader, composition, recorded presentation and visual sign-off.
No such full renderer validation is asserted here.


## 22. 2026-10-20 superseding implementation candidates, never visual acceptance

All visual failure checkboxes in `Current_Plan.md` remain open. This section updates
§§20–21 with source changes and Qt-free logical evidence after the operator expressly
rejected the assumption that most judder came from the camera or near-focus path.

### 22.1 Historical Bubble Temporal Fidelity and causation

Read `Docs/Guardrails/Bubble_Temporal_Fidelity.md` and
`Docs/Historical_Bugs/R-105_Bubble_Remaining_Small_Radius_Judder.md` first.
The **accepted 2D Bubble** repair used an immediate rising presentation size
loudness/body gate with `RENDER_SIZE_RELEASE_S` release, preserving prompt musical
attack. Its later tiny-breath alternate filter was rejected and removed because it
worsened same-recording results and altered strong reference extrema; it must not
be reintroduced. The rejected physical 1–2px jitter is primarily a
presentation/audio-target/radius/temporal-fidelity problem to be traced using SAME
identity at true physical DPR and Qt frame presentation cadence. The separate
hard `sceneNearCircle > 1.5` normal/defocus pass switch (§21.2) is credible
but **not evidence of the majority** of bubble judder, especially out of focus.

Record for each common ID: real source band timestamps and freshness, raw target,
reference, body and final envelope, nominal/current physical radius, projected
radius, pass choice, Qt swap/paint timing, pixel motion and recorded music. Include
quiet, gentle bass/vocals, changes within held loud, onset, pause/resume and
Settings/preset swap. No bypass clock or indiscriminate visual filter.

### 22.2 Large-bubble startup: implemented, numerically guarded, still unaccepted

PRE-CHANGE synthetic replay (`§20`) at 60Hz using the **actual mutable P1/P7
values** gave a peak/final ratio ~2.7 for (1) joining already-playing music,
and (2) the engine's one-second quadratic playback ramp. Priming the references
alone repaired case (1) but NOT case (2). Naïvely clamping the big change
contribution reduced the numerical overshoot but FAILED the existing
`test_soft_large_breathes_downward...` test. A longer event tail FAILED
`test_large_size_tracks_changing_body_bands...`. Both candidates were rejected.

CURRENT source candidate in `extruded_bubble_simulation.advance`:

* Prime large-body reference on first meaningful playing sample rather than
  classifying ongoing music as an initial attack.
* Pass the **existing BeatEngine's reactivity warmup state** via
  `is_reactivity_play_ramping` → `logical_frame_capture` → `ExtrudedBubbleFrameRuntime`
  → `MusicInput.play_ramping`. This is source-owned metadata: the original band
  calculation and one-second ramp remain unchanged, with no extra timer or floor.
  Both large and small lanes hold their body-change reference to the source
  during warmup and through its final transition tick.
* For gradual unflagged rises, a faster body-reference follower and bounded
  positive change prevent a repeated false phrase attack. Genuine abrupt
  musical rises receive a short real-change follower (0.25× authored softness),
  retaining sharp musical excursion and deliberate soft-breathing descent.

Qt-free focus suite: **39 passed** (`tests/test_extruded_bubble_simulation.py`,
`tests/test_extruded_bubble_full_dynamic_audio.py`,
`tests/test_extruded_bubble_startup_and_sizes.py`). Controlled P1/P7 hot-start
large radius peak/final **1.253/1.253**; source-tagged engine quadratic ramp
**1.238/1.238** (~1.00×), and untagged negative-control ramp
**~1.517/~1.238** (~1.23×); a genuine post-idle sudden musical rise still
reaches a strong excursion (>1.8 peak/final). These are logical test inputs,
NOT proof of normal musical response, good visual feel, correct preset-switch
behavior or actual recorded start. **Small-bubble untagged startup and genuine quiet→hot steps still exhibit
independent huge numerical size peaks (>3× nominal); this does not occur in
the source-tagged engine warmup case, but its visual behavior and scale remain
unaccepted.**

The existing `tools/visualizer_replay/extruded_bubble_startup_probe.py --gate`
checks large and small actual warmup/hot-start gates and the separate unflagged
large-gradual gate. The unflagged small ramp remains intentionally an
open/sensitive negative control. Preserve the original-red historical result
in §20. Test real recorded bands and the play-ramp
boolean from production, not a synthetic flag assumption, plus repeated source
activation/deactivation and native visual before sign-off.

### 22.3 True bucket-lazy EB UI and independent size authorship

BEFORE: EB's whole settings page was lazy but, once opened, every bucket
constructed all controls and signals even if the bucket remained collapsed.
NOW `ui/tabs/media/spec_mode_builder.py` creates bucket shells and lazily
constructs each bucket's control rows only on first opening. The whole EB mode
continues to obey the shared builder/body lifecycle. Unopened controls persist
through the typed canonical cache; built controls persist through real UI
widgets. `load_spec_mode_settings` updates closed-bucket cache and built
widgets; `collect_spec_mode_settings` merges both. Conditional enable/visibility
bindings are refreshed as dependent controls are constructed.

Canonical slider IDs `extruded_bubble_large_size`,
`extruded_bubble_small_size`, `extruded_bubble_bead_size` (0.5–2.0,
default 1.0 each) belong to Bubbles, independent of Size Variety and counts.
`ExtrudedBubbleFrame` projects large/small values into the simulation's
nominal radii. Existing SAME-ID sphere radii scale once per changed authoring
value, and newly admitted bubbles use the same scale. Collision/wake path uses
current physical radii. `uBeadSize` now multiplies chain and parent-attached
wake procedural bead radii; unrelated marine snow does not use the multiplier.
The third type is thus *beads/wakes*, not a third physical large-shell species.

The CAMERA bucket independently authors `extruded_bubble_camera_fov` (35–62°,
default 45°). Existing JSON presets were **not** mass-edited; canonical
settings defaults and missing-key runtime fallback preserve owner-authored
choices without a migration overwrite. Qt integration, real Settings startup,
Reset/Custom/preset switching, hidden-bucket edit persistence, rendering shape,
0.5–2.0 endpoints and cross-bucket predicates need native test and visual
inspection. Added `tests/test_extruded_bubble_lazy_settings.py`, a real VisualizersTab
Qt test for unopened-bucket hydration, live edits, first-open construction,
cross-bucket preservation and silent preset reload; it compiles but is NOT
executable in this environment. The Python environment here lacks PySide6
and cannot certify that lifecycle. The C++ Qt/Windows build stays operator-owned.

### 22.4 Camera distortion: concrete removal of off-axis shift, unaccepted framing

BEFORE: 62° vertical perspective, and Scene Pan modified the projection's
`shift[0]/shift[1]` rather than changing a camera viewing direction. Any
honest projected physical sphere approaching the edges of that wide FOV can
be horizontally elongated; §21.1 predicts up to ~1.306:1 at 40° from the
camera axis. Such scene distortion IS objectionable regardless of whether
it has a separate fish-eye warp pass.

CURRENT CANDIDATE: default FOV **45°**, optional 35–62° control; centred
projection (zero lens shift), and Scene Pan modifies yaw/pitch
(`camera_look_pan`), leaving all world bubble IDs/XYZ/physical radii intact.
This *actually changes* the projection; it is not merely a wording revision.
However, look-pan alone still rotates around a stationary eye rather than
physically moving a camera/dolly or independently choosing a pivot. It can
crop the prior scene. A centred 45° camera does not mathematically guarantee
no edge stretch, optical-pupil correctness, ideal reflected/refraction glass
or good usable underwater composition. The actual lens should be judged
against rendered 62° original at matched camera distance/composition, with
native near/far/orbit tests and water/abyss framing. Physical placement/pivot
and further correction stay OPEN until approved.

### 22.5 Offscreen GPU capability is real, not native parity

The container has EGL Mesa llvmpipe GL 4.5 core, so isolated GPU geometry and
optic diagnostics are feasible, even without PySide6 or a Windows RTX 4090.
The unmodified GL 4.6 product shaders and Qt Quick presentation, compositor,
DPR/scheduling, source capture and actual musical screenshots have NOT been
validated here. Neither CPU nor offscreen primitive checks visually accept
any of the above candidate changes.


## 23. Camera semantic correction, physical world-space eye, and bounded Settings work (2026-10-20)

**All `[~]`; operator/qualified local visual acceptance remains outstanding.** This section
supersedes the *candidate behavior* in §22.4, **not the retained historical failure**.
The original Scene Pan was an off-axis lens shift. The first correction accidentally
changed Scene Pan into `camera_look_pan(turn, tilt, ...)`, duplicating the existing
Alt+left-click rotation control. That was operator-rejected. The intended contract is:

| Existing input | Source owner | Actual camera behavior (candidate) | Must not do |
| --- | --- | --- | --- |
| Alt+left orbit | `extruded_bubble_turn/tilt` | Eye circles a fixed world pivot; look direction tracks it | Pan, move widget card or turn scene geometry |
| Scene Pan | `extruded_bubble_scene_pan_x/y` | Translate eye and target in local camera right/up plane, preserve orientation/FOV | Add yaw/pitch, shift sensor/frustum or teleport world |
| Wheel/zoom | `extruded_bubble_scene_scale` | Dolly eye/pivot distance (15 / authored scale), preserve orientation/FOV | Fake focal-length zoom, rescale bubble radii/world |
| FOV in Camera bucket | `extruded_bubble_camera_fov` | Independently authors centred vertical FOV, default 45°, 35–62° | Change scene geometry or silently rewrite presets |

**Source:** `rendering/gl_programs/extruded_bubble_scene.py` owns
`physical_camera` and the fixed pivot 15 world units ahead of the original default
look ray (default eye remains at origin). Its 5-tuple supplies world-rotation matrices,
**world-space eye**, pixel-angle factors and centred projection; pan uses camera-plane
translation and dolly shifts physical depth. Underwater surface clearance constrains
actual motion at extreme upward angles rather than silently adding another camera
rotation. The baseline camera orientation helper remains solely for orientation,
no old lens-shift/look-pan APIs exist. Any camera limit, sign or pivot must still be
compared with operator interaction expectations on Windows.

**Source-propagation audit:** `rendering/quick/visualizer/implementations/extruded_bubble.py`
uses one `physical_camera` per frame. `extruded_bubble_program.py` now subtracts
`uEye` before **ordinary shell/union, speck, bead, wake and cube-proxy** world-to-view
transforms. `uEye` is also included in common/program uniforms, translated world-water
surface intersections and shaft world-space marching. Proxies captured into the
cube probe follow the current eye. Near CoC no longer double-counts virtual zoom.
The bubble/stream physical population is untouched. The shader/camera contract was
**source/Qt-free checked, not full product GL 4.6 compiled or visually accepted**.

**Geometry limit:** Centred perspective and physical camera translation remove the
unwanted sensor shift and control duplication. They do **not** remove rectilinear
off-axis stretching. Existing analytic same-ray sphere ratios: centre 1.000:1,
30° 1.155:1, 40° 1.306:1; default 45° FOV reduces the available off-axis angle
at a given card position but does not abolish that effect. An honest decision about
remaining apparent shape requires **native side-by-side silhouettes plus material
coverage**, possibly a further documented camera-projection design. Do not call
"non-distorted" achieved simply because matrices or shaders compile.

**Lazy Settings correction:** `ui/tabs/media/spec_mode_builder.py` previously
called full `load_spec_mode_settings` on every **first bucket open**, re-admitting
and writing widgets in ALL previously opened buckets. New `only_buckets` hydration
reuses authoritative cache and hydrates only the new bucket, while full preset
updates still refresh both built and unbuilt values and cross-bucket visibility.
The lifecycle barrier remains strict. The 01:11:43 Settings timeout had one
`QuickDisplayVisualizerOwner` survivor, not a proven slow bucket control. **Next
native evidence:** elapsed mode skeleton construction, one-open and all-open bucket
widget-count/cost, signal hookup count, per-preset save/reload, and failure-only
Python referrer receipt for the sole owner that blocks retirement; identify precisely
whether the builder retains it or only consumes time during startup. Do not add a
polling/timer/timeout workaround. Check an exception halfway through one bucket's
creation for duplicate rows/signals on retry. The section-only construction,
cache/unsaved UI guard and last-open-bucket preservation remain mandatory.

**Falsifiers:** run Qt-free `tests/test_extruded_bubble_physical_camera_contract.py`
via the startup probe bootstrap and `--noconftest`; follow with actual native Qt,
GL 4.6 build and 1672×941/2560×1440 side-by-side P1/P7 screenshots. Test near and
far fixed-ID bubble projection across pan/orbit/dolly, independent controls, the
water surface as the camera moves, near DoF class switching separately, accurate
cube-probe glints and Settings handoff. Nothing in this section closes the operator's
camera, judder, reactivity, optics or lifecycle failures.

## 24. 2026-10-20 evening: camera reset, recovered pan signs, 10% rest motion, renewed reaction rejection

**Acceptance state:** **ALL [~] source candidates; ALL visual failures open.** This section does not replace
§§20–23, the operator's source recordings, R-105, or `Bubble_Temporal_Fidelity.md`.

### 24.1 Camera reset semantics and the avoidable pan reversal

The first physical camera implementation used `eye += right * panX + up * panY`, directly interpreting
screen-normalized presentation coordinates as camera movement. That is wrong: moving the eye right
makes the stationary subject move **left**. It also ignored the screen's down-positive Y convention.
Compare the pre-physical source `lens_shift(pan_x,pan_y)=(2panX,-2panY)` and Qt Alt-right
`display_manager._move_quick_visualizer(offset.x/width,offset.y/height)`; both mean a positive
scene pan should move the **subject** right/down, not the eye right/down. Correct physical camera:

```
dx = -2 * distance * tanX * panX   # camera LEFT gives subject RIGHT
dy = +2 * distance * tanY * panY   # camera UP gives subject DOWN
new eye = pivot + back*distance + right*dx + up*dy
```

The camera's underlying rotation still belongs to Alt+left/WASD. Scene Pan remains Alt+right/Scene
Pan and keeps orientation/FOV invariant. Zoom remains a dolly rather than FOV multiplication.
`test_pan_follow_screen_pointer_sign_is_not_inverted_again` and
`test_physical_pan_screen_axes_match_alt_right_drag` now distinguish physical translation from
mere rotated view. Test at nonzero turns and near the underwater ceiling on native Windows;
no operator visual acceptance yet.

**R shortcut + glyph candidate:** An application-wide `R` (when a framed 3D Visualizer is
admitted, from any active display) now emits one non-repeat reset signal via
`RuntimeInputOwner` → `QuickDisplayRuntime` → generation-scoped `DisplayManager`. EB also offers
one translucent lower-right `↺` glyph in the existing `VisualizerPresentation.qml`, revealed
only on hover during admitted interaction/Ctrl. Its QML signal is bridged through the existing
Quick scene/runtime reset signal to the **same** handler. No second camera owner and no new
timer or polling. Screen mode admission is event-published and cached for a QML root created
lazily later. The route cancels held orbit/drag intents, release inertia, auto rotate, in-flight
pan/zoom and old pending pose transactions, then writes the reset ONCE using the existing
`resolve_visualizer_view_orbit` persistence owner and refreshes edit framing. Preview remains
possible but native click/input/hover/Settings/save/reload/lifecycle acceptance is pending.

**Home source:** all seven on-disk EB presets have valid `starting_view` metadata: P1/P2
(0 tilt), P3 (+0.022), P4 (-0.022), P5 (-0.111), P6 (-0.500), P7 (-0.133); all pan=(0,0),
scale=1.0 and turn=0. They have NO stored FOV field in JSON, despite the in-memory Settings
normalizer being able to fill that key with the canonical default. Presets stay operator-authored
and mutable. `starting_camera_pose` reads metadata WITHOUT modifying it; Custom resets to
mode canonical pose (no pretense of an immutable Custom starting view). Reset explicitly restores
EB's separate canonical *lens* FOV to 45°, so an old live 62° setting cannot survive R unnoticed.
This reset of the FOV is not an automatic preset migration and does not modify JSON or other
current artistic settings. Confirm on screen that the lens angle, tilt/pivot and water ceiling
produce useful desired framing. All failures including rectilinear peripheral stretching remain.

### 24.2 Additional operator observations, not already accepted

- Breathing is noticeably improved overall, **still unaccepted**; large bubbles appear pinned
  near maximum size far too frequently. Need per-ID percent-near-peak and minimum/peak/run-length
  compared with music phrase structure; a slower generic release could actually worsen pinning.
- Small bubbles jump between two apparent size states rather than move continuously between
  them. Disambiguate source envelope reversal/target discontinuity, direct `current_radius`
  publishing without per-ID drawn state, representation gate crossing, and presentation
  starvation. Compare accepted 2D `RENDER_SIZE_RELEASE_S=.10s` / actual BTF contracts;
  specifically do not restore R-105 rejected tiny-breath directional hold.
- Light rays show **no perceptible musical reactivity**, including on strong music, regardless
  of existing source wiring. Need native ray-mask/shaft ROI signal/contrast evidence.
- Stream/drift behave like one big idle→playing switch. A slow→fast→slow musical *section*
  within continuous playback has little to no visible motion difference. Need proper fast
  attack, slow decay and significant projected motion change even under already-high bass.
- Resting motion should be ~10% greater among moving families, EXCEPT the ocean surface.
  Operator permits gently increased nonmusical baseline movement, **not** a fake audio band,
  full-on speed, periodic bubble breathing or a new source/clock.

### 24.3 Source-owner audit and bounded new numerical evidence

`ExtrudedBubbleSimulation.advance` uses normalized `level=max(bass,0.70*mid+0.35*high)`;
`change_drive=_soft_top(0.60*level+0.60*small_envelope+0.15*flash)`; and
`activity=min(1,idle_rate+1.6*level)` (prior to a 10% rest-only multiplier).
That `activity` saturates at level around 0.59, while `_soft_top` and target followers can
compress/lag intra-song differences. However saturation ALONE is **not** enough to explain
all the reported visual lack of reaction. Source can vary in an isolated controlled input.

A Qt-free **synthetic**, steady high-bass `.85` sweep at `(mid,high)=(.15,.12)→(.85,.8)
→(.15,.12)`, each section 2 seconds (average of last 30 frames, 60Hz, P1 settings,
no onsets), yielded the following logical snapshot averages:

| Phase | Level | Stream world units/s | Drift | Ray driver | Small body envelope |
|---|---:|---:|---:|---:|---:|
| high bass / low mid | .850 | 1.213 | .605 | .332 | .027 |
| high bass / high mid | .875 | 1.789 | .818 | .688 | .637 |
| high bass / low mid again | .851 | 1.385 | .628 | .341 | .027 |

Thus stream changes by about +47% and drift about +35% IN THE LOGICAL SNAPSHOT, and the ray
driver roughly doubles. This test **does not falsify** the operator's observed in-game
stillness: projected optical-flow pixels/s, camera distance, shader contrast, emitter paths,
per-pixel range and multi-stage latency have not been measured. A 2-second synthetic plateau
with no onsets is unlike real recordings and cannot certify fast ramp/slow decay. Measure the
logged same-ID world travel vector and projection into pixel motion; `WORLD_UNIT=9`; then
compare with accepted 2D on exactly the same recorded slow→fast→slow sections.

For rays, `ray_strength(parameters,state.rays)` applies both the authored Range interpolation
and an additional `(0.03+0.97*driver)` multiplier; final `uRays` enters the backdrop using
`texture(uShafts)` and a `uRayCut` smoothstep/focus, mixed with water and bloom.
`_draw_shafts` renders the fan/depth-march texture independently from the musical driver; the
backdrop controls how visibly music modulates that pattern. Log all of: `_rays`, `uRays`,
shaft texture mask mean/p95, cutoff-surviving area, pre/post-water luminance, post-target
HDR/bloom, and change in a shaft-only ROI. Difference images need synchronized input,
identical camera and exposure, no motion confound. Don't claim success from an animated
`uShimmer` texture if steady/faster music does not change perceptible rays.

For sizes, calculate `big_target` and `small_target`, per-ID nominal/current radius,
class-specific envelope, near-CoC branch, projected radius and display timing on each logical
revision. Histograms of per-ID frames above 90%/95% of respective local dynamic upper radius,
mean flat-run duration and 10–90% opening/closing times are important; a global mean washes out
the distinct large-pinned/small-snapping complaints. Include source-band and onset timestamps
before any follower changes.

### 24.4 Narrow +10% idle motion source candidate

The simulator now computes `rest_motion_boost = 1.0 + 0.10*quiet` where
`quiet = max(0,1-intensity/.10)` is an already-existing music/silence blend. Only the
*resting contributions* to speed/drift admission, wake/bead/snow/speck travel, sway amplitude
and ray shimmer increment use the multiplier. Do **not** increase the separate shared
`_motion_phase`: it drives the ocean surface and must remain unchanged. The 10% extra
speed can be swallowed by downstream projection, and the resting emission minimum
`max(0.25, activity)` can swallow it entirely for speck population; neither receives an
unearned visual-acceptance checkbox. The Qt-free idle test checks exact speed and shimmer
scalars and unchanged surface phase, not actual fluid visuals. No additional source clocks,
latent channels, timers, or authoring overwrites were introduced.

### 24.5 Native falsification and remaining status

- Verify keyboard R in interaction, Ctrl, Custom/Edit, both displays, while WASD is held,
  Alt+left is mid-drag, auto-rotate running, Settings open, and mode/preset switch or
  runtime replacement is pending. Verify only one camera/preset commit, no accidental
  reset outside framed 3D, and no ordinary previous-image/exit hotkey regressions.
- Inspect EB glyph under card hover and under edit/resize chrome at normal and tiny sizes:
  correct z-order, opacity/colour, click target, mouse focus and no event passthrough.
- Confirm all 7 curated pose homes and Custom, FOV=45 reset, manual FOV retention except
  when R is explicitly invoked, physical pan signs, side-pan parallax, zoom and water ceiling.
- Capture 12 seconds of `anything_mixed2`, plus slow→fast→slow, heavy and acoustic recordings
  with SAME-ID world/render radius, stream velocity, drift, projected optical flow and shaft-only
  ROI. Distinguish quick attack from slow decay and base/rest behaviour from sustained content.
- Run native Qt Settings-lifecycle/preset UI tests and actual GL 4.6 render. These are not
  available in the sandbox, and the Qt-free contract tests do not stand in for them.

**Final status: ZERO operator visual failures closed.**


## 25. P7 particle controls and split audio-vs-visual smoothing audit (2026-10-20)

**Investigation only, NO operator/agent visual acceptance.** This section is in
addition to §24, the existing full 4B checklist and BTF/R-105; nothing is closed.
No EB Lab, real audio recording, or native production shader context was necessary
for this source investigation. All numerical comparisons below used synthetic
piecewise constant band tuples and P7-authored control values, not live gameplay
or matched native pixel captures.

### 25.1 P7's visible particulate: the exact authoring/renderer wiring

- `core/settings/visualizer_mode_settings.py`, `_EXTRUDED_BUBBLE` Particles bucket:
  `Particles` range (`extruded_bubble_particles`), `Particle Size`, `Particle
  Colour`, `Warm Share`, `Particle Glow`, `Particle Bands`, conditional `Band
  Contrast`. `Sparkle` is a **Glass** control; `Bead Chains` is its own **Bubbles**
  count range. There is no named mesh-debris emitter control for EB.
- The on-disk P7 `preset_7_ember_drift.json` snapshot has `Particles` [.85,1.0],
  `Particle Size` 1.6, `Particle Colour` [255,64,5,255], `Warm Share` .9,
  `Particle Glow` .6, Bands enabled, Band Contrast 1.0. P1–4: [.1,.35], size
  1.0, warmth .3, glow 0, bands disabled. P5: [.3,.4], P6: [.5,.6], both
  bands disabled and particle glow 0. Their ember specks can therefore look
  absent without the P7 treatment even though they use the same code path.
- `extruded_bubble_frame_runtime.controls_from_parameters` resolves Particles
  once to the simulation `emission` pair. `ExtrudedBubbleSimulation.advance`
  computes and smooths `_emission`; `_procedural_fill` uses that state for
  marine snow and emitter fizz, while the separate SPECK pass uses
  `speck_amount(parameters,state.emission)` from `extruded_bubble_scene.py`.
  The latter outputs `(emission², 2.4 × emission)`; the renderer computes
  `round(216000 × emission² × scene3d_detail.particles)` submitted instances.
  Shaders can cull via cloud masks, camera, alpha/light and bloom; instance
  counts are NOT visible-dot counts.
- Synthetic comparison at 90 Hz, constant playing bands (.85,.74,.64), four
  seconds and P1/P7 authored reaction/emission controls: P1 emission ~.248
  and ~13,235 speck instances (full particle detail); P7 emission ~.900 and
  ~174,939. At zero bands for four seconds, P1 emission ~.025 (~135
  submitted), P7 ~.211 (~9,622). Counts ignore the GPU shader's masked
  fragments and do not prove visually observed density, but clearly identify
  why P7 is dramatically more aggressive.
- Safe operator experiment: first change only `Particles` endpoints, then
  only `Glow`, `Size`, and `Particle Bands` to isolate density versus brightness
  and diagonal clustering; avoid misdiagnosing Glass/Sparkle as scene debris.

### 25.2 Source-confirmed control contract mismatch: Smoothing changes MUSIC

Source `widgets/spotify_visualizer/extruded_bubble_simulation.py`, `advance`:

```python
soft = 0.5 + 1.5 * max(0.0, min(1.0, controls.smoothing))
self._level = _follow(self._level, intensity, dt, 0.08 * soft, 0.45 * soft)
self._small_body_reference = _follow(self._small_body_reference, small_body,
                                     dt, 0.55 * soft, 0.25 * soft)
small_change = max(0.0, small_body - self._small_body_reference)
self._body_small_envelope = _follow(self._body_small_envelope,
    _soft_top(0.18 * small_body + (6.0 + 2.0 * sustain) * small_change),
    dt, 0.06 * soft, body_release)
```

The `soft` factor ranges .5–2.0, **a 4× range of audio-following time
constants**, not simply visual presentation smoothing. It also multiplies
large body reference, big/small envelope release, motion, stream, drift and
emission time constants. On a new mid/high phrase, raising Smoothing slows
`_small_body_reference`, thereby artificially prolonging the positive delta
multiplied by 6–7.2; slow reference tracking changes both *amplitude* and
*duration* of actual sound-derived size targets.

Probe used actual P7 `ExtrudedBubbleControls` with collision disabled only to
prevent object turnover confounding the class envelopes; deterministic 90-Hz
steps: 1.33 s zero bands → 4.00 s (.85,.74,.64) → 3.33 s (.27,.16,.12)
→ 2.67 s (.95,.90,.85) → 3.33 s (.27,.16,.12), no onsets, source playing
throughout. Derived class radius multipliers after each stage:

| Smoothing | quiet large/small | first loud large/small | first soft large/small | second fast large/small | second soft large/small |
|---:|---:|---:|---:|---:|---:|
| 0.0 | .130/.130 | 1.870/.341 | .312/.168 | 1.837/.394 | .309/.168 |
| 0.5 | .130/.130 | 1.867/.377 | .314/.168 | 1.833/.683 | .311/.168 |
| 1.0 | .130/.130 | 1.869/.710 | .316/.168 | 1.872/2.066 | .313/.168 |

This is a **much stronger falsifiable lead** for the small-bubble size-state
complaint than generic 'not enough smoothing': the setting itself can produce
massively greater *logical* inflation after the same musical change. It does
not establish whether the actual visible steps are also caused by output
cadence or the known near-DoF branch. Only recorded bands/native size traces
can confirm on-screen causation. Importantly, the big/large held path barely
changes between two different high-energy synthetic sections, furnishing a
lead for musical contrast/pinning without claiming actual max clamp.

### 25.3 Why 2D Bubble is meaningfully different

- 2D Bubble maintains per-bubble `pulse_energy` and `size_gate_energy` and
  presentation-side `_drawn_body_energy`/`_drawn_loud_energy` that rise
  immediately and fall over `RENDER_SIZE_RELEASE_S = 0.10s`; underlying
  musical pulse integration and input are NOT slaved to a visual Smoothing
  multiplier. Its hero big `display_radius` advances per ID, with smoothly
  blended near-target rates. BTF and `R-105` expressly forbid resurrecting
  the rejected tiny-breath hold/dead-band experiment.
- EB currently derives one `_body_big_envelope` and one
  `_body_small_envelope` for the entire population; the next capture
  replaces each bubble's `current_radius` with `radius × class_scale`.
  There is **no independent per-ID displayed-radius memory** for either
  population. All same-class silhouettes must expand/shrink in synchrony;
  2D's per-hero history and size envelope cannot be reproduced simply by
  increasing EB's global musical smoothing.
- The big lane receives permanent held component
  `(0.25 + 0.75*sustain)*big_body` even without new events; `_reaction_scale`
  converts that one held drive into BOTH baseline re-expansion and a positive
  expansion term with the same held input. This plausibly produces long
  plateau occupancy and soft-to-loud binary visual behavior, but further
  numerical and native probes must distinguish legitimate sustained bass
  body from musical flatlining, and distinguish intrinsic radius from
  actual visual-edge clipping or bloom.

### 25.4 Specific next falsifiers and candidate direction (NO source fix yet)

1. **Restore independent authorities.** Smoothing setting should tune only
   visual-size convergence, *not* `_level`, body reference/delta, `_sustain`,
   stream/drift/emission or musical phase. Keep the preexisting shared capture
   clock and real band feed. Measure raw-body/reaction trajectories before
   and after source correction; smoothing 0 vs 1 must leave the logical
   musical driver unchanged to numerical tolerance.
2. **Continuous, per-ID presentation-size evolution at canonical owner.**
   Add an identity-stable displayed radius per bubble; separate desired
   musical `target_radius` from its visual convergence. Rise promptly, release
   with a bounded continuous decay, interpolate rates continuously through
   small errors, never latch at a percentage dead-zone, and never simply
   quantize/discretize between two sizes. Preserve geometry SSOT and
   consistent use of the actual drawn radius in shells, fused contacts and
   wakes; no second renderer-side simulation or additional clock. Verify
   a fast attack is visually preserved at smoothing=1, and strong downward
   contraction on a soft passage is visible without stepping.
3. **Fix excessive held occupancy separately.** Instrument each stable
   large ID's time >90% and >95% of its observed passage-local maximum,
   duration of flat sections, and 10%→90%/90%→10% opening/closing times.
   Compare 2D's held-body support and separated crest support before
   adjusting EB's `(0.25+.75*sustain)*big_body`, the positive delta term,
   `_soft_top` knee or `_reaction_scale`; do not simply globally lower
   breathing strength, flatten loud peaks or contract every bubble to a dot.
4. **Line up one actual recorded passage.** Use `anything_mixed2` and at
   least a slow→fast→slow section (plus quiet/heavy controls). On the SAME
   stable IDs record captured bass/mid/high and ramp flag, small/big
   reference, uncapped delta, class envelope, target radius, drawn world
   radius, near-DoF branch, projected per-pixel radius and Qt presentation
   timestamp. Compare accepted 2D render-gate/hero traces with EB from the
   very same source. If target oscillates, fix its cause; if drawn radius
   jumps despite smooth target, fix temporal presentation and/or view branch.
5. **Native output remains the acceptance gate.** Identical recorded-audio
   samples, chosen P1/P7 Settings, same DPR/viewport and visible bubbles,
   with operator review. A passing synthetic unit test or generated diagram
   cannot close any of the failures. No preset overwrite, no silent control
   reroute, no slow build and no environment-variable setup.

**Status: all related EB visual failures remain `[ ]` or `[~]`.**


## 26. Interrupted recovery checkpoint: visual-only radius, count admission and ray plateau (2026-10-20; **UNACCEPTED**)

**Archive scope.** The earlier interrupted agent's unarchived work was not available as a ready-to-ship working tree. This checkpoint is rebuilt from the last verified `EB_SPECKS_BREATHING_INVESTIGATION` Godzip, not from a live repository and not from verbal claims about an unverified later source. Only changes actually present in this full handoff count as implemented.

### 26.1 Candidate changes (not visually verified)

- Smoothing multiplies **no musical/flow/light/emission follower**. `soft` in `ExtrudedBubbleSimulation.advance` is now constant 1.0 for these logical followers; `controls.smoothing` is used only in a 10–95 ms displayed-radius rise and 12–177 ms displayed-radius release (per stable bubble ID; dt-invariant exponential). The physical `current_radius` remains unsmoothed for collision and cluster resolution; displayed `visual_radius` feeds snapshot shell and wake emitter. These tau values are candidates, not copied or claimed accepted 2D values.
- The held-large coefficient is tentatively `(0.22+0.70*sustain)` vs previous `(0.25+0.75*sustain)`. This does **not** duplicate 2D's soft ceiling and separated presentation/hero controls. Operator specifically questions reducing held support instead of making crest activation rarer, preserving continuous rise and fall; retain both hypotheses for visual comparison. Measure amplitude *and fraction of track* held near local peak.
- Stream-speed musical attack is a fixed 0.68 s to maintain temporal continuity without coupling to display smoothing. Do not apply this visual change to the water-surface phase. Existing prescribed +10% idle motion remains.
- New `tests/test_extruded_bubble_display_only_smoothing.py` compares 390 same-seed frames under `Smoothing=0` vs `Smoothing=1` for identical musical scalars, flow, rays, emissions, positions, stable IDs, physical sizes, contacts and clusters, allowing only visual radius variation. This is a logical test, not native render acceptance.

### 26.2 Unresolved new count saturation symptom

Operator observes that **both** large and small population counts reach authored loud-end quantities on minimal audible audio. Source `targets` linearly maps the already-normalized, quick-followed `_level` into `(low,high)` range; `_level` follows `intensity=max(bass, 0.7*mid+0.35*high)` with 80 ms attack. Distinct from particle emission (`extruded_bubble_particles`, governing speckle density). That is a concrete possible early-saturation mechanism, not proof of which source stages or presets force the count to maximum. Record target, live, retiring, spawn-credit, source normalized bands, and idle→playing→quiet/loud phrases; compare actual 2D count transfer and admission smoothness. Candidate intervention is an explicit monotonic response curve for *count* with high crest threshold and fast attack/slow decay. Do not conflate number of bubbles with bubble radius and never silently rewrite preset min/max endpoints.

### 26.3 Rays and source/endpoint remain open

Rays rise conspicuously when playback begins but reportedly peg at a high visible brightness during ordinary playing, rather than moving within selected `Ray Strength` quiet/loud endpoints. Request transient-linked subtle lifts with graceful decay, without random rapid flicker. Measure simulation driver → uniform → HDR pixel → post-bloom pixel with the same recorded sections. No definitive bubble/particle shaft attenuation currently established, so test before claiming physical occlusion. Both directional and ray controls are **still one-point in this archive**, as in the verified baseline: the earlier discussion of fully wired two-node source/end controls is not a verified delivered artifact. Next slice requires Settings visual-widget, schema migrations without touching mutable presets, renderer/physics integration, and native coverage as a unit.

### 26.4 Validation status

A test that previously required smoother *musical flash* was explicitly corrected to assert equal flash and different displayed-radius response, because mutating musical flash violates the stated operator contract. The preexisting untagged playback-ramp gate remains red. All visual failures stay `[ ]` or `[~]` until operator or explicitly authorized local agent visual verification.


### 26.5 Separate population occupancy candidate (NOT visually accepted)

`ExtrudedBubbleSimulation` now resolves **big/small count occupancy only** from a continuous composite of musical body-band breadth: 52% strongest normalized `max(bass,vocal_body)` plus 48% weighted bass/mid/high (`0.42/0.39/0.19`), raised to the 1.8 power. This deliberately prevents a lone near-peak band from immediately requesting both authored maximum counts. Count eligibility follows on the existing logical capture with 0.28 s fast attack / 1.05 s slow release. The first logical fill uses the current musical eligibility and then the usual bounded entry/fade path applies. Preset count endpoints remain untouched. Musical body energy, size, particles, rays, flow, and water phase are not retuned by this count control.

**Source test trap caught before handoff:** the existing flow owner used `low, high = controls.stream_speed`, shadowing the earlier audio-band `high` name inside `advance`. The initial composite calculation incorrectly read the speed cap as treble, yielding only ~0.84 full-band population eligibility even for `(1,1,1)` synthetic input. Renaming `low_speed, high_speed` restored actual audio-band ownership, making the all-band max 1.0 and restoring all existing 36 tested admission invariants. This was a candidate-code bug discovered during verification, not evidence of a previously present production failure.

`tests/test_extruded_bubble_population_candidate.py` verifies all-band true maximum, absence of one-band count saturation, monotonically differentiated musical contents, smooth slow release, bounded per-frame target change and authored population limits. These are synthetic, not a substitute for actual AGC trace distributions. The 2D Bubble uses stable operator-authored counts rather than EB's audio-interpolated count ranges, so **no literal count transfer function can be copied from 2D**. The accepted 2D continuity and entry/fade principles remain comparison targets. No visual checklist closure permitted.

## 27. Two-ended real-world source controls and ray transport proxy (2026-10-20; **NOT VISUALLY ACCEPTED**)

### 27.1 Implementation boundaries

The source for this checkpoint is the superseding `EB_POPULATION_RESPONSE_CANDIDATE` Godzip, not the live repository and not the aborted, unarchived prior two-node work. `Current_Plan.md` EB-R27 is the ACTIVE checklist; prior §26's historical statement that two-node controls were absent was true of that earlier checkpoint, not a promise that anything in this candidate is accepted.

- **Schema and persistence:** `core/settings/visualizer_mode_settings.ScenePath` subclasses the existing typed Direction contract, persisted under original `extruded_bubble_stream_direction` and `extruded_bubble_light_direction` keys as normalized six-tuples (`source x,y,z; end x,y,z`). `extruded_bubble_ray_path` adds an independent canonical six-tuple, without changing seven preset files. `core/settings/visualizer_paths.py` validates finite noncoincident paths and migrates old `[around,height]` values to physical volume endpoints. Legacy migration preserves the prior world direction, accounting for the world box's nonuniform X/Y/Z extents. The sole volume dimensions now live in `core/constants/extruded_bubble_world.py` and are reexported by `extruded_bubble_geometry.py` rather than duplicated. No environmental configuration.
- **UI:** `ui/widgets/visual_controls.ScenePathMapper` is a shared double-ended S/E disc (world X/Y, bottom=floor, top=ceiling) and two Z/depth rails, one for each endpoint. Full square→disc reversible mapping permits XY corners; naive circle clipping would mutate oblique preset directions. Node drag produces `valueChanged`, one `valueCommitted` on release; arrow/Page Up/Down and Tab target the chosen endpoint. `spec_mode_builder` chooses this visual control in the existing lazy EB bucket and unchanged persistence owner. **The full native Settings lazy load, preset switch, Reset, Custom and strict owner retirement must still be exercised.**
- **Ordinary-bubble source ownership:** `extruded_bubble_frame_runtime.controls_from_parameters` projects a scene path into one `ExtrudedBubbleControls.stream_path`. `extruded_bubble_simulation.advance` derives the world-space direction; `_spawn` uses the source node plus a bounded transverse spread, locking exact boundary coordinates, instead of sampling arbitrary entry faces or inventing camera-space source points. The previous immediate `anywhere=True` mature first fill is skipped for path-enabled runtime so no initial bubbles spontaneously appear halfway through the scene. The existing emission-credit / fade admission is used on subsequent captures, without timers. **Risk:** the card may start too empty or spawn source-overlaps too densely; only native material and playback can judge. The free bead-chain, marine snow and particle shader populations still need their own physically coherent origin audit. This slice must NOT be described as solving all emergence locations.
- **Light:** `scene_knobs` converts light endpoints to the existing directional `sun` for surface light, also carries `light_source` and `light_end` world points. The deep-light visible lobe uses true `uLightSource - uEye` so moving the light without rotating it changes its on-screen position. Deep bubble glint proxies similarly look toward that physical source. The full probe / analytic highlight source is still partly directional: **positional lighting parity is not complete**.
- **Rays:** `ray_source/end` coordinates are passed into the true production half-res `SHAFT_FRAGMENT`. `beamExtent(p)` softly gates each marched sample to the finite ray segment, plus a separate fan extent evaluated along the translated eye's view ray. Old Ray Reach is not deleted or co-opted: it is relabelled **Ray Fan Spread** for its real angular purpose; potential redundancy can be reviewed AFTER visuals. Source and End form an independent authorable ray path; canonical initial vertical ray segment does **not** automatically inherit P7's angled light source. This is a deliberate unaccepted default and important P7 comparison point, not a hidden claim of perfect visual migration.
- **Light loss through objects:** four largest ordinary visible bubbles from the current one-copy shell buffer are passed as `vec4(world xyz, radius)` proxies, each able to weaken the shaft by up to about 16% behind an approximate light-path shadow with softened edges. An aggregate 0–8% density-dependent dust attenuator is applied. This is only a bounded approximate **screen-space sampled** loss, not 3D per-particle shadow, no scene-depth voxelization, no direct shadow receiver or true volumetric multiple-scattering. Cost includes extra per-pixel maths at half resolution and selecting four shells in Python; compare GPU timing and screen image before accepting. The ray driver/range transfer itself is not changed, hence the operator's pegged intra-song luminosity failure remains open.

### 27.2 What passed and what has NOT

- Qt-free `tests/test_extruded_bubble_source_end_candidate.py` includes legacy conversion for every EB preset (no file changes), nonfinite/coincident rejection, entire XY square↔disc reach, real floor/ceiling birth, zero halfway mature initial population, physical 3D stream direction, light position and ray path knob ownership and shader uniform-path assertions. The independent prior `test_extruded_bubble_population_candidate.py` and `test_extruded_bubble_display_only_smoothing.py` scripts remain passing. These tests do not run the actual QWidget controls.
- Optional Linux/Mesa `python tools/visualizer_replay/eb_shaft_mesa_compile.py` compiles **and links** the production shaft vertex/fragment pair in a software OpenGL 4.5 core EGL context with only the `#version` downgraded for this diagnostic. This is neither product GL 4.6 on Windows nor a rendered A/B comparison; none of the material, FPS, occlusion, or ray-reactivity failures are accepted.
- **Native validation sequence, mandatory before closure:** load all seven originals then move both nodes without accidental Custom value loss; launch from dormant mode and repeatedly open/close the lazy buckets while asserting one surviving Settings owner; test directional near/far and underside/ceiling/floor source placement, with 3D camera orbit/pan/zoom (especially P7); compare free chains, wakes and specks vs ordinary bubble emergence; ray-only HDR and post-bloom captures from fixed camera on the SAME slow→fast→slow recorded passage with independently moved ray endpoints and low/high Ray Strength; examine shadow proxy readability behind foreground glass rather than painted dark discs; record new shaft-pass GPU median/p90 at 1672×941 and 2560×1440 with same density/detail/DPR. Preserve physical camera projection parity, frame timing, water-surface resting speed exclusion and operator preset authoring.

**Explicit acceptance status: ALL related entries remain `[~]` or `[ ]`.** Source improvements, Mesa compile/link and logical tests are evidence about implementation, never evidence that the operator's actual visual complaint is resolved.


## 28. Ragdoll 256/512 temporal clue, ray musical contrast, particles and recurring Settings survivor (2026-10-20; UNACCEPTED)

### 28.1 Evidence, not acceptance

Incoming operator log: `logsbae635b6764.zip` (43 files; includes Spotify visualizer, audio, lifecycle, frame-trace binary). `screensaver.log` confirms `negotiated_block=512 requested=512` in earlier Oct 20 sessions and `negotiated_block=256 requested=256` at 22:40:34. The operator reports ~80% less judder with 256, not full correction; the hardest problem is still small-bubble reaction/visual continuity even with Smoothing=1.0. The final 256 session's `screensaver_spotify_vis.log` shows `Runtime stopped (generation=1 steps=12451 skipped_deadlines=8 slow_steps=1 failures=0 joined=True)` at 22:42:50 and overall tick period measurements with `dt_max=29.61 ms`; these aggregate observations are insufficient to identify individual judder events. Need correlate **capture timestamp, normalized bass/mid/high, onset, logical sample, bubble ID, physical target radius, displayed radius, render frame ID and draw interval** with both blocks on the identical recorded passage. A block-size change may alter **source freshness, event batching, spectral windowing, onset cadence or sample timing**; do NOT label one root cause until falsified, and do not conflate BTF source cadence with the near-focus or off-axis camera separately identified defects.

`screen saver lifecycle`: 22:42:50 `armed reason=settings retiring_generation=1 qobjects=948 python_owners=3`; at 22:42:58 `CRITICAL timeout ... qobjects={} python_owners={'QuickDisplayUnit':1,'QuickDisplayVisualizerOwner':1} resources=[] thread_work=[] global_subscriptions=[]`. Also 18:35:58→18:36:06 same two survivors. Successful 22:38:44→22:38:45 and 21:00:06 transitions retired in ~575 and ~533 ms respectively. This isolates surviving Python ownership after Qt teardown. Inspect `QuickDisplayUnit.runtime_retirement_roots`, `QuickDisplayUnit.retire`, `QuickDisplayVisualizerOwner.retire`, `DisplayManager` manager-unit-owner detach / pending lambda lifetimes; do NOT simply raise the eight-second barrier, force object destruction, call gc indiscriminately every frame, or attribute a Python owner leak to bucket construction. Run strict owner destruction tests after high 3D modes and ordinary modes; report exact surviving strong-reference edges and why only this generation retains them.

### 28.2 Ray signal-path candidate, exact changes

Former ray target: `0.35 * level + 0.45 * body_small_envelope + 0.05 * sustain`; positive onsets primarily affected integrated `shimmer`, so the fan might look bright once and then visually unchanged despite music evolving. This pass adds an **independent ray-only body reference**, a bounded **positive phrase-difference follower** (0.07 s attack, 0.62 s release), event `ray_lift` admitted from real onsets once (0.42-s release, then 0.12-s brightness attack), and a held mix with reserved transient headroom (`0.24*level + 0.26*small_envelope + 0.06*sustain + 0.23*ray_phrase + 0.32*ray_lift`, followed 0.12-s attack / slow release). `snapshot.rays` is sent *directly* to existing `ray_strength`; no additional flash lift is added on snapshot and no new audio floor or clock. Synthetic uninterrupted segments (90 Hz, 2 s each, onsets every .5 s, `soft(.10,.10,.10)`, `loud(.72,.65,.58)`, `mid(.46,.48,.33)`, `fast(.85,.89,.70)`, `release(.32,.23,.15)`) show soft-section final driver ~.17 (with synthetic onsets), loud crest ~.76, loud held ~.50, lower section ~.29, fast crest ~.75, and final softer section ~.25. **These are logical uniform drivers, not measured visual intensity.** Need native ray-only frame luminance charts over the same song with stable camera/exposure, deep/surface lenses, Ray Strength endpoints, P1/P7 and bloom, including occlusion interactions. Transient lift must not become strobing. No accepted state change.

### 28.3 Particles were moving, but not from the authored stream source

`SPECK_VERTEX` already generated up to `SPECKS_FULL=216000` glitter instances per frame. The vertex generated deterministic seeds, lit colours and `fract(seed + uStreamWorld * uSpeckTravel / (2 * uWorldHalf))`, which **does move** particles along stream direction and wraps at volume boundaries; unlike ordinary bubbles, each seed starts distributed throughout the box and not at the two-node physical Source. Particle colour and bloom were artistically useful, P7 especially. Candidate changes ONLY speck path progression: admitted legacy/new physical `Stream Source -> End`, progress fract around the finite path, broad seeded transverse scatter, 0.30× existing integrated stream distance (including idle), edge fade from origin and toward exit. No CPU per-particle step, new timers or extra buffer uploads; the vertex shader uses existing per-instance seed and uniforms. User may prefer a different width, density, or relative speed after viewing, particularly at short/diagonal paths. The existing independent procedural snow and fizz are **not** migrated in this slice and must not be claimed coherent. Existing `Particle Glow` remains exactly authored; `Glow Reactivity` default 0 allows optional positive glow lift from already-simulated ray/flash (without an extra envelope). Verify emission threshold temporal fade when the draw **instance count** changes, not only the path edge fade; the current draw count still changes with emission, potentially causing popping at both ends of the range. Compare real 3D movement, not just source-level motion assertions.

### 28.4 Gates, remaining work

Standalone Qt-free gates `python tests/test_extruded_bubble_ray_particle_candidate.py`, `python tests/test_extruded_bubble_display_only_smoothing.py`, and `python tests/test_extruded_bubble_population_candidate.py`. Extend existing optional `python tools/visualizer_replay/eb_shaft_mesa_compile.py`: GLSL 4.5 offscreen syntax/link for **both** shaft pair and new particle pair. Native Windows GL 4.6 at real card sizes, Qt lazy UI/preset save/load, logged Ray Strength luminance A/B, GPU p50/p90/99 and *visual operator acceptance* are all outstanding. The full pytest harness cannot run in this tool container without PySide6. No original presets changed. All original failure checkboxes remain open; this is a source candidate/checkpoint, not a success report.


## 29. Uniform vec4 production crash and shared procedural Stream Source/End (2026-10-20; UNACCEPTED)

### 29.1 Operator crash, confirmed causal mismatch

The operator supplied an immediate renderer exception at 23:40:27 after the R28 ray-phrase/attenuation slice. The shaft program's `uBlock0` was a tuple `(x, y, z, radius) = (-10.840106010437012, 1.3623005151748657, -17.55120849609375, 0.052287131547927856)`. `rendering/quick/visualizer/implementations/extruded_bubble.py:_Uniforms.set` accepted 1, 2, 3, 9 or 16 values, not 4, and raised `ValueError` on a *valid* `vec4` uniform. The shader uses `uniform vec4 uBlock0/1/2/3`, introduced for bounded bubble light attenuation, so this is a host-dispatch error, not proof of faulty bubble coordinates, a bad GLSL shader or scene corruption. The code now dispatches length-4 tuples to `glProgramUniform4f` and moves the per-program value cache assignment to **after successful upload**, preventing a failed first attempt from concealing later retries. An exact-value Qt-free test executes the real `_Uniforms` class with a recording fake GL, repeats the upload for cache validation, and checks that unsupported values do not poison the cache. The full native shaft pass including zero-bubble filler and multi-bubble transitions remains `[~]` until native 4.6 render/visual acceptance.

### 29.2 What a spatial fade does and does not guarantee

A seeded GPU particle with `progress = fract(seed + integratedTravel / pathLength)` and opacity `smoothstep(0,begin,progress) * (1-smoothstep(end,1,progress))` is nearly invisible while wrapping from End to Source, provided it retains stable seed, identity and continuous travel. This is already the intended decorator-speck path, whose draw instance count is **fixed for a chosen detail tier**, not tied directly to music. Music affects speck brightness/glow and authored particle response. The earlier generic warning that musical emission changes the *speck instance count* was incorrect; correct that assumption in future investigation.

Free chains and marine snow did NOT yet follow the operator's authored two-node Stream Source/End in R28: their GPU vertices seeded positions across the world and wrapped by axis. The new candidate supplies the same admitted `stream_path` world source/end to the bead generator used for **free** chains and marine snow. A stable per-chain transverse offset and coherent curvature accompany an integrated, finite path, with origin/end fade and world-bound clip. Free marine snow now uses the same physical source and travel direction and per-instance origin/end fade. Existing `uBeadTravel` and `uSnowDrift` retain their independent integrated-speed multipliers. `uChainFill` and `uSnowFill` still interpolate the last fractional allocation; this is not a new emitter owner or admission clock. Preset values are untouched. Camera remains a viewer of the fixed world, not the object-position authority.

**Important exception:** fizz is NOT an independent free stream and must stay attached to its parent bubble. Its producer reads the `EbWakes` stable owner records, already has a tail-progress source/exit fade plus retirement wipe and still travels relative to its parent. Reanchoring those fizz dots at a global scene Source would be a new disconnect bug. Test attached fizz separately from free chain/snow emission and count transitions.

**Open discontinuity:** when `ceil(uChainFill)` or `ceil(uSnowFill)` increases rapidly, GPU instance seeds added that capture already have a nonzero path phase. The path-edge fades do not guarantee a fade-in for such a newly admitted ID. Reducing a count can likewise retire more than the fractional final instance in one logical step. Test stable ID/world progress, active shader opacity and screen pixels across a population step. If observable, a per-ID birth/retirement age on the existing simulation clock or a bounded cohort owner would be needed to guarantee full fade, rather than simply changing two smoothstep cutoffs. Strictly avoid claiming EoL fades imply no pops.

### 29.3 Regression / operator gates

- **Crash regression:** `python tests/test_extruded_bubble_uniform_source_parity.py` executes the actual Python upload dispatcher in isolation and asserts the exact `uBlock0` tuple reaches `glProgramUniform4f`. It also verifies caching only after accepted uploads, shared path wiring, source/end fades and parent-fizz identity separation. The earlier `test_extruded_bubble_ray_particle_candidate.py` assertions are updated from separate speck path normalization to the stronger *one admitted shared path* contract. The existing native speck GPU test is likewise updated to supply actual physical source/end uniforms and test camera-independent live world positions (unrun here: native Qt/PySide6 missing); the former whole-box uniform-distribution oracle is no longer a legitimate requirement for a finite directed stream. Do not weaken native tests or visual checklist items.
- **Shader diagnostic:** `python tools/visualizer_replay/eb_shaft_mesa_compile.py` compiles and links shaft and speck programs and the procedural bead vertex with a minimal diagnostic fragment on Mesa GL4.5; the diagnostic alone substitutes `#version 450`, plus it neutralizes fragment-only `fwidth` in an otherwise unreachable shared vertex function when testing bead stage. This is **not a production GLSL change** and says nothing about NVIDIA GL4.6, draw correctness, opacity, glass material or frame time.
- **Native mandatory:** open P1/P7 from dormant and rapid Settings transitions; try finite ray attenuation over bubbles large/small and no-bubbles; test vertical surface↔floor, diagonal, reversed and oblique-depth physical stream paths with active drifting particles/free chains/snow/attached fizz; verify 30% speck carry, native pop-free birth/exit during fast music/count changes and source editing, and camera orbit/parallax. Compare identical Ragdoll 512 and 256 audio capture blocks with per-ID physical target/displayed radius + capture/render cadence; investigate surviving `QuickDisplayUnit` and `QuickDisplayVisualizerOwner` without extending the strict barrier. Entire reaction/art/lifecycle list remains open until visual operator or local-agent acceptance.

**Retained live status:** `[~]` candidate for the vec4 uploader, free-chain and marine-snow physical transport, no-pops property, ray material attenuation and persistent emission; all prior `[ ]` and `[~]` remain unclosed.


## 30. Oblique world editor, independently translatable camera and operator log/suite forensic (2026-10-21; UNACCEPTED)

### 30.1 Camera-distance reconstruction

`logsbae635b6766.zip/screensaver_verbose.log`: at 00:02:19, :24, :36 and :50 on 2026-10-21, the live view pose repeatedly persisted `extruded_bubble_scene_scale=2.0`. The spec range is `.5..2.0`, so native gestures hit their numerical ceiling. `physical_camera` had `ORBIT_DISTANCE=15`, one fixed pivot, no explicit XYZ eye input, pan [-.5,+.5], and a `SURFACE_Y-.5` ceiling. A centre dolly distance of 7.5 at Scale 2 doesn't guarantee proximity to particles throughout the world ±18 XZ, ±8 Y. This is a source-owned access restriction consistent with the operator's observation. Log does not contain a measured particle-to-camera range, so do not claim precise eye/pixel distance.

Source candidate: `extruded_bubble_camera_position` is a default-zero normalized *physical translation offset* to the SAME renderer eye. The camera function computes ordinary orbit/pan/dolly first, then adds `offset[i]*WORLD_HALF[i]`, clamping only above the water ceiling. Range ±8 each axis leaves ability to reach any normalized scene point even from extreme legacy orbit positions; direct picker dragging restricts the desired eye to the actual authored scene. Pan translation becomes aspect-independent in world units, which changes world displacement per displayed card pixel relative to earlier builds: explicitly visual-check gestures. Lens FOV has not been modified and no lens-shift code is reintroduced. Shader eye origin already propagates through render passes. Camera Home `R`/glyph now also zeroes this translation and retains the selected operator-authored preset pose plus canonical FOV.

### 30.2 Volume editor architecture and open checks

New EB-only `SceneVolumePath(ScenePath)` displays existing six-element path values through `SceneVolumeMapper`: oblique 3/4 cylindrical world cage, same XYZ SSOT as simulation and shaders, two marker handles in distinct colors, camera diamond, and neighbouring stream/light/ray paths shown faintly in each other's panel. Drag XY at unchanged Z, Shift/right-drag depth at unchanged XY; Tab selects which of the two endpoint nodes for keyboard arrows and PageUp/PageDown. On camera diamond drag in any panel, the same model-owned `extruded_bubble_camera_position` value goes to the existing `collect_spec_mode_settings` and save flow. Camera bucket separately exposes its camera-position editor. `_refresh_eb_volume` reuses the single renderer camera math and values in both built controls and unopened lazy-bucket cache; full preset load and first-open hydration explicitly repaint dependent editors. The older `ScenePathMapper` class remains untouched for future/non-EB consumers. No new time source/renderer ownership or update loop.

Open: PySide6 is absent here, so actual native Qt first-open, hit testing, theme paint, signal connection lifetime, full preset-change/bucket-order saving, 3D perception, eye/near clipping, frame cost, physical particle approach, R reset, perceived pan scale and GL4.6 composition are **NOT** accepted. Source and input math tests only. Avoid adding polling or increasing lifecycle timeout. Preserve the live failures for peripheral perspective stretch and near-field changes that are unrelated to ability to translate the eye.

### 30.3 Chunk result triage / accurate status

The 22:17–23:55 run results provided by operator collected fully, then all four chunks failed. Aggregate 102 failures, 7,993 passes, 1 skipped; complete logs retained in operator handoff, not inside the main Godzip to avoid bloat. Some contracts still expect eager EB buckets or two-value direction arrays and cannot reflect the new documented design. Others are concrete regressions requiring investigation: recorded-large/small breathing excursion under 1.8 threshold (measured median 1.7506), pause first-frame smooth-release failure, and GPU coverage discrepancy ~1.698 versus expected ~1.269. Do NOT unconditionally label these failures stale. The prior `uBlock0..3` four-float upload error was logged repeatedly (693 render-node errors); a candidate fix exists in R29 and needs a targeted native verification instead of re-running the entire suite. Frame-trace/HUD show occasional long frames but the log does not isolate them to camera navigation; no performance improvement can be concluded.

`logsbae635b6766.zip/screensaver_lifecycle.log` shows timeouts for Settings at 22:42:58 on Oct 20 and application exit at 00:03:21 on Oct 21: each records no remaining tracked Qt resources, but one Python `QuickDisplayUnit` and one `QuickDisplayVisualizerOwner`. Keep barrier strict and investigate referrers of the generation-scoped owners after tracked resources retire.

### 30.4 Validation and accountability

Candidate test: `tests/test_extruded_bubble_volume_camera_candidate.py` verifies every existing directional default migrates to same six-number path, world translation of real camera reaches representative physical interior source points without changing lens matrices or orbit basis, pan is aspect-independent in world coordinates, old shared widget is retained and camera Home has one canonical zero offset. The full chunked suite need not be rerun; use minimal Qt-native tests in the next operator/local-agent pass. Keep every visual checklist item `[ ]` or `[~]` until accepted by operator or local agent.


## 31. Mode-scoped physical flight and EB Settings failure (2026-10-21; UNACCEPTED)

### 31.1 Operator intent and routing

The prior Q exit bind was expressly revoked. EB framed only: Q/E rotate yaw left/right, Shift+W/S pitch up/down, and W/A/S/D physically translate the eye relative to current facing; forward includes the existing 16° home pitch and selected tilt, A/D use the true view-right basis. These key holds coexist with Alt-left orbit, Alt-right pan, card Alt-wheel scale and R reset; they are **different controls**. Lens FOV, camera scene scale, preset artistic geometry and input audio are never modified by flight. Spectrum and Sphere still use legacy WASD orbit. No Neon Lake behavioral change is authorized here, merely an audit requirement: future framed-flight admission for that landscape must keep the camera above terrain, retain its accepted vertical tilt/geometry bounds and prevent viewing the world from beneath the land surface.

`RuntimeInputOwner` publishes one 4-component held-flight intent on actual press/release or shift-modifier edge, not OS repeat. `QuickDisplayRuntime` relays it through existing live display-generation routing to `DisplayManager._set_quick_framed_flight_rates`; only EB admits it. `widgets.spotify_visualizer.view_orbit.py` owns `FramedFlightMotion` and the same physical view-basis formula as `rendering/gl_programs/extruded_bubble_scene.py:camera`. At logical capture time, the immutable motion record maps world-space translation into the preexisting 3-component normalized `extruded_bubble_camera_position`; this is the *only* camera position attribute the shader reads. Simultaneous yaw+flight integrates facing over elapsed time in bounded substeps; no per-frame state writes or timer and no new renderer simulation. At each key transition, settle previous travel into the single presentation authority before rebasing the next record; when the last key/drag ends, persist orbit and real XYZ translation once through the existing Settings owner. Q is no longer a global exit key. The shortcut `R` and glyph clear held motion and position offset.

### 31.2 Native first-open crash

Operator stack at 2026-10-21 00:44: `_select_mode_page → VisualizerModeBodyHost.ensure → build_extruded_bubble_ui → build_spec_mode_ui → build_bucket → _build_control → _build_visual_control → QLabel(describe(widget.value()))` fails with `UnboundLocalError: describe`. When `SceneVolumeMapper` replaced the original path widget, its new `(SceneVolumePath, SceneCameraPosition)` branch omitted `describe = control.text` and `widget.setValue(value)`. Both are now initialized like the other visual controls before the label and signal subscriptions. Repeated failures explain inability to open EB; they are not evidence for a longer lifecycle timeout. Native construction and subsequent bucket-hydration/signal-retirement validation remain required; no barrier relaxation, eager rebuild or swallowed exception. The one QFont invalid point-size warning cannot be causally assigned from the stack and requires separate investigation if it recurs.

### 31.3 Evidence, limits, acceptance gates

Pure mathematical/source regression `tests/test_extruded_bubble_flight_navigation_candidate.py` covers camera-relative forward/strafe, reverse, simultaneous yaw+travel continuity, fixed FOV, settled single-owner offset, mode exclusion and the `describe` branch. `tests/test_extruded_bubble_flight_keyboard_native.py` is a focused Windows PySide6 keyboard/Settings-construction test: unrun here because PySide6 is absent. Also validate Windows native pressing Q/E and Shift+W/S from both displays, mouse-plus-key overlaps, key-auto-repeat and focus loss, Ctrl interaction and Edit mode, reset during held keys, mode/preset swapping, customized authored camera pose persistence and scene bounds. Test movement inside P1/P7 streams without unexpected FOV/zoom, and judge feel/constant-speed and clipping physically on-screen; synthetic records DO NOT amount to visual acceptance.

**No existing defect or milestone is marked accepted.** All EB size, temporal, reactivity, rays, particles, emission, projection, large/small bubble, native Settings lifecycle and previous log failures remain active exactly as documented in the live plan and preceding sections. Do not demand another chunked suite.


## 39. SCENE floor inlet distribution and alleged early bubble death (22 October; all unaccepted)

**Operator evidence.** Two SCENE captures at 00:52:32 and 00:53:12 show decorative particle groups remaining in conspicuously localized regions, only sparse physical bubbles across the frame, and an apparent absence of bubbles near the visible Sunlit Surface. The focused native Settings test reports 9 passes; it tests mode admission and controller construction, not whether pixels satisfy an aquarium-wide distribution or whether bubbles physically die at the observed screen height.

**Log provenance.** The 22 October run selected `extruded_bubble_emission_geometry='SCENE'`, an authored floor/upward stream (Source Y = -1; End Y about 0.87–1), Sunlit Surface, large-count handles [1,8], small-count handles [7,55], 256-sample audio. These current operator-authored values can legitimately leave a sparse 36×16×36 volume. Do not overwrite them or automatically raise `MAX_BUBBLES`. No per-ID world-position/exit-reason trace is available in the supplied runtime log, so it cannot prove a collision death or even true death rather than leaving the camera view.

**Confirmed shader shortcuts relevant to clumping.** The SCENE `sceneInlet` sampler previously generated a floor-face Z coordinate by applying `fract` to a mixture of independent UV samples; that introduces transverse correlation/nonuniformity absent from the CPU physical-face sampler. More importantly, the speck shader always applied BEAM's sine-cloud *visibility mask* on the global seed before sampling the actual SCENE path. Hence a world-wide source could still produce isolated bright cloud patches. The R45 source candidate maps each face's two transverse coordinates directly from separate uniform seed components and, for SCENE only, applies a bounded seed-based visibility threshold, retaining authored band/cloud variation in brightness rather than dropping spatial patches. BEAM math, source/exit identities and preset choices are unchanged. Tests must still inspect actual native pixels and costs. No new render passes, clocks or persistent allocations.

**Early surface claim remains separate and serious.** Simulation logic normally starts Sunlit Surface departure when centre Y reaches the shared world plane `WATER_SURFACE_Y=9`, but camera projection, render-layer branch, world side bounds and logical death causes must be distinguished before concluding why large bubbles appear to vanish halfway up the screenshot. SCENE distribution means collision is not a credible default explanation; do not use it as one without a recorded Pop/contact. The R44 G04 and G09 gates require a captured stable ID, alpha and true world→pixel projection at the same time as the visible water. Do not move the surface Y, fiddle with FOV, weaken lifetime fades, or mark this accepted from the new distribution correction.


## 40. 22 October source audit: lighting authority, finite beam width and persistently clustered SCENE (UNACCEPTED)

This section supplements §39 and all earlier measurements; it closes **nothing**.
The operator supplied a new screenshot (preserved at `Evidence/2026-10-22_SCENE_operator_rejected_clustering.png`) showing SCENE emission **still visibly
clumped** after the R45 handoff. Narrow bright islands across the lower water
remain, with dark gaps; the larger bubbles are sparse. A still validates the
visible grouping complaint, not physical world coordinates or the exact current
exe commit. R45 source changes may or may not be the exact binary used: capture
the native build/source provenance alongside screen and uniform evidence. The
clustered visual result is rejected `[~]`; G07/G08/G09/G32 remain open.

**Important correction to former reasoning:** low population demand explains
sparsity, **not narrow groups of actually distributed points**. Do not present
counts as the source of spatial grouping. Do not quietly conflate emission
clumps with light/bloom-localized visibility or the still-separate apparent
Sunlit Surface premature bubble disappearance (G04/G09).

**Additional possible mechanism: historical cohorts on emission-mode change.**
Ordinary simulation bubbles persist as `_bubbles` across controls changes;
`_spawn` consults the current `emission_geometry` only for a *new* birth.
Switching BEAM→SCENE is not a command to relocate already-living BEAM
bubbles. This explains why a scene *could* remain grouped after switching, but
**cannot** explain clustering on an independent direct-cold SCENE start without
a different mechanism. Tag stable IDs with admission geometry and age for the
three controlled source-mode histories; preserve continuity, never forcibly
teleport/delete or visually hide old populations to make a quick fix. Compare
physical bubbles, procedural free chains/marine snow/specks, attached fizz and
actual HDR/luminance pixels separately; the latter can group even with a
well-distributed physical inlet because of masks/light/occlusion.

**New source findings for P1 and P4, not yet implemented:**
- `extruded_bubble_scene.py:MODES["surface"]["shaft_fan"] = 1.0` favors
  a view-direction-based fan. Its `SHAFT_FRAGMENT` camera-relative `fanExtent`
  probes at 12 and 23 units and `labShaftFan(viewRay, ...)` can dominate the
  marched world component; seeing thin/wrong/down-view beams follows plausibly
  from this architecture but still needs native camera A/B.
- `extruded_bubble_program.py:SHAFT_FRAGMENT:beamExtent` gates projection
  `along` the Source→End axis only. It does **not** measure lateral distance,
  so the raw extent is a pair of parallel slab boundaries rather than a real
  bounded tube/cone. Procedural noise only disguises that geometric defect.
- Surface light is directional (correct for the sun) while the Settings light
  source **position** is misleading. Deep uses physical source coordinates,
  but its visible glow is primarily the angular `dot(viewRay, normalize(
  lightSource-eye))` and high exponents with no proper world-space distance
  attenuation. `scene_knobs` aligns deep ray start to light start, not all
  water/glint/shaft illumination consumers into a coherent positional field.
- Existing shaft attenuation uses four physical bubble `vec4` proxies
  (`uBlock0..3`) plus an aggregate particle term; this is a bounded
  approximation, not volumetric shadow parity. No expensive shadow-map
  mandate follows from noticing the limitation.

**Next architectural repair order (not a second task queue):** G05 audit all
light-to-pixel consumers → G05/G06/G27 unify physical emitter and truthful
light field → replace angular placement with bounded world-space scattering,
lateral extent and Deep distance falloff while keeping existing half-resolution
optics → G05/G27/G30 add a separate proposed Lighting Coverage BEAM/SCENE
under existing Light Type only after correctness → G06/G27/G32/G33 native
all-angle, shader, pre/post-bloom, CPU/GPU p95/p99 and P1–P7 acceptance.
Lighting Coverage is entirely separate from Motion Emission Geometry, and
current authored presets/Custom must not be overwritten.

**Primary detailed plan with fixed falsifiers:**
`Lighting_Authority_Repair.md`; sole live task ownership remains the G00–G33
items in `Current_Plan.md` §4B and the corresponding runbook. All previously
failed/partial tasks and their evidence remain unaccepted.

**Local native measurement receipts (22 October):** `Evidence/2026-10-22_world_authority_p1_verified`
and `Evidence/2026-10-22_world_authority_p7_verified` retain frozen 4-second `anything_mixed2`
states, fifteen native NVIDIA views each, source hashes, physical eye/lens and unchanged world IDs.
These are BEAM/current-preset baselines, not the operator's SCENE reproduction or fixed-eye shaft parity.
`Evidence/2026-10-22_ray_authority_p1_baseline` independently intervenes on ray driver/softness at
3 seconds: both controls reach native pixels. It does not establish within-song responsiveness.
All captures are offscreen; first-draw compilation/readback and changing views invalidate performance
claims. The former native silhouette red was a clipped fixture at the narrower lens, not demonstrated
product projection failure; its whole-ellipse oracle now requires analytic sensor clearance.

`Evidence/2026-10-22_light_strength_p7` retains the diagnostic producer and same-recording native
P7 before/after images (4.004295 seconds, yaw 0.5, 2560×1440, four identical logical bubbles).
Only the analytic highlight consumer changes from its former strength-independent radiance to the
authored 0.12 strength. Native isolated reflected/transmitted tests establish proportional intensity;
this full-frame still does not accept P7 art or the remaining lighting geometry. Cold first draws
make the recorded GPU times unsuitable as a before/after performance comparison.

**Near-lens diagnostic A/B:** `Evidence/2026-10-22_near_lens` preserves the producer, baseline
shader revision and hashes, and native ordinary/fused diagnostic images at 25/50/85/102% of
viewport short-side diameter. At zero aperture the former shader stays sharp through full-frame
coverage; the candidate visibly blurs at half size and fades/culls at extreme size. This is a
controlled white-silhouette/defocus comparison, not real-music or authored-glass acceptance.
Native off-axis crossing and sparse-union regressions guard against hiding valid grazing geometry;
logical populations are unchanged. The existing P1/P7 visual and cost gates remain open.

## 41. Native idle comparison against 2D Bubble (22 October; FAILED)

The operator rejected the source-level inference that EB bubbles visibly satisfy idle. Native production-host
captures at 1672×941 confirm the rejection. `Evidence/2026-10-22_idle_comparison/` retains `run.py`,
`settings_input.json`, `capture.json`, full-resolution frames, paired contact sheets and `idle_layers.png`.
The input is the first ten seconds of `anything_mixed2.jsonl`, then explicit paused zero-input for sixty
seconds at 90 Hz. Frames show music end and 5/30/60 seconds idle. Comparisons cover current curated 2D P1,
saved EB fields and current curated EB P1/P7; no art controls are retuned. The saved mapping is not proof of
an unsaved live controller state. Source revision/status, producer hash, input hash, settings and native GPU
identity are retained. Final capture reads only the saved input mapping and performs no Settings writes.

**Observed failure:** 2D retains a clearly visible small-bubble field. EB's ordinary layer is almost empty;
the prominent larger shells/vertical strings in the full Surface view are mainly free chains. Diagnostic
pass isolation uses the exact same idle state/camera and suppresses procedural layers for ordinary-only,
or ordinary/wake geometry and other procedural layers for chain-only. It does not retune physics or source
positions. Fading chains alone will expose the nearly empty ordinary field rather than repair it.

At sixty seconds idle, saved EB/P1 contains 28 ordinary records, but the existing physical eye/FOV/sphere
frustum estimate admits only 3 candidates; P7 contains 26 ordinary records and admits zero. P7 also has zero
ordinary candidates at music end in this window. These are conservative geometry estimates, not a claim
that every candidate yields visible pixels. Global residency and nonzero stream speed are insufficient
visibility evidence. Do not transfer the accepted 2D radius units directly into physical EB world units.

Source/geometry audit explains a concrete coverage confound. Saved EB/P1's BEAM runs from `(0,-8,0)`
to `(0,8,0)` through the camera's world plane, with a 4.95-unit transverse patch half-width, while the
default eye looks forward along -Z and upward 16 degrees. P7's left-entry path spans about 38 world units;
after this warmup/idle window its ordinary cohort is still approaching from the left outside the lens.
Settled stream speed is about 0.0371 world units/s. This is not a stopped clock, but neither is it proof of
a visible, continuously replenished field. Trace physical transit/occupancy before changing optical size.

**Next falsifier:** trace the authored physical source patch/path and stable-ID projection against ordinary
glass-only native pixels, including cold idle and a long physical source-to-exit interval. Separate low
frustum occupancy from radius/material invisibility. Preserve the camera-independent scene, count endpoints,
zero authored amounts and strict physical lifetime; do not fill the viewport with camera-relative births.
Then verify the requested chain opacity fade and retained, smaller, glow-free particle field. Still frames
do not prove no breathing, slow travel, source births, breach/exit or idle→active recovery. These offscreen
native renders are not actual compositor-window, mixed-DPR, dual-display or performance acceptance.

## 42. Retained SCENE pose and physical fade isolation (22 October; coverage still FAILED)

The later operator image `Evidence/2026-10-22_SCENE_operator_empty_swath.png` shows a broad empty lower region.
Local logs archived in `Evidence/2026-10-22_SCENE_retained_pose/logs/` establish cold SCENE at 20:42:17,
upward floor flow and a nearby saved camera rotation at 20:48:48. They do not establish the exact screenshot's
loaded source revision, pose or audio. The screenshot file's later creation time is not loaded-code provenance.
No operator reproduction is required to investigate these retained inputs.

The native reconstructed-pose producer freezes recorded four-second input and the same seeds/counts/travel,
then separates tank ray length, flat occupancy, entry/exit fade, lateral boundary fade and final lighting.
It explicitly compares the earlier loaded pivot and the current fixed-tank pivot. With the retained offset,
the latter eye is outside the near tank face: lower image rays see a much thinner finite population volume,
while the water backdrop continues. This is a conditional reconstruction, not proof of screenshot equivalence.

An independent defect is proved inside the actual tank. The former percentage-of-tank lateral fade compounds
with the long percentage-of-track entry fade, almost erasing near-wall interior samples. The native generator
regression pins valid points at `(0,-7.5,0)` and `(0,-7.5,17.9)` while holding seeded light constant; the old
near-wall result is roughly 1.17% of the centre result. The physical-fade candidate gives both full interior
visibility while retaining zero entry/face/outside opacity and a smooth outgoing fade.

SCENE specks, snow and free chains now share footprint-scaled entry/exit/wall-crossing distances, capped on
short paths. Chain offsets still use their actual positions for containment. BEAM formulas and attached fizz
are unchanged. `Evidence/2026-10-22_SCENE_physical_fades/` retains the producer, native images, shader hash,
frozen-population parity and bounded GPU-query samples. Flat occupancy pixels are identical before/after in
both reconstructed poses; BEAM final pixels are byte-identical in the old/new generator comparison. In the
thin lower-quarter diagnostic, mean unlit occupancy was 0.0893, old faded output about 0.0005 and candidate
output 0.0893 (8-bit image means, not physical luminance). Moving birth/exit smoothness and installed costs
still need validation. No pass, instance count, world position or camera-relative population is added.

The large coverage complaint stays open. Do not mistake the narrower opacity repair for full tank/framing,
ordinary-population, physical illumination or backdrop-domain acceptance. The cold-SCENE log also disproves
inherited BEAM cohorts as a universal explanation for this report. GPU query medians from these offscreen
captures are not an isolated performance comparison or proof of a speed improvement.

## 43. Surface analytic direction and controlled MC activation (22 October; narrow candidates)

The G05 source map found a second Surface emitter: water/particle/probe glints followed refracted authored
sunlight, but analytic reflected/transmitted glass lobes used world-up. `scene_knobs` now resolves the
refracted direction once and shares it with Surface glass, leaving Deep and authored state untouched.
The native regression crosses authored oblique light paths through `_glass` into ordinary, fused and both
near variants, subtracting emitter-off float HDR pixels to measure the highlight's directional movement.
It includes a roughly 3.9px-radius ordinary shell: reflection still moves while the existing sub-8px
transmitted-lens suppression remains explicit. The near fixture must enable actual aperture/focus admission;
an otherwise zero near image cannot test direction. Translating both Surface endpoints preserves direction.

`Evidence/2026-10-22_surface_light_direction/` retains the frozen four-second recorded P1/P7 A/B, native
frames, hashes and producer. Only the former versus shared Surface analytic uniform changes. P1's native
highlights visibly shift consistently with the directional repair; P7 Deep's mean RGB code delta is about
4.24e-7 (two total 8-bit channel steps), not a claim of byte identity. First-draw timings include shader
preparation and are unusable as performance evidence. This does not repair Deep positional analytic light,
strength-independent glint proxies, the world-space shaft field, SCENE coverage or idle readability.

The earlier fixed-pivot idle capture admits 27/28 P1 and 5/26 P7 ordinary IDs at sixty seconds, compared with
3/28 and 0/26 before it. P1's median projected radius is only 4.5px. Native ordinary glass remains weak after
chains fade and particles retain their smaller glow-free idle appearance. Small-shell analytic reflection
fades over 2.5–10px and transmitted light over 8–24px, so emitter direction cannot alone establish idle
visibility. No size/count floor, preset rewrite or camera-relative replacement population is introduced.

Latest MC source receipts: `logs/run_matrix/2026-10-22_mc_after_idle_scene_fades/` retains three idle
Settings restarts after the candidate changes. `2026-10-22_mc_controlled_active/` then invokes canonical
owner play-state admission four times through a disposable, weak-engine, one-shot driver. Real WASAPI
loopback capture starts at block size 256 and actual DSP publications occur; no synthetic PCM/source or
product timer/retirement override is added. Paused canonical Media overrides the stimuli after roughly
0.05/0.55/1.06/4.06 seconds, so these are controlled activation/warm-capture retirement checks, not sustained
music or audiovisual acceptance. All six Settings barriers complete in 0.70–4.97 seconds at the unchanged
eight-second limit, with zero scoped lifecycle errors and normal CLI exit 0. The strict retained-owner
failure is not reproduced. All useful CLI diagnostics and normal updates stay enabled; no `--noupdates`.

## 44. Glint-proxy intensity authority (22 October; native candidate)

Proxy emission remained fixed at Surface 10 / Deep 2.5 while authored Light Strength already scaled the
visible emitter and analytic glass. `scene_knobs` now resolves that existing mode gain times Light Strength
once; the renderer requires the resolved value rather than maintaining a second default. Strength 1 retains
the former power. Positions, radii, lifetime opacity, source direction, instance counts and draw passes stay
unchanged; this is an amplitude correction, not a density/performance change.

The native production-host regression captures all six faces of the actual half-float reflection probe,
subtracting a proxy-zero control at identical scene/light uniforms for each strength. Both light modes now
give no proxy HDR contribution at zero and twice the half-strength contribution at full strength, allowing
only half-float quantisation. The test also checks unchanged uploaded spatial records and the existing
full-strength gains. Before the repair, both modes fail because zero strength still uploads full power.
Connected renderer/particle tests pass. Native moving P1/P7 art, self-proxy appearance, small idle visibility,
Deep per-shading-point direction, shared positional attenuation and the physical shaft field remain open.

## 45. Deep analytic direction at physical glass points (22 October; partial candidate)

The earlier Deep lobe used a single authored Source→End direction even though visible emitter/proxy placement
used positional Source. Moving End with Source fixed therefore moved native reflected/transmitted highlights.
The regression reproduces that failure before repair. Deep now resolves Source direction from each local
interface/exit transformed by sphere radius/centre and the actual camera eye/basis. Surface keeps its shared
refracted direction. The existing tracer returns its already-computed interface hits and final origin;
homogeneous lens refraction returns its matching chord exit (front point on entry TIR). All GLSL/CPU callers
are migrated, without a legacy wrapper or second tracer. The lab explicitly retains its angular reference-art
emitter; it has no physical Deep Source authoring and is not production positional-light evidence.

Native tests cover ordinary/fused/near reflection and transmission, fixed-Source End invariance, real Source
movement, rigid translation and a non-symmetric rotated camera/world configuration. The fixture must reset
its eye between draws; retaining a prior intervention's uniform creates a false invariance failure. Shared
CPU/GPU mirrors compare all eight path slots and origins, including inside-core/wall and trapped TIR; a
coincident-source approach stays finite but does not define finite-emitter physics. Fused glass still uses
its pre-existing tangent-sphere material approximation, not exact secondary rays through the whole union.

`Evidence/2026-10-22_deep_shading_points/` retains frozen recorded P1/P7 final comparisons and source hashes.
The diagnostic disables only positional analytic direction, reproducing the former global-direction
consumer in the current tracer. P1 Surface pixels are byte-identical; P7 changes with unchanged physical
counts. This is source-direction evidence, not proof of shared distance attenuation, complete transport,
moving art, ordinary idle readability or full-SCENE coverage. The extra eight local vec3 points can increase
per-fragment register pressure, and Deep adds normalization per lobe (including rim sub-rays). No new
pass/target/clock is added; performance neutrality must not be inferred. A separate true-baseline shader/
optics timing producer retains bounded full-frame GPU queries with explicit limitations.

The initial/reversed-order timing warning prompted a narrower correction before landing: Surface no longer
records or reads unused interface-point metadata. Direction-only tracing keeps exactly the same directions,
weights and traversal; only Deep requests the point outputs. This avoids adding five specialized program
variants and their warm-up/storage burden. Register reservation can still reflect the linked shader's worst
case; this conditional omission alone is not proof of performance neutrality. Preserve the initial, reversed
and optional-metadata receipts; limited single-card query samples cannot close moving/dual-display G32.
The final quiet sequential optional-metadata sample is P1 before/after p50 4.02/4.74ms and p99 7.86/6.48ms;
P7 p50 4.91/4.76ms and p99 6.76/6.87ms (60 samples per condition after eight warm draws). Earlier reversed
samples differ materially. This does not establish a speed improvement or neutrality, and the P1 median
increase remains explicit cost debt. The earlier optional-points receipt marked `overlap_possible` may have
overlapped focused-test warm-up and is excluded from isolated claims. Final native comparisons retain exact
source hashes after optional metadata omission; P1 remains byte-identical with the directional intervention.

## 46. Same-world SCENE retained pose versus explicit reset (22 October; coverage still FAILED)

The bounded Medium audit froze the reconstructed retained SCENE world, then used the actual camera-reset
contract (`starting_camera_pose` for the saved Custom index, canonical FOV/position) as a diagnostic intervention.
No physical records, seeds, count, travel, light or saved profile changed between views. Production final
images, flat speck occupancy and tank ray-length maps are in `Evidence/2026-10-22_SCENE_reset_comparison/`.

In the retained bottom quarter, 17.06% of rays miss the finite tank and 57.63% traverse at most two world units;
mean tank path is 1.206. Explicit reset gives zero missing/thin rays there and mean path 34.215. Flat occupancy
and final native images visibly extend through the lower region after reset. This identifies framing/domain
geometry as a major contributor to the reconstruction, without claiming exact screenshot/source/pose provenance.

The population tank is finite while water/wisps continue beyond it, and legitimate authored cameras can be
outside it. Visible water therefore does not imply a long population path. Separate missing-domain rays from
in-domain opacity/material/lighting loss. Do not darken the backdrop, invent walls, clamp/overwrite saved poses,
inflate counts or enlarge populations around the eye to conceal this mismatch. A required broader domain would
need coherent fixed-world extent/node/presentation design, not an incidental constant patch. The user's whole-
viewable-tank complaint remains failed, with local evidence available rather than a reproduction request.

## 47. Native idle release and recorded recovery (22 October; scoped evidence)

`Evidence/2026-10-22_idle_recovery/` retains the producer, source hash, settings, complete sampled ordinary
records/scalars, selected full-resolution frames, contact sheets and full/chains-only GIFs for P1/P7 on 82467ae2.
Input is recorded `anything_mixed2` first ten seconds, explicit paused zero-input sixty seconds at 90Hz, then
the same recorded passage resumed in the same logical runtime. GIFs show continuous release 0–8 seconds at
10fps, an explicitly labelled jump to settled idle60s, then continuous resume 0–8 seconds. They are silent
offscreen native GL captures, not actual compositor/DPR/high-refresh or audiovisual acceptance.

Per-frame activity gives chain opacity 1 at release, .831 at one second, .018 at two, zero from three seconds;
on resume it is zero initially, .789 at one second and 1 by two. Corresponding native chain-isolated images
show disappearance and gradual return. Particle presentation reaches quarter radius and zero particle emission
activity; P7 retains its fine gold dust while the independently visible emitter/ambient remains. P1/P7 quiet
emission settles to .1/.844 respectively, reflecting their authored low endpoints rather than another activity
attenuation. The diagnostic chains-only layer suppresses ordinary/wake/snow/fizz/specks on identical full-scene
snapshots; it never creates a replacement simulation.

Ordinary fields still fail the comparison against 2D Bubble. The wall A/B in `2026-10-22_idle_wall_diagnostic/`
shows a concrete material contributor: the current 1.5px minimum wall is far thicker than authored for tiny
shells, and authored 3% walls make several 2–3.5px identities clearer. The existing shell=0 alternative looks
softer/darker and is not accepted air-interface physics. Moving thin-wall stability and radius-dependent
sparkle hashing remain actionable before a production material repair. Neither retained IDs nor sampled
stills prove no physical lifetime/art/motion failure; existing source birth/breach/exit checks are scoped proof.

The latest MC Qt captures also establish zero messages in both valid 21:23 and 21:30 session intervals,
including three Settings reopen cycles each. Appended older `QFont`/`QUnifiedTimer` warnings are not current-run
failures. Shared combo point-size policy is already implemented; editor/bucket-specific warning attribution
remains conditional work, not a reason for another identical idle launch or a claim of a font repair.

## 48. Tiny-shell radius-dependent sparkle discontinuity (22 October; native candidate)

The sub-2.5px ordinary material mixed in a discrete sparkle value selected by
`fract(stableSeed*17.31 + changingRadius*913.7) > .8`. A smooth breathing radius therefore repeatedly
reclassified the same physical identity between brightness .2 and 2.5. The native production-fragment
regression straddles one threshold with a radius delta of only 2e-7 world units: unchanged camera/identity,
negligible projected geometry change, but the old integrated RGBA difference is about 12.1% of the two
frames' combined energy. This is a proved material step, not proof of discontinuous simulation radii.

Sparkle membership now uses the existing stable seed alone, matching the identity policy already used by
the dedicated micro-glass branch. The native threshold bar passes below .1% relative change, alongside the
connected geometry/near/lifetime/wake checks. No new floor, interpolation, state, pass, timer or random owner
is introduced; the obsolete radius multiply/add disappears. The small-shell wall policy is unchanged.
Recorded musical motion, perceived idle visibility and 256/512/2D breathing comparisons remain unaccepted.

## 49. Latest saved-pose active/idle rejection reproduced (22 October; both FAILED)

The operator's latest pair shows a populated upper strip over empty lower water during playback and essentially
background-only idle. Originals and contemporaneous logs are retained in
`Evidence/2026-10-22_operator_active_idle_rejection/`. The 22:17:17 source run identifies `f60f9581` and cold
SCENE/Custom index 7; its saved camera has turn .0506971, tilt -.2253051, scale 1, zero pan, FOV45 and normalized
position offset (.320911,-1.110771,1.90208). No intervening camera gesture/reset is logged before the pause at
22:18:09. Clipboard creation times are not exact capture timestamps, and the actual screenshot audio/seed/frame
timing is unrecovered. Do not claim pixel-identical reconstruction.

The derived physical eye is (8.1487,-7.7674,49.0063). Against the fixed half-extents (18,8,18), 62.71% of viewport
rays and the entire lower half miss the actor domain. This is an actual camera/world/backdrop mismatch, not a
uniform sampler test failure or a reason to increase counts. Water/wisps extend beyond the actor box. Neither
the earlier reset intervention nor preserving positive physical counts satisfies whole-viewable-tank coverage.
Reconcile the physical camera/offset calibration and fixed populated world with the navigation contract before
tuning coverage; do not silently reset/clamp poses, relocate actors around the eye or inflate global counts.
The bounded source audit verifies flight stores world travel divided by `WORLD_HALF`, and camera projection
multiplies that offset once. The editor legally admits offsets up to +/-8; Z49 is not a doubled-unit defect.
The background has no larger physical tank authority: abyss/plane/angular mist and camera-relative wisps continue
outside the finite actor domain. A larger `WORLD_HALF` alone also moves normalized nodes/camera and dilutes global
counts. Clarification is required between populated open water with density semantics and a visibly bounded tank;
the existing finite-global-count/unrestricted-travel rules cannot guarantee occupied water in every legal view.

`reproduce.py` asserts the saved controls/pose, uses the production native GL host at 1738×1143, plays the first
47 seconds of recorded `anything_mixed2`, then advances explicit paused zero input at 90Hz through 5/25/60s.
`same_saved_pose_layers.png`, full-resolution layers and `reproduction.json` retain state and source/input hashes.
Layer subtraction freezes full-scene ray-blocker uniforms, preventing altered shaft attenuation from being
miscounted as direct object pixels. It independently reproduces the active cutoff and almost empty idle without
changing the profile or resetting the camera. It is offscreen production rendering, not compositor/music playback.

At idle25s twelve ordinary conservative frustum candidates remain, mostly below 1px radius. Their isolated final
image differs from frozen background by >=3 eight-bit channel levels in only 39 pixels (81 at >=1); corresponding
specks reach 1073/4184 pixels. These are raster-contribution measurements, not perceptual thresholds or acceptance.
The full view visibly fails. Preserve quiet source births/travel/exit and zero authored amounts while repairing
readability; in-view IDs alone are insufficient, and distant subpixel shells confound material-only diagnoses.

`compare_radiance.py`/`radiance_comparison/` isolate amount-dependent particle brightness: identical snapshots,
density/counts, seed, quarter-radius idle sizing and zero glow, replacing only `2.4*amount` with constant 2.4.
The quiet field brightens but the same saved-pose image still looks too empty; active art also changes. This is
a diagnostic, not a landed transfer or accepted standalone repair. Particle amount semantics and ordinary Range
endpoint coupling remain explicit design/validation work; do not add arbitrary visibility floors to bless it.

`compare_quiet_endpoint.py`/`quiet_endpoint_candidate/` separately test the existing rest law with the quiet
handle as its owner instead of `max(pair)`. This corrects the proposed authority mapping, but is not landed:
the saved .15 quiet handle raises rest from .13 to .7825 nominal (about six times the radius) and every subcrest
scale rises by .6525*(1-drive); drive-one crests remain unchanged. The native replay gives readable small rings
in the upper field (idle60 ordinary >=3-level contribution rises from 41 to 898 pixels), while overall coverage
and dust still fail. It changes physical admission/contact/clearance, not just presentation. Judge endpoint
independence separately from 2D breathing/minimum-size and connected physical lifetime acceptance; do not land
this merely to compensate for distant framing or silently preserve the former unaccepted .13 test oracle.

## 50. Authored small-shell wall and native camera sweep (22 October; partial material candidate)

The former wall floor `max(uShell,1.5/radius_px)` changed the traced inner sphere with camera distance. At 4px
radius it substituted a ~39%-radius wall for authored 3%, and at <=1.5px it could remove the air core. The native
ordinary/union regression changes authored thickness .03→.3 at identical ~4px geometry: the former shader
produces identical transmission, while the corrected shader responds. Production now retains `uShell`; the
lab's explicit `uShellMin` switch remains separate. Existing optical footprint/rim filtering is unchanged.

`Evidence/2026-10-22_authored_wall_motion/` freezes the actual retained P1 idle60 world records, then moves the
physical camera .08 world units in X over two seconds, sampled at 30fps. Both variants use identical records,
settings and camera path; shader hashes, full-resolution selected images, crop GIF and five sampled crop pairs
are retained. The 2.2–3.5px identities read more clearly as small rings through the sampled movement; this is
bounded offscreen material evidence, not recorded radius-response/compositor/whole-idle acceptance. The latest
Custom domain failure remains open, and ordinary simulation radii/counts/lifetimes are untouched.

Thirty-six connected geometry/near/lifetime/wake checks pass. No extra pass, program, target, clock or sample
loop is introduced. Different shell geometry can change actual tracer work inside its existing bounds; do not
claim neutrality. Sequential full-frame queries during this sweep, after eight warm draws, give previous/new
p50 3.03/3.17ms and p99 5.08/6.45ms on this workstation. This moving short sample does not isolate shared GPU
load or establish production p99 cost; retain the warning for G32 and inspect other authored modes/close glass.

## 51. Shared finite-world camera admission (22 October; native coverage candidate)

The operator chooses populated open water only if populations remain independent of the camera; otherwise the
boundary must be enforced by camera movement. The current finite-world repair keeps global counts, world actor
positions and source nodes fixed. `core/settings/extruded_bubble_camera.py` owns the pure axes/orbit baseline and
joint eye/offset resolution. Three world units of inner clearance preserve the canonical home (minimum clearance
about 3.58) and guarantee that every unit sightline traverses at least three units of the convex population box.
This is an explicit camera policy, not a mathematical guarantee of perceptual density.

Runtime admission resolves the complete incoming pose, including partial angle/pan/dolly/FOV/Light Type changes,
then publishes the effective existing offset. The renderer uses the same resolver. Settings hydrates/collects that
offset and refreshes every special 3D marker before synchronous saves; Aim rebases against the shared orbit
baseline to rotate the admitted eye in place. Native Qt tests include actual arrow-key wall/reversal, all four
editors, closed buckets and nonzero-pan FOV changes inspected inside the save callback. No profile reset or
second eye, presentation owner or coordinate schema is introduced.

Flight integrates wall saturation rather than retaining invisible outward displacement. Constant-pitch horizontal
eye motion is circular (orbit plus integrated travel); split at coordinate extrema, clamp monotone increments,
and evaluate one full cycle plus remainder because the closed-cycle saturation map is idempotent. Y saturates
linearly. This gives bounded work independent of long hold duration, including negative/tiny yaw. Changing pitch
uses .015-radian quadrature until the pitch limit, at most 512 intervals; partition accuracy is tested at actual
keyboard rates, not arbitrary tiny synthetic pitch rates. The limit endpoint is derived once in the existing
immutable gesture, avoiding repeated prefix work after tilt settles. Orbit/pan/dolly settle and rebase that same
record at GUI gesture boundaries. No per-frame write, timer, polling, mutable cache or new motion owner is added.

`Evidence/2026-10-22_operator_active_idle_rejection/camera_bounded/` retains the same saved request, admitted
offset and native active→idle layers. The eye becomes (8.1487,-5,15); ordinary world records at every sampled
time are exactly identical to the previous failure fixture. Active dust extends through the previously empty
lower region. Idle still fails: only five ordinary conservative candidates remain visible from this nearer
view, and at idle60 the ordinary image contributes just 32 pixels at >=3 byte levels against frozen background.
The repair does not satisfy idle, nor does it promise that unchanged global counts are all visible simultaneously.

`camera_bounds_all_angles/` retains eleven frozen-world views, labelled Surface/Deep settings, native images,
camera parameters and 129×97 ray-grid receipts, all with >=3 world units of domain path. Some outward views are
sparse; geometry is no density acceptance. Actual interactive compositor/high-refresh/multi-display and complete
moving lifetime validation remain open. CPU samples of steady long-held constant-pitch evaluation are about
.03–.05ms here; changing-pitch evaluation costs more during its short prefix. This does not close full G32 cost.

Focused camera/editor/renderer checks pass; the separate old file-wide FOV-in-preset assertion fails against
the operator's parallel P1 JSON edit. That preset and simultaneous target-image renames are left untouched;
reconcile their camera/artwork contract separately, rather than weakening the new camera bounds or editing
operator authoring to make the test green.

## 52. Class-specific quiet size and particle Amount ownership (partial; idle still rejected)

Operator's later report considers P1 generally good, with idle only partly improved and no waiver of remaining
fidelity work. Latest physical screenshot `captures/2026-10-22_23-13-55_501801_display1_visualizer_55a2e404.png`
still has very faint small rings/dust against dominant water. Renamed `Targets/Originals/*Goal.png` files own
subsequent parity comparisons, including more capable 3D optical features; operator authoring is preserved.

The previous common .13 rest incorrectly treated small bubbles like large ones. CPU 2D reference with archived
controls and floor ON configured gives large settled .132 nominal, small 1.0; active small cohort crest medians
about3.88/max4.14. These are cohort-normalized values, not same-ID active-to-idle ratios (no ID survives to60s),
and replay begins at post-DSP features rather than re-exercising adaptive floor/PCM. A common .7825 rest diagnostic
was rejected for large bubbles. Current separate contraction gains5.8/1.45 give large .13 and small .7825 at quiet
.15; expansion4 gives authored .6/.8 crests3.4/4.2. The large gain is deliberate calibration, not derived physics.
The high handle cannot change zero-drive rest; quiet cannot change the full-drive crest. Large quiet values
above about .15 already reach the .13 minimum, so complete slider authority remains unaccepted.

Response normalizes the old .13-reference curve before spanning independent rest/crest. A naive lifted rest
accelerated relative pause settling (one-second residual .233 vs prior .269); normalization preserves the
mathematical shape and passes the retained gradual-release bar. Existing band followers/display smoothing remain
unchanged. Prospective source admission and actual contacts/wake attachment use the same class policy. Quiet-small
overlap must defer birth rather than force a bubble into the tank; source/contact tests cross that boundary.

Particle Amount is explicitly changed from squared density plus emission-scaled radiance to squared density
at fixed2.4 radiance. Existing zero counts, stable seeds, geometry, quarter-radius idle, glow release and quality
shares remain. This is NOT another double-Range defect repair. Sub-full active authoring becomes brighter too:
Custom amount .4 gives2.5× per-point radiance; .1 quiet gives10×; archived P7 quiet .844 gives~1.185×. Native active
glare stays open; no blanket P7 art or performance neutrality claim follows. Tiny positive amounts may still round
to no instances; zero is intentionally invisible. Tools/callers and Settings tooltips describe the actual owner.

`Evidence/2026-10-22_idle_class_transfer/run.py` / `capture.json` retain producer/input/source hashes, complete
settings,94 snapshots per case and1738×1143 native RTX4090 images. First47s of `anything_mixed2` → explicit paused
zero input60s → same-recording resume4s share one runtime. Labelled motion GIFs sample release0–5s/resume0–4s at10fps
with explicit jumps to idle25/60. Cases are exact saved Custom, archived P7 and archived 2D P1 with floor ON;
EB floor is OFF. This does not prove raw floor behavior, live audiovisual timing, compositor/DPR or high refresh.

Frozen full-ray blockers permit isolated layer subtraction. Custom idle60 ordinary contribution rises from the
camera-only candidate32 pixels to961 at >=3 byte-level max-channel delta; specks contribute2209. This is improved
output, not accepted readability: independent visual audit still finds only a few faint rings/tiny points while
2D has clearly readable resting bubbles across the frame. P7 is populated at rest but active/recovery is heavily
luminous. Zero-particle and settled-chain layers are byte-identical to background. The radiance intervention holds
current world/count/size/glow fixed; it is not a previous-versus-current class-transfer A/B. Contacts demonstrate
disappearance/return; full temporal smoothness and complete native birth→breach→exit remain open.

Between idle25 and60, Custom retains15 IDs with one retirement/no births; P7 retains32 with no births/retirements.
Retained displacements .36–.73 and .87–1.63 world units prove slow travel only. `lifecycle_cpu.json` extends each
authored geometry for3600 logical seconds at .1s steps: Custom17 births/17 exits/17 retired; P7 86 births/57 exits/
60 retired. This proves continued source admission/retirement in simulation, not native visibility or exact
physical exit classification for every P7 retirement (collision/cluster outcomes also apply).

Recorded-response instrumentation was wrong: paced BEAM admission interleaves large/small IDs, so numeric ID
ranges mixed classes. Tests now record actual successful admission metadata. The actual large minimum median
1.975896 and4–8s span1.398385 FAIL unchanged <.8/>1.8 bars; these failures also exist under the prior transfer.
Actual small span is1.820475. Do not call class-rest repair musical parity. The no-oscillator scalar-negative
control asserts the actual authored .05/.03 quiet endpoints rather than obsolete common contraction.
The startup probe uses canonical parameter admission/runtime controls instead of stale source mapping;
mutable six-coordinate P1 previously crashed it. Missing class samples stay explicit nulls.

Final connected simulation/recorded/inlet/world/renderer/wake/display-smoothing/full-dynamic/particle-idle/startup/
tooltip run:114 pass, two retained actual-large acceptance failures. No new candidate contract failure remains.
No new pass/clock/polling/schema/preset edits. Larger quiet-small footprints can raise contact/admission/fragment
work and active small crest rises to4.2; G32 native cost remains open. Next requested light/particle release
extension must use existing followers (min150ms or20% extra); held-left-drag orbit must preserve existing
input/focus/double-click behavior through shared owners and cursor fades, without new polling/timers.

## 53. Modest ray/particle release extension (native candidate; visual acceptance open)

The existing two EB followers add min(.15 seconds, .20× previous release), without another owner or stage.
Ray release is .696s during music/.98s in silence (formerly .58/.83); particle amount .30/1.65s (formerly .25/1.50).
Attacks, underlying musical sources, glow/size activity, bubble radii/motion and other modes are unchanged.
Forty-five focused simulation/audio/ray-particle/native-idle tests pass, including both formula branches at the
production call seam. `Evidence/2026-10-22_release_extension/` repeats the exact Custom native producer from §52:
94 release/idle/resume snapshots, unchanged input/settings, explicit source hashes. All sampled ordinary records
are exactly equal; idle60 full native pixels are byte-identical. Particle emission at1/3/5s is .2881/.1682/.1230
versus .2812/.1604/.1187 before. At1s native mean channel difference is .384 levels; the effect is deliberately
modest. Continuous musical release changes the preceding active state slightly too. This is a scoped timing
repair, not an idle-readability, glare, whole-scene density or audiovisual acceptance claim.

## 54. Bound large phrase-edge support by actual body change (native candidate)

The first eight recorded seconds expose a held-edge ownership defect: in the4–8s phrase, clean large body falls
as low as .092 while its radius envelope stays .589–.996. An independently decaying .25s phrase-edge value is
added even when the actual body is below its tracked reference. Repeated rises stack that value into inflation.
The consumer now uses min(held edge,current positive body change), preserving the same reference, edge state,
attack/release times, strength ranges and sustained body authority. Removing the edge entirely weakened soft
attacks; merely shortening its tail did not recover contracted minima. Supporting only the current positive
change corrects ownership without inventing another follower, oscillator, floor or threshold policy.

The corrected actual-class recorded gates retain their original bars: large whole-clip minimum median improves
1.975896→.450600 nominal and active4–8s span1.398385→1.895876 (>1.8 required). Small active span remains1.820475.
Ninety-one connected recorded/simulation/startup/recovery/audio/display-smoothing/wake/inlet/world checks pass.
The former pause check incorrectly capped all first-frame contraction at3%, including contraction already
underway in music. A same-feature/time continuation counterfactual isolates pause: continued large radius falls
3.51%, paused falls3.22%, with only .30% relative difference. The replacement keeps the3% additional-pause-loss
bar; subsequent one-second gradual settling and idle endpoint/motion assertions remain unchanged.

`Evidence/2026-10-23_large_response/` retains baseline driver trace, test-owned CPU measurements, current P1 native
candidate and one-line counterfactual restoring the old independent-edge consumer. Both native runs use unchanged
operator P1 controls, the same first8s recording,1738×1143 production GL and96 samples at12fps, with custody,
full settings, source bytes/hashes, native frames/contacts/motion GIFs and same-frame zero-swell interventions.
`same_id_native_crops.png` follows mature, nonpopping/nonleaving ID1 at2/2.5/3/3.5s without resizing native pixels:
old nominal ratios3.309/3.343/3.117/3.303 versus2.273/1.317/1.556/1.877. These are actual within-song changes,
not entrance/exit shrinkage. Crops follow each variant's projected centre; geometry/contact/lifetime may diverge
between variants, so they are not fixed-region pixel subtraction or an assertion of identical world evolution.
The counterfactual changes only the edge consumer, not an entire historical checkout; its function is retained.

The forensic tool's old projection report ignored physical eye/pan/FOV and treated scene scale as rotation-camera
FOV. It now uses the same physical-camera resolver and eye-relative world coordinates as rendering. Estimates
still exclude integrated flight/auto-orbit and near-plane/inside cases; actual images remain production draws.
Earlier projection statistics must not be reused as current eye-aware measurements.

Visual inspection confirms the scoped same-ID contraction improvement; full 2D-ON/EB-OFF audiovisual parity,
soft/heavy/quiet-to-loud passage coverage, idle readability, material fidelity and operator review stay open.
Two sequential short GPU samples are not neutrality proof: baseline median/p90 9.51/16.85ms, candidate10.81/15.02ms
(first frame includes shader warmup). G32 needs controlled warmed/interleaved cost; no pass/clock/target was added.

## 55. Authored lens metadata versus starting pose

The stale camera-reset test banned the text `extruded_bubble_camera_fov` anywhere in a preset file, although the
current Settings control and normal preset snapshot admit that independent intrinsic. Operator P1 authoring
exposed the contradiction. The gate now excludes FOV from starting-view pose metadata, checks any authored FOV
through the canonical control, and retains Custom canonical-home/lens and curated reset expectations. No preset,
camera implementation or reset behavior changed. Thirty-one camera/reset/startup checks pass; operator P1 and
reference renames remain untouched.

## 56. Lower-frame ordinary coverage and physical SCENE throughput (partial native repair)

The operator correctly flags sparse ordinary bubbles near the bottom of the hint preview and earlier native
frames. The hint preview used a frozen older EB background; the concern remains valid independently of that
preview. Current P1 was recaptured after the body fix: first47s recording→paused zero60s→resume4s, same1738×1143
native production host/settings, EB floor OFF. `Evidence/2026-10-23_current_p1_idle/` retains94 frames/custody.
At active end it has23 ordinary records, idle25/60 has16/15; ordinary idle60 contributes1658 pixels >=3 levels,
specks2882, free chains/background byte-identical. Visible fine rings improve on the original rejection but
remain faint compared with the2D field. This is not full idle acceptance.

The birth path has a concrete normalization defect: SCENE used36 world units (the longest tank dimension) for
all inlet rates even when the actual upward track is about16. The new pure mean-passage geometry uses the same
area/component face weights and authored face selection as physical source sampling. On each entry face the two
other exit distances are independent uniforms; integrating their survival product to the shortest full crossing
and mixing face weights gives the expected inside path. Exact vertical/horizontal controls are16/36; independent
sampled floor/corner/oblique tracks agree within1.5%. No camera, sampling in production, retained counter or new
clock/schema is introduced. Existing resting inlet, per-class12/s and one-birth/frame caps, overlap deferral,
initial pre-age and global/authored ceilings remain. Mean inside path does not model exit padding/fade or each
bubble's nominal-size travel factor; it corrects the physical reference, not a promise of exact target occupancy.

`Evidence/2026-10-23_scene_throughput/` retains exact settings and half-second CPU histograms over the same47s
P1 recording. Real source births excluding startup pre-age rise69→84; median small target remains23, actual21→24
(the existing policy retains in-flight surplus after the target falls). Mean world bottom/middle/top counts rise
7.39/6.86/8.84→8.61/7.86/10.22. Conservative mature centre candidates in screen top/middle/bottom rise
2.05/4.34/3.50→2.46/4.55/4.03. Therefore this fixes underfeeding; it does not establish a universal bottom-only
spawn failure or guarantee uniform projected density. Do not move sources/populations around the camera.
A separate constant-target40 low-crowding Surface control averages36.70→39.32 over60–180s, never above40; the
>=95% steady-occupancy gate fails under the former consumer. Entry fade/retirement/spacing still have real costs.

`Evidence/2026-10-23_scene_rate_candidate/` repeats the native current-P1 producer with the corrected rate.
Active/idle25/idle60 records become27/21/21. Idle60 ordinary contribution rises1658→8067 pixels while specks remain
exactly2882; no particle/material/timing change is involved. Native inspection finds more readable rings, including
lower-frame identities; quiet dust remains weak. Whole-tank moving distribution, composited temporal appearance,
fused lifecycle and all-angle density remain unaccepted. Same source geometry plus different birth history can
change contacts/locations/cohorts, so pixel totals are not isolated material-quality attribution.

Eighty-two connected SCENE/source/inlet/surface/world/simulation/recorded checks pass. Geometry source bytes/hashes
were preserved immediately after the native run (explicitly marked post-capture custody, not falsely pre-capture);
native producer receipts separately retain simulation/scene/renderer hashes. More physical admissions mean more
real contact/fragment work: G32 warmed cost remains open. This is not performance-neutral merely because no pass
or draw-clock was added. Operator presets and goal-image renames stay untouched.

## 57. Idle particle display radius and authored energy (2026-10-23)

The quarter-radius idle consumer also squared the contracted radius in the subpixel energy numerator.
For points already below the existing raster floor, coverage stayed unchanged while colour lost93.75%.
The shared production vertex now contracts only displayed radius; authored radius owns energy with the same
unit cap. Resolved points still shrink, fully subpixel points retain their authored light, and idle emission
remains zero. Generated SCENE entry/wall/exit fades explicitly use contracted radius to preserve their former
physical widths. Light proxies and the frozen-art lab explicitly use share1. No settings/preset/population,
simulation state, pass, clock or timer is added. The shader gains one scalar uniform and vertex multiply;
whole-scene cost neutrality is not measured by this slice.

The reused Medium agent supplied production-vertex/fragment native HDR regressions. The process-local negative
control restores contracted energy and fails with exactly1/16 retained colour. Root review runs47 connected
renderer, vertex, procedural population, shader and fade checks; the final fade counterfactual adds3 passing
checks proving contracted-radius Source/wall/exit parity. Fully active vertex colour/emission is bitwise equal
to an independently compiled uncontracted reference; zero authored radius/amount remain invisible and floor
crossing follows the continuous Gaussian law. Fragment-only tests could not detect this defect.

`Evidence/2026-10-23_idle_particle_energy/` retains the producer, exact current P1/P7 resolved settings, hashes,
94 frames per case over recorded47s→pause60s→resume4s, motion/contact sheets and isolated layers. A uniform-only
counterfactual restores former behaviour on identical frozen state: contracted authored size plus display share1.
P1 idle specks above3-channel-delta increase2882→4282 pixels; ordinary rings remain exactly8067. P7 specks
increase98745→111901, ordinary39334. Zero-particle and settled free-chain layers remain background-identical.
P1 active full composition is byte-identical; P7 differs in four pixels by one channel step each between repeated
full draws, so full-scene bitwise parity is not claimed there. Production vertex share1 is independently exact.
These are native offscreen production renders, not mixed-DPI compositor/physical audiovisual acceptance.

Operator explicitly accepts the shown P1 idle appearance: "That P1 Idle looks good actually." This is the scoped
visual milestone; it does not accept long lifecycle, all-angle density, every P1 defect or other preset fidelity.
P7 and the remaining presets still require substantial changes against their individual renamed targets.

## 58. Finite lateral shaft envelope, not complete world lighting (2026-10-23)

`beamExtent` admitted arbitrarily distant lateral points between the Source→End endpoint planes. It now
multiplies the same axial fades by a world-space cone. Source aperture is the explicit artistic calibration
0.1*WORLD_UNIT (0.9 physical radius), independent of End/camera, from shared ENGINE. Existing effective angular
reach widens the cone; softness feathers20–60% inward without moving its outer boundary. This intentionally
extends Ray Fan Spread's physical consumer to the marched volume; its tooltip now states that widening and
keeps Source/End as length owners. No schema/preset, pass, sample count, timer or scene population is changed.
Effective coincident/sub-threshold paths emit no shafts and have neutral proxy transmittance, avoiding
normalize(0), including Deep's overridden ray origin. World units are arbitrary; the threshold is0.001 units.

The reused Medium supplied11 native geometry tests executing unchanged production functions via SSBO against
an independent scalar oracle: core/feather/exterior, rigid transforms, camera independence, reach/softness,
old axial fades, reverse/short/coincident paths and actual Surface/Deep source ownership. A process-local old
slab negative control fails. Root review plus renderer/source/end checks passes48 tests. That connected run
also exposed a stale startup test expecting zero-speed Source births within0.33s. Direct floor/ceiling traces
show the existing0.4/s/class inlet produces first births at frame225 (2.5s), at y=±8.72. The test now asserts
absence through224 captures and real Source births at225, retaining the no-mid-volume-activation contract.
No simulation behavior changed to satisfy the stale timing expectation.

`Evidence/2026-10-23_shaft_extent/` retains the exact former shader, source hashes, current resolved P1/P7,
frozen recorded5s physical state, full native images, linear half-resolution shaft arrays and twelve
interleaved timings after four warmups for each of four legal views. Final producer run was isolated from
other tests. Authored P1 shaft mean0.14794→0.08295; P7 mean0.11717→0.07127. Frozen P1 remains visually coherent;
P7 is still heavily bright/dense and far from its renamed goal. Directional/full-field artistic acceptance
is not established by the finite envelope. Small warmed authored-view full-frame medians are P1 baseline/new
5.84/4.94ms and P7 4.12/4.40ms. Variable other poses and small sample size prohibit a neutrality/p99 claim;
extra per-sample lateral math must earn its cost in G32, despite no additional pass.

The camera-derived angular fan, two fixed fanExtent depths and representative18-unit attenuation point
remain independently wrong. This cone cannot fix sample-depth misses, all-angle field continuity or Deep
positional illumination/falloff. The production-host producer is authoritative for these comparisons;
inspection found the historical frozen-art lab's manual common upload omits physical Source/End uniforms.
That tooling debt remains actionable in the live plan; shared GLSL does not make its current output physical parity.

Native MC source integration also runs with normal updates and all useful CLI diagnostics plus20s self-exit.
The valid run is `logs/run_matrix/2026-10-23_idle_hint_shaft/bound_receipt.json`: one available LG TV display,
one EB owner, canonical P1 in an isolated settings copy, original profile hash unchanged, normal retirement,
exit0,76352 trace records/no drops or write errors and no failed settings writes. The saved display2 was absent,
so unmodified-profile runs admitted no display; they are not render evidence. Settings copy/log isolation uses
process-local owners, without environment overrides. An unguarded harness worker reentry and intrusive Qt
`grabWindow` stall were corrected; those aborted probes are explicitly invalid, not product failure attribution.
An external screenshot landed after exit and was removed. Production-host images above remain the visual proof.
Valid-session Qt capture reports one recurring startup `QUnifiedTimer::stopAnimationDriver` warning, not a clean
Qt pass; source attribution remains live. Steam artwork hash9b4a68b51c5f returns404 with updates enabled and stays
on the independent watchlist. No recorded/audio playback acceptance is inferred from idle MC integration.

A further settled47s→pause60s P1/P7 A/B (`idle.py`, `idle_receipt.json`) checks quiet nonregression separately
from active views. Main-agent visual inspection preserves the accepted P1 quiet rings/dust; mean RGB change is
0.77/255 for P1 and0.061/255 for P7, attributable to the narrower ray field. This is scoped preservation of the
shown quiet look, not transferred operator acceptance of complete lighting or P7.

## 59. World-field replacement pilot and next constraints (2026-10-23)

`Evidence/2026-10-23_world_field_pilot/` changes only the Surface fan-share uniform to0 on frozen current P1,
keeping the landed cone and all world actors. Main-agent native inspection rejects this as a complete replacement:
existing march alone loses much of the readable authored shaft structure. Authored shaft mean drops0.08295→0.03746;
side/away rise0.00953→0.02001 and0.00383→0.01246. It demonstrates the current fan's view bias, not accepted art.
Two draws/view provide no performance conclusion. Product source remains unchanged by this pilot.

The independent reused Medium audit supports one source-anchored world density within the existing40 samples.
Surface needs projection perpendicular to authoritative refracted sun; Deep must derive projection from effective
Ray Source→End. Renderer currently overwrites Deep sun_below from eye→Source for other consumers; do not use that
vector for world density or globally change it without their audit. A Light-Type-only discriminator must remain
independent of strength. Share cone widening exactly. Current pattern has FOUR noise calls (including flicker),
so preserve a bounded evaluated pattern instead of adding both old fan and old march noise at every sample.
At p=eye+ray*s, accumulate sum(weight*s) alongside sum(weight); reconstruct the identical weighted centroid from
one scalar moment. Skip proxy attenuation for zero mass. A centroid between separated lit lobes need not itself
be lit: this remains selective four-proxy attenuation, not integrated volumetric shadowing. Surface's old dominant
fan calibration and Deep's artificial shaft-height decay also require explicit treatment and native art/cost checks.

## 60. One world shaft field and contribution-weighted proxy sample (2026-10-23)

The production shader now integrates one source-anchored world pattern in the existing40-step,45-unit,
half-resolution march. Surface projects samples parallel to refracted sunlight into Source-relative coordinates;
Deep uses effective Source→End and the canonical `stream_basis` from physical geometry, divided by the same
`beamRadius` law as its cone. A Light-Type-only discriminator is independent of Light Strength. Deep's shared
eye-derived sun vector is preserved for other consumers and phase gain; it cannot steer the density projector.
No camera-anchored angular fan, two-depth fan mask or fixed18-unit attenuation point remains in this pass.

The same four-noise pattern retains softness and logical flicker/shimmer; outside-cone samples skip that work.
Obsolete private fan-frequency/contrast/march derivatives and uniforms are deleted, including their lab uploads;
public settings/ranges, source geometry and logical response timing do not change. Surface's former dominant
additive fan needs explicit art calibration: gain2.2 multiplies the volume; Deep stays1. This is an acknowledged
calibration change, not a placement-only claim. Deep shaft falloff now uses actual Source distance rather than
an artificial global shaft height; shared falloff/intensity across other consumers still needs repair.

One scalar sum(weight*distance) alongside sum(weight) reconstructs the actual illumination centroid along the
view ray. Empty fields skip proxy attenuation; at most four existing blockers plus aggregate dust remain.
The centroid can fall between separated lit lobes: this is selective proxy shadowing, not integrated transport.
Production functions and full-main native tests pass62 connected checks. The full-main controlled-density/jitter
case places a blocker after the actual lit centroid but before the former18-unit sample: restoring that sample
creates exactly16% erroneous shadow and fails. The reused Medium supplied13 helper tests; root added final-main
wiring proof. Independent integral/centroid oracles, zero-mass and mode/basis tests do not accept reference art.

`Evidence/2026-10-23_world_shaft_candidate/` preserves the160d6a78 baseline shader, exact settings/source hashes,
four legal views for current P1/P7 at frozen recorded5s and separate recorded47s→pause60s quiet comparisons.
The baseline upload shim explicitly restores deleted private uniforms from identical mode/softness, so it does
not accidentally compare against a fan disabled by missing uniforms. Main-agent native review retains P1's
readable overall and quiet appearance; quiet mean RGB changes0.376/255 (P1),0.027/255 (P7). P7 still exhibits
excess glow/density and materially misses its renamed target; this is no general preset acceptance.

Full-frame interleaved12-sample medians after4 warmups, baseline/new: P1 authored4.98/4.71ms, down3.57/3.33,
side3.72/3.68, away3.77/3.36; P7 authored3.16/2.93, down2.84/2.67, side3.25/3.12, away3.53/3.38.
No pass/sample-count/frame-pump/timer is added; old fan evaluation and two extra cone masks disappear, outside-cone
noise is skipped, and a scalar moment replaces an arbitrary sample. These bounded fixtures look favorable but
do not establish p99, moving populations, dual-display, first activation, or complete G32 performance acceptance.
Shared Deep emitter intensity/falloff for medium/core/glints/shafts/particles and final moving art remain next.

The new production source also completes the guarded MC integration with all useful CLI flags, normal updates
and20s self-exit: `logs/run_matrix/2026-10-23_world_shaft/bound_receipt.json`. One available display/EB owner,
normal retirement/exit0 and unchanged operator profile hash are recorded using isolated settings/logs. No GUI
image grab or synthetic audio is involved. The same single startup animation warning remains in Qt session
ba5361b7a644/pid42156; the timeout stack file stays empty. This is native idle source integration, not music,
dual-display or a clean-zero-warning acceptance claim.

## 61. One direct-light gain across the existing consumers (2026-10-23)

The reused Medium source audit confirmed that Light Strength reached analytic glass, CPU glint proxies,
visible Deep core and probe sun, while water glow/caustics, shaft compositing and particle scattering bypassed
it. The shared scene mapping now publishes the authored strength; common upload applies it to the musical
shaft gain once and the shader applies it to water-derived light. Particle direct phase consumes it while
retaining its0.3 ambient floor. Deep particles use Source at the actual point instead of the eye's source
direction. CPU-lit glint proxies explicitly bypass another strength factor in the shared particle vertex.
The follow-up audit found two additional tiny-shell/bead sparkle terms; their shared speck-glow owner now
scales once, and marine snow's seeded sparkle consumes strength separately from its ambient appearance.

Zero strength therefore preserves ambient water, environmental probe fill, faint particles, transmitted
background/probe light and snow opacity. Counts, physical radii/positions, source geometry, simulation/audio
timing, ranges and presets do not change. Existing historical lab recipes publish strength1 because their
gains are already calibrated; this does not resolve their separate missing physical Source/End uniforms.

The final connected gate passes76 tests: production particle vertex HDR diagnostics, scene/uniform mapping,
full production backdrop main for water glow/shaft compositing/caustics, actual renderer admission for
specks1/proxies0, and ordinary subpixel/stable-bead/marine-snow branches. Strength0/.5/1 (backdrop also2)
retains ambient and yields linear direct deltas with unchanged coverage. The Medium's doubled-strength
mutation fails its direct-delta cases. Large-shell diagnostics alone would have missed the tiny-material bypass.

`Evidence/2026-10-23_light_strength/` retains exactb256036f shader strings and common/glass uniform factories
as baseline, identical current settings/world snapshots, recorded5s active at four legal views and47s→pause60s
settled idle. Main-agent visual inspection preserves P1: authored/down/away active are byte-identical, side
differs at one channel step in one pixel; idle differs at one step in two pixels. This preserves the shown
accepted quiet look without claiming byte-identical whole-pipeline arithmetic. P7 authors strength0.12:
the excessive broad glow decreases substantially (authored mean RGB change50.73/255; idle16.71/255), but
its visible bubble depth/readability, directional stream structure, material and target match still fail.
This is shared control authority, not a completed P7 artistic repair or permission to freeze the other presets.

The work adds uniform arithmetic and one coherent positional direction calculation per Deep particle vertex;
Surface skips that branch. No pass, timer, sampling loop, resource owner or logical follower is added.
The saved interleaved query samples are diagnostic only: a focused GPU test process overlapped this capture
producer, so these timings must not establish performance neutrality. Moving/dual-display/G32 cost remains open.

Distance and finite-emitter optics remain the next required physical-light slice. Existing Deep core/glass
angular widths still do not follow a finite world radius, and the remaining medium/decorative field still
has angular placement debt. The canonical `scenePointLight` falloff describes received illumination;
applying it again to an already shrinking finite-emitter radiance footprint could double-count distance
dilution. Choose and verify that distinction before implementing attenuation or adding Lighting Coverage.

Final source integration also completes MC with normal updates, every useful diagnostic flag and20s self-exit:
`logs/run_matrix/2026-10-23_light_strength_final/bound_receipt.json`. The isolated profile selects P7 on ALL
currently available displays; one physical display/EB owner retires normally, exit0, original profile hash
unchanged,72675 trace records/no drops or write errors. Qt sessionfb232812e3ed still reports the same single
startup animation-driver warning; it is not a zero-warning pass. Native host captures above prove the visual
comparison; idle MC integration does not establish live music, dual-display or operator art acceptance.

## 62. Operator rejects broadened ray structure (2026-10-23)

The latest operator screenshot (`Evidence/2026-10-23_ray_structure/operator_rejected.png`) rejects the active
P1 ray appearance after the source-anchored world-field change: broad pale columns replace much of the fine/
medium shaft structure. This overrides the earlier frozen-view main-agent judgment that overall art was retained;
P1's separately accepted shown idle remains protected. The screenshot does not prove a changed preset or exact
audio state, and the stored `captures/Preset1Acceptance.png` is a useful earlier appearance reference, not a
matched counterfactual. Preserve all settings/actors in the new production-host A/B.

Source attribution: the removed angular fan carried three neighbouring fine/medium/coarse noise bands. The
replacement world field kept the old coarse2D march pattern and applied Surface gain2.2, which can retain
world placement while losing striation and raising broad wash. Restoring the old camera-ray fan would regress
physical geometry. First test a multiscale, anisotropic physical source-plane density with the same four noise
evaluations/40 samples and existing softness/flicker controls; compare against the present shader and earlier
appearance before choosing calibration. No simulation, preset, exposure or particle workaround is authorized
by this ray-specific repair. Native motion/aliasing and cost remain gates, not automatic passes from fine stills.

**Operator correction:** the earlier appearance was not a thin-ray target. Preserve broad coverage, internal
structure and soft diffusion after bubble interaction. The root's thin/narrow interpretation was wrong. None of
the pattern/sparse/analytic prototypes has been applied to product source. Noise-only candidates wash out or
lose intensity; the finite analytic packet currently loses the desired broad character. Inspect the Surface
entry aperture too: the shared0.1*WORLD_UNIT patch was introduced as a geometry calibration, not an accepted
Sunlit coverage reference. A wide directional surface entry and a small Deep source need not share that width.

**Independent selector/width candidate:** Light → Lighting Coverage BEAM/SCENE and Rays → Beam Width now
use the canonical descriptor/default/model/runtime path. All seven existing presets inherit BEAM/1x without
file rewrites, and Motion → Emission Geometry stays independent. Width0.25–3x scales the complete finite
cross-section, with1x matching the existing geometry oracle. SCENE integrates inside the fixed world box,
ignoring unused beam Source/End/width; Surface uses the world origin and refracted sunlight, Deep the actual
Light Source. It does not create actors or track the eye. Lazy construction, conditions and persistence are
covered through actual Settings widgets.

The attempted directional-phase restoration was rejected by root native visual comparison against160d6a78:
it still lost the broad structured appearance, so it remains ignored evidence under `rejected_phase/` and
`2026-10-23_lighting_coverage_prior/`. It is not product code. The final BEAM1x path retains0bb0f228 equations;
full broad-ray restoration remains open. The existing soft four-bubble attenuation is a selective approximation,
not proof of realistic diffusion after glass interception. SCENE Deep now rejects blockers behind the physical
emitter, and final backdrop compositing no longer applies BEAM's look-toward-source gate to SCENE. Native
production-main pixels falsify side/back-facing SCENE extinction; BEAM retains its previous compositing.

Native production-host comparisons (`Evidence/2026-10-23_lighting_coverage/`) use the same recorded5s snapshot
and47s music→60s pause state, authored settings/actors, against exact0bb0f228 shader/common/glass/scene-knob
owners. P1/P7 default BEAM active and settled-idle captures are byte-identical. Resting bubbles/specks remain
visible. P7 still needs major fidelity work. Width0.25/3 and SCENE captures show independent coverage changes,
not automatic preset migration. RTX4090 interleaved12-sample medians after4 warmups are recorded per case in
`capture.json`; they are a small frozen diagnostic, not p95/p99, moving/dual-display cost neutrality or operator
art acceptance. SCENE admits more samples to the same four-noise field, so unchanged passes/40-step budget do
not establish equal cost. No resource, timer, simulation or frame scheduler is added. Broad coverage, all-angle
striation, actual bubble diffusion and shared finite-source/falloff coherence remain open.

The final79 focused renderer/geometry/world-shaft/backdrop/lazy-Settings checks pass. Full diagnostic MC with
normal updates and20s self-exit now starts/reveals both physical displays and retires normally, exit0, with
the original profile hash unchanged (`logs/run_matrix/2026-10-23_lighting_orbit_retry/bound_receipt.json`).
This validates source integration, not ray art acceptance. The earlier orbit startup bridge failure and native
gesture acceptance remain separate input work; the successful run's orbit probe did not promote a gesture.

## 63. Restore accepted BEAM; isolate SCENE lighting (23 October)

The operator rejects the09:41:49 capture's displaced columns/sheets and explicitly requests checkpoint
restoration for BEAM, with further experiments confined to SCENE. `Preset1Acceptance.png` was captured22 Oct
23:47:35. The160d6a78 lateral cone (23 Oct01:20) therefore postdates that image; restoring only the angular fan
removed in b256036f would still leave a narrowed footprint. The pre-acceptance a51aab8a shader owns the restored
BEAM fan, axial Source→End fades, two-depth fan support, fixed18 selective attenuation and matching
shaft_fan/fan_rays/fan_contrast/fan_march uniform mapping. New width1x is an identity. Its other values scale the
fan/angular concentration, including Deep compositing; they no longer assert a physical cone aperture.
Degenerate effective paths remain safely dark. No curated preset file or operator Custom is rewritten.

The frozen custom shader body in `tests/fixtures/extruded_bubble/accepted_beam_a51aab8a.glsl` is a test oracle,
not a product fallback. Native conformance compares the production BEAM fragment against it for Surface/Deep,
multiple poses and softness values, with a positive-energy guard. Source/End native tests protect the restored
broad axial envelope. The rejected cone and transverse-basis helpers/knobs are retired rather than kept as dead
production code or misrepresented by passing geometry tests. Historical lab recipes are explicitly BEAM/1x;
MC owns current full-runtime visual validation.

This is an uncheckpointed working-tree candidate. Its last focused lighting gate passed83 checks; that result
does not close the subsequent audit findings. The oracle uses current shared uniforms/common GLSL on both
sides, so it does not independently freeze historical knob mapping or the complete backdrop. Those boundaries
still require verification before claiming accepted BEAM parity.

SCENE keeps the same shader/half-resolution target/blur owner and executes one separate selected march.
Surface density backprojects to the actual water plane; its broad structured phase shares the real refracted
sun direction over fixed-world support. Deep density uses normalized sample−Light Source directions, replacing
unrelated parallel texture planes with a radial field. SCENE ignores the beam path/width, retains contribution
centroid shadowing, and rejects behind-emitter blockers. No pass, simulation, resource owner, polling or frame
scheduler is added. Native tests falsify radial invariance, source movement, side/away compositing, width
independence and shadow direction. Full multiple scattering, finite-emitter size and all-angle moving fidelity
remain unaccepted; this is not full physical-light compliance.

Actual MC captures now preserve the saved Display2 route instead of forcing ALL. The unwrapped main_mc.py
run starts/reveals screen1 and exits0 with normal updates/full useful diagnostic CLI. The exact-route disposable
capture driver records mc_identity=True/profile=Screensaver_MC, one visible LG window and an unchanged source
profile hash. Its ordinary BEAM run uses unmodified current authoring (`2026-10-23_mc_saved_route_beam`). The
P1 BEAM/SCENE placement drivers use current curated authoring in an isolated Custom, fixing only rendered ray
intensity0.8 so rays can be inspected while real media is paused; those are NOT music or idle acceptance.
Receipts/captures: `logs/run_matrix/2026-10-23_mc_ray_beam/` and `2026-10-23_mc_ray_scene/`. They show a broad
sun-centred fan in both choices, replacing the rejected separate columns. Earlier ALL-display/synthetic-input
runs do not represent the operator's MC experience, and offscreen-host stills do not meet the latest MC request.

Next: moving/music/all-angle Surface and Deep SCENE, actual bubble diffusion and cost, then remaining preset
fidelity (especially P7). Preserve BEAM's restored baseline. Do not silently promote a plausible still to parity.

The final read-only audit found two lighting defects still present in the candidate: SCENE fan coverage is
binary whenever any march sample intersects the tank, and a nonzero Surface fan with zero procedural density
shadows at the eye because its density centroid is zero. Continuous medium support and a real fan contribution
centroid are required; keep the existing selected march and bounded blocker query, without touching BEAM.
The Deep Ray Fan Spread row is also ineffective and should be hidden for that Light Type. The MC placement
captures above precede final source cleanup and these pending corrections; rerun on the final tree, preserving
saved routes. These are implementation tasks, not requests for operator logs.

## 64. Held-left orbit, black startup and release ownership (23 October)

The broad Python QuickDisplayWindow.event override deadlocks visible threaded-Quick startup inside its C++
superclass. The9s receipt and20s self-exit never execute;35s stacks are in
`logs/run_matrix/2026-10-23_lighting_orbit_final/`. Hidden input tests missed it. That override is removed:
a narrow event filter leaves normal startup/render delivery in C++, and a source regression forbids restoring
it. Actual MC startup/self-exit subsequently pass on the saved single-display route. The operator independently
reports startup fixed and physical left orbit working; those reports override failed synthetic driver claims.

The gesture reuses existing camera admission, deltas and persistence. Real retained passive/exclusive grab
notifications preserve visualizer descendants/glyphs and controls above the card. Lower ordinary handlers do
not veto a visually higher visualizer; press admission and grab refusal use the same retained stacking
comparison. Capture begins only after Qt's drag threshold, clips to the actual physical card/client rectangle,
and reuses the existing cursor fade/cache. Held motion does not revive the cursor. Discrete release, reset,
mode/menu/Edit/focus/topology/hide/close edges unwind the gesture without a new timer or polling owner.

An audit subsequently identified a remaining ownership hole: the lower-handler stacking exception also admits
an existing exclusive MouseArea grab, but promotion only clears passive grabs and can consume that control's
release. Decline promotion for any existing exclusive/mouse grab and verify the lower MouseArea returns to
unpressed normally. **Implemented 2026-10-23:** `_promote_plain_orbit` and the press-scoped grab observer now
decline on any exclusive grab regardless of stacking; only passive grabs use the retained stacking comparison.
A real retained lower MouseArea falsifier reproduced the stolen press (orbit card acquired, release consumed)
before the fix and passes after it, alongside the existing orbit/framed-camera suites. Physical overlap and
ownership acceptance remain open.

The operator's native release error exposed an incorrect success test: Qt's boolean return alone cannot
establish that native capture remains owned. Release now verifies actual GetCapture after the Qt call. A
false result with no remaining ownership completes; a true result with retained capture still fails loudly
and retains the cleanup token. Failed clip/query/ungrab work stays with the existing window/runtime deletion
barrier for later discrete cleanup; foreign replacement owners are untouched. No timeout or barrier bypass.

Native synthetic Qt events did not reliably promote capture: lower Media TapHandler refusal and synchronous
WM_CAPTURECHANGED during acquisition invalidated those probes. They are not physical orbit acceptance.
In particular, copying the MC entry/profile while forcing ALL displays changed route/overlap/focus and was an
incorrect reproduction setup. The agent is stopped from launching apps. Physical focus-loss/capture theft,
close/reset and mixed-DPI acceptance remain open; no new real-input polling is justified by the probe failures.

### 2026-10-23 replay tooling cleanup annotation

Historical entries referring to `extruded_bubble_startup_probe.py` document what investigators used at the time, not a live required diagnostic. The one-off command was retired and the test-owned Qt-free simulation support moved into `tools/visualizer_replay/eb_simulation_support.py`; behavioral overshoot coverage now lives in normal tests. The authored preset references in the old probe were replaced by synthetic fixture profiles. This does not establish visual acceptance of breathing or real-music parity. See [Test Oracle Repair](../../Audits/Test_Oracle_Repair_2026-10-23.md).
