# The SRPSS native core (Current_Plan.md item 8b, N2.1; decision D5.7): the product's CPython extension module
# _srpss_native_core (stable ABI, abi3), loaded into our PySide6 process and imported only by rendering/native/.
# Compiled only by .github/workflows/native-module.yml on GitHub (build.cmd is its one CMake invocation).
cmake_minimum_required(VERSION 3.26)
project(srpss_native_core VERSION 0.1.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# The Qt guard (carried over from native/spike_p1): the module must be compiled against exactly the Qt that PySide6
# ships (PySide6.QtCore.qVersion()), because QRhi carries no compatibility guarantee. One value for the whole
# repository: requirements.txt's PySide6==x.y.z pin (tools/native_sdk_fetch.py fetches that Qt's SDK; the build
# manifest is checked against the same pin).
set(_requirements "${CMAKE_CURRENT_SOURCE_DIR}/../../requirements.txt")
file(STRINGS "${_requirements}" _pyside6_pin REGEX "^PySide6==")
string(REGEX MATCH "^PySide6==([0-9]+\\.[0-9]+\\.[0-9]+)" _pyside6_match "${_pyside6_pin}")
if(NOT CMAKE_MATCH_1)
    message(FATAL_ERROR "${_requirements} pins no PySide6==x.y.z")
endif()
set(CORE_QT_VERSION "${CMAKE_MATCH_1}")

set(CORE_QSB "" CACHE FILEPATH "qsb.exe shipped in the PySide6 package")
set(CORE_VULKAN_INCLUDE "" CACHE PATH "Vulkan-Headers include dir (vulkan/vulkan.h)")
if(CORE_VULKAN_INCLUDE)
    # Lets Qt's own WrapVulkanHeaders lookup succeed (QVulkanInstance needs vulkan.h; D6 lives in this module).
    set(Vulkan_INCLUDE_DIR "${CORE_VULKAN_INCLUDE}" CACHE PATH "" FORCE)
endif()

find_package(Qt6 REQUIRED COMPONENTS Core Gui GuiPrivate Qml Quick)
if(NOT Qt6_VERSION VERSION_EQUAL CORE_QT_VERSION)
    message(FATAL_ERROR "Qt SDK ${Qt6_VERSION} != PySide6's Qt ${CORE_QT_VERSION}")
endif()

find_package(Python 3.10 REQUIRED COMPONENTS Interpreter Development.SABIModule)

if(NOT EXISTS "${CORE_QSB}")
    message(FATAL_ERROR "Set CORE_QSB to PySide6's qsb.exe")
endif()
if(NOT EXISTS "${CORE_VULKAN_INCLUDE}/vulkan/vulkan.h")
    message(FATAL_ERROR "Set CORE_VULKAN_INCLUDE to a Vulkan-Headers include directory")
endif()

# Shaders: every file in shaders/ (GLSL 440: .vert, .frag, .comp) is baked by PySide6's qsb for every shipped
# backend (SPIR-V, GLSL 430, HLSL 5.0, MSL 1.2; N1.7) into generated/<file>.qsb and embedded in the module, so a
# frozen build needs no data files. The workflow's staging requires one .qsb per shader source. Before the bake the
# conventions include (shaders/srpss_conventions.glsl, the production text; N0.3 rule 3) is spliced in at the line
# "//@srpss_conventions" (cmake/compose_shader.cmake): qsb has no include path.
set(_gen "${CMAKE_CURRENT_BINARY_DIR}/generated")
file(MAKE_DIRECTORY "${_gen}")
file(MAKE_DIRECTORY "${_gen}/composed")
set(_conventions "${CMAKE_CURRENT_SOURCE_DIR}/shaders/srpss_conventions.glsl")
file(GLOB _shader_sources CONFIGURE_DEPENDS
    "${CMAKE_CURRENT_SOURCE_DIR}/shaders/*.vert"
    "${CMAKE_CURRENT_SOURCE_DIR}/shaders/*.frag"
    "${CMAKE_CURRENT_SOURCE_DIR}/shaders/*.comp")
set(_shader_headers)
set(_shader_includes "#pragma once\n")
foreach(_src ${_shader_sources})
    get_filename_component(_file "${_src}" NAME)
    string(MAKE_C_IDENTIFIER "${_file}_qsb" _symbol)
    set(_composed "${_gen}/composed/${_file}")
    set(_qsb "${_gen}/${_file}.qsb")
    set(_hdr "${_gen}/${_symbol}.h")
    add_custom_command(
        OUTPUT "${_qsb}" "${_hdr}"
        COMMAND "${CMAKE_COMMAND}" -DINPUT=${_src} -DOUTPUT=${_composed} -DCONVENTIONS=${_conventions}
                -P "${CMAKE_CURRENT_SOURCE_DIR}/cmake/compose_shader.cmake"
        COMMAND "${CORE_QSB}" --glsl 430 --hlsl 50 --msl 12 -o "${_qsb}" "${_composed}"
        COMMAND "${CMAKE_COMMAND}" -DINPUT=${_qsb} -DOUTPUT=${_hdr} -DSYMBOL=${_symbol}
                -P "${CMAKE_CURRENT_SOURCE_DIR}/cmake/embed_file.cmake"
        DEPENDS "${_src}" "${_conventions}" "${CMAKE_CURRENT_SOURCE_DIR}/cmake/compose_shader.cmake"
                "${CMAKE_CURRENT_SOURCE_DIR}/cmake/embed_file.cmake"
        COMMENT "qsb ${_file}"
        VERBATIM)
    list(APPEND _shader_headers "${_hdr}")
    string(APPEND _shader_includes "#include \"${_symbol}.h\"\n")
endforeach()
file(WRITE "${_gen}/core_shaders.h.in" "${_shader_includes}")
configure_file("${_gen}/core_shaders.h.in" "${_gen}/core_shaders.h" COPYONLY)

set(_sources
    src/module.cpp
    src/host_adapter.cpp
    src/frame_driver.cpp
    src/probe_pass.cpp
    src/load_pass.cpp
    src/gpu_timer.cpp
    src/surfaces.cpp
    src/composite.cpp
    src/targets.cpp
    src/conventions.cpp
    src/vulkan_context.cpp
    src/thread_probe.cpp
    src/process_counters.cpp
    ${_shader_headers})

# Stable ABI (abi3) like PySide6 itself: one .pyd for every CPython >= 3.10.
Python_add_library(_srpss_native_core MODULE USE_SABI 3.10 WITH_SOABI ${_sources})
target_include_directories(_srpss_native_core PRIVATE "${_gen}" "${CORE_VULKAN_INCLUDE}")
target_compile_definitions(_srpss_native_core PRIVATE
    QT_NO_KEYWORDS
    SRPSS_NATIVE_CORE_VERSION="${PROJECT_VERSION}")
target_link_libraries(_srpss_native_core PRIVATE Qt6::Core Qt6::Gui Qt6::GuiPrivate Qt6::Qml Qt6::Quick)
if(MSVC)
    target_compile_options(_srpss_native_core PRIVATE /W4 /permissive- /Zc:__cplusplus /utf-8)
    # No FH4 exception handler (compile /d2FH4-, link /d2:-FH4-): the module then imports nothing from
    # vcruntime140_1.dll, whose in-process copy is shiboken6's, older than the runner's compiler (build round 1 of
    # N2.1: 14.44 against cl 19.51). It needs only vcruntime140.dll, Python's own copy, at least as new as the compiler.
    # rendering/native/runtime_check.py refuses the module otherwise.
    target_compile_options(_srpss_native_core PRIVATE /d2FH4-)
    target_link_options(_srpss_native_core PRIVATE /d2:-FH4-)
endif()
