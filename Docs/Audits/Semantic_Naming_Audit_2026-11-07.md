# Semantic Naming Audit (2026-11-07)

Read-only audit. No code, docs, settings, presets or tests were changed. Source snapshot: branch
`worktree-agent-ab77df54c8fe5d4a6` at `c2e20df1` (main `106592b0` plus the unmerged evidence-layout work).
Counts are `git grep` over tracked files, excluding `release/` and `logs/`. "files/lines" means matching files and
matching lines.

Operator trigger: "The oddity with neon lake is an old semantic never being updated and spread across the
application, same thing with Devcurve which is actually called Spline Curve."

## 0. Summary

- **Two user-facing name sources disagree.** Settings and Guided Setup show `VisualizerModeDescriptor.display_name`.
  The Studio shows its own hand-typed titles. Four of the nine modes differ, and the Studio shows the dev name
  **"DevCurve Studio"** to users (§2.3).
- **Neon Lake has three vocabularies in code:** `shockwave_grid` (the id, keys, renderer, builder, Studio adapter
  module), `shockwave` (the frame-runtime file and the onset-wave concept) and `neon_lake`/`neon_*` (camera,
  world constants, eight GL program modules, 26 test files). 103 files mention only "shockwave" and 37 only
  "neon lake". A grep for either name misses owners.
- **The product name "Spline Curve" hardly appears in the repo.** It is in 6 files and 9 lines. `devcurve`/`DevCurve`
  appears in 181 files. Index.md has no routing row for it, and Current_Plan.md calls it DevCurve 13 times and
  Spline Curve never.
- **Persisted ids should stay as they are.** Each mode id is the key for 70-145 persisted settings leaves, preset
  folders (shipped and user), preset JSON `mode` fields, bucket-state members, the Custom cache, goldens and
  release media. Fix the naming with a generated, test-guarded name map and product-first docs, not with renames.
- **Evidence layout:** keep `visualizers/<mode id>` and accept product-name slugs as aliases that resolve to the id
  (§5).

## 1. Name map (from the canonical owners)

### 1.1 Visualizer modes

User-facing names are taken from where they are rendered:

- **Settings:** the pills and enable checkboxes (`ui/tabs/visualizers_tab.py:179`, `:263`), the 3D Quality tab
  (`ui/tabs/scene3d_tab.py:61`) and the preset row (`ui/tabs/media/preset_slider.py:445`). All of these read
  `descriptor.display_name`.
- **Guided Setup:** `ui/onboarding/selection_pages.py:217` and `:566`, which read `display_name`.
- **Studio:** `ui/studio/registry.py:48-58`, through the mode switcher `ui/studio/settings_link.py:557`, plus each
  adapter's `StudioSchema` title (header, `ui/studio/controller.py:181-182`) and class `title` (window title,
  `ui/studio/surface.py:154`).

