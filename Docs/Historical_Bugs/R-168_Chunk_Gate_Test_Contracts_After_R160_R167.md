# R-168 | Stale tests after R160 mode-owned audio and R166/R167 ghosts

**Status:** Source/test-only repairs now have an operator-confirmed **187 passed** focused Windows selection (2026-10-09). The separate Dev Curve replay remains RED on rerun. No production runtime changes. Supersedes no previous accepted runtime behavior.

## Evidence

The operator's R167 four-chunk result bundle records 29 failures (9/1/15/4). Eight 2D Spectrum Quick GL tests used immutable frames missing `spectrum_rainbow_ghost`; eight curated Extruded tests treated a newly introduced optional key as if operator-edited preset JSON files had been forcibly rewritten. A separate Extruded appearance test incorrectly assumed Bar Colours would prevent the independent ghost-rainbow pass from changing pixels. Runtime admission and reveal tests reflected older owner/call signatures; one tests-durability finding was a copied visualizer-mode enumeration.

Several Spectrum-specific worker fixtures construct synthetic Spectrum nodes/lanes but never select Spectrum shaping, causing their shaped bar output to be intentionally zero since R160. Those tests now *explicitly activate the Spectrum shaper only for their Spectrum-specific test workers*. Fake worker tests that do not produce pre-AGC lanes must not claim zero energy signals regression for unshaped modes. Mode-crossing tests now assert that Bubble's FFT analysis boundaries remain present while Spectrum shape nodes/weights are absent. The R150 Sphere `KeyError('Treble')` and R160 mode-owned shaper capability are permanent guardrails; do not regress them to pass old tests.

One Dev Curve `gradual_ramp` replay output-flux floor remains unresolved at 18.61387083343637 versus the existing 19.269285559818062 threshold. This archive does not contain the corresponding fixture/reference, so no justified threshold update or runtime fix could be established. The R168 source deliberately leaves the floor unchanged.

## Applied test-only repairs

- Synthetic offscreen Spectrum frame carries explicit `spectrum_rainbow_ghost=False`.
- Curated Extra 3D ownership accepts only the newly missing optional schema field; normalized authored values still must survive activation. Actual packaged curated JSON is untouched.
- Extruded colour-only drift test disables the independently animated ghost-rainbow layer for isolation.
- Bubble tests assert pre-AGC analysis notches are routed without Spectrum-shaper setters.
- Synthetic Spectrum FFT/soak/integration workers explicitly enable Spectrum's *own* shaping. Nonshaper workers are not given a fake Spectrum profile.
- Real startup reveal's 300 ms hold is asserted at its owning `rendering.quick.startup_reveal` module; refresh-gated transition admission uses the current parameterized transaction claim.
- Compute-lane fake checks inline/pooled parity and does not synthesize analysis energy from bars.
- Durability audit uses mode descriptors rather than a closed mode list.

## Exit criteria

R168 focused Windows regressions ran successfully (187 passed). The separate Dev Curve replay rerun reproduced the same below-floor result and remains open until input/reference provenance and mode-owned output are compared. Preserve accepted Spectrum and Extruded Rainbow Ghost. No full chunk rerun unless the operator chooses it. Never regenerate goldens from mutable curated presets. No builds/installers or physical acceptance assertions from this environment.
