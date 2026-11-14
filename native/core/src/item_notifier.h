// An item's notifier (N3.8, D9 as built points 3 and 9): how the render thread and the job thread reach the GUI thread's
// item without calling into it. Each edge is queued to the GUI thread with the item as the context (Qt drops the event
// if the item is deleted first), and the item detaches the notifier in its destructor, under the notifier's lock, before
// anything else; so no thread ever touches a deleted item.
//
// - jobFinished (JobNotifier, the job thread): a job of the item's content published or failed: the item's update() is
//   queued, and its source's next sync sees the count change (so the surface records and the content commits).
// - texturesLost (the render thread): textures of the item's content were found lost (a node made again, a texture that
//   could not be created): the owner's listener (NativeMode.on_textures_lost) is called on the GUI thread with the names.
//   The edge, never a state read (N4.a's leftover).
#pragma once

#include "job_service.h"

#include <QtCore/QAtomicInteger>
#include <QtCore/QMutex>
#include <QtCore/QStringList>

#include <memory>

class QQuickItem;

namespace srpss_core {

// The owner's side of the lost edge (the module's: a Python callable). Called and released on the GUI thread only.
class TexturesLostListener
{
public:
    virtual ~TexturesLostListener() = default;
    virtual void texturesLost(const QStringList &names) = 0;
};

class ItemNotifier final : public JobNotifier, public std::enable_shared_from_this<ItemNotifier>
{
public:
    // GUI thread.
    void attach(QQuickItem *item);
    void detach();                         // the item's destructor: no edge reaches it afterwards; the listener goes
    void setListener(const std::shared_ptr<TexturesLostListener> &listener);

    // Any thread.
    void jobFinished() override;
    void requestFrame();
    void texturesLost(const QStringList &names);

    quint64 jobsFinished() const { return m_jobsFinished.loadAcquire(); }
    qint64 lostEdges() const { return m_lostEdges.loadRelaxed(); }
    qint64 lostDelivered() const { return m_lostDelivered.loadRelaxed(); }
    qint64 frameRequests() const { return m_frameRequests.loadRelaxed(); }

private:
    void deliverLost(const QStringList &names); // GUI thread

    mutable QMutex m_mutex;
    QQuickItem *m_item = nullptr;                       // valid while attached (the item detaches before it goes)
    std::shared_ptr<TexturesLostListener> m_listener;   // GUI thread only (set, called, released)
    QAtomicInteger<quint64> m_jobsFinished { 0 };
    QAtomicInteger<qint64> m_lostEdges { 0 };
    QAtomicInteger<qint64> m_lostDelivered { 0 };
    QAtomicInteger<qint64> m_frameRequests { 0 };
};

} // namespace srpss_core
