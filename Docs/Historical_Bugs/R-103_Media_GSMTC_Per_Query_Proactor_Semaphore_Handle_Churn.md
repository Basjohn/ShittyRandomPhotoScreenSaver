# R-103 — Media/GSMTC Per-Query Proactor Context Ratcheted Semaphore Handles

**STRONG RETENTION VALUE DOCUMENT**

**Status:** SOLVED (2026-10-02). The retained Media affinity lane now retains its WinRT/async query context too.

## Symptom

A long runtime showed steadily rising main-process handles. Early correlation made the growth look almost one-for-one with image transitions, but handle-type attribution later showed **Semaphore** growth even across windows with no image change.

## Root cause

The Media/GSMTC path already had a retained affinity lane, but each query created a fresh Windows `asyncio` `IocpProactor` event loop and requested a fresh GSMTC manager. In one short run roughly 224 Media affinity jobs corresponded to roughly 225 fresh Proactor loops. The repeated kernel-backed query context, not image presentation/SHM, was the real churn owner.

## Fix

- Lazily retain one Proactor event loop and one GSMTC manager on the Media owner lane.
- Reuse that context for repeated queries/reconciles/commands.
- Tear it down deterministically on the same owner thread.
- Dormant Media does not acquire the context just because the capability exists.

## Acceptance / negative controls

- Focused test: 100 queries reuse one retained loop and manager.
- Windows integration test: 200 real GSMTC queries do not reproduce a process-handle ratchet.
- Subsequent runtime evidence showed the pre-FEEDS-parser Semaphore baseline flat (`330 -> 328 -> 330`) rather than climbing.
- Do not infer ownership from two periodic counters that happen to share cadence; require handle type/event ownership evidence.

This incident is separate from R-84's older replacement-generation handle question.
