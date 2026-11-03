# SRPSS 2D Bubble: hero-size foreground occlusion (experimental Slice 7)

## Intent / scope

The operator accepted the ambience masks through Slice 6 and asked whether **big Bubble heroes can occlude normal small Bubble heroes** at low cost. The ordinary 2D Bubble image frequently shows small rings and specular dots visibly crossing big ring interiors. This slice applies an artistic foreground rule **only to main hero-body contributions**: within a visible big bubble's *actual* rendered circle, small hero bodies disappear beneath it. No simulation, motion, reaction, collision, preset, builder or decorative layer settings change.

## Minimal rendering contract

- The authoritative simulation's `is_big` flag is the sole class authority; rendered radius cannot substitute because both small and big heroes change size with music, and small heroes can be temporarily promoted.
- Serialize this classification as four uint32 words, 16 bytes per frame, indexed in precisely the same order as the 110-authoritative hero arrays. The immutable frame validates dimensions and rejects out-of-range bits.
- The Quick renderer uploads one `uvec4` (`glUniform4ui`) alongside the existing exact-size hero arrays. No new offscreen targets, draw calls, framebuffer loops or bubble simulation populations.
- The existing hero GLSL loop evaluates each hero *once*, with separate small/big colour accumulators against the exact wake/ghost/background result already present before the hero loop. This preserves ordinary mixing within each class and lets the big class occlude the small class. A cheap square reject makes big-circle coverage smoothing local to the actual silhouette.
- Composite as `big_heroes + (small_heroes - hero_underlay) * (1 - big_coverage)`. Thus, with no big coverage, small heroes retain their unchanged contribution; when fully covered, only the big hero and the original wake/ghost/gradient remain. No flat background replacement disk is introduced.
- Small and big heroes continue drawing their original styles; ghost/wake and the Slice 6 decorative ambient mask retain their previously accepted pass ordering.

## Performance assumptions and cautions

Extra work is one class-bit test, local colour assignment and a conditional big-circle coverage estimate inside the *existing* up-to-110 hero loop, plus four 32-bit uniform words. This is vastly cheaper in principle than a second full-screen render pass or a fragment-by-big-bubble occlusion scan, but **GPU cost and final appearance must be evaluated on the operator's actual Windows/OpenGL hardware**. The new per-fragment registers/branches have not been measured in this environment. If regression is material, revert this single slice instead of weakening established Bubble reactivity or resorting to expensive parallel shaders.

## Focused acceptance

- [x] Exact `is_big` class including temporary promotions, independent of pulse radius.
- [x] 110-hero bound and 4×32-bit sealed class contract.
- [x] No additional draw call, target or simulation system introduced.
- [x] Existing ambient, waveform and future-work plans left unchanged.
- [ ] Native GL compilation and performance compared at ordinary/wide/tall viewports, including concurrent GPU load.
- [ ] Visually check large/small overlap at idle, peaks, and halfway through fade/pop/promotion. Small outline/specular should vanish only where covered; big outline and highlight must remain.
- [ ] Confirm no abnormal halo, dark/light seams or disappearing heads as bubbles cross the big silhouette edge.
- [ ] Verify existing ghost/wake effects and Slice 6 ambient masking remain accepted.

This is an opt-in *experiment by branch/working-tree choice*, not a new persistent preset toggle. The last accepted Slice 6 GODZIP remains the fallback if the GPU/visual checks fail.
