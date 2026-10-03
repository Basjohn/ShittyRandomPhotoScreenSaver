# Voxel Sphere — experimental preservation and shared-Scene3D promotion contract

Status: **ACCEPTED EXPERIMENTAL — LOW-LEVEL SUBSTRATE PROMOTION ACTIVE.** Sphere remains independently removable, lazy and mode-owned while S19 moves only its duplicate GPU/resource plumbing onto the shared scene3d substrate. Visual/product acceptance does **not** promote Sphere reaction/state semantics into shared Visualizer architecture or make Sphere a permanent default mode.

## Current golden

Sphere remains a separate, disabled-by-default experimental Visualizer mode; its accepted look and response are preservation inputs, not permission to promote its implementation into the established five modes. Ordinary-widget semantic Edit/lifetime machinery is not part of Sphere's viewport ownership.

The accepted representation is the stepped voxel shell, not the retired smooth icosphere. Current musical behaviour is now a preservation target: strong/local detached fragmentation, granular event-owned intake/outtake cohorts, stable four-corner population identity, sustained body growth, event-stepped tracer travel, continuous rotation and the vocal-linked intake recoil. Presentation or cleanup work may not make the mode quieter, slower to react, less spatially articulate or more ambient/free-running.

Two original Sphere goldens remain (two additional Rainbow variants are separately curated):

| Preset | Name | Golden role |
| --- | --- | --- |
| 1 | **Glass Current** | Former Preset 5 / Transparent React snapshot. Intake (`Particle Outtake` off), translucent fill and bright independent edges preserved. |
| 2 | **Voxel Bloom** | Former Preset 6 / Reactive Voxel snapshot. Outtake on, opaque neutral presentation and Sphere shadow enabled. |

Their exact persisted snapshots are golden inputs. The active substrate promotion must preserve resolved behaviour, not merely names or superficially similar slider values.

## Isolation / ownership contract

- The descriptor remains an independently disabled experimental mode with lazy Settings builder, capture, frame runtime and renderer. Heavy resources stay dormant while disabled and retire through the existing render-context lifecycle.
- Canonical persisted state remains in the existing `sphere_*` namespace. Do not invent a private Settings manager/default store, and do not promote Sphere into shared setting families merely for tidiness.
- **Pre-S19 current state:** Sphere declares `technical_controls=False`, `rainbow_controls=False` and `shared_bar_appearance=False`. Capture that current state before migration; do not reinterpret it as the final desired technical-control model.
- **Pre-S19 current state:** the descriptor resolves its hidden technical profile through canonical **Spectrum** technical settings. Those exact resolved values are behavioural golden input for the migration. S19 explicitly replaces this hidden whole-profile borrowing with a Sphere-owned resolved technical profile and per-control capability metadata, exposing only controls that demonstrably affect Sphere's analysis inputs. Dead controls are forbidden.
- Existing BeatEngine spectrum/live-pre-AGC/musical-level (`get_musical_level`) seams remain read-only consumers of already-authored analysis. No second FFT, worker, timer, poller or private cadence is allowed.
- Product acceptance does not authorize extracting Sphere behavioural internals into shared infrastructure. The active promotion authorises sharing low-level GPU/resource/material/post/compute infrastructure only; Sphere reaction/state semantics remain private.

### What is reusable from the experimental-isolation method

The **boundary mechanism** remains valuable: descriptor-driven lazy Settings/runtime/renderer/capture resolution, independent enable/disable/dormancy, a private persisted prefix where behaviour is mode-specific, explicit capability metadata and normal renderer retirement. Sphere itself is a legacy exception because it was built before shared Scene3D. **Future experimental modes must use the canonical shared low-level Scene3D/compute/resource/material/quality substrate from their first implementation.** Experimental status may keep them default-off and behaviorally private; it must not create a private GPU engine that later requires a second "promotion" job.

Do **not** generalize Sphere itself to achieve this. `sphere_*` parameters, Sphere audio/voxel logic, hard-coded Sphere capability memberships and Sphere shader semantics remain private implementation. The active substrate promotion does not authorize extracting or refactoring those behavioural owners into a shared experimental framework. Reusable isolation means a reusable **host seam**, not a reusable Sphere feature stack.

## Current Settings hygiene

Sphere Custom now uses the shared themed circular checkbox styling and collapsible bucket scaffold while all persisted/runtime ownership remains Sphere-local. Recommended slider notches are presentation-only hints matching the accepted **Glass Current** baseline; they are not defaults and do not alter saved or runtime values.

