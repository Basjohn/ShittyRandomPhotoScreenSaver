# R-66 — Media Runtime Fast Polling Replaced By Provider Event Ownership

Date: 2026-09-01
Status: Solved (runtime observation architecture); slow reconciliation watchdog intentionally retained

## Symptom

The retained Media runtime still carried a legacy active polling ladder (`1000 -> 2000 -> 2500 ms`, with slower idle stages). It worked, but kept recurring work alive even though the Windows GSMTC provider exposes native change events. During a performance-sensitive Qt Quick migration this was unnecessary contention and an ownership smell.

## Root Cause

The migration had preserved snapshot ownership but had not migrated observation ownership. Media state remained discovered by timers rather than having the existing shared owner react to provider-native dirty edges.

## Fix

The existing `_SharedMediaRuntimeOwner` remains the **only** query/snapshot authority:

- `WindowsGlobalMediaController` retains the GSMTC manager/provider-matched session and owns its event tokens.
- native callbacks perform no query/decode/presentation work; they generation-fence a small dirty reason into the shared owner.
- the shared owner hops to the UI thread and coalesces event storms to at most one refresh in flight plus one pending dirty edge.
- command confirmation converges through the same owner.
- the fast active polling ladder is retired.
- one ~30 s reconciliation/liveness watchdog remains intentionally. Observation degradation is loud (`[MEDIA_EVENT][DEGRADED]` / missed-event evidence); there is **no silent fast-poll fallback**.

## Acceptance Evidence

Multiple installed runs, including the 2026-09-01 long diagnostic sessions, repeatedly re-established native observation across runtime generations and reported summaries such as:

```text
stale_rejected=0
missed=0
degraded=False
```

Operator-observed track/playback reactions were prompt. The high refresh count in those runs tracks native timeline/event edges, not a resurrected one-second polling cadence.

## Binding Lesson

When a provider has a trustworthy event contract, event observation should feed the existing accepted-state owner rather than create a second model/controller. Keep a slow reconciliation watchdog for missed-event/liveness detection, make degraded observation conspicuous, and never silently restore a high-frequency fallback poller.
