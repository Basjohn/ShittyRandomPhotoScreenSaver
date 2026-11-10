"""Linux MC product selection and isolation (no Linux toolchain or GitHub run required).

These checks run on Windows too; they ensure the GitHub Remote row selects the real MC entrypoint,
that both Linux products publish different artifacts and that their installed settings stay separate.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from core.settings.storage_paths import detect_current_profile
from tools import build_runner, linux_build

ROOT = Path(__file__).resolve().parents[1]


def test_linux_nuitka_profiles_share_declarations_but_not_entrypoint(tmp_path: Path) -> None:
    standard = linux_build.nuitka_arguments(tmp_path / "standard", 2)
    mc = linux_build.nuitka_arguments(tmp_path / "mc", 2, "mc")
    assert standard[-1] == "main.py" and mc[-1] == "main_mc.py"
    assert "--output-filename=srpss" in standard
    assert "--output-filename=srpss-mc" in mc
    assert any(arg == "--include-data-dir=presets=presets" for arg in standard)
    assert {arg for arg in standard if not arg.startswith(("--output-dir=", "--output-filename=")) and arg != "main.py"} == {arg for arg in mc if not arg.startswith(("--output-dir=", "--output-filename=")) and arg != "main_mc.py"}
    assert all("-linux" not in arg for arg in standard if arg.startswith("--output-filename="))


def test_linux_mc_only_appears_as_an_optional_github_remote_job(tmp_path: Path) -> None:
    assert "linux_mc" not in {job.key for mode in ("normal", "venv")
                              for job in build_runner.jobs_for_mode(mode, tmp_path)}
    jobs = {job.key: job for job in build_runner.jobs_for_mode("github", tmp_path)}
    assert jobs["linux"].expected_artifact.name.endswith("-linux-x86_64.tar.gz")
    assert jobs["linux_mc"].expected_artifact.name.endswith("-linux-mc-x86_64.tar.gz")
    assert jobs["linux"].expected_artifact != jobs["linux_mc"].expected_artifact
    assert jobs["linux_mc"].script == jobs["linux"].script
    assert not jobs["linux_mc"].default_selected
    commit = SimpleNamespace(branch="main", sha="a" * 40)
    pinned = build_runner.PreflightResult(remote_commit=commit)
    assert build_runner._job_arguments(jobs["linux"], pinned) == ["-Branch", "main", "-Commit", "a" * 40]
    assert build_runner._job_arguments(jobs["linux_mc"], pinned) == [
        "-Profile", "mc", "-Branch", "main", "-Commit", "a" * 40,
    ]
    assert build_runner._job_arguments(jobs["linux_mc"], build_runner.PreflightResult()) == ["-Profile", "mc"]


def test_mc_frozen_executable_resolves_its_own_settings_profile(monkeypatch) -> None:
    main = sys.modules["__main__"]
    original_file = getattr(main, "__file__", None)
    try:
        monkeypatch.setattr(main, "__file__", "/srv/runtime/app", raising=False)
        monkeypatch.setattr(sys, "argv", ["/home/test/.local/opt/srpss-mc/srpss-mc", "/s"])
        assert detect_current_profile() == "Screensaver_MC"
        monkeypatch.setattr(sys, "argv", ["/home/test/.local/opt/srpss/srpss", "/s"])
        assert detect_current_profile() == "Screensaver"
        monkeypatch.setattr(sys, "argv", ["/home/test/projects/srpss-mc/src/main.py", "/s"])
        assert detect_current_profile() == "Screensaver"  # repo folder names are not product identities
    finally:
        if original_file is None:
            delattr(main, "__file__")
        else:
            setattr(main, "__file__", original_file)


def test_both_linux_install_scripts_have_separate_executables_desktop_entries_and_uninstalls() -> None:
    standard = linux_build.install_script()
    mc = linux_build.install_script("mc")
    for binary, script in (("srpss", standard), ("srpss-mc", mc)):
        assert f'APP="{binary}"' in script
        assert 'PREFIX="$HOME/.local/opt/$APP"' in script
        assert 'ln -sf "$PREFIX/$APP" "$BIN/$APP"' in script
        assert '$APP.desktop' in script
        assert '$APP-settings.desktop' in script
        assert 'if [[ ! -d "$HOME/.local/opt/$PEER" ]]; then' in script
        assert "__APP_" not in script and "__RUN_MODE__" not in script
    assert "SRPSS Screensaver" in standard and "SRPSS Media Center" in mc


def test_workflow_and_dispatch_have_distinct_linux_artifact_authorities() -> None:
    workflow = (ROOT / ".github/workflows/linux-build.yml").read_text(encoding="utf-8")
    dispatcher = (ROOT / "scripts/linux/build_from_windows.ps1").read_text(encoding="utf-8")
    assert "--profile \"$BUILD_PROFILE\"" in workflow
    assert "refs/tags/linux-build/mc-" in workflow
    assert "srpss-linux-mc" in workflow and "srpss-linux" in workflow
    assert "SRPSS-*-linux-mc-x86_64.tar.gz" in workflow
    assert "SRPSS-*-linux-x86_64.tar.gz" in workflow
    assert "ValidateSet('screensaver', 'mc')" in dispatcher
    assert "'-f', 'profile=mc'" in dispatcher
    assert "'linux-build/'" in dispatcher and "'mc-'" in dispatcher
    assert "--json', 'databaseId,headBranch'" in dispatcher
    assert "'srpss-linux-mc'" in dispatcher and "'srpss-linux'" in dispatcher
    assert "Default workflow has no MC input yet" in dispatcher
    assert "origin/main:.github/workflows/linux-build.yml" in dispatcher


def test_generated_installers_are_valid_bash_when_available(tmp_path: Path) -> None:
    bash = shutil.which("bash")
    if not bash:
        pytest.skip("bash unavailable (syntax validated in Ubuntu workflow)")
    for profile in linux_build.PROFILES:
        path = tmp_path / f"{profile}.sh"
        path.write_text(linux_build.install_script(profile), encoding="utf-8")
        assert subprocess.run([bash, "-n", str(path)], check=False).returncode == 0


def test_installing_and_uninstalling_mc_preserves_existing_screensaver(tmp_path: Path, monkeypatch) -> None:
    """Actual shell install contract, with tiny test-owned stand-ins rather than a 480 MB Nuitka distribution."""
    bash = shutil.which("bash")
    if not bash or sys.platform == "win32":
        pytest.skip("requires a Linux/POSIX bash for isolated installer execution")
    home = tmp_path / "home"
    home.mkdir()
    data = home / ".local/share"
    env = {**__import__("os").environ, "HOME": str(home), "XDG_DATA_HOME": str(data)}

    def product(profile: str) -> Path:
        name = linux_build.PROFILES[profile][1]
        folder = tmp_path / f"product-{name}"
        folder.mkdir()
        for rel, payload in {
            name: b"stub executable",
            "srpss.png": b"icon",
            "presets/visualizer_modes/bubble/preset_1.json": profile.encode(),
            "themes/theme.srtheme": b"test theme",
            "resources/tutuogg.ogg": b"sound",
            "resources/jedimodeyall.mp3": b"sound",
        }.items():
            file = folder / rel
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_bytes(payload)
        (folder / "install.sh").write_text(linux_build.install_script(profile))
        return folder

    screensaver = product("screensaver")
    mc = product("mc")
    for folder in (screensaver, mc):
        subprocess.run([bash, str(folder / "install.sh")], cwd=folder, env=env, check=True, capture_output=True)
    assert (home / ".local/opt/srpss/srpss").exists()
    assert (home / ".local/opt/srpss-mc/srpss-mc").exists()
    assert (home / ".local/bin/srpss").is_symlink()
    assert (home / ".local/bin/srpss-mc").is_symlink()
    assert (data / "applications/srpss.desktop").is_file()
    assert (data / "applications/srpss-mc.desktop").is_file()
    shared = data / "SRPSS/presets/visualizer_modes/bubble/preset_1.json"
    assert shared.is_file()
    subprocess.run([bash, str(mc / "install.sh"), "--uninstall"], cwd=mc, env=env, check=True, capture_output=True)
    assert not (home / ".local/opt/srpss-mc").exists()
    assert (home / ".local/opt/srpss/srpss").exists()
    assert shared.is_file(), "uninstalling MC must not wipe the other installed profile's preset tree"


def test_linux_build_publishes_separate_profile_tarballs_without_interference(tmp_path: Path, monkeypatch) -> None:
    """Exercise the real build folder/publish/tar logic with a deterministic stand-in for Nuitka."""
    def fake_nuitka_run(command, *, cwd, check):
        assert check and cwd == linux_build.REPO
        if "nuitka" not in command:
            assert any(str(arg).endswith("regen_qrc.py") for arg in command)
            return SimpleNamespace(returncode=0)
        output = Path(next(arg.split("=", 1)[1] for arg in command if arg.startswith("--output-dir=")))
        source = command[-1]
        binary = next(arg.split("=", 1)[1] for arg in command if arg.startswith("--output-filename="))
        folder = output / (Path(source).stem + ".dist")
        folder.mkdir(parents=True)
        (folder / binary).write_bytes(f"built:{source}".encode())
        return SimpleNamespace(returncode=0)

    def fake_extras(folder: Path, profile: str):
        (folder / "install.sh").write_text(linux_build.install_script(profile), encoding="utf-8")

    monkeypatch.setattr(linux_build.subprocess, "run", fake_nuitka_run)
    monkeypatch.setattr(linux_build, "_write_payload_extras", fake_extras)
    outputs = {}
    for profile, binary, suffix in (("screensaver", "srpss", ""), ("mc", "srpss-mc", "-mc")):
        product = linux_build.build(tmp_path, 2, False, profile)
        assert product.name == f"SRPSS-{linux_build._app_version()}-linux{suffix}-x86_64"
        assert (product / binary).read_bytes() == f"built:{linux_build.PROFILES[profile][0]}".encode()
        archive = product.with_name(product.name + ".tar.gz")
        assert archive.is_file() and archive.stat().st_size > 0
        outputs[profile] = product
    assert outputs["screensaver"] != outputs["mc"]
    assert (outputs["screensaver"] / "srpss").is_file()
    assert (outputs["mc"] / "srpss-mc").is_file()


def test_mc_smoke_seeds_an_available_xvfb_display(monkeypatch, tmp_path: Path) -> None:
    """MC's display-2 default must not create a falsely headless one-monitor smoke run."""
    from tools import linux_headless as lh
    from core.settings.display_selection import enabled_monitor_numbers

    assert enabled_monitor_numbers([2], 1) == frozenset()
    assert enabled_monitor_numbers("ALL", 1) == frozenset({1})
    recorded = {}

    def capture(argv, *, cwd, env, capture_output, check):
        recorded["argv"] = argv
        assert cwd == lh.REPO and capture_output and check
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(lh.subprocess, "run", capture)
    lh.seed_profile({"DISPLAY": ":95"}, tmp_path, 4, application="Screensaver_MC")
    script = recorded["argv"][2]
    assert 'settings.set("display.show_on_monitors", "ALL")' in script
    assert recorded["argv"][-1] == "Screensaver_MC"


