"""
Session-aware Windows URL launcher used by the native screensaver.

When SRPSS runs as a frozen .scr/.exe on the Winlogon desktop, launching
Reddit links via QDesktopServices fails because the spawned browser
inherits the secure desktop.  This module provides a minimal helper that
starts a short-lived Windows process on the standard ``winsta0\\default``
desktop so the user's default browser can complete its activation.
"""

from __future__ import annotations

import os
import sys
import ctypes
from ctypes import wintypes
from typing import Optional
import builtins

from core.logging.logger import get_logger

logger = get_logger(__name__)

IS_WINDOWS = sys.platform == "win32"

_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True) if IS_WINDOWS else None
_advapi32 = ctypes.WinDLL("advapi32", use_last_error=True) if IS_WINDOWS else None
_wtsapi32 = ctypes.WinDLL("wtsapi32", use_last_error=True) if IS_WINDOWS else None


if IS_WINDOWS:
    CREATE_NEW_CONSOLE = 0x00000010
    CREATE_NO_WINDOW = 0x08000000
    CREATE_UNICODE_ENVIRONMENT = 0x00000400
    STARTF_USESHOWWINDOW = 0x00000001
    SW_HIDE = 0
    LOGON_WITH_PROFILE = 0x00000001

    TOKEN_ASSIGN_PRIMARY = 0x0001
    TOKEN_DUPLICATE = 0x0002
    TOKEN_QUERY = 0x0008
    TOKEN_ADJUST_DEFAULT = 0x0080
    TOKEN_ADJUST_SESSIONID = 0x0100
    TOKEN_ALL_NECESSARY = (
        TOKEN_ASSIGN_PRIMARY
        | TOKEN_DUPLICATE
        | TOKEN_QUERY
        | TOKEN_ADJUST_DEFAULT
        | TOKEN_ADJUST_SESSIONID
    )

    SecurityImpersonation = 2
    TokenPrimary = 1

    class STARTUPINFOW(ctypes.Structure):
        _fields_ = [
            ("cb", wintypes.DWORD),
            ("lpReserved", wintypes.LPWSTR),
            ("lpDesktop", wintypes.LPWSTR),
            ("lpTitle", wintypes.LPWSTR),
            ("dwX", wintypes.DWORD),
            ("dwY", wintypes.DWORD),
            ("dwXSize", wintypes.DWORD),
            ("dwYSize", wintypes.DWORD),
            ("dwXCountChars", wintypes.DWORD),
            ("dwYCountChars", wintypes.DWORD),
            ("dwFillAttribute", wintypes.DWORD),
            ("dwFlags", wintypes.DWORD),
            ("wShowWindow", wintypes.WORD),
            ("cbReserved2", wintypes.WORD),
            ("lpReserved2", ctypes.POINTER(ctypes.c_byte)),
            ("hStdInput", wintypes.HANDLE),
            ("hStdOutput", wintypes.HANDLE),
            ("hStdError", wintypes.HANDLE),
        ]

    class PROCESS_INFORMATION(ctypes.Structure):
        _fields_ = [
            ("hProcess", wintypes.HANDLE),
            ("hThread", wintypes.HANDLE),
            ("dwProcessId", wintypes.DWORD),
            ("dwThreadId", wintypes.DWORD),
        ]

    class SECURITY_ATTRIBUTES(ctypes.Structure):
        _fields_ = [
            ("nLength", wintypes.DWORD),
            ("lpSecurityDescriptor", ctypes.c_void_p),
            ("bInheritHandle", wintypes.BOOL),
        ]

    _kernel32.CreateProcessW.argtypes = [
        wintypes.LPCWSTR,
        wintypes.LPWSTR,
        ctypes.c_void_p,
        ctypes.c_void_p,
        wintypes.BOOL,
        wintypes.DWORD,
        ctypes.c_void_p,
        wintypes.LPCWSTR,
        ctypes.POINTER(STARTUPINFOW),
        ctypes.POINTER(PROCESS_INFORMATION),
    ]
    _kernel32.CreateProcessW.restype = wintypes.BOOL
    _kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    _kernel32.CloseHandle.restype = wintypes.BOOL
    _kernel32.WTSGetActiveConsoleSessionId.restype = wintypes.DWORD

    if _advapi32 is not None:
        _advapi32.DuplicateTokenEx.argtypes = [
            wintypes.HANDLE,
            wintypes.DWORD,
            ctypes.POINTER(SECURITY_ATTRIBUTES),
            wintypes.DWORD,
            wintypes.DWORD,
            ctypes.POINTER(wintypes.HANDLE),
        ]
        _advapi32.DuplicateTokenEx.restype = wintypes.BOOL

        _advapi32.CreateProcessWithTokenW.argtypes = [
            wintypes.HANDLE,
            wintypes.DWORD,
            wintypes.LPCWSTR,
            wintypes.LPWSTR,
            wintypes.DWORD,
            ctypes.c_void_p,
            wintypes.LPCWSTR,
            ctypes.POINTER(STARTUPINFOW),
            ctypes.POINTER(PROCESS_INFORMATION),
        ]
        _advapi32.CreateProcessWithTokenW.restype = wintypes.BOOL

    if _wtsapi32 is not None:
        _wtsapi32.WTSQueryUserToken.argtypes = [
            wintypes.ULONG,
            ctypes.POINTER(wintypes.HANDLE),
        ]
        _wtsapi32.WTSQueryUserToken.restype = wintypes.BOOL


