# Settings Theme Architecture

Expansion persistence follows the [single-current-context Settings bucket contract](Settings_Bucket_Persistence_Contract.md).
Connector rails show that hierarchy; they do not own its stored editing path.

Durable contract for the QWidget Settings theme system, native backdrop ownership and theme authoring. This document owns the current Settings-theme architecture. Historical investigation belongs under `Docs/Historical_Bugs/`; temporary theme migration notes do not override this contract.

## Product boundary

Settings remains a frameless QWidget/QDialog surface. The top-level Settings widget uses `WA_TranslucentBackground`; on Windows Qt presents that top-level as a layered HWND. Theme implementation must therefore preserve the composition contract that has been physically validated on this actual window architecture.

The theme stack is deliberately split by responsibility:

```text
SettingsThemeSpec / .srtheme
    -> semantic visual request

ui/settings_theme_runtime.py
    -> one active immutable theme + synchronous live notification

ui/settings_theme.py + component QSS/renderers
    -> Qt semantic surfaces, colours, alpha, geometry-preserving selector rendering

ui/settings_dialog.py
    -> shell lifecycle, forged edge/corner renderer, native-mode transition ownership

core/windows/dwm_blur.py
    -> Windows AccentPolicy mechanics only
```

No renderer may invent a second palette because a particular native material is inconvenient.

## Shared text and control painting

QLabel text shadows use the label's already padded `contentsRect`, then its margin and actual indent, followed by the
selected signed shadow offset. Do not add title-bar padding a second time. The shared overlay draws one shadow and
leaves foreground text to QLabel; no per-theme shadow-strength override is permitted.

Shadow-direction arrows consume `control.button.text`. Combo indicators consume the existing `control.stepper.*`
state roles, including disabled state, with the existing explicit Foundry-preview properties retained. Light and dark
surfaces use the same semantic resolution and paint path. Native Glass/Acrylic composition must be inspected; declared
palette contrast alone is insufficient evidence of legibility.

The Settings root projects plain line/spin/combo input text from `control.input.text`; placeholders use that same
colour at half its authored alpha, and disabled text/placeholder roles use `control.input.disabled_text`. Component
surface overrides keep this shared foreground rule. An inherited Windows palette must not leave white input text
on a light semantic surface. This adds no theme field, watcher, surface adjustment or shadow override.

`ui/theme_semantics.py` derives light-palette admission from existing semantic foreground/surface roles; it stores no
theme state. `ui/theme_typography.py` copies authored fonts and adds a real weight increment for light palettes.
Jost uses a private variable family with explicit `wght`, retaining the original static family for dark matching;
other variable families retain their axes, and static families use their nearest stronger installed face.
Settings applies the reversible policy through existing root/shared/lazy style edges, including tooltips. Quick
uses the generation-owned typography input and shared text primitives; opening Settings retires the old factory before
theme changes, so the new runtime receives the new classification. No extra theme watcher or frame-time font scan exists.
Repeated projection must not accumulate weight, replace the stored font choice or change dark glyph pixels.

Runtime text/header-logo shadow softness is an explicit global Settings choice,
`widgets.shadows.soft_text_on_light_themes`, projected once through the existing family styles. It keeps text shadows
enabled under the existing master, signed offsets and opacity. `SoftShadowEffect` supplies one fixed-kernel diffuse
profile, applied to half-resolution shadow-only captures; header logos reuse their existing effect layer. It does not
blur foreground text or alter card backgrounds. Dark palettes and an unchecked modifier retain their original hard
path. Settings-window theme-authored `ShadowStyle` values are unchanged. See the shadow authority in `Docs/Contracts.md`
and the [bounded native validation record](../Audits/Light_Theme_Legibility_2026-10-26.md).

## Schema-v6 contract

`ui/settings_theme_spec.py` owns the compiled `DEFAULT_DARK_SETTINGS_THEME` and schema-v6 semantic vocabulary.

A complete `.srtheme` owns:

- `backdrop.mode`: `off`, `acrylic`, `glass`, `frosted`, `mica` or `smoked`;
- `backdrop.tint`: material tint recipe payload; retained in the schema for all modes, but Glass does not apply it. The tinted materials need non-zero alpha. Frosted, Mica and Smoked derive their material tint from it
  (`NativeBackdropStyle.native_tint`, renderer constants in `ui/settings_theme_spec.py`): Frosted mixes it halfway to
  white at a heavier strength (a milky haze), Mica keeps it near-solid (the wallpaper only faintly through), Smoked
  desaturates and darkens it. They are the card materials' family (`Card_Surface_Materials.md` 3.5) on the Settings
  window;
