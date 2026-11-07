// P1 spike, part B: the production shape. A C++ QQuickItem whose paint node is
// a C++ QSGRenderNode recording through Qt Quick's own QRhi command buffer.
// No Python runs in updatePaintNode(), prepare() or render().
#pragma once

#include "quadfield.h"
#include "thread_probe.h"

#include <QtQuick/QQuickItem>
#include <QtQuick/QSGRenderNode>

class QQuickWindow;

namespace srpss_spike {

ThreadProbe &nativeNodeProbe();

class QuadFieldNode final : public QSGRenderNode
{
public:
    QuadFieldNode(QQuickWindow *window, int instances);
    ~QuadFieldNode() override;

    // Called from updatePaintNode(): render thread, GUI thread blocked.
    void sync(const QSizeF &size, float timeSeconds);

    void prepare() override;
    void render(const RenderState *state) override;
    void releaseResources() override;
    StateFlags changedStates() const override;
    RenderingFlags flags() const override;
    QRectF rect() const override;

private:
    QQuickWindow *m_window;
    QuadField m_field;
    QSizeF m_size;
    float m_time = 0.0f;
};

class QuadFieldItem : public QQuickItem
{
    Q_OBJECT
    Q_PROPERTY(qreal time READ time WRITE setTime NOTIFY timeChanged)
    Q_PROPERTY(int instances READ instances WRITE setInstances NOTIFY instancesChanged)

public:
    explicit QuadFieldItem(QQuickItem *parent = nullptr);

    qreal time() const { return m_time; }
    void setTime(qreal time);
    int instances() const { return m_instances; }
    void setInstances(int instances);

Q_SIGNALS:
    void timeChanged();
    void instancesChanged();

protected:
    QSGNode *updatePaintNode(QSGNode *oldNode, UpdatePaintNodeData *) override;

private:
    qreal m_time = 0.0;
    int m_instances = 4096;
};

// QML module "SrpssNativeSpike 1.0", type "QuadField". Called from PyInit.
void registerQmlTypes();

} // namespace srpss_spike
