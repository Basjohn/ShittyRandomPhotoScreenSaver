# 10 — Donor Extraction Matrix

## Rule

The donor branch is a reference library, not a merge source.

For each donor feature:

1. identify the product requirement;
2. inspect baseline behavior;
3. inspect donor implementation;
4. extract the smallest principle or algorithm;
5. redesign it under the target ownership model;
6. add tests before integration;
7. benchmark in isolation.

## Commit progression

### `00edb57` — behavioural baseline

Use as reference for:

- visualizer response and feel;
- smoother presentation behavior;
- Settings/Edit lifecycle topology;
- pre-compositor integration behavior.

Do not preserve unchanged:

- unbounded memory/resource lifetime;
- high recurring task rate;
- large CPU workload;
- duplicated image representations.

### `7eed32c` — texture streaming/resource profiling work

Likely donor value:

- texture usage instrumentation;
- streaming tests;
- geometry/resource profiling;
- resource-use visibility.

Extraction decision:

- **Inspect and selectively reconstruct.**
- Prefer tests and accounting ideas.
- Do not assume texture-manager code can be copied without ownership review.

### `6e4a2cf` — orchestration expansion begins

Notable direction:

- larger `display_image_ops.py`;
- program-cache and transition lifecycle work;
- visualizer overlay changes;
- more transaction/retry behavior.

Extraction decision:

- **Generally reject orchestration shape.**
- Inspect for isolated shader/program cache fixes.
- Do not port widget-instance free-function coupling.
- Do not port retries without identifying the ownership defect they mask.

### `7e10589` — compositor architecture and single-surface visualizer layer

Notable direction:

- architecture document;
- large `spotify_visualizer_layer.py`;
- extensive compatibility and staging code;
- single-surface pivot.

Extraction decision:

- **Keep the product goal; reject the compatibility implementation.**
- Reuse context-agnostic renderer math or shaders only after fidelity proof.
- Do not port the layer mega-object.
- Do not port dynamic forwarding.
- Do not retain both old overlay and new layer as long-term architecture.

### `729ef2e` — adaptive timing/backpressure/performance work

Notable direction:

- adaptive timer expansion;
- compositor scheduling changes;
- usage sampling;
- thread-manager changes.

Extraction decision:

- **Reject adaptive timer and paint-ack path.**
- Retain only diagnostics that can operate passively.
- Review any thread-manager simplifications independently.

### `7376bb9` — resource/lifecycle expansion

Notable direction:

- shared texture registry;
- image upload payload;
- lifecycle helper;
- compositor state expansion;
- visualizer-layer expansion;
- image-pipeline changes;
- adaptive timer expansion;
- many tests.

Extraction decision:

#### Keep/reconstruct

- explicit share-group-aware texture identity;
- lease/reference concept;
- callbacks outside locks;
- GL affinity assertions;
- context/lifecycle generation checks for stale results;
- immutable worker/render handoff principle;
- resource accounting tests;
- selected profiling utilities.

#### Rewrite

- shared texture registry into a smaller resource store;
- image upload payload without mandatory full-buffer hash/copy;
- context-agnostic visualizer renderer behind a narrow interface;
- one-outstanding-update coalescing as a GUI-only flag;
- diagnostics as sampled observation.

#### Discard

- adaptive timer;
- paint acknowledgement;
- compositor cadence starvation flow;
- partial reinitialization;
- terminal transaction machinery;
- compatibility mega-layer;
- dynamic attribute forwarding;
- retained fallback/retry state spread;
- whole-widget free-function seams;
- hot-path SHA-256 of full buffers.

## Component matrix

| Donor component/principle | Decision | Conditions |
|---|---|---|
| One surface per display | Reconstruct | Only after lifecycle, resource, and visualizer decoupling phases |
| Context-agnostic visualizer renderer | Reconstruct | Narrow API; deterministic fidelity proof |
| `CompositorSpotifyVisualizerLayer` | Discard | Mine only isolated renderer/shader logic |
| Shared texture registry concept | Keep | Simplify and byte-bound |
| Current shared registry implementation | Selective donor | Verify locks, generations, deletion, driver behavior |
| Immutable upload payload concept | Keep | Avoid duplicate copy/hash |
| Full SHA-256 content identity | Discard default | Optional diagnostic only |
| Adaptive timer | Discard | No replacement worker handshake |
| Paint generation acknowledgement | Discard | Latest-state coalescing only |
| One pending `update()` principle | Keep | GUI-local boolean/atomic state |
| Partial Settings/Edit reinit | Discard | Full teardown/recreate |
| GL affinity assertions | Keep and strengthen | Fail early in development |
| Lifecycle generation | Keep narrowly | One real lifetime boundary |
| Terminal-frame transactions | Discard | Local transition completion |
| Dynamic compatibility forwarding | Discard | Explicit typed interfaces |
| `display_image_ops` widget-shaped seam | Discard/refactor | Explicit services and DTOs |
| Performance logging | Keep selectively | Sampled, aggregated, low overhead |
| Texture streaming tests | Keep/adapt | Add byte plateau and context recreation |
| Legacy visualizer behavior | Preserve | Golden replay and manual review |

## Cherry-pick policy

Allowed only when a donor commit:

- is small;
- is independent;
- does not import rejected dependencies;
- has a clear test;
- does not modify visualizer behavior;
- does not alter lifecycle or presentation without phase approval.

Otherwise manually reconstruct.

## Donor comparison commands

Examples:

```bash
git diff recovery-00edb57..donor-7376bb9 -- rendering/gl_compositor.py
git show donor-7376bb9:rendering/gl_programs/shared_texture_registry.py
git show donor-7376bb9:rendering/gl_compositor_pkg/spotify_visualizer_layer.py
git log --oneline 00edb57..7376bb9
```

Record every donor extraction in a decision or phase report.
