"""Fetch the pinned SDK the native module compiles against: PySide6's Qt (msvc2022_64 qtbase + qtdeclarative) and
Vulkan-Headers v1.4.341, each checked against its sha256 before anything is extracted.

The one owner of the SDK pins (decision D11: the Qt is PySide6's exact Qt, upgraded only between stages through this
script). ``.github/workflows/native-module.yml`` runs it on GitHub's Windows runner before compiling; the lead may run
it locally only to *download* (builds happen only through GitHub workflows, operator 12 Nov 2026).

The Qt version is one value: the ``PySide6==x.y.z`` pin in ``requirements.txt`` (``pinned_qt_version``). The
workflow reads it from here (``--print-qt-version``), ``native/spike_p1/CMakeLists.txt`` reads the same pin for its
guard, and the build manifest is checked against it. Each Qt version's archive names and sha256 values are one entry
of ``QT_SDKS``; a pin with no entry is refused. A Qt upgrade (the lead's, between stages) is: add the version's
entry, change the PySide6 pins in ``requirements.txt``.

Layout under ``--prefix`` (the one ``native/spike_p1/build.cmd`` reads):

    qt/                                          Qt prefix (qtbase; qtdeclarative extracts into the same prefix)
    vulkan_headers/Vulkan-Headers-1.4.341/include
    native_sdk.json                              stamp: the pins this prefix was fetched for

Fail closed: every archive is downloaded and verified (size where pinned, the pinned sha256 where pinned, and the
sha256 Qt publishes beside each archive) before any is extracted; one mismatch extracts nothing and exits non-zero.
A prefix whose stamp matches the current pins and whose layout is whole is left as it is (the workflow's cache).

Standard library only (py7zr for the Qt ``.7z`` archives, imported when one is extracted), so it runs from the tool
venv with ``python -I``:

    python -I tools/native_sdk_fetch.py --prefix D:/Temp/Scratch/SRPSS/native_spike
    python tools/native_sdk_fetch.py --print-qt-version
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
import time
import urllib.request
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath
from typing import Callable, Sequence

REPO_ROOT = Path(__file__).resolve().parents[1]
REQUIREMENTS = REPO_ROOT / "requirements.txt"
VULKAN_HEADERS_VERSION = "1.4.341"

QT_DIR = "qt"
VULKAN_DIR = "vulkan_headers"
# Relative to the prefix, with the separators build.cmd uses.
VULKAN_INCLUDE_RELATIVE = f"{VULKAN_DIR}\\Vulkan-Headers-{VULKAN_HEADERS_VERSION}\\include"
STAMP_NAME = "native_sdk.json"
DOWNLOADS_DIR = "downloads"
STAMP_SCHEMA = 1
USER_AGENT = "srpss-native-sdk-fetch/1"
ATTEMPTS = 3

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
# ``PySide6==6.11.2`` (a PySide6 build release ``6.11.2.1`` ships the same Qt 6.11.2).
_PYSIDE6_PIN = re.compile(r"^PySide6==(\d+\.\d+\.\d+)(?:\.\d+)?\s*(?:#.*)?$", re.MULTILINE)


class SdkFetchError(RuntimeError):
    """A download, checksum or layout check failed; nothing unverified was extracted."""


def qt_version_from_requirements(text: str) -> str:
    """The Qt version a ``requirements.txt`` text pins: its ``PySide6==x.y.z``."""
    match = _PYSIDE6_PIN.search(text)
    if match is None:
        raise SdkFetchError("requirements.txt pins no PySide6==x.y.z (the Qt the native module is built against)")
    return match.group(1)


def pinned_qt_version(requirements: Path = REQUIREMENTS) -> str:
    """The one Qt version: PySide6's, as ``requirements`` pins it."""
    try:
        return qt_version_from_requirements(Path(requirements).read_text(encoding="utf-8"))
    except OSError as exc:
        raise SdkFetchError(f"cannot read {requirements}: {exc}") from exc


@dataclass(frozen=True)
class QtSdk:
    """One Qt version's msvc2022_64 archives in Qt's online repository: where they are and what they must hash to
    (``None``: only Qt's published ``.sha256`` is checked)."""

    repository: str
    stamp: str
    tail: str
    qtbase_sha256: str | None = None
    qtbase_size: int | None = None
    qtdeclarative_sha256: str | None = None
    qtdeclarative_size: int | None = None


