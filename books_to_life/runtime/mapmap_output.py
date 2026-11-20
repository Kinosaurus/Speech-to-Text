"""Read the fullscreen output canvas of the local Windows MapMap process."""

import ctypes
from ctypes import wintypes as win
import sys


class MonitorInfo(ctypes.Structure):
    _fields_ = [('size', win.DWORD), ('bounds', win.RECT), ('work', win.RECT), ('flags', win.DWORD)]


def detect_output_size(process_id):
    if sys.platform != 'win32' or process_id is None:
        return None

    def bind(name, result, *arguments):
        function = getattr(user32, name)
        function.restype = result
        function.argtypes = arguments
        return function

    try:
        user32 = ctypes.WinDLL('user32', use_last_error=True)
        callback_type = ctypes.WINFUNCTYPE(win.BOOL, win.HWND, win.LPARAM)
        enum_windows = bind('EnumWindows', win.BOOL, callback_type, win.LPARAM)
        window_process = bind('GetWindowThreadProcessId', win.DWORD, win.HWND, ctypes.POINTER(win.DWORD))
        visible = bind('IsWindowVisible', win.BOOL, win.HWND)
        minimized = bind('IsIconic', win.BOOL, win.HWND)
        window_text = bind('GetWindowTextW', win.INT, win.HWND, win.LPWSTR, win.INT)
        window_rect = bind('GetWindowRect', win.BOOL, win.HWND, ctypes.POINTER(win.RECT))
        window_monitor = bind('MonitorFromWindow', win.HANDLE, win.HWND, win.DWORD)
        monitor_info = bind('GetMonitorInfoW', win.BOOL, win.HANDLE, ctypes.POINTER(MonitorInfo))
        window_dpi = bind('GetDpiForWindow', win.UINT, win.HWND)
        dpi_context = bind('SetThreadDpiAwarenessContext', win.HANDLE, win.HANDLE)
        # Per-monitor aware coordinates give physical bounds on either display.
        previous_context = dpi_context(ctypes.c_void_p(-4))
    except (AttributeError, OSError):
        return None
    if not previous_context:
        return None

    outputs = []

    @callback_type
    def inspect(window, _):
        owner = win.DWORD()
        window_process(window, ctypes.byref(owner))
        if owner.value != process_id or not visible(window) or minimized(window):
            return True
        title = ctypes.create_unicode_buffer(128)
        window_text(window, title, len(title))
        # The fullscreen dialog is titled MapMap. The editor includes the project name.
        if title.value != 'MapMap':
            return True
        monitor = window_monitor(window, 0)
        bounds = win.RECT()
        info = MonitorInfo(size=ctypes.sizeof(MonitorInfo))
        if not monitor or not window_rect(window, ctypes.byref(bounds)) or not monitor_info(monitor, ctypes.byref(info)):
            return True
        if bytes(bounds) != bytes(info.bounds):
            return True
        dpi = window_dpi(window)
        if dpi:
            # MapMap's Qt output scene uses device-independent coordinates.
            dimensions = (bounds.right - bounds.left, bounds.bottom - bounds.top)
            outputs.append(tuple((pixels * 96 + dpi // 2) // dpi for pixels in dimensions))
        return True

    try:
        succeeded = enum_windows(inspect, 0)
    finally:
        dpi_context(previous_context)
    return outputs[0] if succeeded and len(outputs) == 1 else None