- the complete semantic colour-role map;
- the complete semantic Settings shadow-role map;
- the complete semantic gradient-role map.

`ui/settings_theme_io.py` admits a file whole or rejects it whole. Current parsing is schema-v6-only after the explicit `ui.settings_theme_input_compat` boundary has promoted an exact supported schema-v5 user file. Unknown/missing roles, wrong format/schema or invalid values do not partially merge into a theme. Compiled Default Dark remains the unconditional no-file/failure fallback.

Schema v6 owns `about.art.liquid`, the Settings-only colour authority for the explicitly masked liquid/background field in `:/srpss/branding/about/Logo.png` and `:/srpss/branding/about/Shoogle300W.png` (sources in `ui/assets/branding/about/`). The companion masks preserve source shading/alpha and leave bubbles, text, outlines, fish shading and drop shadows untouched. New theme generation may seed `about.art.liquid` from `chrome.outer_border` RGB, but these are **independently operator-editable artistic roles** after authoring. Never assert all current themes match one another or pin a named theme's current palette. The role remains explicit/editable in Theme Foundry, not a second runtime inheritance mechanism. Supported schema-v5 user themes are admitted only by `ui.settings_theme_input_compat`: the v5 colour-role set must be exact, then `about.art.liquid` is seeded from `chrome.outer_border` RGB at full alpha and the payload becomes v6 before strict current parsing. No arbitrary missing/unknown role is default-merged.

The persisted theme selection is resolved and validated before first Settings construction. Persistence must never deliberately flash Default Dark before a valid saved custom theme.

## Theme file storage / packaged path authority

Settings Themes and the current Widget Themes (colours plus an optional card material) share one durable **theme root** rather than inventing separate installation trees.

Installed/frozen Windows builds use the same stable ProgramData base used by other SRPSS curated/runtime assets:

```text
%ProgramData%\SRPSS\
    themes\
        *.srtheme
        widgets\
            *.srwtheme
```

Settings GUI themes therefore live directly in `%ProgramData%\SRPSS\themes\`; Widget Themes live in the
`widgets\` child so a large mirrored theme pack does not dump both file types into one directory.

Source/development resolution mirrors that hierarchy:

```text
<repo-root>\themes\
    *.srtheme
    widgets\
        *.srwtheme