| Settings / Guided Setup (`display_name`) | Studio (switcher / header) | Mode id (persisted) | Key prefixes (persisted) | Frame runtime | Renderer / shader | Settings builder · Studio adapter | Spec section in `visualizer_mode_settings.py` | Other names in circulation |
|---|---|---|---|---|---|---|---|---|
| Spectrum | Spectrum / Spectrum Studio | `spectrum` | `spectrum_` | `widgets/spotify_visualizer/spectrum_frame_runtime.py` `SpectrumFrameRuntime` | `rendering/quick/visualizer/implementations/spectrum.py`; `widgets/spotify_visualizer/shaders/spectrum.frag` | `ui/tabs/media/spectrum_builder.py` · `ui/studio/spectrum_adapter.py` | `# ---- Spectrum` (:1356) | none |
| Oscilloscope | Oscilloscope / Oscilloscope Studio | `oscilloscope` | `osc_` (look) **and** `oscilloscope_` (analysis) (`visualizer_mode_registry.py:230`) | `oscilloscope_frame_runtime.py` | `implementations/oscilloscope.py`; `shaders/oscilloscope.frag`; `rendering/gl_programs/oscilloscope_program.py` | `oscilloscope_builder.py` · `oscilloscope_adapter.py` (`PREFIX = "osc_"`, :36) | (:1135) | "osc" |
| Bubble | Bubble / Bubble Studio | `bubble` | `bubble_` | `bubble_frame_runtime.py` | `implementations/bubble.py`; `shaders/bubble.frag` | `bubble_builder.py` · `bubble_adapter.py` | (Bubble spec) | "original Bubble", "2D Bubble" (23 doc/test/tool files) |
| **Spline Curve** (`visualizer_mode_registry.py:267`) | **DevCurve / DevCurve Studio** (`ui/studio/registry.py:57`; `devcurve_adapter.py:417`, `:489`) | `devcurve` | `devcurve_` (73 leaf lines in `core/settings/default_settings.py`) | `devcurve_frame_runtime.py` `DevCurveFrameRuntime`; solver `devcurve_runtime.py` | `implementations/devcurve.py` `QuickDevCurveRenderer`; `shaders/devcurve.frag` (`shaders/__init__.py:35`) | `devcurve_builder.py` · `devcurve_adapter.py` `DevCurveStudioAdapter` | header "Spline Curve" (:1199), object `_DEVCURVE` (:1203), comment "DevCurve solves..." (:1201) | "DevCurve" (70 files/325 lines), "Dev Curve" (15/20), README "Spline Curve (Dev Curve)" (`README.md:48`) |
| Voxel Sphere (:284) | **Sphere / Sphere Studio** (`registry.py:51`; `sphere_adapter.py:226`, `:550`) | `sphere` | `sphere_`; layout profile `3d:sphere` (:319, persisted) | `sphere_frame_runtime.py` | `implementations/sphere_voxel.py` `QuickSphereVoxelRenderer` | `sphere_builder.py` · `sphere_adapter.py` | "Voxel Sphere" (:1459) | "Sphere" |
| Extruded Spectrum | Extruded Spectrum / … Studio | `extruded_spectrum` | `extruded_spectrum_`; layout profile `3d:extruded_spectrum` | **shares** `SpectrumFrameRuntime` (:336-337) | `implementations/extruded_spectrum.py` | `extruded_spectrum_builder.py` · `extruded_spectrum_adapter.py` | (:1293) | none |
| **Neon Lake Basin** (:367) | **Neon Lake / Neon Lake Studio** (`registry.py:56`; `shockwave_grid_adapter.py:401`, `:557`) | `shockwave_grid` | `shockwave_grid_` (124 leaf lines in defaults; 124 distinct keys in preset 1) | **`shockwave_frame_runtime.py`** (no `_grid`) `ShockwaveGridFrameRuntime` (:375-376) | `implementations/shockwave_grid.py` `QuickShockwaveGridRenderer`, which calls itself "Neon Lake Basin" (:92-95, :260); `gl_programs/shockwave_grid_program.py`; `gl_programs/neon_lake_basin_program.py`, `neon_lake_basin_mesh.py`, `neon_lake_basin_options.py`, `neon_celestial.py`, `neon_starscape.py`, `neon_terrain_*.py` | `shockwave_grid_builder.py` · `shockwave_grid_adapter.py` **`NeonLakeStudioAdapter`** | header **"Shockwave Grid"** (:836), `_SHOCKWAVE_GRID` (:851), `_NEON_AUTO_ROTATE` (:849) | camera `core/settings/neon_lake_camera.py` (:393), `core/constants/neon_lake_world.py`; "Shockwave Grid" (28/39), "Shockwave" (bare), README "Shockwave Grid (3D)" (`README.md:51`) |
| Extruded Bubble | Extruded Bubble / … Studio | `extruded_bubble` | `extruded_bubble_` | `extruded_bubble_frame_runtime.py` | `implementations/extruded_bubble.py`; `gl_programs/extruded_bubble_*.py` | `extruded_bubble_builder.py` · `extruded_bubble_adapter.py` | (:1747) | "EB" (94 files/504 lines) |
| Waveform Ribbon | **Waveform / Waveform Studio** (`registry.py:48`; `waveform_adapter.py:299`, `:1018`) | `waveform_ribbon` | `waveform_ribbon_` | `waveform_ribbon_frame_runtime.py` | `implementations/waveform_ribbon.py`; `rendering/quick/scene3d/waveform.py`; `gl_programs/waveform_*.py`, `ribbon*.py` | `waveform_ribbon_builder.py` · **`waveform_adapter.py`** | Waveform Ribbon | "Waveform" (192 whole-word lines in docs), "ribbon" (shared `core/ribbon_*.py` primitives); camera SPEC lives in `core/waveform_ribbon_scene.py:10`, not in `core/settings/waveform_ribbon_camera.py` (which holds the floor contract) |
| *Retired* Sine Waves | none | `sine_wave` | `sine_`, `sinewave_`, `preset_sine_wave` | none | none | none | none | stripped by `core/settings/visualizer_retired_modes.py:9`, `:70` |
| *Retired* Blob | none | `blob` | `blob_`, `preset_blob` | none | none | none | none | same seam |

#### Persisted surfaces for every mode id

- the `widgets.spotify_visualizer.mode` value;
- `mode_activation` keys;
- the `preset_<id>` key (`visualizer_mode_registry.py:200-202`);
- every `<prefix>*` leaf;
- `ui.visualizer_bucket_states` members `<id>:<bucket>` (e.g. `'shockwave_grid:terrain'`, `'devcurve:shaper'`
  in `core/settings/default_settings.py`);
- `visualizer_custom_presets` keys (`visualizer_retired_modes.py:113-119`);
- shipped `presets/visualizer_modes/<id>/` and each preset JSON's `"mode"` field;
- the user preset folder `<shared presets>/visualizer_modes/<id>/` (`core/settings/visualizer_presets.py:475`,
  `:489`) and the release preset tree;
- SST exports;
- `tests/fixtures/visualizer_frozen_settings/<id>.json` and `tests/goldens/visualizer_replay/v1/*__<id>.json`;
- onboarding art `ui/assets/onboarding/source/visualizer_<id>.png`;
- release showcase file names `visualizer_<id>_<preset>.webp` (`tools/release_media.py:111`, `:148`).

`display_name` and Studio titles are **not** persisted. Studio titles reach only the switcher, header and window
title.

### 1.2 Transitions (`rendering/transition_registry.py`, `rendering/transition_settings.py`)