def test_linux_smoke_failure_includes_child_diagnostics(tmp_path: Path, capsys) -> None:
    """An Xvfb smoke failure must expose logs AND the frozen child's captured output."""
    from tools import linux_smoke_dist

    logs = tmp_path / "logs"
    logs.mkdir()
    (logs / "screensaver_qml.log").write_text("QML trace", encoding="utf-8")
    assert linux_smoke_dist._fail("missing ready marker", logs / "screensaver.log", stdout=b"crash details") == 1
    output = capsys.readouterr().out
    assert "Main log missing" in output
    assert "screensaver_qml.log" in output
    assert "crash details" in output


def test_smoke_does_not_enable_release_logging() -> None:
    """Release profiles remain logging-off; smoke observes actual Xvfb pixels."""
    import inspect
    from tools import linux_smoke_dist

    main_source = inspect.getsource(linux_smoke_dist.main)
    assert "logging.cfg" not in main_source
    assert "_has_rendered_scene" in main_source
    assert "_xvfb_gl46_available" in main_source
    assert "Quick startup display ready" not in main_source


def test_smoke_scene_evidence_rejects_blank_and_nearly_flat_frames(tmp_path: Path) -> None:
    from PIL import Image, ImageDraw
    from tools import linux_smoke_dist

    blank = tmp_path / "blank.png"
    black = tmp_path / "black.png"
    flat = tmp_path / "flat.png"
    scene = tmp_path / "scene.png"
    Image.new("RGB", (480, 270), "black").save(blank)
    Image.new("RGB", (480, 270), "black").save(black)
    Image.new("RGB", (480, 270), (36, 36, 36)).save(flat)
    picture = Image.new("RGB", (480, 270), "black")
    draw = ImageDraw.Draw(picture)
    for x in range(0, 480, 20):
        draw.rectangle((x, 0, x + 9, 269), fill=(x % 190 + 50, 110, 220))
    picture.save(scene)
    assert not linux_smoke_dist._has_rendered_scene(blank, black)[0]
    assert not linux_smoke_dist._has_rendered_scene(blank, flat)[0]
    assert linux_smoke_dist._has_rendered_scene(blank, scene)[0]


