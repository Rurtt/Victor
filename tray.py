"""Dependency-free Windows tray. Callbacks run on its message thread, never Tk.

The caller must marshal events onto the UI thread. Acquire the instance guard
only in the application entry point, and release it on final application exit.
"""
from __future__ import annotations

import ctypes as C
from ctypes import wintypes as W
import logging
import os
import threading
import time

_LOG = logging.getLogger(__name__)
_CLASS = "JarvisDesktopTrayWindow.v1"
_MUTEX = "Local\\JarvisDesktop.Instance.v1"
_OPEN_MESSAGE = "JarvisDesktop.ShowWindow.v1"
_WM_TRAY, _WM_STOP, _WM_WAKE = 0x8001, 0x8002, 0x8003
_WNDPROC = getattr(C, "WINFUNCTYPE", C.CFUNCTYPE)(C.c_ssize_t, W.HWND, W.UINT, C.c_size_t, C.c_ssize_t)


class _WindowClass(C.Structure):
    _fields_ = [("cbSize", W.UINT), ("style", W.UINT), ("lpfnWndProc", _WNDPROC),
                ("cbClsExtra", C.c_int), ("cbWndExtra", C.c_int),
                ("hInstance", W.HINSTANCE), ("hIcon", W.HICON),
                ("hCursor", W.HANDLE), ("hbrBackground", W.HBRUSH),
                ("lpszMenuName", W.LPCWSTR), ("lpszClassName", W.LPCWSTR),
                ("hIconSm", W.HICON)]


class _NotifyIcon(C.Structure):
    _fields_ = [("cbSize", W.DWORD), ("hWnd", W.HWND), ("uID", W.UINT),
                ("uFlags", W.UINT), ("uCallbackMessage", W.UINT),
                ("hIcon", W.HICON), ("szTip", W.WCHAR * 128),
                ("dwState", W.DWORD), ("dwStateMask", W.DWORD),
                ("szInfo", W.WCHAR * 256), ("uTimeout", W.UINT),
                ("szInfoTitle", W.WCHAR * 64), ("dwInfoFlags", W.DWORD),
                ("guidItem", C.c_byte * 16), ("hBalloonIcon", W.HICON)]


class _WindowsAPI:
    """Declare every ABI explicitly; defaults truncate handles on 64-bit Windows."""
    def __init__(self):
        if os.name != "nt":
            raise RuntimeError("The Jarvis tray requires Windows.")
        self.user = C.WinDLL("user32", use_last_error=True)
        self.shell = C.WinDLL("shell32", use_last_error=True)
        self.kernel = C.WinDLL("kernel32", use_last_error=True)
        declarations = {
            "RegisterClassExW": (W.ATOM, [C.POINTER(_WindowClass)]),
            "UnregisterClassW": (W.BOOL, [W.LPCWSTR, W.HINSTANCE]),
            "CreateWindowExW": (W.HWND, [W.DWORD, W.LPCWSTR, W.LPCWSTR, W.DWORD,
                C.c_int, C.c_int, C.c_int, C.c_int, W.HWND, W.HMENU, W.HINSTANCE, W.LPVOID]),
            "DestroyWindow": (W.BOOL, [W.HWND]),
            "DefWindowProcW": (C.c_ssize_t, [W.HWND, W.UINT, C.c_size_t, C.c_ssize_t]),
            "RegisterWindowMessageW": (W.UINT, [W.LPCWSTR]),
            "PostMessageW": (W.BOOL, [W.HWND, W.UINT, C.c_size_t, C.c_ssize_t]),
            "PostQuitMessage": (None, [C.c_int]),
            "GetMessageW": (C.c_int, [C.POINTER(W.MSG), W.HWND, W.UINT, W.UINT]),
            "TranslateMessage": (W.BOOL, [C.POINTER(W.MSG)]),
            "DispatchMessageW": (C.c_ssize_t, [C.POINTER(W.MSG)]),
            "LoadImageW": (W.HANDLE, [W.HINSTANCE, W.LPCWSTR, W.UINT, C.c_int, C.c_int, W.UINT]),
            "LoadIconW": (W.HICON, [W.HINSTANCE, C.c_void_p]),
            "DestroyIcon": (W.BOOL, [W.HICON]),
            "CreatePopupMenu": (W.HMENU, []),
            "AppendMenuW": (W.BOOL, [W.HMENU, W.UINT, C.c_size_t, W.LPCWSTR]),
            "TrackPopupMenu": (W.UINT, [W.HMENU, W.UINT, C.c_int, C.c_int,
                                      C.c_int, W.HWND, C.POINTER(W.RECT)]),
            "DestroyMenu": (W.BOOL, [W.HMENU]),
            "GetCursorPos": (W.BOOL, [C.POINTER(W.POINT)]),
            "SetForegroundWindow": (W.BOOL, [W.HWND]),
            "FindWindowW": (W.HWND, [W.LPCWSTR, W.LPCWSTR]),
        }
        for name, (result, args) in declarations.items():
            fn = getattr(self.user, name)
            fn.restype, fn.argtypes = result, args
        self.shell.Shell_NotifyIconW.restype = W.BOOL
        self.shell.Shell_NotifyIconW.argtypes = [W.DWORD, C.POINTER(_NotifyIcon)]
        for name, result, args in [
            ("GetModuleHandleW", W.HMODULE, [W.LPCWSTR]),
            ("CreateMutexW", W.HANDLE, [W.LPVOID, W.BOOL, W.LPCWSTR]),
            ("CloseHandle", W.BOOL, [W.HANDLE]),
        ]:
            fn = getattr(self.kernel, name)
            fn.restype, fn.argtypes = result, args


