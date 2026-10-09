#!/usr/bin/env python3
r"""
Python / Open-With registry repair GUI for Windows.

Purpose:
  * Repair stale Python Launcher (PEP 514) registration to a real interpreter.
  * Collapse the ugly Windows "Open with" Python duplicates to one canonical
    Python entry for .py/.pyw/.pyc without disturbing unrelated apps such as
    PyCharm, editors or PowerShell.
  * Remove dead Python shell/context-menu verbs and dead Python application
    registrations.
  * Purge stale Python Shell MuiCache labels so Explorer stops resurrecting
    dead entries.
  * Explain every failure instead of silently skipping it.

Default target:
    C:\Python314\python.exe

Every touched registry key is snapshotted to JSON before modification.
"""

from __future__ import annotations

import argparse
import base64
import ctypes
from dataclasses import dataclass, field
from datetime import datetime
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import threading
import traceback

if os.name != "nt":
    raise SystemExit("This utility is Windows-only.")

import winreg

try:
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
except Exception as exc:
    raise SystemExit(f"Tkinter is required for this GUI: {exc}") from exc


DEFAULT_TARGET = Path(r"C:\Python314\python.exe")
FILE_EXTS = (".py", ".pyw", ".pyc")
VIEWS = (winreg.KEY_WOW64_64KEY, winreg.KEY_WOW64_32KEY)
ROOTS = (
    ("HKCU", winreg.HKEY_CURRENT_USER),
    ("HKLM", winreg.HKEY_LOCAL_MACHINE),
)

PYTHON_APP_RE = re.compile(
    r"(?i)^(?:(?:python(?:w)?(?:\d+(?:\.\d+)?)?(?:_d)?)|(?:pyw?)|(?:idlew?))\.exe$"
)
PYTHONISH_RE = re.compile(r"(?i)(python|idle|py_auto_file|pythoncore|\.pyw?\b)")
ABS_PATH_RE = re.compile(
    r"""(?ix)
    "(?P<quoted>(?:[a-z]:\\|\\\\)[^"\r\n]+?\.(?:exe|pyw?|dll))"
    |
    (?P<plain>(?:[a-z]:\\|\\\\)[^\s"\r\n]+?\.(?:exe|pyw?|dll))
    """
)

KNOWN_SHELL_OWNERS = (
    "*",
    "Directory",
    r"Directory\Background",
    "Drive",
    "Folder",
    r"SystemFileAssociations\.py",
    r"SystemFileAssociations\.pyw",
    r"SystemFileAssociations\.pyc",
)

REG_TYPE_NAMES = {
    winreg.REG_NONE: "REG_NONE",
    winreg.REG_SZ: "REG_SZ",
    winreg.REG_EXPAND_SZ: "REG_EXPAND_SZ",
    winreg.REG_BINARY: "REG_BINARY",
    winreg.REG_DWORD: "REG_DWORD",
    winreg.REG_MULTI_SZ: "REG_MULTI_SZ",
    winreg.REG_QWORD: "REG_QWORD",
}


@dataclass
class Finding:
    category: str
    scope: str
    problem: str
    planned_action: str
    severity: str = "INFO"
    details: list[str] = field(default_factory=list)


class RepairLog:
    def __init__(self, sink):
        self._sink = sink

    def write(self, message: str = "") -> None:
        self._sink(message)

    def section(self, title: str) -> None:
        self._sink("")
        self._sink("=" * 78)
        self._sink(title)
        self._sink("=" * 78)


def is_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def view_name(view: int) -> str:
    return "32-bit" if view == winreg.KEY_WOW64_32KEY else "64-bit"


def root_name(root: int) -> str:
    return "HKCU" if root == winreg.HKEY_CURRENT_USER else "HKLM"


def full_root_name(root: int) -> str:
    return "HKEY_CURRENT_USER" if root == winreg.HKEY_CURRENT_USER else "HKEY_LOCAL_MACHINE"


def reg_label(root: int, subkey: str, view: int) -> str:
    return f"{root_name(root)}\\{subkey} [{view_name(view)}]"


def key_exists(root: int, subkey: str, view: int) -> bool:
    try:
        with winreg.OpenKey(root, subkey, 0, winreg.KEY_READ | view):
            return True
    except (FileNotFoundError, PermissionError, OSError):
        return False


def enum_subkeys(root: int, subkey: str, view: int) -> list[str]:
    result: list[str] = []
    try:
        with winreg.OpenKey(root, subkey, 0, winreg.KEY_READ | view) as key:
            index = 0
            while True:
                try:
                    result.append(winreg.EnumKey(key, index))
                    index += 1
                except OSError:
                    break
    except (FileNotFoundError, PermissionError, OSError):
        pass
    return result


def enum_values(root: int, subkey: str, view: int) -> list[tuple[str, object, int]]:
    result: list[tuple[str, object, int]] = []
    try:
        with winreg.OpenKey(root, subkey, 0, winreg.KEY_READ | view) as key:
            index = 0
            while True:
                try:
                    result.append(winreg.EnumValue(key, index))
                    index += 1
                except OSError:
                    break
    except (FileNotFoundError, PermissionError, OSError):
        pass
    return result


def read_value(root: int, subkey: str, name: str | None, view: int, default=""):
    try:
        with winreg.OpenKey(root, subkey, 0, winreg.KEY_READ | view) as key:
            value, _kind = winreg.QueryValueEx(key, name)
            return value
    except (FileNotFoundError, PermissionError, OSError):
        return default



def value_exists(root: int, subkey: str, name: str | None, view: int) -> bool:
    try:
        with winreg.OpenKey(root, subkey, 0, winreg.KEY_READ | view) as key:
            winreg.QueryValueEx(key, name)
        return True
    except (FileNotFoundError, PermissionError, OSError):
        return False


def create_key(root: int, subkey: str, view: int):
    return winreg.CreateKeyEx(root, subkey, 0, winreg.KEY_READ | winreg.KEY_WRITE | view)


def delete_tree(root: int, subkey: str, view: int) -> None:
    while True:
        children = enum_subkeys(root, subkey, view)
        if not children:
            break
        delete_tree(root, subkey + "\\" + children[0], view)
    winreg.DeleteKeyEx(root, subkey, view, 0)


def pythonish_app_name(name: str) -> bool:
    return bool(PYTHON_APP_RE.match(str(name or "").strip()))


