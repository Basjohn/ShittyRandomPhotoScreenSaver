# Voxel Sphere — standard-mode preservation and shared-Scene3D contract

Status: **STANDARD VISUALIZER — MODE-OWNED.** Sphere is normally selectable in Settings and Guided Setup, uses canonical per-mode activation/preset/reset semantics, and remains independently removable, lazy and dormant when inactive. Standard product admission does **not** promote Sphere reaction/state semantics into shared Visualizer architecture.

## Current golden

Sphere is a standard Visualizer mode whose enablement comes from canonical `mode_activation`; its accepted look and response are preservation inputs, not permission to collapse its behavior into the shared carded-mode implementation. Ordinary-widget semantic Edit/lifetime machinery is not part of Sphere's viewport ownership.

The accepted representation is the stepped voxel shell, not the retired smooth icosphere. The musical *vocabulary* is the preservation target: strong/local detached fragmentation, granular event-owned intake/outtake cohorts, stable four-corner population identity, sustained body growth, event-stepped tracer travel, continuous rotation and the vocal-linked intake recoil. Its reaction *numbers* are not (operator 2026-10-04): the S19 ramp retune makes small sounds and near-silence deliberately calmer. Presentation or cleanup work may not make loud passages or big hits quieter or slower to react, nor the mode less spatially articulate or more ambient/free-running.

Two original Sphere goldens remain (two additional Rainbow variants are separately curated):

| Preset | Name | Golden role |
| --- | --- | --- |
| 5 | **Glass Current** | Former Preset 5 / Transparent React snapshot (Preset 1 until 2026-10-04, when Mirror Ball took slot 1). Intake (`Particle Outtake` off), translucent fill and bright independent edges preserved. |
| 2 | **Voxel Bloom** | Former Preset 6 / Reactive Voxel snapshot. Opaque neutral presentation and Sphere shadow enabled. |

The historical reference contains test-owned frozen settings. `sphere_golden.py` always replays those same settings, including for `--write`, and never seeds from curated slots. The curated files are operator-authored content, not a test oracle. The active substrate promotion must preserve resolved behaviour, not merely names or superficially similar slider values.

## Consolidated Sphere event/cohort investigation

The five September 10 incidents about silent intakes, density, velocity and corner continuity are preserved together in `Docs/Historical_Bugs/Sphere_2026-09-10_Acoustic_Admission_And_Cohort_Motion_Investigation.md`. The lasting distinction is **source active ≠ live acoustic energy ≠ transient confidence ≠ particle population ≠ per-cohort speed**. A new cohort needs current pre-AGC energy and a qualified event, not a stale playing flag or held gate. Shared event confidence may saturate at 1.0 and cannot alone set maximum velocity; local onset contrast/flux accents and stable per-cohort launch state own travel. Passage loudness is not population authority. Each quadrant keeps a stable voxel-seed rank; dominance affects only the feathered fringe, without re-ranking the entire shell. New events must not teleport or accelerate existing cohorts. Specific historical threshold/population percentages are evidence, not immutable operator-curated preset defaults.

## Isolation / ownership contract

### Consumed controls and source seams

`config_applier.py` owns configure-time Sphere parameters; `sphere_capture.py` supplies immutable frame input to
`SphereFrameRuntime`, and `sphere_voxel.py` consumes its result. The following field suffixes use the `sphere_` prefix.
This is a consumer inventory, not another settings/default catalog; the canonical model/descriptor and Settings binding
remain authoritative for persisted fields and ranges.

