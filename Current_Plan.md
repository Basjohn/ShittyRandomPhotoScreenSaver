# Current Plan

Last updated: 2026-04-30

This file tracks active work and near-term validation. Completed implementation detail belongs in a compact ledger, not as the main working surface.

## Guardrails
- Keep this aligned with `Spec.md`, `Index.md`, `Docs/Guardrails.md`, `Docs/Historical_Bugs.md`, and `Docs/Gmail_Widget_Plan.md`.
- Keep harnesses/probes intact unless explicitly asked to retire them.
- Treat `presets/visualizer_modes/` as authored content. Tests may validate schema/index/repair behavior, but must not force exact preset names, slots, or creative numeric values.
- Do not close visual/runtime bugs from tests alone when symptoms are user-visible.
- Avoid broad focus, window-flag, compositor, visualizer, or Qt effect/shadow rewrites unless the current task directly requires them.

## Active Priorities

### Gmail Widget
Primary plan: `Docs/Gmail_Widget_Plan.md`.

Current status:
- Gmail is a normal feature, not dev-gated.
- IMAP/app-password is the primary supported backend; OAuth/REST remains optional/advanced.
- Normal and MC Gmail link opening works.
- Mark Read/Unread, Spam, and Delete work in runtime reports.
- Archive remains the only action that repeatedly fails. Treat it as a Gmail IMAP capability/research question, not a local guessing target.
- Gmail refresh/paint has first-pass caching and transition contention mitigation. Recent fix also covers refreshes already in flight when a transition is requested.
- Settings dialog creation flicker is fixed in live use; keep R-18 guardrails active for future settings work.

Near-term targets:
- Runtime-validate the latest Gmail/Reddit refresh contention fix from fresh `/logs`: in-flight refresh + manual transition should suspend spinner repaint and defer apply until transition idle.
- Rebuild/inspect final normal and MC artifacts for Gmail logo, envelope, action icons, refresh visual, and notification sound from ProgramData.
- Run a concise Gmail defaults/security/build audit after packaging changes: no credentials or OAuth local secrets tracked or bundled.
- Runtime-check display polish only where screenshots still show issues: header/logo alignment, unread/read envelope distinction at 16px, date modes at practical widths, sender/subject column alignment.

Deferred Gmail targets:
- Thread grouping/conversation display remains default-off until researched. Prefer `X-GM-THRID`, split read/unread groups, and decide collapsed-row action semantics before implementing.
- Archive may not be viable through Gmail IMAP in modern Gmail for this account/build path. Do not keep changing it without a source-backed finding or a small diagnostic harness that proves the exact accepted command.
- Low-priority shared stretch: open Gmail/Reddit links on monitor index `0` when cleanly possible, with fallback to current behavior.

### Reddit Widget
Current status:
- Refresh spiral no longer triggers normal-build URL exit.
- Refresh spiral queues guarded refreshes, respects fetch-in-progress, defers start/result/cache regeneration during pending/running transitions, and suspends live spinner repaint if a transition starts mid-refresh.

Near-term targets:
- Runtime-validate Reddit spiral refresh in normal and MC builds: no link-exit unless a real URL is clicked, one queued refresh after transition idle, spinner stops cleanly.

### Visualizer
Current status:
- Spline Curve/DevCurve specular now fades out while idle/paused and fades back in on playback using the runtime specular alpha multiplier.

Guardrails:
- Do not touch visualizer timing/mitigation paths as a side effect of widget performance work.
- Keep preset tooling/schema and runtime behavior aligned as visualizer modes evolve.

Near-term targets:
- Preset repair/reindex round-trip checks after visualizer schema changes.
- Assess `card_height.py` and whether a centralized sizing contract can replace scattered multipliers without bleed or visual regressions.

### General Runtime
Open watchlist:
- Mute button fade-in reliability under startup event pressure.
- Transition random mode actual distribution vs expected uniform over 50+ rotations.
- Settings destructive-flow checks: reset/import when touching settings architecture.
- Settings cache stale-read behavior after section/root writes.

## Historical Ledger
- U-05 MC Keyboard Focus / Ctrl Halo Runtime Input Family resolved on 2026-04-25 by wiring `_restore_mc_input_focus` into click routing. User validated media keys, `C`, and `S` after manual click in MC mode.
- Cursor halo side effect from focus restore was fixed by re-raising the halo after `DisplayWidget` focus restoration.
- MuteButtonWidget fade-in race was fixed by replacing bespoke opacity animation with `ShadowFadeProfile`; keep the pattern documented in `Docs/Historical_Bugs.md`.
- Gmail foundation, settings UI, defaults, sound packaging guardrails, row/link routing, menu ownership, date modes, text cleanup, cache ordering, header parity start, stable-content cache, and transition-aware refresh deferral have been implemented.
- Reddit refresh control click classification and guarded refresh path have been implemented.

## Latent Focus Architecture Risks
These remain risky and should be handled only when a focused task justifies them:
- Assess/fix general focus policies on overlay widgets.
- Assess GL compositor focus policy.
- Assess focus-restore reason consistency.
- Assess global Raw Input registration vs per-window.
- Assess halo focus interactions.
- Assess activation-refresh contract.
- Audit post-show `setWindowFlag()` calls.

## Documentation Rule
- Architecture: `Spec.md`
- Module map: `Index.md`
- Policy: `Docs/Guardrails.md`
- Dated regressions: `Docs/Historical_Bugs.md`
- Gmail implementation plan: `Docs/Gmail_Widget_Plan.md`

## Idea Box/Problem Box
0. CRITICAL, ADD AS HIGH PRIORITY TASK. Two sided issue. First all widgets except for Gmail have a natural anti shadow corruption cadence at some point, gmail lacking it means that it sticks out when this triggers. Other side, shadow/shadow cache corruption is now happening extremely often when clicking into the app in MC mode on Display 1 and then clicking into anything on Display 0. Clicking back in fixes it because of our mitigations (which are great) but we should see if there are ways to permanently solve this issue without ruining/altering fidelity with research compared against our historicals (careful not to regress MC focus which finally fixed our keys!) and even if not investigate why it now suddenly happens on every focus loss. (Is this only detectable by my eyesight? Why do we not log shadow corruption if not?)

1. Add a lightweight doc-drift check for stale references between `Spec.md`, `Index.md`, `Current_Plan.md`, and `Docs/Gmail_Widget_Plan.md`.

2. Add a small harness smoke command list for recurring investigations.

3. Add a transition-distribution logger that reports session skew at shutdown.

4. Archive button still appears in the triple dot menu when using Imap despite being disabled.