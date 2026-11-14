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
//
// N2.9, the frame block by name: a generic mode's per-frame values come from its frame record, packed into its frame
// block the same way (packRecordField): the block member named as the record's field takes the field's numbers (a u32
// or an f64 one number an element, an f64x4 four), at the member's reflected offset, type and stride. A field fits a
// member only exactly (recordFieldFits): an f64 a float, an f64x4 a vec4, a u32 a uint or bool, or an int or float
// under a range rule that keeps it exact (at_most within int32 or 2^24, or boolean: audit N29 L7), an array the same
// length; nothing is truncated or padded.
#pragma once

#include "frame_abi_generated.h"

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
    int dimensions = 0;      // array dimensions (0: not an array)
    // Per element; 0 when the member is not packed (mat2, mat3, a double, a struct, a multi-dimensional array): set()
    // refuses it and unfilled() always lists it, so a shader member nobody can fill never draws as silent zeros.
    int components() const;
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

// N2.9: why the record's `field` cannot fill the block's `member` (empty: it fits exactly).
QString recordFieldFits(const BlockMember &member, const frame_abi::Field &field);

// N2.9: the record's `field` into the member of the same name; refused (with the reason) when the block has no such
// member, the field does not fit it, or the record is not long enough to hold the field.
bool packRecordField(BlockValues &block, const frame_abi::Field &field, const QByteArray &record, QString *error);

} // namespace srpss_core