def _failure(operation):
    return RuntimeError(f"{operation} failed (Windows error {C.get_last_error()}).")


_instance_lock = threading.Lock()
_instance_handle = None
_instance_api = None


def acquire_instance() -> bool:
    """Keep a named mutex alive; a duplicate signals the first tray and returns False."""
    global _instance_handle, _instance_api
    with _instance_lock:
        if _instance_handle:
            return True
        api = _WindowsAPI()
        handle = api.kernel.CreateMutexW(None, False, _MUTEX)
        error = C.get_last_error()  # Capture immediately, before any other Win32 call.
        if not handle:
            raise _failure("Creating the Jarvis instance guard")
        if error == 183:  # ERROR_ALREADY_EXISTS
            api.kernel.CloseHandle(handle)
            message = api.user.RegisterWindowMessageW(_OPEN_MESSAGE)
            deadline = time.monotonic() + 2.0
            while message:
                hwnd = api.user.FindWindowW(_CLASS, None)
                if hwnd:
                    api.user.PostMessageW(hwnd, message, 0, 0)
                    break
                if time.monotonic() >= deadline:
                    # Hidden top-level windows also receive registered broadcasts.
                    api.user.PostMessageW(0xFFFF, message, 0, 0)
                    break
                time.sleep(0.05)
            return False
        _instance_handle, _instance_api = handle, api
        return True


def release_instance() -> None:
    global _instance_handle, _instance_api
    with _instance_lock:
        if _instance_handle:
            _instance_api.kernel.CloseHandle(_instance_handle)
            _instance_handle, _instance_api = None, None


