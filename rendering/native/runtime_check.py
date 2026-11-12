"""The MSVC runtime origin check for the native core (P1 risk 4, `Docs/Future_Work/Native_Core_P1_Spike.md`).

The module is compiled on GitHub's runner with that image's MSVC, but it runs in a process whose C++ runtime DLLs were
loaded by others before it: ``msvcp140.dll`` is shiboken6's (PySide6's) copy, older than the compiler (P1 measured
14.44 against a 14.51 compiler), and ``vcruntime140.dll`` is Python's. Code built with a newer toolset than the
runtime it calls into is unsupported by Microsoft and fails in ways no test sees (code from 14.40 on, whose
``std::mutex`` constructor became constexpr, crashes against an older ``msvcp140``: a known failure of extension
modules in exactly this arrangement). So, read from the module file's own PE import table:

1. the module imports nothing from ``msvcp140*.dll`` (the core uses Qt's containers, threads and locks, which come
   from the same Qt DLLs PySide6 ships, never the STL DLL);
2. every symbol it imports from ``vcruntime140*.dll`` is exported by the copy this process loaded, and that copy is
   at least as new as the module's toolset (``_MSC_FULL_VER`` 19.xx is toolset 14.xx).

``rendering.native.loader`` runs the rule twice: before the import from the file alone (``check_file``: the import
table and the linker's toolset in the PE optional header, against the runtime copies already loaded), so a refused
module never runs code in the process; and after it with the compiler version the module reports (``check_module``).
Pure standard library, no Qt: the workflow's import check and the frozen probe go through that loader. On a platform
other than Windows there is nothing to check (the module is not built there).
"""
from __future__ import annotations

import os
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

STL_PREFIX = "msvcp140"           # msvcp140.dll, msvcp140_1.dll, msvcp140_2.dll, msvcp140_atomic_wait.dll, ...
VCRUNTIME_PREFIX = "vcruntime140"  # vcruntime140.dll, vcruntime140_1.dll

_IMAGE_DIRECTORY_EXPORT = 0
_IMAGE_DIRECTORY_IMPORT = 1
_IMAGE_DIRECTORY_DELAY_IMPORT = 13


class PeFormatError(ValueError):
    """The file is not a PE image this reader understands."""


@dataclass(frozen=True)
class _Image:
    data: bytes
    pe32_plus: bool
    directories: tuple[tuple[int, int], ...]
    sections: tuple[tuple[int, int, int], ...]          # (virtual address, size, file offset)
    linker: tuple[int, int]                             # MajorLinkerVersion, MinorLinkerVersion

    def offset(self, rva: int) -> int:
        for virtual, size, raw in self.sections:
            if virtual <= rva < virtual + size:
                return rva - virtual + raw
        raise PeFormatError(f"RVA 0x{rva:x} is in no section")

    def cstr(self, rva: int) -> str:
        start = self.offset(rva)
        end = self.data.index(b"\0", start)
        return self.data[start:end].decode("ascii", errors="replace")

    def directory(self, index: int) -> tuple[int, int]:
        return self.directories[index] if index < len(self.directories) else (0, 0)


def _image(path: Path) -> _Image:
    data = Path(path).read_bytes()
    try:
        return _parse_image(path, data)
    except struct.error as exc:                          # a header that runs past the end of the file
        raise PeFormatError(f"{path} is not a PE image ({exc})") from exc


def _parse_image(path: Path, data: bytes) -> _Image:
    if data[:2] != b"MZ":
        raise PeFormatError(f"{path} is not a PE image (no MZ header)")
    pe = struct.unpack_from("<I", data, 0x3C)[0]
    if data[pe:pe + 4] != b"PE\0\0":
        raise PeFormatError(f"{path} has no PE signature")
    sections, optional_size = struct.unpack_from("<H", data, pe + 6)[0], struct.unpack_from("<H", data, pe + 20)[0]
    optional = pe + 24
    magic = struct.unpack_from("<H", data, optional)[0]
    if magic == 0x20B:                                   # PE32+
        count_at, directories_at = optional + 108, optional + 112
    elif magic == 0x10B:                                 # PE32
        count_at, directories_at = optional + 92, optional + 96
    else:
        raise PeFormatError(f"{path} has an unknown optional header magic 0x{magic:x}")
    count = min(struct.unpack_from("<I", data, count_at)[0], 16)
    directories = tuple(struct.unpack_from("<II", data, directories_at + 8 * index) for index in range(count))
    table = optional + optional_size
    rows = []
    for index in range(sections):
        virtual_size, virtual, raw_size, raw = struct.unpack_from("<IIII", data, table + 40 * index + 8)
        rows.append((virtual, max(virtual_size, raw_size), raw))
    linker = (data[optional + 2], data[optional + 3])
    return _Image(data, magic == 0x20B, directories, tuple(rows), linker)


