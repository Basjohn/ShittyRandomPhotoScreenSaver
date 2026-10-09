# R-108 | Card chrome parity and Spectrum regression audit

**STRONG RETENTION VALUE DOCUMENT**

**Status:** Spectrum raster defect **SOLVED / PHYSICALLY ACCEPTED**; PyAudioWPatch packet-framing defect **SOLVED IN CODE / REGRESSION-PROTECTED**; broader C4 Organs reaction and C5 cross-display parity acceptance remain open.

## Trigger

Physical comparison against the operator's ~02:42 2026-10-06 build showed framed Visualizer corners had become visually square in affected CUSTOM poses, outer card borders no longer read at one thickness across widget families, and current Spectrum showed disappearing/flickering bar top edges plus weaker Organs reaction. Existing tests were green because several encoded scale-dependent shell chrome as intended behavior.

## Checkpoint 1 root causes

`widgets.global.card_border_width_px` is the product authority for Card Border Width. Most ordinary family adapters nevertheless called their style projectors without that value and therefore used a local `4.0` default; Games You Follow independently resolved the global key. H9 uniform-transform cards then scaled the outer `OverlayCard` border with `presentationScale`, so finished thickness depended on each card's geometry even when all started at the same nominal width.

The retained Visualizer had a parallel semantic error in `presentation_geometry.py`: visible border width was a bounded function of `uniform_visual_scale` and the 8 px card radius was multiplied by that scale. The resulting `inner_corner_radius` is the value correctly consumed by the existing clip/stencil owner, so Bubble's stencil was not independently broken; it was being handed the wrong shell geometry.

The repair keeps a single authority/path: ordinary adapters resolve the global width, whole-card transforms inverse-compensate only that outer stroke, and the Visualizer resolver emits the exact visible width/radius and derives the matching content/stencil inset. No extra mask, guard, timer, QML layer or family-specific border correction exists.

## Checkpoint 2: Spectrum pixel defect and source-input regression

The physically-good anchor is `f12137cf2f`. Comparing it forward to `8448717216` still shows no direct committed edit to Spectrum's renderer or fragment shader. The operator also disproved the first width-based explanation: the cap can flicker in narrow as well as wide poses.

The CP1 Windows real-GL gate finally exposed the pixel defect directly. In solid-bar mode the vertical edges are selected from a floored X coordinate, but the moving horizontal cap used the interval `active_height - authored_scale <= y_rel < active_height`. `authored_scale` is a visual-world scale. Below one logical pixel that interval can contain no fragment centre at particular fractional heights, so the bar remains present but its top sample is fill colour. The failed gate recorded exactly that: at level 0.08 one endpoint was white border and the moving top endpoint was `[8, 8, 8]` fill. The repair changes only that ownership mistake: top-cap coverage has a one-logical-pixel minimum while retaining authored growth above it. No derivative, extra pass, timer or guard is added.

That fixes the rendering defect but does not invent a false commit attribution. The good anchor contains the same latent predicate, so the *trigger* that made it newly visible remains a separate bisect target if physical testing still reproduces it. The dirty post-head CUSTOM geometry-profile work is the only non-committed geometry family change in the supplied tree and therefore remains the first scale-decomposition comparison point, not a proven culprit.

For reactivity, the diff does contain a concrete semantic regression candidate. `fd3a072985` changed PyAudioWPatch callback admission from the known-good rule "reshape the actual delivered float32 payload when its length is channel-divisible" to strict equality with PortAudio callback `frame_count`. A valid payload whose advisory count disagrees is now dropped completely, even though preset values and `bar_computation.py` are unchanged. Checkpoint 2 restores actual-payload shaping while retaining the affinity-lane owner, float32 format, exact block-size request and malformed-channel rejection. Physical Organs comparison remains the acceptance authority.

This audit treats old screenshots/build behavior as physical evidence, not permission to tune current output until it looks close. Root cause first.
## 2026-10-07 closure evidence and permanent regression contracts

The operator physically confirmed that the characteristic Spectrum bar-top flicker is gone after the moving-cap coverage repair. The real-GL regression now sweeps 37 fractional activity levels from 0.08 through 0.92 at an extreme `uniform_visual_scale < 0.2` and asserts the **moving cap** remains border-coloured. An overlap follow-up corrected the oracle itself: alpha coverage spans the full bar, so the opposite endpoint is the stationary baseline and is not the target of this repair. The regression must not be broadened back into requiring an unrelated sub-pixel bottom stroke.

The native-capture regression reproduces the independent PyAudioWPatch failure directly. A valid three-frame, two-channel float32 payload is delivered while the callback supplies contradictory advisory `frame_count` values both smaller and larger than the real payload. Every channel-divisible payload must be admitted and reshaped from its delivered sample count. The malformed-payload rule remains strict: data that is not float32/channel-divisible is still rejected. `frame_count` may describe PortAudio's callback expectation; it must never become a second PCM-shape authority.

After the CP2 overlap-oracle repair, the operator reran the focused tranche and recorded **220 passed in 8.65 s** (`20261007_233403_aca4de87`). This closes the overlap test failures and makes these two regression contracts durable. It does **not** substitute for the still-open physical comparison of Organs reaction or the broader C5 visual-parity gate.

