# Test suite redundancy / false-oracle audit — 2026-10-23

**Scope:** read-only static review of the current test tree; no tests were deleted, XFAIL-marked, skipped, or rewritten. This is **an audit record, not a second suite inventory or a live queue**. [Test Suite](../TestSuite.md) remains the inventory; [Test Durability](../Guides/Test_Durability.md) owns authoring rules; [Guardrails](../Guardrails.md) is only the entry point. Agents can address individual findings during an appropriate test-maintenance pass without promoting a new subjective-work project.

## Counts and methodological limitations

- 745 files below `tests/` in this archive, including helpers/fixtures; **733** match `test_*.py` and contain **6,396 named `test_*` functions**. Parametrization increases the number of runnable cases; no claim of 6,396 pytest executions is made.
- AST-equivalent whole test bodies across files: **two pairs**, both between the Steam Abandonment and Steam Achievement service suites. They test different real runtime implementations and must **not** simply be deleted as duplicates. A shared parametrized lifetime/source-inert contract is optional *if* it still executes independently against both owners.
- **766 occurrences of identical assert-expression ASTs repeated inside functions** (not 766 redundant tests). Most are state checks before and after separate actions, or polling/retry phases. Expression equality alone is not a valid removal criterion.
- **58 files / approximately 371 named functions** meet a deliberately broad *review-only* static signal: literal-source comparisons/readers without direct product imports. This includes genuine packaging/architecture negative guards as well as brittle UI pins. These figures are **not 371 garbage tests**.
- The current [default-pin advisory scanner](../../tools/default_pin_scan.py) reports **61 candidate statements in 28 files**, not 61 confirmed authored-value violations. The [blocking durability audit](../../tools/test_durability_audit.py) reports **zero blockers**. It does not cover every possible oracle mistake.
- Static analysis cannot prove that two tests exercise the same failure mode at runtime. The archived failure snapshot (see [failure triage](Archived_Test_Failure_Triage_2026-10-23.md)) is not a current post-change execution result. Preserve recorded physiological/audio/3D/pixel falsifiers.

## High-priority source-spelling / visual-golden review

These tests are **high-confidence maintenance-debt candidates** because they assert the current spelling of QML, exact decoration or animation implementation, rather than measuring the advertised functionality. A subset enforces real negative boundaries; rewrite or merge those portions instead of deleting them blindly.

| File | Static scope | Concrete brittle expectation | Recommended disposition |
| --- | --- | --- | --- |
| `tests/test_achievement_pulse_progress_text_visual_scale_contract.py` | 2 tests | Exact `progressTextVisualScale: 0.90`, three numerical transform expressions, positions in QML | Remove artistic-number pins; retain functional sizing, fitting and independent geometry behavior in a genuine renderer/layout test if needed |
| `tests/test_achievement_pulse_polish_contract.py` | 6 tests | Exact `fontSize * 1.998`, former `2.22` spelling and other precise presentation literals | Fold genuine role/ownership guards into descriptor/geometry tests; retire one-off visual-polish spellings |
| `tests/test_reddit_spacing_contract.py` | 1 test | Literal `ageValueAgoGap: 2.0`, column widths, expression spelling | Replace with semantic column-order and nonoverlap checks; no fixed currently authored gap pixels |
| `tests/test_r40_hover_edit_lock_contract.py` | 3 tests | Exact line/canvas X coordinates, glyph fade durations and QML callback text | Keep event-driven Lock and sole hover-owner semantics; drop incidental vector-path/fade spelling |
| `tests/test_custom_layout_guides_contract.py` | 21 tests | Hundreds of exact QML snippets, fixed guide colours, z-values, pixel widths, function spellings | **First major consolidation candidate**. Split behavioral safety guards from decoration pins; use retained-scene geometry/paint evidence for alignment and Edit behavior |
| `tests/test_qtquick_artwork_fade_contract.py` | 6 tests | `source.count("NumberAnimation {") == 2`, fixed fade durations, exact `z`/visible expressions | Preserve no-timer and correct successive images/crossfade ordering; avoid pinning the chosen QML implementation and arbitrary durations |
| `tests/test_achievement_pulse_polish_contract.py` / `tests/test_achievement_pulse_progress_text_visual_scale_contract.py` | Overlapping same subsystem | Both pin `canonicalProgressSize` layout and progress-text geometry in source | Consolidate the one actual behavioral invariant under one owner; remove independently stale polish snapshots |
| `tests/test_devcurve_shader_contract_current.py` | 2 tests | Uniform names required as source substrings | Uniform protocol names can be real ABI, **not** automatically garbage; prefer actual program compile/uniform-admission checks and remove redundant text duplicates when equivalent coverage exists |

