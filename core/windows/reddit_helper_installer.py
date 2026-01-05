"""
Install and trigger the Reddit helper worker executable.

This is responsible for copying the embedded helper payload to
``%ProgramData%\SRPSS\helper`` and launching it inside the interactive user
session so it can drain the ProgramData queue.
"""

from __future__ import annotations

import ctypes
import os
import pkgutil
import subprocess
import sys
from ctypes import wintypes
from datetime import datetime
from pathlib import Path

from core.logging.logger import get_logger
from core.windows import reddit_helper_bridge

logger = get_logger(__name__)

IS_WINDOWS = sys.platform == "win32"

HELPER_NAME = "SRPSS_RedditHelper.exe"
BASE_DIR = Path(os.getenv("PROGRAMDATA", r"C:\ProgramData")) / "SRPSS"
HELPER_DIR = BASE_DIR / "helper"
HELPER_PATH = HELPER_DIR / HELPER_NAME
HELPER_TASK_SENTINEL = HELPER_DIR / "task_registered.ok"
_HELPER_TASK_NAME = os.getenv("SRPSS_REDDIT_HELPER_TASK", r"SRPSS\RedditHelper")

_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True) if IS_WINDOWS else None
_advapi32 = ctypes.WinDLL("advapi32", use_last_error=True) if IS_WINDOWS else None
_wtsapi32 = ctypes.WinDLL("wtsapi32", use_last_error=True) if IS_WINDOWS else None

if IS_WINDOWS:
    CREATE_NO_WINDOW = 0x08000000
    CREATE_UNICODE_ENVIRONMENT = 0x00000400
    LOGON_WITH_PROFILE = 0x00000001
    _NO_WINDOW_FLAG = CREATE_NO_WINDOW
else:
    _NO_WINDOW_FLAG = 0

