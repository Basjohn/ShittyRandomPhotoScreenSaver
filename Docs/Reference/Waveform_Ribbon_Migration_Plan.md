# Waveform Ribbon: migration plan (WR-08 controls, reactivity and production port)

Planning owner for **WR-08**, subordinate to [`Current_Plan.md`](../../Current_Plan.md) §7.1 and the lab plan's
WR-08 gates ([`Waveform_Ribbon_Lab_Plan.md`](Waveform_Ribbon_Lab_Plan.md)). The lab owns the look; this document
owns the full production control design, production calibration and the order of the port. A registered production
candidate now connects canonical Settings, two authored presets, visual editors, the sole logical runtime and the
retained scene. A finite user-triggered quiet/middle/peak preview renders that same production body/scene without
a second clock or audio engine. Complete endpoint/framing audits and loaded live admission remain open in
`Current_Plan.md`; existence of the candidate is not acceptance. Core geometry/motion evidence and timing belong to
the lab plan §5.1. The selected grammar is
**C elastic dynamics as primary, with A's accumulated twisting**. Values quoted are the lab
recipes' current values, recorded for orientation: presets are operator-authored and never test oracles.

**Operator direction (1 November):**
- The migration is a **full Visualizer migration**: full controls, Settings and the preset/control systems, designed
  as a whole. Nothing is half-built ahead of it in the lab.
- **Everything a 3D Framed mode like Extruded Bubble has** (scaffolding, camera, presets, technical profile), with
  the projection **defaulting to Orthographic**. Its reactivity and most of its controls are its own: a waveform
  ribbon reacts very differently from EB's bubbles, and its visual editors are unique to it.
- **Every look value is adjustable** in the builder through **user-friendly visual editors**, not raw numbers alone.
- The **shape and reactivity tuner** is the most important new control. It is a tuner, not a free shape builder:
  it can never break the smooth-curve rules. Musical history stays the dominant force.
- **Mist is core** to every preset (the design direction) and becomes optional in Settings.

**Selected implementation (2 November):** C drives elastic bending/lateral/torsional response; A supplies independently
adjustable rolling twist. Add localized colour shifts in highest-power regions, controllable whole-waveform rotation
whose angular speed attacks quickly and decays slowly, particles and rim-rooted strands. Rotation is a waveform
deformation, separate from camera orbit and fixed history travel. Integrate angle from speed on the sole logical clock;
the operator's clarified motion is axial roll, like a skewer turning on its stick (the longitudinal world-x axis in
this scene), not rotation around another point. Its centre stays in place.
All floor/reflection/accent/mist-clearance consumers use the same transformed geometry. Bend, torsion, stretch, twist,
rotation magnitude/speed and visual accents remain customizable. Visual editors and quiet→peak range sliders expose
their actual consumers, with audits of both handles. Smooth fog-fringe grain before the port; floor reflectivity,
colour tint and brightness become settings rather than blocking visual polish. Start with exactly two authored
presets from the primary and alternate examples; preserve all shared framed-3D features and technical/preset systems.

The single live operator-rejection checklist is `Current_Plan.md` section 7.1. It covers missing punch/shape response,
weak particles, strand flicker, highlights/colour, idle/first-play blackout, floor/viewport, grounded near-flat navigation,
rejected mist and deferred rejected UX. Working inputs or range tests do not constitute visual acceptance.

## Production signal ownership and calibration

Waveform selects `raw_musical_signals` through its mode descriptor. The sole existing FFT and transient bus
read fixed-reference raw levels for its musical level, passage and typed onsets, independently of Dynamic Floor.
Every other mode retains its established post-floor bus input. Changing numerical policy replaces musical bus
context and fences detached compute; same-policy settings application preserves it. Digital silence updates the
Waveform raw lanes and bus instead of retaining the previous music. PCM replay requires the current accepted
source and compute-configuration epoch, and reanalyses Waveform's musical bus as well as body bands. Bubble/EB
replay retains its documented recorded-event hybrid.