Additional candidates deserving individual review (not preauthorized deletion): `test_click_affordance_parity.py`, `test_feed_header_parity_contract.py`, `test_qtquick_child_mapped_source_contract.py`, `test_theme_completion_slice_contract.py`, `test_r39_hover_edit_handoff_contract.py`, `test_r41_glyph_tooltip_and_light_audit.py`, `test_weather_settings_target_contract.py`, `test_quick_child_paint_containment_contract.py`.

## False-authority review: current defaults, modes, values, catalogue

**Forbidden:** assertions which assume today's operator-authored preset/Settings/theme values or mutable catalogue membership. **Valid:** schema/ranges/protocols, explicitly test-owned initial values and saved round-trips, canonical producer-consumer agreement without copying a current value.

- `test_extruded_bubble_lazy_bucket_ui.py` has a value assertion for `"Sunlit Surface"` in a Settings-collection path. Establish whether the test itself selects that value; if not, replace the value pin with a test-owned selection and round-trip.
- `test_bubble_spec_ui.py` contains an apparent `bubble_big_size_max == 0.037` pin. Verify the origin: a test-chosen value can be legitimate, a copied mutable default cannot. `bubble_gradient_semantics_version` may be a real schema version, not art.
- `test_steam_phase3_settings_descriptors.py` contains multiple numeric values and allowed-choice checks. Many assert **schema bounds** or test-entered updates; **do not delete them by scanner match**. Inspect origin per assertion.
- `test_settings_manager.py` contains a group of six exact extruded-spectrum values (around lines 812–817 in this snapshot). Determine whether each comes from explicit test-owned payload authoring, not a curated preset/default copy.
- `test_widgets_tab_current.py`, `test_widget_descriptors.py` and `test_widget_display_route_prompt.py` contain apparent clock/display-position pins. Prove whether the test assigned the initial state before changing anything.
- `test_qtquick_transition_parameter_defaults.py` is mostly **good canonical-authority comparison** rather than frozen numeric defaults: it calculates expected results from the live canonical dictionary.

**No product defaults or presets may be changed to quiet these tests.** The scanner is advisory; report source provenance per assertion before modifying one.

## Apparent duplication that should **not** be removed blindly

- `tests/test_steam_abandonment_runtime.py` vs `tests/test_steam_achievement_runtime.py`: AST-identical `test_construction_configuration_and_attach_are_source_inert` and `test_queued_callbacks_do_not_strongly_retain_retired_owner`. These operate different services. Keep both runtime checks, possibly as a shared parametrized contract to reduce harness maintenance.
- Repeated `assert` expressions in a single test can reflect meaningful pre/post conditions. Examples include lifecycle resource counts changing across start/stop and persisted settings state before/after reload. Do not optimize based on duplicate text counts.
- Numeric tests for EB breathing response, native 3D projection, Neon Lake occlusion and defocus image energy are **behavioral falsifiers**, not source-string vanity tests. Their failures must be diagnosed independently rather than dropped for pass-rate gain.
- `test_qtquick_runtime_purity_source.py` tests prohibition of retired presentation/QtWidgets/QPixmap escape hatches: static safety checks are justified here. Prefer AST import-graph inspection over fragile function-body string snippets where possible.
- `test_godzip_foundry_core.py` exercises critical archive paths and integrity: do not classify as decorative tooling just because it concerns a tool.

## Cleanup procedure for a local agent

1. Identify each tested contract's **owner** and a real failure it should catch. If it only says a chosen QML colour, font, duration, line count, private callback spelling or snapshot is *still written exactly like yesterday*, discard that assertion.
2. Check cross-file overlaps before deleting an entire test function. Preserve the one behavior check and its owner, not several copies of historical implementation snippets.
3. Convert appropriate source-only tests to real semantic/parse/schema or rendered functional checks **only if the check is important enough to justify maintenance**. Never create heavier visual tests merely to compensate for deleted brittle tests.
4. For mutable values, determine explicit test authoring before any assertion. Never freeze today's presets, themes or current Settings. No tests may become blockers on selected artistic appearance.
5. Retain independent safety, schema, network/TLS, lifecycle, resource-retirement, frame freshness, financial/data mutation and archive-integrity negative controls. Deleting tests by file age, file length or test count would damage protection.
6. After a focused change, run the smallest related suites plus the durability guard. Classify failures by current contracts instead of reviving retired APIs to satisfy them. Native-agent validation is preferred where available; subjective art remains an operator decision.

