#include "quick_item.h"

#include <QtQml/qqml.h>
#include <QtQuick/QQuickWindow>

namespace srpss_spike {

ThreadProbe &nativeNodeProbe()
{
    static ThreadProbe probe;
    return probe;
}

QuadFieldNode::QuadFieldNode(QQuickWindow *window, int instances)
    : m_window(window), m_field(instances)
{
}

QuadFieldNode::~QuadFieldNode()
{
    releaseResources();
}

void QuadFieldNode::sync(const QSizeF &size, float timeSeconds)
{
    m_size = size;
    m_time = timeSeconds;
}

void QuadFieldNode::prepare()
{
    nativeNodeProbe().hit();
    QRhi *rhi = m_window ? m_window->rhi() : nullptr;
    QRhiCommandBuffer *cb = commandBuffer();
    QRhiRenderTarget *rt = renderTarget();
    if (!rhi || !cb || !rt)
        return;
    QRhiResourceUpdateBatch *updates = rhi->nextResourceUpdateBatch();
    if (m_field.ensure(rhi, rt->renderPassDescriptor(), rt->sampleCount(), updates)) {
        QMatrix4x4 unitToClip = *projectionMatrix() * *matrix();
        unitToClip.scale(float(m_size.width()), float(m_size.height()));
        const float aspect = float(m_size.width() / qMax<qreal>(1.0, m_size.height()));
        m_field.update(updates, unitToClip, m_time, aspect);
    }
    cb->resourceUpdate(updates);
}

void QuadFieldNode::render(const RenderState *)
{
    nativeNodeProbe().hit();
    QRhiCommandBuffer *cb = commandBuffer();
    QRhiRenderTarget *rt = renderTarget();
    if (!cb || !rt)
        return;
    const QSize px = rt->pixelSize();
    m_field.record(cb, QRhiViewport(0, 0, float(px.width()), float(px.height())));
}

void QuadFieldNode::releaseResources()
{
    m_field.release();
}

QSGRenderNode::StateFlags QuadFieldNode::changedStates() const
{
    return ViewportState;
}

QSGRenderNode::RenderingFlags QuadFieldNode::flags() const
{
    // QRhi only (no native API calls), and we stay inside rect().
    return BoundedRectRendering | NoExternalRendering;
}

QRectF QuadFieldNode::rect() const
{
    return QRectF(QPointF(0, 0), m_size);
}

QuadFieldItem::QuadFieldItem(QQuickItem *parent)
    : QQuickItem(parent)
{
    setFlag(ItemHasContents, true);
}

void QuadFieldItem::setTime(qreal time)
{
    if (qFuzzyCompare(m_time, time))
        return;
    m_time = time;
    Q_EMIT timeChanged();
    update();
}

void QuadFieldItem::setInstances(int instances)
{
    if (instances == m_instances || instances < 1)
        return;
    m_instances = instances;
    Q_EMIT instancesChanged();
    update();
}

QSGNode *QuadFieldItem::updatePaintNode(QSGNode *oldNode, UpdatePaintNodeData *)
{
    auto *node = static_cast<QuadFieldNode *>(oldNode);
    if (!node)
        node = new QuadFieldNode(window(), m_instances);
    node->sync(size(), float(m_time));
    node->markDirty(QSGNode::DirtyMaterial);
    return node;
}

void registerQmlTypes()
{
    qmlRegisterType<QuadFieldItem>("SrpssNativeSpike", 1, 0, "QuadField");
}

} // namespace srpss_spike
