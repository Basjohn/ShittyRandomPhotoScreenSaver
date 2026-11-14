# R-NEW | The surface backdrop's first publish had its heavy level overwritten by Qt's one-time generateMips

**Status:** fixed 14 Nov 2026 (plan item N5.7b leftovers, found by `backdrop_pyramid_check.py` round `cards`, fact
`todays_first_publish_against_steady`). Today's OpenGL product path (the Python backdrop) since the backdrop shipped.

`_BackdropRenderNode._claim_mip_levels` (`rendering/quick/render/surface_backdrop.py`) now consumes the wrapped
texture's one-time mip generation at publish: it calls `commitTextureOperations` into a QRhi resource update batch
and releases that batch without submitting it. No GL work, no extra refresh, no timer; the pipeline still writes
both output levels on every refresh.

Regression bar: `tests/test_surface_materials.py::test_first_publish_draws_the_steady_blur` (hidden GL host, Acrylic
over a busy wallpaper): the first-published frame equals the frame after a second refresh within 1 level inside the
card. Negative control: with the call removed the test fails at 74 levels. Harness, same photos as the product's
review (dark `Usu_Underwater_Lab_1440p.png`, bright `670483.jpg`): first publish against steady, before
dark Acrylic 2 / Frosted 9 / Mica 1 / Smoked 5 and bright 19 / 9 / 15 / 3 levels; after 0 everywhere.

## Symptom

Silent: Acrylic, Frosted, Mica and Smoked cards blurred more sharply than designed (up to 19 levels on a bright
photo) from the moment the backdrop first appeared until the next wallpaper or dimming refresh, which on a running
saver is the first wallpaper after the owner is created or woken from parked. Glass (light level only) was unaffected.

## Cause

The output is one RGBA8 texture with two levels the pipeline writes itself (level 0 light, level 1 heavy), wrapped
for the scenegraph with `TextureHasMipmaps` and Linear mipmap filtering. Qt 6's `QSGPlainTexture::
commitTextureOperations` (qtdeclarative `src/quick/scenegraph/util/qsgplaintexture.cpp`) does, for a clean texture
with mipmap filtering, `generateMips` once and sets `m_mipmaps_generated`; `setTexture` resets that flag. The first
commit happens on the first frame a card samples the texture, which follows the refresh that published it and has
no refresh of its own, so `glGenerateMipmap` replaced level 1 with a box downsample of level 0. Later refreshes
rewrote level 1 and Qt never generated again, which is why only the first publish was wrong. Proved with one
variable: consuming that generation (and nothing else) brought every material to 0 levels.

## Lesson

A texture whose levels the producer writes must tell Qt so: a wrapped QSGTexture with mipmap filtering assumes it
owns the chain and regenerates it once from level 0. Compare a first publish against the steady state, not only
the steady state.