def expanded_text(value: object) -> str:
    if value is None or isinstance(value, bytes):
        return ""
    return os.path.expandvars(str(value))


def absolute_targets(command: str) -> list[Path]:
    targets: list[Path] = []
    for match in ABS_PATH_RE.finditer(expanded_text(command)):
        raw = match.group("quoted") or match.group("plain")
        if raw:
            targets.append(Path(raw))
    return targets


def command_executable(command: str) -> Path | None:
    command = expanded_text(command).strip()
    if not command:
        return None
    if command.startswith('"'):
        end = command.find('"', 1)
        if end > 1:
            candidate = Path(command[1:end])
            if candidate.suffix.lower() == ".exe":
                return candidate
    first = command.split(None, 1)[0].strip('"')
    if re.match(r"(?i)^[a-z]:\\", first) and first.lower().endswith(".exe"):
        return Path(first)
    return None


def command_points_to_missing_python(command: str) -> tuple[bool, list[Path]]:
    if not PYTHONISH_RE.search(command or ""):
        return False, []
    decisive = []
    for path in absolute_targets(command):
        low = path.name.casefold()
        if (
            path.suffix.lower() in {".py", ".pyw"}
            or low.startswith(("python", "idle"))
            or low in {"py.exe", "pyw.exe"}
        ):
            decisive.append(path)
    missing = [p for p in decisive if not p.exists()]
    return bool(missing), missing


def target_version(python_exe: Path) -> tuple[str, str]:
    result = subprocess.run(
        [
            str(python_exe),
            "-c",
            "import platform,sys; print(f'{sys.version_info.major}.{sys.version_info.minor}'); print(platform.architecture()[0])",
        ],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=10,
    )
    lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    if not lines:
        raise RuntimeError("Target Python returned no version information.")
    return lines[0], (lines[1] if len(lines) > 1 else "unknown")


def serialize_value(value: object) -> object:
    if isinstance(value, bytes):
        return {"__binary_base64__": base64.b64encode(value).decode("ascii")}
    if isinstance(value, tuple):
        return list(value)
    return value


def snapshot_key(root: int, subkey: str, view: int) -> dict:
    def walk(path: str) -> dict:
        node = {"path": path, "values": [], "children": []}
        for name, value, kind in enum_values(root, path, view):
            node["values"].append(
                {
                    "name": name,
                    "type": REG_TYPE_NAMES.get(kind, str(kind)),
                    "type_id": kind,
                    "value": serialize_value(value),
                }
            )
        for child in enum_subkeys(root, path, view):
            node["children"].append(walk(path + "\\" + child))
        return node

    return {
        "root": full_root_name(root),
        "view": view_name(view),
        "key": subkey,
        "snapshot": walk(subkey),
    }


class BackupManager:
    def __init__(self, base_dir: Path, log: RepairLog):
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.directory = base_dir / f"python_registry_backup_{stamp}"
        self.directory.mkdir(parents=True, exist_ok=True)
        self._seen: set[tuple[int, str, int]] = set()
        self.log = log

    def backup(self, root: int, subkey: str, view: int) -> None:
        identity = (root, subkey.casefold(), view)
        if identity in self._seen or not key_exists(root, subkey, view):
            return
        self._seen.add(identity)
        payload = snapshot_key(root, subkey, view)
        filename = re.sub(
            r"[^A-Za-z0-9_.-]+",
            "_",
            f"{root_name(root)}_{view_name(view)}_{subkey}",
        ).strip("_") + ".json"
        path = self.directory / filename
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        self.log.write(f"BACKUP  {reg_label(root, subkey, view)} -> {path.name}")


def launcher_entries() -> list[tuple[int, int, str, str, str, str]]:
    rows = []
    base = r"Software\Python\PythonCore"
    for _rname, root in ROOTS:
        for view in VIEWS:
            for version in enum_subkeys(root, base, view):
                install_key = base + "\\" + version + r"\InstallPath"
                install = str(read_value(root, install_key, None, view, "") or "")
                exe = str(read_value(root, install_key, "ExecutablePath", view, "") or "")
                windowed = str(read_value(root, install_key, "WindowedExecutablePath", view, "") or "")
                rows.append((root, view, version, install, exe, windowed))
    return rows



def python_executable_candidates(target: Path) -> set[str]:
    """Names Windows may independently surface as Python applications.

    Include real siblings in the selected Python install plus the Windows
    launcher family. This intentionally catches debug builds such as
    pythonw_d.exe which the old cleaner missed.
    """

    names = {"py.exe", "pyw.exe", "pythonw.exe", "python_d.exe", "pythonw_d.exe"}
    try:
        for path in target.parent.glob("*.exe"):
            if pythonish_app_name(path.name):
                names.add(path.name.casefold())
    except OSError:
        pass
    return {name.casefold() for name in names}


def python_progids_for_extensions() -> set[str]:
    result: set[str] = set()
    for _rname, root in ROOTS:
        for view in VIEWS:
            for ext in FILE_EXTS:
                for subkey in (
                    rf"Software\Classes\{ext}\OpenWithProgids",
                    rf"Software\Microsoft\Windows\CurrentVersion\Explorer\FileExts\{ext}\OpenWithProgids",
                ):
                    for name, _value, _kind in enum_values(root, subkey, view):
                        if str(name).casefold().startswith("python."):
                            result.add(str(name))
    # Python's standard installer ProgIDs. They may be the default association
    # even when absent from OpenWithProgids at the moment.
    result.update({"Python.File", "Python.NoConFile", "Python.CompiledFile"})
    return result


def progid_has_noopenwith(progid: str) -> bool:
    for _rname, root in ROOTS:
        for view in VIEWS:
            key = rf"Software\Classes\{progid}"
            if key_exists(root, key, view) and value_exists(root, key, "NoOpenWith", view):
                return True
    return False