def _thunk_names(image: _Image, rva: int) -> set[str]:
    width, flag = (8, 1 << 63) if image.pe32_plus else (4, 1 << 31)
    names: set[str] = set()
    at = image.offset(rva)
    while True:
        value = int.from_bytes(image.data[at:at + width], "little")
        if value == 0:
            return names
        names.add(f"#{value & 0xFFFF}" if value & flag else image.cstr((value & 0x7FFFFFFF) + 2))
        at += width


def read_imports(path: Path) -> dict[str, frozenset[str]]:
    """Every DLL the image imports (lower-case name) with the symbols it takes from it; ordinals as ``#N``. Both the
    import table and the delay-load table are read."""
    image = _image(path)
    found: dict[str, set[str]] = {}
    rva, _size = image.directory(_IMAGE_DIRECTORY_IMPORT)
    if rva:
        at = image.offset(rva)
        while True:
            lookup, _stamp, _chain, name, address = struct.unpack_from("<IIIII", image.data, at)
            if not (lookup or name or address):
                break
            found.setdefault(image.cstr(name).lower(), set()).update(_thunk_names(image, lookup or address))
            at += 20
    rva, _size = image.directory(_IMAGE_DIRECTORY_DELAY_IMPORT)
    if rva:
        at = image.offset(rva)
        while True:
            attributes, name, _handle, address, lookup, _bound, _unload, _stamp = struct.unpack_from(
                "<IIIIIIII", image.data, at)
            if not (name or address or lookup):
                break
            if attributes & 1:                           # RVAs (every MSVC since 2005); old VA tables are skipped
                found.setdefault(image.cstr(name).lower(), set()).update(_thunk_names(image, lookup))
            at += 32
    return {dll: frozenset(names) for dll, names in found.items()}


def read_exports(path: Path) -> frozenset[str]:
    """The names (and ``#ordinal`` forms) an image exports."""
    image = _image(path)
    rva, _size = image.directory(_IMAGE_DIRECTORY_EXPORT)
    if not rva:
        return frozenset()
    at = image.offset(rva)
    base, functions, names, _functions_rva, names_rva = struct.unpack_from("<IIIII", image.data, at + 16)
    exported = {f"#{base + index}" for index in range(functions)}
    if names:
        table = image.offset(names_rva)
        for index in range(names):
            exported.add(image.cstr(struct.unpack_from("<I", image.data, table + 4 * index)[0]))
    return frozenset(exported)


def toolset_of(msc_full_ver: int) -> tuple[int, int]:
    """``_MSC_FULL_VER`` (194435227: cl 19.44) as the runtime version it needs (14.44)."""
    value = int(msc_full_ver)
    if value < 10_000_000:
        raise ValueError(f"not an _MSC_FULL_VER: {msc_full_ver!r}")
    major, minor = value // 10_000_000, value // 100_000 % 100
    if major != 19:
        raise ValueError(f"not an MSVC 14.x compiler (cl {major}.{minor})")
    return 14, minor


def linker_toolset(path: Path) -> tuple[int, int]:
    """The toolset that linked the image, from its PE optional header (``link`` 14.51: toolset 14.51, the same
    number as the compiler's cl 19.51 in one MSVC install). Read from the file, so before anything loads it."""
    major, minor = _image(path).linker
    if major != 14:
        raise ValueError(f"{path} was not linked by an MSVC 14.x toolset (link {major}.{minor})")
    return major, minor


def file_version(path: Path) -> tuple[int, int, int, int] | None:
    """A Windows image's fixed file version, or None where it cannot be read."""
    if os.name != "nt":
        return None
    import ctypes

    try:
        version = ctypes.WinDLL("version")
        size = version.GetFileVersionInfoSizeW(str(path), None)
        if not size:
            return None
        buffer = ctypes.create_string_buffer(size)
        if not version.GetFileVersionInfoW(str(path), 0, size, buffer):
            return None
        pointer, length = ctypes.c_void_p(), ctypes.c_uint()
        if not version.VerQueryValueW(buffer, "\\", ctypes.byref(pointer), ctypes.byref(length)) or not length.value:
            return None
        fixed = (ctypes.c_uint32 * 13).from_address(pointer.value)          # VS_FIXEDFILEINFO
        if fixed[0] != 0xFEEF04BD:
            return None
        return fixed[2] >> 16, fixed[2] & 0xFFFF, fixed[3] >> 16, fixed[3] & 0xFFFF
    except (OSError, AttributeError, ValueError):
        return None


