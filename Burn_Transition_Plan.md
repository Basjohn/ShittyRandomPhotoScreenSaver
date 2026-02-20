# Burn Transition Plan

## Core Architecture & Safety Policies
*See 3_0_Action_Plan.md for full global policies.*
- **Transitions:** All visual transitions must end on a final frame that is visually as close as possible to the target static image. At progress 1.0 there should be no residual blending, old-image remnants, or transitional artifacts. This is a **strict policy**.
- **ThreadManager:** Use for IO/computation. The transition itself runs on the UI thread (GL rendering), but any heavy precomputation (noise textures) should use `submit_compute_task()`.
- **Settings:** Must be added to all layers (model dataclass, `from_settings()`, `from_mapping()`, `to_dict()`, defaults, UI).
- **Resource Management:** Register Qt objects properly via `ResourceManager`.
- **Transition framework:** Transitions extend `BaseTransition` (`transitions/base_transition.py`). GL compositor transitions are registered in `rendering/transition_factory.py` and use shaders loaded by `rendering/gl_transition_renderer.py`. The shader receives `u_texture0` (old image), `u_texture1` (new image), `u_progress` (0.0–1.0), `u_resolution`, and custom uniforms.
- **Existing pattern:** See `transitions/gl_compositor_wipe_transition.py` as the closest reference (directional wipe with progress). The Burn transition is essentially a wipe with a noisy edge, charring zone, glow, and optional particles.

## Goal
Implement a "Burning Away" effect transition. Similar to a wipe, but the edge "corrupts" (turns black and jagged) as it eats away in a direction. The edge shape must lightly randomly change as it burns. Include smoke particles, small burnt edge pieces falling downwards, and a warm glow on the burnt edges (like burning paper).

## User Requirements & Guidance (Verbatim)
> "Would a burning away effect transition be possible? (Ideally with a small amount of smoke particles) Basically Wipe but with the edge 'corrupting' turning black and jagged as it eats away in a direction."
> "The shape of the edge must (light) randomly change as it burns away."
> "Assess if this is viable, if smoke particles and small pieces of the burnt edges falling downwards as it burns are viable..."
> "...if we can make the burnt edges have a slight warm glow as they burn away (as if you were to burn paper)"
> "what sort of performance we can expect, what we should make optional/adjustable and how we'd best utilize our current architecture for it."

## Viability & Performance Assessment
- **Viability:** Highly viable using a custom GLSL fragment shader (`burn.frag`) combined with the existing GL compositor transition framework.
- **Performance:**
  - **Shader Math:** 2D Simplex/value noise for the jagged edge is standard and cheap in GLSL (~0.1ms per frame at 4K). Multiple octaves (FBM) for richer edge detail add ~0.2ms. Well within budget.
  - **Edge Glow:** A simple `exp(-dist)` falloff with orange/red colour is trivially cheap. No performance concern.
  - **Smoke Particles (in-shader):** Rendering ~50–100 smoke "puffs" as moving Gaussian blobs in the fragment shader is feasible but requires careful optimization. Each puff = 1 `exp()` per pixel per puff. At 100 puffs on a 3840×2160 framebuffer, that's ~830M exp() calls/frame — potentially expensive. **Mitigation:** Limit smoke to a narrow band around the burn edge (early discard for distant pixels), reducing effective pixel count to ~10% of the framebuffer. This brings it to ~83M exp() calls — acceptable.
  - **Ash Particles (in-shader):** Falling ash can be rendered as small bright dots using cellular noise or a simple hash-based particle system. Very cheap (~0.05ms).
  - **Fallback:** If smoke is too heavy on lower-end GPUs, it should be toggleable. Ash is always cheap enough to keep on.
- **Architecture Utilization:**
  - Create `transitions/gl_compositor_burn_transition.py` extending the GL compositor transition pattern (same as wipe, slide, etc.).
  - Create `transitions/shaders/burn.frag` for the GLSL shader.
  - Register in `rendering/transition_factory.py` alongside existing transitions.
  - Transition duration should default to ~3.0s (longer than standard 1.5s crossfade) to appreciate the effect. User-configurable.

## Visual Design (Burn Zones)

The shader divides the image into zones based on distance from the burn front:

```
[New Image] | [Glow Zone] | [Char Zone] | [Old Image]
            ←── burn front moves this way ──→
```

1. **New Image Zone** (`distance > 0`): Pure `texture(u_texture1, uv)`. The revealed new wallpaper.
2. **Glow Zone** (`0 > distance > -glow_width`): Warm orange/red/yellow glow fading from bright at the edge to transparent. Simulates the incandescent edge of burning paper. Colour: `mix(vec3(1.0, 0.8, 0.2), vec3(1.0, 0.2, 0.0), t)` where `t` is normalised distance into the glow zone.
3. **Char Zone** (`-glow_width > distance > -char_width`): Black/dark brown charred edge. The old image darkens to black. `mix(old_color, vec3(0.02, 0.01, 0.0), char_t)`.
4. **Old Image Zone** (`distance < -char_width`): Pure `texture(u_texture0, uv)`. Unburned old wallpaper.
5. **Smoke Zone** (above/behind the burn front): Semi-transparent grey/white puffs that rise and dissipate. Only rendered within `smoke_band` pixels of the burn front.
6. **Ash Zone** (below the burn front): Tiny bright orange/black dots that fall downward with slight lateral drift.

