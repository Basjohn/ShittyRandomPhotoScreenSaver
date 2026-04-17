# Current Plan

Update this after every significant change.

## Guardrails

- Keep this aligned with [Index.md](F:\Programming\Apps\ShittyRandomPhotoScreenSaver\Index.md), [Spec.md](F:\Programming\Apps\ShittyRandomPhotoScreenSaver\Spec.md), [Docs/Defaults_Guide.md](F:\Programming\Apps\ShittyRandomPhotoScreenSaver\Docs\Defaults_Guide.md), [Docs/Visualizer_Debug.md](F:\Programming\Apps\ShittyRandomPhotoScreenSaver\Docs\Visualizer_Debug.md), and [Docs/Historical_Bugs.md](F:\Programming\Apps\ShittyRandomPhotoScreenSaver\Docs\Historical_Bugs.md).
- Do not mark runtime or visual-feel issues as fixed without user confirmation.
- Treat `presets/visualizer_modes` as the only authored visualizer preset source tree.
- Treat `release/main_mc.dist/presets/visualizer_modes*` as generated artifacts only.
- Do not treat passing tests as visual sign-off.
- Do not make global/shared math changes unless explicitly requested.
- Do not reduce FPS caps below current configured values.
- Do not revive retired visualizer sidecar toggles such as `_use_raw_energy`.
- Do not solve Bubble/Blob by merely swapping one failure family for the opposite one.
- Do not split Bubble directional boot fixes by axis family. Horizontal and vertical directional streams must rise or fall together; if the startup treatment is wrong for one, neither keeps the special case.
- Failures at fixing are to be kept summarised in an issue until the user states the issue is solved.
- Keep checkboxes honest:
  - `[x]` landed and validated by user if visual
  - `[~]` landed or partially proven, still needs runtime eyes
  - `[ ]` not done

---

## Recently Closed

### Visualizer Custom Settings Lost on Save / Navigation / Runtime Round-Trip

Closed from the live plan on 2026-04-16 after user-reported runtime confirmation that the issue now appears solved.

Historical detail remains in [Docs/Historical_Bugs.md](F:\Programming\Apps\ShittyRandomPhotoScreenSaver\Docs\Historical_Bugs.md) under:
- `2026-04-11 — Visualizer Preset Override Bug (MERGE Semantics + Cross-Mode Pollution + Call-Site MERGE)`
- `2026-04-13 — Visualizer Sine/Oscilloscope Lines 4-6 Settings Never Persisted (Resolved)`

Reason for pruning here: the active root-cause work is done, the sneaky multi-layer persistence/runtime bridge failure is now documented historically, and this live plan should stay focused on open validation and remaining Blob/Bubble work.

---

## Awaiting Validation

### 3. Visualizer Mode Isolation / Bleed Audit

**Status:** `[~]` Mostly landed, final runtime confirmation still open
**Priority:** High

**Landed:**
- [x] Dedicated Blob/Bubble/Spectrum/Oscilloscope/Sine renderer ownership audited
- [x] Dedicated visualizer math/helper ownership audited
- [x] Static isolation fences added for dedicated mode-owned modules
- [x] Shared visualizer change checklist established in [Docs/Visualizer_Change_Checklist.md](F:\Programming\Apps\ShittyRandomPhotoScreenSaver\Docs\Visualizer_Change_Checklist.md)
- [x] Preset/save/repair/regeneration paths aligned with current mode ownership
- [x] Shared beat-engine bar-count hitch fix moved onto one startup/runtime-parity rebuild path
- [x] Shared technical cache replay now no-ops when a mode entry is missing instead of silently borrowing foreign technical state
- [x] GPU extra kwargs now stay mode-local rather than carrying unrelated payload clutter

**Still open:**
- [~] Shared seams in `config_applier`, `spotify_visualizer_widget`, and `spotify_bars_gl_overlay` are much cleaner but remain the highest-risk bleed area
- [ ] Finish a live runtime spot-check across shaper-capable modes once Bubble/Blob validation is calmer

**Lesson:** The remaining bleed risk lives in the shared transport/reset/apply seams, not in the dedicated renderer files.

### 4. Shared Preset Install / Save Location Across SCR and MC

**Status:** `[~]` Landed in code, awaiting live coexistence validation
**Priority:** Medium

