# H Media Event Observation — Physical Smoke (2026-09-01)

Repo implementation under review: `2e7a9242dabbc838c5ac212e57c25a269f8cf23f`.

The short installed run supplied after the event-driven GSMTC migration is strong enough to absorb the architecture while leaving the broad frozen/provider-switch gate open.

Observed across four runtime observation lifetimes:

- native Spotify GSMTC observation established every time with `manager_events=2` and `session_bound=True`;
- real timeline and playback dirty edges arrived and drove the shared refresh path;
- event bursts coalesced (`coalesced=3` in the busier lifetimes);
- every retirement summary reported `stale_rejected=0`, `missed=0`, `degraded=False`;
- repeated Settings/runtime reconstruction re-established observation cleanly;
- `screensaver_qml.log` contained zero Qt/QML messages for the entire run;
- final application exit was clean.

The one startup warning (`slow shared refresh total_ms≈2203`, `worker_ms≈46`) is activation wall time and is not evidence that the retired 1–2.5 s steady poll has returned. The run's steady Media refreshes correspond to activation/native events/reconciliation rather than a one-second recurring truth cadence.

Still `AWAITING PHYSICAL VALIDATION`: explicit provider switching, heavier CUSTOM Save/Continue/reload churn, installed/frozen teardown, artwork/provider identity, and cross-display Visualizer playback binding. No unexplained `[MEDIA_EVENT][MISSED_EVENT]`, stale-generation publication, leaked token, or late native callback is acceptable.
