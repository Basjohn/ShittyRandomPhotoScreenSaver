"""The application icon's one owner: where ``SRPSS.ico`` is, and the icon every product window carries.

``main.py`` sets the application icon from :func:`application_icon` right after constructing the application, and every
standalone top-level window that has a taskbar button of its own (the Studio) applies the same icon with
:func:`apply_application_icon`. Qt never reads the executable's embedded icon by itself: it registers its window class
with an ``IDI_ICON1`` resource, which Nuitka's icon resource does not carry, so a top-level ``HWND`` without an icon
shows Windows' default application box on the taskbar.

Where the icon is:

* source: ``SRPSS.ico`` at the repository root;
* Nuitka onedir (the Dashboard): beside the executable, which is the distribution root every compiled module's
  ``__file__`` is relative to;
* Nuitka onefile (``SRPSS_Screensaver.scr``, ``SRPSS_Screensaver_Diagnostic.scr``): in the extraction folder (``--onefile-tempdir-spec``),
  again the root of every compiled module's ``__file__`` and the folder of the running executable; the launcher's own
  folder (``System32``, ``release/screensaver``) holds only the ``.scr``.

A candidate counts only when Qt can decode it (a file that exists but cannot be read is skipped, never set as an empty
icon). When no candidate decodes, a Windows process takes the icon resource of its own executable (every SRPSS
Windows build embeds ``SRPSS.ico`` with ``--windows-icon-from-ico``).

QtGui only (no QtWidgets, R-176), imported inside the functions: the worker processes never import this module.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Iterable

ICON_FILE_NAME = "SRPSS.ico"

#: The repository root in source, the distribution root in a compiled build (this module is ``ui/app_icon.py``).
_PACKAGE_ROOT = Path(__file__).resolve().parents[1]

#: The square sizes taken from an executable's icon resource when no icon file decodes.
_RESOURCE_SIZES = (16, 24, 32, 48, 64, 128, 256)

_cached_icon = None
_cached_source = ""


def _process_executable() -> str:
    """The running process's own image (the extracted executable of a onefile build); ``sys.executable`` elsewhere."""
    if sys.platform == "win32":
        try:
            import ctypes
            buffer = ctypes.create_unicode_buffer(32768)
            length = ctypes.windll.kernel32.GetModuleFileNameW(None, buffer, len(buffer))
            if length:
                return buffer.value
        except Exception:
            pass
    return str(getattr(sys, "executable", "") or "")


def icon_path_candidates(*, package_root: Path | str | None = None, executable: str | None = None,
                         launcher: str | None = None) -> list[Path]:
    """The places ``SRPSS.ico`` can be, in order: the package root, the running executable's folder, the launcher's
    folder (``sys.argv[0]``). The keyword arguments replace the live values (tests simulate frozen layouts)."""
    root = Path(package_root) if package_root is not None else _PACKAGE_ROOT
    executable = _process_executable() if executable is None else executable
    if launcher is None:
        launcher = sys.argv[0] if sys.argv else ""
    folders: list[Path] = [root]
    for value in (executable, launcher):
        if value:
            folders.append(Path(os.path.abspath(value)).parent)
    seen: set[str] = set()
    result: list[Path] = []
    for folder in folders:
        key = os.path.normcase(os.path.abspath(str(folder)))
        if key not in seen:
            seen.add(key)
            result.append(folder / ICON_FILE_NAME)
    return result


def _decodes(path: Path) -> bool:
    if not path.is_file():
        return False
    from PySide6.QtGui import QImageReader
    reader = QImageReader(str(path))
    return reader.canRead()


def application_icon_path(candidates: Iterable[Path] | None = None) -> Path | None:
    """The first candidate (:func:`icon_path_candidates`) that exists and that Qt can decode, else None."""
    for candidate in (icon_path_candidates() if candidates is None else candidates):
        try:
            if _decodes(candidate):
                return candidate
        except Exception:
            continue
    return None


def _executable_resource_icon(executable: str):
    """The icon resource of ``executable`` at several sizes (Windows), or a null QIcon."""
    from PySide6.QtGui import QIcon, QImage, QPixmap
    icon = QIcon()
    if sys.platform != "win32" or not executable or not os.path.isfile(executable):
        return icon
    import ctypes
    from ctypes import wintypes
    shell32, user32 = ctypes.windll.shell32, ctypes.windll.user32
    extract = shell32.SHDefExtractIconW
    extract.restype = ctypes.c_long
    extract.argtypes = (wintypes.LPCWSTR, ctypes.c_int, wintypes.UINT, ctypes.POINTER(wintypes.HICON),
                        ctypes.POINTER(wintypes.HICON), wintypes.UINT)
    user32.DestroyIcon.argtypes = (wintypes.HICON,)
    for size in _RESOURCE_SIZES:
        large = wintypes.HICON()
        if extract(executable, 0, 0, ctypes.byref(large), None, size) != 0 or not large.value:
            continue
        try:
            image = QImage.fromHICON(large.value)
            if not image.isNull():
                icon.addPixmap(QPixmap.fromImage(image))
        finally:
            user32.DestroyIcon(large)
    return icon


def application_icon():
    """The application icon (cached): ``SRPSS.ico`` from :func:`application_icon_path`, else the running executable's
    own icon resource, else a null QIcon. Needs a QGuiApplication."""
    global _cached_icon, _cached_source
    from PySide6.QtGui import QIcon
    if _cached_icon is not None and not _cached_icon.isNull():
        return QIcon(_cached_icon)
    icon, source = QIcon(), ""
    path = application_icon_path()
    if path is not None:
        icon, source = QIcon(str(path)), str(path)
    if icon.isNull():
        executable = _process_executable()
        icon = _executable_resource_icon(executable)
        source = f"{executable} (icon resource)" if not icon.isNull() else ""
    if not icon.isNull():
        _cached_icon, _cached_source = icon, source
    return QIcon(icon)


def application_icon_source() -> str:
    """Where the cached application icon came from (a path), empty before one was found."""
    return _cached_source


def apply_application_icon(window) -> bool:
    """Give a standalone top-level QWindow the application icon (its native taskbar/title icon). True when applied."""
    icon = application_icon()
    if icon.isNull():
        return False
    window.setIcon(icon)
    return True


def native_window_has_icon(window) -> bool | None:
    """Whether the created native window carries a big or small icon (Windows ``WM_GETICON``); None elsewhere (other
    systems, the offscreen platform)."""
    if sys.platform != "win32":
        return None
    try:
        from PySide6.QtGui import QGuiApplication
        if QGuiApplication.platformName() != "windows":
            return None
        import ctypes
        from ctypes import wintypes
        send = ctypes.windll.user32.SendMessageW
        send.restype = ctypes.c_void_p
        send.argtypes = (wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)
        hwnd = int(window.winId())
        return bool(send(hwnd, 0x007F, 1, 0) or send(hwnd, 0x007F, 0, 0))  # WM_GETICON: ICON_BIG, ICON_SMALL
    except Exception:
        return None


__all__ = [
    "ICON_FILE_NAME",
    "application_icon",
    "application_icon_path",
    "application_icon_source",
    "apply_application_icon",
    "icon_path_candidates",
    "native_window_has_icon",
]
