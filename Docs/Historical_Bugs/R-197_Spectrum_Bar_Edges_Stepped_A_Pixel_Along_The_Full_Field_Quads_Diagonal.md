# R-197 | Spectrum bar edges stepped sideways by one pixel along the diagonal of the full-field quad

**Status:** fixed 12 Nov 2026 (plan 1B.10, side defect found in the curated looks' stills). Spectrum's bar coverage
now comes from one continuous coordinate: `gl_FragCoord` through the item's own affine map
(`rendering/quick/visualizer/implementations/spectrum.py`, `item_from_fragment`, uploaded as `u_item_from_frag_x/y`
only when the item's matrix, viewport, size or rotation change; `widgets/spotify_visualizer/shaders/spectrum.frag`).
An item whose matrix is not affine keeps the interpolated coordinate. Regression bar:
`tests/test_qtquick_visualizer_spectrum.py::test_real_gl_bar_edges_keep_one_x_on_both_sides_of_the_quads_diagonal`
(the card at 2x, 840 x 560, bar counts 8 to 64 at full height: every row of the band the bars cover has the same bar
edges; red on the pre-fix shader at most counts) and
`test_the_fragment_mapping_gives_the_quads_own_item_coordinate_at_every_rotation`.

## Symptom

In every thin-bar still of the curated looks (12 Nov round, 840 x 560) one bar stepped sideways by a pixel at about
(123,478), (325,345) and (525,208): both its edges moved, so the bar read as broken in two along a slanted line. The
points lie on the line from the card's bottom-left to its top-right corner.

## Cause

Spectrum draws one full-field quad (a two-triangle strip) and computed each fragment's item coordinate as the
interpolated `v_uv * u_resolution`. Each triangle interpolates with its own barycentric rounding, so the same pixel
column gets coordinates that differ by about 1e-5 in the two triangles. Wherever a bar edge lies exactly on a pixel
centre (common: the layout's widths and gaps are multiples of a quarter pixel at many bar counts), the half-open bar
test (`bar_local_x >= bar_width`, the `floor` of the bar index) decided that column one way above the diagonal and
the other way below it. Silent since the Quick renderer: no test drew bars across the diagonal with an edge on a
pixel centre.

## Fix and evidence

The window position is the same exact value in both triangles; mapping it through the inverse of what the rasteriser
does (viewport, item matrix, `aPosition * uItemSize`, content rotation) gives the item coordinate the interpolation
stands for, and every column is decided once. On the round's stills scene (7 looks x quiet/mid/peak, 9.88 M pixels):
192 seam columns changed, each only on one side of the diagonal (27,953 pixels, the half-column that had stepped);
everywhere else 649 pixels changed by one level (float rounding), none by more. Evidence (worktree):
`.artifacts/evidence/visualizers/spectrum/diagonal_seam/20261112_fix/` (4x crops before/after at the three points,
the still before and after).

## Lesson

A full-field quad's interpolated coordinate is not one continuous function: its two triangles round differently, and
any hard threshold that lands on a pixel centre shows their shared diagonal. Derive hard coverage decisions from
`gl_FragCoord` (one function for the whole quad), or never let a threshold sit on a pixel centre.
