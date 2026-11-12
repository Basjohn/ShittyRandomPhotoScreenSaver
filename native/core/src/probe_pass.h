// The frame driver's probe pass (Current_Plan.md item 8b, N2.2): the trivial core pass that proves, end to end, the
// frame edge (it is recorded on the driver's beforeRendering edge into the host's command buffer), the upload correction
// (N0.3 rule 1 with F1), the front-face rule on the corrected matrix (rule 4 with F3), the conventions block of a target
// the core owns (F1, F2) and the readback orientation (rule 2: the core's readbacks are never flipped).
//
// Into a target of its own (RGBA8, preserving, primed: targets.h) it draws, through an OpenGL-form item matrix (item
// pixels, y down, like Qt Quick's) corrected once at upload:
// - a background quad over the whole target, each fragment coloured with what the conventions include says about it:
//   fragUv in r and g, ndcToUv of the clip NDC in b and a (both equal the memory texel's centre over the size);
// - two triangles in the top half with back-face culling: the left one front-facing (counter-clockwise in OpenGL's clip
//   space through a Y-down matrix), the right one back-facing; the front face is chosen by rule 4 on the uploaded
//   matrix, from two prebuilt pipelines.
// The harness reads the target back raw and compares it with the analytical image from the facts the pass reports.
// The probe exists only while a harness asks for it (no resource, no work otherwise). Its options other than the
// defaults are negative controls: no correction, the rule fed the uncorrected matrix, a fixed front face, a forced
// fragment flip or clip-NDC flip.
#pragma once

#include <QtCore/QByteArray>
#include <QtCore/QJsonObject>
#include <QtCore/QString>

#include <QtCore/QAtomicInteger>
#include <QtCore/QMutex>

#include <memory>

class QRhi;
class QRhiCommandBuffer;

namespace srpss_core {

struct ProbeConfig
{
    int width = 160;
    int height = 90;
    QString correction = QStringLiteral("target");  // "target" (rule 1, F1) | "none"
    QString frontFace = QStringLiteral("rule");      // "rule" (rule 4 on the uploaded matrix) | "rule_uncorrected" |
                                                     // "ccw" | "cw"
    int fragmentFlip = -1;                           // the block's x: -1 the target's (F1: 0), 0 or 1 forced
    int ndcFlip = -1;                                // the block's y: -1 the backend's (F2), 0 or 1 forced

    // From the harness's JSON (missing keys keep the defaults); false with `error` for an unknown value.
    static bool fromJson(const QByteArray &json, ProbeConfig *out, QString *error);
    QJsonObject toJson() const;
};

class ProbePass
{
public:
    explicit ProbePass(const ProbeConfig &config);
    ~ProbePass();
    ProbePass(const ProbePass &) = delete;
    ProbePass &operator=(const ProbePass &) = delete;

    // Render thread, inside a frame, outside any pass: creates the resources on first use, then records the pass;
    // with `readback`, the target is read back at the pass's end (completed later by the QRhi).
    bool record(QRhi *rhi, QRhiCommandBuffer *cb, bool readback, qint64 frame, QString *error);
    // Render thread. Releases every QRhi object; a pending readback is first completed with QRhi::finish() when the
    // caller is outside a frame, and otherwise the release is refused (false) until it completes.
    bool release(QRhi *rhi, bool outsideFrame);
    bool readbackPending() const;
    int liveResources() const;

    // Any thread: the last completed readback (rows top-down as the memory holds them, never flipped) with the facts
    // of the recording that produced it. False when none has completed since the last take.
    bool takeResult(QJsonObject *facts, QByteArray *rgba, int *width, int *height, qint64 *frame);

private:
    bool ensure(QRhi *rhi, QString *error);

    struct Resources;
    ProbeConfig m_config;
    std::unique_ptr<Resources> m_res;
    QJsonObject m_facts;           // render thread: what the resources were built with
    QAtomicInt m_live { 0 };       // QRhi objects this pass holds (read from any thread)

    mutable QMutex m_mutex; // guards the result below and the pending flag
    bool m_pending = false;
    qint64 m_pendingFrame = -1;
    bool m_hasResult = false;
    QJsonObject m_resultFacts;
    QByteArray m_resultRgba;
    int m_resultWidth = 0;
    int m_resultHeight = 0;
    qint64 m_resultFrame = -1;
};

} // namespace srpss_core
