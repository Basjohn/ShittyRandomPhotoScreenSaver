# Current Plan

Last updated: 2026-06-05

This file tracks active work only. Ongoing architecture truth belongs in the reference docs, while dated severe/complex bug narratives belong in `Docs/Historical_Bugs.md`.

## Guardrails
- Keep this aligned with `Spec.md`, `Index.md`, `Docs/Guardrails.md`, and `Docs/Historical_Bugs.md`.
- Prune validated work aggressively. Do not let this become a changelog.
- Keep harnesses/probes intact unless explicitly asked to retire them.
- Treat `presets/visualizer_modes/` as authored content. Tests may validate schema/index/repair behavior, but must not force exact creative values.
- Do not close visual/runtime bugs from tests alone when symptoms are user-visible.
- Prefer stronger runtime-shaped automation over helper/proxy checks when live behavior is the complaint.

## Active Tasks

- [ ] Re-close the CUSTOM visualizer geometry contract around settings-exit rebuilds before touching custom sizing logic again.
  - [ ] Reproduce and trace the exact settings-exit mismatch shown in the 2026-06-05 `--geo` run:
    - pre-settings runtime logs healthy visualizer placement at `geom=(30,249,600,400)` then `geom=(30,217,600,400)`
    - after the `17:30:41-17:30:42` rebuild, visualizer `CFG create/refresh` lines still fire but the normal `Positioned visualizer widget geom=...` line disappears while `spotify_volume` is repositioned immediately to `geom=(660,220,32,284)`
    - this is the core evidence to keep anchored to, not the older frozen-rect/custom-envelope experiments
  - [ ] Audit the CUSTOM visualizer runtime path end-to-end without changing the contract first:
    - saved custom route / monitor owner
    - `Custom+ALL` recovery path
    - `custom_routing=True` visualizer creation
    - `WidgetManager` positioning branch
    - preferred-height deferral while CUSTOM is active
    - post-settings rebuild/reapply order versus volume/media
  - [ ] Prove whether the visualizer shell is failing to position, positioning off the wrong owner monitor, or being resized after positioning; add/keep only diagnostics that directly answer that question.
  - [ ] Keep the actual contract explicit while debugging:
    - CUSTOM routing stays decoupled from media
    - the saved CUSTOM visualizer rect is still a maximum envelope preview, not a frozen live rect
    - authored preset/mode size deltas must still resolve inside that envelope
    - edit preview and saved runtime geometry must match

- [ ] Re-close Bubble from the restored `510520e` baseline without reintroducing complexity.
  - [ ] Validate the current single small-lane support/source changes against live runtime and keep them only if they materially improve small-bubble participation without harming the restored big-bubble life.
  - [ ] Use the current runtime logs as the Bubble oracle target before adding more signal-path work.
    - Latest live evidence still says the small lane is the blocker: loud windows with strong source energy such as `raw_bass=1.902` / `2.015` are still publishing weak bars (`~0.08` / `~0.15` max), while the restored big lane now at least keeps obvious life.
    - Treat the restored `510520e` + Dynamic Noise Floor behavior as the minimum baseline to protect while tightening the oracle; do not let the oracle drag Bubble backward again.
  - [ ] Tighten the Deep Sea oracle upward from the current floor guard so it matches present runtime behavior as closely as possible under synthetic/runtime-shaped replay, especially small-lane soft/loud participation and vocal/snare lift.
    - In the 2026-06-05 run, `Preset 1 (Deep Sea)` only held for a few seconds (`17:31:18-17:31:21`), so the useful baseline from that window is startup/reset behavior rather than a full phrase:
      - dynamic floor on, manual floor `0.10`, `input_gain=0.350`, `sensitivity=0.400`, `block=128`
      - first fresh-frame render after reset reached `display_max=0.177`, `display_avg=0.114`
      - dynamic floor ramped from `applied=0.184` to `0.626` within roughly two seconds while the transient bus stayed quiet (`onset=False`)
    - Use that as the minimum “alive under restored baseline” floor, but do not pretend this run alone is enough to model a sustained Deep Sea loud section; a longer single-preset capture is still needed before tightening beyond that.
  - [ ] Add the deferred Bubble interpolation / motion-blur option cleanly if runtime still wants it after the signal path is stable.
  - [ ] Keep Bubble options/settings propagation complete if interpolation lands: UI buckets, settings model, serializer, defaults, preset payloads, and `/tools` support must all stay in sync.
  - [ ] Keep changes one visible seam at a time: after each significant Bubble change, compare runtime and oracle before stacking another.