if IS_WINDOWS:
    TOKEN_ASSIGN_PRIMARY = 0x0001
    TOKEN_DUPLICATE = 0x0002
    TOKEN_QUERY = 0x0008
    TOKEN_ADJUST_PRIVILEGES = 0x0020
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
    SE_PRIVILEGE_ENABLED = 0x00000002
    _PRIVILEGES_REQUIRED = (
        "SeTcbPrivilege",
        "SeAssignPrimaryTokenPrivilege",
        "SeIncreaseQuotaPrivilege",
    )

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

    class LUID(ctypes.Structure):
        _fields_ = [
            ("LowPart", wintypes.DWORD),
            ("HighPart", wintypes.LONG),
        ]

    class LUID_AND_ATTRIBUTES(ctypes.Structure):
        _fields_ = [
            ("Luid", LUID),
            ("Attributes", wintypes.DWORD),
        ]

    class TOKEN_PRIVILEGES(ctypes.Structure):
        _fields_ = [
            ("PrivilegeCount", wintypes.DWORD),
            ("Privileges", LUID_AND_ATTRIBUTES * 1),
        ]

    ERROR_NOT_ALL_ASSIGNED = 1300

    _kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    _kernel32.CloseHandle.restype = wintypes.BOOL
    _kernel32.WTSGetActiveConsoleSessionId.restype = wintypes.DWORD
    _kernel32.GetCurrentProcess.restype = wintypes.HANDLE

    if _advapi32 is not None:
        _advapi32.DuplicateTokenEx.argtypes = [
            wintypes.HANDLE,
            wintypes.DWORD,
            ctypes.c_void_p,
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
        _advapi32.OpenProcessToken.argtypes = [
            wintypes.HANDLE,
            wintypes.DWORD,
            ctypes.POINTER(wintypes.HANDLE),
        ]
        _advapi32.OpenProcessToken.restype = wintypes.BOOL
        _advapi32.LookupPrivilegeValueW.argtypes = [
            wintypes.LPCWSTR,
            wintypes.LPCWSTR,
            ctypes.POINTER(LUID),
        ]
        _advapi32.LookupPrivilegeValueW.restype = wintypes.BOOL
        _advapi32.AdjustTokenPrivileges.argtypes = [
            wintypes.HANDLE,
            wintypes.BOOL,
            ctypes.POINTER(TOKEN_PRIVILEGES),
            wintypes.DWORD,
            ctypes.c_void_p,
            ctypes.c_void_p,
        ]
        _advapi32.AdjustTokenPrivileges.restype = wintypes.BOOL

    if _wtsapi32 is not None:
        _wtsapi32.WTSQueryUserToken.argtypes = [
            wintypes.ULONG,
            ctypes.POINTER(wintypes.HANDLE),
        ]
        _wtsapi32.WTSQueryUserToken.restype = wintypes.BOOL


_PRIVILEGES_READY = False


def _running_as_system() -> bool:
    username = os.getenv("USERNAME", "")
    domain = os.getenv("USERDOMAIN", "")
    qualified = f"{domain}\\{username}" if domain else username
    upper = qualified.strip().upper()
    return upper.endswith("\\SYSTEM") or upper == "SYSTEM" or upper.endswith("NT AUTHORITY\\SYSTEM")


def _prefer_scheduler_launch() -> bool:
    raw = os.getenv("SRPSS_PREFER_HELPER_SCHEDULER")
    if raw is not None:
        return raw.strip().lower() not in {"0", "false", "no"}
    return True


def _token_launch_enabled() -> bool:
    raw = os.getenv("SRPSS_ENABLE_HELPER_TOKEN")
    if raw is not None:
        return raw.strip().lower() in {"1", "true", "yes", "on"}
    # By default, avoid token launches when running as SYSTEM (Winlogon SCR).
    return not _running_as_system()


def _log_helper_event(message: str) -> None:
    try:
        log_dir = BASE_DIR / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / "scr_helper.log"
        stamp = datetime.utcnow().isoformat(timespec="seconds") + "Z"
        with log_file.open("a", encoding="utf-8") as handle:
            handle.write(f"{stamp} {message}\n")
    except Exception as e:
        logger.debug("[REDDIT] Exception suppressed: %s", e)


def _format_win32_error(error_code: int | None) -> str:
    if not error_code:
        return "Win32 error (no code)"
    try:
        message = ctypes.WinError(error_code).strerror
    except Exception as e:
        logger.debug("[REDDIT] Exception suppressed: %s", e)
        message = f"Win32 error {error_code}"
    return f"{message} (code={error_code})"


def ensure_helper_installed() -> Path | None:
    if not IS_WINDOWS:
        return None
    try:
        payload = pkgutil.get_data(
            "core.windows", f"helper_payload/{HELPER_NAME}"
        )
    except Exception as e:
        logger.debug("[REDDIT] Exception suppressed: %s", e)
        payload = None
    if not payload:
        logger.debug("[REDDIT-INSTALL] Helper payload missing in build")
        return None
    try:
        HELPER_DIR.mkdir(parents=True, exist_ok=True)
        existing = None
        if HELPER_PATH.exists():
            try:
                existing = HELPER_PATH.read_bytes()
            except Exception as e:
                logger.debug("[REDDIT] Exception suppressed: %s", e)
                existing = None
        if existing != payload:
            HELPER_PATH.write_bytes(payload)
            logger.info("[REDDIT-INSTALL] Helper payload refreshed at %s", HELPER_PATH)
        return HELPER_PATH
    except Exception as exc:
        logger.warning("[REDDIT-INSTALL] Failed to write helper payload: %s", exc)
        return None


def trigger_helper_run() -> bool:
    """
    Ensure helper is installed and launch it inside the active user session.
    """
    helper_exe = ensure_helper_installed()
    if helper_exe is None:
        return False
    queue_dir = reddit_helper_bridge.get_queue_dir()
    _maybe_register_helper_task(helper_exe, queue_dir)

    scheduler_first = _prefer_scheduler_launch()
    token_allowed = _token_launch_enabled()
    launch_cmd = f'"{helper_exe}" --queue "{queue_dir}"'

    def _try_scheduler() -> bool:
        if _trigger_helper_via_scheduler():
            logger.debug("[REDDIT-INSTALL] Helper triggered via scheduled task")
            return True
        return False

    def _try_token() -> bool:
        if not token_allowed:
            return False
        launched = _launch_as_active_user(launch_cmd)
        if launched:
            return True
        _log_helper_event("CreateProcessWithTokenW path failed; scheduler may still be available")
        return False

    attempts = []
    if scheduler_first:
        attempts.append(_try_scheduler)
    if token_allowed:
        attempts.append(_try_token)
    if not scheduler_first:
        attempts.append(_try_scheduler)

    for attempt in attempts:
        if attempt():
            return True

    logger.debug(
        "[REDDIT-INSTALL] Helper trigger failed (scheduler preferred=%s, token_allowed=%s)",
        scheduler_first,
        token_allowed,
    )
    return False


def _trigger_helper_via_scheduler() -> bool:
    if not IS_WINDOWS or not _HELPER_TASK_NAME:
        return False
    try:
        creation_flags = _NO_WINDOW_FLAG if _NO_WINDOW_FLAG else 0
        result = subprocess.run(
            [
                "schtasks",
                "/Run",
                "/TN",
                _HELPER_TASK_NAME,
            ],
            capture_output=True,
            text=True,
            check=False,
            creationflags=creation_flags,
        )
        if result.returncode == 0:
            _log_helper_event(f"schtasks fallback triggered {_HELPER_TASK_NAME}")
            return True
        logger.debug(
            "[REDDIT-INSTALL] schtasks fallback failed (rc=%s): %s",
            result.returncode,
            (result.stderr or result.stdout).strip(),
        )
        _log_helper_event(
            f"schtasks fallback failed (rc={result.returncode}): {(result.stderr or result.stdout).strip()}"
        )
    except Exception as exc:
        logger.debug("[REDDIT-INSTALL] schtasks fallback exception: %s", exc, exc_info=True)
        _log_helper_event(f"schtasks fallback exception: {exc}")
    return False


def _maybe_register_helper_task(helper_exe: Path, queue_dir: Path) -> None:
    if _running_as_system():
        return
    try:
        helper_exe.stat()
    except Exception as e:
        logger.debug("[REDDIT] Exception suppressed: %s", e)
        return
    sentinel_valid = False
    if HELPER_TASK_SENTINEL.exists():
        try:
            sentinel_mtime = HELPER_TASK_SENTINEL.stat().st_mtime
            helper_mtime = helper_exe.stat().st_mtime
            sentinel_valid = sentinel_mtime >= helper_mtime
        except Exception as e:
            logger.debug("[REDDIT] Exception suppressed: %s", e)
            sentinel_valid = False
    if sentinel_valid:
        return

    log_arg = BASE_DIR / "logs"
    cmd = [
        str(helper_exe),
        "--register-only",
        "--queue",
        str(queue_dir),
        "--log-dir",
        str(log_arg),
    ]
    try:
        creation_flags = _NO_WINDOW_FLAG if _NO_WINDOW_FLAG else 0
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
            creationflags=creation_flags,
        )
        if result.returncode == 0:
            HELPER_TASK_SENTINEL.parent.mkdir(parents=True, exist_ok=True)
            HELPER_TASK_SENTINEL.write_text(
                datetime.utcnow().isoformat(timespec="seconds") + "Z",
                encoding="utf-8",
            )
            logger.debug("[REDDIT-INSTALL] Helper scheduled task refreshed via register-only run")
        else:
            logger.debug(
                "[REDDIT-INSTALL] Helper register-only run failed (rc=%s): %s",
                result.returncode,
                (result.stderr or result.stdout).strip(),
            )
    except Exception as exc:
        logger.debug("[REDDIT-INSTALL] Helper register-only invocation failed: %s", exc, exc_info=True)