def scan_findings(target: Path, log: RepairLog) -> tuple[list[Finding], str, str]:
    findings: list[Finding] = []
    version, arch = target_version(target)

    log.section("TARGET")
    log.write(f"Interpreter:  {target}")
    log.write(f"Version:      {version}")
    log.write(f"Architecture: {arch}")
    log.write(f"Administrator:{is_admin()}")

    log.section("PYTHON LAUNCHER / PEP 514")
    found_target_registration = False
    for root, view, reg_version, install, exe, windowed in launcher_entries():
        scope = reg_label(root, rf"Software\Python\PythonCore\{reg_version}\InstallPath", view)
        actual = Path(exe) if exe else (Path(install) / "python.exe" if install else None)
        exists = bool(actual and actual.exists())
        if reg_version == version:
            if root == winreg.HKEY_CURRENT_USER and view == winreg.KEY_WOW64_64KEY:
                found_target_registration = True
            if not exists or (actual and actual.resolve() != target.resolve()):
                findings.append(Finding(
                    "Launcher", scope,
                    f"Python {reg_version} points to {actual or '<nothing>'}",
                    f"Set the canonical HKCU {version} registration to {target}; delete dead duplicates.",
                    "FIX",
                ))
                log.write(f"STALE   {scope}")
                log.write(f"        registered: {actual or '<missing>'}")
            else:
                log.write(f"LIVE    {scope} -> {actual}")
        elif actual and not actual.exists():
            findings.append(Finding(
                "Launcher", scope,
                f"Dead Python {reg_version} registration points to {actual}",
                "Delete dead registration.",
                "DELETE",
            ))
            log.write(f"DEAD    {scope} -> {actual}")
        else:
            log.write(f"LIVE    {scope} -> {actual or '<incomplete>'}")

    if not found_target_registration:
        findings.append(Finding(
            "Launcher",
            f"HKCU\\Software\\Python\\PythonCore\\{version}",
            "Canonical per-user launcher registration is missing.",
            f"Create it for {target}.",
            "CREATE",
        ))

    log.section("APP PATHS")
    app_path = r"Software\Microsoft\Windows\CurrentVersion\App Paths\python.exe"
    for _rname, root in ROOTS:
        for view in VIEWS:
            if not key_exists(root, app_path, view):
                continue
            current = str(read_value(root, app_path, None, view, "") or "")
            if current and Path(current).exists() and Path(current).resolve() == target.resolve():
                log.write(f"OK      {reg_label(root, app_path, view)} -> {current}")
            else:
                findings.append(Finding(
                    "App Paths", reg_label(root, app_path, view),
                    f"python.exe resolves to {current or '<missing>'}",
                    f"Normalize the per-user App Paths entry to {target}; delete dead machine-wide duplicate if writable.",
                    "FIX",
                ))
                log.write(f"STALE   {reg_label(root, app_path, view)} -> {current or '<missing>'}")

    log.section("OPEN WITH APPLICATION REGISTRATIONS")
    for _rname, root in ROOTS:
        for view in VIEWS:
            apps = r"Software\Classes\Applications"
            for app in enum_subkeys(root, apps, view):
                if not pythonish_app_name(app):
                    continue
                key = apps + "\\" + app
                command = str(read_value(root, key + r"\shell\open\command", None, view, "") or "")
                exe = command_executable(command)
                live = bool(exe and exe.exists())
                suppressed = value_exists(root, key, "NoOpenWith", view)
                canonical = app.casefold() == "python.exe" and live and exe.resolve() == target.resolve()
                if canonical:
                    log.write(f"CANON   {reg_label(root, key, view)} -> {command}")
                    continue
                if suppressed:
                    log.write(f"HIDDEN  {reg_label(root, key, view)}")
                    continue
                action = (
                    "Delete dead registration."
                    if not live
                    else "Hide from Open With (NoOpenWith) so only the canonical target remains."
                )
                findings.append(Finding(
                    "Open With app", reg_label(root, key, view),
                    f"{app}: {command or '<no command>'}",
                    action,
                    "DELETE" if not live else "HIDE",
                ))
                log.write(f"{'DEAD' if not live else 'DUP'}     {reg_label(root, key, view)} -> {command or '<none>'}")

    log.section("EXPLORER OPEN WITH LISTS")
    fileext_base = r"Software\Microsoft\Windows\CurrentVersion\Explorer\FileExts"
    for ext in FILE_EXTS:
        owlist = fileext_base + "\\" + ext + r"\OpenWithList"
        values = enum_values(winreg.HKEY_CURRENT_USER, owlist, winreg.KEY_WOW64_64KEY)
        for name, value, _kind in values:
            if name == "MRUList":
                continue
            app = str(value or "")
            if pythonish_app_name(app) and app.casefold() != "python.exe":
                findings.append(Finding(
                    "Open With list",
                    f"HKCU\\...\\FileExts\\{ext}\\OpenWithList",
                    f"Duplicate Python app '{app}' is cached under value {name}.",
                    "Remove it; keep one python.exe entry.",
                    "DELETE",
                ))
                log.write(f"DUP     {ext}: {name}={app}")
        for sub in (
            fileext_base + "\\" + ext + r"\OpenWithProgids",
            rf"Software\Classes\{ext}\OpenWithProgids",
        ):
            for name, _value, _kind in enum_values(winreg.HKEY_CURRENT_USER, sub, winreg.KEY_WOW64_64KEY):
                if PYTHONISH_RE.search(name or "") and name.casefold() != r"applications\python.exe":
                    findings.append(Finding(
                        "Open With ProgID",
                        f"HKCU\\{sub}",
                        f"Python ProgID '{name}' can create another Python entry.",
                        r"Remove it and register only Applications\python.exe.",
                        "DELETE",
                    ))
                    log.write(f"DUP     {ext}: ProgID {name}")

    log.section("PYTHON PROGID OPEN-WITH SOURCES")
    for progid in sorted(python_progids_for_extensions(), key=str.casefold):
        present = False
        for _rname, root in ROOTS:
            for view in VIEWS:
                key = rf"Software\Classes\{progid}"
                if not key_exists(root, key, view):
                    continue
                present = True
                if value_exists(root, key, "NoOpenWith", view):
                    log.write(f"HIDDEN  {reg_label(root, key, view)}")
                else:
                    findings.append(Finding(
                        "Python ProgID",
                        reg_label(root, key, view),
                        f"{progid} can be offered by OpenWithProgids/default file association.",
                        "Add NoOpenWith directly to this ProgID without disturbing its normal open command.",
                        "HIDE",
                    ))
                    log.write(f"VISIBLE {reg_label(root, key, view)}")
        if not present:
            log.write(f"ABSENT  {progid}")

    log.section("PYTHON SHELL / CONTEXT MENU VERBS")
    for _rname, root in ROOTS:
        for view in VIEWS:
            classes = r"Software\Classes"
            owners = set(KNOWN_SHELL_OWNERS)
            for owner in enum_subkeys(root, classes, view):
                folded = owner.casefold()
                if "python" in folded or folded in {".py", ".pyw", ".pyc", "py_auto_file"}:
                    owners.add(owner)
            for owner in sorted(owners, key=str.casefold):
                shell = classes + "\\" + owner + r"\shell"
                for verb in enum_subkeys(root, shell, view):
                    verb_key = shell + "\\" + verb
                    display = str(read_value(root, verb_key, None, view, "") or "")
                    command = str(read_value(root, verb_key + r"\command", None, view, "") or "")
                    combined = " ".join((owner, verb, display, command))
                    if not PYTHONISH_RE.search(combined):
                        continue
                    dead, missing = command_points_to_missing_python(command)
                    if dead:
                        findings.append(Finding(
                            "Context menu", reg_label(root, verb_key, view),
                            f"Dead Python shell verb; missing: {', '.join(map(str, missing))}",
                            "Delete the dead verb.",
                            "DELETE",
                        ))
                        log.write(f"DEAD    {reg_label(root, verb_key, view)}")
                        log.write(f"        {command}")

    log.section("SHELL MUICACHE (INFORMATIONAL ONLY)")
    mui = r"Software\Classes\Local Settings\Software\Microsoft\Windows\Shell\MuiCache"
    for name, value, _kind in enum_values(winreg.HKEY_CURRENT_USER, mui, winreg.KEY_WOW64_64KEY):
        combined = f"{name} {expanded_text(value)}"
        if PYTHONISH_RE.search(combined):
            # MuiCache is descriptive shell metadata. Running this very utility
            # through python.exe immediately recreates legitimate Python cache
            # rows, so their mere existence is not an Open-With failure.
            log.write(f"CACHE   {name} = {value}")


    return findings, version, arch


