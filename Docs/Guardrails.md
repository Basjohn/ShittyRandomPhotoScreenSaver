# SRPSS Guardrails

This is the **short preflight**, not a second documentation authority. Use the focused owners below before changing their code. Active tasks and acceptance states belong only in `Current_Plan.md`.

## Non-negotiable boundaries

- Work from the operator-provided tree; never reset or overwrite unrelated changes, authored presets, themes or mutable Settings.
- **Mutable authored content is never a test golden.** Test functionality, code-owned contracts, schema, SSOT, test-owned inputs and round-trips, never current authored values; code-owned geometry may warrant exact checks. No routine GUI/style tests for subjective side tools.
- Physical display owns one standalone `QQuickWindow` and retained Qt Quick scene; **Settings is Qt Widgets**. The only Qt Quick window opened from Settings is the Visualizer Studio, which saves through Settings' own Custom path and always restores the same Settings window ([Visualizer Studio](Reference/Visualizer_Studio.md)). No retired presenter fallback, duplicated scene authority or new presentation polling loop.
- Qt Quick owns scheduling; preserve latest-wins state, transition admission, render-thread safety and bounded lifetime. No unnecessary dormant work or GUI blocking.
- Keep visualizers musically faithful and geometrically correct. Performance changes cannot reduce authored fidelity.
- **Graphics backend (decided 5 Nov 2026, [decision](Future_Work/Graphics_Backend_Decision_2026-11-05.md)):** when Vulkan
  (or any non-GL API) is admitted, it is a **native (compiled) render core behind `QSGRenderNode`, hosted by Qt Quick on
  its RHI backend**: that is better than today (no GIL on the render thread; DLSS/FSR via the RHI native handles). A
  Python-driven Vulkan/D3D port is forbidden: far more API calls per frame, each fighting for the GIL, so it is worse
  than today's GL. Whole-frame upscalers are rejected for our content (FSR 1/spatial: soft lines, ringing on dot grids
  and 1-px cores; FSR 2-3/DLSS temporal: smear emissive lines, particles, OIT and fog unless each mode supplies masks):
  reduce cost with mixed resolution (only soft layers such as mist, bloom, reflection/glass blur at reduced resolution
  with depth-aware upsampling; lines, dots, particles and rims always native). New GPU code follows the port-readiness
  rules in that decision.
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
- [Linux Compatibility](Guardrails/Linux_Compatibility.md): platform branching, the single path-root owner, marked dependencies, loud unavailability and Linux evidence limits.
- [Settings Bucket Persistence](Architecture/Settings_Bucket_Persistence_Contract.md): active editing-path ownership.