- [x] Frozen SCR and MC resolve active curated presets through the shared ProgramData tree
- [x] Packaged assets remain the replacement/bootstrap source rather than the active runtime root
- [x] Normal SCR uninstall no longer deletes the shared curated tree out from under MC
- [x] Focused tests for frozen shared-root resolution and replacement routing landed
- [ ] Validate install, upgrade, and coexistence behavior with both builds present on one machine

---

## Planned

### 5. Goo Mode — New Reactive Liquid Visualizer (Dev-Gated)

**Status:** `[ ]` Architecture decided, implementation not started
**Priority:** High
**Detailed plan:** [Docs/Blob_Redesign_Plan.md → Goo Mode Plan](F:\Programming\Apps\ShittyRandomPhotoScreenSaver\Docs\Blob_Redesign_Plan.md)

**Decision (2026-04-17):** The mockup target is so architecturally different from Blob that retrofitting it into `blob.frag` would poison both paths. Instead, introduce **Goo** as a brand-new visualizer mode with its own shader, solver, renderer, settings, UI, and presets. Both Goo and current Blob are dev-gated during development so the application builds and ships safely.

**Visual target (authoritative mockup):**
- **Inverted spatial model**: liquid pools advance inward from all card edges surrounding a reactive dark void in the center
- **Flat vector fill** — one flat color, no volumetric/orb shading
- **Clean white contour lines** on every liquid edge (outer, inner, merged bridges)
- **Sparse white specular puddles/ribbons** — small, curvature-derived, inside liquid only
- **Soft offset shadow/accent** beneath liquid edges — drop shadow, not glow
- **Audio-reactive**: bass = broad deep pushes, mids = tendrils, highs = small drips, void breathes with overall energy

**Why a new mode instead of a Blob retrofit:**
- Blob's rendering model (centered radial SDF + additive perturbations) is structurally incompatible with the target
- Blob Shaper (shaped Blob) is architecturally healthy and must not be disrupted
- Sharing `blob.frag` would require massive unshaped-vs-shaped conditionals that create the exact hidden-branch problem we diagnosed
- A new mode gets clean ownership from day one: own shader, own solver, own settings namespace
- No risk of breaking existing Blob presets, settings, or regressions during development
- When Goo is validated, Blob can be retired or kept as a separate simpler mode

**Guardrails:**
- Do NOT add 3D volumetric shading — the target is flat vector illustration
- Do NOT let speculars become a whole-body gradient — sparse discrete puddles only
- Do NOT let shadow become a glow — crisp offset accent only
- Do NOT let the void collapse to zero — always visible dark center
- Do NOT declare success from tests alone — visual/runtime sign-off required
- Do NOT touch Blob code except for the dev-gate addition

**Success criteria:**
- [ ] Goo renders as edge-sourced pooled liquid, NOT a centered blob
- [ ] Central void is visible and reactive, never collapses has adjustable opacity.
- [ ] White vector outlines on all liquid edges
- [ ] Flat vector fill
- [ ] Sparse rounded but opaque white specular puddles inside liquid that adjust for changes in shape.
- [ ] Sharp (but not aliased!) offset shadow behind liquid edges
- [ ] Audio-reactive tendril dynamics, never pinches center "><"
- [ ] No fallback to spectrum — goo.frag compiles and runs
- [ ] Settings/presets survive round-trip
- [ ] Visual sign-off from user against the mockup, remember of example \images\GooGoalMock.png
- [ ] Substantial Tuning GUI but sorted into buckets. All colours adjustable by swatches like other modes.
- [ ] Dev gate can be flipped to expose Goo in production builds

#### 5A. Dev-Gate Architecture

**Status:** `[x]` Implemented

**Intent:** Both Goo (new) and Blob (legacy) are dev-gated so the application builds and ships safely while Goo is developed and Blob is stabilized.