def _truthy_env(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _is_mc_build() -> bool:
    exe0 = str(getattr(sys, "argv", [""])[0]).lower()
    return (
        "srpss mc" in exe0
        or "srpss_mc" in exe0
        or exe0.endswith("main_mc.py")
    )


def _is_frozen_runtime() -> bool:
    if bool(getattr(sys, "frozen", False)):
        return True
    try:
        return bool(getattr(builtins, "__compiled__", False))
    except Exception:
        return False


def should_use_session_launcher() -> bool:
    """Determine if the helper launch path should be used."""
    if not IS_WINDOWS:
        logger.debug("[SCR-HELPER] Disabled: platform is not Windows")
        return False
    if _truthy_env("SRPSS_DISABLE_REDDIT_HELPER"):
        logger.debug("[SCR-HELPER] Disabled via SRPSS_DISABLE_REDDIT_HELPER")
        return False
    if _truthy_env("SRPSS_FORCE_REDDIT_HELPER"):
        logger.debug("[SCR-HELPER] Forced via SRPSS_FORCE_REDDIT_HELPER")
        return True
    if _is_mc_build():
        logger.debug("[SCR-HELPER] Disabled: MC build detected")
        return False
    frozen = _is_frozen_runtime()
    logger.debug("[SCR-HELPER] Helper decision: frozen_runtime=%s", frozen)
    return frozen


def _get_rundll32_path() -> Optional[str]:
    system_root = os.environ.get("SystemRoot", r"C:\Windows")
    candidate = os.path.join(system_root, "System32", "rundll32.exe")
    if os.path.exists(candidate):
        return candidate
    candidate = os.path.join(system_root, "SysWOW64", "rundll32.exe")
    if os.path.exists(candidate):
        return candidate
    return None


def _create_process(command_line: str) -> bool:
    if not IS_WINDOWS:
        return False

    startup = STARTUPINFOW()
    startup.cb = ctypes.sizeof(STARTUPINFOW)
    desktop_buffer = ctypes.create_unicode_buffer("winsta0\\default")
    startup.lpDesktop = ctypes.cast(desktop_buffer, wintypes.LPWSTR)
    startup.dwFlags = STARTF_USESHOWWINDOW
    startup.wShowWindow = SW_HIDE

    proc_info = PROCESS_INFORMATION()
    # CreateProcessW requires a mutable buffer for the command line.
    cmd_buffer = ctypes.create_unicode_buffer(command_line)

    creation_flags = CREATE_NO_WINDOW | CREATE_NEW_CONSOLE

    logger.debug("[SCR-HELPER] CreateProcessW start: %s", command_line)

    success = _kernel32.CreateProcessW(
        None,
        cmd_buffer,
        None,
        None,
        False,
        creation_flags,
        None,
        None,
        ctypes.byref(startup),
        ctypes.byref(proc_info),
    )

    if not success:
        error = ctypes.get_last_error()
        try:
            message = ctypes.WinError(error).strerror
        except Exception:
            message = f"Win32 error {error}"
        logger.debug("[REDDIT] CreateProcessW failed: %s", message)
        return False

    # Close handles immediately; the helper process keeps running as needed.
    _kernel32.CloseHandle(proc_info.hProcess)
    _kernel32.CloseHandle(proc_info.hThread)
    logger.debug("[SCR-HELPER] CreateProcessW succeeded")
    return True


def launch_url_via_user_desktop(url: str) -> bool:
    """
    Launch ``url`` on the user desktop using a one-shot rundll32 process.

    Returns:
        True if the helper process was created successfully.
    """
    if not IS_WINDOWS:
        return False
    sanitized_url = url.replace('"', "")
    if _launch_via_user_session_token(sanitized_url):
        return True
    logger.debug("[SCR-HELPER] Token-based launch unavailable; falling back to rundll32")
    return _launch_via_rundll32(sanitized_url)


def _launch_via_rundll32(sanitized_url: str) -> bool:
    rundll32 = _get_rundll32_path()
    if not rundll32:
        logger.debug("[REDDIT] rundll32.exe not found; cannot use helper launcher")
        return False
    command_line = f'"{rundll32}" url.dll,FileProtocolHandler "{sanitized_url}"'
    logger.debug("[SCR-HELPER] Launching helper via rundll32 for URL: %s", sanitized_url)
    return _create_process(command_line)


def _launch_via_user_session_token(sanitized_url: str) -> bool:
    if not IS_WINDOWS or _advapi32 is None or _wtsapi32 is None or _kernel32 is None:
        return False

    rundll_path = _get_rundll32_path()
    if not rundll_path:
        logger.debug("[SCR-HELPER] Token launcher unavailable: rundll32 missing")
        return False

    session_id = _kernel32.WTSGetActiveConsoleSessionId()
    if session_id == 0xFFFFFFFF:
        logger.debug("[SCR-HELPER] WTSGetActiveConsoleSessionId returned INVALID_SESSION")
        return False

    primary_token = wintypes.HANDLE()
    user_token = wintypes.HANDLE()
    if not _wtsapi32.WTSQueryUserToken(session_id, ctypes.byref(user_token)):
        error = ctypes.get_last_error()
        logger.debug("[SCR-HELPER] WTSQueryUserToken failed: %s", error)
        return False

    try:
        duplicated = wintypes.HANDLE()
        success = _advapi32.DuplicateTokenEx(
            user_token,
            TOKEN_ALL_NECESSARY,
            None,
            SecurityImpersonation,
            TokenPrimary,
            ctypes.byref(duplicated),
        )
        if not success:
            error = ctypes.get_last_error()
            logger.debug("[SCR-HELPER] DuplicateTokenEx failed: %s", error)
            return False
        primary_token = duplicated
    finally:
        _kernel32.CloseHandle(user_token)

    try:
        command_line = f'"{rundll_path}" url.dll,FileProtocolHandler "{sanitized_url}"'

        startup = STARTUPINFOW()
        startup.cb = ctypes.sizeof(STARTUPINFOW)
        startup.dwFlags = STARTF_USESHOWWINDOW
        startup.wShowWindow = SW_HIDE

        proc_info = PROCESS_INFORMATION()
        cmd_buffer = ctypes.create_unicode_buffer(command_line)
        logon_flags = LOGON_WITH_PROFILE
        creation_flags = CREATE_NO_WINDOW | CREATE_UNICODE_ENVIRONMENT

        logger.debug("[SCR-HELPER] CreateProcessWithTokenW start: %s", command_line)
        success = _advapi32.CreateProcessWithTokenW(
            primary_token,
            logon_flags,
            None,
            cmd_buffer,
            creation_flags,
            None,
            None,
            ctypes.byref(startup),
            ctypes.byref(proc_info),
        )
        if not success:
            error = ctypes.get_last_error()
            logger.debug("[SCR-HELPER] CreateProcessWithTokenW failed: %s", error)
            return False

        _kernel32.CloseHandle(proc_info.hProcess)
        _kernel32.CloseHandle(proc_info.hThread)
        logger.debug("[SCR-HELPER] CreateProcessWithTokenW succeeded")
        return True
    finally:
        if primary_token:
            _kernel32.CloseHandle(primary_token)