def backup_parent(backup: BackupManager, root: int, key: str, view: int) -> None:
    if key_exists(root, key, view):
        backup.backup(root, key, view)


def ensure_launcher_registration(target: Path, version: str, arch: str, backup: BackupManager, log: RepairLog) -> None:
    root = winreg.HKEY_CURRENT_USER
    view = winreg.KEY_WOW64_64KEY
    version_key = rf"Software\Python\PythonCore\{version}"
    install_key = version_key + r"\InstallPath"
    backup_parent(backup, root, version_key, view)

    with create_key(root, version_key, view) as key:
        winreg.SetValueEx(key, "DisplayName", 0, winreg.REG_SZ, f"Python {version} ({target.parent})")
        winreg.SetValueEx(key, "SysVersion", 0, winreg.REG_SZ, version)
        winreg.SetValueEx(key, "SysArchitecture", 0, winreg.REG_SZ, "64bit" if "64" in arch else "32bit")

    with create_key(root, install_key, view) as key:
        winreg.SetValueEx(key, None, 0, winreg.REG_SZ, str(target.parent) + "\\")
        winreg.SetValueEx(key, "ExecutablePath", 0, winreg.REG_SZ, str(target))
        pythonw = target.with_name("pythonw.exe")
        if pythonw.exists():
            winreg.SetValueEx(key, "WindowedExecutablePath", 0, winreg.REG_SZ, str(pythonw))
    log.write(f"FIXED   Canonical launcher registration -> {target}")

    base = r"Software\Python\PythonCore"
    for _rname, other_root in ROOTS:
        for other_view in VIEWS:
            for reg_version in enum_subkeys(other_root, base, other_view):
                install = base + "\\" + reg_version + r"\InstallPath"
                raw_exe = str(read_value(other_root, install, "ExecutablePath", other_view, "") or "")
                raw_dir = str(read_value(other_root, install, None, other_view, "") or "")
                actual = Path(raw_exe) if raw_exe else (Path(raw_dir) / "python.exe" if raw_dir else None)
                if actual and actual.exists():
                    continue
                version_node = base + "\\" + reg_version
                if other_root == root and other_view == view and reg_version == version:
                    continue
                backup_parent(backup, other_root, version_node, other_view)
                try:
                    delete_tree(other_root, version_node, other_view)
                    log.write(f"DELETED dead launcher registration {reg_label(other_root, version_node, other_view)}")
                except PermissionError as exc:
                    log.write(f"FAILED  {reg_label(other_root, version_node, other_view)}: permission denied ({exc})")
                except OSError as exc:
                    log.write(f"FAILED  {reg_label(other_root, version_node, other_view)}: {exc}")


def ensure_app_path(target: Path, backup: BackupManager, log: RepairLog) -> None:
    root = winreg.HKEY_CURRENT_USER
    view = winreg.KEY_WOW64_64KEY
    key_path = r"Software\Microsoft\Windows\CurrentVersion\App Paths\python.exe"
    backup_parent(backup, root, key_path, view)
    with create_key(root, key_path, view) as key:
        winreg.SetValueEx(key, None, 0, winreg.REG_SZ, str(target))
        winreg.SetValueEx(key, "Path", 0, winreg.REG_SZ, str(target.parent))
    log.write(f"FIXED   App Paths\\python.exe -> {target}")

    for other_root in (winreg.HKEY_LOCAL_MACHINE,):
        for other_view in VIEWS:
            if not key_exists(other_root, key_path, other_view):
                continue
            value = str(read_value(other_root, key_path, None, other_view, "") or "")
            if value and Path(value).exists():
                continue
            backup_parent(backup, other_root, key_path, other_view)
            try:
                delete_tree(other_root, key_path, other_view)
                log.write(f"DELETED dead {reg_label(other_root, key_path, other_view)}")
            except PermissionError as exc:
                log.write(f"FAILED  {reg_label(other_root, key_path, other_view)}: permission denied ({exc})")
            except OSError as exc:
                log.write(f"FAILED  {reg_label(other_root, key_path, other_view)}: {exc}")


