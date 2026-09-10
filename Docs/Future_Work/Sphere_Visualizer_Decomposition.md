# Voxel Sphere visualizer

Status: **ACTIVE EXPERIMENTAL ITERATION — smooth Sphere retired; voxel shell passed the first eyes-on bar and is now being tuned for causal musical response.**

Working checkpoint baseline: GODZIP source HEAD `c45845d44d21537ca4c09be41f6decf4cde0d16a` plus the current Future Work isolation rules. The mode remains dormant-by-default and does not block migration closeout.

## Decision that produced this checkpoint

The previous smooth deformable icosphere failed the visual bar. Obsidian was only marginally acceptable and the rest read as malformed smooth geometry. Its attempted fragment-derivative silhouette AA could not create triangle coverage outside the rasterized edge, and its analytical cast shadow lived inside the clipped Visualizer item rather than a true scene-owned shadow seam. Preserving that renderer for comparison or first polishing it into architectural purity would be sunk-cost work.

Therefore the smooth implementation was removed directly. There is no parallel old renderer, comparison toggle or rescue branch.

## Current representation

Sphere mode ID remains `sphere`, now displayed as **Voxel Sphere (Experimental)**.

The renderer owns exactly one Sphere-local 3D geometry foundation plus optional Sphere-local presentation passes:

- one static 36-vertex cube mesh;
- one static stepped lattice shell instance buffer (radius-5 shell, 278 instances);
- one primary instanced shell draw/program;
- one flat 2D shadow program that uses the inherited shared quad only when Sphere's own Drop Shadow checkbox is on;
- one bounded rainbow-ghost program/history path used only when the Sphere-owned checkbox is enabled; the ghost fragment path is gated to reactive/moving cubes so the full shell cannot accumulate into a white bloom;
- the existing bounded depth/scissor state needed by the Quick Visualizer render item.

There is still no generic Sphere/3D subsystem: disabling/switching away from Sphere retires these renderer-owned resources through the existing mode renderer lifecycle. Accepted visualizers neither compile these programs nor retain the ghost history.

The shell intentionally preserves integer-lattice stepping. Each cube carries only a static centre/seed plus patch-local radial polarity. Musical locality is no longer stored as a fake per-cube Spectrum height. `SphereFrameRuntime` authors eight bounded spatial section envelopes and the vertex shader applies smooth angular distance falloff from those fixed 3D section centres, so nearby blocks move strongly and remote blocks receive zero authority.

The rejected smooth-only resource islands are gone: no icosphere topology, tangent-sampled deformed normals, liquid/fire auxiliary meshes/programs, derivative silhouette-AA path or clipped pseudo-shadow program/mesh.

## Settings / single-authority contract

Experimental isolation does **not** mean a second Settings authority.

All surviving Sphere values remain in the canonical `widgets.spotify_visualizer` settings/default/model path and save through the normal SettingsManager. The lazy Sphere Settings body merely edits that owned canonical block.

Surviving canonical values remain representation-owned, but several legacy experiment controls are temporarily disabled/inert while the voxel contract is proven. The live operator controls are now:

- Settings-only **Finish Preset** convenience: Custom / Neutral / Matte / Plastic / Polished / Metallic / Glassy. It only writes the visible Gloss/Specular sliders and is never sent to the renderer;
- independent literal **Fill Color** and **Edge Color** swatches;
- Deformation, Block Reactivity and **Size Response** (staged slow sustained growth only);
- Vocal Response;
- **Base Rotation** (`sphere_base_rotation_speed`) and **Velocity Reaction** (the existing `sphere_rotation_speed` persisted key);
- light direction, materially visible Gloss/Specular;
- optional **Toon Shading**, **Drop Shadow**, Scene Overflow, Incoming Fade and default-off **Rainbow Ghosting**.