QT_SDKS: dict[str, QtSdk] = {
    # Values recorded in native/spike_p1/README.md when the P1 spike fetched them (7 Nov 2026). aqtinstall 3.3.0
    # cannot read this repository layout, so the archives are named here.
    "6.11.2": QtSdk(
        "https://download.qt.io/online/qtsdkrepository/windows_x86/desktop/qt6_6112/qt6_6112_msvc2022_64/"
        "qt.qt6.6112.win64_msvc2022_64",
        "6.11.2-0-202608131017",
        "-Windows-Windows_11_24H2-MSVC2022-Windows-Windows_11_24H2-X86_64.7z",
        qtbase_sha256="fd984b7264361b4dd3fd2a417702ca1258e4086268f2ee6a69b9a393d9c3f6bb",
        qtbase_size=39_618_573,
        qtdeclarative_size=172_484_222,
    ),
}


@dataclass(frozen=True)
class SdkArchive:
    """One pinned download. ``sha256`` and ``size`` are pinned in this file where known; ``published_sha256_url``
    is the checksum the vendor publishes beside the archive. At least one hash source is always required."""

    name: str
    url: str
    filename: str
    kind: str                       # "7z" or "zip"
    destination: str                # below the prefix
    sha256: str | None = None
    size: int | None = None
    published_sha256_url: str | None = None
    member_filter: str | None = None  # zip only: extract the members whose path contains this


VULKAN_HEADERS_ARCHIVE = SdkArchive(
    "vulkan_headers",
    f"https://codeload.github.com/KhronosGroup/Vulkan-Headers/zip/refs/tags/v{VULKAN_HEADERS_VERSION}",
    "vulkan_headers.zip", "zip", VULKAN_DIR, size=3_092_442,
    sha256="c3b074a30b5bce4cf32a41d234fa559ff458513b7314d69cd0b336a01b53bb78",
    member_filter="/include/",
)


def archives_for(qt_version: str) -> tuple[SdkArchive, ...]:
    """Every download for ``qt_version``: its two Qt archives (from ``QT_SDKS``) and Vulkan-Headers."""
    sdk = QT_SDKS.get(qt_version)
    if sdk is None:
        raise SdkFetchError(f"no SDK is pinned for Qt {qt_version}: add its archives to QT_SDKS in {Path(__file__).name}"
                            f" (pinned: {', '.join(sorted(QT_SDKS))})")

    def qt_archive(module: str, sha256: str | None, size: int | None) -> SdkArchive:
        url = f"{sdk.repository}/{sdk.stamp}{module}{sdk.tail}"
        return SdkArchive(module, url, f"{module}.7z", "7z", QT_DIR, sha256=sha256, size=size,
                          published_sha256_url=f"{url}.sha256")

    return (
        qt_archive("qtbase", sdk.qtbase_sha256, sdk.qtbase_size),
        qt_archive("qtdeclarative", sdk.qtdeclarative_sha256, sdk.qtdeclarative_size),
        VULKAN_HEADERS_ARCHIVE,
    )


@dataclass(frozen=True)
class SdkLayout:
    prefix: str
    qt_prefix: str
    vulkan_include: str
    qt_version: str
    fetched: bool                   # False: the prefix already held this exact SDK


Transport = Callable[[str, Path], None]          # (url, destination file)
Extractor = Callable[[Path, Path], None]         # (archive, destination directory)
Log = Callable[[str], None]


def urllib_transport(url: str, destination: Path) -> None:
    """Stream ``url`` to ``destination`` (redirects followed; the mirror is irrelevant, the hash decides)."""
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=120) as response, destination.open("wb") as handle:
        shutil.copyfileobj(response, handle, length=1024 * 1024)


def _safe_member(name: str) -> bool:
    path = PurePosixPath(name.replace("\\", "/"))
    return bool(name) and not path.is_absolute() and ".." not in path.parts and ":" not in name


def py7zr_extract(archive: Path, destination: Path) -> None:
    import py7zr  # the tool venv's; only needed when a Qt archive is extracted

    with py7zr.SevenZipFile(archive, mode="r") as seven:
        unsafe = [name for name in seven.getnames() if not _safe_member(name)]
        if unsafe:
            raise SdkFetchError(f"{archive.name} names paths outside its prefix: {unsafe[:3]}")
        seven.extractall(path=destination)


