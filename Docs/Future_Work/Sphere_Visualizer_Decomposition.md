# Voxel Sphere — accepted experimental preservation and future migration gate

Status: **ACCEPTED EXPERIMENTAL — ISOLATED.** Visual/product acceptance does **not** promote Sphere into permanent/shared visualizer architecture. All experimental modes remain independently removable, lazy and mode-owned until the operator explicitly authorizes migration.

Current supplied source provenance before this polish pass: `c45845d44d21537ca4c09be41f6decf4cde0d16a`.

## Current golden

The accepted representation is the stepped voxel shell, not the retired smooth icosphere. Current musical behaviour is now a preservation target: strong/local detached fragmentation, granular event-owned intake/outtake cohorts, stable four-corner population identity, sustained body growth, event-stepped tracer travel, continuous rotation and the vocal-linked intake recoil. Presentation or cleanup work may not make the mode quieter, slower to react, less spatially articulate or more ambient/free-running.

Only two curated Sphere presets remain:

| Preset | Name | Golden role |
| --- | --- | --- |
| 1 | **Glass Current** | Former Preset 5 / Transparent React snapshot. Intake (`Particle Outtake` off), translucent fill and bright independent edges preserved. |
| 2 | **Voxel Bloom** | Former Preset 6 / Reactive Voxel snapshot. Outtake on, opaque neutral presentation and Sphere shadow enabled. |

Their exact persisted snapshots are golden inputs. A future migration must preserve resolved behaviour, not merely names or superficially similar slider values.

## Isolation / ownership contract

- The descriptor remains an independently disabled experimental mode with lazy Settings builder, capture, frame runtime and renderer. Heavy resources stay dormant while disabled and retire through the existing render-context lifecycle.
- Canonical persisted state remains in the existing `sphere_*` namespace. Do not invent a private Settings manager/default store, and do not migrate Sphere into shared setting families merely for tidiness.
- Sphere currently declares `technical_controls=False`, `rainbow_controls=False` and `shared_bar_appearance=False`. Those omissions are deliberate isolation, not missing wiring to repair.
- The descriptor currently resolves its hidden technical profile through canonical **Spectrum** technical settings. That resolved technical state is part of the pre-migration golden even though Sphere has no generic technical-control UI. Do not casually expose, remap or replace it.
- Existing BeatEngine spectrum/live-pre-AGC seams remain read-only consumers of already-authored analysis. No second FFT, worker, timer, poller or private cadence is allowed.
- Product acceptance does not authorize extracting Sphere internals into shared infrastructure. Reuse/extraction is a future migration decision requiring explicit operator activation.

### What is reusable from the experimental-isolation method

The **boundary mechanism** is valuable architecture for future experiments: descriptor-driven lazy Settings/runtime/renderer/capture resolution, independent enable/disable/dormancy, a private persisted prefix, explicit opt-out from shared setting families, and normal renderer retirement. Future experimental modes should reuse that pattern rather than contaminating accepted-mode owners.

Do **not** generalize Sphere itself to achieve this. `sphere_*` parameters, Sphere audio/voxel logic, hard-coded Sphere capability memberships and Sphere shader semantics remain private implementation. Extracting or refactoring those into a shared experimental framework is itself migration work and is forbidden until explicitly requested. Reusable isolation means a reusable **host seam**, not a reusable Sphere feature stack.

## Current Settings hygiene

Sphere Custom now uses the shared themed circular checkbox styling and collapsible bucket scaffold while all persisted/runtime ownership remains Sphere-local. Recommended slider notches are presentation-only hints matching the accepted **Glass Current** baseline; they are not defaults and do not alter saved or runtime values.

The following experimental-era controls had no live runtime/render authority and are fully retired rather than displayed disabled: `sphere_surface_detail` (old Block Relief), `sphere_bass_response`, `sphere_mid_response`, `sphere_high_response`, `sphere_energy_curve`, and `sphere_idle_motion` (old Idle Drift). **Base Rotation** is the sole continuous idle rotation authority; **Velocity Reaction** adds music-driven rotation velocity.

The formerly overloaded `sphere_deformation` + `sphere_bump_reactivity` pair is also retired as canonical state. Visualizer schema v8 first migrates their exact resolved local-displacement product into **Fragment Strength** and copies the old Deformation value into **Particle Distance**, then strips both legacy keys. **Particle Amount** is a renderer-side post-admission population multiplier (`1.0` preserves accepted behaviour), and the UI label for the existing density-response toggle is **Particle Density Response**. Vocal Response stops at its existing effective ceiling (`1.35`); Size Response stops at the existing growth saturation (`2.54`).