def _launch_as_active_user(command_line: str) -> bool:
    if not IS_WINDOWS or _advapi32 is None or _wtsapi32 is None or _kernel32 is None:
        logger.debug("[REDDIT-INSTALL] Required Windows APIs unavailable for token launch")
        _log_helper_event("Windows APIs unavailable for token launch")
        return False

    if not _ensure_privileges_enabled():
        logger.debug("[REDDIT-INSTALL] Required privileges could not be enabled")
        _log_helper_event("Failed to enable required privileges")
        return False

    session_id = _kernel32.WTSGetActiveConsoleSessionId()
    if session_id == 0xFFFFFFFF:
        logger.debug("[REDDIT-INSTALL] Invalid console session id")
        _log_helper_event("WTSGetActiveConsoleSessionId returned INVALID_SESSION")
        return False

    user_token = wintypes.HANDLE()
    if not _wtsapi32.WTSQueryUserToken(session_id, ctypes.byref(user_token)):
        error = ctypes.get_last_error()
        logger.debug("[REDDIT-INSTALL] WTSQueryUserToken failed: %s", error)
        _log_helper_event(f"WTSQueryUserToken failed: {_format_win32_error(error)}")
        return False

    primary_token = wintypes.HANDLE()
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
            logger.debug("[REDDIT-INSTALL] DuplicateTokenEx failed: %s", error)
            _log_helper_event(f"DuplicateTokenEx failed: {_format_win32_error(error)}")
            return False
        primary_token = duplicated
    finally:
        _kernel32.CloseHandle(user_token)

    proc_info = PROCESS_INFORMATION()
    try:
        startup = STARTUPINFOW()
        startup.cb = ctypes.sizeof(STARTUPINFOW)
        cmd_buffer = ctypes.create_unicode_buffer(command_line)
        success = _advapi32.CreateProcessWithTokenW(
            primary_token,
            LOGON_WITH_PROFILE,
            None,
            cmd_buffer,
            CREATE_NO_WINDOW | CREATE_UNICODE_ENVIRONMENT,
            None,
            None,
            ctypes.byref(startup),
            ctypes.byref(proc_info),
        )
        if not success:
            error = ctypes.get_last_error()
            logger.debug(
                "[REDDIT-INSTALL] CreateProcessWithTokenW failed: %s",
                error,
            )
            _log_helper_event(f"CreateProcessWithTokenW failed: {_format_win32_error(error)}")
            return False
        logger.debug("[REDDIT-INSTALL] Helper launched via user session")
        _log_helper_event("Helper launched via CreateProcessWithTokenW")
        return True
    finally:
        if proc_info.hProcess:
            _kernel32.CloseHandle(proc_info.hProcess)
        if proc_info.hThread:
            _kernel32.CloseHandle(proc_info.hThread)
        if primary_token:
            _kernel32.CloseHandle(primary_token)


