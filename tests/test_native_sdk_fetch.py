"""The native module's SDK fetch (tools/native_sdk_fetch.py): fail closed, verify before extracting.

Nothing here touches the network: the transport is a dictionary of fake archives, the ``.7z`` extractor writes a
fake Qt prefix, and the zip is built in ``tmp_path``. The contracts proven: an archive is extracted only after every
archive matched each checksum its pin names (pinned sha256, Qt's published ``.sha256``, the pinned size); one
mismatch extracts nothing and leaves no stamp; an archive that escapes its prefix is refused; a prefix whose stamp
matches the pins is left alone; the pins agree with build.cmd, CMakeLists.txt and requirements.txt."""
from __future__ import annotations

import hashlib
import io
import json
import re
import zipfile
from dataclasses import replace
from pathlib import Path

import pytest

from tools import native_sdk_fetch as sdk

ROOT = Path(__file__).resolve().parents[1]
QT = sdk.pinned_qt_version()
ARCHIVES = sdk.archives_for(QT)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _vulkan_zip(extra: dict[str, bytes] | None = None) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as bundle:
        top = f"Vulkan-Headers-{sdk.VULKAN_HEADERS_VERSION}"
        bundle.writestr(f"{top}/include/vulkan/vulkan.h", "/* vulkan */\n")
        bundle.writestr(f"{top}/README.md", "not extracted\n")
        for name, data in (extra or {}).items():
            bundle.writestr(name, data)
    return buffer.getvalue()


class Fixture:
    """Fake archives for the real pin table's shape: two Qt 7z archives (pinned + published sha) and a zip."""

    def __init__(self, *, qt_version: str = QT, zip_bytes: bytes | None = None):
        self.qt_version = qt_version
        self.blobs: dict[str, bytes] = {}
        self.calls: list[str] = []
        self.extracted: list[str] = []
        archives = []
        for item in ARCHIVES:
            data = zip_bytes if item.kind == "zip" and zip_bytes is not None else (
                _vulkan_zip() if item.kind == "zip" else f"7z:{item.name}".encode())
            self.blobs[item.url] = data
            if item.published_sha256_url:
                self.blobs[item.published_sha256_url] = f"{_sha(data)}  {item.filename}\n".encode()
            archives.append(replace(
                item,
                sha256=_sha(data) if item.sha256 is not None else None,
                size=len(data) if item.size is not None else None,
            ))
        self.archives = tuple(archives)

    def transport(self, url: str, destination: Path) -> None:
        self.calls.append(url)
        destination.write_bytes(self.blobs[url])

    def extract_7z(self, archive: Path, destination: Path) -> None:
        self.extracted.append(archive.name)
        cmake = destination / "lib" / "cmake"
        (cmake / "Qt6").mkdir(parents=True, exist_ok=True)
        (cmake / "Qt6" / "Qt6ConfigVersionImpl.cmake").write_text(
            f'set(PACKAGE_VERSION "{self.qt_version}")\n', encoding="utf-8")
        if archive.name.startswith("qtdeclarative"):
            (cmake / "Qt6Quick").mkdir(parents=True, exist_ok=True)
            (cmake / "Qt6Quick" / "Qt6QuickConfig.cmake").write_text("# quick\n", encoding="utf-8")

    def fetch(self, prefix: Path, **kwargs):
        return sdk.fetch_sdk(prefix, qt_version=QT, archives=self.archives, transport=self.transport,
                             extract_7z=self.extract_7z, log=lambda _line: None, **kwargs)


