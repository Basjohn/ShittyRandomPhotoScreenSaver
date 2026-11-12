# Splices the conventions include into a core shader before qsb bakes it: the line "//@srpss_conventions" becomes
# shaders/srpss_conventions.glsl, the production include's text (rendering/gl_programs/conventions.py
# SRPSS_CONVENTIONS_GLSL; tests/test_native_core_host.py keeps the two equal). qsb has no include path, so the include is
# spliced, as the N0.3 harness did. A shader without the marker is copied unchanged.
# Usage: cmake -DINPUT=<source> -DOUTPUT=<composed> -DCONVENTIONS=<file> -P compose_shader.cmake
file(READ "${INPUT}" _source)
file(READ "${CONVENTIONS}" _conventions)
string(REPLACE "//@srpss_conventions" "${_conventions}" _source "${_source}")
file(WRITE "${OUTPUT}" "${_source}")