def normalize_application_registrations(target: Path, version: str, backup: BackupManager, log: RepairLog) -> None:
    apps = r"Software\Classes\Applications"
    for _rname, root in ROOTS:
        for view in VIEWS:
            for app in enum_subkeys(root, apps, view):
                if not pythonish_app_name(app):
                    continue
                key = apps + "\\" + app
                command = str(read_value(root, key + r"\shell\open\command", None, view, "") or "")
                exe = command_executable(command)
                live = bool(exe and exe.exists())
                canonical = app.casefold() == "python.exe" and live and exe.resolve() == target.resolve()
                if canonical:
                    continue

                backup_parent(backup, root, key, view)
                try:
                    if not live:
                        delete_tree(root, key, view)
                        log.write(f"DELETED dead Open With app {reg_label(root, key, view)}")
                    else:
                        with create_key(root, key, view) as h:
                            winreg.SetValueEx(h, "NoOpenWith", 0, winreg.REG_SZ, "")
                            winreg.SetValueEx(h, "NoStaticDefaultVerb", 0, winreg.REG_SZ, "")
                        supported = key + r"\SupportedTypes"
                        if key_exists(root, supported, view):
                            try:
                                delete_tree(root, supported, view)
                            except OSError as exc:
                                log.write(f"FAILED  remove {reg_label(root, supported, view)}: {exc}")
                        log.write(f"HIDDEN  duplicate live Python app from Open With: {reg_label(root, key, view)}")
                except PermissionError as exc:
                    log.write(f"FAILED  {reg_label(root, key, view)}: permission denied ({exc})")
                except OSError as exc:
                    log.write(f"FAILED  {reg_label(root, key, view)}: {exc}")

    root = winreg.HKEY_CURRENT_USER
    view = winreg.KEY_WOW64_64KEY
    key = apps + r"\python.exe"
    backup_parent(backup, root, key, view)
    with create_key(root, key, view) as h:
        try:
            winreg.DeleteValue(h, "NoOpenWith")
        except FileNotFoundError:
            pass
        winreg.SetValueEx(h, "FriendlyAppName", 0, winreg.REG_SZ, f"Python {version}")
        winreg.SetValueEx(h, "ApplicationIcon", 0, winreg.REG_SZ, f'"{target}",0')

    supported = key + r"\SupportedTypes"
    with create_key(root, supported, view) as h:
        for ext in FILE_EXTS:
            winreg.SetValueEx(h, ext, 0, winreg.REG_SZ, "")

    command_key = key + r"\shell\open\command"
    with create_key(root, command_key, view) as h:
        winreg.SetValueEx(h, None, 0, winreg.REG_SZ, f'"{target}" "%1" %*')
    log.write(f"CREATED canonical Open With app: Python {version} -> {target}")


def delete_value_if_present(root: int, subkey: str, name: str, view: int, log: RepairLog) -> bool:
    try:
        with winreg.OpenKey(root, subkey, 0, winreg.KEY_QUERY_VALUE | winreg.KEY_SET_VALUE | view) as key:
            winreg.DeleteValue(key, name)
        log.write(f"DELETED value {root_name(root)}\\{subkey} :: {name}")
        return True
    except FileNotFoundError:
        return False



def suppress_python_application_variants(target: Path, backup: BackupManager, log: RepairLog) -> None:
    """Create per-user NoOpenWith tombstones for every noncanonical Python exe.

    This blocks candidates such as py.exe, pythonw.exe and pythonw_d.exe even
    when a machine-wide registration or Shell tracking tries to resurrect them.
    """

    root = winreg.HKEY_CURRENT_USER
    view = winreg.KEY_WOW64_64KEY
    base = r"Software\Classes\Applications"
    for name in sorted(python_executable_candidates(target)):
        if name == "python.exe":
            continue
        key = base + "\\" + name
        backup_parent(backup, root, key, view)
        with create_key(root, key, view) as handle:
            winreg.SetValueEx(handle, "NoOpenWith", 0, winreg.REG_SZ, "")
            winreg.SetValueEx(handle, "NoStaticDefaultVerb", 0, winreg.REG_SZ, "")
        # A SupportedTypes key overrides NoOpenWith for the declared extension,
        # so remove it from the user-level tombstone if an older run created one.
        supported = key + r"\SupportedTypes"
        if key_exists(root, supported, view):
            backup_parent(backup, root, supported, view)
            try:
                delete_tree(root, supported, view)
            except OSError as exc:
                log.write(f"FAILED  remove {reg_label(root, supported, view)}: {exc}")
        log.write(f"HIDDEN  Python Open-With executable candidate: {name}")


def suppress_python_progids(backup: BackupManager, log: RepairLog) -> None:
    """Put NoOpenWith on Python ProgIDs themselves.

    Microsoft documents that an OpenWithProgids entry can make an application
    appear even when the executable registration has NoOpenWith. Therefore the
    ProgID itself must carry NoOpenWith too. We preserve the ProgID and its shell
    command so default/double-click associations keep working.
    """

    for progid in sorted(python_progids_for_extensions(), key=str.casefold):
        found = False
        for _rname, root in ROOTS:
            for view in VIEWS:
                key = rf"Software\Classes\{progid}"
                if not key_exists(root, key, view):
                    continue
                found = True
                backup.backup(root, key, view)
                try:
                    with create_key(root, key, view) as handle:
                        winreg.SetValueEx(handle, "NoOpenWith", 0, winreg.REG_SZ, "")
                    log.write(f"HIDDEN  Python ProgID from Open With: {reg_label(root, key, view)}")
                except PermissionError as exc:
                    log.write(f"FAILED  {reg_label(root, key, view)}: permission denied ({exc})")
                except OSError as exc:
                    log.write(f"FAILED  {reg_label(root, key, view)}: {exc}")
        if not found:
            log.write(f"ABSENT  Python ProgID {progid}")


def remove_python_progids_from_openwith_lists(backup: BackupManager, log: RepairLog) -> None:
    """Remove alternate Python ProgIDs from explicit OpenWithProgids lists.

    The file type's default ProgID is left intact. The canonical application
    entry is supplied separately through Applications\\python.exe.
    """

    for _rname, root in ROOTS:
        for view in VIEWS:
            for ext in FILE_EXTS:
                for subkey in (
                    rf"Software\Classes\{ext}\OpenWithProgids",
                    rf"Software\Microsoft\Windows\CurrentVersion\Explorer\FileExts\{ext}\OpenWithProgids",
                ):
                    if not key_exists(root, subkey, view):
                        continue
                    python_names = [
                        name for name, _value, _kind in enum_values(root, subkey, view)
                        if str(name).casefold().startswith("python.")
                    ]
                    if not python_names:
                        continue
                    backup.backup(root, subkey, view)
                    for name in python_names:
                        try:
                            delete_value_if_present(root, subkey, name, view, log)
                        except PermissionError as exc:
                            log.write(f"FAILED  remove {name} from {reg_label(root, subkey, view)}: permission denied ({exc})")
                        except OSError as exc:
                            log.write(f"FAILED  remove {name} from {reg_label(root, subkey, view)}: {exc}")


