// The harness's known-cost pass (Current_Plan.md item 8b, N2.6): the GPU timer's proof of correctness. Into a target of
// its own (RGBA8, preserving, primed: targets.h) one pass draws `draws` full-target triangles, each running the same
// fixed fragment loop (`iterations` dependent steps per fragment) with additive blending, so every draw's fragments are
// executed and the pass costs `draws` times one draw plus a constant. The timer must report that: a pass scaled up N
// times takes N times longer. Its `timing` option "before" is the negative control: the timer's bracket is recorded empty
// in front of the pass, which must then not scale at all.
//
// It exists only while a harness asks for it (no resource, no work otherwise).
#pragma once

#include <QtCore/QAtomicInteger>
#include <QtCore/QByteArray>
#include <QtCore/QJsonObject>
#include <QtCore/QString>

#include <memory>

class QRhi;
class QRhiCommandBuffer;

namespace srpss_core {

struct LoadConfig
{
    int width = 1024;
    int height = 1024;
    int draws = 1;
    int iterations = 128;
    QString timing = QStringLiteral("pass"); // "pass": the bracket encloses the pass; "before": an empty bracket first

    // From the harness's JSON (missing keys keep the defaults); false with `error` for a value out of range.
    static bool fromJson(const QByteArray &json, LoadConfig *out, QString *error);
    QJsonObject toJson() const;
    bool sameResources(const LoadConfig &other) const { return width == other.width && height == other.height; }
};

class LoadPass
{
public:
    explicit LoadPass(const LoadConfig &config);
    ~LoadPass();
    LoadPass(const LoadPass &) = delete;
    LoadPass &operator=(const LoadPass &) = delete;

    const LoadConfig &config() const { return m_config; }
    // Render thread: the draw count and loop length from the next recording (the target keeps its size).
    void retune(const LoadConfig &config);

    // Render thread, inside a frame, outside any pass: creates the resources on first use, then records the pass.
    bool record(QRhi *rhi, QRhiCommandBuffer *cb, QString *error);
    // Render thread: every QRhi object goes.
    void release();
    int liveResources() const { return m_live.loadRelaxed(); }
    qint64 passesRecorded() const { return m_passes.loadRelaxed(); }

private:
    bool ensure(QRhi *rhi, QString *error);

    struct Resources;
    LoadConfig m_config;
    std::unique_ptr<Resources> m_res;
    QAtomicInt m_live { 0 };
    QAtomicInteger<qint64> m_passes { 0 };
};

} // namespace srpss_core
