# Ordinary widget resize capture harness

`tools/ordinary_widget_resize_capture.py` is maintained tooling, retained beyond
the resize normalization project. Production code must not import it.

Run from the repository root with the project's Python/PySide6, Pillow and NumPy
dependencies. A visible local OpenGL Quick window is required. No environment
variables, network access, provider activation or real account data are needed.

```powershell
python -m tools.ordinary_widget_resize_capture --output logs/widget_resize_normalization/before
# Apply the reviewed presentation change, keeping the same desktop/DPI/font setup.
python -m tools.ordinary_widget_resize_capture --output logs/widget_resize_normalization/after
python -m tools.ordinary_widget_resize_capture --compare logs/widget_resize_normalization/before logs/widget_resize_normalization/after --output logs/widget_resize_normalization/comparison
```

Every output directory must be new: existing evidence is never overwritten.
`--families weather` (or either Steam family descriptor name) narrows a capture.

The real Quick scene, retained host, models and CUSTOM payload projection render
fixed snapshots and generated local artwork at five uniform sizes and three aspect
envelopes. The 112-case matrix covers Steam normal/hidden/portrait artwork and long
titles, plus Weather ready/long/missing/loading/error/cached states. Snapshots enter
at the presentation boundary; this is not a provider or input-event harness.

Each capture records PNGs and `ledger.json`: named item geometry/fonts, preferred
size, shared scale, shadow/glow bounds, Weather fit/insets, DPR, Qt/platform,
fixture version, source HEAD and all captured Qt messages including teardown.
HEAD is provenance, not proof of a clean checkout; retain the reviewed diff alongside
evidence when comparing uncommitted changes. A failed run leaves incomplete evidence
for diagnosis and must be rerun into a new directory.

Comparison rejects environment, DPR and case mismatches or Qt messages. It reports
exact RGBA changed-pixel counts, bounds and geometry equality, and writes opaque
difference masks plus a side-by-side `review.html` linking the original PNGs.
Normal-size identity is reported separately. Pixel differences
are evidence for inspection, never automatic baseline acceptance. Inspect both
original PNGs and the ledger; a tiny changed region can still be a meaningful defect.
`--max-channel-delta N` additionally reports pixels exceeding an explicit per-channel
tolerance; it defaults to zero and always retains exact counts. Only use a nonzero
tolerance justified by unchanged repeated captures on the same graphics setup.

This harness does not close real CUSTOM gestures, Save/Cancel/slot hydration,
tooltips, animated glow, mixed-DPR movement, physical stacking or runtime recreation
gates. Keep those explicitly awaiting their corresponding validation. Its bounded
event-loop waits permit fixture rendering only; they add no production timer.

## Whole-display packing companion

`python -m tools.ordinary_widget_stack_capture --output NEW_DIRECTORY` reuses these
fixed model fixtures and real Quick capture helpers. It records full-size, crowded
stack-only, crowded auto-shrink/re-stack, and expanded/restored layouts with scales,
geometry and Qt messages. It refuses existing directories and activates no providers.
This is visual evidence for the shared pure planner; the retained-presenter/Edit
integration is covered separately by `test_qtquick_resize_normalization.py`.
