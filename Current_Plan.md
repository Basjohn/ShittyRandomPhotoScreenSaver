# SRPSS | Current Plan

## NEWS provider probation log (run once per day)

Run `python tools/feed_probe.py --catalog` once per calendar day and add one row (newest first). **Satisfied** for a category when two independent providers have each passed on at least 6 of 7 separate days, every pass `via=direct` (a discovery rescue means the endpoint moved: update the candidate, restart its count), and neither provider's newest item is older than 72 h on its last three runs. Only then may that category's NEWS widget be admitted (`Docs/Future_Work/Feeds.md` § NEWS provider probation).

| Date | US (CBS, ABC) | World (CBS, ABC) | Politics (CBS, ABC) | Tech (CBS, ABC, Ars) | Gaming (Ars, PC Gamer) | Notes |
|---|---|---|---|---|---|---|
| 2026-09-24 | ok 30 / ok 25 | ok 30 / **FAIL** empty feed | ok 30 / ok 25 (newest 16 h) | ok 30 / ok 25 / ok 20 | ok 20 (newest 47 h) / ok 50 | 10/11; all direct. CBS images 0 = parser gap (item-level `<image>URL</image>` unread), not absent art. |

Tally toward 6/7 days: US 1/1 both; World CBS 1/1, ABC 0/1; Politics 1/1 both; Tech 1/1 all; Gaming 1/1 both.

## FEEDS | Custom 1 closure and bounded family expansion (ACTIVE)

**Authority:** `Docs/Reference/Feeds.md` owns implemented architecture. `Docs/Future_Work/Feeds.md` owns the still-pending expansion/deferred work. Continue to audit **durability, content adaptability and performance neutrality** before multiplying sources or widget identities.

### Accepted current-tree evidence

- [x] `feeds_custom_1` is the only admitted FEEDS runtime widget. It uses the shared bounded RSS/Atom transport/parser/cache/source/runtime path, retained List/Grid/Compact QML, HTTP/S-only external actions, event-admitted local artwork and the ordinary shared Edit/CUSTOM owner.
- [x] The requested consolidated Windows regression gate is green on the current tree. Do not retain older focused pass counts as current acceptance evidence.
- [x] Physical Custom 1 artwork editing is accepted for free X/Y/width/height adjustment, with Grid text/content reflow following the changed artwork geometry rather than preserving a fixed landscape slot.
- [x] Physical source adaptability has exercised an image-sparse Hacker News feed plus image-bearing GitHub and Ars feeds. Image absence is a valid feed/content state, and tested story links reached the correct external destinations.
- [x] Product-wide clickable highlighting is physically accepted on the current tree: semantic colour is the resting/state language and an admitted active click target uses bright white where the shared contract calls for a border/separator/emphasized text cue. Text-dense row surfaces remain borderless where specified; Media retains its no-hover-border exception.
- [x] Website-address discovery is physically accepted (2026-09-24): `arstechnica.com` resolved to its feed in Custom 1. Standards-based, no per-site rules; `Docs/Reference/Feeds.md` § Feed discovery.
- [x] Custom 1 closure is physically accepted (2026-09-24): full Edit transaction (alignment flip, resize, child edits, Reset, Ctrl-Z, lock, Save, re-entry, fresh runtime), Show Feed Subtitle off/on with Save/reopen, last-good through an offline restart and reconnect, and disable/replace while work was in flight.
- [x] Modern feed formats are physically accepted (2026-09-24): Mastodon posts read as text titles, Daring Fireball's JSON Feed renders with dates and images, and Reddit resolves through the `.rss` suffix.
- [x] The secure Winlogon handoff remains the external-link authority: saver-side queue admission is the success boundary, helper wake is best-effort, and helper readiness never gates normal saver exit. Reddit/Reddit2, Gmail, FEEDS and Steam-family actions stay behind the same product-action/session boundary rather than calling direct browser APIs from retained runtime code.

### Multi-CUSTOM expansion gate

Custom 2–4 remain dormant until the same shared codepath is proven with more than one active source. Do **not** clone providers, QML, editor state, schedulers or persistence owners.

- [ ] Exercise two simultaneous independent endpoints through refresh, cancellation, one-source retirement and reactivation. Retiring A must not cancel, delay or publish into B; identical endpoints must continue to share one source transaction where privacy/cache identity permits it.
- [ ] Add deterministic Custom 2–4 monogram collision ordinals through the existing cached vector-monogram path, then admit the remaining fixed IDs through the same descriptor/runtime/QML component.

### Independent Games You Follow verification

- [ ] When a newly refreshed syndicated Steam article actually contains its validated original article URL, verify that exact article opens that destination. Older cached records without that URL correctly fall back to the app news hub. This check must not trigger a whole followed-set sweep and does not block FEEDS work.

## Voxel Sphere | isolated energy-floor controls

The independent fragment and particle minimum-energy settings are implemented with curated/default and user-authored preset protection. Focused pure-Python settings/preset gates were previously reported green. The remaining Sphere-specific operator gate is the native Windows settings/preset run and active-music observation of independent floor effects, Reset and Custom Save/reopen. Do not retune authored values on the operator's behalf; promote a reproduced defect here if one appears.

## Future Work transitions | correction and removal

`Docs/Future_Work/Transition_Expansion.md` owns the detailed work; `Docs/Reference/Transitions.md` owns current behavior and controls.