def loaded_module_path(name: str) -> str | None:
    """Where this process loaded the DLL ``name`` from (None when it is not loaded, or off Windows)."""
    if os.name != "nt":
        return None
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.GetModuleHandleW.restype = wintypes.HMODULE
    kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
    kernel32.GetModuleFileNameW.restype = wintypes.DWORD
    kernel32.GetModuleFileNameW.argtypes = [wintypes.HMODULE, wintypes.LPWSTR, wintypes.DWORD]
    handle = kernel32.GetModuleHandleW(name)
    if not handle:
        return None
    buffer = ctypes.create_unicode_buffer(32768)
    length = kernel32.GetModuleFileNameW(handle, buffer, len(buffer))
    return buffer.value[:length] if length else None


def runtime_problems(
    imports: Mapping[str, frozenset[str]],
    msc_full_ver: int,
    loaded: Mapping[str, str | None],
    *,
    exports_of=read_exports,
    version_of=file_version,
) -> list[str]:
    """What is wrong with this module's MSVC runtime arrangement (empty when nothing is). ``imports`` is the module's
    import table (``read_imports``), ``loaded`` maps a DLL name to where the process loaded it from."""
    toolset = toolset_of(msc_full_ver)
    return toolset_problems(imports, toolset, f"cl 19.{toolset[1]}", loaded, exports_of=exports_of,
                            version_of=version_of)


def toolset_problems(
    imports: Mapping[str, frozenset[str]],
    toolset: tuple[int, int],
    source: str,
    loaded: Mapping[str, str | None],
    *,
    exports_of=read_exports,
    version_of=file_version,
) -> list[str]:
    """The rule itself, for a module built by MSVC ``toolset`` (14.xx); ``source`` names where that number was read
    (``cl 19.51`` from the module's ``_MSC_FULL_VER``, ``link 14.51`` from its file)."""
    problems: list[str] = []
    for dll in sorted(imports):
        if dll.startswith(STL_PREFIX):
            first = sorted(imports[dll])[:3]
            problems.append(
                f"the module imports {len(imports[dll])} symbol(s) from {dll} ({', '.join(first)}): the process's "
                f"{dll} is shiboken6's copy, older than the compiler (P1 risk 4); the core uses no STL DLL")
    for dll in sorted(imports):
        if not dll.startswith(VCRUNTIME_PREFIX):
            continue
        path = next((value for key, value in loaded.items() if key.lower() == dll and value), None)
        if path is None:
            problems.append(f"the module imports {dll}, but this process has not loaded it")
            continue
        missing = sorted(imports[dll] - exports_of(Path(path)))
        if missing:
            problems.append(f"{path} does not export {', '.join(missing[:5])} that the module imports")
        version = version_of(Path(path))
        if version is None:
            problems.append(f"the file version of {path} cannot be read")
        elif version[:2] < toolset:
            problems.append(
                f"{path} is {'.'.join(map(str, version))}, older than the module's toolset "
                f"{toolset[0]}.{toolset[1]} ({source}): the runtime must be at least as new as the compiler")
    return problems


def _loaded_runtimes(imports: Mapping[str, frozenset[str]]) -> dict[str, str | None]:
    return {dll: loaded_module_path(dll) for dll in imports if dll.startswith(VCRUNTIME_PREFIX)}


def check_file(module_path: Path, loaded: Mapping[str, str | None] | None = None) -> list[str]:
    """The rule for a module file this process has not imported yet: its import table and the toolset that linked it,
    both read from the file, against the runtime copies this process has already loaded (empty off Windows). The
    loader runs this before the import, so a module the rule refuses never runs any code in the process."""
    if os.name != "nt":
        return []
    path = Path(module_path)
    imports = read_imports(path)
    toolset = linker_toolset(path)
    return toolset_problems(imports, toolset, f"link {toolset[0]}.{toolset[1]}",
                            _loaded_runtimes(imports) if loaded is None else loaded)


def check_module(module_path: Path, msc_full_ver: int, loaded: Mapping[str, str | None] | None = None) -> list[str]:
    """``runtime_problems`` for the module file at ``module_path`` in this process (empty off Windows), with the
    compiler version the imported module reports about itself."""
    if os.name != "nt":
        return []
    imports = read_imports(Path(module_path))
    return runtime_problems(imports, msc_full_ver, _loaded_runtimes(imports) if loaded is None else loaded)
