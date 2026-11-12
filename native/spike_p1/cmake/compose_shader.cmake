# N0.3: splices the shared text into a scene shader before qsb bakes it. The line "//@srpss_conventions" becomes the
# production conventions include (shaders/srpss_conventions.glsl) and "//@n03_common" the scenes' shared fragment
# declarations (shaders/n03_common.glsl).
# Usage: cmake -DINPUT=<source> -DOUTPUT=<composed> -DCONVENTIONS=<file> -DCOMMON=<file> -P compose_shader.cmake
file(READ "${INPUT}" _source)
file(READ "${CONVENTIONS}" _conventions)
file(READ "${COMMON}" _common)
string(REPLACE "//@srpss_conventions" "${_conventions}" _source "${_source}")
string(REPLACE "//@n03_common" "${_common}" _source "${_source}")
file(WRITE "${OUTPUT}" "${_source}")