def normalize_openwith_lists(target: Path, backup: BackupManager, log: RepairLog) -> None:
    root = winreg.HKEY_CURRENT_USER
    view = winreg.KEY_WOW64_64KEY
    base = r"Software\Microsoft\Windows\CurrentVersion\Explorer\FileExts"

    for ext in FILE_EXTS:
        owlist = base + "\\" + ext + r"\OpenWithList"
        if key_exists(root, owlist, view):
            backup.backup(root, owlist, view)
            values = enum_values(root, owlist, view)
            keep_letters: list[str] = []
            python_letters: list[str] = []
            for name, value, _kind in values:
                if name == "MRUList":
                    continue
                app = str(value or "")
                if pythonish_app_name(app):
                    python_letters.append(name)
                else:
                    keep_letters.append(name)

            with winreg.OpenKey(root, owlist, 0, winreg.KEY_READ | winreg.KEY_WRITE | view) as key:
                for letter in python_letters:
                    try:
                        winreg.DeleteValue(key, letter)
                    except FileNotFoundError:
                        pass

                used = set(keep_letters)
                python_letter = next((c for c in "abcdefghijklmnopqrstuvwxyz" if c not in used), "z")
                winreg.SetValueEx(key, python_letter, 0, winreg.REG_SZ, "python.exe")
                new_mru = "".join(keep_letters + [python_letter])
                winreg.SetValueEx(key, "MRUList", 0, winreg.REG_SZ, new_mru)
            log.write(f"NORMAL  {ext} OpenWithList -> one python.exe entry")

        for subkey in (
            base + "\\" + ext + r"\OpenWithProgids",
            rf"Software\Classes\{ext}\OpenWithProgids",
        ):
            if key_exists(root, subkey, view):
                backup.backup(root, subkey, view)
            for name, _value, _kind in enum_values(root, subkey, view):
                if PYTHONISH_RE.search(name or ""):
                    try:
                        delete_value_if_present(root, subkey, name, view, log)
                    except PermissionError as exc:
                        log.write(f"FAILED  remove ProgID {name}: permission denied ({exc})")
                    except OSError as exc:
                        log.write(f"FAILED  remove ProgID {name}: {exc}")
            with create_key(root, subkey, view) as key:
                winreg.SetValueEx(key, r"Applications\python.exe", 0, winreg.REG_NONE, b"")
            log.write(f"NORMAL  {ext} OpenWithProgids -> Applications\\python.exe")


def remove_dead_shell_verbs(backup: BackupManager, log: RepairLog) -> None:
    for _rname, root in ROOTS:
        for view in VIEWS:
            classes = r"Software\Classes"
            owners = set(KNOWN_SHELL_OWNERS)
            for owner in enum_subkeys(root, classes, view):
                folded = owner.casefold()
                if "python" in folded or folded in {".py", ".pyw", ".pyc", "py_auto_file"}:
                    owners.add(owner)

            for owner in sorted(owners, key=str.casefold):
                shell = classes + "\\" + owner + r"\shell"
                for verb in enum_subkeys(root, shell, view):
                    verb_key = shell + "\\" + verb
                    display = str(read_value(root, verb_key, None, view, "") or "")
                    command = str(read_value(root, verb_key + r"\command", None, view, "") or "")
                    combined = " ".join((owner, verb, display, command))
                    if not PYTHONISH_RE.search(combined):
                        continue
                    dead, _missing = command_points_to_missing_python(command)
                    if not dead:
                        continue
                    backup.backup(root, verb_key, view)
                    try:
                        delete_tree(root, verb_key, view)
                        log.write(f"DELETED dead context-menu verb {reg_label(root, verb_key, view)}")
                    except PermissionError as exc:
                        log.write(f"FAILED  {reg_label(root, verb_key, view)}: permission denied ({exc})")
                    except OSError as exc:
                        log.write(f"FAILED  {reg_label(root, verb_key, view)}: {exc}")


def purge_python_muicache(backup: BackupManager, log: RepairLog) -> None:
    root = winreg.HKEY_CURRENT_USER
    view = winreg.KEY_WOW64_64KEY
    mui = r"Software\Classes\Local Settings\Software\Microsoft\Windows\Shell\MuiCache"
    if not key_exists(root, mui, view):
        return
    backup.backup(root, mui, view)
    for name, value, _kind in list(enum_values(root, mui, view)):
        combined = f"{name} {expanded_text(value)}"
        if not PYTHONISH_RE.search(combined):
            continue
        try:
            delete_value_if_present(root, mui, name, view, log)
        except OSError as exc:
            log.write(f"FAILED  MuiCache value {name}: {exc}")


def notify_shell_association_changed(log: RepairLog) -> None:
    try:
        SHCNE_ASSOCCHANGED = 0x08000000
        SHCNF_IDLIST = 0x0000
        ctypes.windll.shell32.SHChangeNotify(SHCNE_ASSOCCHANGED, SHCNF_IDLIST, None, None)
        log.write("NOTIFY  Explorer shell association cache invalidated via SHChangeNotify.")
    except Exception as exc:
        log.write(f"FAILED  SHChangeNotify: {exc}")