```

`ui/settings_theme_paths.py` owns this resolved-root policy. Frozen/installed builds resolve directly to the stable
ProgramData theme root above, including Diagnostic; source/dev builds resolve the repository `themes` tree. Installer scripts seed the same
ProgramData tree from the bundled curated pack, matching the existing preset-seeding model. Do not reintroduce a frozen
build placeholder or teach `settings_theme_catalog.py` to merge multiple roots.

Resolution rules:

1. explicit path injection remains valid for tests/tools;
2. every installed/frozen flavour uses the stable `%ProgramData%\SRPSS\themes` root, never its extraction tree;
3. source/dev builds use repository-root `themes`;
4. Widget Theme discovery is always the `widgets` child of the resolved theme root;
5. a bundled/repository theme tree may be used as a bootstrap/copy source when constructing ProgramData, but production
   must not merge two roots simultaneously or create duplicate file identities;
6. installed/frozen `.srtheme`/`.srwtheme` files are curated/read-mostly catalogue assets;
7. automatic Widget Theme `Custom` state is stored in normal SRPSS Settings persistence, **not** as a writable
   `%ProgramData%\SRPSS\themes\widgets\Custom.srwtheme`;
8. compiled Default Dark remains the unconditional Settings fallback even if the external directory is absent/invalid.

Widget Theme palette roles are runtime **baseline/defaults** rather than a writer that erases existing per-family `widgets.<family>.card.*` settings. Explicit family card values win for that family; the Context Menu consumes Widget Theme values directly because it has no family layer. This precedence is independent of the shared filesystem root.

Widget Theme schema v3 separates a strict core card/context role set from a sparse optional semantic vocabulary. Specialized roles may be omitted and inherit through `ui/widget_visual_roles.py`: exact role -> semantic parent -> runtime `local.*` current value -> preserved fallback, with an intentional family override above the theme when one exists. `local.*` roles are never file/persistence data. This is the approved mechanism for separators, panels, gradients, branded headers, Media controls and similar visual-only detail; do not encode those fallbacks independently in each widget and do not make every optional role mandatory in every `.srwtheme`. The resolver vocabulary is intentionally larger than the Settings GUI. **Branded Header Fill/Text/Border are no longer per-family Settings palettes:** shared `header.*` semantics own them, with `Header Fill` exposed once in `Widgets -> General -> Style Overrides`. Durable specialized family overrides such as Media Seek/Volume may remain where they represent a genuinely useful family contract. Retired family header fields are compatibility inputs only until their deletion horizon; they are not permission to recreate hidden header authority.

Widget Theme implementation should follow the same one-root principle and keep its own built-in/default-safe behavior as
defined by the Widget Theme contract. Theme selection IDs remain portable and must not encode absolute ProgramData/repo
paths. A real `.srwtheme` file is produced only by explicit import/export/authoring flow, not as a side effect of changing
a runtime swatch.

### Settings / Widget Theme linking

Settings Themes and Widget Themes are independently selectable palettes with an optional **bidirectional stable-ID link**.
The link is one persisted relationship state and is surfaced on both theme pages with the same lock/unlock affordance.

While linked:

- selecting a Settings Theme selects and persists its explicitly paired Widget Theme;
- selecting a Widget Theme selects and persists its explicitly paired Settings Theme;
- pairing is resolved only through stable metadata IDs (`linked_settings_theme_id` and the catalogue reverse lookup), never
  through display-name matching;
- an unpaired theme or settings-persisted Widget `Custom` snapshot cannot silently break the relationship; the user must
  switch to Independent first.

While independent, either catalogue may change without mutating the other. Card Surface/Card Border/Header Fill edits that create Widget `Custom` therefore also require/produce an independent Widget-theme state rather than inventing a synthetic Settings counterpart.

`Widgets -> General -> Style Overrides` is the single ordinary-widget shared styling surface: Card Surface, Card Border and Header Fill are theme-authoring edits that fork the full resolved palette to Widget `Custom`; **Reset All Colours to Theme** explicitly normalizes ordinary family colour/card-alpha compatibility overrides back to canonical Inherit values; Card Border Width and Surface Material (`Docs/Architecture/Card_Surface_Materials.md`) are global style values outside Widget Theme schema. The reset is operator-invoked, never a startup migration, and excludes Visualizer-authored colours. Runtime Widget Themes are colour/semantic bundles only; Settings-window Glass/Acrylic remains a separate native-window concern.

Hydrated Feeds, Steam-card and System Stats savers project their base payload from current stored values restricted to
canonical default keys, then replace the controls the page actually owns. Supported unexposed local styling therefore
survives an unrelated content, font or sampling edit. Retired/unknown leaves cannot return through this projection;
explicit Reset All Colours and imports remain authoritative because the base is read at save time, not cached in the UI.
Reset membership derives from the canonical widget-family catalogue, including disabled families and every Clock,
Feeds, Steam and System Stats member. Visualizer-authored colours remain excluded; no second family list is maintained.

The curated catalogue contains Settings themes and deterministic Widget mirrors, including genuinely light/white-adjacent themes and silver/metal themes (catalogue discovery owns membership and count).

**Materials and light themes (operator, 8 Nov 2026).** A theme's material is the window's base, not decoration under an
opaque shell: `window.dialog_glass` stays under half opacity on every theme with a material. Light themes carry a
tinted pale material (Frosted or Mica): over untinted Glass a dark desktop shows through, so dark text could only stay
legible by making the shell nearly opaque, which hid the material entirely (the light themes' "no material at all").
Every text role of a light theme and of every Frosted/Mica/Smoked theme holds 4.5:1 small / 3:1 large over its
surface stack, over its material, over a black and a white desktop (`tools/theme_legibility.py`; compositing is
affine in the desktop colour, so those two bound every wallpaper). Bar:
`tests/test_theme_material_legibility_contract.py`. Dark themes on untinted Glass or a light Acrylic tint do not
meet that bar over a bright wallpaper; that is recorded in `Current_Plan.md`, not hidden. Mirrors use the same stable-ID projection authority as the original pack. Dark-text light/light-metal Widget mirrors also establish a high-opacity light runtime card floor because, unlike the Settings HWND, runtime cards sit directly over arbitrary wallpaper. Regeneration must remain deterministic; mirrors change only when their semantic source/mapping intentionally changes.

## Proven Windows backdrop mapping

Material density calibration belongs to runtime semantic composition, not authored catalogue files.
`core/settings/surface_opacity.py` owns the Settings Opacity Adjust mapping (-1..1; zero is the calibrated
recipe, negative removes a fraction of density, positive fills remaining transparency). The cached projection in
`ui/settings_surface_composition.py` applies calibration to the **combined native and Qt stack**, then solves each
neutral overlay alpha against its already projected parent. A native underlay, window shell and group must not each
claim an independent contrast floor for the same text. Acrylic, Frosted and Mica reduce combined density by their
material calibration; Glass gains density; Smoked reduces dark surfaces only. Structural alpha-zero roles remain absent.
Interaction fills retain their authored state distinction and receive the same mapping at their own layer.

The same module owns the actual text/surface stack map used by the analytic legibility tool. After density is resolved,
semantic ink keeps its authored RGB when raising ink alpha suffices; otherwise the smallest readable mix toward either black or white preserves hue and seeks the role's contrast bar.
Encoded ink brightness alone does not choose polarity; the actual composed locations do.
Mode buttons resolve checked and hover ink separately against those states, including styled subsection parents;
the lock icon consumes the same checked/hover ink, with checked precedence. State inks are cached derivatives, never extra authored tokens. Faint 10–11px tertiary/helper ink reserves
0.3 contrast headroom above 4.5 for actual antialiasing; mode-state ink reserves 5.1 for its small geometric icon/text. No extra panel density is invented when a very
transparent stack cannot meet a conservative desktop bound. Native pixel evidence remains necessary for actual ink,
blur and layered-window composition; the analytic model cannot prove every painted glyph or native AA sample.
`SettingsThemeSpec.material_tint()` exposes the cached material tint, and `window_surface()` composes the existing
window role over that tint once. `native_backdrop_request()` selects the existing untinted Accent state-3 blur for
every enabled Settings material. This avoids Acrylic state 4's observed alpha-insensitive luminosity on light tints;
Qt owns the controllable tint and haze. Glass has no material tint and retains its untinted primitive; Normal remains
Off. The raw `NativeBackdropStyle.native_tint()` recipe and authoring files remain unchanged.

Settings, Studio and Foundry chrome consume this shared native request and combined Qt window fill. The explicit
non-Windows underlay represents only the neutral blurred-desktop base; the same Qt fill applies the tint once.
Analytic tools model the material tint and semantic stack once. One bounded per-theme projection cache is invalidated
by the admitted override, so paint-time lookups perform no contrast search. Native visual acceptance belongs in
`Current_Plan.md`; this transparency contract does not establish native rounded-corner clipping.

All enabled Settings materials use `SetWindowCompositionAttribute` / `WCA_ACCENT_POLICY` state 3 on the existing
layered Qt HWND. The native adapter still exposes state 4 as a primitive, but the shared Settings composition request
does not select it.

```text
Off -> ACCENT_DISABLED (state 0)

