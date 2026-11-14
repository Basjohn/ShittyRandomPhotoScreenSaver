// An item's notifier (N3.8): item_notifier.h has the contract.
#include "item_notifier.h"

#include <QtCore/QMetaObject>
#include <QtQuick/QQuickItem>

namespace srpss_core {

void ItemNotifier::attach(QQuickItem *item)
{
    QMutexLocker lock(&m_mutex);
    m_item = item;
}

void ItemNotifier::detach()
{
    std::shared_ptr<TexturesLostListener> listener;
    {
        QMutexLocker lock(&m_mutex);
        m_item = nullptr;
        listener.swap(m_listener);
    }
    // `listener` is released here, on the GUI thread (a Python callable's reference goes with the GIL taken there).
}

void ItemNotifier::setListener(const std::shared_ptr<TexturesLostListener> &listener)
{
    std::shared_ptr<TexturesLostListener> previous;
    QMutexLocker lock(&m_mutex);
    previous = m_listener;
    m_listener = listener;
    lock.unlock();
    // `previous` goes here, on the GUI thread.
}

void ItemNotifier::jobFinished()
{
    m_jobsFinished.fetchAndAddOrdered(1);
    requestFrame();
}

void ItemNotifier::requestFrame()
{
    // Under the lock: the item cannot be deleted between the test and the post (its destructor detaches first, under the
    // same lock), and once posted Qt drops the event if the item goes before it is delivered.
    QMutexLocker lock(&m_mutex);
    QQuickItem *item = m_item;
    if (!item)
        return;
    m_frameRequests.fetchAndAddRelaxed(1);
    QMetaObject::invokeMethod(item, [item]() { item->update(); }, Qt::QueuedConnection);
}

void ItemNotifier::texturesLost(const QStringList &names)
{
    if (names.isEmpty())
        return;
    m_lostEdges.fetchAndAddRelaxed(1);
    QMutexLocker lock(&m_mutex);
    QQuickItem *item = m_item;
    if (!item)
        return;
    const std::weak_ptr<ItemNotifier> weak = weak_from_this();
    QMetaObject::invokeMethod(item, [weak, names]() {
        if (const std::shared_ptr<ItemNotifier> self = weak.lock())
            self->deliverLost(names);
    }, Qt::QueuedConnection);
}

void ItemNotifier::deliverLost(const QStringList &names)
{
    std::shared_ptr<TexturesLostListener> listener;
    {
        QMutexLocker lock(&m_mutex);
        if (!m_item)
            return;
        listener = m_listener;
    }
    m_lostDelivered.fetchAndAddRelaxed(1);
    if (listener)
        listener->texturesLost(names); // outside the lock: the owner may destroy the item from its callback
}

} // namespace srpss_core