Own fixed band anchors are `(5.4, 3.1, 1.1)` at reference FFT 256, with the existing measured block-length
correction math. The passage scale maps raw held level `3.4` to the shared usual musical loudness, rounded from
pooled median `3.359` over four 60-second native PCM captures with three-second pre-roll. No song-relative level
is learned. Elastic impulses are expressed as requested normalized spring excursion: the velocity kick is
scaled by the inverse analytic unit-velocity peak for the current frequency/damping. Those controls change timing
without accidentally removing the hit's displacement. Authorable geometry remains smoothly bounded. Particle Admission
selects eligible cohorts with deterministic continuous-rate admission; admitted count and light each follow their own
range once, instead of multiplying count by the same musical strength repeatedly. Birth positions and halo strength
are held world-space records with bounded lifetime/capacity. Strand flicker remains an explicit open operator rejection.
 Event reward uses unclipped magnitude above its recent per-kind onset mean and shared acoustic/passage weighting; typed kick/snare/vocal
impulses have different elastic axes. Raw band routing follows the one eased passage; authorable idle motion is
independent of acoustic rewards. A ready scene survives source-epoch and idle/play changes within its runtime.

The controlled PCM audit (`tools/visualizer_replay/waveform_ribbon_signal_audit.py --mode-output`) produced
identical floor-OFF/ON raw bands, passage statistics, exact typed events and complete body/birth publication hashes
for all four captures. Passage medians at authored gain/block 256:

| Captured window | Median passage |
| --- | ---: |
| ragdoll_quiet_intro_loud_end1 | 0.617 |
| nightsolong_acousticsoft1 | 0.744 |
| human_heavy1 | 0.456 |
| anything_mixed2 | 0.677 |

All fourteen routed drivers retain headroom (no ceiling occupancy in this audit); do not classify these captures
by filename or substitute this source evidence for native musical response. The captures are only 60 seconds,
not full-song loud-section evidence. Remaining native acceptance and rejected UX are owned by Current_Plan.

## 1. Mode shape (shared 3D Framed scaffolding)

- Canonical descriptor and implementation wiring with the framed scene capability; lazy imports; only the active
  mode does per-frame work (Visualizer guardrails).
- Typed logical state and render snapshot on `VisualizerLogicalRuntime` dt and `QuickVisualizerRenderHost`
  resource ownership; generation fences; warm/reveal and inactive disposal. The ring of immutable knots (`RibbonRing`)
  is the logical history; rendering reads packets and never writes history.
- Settings through the shared spec builder (`core/settings/visualizer_mode_settings.py`,
  `ui/tabs/media/spec_mode_builder.py`): the shared preset/advanced/technical scaffold, then closed-by-default
  buckets, one open per level, one-sentence intros, details in tooltips (Settings UX rules).
- Shared framed camera (`core/settings/framed_camera.py`) with a Waveform spec. **Orthographic is the default
  projection**; Perspective is a choice with its own FOV. Turn, tilt, Scene Scale and pan come from in-scene
  navigation as in EB (hidden sliders), with Camera Position as the scene editor.
- Every new control is authored into every preset (preset repair fill plus the completeness guard). Presets stay
  freely operator-authored.

## 2. Starting presets

The lab's named recipes become the first presets, each one scene across quiet and loud:

| Preset | Lab recipe | Look |
|---|---|---|
| 1 — Complete Scene | `complete` | Main fog board: three sheets, cyan → blue-violet → magenta world grade, mist shaped and lit by the waveform, wet columns |
| 2 — Silk Bands | `alternate` | Alternate board: three per-band ribbons coloured by ribbon (quiet blue/teal/lavender, loud magenta/orange/blue-violet), luminous silk, free strands |

Names are suggestions for the operator to rename.

The shared preset store uses zero-based indices: displayed Preset 1/2 resolve stored 0/1. The native capture route is
`tools/waveform_ribbon_capture.py --clip <recording.jsonl> --preset 1 --start 20 --duration 4 --fps 24
--output <new-directory> [--ffmpeg <explicit-executable>]`. It reanalyses original recorded PCM through the production
worker and captures the real logical/frame/retained-render path; audio is not shifted to conceal response latency.

### Production ownership

`core/waveform_ribbon_authoring.py` strictly admits matrix, ribbon cards and gradient nodes. Configuration is compiled
once into detached immutable inputs (`waveform_ribbon_parameters.py`); camera-only edits do not recompile body inputs.
`WaveformRibbonFrameRuntime` fences activation/source identity and consumes each typed onset serial once. Its neutral
`WaveformDynamics` integrates C elastic response per ribbon, A twist and axial speed/angle; history stays fixed at 6 Hz.
Every logical publication projects the existing body immediately and supplies immutable bytes to the renderer. A
separate eased canonical passage moves appearance ranges independently of the editable Light routing row.

