# R-170 | Bubble speed changed with card shape; aspect "tail" modifiers faked a fix

**Status:** fixed 2026-11-05 at the owning boundary (`widgets/spotify_visualizer/bubble_viewport_profile.py`,
`bubble_simulation.py`, `bubble_ambient.py`, the Quick Bubble layout and `bubble.frag`). The aspect modifiers are deleted.
Canonical-card output is byte-identical to the previous build. Operator eyes-on (tall / wide / TV card) is the remaining
acceptance. **Supersedes** the 2026-09 "renderer-content-relative" Bubble motion contract and the 2026-09-05
equal-area-of-the-current-card radius projection. R-69 still binds (no compressor on an already-projected radius/history).

## Symptom (operator, 5 Nov 2026)

"At extreme x and y shapes Bubble would change in speed behaviour. Extreme vertical would speed up and extreme horizontal
would slow down so we implemented some modifiers in that state but we never should have had to do that, we should have
achieved rect quality at every shape. The only thing that should scale is density of bubbles/decor at large sizes."

## Root cause: two different scaling authorities

Bubble's world was 1 unit = the **current** card's width across and the current card's height down. Every move was
projected per axis by the domain (`move_x *= domain_w; move_y *= domain_h`, and the same for impulses, swirl geometry,
trail smear, margins, entry depths, collision corrections), so the snapshot divided it straight back out: motion was a
**fraction of the current card per second**. On a tall 280x1200 card an upward stream therefore covered 4.3x the pixels
per second of the canonical card; on a 2400x300 card a horizontal stream covered 5.7x.

Bubble *size*, however, used a different owner: radius projected through the equal-area response height of the current
card, `sqrt(content_w * content_h / 1.5)`. So the bubbles grew with the square root of the card's area, while the motion
grew with each axis separately. Relative to the bubbles themselves (how motion is perceived), a tall card streamed up
to +186% faster vertically and a wide card -48..-51% slower; equal-area shapes still differed by aspect.

The 2026-09-05 extreme-viewport modifiers (`resolve_bubble_viewport_profile`: `wide_tail` +1 big / +3 small and +20%
stream baseline/cap from 2.5:1, `tall_tail` -1/-1 and -30% stream cap from 1.5:1 height) were tuned on top of that to
make the extremes "feel" right. They could not: the error was continuous in aspect, and they changed authored counts
and speeds by shape. The outline firmness also had aspect terms (`wide_firmness`, `tall_firmness`).

Population never followed area at all (fixed authored counts), so large cards were not denser, only bigger.

## Fix: one unit, density from area

- **The world is in canonical-card units on every card.** `resolve_bubble_world(extent, authored_population)` makes the
  world `extent / canonical` units wide and tall. Every authored literal (stream/drift/swirl speeds, margins, entry depth,
  cluster spread, collision gaps and pushes, overlap retry, prediction distance, trail smear) is used unprojected; all
  per-axis projections, the content-space trail solver and the swirl content-space branch are deleted. At equal uniform
  scale a tall, wide, tiny or huge card moves and sizes exactly like the canonical card.
- **Density follows area.** Authored big/small counts describe one canonical card; `scale_bubble_population` multiplies
  them by the world's area (`population_scale`).
- **Renderer capacity.** The shader holds 110 heroes (`u_bubbles_pos[110]`, per-fragment loops) and that includes
  bubbles whose heads left the card while their trails drain (up to ~1.5x the live population on the curated presets).
  A card larger than the canonical one grows its live population to `BUBBLE_LIVE_CAPACITY` (72, or the authored
  population if larger); past that the whole world zooms isotropically by `world_scale` (bubbles, speeds, distances
  together, exactly like a larger uniform scale), so density and look stay canonical. The canonical card and anything no
  larger never zoom. When the zoom changes live (a capacity-bound card resized, or its count edited) bubbles keep their
  place on the card.
- **One projection in the renderer.** The snapshot keeps radius in canonical units; `BubbleFrame.world_scale` carries the
  zoom. `compute_quick_bubble_layout` projects one radius unit through the canonical card's equal-area response height at
  the current uniform scale and inset, times the zoom (on the canonical extent this is the previous projection exactly).
  The wake ring constants project the same way (`u_trail_radial_scale`); the per-axis history compression
  `u_trail_axis_scale` is deleted because history is already canonical-unit. Outline firmness follows the zoom only.
