# SRPSS Guardrails

This is the **short preflight**, not a second documentation authority. Use the focused owners below before changing their code. Active tasks and acceptance states belong only in `Current_Plan.md`.

## Non-negotiable boundaries

- Work from the operator-provided tree; never reset or overwrite unrelated changes, authored presets, themes or mutable Settings.
- **Mutable authored content is never a test golden.** Test functionality, code-owned contracts, schema, SSOT, test-owned inputs and round-trips, never current authored values; code-owned geometry may warrant exact checks. No routine GUI/style tests for subjective side tools.
- Physical display owns one standalone `QQuickWindow` and retained Qt Quick scene; **Settings is Qt Widgets**. No retired presenter fallback, duplicated scene authority or new presentation polling loop.
- Qt Quick owns scheduling; preserve latest-wins state, transition admission, render-thread safety and bounded lifetime. No unnecessary dormant work or GUI blocking.
- Keep visualizers musically faithful and geometrically correct. Performance changes cannot reduce authored fidelity.
- Settings remembers only the active tab/pill editing path and necessary ancestors. Inactive buckets close; Settings values and presets remain freely editable.
- Use the present virtual environment and bounded focused tests. **No test-command environment-variable writes, no local frozen builds.** Prefer agent-executable verification; subjective appearance requires operator acceptance.
- Treat source-only validation as source evidence. Do not close an unverified functional or visual failure.

## Focused owners (read the relevant ones)

- [Contracts](Contracts.md): service owners, network/TLS, persisted capabilities, cache retention, callback retirement, system audio.
- [Visualizer Presentation](Guardrails/Visualizer_Presentation.md): Quick architecture, texture lifetime, multi-display, geometry and preset/DSP ownership.
- [Performance Optimization Contract](Guardrails/Performance_Optimization_Contract.md): scheduling, memory, frame pacing, priorities and rejected optimizations.
- [Bubble Temporal Fidelity](Guardrails/Bubble_Temporal_Fidelity.md): Bubble responsiveness and visual fidelity.
- [Presentation Change Preflight](Guardrails/Presentation_Change_Preflight.md): blockers, accepted evidence, fallback discipline.
- [CUSTOM Child Geometry](Guides/Custom_Child_Geometry.md), [Widget Guidelines](Guides/10_WIDGET_GUIDELINES.md): Edit, reflow, containment and nested ownership.
- [Documentation Maintenance](Guides/Documentation_Maintenance.md): source discipline, document roles and build delegation.
- [Test Durability](Guides/Test_Durability.md) and [Test Suite](TestSuite.md): exact-value limits, prohibited tests and suite inventory.
- [Logging Guide](Guides/Logging_Guide.md): diagnostic captures and evidence logging.
- [Settings Bucket Persistence](Architecture/Settings_Bucket_Persistence_Contract.md): active editing-path ownership.
