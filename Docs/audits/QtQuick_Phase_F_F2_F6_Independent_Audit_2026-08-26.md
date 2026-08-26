# Qt Quick Phase-F F2–F6 Independent Audit — 2026-08-26

Source basis:

```text
c6af1260b695e35b802e7b70ddcbb2277ef0100a
5.0.0 - Phase F6 Partial
```

Independent source/architecture/test-design review of rapid retained-family work from Weather through current
partial Gmail checkpoint. Reviewer did **not** rerun implementation agent's Windows/PySide/OpenGL commands or
independently inspect generated smoke PNGs; execution/eyes-on reports remain attributed to implementation agent.

## Verdict

```text
F2 Weather                         GREEN
F3 Media core                     GREEN
F4 Media controls/accessories     GREEN
F5 Reddit / Reddit2               GREEN
F6 retained model                 GREEN as bounded model slice
F6 current QML/wrapper direction  GREEN / PARTIAL
integrated repository             YELLOW — shared Quick import dormancy correction required
```

YELLOW does not reopen F2–F5 or invalidate their old-pixel retirements.

## F2 Weather

Confirmed stable WeatherPresentationModel; real WidgetRuntimeManager -> WeatherRuntimeService injection;
QuickSceneController host activation/retirement; provider/network/startup-cache/persistence/cadence/retry/
request-generation neutral ownership; loading/ready/cached-error/missing-location and packaged icons; canonical
style/direction in-place; old QWidget pixels removed. GREEN.

## F3/F4 Media

Confirmed one runtime-generation shared Media owner -> display leases; separate shared app-volume/system-mute
owners -> narrow display leases; one retained Media model/item per display. Owner uses runtime-generation/
ThreadManager identity, weak lease accounting and generation/request/provider/playback fencing. One lease
retirement does not inherently retire survivor.

Retained model owns presentation/action admission and rolls back auxiliary leases on partial activation
failure. Artwork uses one process-engine provider with stable identity/reference accounting/bounded
unreferenced retention.

F4 correction landed before retirement: capability-gated semantic seek, accepted playback state truth,
retained soft progress glow, no visible seek handle by design. Old header/metadata/artwork/control/progress/
volume/mute pixels deleted. Remaining MediaWidget is temporary non-painting old-host/Visualizer anchor until H.
GREEN.

## F5 Reddit / Reddit2

Confirmed one retained Reddit QML family; separate stable model/list-model per configured member; Reddit2 not
second provider architecture; per-member neutral RedditRuntimeService owns provider/startup cache/accepted
candidate/cadence/blocked-gate persistence/request generations/retirement; shared rate limiter remains shared;
stale results fenced; production-shaped tests cross real manager service, retained model, current Quick host,
semantic refresh/open, geometry/style mutation and retirement; old QWidget pixels/caches/hit/hover removed.
GREEN.

## F6 retained model / partial QML

Model has bounded config/style, stable row/list identity, stable thread/message identity, grouping/formatting,
stale revision rejection and semantic refresh/auth/open/message-action admission without moving backend/
cadence/cache/persistence into QML.

At `c6af1260`, GmailPresentation.qml and RetainedGmailPresentation landed. It is partial: Gmail is not yet in
static family registry and real manager/runtime-host caller proof has not landed. Direction GREEN/PARTIAL.

### Gmail fidelity findings

Before real owner injection:

1. Preserve existing floating QMenu-style three-dot action menu and icons; partial QML row-expanding text-chip
   strip is an unrequested redesign and changes geometry.
2. Existing header frame derives from card/background border style; partial QML uses low-alpha row separator
   colour width 1. Project real header-border style.
3. `desaturate_when_no_unread` historically desaturates logo; opacity reduction is not equivalent.
4. Preserve blank-space double-click refresh.
5. Prove dynamic content height from accepted rows separately from transient popup/menu state.

These are bounded retained-presentation corrections, not rollback reasons.

## Shared Quick import-dormancy YELLOW

```text
rendering.quick.scene_controller
-> rendering.quick.widgets package
-> eager all-family imports
-> Gmail presentation
-> widgets.gmail_runtime/helpers
-> Gmail backend/runtime tree while inactive
```

This weakens landed capability dormancy; existing fresh-process tests focus legacy hosts. During F6 before
real Gmail owner injection: make common package import-light, resolve family implementation at caller/
activation, keep static registry metadata light, TYPE_CHECKING annotation-only runtime types as appropriate,
no new registry/plugin framework, and fresh-process `import rendering.quick.scene_controller` must leave
inactive Gmail/Weather/Reddit/Media business/runtime/backend trees dormant. YELLOW until corrected.

## H planning finding

Pre-H Quick runtime owns window/scene/pacer/input/transition but normal production remains DisplayWidget and
Quick production path does not yet own real display WidgetRuntimeManager orchestration. Expected, but H must
explicitly prove:

```text
QuickDisplayRuntime
-> one display WidgetRuntimeManager
-> canonical capability/instance resolution
-> current neutral service leases
-> stable family models
-> QuickSceneController
-> retained family items
```

Do not run old/new production runtime managers in parallel.

## Documentation sweep findings

Found current-authority drift: Project Overview frozen at F0.5 YELLOW; Contracts called Clock candidate with
old pixels alive; Custom Style said F0.5 awaiting audit; capability doc said E3 active/E1 next and Imgur future
removal; Defaults Guide called Imgur future F0 work; owner/bridge docs retained future-tense landed examples;
Clock analogue doc was pre-F1 gate; Phase-G doc lacked edit X semantics; Guardrails permitted completed
closure narrative in Current Plan while Documentation Maintenance said plan stays lean.

The 2026-08-26 reconciliation pack updates these authorities and makes `Docs/10_WIDGET_GUIDELINES.md` the
proven ordinary-widget authoring guide.
