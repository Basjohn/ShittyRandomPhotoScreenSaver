# SRPSS P1 spike: a native QRhi renderer loaded into our PySide6 process as a
# CPython extension module (stable ABI). See README.md for the exact commands.
cmake_minimum_required(VERSION 3.26)
project(srpss_native_spike LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Must equal the Qt that PySide6 ships (PySide6.QtCore.qVersion()): QRhi has
# limited compatibility guarantees, so the module is rebuilt per Qt release.
# One value for the whole repository: requirements.txt's PySide6==x.y.z pin
# (tools/native_sdk_fetch.py fetches that Qt; the build manifest records it).
set(_requirements "${CMAKE_CURRENT_SOURCE_DIR}/../../requirements.txt")
file(STRINGS "${_requirements}" _pyside6_pin REGEX "^PySide6==")
string(REGEX MATCH "^PySide6==([0-9]+\\.[0-9]+\\.[0-9]+)" _pyside6_match "${_pyside6_pin}")
if(NOT CMAKE_MATCH_1)
    message(FATAL_ERROR "${_requirements} pins no PySide6==x.y.z")
endif()
set(SPIKE_QT_VERSION "${CMAKE_MATCH_1}")
option(SPIKE_WITH_QUICK "Build part B: the C++ QSGRenderNode + QML type (needs Qt Quick/Qml SDK)" ON)
set(SPIKE_QSB "" CACHE FILEPATH "qsb.exe shipped in the PySide6 package")
set(SPIKE_VULKAN_INCLUDE "" CACHE PATH "Vulkan-Headers include dir (vulkan/vulkan.h)")

if(SPIKE_VULKAN_INCLUDE)
    # Lets Qt's own WrapVulkanHeaders lookup succeed (QVulkanInstance needs vulkan.h).
    set(Vulkan_INCLUDE_DIR "${SPIKE_VULKAN_INCLUDE}" CACHE PATH "" FORCE)
endif()

set(_qt_components Core Gui GuiPrivate)
if(SPIKE_WITH_QUICK)
    list(APPEND _qt_components Qml Quick)
endif()
find_package(Qt6 REQUIRED COMPONENTS ${_qt_components})
if(NOT Qt6_VERSION VERSION_EQUAL SPIKE_QT_VERSION)
    message(FATAL_ERROR "Qt SDK ${Qt6_VERSION} != PySide6's Qt ${SPIKE_QT_VERSION}")
endif()
if(SPIKE_WITH_QUICK)
    set(CMAKE_AUTOMOC ON)
endif()

find_package(Python 3.10 REQUIRED COMPONENTS Interpreter Development.SABIModule)

if(NOT EXISTS "${SPIKE_QSB}")
    message(FATAL_ERROR "Set SPIKE_QSB to PySide6's qsb.exe")
endif()
if(NOT EXISTS "${SPIKE_VULKAN_INCLUDE}/vulkan/vulkan.h")
    message(FATAL_ERROR "Set SPIKE_VULKAN_INCLUDE to a Vulkan-Headers include directory")
endif()

# Shaders: GLSL 440 -> .qsb (SPIR-V + HLSL 5.0 + GLSL), embedded in the module.
set(_gen "${CMAKE_CURRENT_BINARY_DIR}/generated")
file(MAKE_DIRECTORY "${_gen}")
set(_shader_headers)
foreach(_stage vert frag)
    set(_src "${CMAKE_CURRENT_SOURCE_DIR}/shaders/quadfield.${_stage}")
    set(_qsb "${_gen}/quadfield.${_stage}.qsb")
    set(_hdr "${_gen}/quadfield_${_stage}_qsb.h")
    add_custom_command(
        OUTPUT "${_qsb}" "${_hdr}"
        COMMAND "${SPIKE_QSB}" --glsl "100 es,120,150" --hlsl 50 -o "${_qsb}" "${_src}"
        COMMAND "${CMAKE_COMMAND}" -DINPUT=${_qsb} -DOUTPUT=${_hdr}
                -DSYMBOL=quadfield_${_stage}_qsb
                -P "${CMAKE_CURRENT_SOURCE_DIR}/cmake/embed_file.cmake"
        DEPENDS "${_src}" "${CMAKE_CURRENT_SOURCE_DIR}/cmake/embed_file.cmake"
        COMMENT "qsb quadfield.${_stage}"
        VERBATIM)
    list(APPEND _shader_headers "${_hdr}")
endforeach()
file(WRITE "${_gen}/quadfield_shaders.h.in"
    "#pragma once\n#include \"quadfield_vert_qsb.h\"\n#include \"quadfield_frag_qsb.h\"\n")
configure_file("${_gen}/quadfield_shaders.h.in" "${_gen}/quadfield_shaders.h" COPYONLY)

# N0.7 (D9's proof, Qt Quick part only): the edge field's five compute stages, ported to Vulkan GLSL. The job
# service runs them on Vulkan only, so the .qsb holds SPIR-V alone (qsb's default target).
set(_n07_compute luma blur edges flood resolve)
set(_n07_shader_headers)
set(_n07_includes "#pragma once\n")
foreach(_name ${_n07_compute})
    set(_src "${CMAKE_CURRENT_SOURCE_DIR}/shaders/n07_edge_${_name}.comp")
    set(_qsb "${_gen}/n07_edge_${_name}.comp.qsb")
    set(_hdr "${_gen}/n07_edge_${_name}_comp_qsb.h")
    add_custom_command(
        OUTPUT "${_qsb}" "${_hdr}"
        COMMAND "${SPIKE_QSB}" -o "${_qsb}" "${_src}"
        COMMAND "${CMAKE_COMMAND}" -DINPUT=${_qsb} -DOUTPUT=${_hdr}
                -DSYMBOL=n07_edge_${_name}_comp_qsb
                -P "${CMAKE_CURRENT_SOURCE_DIR}/cmake/embed_file.cmake"
        DEPENDS "${_src}" "${CMAKE_CURRENT_SOURCE_DIR}/cmake/embed_file.cmake"
        COMMENT "qsb n07_edge_${_name}.comp"
        VERBATIM)
    list(APPEND _n07_shader_headers "${_hdr}")
    string(APPEND _n07_includes "#include \"n07_edge_${_name}_comp_qsb.h\"\n")
endforeach()
file(WRITE "${_gen}/n07_shaders.h.in" "${_n07_includes}")
configure_file("${_gen}/n07_shaders.h.in" "${_gen}/n07_shaders.h" COPYONLY)

set(_sources
    src/module.cpp
    src/quadfield.cpp
    src/rhi_offscreen.cpp
    src/gui_helpers.cpp
    src/image_stats.cpp
    src/thread_probe.cpp
    src/vk_n06.cpp
    ${_shader_headers})
if(SPIKE_WITH_QUICK)
    list(APPEND _sources src/quick_item.cpp src/quick_offscreen.cpp src/vk_n07.cpp ${_n07_shader_headers})
endif()

# Stable ABI (abi3) like PySide6 itself: one .pyd for every CPython >= 3.10.
Python_add_library(_srpss_native_spike MODULE USE_SABI 3.10 WITH_SOABI ${_sources})
target_include_directories(_srpss_native_spike PRIVATE "${_gen}" "${SPIKE_VULKAN_INCLUDE}")
target_compile_definitions(_srpss_native_spike PRIVATE QT_NO_KEYWORDS)
target_link_libraries(_srpss_native_spike PRIVATE Qt6::Core Qt6::Gui Qt6::GuiPrivate)
if(SPIKE_WITH_QUICK)
    target_compile_definitions(_srpss_native_spike PRIVATE SPIKE_WITH_QUICK)
    target_link_libraries(_srpss_native_spike PRIVATE Qt6::Qml Qt6::Quick)
endif()
if(MSVC)
    target_compile_options(_srpss_native_spike PRIVATE /W4 /permissive- /Zc:__cplusplus /utf-8)
endif()
