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

The former ordinary-only scalar has now been split correctly at the presentation
property seam without adding another animation owner:

```text
QuickStartupRevealCoordinator (rendering/quick/startup_reveal.py)
  one generation-scoped scalar, one bounded QVariantAnimation, no repeating timer
-> DisplayManager._apply_quick_startup_reveal_opacity
   -> QuickDisplayPresenter.set_startup_reveal_opacity
      -> ordinary QML root startupRevealOpacity
   -> QuickSceneController.set_visualizer_startup_reveal_opacity
      -> Visualizer root startupRevealOpacity

ordinary root opacity   = family fadeOpacity * startupRevealOpacity
visualizer root opacity = authoredSceneOpacity(scene_fade) * startupRevealOpacity
```

This matters because Steam families legitimately own local lifecycle fades. The
old implementation reused `fadeOpacity` for the generation reveal, allowing a
family-local `fadeRequested` publication to set that same property back to 1 and
briefly punch through before the shared reveal. The independent multiplicative
gate makes that structurally impossible.

## Area 1 — residual pre-fade widget flash

**2026-09-01 PHYSICAL VALIDATION FAILED — repair pending.**

The attempted independent gate did not stop the same Steam-family startup flashes in the operator run. The code below describes the intended ownership shape, not accepted behavior. The next repair must identify the actual first-visible frame/admission seam rather than adding Steam-specific delays.

The common retained root now has an independent startup gate. No Steam-specific
patch exists: every ordinary family is fenced by the same property and the
Visualizer has the corresponding root gate. The ordinary presentation host also
retains the current gate value and stamps it **plus any explicit initial family
fade value** onto a new root before that root is parented into the scene, so
delayed family construction cannot flash at either QML default between reveal
samples. Immediately before reveal the coordinator re-projects zero and recounts
live roots, so a family that finishes construction during the desktop crossfade
still joins the shared reveal. A family may continue to own its real lifecycle
fade/readiness while the generation gate is closed.

Acceptance: no family is visible for even one frame before the coordinated reveal
begins; especially watch Achievement Pulse and Abandonment Issues.

## Area 2 — Visualizer startup synchronization

**2026-09-01 implemented / AWAITING PHYSICAL VALIDATION.**

The shared generation scalar now reaches the Visualizer root while preserving the
Visualizer's single authored `scene_fade` authority as a separate multiplicand.
No visualizer renderer, logical runtime, bridge, pacer or content shader receives a
new clock. This closes the former ordinary-only fan-out seam without weakening F/R-69.

## Area 3 — desktop -> application crossfade reveal

**2026-09-01 PHYSICAL VALIDATION FAILED — repair pending.**

The operator observed **no desktop -> first-wallpaper crossfade at all**, while the same startup widget flashes remained. Do not describe the current implementation as accepted. The next repair must prove that the desktop capture is actually the first presented retained source and must preserve the accepted R-63 non-exact-cover/1 px overscan window geometry during the entire startup presentation; never create an exact-cover startup-only path that can re-admit fullscreen-flip behavior.

A transparent top-level window is not needed. On the target Windows/Qt path, the
hidden display's `QScreen.grabWindow(0)` can snapshot the currently composed screen
before SRPSS exposes any Quick window. This ceremony is admitted only for cold
application runtime generation 0; later Settings/runtime replacement generations
must not masquerade as a new application launch. The implementation therefore uses the same
retained image/transition path rather than DWM underlay transparency:

```text
selected QScreen while SRPSS window is hidden
-> QScreen.grabWindow(0) once
-> deep-copied PresentationImage startup staging source
-> publish staging source into the already-owned retained BackgroundRenderItem
-> show the same Quick window
-> first processed wallpaper arrives
-> force canonical Crossfade, 1300 ms, staging source -> first wallpaper
-> transition_finalized installs destination and calls _on_image_displayed
-> only when ALL selected displays have authoritative first wallpapers
   + readiness does QuickStartupRevealCoordinator start the 1800 ms widget gate
```

The staging source is deliberately excluded from `current_images`, queue/history
truth and `has_presented_image()` admission. This lets the engine still regard the
wallpaper as the first semantic image while giving the transition renderer a real
source. First-image finalization discards the startup-seed marker; the transition
run then releases its immutable source normally.

No recurring timer, polling loop, cover window, second surface, transparent-window
opacity animation, `processEvents()` pump, or steady-state owner was added. Desktop
capture failure is emitted as an ERROR and the display takes the explicit old
no-seed first-image publication path; it is not silently replaced by another
presentation mechanism.

### Physical acceptance for Area 3

1. SRPSS launch should appear to remain on the current desktop, then smoothly
   crossfade to the first wallpaper; there must be no black/old-image/underlay gap.
2. Widgets remain fully absent throughout the base crossfade.
3. After the base crossfade completes on all selected displays, ordinary families
   and Visualizer begin the same gentle coordinated reveal. Family-local readiness
   may keep genuinely unavailable content hidden, but nothing may appear early.
4. Multi-monitor startup must not leak one display's capture onto another.
5. Normal later wallpaper transitions remain Settings-authored; the forced Crossfade
   is startup-only and must never enter random/transition-selection semantics.
6. Opening/applying Settings or another runtime replacement in the same application
   session must not recapture the desktop or replay the desktop -> wallpaper ceremony.

## What must remain true

- One widget-reveal owner, one startup-gate scalar and one bounded one-shot reveal animation; the base phase reuses the existing retained transition owner rather than adding a second reveal clock. No new timer/pacer.
- Reveal is presentation-only; it never changes image identity, semantic state, or
  render/content cadence.
- Reveal completion still fires exactly once per generation (`startup_reveal_completed`).
- The visualizer and Bubble authored cadence/fidelity are never traded for reveal cosmetics.
