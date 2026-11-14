#include "program_blocks.h"

#include <QtCore/QJsonArray>
#include <rhi/qshaderdescription.h>

#include <cstring>

namespace srpss_core {

namespace {

bool integerType(int type)
{
    const auto t = QShaderDescription::VariableType(type);
    return t == QShaderDescription::Int || t == QShaderDescription::Int2 || t == QShaderDescription::Int3
        || t == QShaderDescription::Int4 || t == QShaderDescription::Uint || t == QShaderDescription::Uint2
        || t == QShaderDescription::Uint3 || t == QShaderDescription::Uint4 || t == QShaderDescription::Bool
        || t == QShaderDescription::Bool2 || t == QShaderDescription::Bool3 || t == QShaderDescription::Bool4;
}

void writeScalar(char *at, int type, double value)
{
    if (integerType(type)) {
        const qint32 v = qint32(value);
        std::memcpy(at, &v, 4);
    } else {
        const float v = float(value); // round to nearest, as Python's struct.pack('<f') does
        std::memcpy(at, &v, 4);
    }
}

} // namespace

int BlockMember::components() const
{
    switch (QShaderDescription::VariableType(type)) {
    case QShaderDescription::Float:
    case QShaderDescription::Int:
    case QShaderDescription::Uint:
    case QShaderDescription::Bool:
        return 1;
    case QShaderDescription::Vec2:
    case QShaderDescription::Int2:
    case QShaderDescription::Uint2:
    case QShaderDescription::Bool2:
        return 2;
    case QShaderDescription::Vec3:
    case QShaderDescription::Int3:
    case QShaderDescription::Uint3:
    case QShaderDescription::Bool3:
        return 3;
    case QShaderDescription::Vec4:
    case QShaderDescription::Int4:
    case QShaderDescription::Uint4:
    case QShaderDescription::Bool4:
        return 4;
    case QShaderDescription::Mat4:
        return 16;
    default:
        return 0;
    }
}

BlockLayout BlockLayout::reflect(const QShader &shader, const QByteArray &blockName)
{
    BlockLayout layout;
    if (!shader.isValid())
        return layout;
    for (const QShaderDescription::UniformBlock &block : shader.description().uniformBlocks()) {
        if (block.blockName != blockName)
            continue;
        layout.m_valid = true;
        layout.m_name = block.blockName;
        layout.m_size = block.size;
        layout.m_binding = block.binding;
        for (const QShaderDescription::BlockVariable &variable : block.members) {
            BlockMember member;
            member.name = variable.name;
            member.type = int(variable.type);
            member.offset = variable.offset;
            member.count = variable.arrayDims.isEmpty() ? 1 : variable.arrayDims.first();
            member.stride = variable.arrayStride;
            if (member.count > 1 && member.stride <= 0) {
                // The baked shader reflects a scalar array's stride as 0 (N2.5 build round 1); std140 rounds every
                // array element up to a vec4.
                const int bytes = 4 * (member.components() > 0 ? member.components() : 1);
                member.stride = ((bytes + 15) / 16) * 16;
                member.strideInferred = true;
            }
            layout.m_members.append(member);
        }
        break;
    }
    return layout;
}

const BlockMember *BlockLayout::member(const QByteArray &name) const
{
    for (const BlockMember &member : m_members) {
        if (member.name == name)
            return &member;
    }
    return nullptr;
}

QJsonObject BlockLayout::toJson() const
{
    QJsonObject o;
    o.insert(QStringLiteral("name"), QString::fromLatin1(m_name));
    o.insert(QStringLiteral("size"), m_size);
    o.insert(QStringLiteral("binding"), m_binding);
    QJsonArray members;
    for (const BlockMember &member : m_members) {
        members.append(QJsonArray { QString::fromLatin1(member.name), member.type, member.offset, member.count,
                                    member.stride, member.strideInferred });
    }
    o.insert(QStringLiteral("members"), members);
    return o;
}

BlockValues::BlockValues(const BlockLayout &layout)
    : m_layout(layout), m_filled(layout.members().size(), false)
{
    m_bytes.fill('\0', layout.size());
}

bool BlockValues::set(const QByteArray &name, const double *values, int count, QString *error)
{
    const QList<BlockMember> &members = m_layout.members();
    for (int index = 0; index < members.size(); ++index) {
        const BlockMember &member = members.at(index);
        if (member.name != name)
            continue;
        const int components = member.components();
        if (components == 0) {
            *error = QStringLiteral("'%1' is not a packable member of %2")
                         .arg(QString::fromLatin1(name), QString::fromLatin1(m_layout.name()));
            return false;
        }
        const int whole = components * member.count;
        const bool array = member.count > 1;
        if (count <= 0 || count > whole || (!array && count != whole) || count % components != 0) {
            *error = QStringLiteral("'%1' takes %2 number(s), not %3")
                         .arg(QString::fromLatin1(name)).arg(whole).arg(count);
            return false;
        }
        char *data = m_bytes.data();
        for (int i = 0; i < count; ++i) {
            const int element = i / components;
            const int component = i % components;
            const int at = member.offset + element * (array ? member.stride : 0) + component * 4;
            if (at + 4 <= m_bytes.size())
                writeScalar(data + at, member.type, values[i]);
        }
        m_filled[index] = true;
        return true;
    }
    *error = QStringLiteral("'%1' is not a member of %2 (an unknown name is refused)")
                 .arg(QString::fromLatin1(name), QString::fromLatin1(m_layout.name()));
    return false;
}

bool BlockValues::setJson(const QJsonObject &values, QString *error)
{
    BlockValues staged = *this;
    for (auto it = values.begin(); it != values.end(); ++it) {
        QList<double> numbers;
        if (it.value().isDouble() || it.value().isBool()) {
            numbers.append(it.value().isBool() ? (it.value().toBool() ? 1.0 : 0.0) : it.value().toDouble());
        } else if (it.value().isArray()) {
            for (const QJsonValue &item : it.value().toArray()) {
                if (!item.isDouble()) {
                    *error = QStringLiteral("'%1' holds a value that is not a number").arg(it.key());
                    return false;
                }
                numbers.append(item.toDouble());
            }
        } else {
            *error = QStringLiteral("'%1' is not a number or a list of numbers").arg(it.key());
            return false;
        }
        if (!staged.set(it.key().toLatin1(), numbers.constData(), int(numbers.size()), error))
            return false;
    }
    *this = staged;
    return true;
}

QStringList BlockValues::unfilled() const
{
    QStringList names;
    const QList<BlockMember> &members = m_layout.members();
    for (int index = 0; index < members.size(); ++index) {
        if (!m_filled[index] && members.at(index).components() > 0)
            names.append(QString::fromLatin1(members.at(index).name));
    }
    return names;
}

QStringList BlockValues::filled() const
{
    QStringList names;
    const QList<BlockMember> &members = m_layout.members();
    for (int index = 0; index < members.size(); ++index) {
        if (m_filled[index])
            names.append(QString::fromLatin1(members.at(index).name));
    }
    return names;
}

} // namespace srpss_core
