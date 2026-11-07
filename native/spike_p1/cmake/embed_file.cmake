# Writes a C++ header holding one binary file (a .qsb) as a byte array, so the
# compiled module carries its shaders and needs no data files in a frozen build.
# Usage: cmake -DINPUT=<file> -DOUTPUT=<header> -DSYMBOL=<identifier> -P embed_file.cmake
file(READ "${INPUT}" _hex HEX)
string(LENGTH "${_hex}" _hex_len)
math(EXPR _size "${_hex_len} / 2")
string(REGEX REPLACE "([0-9a-f][0-9a-f])" "0x\\1," _bytes "${_hex}")
file(WRITE "${OUTPUT}"
    "// Generated from ${INPUT}; do not edit.\n"
    "#pragma once\n"
    "static const unsigned char ${SYMBOL}[] = {${_bytes}};\n"
    "static const unsigned int ${SYMBOL}_size = ${_size};\n")
