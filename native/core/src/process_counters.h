// The process's counters for lifecycle proofs (the N0.6 owners round's readings): handles, GDI and USER objects,
// threads, private bytes and working set. Read on demand only; nothing runs at rest.
#pragma once

#include <QtCore/QByteArray>

namespace srpss_core {

// One JSON object: handles, gdi_objects, user_objects, threads, private_mib, working_set_mib.
QByteArray processCountersJson();

} // namespace srpss_core