Bass/Mid/High/Energy-Curve/Idle-Drift and Block Relief remain canonical persisted keys but are disabled/inert during this experiment. The old Palette Effects/material pseudo-shading keys were retired instead of preserved because they directly contaminated voxel finish diagnosis. **Size Response is live again** and owns only slow sustained passage-weight growth; it is not a transient pulse. The sustained owner is adaptive to the current song: it tracks a local quiet floor and recent peak, then maps their relative span through four ramped stages. A constant loud source therefore calibrates as baseline rather than pinning the shell swollen, while a genuine quiet→heavy transition can earn a distinct upper stage.

The obsolete `sphere_antialiasing`, `sphere_shadow_strength`, `sphere_rainbow_enabled` and `sphere_rainbow_speed` keys remain retired. `sphere_shadow_enabled` has been deliberately reintroduced as a **Sphere-owned** canonical Drop Shadow checkbox; it is not a shared/card-shadow escape hatch.
Sphere therefore advertises no per-mode Rainbow Settings capability and no owned shared bar-appearance key family. Descriptor flags are capability/routing metadata only: canonical defaults remain the sole persisted-value/key authority. The generic Settings UI skips those non-owned families, while the non-persisted runtime presentation mirror resolves the descriptor-declared canonical Spectrum shared-bar profile. No `sphere_bar_*` defaults are invented. Shared consumers must use the canonical family key/profile resolver rather than manufacturing `{mode}_...` keys, and focused coverage must fail if descriptor participation/profile routing and canonical key ownership ever diverge.

## Technical-profile contract repair

Sphere deliberately has no ordinary per-mode technical controls. The previous shared runtime nevertheless assumed every active mode had `technical_cache[mode]`, which made the experiment an unsafe template.

The descriptor now owns an explicit `technical_profile_mode`. Empty means “this mode owns its own profile”; Sphere names `spectrum`. Shared startup/mode-switch configuration resolves the descriptor-owned profile generically. There is no `if sphere` fallback and no second technical/default authority.

This is the pattern future experimental modes may use when they have no dedicated technical-control UI but still need deterministic BeatEngine input configuration.

## Cadence / dormancy / lifetime

`SphereFrameRuntime` remains the sole owner of activation-relative authored time, eight 3D spatial section envelopes, the staged slow sustained-growth envelope, optional tracer articulation, and monotonic rotation phase. `sphere_capture` reuses the existing public support-aware Bubble energy feed plus the existing consume-once event scheduler; it does not consume saturated Spectrum bar heights as displacement authority and creates no second audio worker/cadence. The renderer consumes immutable section drives passively, applies only spatial distance falloff, advances no simulation, and reads no live Settings/QObject/engine state.

Disabled/default startup must not import/construct the Sphere Settings body, capture/runtime implementation or renderer resources. Active renderer resources are context-local and retire through the existing event-owned visualizer renderer retirement path. No polling loop, worker or independent timer exists.

## What may be reused later

Keep because it is already shared architecture, not because Sphere used it:

- descriptor-driven lazy runtime/capture/renderer/Settings-body resolution;
- immutable logical-frame transport;
- context-owned renderer lifetime and explicit retirement;
- Quick render fence / GL-state ownership;
- existing viewport/projection ownership and bounded depth clear.

Potential second-consumer candidates, **not yet shared abstractions**:

- one static cube mesh + one static instance buffer;
- tiny instanced-mesh binding helpers;
- identical 3D projection/depth helper math if another independent consumer actually matches it.

Exploding Tiles is the obvious future falsifying consumer. Extract only the smallest identical seam when it exists. Do not grow a generic SRPSS 3D engine, material hierarchy, camera tree or physics owner from this one experiment.

## Transition boundary

3D transitions may reuse low-level GPU primitives but must keep finite transition lifecycle/source-texture ownership separate from the persistent Visualizer logical/audio runtime. Slide extras such as Elastic/Wobble/Flex remain accepted-owner modifiers and are not forced through experimental plugin isolation simply because they bolt onto Slide.

