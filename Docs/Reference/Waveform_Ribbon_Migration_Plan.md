# Waveform Ribbon: migration plan (WR-08 controls, reactivity and production port)

Planning owner for **WR-08**, subordinate to [`Current_Plan.md`](../../Current_Plan.md) §7.1 and the lab plan's
WR-08 gates ([`Waveform_Ribbon_Lab_Plan.md`](Waveform_Ribbon_Lab_Plan.md)). The lab owns the look; this document
owns what the production mode exposes, how reactivity is mapped and calibrated, and the order of the port. Nothing
here is built yet. Values quoted are the lab recipes' current values, recorded for orientation: presets are
operator-authored and never test oracles.

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
| Complete Scene | `complete` | Main fog board: three sheets, cyan → blue-violet → magenta world grade, mist shaped and lit by the waveform, wet columns |
| Silk Bands | `alternate` | Alternate board: three per-band ribbons coloured by ribbon (quiet blue/teal/lavender, loud magenta/orange/blue-violet), luminous silk, free strands |
| Preset Range | `range` (parked) | Preset-range board: tight braid, a towering bass arc, gradient running on to orange |

Names are suggestions for the operator to rename.

## 3. Controls by bucket

Each bucket lists its controls and the editor that shows them. "Existing" editors are already in the codebase;
"New" editors are built in this migration and shared by later modes where they fit.

### Ribbons
- **Ribbon Count:** 1-3. The cap follows the mist's per-sheet clearance rows (`ENVELOPE_RIBBONS`, 3 in the lab)
  and the packet's `MAX_RIBBONS` (8); raising it past 3 needs more envelope rows and a cost check first.