def test_a_verified_sdk_is_extracted_into_the_build_layout_and_stamped(tmp_path):
    fixture = Fixture()
    layout = fixture.fetch(tmp_path / "sdk")
    prefix = (tmp_path / "sdk").resolve()
    assert layout.fetched and layout.qt_version == QT
    assert Path(layout.qt_prefix) == prefix / sdk.QT_DIR
    assert (Path(layout.vulkan_include) / "vulkan" / "vulkan.h").is_file()
    assert not (prefix / sdk.VULKAN_DIR / f"Vulkan-Headers-{sdk.VULKAN_HEADERS_VERSION}" / "README.md").exists()
    assert sdk.layout_problem(prefix, QT) is None
    stamp = json.loads((prefix / sdk.STAMP_NAME).read_text(encoding="utf-8"))
    assert stamp["pins"] == sdk.pins_fingerprint(fixture.archives, QT) and set(stamp["sha256"]) == {
        item.name for item in fixture.archives}
    assert not (prefix / sdk.DOWNLOADS_DIR).exists()                    # archives removed after extraction

    # The cached prefix: nothing is downloaded or extracted again.
    fixture.calls.clear()
    fixture.extracted.clear()
    again = fixture.fetch(tmp_path / "sdk")
    assert not again.fetched and fixture.calls == [] and fixture.extracted == []


def test_a_changed_pin_refetches_a_stamped_prefix(tmp_path):
    fixture = Fixture()
    fixture.fetch(tmp_path / "sdk")
    fixture.calls.clear()
    fixture.archives = tuple(replace(item, url=item.url) for item in fixture.archives[:-1]) + (
        replace(fixture.archives[-1], member_filter="/include/vulkan/"),)
    assert fixture.fetch(tmp_path / "sdk").fetched and fixture.calls


def _mutate(fixture: Fixture, case: str) -> None:
    qtbase = next(index for index, item in enumerate(fixture.archives) if item.name == "qtbase")
    declarative = next(index for index, item in enumerate(fixture.archives) if item.name == "qtdeclarative")
    items = list(fixture.archives)
    if case == "pinned-sha":
        items[qtbase] = replace(items[qtbase], sha256="0" * 64)
    elif case == "published-sha":
        fixture.blobs[items[declarative].published_sha256_url] = b"1" * 64 + b"  qtdeclarative.7z\n"
    elif case == "malformed-published":
        fixture.blobs[items[declarative].published_sha256_url] = b"<html>mirror error</html>"
    elif case == "size":
        items[qtbase] = replace(items[qtbase], size=items[qtbase].size + 1)
    elif case == "no-checksum":
        items[declarative] = replace(items[declarative], sha256=None, published_sha256_url=None)
    elif case == "zip-bytes":
        fixture.blobs[items[-1].url] = _vulkan_zip({"extra.txt": b"x"})
    fixture.archives = tuple(items)


@pytest.mark.parametrize("case", ["pinned-sha", "published-sha", "malformed-published", "size", "no-checksum",
                                  "zip-bytes"])
def test_any_checksum_mismatch_extracts_nothing(tmp_path, case):
    fixture = Fixture()
    _mutate(fixture, case)
    with pytest.raises(sdk.SdkFetchError):
        fixture.fetch(tmp_path / "sdk")
    prefix = tmp_path / "sdk"
    assert fixture.extracted == []
    assert not (prefix / sdk.QT_DIR).exists() and not (prefix / sdk.VULKAN_DIR).exists()
    assert not (prefix / sdk.STAMP_NAME).exists()


def test_an_archive_that_escapes_its_prefix_is_refused(tmp_path):
    hostile = _vulkan_zip({f"Vulkan-Headers-{sdk.VULKAN_HEADERS_VERSION}/include/../../../escape.h": b"x"})
    fixture = Fixture(zip_bytes=hostile)
    with pytest.raises(sdk.SdkFetchError, match="outside"):
        fixture.fetch(tmp_path / "sdk")
    assert not list(tmp_path.rglob("escape.h"))
    assert not ((tmp_path / "sdk") / sdk.STAMP_NAME).exists()


def test_an_sdk_of_another_qt_version_is_refused(tmp_path):
    fixture = Fixture(qt_version="6.11.1")
    with pytest.raises(sdk.SdkFetchError, match="6.11.1"):
        fixture.fetch(tmp_path / "sdk")
    assert not ((tmp_path / "sdk") / sdk.STAMP_NAME).exists()