## Acceptance / retirement gate

The next work is deliberately eyes-on, not another architecture tranche:

1. inspect the voxel Sphere physically under active audio and quiet/idle state;
2. inspect ordinary and CUSTOM aspect/scale changes and all five palettes;
3. confirm switching away retires the renderer cleanly and logs no new authority/lifecycle failures;
4. if the voxel representation looks worth keeping, tune it only inside this owned boundary;
5. if it still looks bad, retire `sphere` completely and strip its owned persisted namespace through one explicit retired-mode/key migration.

The voxel representation may receive further bounded iterations while physical evidence continues to show useful progress. Do not revive the rejected smooth renderer or create a parallel representation merely to avoid fixing the current mapping.

## Focused automated contracts

- voxel geometry is deterministic, finite, stepped and symmetric;
- one cube mesh is 36 vertices and one shell is 278 static instances;
- Sphere descriptor exposes no technical controls but resolves the canonical Spectrum technical profile;
- ordinary technical modes continue to resolve their own profiles;
- canonical default snapshot matches the generated default authority;
- changed Python compiles before checkpoint packaging.
## Causal voxel reaction checkpoints — 2026-09-09

Physical testing has rejected six audio mappings/iterations while retaining the voxel representation itself:

1. **Free-running phase mapping:** time chose block movement and music only modulated unrelated procedural wriggle.
2. **Global static-mask mapping:** every block still consumed the same global signals, producing larger flicker and near-uniform movement.
3. **33-lane rise/event mapping:** the source Spectrum profile is routinely saturated near `1.0`, so recent-rise authority became nearly absent; consume-once kick/vocal events were also too sparse to provide continuous musical motion. The result was ~99% visually pinned blocks with only rare 1–2 px reactions.
4. **First support-aware section mapping:** finally produced causal local movement, but physical acceptance found only ~20% of the required displacement, weak response during already-loud passages, and mild low-level jitter. The support-aware source is retained; the continuous-target/low-travel motion law is rejected.
5. **Duration/round-robin packet mapping:** detached travel became desirable, but busy passages mechanically walked/fill-lit most octants; one diagnostic run averaged ~7.05/8 active sections and ~4.31 packets per 0.5 s. Round-robin authorship and duration-like packet accumulation are rejected.
6. **First distinct-change/local routing pass:** occupancy improved, but real playback still averaged ~1.58 packets per 0.5 s and rotation remained effectively binary (0.933 mean drive, 0.952 median, >0.90 for 90.7% of active samples). The face-detail fix from this pass is retained; continuous fallback over-authoring and the peak-held rotation reservoir are rejected.

Current reaction contract:

- **Do not use saturated Spectrum height or sustained band level as fragmentation authority.** Sphere reuses the existing public support-aware Bubble energy seam and immutable transient/event snapshot; it does not invent another audio worker or alter the shared transient bus.
- **Detached cubes are the punch reward.** Strong events may separate a local patch by a substantial fraction of the shell radius; over-authoring must be fixed by admission, never by shrinking the accepted travel.
- **Fragmentation admission is strict:** generic transient crest, support-shaped three-band rise and generic envelope level have **zero packet authority**. Detached packets may be authored by typed `vocal_swell` / kick / snare / onset events or by Sphere-local **peak-picked half-wave spectral flux** over an immutable copy of the existing temporally-unsmoothed pre-shape/pre-AGC analysis spectrum. Flux uses positive log-ratio bin movement with a support gate, adaptive thresholding and a refractory window; held levels and tiny near-zero noise bins cannot keep firing.
- **Packet placement is music-derived, never cursor-derived.** Current spectral balance/brightness plus bounded event classification resolves an octant. Similar material tends to reinforce one local region; round-robin progression is forbidden.
- **Three response timescales are intentionally separate:** punch -> typed/peak-picked spectral-onset fragmentation; unsmoothed live pre-AGC loudness -> staged slow shell/block-size growth; accepted onset events -> optional tracer travel while broader crest/shape evidence may still influence whole-shell rotation. Generic crest/shape cannot detach geometry or keep the tracer alive. Fragment packets remain globally coalesced, but each accepted hit authors a strong region plus one weaker companion region so it reads as a visible event.
- **Sustained growth is not a pulse.** `sphere_size_response` is live and scales only a Sphere-local envelope derived from the existing **pre-AGC** band feed (~0.5 s attack / ~1 s release). The local floor rises extremely slowly and the peak releases slowly so quiet/heavy contrast is not erased immediately. The geometry path has a larger experimental headroom (absolute safety cap near 42%) because the previous 5–10% body range was physically unreadable.
- **Tracer is the intentional version of the useful bright-block accident.** It is rendered as one long/narrow connected spherical ribbon/tail. The tracer has **no free-running phase**: every accepted spectral/typed event queues one bounded angular step, queue backlog is capped, and visible phase advances with a bounded velocity until the target is actually reached. Brightness is held above a stable floor while travel remains and may fade only after settle, avoiding the old stationary flicker caused by decaying drive during unfinished movement. Event rate therefore owns travel demand without permitting runaway speed. Selected cubes may receive only a gentle local tilt before the rigid shell turn, while face/bevel identity remains anchored to the unrotated local face normal.
- **Peak/drop temporal law:** a packet raises its authored section target immediately; targets then decay monotonically with the existing release. Optional `sphere_fragment_interpolation_enabled` changes only rendered displacement: a short critically-damped follower starts moving on the same event frame while keeping cube position/velocity continuous. It may not smooth audio, reduce packet amplitude, delay admission, or become whole-frame blur. Source loss/pause remains decay-only.
- **Temporary statics rather than Settings churn:** Bass Response, Mid Response, High Response, Energy Curve, Idle Drift and Block Relief remain canonical persisted keys but disabled/inert. Palette Effects/material pseudo-shading was explicitly retired because it contaminated voxel finish diagnosis. Deformation, Size Response, Base Rotation, Velocity Reaction, Block Reactivity and Vocal Response remain live.
- **Sustained growth mapping:** use the existing pre-AGC bass/mid/high snapshot with mid-weighted loudness, smooth it, and maintain a Sphere-local quiet floor / recent peak. Normalize inside that span and apply four relative ramps (~0.12..0.30, 0.30..0.48, 0.48..0.68, hard 0.76..0.94 top stage). The floor falls promptly but rises on a ~120 s scale; the peak learns highs promptly and releases slowly.
- **Audio owns geometry only.** Fill colour, Edge colour, Toon, Gloss/Specular, Drop Shadow and Rainbow Ghosting are authored presentation controls and cannot become a second audio-reactive palette/emission owner.
- **Continuity is geometry-local, never whole-frame blur.** The voxel corners are already intentionally soft; temporal frame blending/motion blur is rejected for this pass. Smooth the specific changing geometry state (fragment displacement / ingress fringe), not the finished image.
- **Stable directional lighting + invariant cube definition:** broad diffuse/specular direction is screen-X/Y anchored. Shell Z and rotating cube-face normals have no broad-light authority. Each face carries its unrotated local identity for fixed face tone/bevel UV selection; this physically accepted detail/edge fix must not regress.
- **Finish / bright-block separation:** Gloss/Specular are light-directed per-face finish and must not use a shell-space highlight lobe that selects one/few cubes. Stable unrotated local face identity still selects bevel/UV coordinates; a separately rotated face normal may affect continuous finish lighting only. Any gloss edge line must point toward the fixed authored light and be suppressed on the opposite shell side. `sphere_light_tracer_enabled` is a Sphere-only optional checkbox and is the sole authored moving bright-block snake when enabled.
- **Toon:** hard banding/ink/highlight remains Sphere-only. The physical validation preset uses a neutral mid-tone literal Fill Color so Toon can be judged without any pseudo-material transform.
- **Edge alpha:** edge alpha uses a stronger independent edge mask than the RGB edge mix so opaque edges can remain opaque around translucent fill.
- **Independent fill/edge alpha:** final fragment alpha interpolates from Fill Color alpha toward Edge Color alpha according to edge coverage. A translucent block interior may not force a full-alpha edge transparent.
- **Finish:** the renderer receives only literal Fill/Edge RGBA plus explicit Gloss/Specular/Toon. The historical Chrome/Obsidian/Magma/Silver/Water branches and seed-based per-cube brightness transforms are forbidden. Gloss/Specular operate only as stable per-face sheen whose axes are numerically substantial. Toon uses hard diffuse plateaus, strong edge/ink colour and a hard highlight patch. These remain **physically unaccepted** until an on/off hardware comparison shows an obvious difference.
- **Rotation:** phase remains monotonically integrated. Base Rotation is the continuous floor; Velocity Reaction follows current articulation with fast attack and a short release so speed can rise/fall while playback remains active.
- **Shadow:** literal flat 2D soft quad/disc, offset opposite the selected light and gated by canonical Sphere-only `sphere_shadow_enabled`. Its radius/offset/alpha may grow modestly with the staged sustained body envelope, but it has no voxel Z/cube faces/self-overlap. The prior experimental shared `authored_shadow_enabled` metadata has been removed; ordinary frameless/card shadow admission is untouched.
- **Rainbow Ghosting:** default-off and Sphere-local. Renderer history is bounded and draws only reactive/moving blocks after the hero with ordinary alpha blending; it must never redraw the complete historical shell additively into a white orb. No timer/poller/worker/logical owner exists.
- **Diagnostics:** `[SPHERE_AUDIO]` reports raw analysis-spectrum mean level + spectral flux + adaptive threshold + peak-picked spectral event/band, crest diagnostics, typed events/onset, live pre-AGC loudness, local floor/peak, relative sustained stage/body, tracer phase/queued target, rotation, occupancy and packet-source counts in `vocal/spectral/kick/snare/onset` order. Three-band rise counters are deliberately gone.
- **Accepted visual floor:** detached local travel/fallout and unrotated-face detail remain protected. Causality/finish changes may not reduce that reward or reintroduce rotating face-axis lighting decisions.

