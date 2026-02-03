"""
Low-level keyboard hook for media key passthrough.

Uses WH_KEYBOARD_LL to detect media keys and pass them through to the OS.
This bypasses Winlogon desktop isolation that blocks WM_APPCOMMAND.

The hook is optional (controlled by settings) and defaults to disabled.
When disabled, there is zero performance impact (no hook installed).
"""
from __future__ import annotations

import ctypes
import threading
import time
from ctypes import wintypes
from typing import Optional

from PySide6.QtCore import QObject, Signal

from core.logging.logger import get_logger

logger = get_logger(__name__)

# Windows constants
WH_KEYBOARD_LL = 13
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
WM_SYSKEYDOWN = 0x0104
WM_SYSKEYUP = 0x0105
PM_REMOVE = 0x0001

# Media key virtual key codes
VK_VOLUME_MUTE = 0xAD
VK_VOLUME_DOWN = 0xAE
VK_VOLUME_UP = 0xAF
VK_MEDIA_NEXT_TRACK = 0xB0
VK_MEDIA_PREV_TRACK = 0xB1
VK_MEDIA_STOP = 0xB2
VK_MEDIA_PLAY_PAUSE = 0xB3

MEDIA_KEY_CODES = {
    VK_VOLUME_MUTE,
    VK_VOLUME_DOWN,
    VK_VOLUME_UP,
    VK_MEDIA_NEXT_TRACK,
    VK_MEDIA_PREV_TRACK,
    VK_MEDIA_STOP,
    VK_MEDIA_PLAY_PAUSE,
}


class KBDLLHOOKSTRUCT(ctypes.Structure):
    """Low-level keyboard hook structure."""
    _fields_ = [
        ("vkCode", wintypes.DWORD),
        ("scanCode", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(wintypes.ULONG)),
    ]


class MSG(ctypes.Structure):
    """Windows message structure."""
    _fields_ = [
        ("hwnd", wintypes.HWND),
        ("message", wintypes.UINT),
        ("wParam", wintypes.WPARAM),
        ("lParam", wintypes.LPARAM),
        ("time", wintypes.DWORD),
        ("pt", wintypes.POINT),
    ]