**Conclusion:** This archive does not support a mass cull based on duplicates. It **does** support a prioritized audit of brittle source-expression and one-off polish tests, with `test_custom_layout_guides_contract.py` and the overlapping Achievement Pulse visual-polish tests as the first candidates for surgical consolidation. Do not mark the suite healthy until active functional failures are independently classified.

## Executed narrow cleanup: semantic contracts, not artistic source snapshots (2026-10-23)

This pass was applied to the test tree without changing production source, user-authored data, or any active task status. It is **not** a declaration that the remaining source-spelling suites are good; it addresses the demonstrably low-value pins first.

- **Retired:** `tests/test_achievement_pulse_progress_text_visual_scale_contract.py`. Its two assertions pinned the chosen 0.90/1.11/1.045 font transformations, card offsets and exact QML wording. Achievement Pulse model total/progress admission and custom child geometry are already exercised separately by native functional tests in `test_qtquick_achievement_pulse_presentation.py`. This retirement does **not** mark their native functionality accepted on this tree.
- **Consolidated:** `test_achievement_pulse_polish_contract.py` from six source-snapshot tests into three narrower semantic checks: missing shelf data normalization, persisted CUSTOM role identity, and rejection of child-owned parent sizing. Removed font multipliers, exact visual reflow expressions and historical values.
- **Rewritten:** `test_reddit_spacing_contract.py` to protect distinct column roles and order semantics, not specific age/title pixel gaps or source expressions. The result is **not** a pixel-legibility certification.
- **Simplified:** `test_r40_hover_edit_lock_contract.py` retains one opacity owner, deferred Lock handoff and shared glyph component, without pinning the hand-drawn X coordinates or fade timing.
- **Trimmed:** `test_qtquick_artwork_fade_contract.py` removes animation-count, fade-duration and unrelated Weather vertical-inset golden assertions while retaining readiness, no new timers, fade routing, inactive-source retirement and compositing semantics.
- **Reduced:** `test_custom_layout_guides_contract.py` drops fixed line colour/thickness, glyph/wedge dimensions, a duplicated mutable Settings default, decorative fade durations and a test that examined another test's source text. Preserved its standalone guards for event-driven geometry, one session owner, collision authority, idempotent edit-only guides, selection and blocked action routing. Native geometry is owned by `test_qtquick_child_mapped_geometry.py`, not by copied QML pixels.

Before these changes the six reviewed source files collected **39 tests**, of which **37 passed and 2 failed** on this unpacked baseline. Both failures were exact obsolete decorative QML strings, not observed product regressions. Afterwards the five retained files collect **33 passing tests** under `--noconftest`. The focused durability tests and archive-core tests additionally yielded **42 passing tests**. No PySide6/native visual or broad suite result is claimed.

**Remain for separate evidence-led review:** the rest of the large CUSTOM-layout static suite; source-sensitive media/hover/parity contracts; the 61 advisory default-pin candidates; genuine numeric EB, 3D and GL failures. Do not remove functional negative guards or weaken a behavioral failure merely because its neighboring source-spelling test was redundant.

## Rebased test-maintenance correction: expected-value provenance (2026-10-23)

The earlier audit was overbroad wherever it treated a hardcoded pixel offset or
source-owned geometry as disposable **merely for being a literal**. Retain exact
code-owned geometry, containment and clipping assertions when they catch a
functional defect. Reject only assertions copied from *operator-editable*
defaults, presets, themes, fonts or Settings, and subjective implementation pins
with no meaningful contract. The [durability owner](../Guides/Test_Durability.md#ownership-test-before-creating-or-deleting-an-assertion)
distinguishes all four cases.

This rebase slice addresses: (1) EB tooltip tests which pinned the number of
controls and historical audit-tag wording rather than tooltip functionality,
(2) a retired Oscilloscope source path in a mode-isolation test, now checking
actual attribute accesses by AST instead of source comments, and (3) stale
all-mode assumptions that every CARD uses planar quarter-turn and that a
historical list of 3D modes is forever FRAMELESS. The presentation registry
remains the policy SSOT; tests check its *independent structural invariants*.
No rendering, authored values, active project tasks or presets are changed.
Native Qt tests remain agent-verification candidates, not declared green.
