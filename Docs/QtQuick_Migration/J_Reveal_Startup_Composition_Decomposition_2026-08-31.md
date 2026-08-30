# Reveal / Startup Composition Decomposition

Date: 2026-08-31

Successor to the (now solved) recurring black flash. This decomposes how a display
goes from nothing to full application state, and the consistency of that reveal
across widgets. This is J Parity+ quality, not H correctness — but it is grounded
in real owners and one operator-observed bug, so it is decomposed rather than left
as generic "gentle fade" polish.

Do not reintroduce any removed black-flash experiment (deferred first-show,
event-driven surface-refresh). Do not add a second surface, cover window, repaint
loop, timer/cadence, or presentation owner. The fixed overscan / present-mode
contract (`R-63`, `QuickDisplayWindow._fullscreen_compat_geometry`) stays intact.

## Reveal ownership (current)

```text
QuickStartupRevealCoordinator (rendering/quick/startup_reveal.py)
  one generation-scoped opacity scalar, one QVariantAnimation (bounded, one-shot),
  no repeating timer/pacer; publishes `completed(generation)`.
-> DisplayPresenter.set_family_fade_opacity(opacity)   (display_presenter.py)
   presentation-only fan-out over `bound_widget_ids` (the ORDINARY families)
-> each family presentation.set_fade_opacity(opacity)
-> OrdinaryWidgetPresentationHost.set_fade_opacity -> QML root `fadeOpacity`
```

The base image and the visualizer are NOT in `bound_widget_ids`:

- the base image is the retained `BackgroundRenderItem` (its own render node);
- the visualizer is the separate retained visualizer owner + render bridge, which
  `startup_reveal.py` explicitly leaves its "independent authored startup/fade
  authority."

## Area 1 — residual startup micro-flash (low priority)

Operator sees at most ~1 barely-perceptible flash on startup, not consistently
reproducible: the show-before-first-rendered-frame interval on the LG output,
distinct from the solved activation flash. Not a standalone concern.

- Promote only if it becomes consistent, or fold it into Area 3.
- Any first-frame gate must be MEASURED (PresentMon / `[QUICK_SURFACE]`), never
  assumed, and must not resurrect the failed deferred-show.

## Area 2 — visualizer does not fade in on startup (reveal-consistency bug)

**Observed:** ordinary widgets fade in; the visualizer pops in.

**Seam:** the coordinated reveal scalar fans out only over `bound_widget_ids`, so it
never reaches the visualizer; the visualizer's own "independent authored fade
authority" does not fade it in on the fresh-frame admission path.

Decompose before fixing:

1. Confirm the exact visible behavior (instant pop vs a different authored curve
   that only looks like a pop).
2. Locate the visualizer's own reveal/opacity authority, or prove it has none on
   the fresh-frame admission path.
3. Choose ONE owner:
   - (a) extend the coordinated reveal scalar to the retained visualizer item's
     ROOT opacity — a presentation-only fan-out like the family one; **preferred**
     for consistency;
   - (b) drive the visualizer's existing authored fade from the same
     generation-scoped reveal completion.
4. Add a regression: the reveal scalar reaches the visualizer item's root opacity
   and `completed` still fires exactly once.

**Invariants:** presentation-only opacity; fade the ROOT opacity only, never the
visualizer's render/content timing; one source/logical runtime/pacer; stale-
generation fencing and fresh-frame admission preserved; all-five visualizer
fidelity preserved (do not regress F).

## Area 3 — desktop -> application crossfade reveal (aspiration, optional)

**Operator aspiration, only if achievable cleanly; NOT required for H.**

```text
existing desktop (last composed frame)
-> crossfade into the application base image/state
-> widgets fade in AFTER the base is presented (staggered on their own fade)
```

1. **Feasibility first.** Under DWM the app cannot read the desktop's pixels, so a
   true desktop->app crossfade likely means presenting the app initially
   transparent and raising base opacity — which risks the desktop showing through
   (an underlay-leak class, the same family the historical GL underlay work
   guarded against). Capture the composed output and measure before committing.
2. If feasible, base-image reveal and widget reveal become two ORDERED PHASES of
   the same `QuickStartupRevealCoordinator` (base first, then the family +
   visualizer fan-out) — not two owners.
3. This subsumes Areas 1 and 2, but only as ONE coherent reveal contract.

**Hard constraints:** one retained window/scene; no second/cover surface; no
repaint loop; the fixed overscan/present-mode contract stays intact; the base
image must never expose an invalid/underlay frame while opacity ramps (measure).

## What must remain true

- One reveal owner, one scalar, one bounded one-shot animation; no new timer/pacer.
- Reveal is presentation-only; it never changes image identity, semantic state, or
  render/content cadence.
- Reveal completion still fires exactly once per generation (`startup_reveal_completed`).
- The visualizer and Bubble authored cadence/fidelity are never traded for reveal cosmetics.
