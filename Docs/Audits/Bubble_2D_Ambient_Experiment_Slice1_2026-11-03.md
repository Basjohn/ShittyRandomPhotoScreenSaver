# 2D Bubble ambient experiment, slice 1 (2026-11-03)

**Scope:** deliberately isolated experiment on the `cc4c390a9e` GODZIP working tree. `Current_Plan.md` and `Future_Work.md` are untouched. This does not change EB or the original Bubble population, collisions, ghosting, shader or its authored audio response.

## Design invariants

- **Off is the original Bubble.** All new controls default false. No new GL program, VAO, buffer or point drawing is created when the opt-in layer is disabled.
- A new **Particles** builder bucket contains two independent sets of circle checkboxes. Microbubble Stream and Microbubble Drift can be enabled separately; Particles Stream, Particles Drift and Particles Glow can each be independently enabled.
- Microbubbles are independently seeded short chains of lightweight, glassy circular outlines. Their speed is inherited from Bubble's *already resolved* stream speed (including musical modulation); drift follows the authored existing drift direction, speed, amount and frequency. They have **no direct musical size/glow response**. Density and physical diameter are separate scalar sliders.
- Particles are independently seeded small fixed-size specks. They can inherit the same stream velocity and/or drift. When glow is enabled, the existing post-integrated small Bubble **breathing pulse** modulates *only their halo intensity*, not their core diameter, position or scale. Glow intensity and glow reactivity are shown only when Particles Glow is checked. A colour swatch, size slider and density slider remain ordinary authoring controls.
- Two independent `random.Random` instances protect the original global `random` stream and Bubble's exact hero bubble sequences. Both populations are bounded at 96 points apiece; no growing trail pool, extra timer, or GPU fragment loop over 192 new objects.
- Optional renderer path: one lazily allocated **GL_POINTS** draw, separate from the existing 110-head fullscreen Bubble shader. Alpha falls toward content edges to hide stream wrap. The existing Bubble frame's immutable publication/Quick rendering path carries the new packed point tuple. Inactive frames publish an empty tuple.
- The old Bubble simulation's resolved base stream velocity is exposed as an attribute read by the optional layer, with no change to the old motion formula. The glow drive comes from that tick's actual `pulse_energy` values for the existing non-promoted small bubbles after Bubble integrates its admitted audio.

## Validation and unresolved native acceptance

- Python syntax compiled for all touched Python files. Standalone isolated ambient simulation checks passed for deterministic point counts, disabled-layer emptiness, fixed particle size under quiet/loud breathing changes and glow change with the same audio input.
- Added `tests/test_bubble_ambient_optin.py` for Windows/venv native test execution, including independent seeds, no global RNG consumption, capped counts, and no breathing-induced physical size change.
- **Not yet physically accepted:** the archive runtime cannot import PySide6 or OpenGL. The GL overlay was source-audited but **not executed on the user's native GPU**, so no FPS or actual image-parity claim is made.
- Native checks required: open old Bubble preset with all five toggles off and compare still/motion/reaction with `cc4c390a9e`; enable micro stream and drift individually and in combination; enable particles stream/drift/glow separately, inspect halo on sustained loud recordings; verify no size pulse, proper orientation and clipping on resized/rotated cards, no pink shader compilation errors, acceptable FPS with both densities at 100%, and no GL resources left on mode switch.
- This is a first slice to be judged visually. Placement, chain density, microcircle size, alpha and visual interaction with existing hero bubbles may need further operator tuning. In particular the extra pass is a subtle ambient **overlay**, not a depth-occluded background render; inspect hero overlaps during native review.

**Reversion:** revert the small set of changed and added full files or revert to the preceding `GODZIP_cc4c390a9e_2026-11-03_1344.zip`; do not apply partial work atop unrelated local changes without reconciling it.