def _ensure_privileges_enabled() -> bool:
    if not IS_WINDOWS or _advapi32 is None or _kernel32 is None:
        return False
    global _PRIVILEGES_READY
    if _PRIVILEGES_READY:
        return True

    process_handle = _kernel32.GetCurrentProcess()
    token_handle = wintypes.HANDLE()
    desired = TOKEN_ADJUST_PRIVILEGES | TOKEN_QUERY
    if not _advapi32.OpenProcessToken(process_handle, desired, ctypes.byref(token_handle)):
        error = ctypes.get_last_error()
        logger.debug("[REDDIT-INSTALL] OpenProcessToken failed: %s", error)
        _log_helper_event(f"OpenProcessToken failed: {_format_win32_error(error)}")
        return False

    success = True
    missing: list[str] = []
    try:
        for privilege in _PRIVILEGES_REQUIRED:
            if not _enable_privilege(token_handle, privilege):
                success = False
                missing.append(privilege)
    finally:
        _kernel32.CloseHandle(token_handle)

    _PRIVILEGES_READY = success
    if success:
        _log_helper_event("Token privileges enabled successfully")
    else:
        _log_helper_event(f"Token privileges missing: {', '.join(missing) or 'unknown'}")
    return success


def _enable_privilege(token: wintypes.HANDLE, privilege_name: str) -> bool:
    luid = LUID()
    if not _advapi32.LookupPrivilegeValueW(None, privilege_name, ctypes.byref(luid)):
        error = ctypes.get_last_error()
        logger.debug("[REDDIT-INSTALL] LookupPrivilegeValueW failed for %s: %s", privilege_name, error)
        _log_helper_event(
            f"LookupPrivilegeValueW failed for {privilege_name}: {_format_win32_error(error)}"
        )
        return False

    tp = TOKEN_PRIVILEGES()
    tp.PrivilegeCount = 1
    tp.Privileges[0].Luid = luid
    tp.Privileges[0].Attributes = SE_PRIVILEGE_ENABLED

    ctypes.set_last_error(0)
    if not _advapi32.AdjustTokenPrivileges(
        token,
        False,
        ctypes.byref(tp),
        0,
        None,
        None,
    ):
        error = ctypes.get_last_error()
        logger.debug("[REDDIT-INSTALL] AdjustTokenPrivileges failed for %s: %s", privilege_name, error)
        _log_helper_event(
            f"AdjustTokenPrivileges failed for {privilege_name}: {_format_win32_error(error)}"
        )
        return False
    post_error = ctypes.get_last_error()
    if post_error == ERROR_NOT_ALL_ASSIGNED:
        logger.debug("[REDDIT-INSTALL] Privilege %s not assigned to token", privilege_name)
        _log_helper_event(f"Privilege {privilege_name} not assigned to token (ERROR_NOT_ALL_ASSIGNED)")
        return False
    _log_helper_event(f"Privilege {privilege_name} enabled")
    return True
