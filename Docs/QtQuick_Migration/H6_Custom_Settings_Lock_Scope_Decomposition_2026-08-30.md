# H6 Technical Decomposition — CUSTOM Settings Lock Scope

Date: 2026-08-30  
Starting source: `af8896b52fbee153fe1cd0b627a55455c14625d1`

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
media_playback_progress_enabled
media_playback_progress_height
media_playback_progress_shadow_enabled
media_playback_progress_glow_enabled
media_playback_progress_glow_color_btn
media_spotify_volume_enabled
media_mute_button_enabled
```

Some of those controls can still be disabled by their own normal dependencies. Example: glow colour may be disabled when glow itself is off. That is legitimate and must remain.

## Current symptom

Physical Settings shows seek/progress/glow-related features greyed merely because Media is in CUSTOM.

Because `_refresh_custom_resize_lock_state()` only iterates descriptor `control_attrs`, this suggests the observed lock is outside the canonical Custom resize descriptor.

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

Supplied:

```text
tests/test_custom_resize_lock_scope.py
```

It pins descriptor intent and should be GREEN even before the physical bug is fixed.

Add a Settings-level test for the actual regression once the secondary owner is found:

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

Also test a legitimate dependency-off case so the repair cannot become “force-enable everything.”
