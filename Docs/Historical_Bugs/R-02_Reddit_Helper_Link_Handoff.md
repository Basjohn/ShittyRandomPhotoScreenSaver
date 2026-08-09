# R-02 — 2026-04-08 / 2026-04-09 — Reddit Helper Link Handoff Fails In Real Screensaver Runtime (Resolved)

## Classification

- [ ] COMPLETELY FUCKED
- [ ] PARTIAL
- [ ] AWAITING VALIDATION
- [x] SOLVED

- **Final resolved state:** real runtime success now holds with a durable reusable scheduled task named `SRPSS_RedditHelper`, interactive-only launch authority, normal saver exit, helper-side shell polling, and post-handoff self-exit. The queue/clipboard fallback behavior remains secondary.
- **2026-07-28 recovery follow-up:** the original launch-authority fix remains healthy: the installed task is still interactive-only, its latest observed result was `0`, and recent queued links reached the helper. A separate recovery/ownership family is now active in `Current_Plan.md`: both helper log writers are unbounded, `.bridge_ready` is rewritten as a hard availability gate, runtime-created ProgramData paths do not have an installer-owned least-privilege ACL contract, and queue terminal/debris retention is incomplete. The current healthy machine snapshot has a broad inherited `BUILTIN\Users` write shape across the shared tree; regardless of how that ACL arose, it is not an acceptable packaged repair because the same tree contains the helper executable and an `open_settings` command spool. Keep Task Scheduler authority intact while P0 replaces the fragile storage/recovery layer.
- **What finally worked:** the winning launch-authority model is:
  - saver writes queue entries and exits normally
  - saver may refresh a benign ProgramData session ticket while active, but that ticket never gates saver shutdown
  - Windows Task Scheduler owns helper launch authority in the logged-in user desktop
  - the task definition is durable and reusable; only the helper process is ephemeral
  - helper waits for shell readiness independently, opens the URL, and exits itself
- **Actual final technical solution:** Task Scheduler registration uses native COM XML registration with `InteractiveToken`.
  - the XML owns the principal `UserId`
  - the COM registration call passes empty user/password variants
  - runtime starts the task with `schtasks /Run`
  - helper/browser launch remains shell-native (`os.startfile` first)
- **Why the final solution worked:** it cleanly separated responsibilities.
  - saver no longer tries to birth or manage the helper from the active saver desktop
  - helper no longer influences saver exit timing
  - Task Scheduler provides the user-desktop launch authority without a 24/7 resident process, token tricks, or repeated runtime prompts
- **Key failed methods worth preserving:**
  - persistent Windows-login helper: rejected because it kept the helper alive outside actual screensaver use
  - click-path helper bootstrap on the same Reddit exit click: regressed into a black/dark-grey cursor-only trap while helper waited for shell readiness
  - saver-desktop preload/spawn, even detached: still regressed into black-screen/dead-Winlogon behavior
  - `schtasks /Create` as the registration authority: kept pulling user-task registration back toward password-oriented semantics and failed for this product shape
  - COM XML registration with `encoding="UTF-8"` in the XML declaration: failed because the XML was being passed as a Unicode COM string
  - COM XML registration while also passing user/password args into `RegisterTask(..., TASK_LOGON_INTERACTIVE_TOKEN)`: failed with credential/logon errors because the XML already owned the principal
- **Useful supporting work that remained part of the fix:**
  - removed the app-driven shutdown race that could kill the session helper before deferred URLs became eligible
  - removed the legacy `HKCU\Run` startup helper path
  - kept MC direct-open behavior separate from real SCR helper authority
  - added ProgramData breadcrumb logging for packaged diagnosis
  - added a best-effort clipboard copy of clicked Reddit URLs as a non-blocking fallback only
  - shortened secure-desktop queue delay from `11.0s` to `3.0s`
  - shortened helper shell-settle wait from `1.0s` to `0.75s`
- **Repo-side proof/harness now available:** `python tools\reddit_helper_task_harness.py --action smoke-test --task-name SRPSS_TaskHarness_Test`
  - this locally proved register/query/run/delete of the same native task-authority layer used by the installer/runtime
- **Observed final validation evidence:**
  - installed task now queries successfully as `\SRPSS_RedditHelper`
  - task is `Interactive only`
  - real runtime success has been observed
- **Takeaways:**
  - do not let helper state leak back into saver teardown logic
  - do not trust preview/script success as proof of real SCR behavior
  - for this feature family, Windows launch authority matters more than queue semantics once queueing already works

## Record Provenance

This standalone file preserves the complete former inline `R-02` record from `Docs/Historical_Bugs.md`. The chronology and technical claims are retained from that source; only heading normalization, standalone-link retargeting, and removal of monolith-only section dividers were applied during extraction.
