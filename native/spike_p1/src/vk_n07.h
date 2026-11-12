// N0.7 (D9's proof): the async job service beside Qt Quick on the module's own Vulkan device. Harness only; nothing
// here ships. Decision and amendment: Docs/Future_Work/Native_Core_P3_Decisions.md D9; Qt facts:
// Docs/Future_Work/Native_Core_N06_N07_Qt_Facts.md (sections B, C, H). Driven by python/run_n07.py. Every entry
// point returns one JSON object (UTF-8); none sets or reads an environment variable.
//
// Shape:
// - One job thread per device (a QThread with its own run(), no event loop), parked on a condition variable at
//   rest; every return from the wait is counted (wake-ups). It owns a second QRhi created on our VkDevice with
//   the second queue N0.6 found (family 0, index 1): whether that works is the start-up probe.
// - Jobs are self-contained: an upload job (a 4K photo generated on the job thread, uploaded, its mips generated)
//   and a heavy job (the edge field's five compute stages at the field size, repeated). Each writes a back slot
//   of its kind (three slots: never the front, never the latest published), waits for its own submission with
//   QRhi::finish() on its own thread, and publishes one atomic generation edge (the latch).
// - The frame driver (render thread of a hidden Qt Quick host on our device, Qt's queue 0) reads the edge at frame
//   start; on a new generation it swaps the front to the published slot (Qt's QRhi imports the slot's VkImage with
//   QRhiTexture::createFrom; same queue family, so no ownership transfer), and copies a region of it into a
//   texture of its own (a real read on Qt's queue). Image layouts are handed over both ways with
//   setNativeLayout. A frame never waits for a job.
// - The in-frame form records the same job bodies into Qt's frame command buffer (D9 point 5).
#pragma once

#include <QtCore/QByteArray>
#include <QtCore/QString>

class QObject;
class QQuickWindow;

namespace srpss_spike {

class QuickOffscreenSession;

// Before the window's scene graph is initialised: our instance and device (n06AttachQuickWindow) and Qt Quick's
// GPU timestamps (QQuickGraphicsConfiguration::setTimestamps), so Qt's QRhi reports each frame's GPU time.
bool n07AttachQuickWindow(QQuickWindow *window, QString *error);

// Starts the job service on the N0.6 context's device (created with queue mode "second"): the job thread, its QRhi
// on the second queue (the probe: created, its native handles, a 64x64 upload read back on that queue), then the
// job bodies at fieldWidth x fieldHeight (upload slots, the edge field with its photo). Waits for the thread's
// start-up (a start-up handshake on its own condition variable, not counted as a wake-up). GUI thread.
QByteArray n07ServiceStartJson(int fieldWidth, int fieldHeight);
// Quiesces the job service (D9 point 6, D1's barrier): a job in flight finishes its own GPU wait and, when
// `abandon`, is dropped unpublished; the thread releases its bodies and QRhi and exits. Idempotent. GUI thread.
QByteArray n07ServiceStopJson(bool abandon);
// The job thread's counters: wake-ups, state, its CPU cycles (QueryThreadCycleTime) and times, calls with a Python
// thread state, published and abandoned jobs, and the job log (with `includeLog`). Any thread.
QByteArray n07ServiceStatsJson(bool includeLog);

// Runs `frames` frames of `session` paced at `periodMs` with the frame driver (created on first use for this
// session). `configJson`: {"mode": "none"|"inframe"|"job", "kind": "field"|"upload", "first": frame of the first
// trigger, "every": frames between triggers (0: one trigger), "triggers": the most triggers (0: no limit),
// "repeat": edge-field builds per job, "seed": upload photo seed, "low"/"high": edge thresholds, "readback": ""
// or "field_job"|"field_inframe"|"upload_job"|"upload_inframe" (on the run's last frame; hashes returned)}.
// Returns per frame: scheduled, start and completion times, Qt's frame GPU time (as Qt reports it: an offscreen
// frame's time is read at the next begin of the same frame slot, two frames later), the latch read and swap time,
// the hook time; the triggers and the swaps (with generations). GUI thread, without the GIL.
QByteArray n07RunFramesJson(QuickOffscreenSession *session, QObject *animated, int frames, double periodMs,
                            const QByteArray &configJson);
// Releases the frame driver's render-side resources (slot wrappers, consumers, the in-frame bodies) on the render
// thread, before Qt's QRhi goes; also called by quick_session_end for the driver's session. GUI thread.
QByteArray n07ReleaseRenderSideJson(QuickOffscreenSession *session);
// quick_session_end calls this before the session (and Qt's QRhi) goes: releases the driver if it is this session's.
void n07SessionEnding(QuickOffscreenSession *session);
// (v) Retirement in the middle of a job: submits a heavy job (`repeat` builds), waits (bounded) until the job
// thread is recording it or waiting on its GPU work, then retires: the render side is released, the service is
// stopped with abandon. Returns the state seen at retirement and the quiesce record. GUI thread.
QByteArray n07RetireJson(QuickOffscreenSession *session, int repeat);
// The FNV-1a 64 of the upload photo's pixels (RGBA8, rows top to bottom) for a seed: mip 0's expected hash.
QByteArray n07PhotoHashJson(int width, int height, quint32 seed);

} // namespace srpss_spike
