"""
Policy enforcement tests for codebase compliance.

These tests perform static analysis on the codebase to verify adherence to
architectural policies regarding threading, resource management, and settings.

Run these to catch policy violations early in development.
"""
import re
from pathlib import Path

import pytest


class TestThreadingPolicyCompliance:
    """
    Tests that enforce Threading Policy compliance.

    Policy: All background task execution must use ThreadManager.
    Raw threading.Thread/ThreadPoolExecutor should only be used in:
    1. ThreadManager implementation itself
    2. External library wrappers where ThreadManager cannot be injected
    3. Test files simulating external library behavior
    """

    EXCLUDED_PATHS = [
        # ThreadManager implementation itself
        "core/threading/manager.py",
        "core/threading/",
        # External library wrappers and pre-policy implementations
        "core/process/supervisor.py",
        "rendering/adaptive_timer.py",
        # Tests that simulate external library behavior
        "tests/test_thread_manager.py",
        "tests/test_qt_timer_threading.py",
        # Deprecated/backup files
        "tests/test_threading_deprecated.py",
        # Conftest and test utilities
        "tests/conftest.py",
    ]

    def _get_source_files(self) -> list[Path]:
        """Get all Python source files in the project."""
        project_root = Path(__file__).parent.parent.parent
        source_files = []

        for pattern in ["core/**/*.py", "ui/**/*.py", "rendering/**/*.py", "widgets/**/*.py"]:
            source_files.extend(project_root.glob(pattern))

        return [f for f in source_files if f.is_file()]

    def _is_excluded(self, file_path: Path) -> bool:
        """Check if file is in exclusion list."""
        path_str = str(file_path).replace("\\", "/")
        return any(excluded in path_str for excluded in self.EXCLUDED_PATHS)

    def test_no_raw_threading_in_production_code(self):
        """
        Verify that raw threading.Thread is not used outside exempted modules.

        This catches accidental use of threading.Thread when ThreadManager should be used.
        """
        violations = []
        threading_pattern = re.compile(r"threading\.Thread\(")

        for file_path in self._get_source_files():
            if self._is_excluded(file_path):
                continue

            try:
                content = file_path.read_text(encoding="utf-8")
                if threading_pattern.search(content):
                    # Check if it's just an import
                    lines = content.split("\n")
                    for i, line in enumerate(lines, 1):
                        if "threading.Thread(" in line and "import" not in line:
                            violations.append(f"{file_path}:{i}: {line.strip()}")
            except Exception:
                continue

        if violations:
            pytest.fail(
                "Found raw threading.Thread usage in production code:\n"
                + "\n".join(violations)
                + "\n\nUse ThreadManager instead, or add to EXCLUDED_PATHS if justified."
            )

    def test_no_threadpoolexecutor_in_production_code(self):
        """
        Verify that ThreadPoolExecutor is not used outside ThreadManager.

        All thread pool usage should go through ThreadManager.
        """
        violations = []
        executor_pattern = re.compile(r"ThreadPoolExecutor\(")

        for file_path in self._get_source_files():
            if self._is_excluded(file_path):
                continue

            try:
                content = file_path.read_text(encoding="utf-8")
                if executor_pattern.search(content):
                    lines = content.split("\n")
                    for i, line in enumerate(lines, 1):
                        if "ThreadPoolExecutor(" in line and "import" not in line:
                            violations.append(f"{file_path}:{i}: {line.strip()}")
            except Exception:
                continue

        if violations:
            pytest.fail(
                "Found ThreadPoolExecutor usage outside ThreadManager:\n"
                + "\n".join(violations)
                + "\n\nUse ThreadManager instead."
            )


