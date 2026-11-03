# 2D Bubble ambient decoration: Slice 5, glow/compositing and true big-bubble occlusion

**Status:** Implementation candidate, not visually accepted. Supersedes the code portions of Slice 4 while preserving the current working-tree and all existing Bubble behaviour with the decoration toggles off. This is **not** an item in `Current_Plan.md`.

## Inputs / operator report

- The November 3 screenshots, `image(20261103-191815).png` (playing) and `image(20261103-191823).png` (idle), show lovely small environmental specks and microbubble chains, but the particles do not create clearly distinguishable *emitted light*, even at maximum Glow Intensity and Reactivity.
- Direction toggles work; do not revisit or modify the accepted direction/columnarity implementation.
- Request: when decorative particles/microbubbles move behind an actual **big Bubble** body, hide them in that interior if the cost is small.
- `logs826e7b1b484.zip`: Bubble runs and post-integration pulses are available; no native GLSL error is established. Settings logs confirm glow enabled and the authored particle color is near-white/fully opaque in the reported run. Logs alone cannot establish actual glow pixels.

## Root cause in code

The Slice 4 point shader mapped the glow envelope mainly into **alpha** (`alpha = core + innerHalo + outerHalo`), then drew with straight-alpha source-over. The final Bubble compositor simply overlaid that color onto the dark gradient. This makes a slightly blurred pale speck rather than light that visibly illuminates the background; opaque core pixels also cap apparent brightness. Increasing slider ceilings alone cannot solve the optical distinction. The earlier 3x → 5x particle sprite expansion also made the visible dot seem larger, although its inner body threshold was reduced to retain the physical core size.

## Implementation

### True additive *light*, not size breathing

`rendering/quick/visualizer/implementations/bubble_ambient_gl.py` now computes a separately shaped emissive RGB term from the existing small-Bubble breathing signal. Its core-size term is invariant with breathing. It emits **premultiplied RGB plus radiance** into the owned RGBA8 ambient target, using `GL_ONE / GL_ONE_MINUS_SRC_ALPHA` for RGB and alpha rather than incorrectly multiplying the premultiplied source a second time. The existing main Bubble compositing formula already expects premultiplied RGB. Light falloff spans the wider halo sprite; authored core remains compact and constant. Glow at idle is nonzero if enabled; musical drive can materially brighten it with no extra audio attack, signal ingress or movement path. The strength is still controlled by the existing Glow Intensity and Glow Reactivity settings and the input color/alpha.

This is **not** an expensive fullscreen bloom chain, and doesn't alter the ordinary Bubble shader.

### True big-Bubble occlusion using a bounded mask

The existing Bubble simulation publishes the same final radii and centers to the original renderer. Slice 5 selects **only `is_big` bodies** after that exact snapshot, packs only their actual center/radius/alpha in a new `ambient_occluders` immutable field, and forwards that field solely to the optional ambient pass. That pass draws **six vertices (two triangles) per visible big Bubble**, with feathered circular coverage and a multiplicative erase blend. This subtracts the decor underneath the big-bubble interior *inside the ambient texture*, BEFORE the original Bubble main shader draws gradients, ghosts, wakes, outlines and glints. No duplicated hero-body shader loop or full-screen mask texture, no guessed radius cutoff, no original Bubble physics changes. Promoted small bodies are not classified as big.

The mask is content-local with the exact Bubble `response_radius_scale`, so perspective, source opacity, quarter-turn rotation, card scaling, extreme wide and tall extents use one shared geometry contract. Triangle quads avoid the native GL point-sprite maximum size truncating very large bubbles. The optional mask program, VAO, VBO and transparent FBO are lazily created only when decorative points are actually active and released on return to ordinary Bubble.

**Tradeoff:** This is one additional tiny draw call (and a small transfer of big-bubble geometry) while ambience is on. The actual GPU cost is not measured in this environment; check game60 / concurrent GPU load on the user machine. Occlusion is automatic when decorations are enabled, with no extra UI control. Disable the decorations to return to the original renderer's opt-out path.

## Contracts and evidence

- `Current_Plan.md`, `Future_Work.md`, the original Bubble simulation and the 110-body Bubble GLSL are unmodified.
- No additional RNG work, clocks, reactive lanes, collisions, movement or population work in existing Bubble.
- Optional ambient layer remains beneath Bubble foreground elements and above the authored gradient. Same content-local clipping/stencil as before.
- 9 isolated tests passed: exact big-only snapshot selection, immutable frame validation, bounded coverage and aspect/response-scale invariance across ordinary, extreme-wide and extreme-tall dimensions.
- Affected Python modules parsed successfully. Native OpenGL 4.6 shader linking, image comparison and GPU frame timings are **unverified**, because PySide6 / desktop GL are not present in this test container.

## Acceptance sequence on the native machine (open)

- [ ] Play recorded music while all decorative toggles are OFF: original Bubble visuals, behaviour and pacing remain unchanged.
- [ ] Enable particles with Glow OFF: original fixed core and no glowing halo.
- [ ] Enable Glow at a moderate authored intensity: visible soft pool of light around each particle, without changing its core size or blurring main bubbles.
- [ ] Increase Intensity through maximum: clearly stronger emitted halo, not just a larger opaque white particle; no fullscreen washout.
- [ ] Test quiet → sustained loud → quiet: noticeable but graceful glow variation matching **small-bubble breathing**, with no particle size change or rapid flicker.
- [ ] Enable microbubbles together: both varieties remain independent and retain accepted direction/columns motion.
- [ ] Large bubbles travel across the ambient field: decorative microbubbles **and** particles disappear inside their current rendered discs, and reappear smoothly outside without a 128px masking cutoff or a clipping seam. Foreground outlines, glints, ghosts and wakes stay intact.
- [ ] At most, fading/popping big bubbles gradually release occlusion as their alpha falls; do not let hard black holes appear in the gradient.
- [ ] Repeat on narrow/tall, wide, large, rotated and normal card sizes; confirm stencil containment and physical circles rather than elliptical cut-outs.
- [ ] Measure typical and concurrent-game GPU/FPS difference against Slice 4; reject the occlusion approach if its cost becomes material.

If glow is still indistinct, **capture a high/low reaction image pair and the actual generated FBO buffer** before changing more multipliers; distinguish a broken brightness pipeline from insufficient artistic strength. Do not merge into the broader Waveform plans.