**Persistence is the inverse of Visualizers.** The **display label** is persisted:

- `transitions.type`;
- the `activation`, `pool` and `durations` maps (`core/settings/transition_retired.py:21`).

The **section** is the stable id, or `section_key` where one is set (`transition_registry.py:46-49`). Renaming a
label already has a bridge: `legacy_names` (`:43`, `:262-268`).

Labels and ids are the same apart from case for Wipe, Slide, Glass Shatter, Exploding Tiles, Beam, Volumetric
Dissolve, Liquid Lens, Chromatic Shear, Capillary Bloom, Cube Turn, Disintegrate, Page Curl, Crossfade, Blinds,
Crumble, Particle and Burn. The ones that differ:

| Label (persisted) | Stable id / section | Other internal names | Note |
|---|---|---|---|
| Ripple | `ripple` | GL key `raindrops`, `raindrops_program.py`, `raindrops_program`/`raindrops_uniforms`, `GLCompositorRainDropsTransition` (:53-64); runtime label `raindrops` (:341) | legacy label "Rain Drops" (:63) |
| 3D Block Spins | id `block_spins`, **section `blockspin`** (:75-81) | `blockspin_program.py`, `BLOCK_SPIN_*`, `GLCompositorBlockSpinTransition`, **`gl_program_key=WARP`** (:78) | four spellings. The WARP key belongs to Warp Dissolve. |
| Warp Dissolve | `warp_dissolve` | `implementations/warp.py`, `warp_program.py`, key `warp` | |
| Directional Pixel Accretion | `pixel_accretion` | | |
| Melt Drip | `melt_drip` | docs say "Melt" | |
| VHS Distortion | `vhs` | | |
| Edge Bloom Reveal | `edge_bloom` | | |
| Membrane Turnover | `membrane` | | |
| Surface Tension Merge | `surface_tension` | | |
| Depth Card Cascade | `depth_cascade` | | |
| Jigsaw Piece Flip | `jigsaw` | | |
| Burn | `burn` | field `smoke_density` labelled "Spark Intensity:" (`transition_settings.py:602`) | persisted field |
| *Retired* Diffuse, Block Puzzle Flip, Ink Bloom, Relief Rise, Accordion Fold | `diffuse`, `block_flip`, `ink_bloom`, `relief_rise`, `accordion_fold` | | stripped (`transition_retired.py:14-20`); "Claw Marks" and "Shuffle" map to Crossfade (`transition_registry.py:267-268`) |

The `gl_program_key`, `program_attr`, `uniforms_attr` and `compositor_transition_class` fields, and
`get_transition_program_specs`/`get_transition_program_map` (:311-329), have **no production caller**. Only
`tests/test_transition_registry.py` uses them. No `class GLCompositor*` exists anywhere. The runtime resolver still
accepts the class-name strings (:373-375), which 12 test files use as identities.

### 1.3 Widgets (`core/settings/widget_family_catalog.py`, `rendering/widget_descriptors.py`)

| User-facing | Id (persisted section) | Other internal names |
|---|---|---|
| Family "Visualizers"; checkbox "Enable Beat Visualizer" (`ui/tabs/visualizers_tab.py:238`); member label **"Spotify Visualizer"** (`widget_family_catalog.py:174`), shown in Guided Setup Arrange (`ui/onboarding/arrange_model.py:517`), display routes (`ui/widget_display_routes.py:80`) and stack-conflict text (`ui/widget_stack_predictor.py:688`, `:809`) | `spotify_visualizer` (668 files/2811 lines) | package `widgets/spotify_visualizer/`, `SpotifyVisualizer*`, `core/settings/models/_spotify_visualizer.py`, `VisualizerPresentation.qml` |
| Games You Follow (:181) | `steam_progress` (catalog comment :166 calls it "the retired persistence key"; `default_settings.py:404-406`, `:6032`) | `games_you_follow.py`, `GamesYouFollowPresentation.qml`, `steam_followed_runtime.py`, `steam_followed_layout.py`, `rendering/games_followed_child_roles.py`: five spellings |
| Volume | `spotify_volume` | `media_volume_runtime.py` |
| Mute Button | `mute_button` | `system_mute_runtime.py` |
| Clock / Clock 2 / Clock 3, Weather, Media, Reddit 1/2, Custom 1-4, NEWS categories, Gmail, Achievement Pulse, Abandonment Issues, Friend Pulse, System Audio OSD, System Stats | same as label | no mismatch worth acting on |

### 1.4 Materials and themes. One word, several systems.

"Glass" means all of the following:

| Meaning | Owner | Persisted as |
|---|---|---|
| Settings/Studio **window backdrop** (DWM AccentPolicy) | `core/windows/dwm_blur.py:194-208` (`"glass"` :202); `ui/settings_theme_io.py:151-156` | `.srtheme` `backdrop.mode`; the file-name tags `[Glass]`/`[Acrylic]` |
| **Card surface material** (shader-drawn) | `rendering/quick/widgets/surface_material.py:22-31`; `rendering/quick/qml/MaterialSurface.qml:26-30` | `widgets.global.surface_material` and per-widget overrides, `"glass"` |
| Glass Shatter transition | `glass_shatter` | label + section |
| 3D Block Spins "edge glass" | `transitions.blockspin.edge_glass` (`rendering/quick/transitions/parameter_resolution.py:435`) | field |
| Neon Lake surface style "glass" | `_BASIN_GLASS` (`visualizer_mode_settings.py:839`) | `shockwave_grid_*` value |
| Extruded Bubble "Glass" bucket, "Lit Glass" | `visualizer_mode_settings.py:1772`, `:1916` | `extruded_bubble_*` |