**Gate mechanism (implemented):**
- [x] `core/dev_gates.py` — reads `-devblob` / `-devgoo` from `sys.argv`; exposes `is_blob_enabled()`, `is_goo_enabled()`, `force_gate()` for tests
- [x] `core/settings/visualizer_mode_registry.py` — `_GATED_MODES` maps mode_id → gate function; `_active_descriptors()` filters; `is_mode_active()` for runtime checks
- [x] Gated modes excluded from UI combo, preset sliders, rainbow state, shader compilation
- [x] Settings/model fields always exist in code (no conditional imports) — only UI visibility and runtime mode selection are gated
- [x] When a gate is off, stored mode in settings JSON silently falls back to the default active mode
- [x] `main.py` — `-devblob` / `-devgoo` in the filtered-args set so they don't interfere with screensaver mode parsing
- [x] `widgets/spotify_visualizer/shaders/__init__.py` — `_active_shader_files()` skips gated modes' shaders
- [x] `widgets/spotify_bars_gl_overlay.py` — `set_state()` validates mode via `is_mode_active()`, falls back to default
- [x] Tests call `force_gate(blob=True)` / `force_gate(goo=True)` to enable gates without CLI flags
- [x] Documented in `Spec.md` § Visualizer Mode Dev Gates and `Index.md` § Dev Gates

**Dev workflow:**
- Normal build/ship: Neither Blob nor Goo visible, no risk
- Development: `python main.py --debug -devblob` or `python main.py --debug -devblob -devgoo`
- Tests: Goo/Blob tests use `force_gate()` internally, always run in CI

#### 5B. New Mode Registration & Skeleton

**Intent:** Register Goo as a first-class visualizer mode with clean ownership from day one.

**New files to create:**
- [ ] `widgets/spotify_visualizer/shaders/goo.frag` — fragment shader for Goo
- [ ] `widgets/spotify_visualizer/renderers/goo.py` — uniform upload / renderer
- [ ] `widgets/spotify_visualizer/goo_liquid_field.py` — CPU-side liquid field solver
- [ ] `ui/tabs/media/goo_builder.py` — builder UI for Goo settings
- [ ] `ui/tabs/media/goo_settings_binding.py` — settings collection/load for Goo
- [ ] `presets/visualizer_modes/goo/` — curated Goo presets directory

**Registration checklist:**
- [x] Add `"goo"` to the visualizer mode registry (gated behind `-devgoo`)
- [x] Register `goo.frag` in the shader registry (gated, file not yet created)
- [ ] Register `goo.py` renderer in the renderer dispatch
- [ ] Add Goo to `config_applier.py` mode dispatch (new `_apply_goo_config` or equivalent)
- [ ] Add Goo kwargs builder to `spotify_widget_creators.py`
- [ ] Add Goo state fields to `spotify_bars_gl_overlay.py::set_state()`
- [ ] Add Goo builder to the builder tab dispatch (gated)
- [ ] Add Goo to mode combo in UI (gated)
- [x] Update `Index.md` with dev gates module entry
- [x] Update `Spec.md` with dev gate documentation

**Settings namespace:**
- All Goo settings use `goo_*` prefix — completely separate from `blob_*`
- Shared infrastructure (energy bands, time, resolution, DPR, fade, playing, rainbow) reused from existing uniform contract
- No key collisions with Blob

#### 5C. Phase 1 — Liquid Field Composition Engine

**Intent:** The core rendering model. A 2D scalar field composed of edge-sourced metaballs that merge via smooth-union.

**1A. Field Model Design (before code):**
- [ ] Define field equation — polynomial falloff preferred (cheaper, no singularities)
- [ ] Source budget: ~32 sources (8 per edge), uploaded as `vec4` uniform arrays
- [ ] Threshold: liquid exists where `F(x,y) > threshold`; below = void
- [ ] Audio→source mapping: ~40% bass, ~30% mid, ~20% high, ~10% overall
- [ ] Document in `Docs/Goo_Liquid_Field_Spec.md`

**1B. CPU Solver (`goo_liquid_field.py`):**
- [ ] `GooFieldState` dataclass: per-source position, depth, radius, velocity, band assignment
- [ ] `solve_goo_field_step(dt, energy_bands, playing, seed)`:
  - Base drift — sources move along edges during silence
  - Audio advance — energy pushes sources inward
  - Retreat — energy drop pulls sources back
  - Void breathing — overall energy shrinks void
  - Containment — sources cannot cross center
- [ ] Spring-damper motion per source with neighbor smoothing
- [ ] Tests: silent=near edges, bass=deeper, void preserved, smooth motion, continuous profile