The burn front position is: `burn_x = u_progress * (1.0 + noise_amplitude) - noise(uv)`. The noise function creates the jagged, randomly-changing edge. Noise coordinates are modulated by `u_progress * 0.3` so the edge shape evolves as it burns.

## Required Settings (All Adjustable)

| Setting Key | Type | Default | Range | Description |
|---|---|---|---|---|
| `burn_direction` | str | "left_to_right" | left_to_right/right_to_left/top_to_bottom/bottom_to_top/center_out | Burn direction |
| `burn_jaggedness` | float | 0.5 | 0.0–1.0 | Edge noise amplitude (0=smooth wipe, 1=very jagged) |
| `burn_glow_intensity` | float | 0.7 | 0.0–1.0 | Warm glow brightness on burning edge |
| `burn_glow_color` | list[int] | [255,140,30,255] | RGBA | Primary glow colour (orange) |
| `burn_char_width` | float | 0.5 | 0.1–1.0 | Width of the charred/blackened zone |
| `burn_smoke_enabled` | bool | True | on/off | Toggle smoke particles |
| `burn_smoke_density` | float | 0.5 | 0.0–1.0 | Smoke particle density/opacity |
| `burn_ash_enabled` | bool | True | on/off | Toggle falling ash particles |
| `burn_ash_density` | float | 0.5 | 0.0–1.0 | Ash particle density |
| `burn_duration` | float | 3.0 | 1.0–6.0 | Transition duration in seconds |

**Total: 10 settings** (4 sliders, 2 toggles, 1 combobox, 1 colour picker, 1 float, 1 float)

## Shader Uniform Layout (`burn.frag`)
```glsl
uniform sampler2D u_texture0;       // old image
uniform sampler2D u_texture1;       // new image
uniform float u_progress;           // 0.0–1.0 transition progress
uniform vec2 u_resolution;          // framebuffer size
uniform float u_dpr;                // device pixel ratio
uniform int u_direction;            // 0=L→R, 1=R→L, 2=T→B, 3=B→T, 4=center→out
uniform float u_jaggedness;         // noise amplitude (0–1)
uniform float u_glow_intensity;     // glow brightness (0–1)
uniform vec4 u_glow_color;          // glow colour (RGBA)
uniform float u_char_width;         // char zone width (normalised)
uniform int u_smoke_enabled;        // 1=on, 0=off
uniform float u_smoke_density;      // smoke opacity multiplier
uniform int u_ash_enabled;          // 1=on, 0=off
uniform float u_ash_density;        // ash density multiplier
uniform float u_time;               // wall-clock time for animation
uniform float u_seed;               // random seed per-transition for variety
```

## Research & Implementation Steps

### Phase 1: Shader Development (`transitions/shaders/burn.frag`)
- [ ] **Research:** Review existing GL compositor transition shaders (e.g., `gl_compositor_wipe_transition.py` and its shader) to understand the uniform interface and texture sampling pattern.
- [ ] **Research:** Evaluate noise functions. Options:
  - **Value noise + FBM:** Already used in `starfield.frag`. Cheap, good enough for jagged edges.
  - **Simplex noise:** Smoother, slightly more expensive. Better for organic burn edges.
  - **Decision:** Use value noise FBM (3 octaves) for the burn edge. It's already proven in the codebase and cheap.
- [ ] **Base Wipe:** Implement directional wipe driven by `u_progress`. Support all 5 directions. For center→out, use radial distance from center.
- [ ] **Jagged Edge:** Offset the wipe threshold using FBM noise. `burn_front = progress_at_pixel + noise(uv * 4.0 + u_progress * 0.3) * u_jaggedness * 0.15`. The `u_progress * 0.3` term makes the edge shape evolve as it burns.
- [ ] **Edge Coloring (3 zones):**
  - Glow zone: `exp(-dist / glow_width)` falloff, coloured with `u_glow_color`, intensity scaled by `u_glow_intensity`.
  - Char zone: Old image darkened toward black using `mix(old_rgb, vec3(0.02), char_t)`.
  - Clean transition at zone boundaries using `smoothstep`.
- [ ] **Smoke Particles (in-shader):**
  - Generate ~30–60 smoke puffs as hash-seeded positions that drift upward/away from the burn front.
  - Each puff: position = `hash(seed + i) + drift * (u_time - spawn_time)`. Size grows over lifetime. Alpha fades.
  - Only evaluate puffs within `smoke_band` pixels of the burn front (early discard optimization).
  - Render as soft Gaussian blobs: `exp(-dist^2 / sigma^2)`. Colour: grey-white with low alpha.
  - Gate behind `u_smoke_enabled`.