The following experimental-era controls had no live runtime/render authority and are fully retired rather than displayed disabled: `sphere_surface_detail` (old Block Relief), `sphere_bass_response`, `sphere_mid_response`, `sphere_high_response`, `sphere_energy_curve`, and `sphere_idle_motion` (old Idle Drift). **Base Rotation** is the sole continuous idle rotation authority; **Velocity Reaction** adds music-driven rotation velocity.

The formerly overloaded `sphere_deformation` + `sphere_bump_reactivity` pair is also retired as canonical state. Visualizer schema v8 first migrates their exact resolved local-displacement product into **Fragment Strength** and copies the old Deformation value into **Particle Distance**, then strips both legacy keys. **Particle Amount** is a renderer-side post-admission population multiplier (`1.0` preserves accepted behaviour), and the UI label for the existing density-response toggle is **Particle Density Response**. Vocal Response stops at its existing effective ceiling (`1.35`); Size Response stops at the existing growth saturation (`2.54`).

**Musical reward (operator 2026-10-03):** near-silence fragmented and launched particles as fully as a full blast, whatever the floors. Cause: Sphere's gates and both floors compared the live pre-AGC lane, which is clamped at `2.5` and sits at that cap through ordinary music (hardware logs: intake 1.4..2.5 for whole songs), while its event sources are loudness-blind (the transient bus's input is loudness-normalised, Sphere's spectral flux is a log ratio) and every admitted event earned a fixed `0.42..0.70` minimum amplitude. Now what an admitted event *earns* follows the shared musical rule of `transient_bus.py` that Shockwave Grid uses (`musical_weight` x `musical_emphasis`, read per frame through `BeatEngine.get_musical_level`): nothing in near-silence (absolute loudness) or in a passage far quieter than the track's running level (presence), less below the track's usual event presence (learned by `learn_usual_presence` from a neutral 1.0), the full accepted reward at the usual level and above, so loud material keeps exactly its accepted reaction. It scales fragment amplitude (a packet under `0.05` is not emitted), cohort travel strength, the event confidence and acoustic impact behind cohort population and velocity, and tracer travel. Event qualification, the typed/onset/spectral sources, the hysteretic gate and the live-lane real-silence authoring floor are unchanged. Known limit (operator log 2026-10-03 22:42-22:51): in real scales (loudness 3-17 in music) the absolute near-silence edge only engages at true silence, admission frequency does not ramp, and quiet frames still earn 0.15-0.35; the full ramp ("everything ramps, fast up and gentle down") is the open S19 item in `Current_Plan.md`.

