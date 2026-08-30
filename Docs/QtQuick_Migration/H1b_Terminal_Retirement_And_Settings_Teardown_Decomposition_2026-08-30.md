# H1b Technical Record — Terminal Retirement and Settings Teardown

Date: 2026-08-30  
Status: **CLOSED / permanent lifecycle regression reference**

This document records the ownership failure and accepted repair. It is not active work admission; `Current_Plan.md` owns current sequence.

## Failure

Terminal Exit used to:

```text
quiesce / clear
-> begin asynchronous Quick retirement
-> continue process/thread shutdown
-> log normal code=0 exit
-> BackgroundRenderItem slot complaint
-> Windows access violation during GC
```

Clock QML simultaneously evaluated against a null model during deferred item retirement, and two Settings helper event filters could receive late Qt events after their Python-side target attributes were already gone.

## Root cause class

Replacement already had a destruction proof. Terminal `application_exit` did not wait for equivalent asynchronous Quick/QObject retirement before ending process/Qt lifetime.

The Clock model was also parentless in the retained presentation path, so Python could release it before the still-live QQuickItem finished binding teardown.

## Accepted repair

### Terminal retirement purpose

The existing destruction authority distinguishes:

```text
retirement proof
replacement permission
```

Replacement mode observes retirement and may run one generation-fenced replacement continuation.

Terminal mode observes the same retirement facts but **can never admit replacement**. Final terminal worker/process shutdown and `QApplication.quit()` happen only after legal Quick retirement completion/failure handling.

### Retained model lifetime

Parentless QObject models passed into retained QML are bound to the retained item lifetime where required so the model survives binding teardown. Already-parented generation-scoped models keep their existing ownership.

### Settings event filters

`_ControlShadowHelper` and `ComboKnobController` tolerate their tracked target already being absent/invalid during late Qt events and never raise through `eventFilter()`.

## Explicitly rejected fixes

- `processEvents()` pumping;
- arbitrary sleeps;
- forced `gc.collect()`;
- force-kill;
- deliberately leaked Quick windows;
- per-property Clock QML null guards as the ownership fix;
- missing-font work;
- a second lifecycle/display manager.

## Physical acceptance

Later dual-display runs show:

```text
application_exit barrier armed
-> Quick/QObject roots retire
-> barrier complete (~200–250 ms)
-> terminal process/thread finalization
-> clean natural code=0 exit
```

No Windows access violation, `BackgroundRenderItem::` slot error, Clock null-model storm or Settings event-filter exceptions remain in the accepted gate.

## Permanent regression requirements

Keep tests that prove:

- terminal purpose waits for tracked roots;
- terminal purpose never runs a replacement continuation;
- replacement purpose remains unchanged;
- completion/finalization is exactly once;
- parentless retained model lifetime survives item teardown;
- late Settings event filters are harmless.

Qt/QML acceptance must also inspect `screensaver_qml.log`; see `Docs/Qt_QML_Observability.md`.
