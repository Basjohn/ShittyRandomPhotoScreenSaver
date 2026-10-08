# R-110 | Refresh animator turned network latency into an unbounded Qt Quick render storm

**Status:** SOLVED / REGRESSION-PROTECTED / PERF-PHYSICALLY ACCEPTED 2026-10-08

## Trigger

The refresh-accessory parity side quest gave Reddit, Gmail and Feeds a retained QML `RotationAnimator` that ran for the entire already-published `refreshing` state. The glyph looked correct in source and the broad Windows gate passed, but cold startup and the Settings replacement generation could make the machine feel frozen for roughly ten seconds.

The affected installed run used SRPSS's intentionally retained Qt Quick `swapInterval=0` surface policy. R-86 already proved that forcing generic interval-1 VSync is not an acceptable global repair for SRPSS's mixed-refresh multi-window workload.

## Evidence

The 2026-10-08 operator capture is unusually clean:

- cold startup reached roughly **871 scene swaps/s** during the authored reveal, then remained roughly **230-460 swaps/s** for the network-refresh window even though Bubble logical revisions were about **90/s**;
- the scene finally settled to about **90 swaps/s at 01:00:40** after the long startup refresh work completed;
- after closing Settings, the replacement scene was already transition-idle but still ran roughly **451-575 swaps/s from 01:03:23 through 01:03:33** while logical Visualizer revisions remained about **90/s**;
- Gmail logged `Fetched mail unchanged` at **01:03:33** and the very next PERF_HUD sample at **01:03:34** dropped to about **90 swaps/s**;
- the retained QML tree contained exactly three `RotationAnimator` / `Animation.Infinite` sites, all three added by this refresh-parity slice.

That timing separates the defect from image decode, Settings construction and Visualizer DSP. Network latency was merely holding `refreshing=True`; the QML animator converted that state lifetime into continuous scene dirtiness. With an uncapped swap surface, Qt rendered the 4K scene as fast as it could instead of at the approximately 90 Hz logical demand.

## Root cause

`RotationAnimator` is a presentation cadence owner even when its target is only a 30×30 glyph. In a retained Qt Quick scene the animation invalidates presentation continuously. Binding an infinite animator directly to an asynchronous network state therefore couples arbitrary network duration to full-scene render duration.

The mistake was architectural, not a slow Gmail implementation: **a tiny accessory animation was allowed to become an independent render-loop owner**.

## Repair

Remove every per-widget infinite refresh animator. Keep the accepted visual parity and make the state transition itself shared:

- bounded 30×30 refresh target;
- 72% glyph sizing;
- matching border / hover language;
- `↻` when idle;
- `◌` while the provider's existing BUSY fact is true;
- one **240 ms display-scoped `RefreshTransitionClock`** owned by the retained ordinary-widget host;
- one shared `RefreshStateGlyph.qml` used by Reddit, Gmail, every NEWS/CUSTOM Feed instance, and Games You Follow;
- simultaneous edges join the already-running epoch instead of starting or restarting per-widget animation;
- once that short epoch ends, a provider may remain BUSY indefinitely with **zero refresh-transition activity**.

The clock uses one bounded Qt `QVariantAnimation`, not a QML loop, timer, polling owner, network scheduler or per-card animator. This is the deliberately narrow exception to the general no-extra-cadence rule: one display owner, fixed 240 ms lifetime, dormant at rest, and consumer-count invariant.

Games You Follow previously had the visual refresh action but no published BUSY fact. Its generation-shared Steam followed owner already had the authoritative `_in_flight` state; that fact is now delivered to active leases on submit/complete/failure and projected by the presentation model. No second worker, deadline or source owner was created.

A future truly rotating busy glyph remains rejected unless it can prove the same bounded/count-invariant render behavior.

## Permanent regression

The refresh regression set now protects both negative and positive architecture:

- every refresh accessory uses `RefreshStateGlyph.qml` and the display's `refreshTransitionClock`;
- no family refresh block and no shared glyph contains `RotationAnimator`, `Animation.Infinite`, `NumberAnimation` or `Timer`;
- the shared clock is bounded to 240 ms and idle at phase 1;
- **32 callers joining while active remain one epoch**, proving widget/feed-instance count does not create animation owners;
- a later edge after rest creates exactly one new epoch;
- Games You Follow publishes BUSY from its one generation-shared `_in_flight` owner to every active display lease without additional worker submission;
- NEWS and CUSTOM feed multiplicity is covered structurally because all configured feed IDs use the one `FeedPresentation.qml` family component and every retained root receives the same per-display clock.

The installed runtime PERF_HUD remains the physical oracle: source/unit proof can show bounded ownership but cannot prove the compositor/driver's actual swap behavior.

## Physical acceptance

Run a diagnostic cold start and one Settings close/reinit with Gmail, Reddit, Games You Follow and several NEWS/CUSTOM Feed cards enabled where practical. Trigger several manual refreshes close together so multiple BUSY edges overlap. The one display-scoped 240 ms epoch may briefly add bounded presentation work, but once it rests, PERF_HUD scene/draw cadence must settle to the normal active logical demand even if one or many providers remain BUSY. Additional simultaneous feed instances must not multiply or prolong the transition cadence.

Do **not** repair recurrence by changing global swap interval; R-86 already rejected that path physically.

## Acceptance evidence

The follow-up 2026-10-08 operator run with the shared edge clock showed no negative Visualizer feel and no return of the old provider-lifetime render storm. Scene-rate excursions were short edge/edit bursts rather than hundreds of swaps per second for the duration of Gmail/Feeds BUSY state, while Visualizer logical revisions remained around their normal cadence. The operator specifically reported no observed negative side effect. Q2 is therefore accepted with the bounded/count-invariant architecture above remaining the permanent guardrail.
