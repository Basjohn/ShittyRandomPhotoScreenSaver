# R-62 — Transition-Scoped Presentation Deferral Degraded Bubble

Date: 2026-08-17
Status: Rejected on fidelity; reverted to the approved anchor

## Commits

```text
approved anchor (restored):   30e66e08
rejected candidate:           8eb381fb
revert on main:               b6e3e051
preserved evidence:           logs/evidence_chest/08_17_8eb381fb_p2_transition_deferral_REJECTED/
```

## Observed Failure

Installed manual review reported **Bubble worse in every relevant way**. Under
`Docs/Guardrails.md` §1 visualizer fidelity and reactivity outrank every counter, so this fails
the acceptance gate regardless of delivery numbers. `Current_Plan.md`'s checkpoint policy and
`Docs/Guardrails/Visualizer_Presentation.md` both require immediate rollback rather than
retuning in place.

## What The Candidate Did

Deferred auxiliary overlay presentation **only while the transition render strategy was
running**, restoring one-request-per-publication when it paused:

```text
no transition / paused  -> unchanged, one request per accepted publication
transition active       -> integrate every publication, mark latest render state
                           dirty, present on the strategy's frame opportunity
```

It avoided every mechanism on the R-27 blacklist: no producer gate, no pending-until-paint
admission, no `paintGL()` self-update, no requeue timer, no source throttling. Logical
integration ran for every input. Deferral tracked the strategy lifecycle so a paused source
could not strand the overlay (the R-61 defect).

It was still wrong.

## Cause

### 1. The presentation source was disqualified to begin with

`Current_Plan.md` and `Docs/Guardrails/Visualizer_Presentation.md` state that a presentation
source must be live whenever the visualizer is live, and name `AdaptiveTimerStrategy` as
transition-scoped and therefore ineligible. A revision of
`Docs/Presentation_Change_Preflight.md` — written during the R-61 cleanup — asserted that
while-active-only use was acceptable because R-61 barred only *sole* dependence. That claim
contradicted the plan and the focused guardrail, and it is now withdrawn.

**`AdaptiveTimerStrategy` is not an eligible presentation source in any scope.**

### 2. The edge bypass probably did not protect the real Bubble edge

The bypass fired on a **rising kick/snare event strength** in the incoming publication. But the
protected Bubble response recorded in the v1 golden is authored on one tick and becomes visible
in the **Bubble positional payload on the following tick**
(`kick_authored` at tick 3, `visible_edge` at tick 4).

So the immediate request could fire one publication *before* the visible edge, leaving the edge
itself eligible for coalescing. The test that covered this asserted only that the bypass fired
— not that the real Bubble edge survived presentation. It looked like edge coverage and was not.

This remains the leading hypothesis and must be confirmed against the preserved logs before any
new design.

### 3. The candidate was narrower than the stated goal

`Current_Plan.md` P2 requires removing the one-publication → one-auxiliary-update requirement.
The candidate deliberately retained 1:1 outside transitions. Even had it passed review, it could
not have closed P2 without evidence justifying a deliberate narrowing of the goal.

## Process Lessons

- **A green bypass test is not edge coverage.** A test asserting that a protection *triggered*
  proves nothing about whether the protected thing *survived*. Any future edge protection must
  assert against the actual Bubble positional-payload edge from the v1 golden, on the tick where
  it becomes visible.
- **A register of past failures must not grant eligibility.** The preflight document's job is to
  record disproven mechanisms. When it began ruling on what was *permitted*, it manufactured a
  contradiction with the plan and the focused guardrail, and an implementation was built on it.
- **P1's mixed-refresh bar is an architectural model, not runtime proof.** It models the target
  state as the visualizer adding zero independent GUI dispatch demand. A candidate that still
  issues `update()` from a separate `QOpenGLWidget` — merely at different moments — does not
  satisfy that model, and green P1 tests do not establish runtime equivalence.

## Retained From The Attempt

- Logical integration before presentation; no source/event/cadence reduction.
- No paint acknowledgement, pending-until-paint admission, producer timestamp gate,
  display-rate divisor, or second visualizer clock.
- Worker-thread callers must marshal Qt work to the GUI owner.
- Bubble short-lived responses must remain visible.
- Phase 8 remains deferred; P3/P4 attribution remains required.
- The measured defect is unchanged and still real: `update_requests / set_state == 1.0000`
  across both modes, overlay painting ~31% above what a 60 Hz display can present, ~1.7 ms CPU
  p95 per overlay paint.
