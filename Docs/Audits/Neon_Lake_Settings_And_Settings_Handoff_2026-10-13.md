# Neon Lake settings and Settings-handoff audit — 2026-10-13

Scope: the supplied `logs6a63dcda0b3.zip`, the latest `6a63dcda0b` Neon Lake Celestial/Terrain Godzip, and the follow-up code in this archive. This is an architectural/source audit; Qt/Windows Settings re-entry has **not** been validated by the operator after this change. Preset 1 is the sole protected salvage reference. Skyline work remains provisional and unchanged.

## 1. Failure timeline and remediation

At 23:05:05 the Settings request was queued/admitted; at 23:05:06 Quick runtime stop/retirement completed its scheduling. The destruction barrier armed with 717 QObjects and three Python owners (`QuickDisplayUnit`, `QuickDisplayPresenter`, `QuickDisplayVisualizerOwner`). All tracked QObjects, resources and thread work eventually cleared, as did `QuickDisplayPresenter`, but the barrier timed out at 23:05:14 holding `QuickDisplayUnit` and `QuickDisplayVisualizerOwner`. The process exited with code 1. There was **no evidence** of a Settings-tab Python exception, GL shader compile failure or QML error at that moment.

Concrete cause addressed: `DisplayManager._connect_quick_runtime` previously installed many Qt signal lambdas with default arguments such as `display=unit`. The Qt signal kept a strong reference to a Python display unit past runtime retirement, while the unit's retirement barrier was explicitly watching that object's collection. Those callbacks now dereference the unit weakly at invocation time, reject retired/collected units and preserve live dispatch semantics. They create no new timers, resources, polling, or alternate Settings authorities. A standalone test compiles/executes the actual `_connect_quick_runtime` method and verifies that a connected signal still dispatches while alive, and that its connection cannot keep the unit alive after it is otherwise released.

**Not yet proven:** the second orphan owner (`QuickDisplayVisualizerOwner`) may have another retention path. The changed display-signal routes are a real cyclic-retention hazard, but without live Windows diagnostics or another observed Settings transition after this change, a complete fix cannot be certified. The fail-closed barrier remains unchanged and must never be bypassed or relaxed. If another timeout occurs, use the existing diagnostic-product Python-owner referrer logger (`[LIFECYCLE_BARRIER][PYTHON_OWNER_REFS]`), which is only run after the barrier has already failed; keep its bounded cost out of the healthy runtime.

## 2. Settings ownership review

| Path | Finding | Disposition |
| --- | --- | --- |
| `core/settings/visualizer_mode_settings.py` | Typed spec owns labels, ranges, conditional controls, grouping and the two Custom editors. | Keep; no second Neon Lake control table introduced. |
| `core/settings/default_settings.py` | Canonical default values remain distinct from user-authored curated presets. | Keep; do not freeze artistic preset numbers. |
| `ui/tabs/media/shockwave_grid_settings_binding.py` | `load` uses blocked signals for the shape/smoothing controls; terrain load silently updates canvas/history. `collect` obtains data from the one editor. | Keep. |
| `ui/tabs/media/shockwave_grid_builder.py` | One `TerrainEditor` attached to the spec-owned Custom entry; completed strokes switch to Custom and save. | Keep; no duplicate terrain persistence path. |
| `rendering/gl_programs/heightfield.py` | Authored `heights=0` defines real water. | Keep; do not blur into a cosmetic water threshold. |
| View fields (tilt, turn, scale, pan) | Five hidden presentation keys are independent of artistic presets and card geometry; camera admission is mode-owned. | Keep, no extra Settings sliders or alternate pose authority. |
| `TerrainCanvas` | Editing is stroke-batched; `set_heightfield` and Cancel do not save; no running timer. | Keep. Dark-glass palette now matches the other shape editors; data and brush semantics unchanged. |

No active **second settings-value authority** was proven in the audited Neon Lake path. The real duplication/complexity is primarily user-facing coupling and controls that do more/less than their label suggests, not a demonstrated second live defaults writer. Do not delete or merge any control without operator authorization and saved-preset compatibility treatment.

## 3. Complexity and behavior inventory (operator approval required for changes)