- **Per ribbon (Ribbon Cards, New):** one card per ribbon with a live thumbnail of that ribbon.
  - band it follows (Bass, Mids, Highs, All);
  - character: height share, width share, wave rate share, phase offset, light share;
  - quiet and loud colours, as two swatch pairs (centre and edge);
  - how far loud colour replaces quiet (the tuner's `tint` target, per ribbon).
- **Sheet Look:** strand count and fineness, strand light, body fill, rim light and rim glow, glints. Sliders over a
  live close-up of one sheet (Glow Preview, New).

### Shape and Reactivity (Shape Tuner, New)
- **Matrix editor:** rows are energy sources, columns are ribbon properties; each cell has a gain and a response
  curve with draggable handles.
  - **Sources:** Bass, Mids, Highs, Loudness, Onsets, and the Head Wave (the authored oscillator that draws the waves,
    the musical history's carrier).
  - **Targets:** height, swell (local compression of neighbouring folds), width, twist, lift, spread between ribbons,
    depth sway, secondary deformation, light, sparkle, colour (tint), bass arc (one taller arc per bass passage).
  - Per target: quiet and loud values (the range the source sweeps) and a smoothing time with an enforced minimum.
- **Character presets inside the tuner:** e.g. Even Swell (complete scene), Dominant Peak (preset range), Silk Sweep
  (alternate).
- **Live preview:** a 3D or angled-2D ribbon driven by a synthetic sweep (bass, mids, highs, loud passage) so the user
  sees the result without music. The lab's `Shaping` dataclass is the model this editor edits.

### Flow
- **Flow Speed:** the history's drift across the hall. A fixed scene constant while running: music never changes it
  (gate A), but the user authors it.
- **Wave Rate:** the head wave's frequency (long sweeps to tight ripples).
- **Wave Swell, Height Swell, Depth Sway:** the head wave's slow variation.

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
- **Sheet Glow:** the share of sheet light sent to the bloom (local glow without blooming the mist).
- **White-Hot Cores:** the brightest strands burn white; the rest keep their colour.
- **Bloom, Exposure:** scene-wide (also mirrored in Lens).

### Free Strands
- **Free Strands** toggle, then: count per knot, length, reach (how far they curl away), halo (fuzzy splash), glow,
  droplets, peel time. Previewed on a sheet during a synthetic loud passage (Glow Preview).
- Strands always grow out of a rim line and fade in. Their gating follows sparkle (loud passages throw off more).

### Sparks
- **Sparks** toggle, then: count per knot, size range (smallest/largest), drift, rise, light, lifetime, whiteness.

### Mist
- **Mist** toggle (on in every starting preset; off removes all of its passes and resources).
- Density, Clearance (how far the waveform repels it, with a minimum), Billows, Edge Line (strength and fibre),
  Fringe Colour (gradient share), Distance Haze (darkness, never pure black), Floor Mist (thickness toward edges and
  distance).
- Preview: the scene itself; a small turned-view inset helps judge 3D clearance.

### Floor
- Wetness/Reflection, Streak Length, Column Fade, Mist Reflection.
- Floor contact (sheets deform onto the floor) is a rule, not a control.

### Reaction
Waveform Ribbon's own controls, following the reactivity guide (`Docs/Guides/Visualizer_Reactivity_Authoring.md`);
the shared audio controls (sensitivity, input gain, block size) stay at their shared technical owners.
- **Passage Response:** how far quiet → loud passages move the tuner's ranges (the eased passage drive, §4.2).
- **Beat Pulse:** how much a hit lifts height and light, and how gently it settles (rise about 45 ms, settle about
  0.65 s as DevCurve).
- **Accent Threshold:** how far an onset must stand out from the recent ones to throw sparks and strands.
- **Idle Motion:** the head wave's own drift in silence (honest idle, no fake music).
These sit beside the Shape Tuner, which says *what* each source moves; these say *how* the music arrives.

### Camera (advanced, shared framed camera)
- Camera Position (Existing: `SceneCameraPosition`), Projection (Orthographic default, Perspective), FOV (Perspective
  only), Auto Rotate with After and Speed.

### Lens (advanced)
- Exposure, Bloom; Focus and Aperture only once shared defocus exists for this mode.

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
flowing history, so it reacts unlike Extruded Bubble: music is *written into the ribbon at its head* and then
travels across the hall, plus immediate light and accents that need no history.

### 4.1 Waveform ribbon practice (research, 1 November)
Waveform ribbon visualisers commonly render the signal or its band energies as a flowing 3D ribbon. Bass, mids and
treble drive the geometry and colour, and hits drive bursts of light. Smoothing uses envelope followers with
separate attack and release. Sources:
- [3D Audio Visualizer, waveform as a flowing 3D ribbon (teamzlab)](https://tool.teamzlab.com/3d/audio-visualizer/)
- [How to Make a 3D Music Visualizer (Violet Recording)](https://violetrecording.com/how-to-make-a-3d-music-visualizer/)
- [Envelope detector (musicdsp)](https://www.musicdsp.org/en/latest/Analysis/97-envelope-detector.html),
  [Faust analyzers](https://faustlibraries.grame.fr/libs/analyzers)

**Chosen concept (the pleasant common ground, in our terms):**
- **The head wave carries the shape.** Music modulates its height, swell and rate. Raw bands plotted as height make
  jagged plateaus (lab plan §4A).
- **One ribbon per band** (alternate board: bass, mid, high), each through the tuner; the complete scene's sheets
  share all bands with different characters.
- **Hits light things up immediately:** whole-ribbon light, sparks, free strands. Light needs no history, so it can
  be fast.
- **The passage sweeps the quiet → loud ranges**, slowly, never per beat.

### 4.2 Reaction vocabulary (guide §12)

| Musical moment | Waveform Ribbon response | Signal (existing authority) |
|---|---|---|
| Idle / silence | Head wave keeps a slow honest drift; no sparks, strands or pulses; fade, never vanish | presence from `musical_weight`; an explicit idle lane, never fake energy |
| Sustained quiet passage | Ranges near their quiet handles: low waves, narrow sheets, quiet colours | eased passage intensity on the fixed real-music scale (guide §2A, §5 "slow passage drive": two even ~1.2 s stages) |
| Sustained loud passage | Ranges near their loud handles: tall sweeps, wide sheets, loud colours, more sparkle; beat contrast kept inside the chorus | same passage drive; beats multiply inside it, never add a floor (§13C) |
| Kick / bass hit | Height pulse at the head (written into history, so it travels), bass ribbon wider; a bass passage can raise one taller arc | bass transient through `passage_ramp`, asymmetric envelope (rise ~45 ms, settle ~0.65 s) |
| Snare / generic onset | Light flash along the ribbons, sparks; free strands peel off on accents | typed event bus, consume once; accents = onsets above the recent mean (§13C) |
| Vocal rise / swell | Twist and depth sway grow; colour moves toward loud | mid/vocal lane, medium continuous envelope |
| Highs | Fine shimmer: glints, sparkle density | high band, control-normalised, ramped by the passage |
| Release to calm | Ranges ease back over the passage stages; flow speed never changes | passage drive |

**History rules specific to this mode:**
- **Written at the head, never rewritten.** History-carried controls (height, width, twist, lift, tint) are sampled
  when a knot is admitted. A control changing over d seconds draws a feature flow speed × d long, so every one passes
  the two-stage band-limit (lab plan §4A).
- **Immediate channels** (whole-ribbon light, sparks, strands, glow) may follow the beat directly; they need no
  history.
- **Flow speed never follows the music** (gate A). DevCurve's lesson: a ±10% beat nudge on travel read as
  fast/slow/fast/slow.

### 4.3 Where to calibrate (recommendation)
- **Look and the tuner model: the lab** (done for both boards, synthetic sources).
- **A cheap lab smoke (WR-07):** replay one quiet and one loud recorded feature window
  (`logs/visualizer_recordings/*.jsonl`) into the lab's tuner sources. It checks that the model reaches the boards'
  quiet and loud shapes from real signal shapes before production code depends on it. It does not calibrate.
- **Calibration: the migration**, because it needs the real BeatEngine lanes on their real scales, the shared
  sensitivity and technical profile, and the preset system, which exist only in production. Follow guide §12:
  - neutral to maximum synthetic cases with monotonic ordering;
  - silence, quiet song, ordinary, hot chorus and isolated hits over a loud bed;
  - the share of frames at each driver's ceiling (pinned drivers, §13B);
  - preset-to-source reachability;
  - then `tools/visualizer_live_check.py` with recorded music and `--load game60`, and installed eyes-on review.

## 5. Port order

1. Descriptor, logical runtime, ring/packet ownership, empty scene with the framed camera (Orthographic default) and
   dormancy/Off paths.
2. Ribbons with material and glow (complete-scene preset), then floor with reflection and contact.
3. Mist (volume, march, shape bake, edge line, floor mist) with its Off path and quality tier.
4. Sparks and free strands.
5. Settings buckets and the existing editors; then the New editors (Gradient Node Editor, Ribbon Cards, Shape Tuner,
   Glow Preview), each previewing the real renderer.
6. Starting presets authored from the lab recipes; preset repair fill and completeness guard.
7. Reactivity: recorded-feature replay calibration, then the live check with recorded music and game load.
8. WR-09 acceptance: mock | lab | production sheets, all camera views, cost at 1080p/1440p/4K, operator review.

## 6. Open findings carried into the migration (camera sweep, 1 November)

Twelve views per look, both projections (`wr08_camera_sweep/`):
- **Fixed:** in zoomed-out and low Orthographic views the floor near the camera was clipped into a black band. The
  near plane now sits behind the eye; the mock pose is unchanged (7 pixels moved by more than 8/255).
- **Open: end-on views (turn about ±0.35, 63°).** Looking along the ribbons, their light stacks along the line of
  sight and the floor reflection blows out into white columns. Black sky shows past the mist's ends at the top
  corners.
- **Open: turned Perspective view.** The far floor stays bright and streaked up to its far edge (horizon visible);
  the distance mist does not hide it along every view direction.
These are lab look fixes, owed before WR-09; production must not paper over them with per-view limits.
