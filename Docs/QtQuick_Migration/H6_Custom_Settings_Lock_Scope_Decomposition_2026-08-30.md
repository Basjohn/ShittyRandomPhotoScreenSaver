# H6 Technical Decomposition — CUSTOM Settings Lock Scope

Date: 2026-08-30  
Starting source: `af8896b52fbee153fe1cd0b627a55455c14625d1`

Checkpoint status (2026-08-31): **source/runtime-shaped GREEN. H is now closed; this file is historical decomposition, not a live physical-revalidation queue. Any surviving global-CUSTOM acceptance debt is owned by `Current_Plan.md`.**

## Contract

CUSTOM commits layout geometry. Settings controls whose values directly author that committed size may be locked so two owners do not fight.

CUSTOM does **not** make ordinary semantic/appearance controls immutable.

For Media, current descriptor authority already says the CUSTOM size lock is exactly:

```text
media_font_size
media_artwork_size
```

Examples that CUSTOM itself must not lock:

```text
media_show_controls
media_show_album
media_show_playback_state
media_playback_progress_enabled
media_playback_progress_height
media_playback_progress_shadow_enabled
media_playback_progress_glow_enabled
media_playback_progress_glow_color_btn
media_spotify_volume_enabled
media_mute_button_enabled
```

Some of those controls can still be disabled by their own normal dependencies. Example: glow colour may be disabled when glow itself is off. That is legitimate and must remain.

## Reported symptom

Physical Settings shows seek/progress/glow-related features greyed merely because Media is in CUSTOM.

Because `_refresh_custom_resize_lock_state()` only iterates descriptor `control_attrs`, this suggested the observed lock was outside the canonical Custom resize descriptor.

## Current-source result

The bounded audit found no second CUSTOM disable owner:

- `_refresh_custom_resize_lock_state()` iterates only the canonical descriptor controls;
- Media progress/glow state is owned only by the ordinary transport/progress dependency refresh;
- Media app-volume state is owned only by provider capability refresh;
- the normal profile persists the reported state: `Custom`, Spotify, and transport/progress/glow/volume/mute all enabled;
- a real `WidgetsTab` loaded with that exact state reports only `media_font_size` and `media_artwork_size` disabled. Every listed feature control and its relevant parent remain effectively enabled.

No production force-enable change is justified by current evidence. The former physical observation remains an operator revalidation gate; if it recurs, capture control, parent/grandparent enabled state and style state before changing ownership.

## Investigation order

For each affected control, capture one bounded state tuple before and after CUSTOM selection/load:

```text
control.objectName / attr
control.isEnabled()
parent.isEnabled()
grandparent.isEnabled()
normal dependency inputs
custom_resize_lock_active
```

Then inspect:

1. parent bucket/container `setEnabled(False)` calls;
2. Media-specific “update progress controls” dependency function;
3. order of `_load_settings()`, `_refresh_custom_resize_lock_state()`, and Media dependency refresh;
4. stale UI state retained through lazy Settings page hydration/reload;
5. any second historical Custom lock path outside descriptor authority.

## Repair rule

The fix should remove only the **CUSTOM-derived** disabling of non-size controls.

Do not solve by indiscriminately calling `setEnabled(True)`, because that would break provider/feature dependency gating.

Prefer one canonical re-evaluation order:

```text
load semantic values
-> evaluate normal feature/provider dependencies
-> apply CUSTOM size lock only to descriptor-owned size controls
```

or an equivalent owner-specific solution.

## Regression

Permanent deterministic coverage:

```text
tests/test_widget_descriptors.py
tests/test_widgets_tab.py
```

The descriptor test pins the two-control metadata. The real Settings-level regression now loads:

```text
Media position = Custom
show_controls = True
progress_enabled = True
glow_enabled = True

font size disabled
artwork size disabled

progress toggle enabled
progress height enabled
glow toggle enabled
glow colour enabled (subject to glow=True)
volume/mute toggles enabled subject to provider capability
```

It requires font/artwork disabled while progress toggle/height/shadow/glow/colour and volume/mute remain enabled. Existing transport-off and unsupported-provider tests pin legitimate dependency-off behavior so this cannot become “force-enable everything.” The full pair passes `126/126`.