- **Decor** (microbubbles/particles) moves in the same units (positions remain card fractions with wrap) and its count
  follows area up to its own 96 cap.

Uniform visual scale stays the presentation zoom (presentation_geometry owns it); viewport extent is playroom.

## Evidence

`python -m tools.visualizer_replay.bubble_shape_invariance` (recording `balanced`, 30 s, curated presets 1/3/4/7,
production replay at uniform scale 1, speeds in canonical-card px/s = motion relative to the bubbles' drawn size). Full
tables: `.artifacts/evidence/visualizers/bubble/shape_invariance/20261107_shape_invariance/before_head.txt`, `after.txt`, `summary.txt`.

Stream speed along each preset's stream axis, relative to the canonical card (presets 1 up / 3 left / 4 right):

| shape (extent) | before | after | live heroes after (zoom) |
| --- | --- | --- | --- |
| tall 280x1200 | +80% / -72% / -71% | +0.5% / -2.0% / +1.4% | 65 / 58 / 60 (1.39 / 1.23 / 1.31) |
| wide 2400x300 | -48% / +172% / +179% | -0.6% / -0.1% / +1.4% | 58 / 61 / 66 (2.04 / 1.80 / 1.91) |
| square 600x600 | +22% / -18% / -18% | +0.2% / -1.0% / +0.9% | 64 / 62 / 63 (1.44 / 1.27 / 1.35) |
| tiny 210x140 | 0 / 0 / 0 | -0.6% / -0.8% / +1.7% | 10 / 8 / 9 (1.0) |
| huge 1260x840 | 0 / 0 / 0 | -0.4% / +0.1% / +1.5% | 63 / 62 / 64 (2.47 / 2.18 / 2.32) |
| operator TV 3874.7x1449.5 | -25% / +31% / +35% | +0.2% / -1.0% / +0.9% | 61 / 63 / 65 (5.70 / 5.02 / 5.34) |

The operator's report is the first column: an upward stream on a tall card ran +80% and on a wide card -48%.

Median |velocity| is within 2.2% on every directional shape; live density per canonical card within +-6.5% (tiny: integer
rounding of a quarter population). Swish lateral speed and cadence medians are small, collision-noisy numbers (+-10%,
Group Drift's cadence estimate unreliable); their per-bubble laws are pinned exactly by tests. Swirl (preset 7) keeps the
identical orbit law but a narrow card crops the spiral where it exits, so its distribution metrics follow the crop.

Canonical identity: every published canonical-card BubbleFrame (positions/extras/trails/ambient/class bits/count) for six
curated presets is byte-identical to the previous build (`canonical_digest_head.json` == `canonical_digest_after.json`),
the replay goldens pass, and the canonical-extent renderer layout equals the previous one exactly for every uniform scale
and inset measured (`canonical_layout_head.json`).

Visual: `tools/visualizer_replay/bubble_shape_strip.py` renders the production renderer offscreen (no window):
`after_preset0_window.png` (canonical-size windows of baseline/tall/wide, same bubble size and per-step travel) and
`*_cards.png`; `before_preset0_*` the same frames from the previous build.

## Remaining limit (operator decision: accepted, 5 Nov)

Density can grow only to the renderer's 110-hero capacity (72 live). On the operator's TV card (world 47.8 canonical
cards at uniform scale 0.285) a 49-hero preset now aims at 72 live heroes drawn ~1.6x the canonical size instead of 49 at ~2.0x;
growing density further needs a renderer that is not a per-fragment loop over uniform arrays (instanced/binned
heroes) and its own performance evidence. **Decision (operator, 5 Nov 2026):** after reviewing Preset 1 rendered on the
TV card at the cap, the capped density is "easily enough": keep the 72-live cap and uniform zoom; no instanced/binned
hero renderer.

## Binding lessons

- A shape-dependent speed is a units bug, not a tuning problem. Never add aspect/extent speed or count modifiers to
  Bubble; fix the unit at the owner.
- One authority per quantity: motion, size, wake and outline all derive from the canonical-card unit and the single
  capacity zoom. Uniform visual scale is the only presentation zoom.
- R-69 still binds: the renderer projects the canonical radius exactly once; nothing compresses an already-projected
  radius or history by viewport extent.
