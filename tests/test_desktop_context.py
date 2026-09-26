"""Desktop identity is a fail-closed D1 boundary and needs no visible Qt surface."""
from __future__ import annotations

from core.windows.desktop_context import is_interactive_user_desktop


class FakeWin32:
    def __init__(self, desktop_name: str | None, *, raises: bool = False) -> None:
        self.desktop_name = desktop_name
        self.raises = raises
        self.calls = 0

    def current_thread_desktop_name(self) -> str | None:
        self.calls += 1
        if self.raises:
            raise OSError("desktop unavailable")
        return self.desktop_name


def test_default_desktop_is_interactive() -> None:
    api = FakeWin32("Default")
    assert is_interactive_user_desktop(api) is True
    assert api.calls == 1


def test_non_default_unknown_and_failed_desktop_checks_are_denied() -> None:
    assert is_interactive_user_desktop(FakeWin32("Winlogon")) is False
    assert is_interactive_user_desktop(FakeWin32(None)) is False
    assert is_interactive_user_desktop(FakeWin32("Default", raises=True)) is False


def test_native_adapter_uses_kernel_thread_id_and_user_desktop_api(monkeypatch):
    import ctypes
    from types import SimpleNamespace
    from core.windows import desktop_context as module

    class Function:
        def __init__(self, call): self.call = call
        def __call__(self, *args): return self.call(*args)
    def information(handle, kind, buffer, size, needed):
        assert handle == 77 and kind == 2
        if buffer is None:
            needed._obj.value = 8 * ctypes.sizeof(ctypes.c_wchar)
            return False
        buffer.value = "Default"
        return True
    kernel = SimpleNamespace(GetCurrentThreadId=Function(lambda: 42))
    user = SimpleNamespace(GetThreadDesktop=Function(lambda tid: 77 if tid == 42 else 0),
                           GetUserObjectInformationW=Function(information))
    monkeypatch.setattr(ctypes, "WinDLL", lambda name, **kwargs: {"kernel32":kernel,"user32":user}[name])
    assert is_interactive_user_desktop() is True
