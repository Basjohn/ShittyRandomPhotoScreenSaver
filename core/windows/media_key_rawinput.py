"""Windows Raw Input API for global media key detection without blocking.

This module provides non-blocking media key detection using Windows Raw Input API.
Unlike RegisterHotKey, this does NOT consume/block keys - they continue to reach
Spotify and other apps. We only detect the press for visualizer wake.

Works with all Qt window types (Tool, Splash, Normal) and requires no focus.
"""

import ctypes
from ctypes import wintypes, Structure, c_ushort, c_ulong, POINTER
from typing import Callable, Optional, Set
import logging

logger = logging.getLogger(__name__)

# Windows constants
WM_INPUT = 0x00FF
RIDEV_INPUTSINK = 0x00000100  # Receive input even when not in foreground
RID_DEVICE_INFO = 0x20000000b
RIM_TYPEKEYBOARD = 1

# Media key VK codes
VK_MEDIA_PLAY_PAUSE = 0xB3
VK_MEDIA_NEXT_TRACK = 0xB0
VK_MEDIA_PREV_TRACK = 0xB1
VK_MEDIA_STOP = 0xB2


class RAWINPUTDEVICE(Structure):
    """Raw input device registration structure."""
    _fields_ = [
        ("usUsagePage", c_ushort),
        ("usUsage", c_ushort),
        ("dwFlags", c_ulong),
        ("hwndTarget", wintypes.HWND),
    ]


class RAWINPUTHEADER(Structure):
    """Raw input header structure."""
    _fields_ = [
        ("dwType", c_ulong),
        ("dwSize", c_ulong),
        ("hDevice", wintypes.HANDLE),
        ("wParam", wintypes.WPARAM),
    ]


class RAWKEYBOARD(Structure):
    """Raw keyboard input structure."""
    _fields_ = [
        ("MakeCode", c_ushort),
        ("Flags", c_ushort),
        ("Reserved", c_ushort),
        ("VKey", c_ushort),
        ("Message", c_ulong),
        ("ExtraInformation", c_ulong),
    ]


class RAWINPUT(Structure):
    """Raw input structure (union of keyboard/mouse/hid)."""
    class _U(Structure):
        class _K(Structure):
            _fields_ = [("keyboard", RAWKEYBOARD)]
        _fields_ = [("ki", _K)]
    
    _fields_ = [
        ("header", RAWINPUTHEADER),
        ("data", _U),
    ]


