#include "rhi_owned.h"

#include <QtCore/QHash>
#include <QtCore/QMutex>

namespace srpss_core {

namespace {

QMutex g_ownedMutex;
QHash<const QRhi *, int> g_ownedLive; // under g_ownedMutex; an entry goes when its count reaches zero
int g_ownedTotal = 0;                 // under g_ownedMutex

} // namespace

void rhiOwnedAdopted(const QRhi *rhi)
{
    QMutexLocker lock(&g_ownedMutex);
    ++g_ownedLive[rhi];
    ++g_ownedTotal;
}

void rhiOwnedRetired(const QRhi *rhi)
{
    QMutexLocker lock(&g_ownedMutex);
    const auto it = g_ownedLive.find(rhi);
    if (it != g_ownedLive.end() && --it.value() <= 0)
        g_ownedLive.erase(it);
    --g_ownedTotal;
}

int rhiOwnedLive(const QRhi *rhi)
{
    QMutexLocker lock(&g_ownedMutex);
    return g_ownedLive.value(rhi, 0);
}

int rhiOwnedLiveTotal()
{
    QMutexLocker lock(&g_ownedMutex);
    return g_ownedTotal;
}

} // namespace srpss_core