- [ ] Re-close visualizer paused/idle startup behavior so reveal authority stays correct without poisoning first-frame guards.
  - [ ] Re-validate that the paused/idle reveal path does not weaken the first-frame guardrails for playing startup or mode/preset reset paths.
  - [ ] Keep watchdog logging diagnostic-only; it must never become reveal authority again.
  - [ ] Keep the current dual-display startup/cadence evidence attached to this task:
    - latest run had clean first-frame commits on both screens at startup and rebuild (`screen=0` and `screen=1`)
    - no `FIRST_FRAME_GUARD` or reveal-watchdog expiry appeared in this run
    - but routine preset/mode churn still emits repeated `MODE_RESET_ASSERT` plus `FIRST_FRAME_PRIMER` lines, so re-check whether that volume of reset logging is still expected diagnostic noise or an unresolved reset-order issue

- [ ] Re-validate the small set of still-open runtime safety checks around recent visualizer/widget work.
  - [ ] Confirm same-track media metadata still does not refit/reformat title or artist due to non-visible churn.
  - [ ] Confirm single-display MC focused-input readiness is still good, while leaving multi-display focused-key ownership explicitly open until real multi-display validation is available.
  - [ ] Re-check the low-grade visualizer latency warnings during routine mode/preset churn:
    - latest run still logged `lag_ms≈94-95` for `sine_wave` and `bubble` with `pending=<none>`
    - keep paused-idle spam fixed, but verify these remaining warnings still correlate to real churn rather than stale lag state

- [ ] Restore image-cache / prescale performance to a healthy runtime contract when Bubble is no longer the blocking interactive problem.
  - [ ] Validate cold-start scaled-hit behavior, early manual-next worker fallthrough, and whether cache-side work still correlates with shared cadence stalls in `--perf`.
  - [ ] Re-run clean `--perf --cache` validation after the next cache-side fix and confirm shutdown summaries show real scaled/raw reuse while `ImageWorker prescale` spikes materially drop.
  - [ ] Treat any renewed startup flicker, wrong backing/shadow behavior, or first-frame mismatch as an automatic rollback condition for cache work.

## Watchlist
- Better repro still needed for current CUSTOM-layout regressions that are not yet visible enough in logs alone:
  - CUSTOM `media` resize can over-scale artwork and erase the preferred gap used for the global volume button, while non-CUSTOM media remains correct. Current logs do not capture enough geometry/payload evidence to tell whether the fault is in `media_scale` payload persistence, resolved custom size application, or live widget reapply after settings exit.
- `--noupdates` is behaving correctly in logs, but the fresh-cache startup-skip branch still needs one normal-mode validation run because this `--noupdates` session can only prove cached content loads plus automatic fetch suppression.
- Non-`Custom` authored stacking remains explicit opt-in and must stay default-off until a future re-audit proves the planner respects real authored screenshots plus `--geo` traces.
- If `--perf` is enabled and a transition watchdog or compositor-complete failure reappears, check `rendering/gl_profiler.py` / `rendering/gl_compositor.py` before treating it as a transition-runtime regression.
- Keep visualizer preset/settings drift in view during later audits:
  - preserve CLEAR-then-APPLY semantics
  - do not reintroduce a second post-overlay merge phase
  - do not reintroduce entry-point-specific fallback behavior for visualizer settings

## Deferred / Not Active
- Multi-display compositor/desync/startup-order validation stays open but deferred until real multi-display runtime is available again.
- Secure-desktop long-runtime exit reliability stays deferred until the current interactive visualizer/widget regressions stop blocking day-to-day validation.
- Future authored runtime oracles for Spectrum `Preset 1 (Organs)` and Spline Curve `Preset 1` should follow the stronger Bubble bar pattern rather than weak generic guards.
- Rain Drops / Blinds cleanup stays deferred unless current runtime evidence shows fallback or dead-path behavior is actively harming users.

## Documentation Rule
- Architecture: `Spec.md`
- Module map: `Index.md`
- Policy: `Docs/Guardrails.md`
- Dated regressions: `Docs/Historical_Bugs.md`
- Drift-check routine: `Docs/Documentation_Maintenance.md`
- Harness reference: `Docs/Harness_Index.md`

#######
### User Task Box: NEVER remove this box/section, only integrate its tasks into the active plan and then remove the text BELOW prompting the tasks.
----
----
######
