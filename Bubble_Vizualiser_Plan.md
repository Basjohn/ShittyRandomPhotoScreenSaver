# Bubble Visualizer Plan

## Core Architecture & Safety Policies
*See 3_0_Action_Plan.md for full global policies.*
- **ThreadManager:** Use for ALL business logic threading. CPU particle updates MUST run via `submit_compute_task()`, never on the UI thread.
- **Locking:** Protect GL overlay state flags with `threading.Lock()`. Particle state arrays must be double-buffered or lock-protected to avoid tearing between compute and render.
- **UI Thread:** Qt widget updates via `invoke_in_ui_thread()`. The GL overlay's `paintGL()` reads the latest particle snapshot; it never writes particle state.
- **Resource Management:** Register Qt objects properly via `ResourceManager`.
- **Settings:** Must be added to all 8 layers (dataclass, `from_settings()`, `from_mapping()`, `to_dict()`, creator kwargs, widget init, extra dict, GL overlay state).
- **No raw QTimers.** Tick is driven by the existing visualizer tick pipeline (`_on_tick` → `push_spotify_visualizer_frame`).
- **Minimal painting, minimal tick work, minimal UI thread work.**
- **Thread contention avoidance is critical.** Particle simulation must not block the render path. Use a lock-free snapshot pattern: compute thread writes to a staging buffer, render thread swaps a pointer atomically.

## Goal
Implement a sound-reactive "Bubble/Water Tank/Flow" visualizer as a new mode in the Spotify visualizer system. Bubbles stream in a configurable direction (default: upward) with specular highlights, bounce/pulse to bass, wobble to vocals, and have configurable lifecycle (some reach the surface, others pop/fade before reaching it). The visual style matches the reference image `images/Logo.png`: **line-vector style** bubbles with white outlines, small crescent/circle specular highlights, varying sizes, occasional clustering, on a warm directional gradient background.

## Reference Image Analysis (`images/Logo.png`)
The logo shows:
- **Bubble style:** Thin white outline circles (1–2px stroke). Interior is transparent/semi-transparent (shows gradient behind). No solid fill.
- **Specular highlights:** Small white crescent or circle inside each bubble, positioned consistently (upper-left in the logo). The highlight is a filled white ellipse, not a gradient.
- **Size variety:** Mix of large bubbles (~20–40px diameter) and small bubbles (~4–10px). Small bubbles are just dots with a faint ring.
- **Clustering:** Some bubbles overlap or group together naturally. No rigid grid.
- **Background:** Warm gradient (lighter upper-left, darker lower-right). The gradient direction matches the specular direction.
- **Tiny bubbles:** Very small bubbles (~2–3px) appear as simple white dots without visible rings.

## User Requirements (Verbatim, Exhaustive)

### Audio Reactivity
> "Bigger bubbles pulse in size to bass (Slider)"
> "Smaller bubbles pulse to other frequencies (Slider)"
> "All bubbles wobble (rotate and very slight directional drift) according to vocals."

- **Big Bubble Bass Pulse:** Slider (0–100%). Controls how much big bubbles grow/shrink with bass energy. At 100%, big bubbles visibly throb on every kick.
- **Small Bubble Frequency Pulse:** Slider (0–100%). Controls how much small bubbles pulse to mid/high frequencies. Reacts to hi-hats, vocals, melodic content.
- **Vocal Wobble:** All bubbles rotate slightly and drift directionally in response to vocal/mid energy. This is NOT a slider — it's always on, driven by the vocal band. The rotation and drift amounts are controlled by separate sliders below.

### Stream Controls
> Combobox for Stream Direction (NONE -> UP [DEFAULT] -> DOWN -> LEFT -> RIGHT -> DIAGONAL -> RANDOM)
> Slider for Stream Travel Speed (0 -> 150%)
> Slider for Stream Speed Reactivity (0 -> 100%) (Controls how much the song pace effects Travel Speed. At 100% a silent song would not travel)

- **Stream Direction:** Combobox. The main direction all bubbles travel by default. Options: NONE, UP (default), DOWN, LEFT, RIGHT, DIAGONAL, RANDOM.
  - **NONE:** Bubbles float in place, only wobble/pulse.
  - **DIAGONAL:** 45° angle (configurable? or fixed upper-right). Fixed upper-right for simplicity.
  - **RANDOM:** Each bubble gets a random direction on spawn, creating chaotic flow.
- **Stream Travel Speed:** Slider 0–150%. Multiplier on base travel velocity. 0% = stationary, 100% = default speed, 150% = fast.
- **Stream Speed Reactivity:** Slider 0–100%. How much overall audio energy modulates travel speed. At 100%, silence = no travel, loud = fast. At 0%, speed is constant regardless of audio. Formula: `effective_speed = base_speed * (1.0 - reactivity + reactivity * overall_energy)`.