**Independent acoustic-floor controls:** The fragment Energy Floor and particle Energy Floor are Sphere-only thresholds on the 0..1 musical weight (`musical_weight`: 0 near-silence or a far quieter passage, 1 the track's level), evaluated after the existing typed/onset candidate qualifications. (They used to compare the saturated live lane and so never bit.) The fragment floor defaults to `0.000`, applying no extra admission filter; the particle floor defaults to `0.075`. Both controls use `0.001` steps across `0.000..1.000` and have separate persisted `sphere_fragment_energy_floor` / `sphere_particle_energy_floor` keys in canonical defaults, Custom, and curated Sphere preset snapshots. Older user-authored preset payloads missing the keys receive these same defaults. The particle slider cannot defeat the separate real-silence presence safeguard; it does not tune population, velocity, or in-flight cohorts. The fragment floor changes neither tracer admission nor particle admission or packet amplitude. Do not change the shared event scheduler, pre-AGC spectrum, renderer, or other visualizer modes to implement these controls.

**Detached-particle population authority:** Particle Density Response must remain post-admission and independent of absolute passage loudness. Loud beds are allowed—and required—to retain strong kick/vocal reactions. Qualified cohorts keep the accepted visible participation floor, then event confidence plus Sphere-local granular motion evidence determine population; full population is exceptional. The Sphere-local presence gate also has a current near-silence authoring floor, so a recently-open hysteretic gate or latched typed event cannot create a new cohort from residual near-silence. Do not implement either rule by raising shared transient thresholds or weakening loud-passage events.

Rainbow Ghosting is likewise retired and forward-stripped. Sphere now has its own isolated **Taste The Rainbow** presentation controls for Surfaces and Edges; they are not `sphere_rainbow_*` keys and do not opt the descriptor into the shared Rainbow family. The voxel shader uses one moving partial-spectrum field across blocks in the existing draw while retaining authored Fill/Edge alpha. **Perspective Strength** is also Sphere-local and deliberately one-sided: `1.0` is the accepted camera projection exactly and `0..1` may only flatten toward orthographic, never intensify projection beyond the golden envelope.

Additional presentation controls expose existing renderer constants rather than inventing new behaviour: **Edge Weight** defaults to `1.0`, which resolves to the accepted `0.72 -> 0.90` face-edge thresholds; **Voxel Size Variation** defaults to `0.35`, the former fixed shader constant; and **Tracer Color** defaults to `[255,242,194,255]`, the former hard-coded warm tracer colour. **Depth Shading** is the only new visual effect and defaults off. When enabled it applies a restrained rear-hemisphere luminance reduction from already-transformed voxel depth in the existing shader; it samples no neighbouring voxels, adds no AO/reflection/shadow pass and does not alter hue, alpha, geometry or audio authority. These controls remain private Sphere parameters while the mode is experimental.

The current experimental drop-shadow implementation is a **projected voxel silhouette**, not the old circular proxy and not voxel-to-voxel lighting. Shadow and hero compile the same Sphere vertex shader and consume the same rigid rotation, fragmentation, size pulse, tracer-local turns, perspective and intake/outtake cohort transforms. The shadow fragment contributes flat inherited shadow colour only. Sphere-local **Shadow Opacity / Softness / Distance / Size** controls parameterize this pass; softness may add one expanded instanced feather layer, while disabled/zero-opacity shadow adds no second shadow clear/draw. Do not generalize this into shared 3D shadow infrastructure unless another concrete consumer proves the same contract.

## Promotion golden gate — active

Before any architectural promotion into shared/permanent ownership, capture both **Glass Current** and **Voxel Bloom** with:

- their exact persisted Sphere snapshots, including presentation baselines such as Edge Weight `1.0`, Voxel Size Variation `0.35`, the accepted Tracer Color and Depth Shading disabled unless explicitly re-authored;
- the exact resolved hidden technical profile/settings that reproduce today's behaviour;
- fixed deterministic `FeatureFrame` / existing Visualizer replay input covering silence, flat/low qualified events, vocals, kicks/drums and sustained passages;
- Sphere logical outputs important to behaviour: event admission/source, section drives, tracer phase/drive, size pulse, rotation, cohort admission/density/velocity/direction/progress and vocal recoil;
- representative renderer captures at ordinary and extreme CUSTOM aspect/scale where the existing capture seam can provide deterministic evidence;
- baseline replay evidence for the five accepted permanent modes over the same shared-analysis change boundary.

After the candidate promotion, replay identical evidence. Promotion is rejected if Sphere's **behavioural** golden materially changes without explicit approval, or if the recognisable stepped-voxel/preset identity is lost, **or** any accepted permanent mode changes in reactivity, latency, source freshness, visual fidelity, cross-mode bleed/isolation, cadence, lifecycle, CPU/GPU resource behaviour or dormancy. Pixel-for-pixel visual parity is not the objective: improved antialiasing, lighting, material/depth readability, shadows, reflection/refraction or other presentation quality is welcome when it is demonstrably better and preserves musical response, silhouette/voxel identity and preset intent. Technical controls require particular caution because the current hidden resolved values are behavioural input even though Sphere has no generic technical-control UI.

The existing deterministic Visualizer/`FeatureFrame` replay seam is the preferred foundation. Extend it only as needed; do not build a Sphere-only second replay engine.

This gate removes competing low-level 3D architectures. Promotion
means moving Sphere onto the shared `rendering/quick/scene3d/` GPU/resource/material/post/compute substrate while
preserving the complete behavioural golden above. It does **not** authorise retuning/renaming Sphere behavioural state, replacing its logical runtime, or turning Sphere
into a base class. S19 **does** authorise replacing the hidden Spectrum-profile borrow with deliberate Sphere-owned
technical-control resolution after the current values are captured as the migration golden. See `Current_Plan.md` S19.

## Current shared-boundary rule

Sphere-specific presentation controls remain confined to Sphere-owned descriptor/capture/runtime/renderer/config branches. Permanent-mode runtimes/renderers and shared logical analysis must not gain Sphere-specific behavior merely to tidy the experiment. Only the low-level GPU/resource/material/post/compute seams named by S19 are in the active promotion; any behavioural extraction beyond them requires separate approval and the golden gate above.

## Open operator gate: energy-floor controls

The independent fragment and particle minimum-energy settings are implemented with curated/default and user-authored preset protection.

- [ ] Native Windows Settings/preset run proves fragment and particle floors change independently.
- [ ] Active-music observation confirms the two floors affect only their intended admission paths.
- [ ] Musical reward: near-silence and quiet intros stay calm (no full fragmentation or particle bursts), a pause's
  first quiet frames throw nothing, loud passages and drops react as before.
- [ ] Reset restores the authored defaults.
- [ ] Custom Save/reopen preserves user-authored values.

Do not retune authored values on the operator's behalf.