The generic Settings-family consumer checklist lives only in the top-level `Future_Work.md` **Experimental isolation + Settings single-authority gate**. Do not duplicate it here as Sphere archaeology.


## Deferred texture / lifecycle concepts after reactivity acceptance

- True textured/reflective voxels are feasible later through explicit per-face UVs or a future environment/scene-texture reflection seam. Do not reintroduce pseudo-fill colour transforms as a substitute for textures/reflections while reactivity is still being proven.
- Event-owned block ageing is feasible: individual cubes can dissolve/fade after a bounded authored lifetime or event count while replacements fade in from distance. Any such lifecycle must stay on the existing logical cadence and must not become a private timer/free-running animation source.

## Isolated presentation/arrival pass — 2026-09-09

- **Lighting space:** broad illumination and the authored light vector are screen-X/Y anchored. Cube face tone/bevel/UV selection uses unrotated local face identity so block definition cannot snap when a rotated normal changes dominant axis. A separate smoothly rotated face normal is permitted only for continuous diffuse/specular incidence; it cannot choose UV planes or move the authored source. Gloss/Specular use light-facing per-face specular + source-edge sheen and remain static presentation only.
- **Toon Shading:** optional Sphere-owned canonical checkbox; presentation-only/default off, using hard bands + strong edge ink + hard highlight rather than the rejected subtle cel approximation.
- **Fill/Edge colour:** independent canonical Sphere swatches. Fill is literal base RGBA; Edge is literal bevel/ink RGBA. No finish preset may alter either in the renderer.
- **Finish preset:** `sphere_finish` is Settings-only convenience metadata. Selecting one writes Gloss/Specular; touching either slider marks it Custom. It is deliberately absent from the renderer parameter bundle. Legacy `sphere_material`, `sphere_material_color`, and `sphere_material_fx` are migration inputs only.
- **Rainbow Ghosting:** optional/default-off, renderer-local bounded history of reactive/moving blocks only, rendered after the hero with ordinary alpha blending plus bounded blur/drift. It must never redraw the complete historical shell additively into a white orb. No timer/poller/worker or shared visualizer history owner.
- **Flat scene shadow:** a dedicated 2D shadow quad offset opposite the selected light, gated by Sphere's own Drop Shadow checkbox, with modest staged growth following the body swell. The rejected 3D duplicate-voxel shadow and shared shadow-admission escape hatch must not return.
- **Scene Overflow:** optional Sphere-owned canonical checkbox. The shared render node bypasses its local visualizer stencil only when a descriptor explicitly names an overflow setting and the immutable mode snapshot has that setting enabled. All accepted modes expose no such capability and stay on the existing clipped path.
- **Incoming Fade / arrival blocks:** optional Sphere-owned canonical checkbox. Curated Reactive/Plastic/Metallic presets may opt in. A sparse subset of shell cubes may be displaced farther outside and fade in while returning. Incoming is independently owned by sufficiently strong typed `vocal_swell` / kick / snare / onset events; generic crest/rise/shape cannot spawn it. Preserve the hardware-observed vocal-linked return/bounce. Successive episodes walk the octants with a coprime stride; each episode combines one broad primary region with a larger sparse whole-shell scatter so it retains focus without overloading one corner. No timer or free-running spawn cadence exists.
- **Rotation split:** canonical `sphere_base_rotation_speed` is the continuous base velocity. Existing `sphere_rotation_speed` remains Velocity Reaction; the boost follows current change demand with fast attack/sub-second release rather than a peak-held multi-second reservoir.
- **Hard isolation bar:** no accepted visualizer changes clip policy, shader, render ordering, geometry contract or Settings family because of these features. Generic seams must default to the pre-existing behavior unless an experimental descriptor explicitly opts in.