def run_py_launcher_probe(log: RepairLog) -> None:
    launcher = shutil.which("py.exe") or shutil.which("py")
    if not launcher:
        log.write("INFO    py.exe launcher is not on PATH; registry repair still applied.")
        return
    try:
        result = subprocess.run(
            [launcher, "-0p"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=10,
        )
        log.write("py -0p:")
        for line in (result.stdout or "").splitlines():
            log.write("        " + line)
        if result.returncode:
            log.write(f"WARNING py -0p exited with code {result.returncode}.")
    except Exception as exc:
        log.write(f"FAILED  py -0p probe: {exc}")


def aggressive_repair(target: Path, base_dir: Path, log: RepairLog) -> Path:
    if not target.is_file():
        raise FileNotFoundError(f"Target Python does not exist: {target}")

    version, arch = target_version(target)
    backup = BackupManager(base_dir, log)

    log.section("AGGRESSIVE REPAIR")
    log.write("Scope: Python launcher + Python-only Open With registrations/caches.")
    log.write("Non-Python apps in Open With are preserved.")

    ensure_launcher_registration(target, version, arch, backup, log)
    ensure_app_path(target, backup, log)
    normalize_application_registrations(target, version, backup, log)
    suppress_python_application_variants(target, backup, log)
    suppress_python_progids(backup, log)
    remove_python_progids_from_openwith_lists(backup, log)
    normalize_openwith_lists(target, backup, log)
    remove_dead_shell_verbs(backup, log)
    # MuiCache is intentionally not treated as an ownership source. It is shell
    # metadata and is recreated immediately when Python/py.exe executes.
    notify_shell_association_changed(log)
    run_py_launcher_probe(log)

    log.write("")
    log.write(f"Backups: {backup.directory}")
    log.section("POST-REPAIR VERIFICATION")
    residuals, _verify_version, _verify_arch = scan_findings(target, log)
    actionable = [finding for finding in residuals if finding.category != "MuiCache"]
    if actionable:
        log.write("")
        log.write(f"PARTIAL: {len(actionable)} actionable Open-With/registry source(s) remain.")
    else:
        log.write("")
        log.write("CLEAN: no actionable Python Open-With sources remain.")
    return backup.directory, actionable


def restart_explorer(log: RepairLog) -> None:
    log.section("RESTART EXPLORER")
    result = subprocess.run(
        ["taskkill.exe", "/F", "/IM", "explorer.exe"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=10,
    )
    if result.returncode not in (0, 128):
        log.write(f"WARNING taskkill explorer.exe returned {result.returncode}: {result.stderr.strip() or result.stdout.strip()}")
    subprocess.Popen(
        ["explorer.exe"],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    log.write("Explorer restart requested.")


def relaunch_elevated(script: Path, target: Path) -> None:
    params = subprocess.list2cmdline([str(script), "--target", str(target), "--elevated"])
    result = ctypes.windll.shell32.ShellExecuteW(
        None, "runas", sys.executable, params, str(script.parent), 1
    )
    if int(result) <= 32:
        raise RuntimeError(f"UAC elevation failed with ShellExecuteW code {int(result)}")


class RepairApp(tk.Tk):
    def __init__(self, target: Path):
        super().__init__()
        self.title("Python Registry + Open With Repair v3")
        self.geometry("1180x760")
        self.minsize(900, 620)
        self.target_var = tk.StringVar(value=str(target))
        self.status_var = tk.StringVar()
        self.last_backup: Path | None = None
        self.findings: list[Finding] = []
        self._busy = False
        self._build_ui()
        self.after(100, self.scan)

    def _build_ui(self) -> None:
        outer = ttk.Frame(self, padding=12)
        outer.pack(fill="both", expand=True)

        ttk.Label(
            outer,
            text="PYTHON REGISTRY + OPEN WITH REPAIR",
            font=("Segoe UI", 15, "bold"),
        ).pack(anchor="w")
        ttk.Label(
            outer,
            text=(
                "Repairs the stale py.exe registration and collapses Python's Windows Open With clutter "
                "to one canonical Python entry. PyCharm/editors/PowerShell are left alone."
            ),
            wraplength=1100,
        ).pack(anchor="w", pady=(4, 10))

        target_row = ttk.Frame(outer)
        target_row.pack(fill="x")
        ttk.Label(target_row, text="Real Python:").pack(side="left")
        self.target_entry = ttk.Entry(target_row, textvariable=self.target_var)
        self.target_entry.pack(side="left", fill="x", expand=True, padx=8)
        ttk.Button(target_row, text="Browse…", command=self.browse_target).pack(side="left")

        info_row = ttk.Frame(outer)
        info_row.pack(fill="x", pady=(8, 8))
        ttk.Label(info_row, text=("Administrator: YES" if is_admin() else "Administrator: NO")).pack(side="left")
        if not is_admin():
            ttk.Button(info_row, text="RELAUNCH ELEVATED", command=self.elevate).pack(side="left", padx=(12, 0))
        ttk.Label(info_row, textvariable=self.status_var).pack(side="right")

        actions = ttk.Frame(outer)
        actions.pack(fill="x", pady=(0, 8))
        self.scan_btn = ttk.Button(actions, text="SCAN / EXPLAIN", command=self.scan)
        self.scan_btn.pack(side="left")
        self.repair_btn = ttk.Button(actions, text="AGGRESSIVE REPAIR", command=self.repair)
        self.repair_btn.pack(side="left", padx=6)
        self.restart_btn = ttk.Button(actions, text="RESTART EXPLORER", command=self.restart_shell)
        self.restart_btn.pack(side="left")
        self.backup_btn = ttk.Button(actions, text="OPEN BACKUP FOLDER", command=self.open_backup, state="disabled")
        self.backup_btn.pack(side="left", padx=6)

        pane = ttk.Panedwindow(outer, orient="vertical")
        pane.pack(fill="both", expand=True)

        findings_frame = ttk.Labelframe(pane, text="Findings")
        self.tree = ttk.Treeview(
            findings_frame,
            columns=("category", "scope", "problem", "action"),
            show="headings",
            height=10,
        )
        for col, text, width in (
            ("category", "TYPE", 130),
            ("scope", "REGISTRY / CACHE LOCATION", 300),
            ("problem", "PROBLEM", 330),
            ("action", "PLANNED ACTION", 350),
        ):
            self.tree.heading(col, text=text)
            self.tree.column(col, width=width, anchor="w")
        scroll = ttk.Scrollbar(findings_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        pane.add(findings_frame, weight=2)

        log_frame = ttk.Labelframe(pane, text="What happened / why")
        self.log_text = tk.Text(log_frame, wrap="word", font=("Consolas", 10), state="disabled")
        log_scroll = ttk.Scrollbar(log_frame, orient="vertical", command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=log_scroll.set)
        self.log_text.pack(side="left", fill="both", expand=True)
        log_scroll.pack(side="right", fill="y")
        pane.add(log_frame, weight=3)

        ttk.Label(
            outer,
            text=(
                "If the visible menu does not change immediately, click RESTART EXPLORER. "
                "The repair also calls SHChangeNotify automatically, but Explorer can cling to an old Open With cache."
            ),
            wraplength=1100,
        ).pack(anchor="w", pady=(8, 0))

    def log(self, message: str = "") -> None:
        def append():
            self.log_text.configure(state="normal")
            self.log_text.insert("end", message + "\n")
            self.log_text.see("end")
            self.log_text.configure(state="disabled")
        if threading.current_thread() is threading.main_thread():
            append()
        else:
            self.after(0, append)

    def clear_log(self) -> None:
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")

    def set_busy(self, busy: bool, text: str = "") -> None:
        self._busy = busy
        state = "disabled" if busy else "normal"
        for btn in (self.scan_btn, self.repair_btn, self.restart_btn):
            btn.configure(state=state)
        self.status_var.set(text)

    def browse_target(self) -> None:
        path = filedialog.askopenfilename(
            title="Choose the real python.exe",
            filetypes=(("python.exe", "python.exe"), ("Executables", "*.exe"), ("All files", "*.*")),
        )
        if path:
            self.target_var.set(path)

    def target(self) -> Path:
        return Path(os.path.expandvars(self.target_var.get().strip())).expanduser()

    def run_worker(self, fn, done=None):
        if self._busy:
            return
        self.set_busy(True, "Working…")

        def work():
            try:
                result = fn()
            except Exception as exc:
                details = traceback.format_exc()
                self.after(0, lambda: self._failed(exc, details))
            else:
                self.after(0, lambda: self._finished(result, done))

        threading.Thread(target=work, name="python-registry-repair-gui", daemon=True).start()

    def _failed(self, exc: Exception, details: str) -> None:
        self.set_busy(False, "FAILED")
        self.log("")
        self.log("FATAL FAILURE:")
        self.log(str(exc))
        self.log(details)
        messagebox.showerror(
            "Repair failed",
            f"{exc}\n\nThe full traceback is shown in the lower log pane.",
            parent=self,
        )

    def _finished(self, result, done):
        self.set_busy(False, "Ready")
        if done:
            done(result)

    def scan(self) -> None:
        self.clear_log()
        for item in self.tree.get_children():
            self.tree.delete(item)
        log = RepairLog(self.log)

        def do_scan():
            target = self.target()
            if not target.is_file():
                raise FileNotFoundError(f"Python executable does not exist: {target}")
            return scan_findings(target, log)

        def done(result):
            findings, version, arch = result
            self.findings = findings
            for finding in findings:
                self.tree.insert(
                    "", "end",
                    values=(
                        finding.category,
                        finding.scope,
                        finding.problem,
                        finding.planned_action,
                    ),
                )
            self.status_var.set(f"{len(findings)} item(s) need cleanup · Python {version} {arch}")
            if not findings:
                self.log("")
                self.log("No stale Python registry/Open-With entries were found by this scan.")

        self.run_worker(do_scan, done)

    def repair(self) -> None:
        target = self.target()
        if not target.is_file():
            messagebox.showerror("Missing Python", f"Not found:\n{target}", parent=self)
            return
        if not messagebox.askyesno(
            "Aggressive Python cleanup",
            (
                "This will:\n\n"
                "• repair py.exe's Python registration to the selected interpreter\n"
                "• collapse Python Open With entries to ONE canonical Python entry\n"
                "• hide other live Python executables from Open With\n"
                "• delete dead Python app/context-menu registrations\n"
                "• suppress Python ProgIDs and executable variants that can resurrect Open With rows\n• treat MuiCache as informational metadata rather than a false failure\n\n"
                "It will NOT remove PyCharm/editors/PowerShell or uninstall Python.\n\n"
                "Continue?"
            ),
            parent=self,
        ):
            return

        self.clear_log()
        log = RepairLog(self.log)

        def do_repair():
            return aggressive_repair(target, Path.cwd(), log)

        def done(result):
            backup_dir, residuals = result
            self.last_backup = backup_dir
            self.backup_btn.configure(state="normal")
            self.log("")
            if residuals:
                self.status_var.set(f"PARTIAL · {len(residuals)} actionable source(s) remain")
                self.log("PARTIAL REPAIR: actionable registry/Open-With sources remain.")
                for finding in residuals:
                    self.log(f"  - {finding.category}: {finding.scope} :: {finding.problem}")
                messagebox.showwarning(
                    "Repair is partial",
                    f"{len(residuals)} actionable source(s) remain.\n\n"
                    "They are listed in the lower log. If they are HKLM permission failures, "
                    "use RELAUNCH ELEVATED.",
                    parent=self,
                )
                return
            self.status_var.set("CLEAN · no actionable Open-With sources remain")
            self.log("REPAIR COMPLETE: no actionable Python Open-With sources remain.")
            self.log("MuiCache rows may reappear after Python runs; they are metadata, not a failure.")
            self.log("Use RESTART EXPLORER below if the visible menu is still showing an old cached list.")
            if not is_admin():
                self.log("")
                self.log(
                    "NOTE: This process is not elevated. Any HKLM cleanup that Windows denied is listed "
                    "above as FAILED. Use RELAUNCH ELEVATED if you want those machine-wide remnants scrubbed too."
                )
            if messagebox.askyesno(
                "Repair complete",
                "Repair finished and Windows was notified of the association change.\n\nRestart Explorer now to force the Open With UI to rebuild?",
                parent=self,
            ):
                self.restart_shell()
            else:
                self.scan()

        self.run_worker(do_repair, done)

    def restart_shell(self) -> None:
        if not messagebox.askyesno(
            "Restart Explorer",
            "This will close and restart Windows Explorer/taskbar windows. Open application windows are unaffected.\n\nContinue?",
            parent=self,
        ):
            return
        log = RepairLog(self.log)

        def do_restart():
            restart_explorer(log)
            return True

        self.run_worker(do_restart, lambda _r: self.scan())

    def open_backup(self) -> None:
        if self.last_backup and self.last_backup.is_dir():
            os.startfile(str(self.last_backup))

    def elevate(self) -> None:
        try:
            relaunch_elevated(Path(__file__).resolve(), self.target())
            self.destroy()
        except Exception as exc:
            messagebox.showerror("Elevation failed", str(exc), parent=self)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="GUI repair for stale Python registry/Open-With entries.")
    parser.add_argument("--target", type=Path, default=DEFAULT_TARGET)
    parser.add_argument("--elevated", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    app = RepairApp(args.target)
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