"Acrylic" also exists as both a window backdrop and a card material. R-61 forbids runtime cards from borrowing the
Settings AccentPolicy stack (`Docs/Architecture/Card_Surface_Materials.md`, "Related records").

## 2. Mismatches ranked by how likely they are to cause wrong work

### 2.1 Neon Lake: three vocabularies, plus a legitimate homonym (highest risk)

**Spread:**

| Term | core | rendering | widgets | ui | tests | tools | Docs |
|---|---|---|---|---|---|---|---|
| `shockwave_grid` | 328 | 111 | 47 | 17 | 1233 | 56 | 276 |
| "Neon Lake" | 5 | 13 | 1 | 21 | 36 | 8 | 111 |
| `neon_lake` | 6 | 13 | 0 | 5 | 52 | 12 | 30 |

Totals: `shockwave_grid` 135 files/2693 lines; "Neon Lake" 78/219; `neon_lake` 49/122; "Neon Lake Basin" 21/47;
"Shockwave Grid" 28/39.

**File sets:** 103 tracked files mention "shockwave" with no "neon lake". 37 mention "neon lake" with no "shockwave".
64 mention both.

- **"shockwave" only:** `core/settings/default_settings.py`, `visualizer_presets.py`,
  `visualizer_settings_contract.py`, `rendering/quick/scene_controller.py`,
  `rendering/quick/visualizer/render_host.py`, `widgets/spotify_visualizer/config_applier.py`,
  `logical_frame_capture.py`, `mode_capabilities.py`, `render_state.py`, `transient_bus.py` and the frame runtime
  itself.
- **"neon lake" only:** `core/constants/neon_lake_world.py`, `neon_lake_basin_mesh.py`, `neon_terrain_extent.py`,
  `ui/studio/brush.py`, `ui/studio/engine_answers.py`, `widgets/spotify_visualizer/view_orbit.py`.

**The tests are split as well.** 26 files are named `tests/test_neon_*.py`, one is `tests/test_qtquick_shockwave_grid.py`,
and 63 test files mention `shockwave_grid`.

**The docs say it four ways:**

- `Spec.md:775` treats them as two modes in one sentence: "Only Spectrum, Extruded Spectrum and Shockwave Grid enter
  the Spectrum-authored bar-shaping pipeline; Neon Lake Basin preserves that frequency profile…".
- `Index.md:22` and `:153` say "Shockwave", the latter inside the Sphere row.
- `Docs/Guardrails/Visualizer_Presentation.md:18` and `:76` say "Shockwave".
- `Docs/TestSuite.md:658`, `:678` and `:699` say "Shockwave Grid".
- `Current_Plan.md:1008` says "Neon Lake (Shockwave Grid)".
- The user-facing `README.md:51` says "Shockwave Grid (3D)".

**Homonyms:**

- "shockwave" is also the mode's real **onset-wave concept**: `ShockwaveEvent`, `SHOCKWAVE_WAVE_GLSL` and
  `SHOCKWAVE_DEPTH` in `rendering/gl_programs/neon_lake_basin_program.py:24`, `:120`, `:370` and
  `neon_terrain_reaction.py:127`. A mechanical `shockwave → neon_lake` sed would corrupt real semantics.
- "neon" collides with preset names (`oscilloscope/preset_2_neon_halo.json`,
  `waveform_ribbon/preset_7_neon_tide.json`, **`devcurve/preset_6_neon_skyline.json`**) and with themes
  ("Neon Mall", "Smoked Neon Orchard").

**History:**

- `ef09aa53` (2026-10-03) added "Shockwave Grid: a neon grid floor rippled by onset shockwaves".
- `86f68912` (2026-10-13) rebuilt it as Neon Lake Basin and kept the id.
- New modules after that were named `neon_*`. The current split is the result of that **partial rename**.

**Failure scenarios:**

- An agent asked to fix Neon Lake's water greps `neon_lake` or "Neon Lake". It finds the camera, the world
  constants and 26 tests. It misses `_SHOCKWAVE_GRID` (`visualizer_mode_settings.py:851`, under a header reading
  "Shockwave Grid"), `widgets/spotify_visualizer/shockwave_frame_runtime.py` and `logical_frame_capture.py`, then
  writes a second Neon-named helper instead of editing the owner.
- An agent looks for the runtime as `shockwave_grid_frame_runtime` and finds nothing, because the file is
  `shockwave_frame_runtime.py` while its class is `ShockwaveGridFrameRuntime`.
- An agent reads Spec.md:775 and treats "Shockwave Grid" and "Neon Lake Basin" as separate modes.
- An agent runs `pytest -k neon` as the focused gate and skips `test_qtquick_shockwave_grid.py` plus the 63
  shockwave-only test mentions.
- The operator cannot find evidence under `visualizers/shockwave_grid` (§5).