**1C. Upload Pipeline:**
- [ ] Uniforms: `vec4 u_goo_sources[32]`, `float u_goo_threshold`, `float u_goo_void_size`
- [ ] Add to `goo.py::get_uniform_names()` and `upload_uniforms()`
- [ ] Wire through config_applier → overlay → renderer
- [ ] Transport regression: uniforms reach shader without fallback

**1D. Shader (`goo.frag`):**
- [ ] `float evaluate_goo_field(vec2 uv)` — sum source contributions
- [ ] `float goo_sdf(vec2 uv)` — `threshold - field` (negative = inside liquid)
- [ ] Basic rendering: inside liquid = flat color, outside = discard
- [ ] Runtime test: goo.frag compiles, mode renders, no fallback

#### 5D. Phase 2 — Vector Styling System

**Intent:** Layer the mockup's vector illustration style onto the rendered liquid field.

**2A. Flat Fill:**
- [ ] Inside liquid → `u_goo_color.rgb` flat, NO depth shading
- [ ] Anti-aliased edge: `smoothstep(-px, 0, goo_sdf)` only

**2B. White Contour Outline:**
- [ ] `outline = exp(-pow(goo_sdf / outline_width, 2.0))` — white, constant width
- [ ] Both outer and inner edges automatically

**2C. Offset Shadow:**
- [ ] Sample `goo_sdf(uv + offset)` — darker color behind liquid
- [ ] Composite: shadow → fill → outline → specular

**2D. Specular Puddles:**
- [ ] Curvature-based: `laplacian(field)` via central differences
- [ ] Noise breakup for sparsity
- [ ] White, small, inside liquid only, drifting

**2E. Inner Edge Parity:**
- [ ] All styling derives from `goo_sdf` — inner void edges get same treatment automatically
- [ ] Verify and test

#### 5E. Phase 3 — Audio Reactivity & Motion

**3A. Void Breathing:** overall energy → void size, spring-damped, never zero
**3B. Tendril Dynamics:** bass=broad, mid=fingers, high=drips, transient=impulse, all spring-damped
**3C. Edge Drift:** slow drift during silence, tangential pressure redistribution, neighbor smoothing
**3D. Pocket Integration:** pocket events → temporary high-energy sources, natural field merge

#### 5F. Phase 4 — Settings, Presets & Transport

**New `goo_*` settings:**
- [ ] `goo_color` — main liquid color
- [ ] `goo_void_floor` — float 0.05-0.40, default 0.15
- [ ] `goo_advance_speed` — float 0.1-3.0, default 1.0
- [ ] `goo_retreat_speed` — float 0.1-3.0, default 1.0
- [ ] `goo_outline_width` — float 0.001-0.010, default 0.004
- [ ] `goo_outline_color` — default white
- [ ] `goo_shadow_strength` — float 0.0-1.0, default 0.3
- [ ] `goo_shadow_color` — default darker variant of goo_color
- [ ] `goo_specular_density` — float 0.0-1.0, default 0.3
- [ ] `goo_source_count` — int 16-64, default 32

**Plumbing (all 8 layers):**
- [ ] `core/settings/defaults.py`
- [ ] `core/settings/models.py`
- [ ] `rendering/spotify_widget_creators.py`
- [ ] `widgets/spotify_visualizer/config_applier.py`
- [ ] `widgets/spotify_bars_gl_overlay.py`
- [ ] `widgets/spotify_visualizer/renderers/goo.py`
- [ ] `goo.frag`
- [ ] Regression: round-trip without loss

**UI:** Goo builder with all controls, gated behind `SRPSS_DEV_GOO`
**Presets:** Author initial curated Goo presets, run repair tool

#### 5G. Shaped Blob Follow-On — Better Reactions (Independent of Goo)

**Status:** `[ ]` Follow-on, independent of Goo development

**Goal:** Give Blob Shaper richer live response while preserving its authored-contour identity.

**Important constraint:** Shaped Blob must become more alive through **contour-space reaction**, not by importing generic unshaped wobble/stretch/pocket behavior wholesale.

**Current shaped-Blob strengths to preserve:**
- authored base contour owns rest shape
- authored reaction contour defines local travel envelope
- routed energy field defines local ownership
- one CPU-solved contour feeds fill/ring/glow/outline consistently

