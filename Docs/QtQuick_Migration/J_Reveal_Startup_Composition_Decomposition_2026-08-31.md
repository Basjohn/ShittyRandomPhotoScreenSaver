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

**2026-09-01 VISUALIZER SKIP FIXED + PHYSICALLY VALIDATED. Ordinary-family flash not reproduced in recent single-display runs — keep watching.**

Instrumenting the actual first-visible boundary (single-display `main_mc` hijack runs with `[STARTUP_TRACE]` logging) proved the orchestration was correct — every ordinary root is created before prime and rides the `startupRevealOpacity` gate — and isolated the real defect to the **Visualizer**, which alone "skipped" its fade:

- the visualizer's GL bars are drawn by a custom `QSGRenderNode` whose content opacity is `u_fade = presentation.content_fade`; the node ignored the QML root's inherited opacity, so `startupRevealOpacity` faded only the card *shell* while the GL bars rendered at full opacity through the reveal and popped;
- the visualizer's authored scene fade was never wired into the Quick presentation (`scene_fade`/`content_fade` were flat `1.0`), so it had no fade of its own on any activation.

Fix (Qt Quick-native, no legacy QWidget/`ShadowFadeProfile`/`push_spotify_visualizer_frame` resurrection):

1. `rendering/quick/visualizer/node.py` folds `QSGRenderNode.inheritedOpacity()` (authored scene fade x generation reveal gate) into `content_fade` at the single `render` seam, allocating a rebased immutable presentation only while genuinely fading. The GL content now fades in lockstep with the card and honours the coordinated startup reveal.
2. `widgets/spotify_visualizer/quick_display_visualizer_owner.py` eases `scene_fade` 0→1 (smoothstep, `_ACTIVATION_SCENE_FADE_DURATION_S`) once per activation, sampled through the existing pacer-driven `sync_present` + transition clock — no new timer. This is the visualizer's own single scene-fade authority; it covers the race where the heavy first frame lands outside the coordinated reveal window.

Regression bars: `tests/test_qtquick_visualizer_fade_authority.py::test_render_node_folds_inherited_opacity_into_content_fade` and `::test_owner_scene_fade_eases_from_zero_on_activation`.

The code below describes the ordinary-family gate ownership shape, which continues to hold.

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

**2026-09-01 PHYSICALLY VALIDATED WORKING in current source.**

The earlier "no crossfade at all" was from a prior build. In the current tree, single-display `main_mc` runs and operator eyes-on both confirm the desktop -> first-wallpaper crossfade: `[STARTUP_DESKTOP] Seeded hidden Quick scene …` (real desktop dimensions), then `[STARTUP_DESKTOP] Crossfade admitted … duration_ms=1300`, then the coordinated widget reveal. The seed lands in `scene_controller.presentation_image`, so the first authored wallpaper resolves the crossfade branch rather than the direct-publish path. The R-63 non-exact-cover / 1 px overscan window geometry is untouched. Continue to watch multi-display cold starts for consistency; no exact-cover startup path was introduced.

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