### 2.2 Spline Curve: the product name is almost absent (high risk)

**Spread:**

| Term | Files/lines | Per directory |
|---|---|---|
| `devcurve` | 153/2840 | core 292, rendering 83, widgets 213, ui 23, tests 1070, tools 75, Docs 168 |
| "DevCurve" | 70/325 | |
| "Dev Curve" | 15/20 | |
| **"Spline Curve"** | **6/9** | `visualizer_mode_registry.py:267`, `visualizer_mode_settings.py:1199` and `:1252`, `README.md:48`, `Docs/Reference/Visualizer_Reference.md:81` and `:397`, R-58, `tests/test_visualizer_settings_plumbing.py:931` |

- **Index.md has no routing row** for Spline Curve, DevCurve or Oscilloscope.
- `Current_Plan.md` says "DevCurve" at :77, :85, :464, :1018 and has 0 "Spline".
- Guardrails only say "DevCurve"/"Dev Curve": `Performance_Optimization_Contract.md:50`,
  `Visualizer_Presentation.md:59`, `:76`, `:284`, `:350`, `:463`.
- Memory files `srpss-continuous-play-reactivity.md`, `srpss-real-music-scales.md` and `srpss-pre-v5-v6-gate.md`
  also use "DevCurve"/"devcurve".

**The users see the dev name.** The Studio switcher shows "DevCurve" (`ui/studio/registry.py:57`). The Studio header
and window title read "DevCurve Studio" (`ui/studio/devcurve_adapter.py:417`, `:489`). The Ghost bucket's tooltip
reads "Optional trail for debug visibility." (`visualizer_mode_settings.py:1209`).

**Homonym:** "spline" is generic math in 16 code files: the Waveform ribbon (`core/ribbon_continuation.py`,
`core/ribbon_geometry.py`, `rendering/gl_programs/ribbon*.py`), `extruded_bubble_program.py`, `heightfield.py`,
`neon_terrain_surface.py` and `shaders/oscilloscope.frag`. Only 3 of them are Spline Curve's.

**Failure scenarios:**

- The operator says "Spline Curve feels dead". An agent greps "spline", lands in the ribbon spline continuation and
  "fixes" Waveform.
- An agent concludes there is no such mode and proposes a new `spline_curve` mode or file.
- An agent reads "DevCurve" in Current_Plan and reports to the operator under a name the operator does not use.

### 2.3 Two user-facing name sources disagree (high risk, user-visible)

`display_name` (Settings, Guided Setup) and the Studio registry titles (switcher, header, window) differ for four
modes:

| Mode id | Settings / Guided Setup | Studio |
|---|---|---|
| `devcurve` | Spline Curve | DevCurve |
| `shockwave_grid` | Neon Lake Basin | Neon Lake |
| `sphere` | Voxel Sphere | Sphere |
| `waveform_ribbon` | Waveform Ribbon | Waveform |

The operator's own word ("neon lake") matches the Studio, not Settings, so even the product name of Neon Lake is
unsettled.

`register_studio_adapter` takes a free-text `title` (`ui/studio/registry.py:24-27`), and every adapter hard-codes
two more titles. That is three copies per mode with no link to `display_name`.

**Failure scenario:** an agent asked to "rename DevCurve to Spline Curve everywhere the user sees it" edits the
registry and stops. The Studio still says DevCurve. The reverse also happens: an agent copies a Studio title into a
new Settings string.

### 2.4 Retired Sine described as live in governing docs (medium)

The code is clean. Sine and Blob appear only in the retirement seam and in maths: no `sine_wave` or `blob_` key use
outside `visualizer_retired_modes.py`. The governing docs still describe Sine as live:

- `Spec.md:775` ("Sine heartbeat and Dev Curve get pre-AGC musical energy…");
- `Docs/Guardrails/Visualizer_Presentation.md:76` ("Sine/Dev Curve must retain musical-energy inputs") and `:463`
  ("Spectrum/Oscilloscope/Sine/DevCurve");
- `Docs/TestSuite.md:658` (lists Sine among the unshaped modes);
- `Docs/Reference/Visualizer_Reference.md:909-910` ("currently Sine, disabled pending eventual retirement").

**Failure scenario:** an agent keeps or rebuilds a Sine input path to satisfy the guardrail.
`Persisted_Input_Compatibility.md:177-178` explicitly blocks re-registering Sine.

### 2.5 Bubble vs Extruded Bubble prefix overlap (medium)