### Drift & Rotation Controls
> Slider for rotation amount
> Slider for directional drift amount
> Slider for directional drift speed
> Slider for directional drift frequency (Never -> Often/Easily)
> Combobox for Directional Shift Travel Direction (NONE -> LEFT -> RIGHT -> DIAGONAL -> RANDOM [DEFAULT])

- **Rotation Amount:** Slider 0–100%. How much each bubble rotates (the specular highlight stays fixed; the bubble outline itself rotates via a subtle wobble deformation). At 0%, no rotation. At 100%, bubbles visibly wobble/rotate.
- **Directional Drift Amount:** Slider 0–100%. How far bubbles drift perpendicular to the stream direction. At 0%, bubbles travel in a straight line. At 100%, significant lateral wander.
- **Directional Drift Speed:** Slider 0–100%. How fast the drift oscillation is. Low = slow lazy wander, high = rapid side-to-side.
- **Directional Drift Frequency:** Slider (Never → Often/Easily). How often a bubble changes its drift direction. "Never" = constant drift, "Often" = frequent direction changes. This controls the noise frequency of the drift function.
- **Directional Shift Travel Direction:** Combobox. The bias direction for drift. Options: NONE, LEFT, RIGHT, DIAGONAL, RANDOM (default).
  - **NONE:** Drift is symmetric (equal chance left/right).
  - **LEFT/RIGHT:** Drift biases in that direction.
  - **DIAGONAL:** Drift biases diagonally.
  - **RANDOM (default):** Each bubble gets a random drift bias.

### Bubble Count & Lifecycle
> Slider for Big Bubble Average Amount
> Slider for Small Bubble Average Amount
> Slider for Bubble's that reach surface (% Of Bubbles that top out vs bubbles that dissipate before reaching the surface)

- **Big Bubble Average Amount:** Slider (1–30, default 8). Target number of large bubbles on screen at any time. The system spawns/despawns to maintain this average.
- **Small Bubble Average Amount:** Slider (5–80, default 25). Target number of small bubbles on screen.
- **Surface Reach %:** Slider 0–100% (default 60%). Percentage of bubbles that travel all the way to the surface edge and exit. The remaining bubbles pop/fade before reaching the edge. A bubble's "fate" is decided at spawn time based on this percentage.

### Styling & Rendering
> Colour picker for all elements that respects alpha.
> Specular Direction Combobox (Top Left -> Top Right -> Bottom Left -> Bottom Right)
>   - Specular stays in position even when bubble rotates.
>   - Specular adjusts in size with pulsing.
> Reference: `images/Logo.png` for bubble and water styling. Styled like line vectors.
> Gradient background: Lightest wherever direction specular is set, darkest opposite, with colour pickers.

- **Colour Pickers (all respect alpha):**
  - **Bubble Outline Colour:** Default white with ~230 alpha. The thin ring around each bubble.
  - **Specular Highlight Colour:** Default white with ~255 alpha. The small crescent/dot inside.
  - **Gradient Light Colour:** The lighter end of the background gradient. Default warm tan (from Logo.png).
  - **Gradient Dark Colour:** The darker end of the background gradient. Default darker brown/grey.
  - **Pop/Fade Colour:** Colour of the brief "pop" flash when a bubble dissipates. Default white with ~180 alpha.
- **Specular Direction:** Combobox (Top Left, Top Right, Bottom Left, Bottom Right). Default: Top Left (matching Logo.png).
  - Specular highlight position is FIXED relative to the card, not the bubble. When a bubble rotates/wobbles, the highlight stays in the same corner. This simulates a fixed light source.
  - Specular highlight size scales with bubble radius (including pulse). When a bubble pulses larger, the highlight grows proportionally.
- **Gradient Background:** A smooth linear gradient across the entire card. The light end is in the specular direction, the dark end is opposite. E.g., if specular = Top Left, gradient is lightest at top-left, darkest at bottom-right.
- **Line-Vector Style:** Bubbles are drawn as thin-stroke circles (not filled). The interior is transparent, showing the gradient behind. Only the outline and specular highlight are opaque.
- **Tiny Bubbles:** Bubbles below ~4px radius are rendered as simple filled dots (no visible ring or specular). This matches the Logo.png style where very small bubbles are just white dots.

### Physics & Interaction (Low Priority)
> Can bubbles hit each other, stick, or pop? Small bubbles hitting big ones cling, big hitting big pop?
> *Constraint:* Physics are a low priority compared to all other desires. CPU thread contention is something the project must always avoid.