Event-owned sparks have at most 36 births per admitted event and a 160 ms minimum gap, with lifetime at most 8 s;
2048 slots cover all simultaneous cohorts without deleting live particles. Count and appearance are authored at
birth on the actual swept rim. GPU flight uses the published scene time; render delivery cannot re-admit a birth.
Strands use bounded history slots, eased musical threshold growth and the same current body packet. Turning Sparks
or volume Mist off retires their own resources.

Matrix cells add independent bounded gains and power curves. Material, fog, floor and accent controls resolve their
quiet/peak endpoints at their actual consumer. The matrix targets name C+A deformations (bend, torsion, stretch,
axial roll, highlight packing) rather than retaining the discarded generic lab deformation grammar.

## 3. Controls by bucket

Each bucket lists its controls and the editor that shows them. "Existing" editors are already in the codebase;
"New" editors are built in this migration and shared by later modes where they fit.

**Range sliders (operator, 1 November).** Every control that can be a range is one: the existing `Range` control
(`core/settings/visualizer_mode_settings.py`, the shared range slider in `ui/widgets/visual_controls.py`), persisted
as `[low, high]`. The meaning is strict:
- **low** is the value with almost no sound (quiet music, the start of a fade-in);
- **high** is the value at the peak (the loudest passage).
- **In between:** the passage drive (§4.2) places the value; beats swing it inside the range and never past high.
- Controls marked **(R)** below are ranges; the rest are single values.
- A range never stands for anything else (for example, a random spread). Its tooltip says "quiet → peak".

The Shape Tuner's per-target quiet/loud values are these same ranges, edited on the tuner and shown in the bucket.

### Ribbons
- **Ribbon Count:** 1-3. The cap follows the mist's per-sheet clearance rows (`ENVELOPE_RIBBONS`, 3 in the lab)
  and the packet's `MAX_RIBBONS` (8); raising it past 3 needs more envelope rows and a cost check first.