`extruded_bubble_` contains `bubble_`. In `core/settings/default_settings.py`, 173 lines contain `bubble_`, but only
77 are Bubble's own `'bubble_…` keys. The same holds for `spectrum_` and `extruded_spectrum_`.

Code is safe because it uses `startswith` (`visualizer_retired_modes.py:91`, registry prefixes). Text tools are not.
Docs add more names: "EB" (94 files/504 lines), "original Bubble" (20 files) and "2D Bubble"/"Bubble_2D" (23 files).

**Failure scenario:** an agent asked to retune Bubble runs a `bubble_` search-and-replace or reads the hits and
edits Extruded Bubble keys. Memory `srpss-extruded-bubble-own-mode.md` exists because of this. The safe pattern is
`\bbubble_`, because the word boundary excludes `extruded_bubble_`.

### 2.6 "Glass" and "Acrylic" across two material systems (medium)

See §1.4. **Failure scenario:** "Glass cards look flat" leads an agent to `core/windows/dwm_blur.py`/AccentPolicy
(the Settings window backdrop) or to `.srtheme` `backdrop.mode`, instead of `surface_material.py` and
`MaterialSurface.qml`. That is the R-61 coupling the card design forbids.

### 2.7 Games You Follow: five spellings (medium)

`steam_progress` (154 lines/39 files, persisted), `games_you_follow`/`GamesYouFollow` (QML and module),
`steam_followed` (runtime and layout) and `games_followed` (child roles).

**Failure scenario:** an agent greps `games_you_follow` and edits the QML and module. It misses
`widgets/steam_followed_runtime.py` and `rendering/games_followed_child_roles.py`, and the settings under
`widgets.steam_progress`.

### 2.8 "Spotify Visualizer" label and `spotify_visualizer` (low-medium, user-visible)

The product calls it Visualizers or Beat Visualizer. Guided Setup Arrange, display-route text and the stack
predictor show "Spotify Visualizer" (§1.3). The id is in 668 files and is persisted as the section.

**Failure scenario:** new UI or docs copy "Spotify Visualizer", or an agent assumes the widget is Spotify-only and
gates it on the Spotify provider.

### 2.9 Waveform Ribbon: "Waveform" and "waveform" (low-medium)

- Studio and docs say "Waveform". Settings says "Waveform Ribbon".
- "waveform" also means PCM (Oscilloscope; "waveform/transient" in `Docs/TestSuite.md:658`).
- `tools/visualizer_replay/waveform_music_response.py` is **Waveform-mode-specific**: it reads the ribbon model's
  `bend`/`height` and Reaction Modes (:83-94). Memory `srpss-music-response-traces.md` describes it as the tool for
  "any Visualizer mode". Neon Lake has its own `neon_lake_music_response.py`.
- The framed-camera SPEC for Waveform lives in `core/waveform_ribbon_scene.py:10`. Its siblings live in
  `core/settings/<mode>_camera.py`, and `core/settings/waveform_ribbon_camera.py` exists but holds only the floor.

**Failure scenario:** an agent edits `core/settings/waveform_ribbon_camera.py` to change Waveform's camera bounds.
The bounds live in `core/waveform_ribbon_scene.py`.

### 2.10 Transition internals (low)

- **Ripple** is `raindrops` in its program, GL key and class string.
- **3D Block Spins** has four spellings: `block_spins` (id), `blockspin` (section, program, settings attributes),
  `BlockSpin` and `GLCompositorBlockSpinTransition`. It also declares `gl_program_key=WARP`, which is Warp
  Dissolve's key.
- **Warp Dissolve** lives in `warp.py`.
- The GL-compositor-era metadata has no production caller (§1.2).

**Failure scenario:** an agent searches for a `GLCompositorRainDropsTransition` class to fix Ripple, or "fixes" the
WARP key as if Block Spins shared Warp's program. Low risk, because the ids are near-substrings of the labels and
`ui/settings_tabs.py:85` and `core/settings/ui_bucket_state.py:269` already warn about the label/section split.

### 2.11 Smaller items

- **Oscilloscope has two prefixes**, `osc_` and `oscilloscope_` (`visualizer_mode_registry.py:230`). This is
  documented and enforced, so it is low risk.
- **Tests pin UI wording.** `tests/test_visualizer_settings_plumbing.py:931` ("Spline Curve"),
  `tests/test_visualizer_mode_activation_schema_current.py:61` ("Voxel Sphere") and
  `tests/test_onboarding_selection.py:129` pin display names. Memory `srpss-tests-no-user-editable-values.md` says
  not to. They will fire on any naming fix.
- **A test uses a mode id that does not exist.** `tests/test_visualizer_plain_orbit.py:169` passes
  `mode_id='neon_lake'`. It is harmless, since any change of mode works for that test, but it shows the product
  name leaking into id positions.
- **`widgets/spotify_visualizer/shaders/devcurve.frag`** still lives under `widgets/`, while newer modes keep their
  GLSL in `rendering/gl_programs/`. This is a location inconsistency, not a naming one.
- **`README.md:43-51`** lists "Spline Curve (Dev Curve)" and "Shockwave Grid (3D)", and omits Extruded Bubble and
  Waveform Ribbon.

## 3. Good patterns already present

- `Docs/Reference/Visualizer_Reference.md:392-398` is a product-first table with the id in parentheses: "Spline
  Curve (DevCurve)".
- `Docs/Reference/Neon_Lake_Basin.md:13` states the id and key prefix up front.
- `Docs/TestSuite.md:857` says "Neon Lake Basin (`shockwave_grid`)".
- The Studio adapter docstrings (`ui/studio/shockwave_grid_adapter.py:1`,
  `ui/studio/shockwave_grid_recorded_inputs.py:3`) say "Neon Lake (mode id `shockwave_grid`)".
- `tools/artifact_paths.py:116-120` derives the evidence vocabulary from the registry, so it cannot drift.

## 4. Recommendations (cheapest effective first)

| # | Action | Label | Reason |
|---|---|---|---|
| 1 | **A generated, test-guarded naming reference.** Add `Docs/Reference/Naming.md`, generated by a small tool (e.g. `tools/naming_reference.py --write`). It reads `_ALL_DESCRIPTORS` (id, `display_name`, `setting_prefixes`, runtime/renderer/builder modules), `ui/studio/registry.py` (title, adapter), `RETIRED_VISUALIZER_MODE_IDS`, the transition registry (label, stable id, section, legacy names), `widget_family_catalog` (id, member label) and `SURFACE_MATERIAL_LABELS`. Hand-written columns, each verified by the tool: "other spellings in code" (e.g. `neon_*`, `shockwave_frame_runtime.py`, `blockspin`, `raindrops`, `steam_followed`/`games_followed`) and "grep hazards" (`\bbubble_`, "neon" preset/theme names, "spline" ribbon maths, "shockwave" onset concept, "Glass" ×6). A test fails when the file differs from a fresh generation, following the `tests/test_artifact_paths_contract.py` pattern. Link it from `Index.md`'s read-first list and from `Docs/Guides/Visualizer_Change_Checklist.md`. | **Safe now** | Docs and tools only. One place answers "what is X called in code". Generation keeps it from becoming another stale doc. |
| 2 | **Add Index.md routing rows** for Spline Curve (`devcurve`) and Oscilloscope. Change `Index.md:22` and `:153` from "Shockwave" to "Neon Lake (`shockwave_grid`)". | **Safe now** | An agent reads Index first, and Spline Curve has no entry today. |
| 3 | **Normalise the governing docs to product-first names, with the id in backticks on first use per section**: "Neon Lake Basin (`shockwave_grid`)", "Spline Curve (`devcurve`)". Scope: `Spec.md` (fix :775, which also carries the Sine claim), `Docs/Guardrails/*` (Visualizer_Presentation.md :18/:59/:76/:284/:350/:463; Performance_Optimization_Contract.md:50), `Docs/TestSuite.md` (:658/:678/:699/:751), `Current_Plan.md` (DevCurve items) and `README.md:43-51` (product list). Leave `Docs/Historical_Bugs/*` and dated `Docs/Audits/*` wording alone: they are records. The naming reference covers them. | **Safe now** | Text only. Removes the "two modes" misreading and the live-Sine claims. |
| 4 | **Remove retired Sine from the governing docs** (same files as #3). | **Safe now** | `Persisted_Input_Compatibility.md:164-178` already retired it. The docs contradict that. |
| 5 | **One user-facing name source.** Make the Studio take its title from `descriptor.display_name`: drop the `title` argument of `register_studio_adapter` and derive the schema and window titles as `f"{display_name} Studio"`. First the operator chooses the product names for the four disagreeing modes, especially **Neon Lake vs Neon Lake Basin**. Rewrite the three tests that pin display names (§2.11) to compare against the registry. | **Safe now** for the mechanism (titles and `display_name` are not persisted). **The operator's call** for the names. | Ends the user-visible "DevCurve Studio" and stops future drift. |
| 6 | **Change the "Spotify Visualizer" member label** (`widget_family_catalog.py:174`) to the product's name (operator's choice: "Visualizer" or "Beat Visualizer"). Same for the Spline Curve Ghost tooltip "for debug visibility". | **Safe now** (labels only) | User-visible stale wording. |
| 7 | **Header lines in owner modules and docs** for split vocabularies: one docstring sentence in `shockwave_frame_runtime.py`, `neon_lake_basin_program.py`, `core/settings/neon_lake_camera.py`, `devcurve_*` modules, `games_you_follow.py`/`steam_followed_runtime.py`/`games_followed_child_roles.py` and `waveform_ribbon_camera.py`: "Neon Lake Basin, mode id `shockwave_grid`; sibling owners: …". Also rename the spec header "Shockwave Grid" (`visualizer_mode_settings.py:836`) to "Neon Lake Basin (`shockwave_grid`)". | **Safe now** | Comment/docstring only. Whichever name an agent greps, it lands on a pointer to the rest. |
| 8 | **Targeted renames of non-persisted files that contradict their own class or id**: `widgets/spotify_visualizer/shockwave_frame_runtime.py` → `shockwave_grid_frame_runtime.py` (update the registry string at :375); `ui/studio/waveform_adapter.py` → `waveform_ribbon_adapter.py`. | **Safe now**, low value. Do it only alongside other work on those files. | The module path is a lazy import string in the registry, not persisted. |
| 9 | **Bulk renames of internals to product names** (`devcurve_*` modules/classes/tests → `spline_curve_*`; `shockwave_grid*` modules → `neon_lake*`; `test_neon_*`/`test_devcurve_*` renames). | **Don't do** | The persisted keys (`devcurve_*`, `shockwave_grid_*`), preset folders, goldens and fixtures stay id-named. Renaming code to product names reproduces exactly the split Neon Lake suffers today: its `neon_*` modules are the leftovers of the 13 Oct partial rename. For the code, the id is the one name that can be consistent everywhere. Product names belong in user strings and docs, joined by #1. |
| 10 | **Rename persisted mode ids** (`shockwave_grid` → `neon_lake`, `devcurve` → `spline_curve`). | **Don't do** (if ever: **needs a compatibility bridge**) | Each id keys the mode value, `mode_activation`, `preset_<id>`, 70-145 leaves, bucket-state members, Custom cache, shipped and user preset folders and JSON `mode` fields, SST, 13 devcurve goldens, frozen fixtures, onboarding art and release WebP names. A rename would need a new *rename* seam beside `strip_retired_visualizer_settings`: map rather than strip, with old-input fixture and idempotence; plus an on-disk move of the user's `visualizer_modes/<id>/` folder (a filesystem bridge like `core/feeds/mc_snapshot_bridge.py`); plus the installer's preset tree. `Persisted_Input_Compatibility.md:88-98` calls this the "widest cascade in the repo" over irreplaceable user data. Expected benefit is small once #1-#7 exist. |
| 11 | **Rename persisted widget ids** (`spotify_visualizer`, `steam_progress`, `spotify_volume`). | **Don't do** | Section keys in every profile, layout, SST and layout slot. The label already carries the product name. |
| 12 | **Rename transition labels** (e.g. "Melt Drip" → "Melt"). | **Needs a compatibility bridge**, which already exists | Labels are persisted (`transitions.type`, activation/pool/durations). Add the old label to `legacy_names` (`transition_registry.py:43`, `:262`). Section ids stay. |
| 13 | **Delete the caller-dead GL-compositor transition metadata** (`gl_program_key`, `program_attr`, `uniforms_attr`, `compositor_transition_class`, `get_transition_program_specs`/`_map`, the `GLCompositor*` identity strings and their test uses). | **Safe now** as ordinary caller-dead removal, with its test cascade in the same commit. Not a naming change as such. | Removes the bogus `WARP` key on Block Spins and the `raindrops`/`GLCompositor*` aliases agents chase. Keep the `_RUNTIME_LABEL_TO_STABLE_ID` entries only if a production producer exists. None was found (only the registry and tests mention them). |
| 14 | **Memory hygiene** (the lead's call): use "Spline Curve (`devcurve`)" in `srpss-continuous-play-reactivity.md`/`srpss-real-music-scales.md`, and correct `srpss-music-response-traces.md`: the tool is Waveform-specific, and Neon Lake has `neon_lake_music_response.py`. | **Safe now** | Memory files are read before docs. |
| 15 | Fix `tests/test_visualizer_plain_orbit.py:169` to use a registered id, or a clearly fake one such as `"other_mode"`. | **Safe now** | Cosmetic. Stops `neon_lake` from looking like an id. |

## 5. Evidence layout (`tools/artifact_paths.py`): `visualizers/<name>`

**Recommendation: keep the mode id as the directory name (`visualizers/shockwave_grid`), and accept product-name
slugs as input aliases.**

**Why the id:**

1. **It is the only stable name.** Neon Lake has already been renamed once ("Shockwave Grid" → "Neon Lake Basin"),
   and Settings and the Studio still disagree ("Neon Lake Basin" vs "Neon Lake"). A product-slug directory would
   split the evidence history at each rename. The id has not changed since 3 Oct.
2. **It joins everything else.** The id is the name used by:
   - `presets/visualizer_modes/<id>/` and the user preset folder;
   - `widgets.spotify_visualizer.<id>_*` keys;
   - `tools/visualizer_live_check.py --mode` (:4) and `tools/release_media.py` cases (:148);
   - goldens, fixtures and onboarding art.
3. **The validation is already derived.** The vocabulary is derived from `VISUALIZER_MODE_IDS` +
   `RETIRED_VISUALIZER_MODE_IDS` (`artifact_paths.py:116-120`, checked at :147). Product slugs would need either a
   hand list for retired modes, which have no `display_name` in the registry, or the retired ids anyway.
4. **The migration already uses ids.** `tools/artifact_migration.py:41` and `:49` move the pre-layout
   `.artifacts/evidence/devcurve` and `.artifacts/evidence/neon_lake` into `visualizers/devcurve` and
   `visualizers/shockwave_grid`. Both old folders still exist in the main checkout today.

**What to add (safe now, small):**

- **Aliases:** `_visualizer_modes()` also accepts `slug(display_name)` and `slug(studio title)` and resolves them to
  the id. For example, `visualizers/neon_lake_basin` and `visualizers/neon_lake` both resolve to
  `visualizers/shockwave_grid`, and `visualizers/spline_curve` resolves to `visualizers/devcurve`. An agent or the
  operator using the product name still lands in the right folder.
- **Product names next to the ids:** the module docstring (:10-11) and the `artifact_paths` CLI listing print the
  product name beside each id, e.g. `shockwave_grid  (Neon Lake Basin)`. That listing is the decoder the operator
  needs when browsing `.artifacts` in Explorer. Harness docs should write
  "`.artifacts/evidence/visualizers/shockwave_grid/` (Neon Lake Basin)", as `Docs/Reference/Harness_Index.md:68`
  nearly does.

**Rejected alternative:** directories named by `slug(display_name)`, e.g. `neon_lake_basin`, `spline_curve`. This
reads better in Explorer but brings back drift on every product rename. It also cannot cover retired modes without
a hand list, and it would create a third folder-naming scheme beside presets and keys.
