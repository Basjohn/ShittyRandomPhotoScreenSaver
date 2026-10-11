# Transition Change Checklist

Quick transition presentation is the current production path. Use this for future transition changes.

## Geometry and shader negative controls from retired minor incidents

- Random selection or rotation never rewrites the operator's authored transition direction; session choice is separate from Settings persistence.
- Circular/angle-dependent transitions must not treat wrapped `atan` angles as monotonically linear across the branch cut; inspect the wrap seam at representative aspect ratios.
- Animated noise fields (including Melt) require spatial continuity: chaotic floating-point hashes can diverge between compiler/precision paths and make obvious rectangular cell boundaries; prefer deterministically defined lattice hashes with tested interpolation and end states.

## Canonical flow

```text
canonical transition registry/settings
-> activation + manual/random admission
-> resolved immutable request
-> TransitionRequest / TransitionRun
-> lazy Quick implementation
-> display QSGRenderNode
```

No new transition may depend on `GLCompositorWidget`, QWidget pixels or a compatibility presenter.

## Settings: one spec per transition

A transition's Settings page is declared once, in `rendering/transition_settings.py`: its Direction
choices with the codes they resolve to (and the order Random draws from), its page controls in
order (`Number`, `Toggle`, `Choice`, `Colour`) and its closed Advanced bucket. From that spec:

- the Transitions tab builds, hydrates, saves and signal-blocks the page and fills the shared
  Direction box; widgets are named `<section>_<field>_<spin|check|combo|btn>`;
- request admission (`parameter_resolution.py`) clamps numbers to the same ranges, admits choices
  and their retired spellings (`aliases`) the same way and resolves directions through the same codes;
  `spec.page_values()` hands every page number and toggle to the renderer under its own name;
- `tests/test_transition_settings_spec.py` checks the spec owns exactly its defaults section, the
  registry and spec agree, admission clamps to the page's ranges, and the real tab builds, saves and
  reloads every control; `test_transition_direction_labels.py` renders every offered side label.

Adding a transition's Settings therefore touches the registry descriptor, the canonical defaults
(its section, activation, duration and pool entries), its spec, and its resolver (usually three lines:
`_spec_inputs`, `page_values`, any colour or code mapping). Values never go in the spec. A page whose
controls no spec type describes (sliders with value labels, colours with alpha, controls that show or
hide each other: Blinds, Particle, Burn) sets `custom` and provides `_build_<section>_group`,
`_hydrate_<section>_page` and `_save_<section>_page`, listing its own fields in `custom_fields`.

## Retired transition presentation

All canonical transitions have Quick implementations. The old `transition_factory`/GL-compositor pixel stack and its presentation helpers are retired and absent from current source. They are not visual-reference authority and must not be reconstructed to satisfy stale tests or old documentation. Historical failure mechanisms belong in `Docs/Historical_Bugs/`.

## Preserve

- canonical transition ids/settings;
- application activation semantics;
- manual vs Random-pool semantics;
- deterministic invalid-state recovery;
- `TransitionRequest` / `TransitionRun` monotonic/exactly-once behavior;
- authored effect math/shaders/parameters used by Quick;
- exact endpoints;
- GL state/resource hygiene.

## Activation

Activated/deactivated is distinct from:

- manual selection;
- Random pool membership.

Effective Random candidates:

```text
activated ∩ saved pool membership ∩ runnable/hardware
```

Do not execute a deactivated Crossfade as a silent fallback.

## Timing

Use authored per-effect timing.

No:

- catch-up;
- paint acknowledgement;
- producer/display divisor;
- per-transition physical frame timer;
- easing used to hide cadence defects.

## Rich effects

Preserve actual authored behavior. Do not replace 3D Block Spins, Particle, Burn or other rich effects
with simplified lookalikes.

See `Docs/Architecture/Compositor_Architecture.md` and `Spec.md` for the durable retained transition contracts.

## Display geometry (R-63 overscan)

A transition draws at `frame.logical_size`: the background item's size. That is the monitor's device-exact rectangle
inside the R-63 window (at 150% a 2560 px monitor is 1706.67 logical px, while `display_bounds()`, Qt's rounded screen
geometry, says 1707) and, before the window's native rectangle is known, the whole overscanned window.
Anything computed for a run outside the renderer (COMPUTE-prepared geometry, caches, per-display aspect or pixel
math) must key on the renderer's own size (`QuickDisplayUnit.transition_logical_size()`), never on the monitor
rectangle, or it silently never matches and the render thread rebuilds it every run (R-95: Glass froze 43–141 ms).
A prepared-work bar must prove a *hit* when the render size differs from `display_bounds()`, not just that preparation ran.

## GL ownership

Every implementation restores touched state and owns/releases context-local resources legally.

Keep exception-path state restoration tests current.

## Future change gate

Choose the smallest falsifiable set:

- registry parity;
- activation/lazy dormancy;
- request/settings resolution;
- endpoints/midpoint behavior;
- parameter sensitivity;
- interruption/exactly-once completion;
- generation fencing;
- prepared-work hit when the render size differs from `display_bounds()` (when anything is prepared off the render thread);
- resource cleanup;
- GL-state restoration;
- focused real-GL/eyes-on evidence when the visual claim requires it.