- **Per ribbon (Ribbon Cards, New):** one card per ribbon with a live thumbnail of that ribbon.
  - band it follows (Bass, Mids, Highs, All);
  - character: height share, width share, wave rate share, phase offset, light share;
  - quiet and loud colours, as two swatch pairs (centre and edge);
  - Colour Reactivity (R): how far loud colour replaces quiet (the tuner's `tint` target, per ribbon).
- **Ribbon Count changes** fade: a removed ribbon fades out over its history and a new one fades in from the head
  (fade, never vanish); the ring keeps its capacity.
- **Sheet Look:** strand count and fineness, Strand Light (R), body fill, Rim Light (R), rim glow, glints. Sliders over
  a live close-up of one sheet (Glow Preview, New).

### Shape and Reactivity (Shape Tuner, New)
- The editor/control scope is required: elastic C is primary, with separately tunable A rolling twist and whole-body
rotation. Source routing/curves and quiet→peak ranges must reach these realized targets rather than dead head controls.
- **Matrix editor:** rows are energy sources, columns are ribbon properties; each cell has a gain and a response
  curve with draggable handles.
  - **Sources:** Bass, Mids, Highs, Loudness, Onsets, and the Head Wave (the authored oscillator that draws the waves,
    the musical history's carrier).
  - **Targets:** height, swell (local compression of neighbouring folds), width, twist, lift, spread between ribbons,
    depth sway, secondary deformation, light, sparkle, colour (tint), bass arc (one taller arc per bass passage).
  - Per target: a quiet → peak range (R) and a smoothing time with an enforced minimum.
- **Character presets inside the tuner:** e.g. Even Swell (complete scene), Dominant Peak (preset range), Silk Sweep
  (alternate).
- **Live preview:** a 3D or angled-2D ribbon driven by a synthetic sweep (bass, mids, highs, loud passage) so the user
  sees the result without music. The lab's `Shaping` dataclass prototypes ranges and source routing; it is not yet
  the complete multi-source/curve model this editor needs. Finalize that model after the bake-off.

### Flow
- **Flow Speed:** the history's drift across the hall. A fixed scene constant while running: music never changes it
  (gate A), but the user authors it.
- **Wave Rate:** the head wave's frequency (long sweeps to tight ripples).
- **Wave Swell, Height Swell, Depth Sway:** the head wave's slow variation.
- **Waveform Rotation:** enabled, quiet→peak axial angular speed, reaction strength, attack and decay.
  Speed changes integrate into continuous angle; this does not move the camera or modulate history flow speed.

### Colour
- **World Gradient (Gradient Node Editor, New):** circular nodes, clickable and draggable, each click opening the
  colour picker (operator design). A quiet gradient and a loud gradient, blended by reactivity, up to six positions
  across both. Shown over a strip of the actual scene colours.
- **Gradient Share:** how much of each ribbon's own colour the gradient takes on the sheets, and on the mist.
- Ribbon colours live on the Ribbon Cards (above), so a look can be coloured by gradient (complete scene), by
  ribbon (alternate), or a mix of both.
- Colours are linear light internally; the pickers show display colours (lab lesson: (1, .4, .05) linear displays
  as gold).

### Glow
- **Sheet Glow (R):** the share of sheet light sent to the bloom (local glow without blooming the mist).
- **White-Hot Cores (R):** the brightest strands burn white; the rest keep their colour.
- **Bloom, Exposure:** scene-wide (also mirrored in Lens).

### Free Strands
- **Free Strands** toggle, then: Count (R), Length, Reach (R, how far they curl away), Halo (fuzzy splash), Glow
  (R), Droplets, Peel Time. Previewed on a sheet during a synthetic loud passage (Glow Preview).
- Strands always grow out of a rim line and fade in. Their gating follows sparkle (loud passages throw off more).

### Sparks
- **Sparks** toggle, then: Count (R), Size (a smallest/largest pair, not a quiet → peak range), Drift (R), Rise,
  Light (R), Lifetime, Whiteness.

### Mist
- **Rejected 2 November:** the entire current shaped mist, including its band, side walls and fringe, is not an
  accepted baseline. The desired replacement is full-scene night fog displaced by the actual moving waveform, with
  reactive wake and light. Failure evidence, options and open validation are in
  [Waveform Ribbon: mist failure and replacement](Waveform_Ribbon_Mist_Failure_and_Replacement.md).
- Mist Off must retire its passes and resources. The existing cheap floor distance mist (`Environment.mist` /
  `MIST_GLSL`) is separate; ground-volume bank height/light remain intentionally zero. Replacement controls and
  previews follow the selected design and native visual judgment; the old fringe controls do not define it.

### Floor
- **Reflection Intensity (R)** (operator, 1 November): how strongly the floor mirrors the scene, quiet → peak.
- Reflection columns are workable production refinement, not a bake-off blocker. A modest reduction in reflectivity
  is an admitted compromise. Expose highlight density and localized packing, including reactive density, after the
  core geometry decision; comparisons use the same reactive accent mapping across candidates and retain body-only diagnostics.
- Wetness, Streak Length, Column Fade, Mist Reflection.
- **Floor Colour/Tint and Brightness:** independently editable surface tint and brightness alongside reflection strength.
- Floor contact (sheets deform onto the floor) is a rule, not a control.

### Reaction
Waveform Ribbon's own controls, following the reactivity guide (`Docs/Guides/Visualizer_Reactivity_Authoring.md`);
the shared audio controls (sensitivity, input gain, block size) stay at their shared technical owners.
- **Passage Response:** how far quiet → loud passages move every (R) control across its range (the eased passage
  drive, §4.2).
- **Beat Pulse:** how much a hit lifts height and light, and how gently it settles. About 45 ms rise / 0.65 s settle
  is an envelope starting point, not a visible-geometry timing claim; sampling, smoothness and travel are measured
  separately under the lab plan §5.1.
- **Accent Threshold:** how far an onset must stand out from the recent ones to throw sparks and strands.
- **Idle Motion:** the head wave's own drift in silence (honest idle, no fake music).
These sit beside the Shape Tuner, which says *what* each source moves; these say *how* the music arrives.

### Camera (advanced, shared framed camera)
- Camera Position (Existing: `SceneCameraPosition`), Projection (Orthographic default, Perspective), FOV (Perspective
  only), Auto Rotate with After and Speed.

### Lens (advanced)
- Exposure, Bloom (R); Focus and Aperture only once shared defocus exists for this mode.

### Technical profile
- **Quality tier:** one Low/Medium/High setting for the large-display caps (march heights, mirrored march, floor
  reflection target and reflection-term pre-pass, strand segments). Not separate sliders.

### Rules, never controls
- **Smoothing:** every history-carried control passes two smoothing stages with an enforced minimum time (features
  at least about half a wavelength long); no sharp bends, spikes or jagged plateaus.
- **Floor contact:** sheets ease onto the floor (smooth, monotone, no creases), never through it.
- **Mist clearance:** a minimum the slider cannot go below; distant haze never pure black.
- **Fade, never vanish:** anything that appears or disappears fades (count changes included).
- **Flow speed:** never driven by music.

## 4. Reactivity

Binding guide: `Docs/Guides/Visualizer_Reactivity_Authoring.md` (signal jobs §1-2, real-music scales §2A, loud
passages §3, timescales §5, anti-patterns §11, new-mode workflow §12, passage ranges §13C). Waveform Ribbon is a
flowing history plus the selected immediate elastic projection: new detail is written at the head and travels,
while current bands, passage and typed accents deform the body already in view. Head travel must never delay
visible musical force. Light, sparks and strands also need immediate responses.

### 4.1 Waveform ribbon practice (research, 1 November)
Waveform ribbon visualisers commonly render the signal or its band energies as a flowing 3D ribbon. Bass, mids and
treble drive the geometry and colour, and hits drive bursts of light. Smoothing uses envelope followers with
separate attack and release. Sources:
- [3D Audio Visualizer, waveform as a flowing 3D ribbon (teamzlab)](https://tool.teamzlab.com/3d/audio-visualizer/)
- [How to Make a 3D Music Visualizer (Violet Recording)](https://violetrecording.com/how-to-make-a-3d-music-visualizer/)
- [Envelope detector (musicdsp)](https://www.musicdsp.org/en/latest/Analysis/97-envelope-detector.html),
  [Faust analyzers](https://faustlibraries.grame.fr/libs/analyzers)

**Selected response vocabulary; native strength and controls remain unaccepted:**
- **C elastic body with A rolling twist.** Keep the smooth flowing carrier; apply band-specific bend/torsion/depth
  and accented elastic impulses to visible geometry, plus accumulated twist and independent reactive axial roll.
  Raw bands plotted directly as head height make jagged plateaus (lab plan §4A).
- **One ribbon per band** (alternate board: bass, mid, high), each through the tuner; the complete scene's sheets
  share all bands with different characters.
- **Hits light things up immediately:** whole-ribbon light, sparks, free strands. Light needs no history, so it can
  be fast.
- **The passage sweeps the quiet → loud ranges**, slowly, never per beat.

### 4.2 Reaction vocabulary (guide §12)

| Musical moment | Waveform Ribbon response | Signal (existing authority) |
|---|---|---|
| Idle / silence | Subtle body/flow drift; no new musical sparks, strands or pulses; living accents retire smoothly | presence from `musical_weight`; an explicit idle lane, never fake energy |
| Sustained quiet passage | Ranges near their quiet handles: low waves, narrow sheets, quiet colours | one fixed-scale eased passage through authored attack/release; do not import another mode's constants |
| Sustained loud passage | Ranges near their loud handles: tall sweeps, wide sheets, loud colours, more sparkle; beat contrast kept inside the chorus | same passage drive; beats multiply inside it, never add a floor (§13C) |
| Kick / bass hit | Immediate C elastic bending/width with distinct kick impulse; A twist and history colour/light continue to flow | bounded passage-gated reward and consume-once typed onset; visible timing/attack must be judged in the recorded bake-off |
| Snare / generic onset | Light flash along the ribbons, sparks; free strands peel off on accents | typed event bus, consume once; accents = onsets above the recent mean (§13C) |
| Vocal rise / swell | Twist and depth sway grow; colour moves toward loud | mid/vocal lane, medium continuous envelope |
| Highs | Fine shimmer: glints, sparkle density | fixed-reference raw high band and local crest/light, ramped by the one passage |
| Release to calm | Ranges ease back over the passage stages; flow speed never changes | passage drive |

**History rules specific to this mode:**
- **Written at the head, never rewritten.** Normalized musical detail, tint and light are sampled when a knot is
  admitted. Current body geometry is a model-specific logical projection over that immutable history, shared by
  ribbons/accents/reflection/mist. Do not constrain the selected hybrid to head-only shape changes or a common global pulse.
  A history-carried control changing over d seconds draws a feature flow speed × d long; band-limit it appropriately
  (lab plan §4A). Projection remains pure; rendering never integrates elastic state or advances history.
- **Immediate channels** (whole-ribbon light, sparks, strands, glow) may follow the beat directly; they need no
  history.
- **Flow speed never follows the music** (gate A). DevCurve's lesson: a ±10% beat nudge on travel read as
  fast/slow/fast/slow.

### 4.3 Calibration boundaries
- **Visual admission and grammar selection: the lab.** The operator admits the current visual range with appearance
  caveats; synthetic low/high recipes alone do not establish a multi-band response. Follow the lab plan's live
  sequence, then §5.1 for the four-way comparison and
  causal timing decision. C-primary/A-twist is selected; native response strength and editor usability remain open.
- **WR-07 recorded-feature response calibration: the lab.** Replay existing recorded audio/analysis through its
  canonical authority into explicit logical time with valid pre-roll. Calibrate the selected grammar's ranges,
  smoothness and attack/settle against quiet, ordinary, hot and isolated-hit windows, including beat contrast over
  a loud bed. Trace actual signal scales and visible realization; a single quiet/loud smoke is insufficient.
- **WR-08 production calibration and reachability:** verify the same response through actual BeatEngine lanes,
  shared sensitivity, technical profile, Settings and presets. Port the accepted lab response rather than replace
  it with a second independently tuned mapping. Follow guide §12:
  - neutral to maximum synthetic cases with monotonic ordering;
  - silence, quiet song, ordinary, hot chorus and isolated hits over a loud bed;
  - the share of frames at each driver's ceiling (pinned drivers, §13B);
  - preset-to-source reachability;
  - then `tools/visualizer_live_check.py` with recorded music and `--load game60`, and installed eyes-on review.

### 4.4 Reactivity testing notes
Taken from the guide (§3, §5, §7, §8, §12, §13A-C) and the lab plan's WR-07 checks, specific to a flowing history:
- **Fixtures, not presets:** test-owned ranges and synthetic sources (neutral, weak, medium, strong, maximum) with
  monotonic ordering of each target. Never assert preset values.
- **Recorded music:** quiet song, ordinary, hot chorus, isolated kick/snare/vocal over a loud bed, from
  `logs/visualizer_recordings/*.jsonl` through the production lanes, with pre-roll so the history is warm. Measure:
  - each driver's p05/p50/p95 as a fraction of its range, and the share of frames at the top 15% (pinned drivers);
  - beat contrast inside a loud passage, not only quiet vs loud means;
  - attack and settle times of the height pulse and the light flash.
- **History-specific checks:**
  - a bass hit written at the head travels across the hall unchanged (the knot never rewrites);
  - a control that changes faster than the band-limit allows shows no lump or kink in the drawn ribbon (crops);
  - flow speed is identical across quiet, loud and silent windows.
- **Silence and state:**
  - silence → music, music → silence, pause/resume (warm and cold), short dropouts;
  - no sparks, strands or pulses in silence;
  - the idle drift is honest (no fake energy) and nothing vanishes.
- **Events:** one event authors one pulse (consume once; the latest-event snapshot never re-fires); an old
  activation's events never reach a new one.
- **Hot start:** activation into an already loud passage seeds the passage drive (no full-width first frame or
  overshoot), and a preset hot-swap does not reseed history into a jump.
- **Render rate:** identical logical history at 30, 60 and 144 fps and with irregular frame delivery. Frames read the
  latest state; they never append history or integrate.
- **Reachability:** preset → Settings → technical profile → audio lanes → mode capture, live, not only from
  pre-built features (guide §10).
- **Floor independence:** reactions hold with Dynamic Floor off (guide §13A).
- **Acceptance:** `tools/visualizer_live_check.py` with recorded music and `--load game60` (invisible saver), plus
  installed eyes-on review; automated correlation alone never closes it.

## 5. Port order

The retained scene is `rendering/quick/scene3d/waveform.py:WaveformScene`; the lab supplies its diagnostic target,
fixtures and explicit camera, while production supplies the existing Quick frame/context. Plain scene inputs live in
`core/waveform_ribbon_scene.py`, primitive appearance values in `core/ribbon_style.py`, programs in
`rendering/gl_programs/waveform_ribbon.py`. No production owner imports the lab. Extraction parity evidence:
`.artifacts/evidence/waveform_ribbon/wr_scene_promotion_parity_v2_20261102/` (three native captures exactly match the
post-fringe baseline). Logical hybrid, incremental/GPU deformation, settings and mode registration remain work below.
Scene retirement validates its owning context before deletion, attempts independent owners after a failure and keeps
failed handles for retry. Volume Mist Off retires its volumes/marches/programs and shape/envelope textures; analytic
floor mist remains a separate scene input. Full production camera/quality/effect-toggle admission remains below.

1. Descriptor, logical runtime, ring/packet ownership, empty scene with the framed camera (Orthographic default) and
   dormancy/Off paths.
2. Ribbons with material and glow (complete-scene preset), then floor with reflection and contact.
3. Mist (volume, march, shape bake, edge line, floor mist) with its Off path and quality tier.
4. Sparks and free strands.
5. Settings buckets and the existing editors; then the New editors (Gradient Node Editor, Ribbon Cards, Shape Tuner,
   Glow Preview), each previewing the real renderer.
6. Starting presets authored from the lab recipes; preset repair fill and completeness guard.
7. Reactivity: verify WR-07 response parity and source reachability through production Settings/presets/audio,
   then the live check with recorded music and game load. Reopen WR-07 if the port exposes a grammar defect.
8. WR-09 acceptance: mock | lab | production sheets, all camera views, cost at 1080p/1440p/4K, operator review.

## 6. Camera sweep findings (1 November)

Twelve views per look, both projections (`wr08_camera_sweep/`):
- **Fixed: near clip.** Zoomed-out and low Orthographic views clipped the floor near the camera into a black band.
  The near plane now sits behind the eye; the mock pose is unchanged.
- **Fixed: clear corridor along the ribbons.** The clear room in front of the sheets ran unbounded along x, so end-on
  and turned Perspective views saw the far floor, the horizon and black sky. The clear band and the sheets' 3D
  clearance now close beyond |x| 8-13, and a billowed side wall of dark haze stands there at every depth, so the
  ribbons run into the off-screen edge mist (`*_walls.png`). Mock pose: only a 4-pixel sliver at the right edge of
  the quiet state moved.
- **Accepted (operator rules):** the side wall's face is near-black distant haze. End-on views keep bright coloured
  reflection columns: real light stacked along the line of sight, no longer clipped white.
- **Rejected:** a soft luminance roll-off on the floor reflection barely changed end-on views and moved the mock pose
  (mean 2.5/255 over 77k pixels). A clear room around the eye did nothing: the dark shape was the wall's face, not a
  wall in front of the lens.

## 7. Gaps to design before or during the port

- **Aspect and the side walls:** the walls sit at fixed world |x| 8-13, outside today's widest framing. Widening
  reveals more fixed world (camera contract), so at ultra-wide aspects or zoomed-out Scene Scale the walls must
  stay outside the view. Derive their position from the widest admitted framing, never per frame from the camera.
- **History capacity at the widest aspect:** knots = (visible span + both margins) / flow speed × knot rate must fit
  the 256-knot cap at the widest admitted aspect and lowest flow speed; Flow Speed's range follows from it.
- **Ribbon count above 3:** needs more envelope rows (mist clearance per sheet) and a cost check.
- **Warm-up:** many programs (ribbon passes, strays, sparks, floor and its pre-pass, mist volume, march, bake,
  composite). Prewarm one per already-rendered frame, next-likely first; never in a burst (warm-up rule).
- **Off paths:** Mist, Free Strands, Sparks, reflections and the mirrored passes each cost nothing when off (no
  programs, targets or per-frame work).
- **Cost by quality tier:** per-tier budgets at 1080p/1440p/4K for the whole frame; the mirrored strays and mirrored
  march are the first cuts.
- **Multiple displays:** one scene per display, each with its own volume and targets; check that memory and cost
  scale acceptably with two 4K displays.
- **Preset repair:** every control above is authored into every preset (repair fill and completeness guard); ranges
  are filled as `[low, high]`, never as a single value.
- **Editors share the real renderer:** the Shape Tuner, Gradient Node Editor, Ribbon Cards and Glow Preview preview
  through the production renderer, not a second drawing path.
- **Motion check:** explicit-time slow motion for mist anchoring, the screen-space edge line's fibres, floor streak
  stability and strands, in both projections, before WR-09.
