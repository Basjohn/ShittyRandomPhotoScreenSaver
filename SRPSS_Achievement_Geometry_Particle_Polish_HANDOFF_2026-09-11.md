# SRPSS Handoff — Achievement / CUSTOM Geometry / Particle Polish — 2026-09-11

## Where we are

Authority for this slice is the operator-supplied GODZIP with source HEAD `c5282049bcd2ebe3139537e30ab2b28ac5d91714`.

Three narrow changes are implemented without changing their established normalization/ownership seams:

- Achievement Pulse: percentage text inside Progress Pulse is exactly 10% smaller (`2.22 -> 1.998` multiplier) and the unchanged 108x108 pulse is raised 4 px by increasing its bottom inset from 16 to 20. Authored card sizing/model/default ownership is untouched.
- Achievement Shelf Style: presentation-only missing-value canonicalization maps both `Unknown` and `Unavailable` to `UNAVAILABLE`. The semantic Steam model remains unchanged; both values therefore share the same shelf font/fit/right-alignment path.
- CUSTOM geometry move editing: the existing edge/centre/peer targets now receive a small 3 px semantic scoring bias against the 12 px grid, because the grid previously masked almost all of the nominal snap threshold. This is a light snag rather than a wider sticky threshold: alignment wins only when it is within a few pixels of the nearest grid target. The new external peer-gap target still uses the shared 30 px widget margin with its separate narrow 5 px candidate band; only positions beside a peer are eligible, never inset/overlap positions. No timer, poller, animation or second geometry owner was added.
- Particle transition: Random's intermittent cut-line case was traced to Swirl -> Center Outward. A linear normalized-`atan()` order term crossed the +/-PI branch cut. Only that angular hint is replaced with a periodic sine term. Particle Settings labels now match existing persisted shader indices: `NW, NE, Front, SW, SE` and `Typical, Center Outward, Edges Inward`.

## What I'm looking for

Only tests/reconciliation remain as blockers in `Current_Plan.md`; work already completed and previously waiting only on visual acceptance is closed there.

The broad repository pytest inventory is still outstanding in the intended Windows/PySide/OpenGL environment. This Linux workspace cannot use that as an acceptance gate when PySide6 is absent.

## What I need to fix

Nothing else is admitted from this slice unless tests expose a current-owner regression. In particular:

- do not alter Achievement Pulse authored-size/ordinary-uniform normalization to tune these pixels;
- do not further strengthen either the 3 px semantic alignment bias or the 30 px peer-gap attraction into sticky snapping without operator evidence;
- do not retune the other Particle modes/orders while validating the Center Outward seam repair;
- preserve Particle enum indices; labels changed, stored meanings did not.

## Added focused tests

- `tests/test_achievement_pulse_polish_contract.py`
- `tests/test_custom_layout_peer_margin_snag_contract.py`
- `tests/test_particle_transition_swirl_seam_contract.py`

These are new tests only; no pre-existing test module is edited by this slice. Direct Qt-free execution is **6/6 PASS** after the small alignment-snag increase.