**Detached-particle population authority:** Particle Density Response must remain post-admission and independent of absolute passage loudness. Loud beds are allowed—and required—to retain strong kick/vocal reactions. Qualified cohorts keep the accepted visible participation floor, then event confidence plus Sphere-local granular motion evidence determine population; full population is exceptional. The Sphere-local presence gate also has a current near-silence authoring floor, so a recently-open hysteretic gate or latched typed event cannot create a new cohort from residual near-silence. Do not implement either rule by raising shared transient thresholds or weakening loud-passage events.

Rainbow Ghosting is likewise retired and forward-stripped. Sphere now has its own isolated **Taste The Rainbow** presentation controls for Surfaces and Edges; they are not `sphere_rainbow_*` keys and do not opt the descriptor into the shared Rainbow family. The voxel shader uses one moving partial-spectrum field across blocks in the existing draw while retaining authored Fill/Edge alpha. **Perspective Strength** is also Sphere-local and deliberately one-sided: `1.0` is the accepted camera projection exactly and `0..1` may only flatten toward orthographic, never intensify projection beyond the golden envelope.

Additional presentation controls expose existing renderer constants rather than inventing new behaviour: **Edge Weight** defaults to `1.0`, which resolves to the accepted `0.72 -> 0.90` face-edge thresholds; **Voxel Size Variation** defaults to `0.35`, the former fixed shader constant; and **Tracer Color** defaults to `[255,242,194,255]`, the former hard-coded warm tracer colour. **Depth Shading** is the only new visual effect and defaults off. When enabled it applies a restrained rear-hemisphere luminance reduction from already-transformed voxel depth in the existing shader; it samples no neighbouring voxels, adds no AO/reflection/shadow pass and does not alter hue, alpha, geometry or audio authority. These controls remain private Sphere parameters while the mode is experimental.

The current experimental drop-shadow implementation is a **projected voxel silhouette**, not the old circular proxy and not voxel-to-voxel lighting. Shadow and hero compile the same Sphere vertex shader and consume the same rigid rotation, fragmentation, size pulse, tracer-local turns, perspective and intake/outtake cohort transforms. The shadow fragment contributes flat inherited shadow colour only. Sphere-local **Shadow Opacity / Softness / Distance / Size** controls parameterize this pass; softness may add one expanded instanced feather layer, while disabled/zero-opacity shadow adds no second shadow clear/draw. Do not generalize this into shared 3D shadow infrastructure unless another concrete consumer proves the same contract.

## Future permanent-migration golden gate — dormant until explicitly activated

Before any architectural migration, capture both **Glass Current** and **Voxel Bloom** with:

- their exact persisted Sphere snapshots, including presentation baselines such as Edge Weight `1.0`, Voxel Size Variation `0.35`, the accepted Tracer Color and Depth Shading disabled unless explicitly re-authored;
- the exact resolved hidden technical profile/settings that reproduce today's behaviour;
- fixed deterministic `FeatureFrame` / existing Visualizer replay input covering silence, flat/low qualified events, vocals, kicks/drums and sustained passages;
- Sphere logical outputs important to behaviour: event admission/source, section drives, tracer phase/drive, size pulse, rotation, cohort admission/density/velocity/direction/progress and vocal recoil;
- representative renderer captures at ordinary and extreme CUSTOM aspect/scale where the existing capture seam can provide deterministic evidence;
- baseline replay evidence for the five accepted permanent modes over the same shared-analysis change boundary.

After migration, replay identical evidence. Migration is rejected if either Sphere golden materially changes without explicit approval **or** any accepted permanent mode changes in reactivity, latency, source freshness, visual fidelity, cross-mode bleed/isolation, cadence, lifecycle, CPU/GPU resource behaviour or dormancy. Technical controls require particular caution: their current hidden resolved values are behavioural input even though Sphere has no generic technical-control UI.

The existing deterministic Visualizer/`FeatureFrame` replay seam is the preferred foundation. Extend it only as needed; do not build a Sphere-only second replay engine.

Until the operator activates this gate, **do not migrate Sphere at all**.

### 2026-09-10 post-presentation isolation audit

After adding Sphere-local Edge Weight, Voxel Size Variation, Tracer Color and optional Depth Shading, the descriptor, capture/runtime, BeatEngine/shared logical runtime and all permanent-mode renderers/runtimes remain byte-identical to the pre-visual-polish checkpoint. The sole shared config-module delta is confined to the existing Sphere parameter tuple/apply branch. This is evidence that presentation polish has not widened Sphere's ownership boundary; it does **not** activate migration.