def test_smoke_gl_capability_probes_isolated_display(monkeypatch) -> None:
    from tools import linux_smoke_dist

    args = []
    def run(command, **kwargs):
        assert command == ["glxinfo", "-B"]
        assert kwargs["env"] == {"DISPLAY": ":95"}
        args.append(command)
        return SimpleNamespace(returncode=0, stdout=b"OpenGL core profile version string: 4.6 (Core Profile) Mesa")

    monkeypatch.setattr(linux_smoke_dist.subprocess, "run", run)
    assert linux_smoke_dist._xvfb_gl46_available({"DISPLAY": ":95"})[0]
    assert args

@pytest.mark.parametrize("binary", ["srpss", "srpss-mc"])
def test_linux_smoke_uses_pixels_not_frozen_logs(monkeypatch, tmp_path: Path, binary: str) -> None:
    """End-to-end harness contract with tiny subprocess/Xvfb stand-ins for both products."""
    from PIL import Image, ImageDraw
    from tools import linux_smoke_dist as smoke

    product_name = f"SRPSS-5.1.3-linux{'-mc' if binary == 'srpss-mc' else ''}-x86_64"
    product = tmp_path / product_name
    product.mkdir()
    (product / binary).write_bytes(b"frozen product stand-in")
    (product / "install.sh").write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    out = tmp_path / "evidence"
    out.mkdir()
    processes = []
    profiles = []
    screenshots = []

    class FakeProcess:
        def __init__(self, argv, **kwargs):
            self.argv = argv
            self.returncode = None
            processes.append(self)

        def poll(self):
            return self.returncode

        def wait(self, timeout=None):
            self.returncode = 0
            return 0

        def terminate(self):
            self.returncode = 0

        def kill(self):
            self.returncode = -9

    def install_or_probe(argv, **kwargs):
        assert argv[0] == str(product / "install.sh")
        home = Path(kwargs["env"]["HOME"])
        installed = home / ".local" / "opt" / binary / binary
        installed.parent.mkdir(parents=True, exist_ok=True)
        installed.write_bytes(b"installed binary")
        data = tmp_path / "work" / "profile" / "data" / "SRPSS"
        for name in ("themes", "presets/visualizer_modes", "sounds"):
            (data / name).mkdir(parents=True, exist_ok=True)
        return SimpleNamespace(returncode=0)

    def screenshot(display, target):
        screenshots.append(target)
        picture = Image.new("RGB", (320, 180), "black")
        if len(screenshots) > 1:
            draw = ImageDraw.Draw(picture)
            for x in range(0, 320, 16):
                draw.rectangle((x, 0, x + 8, 179), fill=(x % 170 + 50, 110, 220))
        picture.save(target)

    monkeypatch.setattr(smoke.lh, "require_linux", lambda: None)
    monkeypatch.setattr(smoke.lh, "child_env", lambda *args: {"DISPLAY": ":95"})
    monkeypatch.setattr(smoke.lh, "start_xvfb", lambda *args: SimpleNamespace(terminate=lambda: None))
    monkeypatch.setattr(smoke.lh, "copy_repo_images", lambda path: None)
    monkeypatch.setattr(smoke.lh, "seed_profile", lambda *args, **kwargs: profiles.append(kwargs["application"]))
    monkeypatch.setattr(smoke.lh, "grab_screen", screenshot)
    monkeypatch.setattr(smoke.subprocess, "run", install_or_probe)
    monkeypatch.setattr(smoke.subprocess, "Popen", FakeProcess)
    monkeypatch.setattr(smoke, "_xvfb_gl46_available", lambda env: (True, "OpenGL Core 4.6"))
    monkeypatch.setattr(smoke, "SHOT_SECONDS", (0, 0))
    monkeypatch.setattr(smoke.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(smoke.evidence_media, "redirect_output", lambda *args: out)
    monkeypatch.setattr(smoke.artifact_paths, "evidence_dir", lambda *args: out)
    monkeypatch.setattr(smoke.artifact_paths, "run_label", lambda *args: "test")

    assert smoke.main([str(product)]) == 0
    assert profiles == ["Screensaver_MC" if binary == "srpss-mc" else "Screensaver"]
    assert len(screenshots) >= 2
    assert any("/s" in proc.argv for proc in processes)
    assert any("/c" in proc.argv for proc in processes)
    assert not list(tmp_path.rglob("*.logging.cfg"))