| Consumer | Controls that reach it | Meaningful boundary |
| --- | --- | --- |
| Logical event admission | `fragment_energy_floor`, `particle_energy_floor` | Acoustic gates after typed/event-spectrum qualification; quiet/inactive sources cannot author cohorts |
| Logical fragment/flow response | `fragment_interpolation_enabled`, `incoming_density_response_enabled`, `incoming_transient_velocity_enabled`, `particle_outtake_enabled`, `vocal_response` | Section easing and immutable cohort density, event velocity, intake/outtake direction and vocal recoil |
| Logical body/tracer motion | `size_response`, `light_tracer_enabled`, `base_rotation_speed`, `rotation_speed` | Body growth, event-stepped tracer travel, continuous base rotation and musical velocity reaction |
| Voxel transform | `fragment_strength`, `particle_distance`, `particle_amount`, `perspective_strength`, `voxel_size_variation`, `fade_incoming_blocks` | The same hero/shadow vertex transform; bounded section displacement, travel/population, projection, cube size and replacement fade |
| Surface material | `fill_color`, `edge_color`, `tracer_color`, `edge_weight`, `gloss`, `specular`, `light_direction`, `cel_shading`, `depth_shading_enabled`, `depth_shading_strength` | Literal independent RGBA, face lighting, edge thresholds, tracer colour, cel quantization and rear-depth luminance; audio does not recolour the material |
| Rainbow | `taste_the_rainbow_enabled`, `taste_the_rainbow_surfaces`, `taste_the_rainbow_edges`, `taste_the_rainbow_speed`, `taste_the_rainbow_extent` | Independent surface/edge switches, phase speed and spatial hue extent; canonical `0.05` / `0.22` preserve the accepted field |
| Shared source analysis | `bar_count`, `audio_block_size`, `adaptive_sensitivity`, `sensitivity`, `dynamic_floor`, `manual_floor`, `input_gain`, `transient_clamp`, `analysis_notch_positions` | Analysis band count, PCM block size, FFT sensitivity/floor/gain, transient clamp and exact two selected frequency splits |
| Projected shadow | `shadow_enabled`, `shadow_opacity`, `shadow_softness`, `shadow_distance`, `shadow_size` | Actual voxel silhouette, optionally one expanded feather layer; disabled/zero-opacity does not issue a shadow draw |
| Presentation resources | `allow_overflow`, `mirror`, shared `scene3d_detail` and displayed `backdrop` | Stable authored reach, tier multisampling/reflection admission and window-owned wallpaper copy; no music-driven target resize |
| Settings-only finish bundle | `finish` | UI selection writes Gloss/Specular; the renderer consumes those two axes, not a separate material selector |

Source input is generation/activation-fenced current playback. Support-aware bands supply spatial articulation; live
pre-AGC energy supplies body presence; the immutable pre-shape/pre-AGC spectrum supplies generic onsets; musical level and
intensity supply passage-relative qualification; the existing typed event scheduler supplies kick/snare/vocal/onset packets.
No Sphere FFT, source manager or audio clock exists. `get_technical_profile_mode("sphere")` selects Sphere's own profile.
Descriptor metadata selects only its eight consumed technical fields; the complete shared-worker API resolves unused output
knobs from canonical engine defaults, never mutable Spectrum settings. The selected notch record owns only the first and
penultimate interior fractions consumed by the worker, with no unused Spectrum shaper nodes. Spectrum shape/ghost
presentation controls are not Sphere controls. Existing audio-contract tests and the frozen
promotion golden protect event/response vocabulary; visual control usability and standard-mode promotion have now received operator physical acceptance (2026-10-09).

### Shared frame upload and retirement

Hero and shadow programs declare the same `SphereFrameBlock` through `Scene3DBlockLayout`. Its fixed-size section/cohort
arrays use standard std140 strides; one shared `UniformBlock` streams the immutable transform and material values through
the existing context-local `StreamRing`. The current block has **50 fields / 1008 bytes**, including authored Rainbow extent;
its aligned hero/shadow/outtake copies remain within the existing fixed ring capacity. Shadow layer overrides and outtake pass selection write separate bounded copies,
so submitted draws retain their own projection/pass values. Sampler-unit assignments occur once per linked program;
wallpaper names are bound together per frame. Shader arithmetic, mesh/instance identity, draw order and reaction state stay
Sphere-owned.

