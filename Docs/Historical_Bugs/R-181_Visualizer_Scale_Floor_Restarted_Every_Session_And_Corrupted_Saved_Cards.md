# R-181 | Edit's Visualizer scale minimum restarted every session, so saved cards compounded far below it

**Status:** fixed 8 Nov 2026 (`15358d86`). The uniform-scale minimum of a Visualizer card is now absolute in pixels per
world unit, and settings load repairs stored cards below it. Regression bars in
`tests/test_visualizer_content_scale_floor.py`: `test_runtime_edit_sessions_never_compound_the_content_scale_below_the_minimum`
(a 2D and a framed 3D mode; before the fix session 2 saved 67x45 px over a 420x280 world, 0.16 px per world unit) and
`test_settings_arrange_sessions_never_compound_the_content_scale_below_the_minimum` (before: 72x45 over 450x280); the
repair tests are listed in `Docs/TestSuite.md`. Silent and long-lived: the relative floor dates from the first Quick
CUSTOM owner (`b89b0a94`, 30 Aug 2026), and the operator's own Standard profile held two corrupt Visualizer entries.

## Symptom

The saver's Extruded Bubble card on the LG TV looked like a fish-eye "wide angle" (144° before the 90° horizontal cap,
90° x 90° after it) instead of the authored 45° lens. The card is the Standard profile's shared `planar` CUSTOM entry:
592 x 592 px over a `viewport_extent` of 2077.7 x 2077.7, so 0.285 px per world unit. A framed lens's aperture is
`extent_height / 280`, so 2077.7 / 280 = 7.4x the authored view. The record was schema-valid (finite, positive, one
consistent scale), so nothing rejected it. The same profile's layout slot 6 held a 2436 x 364 card over 11544 x 1725
(0.211 px per world unit). Evidence: `.artifacts/evidence/architecture/framed_camera/20261108_hfov_cap/` and
`20261108_scale_repair/`.

## Cause

1. **The content scale is pixels per world unit.** The canonical card (no CUSTOM entry) draws its 420 x 280 world 1:1.
   A wheel or corner gesture changes the card's size at a fixed world; a side drag changes the world at a fixed pixels
   per world unit.
2. **The minimum was relative to the session's starting card.** Every editor admits the Visualizer at `resize_scale`
   1.0: Runtime Edit and the Alt direct gesture (`_admit_visualizer_item`) and Settings Arrange (no
   `_custom_resize_scale` in the Visualizer payload). `uniform_scale_geometry` floored the scale at 0.4 of that start,
   and the Visualizer's size payload (`width`, `height`, `viewport_extent`) stores no scale scalar to measure from. So
   each session (or each Alt-wheel gesture, which is its own session) could shrink the content another 0.4x: 1.0 ->
   0.4 -> 0.16 -> the 48 x 32 px card floor.
3. **A later side drag grew the world at that scale.** Edge resizing keeps pixels per world unit, so dragging a shrunk
   card back to a usable size made the world `card / 0.285`. For a 2D mode that is a sparse, tiny-content card; for a
   framed 3D mode it widens the lens.

Ordinary widgets never had this: their uniform scale is stored (`_custom_resize_scale`) and measured against the
authored size, and `Docs/Contracts.md` already required "re-entering CUSTOM must not compound shrink". The Visualizer is
documented as separate (`uniform_visual_scale` vs `viewport_extent`), and its floor was never made absolute.

## Fix

- `rendering/quick/custom_layout_size.py`: `VISUALIZER_MIN_PIXELS_PER_WORLD` = the shared 40% minimum x the canonical
  1.0. `uniform_scale_geometry`, the one rule Runtime Edit, the Alt direct gesture and Settings Arrange share, floors a
  card's (planar, framed included) next pixels per world unit at it. A card already below it is lifted to it by its
  next uniform gesture. Freeform 3D stages are unchanged: their world is independent of the stage by design.
- **Repair rule** (`repair_visualizer_card_content_scale`, called once per entry by `SettingsManager`'s existing
  `validate_and_repair`, no second repair owner): the content scale is judged from the stored card pixels
  (`width`/`height`, which every save writes) over `viewport_extent`. An entry is legal when it reaches the minimum
  within the half pixel its integer rect carries, so Edit's own floor output is legal. A card below it keeps its
  visible card (normalized rect, `width`, `height`, rotations, every other key) and its world shrinks uniformly until the
  smaller axis scale is exactly the minimum: `extent *= min(w / ex, h / ey) / minimum`. The world's aspect, and so the
  card's framing, stays as authored. Legal entries stay bit-identical and a second load changes nothing.
- **Where it applies:** every stored `spotify_visualizer` entry in the `planar` profile and the legacy `default`
  record, in the live CUSTOM map and in every layout slot, under both profiles (Standard and Media Center share the
  schema). Not touched: live freeform profiles (`3d:sphere`, `3d:extruded_spectrum`; their world is not tied to the
  stage), and retired `3d:extruded_bubble` / `3d:shockwave_grid` entries, which nothing reads any more (both modes
  use `planar`). Entries without a stored card size or world, or with malformed values, are left alone.

## Verification on the operator's profile

A copy of `%APPDATA%\SRPSS\settings_v2.json` loaded through the real `SettingsManager` in scratch (the copy was deleted
afterwards; the real file was only read):

| entry | before | after |
| --- | --- | --- |
| LG TV `planar` (the saver card) | 592 x 592 over 2077.7 x 2077.7 (0.285) | 592 x 592 over 1480 x 1480 (0.400) |
| layout slot 6, `default` | 2436 x 364 over 11544.3 x 1725.0 (0.211) | 2436 x 364 over 6090 x 910 (0.400) |

Slot 5 (1.0) and every `3d:*` entry were unchanged; the second load repaired nothing. The operator's real profile is
repaired on its next load.

**The repair does not bring the saver card's lens back to 45°.** At 0.4 px per world unit a 592 px card still holds
a 1480-unit world, an aperture of 5.29: 131° before the cap, so it renders at the 90° x 90° cap exactly as before
(`eb_standard_profile__saver_planar__repair_before_after.png`: before, after and the aperture-1 reference). The
authored 45° look on a 592 px card needs about 2.11 px per world unit (a 280-unit world). That needs a separate decision
(bound the framed aperture), recorded in `Current_Plan.md`. In Edit the card returns to it with Restore Size (the
canonical world at the card's current scale), the wheel up to the wanted height, and a side drag to the wanted width.

## Why it hid

- One session cannot show it: within a session the floor holds, and every test started at the canonical card.
- The corrupt record is valid by every schema check (finite, positive, one consistent pixels per world unit).
- The visible result builds up over weeks of ordinary use (and of Alt-wheel gestures, one session each), and on a 2D
  card it only looks like "sparse content".

## Lessons

1. A minimum must be measured against something persisted (or derivable from persisted geometry), never against a
   value every session resets.
2. When one geometry family is exempt from a shared contract ("Visualizer is intentionally separate"), check each of
   that contract's guarantees (here "must not compound shrink") is restated for it.
3. A repair that brings a value into its legal range does not restore a look the illegal value destroyed: verify on the
   real record and say so.