class MediaKeyLLHook(QObject):
    """
    Low-level keyboard hook for media key detection.
    
    Detects media keys (play/pause, volume, next/prev) and signals them
    while passing them through to the OS (CallNextHookEx always called).
    
    Thread-safe: Uses atomic operations and signals for communication.
    
    Attributes:
        media_key_detected: Signal emitted when a media key is detected.
                           Arguments: (vk_code, key_name)
    """
    
    media_key_detected = Signal(int, str)
    
    # Key name mapping
    KEY_NAMES = {
        VK_VOLUME_MUTE: "mute",
        VK_VOLUME_DOWN: "volume_down",
        VK_VOLUME_UP: "volume_up",
        VK_MEDIA_NEXT_TRACK: "next",
        VK_MEDIA_PREV_TRACK: "prev",
        VK_MEDIA_STOP: "stop",
        VK_MEDIA_PLAY_PAUSE: "play_pause",
    }
    
    def __init__(self) -> None:
        super().__init__()
        self._hHook: Optional[int] = None
        self._hook_thread: Optional[threading.Thread] = None
        self._running = False
        self._lock = threading.Lock()
        
        # Load user32.dll
        self._user32 = ctypes.windll.user32
        self._kernel32 = ctypes.windll.kernel32
        
        # Set up function prototypes
        self._user32.SetWindowsHookExW.argtypes = [
            ctypes.c_int, wintypes.HANDLE, wintypes.HINSTANCE, wintypes.DWORD
        ]
        self._user32.SetWindowsHookExW.restype = wintypes.HANDLE
        
        # Note: CallNextHookEx argtypes not set to allow flexible testing
        # The function accepts any pointer type for lParam
        self._user32.CallNextHookEx.restype = ctypes.c_longlong
        
        self._user32.UnhookWindowsHookEx.argtypes = [wintypes.HANDLE]
        self._user32.UnhookWindowsHookEx.restype = wintypes.BOOL
        
        self._user32.PeekMessageW.argtypes = [
            ctypes.POINTER(MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT, wintypes.UINT
        ]
        self._user32.PeekMessageW.restype = wintypes.BOOL
        
        self._user32.TranslateMessage.argtypes = [ctypes.POINTER(MSG)]
        self._user32.TranslateMessage.restype = wintypes.BOOL
        
        self._user32.DispatchMessageW.argtypes = [ctypes.POINTER(MSG)]
        self._user32.DispatchMessageW.restype = ctypes.c_longlong
        
        # Keep reference to callback to prevent GC
        self._hook_proc = None
        
        logger.debug("[MEDIA_KEY_LL] Initialized")
    
    def start(self) -> bool:
        """
        Start the low-level keyboard hook.
        
        Returns:
            True if hook was installed successfully, False otherwise.
        """
        with self._lock:
            if self._running:
                logger.debug("[MEDIA_KEY_LL] Hook already running")
                return True
            
            try:
                # Create hook procedure
                self._hook_proc = ctypes.WINFUNCTYPE(
                    ctypes.c_longlong, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM
                )(self._hook_callback)
                
                # Install hook on this thread (will be moved to hook thread)
                # We need to install from the thread that will run the message pump
                self._running = True
                self._hook_thread = threading.Thread(
                    target=self._hook_thread_proc,
                    name="MediaKeyLLHook",
                    daemon=True
                )
                self._hook_thread.start()
                
                logger.info("[MEDIA_KEY_LL] Hook thread started")
                return True
                
            except Exception as e:
                logger.error("[MEDIA_KEY_LL] Failed to start hook: %s", e)
                self._running = False
                return False
    
    def stop(self) -> None:
        """Stop the hook and clean up resources."""
        with self._lock:
            if not self._running:
                return
            
            logger.debug("[MEDIA_KEY_LL] Stopping hook")
            self._running = False
            
            # Wait for thread to finish
            if self._hook_thread and self._hook_thread.is_alive():
                self._hook_thread.join(timeout=2.0)
            
            # Unhook if still installed
            if self._hHook:
                try:
                    self._user32.UnhookWindowsHookEx(self._hHook)
                    logger.debug("[MEDIA_KEY_LL] Hook uninstalled")
                except Exception as e:
                    logger.debug("[MEDIA_KEY_LL] Error unhooking: %s", e)
                finally:
                    self._hHook = None
            
            self._hook_thread = None
            self._hook_proc = None
            logger.info("[MEDIA_KEY_LL] Hook stopped")
    
    def _hook_thread_proc(self) -> None:
        """Hook thread procedure - runs message pump."""
        try:
            # Get module handle
            hMod = self._kernel32.GetModuleHandleW(None)
            
            # Install hook
            self._hHook = self._user32.SetWindowsHookExW(
                WH_KEYBOARD_LL,
                self._hook_proc,
                hMod,
                0  # All threads
            )
            
            if not self._hHook:
                logger.error("[MEDIA_KEY_LL] Failed to install hook")
                self._running = False
                return
            
            logger.info("[MEDIA_KEY_LL] Hook installed successfully")
            
            # Message pump
            msg = MSG()
            while self._running:
                # Non-blocking message check
                if self._user32.PeekMessageW(
                    ctypes.byref(msg), 0, 0, 0, PM_REMOVE
                ):
                    self._user32.TranslateMessage(ctypes.byref(msg))
                    self._user32.DispatchMessageW(ctypes.byref(msg))
                else:
                    # Yield to avoid busy-wait
                    time.sleep(0.001)
                    
        except Exception as e:
            logger.error("[MEDIA_KEY_LL] Hook thread error: %s", e)
        finally:
            # Cleanup
            if self._hHook:
                try:
                    self._user32.UnhookWindowsHookEx(self._hHook)
                except Exception:
                    pass
                self._hHook = None
            self._running = False
    
    def _hook_callback(self, nCode: int, wParam: wintypes.WPARAM, 
                       lParam) -> ctypes.c_longlong:
        """
        Low-level keyboard hook callback.
        
        Called for every keystroke in the system. Must be fast and non-blocking.
        Always calls CallNextHookEx to pass through to next hook/OS.
        """
        if nCode == 0:  # HC_ACTION
            try:
                # Extract keyboard data - handle both real Windows calls and test mocks
                if hasattr(lParam, 'vkCode'):
                    # Test mock object
                    vk_code = lParam.vkCode
                else:
                    # Real Windows LPARAM (pointer to KBDLLHOOKSTRUCT)
                    kbd = ctypes.cast(lParam, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
                    vk_code = kbd.vkCode
                
                # Check if it's a media key
                if vk_code in MEDIA_KEY_CODES:
                    # Get key name
                    key_name = self.KEY_NAMES.get(vk_code, f"vk_{vk_code:02X}")
                    
                    # Log for debugging
                    logger.debug("[MEDIA_KEY_LL] Detected: %s (0x%02X)", key_name, vk_code)
                    
                    # Emit signal (thread-safe via Qt's queued connections)
                    try:
                        self.media_key_detected.emit(vk_code, key_name)
                    except Exception as e:
                        logger.debug("[MEDIA_KEY_LL] Signal emit error: %s", e)
                        
            except Exception as e:
                logger.debug("[MEDIA_KEY_LL] Callback error: %s", e)
        
        # ALWAYS pass through to next hook/OS
        # This is critical for anti-cheat safety
        # Handle test mocks (when hHook is None) vs real Windows calls
        if self._hHook:
            return self._user32.CallNextHookEx(self._hHook, nCode, wParam, lParam)
        else:
            # In tests, hHook is None, just return 0
            return 0
    
    def is_running(self) -> bool:
        """Check if the hook is currently running."""
        with self._lock:
            return self._running and self._hHook is not None