The ring allocates only on the admitted renderer's prepared reveal or first draw. Program attachment alone allocates no
stream. The normal renderer `has_resources` and retirement path include the block/ring alongside `MeshResources`,
`SceneTarget` and `BackdropEnvironment`; failed cleanup remains a loud error with its existing owner, and a later release
can retry. Each hero/shadow scope stays within the shared fixed per-frame capacity, including outtake; no larger Sphere pool,
background preparation or cleanup poller exists.

- The descriptor remains independently enabled/disabled with lazy Settings builder, capture, frame runtime and renderer. Heavy resources stay dormant while disabled and retire through the existing render-context lifecycle.
- Canonical persisted state remains in the existing `sphere_*` namespace. Do not invent a private Settings manager/default store, and do not promote Sphere into shared setting families merely for tidiness.
- Sphere declares its consumed technical subset and its private Taste the Rainbow controls. Shared bar appearance and the older generic Rainbow family remain absent; its literal fill/edge/tracer RGBA and richer field stay Sphere-owned.
- Visualizer schema v10 seeds missing owned analysis fields once from the former **RAW** Spectrum profile, including the selected mirrored/linear notch fractions, before default filling. An active Spectrum preset never supplies this bridge. Explicit Sphere fields survive, subsequent Spectrum edits cannot alter them, and Custom snapshots normalize through the same canonical model.
- Legacy mode-local Custom snapshots seed missing analysis from the same persisted RAW source section, preserving explicit cached fields. SST normalization passes the complete incoming RAW source to that same cache authority before processing sections, so nested/flat payloads and cache-first order retain exact historical analysis values.
- Existing BeatEngine spectrum/live-pre-AGC/musical-level (`get_musical_level`) seams remain read-only consumers of already-authored analysis. No second FFT, worker, timer, poller or private cadence is allowed.
- Product acceptance does not authorize extracting Sphere behavioural internals into shared infrastructure. The active promotion authorises sharing low-level GPU/resource/material/post/compute infrastructure only; Sphere reaction/state semantics remain private.

### What is reusable from the experimental-isolation method

The **boundary mechanism** remains valuable: descriptor-driven lazy Settings/runtime/renderer/capture resolution, independent enable/disable/dormancy, a private persisted prefix where behaviour is mode-specific, explicit capability metadata and normal renderer retirement. Sphere itself is a legacy exception because it was built before shared Scene3D. **Future experimental modes must use the canonical shared low-level Scene3D/compute/resource/material/quality substrate from their first implementation.** Experimental status may keep them default-off and behaviorally private; it must not create a private GPU engine that later requires a second "promotion" job.

Do **not** generalize Sphere itself to achieve this. `sphere_*` parameters, Sphere audio/voxel logic, hard-coded Sphere capability memberships and Sphere shader semantics remain private implementation. The completed substrate promotion does not authorize extracting or refactoring those behavioural owners into a shared experimental framework. Reusable isolation means a reusable **host seam**, not a reusable Sphere feature stack.

## Current Settings hygiene

Sphere Custom now uses the shared themed circular checkbox styling and collapsible bucket scaffold while all persisted/runtime ownership remains Sphere-local. Recommended slider notches are presentation-only hints matching the accepted **Glass Current** baseline; they are not defaults and do not alter saved or runtime values.

The lazy Settings body exposes the descriptor-selected analysis controls as **Analysis Bands**, PCM block size,
sensitivity, noise floor, input gain and transient clamp, with two **Frequency Zones** splits. Direct fill, edge and tracer
opacity edit each existing RGBA alpha byte; there is no competing opacity setting. Quiet preset hydration preserves exact
analysis fractions and does not save or switch to Custom. Each curated look explicitly owns the complete consumed analysis
record and Rainbow speed/extent; default/Reset and Custom persistence use the normal Settings/preset authorities.

The following experimental-era controls had no live runtime/render authority and are fully retired rather than displayed disabled: `sphere_surface_detail` (old Block Relief), `sphere_bass_response`, `sphere_mid_response`, `sphere_high_response`, `sphere_energy_curve`, and `sphere_idle_motion` (old Idle Drift). **Base Rotation** is the sole continuous idle rotation authority; **Velocity Reaction** adds music-driven rotation velocity.