- **Collision is NOT mandatory.** Do not implement a full physics engine.
- **Clustering IS desired:** Bubbles should occasionally appear to group together. This can be achieved by spawning some bubbles in clusters (2–4 bubbles spawned near each other with similar velocities) rather than true collision detection.
- **Popping IS desired:** Bubbles that are fated to not reach the surface should visually pop — a brief flash/expansion then fade to zero alpha over ~150ms.
- **If time permits (stretch goal):** Simple overlap detection where small bubbles near a big bubble get a slight velocity bias toward the big bubble (gravitational clustering). This is O(N*M) where N=small, M=big, which is cheap for <100 total bubbles.

## Rendering Architecture Decision

### Approach: Pure Fragment Shader (SDF-based)
- **Reasoning:** The user prefers as much on the GPU as possible. Collision is not mandatory. The bubble count is modest (max ~110 bubbles). Each bubble can be represented as a uniform array entry (position, radius, phase, fate). The fragment shader iterates all bubbles per pixel using SDF circles.
- **Performance:** At 110 bubbles, each pixel evaluates ~110 distance checks. For a 400×200 card at 60fps, that's ~5.3M distance checks/frame — trivially fast for modern GPUs.
- **CPU side:** A lightweight Python loop (or numpy) updates bubble positions each tick (~16ms). The updated arrays are uploaded as uniforms. No vertex buffers, no instancing, no texture uploads.
- **Uniform limits:** GLSL 330 allows at most 1024 uniform components per block. Each bubble needs ~6 floats (x, y, radius, specular_size, alpha, phase). 110 bubbles × 6 = 660 floats — within limits. Alternatively, use a uniform buffer object (UBO) or texture buffer for larger counts.
- **Fallback:** If uniform array limits are hit, pack bubble data into a 1D texture (RGBA32F, 110 texels × 2 rows = 220 texels). This is a standard pattern and avoids the uniform limit entirely.

### Bubble Data Structure (CPU side)
```python
@dataclass
class BubbleState:
    x: float          # 0..1 normalised position
    y: float          # 0..1 normalised position
    radius: float     # base radius (normalised)
    is_big: bool      # True = big bubble, False = small
    reaches_surface: bool  # fate: True = exits, False = pops
    phase: float      # spawn-time random phase for wobble/pulse offset
    age: float        # seconds since spawn
    max_age: float    # lifetime (inf if reaches_surface, else random 2-8s)
    alpha: float      # current opacity (1.0 normal, fading on pop)
    drift_bias: float # directional drift bias (-1..1)
    rotation: float   # current rotation angle (radians)
```

### Shader Uniform Layout
```glsl
uniform int u_bubble_count;           // active bubble count (0..110)
uniform vec4 u_bubbles_pos[110];      // xy = position, z = radius, w = alpha
uniform vec2 u_bubbles_extra[110];    // x = specular_size, y = rotation
uniform vec2 u_specular_dir;          // normalised direction to light source
uniform vec4 u_outline_color;         // bubble outline colour
uniform vec4 u_specular_color;        // specular highlight colour
uniform vec4 u_gradient_light;        // gradient light end colour
uniform vec4 u_gradient_dark;         // gradient dark end colour
uniform vec4 u_pop_color;             // pop flash colour
uniform float u_fade;                 // overlay fade
uniform vec2 u_resolution;            // card size
uniform float u_dpr;                  // device pixel ratio
```

## Complete Settings List (All 8 Layers Required)

| Setting Key | Type | Default | Range | Description |
|---|---|---|---|---|
| `bubble_big_bass_pulse` | float | 0.5 | 0.0–1.0 | Big bubble bass pulse intensity |
| `bubble_small_freq_pulse` | float | 0.5 | 0.0–1.0 | Small bubble mid/high pulse intensity |
| `bubble_stream_direction` | str | "up" | none/up/down/left/right/diagonal/random | Main stream direction |
| `bubble_stream_speed` | float | 1.0 | 0.0–1.5 | Stream travel speed multiplier |
| `bubble_stream_reactivity` | float | 0.5 | 0.0–1.0 | Audio energy → speed modulation |
| `bubble_rotation_amount` | float | 0.5 | 0.0–1.0 | Wobble rotation intensity |
| `bubble_drift_amount` | float | 0.5 | 0.0–1.0 | Lateral drift magnitude |
| `bubble_drift_speed` | float | 0.5 | 0.0–1.0 | Drift oscillation speed |
| `bubble_drift_frequency` | float | 0.5 | 0.0–1.0 | Drift direction change frequency |
| `bubble_drift_direction` | str | "random" | none/left/right/diagonal/random | Drift bias direction |
| `bubble_big_count` | int | 8 | 1–30 | Target big bubble count |
| `bubble_small_count` | int | 25 | 5–80 | Target small bubble count |
| `bubble_surface_reach` | float | 0.6 | 0.0–1.0 | % that reach surface vs pop |
| `bubble_outline_color` | list[int] | [255,255,255,230] | RGBA | Bubble outline colour |
| `bubble_specular_color` | list[int] | [255,255,255,255] | RGBA | Specular highlight colour |
| `bubble_gradient_light` | list[int] | [210,170,120,255] | RGBA | Gradient light end |
| `bubble_gradient_dark` | list[int] | [80,60,50,255] | RGBA | Gradient dark end |
| `bubble_pop_color` | list[int] | [255,255,255,180] | RGBA | Pop flash colour |
| `bubble_specular_direction` | str | "top_left" | top_left/top_right/bottom_left/bottom_right | Light source direction |