| Existing controls | Assessment | Recommendation, **NOT implemented** |
| --- | --- | --- |
| `Surface Style` (`Edges`, `Both`, `Glass + Edges`, `Glass + Both`, and other choices) | Seven render combinations, including generalized interior wires. The operator dislikes internal edges but values the lake perimeter and intended skyline. `Terrain Lines` colour participates in wire and shoreline presentation. | Prefer `Vertices`, `Glass`, `Glass + Vertices` as primary modes; decouple shoreline/skyline contours before retiring internal wires and edge combinations. Do **not** remove yet. |
| `Wire Density` | Changes curve grid and vertex lattice density, even for styles with no visible wires. Misleading label and potentially nontrivial cost. | Consider `Surface Detail / Point Density` or a quality-managed derivation. Seek approval for any label/authority change. |
| `Terrain Growth`, `Growth Rise`, `Growth Settle` | Actual independent eight-lane musical growth exists. Land height multiplier in shader is `1 + 0.25 * TerrainGrowth * envelope`, giving at most ~25% added height; the operator's observation of mostly swelling is consistent. Distinct from brightness-driven Ridge Glow. | Consider keeping a compact single Terrain Motion control with authored response timings hidden in Advanced, or replace with a stronger *art-directed* movement. Do not retune, consolidate or delete without visual approval. |
| `Ridge Glow Response` and `Wave / Ridge Glow` | Frequency-linked land illumination, **not** a true skyline outline. The current skyline rim is still a shader approximation. The same crest colour serves waves and ridge light. | The missing feature is a genuinely readable screen-space terrain/sky silhouette, not another glow slider. Remains provisional. |
| `Water Detail`, `Wave Height`, `Wave Speed`, `Water Flow`, `Idle Swell`, `Water Reflection` | Distinct sampling/scroll/displacement/reflection paths but many overlapping-looking surface behaviors. | Expose a lean primary Waves group and move extras into Advanced after operator trial. No changes yet. |
| `Surface Fill` and `Terrain Fill` / `Water Colour` | Single fill-alpha control modulates land and water together despite separate RGBA colours, making some color/opacity combinations confusing. | Candidate for clearer descriptions or separation, only with approval. |
| `Glass Tint`, `Glass Strength`, `Glass Roughness`, vertex/accent/outline colours | Some are conditional on Surface Style. Their shader consumers are real, including Glass + Vertices. | Preserve core glass and vertex editing; simplify only after operator chooses retained styles. |
| `Glow` | Post effect depends on 3D Detail tier; in Performance/KAK it may look inert even though the slider saves correctly. | Clarify or disable unavailable effect in UI when a tier does not admit post effects, subject to operator approval. |
| Frequency Response editor, notches, lane strength, mirroring, smoothing, hysteresis, profile floor, falloff | Separate shaping stages; tests/presets depend on them. Complex but they are not all duplicate controls. | Preserve DSP boundaries. Consider collapsing Advanced subgroup by default, not deleting distinct filters. |
| Sky / Stars / Clouds / Horizon and Celestial X/Y/Z, phase, orbit, rays | Each has separate renderer contribution and conditionally visible settings. UI density is high. | Keep until live inspection; collapsing/relocating is preferable to deleting authored settings. |

## 4. Possible missing capabilities (explicit operator approval needed)

- A true mountain-vs-sky silhouette line, orbit-aware and distinct from the current grazing-angle ridge glow. Already requested, still provisional, no change in this package.
- A source/render behavior that makes Terrain Growth distinctly reactive rather than barely swelling, if the operator chooses to retain terrain motion. No added control or changed DSP in this package.
- A clearer breakdown of Glass+Vertices opacity/glow to avoid washing out the moonlit lake. This may be artistic preset behavior rather than missing settings; validate with operator before implementing.

## 5. Evidence and next check

`tests/test_neon_settings_lifecycle_and_editor.py` is a standalone signal-owner regression, using neither user settings nor process environment-variable changes. `tests/test_neon_lake_landscape_extension.py` continues to cover deterministic geometry. Both run with `--noconftest` and the operator's direct project venv Python binary. The normal `tests/conftest.py` still mutates environment variables; it is an existing project-wide policy violation and not part of this permitted narrow slice.

Do not mark the Settings bug closed until a full screensaver-to-Settings handoff returns cleanly in a real Windows Quick run. If another critical barrier timeout occurs, request the diagnostic-product referrer snapshots instead of bypassing barrier enforcement. Do not mark V4A complete on this evidence.

## Later operator evidence: actual Settings bucket error (2026-10-13)

The earlier display-retention barrier bug is distinct from a newly observed Settings build-time error. A runtime traceback explicitly names `KeyError: 'shockwave_grid:terrain_motion'` from `get_visualizer_bucket_state`; that bucket was added to the typed spec without updating the canonical `ui.visualizer_bucket_states` map. Corrected the canonical map, leaving strict failure for truly undeclared buckets. A new static parity regression guards every Neon spec bucket. No fallback getter is introduced. Operator Windows Settings acceptance is still outstanding.
