# Current Plan — Qt Quick Production Migration

Last updated: 2026-08-30

## Current checkpoint

G is independently audited and accepted. The H production-authority cutover and
legacy physical-host deletion landed, but **H closure is narrowly reopened** by
post-cutover audit + the first real source-mode runtime reality run. I is blocked
until the demonstrated deterministic runtime defects below are corrected and a
short operator smoke passes.

Exact pushed `main` at the time these runtime-reality tests were authored is
`bd27f903cbc6ae793e25bfb8092f0e9211caef30`. That checkpoint had re-declared
H CLOSED after the routing/failover correction, but the preserved real runtime
evidence below narrowly reopens H until its demonstrated live seams are fixed:

```text
9dcb02be  caller-proven legacy physical presentation host deleted
bc8fd6a   Quick visualizer admission restored to canonical effective monitor routing
6f88cca   neutral Visualizer CUSTOM 30 s failover/reclaim lifecycle re-homed
28e95d6   DisplayManager wired the re-homed failover/reclaim lifecycle
bd27f90   docs re-declared H CLOSED after that bounded correction
```

The previous structural H deletion checkpoint passed the maintained
`h-destination` profile 60/60. That remains useful structural evidence, but the
real runtime run below proved the profile did not yet falsify several live
product seams.

The first post-swap runtime evidence is preserved at:

```text
logs/evidence_chest/08_30_RuntimeSwap_03_37/
```

Its own `[SOURCE_HEAD]` records `427eafed8cff8b932bc64efee964764ce3f02260`,
so that run **predates** both `bc8fd6a` and `6f88cca`. Do not use the runtime run
to claim those two later routing/failover corrections failed. Re-audit them on
exact current source, then leave them alone unless current evidence reopens them.

The production architecture itself remains the accepted destination:

```text
selected display
-> DisplayManager semantic orchestration
-> one QuickDisplayUnit
-> one QuickDisplayRuntime
-> one standalone threaded QQuickWindow
-> one retained Quick scene
-> one display-owned WidgetRuntimeManager
-> canonical capability + per-instance monitor admission
-> retained ordinary/CUSTOM/input/context/auxiliary/transition owners
-> zero-or-one admitted visualizer edge per display
-> exactly one product-level visualizer owner across participating displays
```

The old `DisplayWidget`/GL-compositor physical presenter remains deleted. These
corrections are not permission to restore it, add a compatibility facade, or
create a second owner/pacer/presenter.

## Active task — H post-cutover runtime-reality corrections

Detailed evidence and boundaries are in:

`Docs/QtQuick_Migration/H_Post_Cutover_Runtime_Reality_Corrections.md`

Work the smallest demonstrated owner for each defect. Verify exact current
source first because the evidence run predates the two visualizer routing/failover
commits above.

### A. Already landed; audited on current source, not redone

- [x] Canonical effective visualizer monitor routing outside vs inside CUSTOM
  landed at `bc8fd6a`.
- [x] Permanent E2.7 Visualizer CUSTOM 30-second grace/fallback/reclaim state
  landed at `6f88cca`.
- [x] Independently audited both on exact current source: routing + failover +
  remote-capability focused suites are **44/44 GREEN**; no redo needed.

### B. Deterministic runtime failures exposed by `427eafed` — CORRECTED

All four demonstrated seams are fixed and GREEN via
`tests/test_qtquick_runtime_reality.py` (now in the `h-destination` boundary;
whole profile **64/64 GREEN**). The context-menu click is delivered through the
`QQuickWindow` delivery agent (`sendEvent`) because `QTest.mouseClick`'s OS input
queue hangs/crashes this environment's window; that is the same real path that
reproduced the self-dismiss, so the gate is strengthened, not weakened.

- [x] **Live visualizer retained delivery** (`adcfd96d`): the owner never passed
  the optional `request_present` callback and `set_presentation` only dirties the
  item on geometry/style change, so successive logical revisions never re-ran
  `updatePaintNode` (`sync_count=1`). Wired `request_present ->
  scene_controller.request_visualizer_present -> item.update()`; the display
  frame pacer remains the sole GUI sync opportunity (no second cadence owner).
- [x] **Transition replacement/interruption** (`cad4e6d2`): a valid image during
  an active run now cancels that run to its authored destination exactly once
  (`CANCELLED_TO_DESTINATION`) and starts the replacement from that source; the
  controller fences the superseded run's stale completion. No black clear, no
  bare reject.
- [x] **Visible retained context menu** (`747e3140`): the opening right-click
  flipped `menuVisible` true, which made the dismiss scrim visible, and the same
  press was re-delivered to that scrim's `onPressed`, self-dismissing the menu
  (anchor set, `visible=False`). The scrim is now armed only after the opening
  event completes (`Qt.callLater`, one-shot). Verified through the delivery-agent
  path: opening press keeps the menu open; a subsequent click still dismisses.
- [x] **Visualizer diagnostic-state initialization** (`da3dafab`):
  `install_default_logical_tick_state` now installs `_last_tick_spike_log_ts=0.0`
  and `_dt_spike_log_cooldown=0.75` (legacy defaults), so the delegated tick path
  no longer raises `AttributeError`.

The focused deterministic gate supplied with this plan is:

```powershell
pytest tests/test_qtquick_runtime_reality.py -q --tb=short
```

Remaining H re-closure gate: the source-mode operator smoke below. H is NOT
closed and I is NOT started until that smoke passes on real displays.

## H -> I runtime reality gate

Before I is admitted, perform one short source-mode operator smoke against the
exact corrected checkpoint. This is deliberately **not** a new benchmark or a
large test project.

Required smoke:

1. cold start and wait for both displays' intentional first frames;
2. confirm the visualizer visibly evolves for several seconds, not merely that
   logical cadence telemetry advances;
3. open the retained context menu on a real display, leave it visible, execute
   one harmless action, then enter and cancel CUSTOM;
4. request Next once, then request Next again while that transition is still
   active; no exception, stuck transition or black handoff;
5. open/close Settings so the display generation recreates, then click/focus
   between both displays;
6. exit normally and confirm process termination.

If that smoke exposes a reproducible deterministic ownership/routing/action
failure, keep H open and fix the smallest owner. Visual ugliness without a
broken deterministic contract is recorded for J instead.

## Explicit J evidence from the first runtime run

The same `427eafed` run also exposed issues that should **not** be mixed into the
bounded H corrections unless current evidence proves a deterministic contract
failure:

- frequent visible black flashes at startup, focus/click and transition edges;
- no operator-visible gentle widget fade despite a `fade_reveal_completed`
  telemetry milestone;
- inconsistent refresh-spiral presentation between widget/header surfaces;
- several ordinary widget content/outer-size relationships looked wrong;
- transitions fundamentally rendered but looked visually flaky.

J must treat these as named acceptance cells, not vague "visual parity" debt.
The first run showed why cross-layer proof matters:

```text
ready/reveal telemetry fired        != operator saw a clean fade with no black flash
logical visualizer cadence is 90 Hz != retained pixels visibly evolve
context-menu model accepted input   != the operator can see/use the menu
```

A one-shot widget-layout diagnostic at startup/recreation is desired for J:
widget id, effective display route, preferred content size, final outer rect,
CUSTOM override if any, DPR and clamp result. It must not become polling or a
per-frame geometry stream.

The near-hang on exit is **not currently evidence of Quick retirement failure**:
the observed display/process/thread teardown completed in the 03:10:07 second;
the final ~2 seconds were logged pycache cleanup before normal exit code 0.
Re-test shutdown in J, but do not redesign Quick teardown from that observation.

## I residue reconciliation — blocked until H runtime reality gate is GREEN

When H is re-closed, I remains the intentionally boring source-driven cleanup
phase:

- [ ] derive the exact post-H residue inventory from imports/callers and the
  complete-tree collection diagnostic;
- [ ] preserve/re-home only surviving neutral/Quick contracts from old-owner
  tests; delete pure retired-presenter assertions;
- [ ] remove caller-dead old-presenter adapters, aliases, tools, logger routes,
  comments and migration spikes with no destination consumer;
- [ ] restore clean full-tree collection and broad-suite authority;
- [ ] keep `Docs/TestSuite.md`, `Future_Cleanup.md`, `Index.md` and `Spec.md`
  current after material residue slices.

I must not "clean up" the new H runtime-reality tests or the retained physical J
smoke cells merely because their filenames/ancestry are old.

## Binding invariants

- One selected physical display owns one standalone `QQuickWindow`, one
  retained scene and one display runtime/service owner chain.
- No `QQuickWidget`, second accelerated surface, hidden QWidget presenter,
  software/QRhi fallback presenter or presentation screenshot facade.
- No duplicate legacy/Quick production presenter, provider/service manager,
  visualizer controller/source/logical runtime/mailbox/render bridge or CUSTOM
  owner.
- Python owns semantic/settings/provider/runtime truth; QML consumes bounded
  presentation state and emits semantic actions.
- Ordinary family admission resolves activation/effectiveness, instance
  `enabled`, and canonical effective `monitor` routing before construction.
- Outside CUSTOM the visualizer follows canonical effective Media monitor
  routing; committed CUSTOM layout may own the visualizer's persisted route.
- CUSTOM keeps committed geometry separate from temporary working geometry;
  visualizer committed viewport extent remains authoritative outside editing.
- Visualizer authored cadence remains presentation-independent; the display's
  existing Quick frame pacer is the sole GUI synchronization opportunity.
- Transition interruption/replacement must remain exactly-once and must not use
  a black clear as an ownership shortcut.
- Old generation admission closes and logical work joins before legal
  scene/window retirement; generation `0` remains valid.
- Fallbacks are fail-loud, product-authorized and destination-owned; old
  presentation code is not a fallback.

## Deferred J acceptance

J owns compiled/installed and physical acceptance after H/I. Follow
`Docs/QtQuick_Migration/Remaining_J_Final_Installed_Acceptance_Decomposition.md`.
The first post-swap runtime observations above are now explicit J inputs.

The two real-physical-display cells in `tests/test_qtquick_runtime.py` remain J
evidence. Do not weaken/delete them merely to manufacture an I broad-suite pass.

## Unrelated debt

`Future_Cleanup.md` is authoritative. Do not re-admit unrelated Settings theme,
Reddit helper or retired Presets work unless exact current callers make it part
of the active correction/cleanup boundary.
