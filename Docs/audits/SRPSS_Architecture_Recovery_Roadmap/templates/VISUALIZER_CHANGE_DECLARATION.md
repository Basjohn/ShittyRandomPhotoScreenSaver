# Visualizer Change Declaration

Infrastructure, lifecycle, memory, cache, compositor, or threading work must not use this form to justify an accidental regression after the fact.

## Change identity

- Working branch: `main`
- Candidate commit:
- Current approved comparison commit:
- Date/time:
- Requested by:
- Exact user request/approval scope:
- Modes affected:
- Shared source/scheduler/presentation paths affected:

## Attribution

- Direct evidence that this is mode-specific rather than shared/runtime-owned:
- Cause confidence:
- Important details below 90% confidence:

Bubble-specific work requires explicit Bubble scope; aggregate visualizer load is not sufficient evidence.

## Current approved behaviour

Describe attack, decay, amplitude, elasticity, first-visible response, cadence, activation/reset, and relevant mode personality.

## Proposed behaviour

## Why behaviour should change

Performance or resource reduction alone is not sufficient unless the user explicitly requests the behavioural trade.

## Exact changes

- equations/parameters:
- source sampling/normalization:
- executor/scheduler/cadence:
- event/impulse integration:
- publication/coalescing:
- presentation/paint authority:
- renderer/buffer precision/resolution:
- activation/generation/reset:

## Prohibited-shape check

- [ ] No persistent/dedicated visualizer lane unless explicitly approved as the behaviour change
- [ ] No terminal batching or source decimation hidden as optimization
- [ ] No producer-to-paint acknowledgement
- [ ] No second repaint/presentation cadence
- [ ] No authoritative state mutation in `paintGL()`
- [ ] No stale first-frame/activation state
- [ ] No unintended changes to other supported modes

## Deterministic logical evidence

## Production-executor temporal evidence

Include source sequence/timestamp, submit/start/end/callback/commit, publication interval/source age, first-visible result, and generation/activation identity.

## Known-bad negative controls

State results for applicable controls such as `666624d`, terminal batching fixtures, and `ebfec397`.

## Installed manual comparison

- exact source fixture/track segment and playback offset:
- environment/displays/refresh/DPR:
- normal speed and slow-motion comparison where useful:
- Settings/Edit/mode-switch result:
- user verdict separately by mode:

## Performance and resource effect

Report CPU/task/p99/first-visible plus whole-app RSS/private commit/dedicated/shared GPU memory. Do not trade perceivable fidelity silently for a lower number.

## Risks and cross-mode effects

## Golden data policy

- [ ] Existing approved goldens remain unchanged
- [ ] A new version is intentionally created after explicit installed approval
- [ ] Previous approved golden/version remains preserved
- [ ] No automatic regeneration occurred

## Rollback

- exact revert/rollback commit:
- accepted-behaviour revalidation:

## Approval

- [ ] Approved by user for the exact candidate commit
- [ ] Rejected
- [ ] Inconclusive; no production change permitted

- Exact approval/rejection statement:
- Date:
