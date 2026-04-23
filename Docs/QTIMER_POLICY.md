# QTimer Policy

Last updated: 2026-04-23

Use QTimer only for UI-thread timing work. Use ThreadManager for background work.

## 1. Allowed QTimer Use
- UI debounce in settings dialogs.
- Deferred UI work on next event-loop tick.
- UI animation/fade scheduling that is explicitly UI-thread owned.
- Small UI-state coordination timers tied to widget lifecycle.

## 2. Not Allowed for QTimer
- Network polling.
- File/IO background work.
- Compute-heavy work.
- Long-running retries/backoff loops.

These belong in `ThreadManager` IO/compute tasks.

## 3. Implementation Rules
- Mark intentional UI-thread timers clearly in code comments.
- Ensure recurring timers are stopped/cleaned during teardown.
- Avoid hidden timer proliferation in deep widget internals when shared lifecycle helpers exist.

## 4. Regression Prevention
Before adding a timer, verify:
- why it cannot be event-driven,
- why it cannot run in ThreadManager,
- teardown path prevents orphaned timers,
- tests cover lifecycle and timing-sensitive behavior.