def test_a_flaky_download_is_retried_and_a_dead_one_fails_closed(tmp_path, monkeypatch):
    monkeypatch.setattr(sdk.time, "sleep", lambda _s: None)
    fixture = Fixture()
    failures = {"left": 2}
    real = fixture.transport

    def flaky(url, destination):
        if failures["left"]:
            failures["left"] -= 1
            raise ConnectionResetError("reset")
        real(url, destination)

    fixture.transport = flaky
    assert fixture.fetch(tmp_path / "ok").fetched

    def dead(url, destination):
        raise TimeoutError("timed out")

    fixture.transport = dead
    with pytest.raises(sdk.SdkFetchError, match="could not download"):
        fixture.fetch(tmp_path / "dead")


def test_the_cli_reports_a_refusal_with_a_nonzero_exit(tmp_path, monkeypatch, capsys):
    def refuse(*_args, **_kwargs):
        raise sdk.SdkFetchError("qtbase: sha256 x, pinned y")

    monkeypatch.setattr(sdk, "fetch_sdk", refuse)
    assert sdk.main(["--prefix", str(tmp_path / "sdk")]) == 1
    assert "REFUSED" in capsys.readouterr().err


# ------------------------------------------------------------------------------------- the real pins and consumers


@pytest.mark.parametrize("version", sorted(sdk.QT_SDKS))
def test_every_pinned_qt_version_has_checksummed_archives(version):
    archives = sdk.archives_for(version)
    for item in archives:
        assert item.sha256 is not None or item.published_sha256_url is not None, item.name
        assert item.sha256 is None or re.fullmatch(r"[0-9a-f]{64}", item.sha256), item.name
        assert item.url.startswith("https://"), item.name
        if item.kind == "7z":
            assert item.published_sha256_url == f"{item.url}.sha256" and item.destination == sdk.QT_DIR
            assert version in item.url
    assert {item.name for item in archives} == {"qtbase", "qtdeclarative", "vulkan_headers"}


def test_the_qt_version_is_the_pyside6_pin_and_has_an_sdk_entry():
    requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8")
    pin = re.search(r"^PySide6==(\S+)", requirements, re.MULTILINE).group(1)
    assert pin.split(".")[:3] == QT.split(".") and QT in sdk.QT_SDKS
    assert sdk.qt_version_from_requirements("shiboken6==1.0\nPySide6==7.8.9.1  # build release\n") == "7.8.9"
    for text in ("PySide6_Addons==6.11.2\n", "PySide6>=6.11\n", ""):
        with pytest.raises(sdk.SdkFetchError):
            sdk.qt_version_from_requirements(text)
    with pytest.raises(sdk.SdkFetchError, match="no SDK is pinned for Qt 0.0.1"):
        sdk.archives_for("0.0.1")


def test_the_cli_prints_the_pinned_qt_version(capsys):
    assert sdk.main(["--print-qt-version"]) == 0
    assert capsys.readouterr().out.strip() == QT


def test_no_consumer_restates_the_qt_version():
    # One value: the CMake guard reads the pin itself; the workflow takes it from the fetch script.
    cmake = (ROOT / "native" / "spike_p1" / "CMakeLists.txt").read_text(encoding="utf-8")
    assert "requirements.txt" in cmake and 'REGEX "^PySide6=="' in cmake
    assert not re.search(r"\b6\.\d+\.\d+\b", cmake)
    workflow = (ROOT / ".github" / "workflows" / "native-module.yml").read_text(encoding="utf-8")
    assert "tools\\native_sdk_fetch.py --print-qt-version" in workflow and "QT_VERSION=$qt" in workflow
    assert not re.search(r"\b6\.\d+\.\d+\b", workflow)
    build_cmd = (ROOT / "native" / "spike_p1" / "build.cmd").read_text(encoding="utf-8")
    assert not re.search(r"\b6\.\d+\.\d+\b", build_cmd)
    assert sdk.VULKAN_INCLUDE_RELATIVE in build_cmd and f"%SPIKE%\\{sdk.QT_DIR}" in build_cmd
    source = Path(sdk.__file__).read_text(encoding="utf-8")
    assert not re.search(r"^QT_VERSION\s*=", source, re.MULTILINE)          # versions only as QT_SDKS keys