def _extract_zip(archive: Path, destination: Path, member_filter: str | None) -> None:
    with zipfile.ZipFile(archive) as bundle:
        names = [name for name in bundle.namelist() if member_filter is None or member_filter in name]
        unsafe = [name for name in names if not _safe_member(name)]
        if unsafe:
            raise SdkFetchError(f"{archive.name} names paths outside its prefix: {unsafe[:3]}")
        if not names:
            raise SdkFetchError(f"{archive.name} holds no member matching {member_filter!r}")
        bundle.extractall(destination, names)


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def parse_published_sha256(text: str) -> str:
    """The first token of a ``.sha256`` file (``<hash>  <filename>`` or the bare hash), lower-cased."""
    token = (text.split() or [""])[0].strip().lower()
    if not _SHA256.match(token):
        raise SdkFetchError(f"the published checksum is not a sha256: {text[:80]!r}")
    return token


def pins_fingerprint(archives: Sequence[SdkArchive], qt_version: str) -> str:
    """What a stamp must match: every pin (urls, hashes, sizes, layout) and the Qt version."""
    payload = json.dumps({"qt": qt_version, "archives": [asdict(item) for item in archives]}, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _download(transport: Transport, url: str, destination: Path, log: Log) -> None:
    last: Exception | None = None
    for attempt in range(1, ATTEMPTS + 1):
        try:
            transport(url, destination)
            return
        except OSError as exc:          # URLError, timeouts and connection resets are OSErrors
            last = exc
            destination.unlink(missing_ok=True)
            log(f"[NATIVE-SDK] download failed ({attempt}/{ATTEMPTS}): {url}: {exc}")
            if attempt < ATTEMPTS:
                time.sleep(2.0 * attempt)
    raise SdkFetchError(f"could not download {url}: {last}")


def verify_archive(item: SdkArchive, path: Path, published: str | None) -> str:
    """The archive's sha256 once it matches every source this pin names; otherwise SdkFetchError."""
    if item.sha256 is None and published is None:
        raise SdkFetchError(f"{item.name}: no checksum to verify against (refusing an unverified archive)")
    size = path.stat().st_size
    if item.size is not None and size != item.size:
        raise SdkFetchError(f"{item.name}: {size} bytes, pinned {item.size}")
    actual = sha256_of(path)
    if item.sha256 is not None and actual != item.sha256:
        raise SdkFetchError(f"{item.name}: sha256 {actual}, pinned {item.sha256}")
    if published is not None and actual != published:
        raise SdkFetchError(f"{item.name}: sha256 {actual}, published {published}")
    return actual


def qt_version_in(qt_prefix: Path) -> str | None:
    for name in ("Qt6ConfigVersionImpl.cmake", "Qt6ConfigVersion.cmake"):
        path = qt_prefix / "lib" / "cmake" / "Qt6" / name
        if path.is_file():
            match = re.search(r'set\(PACKAGE_VERSION "([^"]+)"\)', path.read_text(encoding="utf-8", errors="replace"))
            if match:
                return match.group(1)
    return None


def layout_problem(prefix: Path, qt_version: str) -> str | None:
    """Why ``prefix`` does not hold the whole SDK for ``qt_version`` (None: it does)."""
    qt_prefix = prefix / QT_DIR
    version = qt_version_in(qt_prefix)
    if version is None:
        return f"no Qt CMake package under {qt_prefix}"
    if version != qt_version:
        return f"the Qt under {qt_prefix} is {version}, pinned {qt_version}"
    if not (qt_prefix / "lib" / "cmake" / "Qt6Quick" / "Qt6QuickConfig.cmake").is_file():
        return f"no Qt Quick CMake package under {qt_prefix} (qtdeclarative)"
    if not (prefix / Path(VULKAN_INCLUDE_RELATIVE.replace("\\", "/")) / "vulkan" / "vulkan.h").is_file():
        return f"no vulkan/vulkan.h under {prefix / VULKAN_DIR}"
    return None


def _layout(prefix: Path, qt_version: str, fetched: bool) -> SdkLayout:
    return SdkLayout(str(prefix), str(prefix / QT_DIR), str(prefix / Path(VULKAN_INCLUDE_RELATIVE.replace("\\", "/"))),
                     qt_version, fetched)


def _stamp_matches(prefix: Path, fingerprint: str, qt_version: str) -> bool:
    try:
        stamp = json.loads((prefix / STAMP_NAME).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return (isinstance(stamp, dict) and stamp.get("schema") == STAMP_SCHEMA
            and stamp.get("pins") == fingerprint and stamp.get("qt_version") == qt_version)


def fetch_sdk(
    prefix: Path,
    *,
    qt_version: str | None = None,
    archives: Sequence[SdkArchive] | None = None,
    transport: Transport = urllib_transport,
    extract_7z: Extractor = py7zr_extract,
    log: Log = print,
    keep_downloads: bool = False,
) -> SdkLayout:
    """Make ``prefix`` hold exactly the SDK for ``qt_version`` (default: the pinned one); verify everything before
    extracting anything."""

    qt_version = qt_version or pinned_qt_version()
    archives = tuple(archives) if archives is not None else archives_for(qt_version)
    prefix = Path(prefix).resolve()
    fingerprint = pins_fingerprint(archives, qt_version)
    if _stamp_matches(prefix, fingerprint, qt_version) and layout_problem(prefix, qt_version) is None:
        log(f"[NATIVE-SDK] {prefix} already holds Qt {qt_version} and Vulkan-Headers {VULKAN_HEADERS_VERSION}")
        return _layout(prefix, qt_version, fetched=False)

    downloads = prefix / DOWNLOADS_DIR
    downloads.mkdir(parents=True, exist_ok=True)
    (prefix / STAMP_NAME).unlink(missing_ok=True)
    verified: dict[str, str] = {}
    try:
        for item in archives:
            archive = downloads / item.filename
            log(f"[NATIVE-SDK] {item.name}: {item.url}")
            _download(transport, item.url, archive, log)
            published = None
            if item.published_sha256_url:
                checksum = downloads / f"{item.filename}.sha256"
                _download(transport, item.published_sha256_url, checksum, log)
                published = parse_published_sha256(checksum.read_text(encoding="utf-8", errors="replace"))
            try:
                verified[item.name] = verify_archive(item, archive, published)
            except SdkFetchError:
                archive.unlink(missing_ok=True)
                raise
            log(f"[NATIVE-SDK] {item.name}: verified sha256 {verified[item.name]}")

        for item in archives:           # only once every archive is verified
            destination = prefix / item.destination
            destination.mkdir(parents=True, exist_ok=True)
            archive = downloads / item.filename
            if item.kind == "7z":
                extract_7z(archive, destination)
            elif item.kind == "zip":
                _extract_zip(archive, destination, item.member_filter)
            else:
                raise SdkFetchError(f"{item.name}: unknown archive kind {item.kind!r}")
            log(f"[NATIVE-SDK] {item.name}: extracted into {destination}")
    finally:
        if not keep_downloads:
            shutil.rmtree(downloads, ignore_errors=True)

    problem = layout_problem(prefix, qt_version)
    if problem is not None:
        raise SdkFetchError(f"the extracted SDK is not whole: {problem}")
    stamp = {"schema": STAMP_SCHEMA, "qt_version": qt_version, "vulkan_headers": VULKAN_HEADERS_VERSION,
             "pins": fingerprint, "sha256": verified}
    (prefix / STAMP_NAME).write_text(json.dumps(stamp, indent=2) + "\n", encoding="utf-8")
    return _layout(prefix, qt_version, fetched=True)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--prefix", type=Path,
                        help="SDK root (never inside the repository; the workflow uses the runner's temp folder)")
    action.add_argument("--print-qt-version", action="store_true",
                        help="print the Qt version requirements.txt pins (PySide6==x.y.z) and exit")
    parser.add_argument("--keep-downloads", action="store_true", help="keep the verified archives in downloads/")
    args = parser.parse_args(argv)
    try:
        if args.print_qt_version:
            print(pinned_qt_version())
            return 0
        layout = fetch_sdk(args.prefix, keep_downloads=args.keep_downloads)
    except SdkFetchError as exc:
        print(f"[NATIVE-SDK] REFUSED: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(asdict(layout), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
