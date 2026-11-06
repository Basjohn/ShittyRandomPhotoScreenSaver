# Waveform Ribbon: migration plan (WR-08 controls, reactivity and production port)

> **Orthographic removed 5 Nov 2026 (operator):** Perspective is the only camera projection in the whole project. Orthographic, its Projection control, raster-slab fit and parallel-ray paths are deleted; any Orthographic passage below is historical and superseded.

Planning owner for **WR-08**, subordinate to [`Current_Plan.md`](../../Current_Plan.md) §7.1 and the lab plan's
WR-08 gates ([`Waveform_Ribbon_Lab_Plan.md`](Waveform_Ribbon_Lab_Plan.md)). The lab owns the look; this document
owns the full production control design, production calibration and the order of the port. A registered production
candidate now connects canonical Settings, the original two authored presets, candidate visual editors, the sole logical runtime and the
retained scene. A finite user-triggered quiet/middle/peak preview renders that same production body/scene without
a second clock or audio engine. Complete endpoint/framing audits and loaded live admission remain open in
`Current_Plan.md`; existence of the candidate is not acceptance. Core geometry/motion evidence and timing belong to
the lab plan §5.1. The 2 November selection of **C elastic dynamics as primary** is superseded (5 November) by the
travelling energy pulse described in [Current reaction model](#current-reaction-model-5-november); A's accumulated
twisting and the axial roll remain. Passages below that still describe C elastic bending as the primary response are
historical design context. Values quoted are the lab recipes' current values, recorded for orientation: presets are
operator-authored and never test oracles.

**Operator direction (1 November):**
- The migration is a **full Visualizer migration**: full controls, Settings and the preset/control systems, designed
  as a whole. Nothing is half-built ahead of it in the lab.
- **Everything a 3D Framed mode like Extruded Bubble has** (scaffolding, camera, presets, technical profile), with
  the projection **defaulting to restrained long-lens Perspective**. Its reactivity and most of its controls are its own: a waveform
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
colour tint and brightness become settings rather than blocking visual polish. Retain the original primary/alternate presets and add Preset 3 from the new November 2 references; preserve all shared framed-3D features and technical/preset systems.

The single live operator-rejection checklist is `Current_Plan.md` section 7.1. It covers missing punch/shape response,
weak particles, strand flicker, highlights/colour, idle/first-play blackout, floor/viewport, grounded near-flat navigation,
rejected mist and deferred rejected UX. Working inputs or range tests do not constitute visual acceptance.

## Current reaction model (5 November)

Operator direction: reactions feel like water waves, gentle but strong, always **with** the waveform's own shape.
This supersedes the R1/R2 elastic body (standing bends and the retired axial stretch read as sideways bursts and
twitch). Owner: `core/waveform_ribbon_dynamics.py` (`WaveformDynamics`, `PulseControls`, the named module
constants); all state integrates on the sole logical clock and the projection only samples it. Decision record:
`Docs/Audits/Waveform_Studio_and_Reactivity_Audit_2026-11-05.md` §5 item 7. Visual/musical acceptance stays in
`Current_Plan.md` §7.1.

- **Travelling energy pulse.** Typed hits and body-energy rises inject energy at an origin set by Pulse Direction
  (Head To Tail, Tail To Head, Centre Out); edge origins sit just beyond the view, so a swell slides in already
  formed. Travelling Pulse's edge swells use the view the card's camera really shows (`core/waveform_ribbon_view.py`
  `card_span`, passed by the capture and the Studio as `view_span`): born `VIEW_MARGIN` envelope sigmas beyond its edge
  (never farther than `PULSE_ORIGIN`), ageing only once seen. Centre Out and the other modes ignore it. Energy travels at Pulse Speed, spreads gently and fades over Pulse Fade on one bounded 1D field per travel
  direction. There is no steady baseline injection. The Bend range is presented as **Pulse Strength**.
- **Flow rule.** Geometry multiplies the waveform's own displacement about its axis by a broad envelope (sign never
  flips) whose slope and curvature are bounded relative to the carrier wavenumber, so a swell may deepen existing
  curvature but never reverse it, add an inflection or dent a curve inward. The bounding share relaxes upward
  smoothly and is computed in closed form each tick. Horizontally, an **along-curve surge** slides knots along their
  own curve (exact resampling of the unsurged body) with bounded local compression, a rate limit and a fixed end
  taper; it moves the cloth's material with the swell without changing the curve.