Glass/Acrylic/Frosted/Mica/Smoked
    -> ACCENT_ENABLE_BLURBEHIND (state 3), zeroed native GradientColor
    -> Qt window_surface applies the resolved material tint once (none for Glass)
    -> remaining semantic Qt surfaces compose above it
```

`ACCENT_ENABLE_BLURBEHIND` is the undocumented AccentPolicy state used through `SetWindowCompositionAttribute`. It is **not** the documented `DwmEnableBlurBehindWindow` API. Windows documentation about the latter must not be used to declare AccentPolicy state 3 equivalent, obsolete or unsupported.

### Glass visual ownership

Glass is intentionally untinted at the native layer. A Glass theme obtains its appearance from the semantic Qt layers painted over state-3 blur:

- `window.dialog_glass` controls the outer semantic surface;
- title bar, sidebar, navigation, panels, lists, buttons and other role alpha values compose above it;
- different Glass themes may therefore differ materially in RGB and opacity without changing the native primitive.

Do not make Glass opacity by inventing a hidden native tint or by changing the native primitive per Glass theme.

## Live Settings-root QObject lifetime

`ui/settings_theme.py` keeps registered Settings roots in a Python `WeakSet`, but **Python wrapper lifetime is not C++ QObject
lifetime under PySide**. A `SettingsDialog` wrapper can remain weak-referenceable after Qt has deleted the underlying C++
object. Theme publication must therefore validate each registered root with Shiboken before applying QSS.

Required transaction behavior:

- an invalid/deleted QObject wrapper is stale ownership debris: prune it from the registry and continue publishing the theme;
- if a `RuntimeError` occurs and Shiboken confirms the target became invalid, prune it and continue;
- a renderer failure from a still-valid Settings root is **not** stale ownership and must remain fatal so
  `settings_theme_runtime.py` can roll the theme transaction back;
- do not solve stale wrappers by weakening all renderer errors, retry timers, event-loop pumping or asynchronous QSS replay.

This distinction is important for native Glass/Acrylic as well as QSS. A stale root-QSS listener must not abort theme
publication before the live native-backdrop listeners receive the committed theme.

## Native transition ownership

The native mode is stateful but simple. Avoid compositor churn.

- Enabled material -> enabled material: native no-op; only the cached Qt tint/surfaces change.
- Any material -> Off: state 0 disables the AccentPolicy backdrop once.
- Off -> material: install state 3 once.
- Repeated Off is cached even though the adapter returns False to mean no material is active.

No post-show retries, zero-delay timers, stylesheet replay, event-loop pumping or repeated native calls are part of this contract.

The mode -> AccentPolicy mapping is one function, `core/windows/dwm_blur.py:apply_backdrop`, called by Settings'
backdrop owner and by the Visualizer Studio's frameless window (`ui/studio/surface.py`), which carries the active
theme's material the same way (applied once on first show; Normal makes no call). The Studio window is a Qt Quick
(OpenGL, alpha surface) top-level rather than a layered QWidget HWND, so its composition is not covered by the
physical validation of the Settings HWND: it awaits its own physical Default Dark / Acrylic / Glass smoke
(`Current_Plan.md` §9). The forged edge painter is likewise shared (`ui/settings_window_edge.py`, below).

## Non-Windows material underlay

Native Glass/Acrylic exist only on Windows. On every other platform the dialog's backdrop owner
(`SettingsDialog._apply_native_backdrop_theme`) never calls `core/windows/dwm_blur.py`; it paints one opaque
underlay beneath the dialog content instead (`ui/settings_material_underlay.py`), announced once per process with
`[PLATFORM]`. The underlay stands in for "the blurred desktop under the material": a neutral matched to the
palette polarity (`settings_theme_is_light`). The shared Qt `window_surface()` combines the resolved material tint
and shell above this neutral exactly once, matching the Windows split between native untinted blur and Qt tint.
Theme files carry no per-platform data. Mode `off` paints no underlay. Windows never paints it.
The Studio window, which wears the same material, never calls `dwm_blur` off Windows either
(`StudioWindowSurface.apply_backdrop`); its theme owner (`ui/studio/theme.py` `studio_theme`) composes the window
surface over this same underlay, so the Studio is opaque there for every material. Off Windows, Settings text over
the underlay is never less legible than the Windows black/white-desktop bound the legibility contract checks
(`tools/theme_legibility.py` with the underlay as the desktop: no role of any shipped theme regresses, 8 Nov).

Why opaque: Linux compositors (where present) show the raw, unblurred desktop through translucent layers, and
without a compositor those layers fall onto black, so the authored look and readability would depend on the
wallpaper. Compositor-specific blur (e.g. KWin's blur-behind hint) is a possible later refinement tracked in
`Linux_Plan.md`, not part of this contract.

## Rejected backdrop architectures for the current Settings HWND

The following were investigated and are **not** current implementation options:

- `DWMWA_SYSTEMBACKDROP_TYPE` / `DWMSBT_TRANSIENTWINDOW` as Settings Glass;
- `DWMWA_REDIRECTIONBITMAP_ALPHA` as a bridge between Qt alpha and the Glass backdrop;
- a QWindow Expose callback/reassertion;
- a post-show native retry;
- native-then-QSS replay ordering;
- near-clear state-4 Acrylic as a fake Glass underlay.

The system-backdrop path accepted DWM writes/readbacks but failed to compose reliably on first startup. The near-clear state-4 experiment produced an opaque black Settings surface. The physically accepted solution is state-3 Glass on the same AccentPolicy family as Acrylic.

A future move to DWM system backdrops is an **architecture change**, not a theme tweak. It requires a deliberate non-layered/native-host presentation design and fresh physical proof before this contract changes.

## Semantic QSS ownership

`ui/settings_theme_qss.py` is the central colour serializer. Opaque semantic values may render as compact hex; translucent values must retain integer 0-255 alpha in Qt `rgba(...)` syntax.

`ui/settings_theme.py`, `ui/tabs/shared_styles.py` and component renderers own selector/geometry application while ThemeSpec owns visual values. Typography, spacing, radii, dimensions and behavior stay renderer-owned unless deliberately promoted into the schema.

The forged Settings outer edge/corner remains renderer-owned: its geometry and painter live in
`ui/settings_window_edge.py` (`paint_forged_window_edge`), called by Settings' `ForgedWindowEdgeOverlay` and by the
Studio's frameless window, never copied. Its geometry is fragile and is **not** theme data. Camouflage colour follows the adjacent semantic shell surface; do not independently theme it.
The edge paints **over** the window's content in both windows (the Studio's edge item at z 1000; Settings' overlay, a
mouse-transparent child kept above every other child). Settings' shell surfaces fill the whole window
(`window.dialog_glass`, the title bar), so an edge painted beneath them is covered: dark themes author those surfaces
nearly clear and hid the defect, light themes author them nearly opaque and lost the border and the rounded corners
(fixed 8 Nov 2026; bar: `tests/test_settings_forged_edge_over_content.py`). `SettingsDialog.paintEvent` paints only
the non-Windows material underlay (`paint_material_underlay`), beneath the content.

Native Settings corner acceptance requires desktop captures of dark and light themes on both dark and light
backgrounds. The forged edge is not a native composition clip: on the layered AccentPolicy HWND, an installed
window region clips Qt painting but does not remove the Accent material in excluded corner pixels. A QWidget mask
therefore cannot establish a clean rounded native silhouette. Keep native material residue distinct from the
renderer stroke, and inspect antialiasing, clipping and seams as well as outside-radius coverage. Product outer-shadow
coverage is zero; assess any OS-owned DWM shadow separately outside the HWND. Offscreen QWidget captures can test
edge ownership and lifecycle but cannot close this native composition gate. The Studio's separate Quick window
is outside this Settings-only acceptance scope.

`tools/settings_native_corners.py` captures this gate from the Windows desktop after `DwmFlush`, using an isolated
profile and controlled backgrounds; never substitute its offscreen functional checks for those pixels. The rejected
logical-mask and post-Accent physical-region evidence is under `.artifacts/evidence/settings/native_outer_border/`
(`20261109_border_before`, `20261109_border_candidate`, `20261109_region_diagnostic`,
`20261109_physical_region_diagnostic`). [Microsoft's rounded-corner guidance](https://learn.microsoft.com/en-us/windows/apps/desktop/modernize/ui/apply-rounded-corners)
also excludes per-pixel alpha layering and window regions from system rounding, including the opt-in API.

Settings shadows remain under `ui/widgets/control_shadow.py`; ThemeSpec supplies their semantic visual parameters. Runtime screensaver widget shadow authority is separate.

Rounded borders on action buttons (every `OutlinedButton` role: compact, standard and the Sources look, each keeping
its original size), buckets, lists, the content area and popups are painted as one `QPainterPath` stroke
(`ui/widgets/outlined_button.py`, `ui/widgets/continuous_border.py`); their QSS border stays transparent. Qt style
sheets draw a rounded border as separate edge and corner pieces whose antialiased ends overlap, and a translucent
theme border colour then shows seams (R-101). New outlined controls reuse these painters rather than a QSS border.

Popups are separate top-level windows and inherit nothing. `ui/styled_popup.py` applies the Settings root stylesheet
and paints `PopupSurface`, so every popup, including the colour picker and account dialogs, takes the active theme's
text, controls and border. A new dialog builds on `StyledPopup` (or those two pieces), never on a bare `QDialog` or
`QMessageBox`. File and folder pickers stay native OS dialogs. Every Settings action button (tabs, popups, Guided
Setup / Quick Start) uses the ordinary Settings button semantics (`control.button.surface` at rest, `hover_surface` on
hover); there is no emphasis-pill style. A default button answers Enter but is never painted as a permanently filled
pill, which reads as a stuck hover in themes that fill it. Navigation pills, mode toggles and the setup
Enable/Disable All actions keep their own theme roles. Only
warning, error and success popups show a glyph beside the title; a plain question or notice shows its title alone.

Bucket headers (`BucketToggle`, every collapsible bucket in Settings and the wizard) lay out their label exactly as
Qt's tool-button label does (arrow box `iconSize.width + 4` by the content height, title after it) except that the
title sits 1 px (normal) or 2 px (large) further from the arrow, because the windows11 down arrow fills its box. The
size hint grows by the same amount, so a title never clips at any scale. The header padding is renderer geometry defined once in
`ui/settings_theme.py` (its QSS and `BucketToggle` both read it; the renderer never imports widgets).

Expanded bucket children use `BucketTreeBody` (`ui/widgets/bucket_tree.py`) through the shared bucket and Visualizer
scaffold builders. One 18-logical-pixel content gutter per disclosure level preserves each level's sibling label/control
columns. The body paints a 1-logical-pixel connector using the active `bucket.open.border` colour at 42% of its authored
alpha. Theme schema, settings values, persistence and accordion ownership are unchanged.

The actual widget/layout tree owns these rails: horizontal form rows contribute their first visible label/control;
vertical grouping hosts are transparent; a nested bucket contributes its header while its `BucketTreeBody` owns its
descendants. Shared explanatory label styles and contextual status owners mark their labels as `settingsAnnotation`;
they remain visible in their existing positions but are not independent tree leaves. Hidden rows, spacers, empty
alignment labels and these annotations are excluded. Each trunk ends at
the last visible relevant child, using mapped widget geometry at paint time. Existing Qt layout requests invalidate the
decoration after lazy insertion, conditions or expansion; ordinary resize/scroll/theme paints handle the rest. There are
no retained endpoint maps, per-page renderer copies, event filters, subscriptions, timers, polling or geometry writes.

Shared combo typography uses positive point sizes equivalent to its authored 14/13/12 logical-pixel sizes at
Windows' 96 logical DPI. Qt 6.11's Windows 11 menu-indicator metric reads `QFont.pointSize()` even for a pixel font;
pixel-only combo QSS therefore produces `QFont::setPointSize(-1)`. Preserve text metrics at the shared style owner,
without suppressing messages or replacing the native style. Painted onboarding labels adjust fonts in their
original units through `ui/onboarding/common.py`, including Arrange's readable minimum size.

## `dark.qss` status

`themes/dark.qss` is **retired and physically deleted**. Both runtime loaders are gone after caller-proofing the surviving structure: `ui/settings_theme.py` owns the narrow Settings-root typography/checkbox structural base, `ui/settings_menu_style.py` owns tray-menu structure using ThemeSpec context-menu roles, and the color-picker wrapper owns its residual subsettings chrome. No legacy palette was copied into a replacement monolith.

The permanent rule is simple: never restore `dark.qss`, add a fallback stylesheet loader, or replace it with another monolithic Settings QSS. Surviving structure belongs to narrow renderer/component owners; colour, opacity and shadow semantics belong to `SettingsThemeSpec`. Native backdrop code and forged edge geometry remain separate owners unless an independently proven defect requires change. Acceptance evidence is retained in `Docs/TestSuite.md`; the completed execution diary is not a live architecture document.

## Theme Foundry authoring contract

Theme Foundry must consume the current `SettingsThemeSpec` and `ui.settings_theme_io` APIs directly. It may not maintain a private old schema.

Required backdrop authoring semantics:

- expose `Off`, `Acrylic`, `Glass`, `Frosted`, `Mica` and `Smoked` as supported schema-v6 modes;
- tint controls are meaningful only for the tinted materials (Acrylic, Frosted, Mica, Smoked), whose alpha must remain non-zero;
- Glass must be described as untinted AccentPolicy state-3 blur whose visible colour/opacity comes from semantic Qt surfaces;
- Glass must never be authored as a pale/clear Acrylic recipe;
- the DWM system-backdrop experiments (Mica/transient window, rejected above) are not selectable theme modes; the
  selectable Mica is the AccentPolicy Acrylic recipe described in the schema section;
- save only complete themes that strict runtime loading can round-trip;
- `Save Widget Counterpart…` is an explicit authoring action, not runtime coupling: persist the current Settings theme into the catalogue first so it has a stable `builtin:`/`file:` identity, then generate/save the `.srwtheme` through the same `widget_counterpart_for_settings_theme()` authority used by the curated mirror pack; never duplicate the semantic mapping inside Foundry.

Foundry previews are authoring aids, not runtime authorities. The actual Settings window remains the final visual oracle for layered composition.

## Change guardrail

For any future Settings visual/backdrop change:

```text
inspect exact current source
-> identify semantic owner vs renderer/native mechanism
-> make one bounded ownership change
-> strict theme round-trip/focused tests
-> physical Default Dark + Acrylic + Glass smoke
-> update this contract only when the proven architecture changes
```

Do not fix a native-material problem by perturbing stylesheet order, and do not fix a QSS-role problem by changing the native compositor.

## Catalogue palette previews and favourites

Both product theme lists use `ThemeListWidget`: one delegate paints each row's right-aligned 2×2 palette and star,
without per-row child widgets. Palette RGBs are derived once from validated semantic colours, ranked by role prevalence
and alpha, grouping nearby shades and excluding invisible/shadow effects. Fully transparent palettes preview their
authored RGBs. These previews never become a new palette authority.
The square's slightly rounded 2 px border uses the current `swatch.border`; palette cells are clipped inside it so
they cannot leak through corners or tint the border. The star uses `control.list.selected_accent`.

`ui.theme_favourites` stores separate Settings and Widget stable-ID lists in normal Settings persistence. Theme files
and schemas are unchanged. Favourites sort first, retaining catalogue order within both groups and preserving missing
IDs for returning files. Star clicks and focused-list Ctrl+D toggle only this preference, keeping selection/activation
and linked theme state unchanged. Widget Custom previews refresh from the existing stored Custom snapshot on page entry.
Names elide before the decorations; the square remains at the visible viewport's right edge.

## Theme filter

Both theme pages carry a type-in filter (`ui/widgets/theme_filter.py` `ThemeFilterField`) in the Linked row, to
the right of the Linked / Independent button, across the row's free space.

- **Terms are derived, never tagged.** `ui.theme_semantics.theme_filter_terms(theme)` is the one pure function both
  catalogues share; it reads only the theme's authored role map and material (no active theme, no opacity
  projection), so imported and user themes are covered automatically. Tone: `Light` when the ink is dark on a light
  surface (`uses_dark_text_on_light_surface`: ink luminance <= 0.18 and surface >= 0.55), else `Dark`. Material:
  the Settings `backdrop.mode` (`off` is Normal) or the Widget `surface_material`, labelled by
  `SURFACE_MATERIAL_LABELS`. Colours: the hue families of the accent and the surface (Settings:
  `control.list.selected_accent`, `panel.group.surface`; Widget: `widget.accent` else `card.border`,
  `card.background`). Hue buckets (HSV degrees): Red < 15, Orange < 45, Yellow < 70, Green < 160, Teal < 195,
  Blue < 250, Purple < 290, Pink < 345, Red again to 360. A colour with chroma < 18 or saturation < 0.15 is
  neutral; a theme whose accent and surface are both neutral is `Grey`.
- **Matching.** Case-insensitive; each word matches when it is a substring of the row's display name or a prefix of
  one of its terms; words combine with AND; an empty filter shows everything (`theme_matches_filter`).
- **View state only.** Filtering only hides `ThemeListWidget` rows (`set_filter_text`): the current/selected row stays
  (even hidden), no selection signal is emitted, nothing is re-applied and nothing is written to Settings.
  Favourites, their favourites-first order and the Linked pairing are unchanged; the filter is re-applied after a
  favourites reorder. When nothing matches the list paints a short empty-state line. Filtering runs on
  `textChanged`; there are no timers.
- **Autocomplete.** A `QCompleter` completes the last word and keeps the words before it. Its model is the tones,
  materials and colour families that occur in that page's loaded list, then the theme names
  (`ThemeListWidget.filter_vocabulary`), rebuilt when the list's themes change. The popup reuses
  `COMBOBOX_POPUP_VIEW_STYLE`; as a translucent top-level it fills `combo.popup.surface` and strokes
  `combo.popup.border` itself as one continuous path.
- **Look.** `THEME_FILTER_INPUT_STYLE` (shared_styles) uses the `control.input.*` roles at the Linked button's
  height and radius, with a transparent stylesheet border; the field strokes `control.input.border` as one
  continuous path (no seams). The clear (x) is painted in the input ink and shows only while there is text.
- Tests: `tests/test_theme_filter_terms.py` (synthetic specs), `tests/test_theme_filter_real_dialog.py` (real
  `SettingsDialog` on a temporary theme tree with imported themes; expectations derived from the catalogue).

## Theme sorting (standalone tool)

[Theme Sorter Foundry](../Guides/Theme_Sorter_Foundry.md) previews editable Settings themes on itself and performs explicit paired Widget/Settings theme file rename/delete using `linked_settings_theme_id`. It does not change product theme selection. [Mutable test-oracle audit](../Audits/Mutable_Test_Oracle_Theme_Sorter_2026-10-23.md) prevents freezing current curated colours, file names or pack count in tests.
