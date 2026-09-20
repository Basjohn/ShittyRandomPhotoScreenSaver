# System Volume / Mute OSD | Current product contract

The independently enabled `system_audio_osd` ordinary widget uses the **existing shared Core Audio source** consumed by Media. The OSD and Media have independent display/enablement, but one GUI-apartment endpoint/callback owner across overlapping display generations. This is a current product reference; completed implementation milestones are not future work.

## Source and lifecycle

- Subscribe through the retained shared audio source; never recreate the retired process-global Media mute endpoint or its polling fallback. Core Audio notifications, default-output rebind and initial snapshot are coalesced to one latest GUI delivery. Read-only callbacks cannot issue actions or synchronously mutate QML.
- Enabling an OSD adds a presentation lease, not another endpoint subscription, process poll, worker, mixer session observer or physical window. With the final consumer gone, unregister and retire its endpoint on the proper COM apartment. Disabled/hidden presentation must not sustain a repaint loop.
- The OSD uses one restartable, event-owned visibility deadline per admitted presentation, with a bounded fade when events settle. Bursts restart the existing deadline; mute/volume events never echo volume writes. Fence late callbacks and deadlines after device replacement, Edit, retirement or generation change.

## Presentation and editing

- The OSD is a retained Quick scene member with semantic Widget Theme card/text/fill/track styling, common border and shadow ownership, a truthful mute/percentage state and a left-to-right level bar. Respect compact X/Y and the configured label placement; no second overlay window or QML source scheduler.
- Global CUSTOM Edit may show the enabled OSD shell without waiting for a new audio event. Shared ordinary-widget edit/session ownership handles movement, X/Y extent, diagonal/wheel, Save/Cancel/Undo/Restore, slots and reopen; the OSD QML handles only its internal text/bar reflow. Disabling the family must not create an Edit-only instance.
- Keep Media's application-session volume separate from the Windows **system master** volume and mute. OSD events must not attempt to synchronize unrelated application/browser playback sessions.

## Regression evidence

Automated Qt and fake-COM tests validate retained geometry, subscription/lifecycle cardinality and bounded latest-value publication. Real hardware callback arrival, output switching, theme/paint ordering and active-input feel require direct Windows observation when those behaviors are changed. The operator has accepted the OSD and Media product behavior; do not reopen unrelated physical acceptance merely because this reference describes its change gates.