- **Appearance band.** A narrower Pulse Width band carries light, Pulse Colour Shift and Pulse Saturation (never
  inventing a hue on neutral colours). It is led by fresh energy, so each beat's band is brightest while it travels;
  geometry follows the fresh field too, so overlapping swells do not inflate the whole view.
- **Pulse Rim.** The rims (crisp line and rim glow), already brighter than the sheet by design, brighten further
  where the pulse is. The logical owner publishes its appearance field (`pulse_at` on `PULSE_GRID`, history-axis x)
  in every snapshot; the scene uploads it once per frame (one small R32F texture, only while Pulse Rim > 0) and the
  light pass alone reads it at the fragment's history x (direct and reflected), so Travel Direction and every
  Reaction Mode place it exactly on the published field. The response is the square of the field over a reference
  level (a passing swell's in-view level on recorded music), softly capped, so the plateau of older swells keeps its
  rims near their own light while a passing swell's rims light up with the field's own smooth falloff. 0 is
  pixel-identical to the light pass without it (`tests/test_waveform_pulse_rim.py`). The reference is set where a
  swell carries half the injection (each Centre Out swell); an edge swell seen at full strength publishes
  `RIM_EDGE_SHARE` of its level, so its rims respond as Centre Out's do. The floor lift reads the card's visible span
  plus `TROUGH_LOOKAHEAD` sigmas of the mode's envelope, within ±`TROUGH_VIEW`.
- **Coupled accents.** Pulse Particles buys births once per injection, released over the swell's first journey and
  only into the headroom left after the authored Spark Count; Pulse Strands gives a restrained lean/chance/glow
  near the swell.
- **Reaction Modes** (`REACTION_MODES`, Settings "Reaction Mode"): **Travelling Pulse** (default); **Frozen Past**
  (a per-cell passage peak held on the cloth and advected with it, so shaped parts keep their size/colour until the
  next swell, decaying slowly in silence and never vanishing); **Whole Swell** (one global level, ignores direction,
  width and speed); **Group Wave** (each swell arrives as a set spanning several carrier wavelengths, leaning toward
  its leading edge with a stronger surge; like Travelling Pulse, its geometry and surge follow the fresh field: built
  from the long-fade field its peak-keeping set envelope pinned the swell at the soft bound over the view, 5 Nov
  Preset 7). Every mode obeys the flow rule and the no-twitch rules.
- **Adaptive response gain.** Geometry drives are divided by a memory of their own recent peak (fast reach, slow
  relaxation, a floor), so each song uses the whole authored Quiet→Peak ramp while a quiet passage after a loud one
  stays quiet; the remembered peak lands below Peak, keeping headroom for accents. Light, colour and sparkle keep the
  fixed calibrated anchors. The whole body's size (height, lift, width) follows the passage, not each beat; beats
  belong to the pulse. Measured in continuous play the gain is not what muted mid-song kicks (removing it lowers kick
  response 40-50% at every point of a song); the frame runtime's per-kind running-mean contrast was (below).
- **Kick force in continuous play** (5 Nov). A typed onset's force follows its own unclipped magnitude (already
  relative to the bus's adaptive flux threshold), the fixed loudness scale and the passage ramp, never this kind's
  running mean: that second adaptation zeroed 2/3 of kicks and faded a steady beat to <1% of its first kick, so songs
  looked reactive at the start and muted in the middle. Accent admission (sparks, strands) keeps the contrast.
- **Breathing** (5 Nov, Reaction bucket). Softness = Breathing x how far the published passage sits below
  `BREATHING_LOUD`; a soft passage releases its geometry drives faster (up to `BREATHING_REACH` of Decay, on both
  stages) and widens each drive's swings about its own phrase-scale mean (up to `1 + BREATHING_CONTRAST`), so it
  swells and lets go within its phrases instead of holding. Loud passages keep Decay, targets and reach. Breathing
  also holds the adaptive gain's memory through a quieter PASSAGE (`RESPONSE_MEMORY x (1 + Breathing x (RESPONSE_HOLD
  - 1))`, engaged only while the slow sustained level sits below `HOLD_BELOW` of the loud level the peaks were set at,
  never between beats), so a quieter passage after a loud one is not re-normalised to loud reach.
  Breathing 0 is bit-exact with the 5 Nov baseline (Preset 4).
- **Anchored history ends** (5 Nov, side-angle tail stagger). The packet header carries the history ring's admission
  phase (`extra.w`); the drawn history ends `ANCHOR_INSET` knots inside each end at anchors fixed in the scene, and the
  C2 continuation starts from the spline's own jet there (`core/ribbon_continuation.py` mirror, ribbon/atmosphere
  shaders). Continuing from the end knot stepped the far end at every 6 Hz admission, visible at the extreme turn.
- **No twitch.** Geometry drives pass through two cascaded followers with a minimum attack (velocity-continuous);
  hit kicks to the sway/torsion springs are spread over a short window; the rim's hit glow rises and settles like the
  pulse instead of flashing with the raw hit decay; swells land with a short rise, never a one-tick pop.
- **Whole-ribbon floor lift.** When a ribbon's lower edge (its sheet hang, width × |cos twist|) would come within the
  floor clearance inside the view, that ribbon lifts as a whole, bounded, through two cascaded followers (quick up,
  slow down). Shape is never changed; per-knot trough limits were rejected as boxy.
- **Dynamic Zoom** (opt-in, off by default): a sustained-level follower widens or narrows only the lens extents,
  frozen while the user operates the camera.

Gates: `tests/test_waveform_energy_pulse.py`, `tests/test_waveform_reaction_modes.py`,
`tests/test_waveform_pulse_coupling.py`, `tests/test_waveform_no_twitch.py`, `tests/test_waveform_trough_clearance.py`,
`tests/test_waveform_dynamic_zoom.py`, `tests/test_waveform_ribbon_dynamics.py`, `tests/test_waveform_continuous_play.py`,
`tests/test_waveform_breathing.py`, `tests/test_waveform_reaction_continuity.py` (quieter passage after a loud one,
Group Wave sets in sustained/soft passages) and `tests/test_waveform_tail_continuity.py` (test-owned controls; structure, never
authored values). Probes: `tools/visualizer_replay/waveform_ribbon_breathing_probe.py` (continuous play: songs back to
back without a reset; kick response by time in song and passage, breathing contrast, reach) and
`tools/visualizer_replay/waveform_ribbon_tail_probe.py`.

## Latest target authority (2 November)

The operator's maximum is **four ribbons**, including complete runtime/clearance/accent support. Add **Preset 3**
using `references/Preset3Goal1.png` and `references/Preset3ReactivityGoalExample.png`; section 1.1 of the Lab Plan
owns native dimensions and hashes. Its teal/orange lattice, flowing twists, strands/particles, continuous wet ground
and clearly separated quiet/high geometric range are visual targets, not permission to optimize one still. The second
board's four-ribbon low/high comparison and explicit user maximum override the first image's count label.

`references/Mist Goal.png` is the new atmosphere/floor target: dark full-scene night fog, gentle near-ground diffusion,
local waveform light, wet foreground extending into softly obscured distance, no horizon seam, raised banks or fringe.
It replaces ALL older mist/fog mechanisms, including the separate legacy floor/distance mist. Migrate to one coherent
world atmosphere; do not retain the rejected layers underneath or as fallbacks. The earlier ground-bank-zero instruction
must not be read as permission to re-enable those banks; the new atmosphere alone supplies the target's soft ground haze.

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
are held world-space records with bounded lifetime/capacity. Strand look/flicker is now operator-approved; persistent travel and repeat pulses remain under validation.
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
- Settings: the canonical spec (`core/settings/visualizer_mode_settings.py`) owns every control; the Custom body is
  Studio-owned (`ui/tabs/media/waveform_ribbon_builder.py` → `build_studio_owned_mode_ui`: preset row, one sentence,
  Open Waveform Studio). The former builder buckets are retired; `tests/test_waveform_studio_parity.py` proves the
  Studio covers everything they built. Editing UX lives in the Studio (`Docs/Reference/Visualizer_Studio.md`).
- Shared framed camera (`core/settings/framed_camera.py`) with a Waveform spec. **Long-lens Perspective is the only
  projection** (Orthographic removed 5 Nov 2026). The candidate uses an 80-unit home radius, 64-104 physical dolly,
  stable 4.5-unit eye height and a 3-degree lens. Turn, tilt, Scene Scale and pan come from in-scene
  navigation as in EB (hidden sliders), with Camera Position as the scene editor.
- Every new control is authored into every preset (preset repair fill plus the completeness guard). Presets stay
  freely operator-authored.

## 2. Starting presets

The lab's named recipes become the first presets, each one scene across quiet and loud:

| Preset | Lab recipe | Look |
|---|---|---|
| 1 — Complete Scene | `complete` | Preserve cyan → blue-violet → magenta world grade and primary sheet identity; replace the rejected fog with the new unified atmosphere |
| 2 — Silk Bands | `alternate` | Preserve per-band ribbon colours (quiet blue/teal/lavender, loud magenta/orange/blue-violet), luminous silk and approved free strands |
| 3 — new operator target | new November 2 boards | Four ribbons; teal/orange lattice and twisting sweeps; high crests roughly twice quiet height, strongly richer geometric/particle response, continuous textured wet floor |

Names are suggestions for the operator to rename.

The shared preset store uses zero-based indices: displayed Preset 1/2/3 resolve stored 0/1/2. The native capture route is
`tools/waveform_ribbon_capture.py --clip <recording.jsonl> --preset 1 --start 20 --duration 4 --fps 24
--output <new-directory> [--ffmpeg <explicit-executable>]`. It reanalyses original recorded PCM through the production
worker and captures the real logical/frame/retained-render path; audio is not shifted to conceal response latency.

### Production ownership

`core/waveform_ribbon_authoring.py` strictly admits matrix, ribbon cards and gradient nodes. Configuration is compiled
once into detached immutable inputs (`waveform_ribbon_parameters.py`); camera-only edits do not recompile body inputs.
`WaveformRibbonFrameRuntime` fences activation/source identity and consumes each typed onset serial once. Its neutral
`WaveformDynamics` integrates the travelling pulse field (see Current reaction model), depth-sway/torsion springs per
ribbon, A twist and axial speed/angle; history stays fixed at 6 Hz.
The travelling carrier's audio amplitude/twist uses the existing two-stage `Flow.shape_tau` contract; raw six-Hz
audio writes produced the rejected small dents. Whole-body elastic impulses and light/colour/accents retain their
immediate inputs. Every logical publication projects the existing body and supplies immutable bytes to the renderer. A
separate eased canonical passage moves appearance ranges independently of the editable Light routing row.

Event-owned sparks have at most 64 births per admitted event and a 160 ms minimum gap, with lifetime at most 8 s;
4096 slots cover the maximum 3200 simultaneous particles without deleting live particles. Count and appearance are authored at
birth on the actual swept rim. GPU flight uses the published scene time; render delivery cannot re-admit a birth.
Strands use bounded history slots, eased musical threshold growth and the same current body packet. Turning Sparks
or volume Mist off retires their own resources.

Matrix cells add independent bounded gains and power curves. Material, fog, floor and accent controls resolve their
quiet/peak endpoints at their actual consumer. The matrix targets name C+A deformations (bend, torsion, stretch,
axial roll, highlight packing) rather than retaining the discarded generic lab deformation grammar.

## 3. Controls by bucket

Each bucket lists its controls and the editor that shows them. "Existing" editors are already in the codebase;
"New" editors are built in this migration and shared by later modes where they fit. This is the 1 November control
design: the canonical control list is the Waveform spec in `core/settings/visualizer_mode_settings.py` (the pulse
controls sit in its Reaction bucket, elastic/attack/decay timing in the advanced Response bucket), and editing
happens in the Studio, whose instrument choice follows the design pack's control policy (audit §5 item 4) with
serialized `[low, high]` data unchanged.

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
- **Ribbon Count:** 1-4 (operator maximum). Four retained cards share the logical/body/clearance/accent paths;
  prove all four reach geometry, light, collisions, accents and reflection within the loaded cost budget. The generic
  ribbon packet allows eight; that is not this mode's authoring maximum.
- Former three-card state migrates forward by appending the canonical fourth card, preserving all original values
  and the visible count. Four-card output is canonical; no parallel legacy runtime. Presets 1/2 retain three visible
  identities; Preset 3 authors four. The extra retained path has an open incremental cost gate.
- The body needs a spatial carrier before axial roll: turning a planar Y wave into depth collapsed its visible height.
  Current candidate adds a quadrature depth carrier and stores local recorded amplitude/twist variation at admission,
  while C springs still punch the existing body immediately. Spring/body bounds leave more peak headroom; roll remains
  physical, with no angle-dependent or viewport-dependent audio gain. Recheck actual preset quiet/peak envelopes at all angles.
- Vertical Lift positions the world-space skewer axis after axial rotation, so rotation cannot move that axis around
  the floor. The candidate raises the resting axis to avoid a continuous flattened contact strip; troughs still deform
  smoothly onto the floor. The night medium uses broader height diffusion and thinner camera-side foreground air
  within its SAME world-density function, keeping the long viewing path readable while distant fog thickens gently.
- The operator delegates the visual route: use restrained long-lens Perspective as the primary candidate, with a farther
  physical eye and narrow field of view calibrated together. The shared edge-resize aperture contract is unchanged;
  the camera cannot excuse colour, material, fog or reaction defects. Defaults and native camera receipts own the concrete calibration.
  Production uses the scene's canonical fixed history head, not a second narrower head that exposes regular endpoint
  continuation inside the baseline view. Full-scene reference likeness and small/extreme aperture behavior remain open.
- Grounded camera calibration must show floor material and depth: use a stable above-floor eye, allow a near-flat
  endpoint, and tune the default downward view against the new reference. A visually rejected low, near-level default
  is not accepted merely because floor intersections and eye admission are mathematically valid.
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
- The editor/control scope is required: the travelling pulse is primary (superseding elastic C; see Current reaction
model), with separately tunable A rolling twist and whole-body rotation. Source routing/curves and quiet→peak ranges must reach these realized targets rather than dead head controls.
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
- **Travel Direction** (Right To Left default, Left To Right): `Flow.direction` is the history's one sign. All history
  computation stays on the history axis (head at +head_x, travelling toward -axis), so packets are identical either
  way; `WaveformScene` alone maps the axis into the world (x mirror on the history-bound view, the bursts' clip matrix,
  the frustum continuation spans and the mist volume lookup), the reduced fields (mist cloth, floor give) are built in
  world x (`uFieldSide`), and the colour grade is mirrored into history x so it stays put in the world. The Studio's
  projection applies the same sign. The logical owner publishes the direction: a change fades ribbons, sparks and
  strands out (`DIRECTION_FADE`, smoothstep), swaps while hidden, and fades back.
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
  (R), Droplets, Peel Time, total Lifetime (R) and Tip Fade Share (R). Latest target: rare strands, 3-5 seconds total,
  with most of their life spent gently fading from tip toward root; the earlier 30-second fade proposal is superseded.
- Strands grow from a rim, with root identity and all base geometry/light/finish held at birth. Latest operator policy
  supersedes endless life: configurable total EoL with a VERY gentle tip-first fade inside that lifetime. Birth admission follows
  real accents and the authored world span, selecting at most eight roots per accent with no camera-following population.
  Admission/renewal requires enough retained root history to finish the full lifetime. Expired cohorts submit no strand
  payload while retaining held metadata for smooth reactivation. A repeat at an occupied root preserves
  its birth/look and adds an approximately 20% temporary length extension plus glow/movement, then returns smoothly.
  Reactivation renews EoL and restores a partly faded strand gradually. Retriggers retain current fade/pulse envelope
  values instead of snapping them to zero. Validate gentle visible retirement and reactivation
  in direct/reflected admitted views, including wide views. Operator approved the look; persistence/pulse and
  wider scene acceptance remain explicit in the live checklist.

### Sparks
- **Sparks** toggle, then: Count (R), Size (a smallest/largest pair, not a quiet → peak range), Drift (R), Rise,
  Light (R), Lifetime, Whiteness.

### Mist
- **Rejected 2 November:** the entire current shaped mist, including its band, side walls and fringe, is not an
  accepted baseline. The desired replacement is full-scene night fog displaced by the actual moving waveform, with
  reactive wake and light. Failure evidence, options and open validation are in
  [Waveform Ribbon: mist failure and replacement](Waveform_Ribbon_Mist_Failure_and_Replacement.md).
- Latest authority is `references/Mist Goal.png`; all previous fog/mist layers are superseded, including the old
  separate analytic floor/distance mist. Replacement controls and previews follow one unified atmosphere. Mist Off
  retires that atmosphere's passes/resources; old fringe/side-wall controls must be migrated away, not retained as debris.
- The replacement candidate uses one world medium for floor, sky, sheets, particles, strands and mirror: smooth
  height diffusion, gentle world-distance thickening behind the waveform, low-frequency drift, actual rolled/cambered
  floor-colliding cross-section clearance and local source light. The old envelope band, side walls, bake, detail march,
  fringe/crackle and independent analytic floor haze are removed. New controls: Density, Ground Diffusion,
  Displacement, Displacement Softness, Local Light, Soft Variation and Atmosphere Drift, with quiet/peak ranges.
- Fog slices use an ordered asinh depth mapping about the camera pivot (positive Perspective depth; the signed
  Orthographic slab was removed 5 Nov 2026).
  Floor samples integrated light/transmittance once to its hit; sky samples to far depth; additive actors sample
  transmittance; reflected rays use the same above-floor world medium. Off leaves no independent floor haze.
- The long lens puts the subject far from the eye: ordinary logarithmic froxels were several world units thick
  at the waveform and could miss its clearance/light. A focus-centred asinh mapping concentrates the SAME fixed
  grid around the actual body's camera depth, while integrating the complete near/far interval. Injection, surface
  sampling and detail helpers share one inverse mapping; legacy positive-depth consumers retain their old mapping.
- `waveform_atmosphere.py` and `waveform_field.py` own the packet-derived GPU field. Beyond its fixed table, evaluate
  the same retained interior spline or endpoint continuation as the drawn cloth. No camera-dependent field resampling,
  CPU readback, side closure or hidden alternate fog. Same-x cross-section distance remains an approximation around
  steep longitudinal bends; a retained moving-body wake is not yet implemented. Current status/gates remain in Current_Plan.

### Floor
- **Reflection Intensity (R)** (operator, 1 November): how strongly the floor mirrors the scene, quiet → peak.
- Reflection columns are workable production refinement, not a bake-off blocker. A modest reduction in reflectivity
  is an admitted compromise. Expose highlight density and localized packing, including reactive density, after the
  core geometry decision; comparisons use the same reactive accent mapping across candidates and retain body-only diagnostics.
- Wetness, Streak Length and Column Fade. The unified atmosphere's reflected light follows the same floor reflectivity.
- **Floor Colour/Tint and Brightness:** independently editable surface tint and brightness alongside reflection strength.
- Floor contact (sheets deform onto the floor) is a rule, not a control.
- **Floor Give** (opt-in, 0 = the rigid floor, drawn exactly as before): where a lower edge comes down onto the floor
  the wet floor yields in a soft dent and the ribbon dips in instead of being flattened along the plane. Owner:
  `rendering/quick/scene3d/floor_give.py` reduces the published packet once per frame on GPU (two small compute
  passes, `rendering/gl_programs/waveform_floor_give.py`) to a bounded field: per world x and ribbon the dent depth (the
  Give share of the edge's softplus reach below floor + gap), its z centre and z radius (reach-weighted over the exact
  cambered section, so the dent follows a turning sheet continuously), blurred along x. `FLOOR_GIVE_GLSL` sums the
  Gaussian dents and soft-caps them (`Floor.give_depth`): no crease, no hole. The floor's ray marches then bisects to
  the first crossing (same coverage, the dented point's depth), its normal drives Fresnel, shading and a reflection
  bent through the dent; ribbons, strands and sparks ease their contact onto the same surface. Stateless and a smooth
  function of the cloth, so it moves as smoothly as the ribbons. Perspective only. Not consumed by the mist's cloth
  field (its plane-contact approximation is well inside its displacement softness).
- Floor material must stay readable away from core reflections. The candidate uses the existing concrete albedo and
  roughness maps with restrained neutral ambient light, without the rejected artificial dark-blue patch modulation;
  reflection OFF and atmosphere OFF must
  still reveal the foreground material. Full foreground/far coverage alone does not establish this visual requirement.

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
- Camera Position (Existing: `SceneCameraPosition`), FOV, Auto Rotate with After and Speed. (The Projection
  control was removed with Orthographic on 5 Nov 2026; Perspective is the only projection.)

#### Orthographic raster depth and continuous world coverage (historical; removed 5 Nov 2026)

> Superseded: Orthographic and `orthographic_raster_projection`/`orthographic_depth_interval` were deleted on
> 5 Nov 2026 (operator). The infinite-floor Perspective ray intersection below still applies; the Orthographic slab
> analysis is kept only as history.

The physical eye, grounded admission, focus, editor inverse and persistence remain owned by
`core/settings/framed_camera.py` and the Waveform policy in `core/settings/waveform_ribbon_camera.py`.
The infinite opaque ground uses `FLOOR_WORLD_GLSL`: intersect the same camera's pixel line with world y=0,
then write its projected depth. Orthographic ground intersections may precede or exceed the fitted actor slab;
ground-only depth clamping does not itself expand actor admission. Perspective requires a forward hit.
The world material/reflection coordinates do not move with coverage. `tests/test_waveform_infinite_floor.py`
protects complete coverage, actual world XZ, occlusion and the unchanged positive Perspective actor interval.

**Depth-slab failure mechanism:** a continuous axial field and a fixed positive Orthographic actor slab cannot
both cover every admitted yaw/aspect. At nonzero yaw, view depth varies with world x. An axial point can therefore
remain inside the card's XY aperture while crossing the near plane; the sheets' differing z/twist makes those cuts
stagger. A wider aperture exposes cuts that lie off-screen in the canonical view. More history or smoother endpoint
continuation cannot repair this clip boundary.

A bounded CPU transform diagnosis used the contiguous idle production packet, radius 12, yaw +35 degrees,
near-level 0.5-degree downward pitch and aspect 4. The eye was `(6.882917, 2.6, 9.829825)` and Orthographic
half-extents `(19.882251, 4.970563)`. Every history head was world x=16, but the continued centrelines produced:

| Diagnostic sheet | Last world x inside aperture XY | Last world x admitted by positive near clip |
| --- | ---: | ---: |
| 0 | 24.0625 | 20.8250 |
| 1 | 24.3875 | 20.1900 |
| 2 | 24.6325 | 19.6825 |

This is a frozen diagnostic example, not a curated-preset golden or a three-ribbon product limit. The missing
2-5 world units are camera clipping, after the finite history's endpoint. Native acceptance remains open.

**Camera-owned raster contract:** fit Waveform's Orthographic **raster depth slab** to the
bounded world support admitted through its XY aperture. Preserve the true eye, world-to-view axes, projection XY,
fixed geometry/phase/IDs and Perspective arithmetic. Derive signed near/far from that support instead of adding an
arbitrary global negative near constant. Main/reflection, body/OIT/light, accents, ground depth and integrated fog
must consume one coherent fitted depth convention. A projection-depth fit is distinct from moving the physical eye
or installing a second camera.

`scene_raster_support` derives conservative body/continuation bounds, living sparks' complete bounded flight, held
strand reach/width and reflected-target pixel halos from the immutable packet/recipe/accent records.
`orthographic_raster_projection` fits the XY-only axial span before considering depth, includes main and mirrored
support, and adds a bounded numerical guard. Fitting from an already depth-clipped frustum would preserve the defect
circularly. Render callers in Quick, Settings preview and the lab supply actual scene support through `physical_view`;
camera-only transform queries use the declared body support. Captures consume the ordinary Quick path.
`core/settings/framed_camera.py:orthographic_depth_interval` publishes the final interval for downstream fog admission.

`tests/test_waveform_orthographic_raster.py` instruments the real strip vertex shader: the old positive slab cuts
in-aperture vertices, while the fitted main/mirrored projections retain them without changing projection XY.
Waveform Orthographic no longer promises to reject every point behind its finite reference plane; Perspective and
non-opted modes keep their existing clip contract. Grounded eye/focus/editor/persistence, world coordinates, floor
occlusion and retained vertex IDs remain independent regression bars.

- [ ] **Awaiting Validation:** replay recorded wide/yawed views with living particles and held strands; inspect complete
  body/accent coverage, both projections, resize stability and reflections without exposing endpoints or phase jumps.
- [ ] **Awaiting Validation:** measure actual fitting/cohort-support and whole-frame cost under game60, then obtain
  operator judgement on attractive framing. A fitted slab does not establish musical response or artistic acceptance.

### Lens (advanced)
- Exposure, Bloom (R); Focus and Aperture only once shared defocus exists for this mode.

### Technical profile
- **Quality tier:** one Low/Medium/High setting for the large-display caps (march heights, mirrored march, floor
  reflection target and reflection-term pre-pass, strand segments). Not separate sliders.

### Rules, never controls
- **Smoothing:** every history-carried control passes two smoothing stages with an enforced minimum time (features
  at least about half a wavelength long); no sharp bends, spikes or jagged plateaus.
- **Floor contact:** sheets ease onto the floor (smooth, monotone, no creases), never through it; with Floor Give
  the floor they ease onto is the yielding surface.
- **Mist clearance:** a minimum the slider cannot go below; distant haze never pure black.
- **Fade, never vanish:** anything that appears or disappears fades (count changes included).
- **Flow speed:** never driven by music.

## 4. Reactivity

Binding guide: `Docs/Guides/Visualizer_Reactivity_Authoring.md` (signal jobs §1-2, real-music scales §2A, loud
passages §3, timescales §5, anti-patterns §11, new-mode workflow §12, passage ranges §13C). Waveform Ribbon is a
flowing history plus an immediate projection (now the travelling pulse of the Current reaction model; the C-elastic
wording in §4.1-4.2 is superseded there): new detail is written at the head and travels,
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
| Idle / silence | Subtle body/flow drift; no new musical sparks, strands or pulses; sparks expire smoothly; strands keep travelling with their roots | presence from `musical_weight`; an explicit idle lane, never fake energy |
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

## 5. Current implementation and admission work

The retained scene is `rendering/quick/scene3d/waveform.py:WaveformScene`; production supplies the existing Quick
frame/context, while the lab supplies explicit diagnostic time/camera. Plain scene inputs live in
`core/waveform_ribbon_scene.py`, appearance values in `core/ribbon_style.py`. No production owner imports the lab.
Retirement stays context-owned, attempts independent cleanup and retains failed handles for retry.

The single live visual rejection/acceptance checklist is `Current_Plan.md` §7.1. Four-card migration, Preset 3,
the unified replacement atmosphere and grounded long-lens camera are candidates under validation. Legacy fog layers
are removed. Their existence or focused checks do not close the operator's visual, motion, UX or loaded-cost gates.

## 6. Historical camera work: evidence only

The 1 November sweep (`wr08_camera_sweep/`) used a behind-eye Orthographic near plane and shaped side walls. Those
wall/fog treatments are now rejected. A later positive actor clip interval exposed the foreground/far-floor gap at
near-level tilt; the opaque infinite world-plane path addresses that gap without reviving walls. The remaining
Orthographic actor-slab diagnosis, fitted raster contract and remaining validation are owned by the Camera section above.
Earlier promotion/parity captures do not establish the latest atmosphere, floor or musical target.

The 3 November `wr_smooth_sparse_shortlife_v8_20261103` capture replays recorded PCM at 20–26 seconds with stable
source hashes. The smoother broad carrier, sparse 3–5-second strands and larger particle population are visible, but
the operator explicitly rejects small travelling dents. Floor texture/reflection, fog and colour remain below the
references. Its GPU-only median 8.15 ms/p90 10.14 ms is scoped capture evidence, not a game60 whole-frame pass.

**Operator-selected material baseline (3 November):**
[preserved exact image](Images/Waveform_Ribbon_Material_Baseline_20261103.png),
[full source/settings/capture receipt](Images/Waveform_Ribbon_Material_Baseline_20261103.capture.json).
The supplied clipboard image is pixel-identical to `wr_preset3_material_balance_20261103/frame_0003.png`, at source
time 23 s. Source revision `2e201069` plus the receipt's six explicit overrides reconstructs this baseline; Preset 3
now incorporates them. Keep background at least this bright and preserve the floor colour level. The operator calls
this a good direction, with remaining lumps; it does not approve full shape, musical motion, mist, floor texture or UX.

## 7. Remaining technical gates

- [ ] Prove history/continuation and persistent strand retirement across the widest admitted view and lowest flow speed.
- [ ] Cover four physical ribbons in geometry, transformed clearance, accents, light, collision and reflection.
- [ ] Prewarm one program per existing preparation opportunity; no shader burst on first playback or an enabled feature.
- [ ] Prove replacement atmosphere, strands, sparks and reflection Off paths retire their own work/resources.
- [ ] Measure whole-frame median/tails by quality tier at 1080p/1440p/4K and multiple displays, including actual
  applied settings, recorded source, CPU preparation, GPU work and uploads. The current strand preset is over budget.
- [ ] Keep all authored preset fields complete and mutable. Quiet/peak ranges remain pairs, never repurposed as random
  spreads, and all new visual editing must drive the same production renderer.
- [ ] Inspect slow motion for world anchoring, smooth density, floor detail/reflections and persistent strands. No
  screen-space fringe fibre test survives as a requirement to retain the rejected effect.
