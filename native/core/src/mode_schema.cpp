// A mode's frame schema handed to the core at run time (N2.9): mode_schema.h has the contract.
#include "mode_schema.h"

#include <QtCore/QCryptographicHash>
#include <QtCore/QJsonArray>
#include <QtCore/QJsonDocument>
#include <QtCore/QJsonParseError>
#include <QtCore/QStringList>

#include <cmath>
#include <cstring>

namespace srpss_core {

namespace fa = frame_abi;

namespace {

constexpr quint32 kMaxRecordBytes = 65536; // far above any record (Spectrum's is 1488); a slot must hold it anyway
constexpr int kMaxFields = 256;
constexpr quint32 kMaxCount = 4096;

const char *kindName(fa::FieldKind kind)
{
    switch (kind) {
    case fa::FieldKind::U32: return "u32";
    case fa::FieldKind::F64: return "f64";
    case fa::FieldKind::F64x4: return "f64x4";
    }
    return "";
}

const char *checkName(fa::FieldCheck check)
{
    switch (check) {
    case fa::FieldCheck::None: return "";
    case fa::FieldCheck::AtMost: return "at_most";
    case fa::FieldCheck::Boolean: return "boolean";
    case fa::FieldCheck::Enum: return "enum";
    }
    return "";
}

quint32 elementBytes(fa::FieldKind kind)
{
    return kind == fa::FieldKind::U32 ? 4u : kind == fa::FieldKind::F64 ? 8u : 32u;
}

// native_schema.NativeLayout.build's alignment: arrays and four-component values 16, an f64 8, a u32 4.
quint32 alignmentOf(fa::FieldKind kind, quint32 count)
{
    if (count > 1 || kind == fa::FieldKind::F64x4)
        return 16u;
    return kind == fa::FieldKind::F64 ? 8u : 4u;
}

bool u32Value(const QJsonValue &value, quint32 *out)
{
    if (!value.isDouble())
        return false;
    const double number = value.toDouble();
    if (!(number >= 0.0 && number <= 4294967295.0) || number != std::floor(number))
        return false;
    *out = quint32(number);
    return true;
}

bool identifier(const QByteArray &text)
{
    if (text.isEmpty() || text.size() > 64)
        return false;
    for (const char c : text) {
        if (!((c >= 'a' && c <= 'z') || (c >= '0' && c <= '9') || c == '_'))
            return false;
    }
    return true;
}

} // namespace

QByteArray RuntimeSchema::fingerprintOf(const fa::Field *fields, quint32 count, quint32 recordBytes)
{
    // NativeLayout places its fields in increasing offsets, so the offset order is its own order.
    QList<const fa::Field *> ordered;
    for (quint32 i = 0; i < count; ++i)
        ordered.append(&fields[i]);
    for (int i = 1; i < ordered.size(); ++i) { // insertion sort: a few dozen fields, no STL algorithm
        const fa::Field *current = ordered.at(i);
        int j = i - 1;
        while (j >= 0 && ordered.at(j)->offset > current->offset) {
            ordered[j + 1] = ordered.at(j);
            --j;
        }
        ordered[j + 1] = current;
    }
    QByteArray text = QByteArrayLiteral("payload_schema:u32:1:0;record_bytes:u32:1:4");
    for (const fa::Field *field : ordered) {
        text += ';';
        text += field->name;
        text += ':';
        text += kindName(field->kind);
        text += ':';
        text += QByteArray::number(field->count);
        text += ':';
        text += QByteArray::number(field->offset);
    }
    text += ";size=";
    text += QByteArray::number(recordBytes);
    return QCryptographicHash::hash(text, QCryptographicHash::Sha256).toHex().left(16);
}

QSharedPointer<const RuntimeSchema> RuntimeSchema::fromJson(const QByteArray &json, QString *error)
{
    QJsonParseError parse;
    const QJsonDocument document = QJsonDocument::fromJson(json, &parse);
    if (parse.error != QJsonParseError::NoError || !document.isObject()) {
        *error = QStringLiteral("a mode's schema is a JSON object (rendering/native/mode.py schema_table_entry)");
        return {};
    }
    return fromJson(document.object(), error);
}

QSharedPointer<const RuntimeSchema> RuntimeSchema::fromJson(const QJsonObject &o, QString *error)
{
    const QStringList keys = { QStringLiteral("schema_id"), QStringLiteral("mode_id"), QStringLiteral("mode_code"),
                               QStringLiteral("version"), QStringLiteral("record_bytes"), QStringLiteral("fingerprint"),
                               QStringLiteral("fields"), QStringLiteral("check_order") };
    for (auto it = o.begin(); it != o.end(); ++it) {
        if (!keys.contains(it.key())) {
            *error = QStringLiteral("unknown schema key '%1' (%2)").arg(it.key(), keys.join(QStringLiteral(", ")));
            return {};
        }
    }
    QSharedPointer<RuntimeSchema> s(new RuntimeSchema);
    quint32 schemaId = 0;
    quint32 modeCode = 0;
    quint32 version = 0;
    quint32 recordBytes = 0;
    if (!u32Value(o.value(QStringLiteral("schema_id")), &schemaId)
        || !u32Value(o.value(QStringLiteral("mode_code")), &modeCode)
        || !u32Value(o.value(QStringLiteral("version")), &version)
        || !u32Value(o.value(QStringLiteral("record_bytes")), &recordBytes)) {
        *error = QStringLiteral("schema_id, mode_code, version and record_bytes are u32 numbers");
        return {};
    }
    s->m_modeId = o.value(QStringLiteral("mode_id")).toString().toLatin1();
    if (!identifier(s->m_modeId)) {
        *error = QStringLiteral("mode_id is a mode identifier (a-z, 0-9, _), not '%1'")
                     .arg(o.value(QStringLiteral("mode_id")).toString());
        return {};
    }
    // native_schema.native_schema_id: (version << 16) | 0x100 | mode code, both 1 to 255.
    if (modeCode < 1 || modeCode > 0xFF || version < 1 || version > 0xFF
        || schemaId != ((version << 16) | fa::kNativeBase | modeCode)) {
        *error = QStringLiteral("schema 0x%1 is not the native id of mode code %2, version %3")
                     .arg(schemaId, 0, 16).arg(modeCode).arg(version);
        return {};
    }
    for (const fa::ModeCode &mode : fa::kModeCodes) {
        const bool sameId = std::strcmp(mode.modeId, s->m_modeId.constData()) == 0;
        if (sameId != (mode.code == modeCode)) {
            *error = QStringLiteral("mode '%1' with code %2 disagrees with the compiled mode table ('%3' is %4)")
                         .arg(QString::fromLatin1(s->m_modeId)).arg(modeCode)
                         .arg(QLatin1String(mode.modeId)).arg(mode.code);
            return {};
        }
    }
    for (const fa::Schema &compiled : fa::kSchemas) {
        if (compiled.schemaId == schemaId) {
            *error = QStringLiteral("schema 0x%1 is compiled in (a hand-written consumer's); it is not replaced at run "
                                    "time").arg(schemaId, 0, 16);
            return {};
        }
    }
    if (recordBytes < 16 || recordBytes % 16 || recordBytes > kMaxRecordBytes) {
        *error = QStringLiteral("record_bytes %1 is not a multiple of 16 from 16 to %2").arg(recordBytes)
                     .arg(kMaxRecordBytes);
        return {};
    }
    const QJsonArray rows = o.value(QStringLiteral("fields")).toArray();
    if (rows.isEmpty() || rows.size() > kMaxFields) {
        *error = QStringLiteral("a schema names 1 to %1 fields").arg(kMaxFields);
        return {};
    }
    // Names first (the fields point into them, and nothing is appended after).
    for (const QJsonValue &rowValue : rows) {
        const QJsonArray row = rowValue.toArray();
        if (row.size() != 6 || !row.at(0).isString()) {
            *error = QStringLiteral("a field row is [name, kind, count, offset, check, limit]");
            return {};
        }
        const QByteArray name = row.at(0).toString().toLatin1();
        if (!identifier(name) || name == "payload_schema" || name == "record_bytes" || s->m_names.contains(name)) {
            *error = QStringLiteral("field name '%1' is not an identifier, is a header word, or repeats")
                         .arg(row.at(0).toString());
            return {};
        }
        s->m_names.append(name);
    }
    for (int i = 0; i < rows.size(); ++i) {
        const QJsonArray row = rows.at(i).toArray();
        const QString name = row.at(0).toString();
        fa::Field field {};
        field.name = s->m_names.at(i).constData();
        const QString kind = row.at(1).toString();
        if (kind == QLatin1String("u32"))
            field.kind = fa::FieldKind::U32;
        else if (kind == QLatin1String("f64"))
            field.kind = fa::FieldKind::F64;
        else if (kind == QLatin1String("f64x4"))
            field.kind = fa::FieldKind::F64x4;
        else {
            *error = QStringLiteral("field '%1': kind '%2' is not u32, f64 or f64x4").arg(name, kind);
            return {};
        }
        if (!u32Value(row.at(2), &field.count) || field.count < 1 || field.count > kMaxCount
            || !u32Value(row.at(3), &field.offset) || !u32Value(row.at(5), &field.limit)) {
            *error = QStringLiteral("field '%1': count (1 to %2), offset and limit are u32 numbers").arg(name)
                         .arg(kMaxCount);
            return {};
        }
        const QString check = row.at(4).toString();
        if (check.isEmpty())
            field.check = fa::FieldCheck::None;
        else if (check == QLatin1String("at_most"))
            field.check = fa::FieldCheck::AtMost;
        else if (check == QLatin1String("boolean"))
            field.check = fa::FieldCheck::Boolean;
        else if (check == QLatin1String("enum"))
            field.check = fa::FieldCheck::Enum;
        else {
            *error = QStringLiteral("field '%1': check '%2' is not at_most, boolean or enum").arg(name, check);
            return {};
        }
        if (field.check != fa::FieldCheck::None && (field.kind != fa::FieldKind::U32 || field.count != 1)) {
            *error = QStringLiteral("field '%1': a range rule applies to a u32 scalar only").arg(name);
            return {};
        }
        const quint64 end = quint64(field.offset) + quint64(elementBytes(field.kind)) * field.count;
        if (field.offset < 8 || field.offset % alignmentOf(field.kind, field.count) || end > recordBytes) {
            *error = QStringLiteral("field '%1': offset %2 is not aligned to %3, overlaps the header words or ends "
                                    "past the %4-byte record").arg(name).arg(field.offset)
                         .arg(alignmentOf(field.kind, field.count)).arg(recordBytes);
            return {};
        }
        for (const fa::Field &other : s->m_fields) {
            const quint64 otherEnd = quint64(other.offset) + quint64(elementBytes(other.kind)) * other.count;
            if (field.offset < otherEnd && other.offset < end) {
                *error = QStringLiteral("field '%1' overlaps '%2'").arg(name, QLatin1String(other.name));
                return {};
            }
        }
        s->m_fields.append(field);
    }
    const QJsonArray order = o.value(QStringLiteral("check_order")).toArray();
    int checked = 0;
    for (const fa::Field &field : s->m_fields)
        checked += field.check != fa::FieldCheck::None ? 1 : 0;
    for (const QJsonValue &value : order) {
        quint32 index = 0;
        if (!u32Value(value, &index) || index >= quint32(s->m_fields.size())
            || s->m_fields.at(int(index)).check == fa::FieldCheck::None || s->m_checkOrder.contains(index)) {
            *error = QStringLiteral("check_order names each field with a range rule once, by its index");
            return {};
        }
        s->m_checkOrder.append(index);
    }
    if (s->m_checkOrder.size() != checked) {
        *error = QStringLiteral("check_order leaves out a field with a range rule");
        return {};
    }
    const QByteArray fingerprint = fingerprintOf(s->m_fields.constData(), quint32(s->m_fields.size()), recordBytes);
    if (o.value(QStringLiteral("fingerprint")).toString().toLatin1() != fingerprint) {
        *error = QStringLiteral("the fingerprint %1 is not the one the fields give (%2)")
                     .arg(o.value(QStringLiteral("fingerprint")).toString(), QString::fromLatin1(fingerprint));
        return {};
    }
    s->m_fingerprint = fingerprint;
    s->m_schema.modeId = s->m_modeId.constData();
    s->m_schema.modeCode = modeCode;
    s->m_schema.version = version;
    s->m_schema.schemaId = schemaId;
    s->m_schema.recordBytes = recordBytes;
    s->m_schema.fingerprint = s->m_fingerprint.constData();
    s->m_schema.fields = s->m_fields.constData();
    s->m_schema.fieldCount = quint32(s->m_fields.size());
    s->m_schema.checkOrder = s->m_checkOrder.isEmpty() ? nullptr : s->m_checkOrder.constData();
    s->m_schema.checkCount = quint32(s->m_checkOrder.size());
    return s;
}

const fa::Field *RuntimeSchema::field(const QByteArray &name) const
{
    for (const fa::Field &field : m_fields) {
        if (name == field.name)
            return &field;
    }
    return nullptr;
}

QJsonObject RuntimeSchema::toJson() const
{
    QJsonObject o;
    o.insert(QStringLiteral("schema_id"), double(m_schema.schemaId));
    o.insert(QStringLiteral("mode_id"), QString::fromLatin1(m_modeId));
    o.insert(QStringLiteral("mode_code"), double(m_schema.modeCode));
    o.insert(QStringLiteral("version"), double(m_schema.version));
    o.insert(QStringLiteral("record_bytes"), double(m_schema.recordBytes));
    o.insert(QStringLiteral("fingerprint"), QString::fromLatin1(m_fingerprint));
    QJsonArray fields;
    for (const fa::Field &f : m_fields) {
        fields.append(QJsonArray { QLatin1String(f.name), QLatin1String(kindName(f.kind)), double(f.count),
                                   double(f.offset), QLatin1String(checkName(f.check)), double(f.limit) });
    }
    o.insert(QStringLiteral("fields"), fields);
    QJsonArray order;
    for (quint32 index : m_checkOrder)
        order.append(double(index));
    o.insert(QStringLiteral("check_order"), order);
    return o;
}

} // namespace srpss_core