**Main weakness to improve:**
- In practice the shaped path can still feel too uniform or too "one contour simply expands/contracts everywhere", especially compared to how expressive the editor suggests the shape could become.
- Live expectation has now been made explicit by user feedback:
  - shaped Blob should have noticeably better reactions than today
  - those reactions must stay contour-authored and fluid
  - if the present shared runtime blocks that, splitting shaped ownership further is now preferred over keeping shaped response timid

**Shaped reaction ideas worth planning explicitly:**
- [ ] **Node-lane ripple / wobble**
  - When a node's attached energy type becomes active, add a small contour-space ripple centered on that authored ownership region.
  - This should travel along the contour locally, not detach into a second shell.
- [ ] **Directional residual pull**
  - Let active routed regions retain short-lived contour momentum after the immediate hit so the response has follow-through instead of only reach-and-release.
- [ ] **Neighbor spill**
  - A strongly driven node region may lend a smaller delayed influence to adjacent sectors so the contour reads as one living body rather than isolated bins.
- [ ] **Local overshoot with decay**
  - Strong positive drive may briefly overshoot the reaction contour slightly in the owning region, then settle back.
  - This must stay softer and more local than unshaped Blob's freeform deformation.
- [ ] **Edge-travel ripple**
  - Strong hits could launch a short-lived contour ripple that rides along the authored outline from the energized region.
- [ ] **Pressure memory per authored lane**
  - Keep a tiny per-region decay memory so repeated hits on the same routed node feel cumulative rather than identical one-offs.

**Shaped follow-on checklist:**
- [ ] Decide whether shaped Blob can be improved safely inside the current shared runtime, or whether it should get a more explicit shaped-only runtime/helper surface first.
- [ ] If needed, split shaped reaction ownership behind a Blob-internal dev gate before tuning stronger reactions.
- [ ] Decide whether the first new reaction feature lives:
  - inside the contour solver
  - as a post-solve contour-space residual
  - or as a tiny per-region memory field consumed by the solver
- [ ] Prefer contour-space residuals over fragment-space shell tricks.
- [ ] Keep the authored base contour readable even during strong reactions.
- [ ] Keep the reaction contour as the dominant local target; new motion should enrich it, not replace it.
- [ ] Ensure ring mode uses the same enriched contour without repainting the hollow center.
- [ ] Expose only the shaped-specific controls that are truly needed after the first reaction feature lands.
- [ ] Do not add five new shaped controls before proving one reaction family is worth keeping.

**High-detail shaped reaction program:**
- [ ] Phase 1: establish stronger local ownership without adding new public controls:
  - region-local reaction gain
  - residual follow-through per authored lane
  - gentle neighbor spill
  - contour-safe damping so the shape does not become sector-blocky
- [ ] Phase 2: add visible fluid response features:
  - node-lane ripple/wobble
  - short-lived overshoot with recovery
  - tangential travel along the contour instead of pure radial expand/contract
- [ ] Phase 3: evaluate whether any of that deserves a user-facing control:
  - only expose controls that clearly matter
  - keep shaped UI lean
  - prefer good authored defaults over a forest of knobs

**Validation checklist:**
- [ ] Driven node regions visibly react more than unrelated regions
- [ ] Adjacent contour motion feels connected, not sector-blocky
- [ ] Rest shape still matches authored base contour
- [ ] Contour motion reads as fluid/gel, not mechanical articulation

#### 5H. Blob Maintenance (Stays Functional, Dev-Gated Later)

**Status:** `[~]` Blob stays fully functional and shippable. Cleanup continues independently of Goo.

**Current state:**
- Blob (both unshaped and shaped) remains the shipping visualizer mode — no changes during Goo development
- Shaped Blob is architecturally healthy
- Unshaped Blob works but is visually inferior to the mockup target — that's why Goo exists
- Inward liquid plumbing is landed and partially working; visual tuning still open
- Blob key cleanup and preset hygiene work continues independently

