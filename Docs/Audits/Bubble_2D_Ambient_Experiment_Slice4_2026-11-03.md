# Bubble 2D ambient experiment, Slice 4: direction, glow, and column sculpting

Status: **implementation candidate / native visual acceptance open**. Branch authority: supersedes experimental Slice 3 on unchanged GODZIP baseline `cc4c390a9e`. This session is intentionally **not** incorporated into `Current_Plan.md` or `Future_Work.md`.

## Intent and boundaries

- Ambient microbubbles and particles are optional decorative water atmosphere, not a substitute for original Bubble. Every toggle remains off in existing configurations. The existing original Bubble simulation, shader bubble population, reactivity, collisions, RNG and authored presets remain untouched.
- Both populations now expose a styled `Same` / `Reversed` direction choice. `Same` corrects the prior opposite-travel sign and is the default for newly admitted settings; `Reversed` retains the accidental counter-current look. No existing stream or drift control is redefined.
- Microbubble **Columns** at zero preserves the clumped short-chain seed; higher values tighten horizontally and lengthen chains vertically. Active chains respond to changes reversibly **without resetting or reseeding**. The underlying population remains bounded at 96 microbubbles.
- Particle **core size is fixed** through musical energy changes. Its existing small-Bubble breathing value modulates only glow. The glow slider gains more usable strength, and the GL fragment uses a wider, stronger inner/outer halo under the original bubbles. No new global bloom pass or full-scene wash is introduced. Particles remain capped at 96.
- The previous separate transparent GPU target is still composited between the background gradient and the original Bubble/ghost/wake shading. Canonical content clipping and bounds are unchanged.

## Operator observations motivating this slice

The operator confirmed both new ambient layers look excellent at idle in Slice 3 but travel against the main Bubble current during idle/play, and particle glow remains almost invisible even when maximized. The opposite direction is intentionally retained as an optional look. Native appearance and performance must be checked on the operator's GPU: source checks do not prove glow is visible, compare live depth or clip passes, or establish the intended column aesthetics.

## Observational drift-trace cross-check (no Bubble behaviour modified)

Source: `logs826e7b1b483.zip`, `screensaver_spotify_vis.log`, 267 `[SPOTIFY_VIS][BUBBLE][DRIFT]` diagnostic lines, 2026-11-03. Values are logged renderer-normalized sample aggregates, not matched same-object positions or native pixel outputs. **Descriptive groups only** (not a controlled time-aligned replay):

| Logged measure (median) | quiet overall < 0.05 (n=37) | loud overall >= 0.50 (n=126) |
| --- | ---: | ---: |
| overall energy | 0.015 | 0.5685 |
| drift drive | 0.000 | 0.1365 |
| drift phase multiplier | 1.000 | 1.065 |
| drift amplitude multiplier | 1.000 | 1.164 |
| drift step | 0.000035 | 0.000089 |
| stream step | 0.000460 | 0.005547 |
| median per-sample drift/stream ratio | 0.077 | 0.0159 |

At the logged configuration, `dir=swish_horizontal`, `group_cfg=False`, `group_active=False`, authored drift `amount=0.350 speed=0.150 freq=0.500` and effective `amount=0.249 speed=0.042 freq=0.500`. This record shows musical drive entering drift, but only modest drift modulation compared with travel and modest actual drift-step share during music. The user's suspicion of **insufficient *perceptible* intensity** is supported; the stronger claim that drift receives no audio is **not**. This is a deferred Bubble main-mode question, not a license to change behaviour in the ambient experiment.

## Validation and open native gates

- [x] Python syntax compile on touched source and new tests.
- [x] Qt-free direct simulation tests: same/reversed opposition, column-spread narrowing, live reversible column re-shaping without reseeding, fixed particle core/stronger glow signal, disabled-path emptiness, 192 total point cap.
- [x] GODZIP generated as a closed manifest inventory; no `__pycache__` or `.pyc`, path-by-path SHA-256 and size verified, ZIP CRC verified, unrelated Slice 3 bytes and documentation preserved.
- [ ] Native Settings: new styled choices and conditional rows render correctly, persist in custom presets and respond live.
- [ ] Native picture: matching current vs deliberate reversed appearance, robust clump-to-column sculpting at varied viewport aspect ratios, and no discontinuities at loop boundaries.
- [ ] Native GPU: halo visibly responds to sustained musical passages but is tasteful at idle; core size unchanged; no local or full-screen washout, and original Bubble bodies always draw above the decorations.
- [ ] Native performance/cleanup: ordinary disabled Bubble FPS and GL allocations unchanged; cap/clip/rotation/size regressions absent; no old scene-state leakage after preset changes.

Do not declare native acceptance on the strength of this source-level validation alone.
