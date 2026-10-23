# Mutable test-oracle audit and Theme Sorter Foundry | 2026-10-23

Supporting audit, **not** an alternative to the authoritative task queue in `Current_Plan.md`.

## Permanent rule

Operator-authored presets, Settings/current defaults and authored themes are freely mutable. No test may require their current contents, theme names, number of curated files, specific source colours or chosen lighting modes. Tests own deterministic fixtures and assert functionality, schema, compatibility, persistence and exact values **only when the test provided them**. A copied authored number is not a contract. `EXACT-VALUE INVARIANT` does not waive this rule.

The blocking audit (`tools/test_durability_audit.py`) now recognizes raw-default snapshots through aliases and a named-shipped-theme artistic oracle. New adversarial self-tests in `tests/test_test_suite_durability.py` verify that violations emit specific `path:line:rule` reports. The Qt-bearing transition registry is no longer needed to run these self-tests. Not all possible Python value-provenance errors are statically decidable: test authors must check origin, especially when expected values are generated via helper calls. This bar complements, but does not replace, review.

## Confirmed bad assertions removed/replaced

- `tests/test_theme_expansion_light_metal_contract.py`: old suite demanded six absent/named light and metallic authored themes and pinned their luminance/contrast/alpha/shadow values. Replaced with independently constructed Settings+Widget test themes; verifies projection, RGB retention, alpha floor and schema round trip **without reading artistic source files**.
- `tests/test_about_art_theme.py`: eliminated the specific Nocturne theme/pink-red palette golden and the rule asserting all currently authored themes must share accent and About-art colours. Kept semantic role parsing/validation and real image mask tests.
- `tests/test_sphere_shared_scene3d_projection.py`: removed `sphere_spin_direction == "Default"` against the live canonical default. Shader phase contracts remain.
- `tests/test_neon_lake_renderer.py`: test now *explicitly authors* the `Vertices` input before verifying corresponding GPU resource behavior, rather than expecting it to be a default.
- `tests/test_widget_theme_mirror_pack.py` and `tests/test_widget_theme_no_material_contract.py`: removed assertions that mutable theme-pack cardinalities must match exactly. Existing loaded Widget themes still obey schema/link contracts. Slim GODZIPs can omit generated Widget files.
- `tests/test_jedi_mode_event_contract.py`: removed a hardcoded boolean default, checking type and consumer/canonical authority agreement instead. Event and UI ownership assertions remain.

The advisory `tools/default_pin_scan.py` now preindexes fixture dictionaries instead of rescanning full test functions for every assert. It reports **61 candidates across 28 files** at this checkpoint. This is deliberately a *review queue*, not 61 confirmed bad tests. Checked representative cases include test-owned settings edits, migration-signature fixtures, schema versions, selector domains, layout round trips and canonical-derived expectations. Do not delete these contracts just to reduce a warning count. Future agents should continue the review on the actual current tree, file by file.

## Theme Sorter Foundry

- `tools/theme_sorter_foundry.py` is a standalone PySide6 QWidget UI. It lists authored Settings themes, applies the selected Settings theme to itself including a control preview, copies name to clipboard, and provides Rename Theme Pair and Delete Theme Combo.
- `tools/theme_sorter_model.py` is Qt-free and owns safe file operations with source path validation, linked Widget ID lookup, conflict detection, staged writes and rollback. Renaming a currently unpaired Settings theme creates its generated Widget counterpart. An existing Widget counterpart keeps its authored colour roles.
- It never changes normal SRPSS Settings theme-selection persistence. For new renamed file IDs, a pre-existing user selection that refers to the old ID can fall back until reselected.
- The optional compiled Default Dark fallback is not destructively editable; other authored themes are freely mutable.

See [Theme Sorter guide](../Guides/Theme_Sorter_Foundry.md) and [Settings Theme Architecture](../Architecture/Settings_Theme_Architecture.md).

## Evidence and open validation

Blocking audit: green. **48 focused Qt-free tests passed** (including the new Theme Sorter pair/rollback and durability guard tests). `python -m py_compile` passes on new/changed tools. The Qt environment is missing PySide6; **no native UI preview, native acrylic/glass visual validation, actual clipboard check or Windows dialog verification has been performed**. Agents should perform those steps on throwaway theme catalogues; operator aesthetic approval is only needed for taste-driven UI refinements.

Nothing in this audit accepts or closes unrelated live visualizer failure gates, presets, Settings lifecycle repairs or the broad archived Windows test failures.
