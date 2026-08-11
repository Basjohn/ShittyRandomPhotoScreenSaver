# R-60 — ImagePresenter DPR Split Rekeyed The Retained Current Texture

Date: 2026-08-11
Status: Resolved In Code, Installed Timing Validation Pending

## Classification

- [ ] COMPLETELY FUCKED
- [ ] PARTIAL
- [x] AWAITING VALIDATION
- [ ] SOLVED

## Observed Failure

On repeated steady transitions, the compositor retained the terminal destination
texture, but the next transition did not find it as the old texture. Exact telemetry
showed `next_old_key == retained_key + 2`, so `generic_pair_warm` allocated and uploaded
both old and new instead of uploading only new.

## Root Cause

`DisplayWidget` owned the live display DPR (`1.5` in the canonical run), while
`ImagePresenter` kept its independent construction default (`1.0`) and was never
synchronized. The presenter changed the destination to `1.0` before texture warm and
retention. After terminal retention, display completion changed it to `1.5` and
presenter completion changed it back to `1.0`. Those two real `QPixmap` mutations
advanced the cache identity by exactly two revisions before the pixmap became the next
old image.

## Fix

`ImagePresenter` now reads the parent display's authoritative DPR whenever it accepts a
pixmap and calls `setDevicePixelRatio()` only when the value actually differs. The
texture manager key scheme, per-compositor/context ownership, generation handling,
budgets, retention policy and deletion paths are unchanged.

## Bars

The production-shaped presenter/texture-manager regression reproduces the former `+2`
identity change, then requires the retained destination key and texture ID to survive
as the next old image with one old cache hit and only one following-image upload. The
focused display/texture/compositor suites pass, and the 45-cycle Phase 4 resource
harness still retains one terminal texture/PBO and returns owned bytes to zero on
strict resets.

## Remaining Runtime Validation

Repeat identical installed transition sequences and require `old_cached_before=true`,
one new upload, lower `generic_pair_warm`/setter/request-age tails, and no increase in
terminal texture or PBO count. Context or generation recreation, physical size or
DPR/transform change, cancellation that retains old, and a genuinely different final
pixmap remain deliberate invalidation boundaries.

## Guardrail

One display-local DPR owner must feed every pixmap lifecycle helper. Do not repair an
identity miss by broadening the cache key, retaining historical textures, crossing
compositor/context generations, or weakening teardown.
