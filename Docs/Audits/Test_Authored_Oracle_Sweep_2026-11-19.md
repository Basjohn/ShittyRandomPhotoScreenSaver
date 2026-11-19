# Test durability sweep: authored values versus behavioral contracts

Date: 2026-11-19  
Source: 2026-11-19 18:34 GODZIP, including the separately repaired Achievement Pulse functional test  
Scope: static sweep of the full repository test inventory; targeted source-only validation here; Windows/Qt/full-suite results remain operator-owned.

## Why this was necessary

`Docs/Guides/Test_Durability.md` already prohibited pinning operator-authored defaults, presets, visual values and themes. Yet a recent Achievement Pulse test froze its then-current QML legibility/tint recipe and failed when the visual treatment was legitimately improved. The blocking scanner could find canonical-default copies but not necessarily *presentation decisions written directly in source*. Merely changing `False` to `True` was the wrong repair.

The governing principle is **expected-value ownership**. Exact assertions are appropriate for test-owned fixture inputs, fixed APIs, protocol versions, geometry/legibility safety boundaries, and negative controls. They are inappropriate for currently chosen artistic defaults, decoration, or other values an operator may legitimately retune. When a setting is editable, exercise alternative test-controlled values and verify behavior, authority and persistence instead.

## Scope and classification

- **1,178** `test_*.py` files in this transfer: **1,175** under `tests/`, **1** under `.github/tests/`, and **2** under `tools/`. The blocking durability scanner and source-oracle review now include nested test modules, `tools` tests, and the workflow test. The advisory default-pin scanner also includes nested tests and the workflow test.
- **Blocking authority-copy scan: 0 findings** after repairs. This is a high-confidence, pattern-based scan, *not* proof that every invalid oracle is recognizable statically.
- **Advisory current-default scan: 60 candidates in 33 files.** The detailed list was evaluated for likely fixture provenance and exact-value purpose; many are deliberate user-input round trips, schema ranges, protocol versions, and normalization limits. It is deliberately not a blocking gate.
- **Advisory source review: 1,517 source-string candidates, 39 literal UI-copy candidates, 0 matching presentation-recipe candidates, 4 potentially visible-window operations.** The new presentation signature detector is narrow. Other source-string assertions have not each been independently certified; the review counts must not be presented as bugs or as proof of clean behavior.

Examples of *legitimate* exact values intentionally retained: a 256-frame audio block size explicitly set by the test before observing the applied worker; `"Top Right"` placed in an onboarding fixture before testing restore; a saved `"hide_borders"` explicitly written through a CLI test; `2` as a serialization version; and mathematical clamp boundaries of the transition resolver.

## What changed

### Blocking and advisory audits

- `tools/test_durability_audit.py` follows additional canonical-default lookup/alias and source-parsing paths, including a helper extracting shipped defaults and literal string copies inside a source/JSON snapshot assertion. Its new **blocking** `mutable-presentation-recipe-pin` rule catches exact production recipe strings and uncontrolled live `legibilityPanel`/tint-style property values. Explicit test-owned values are allowed.
- `tools/test_oracle_review.py` additionally surfaces suspicious source or runtime assertions of literal presentation properties such as `legibilityPanel`, `tintAlphaScale`, and `additionalOpacityAdjust` for manual classification. The general review queue remains advisory; the narrower blocking rule applies in parallel.
- The scan roots of the blocking audit and both advisory utilities cover the full relevant test tree rather than just top-level `tests/` files.
- Adversarial positive and negative self-tests were added to `tests/test_test_suite_durability.py` and `tests/test_test_oracle_review.py`.

### Contract repairs

The touched test modules cover the Achievement ring/material/backdrop, branded headers, clock material presentation, visualizer border material, media child and transport materials, Widget Theme baseline, fullscreen Now Playing material and opacity, fullscreen visualizer display style, media outline width, widget defaults/schema, Friend Pulse preferences, Extruded Bubble authored setting, widget border/separator preferences, and related settings/UI contracts.

In these tests, fixed tint/opacity/legibility recipes or today's editable default values were replaced with one of: explicit input/alternative-state tests, canonical default lookup, schema/domain validation, renderer/ownership checks, or observable Normal/material fallback. Source-contract tests were also synchronized with the actual November 19 fullscreen Media Normal-surface routing, keeping the shared backdrop-owner and opacity boundaries intact. No production or native-core code was modified.

### Durable policy

`Docs/Guides/Test_Durability.md` now calls out **code-authored** presentation recipes as the same kind of brittle oracle even when no user-facing settings control exists. `Docs/TestSuite.md` links the policy to review practices and discourages replacing one pinned literal with another.

## Execution and limits

In this sandbox, the following validation completed:

- Blocking audit: **0 findings**.
- Adversarial scanner self-tests: **46 passed** (`pytest --noconftest` for three scanner/self-test modules); **2 passed** for the installer-style test.
- Focused source-contract tests: **58 passed** (`pytest --noconftest` for 11 non-native test modules).
- Modified Python source: AST/compile validation.
- Source-only checks that reference local Qt/compiled QSB or the explicitly excluded `ui/assets/` tree could not complete here; their missing resources are not a product failure.

Qt/QRhi/native rendering tests were **not validated** in this environment because its PySide6 and compiled shader/runtime resources are absent; an attempted broader Qt-heavy run here is not an SRPSS functional failure. The operator's ongoing Windows full-suite run is the source of evidence for those tests. This audit does not assert that the full suite passes or that every one of 1,517 source-string candidates has been manually reviewed.

## Out of scope and preservation

- No edit to `Current_Plan.md`, native C++ core, rendering implementation, operator-authored presets, settings defaults, curated visualizer art, or shader artifacts.
- No indiscriminate deletion, weakening, skipping, or xfail of tests. Genuine safety, lifecycle, geometry and native parity assertions remain exact where their expected values are independently owned.
- If future failures expose another mutable-value snapshot not recognized by the scanner, add an adversarial detection case and repair the affected test at the behavioral-contract level. Do not merely change the frozen expected value.