- [ ] **Ash Particles (in-shader):**
  - Generate ~20–40 falling ash specks using hash-seeded positions.
  - Each speck: starts at the burn front, falls downward with slight lateral drift. Bright orange fading to dark.
  - Render as 1–2px bright dots using `smoothstep(1.5, 0.0, dist_px)`.
  - Gate behind `u_ash_enabled`.
- [ ] **Progress 1.0 guarantee:** When `u_progress >= 1.0`, output exactly `texture(u_texture1, uv)` with zero effects. Hard `if` guard at the top of `main()`.
- [ ] **Progress 0.0 guarantee:** When `u_progress <= 0.0`, output exactly `texture(u_texture0, uv)`.

### Phase 2: Transition Framework Integration
- [ ] **Create `transitions/gl_compositor_burn_transition.py`:** Extend the GL compositor transition base class (follow `gl_compositor_wipe_transition.py` pattern).
  - Load `burn.frag` shader.
  - Set up all custom uniforms from settings.
  - Pass `u_seed = random()` on transition start for per-transition variety.
  - Pass `u_time` for smoke/ash animation.
- [ ] **Register in `rendering/transition_factory.py`:**
  - Import `GLCompositorBurnTransition`.
  - Add to the transition type map and direction map.
  - Add "Burn" to the available transitions list.
- [ ] **Register in `rendering/transition_state.py`** if needed for state tracking.

### Phase 3: Settings Integration
- [ ] **Add `Burn` to transition type enum/list** in `core/settings/models.py`.
- [ ] **Add Burn-specific settings** to the transition model dataclass (all 10 settings from table above).
- [ ] **Update `from_settings()`**, `from_mapping()`, `to_dict()` for all new settings.
- [ ] **Update `core/settings/defaults.py`** with canonical default values.
- [ ] **Update UI (`ui/tabs/transitions_tab.py`):**
  - Add "Burn" to the transition type combobox.
  - Show Burn-specific settings (direction, jaggedness, glow, smoke toggle, ash toggle, etc.) conditionally when Burn is selected.
  - Direction combobox with 5 options.
  - Jaggedness slider, glow intensity slider, char width slider.
  - Smoke toggle + density slider, ash toggle + density slider.
  - Glow colour picker.
  - Duration slider.

### Implementation Status (Feb 2026)
All Phase 1–3 code is complete:
- [x] `rendering/gl_programs/burn_program.py` — BaseGLProgram subclass with GLSL vertex+fragment shaders
- [x] `rendering/transition_state.py` — `BurnState` dataclass with all settings fields
- [x] `rendering/gl_programs/program_cache.py` — `BURN` registered, lazy load, precompile
- [x] `rendering/gl_compositor_pkg/shader_dispatch.py` — `can_use_burn_shader`, `prepare_burn_textures`, `paint_burn_shader`
- [x] `rendering/gl_compositor_pkg/transitions.py` — `start_burn()` function
- [x] `rendering/gl_compositor.py` — `start_burn()` method, `_on_burn_update`/`_on_burn_complete` callbacks, `_burn` in `__init__`/`_clear_all_transitions`/`_transition_program_map`/program_getters, `_can_use_burn_shader`/`_paint_burn_shader`/`_prepare_burn_textures` proxies
- [x] `rendering/gl_compositor_pkg/paint.py` — burn in shader_paths dispatch
- [x] `transitions/gl_compositor_burn_transition.py` — `GLCompositorBurnTransition` class
- [x] `rendering/transition_factory.py` — `Burn` in `_CONCRETE_TYPES`, random pool, `_create_burn()` helper
- [x] `core/settings/defaults.py` — burn defaults (direction, jaggedness, glow, char, smoke, ash) + duration + pool

**Remaining:** Phase 3 UI controls (transitions_tab.py) and Phase 4 testing.

### Phase 4: Testing & Refinement
- [ ] **Progress 1.0 Guarantee:** Verify that when `u_progress == 1.0`, the shader outputs *exactly* `texture(u_texture1, uv)` with zero noise, glow, smoke, ash, or any transitional artifacts remaining. Screenshot comparison test.
- [ ] **Performance Profiling:** Run iterative cycling at 4K resolution. Target: transition renders at ≥60fps throughout. If smoke causes drops, reduce default puff count or disable by default.
- [ ] **Visual Tweaking:**
  - Adjust warm glow colours (mix of red, orange, yellow) to look like burning paper.
  - Adjust noise scale so the jagged edge looks organic, not pixelated.
  - Ensure smoke rises naturally (not too fast, not too uniform).
  - Ensure ash falls with slight randomness (not perfectly vertical).
- [ ] **Direction testing:** Verify all 5 directions work correctly. Center→out should burn radially from center.
- [ ] **Edge cases:** Test with very short duration (1s), very long (6s), jaggedness at 0 (smooth wipe) and 1 (very jagged). Verify no artifacts.
- [ ] **Overlay compliance:** Verify overlays (clock, media, visualizer) remain visible and correctly stacked during the burn transition. Follow `Docs/10_WIDGET_GUIDELINES.md`.