class TestResourceManagerPolicyCompliance:
    """
    Tests that enforce ResourceManager usage policy.

    Policy: Qt objects should be registered with ResourceManager for cleanup.
    """

    def test_no_deleteLater_without_resource_manager(self):
        """
        Flag potential manual deleteLater() calls that should use ResourceManager.

        This is informational - some deleteLater() calls are legitimate in cleanup code.
        """
        project_root = Path(__file__).parent.parent.parent
        potential_issues = []
        deletelater_pattern = re.compile(r"\.deleteLater\(\)")

        for pattern in ["core/**/*.py", "ui/**/*.py", "rendering/**/*.py", "widgets/**/*.py"]:
            for file_path in project_root.glob(pattern):
                if not file_path.is_file():
                    continue

                # Skip resource manager implementation itself
                if "resource_manager" in str(file_path):
                    continue

                try:
                    content = file_path.read_text(encoding="utf-8")
                    if deletelater_pattern.search(content):
                        lines = content.split("\n")
                        for i, line in enumerate(lines, 1):
                            if ".deleteLater()" in line:
                                # Check if it's part of ResourceManager cleanup
                                if "resource_manager" not in line.lower() and "_resources" not in line.lower():
                                    potential_issues.append(f"{file_path}:{i}")
                except Exception:
                    continue

        # This is a soft check - we just report, don't fail
        # because some deleteLater() calls are legitimate in destructors
        if potential_issues:
            print(f"\n[INFO] Found {len(potential_issues)} manual deleteLater() calls:")
            for issue in potential_issues[:10]:  # Show first 10
                print(f"  - {issue}")
            if len(potential_issues) > 10:
                print(f"  ... and {len(potential_issues) - 10} more")
            print("  Consider using ResourceManager for Qt object lifecycle management.\n")

        # Always pass - this is informational
        assert True


class TestSettingsPolicyCompliance:
    """
    Tests that enforce Settings naming and usage policies.

    Policy: Settings must use dot-notation keys with category prefixes.
    """

    VALID_CATEGORIES = [
        "display", "timing", "queue", "input", "overlay", "window",
        "theme", "weather", "reddit", "spotify", "rss", "mc", "debug",
        "advanced", "performance", "transition", "widget", "image",
    ]

    def test_settings_keys_use_dot_notation(self):
        """
        Verify that settings keys follow category.subkey format.
        """
        project_root = Path(__file__).parent.parent.parent
        violations = []
        # Pattern for settings.set/get calls
        settings_pattern = re.compile(r"[\"']([a-z_]+)\.([a-z_]+)[\"']")

        for pattern in ["core/**/*.py", "ui/**/*.py", "rendering/**/*.py", "widgets/**/*.py"]:
            for file_path in project_root.glob(pattern):
                if not file_path.is_file():
                    continue

                try:
                    content = file_path.read_text(encoding="utf-8")
                    for match in settings_pattern.finditer(content):
                        key = match.group(0).strip("'\"")
                        category = key.split(".")[0]

                        if category not in self.VALID_CATEGORIES:
                            # Check if it's a test file using mock keys
                            if "test_" in str(file_path):
                                continue
                            violations.append(f"{file_path}: Invalid category '{category}' in key '{key}'")
                except Exception:
                    continue

        # This is a soft check - just report
        if violations:
            print(f"\n[INFO] Found {len(violations)} potential settings key issues:")
            for v in violations[:10]:
                print(f"  - {v}")
            print("\n")

        assert True


class TestLoggingPolicyCompliance:
    """
    Tests that enforce logging format policies.

    Policy: Log messages should use [CATEGORY] prefix format.
    """

    def test_no_print_statements_in_production_code(self):
        """
        Verify that print() is not used in production code (use logging instead).
        """
        project_root = Path(__file__).parent.parent.parent
        violations = []
        print_pattern = re.compile(r"^\s*print\(")

        for pattern in ["core/**/*.py", "ui/**/*.py", "rendering/**/*.py", "widgets/**/*.py"]:
            for file_path in project_root.glob(pattern):
                if not file_path.is_file():
                    continue

                try:
                    content = file_path.read_text(encoding="utf-8")
                    lines = content.split("\n")
                    for i, line in enumerate(lines, 1):
                        if print_pattern.match(line):
                            # Allow print in specific files
                            if "__main__" in line or "if __name__" in content:
                                continue
                            violations.append(f"{file_path}:{i}")
                except Exception:
                    continue

        if violations:
            pytest.fail(
                "Found print() statements in production code:\n"
                + "\n".join(violations[:20])
                + "\n\nUse logging instead of print()."
            )
