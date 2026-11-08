"""The Linux build derives its Nuitka declarations from the Windows build scripts.

Pure text checks, so they run on every platform: the Windows scripts are edited on Windows, where the Linux-only
``tests/test_linux_*.py`` files never run (8 Nov 2026: a comment with an apostrophe in ``build_nuitka.ps1`` dropped
every declaration from the Linux build, presets included, and nothing on Windows noticed)."""
from __future__ import annotations

from pathlib import Path

from tools import linux_build

ROOT = Path(__file__).resolve().parents[1]


def test_portable_windows_declarations_reach_linux_without_windows_payload() -> None:
    arguments = linux_build.portable_windows_arguments()
    for required in (
        "--enable-plugin=pyside6",
        "--include-data-dir=presets=presets",
        "--include-data-dir=themes=themes",
        "--include-data-dir=rendering/quick/qml=rendering/quick/qml",
        "--include-data-files=ui/resources/assets.rcc=ui/resources/assets.rcc",
        "--include-package=sounddevice",
        "--noinclude-default-mode=error",
    ):
        assert required in arguments
    lowered = " ".join(arguments).lower()
    for windows_only in ("winrt", "pyaudiowpatch", "--msvc", "--onefile", "--windows-", "$"):
        assert windows_only not in lowered
    assert not any(value.startswith(("--jobs=", "--standalone")) for value in arguments)


def test_every_quoted_declaration_of_the_windows_list_is_read() -> None:
    # Every "--..." literal on a code line of the Windows $argsList (comments removed) is either taken or deliberately
    # filtered; none is lost to quote pairing.
    text = (ROOT / "scripts" / "venv" / "build_nuitka.ps1").read_text(encoding="utf-8")
    block = linux_build._ps1_array(linux_build._strip_ps1_comments(text), "$argsList = @(")
    literals = [line.strip().rstrip(",").strip("\"'") for line in block.splitlines()
                if line.strip().startswith(("\"--", "'--"))]
    taken = set(linux_build.portable_windows_arguments())
    lost = [value for value in literals if value not in taken and "$" not in value
            and not any(marker in value.lower() for marker in linux_build._WINDOWS_ONLY_MARKERS)
            and not value.startswith(linux_build._DRIVER_OWNED)]
    assert literals and not lost


def test_comments_with_quotes_never_shift_the_extraction(tmp_path) -> None:
    script = tmp_path / "build.ps1"
    script.write_text(
        "<# a block comment's \"quotes\" #>\n"
        "$argsList = @(\n"
        "    \"-m\", \"nuitka\",\n"
        "    # Nuitka's one-time prompt: its default \"no\" (and a paren) is fatal\n"
        "    \"--include-data-dir=presets=presets\",  # trailing note, isn't it\n"
        "    '--include-package=sounddevice',\n"
        "    \"--include-data-files=a#b=a#b\"\n"
        ")\n",
        encoding="utf-8",
    )
    assert linux_build.portable_windows_arguments(script) == [
        "--include-data-dir=presets=presets", "--include-package=sounddevice", "--include-data-files=a#b=a#b"]


def test_powershell_escapes_and_here_strings_are_read_as_powershell_reads_them() -> None:
    # Checkpoint audit 11, A11-L8: the stripper paired quotes and cut at any "#" outside them, so it passed today's
    # scripts only by parity. A backtick-escaped quote, a "<# #>" inside a string and a here-string's own text are now
    # read as PowerShell reads them: nothing inside a string is a comment, every real comment goes. Negative control
    # (the toggle-per-quote stripper): six of the twelve lines misread (the escaped quote's string, the escaped "#",
    # both here-strings' text and the string holding "<# #>" cut; the comment after a here-string's closer kept).
    source = [
        ("$a = \"x `\" # in the string\"  # a comment, isn't it", "$a = \"x `\" # in the string\"  "),
        ("$b = 'it''s # in the string'  # a comment", "$b = 'it''s # in the string'  "),
        ("$c = \"say \"\"hi\"\" # in\" # a comment", "$c = \"say \"\"hi\"\" # in\" "),
        ("$d = `#not-a-comment", "$d = `#not-a-comment"),
        ("$e = @'", "$e = @'"),
        ("  # the here-string's own text, isn't it", "  # the here-string's own text, isn't it"),
        ("'@  # a comment after the closer", "'@  "),
        ("$f = @\"", "$f = @\""),
        ("  \"quoted\" # the here-string's text", "  \"quoted\" # the here-string's text"),
        ("\"@", "\"@"),
        ("<# a block \"comment\" #> $g = 'after the block'  # gone", " $g = 'after the block'  "),
        ("$h = \"<# not a block #>\"", "$h = \"<# not a block #>\""),
    ]
    text = "\n".join(line for line, _expected in source) + "\n"
    stripped = linux_build._strip_ps1_comments(text).split("\n")
    assert stripped[:len(source)] == [expected for _line, expected in source]


def test_qt_size_exclusions_translate_to_shared_objects() -> None:
    arguments = linux_build.qt_prune_arguments()
    assert "--noinclude-data-files=PySide6/qml/QtWebEngine/**" in arguments
    assert "--noinclude-dlls=*Qt6WebEngine*.so*" in arguments
    assert "--nofollow-import-to=pytz" in arguments
    assert not any(value.endswith(".dll") for value in arguments)


def test_build_entry_points_and_workflow_reference_existing_files() -> None:
    workflow = (ROOT / ".github" / "workflows" / "linux-build.yml").read_text(encoding="utf-8")
    for path in ("scripts/linux/setup.sh", "tools/linux_build.py", "tools/linux_smoke_dist.py"):
        assert path in workflow and (ROOT / path).is_file()
    assert "linux-build/*" in workflow and "workflow_dispatch" in workflow
    windows = (ROOT / "scripts" / "linux" / "build_from_windows.ps1").read_text(encoding="utf-8")
    assert "linux-build.yml" in windows and "srpss-linux" in workflow and "srpss-linux" in windows
