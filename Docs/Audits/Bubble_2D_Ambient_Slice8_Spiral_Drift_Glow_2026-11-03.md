# Bubble 2D: Ambient Slice 8, spiral winding, normal drift authority and glow

Date: 2026-11-03  
Baseline: supersedes GODZIP `cc4c390a9e_BubbleAmbient_Slice7_HeroForeground_2026-11-03`  
Status: **implementation candidate; native appearance/performance not accepted**.

## Scope and operator intent

- Correct decorative **Microbubble / Particle** spiral direction: `SAME` should follow Bubble's real CW or CCW spiral, `REVERSED` should travel opposite. Maintain the independent choice for each population.
- Make non-group **normal Bubble drift** react with convincing force to the same admitted music. Do not remove Group Drift or retune any operator preset; the user can adjust existing authored drift amount/speed after testing.
- Give fixed-size particle **emissive glow** genuine top-end punch, especially at roughly 150% intensity and 300% reactivity; no particle core breathing, new render pass, or glow over the original bubbles.
- Preserve Slice 7 big-in-front-of-small Bubble body masking and all Slice 1–7 decorative/compositor/builder work.
- Do not modify `Current_Plan.md` or `Future_Work.md`.

## Cause and implementation

### Decorative swirl winding

`bubble_ambient.py` applies a -1 sign for `SAME` to correct the previous ordinary stream direction issue. Its swirl branch had already been formed in screen-space UV coordinates, so applying the same flip made CW run CCW and vice versa. The main Bubble `_swirl_motion` math is already consistent with Y-down display coordinates. Swirl's local tangent sign was inverted **before** the existing `SAME`/`REVERSED` multiplier, leaving ordinary directions unchanged and preserving intentional reverse movement.

### Weak local/non-group musical drift

The local drift displacement in `bubble_simulation.py` used terms of approximately `0.03 * drift_amount` plus a `0.05 * drift_amount` bias, while Group Drift drives a much more forceful shared carrier and has its own loud lift. Further, `loud_drift_drive` is gated late, so moderately active music barely increases local drift at all. Only the local/non-group/non-spiral offset now receives `_normal_drift_music_gain(loud_drift_drive, speed_energy)`. It uses the **existing admitted speed-energy follower**, with a small quiet threshold of 0.04 and a bounded gain from 1x at silence to 15x at maximum musical drive. The authored speed/amount controls still apply normally. The group branch and the distinct original spiral solver do not call this multiplier. There is no new audio clock or event source.

In a deterministic 180-step, 60 Hz synthetic input comparison at fixed seed 1138, 8 big + 40 small target bubbles, Drift Amount/Speed/Frequency `0.55/0.55/0.45`, Swish Horizontal:

| Test | Slice 7 terminal logged drift/sample | Slice 8 terminal logged drift/sample |
|---|---:|---:|
| Non-group quiet, energy 0.0 | 0.0002045 | 0.0002045 (exact same final population/positions) |
| Non-group moderate, energy 0.5 | 0.0002794 | 0.0016338 |
| Non-group loud, energy 0.9 | 0.0004269 | 0.0049731 |
| Group moderate, energy 0.5 | 0.0031831 | 0.0031831 (identical final positions) |
| Group loud, energy 0.9 | 0.0071709 | 0.0071709 (identical final positions) |

These are **terminal single-step normalized displacement diagnostics**, not per-second visual movement or a replay of the user's real audio. They demonstrate the old gap and the selected correction without falsely claiming artistic or byte-identical GPU acceptance. The increased normal drift can affect collision/pop outcomes over time during music, as intended; quiet at zero energy and the Group Drift path remain unchanged.

### Emissive glow high-end

`bubble_ambient_gl.py` already has a separate premultiplied-with-radiance ambient target, so the issue is *insufficient emissive output at high settings*, not missing colour alpha. The revised shader keeps the fixed body/core radius and its texture/occlusion contract. It raises only halo radiance at high `vGlow` with a soft knee at 0.8 and a capped high-end light term; a modestly broader Gaussian lets the emitted light read around, rather than as part of, the particle core. This is still a single point-sprite pass. Extremely high values intentionally approach FBO saturation; the operator should judge the live maximum and tune authored values as desired.

## Verified before delivery

- 42 focused pure/settings/geometry tests passed with the project's Qt-free modules isolated from the absent PySide6 runtime. Includes four CW/CCW × SAME/REVERSED spiral cases, core-size invariance under glow change, range/columnarity tests and the new Group Drift guard.
- Direct deterministic old/new Bubble simulation comparisons performed, with results above.
- Touched Python syntax compiled; no new external requirements.
- Full GODZIP payload inventory and hash verification, CRC check, cache/debris exclusion performed at package time.

## Native/operator acceptance remains mandatory

- [ ] In `SAME`, confirm both microbubble and particle spiral motion follows the visible original Bubble spirals for both CW and CCW; verify `REVERSED` flips each independently.
- [ ] Compare a quiet → moderate → sustained loud → quiet replay with **Group Drift OFF**, and assess whether existing drift amount/speed can now produce strong but smooth movement with no jitter or abrupt changes. Reduce preset sliders as needed rather than automatically changing group behaviour.
- [ ] Confirm Group Drift still has its accepted strength/direction and the original Bubble spiral retains its established appearance.
- [ ] Compare particle glow at ordinary, 150% intensity/300% reactivity, and maximum intensity during both idle and sustained music. Check glow creates a halo (not oversized solid cores), respects all-bubble ambience occlusion, and does not wash out the gradient.
- [ ] Check frame pacing and clipping in normal, extreme-wide, extreme-tall and rotated content viewports, with heavy simultaneous GPU load if possible.
- [ ] If glow still cannot reach the aesthetic goal, require native GPU/framebuffer evidence before another arbitrary gain increase.

## No changes to

`Current_Plan.md`, `Future_Work.md`, user-authored presets, Bubble's builder and settings schema, Group Drift's movement equations, original Bubble spiral solver, original 110-body shader loop, ambient render/occluder targets, camera or display geometry.