class MediaKeyRawInput:
    """Global media key detection using Raw Input API.
    
    This class registers for raw keyboard input and detects media key presses
    without blocking them from reaching other applications.
    """
    
    def __init__(self):
        self._user32 = ctypes.windll.user32
        self._kernel32 = ctypes.windll.kernel32
        self._callback: Optional[Callable[[str], None]] = None
        self._registered = False
        self._hwnd: Optional[int] = None
        
        # Track which media keys to detect
        self._media_vk_codes: Set[int] = {
            VK_MEDIA_PLAY_PAUSE,
            VK_MEDIA_NEXT_TRACK,
            VK_MEDIA_PREV_TRACK,
            VK_MEDIA_STOP,
        }
        
        # VK to command mapping
        self._vk_to_command = {
            VK_MEDIA_PLAY_PAUSE: "play",
            VK_MEDIA_NEXT_TRACK: "next",
            VK_MEDIA_PREV_TRACK: "prev",
            VK_MEDIA_STOP: "stop",
        }
    
    def register(self, hwnd: int, callback: Callable[[str], None]) -> bool:
        """Register for raw keyboard input.
        
        Args:
            hwnd: Window handle to receive WM_INPUT messages
            callback: Function called with command ('play', 'next', 'prev', 'stop')
            
        Returns:
            True if registration succeeded
        """
        if self._registered:
            return True
            
        self._hwnd = hwnd
        self._callback = callback
        
        try:
            # Register for raw keyboard input
            rid = RAWINPUTDEVICE()
            rid.usUsagePage = 0x01  # Generic Desktop
            rid.usUsage = 0x06      # Keyboard
            rid.dwFlags = RIDEV_INPUTSINK  # Receive even when not in foreground
            rid.hwndTarget = hwnd
            
            result = self._user32.RegisterRawInputDevices(
                ctypes.byref(rid),
                1,
                ctypes.sizeof(RAWINPUTDEVICE)
            )
            
            if result:
                self._registered = True
                logger.info("[RAW_INPUT] Media key detection registered")
                return True
            else:
                error = self._kernel32.GetLastError()
                logger.debug("[RAW_INPUT] Registration failed: error=%d", error)
                return False
                
        except Exception as e:
            logger.debug("[RAW_INPUT] Registration exception: %s", e)
            return False
    
    def unregister(self) -> None:
        """Unregister raw input."""
        if not self._registered or self._hwnd is None:
            return
            
        try:
            # Register with RIDEV_REMOVE flag to unregister
            rid = RAWINPUTDEVICE()
            rid.usUsagePage = 0x01
            rid.usUsage = 0x06
            rid.dwFlags = 0x00000001  # RIDEV_REMOVE
            rid.hwndTarget = None
            
            self._user32.RegisterRawInputDevices(
                ctypes.byref(rid),
                1,
                ctypes.sizeof(RAWINPUTDEVICE)
            )
            
            self._registered = False
            logger.info("[RAW_INPUT] Media key detection unregistered")
            
        except Exception as e:
            logger.debug("[RAW_INPUT] Unregistration exception: %s", e)
    
    def process_wm_input(self, wparam: int, lparam: int) -> bool:
        """Process WM_INPUT message.
        
        Args:
            wparam: wParam from WM_INPUT message
            lparam: lParam from WM_INPUT message (HRAWINPUT handle)
            
        Returns:
            True if a media key was detected and processed
        """
        if not self._registered or self._callback is None:
            return False
            
        try:
            # Get the raw input data size
            size = ctypes.c_uint(0)
            self._user32.GetRawInputData(
                ctypes.c_void_p(lparam),
                0x10000003,  # RID_INPUT
                None,
                ctypes.byref(size),
                ctypes.sizeof(RAWINPUTHEADER)
            )
            
            if size.value == 0:
                return False
            
            # Allocate buffer and get the data
            buffer = ctypes.create_string_buffer(size.value)
            result = self._user32.GetRawInputData(
                ctypes.c_void_p(lparam),
                0x10000003,  # RID_INPUT
                buffer,
                ctypes.byref(size),
                ctypes.sizeof(RAWINPUTHEADER)
            )
            
            if result == -1 or result == 0xFFFFFFFF:
                return False
            
            # Parse the raw input structure
            raw = ctypes.cast(buffer, POINTER(RAWINPUT)).contents
            
            # Check if it's keyboard input
            if raw.header.dwType != RIM_TYPEKEYBOARD:
                return False
            
            # Get VK code
            vk = raw.data.ki.keyboard.VKey
            
            # Check if it's a media key we're interested in
            if vk not in self._media_vk_codes:
                return False
            
            # Get the command
            command = self._vk_to_command.get(vk)
            if command is None:
                return False
            
            # Call the callback
            logger.debug("[RAW_INPUT] Media key detected: vk=0x%02X command=%s", vk, command)
            self._callback(command)
            return True
            
        except Exception as e:
            logger.debug("[RAW_INPUT] Process WM_INPUT exception: %s", e)
            return False
    
    def is_registered(self) -> bool:
        """Check if raw input is registered."""
        return self._registered


# Singleton instance
_raw_input_instance: Optional[MediaKeyRawInput] = None


def get_raw_input_instance() -> MediaKeyRawInput:
    """Get or create the singleton MediaKeyRawInput instance."""
    global _raw_input_instance
    if _raw_input_instance is None:
        _raw_input_instance = MediaKeyRawInput()
    return _raw_input_instance