class Tray:
    def __init__(self, icon_path, callback):
        self.icon_path = os.fspath(icon_path) if icon_path else ""
        self.callback = callback
        self._wake = False
        self._thread = None
        self._ready = threading.Event()
        self._stopping = threading.Event()
        self._start_lock = threading.Lock()
        self._error = None
        self._api = None
        self._hwnd = None
        self._icon = None
        self._owned_icon = False
        self._installed = False
        self._wndproc = None  # Strong reference until the window is destroyed.
        self._taskbar_message = self._open_message = 0

    @property
    def running(self) -> bool:
        return bool(self._installed and self._thread and self._thread.is_alive())

    def start(self) -> bool:
        """Return only after icon creation; raise clearly on failure (max ~3.5 s)."""
        with self._start_lock:
            if self._thread and self._thread.is_alive():
                if self.running:
                    return True
                raise RuntimeError("The Jarvis tray thread is still starting or stopping.")
            self._ready.clear()
            self._stopping.clear()
            self._error = None
            self._thread = threading.Thread(target=self._run, name="JarvisTray", daemon=True)
            self._thread.start()
            if not self._ready.wait(3.0):
                self.stop(timeout=0.5)
                raise RuntimeError("The Jarvis tray did not start within 3 seconds.")
            if self._error:
                self.stop(timeout=0.5)
                raise RuntimeError(f"Could not create the Jarvis tray: {self._error}") from self._error
            return self.running

    def stop(self, timeout=2.0) -> None:
        """Request cleanup on the message thread; safe to repeat or call from callback."""
        self._stopping.set()
        if self._hwnd and self._api:
            self._api.user.PostMessageW(self._hwnd, _WM_STOP, 0, 0)
        thread = self._thread
        if thread and thread is not threading.current_thread():
            thread.join(max(0.0, min(float(timeout), 2.0)))

    def set_wake(self, enabled: bool) -> None:
        self._wake = bool(enabled)
        if self._hwnd and self._api:
            self._api.user.PostMessageW(self._hwnd, _WM_WAKE, 0, 0)

    def _notify(self, operation):
        info = _NotifyIcon()
        info.cbSize = C.sizeof(info)
        info.hWnd, info.uID = self._hwnd, 1
        info.uFlags = 1 | 2 | 4  # NIF_MESSAGE | NIF_ICON | NIF_TIP
        info.uCallbackMessage, info.hIcon = _WM_TRAY, self._icon
        info.szTip = "Jarvis - wake " + ("on" if self._wake else "off")
        return bool(self._api.shell.Shell_NotifyIconW(operation, C.byref(info)))

    def _emit(self, event):
        try:
            self.callback(event)
        except Exception:
            _LOG.exception("Jarvis tray callback failed: %s", event)

    def _menu(self):
        user = self._api.user
        menu = user.CreatePopupMenu()
        if not menu:
            return
        try:
            labels = ["Open", "Listen once", "Wake " + ("on" if self._wake else "off"),
                      "Stop / mute", "Exit"]
            for number, label in enumerate(labels, 1):
                if not user.AppendMenuW(menu, 8 if number == 3 and self._wake else 0, number, label):
                    return
            point = W.POINT()
            if not user.GetCursorPos(C.byref(point)):
                return
            user.SetForegroundWindow(self._hwnd)
            command = user.TrackPopupMenu(menu, 0x100 | 0x2, point.x, point.y, 0, self._hwnd, None)
            user.PostMessageW(self._hwnd, 0, 0, 0)  # Standard tray-menu dismissal fix.
            if 1 <= command <= 5:
                self._emit(("open", "listen", "wake", "stop", "exit")[command - 1])
        finally:
            user.DestroyMenu(menu)

    def _window_proc(self, hwnd, message, wparam, lparam):
        # Exceptions must never escape a ctypes callback into the native stack.
        try:
            if message == _WM_TRAY:
                if lparam == 0x203:  # WM_LBUTTONDBLCLK
                    self._emit("open")
                elif lparam in (0x205, 0x7B):  # WM_RBUTTONUP / WM_CONTEXTMENU
                    self._menu()
                return 0
            if self._open_message and message == self._open_message:
                self._emit("open")
                return 0
            if self._taskbar_message and message == self._taskbar_message:
                self._installed = self._notify(0)  # NIM_ADD after Explorer restart.
                if not self._installed:
                    _LOG.error("Could not restore Jarvis tray after Explorer restart")
                    self._emit("open")  # Keep the app reachable if recreation fails.
                return 0
            if message == _WM_WAKE:
                self._notify(1)
                return 0
            if message in (_WM_STOP, 0x10):  # WM_CLOSE
                self._stopping.set()
                self._api.user.PostQuitMessage(0)
                return 0
            if message == 2:  # WM_DESTROY
                self._api.user.PostQuitMessage(0)
                return 0
        except Exception:
            _LOG.exception("Jarvis tray window event failed")
            return 0
        return self._api.user.DefWindowProcW(hwnd, message, wparam, lparam)

    def _run(self):
        atom = module = None
        try:
            self._api = _WindowsAPI()
            user = self._api.user
            module = self._api.kernel.GetModuleHandleW(None)
            self._taskbar_message = user.RegisterWindowMessageW("TaskbarCreated")
            self._open_message = user.RegisterWindowMessageW(_OPEN_MESSAGE)
            if not module or not self._taskbar_message or not self._open_message:
                raise _failure("Registering tray messages")
            self._wndproc = _WNDPROC(self._window_proc)
            window_class = _WindowClass()
            window_class.cbSize = C.sizeof(window_class)
            window_class.style = 8  # CS_DBLCLKS
            window_class.lpfnWndProc = self._wndproc
            window_class.hInstance, window_class.lpszClassName = module, _CLASS
            atom = user.RegisterClassExW(C.byref(window_class))
            if not atom:
                raise _failure("Registering tray window")
            # A hidden top-level window receives TaskbarCreated; HWND_MESSAGE does not.
            self._hwnd = user.CreateWindowExW(0, _CLASS, "Jarvis", 0, 0, 0, 0, 0,
                                            None, None, module, None)
            if not self._hwnd:
                raise _failure("Creating tray window")
            if self._stopping.is_set():
                return
            if self.icon_path:
                self._icon = user.LoadImageW(None, self.icon_path, 1, 0, 0, 0x10 | 0x40)
                self._owned_icon = bool(self._icon)
            if not self._icon:
                self._icon = user.LoadIconW(None, C.c_void_p(32512))
            if not self._icon:
                raise _failure("Loading tray icon")
            self._installed = self._notify(0)
            if not self._installed:
                raise _failure("Adding tray icon")
            self._ready.set()
            message = W.MSG()
            while not self._stopping.is_set():
                result = user.GetMessageW(C.byref(message), None, 0, 0)
                if result == -1:
                    raise _failure("Reading tray messages")
                if result == 0:
                    break
                user.TranslateMessage(C.byref(message))
                user.DispatchMessageW(C.byref(message))
        except Exception as exc:
            self._error = exc
            if self._ready.is_set():
                _LOG.exception("Jarvis tray stopped unexpectedly")
                self._emit("open")
        finally:
            if self._api:
                if self._installed:
                    self._notify(2)  # NIM_DELETE
                self._installed = False
                if self._hwnd:
                    self._api.user.DestroyWindow(self._hwnd)
                self._hwnd = None
                if self._icon and self._owned_icon:
                    self._api.user.DestroyIcon(self._icon)
                self._icon, self._owned_icon = None, False
                if atom:
                    self._api.user.UnregisterClassW(_CLASS, module)
            self._wndproc = None
            self._ready.set()