**Blob inward liquid landed work (for reference):**
- [x] Settings/model/defaults/runtime fields for `blob_inward_liquid_enabled/reactivity/max_size/color`
- [x] Builder controls with honest UI gating
- [x] Full transport path: settings → config apply → overlay → shader
- [x] Taste The Rainbow applied to liquid color
- [x] Retained-band floor: retreat preserves nonzero band
- [x] Focused regressions: persistence, gating, gap preservation, retreat/advance, co-reaction
- [~] Visual quality still needs tuning — reads as diffuse wash rather than vector liquid front
- [ ] Further visual tuning deferred until Goo direction is validated (Goo's vector styling may inform Blob improvements later)

**Blob cleanup landed:**
- [x] Retired Blob keys removed from preset normalization and repair
- [x] Curated preset tree cleaned of retired keys
- [x] Source-authoritative repair tool stance
- [~] Custom-slot normalization fix: active unshaped keys no longer silently dropped
- [ ] Remaining: lock canonical Blob key set, clean settings serialization, regenerate shipped mirrors

**Blob highlight/specular (deferred):**
- Blob's specular currently reads as sphere shading — the correct vector specular language will be developed in Goo first
- If Goo's specular system works well, it can be back-ported to shaped Blob later
- No further Blob specular work until Goo validates the approach
   
### 6. Preset Tooling Source-Tree Authority

**Status:** `[ ]` Planned, not started
**Priority:** Medium

**Goal:** Prevent repair/regenerate tooling from overwriting authored presets or resurrecting retired presets.

**Known issues:**
- `tools/visualizer_preset_repair.py --repair-all` backfills keys that may have been intentionally omitted
- Regenerate tooling can resurrect retired presets if source tree was cleaned but generated tree wasn't
- No guard prevents adding back explicitly removed keys

**Plan:**
- [ ] Audit `_sanitize_settings` for backfill logic that adds keys not present in authored payload
- [ ] Add `--source-authoritative` mode (or make default) — remove junk but never add missing keys
- [ ] Ensure `regenerate_visualizer_shipped_presets.py` only mirrors source tree — no resurrection
- [ ] Add a test that authored presets survive a repair round-trip without gaining new keys

### 7. Cross-Mode Custom-Slot / Preset / Settings Sync Audit

**Status:** `[ ]` Planned, not started
**Priority:** Medium

**Goal:** Prevent the Blob custom-slot normalization failure family from existing in any other visualizer mode.

**Why this is now a planned program:**
- Blob exposed a specific class of bug that is easy to miss:
  - runtime actively uses keys
  - model serialization silently drops them
  - custom-slot normalization therefore strips them
  - preset repair/migration may simultaneously misclassify them as retired
- That exact drift pattern can exist in other modes even when the runtime "mostly works", so it deserves a deliberate repo-wide audit instead of waiting for more mode-specific surprises.

**Modes to cover explicitly:**
- [ ] Spectrum
- [ ] Bubble
- [ ] Blob
- [ ] Goo (once promoted from dev gate)
- [ ] Sine Wave
- [ ] Oscilloscope

**Audit checklist per mode:**
- [ ] Build the canonical active-key list from runtime ownership, not just settings docs.
- [ ] Compare that list against:
  - `core/settings/models.py`
  - defaults
  - settings normalization
  - custom-slot snapshot normalization
  - preset migration
  - preset repair/audit tooling
  - preset regeneration
  - builder visibility/binding collection
  - runtime config apply / creator handoff
- [ ] Identify keys that are:
  - active but not serialized
  - serialized but never used
  - wrongly treated as deprecated
  - preserved in one path but dropped in another
- [ ] Record any discovered drift in `Docs/Historical_Bugs.md` if it represents a real regression family rather than a one-off typo.

**Tests to require from this audit:**
- [ ] One normalization-survival regression per mode for representative active keys.
- [ ] One settings round-trip regression per mode for representative authored keys.
- [ ] One preset repair/regeneration anti-resurrection regression per mode where applicable.
- [ ] One custom-slot regression proving runtime-active keys survive save/load/normalize for each mode.

**Execution order:**
- [ ] Finish the current Blob redesign-critical work first.
- [ ] Then run the audit mode by mode, not all at once:
  1. Bubble
  2. Spectrum
  3. Sine Wave
  4. Oscilloscope
  5. final Blob recheck after the canonical Blob surface is locked
- [ ] Update docs/tests/tooling immediately as each mode is audited so the program creates lasting guardrails rather than one giant late cleanup.

---

## Deferred

## Historical Reference — Preset Override Bug Investigation (Failed Fixes)

These fixes were attempted for the settings-loss bug (Tasks 1 & 2 above) but **did not resolve the core issue**. Kept as context to avoid re-treading the same ground.

**Documentation:** [Docs/Visualizer_Preset_Override_Bug_Investigation.md](F:\Programming\Apps\ShittyRandomPhotoScreenSaver\Docs\Visualizer_Preset_Override_Bug_Investigation.md)
**History:** [Docs/Historical_Bugs.md](F:\Programming\Apps\ShittyRandomPhotoScreenSaver\Docs\Historical_Bugs.md) → `2026-04-11 — Visualizer Preset Override Bug`

- **BUG #1:** `apply_preset_to_config()` used merge overlay → Fixed with CLEAR-then-APPLY
- **BUG #2:** `save_media_settings()` collected all modes → Fixed to current mode only
- **BUG #3:** Call-site `.update()` left stale keys → Fixed to use `restore_visualizer_snapshot()`
  - Files: `ui/tabs/widgets_tab.py`, `rendering/widget_manager.py`
  - Tests: `tests/test_visualizer_preset_cycling_runtime.py`
- **BUG #4:** Technical keys lost when switching presets → `TECHNICAL_CONTROL_KEYS` preservation added
  - Files: `core/settings/visualizer_presets.py`
- **BUG #5:** Technical keys from ALL modes leaked into saves → `current_mode` parameter added
  - Files: `core/settings/visualizer_presets.py`
- **BUG #6:** `_save_settings_now()` replaced entire `spotify_visualizer` section with fresh current-mode-only data → Fixed to merge into existing config before normalizing
  - Files: `ui/tabs/widgets_tab.py`
  - Secondary: `ui/tabs/media/sine_wave_builder.py` — 10 color button lambdas converted to `bind_color_button()`
- **BUG #7:** `SpotifyVisualizerSettings.from_mapping()`, `from_settings()`, and `to_dict()` omitted all sine/osc lines 4-6 keys → normalization silently dropped them
  - Files: `core/settings/models.py` — added ~40 missing keys across all three methods
- **BUG #8:** `apply_spotify_vis_model_config()` only forwarded lines 2-3 kwargs to the runtime widget → lines 4-6 always used defaults at runtime
  - Files: `rendering/spotify_widget_creators.py`, `rendering/widget_manager.py`
- **BUG #9:** Shift updaters wrote `_sine_lineN_horizontal_shift` (wrong attr name) + shift rows used untracked `_aligned_row()` so visibility function couldn't hide them
  - Files: `ui/tabs/media/sine_wave_builder.py`
- **BUG #10:** `SpotifyBarsGLOverlay.set_state()` accepted `sine_line4/5/6_shift` and `sine_travel_line4/5/6` as parameters but **never stored them to `self`** → always used default 0 at GL level despite model and widget having correct values
  - Files: `widgets/spotify_bars_gl_overlay.py`
  - Full detail: [Docs/Historical_Bugs.md](F:\Programming\Apps\ShittyRandomPhotoScreenSaver\Docs\Historical_Bugs.md) → `2026-04-13`

**Status:** BUGs #6-#10 all fixed. #6 = cross-mode save wipe, #7 = model serialization gap, #8 = runtime config bridge gap, #9 = shift updater attr name + row visibility, #10 = overlay set_state dropped shift/travel for lines 4-6. Awaiting user runtime validation.

---

### 3. Bubble Bounce Physics

**Status:** `[~]` Core implementation landed; preset repair/runtime validation pending

**Goal:** Bubbles should bounce gently off each other instead of overlapping. This should be an adjustable setting. The existing `_apply_soft_separation()` in `bubble_simulation.py` already pushes overlapping bubbles apart with class-based strength — but it uses a pure position-correction approach (no velocity reflection). The result is that overlapping bubbles separate but don't visually *bounce*.

**Proposed Architecture:**

The bounce system uses `_apply_bubble_collision_response()` with two paths:
- bounce path: class-scoped bounce probability + speed injects collision impulse on a dedicated impulse channel (`impulse_vx`, `impulse_vy`)
- fallback path: existing soft separation remains for non-bounce collisions

Mixed big/small collisions are intentionally **big-dominant** for both chance and speed.

**Settings to add:**

| Setting key | Type | Range | Default | Description |
|---|---|---|---|---|
| `bubble_bounce_big_pct` | int (slider) | 0–100 | 70 | % of big bubble collisions that bounce (rest overlap/soft-push) |
| `bubble_bounce_small_pct` | int (slider) | 0–100 | 30 | % of small bubble collisions that bounce |
| `bubble_bounce_big_speed` | float (slider) | 0.0–2.0 | 0.8 | Bounce speed multiplier for big bubbles (0 = no rebound, 2 = full elastic) |
| `bubble_bounce_small_speed` | float (slider) | 0.0–2.0 | 0.5 | Bounce speed multiplier for small bubbles |

**Files to touch:**

1. **`widgets/spotify_visualizer/bubble_simulation.py`**
   - Add `bounce_big_pct`, `bounce_small_pct`, `bounce_big_speed`, `bounce_small_speed` to `tick()` settings read
   - Replace `_apply_soft_separation(dt)` callsite with `_apply_bubble_collision_response(...)`
   - Keep soft separation as non-bounce fallback; bounce path adds impulse + post-collision positional correction
   - Use dedicated impulse channel (`impulse_vx`, `impulse_vy`) so random/diagonal stream velocity (`vx`, `vy`) remains untouched

2. **`widgets/spotify_visualizer/config_applier.py`**
   - Add `_bubble_bounce_big_pct`, `_bubble_bounce_small_pct`, `_bubble_bounce_big_speed`, `_bubble_bounce_small_speed` to the bubble kwargs in `apply_vis_mode_config`
   - Keep bounce keys out of `_append_bubble_visual_extras()` (sim-only, no GPU leak)

3. **`widgets/spotify_visualizer/tick_pipeline.py`**
   - Add `bubble_bounce_big_pct`, `bubble_bounce_small_pct`, `bubble_bounce_big_speed`, `bubble_bounce_small_speed` to `sim_settings` dict in `dispatch_bubble_simulation()`

4. **`core/settings/models.py`**
   - Add 4 new fields to `SpotifyVisualizerSettings` dataclass
   - Add to `from_mapping()`, `from_settings()`, `to_dict()`

5. **`core/settings/defaults.py`**
   - Add defaults for the 4 new keys

6. **`ui/tabs/media/bubble_builder.py`**
   - Add a new collapsible bucket "Bounce" in the normal layout (after Motion)
   - 4 sliders: Big Bounce %, Small Bounce %, Big Bounce Speed, Small Bounce Speed
   - Wire with `bind_setting_signal`

7. **`ui/tabs/media/bubble_settings_binding.py`**
   - Add the 4 keys to `collect_bubble_mode_settings()`

8. **`rendering/spotify_widget_creators.py`** + **`rendering/widget_manager.py`**
   - Add the 4 kwargs to `apply_spotify_vis_model_config()` and fallback

9. **`tools/visualizer_preset_repair.py`**
    - Run `--repair-all` after implementation to update curated presets

**Checklist:**
- [x] Implement `_apply_bubble_collision_response()` in `bubble_simulation.py`
- [x] Add 4 settings to model/defaults/serialization
- [x] Add Bounce bucket to `bubble_builder.py`
- [x] Wire settings load/collection in `bubble_settings_binding.py`
- [x] Wire runtime config bridge (config_applier + widget creators + widget attrs)
- [x] Wire tick pipeline `sim_settings`
- [x] Run preset repair (`--audit-curated`, `--repair-all`, `--reindex-curated`)
- [x] Test: big bubbles at 100% bounce + high speed → measurable rebound impulse
- [x] Test: 0% bounce → retains soft-separation behavior
- [x] Test: persistence/normalization round-trip for new bounce keys

---

## Runtime Watchlist

- [ ] `%APPDATA%/SRPSS/settings_v2.json` repair line repeating indefinitely
- [ ] Source curated tree vs generated shipped tree drift
- [ ] Misleading helper/UI preview exceptions
- [ ] Bubble/Blob slipping back into the signal-contract trap documented in [Docs/Historical_Bugs.md](F:\Programming\Apps\ShittyRandomPhotoScreenSaver\Docs\Historical_Bugs.md)

---

## Idea Box

1. Add a shimmer/flicker regression test for Spectrum once the actual shimmer task is active using synthetic audio that shows it, then adjust it to user results until a solution is found.
