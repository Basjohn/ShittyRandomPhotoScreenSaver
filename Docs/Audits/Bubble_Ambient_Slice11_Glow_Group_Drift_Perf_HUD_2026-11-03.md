# Bubble Ambient Slice 11: Glow response, Group Drift subscription, and `--perf` placement

**Baseline:** Supersedes `GODZIP_cc4c390a9e_BubbleAmbient_Slice10_GlowFootprint_Cohesion_2026-11-03.zip`. Full working-tree handoff, no edits to `Current_Plan.md` or `Future_Work.md`. The existing Bubble hero population, collision, ghost, wake, 49/51 Group Drift mix, occlusion and SINE retirement are intentionally preserved.

## User-observed problems

1. The on-card and per-display `--perf` boxes cover the top-left of screenshots. Requested: **top centre**, **70%-opaque black** only, and **1 px vertical inset** for the visualizer plus comfortable padding.
2. Particle glow is more attractive at idle than loud passages: the max setting fills a round shaded orb. Release takes roughly two seconds, despite the requirement to use **small-bubble breathing reactivity**, not extra size pulses.
3. Decorative microbubble/particle **Drift** fails to follow the native Bubble **Group Drift** carrier.

## Contracts / changes

### HUD (QML only)

- `DisplayScene.qml` `perfHud`: top-centre, retain 8 px top inset, black fill `#b3000000` (70.2% alpha). White text and border unchanged.
- `VisualizerPresentation.qml` `visualizerPerfHud`: top-centre, 1 px top inset, internal height +2 px (one additional top/bottom padding px); identical black alpha. Remain read-only / disabled; `--perf` admission unaffected.
- **Note:** Qt Quick native visual check is still required if a full-screen visualizer and the global HUD occupy exactly the same top-center footprint; two HUDs may overlap. Avoid unrelated lifecycle or screen/card coordinate hacks without an actual repro.

### Glow: preserve body, fix drive and shape

- The original hero Bubble `pulse_energy` deliberately releases at a slow rate (including small-bubble `decay_rate` 1.2 for the smallest bubbles). Reusing that **settled size signal** for particle light imposed a long, unwanted afterglow.
- `BubbleSimulation.tick()` now publishes only the **already admitted**, pre-size-smoothing small-bubble `gated_energy` summary when optional particle glow is on. No new raw audio, FFT, side-channel event consumption, clock, or change to the hero breathing response.
- `BubbleAmbientSimulation` follows this with a 45 ms attack and **authored Glow Release** default 160 ms (60–800 ms). That is independent of Bubble size release, and only affects ambient emission.
- Quieter baseline light is deliberately restrained (`0.10 * intensity`). The musical component now fades with the actual small-bubble gating rather than remaining near-full through a two-second hero-size decay.
- The OpenGL point sprite still retains the **identical physical core diameter**. An explicit `Glow Spread` slider (0.6–2.0×; default 1.0) adjusts the transparent *sprite envelope* only, while `vCoreRatio` counter-scales the actual body.
- The shader replaces the high-brightness Gaussian 'solid ball' with a **near-core suppressed** dual-falloff ring-of-light / diffuse aura. The light remains premultiplied radiance above the gradient and below the heroes, with the existing 8-bit target and existing occlusion pass. No extra draw call, texture or bloom pass. The high-end luminance no longer requires increasing coverage alpha.
- Both new controls are typed, defaulted and conditionally visible **only** when `Particles → Glow` is on. Existing Intensity, Reactivity, Colour, size and saved settings remain intact. There is no unexposed new user-tunable control.

### Decorative Group Drift subscription

- The ambient solver previously received the **resolved stream speed** but **not** the current Group Drift carrier. Its home-grown little lateral swish could not follow the Group Drift headings.
- After the hero Group Drift carrier is resolved, Bubble exports a read-only ambient-only `(shared_x, shared_y, independent_speed)` velocity in normalized units per second, with the existing 49/51 mix and the same musical gain as the main Bubble Group Drift.
- The ambient layer consumes it only when the corresponding **Microbubble Drift** or **Particle Drift** toggle is on, `bubble_group_drift` is enabled, and the main solver has an active non-swirl group carrier.
- Independently seeded ambient dots follow the shared vector and retain their own local phase. `Same` / `Reversed` both apply to the inherited carrier. Stream-only decoration remains stream-only; ordinary drift and swirl continue using the accepted previous paths. No changes to hero RNG or Group Drift motion.

## Acceptance and evidence

**Executed in the artifact environment:** 36 focused pytest cases on the actual pure-Python ambience module (Qt package initialization bypassed for testing only), covering optionality, direction, Group Drift inheritance, reversible directions, live columnarity, fixed particle dimensions, glow release envelope and visualizer viewport geometry; all passed. Changed Python source parsed/compiled. Typed/defaulted Builder controls checked. The `--perf` QML source was checked for top-centre anchoring, 70% backing and 1 px visualizer inset.

**Not verified here:** Native Qt Quick rendering, actual on-monitor glow/readability/FPS, real-music playback, compositor correctness or native GPU cost. The native project test harness depends on PySide6, unavailable in this environment. The visual and temporal acceptance gate remains operator-owned; the code is **not** claimed visually finished.

### Recommended native checks

- [ ] On both monitors, compare display-level HUD placement with visualizer-card HUD. Check particularly whether they overlap on full-screen cards.
- [ ] Verify only the black backing is 70% opaque; text/border opacity unchanged.
- [ ] Idle vs sudden loud passage vs stop: compare light immediately and again 0.15, 0.30, 0.60 seconds after stopping. The particle body diameter must remain unchanged.
- [ ] At Glow Intensity 150% / Reactivity 300%, test Glow Release 80/160/500 ms and Spread 0.8/1.0/1.5×. Ensure the peak doesn't resemble a solid grey sphere and idle remains visible but restrained.
- [ ] Enable Group Drift with micro/particle Drift on; compare decor shared direction to real bubbles for Same/Reversed. Verify disabling Drift but leaving Stream on means stream inheritance only.
- [ ] Verify extreme-wide, extreme-tall and enlarged content with/without occlusion, and measure CPU/GPU cost under concurrent load.
- [ ] Confirm existing Bubble presets behave byte-identically with all ambient decorations off *in a native deterministic replay*. This cannot be certified from a non-native container.