- [~] Crumble's separate crack-formation stage is implemented on real fracture borders before chunk/debris motion; retain solid depth and wall debris. Operator visual acceptance remains open.
- [~] Awaiting operator visual acceptance of Glass, Tiles, Ink and corrected Crumble at authored durations.
- [ ] **Check the other value-noise shaders for cell-boundary seams (R-94).** Ink Bloom, Burn, Diffuse, Crumble, Exploding Tiles, Pixel Accretion, Raindrops and Block Flip hash with `fract(sin(dot(...)))`; render each one's noise field (as `test_melt_field_has_no_seams` does) and switch any that seams to an exact integer lattice hash. Low priority: no seam has been reported outside Melt.
- [~] **Glass collisions / break-again options (operator 2026-09-23).** Implemented, off by default: shards can bounce off each other in flight and crack again (on collision, or ~30% at random without collisions), and a split piece can crack once more; solved once per run at build time. Glass and Melt are activated and pooled by default. Details: `Docs/Future_Work/Transition_Expansion.md`. Physical: turn each option on and judge the look in motion.
- [~] **Crumble control rework (operator 2026-09-23).** Each run now draws a different crack layout (seeded impact/cluster/warp patterns), crack complexity is live over its whole range (irregularity 0.34 → 1.00 across 0.5 → 2.0), and debris varies per run with the amount driving chip count and size. Details and measurements: `Docs/Future_Work/Transition_Expansion.md` §Control rework. Physical: visual acceptance at authored durations on both displays; judge whether the 1.8 default is now too broken.
- [ ] Observe both displays with active music and representative heavy external load; confirm Visualizer freshness and transition first-use behavior against the accepted baseline.
- [ ] Validate the installed/frozen build, material save/reopen/Reset and repeated switch/interrupt/retire.


## Runtime -> Settings replacement lifecycle

- [~] Restore the last Settings top-level tab plus its semantic subsection/builder on every runtime round-trip. Widgets, Visualizers, Display, Transitions and Themes persist semantic selection only; restored content is anchored at the top rather than replaying stale pixel scroll. Native round-trip validation remains open.

Transition terminalization, Visualizer owner retirement and shared Core Audio callback retirement are accepted current contracts guarded by source/tests and `Docs/Guardrails.md`; they are not active-plan tasks unless a concrete regression reopens them.

## Runtime audit 2026-09-22 | accepted 2026-09-23/24

`Docs/Future_Work/Runtime_Audit/` holds the register (00, including the accepted-items table with commits and closing evidence), item detail (01–05), structure and the considered-and-rejected list (06), historical-bug constraints (07) and the open-item evidence (08). The whole admitted queue (TX-01/02, LC-05/06, PR-01/03, PR-04 Stages A+B, PW-01/02/03-Clock/05, VZ-01/03/04/05) is accepted from the 2026-09-23 19:29–19:35 run, earlier physical runs and automated bars; the 19:29 trace also exposed and closed a TX-01 duplicate Glass geometry build.

- Watch: PW-04 Feed model reset (trigger: FEEDS Custom 2–4 physical testing shows delegate/artwork churn). Parked: PR-02 (DC-04 stays documented), PR-01 resolve memo, PR-07, ST-01/02, VZ-05 epoch cache, VZ-07. Closed: LC-01, PR-05, PW-06, PW-03 Media, the prefetch double batch.

## Known failing tests and anomalies (tracked until resolved)

Pre-existing reds and runtime anomalies found while gating the runtime audit. Each stays here until fixed or explicitly retired; do not treat them as noise in a gate.

- [ ] **Pre-existing presentation reds (found 2026-09-24, already red before that day's commits; bisected at `d12b2343`).** `tests/test_qtquick_achievement_pulse_presentation.py` (2): the latest-artwork frame sits at x=161/178 where the authored-region and list-flip bars expect it left of 130 / beyond 217. `tests/test_qtquick_weather_presentation.py` (2): the runtime/fake runtime still holds its presentation consumer after the scene host should have released it. Decide which side is intended, then fix the other.
- [ ] **Reddit runtime tests are order-dependent (found 2026-09-24).** `tests/test_reddit_runtime.py` is green alone (13) but 6 fail when run after `tests/test_reddit_post_provider.py` in one process: shared state leaks between files. Per-file isolation remains the acceptance standard; fix the leak rather than reorder.
- [ ] **Stale Reddit title/age gap bar (pre-existing).** `tests/test_qtquick_reddit_child_committed_reopen_scene.py` (2 tests) expects a 6 px title-to-AGO gap; `RedditPresentation.qml` `titleAgeGap` floors it at 8 px (`max(8, 9 / presentationScale)`). Fails identically on a clean HEAD worktree (2026-09-24). Decide which is intended, then fix the other.
- [ ] **Spectrum extreme-viewport smoothness (pre-existing, not an audit regression).** The 2026-09-23 16:53–17:06 acceptance run saw significantly reduced visual smoothness for Spectrum at extreme viewport shapes. Pre-dates the audit; do not reopen VZ-04 over it. Watch item until investigated separately.
- Evidence runs: 2026-09-22 22:53–22:59 — no native fault; the replacement-construction watchdog armed 13× and never fired. 2026-09-23 D1 soak 09:07–10:40 — no native fault, no QML message, watchdog armed 6× and never fired; one `viz_geometry_mismatches` increment at 10:38:32, which is the fail-closed stale-presentation guard working, not a defect. 2026-09-23 16:53–17:06 acceptance run (two processes, each with a Settings round-trip) — no native fault, replacement watchdog never fired. Note: starting a new `--frame-trace` session replaces the previous session's trace segments; copy them first when a trace must survive a restart.

## Handoff and regression rules

When an accepted behavior changes, select only the relevant targeted tests and physical observations; do not re-accept unrelated OSD, Media or widget systems. Keep full superseding GODZIPs with the canonical three `.godzip/` files, manifest-backed replace/delete instructions and no temporary scripts or compiled artifacts. Test commands belong in chat, not an added documentation file.
