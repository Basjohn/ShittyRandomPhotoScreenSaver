# SRPSS Achievement Pulse Post-Fit Text Scale Handoff — 2026-09-11

## Authority

This slice starts from `GODZIP_Misc_Dormancy_WeatherSettings_2026-09-11.zip`.

## Change

Installed screenshot review showed the prior requested 10% Progress Pulse percentage reduction was not visibly reliable. The earlier implementation lowered `font.pointSize`, but all three percentage layers use `Text.HorizontalFit`; lowering only the maximum point-size ceiling does not guarantee the fitted glyph result changes by the requested amount.

`rendering/quick/qml/AchievementPulsePresentation.qml` now applies one `progressTextVisualScale: 0.90` after fitting to all three retained percentage text layers. This is intentionally presentation-only.

## Normalization / geometry invariants

- `rendering/quick/widgets/achievement_pulse.py` is unchanged: Progress Pulse still presents the existing Total field/percentage truth.
- `rendering/quick/widgets/achievement_pulse_layout.py` is unchanged: authored-size normalization remains the sole Python layout authority.
- Pulse geometry remains 108x108.
- The previously accepted 4 px lift remains `y: authoredCanvas.height - height - 20.0`; it was not moved again.
- No setting/default/schema/persistence value was added.
- Shelf `UNAVAILABLE` parity is untouched.

## Validation

New test only: `tests/test_achievement_pulse_progress_text_visual_scale_contract.py`.

Direct Qt-free execution: **2/2 PASS**. Physical installed visual confirmation remains **NEEDS RUN VALIDATION**.