**Total: 19 settings** (9 sliders, 3 comboboxes, 5 colour pickers, 2 int sliders)

## Research & Implementation Steps

### Phase 1: Foundation — COMPLETE
- [x] Mode registered in `VisualizerMode` enum (`audio_worker.py`), shader loader (`shaders/__init__.py`), mode map (`spotify_visualizer_widget.py`).
- [x] Uniform limits verified: 110 × vec4 + 110 × vec2 = 660 floats, well within GLSL 330 limits.
- [x] `bubble.frag` created with SDF-based rendering, gradient background, rainbow support.

### Phase 2: Settings Integration (All 8 Layers) — COMPLETE
- [x] All 19 settings added to `models.py` dataclass with `from_settings()`, `from_mapping()`, `to_dict()`.
- [x] Creator kwargs pass bubble settings through `spotify_widget_creators.py`.
- [x] Widget stores `self._bubble_*` attributes, config_applier wires them.
- [x] `_on_tick` extra dict passes GL-relevant keys (colours, snapshot data) to `set_state()`.
- [x] **Important fix:** Simulation-only settings (counts, speeds, directions) are NOT forwarded to `set_state()` — they caused TypeError. Only GL-relevant keys (colours, pos_data, extra_data, count, specular_direction) are passed.
- [x] GL overlay accepts bubble params in `set_state()`, pushes as uniforms in bubble render block.

### Phase 3: CPU Particle Simulation — COMPLETE
- [x] **Created `widgets/spotify_visualizer/bubble_simulation.py`:** `BubbleSimulation` class managing up to 110 `BubbleState` objects.
  - `tick(dt, energy_bands, settings)` updates positions, spawning/despawning, drift/wobble.
  - `snapshot(bass, mid_high, big_bass_pulse, small_freq_pulse)` returns flat lists for GPU upload.
  - `tick()` accepts both object and dict energy_bands for thread safety.
- [x] **Spawning logic:** Cluster spawning (20% chance), fate decided at spawn, target count maintenance.
- [x] **Movement logic:** Stream direction, drift, wobble all implemented per spec.
- [x] **Pulse logic:** Big bubbles pulse to bass, small to mid/high.
- [x] **Lifecycle:** Surface-reaching bubbles exit and respawn; non-reaching pop with flash/fade.
- [x] **Thread safety — COMPUTE thread pool (NOT UI thread):**
  - Simulation runs via `ThreadManager.submit_compute_task()` with coalescing flag.
  - `_bubble_compute_worker()` runs on COMPUTE thread, takes dict snapshots of energy bands.
  - `_bubble_compute_done()` callback posts results to UI thread via `invoke_in_ui_thread()`.
  - `_bubble_apply_result()` atomically swaps pos_data/extra_data/count on UI thread.
  - No locks needed — snapshot pattern with atomic swap.

### Phase 4: Shader Development (`bubble.frag`) — COMPLETE
- [x] Gradient background with specular-direction-aware linear gradient.
- [x] SDF bubble loop: outline ring, specular crescent (elliptical, aspect-corrected), tiny bubble shortcut (<4px = filled dot).
- [x] Pop flash tinting when alpha < 0.9.
- [x] Anti-aliasing via `smoothstep` with 1px feather.
- [x] Rainbow hue shift support via `apply_rainbow()` helper (HSV-based).
- [x] Greyscale saturation fix applied for rainbow mode.

### Phase 5: UI Integration — COMPLETE
- [x] "Bubble" added to visualizer mode combobox.
- [x] `ui/tabs/media/bubble_builder.py` — full UI builder with all sliders, comboboxes, colour pickers.
- [x] 5 bubble colour picker methods added to `widgets_tab.py`.
- [x] Save/load wired in `widgets_tab_media.py`.

### Phase 6: Testing & Refinement — IN PROGRESS
- [x] **Thread safety:** COMPUTE thread pool with snapshot pattern, no shared mutable state.
- [x] **Rainbow mode:** Verified compatible with bubble shader.
- [x] **Card height:** Bubble added to `card_height.py` DEFAULT_GROWTH (3.0x).
- [x] **Bug fix:** Simulation-only kwargs removed from GPU push to prevent TypeError fallback to spectrum.
- [ ] **Performance:** Regression tests needed.
- [ ] **Visual quality:** Compare against Logo.png reference.
- [ ] **Edge cases:** Test with all sliders at 0/max, all stream directions.
