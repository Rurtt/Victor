"""Screenshots and mouse/keyboard input. Runs only steps the user approved."""
from __future__ import annotations

import ctypes
from ctypes import wintypes
import io
import time

from actions import PolicyError

KINDS = ("click", "double_click", "right_click", "type", "scroll", "key", "done")
KEYS = {"enter": (0x0D,), "tab": (0x09,), "escape": (0x1B,), "backspace": (0x08,),
        "up": (0x26,), "down": (0x28,), "left": (0x25,), "right": (0x27,),
        "page_up": (0x21,), "page_down": (0x22,), "ctrl+a": (0x11, 0x41), "ctrl+c": (0x11, 0x43),
        "ctrl+v": (0x11, 0x56), "ctrl+l": (0x11, 0x4C), "ctrl+t": (0x11, 0x54),
        "ctrl+w": (0x11, 0x57), "alt+tab": (0x12, 0x09)}
MAX_WIDTH = 1280


def validate_step(step) -> dict:
    """Model output is untrusted: keep only the fields this kind needs."""
    if not isinstance(step, dict) or step.get("kind") not in KINDS:
        raise PolicyError("Unknown screen step.")
    kind, label = step["kind"], step.get("label", "")
    if not isinstance(label, str):
        raise PolicyError("Invalid step label.")
    clean = {"kind": kind, "label": label[:200]}
    if kind in ("click", "double_click", "right_click", "scroll"):
        for axis in ("x", "y"):
            value = step.get(axis)
            if type(value) is not int or not 0 <= value <= 1000:
                raise PolicyError("Coordinates must be 0-1000.")
            clean[axis] = value
    if kind == "scroll":
        amount = step.get("amount")
        if type(amount) is not int or amount == 0 or abs(amount) > 10:
            raise PolicyError("Scroll amount must be -10..10.")
        clean["amount"] = amount
    if kind == "type":
        text = step.get("text")
        if not isinstance(text, str) or not text or len(text) > 2000 or any(ord(c) < 32 for c in text):
            raise PolicyError("Typed text must be one line, 1-2000 characters.")
        clean["text"] = text
    if kind == "key":
        if step.get("key") not in KEYS:
            raise PolicyError("That key is not permitted.")
        clean["key"] = step["key"]
    return clean


def describe_step(step: dict) -> str:
    s = validate_step(step)
    kind = s["kind"]
    names = {"click": "คลิก", "double_click": "ดับเบิลคลิก", "right_click": "คลิกขวา"}
    if kind in names:
        return f"{names[kind]}: {s['label']}"
    if kind == "scroll":
        return f"เลื่อน{'ลง' if s['amount'] > 0 else 'ขึ้น'} {abs(s['amount'])} ครั้ง: {s['label']}"
    if kind == "type":
        return "พิมพ์: " + s["text"]
    if kind == "key":
        return "กดปุ่ม: " + s["key"]
    return "เสร็จแล้ว"


def capture():
    """Primary monitor in physical pixels (Pillow grabs DPI-aware)."""
    from PIL import ImageGrab
    return ImageGrab.grab()


def to_png(image) -> bytes:
    small = image.copy()
    small.thumbnail((MAX_WIDTH, MAX_WIDTH))
    out = io.BytesIO()
    small.save(out, "PNG", optimize=True)
    return out.getvalue()


def preview(image, step: dict, width=640):
    from PIL import ImageDraw
    small = image.convert("RGB")
    small.thumbnail((width, width))
    if "x" in step:
        x, y = step["x"] / 1000 * small.width, step["y"] / 1000 * small.height
        draw = ImageDraw.Draw(small)
        draw.ellipse((x - 12, y - 12, x + 12, y + 12), outline="#ff3040", width=4)
        draw.ellipse((x - 3, y - 3, x + 3, y + 3), fill="#ff3040")
    return small


class _KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD), ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.c_size_t)]


class _INPUT(ctypes.Structure):
    class _U(ctypes.Union):
        _fields_ = [("ki", _KEYBDINPUT), ("pad", ctypes.c_byte * 32)]
    _anonymous_ = ("u",)
    _fields_ = [("type", wintypes.DWORD), ("u", _U)]


def type_text(text: str):
    """Unicode key events, so Thai works and the clipboard is untouched."""
    user32 = ctypes.windll.user32
    data = text.encode("utf-16-le")
    for i in range(0, len(data), 2):
        unit = int.from_bytes(data[i:i + 2], "little")
        for flags in (0x4, 0x4 | 0x2):  # KEYEVENTF_UNICODE, then KEYUP
            event = _INPUT(type=1)
            event.ki = _KEYBDINPUT(0, unit, flags, 0, 0)
            user32.SendInput(1, ctypes.byref(event), ctypes.sizeof(_INPUT))


def press(key: str):
    user32 = ctypes.windll.user32
    codes = KEYS[key]
    for code in codes:
        user32.keybd_event(code, 0, 0, 0)
    for code in reversed(codes):
        user32.keybd_event(code, 0, 2, 0)


def perform(step: dict, size: tuple[int, int]):
    """size = screenshot size; the model saw the same screen scaled to 0-1000."""
    s = validate_step(step)
    kind = s["kind"]
    if kind == "done":
        return
    user32 = ctypes.windll.user32
    if kind == "type":
        type_text(s["text"])
        return
    if kind == "key":
        press(s["key"])
        return
    user32.SetThreadDpiAwarenessContext.restype = ctypes.c_void_p
    user32.SetThreadDpiAwarenessContext.argtypes = [ctypes.c_void_p]
    # ponytail: primary monitor only; add monitor offsets when multi-monitor tasks matter.
    old = user32.SetThreadDpiAwarenessContext(ctypes.c_void_p(-4))  # per-monitor v2 = physical pixels
    try:
        user32.SetCursorPos(round(s["x"] / 1000 * (size[0] - 1)), round(s["y"] / 1000 * (size[1] - 1)))
        time.sleep(0.05)
        if kind == "scroll":
            user32.mouse_event(0x0800, 0, 0, -120 * s["amount"], 0)
            return
        down, up = (0x0008, 0x0010) if kind == "right_click" else (0x0002, 0x0004)
        for _ in range(2 if kind == "double_click" else 1):
            user32.mouse_event(down, 0, 0, 0, 0)
            user32.mouse_event(up, 0, 0, 0, 0)
    finally:
        user32.SetThreadDpiAwarenessContext(old)


def foreground_exe() -> str:
    user32, kernel = ctypes.windll.user32, ctypes.windll.kernel32
    user32.GetForegroundWindow.restype = wintypes.HWND
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR,
                                                  ctypes.POINTER(wintypes.DWORD)]
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(user32.GetForegroundWindow(), ctypes.byref(pid))
    handle = kernel.OpenProcess(0x1000, False, pid.value)  # PROCESS_QUERY_LIMITED_INFORMATION
    if not handle:
        return ""
    try:
        buf = ctypes.create_unicode_buffer(1024)
        size = wintypes.DWORD(len(buf))
        return buf.value if kernel.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)) else ""
    finally:
        kernel.CloseHandle(handle)
