# R-186 | The Settings ink guard kept checked mode-button ink on the same side as its fill, so three themes' checked buttons read at 2.5-3.8:1

**Status:** fixed 11 Nov 2026 (material track 1B.8, before M2). `ui/settings_surface_composition.py` `_correct_ink`
takes `state_ink=True` from `_state_inks` only: a derived checked/hover ink may cross to the opposite pole when neither
raising its alpha nor moving toward its own pole reaches the bar, and only to a colour beyond every location it sits on
(never a grey between a black and a white desktop). Ordinary semantic inks keep their polarity. Regression bars:
`tests/test_surface_opacity_adjust.py::test_real_link_button_uses_state_ink_for_checked_text_and_lock_icon_offscreen`
(the real Linked button, rendered never shown; red before the fix with worst contrast 1.58 against 4.5, green after)
and `tests/test_settings_ink_polarity.py::test_only_a_state_ink_may_flip_polarity_when_its_own_pole_cannot_read`.

## Symptom

On three shipped Settings themes the checked mode button (Linked/Independent and every mode pill sharing
`control.mode.*`) drew its text and lock icon in near-white on a pale checked fill: worst analytic contrast over a black
and a white desktop 2.48 (`Ghost [Single] [Glass]`), 3.79 (`Monochrome Frost [Single] [Glass]`) and 2.86
(`Smoke Quartz [Single] [Glass]`) against the 5.1 the state ink reserves. Nothing failed loudly: the derived ink was
returned as the authored colour at full alpha and the only signal was one red test.

## Cause

`9872ca18` (9 Nov 2026, "5.1.3 RC - Theme Fixes") rightly stopped the ink guard from turning authored white-on-dark
text into a mid-grey that balanced a black and a white desktop: it now moves ink only toward the pole the authored ink
already supports. The checked and hover state inks go through the same function, but they are derived for a *state
fill*, which may sit on the other side of the authored mode text (a light theme's dark checked pill, a dark theme's pale
one). There the own pole cannot reach the bar at all, so the guard gave up and returned the authored ink. The test that
covered exactly this (`944484fe`, 9 Nov) went red with that commit and stayed red on main until this fix.

## Fix and evidence

Only state inks get the second pole, and only after their own pole fails; the flipped candidate must lie beyond every
location (so the competing-extremes case still returns the authored ink). Of the 200 checked/hover inks of the shipped
Settings themes, exactly the three checked inks above change (to near-black, 5.10-5.13:1); every other theme's state
ink is byte-identical. Stills of the checked Linked button before and after, light themes plus Default Dark and
Midnight Cobalt plus the three changed themes, each over its group stack on a black and a white desktop:
`.artifacts/evidence/settings/linked_button/20261111_state_ink/` (`linked_button_checked_{before,after}.png`, numbers
in `linked_button_{before,after}.json`).

## Lesson

A guard written for one family of ink (text over desktop extremes) must say which callers it serves. Derived state
inks share the function but not the premise; give them their own admission rather than a shared rule that silently
returns the input when its premise does not hold.
