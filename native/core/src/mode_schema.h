// A mode's frame schema handed to the core at run time (Current_Plan.md item 8b, N2.9: generic mode content).
//
// The compiled-in table (frame_abi_generated.h, kSchemas) holds only the schemas a hand-written C++ consumer reads
// (Spectrum). A generic mode, drawn by the core from data alone, has no C++ of its own: its schema is the Python table
// (core/visualizer_engine/native_schema.py NativeSchema, in the row shape rendering/native/packet_reader.py
// python_schema_table gives: [name, kind, count, offset, check, limit], the check order, the fingerprint) handed over
// when its stream is bound, so a new mode, or a new field in a mode's record, needs no module build. The readers use the
// same table: the C++ packet reader admits the mode's slots by it (packet_reader.h: the runtime schema beside the
// compiled ones), and the core packs the mode's frame block from it by name (program_blocks.h packRecord).
//
// Nothing is taken on trust: the table is refused unless it is a fixed-layout record the transport rule admits (a
// well-formed native schema id agreeing with the mode code and version; the record's size a multiple of 16; every
// field at its kind's alignment, inside the record, after the two header words and overlapping no other; a range rule
// only on a u32 scalar, each applied once in the check order), its fingerprint is the one its own fields give
// (NativeLayout.fingerprint, recomputed here), its mode id and code agree with the compiled mode table where either
// appears there, and it does not replace a compiled schema.
#pragma once

#include "frame_abi_generated.h"

#include <QtCore/QByteArray>
#include <QtCore/QJsonObject>
#include <QtCore/QList>
#include <QtCore/QSharedPointer>
#include <QtCore/QString>

namespace srpss_core {

class RuntimeSchema
{
public:
    // The schema from its table (JSON object); null with `error` when refused.
    static QSharedPointer<const RuntimeSchema> fromJson(const QJsonObject &table, QString *error);
    static QSharedPointer<const RuntimeSchema> fromJson(const QByteArray &json, QString *error);

    RuntimeSchema(const RuntimeSchema &) = delete;
    RuntimeSchema &operator=(const RuntimeSchema &) = delete;

    // The table in the compiled table's own shape: the reader and the packer read either the same way.
    const frame_abi::Schema &schema() const { return m_schema; }
    const frame_abi::Field *field(const QByteArray &name) const;
    QJsonObject toJson() const;

    // NativeLayout.fingerprint() of these fields (the header words first, then every field in offset order).
    static QByteArray fingerprintOf(const frame_abi::Field *fields, quint32 count, quint32 recordBytes);

private:
    RuntimeSchema() = default;

    QByteArray m_modeId;
    QByteArray m_fingerprint;
    QList<QByteArray> m_names;    // the fields' names (m_fields point into them; nothing changes after construction)
    QList<frame_abi::Field> m_fields;
    QList<quint32> m_checkOrder;
    frame_abi::Schema m_schema {};
};

} // namespace srpss_core