The formerly overloaded `sphere_deformation` + `sphere_bump_reactivity` pair is also retired as canonical state. Visualizer schema v8 first migrates their exact resolved local-displacement product into **Fragment Strength** and copies the old Deformation value into **Particle Distance**, then strips both legacy keys. **Particle Amount** is a renderer-side post-admission population multiplier (`1.0` preserves accepted behaviour), and the UI label for the existing density-response toggle is **Particle Density Response**. Vocal Response stops at its existing effective ceiling (`1.35`); Size Response stops at the existing growth saturation (`2.54`).

**Everything ramps (operator 2026-10-03/04):** near-silence fragmented and launched particles as fully as a full blast, and nothing ramped. Causes measured on recorded music (`tools/visualizer_replay/record.py`, 2026-10-04: "Rag Doll", "I Said Hi", "Human", "Into Your Room"): the gates and floors compared the live pre-AGC lane, clamped at 2.5 and pinned in 80-95% of frames; event sources are loudness-blind; admission rate never depended on the music; the tracer's light never faded while it travelled (pinned ~1.0); the body grew from the pinned lane. Now every reaction ramps on the shared **passage intensity** (`BeatEngine.get_musical_intensity`, `transient_bus.PassageIntensity`: how loud the heard passage is on the fixed real-music scale, 0..1, 0.65 at the usual loudness 8.5, 0 in near-silence; 2026-10-04: every version that learned a level from the track, a falling peak and then a 20 s usual level, made Sphere overreact after a Settings rebuild or preset hotswap and fade inside a sustained chorus; a hit's standout is likewise its own loudness on that scale): how often fragments, particle cohorts and tracer steps may fire (`_ramp_interval`: 0.9 / 1.6 / 0.8 s at the quietest down to the accepted 0.16 / 0.26 / 0.09 s at the loudest), what each earns (`_ramp_reward`: the shared near-silence rule x a convex ramp from 0.2 x how far the event stands above the track's usual level), tracer light and speed, spin velocity and the slow body growth. Measured (`python -m tools.visualizer_replay.sphere_ramp`, Glass Current, quiet / usual / loud passages, four songs): fragment bursts 3-4/s flat -> 0.1-0.75 / ~1.5 / ~3 per s, fragment size 0.10 / 0.15 / 0.31, particle launches inverted (Human quiet 11/s, loud 4/s) -> 0.6-1.9 / 2-3 / 4-4.7 per s with strength 0.15 / 0.3 / 0.5, tracer 1.0 flat -> 0.45 / 0.6 / 0.7, spin 0.6 flat -> 0.25 / 0.39 / 0.53, body 0.19-0.25 / 0.24-0.29 / 0.27-0.31. Loud passages keep the accepted cadence and strength. Event qualification, sources, the hysteretic gate and the live-lane real-silence floor are unchanged.

**Independent acoustic-floor controls:** The fragment Energy Floor and particle Energy Floor are Sphere-only thresholds on the 0..1 passage intensity (0 the track's quiet passages, 1 its loud ones), evaluated after the existing typed/onset candidate qualifications. (They used to compare the saturated live lane and so never bit.) The fragment floor defaults to `0.000`, applying no extra admission filter; the particle floor defaults to `0.075`. Both controls use `0.001` steps across `0.000..1.000` and have separate persisted `sphere_fragment_energy_floor` / `sphere_particle_energy_floor` keys in canonical defaults, Custom, and curated Sphere preset snapshots. Older user-authored preset payloads missing the keys receive these same defaults. The particle slider cannot defeat the separate real-silence presence safeguard; it does not tune population, velocity, or in-flight cohorts. The fragment floor changes neither tracer admission nor particle admission or packet amplitude. Do not change the shared event scheduler, pre-AGC spectrum, renderer, or other visualizer modes to implement these controls.

**Detached-particle population authority:** Particle Density Response must remain post-admission and independent of absolute passage loudness. Loud beds are allowed—and required—to retain strong kick/vocal reactions. Qualified cohorts keep the accepted visible participation floor, then event confidence plus Sphere-local granular motion evidence determine population; full population is exceptional. The Sphere-local presence gate also has a current near-silence authoring floor, so a recently-open hysteretic gate or latched typed event cannot create a new cohort from residual near-silence. Do not implement either rule by raising shared transient thresholds or weakening loud-passage events.

Rainbow Ghosting is likewise retired and forward-stripped. Sphere now has its own isolated **Taste The Rainbow** presentation controls for Surfaces and Edges; they are not `sphere_rainbow_*` keys and do not opt the descriptor into the shared Rainbow family. The voxel shader uses one moving partial-spectrum field across blocks in the existing draw while retaining authored Fill/Edge alpha. **Perspective Strength** is also Sphere-local and deliberately one-sided: `1.0` is the accepted camera projection exactly and `0..1` may only flatten toward orthographic, never intensify projection beyond the golden envelope.

Additional presentation controls expose existing renderer constants rather than inventing new behaviour: **Edge Weight** defaults to `1.0`, which resolves to the accepted `0.72 -> 0.90` face-edge thresholds; **Voxel Size Variation** defaults to `0.35`, the former fixed shader constant; and **Tracer Color** defaults to `[255,242,194,255]`, the former hard-coded warm tracer colour. **Depth Shading** is the only new visual effect and defaults off. When enabled it applies a restrained rear-hemisphere luminance reduction from already-transformed voxel depth in the existing shader; it samples no neighbouring voxels, adds no AO/reflection/shadow pass and does not alter hue, alpha, geometry or audio authority. These controls remain private Sphere parameters under standard product admission.

The current Sphere drop-shadow implementation is a **projected voxel silhouette**, not the old circular proxy and not voxel-to-voxel lighting. Shadow and hero compile the same Sphere vertex shader and consume the same rigid rotation, fragmentation, size pulse, tracer-local turns, perspective and intake/outtake cohort transforms. The shadow fragment contributes flat inherited shadow colour only. Sphere-local **Shadow Opacity / Softness / Distance / Size** controls parameterize this pass; softness may add one expanded instanced feather layer, while disabled/zero-opacity shadow adds no second shadow clear/draw. Do not generalize this into shared 3D shadow infrastructure unless another concrete consumer proves the same contract.

## Promotion replay reference and future-change preservation gate

For future shared-substrate changes, retain the *test-owned* replay and visual preservation evidence for **Glass Current** and **Voxel Bloom**, rather than freezing the current user-authored presets, with:

- their exact persisted Sphere snapshots, including presentation baselines such as Edge Weight `1.0`, Voxel Size Variation `0.35`, the accepted Tracer Color and Depth Shading disabled unless explicitly re-authored;
- the exact resolved hidden technical profile/settings that reproduce today's behaviour;
- fixed deterministic `FeatureFrame` / existing Visualizer replay input covering silence, flat/low qualified events, vocals, kicks/drums and sustained passages;
- Sphere logical outputs important to behaviour: event admission/source, section drives, tracer phase/drive, size pulse, rotation, cohort admission/density/velocity/direction/progress and vocal recoil;
- representative renderer captures at ordinary and extreme CUSTOM aspect/scale where the existing capture seam can provide deterministic evidence;
- baseline replay evidence for every accepted comparison mode represented by the maintained replay-floor cohort over the same shared-analysis change boundary.

**Captured 2026-10-04** (`tools/visualizer_replay/sphere_golden.py`, `tests/test_sphere_promotion_golden.py`):

- *Behavioural:* one deterministic real-scale clip (silence, kicks + snares, a flat/low passage after them, vocals,
  a sustained loud bed, a big hit, a quiet outro, silence; quiet passages follow loud ones so the passage ramp is
  exercised) replayed through the production capture for Glass Current, Voxel Bloom and Voxel Bloom with Particle
  Outtake on (the curated snapshots currently all choose intake). Every authored `SphereFrame` field per frame
  (drives, phases, incoming section/blend, every cohort's progress/strength/density/section/lane/velocity/recoil/
  direction), the resolved hidden technical profile (Spectrum-backed: bar count 33, sensitivity 0.4, block 512,
  dynamic floor 0.12, AGC 0.5, ...) and each preset's resolved parameters: `historical sphere promotion replay reference (not bundled in this GODZIP)`.
- *Visual:* the production render host offscreen on replayed snapshots: both goldens at rest, mid-kicks and on the
  big hit (480x270 item), and extreme CUSTOM wide (960x120) and tall (200x600) through the production presentation
  resolver: `tests/goldens/visualizer_replay/sphere_visual/` (bit-identical run to run).
- *Historical cost* (`tools/visualizer_cost_probe.py sphere --size 2560x1440`): CPU submit median 0.44 ms / p90 0.47,
  GPU 0.03 ms. Its reported 17 Python GL calls omitted Sphere's renderer module and is not a complete call baseline.
- *Accepted comparison cohort:* the maintained replay floors (`historical visualizer replay-floor reference (not bundled in this GODZIP)`).

The 2026-10-07 shared-frame migration adds Sphere, shared uniform blocks and the raw stream multi-bind to the existing
cost probe's call counter. A same-process-code baseline comparison loaded the pre-migration renderer from Git in a
separate process, without changing the tree: High detail, shadow/softness `0.18`, `960x540`, 90 frames after 15 warm frames.
Two interleaved runs measured CPU submit median `0.490–0.504 ms` before and `0.433–0.457 ms` after; a separately counted
run measured `185` versus `78` GL calls. Whole-host GPU median stayed around `0.025 ms`, but its p90 rose from about
`0.026 ms` to `0.21–0.33 ms`. Draw-only diagnostic queries measured voxel draw p90 `0.0102 ms` before and `0.0133 ms`
after: the larger whole-host tail includes submission/stream intervals rather than a corresponding increase in voxel
draw time. This is scoped offscreen evidence; loaded-desktop p90 comparison remains historical scoped evidence; source behavior and physical mode acceptance are complete, and only new concrete symptoms reopen this audit. No behavioural
or visual golden was rewritten for this migration.

Presets are authored content and never tested against (operator 2026-10-04). Every case is wholly test-owned:
its resolved Sphere settings are frozen in the historical reference and replayed unchanged even when using `--write`.
Missing cases fail rather than silently reading a current curated preset. Only behavioural frames can fail the
replay comparison; settings and the technical profile are informational. GL visual cases test visibility, musical
state changes and Mirror Cubes' observable effect rather than equality to obsolete PNGs. Optional `--visual`
before/after sheets remain for human assessment. Captures render at pinned High detail against a synthetic
wallpaper (no personal photos in the repository).

**Mirror Cubes** (`sphere_mirror`, 0..1, default 0, presentation-owned like Extruded's Mirror Faces; operator
2026-10-04): the cube faces (never the edge lines or the tracer) become polished mirrors reflecting the displayed
wallpaper (the owner's small copy, `backdrop_setting`, on 3D Detail tiers with reflections), each face by its own
rotated normal toward a near virtual eye, so faces show different parts of the picture and it slides across them as
the shell turns; as sharp as the greater of Gloss and Mirror Cubes, highlights kept on top, faintly tinted by the
fill, a mirrored face more opaque. Mixed in display space after Sphere's tone map so the photograph reads as itself.
A new wallpaper crossfades in the reflections alongside the image transition that brings it (from its start, over its duration; 2 s without one) and the first fades in (`BackdropEnvironment`), never a one-frame switch. Curated **Preset 1 (Mirror Ball)** shows it off: silver cubes, thin graphite edges, full Gloss and Mirror.

`python -m tools.visualizer_replay.sphere_golden` prints the per-segment summary and what differs; `--visual` writes
before/after sheets to `logs/sphere_visual_review/` for review by eye. `--write` refreshes **behavioural output**
using the same frozen test-owned inputs. `--write-visual` is optional, manual review evidence, not a required
step to repair CI after a legitimate renderer change. Neither operation reads curated preset values.

For any future shared-resource change, replay the same test-owned evidence. Sphere's behavioural golden is a **historical reference, not a lock**: the 2026-10-04 replay identified under-reactive and overactive bands, after which the mode-owned passage ramp was retuned and operator-accepted. New work must compare against test-owned preservation inputs, not today's mutable curated preset contents. Promotion is rejected if event ownership, the response vocabulary, voxel/cohort identity or source freshness are lost, if loud passages or big hits react less strongly, if a behavioural difference is not measured against the golden and intended, or if the recognisable stepped-voxel/preset identity is lost, **or** any accepted permanent mode changes in reactivity, latency, source freshness, visual fidelity, cross-mode bleed/isolation, cadence, lifecycle, CPU/GPU resource behaviour or dormancy. Pixel-for-pixel visual parity is not the objective: improved antialiasing, lighting, material/depth readability, shadows, reflection/refraction or other presentation quality is welcome when it is demonstrably better and preserves musical response, silhouette/voxel identity and preset intent. Technical controls require particular caution because the formerly hidden RAW resolved values are preserved behavioural input at migration.

The existing deterministic Visualizer/`FeatureFrame` replay seam is the preferred foundation. Extend it only as needed; do not build a Sphere-only second replay engine.

This gate removes competing low-level 3D architectures. Promotion
means moving Sphere onto the shared `rendering/quick/scene3d/` GPU/resource/material/post/compute substrate while
preserving the complete behavioural golden above. It does **not** authorise retuning/renaming Sphere behavioural state, replacing its logical runtime, or turning Sphere
into a base class. R150 already replaced Sphere's old hidden Spectrum-profile projection with a Sphere-owned **analysis-only** policy, retaining required acoustic inputs while skipping the Spectrum visual shaper; Shockwave intentionally retains its shape output. Do not reopen that completed migration or reseed tests from curated presets.

## Current shared-boundary rule

Sphere-specific presentation controls remain confined to Sphere-owned descriptor/capture/runtime/renderer/config branches. Permanent-mode runtimes/renderers and shared logical analysis must not gain Sphere-specific behavior merely to tidy the experiment. The low-level shared Scene3D substrate is the accepted presentation path; further behavioural extraction requires separate approval and a test-owned preservation gate, not another migration programme.

## Accepted energy-floor control boundaries

The independent fragment and particle minimum-energy settings are implemented with curated/default and user-authored preset protection.

- Native Settings/preset controls preserve independent fragment and particle energy floors.
- Each floor affects only its own event admission path.
- Near-silence and quiet intros stay calm (no full fragmentation or particle bursts); a pause's
  first quiet frames throw nothing, loud passages and drops react as before.
- Reset restores the canonical authored defaults.
- Custom Save/reopen preserves user-authored values.

Do not retune authored values on the operator's behalf.

## Shared camera and drag-release inertia (current)

The mode's shared Scene3D view (turn and tilt) comes from presentation pose, not the voxel shell's continuous audio/base spin. Alt+left dragging steps that view directly. Release samples the last admitted drag velocity, adds one finite cubic ease-out tail on the **existing** logical capture clock, and writes the final camera pose once to the canonical mode-owned view-settings authority. A new drag, held-key motion or preset rebase cancels the stale tail without a snapback or extra resource owner. Sphere orbit and inertia are operator-accepted; reopen only on a concrete drag or momentum regression. See `Current_Plan.md` and `tests/test_visualizer_view_orbit.py`.

Extruded shadow geometry is unrelated: that rejected optional cast pass is centrally disabled; do not reenable it as part of Sphere/parity work.