### Experimental shared read-seam consumers

The two shared BeatEngine read seams introduced for this experiment are intentionally
consumer-limited:

- `get_pre_agc_analysis_spectrum()` → **Voxel Sphere only**. Demand-published immutable
  tuple from the already-computed `_freq_values`; no allocation occurs unless requested.
- `get_live_pre_agc_energy_bands()` → **Voxel Sphere only** in current production code.
  Reads committed `_pre_agc_live_*` floats; does not alter Bubble/Spectrum/accepted modes.

If another experimental mode needs either seam later, it must consume the existing read
contract rather than add another FFT/worker or a parallel smoothing/normalization owner.
### Incoming distribution contract

Incoming/returning blocks are a secondary event-owned response, not a substitute for fragmentation. The current visual distribution uses four screen-visible ingress quadrants. Three keep approximately a 46% admission floor while one reaches approximately 70%; dominance walks between events. **Voxel ingress rank is stable and may depend only on voxel seed + visible quadrant, never current dominant/event identity.** Dominance changes crossfade only the extra ~24% fringe over ~110 ms, with a narrow rank feather so individual blocks do not binary-pop. Quadrant selection intentionally ignores voxel Z so front/back depth participates in each visible corner. Preserve the accepted vocal-linked return/bounce behavior.

Contingency only: if fragmentation still fails physical validation after the raw pre-AGC onset detector is evaluated, a stronger replacement/accretion layer may be explored where event intensity increases incoming velocity and the number of ~70% dominant corners while shell voxels fade as arrivals replace them. Do not implement that contingency as ambient activity, and do not let it displace fragmentation as the primary intended reactive reward without explicit operator acceptance.

