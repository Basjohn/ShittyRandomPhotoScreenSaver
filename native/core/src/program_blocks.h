// Program blocks: a runtime-loaded shader's uniform blocks, packed by reflected name (N2.5's standing port rule).
//
// Every native port of a Visualizer mode draws its product fragment shader from the pack ``tools/regen_qrc.py
// --shaders`` bakes (loaded at run time from bytes Python hands over: no module rebuild for a shader change), and
// fills its std140 block by NAME:
// - values that come from Settings or the card are resolved in Python (the spec system) and handed over as
//   name -> number or list of numbers (setJson): packed at the reflected offset, type and array stride;
// - only per-frame and simulation arithmetic is hand-written C++, and it sets its members through the same set().
// An unknown name, or a value of the wrong size, is refused with a reason; unfilled() names every reflected member
// nobody set (a harness error: a member the shader reads that no side fills).
//
// std140: scalars and vectors at their offset, 4 bytes a component (ints as int32, floats as float32 rounded to
// nearest, as Python's struct.pack('<f')); arrays at the reflected stride, or 16 when the reflection reports 0 for a
// scalar array (build round 1 of N2.5); mat4 as 16 floats, column-major.
#pragma once

#include <QtCore/QByteArray>
#include <QtCore/QJsonObject>
#include <QtCore/QList>
#include <QtCore/QString>
#include <QtCore/QStringList>
#include <rhi/qshader.h>

namespace srpss_core {

struct BlockMember
{
    QByteArray name;
    int type = 0;            // QShaderDescription::VariableType
    int offset = 0;
    int count = 1;           // array elements (1 when not an array)
    int stride = 0;          // array stride in bytes
    bool strideInferred = false;
    int components() const;  // per element; 0 when the type is not packed (samplers, structs)
};

class BlockLayout
{
public:
    // The block named ``blockName`` of ``shader``; invalid when the shader has no such block.
    static BlockLayout reflect(const QShader &shader, const QByteArray &blockName);

    bool valid() const { return m_valid; }
    QByteArray name() const { return m_name; }
    int size() const { return m_size; }
    int binding() const { return m_binding; }
    const QList<BlockMember> &members() const { return m_members; }
    const BlockMember *member(const QByteArray &name) const;
    QJsonObject toJson() const;

private:
    bool m_valid = false;
    QByteArray m_name;
    int m_size = 0;
    int m_binding = -1;
    QList<BlockMember> m_members;
};

class BlockValues
{
public:
    BlockValues() = default;
    explicit BlockValues(const BlockLayout &layout);

    const BlockLayout &layout() const { return m_layout; }
    // ``count`` numbers for ``name`` (components x elements, elements in order); refused when the name is not a
    // member or the count is not the member's size (an array may be given fewer elements: the rest stay zero).
    bool set(const QByteArray &name, const double *values, int count, QString *error);
    bool set(const QByteArray &name, double value, QString *error) { return set(name, &value, 1, error); }
    // Every key of ``values``: a number, or an array of numbers; refused whole on the first bad key (nothing set).
    bool setJson(const QJsonObject &values, QString *error);
    QStringList unfilled() const;
    QStringList filled() const;
    const QByteArray &bytes() const { return m_bytes; }

private:
    BlockLayout m_layout;
    QByteArray m_bytes;
    QList<bool> m_filled;  // Qt containers only: the core imports nothing from the STL DLL (P1 risk 4)
};

} // namespace srpss_core
