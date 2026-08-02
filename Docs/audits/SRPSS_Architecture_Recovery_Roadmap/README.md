# SRPSS Architecture Recovery Roadmap

## Purpose

This document set is the authoritative recovery and reconstruction plan for **Shitty Random Photo Screen Saver (SRPSS)** after the compositor work between the known behavioural baseline and the current donor branch produced severe presentation, lifecycle, and architectural regressions.

This is not a bug-fix list. It is a controlled architecture recovery program designed to:

1. restore the reliable behaviour and visualizer fidelity of the baseline;
2. preserve only the donor ideas that demonstrably improve the system;
3. eliminate the presentation and lifecycle machinery that caused regressions;
4. fix the serious CPU, RAM, VRAM, task-rate, and cache problems that exist in both versions;
5. create guardrails strong enough that later optimization cannot silently damage visualizer feel, frame pacing, or GL ownership again.

## Authoritative Git references

| Role | Branch | Commit |
|---|---|---|
| Working recovery base | `recovery-00edb57` | `00edb57a3076b845cb8ee4b6cb7f36ea83411f0c` |
| Donor/reference branch | `donor-7376bb9` | `7376bb9bb380253f3bd14079e65d7bdbca062fad` |

The donor branch must remain intact. Do not repair it in place. Do not merge it wholesale into the recovery branch.

## Evidence location

Place the two supplied runtime archives here:

```text
logs/evidence_chest/logs7376bb9.zip
logs/evidence_chest/logs00edb57.zip
```

Interpretation:

- `logs7376bb9.zip` is the `7376bb9` donor/head runtime evidence.
- `logs00edb57.zip` is the `00edb57` baseline runtime evidence.

The evidence is not optional reading. It is the basis for the architectural decisions in this package.

## How Codex must use this package

Read in this order:

1. `00_INDEX_AND_LIVE_CHECKLIST.md`
2. `01_EXECUTIVE_AUDIT_AND_DECISIONS.md`
3. `02_CODEX_OPERATING_CONTRACT.md`
4. `03_WORK_ORDER_AND_PHASE_GATES.md`
5. the phase-specific document named by the live checklist;
6. `12_TEST_AND_BENCHMARK_PROTOCOL.md` before claiming any phase complete.

Codex must update the live checklist and create a phase report after each completed phase. A source change is not completion. Completion requires runtime evidence and explicit pass/fail results.

## Non-negotiable product priorities

Priority order:

1. **Visualizer fidelity and reactivity**
2. **Lifecycle safety**
3. **Frame pacing and perceived smoothness**
4. **Bounded RAM and VRAM**
5. **CPU efficiency**
6. **Average FPS**
7. **Code elegance**

Average FPS is deliberately below perceived smoothness. The failed architecture demonstrated that higher average FPS can coexist with worse motion.

## Central recovery decision

The recovery branch is the behavioural and lifecycle foundation. It is not the final performance architecture.

The donor branch is a source of selected ideas, particularly:

- explicit GPU resource accounting and bounded reuse;
- immutable worker-to-render data boundaries;
- context-affinity assertions;
- useful performance instrumentation;
- the long-term goal of one compositor surface per display.

The donor branch is not a valid source for:

- adaptive timer and paint-acknowledgement scheduling;
- compositor-owned visualizer cadence;
- partial GL reinitialization;
- compatibility mega-layers;
- distributed terminal-frame transactions;
- broad dynamic attribute forwarding;
- hot-path whole-buffer hashing;
- lifecycle state spread across widgets, compositor, controller, workers, and resource registries.

## Definition of success

The reconstruction succeeds only when all of the following are true:

- visualizer modes preserve baseline feel under deterministic replay and live Spotify input;
- frame-time tails remain controlled under idle and background-load scenarios;
- Settings and Edit can be entered and exited repeatedly without GL ownership errors;
- RAM and VRAM reach a bounded plateau instead of climbing with image changes;
- CPU usage is materially lower than both evidence runs;
- no producer waits for a Qt paint acknowledgement;
- all GL creation and destruction occurs on the owning GUI/context thread;
- no compatibility façade hides ownership or silently forwards state;
- every accepted optimization has a rollback point and benchmark evidence.

Start with the index.
