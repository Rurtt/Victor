"""Local settings and current-Windows-user DPAPI secret storage."""
from __future__ import annotations

import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import tempfile


class StorageError(RuntimeError):
    pass


class Blob(ctypes.Structure):
    _fields_ = [("size", wintypes.DWORD), ("data", ctypes.POINTER(ctypes.c_ubyte))]


def _crypt(raw: bytes, *, decrypt=False) -> bytes:
    if os.name != "nt":
        raise StorageError("การบันทึกคีย์แบบเข้ารหัสต้องใช้ Windows")
    buffer = ctypes.create_string_buffer(raw)
    source = Blob(len(raw), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte)))
    target = Blob()
    crypt = ctypes.WinDLL("crypt32", use_last_error=True)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    kernel.LocalFree.restype = ctypes.c_void_p
    if decrypt:
        fn = crypt.CryptUnprotectData
        fn.argtypes = [ctypes.POINTER(Blob), ctypes.POINTER(wintypes.LPWSTR), ctypes.POINTER(Blob),
                       ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(Blob)]
        second = None
    else:
        fn = crypt.CryptProtectData
        fn.argtypes = [ctypes.POINTER(Blob), wintypes.LPCWSTR, ctypes.POINTER(Blob),
                       ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(Blob)]
        second = "Jarvis API key"
    fn.restype = wintypes.BOOL
    # UI_FORBIDDEN only: never use LOCAL_MACHINE (which would broaden access).
    if not fn(ctypes.byref(source), second, None, None, None, 1, ctypes.byref(target)):
        raise StorageError("Windows เปิดหรือบันทึกคีย์ไม่ได้ กรุณาบันทึกใหม่จากบัญชี Windows เดิม")
    try:
        return ctypes.string_at(target.data, target.size)
    finally:
        kernel.LocalFree(target.data)


def _write_atomic(path: Path, data: bytes):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.parent.is_symlink() or path.parent.is_junction():
        raise StorageError("โฟลเดอร์ข้อมูลต้องอยู่ภายในโฟลเดอร์ Jarvis")
    fd, temp = tempfile.mkstemp(prefix=".jarvis-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        os.replace(temp, path)
    finally:
        Path(temp).unlink(missing_ok=True)


class LocalStore:
    def __init__(self, base: Path):
        self.directory = base / "data"
        self.key_path = self.directory / "gemini-key.dpapi"
        self.settings_path = self.directory / "settings.json"

    def read_key(self) -> str:
        if not self.key_path.exists():
            return ""
        try:
            raw = self.key_path.read_bytes()
            if len(raw) > 16000:
                raise StorageError("ไฟล์คีย์ไม่ถูกต้อง")
            return _crypt(raw, decrypt=True).decode("utf-8")
        except (OSError, ValueError) as exc:
            raise StorageError("อ่านคีย์ไม่ได้ กรุณาใส่คีย์แล้วบันทึกใหม่") from exc

    def save_key(self, key: str):
        if not key or len(key) > 256 or any(c.isspace() for c in key):
            raise StorageError("รูปแบบ API key ไม่ถูกต้อง")
        _write_atomic(self.key_path, _crypt(key.encode("utf-8")))

    def forget_key(self):
        self.key_path.unlink(missing_ok=True)

    def read_settings(self) -> dict:
        try:
            raw = self.settings_path.read_text(encoding="utf-8")
            data = json.loads(raw) if len(raw) < 5000 else {}
            return data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            return {}

    def save_settings(self, model: str, mentor: bool = False):
        _write_atomic(self.settings_path, json.dumps(
            {"model": model, "language": "th", "mentor": bool(mentor)},
            ensure_ascii=False).encode("utf-8"))

    def read_discord(self) -> dict:
        """{"auto": bool, "targets": {name: https://discord.com/channels/... link}}"""
        try:
            data = json.loads((self.directory / "discord.json").read_text(encoding="utf-8"))
            targets = {k: v for k, v in data.get("targets", {}).items() if isinstance(k, str) and isinstance(v, str)}
            return {"auto": data.get("auto") is True, "targets": targets}
        except (OSError, ValueError, AttributeError):
            return {"auto": False, "targets": {}}

    def save_discord(self, auto: bool, targets: dict):
        _write_atomic(self.directory / "discord.json",
                      json.dumps({"auto": auto, "targets": targets}, ensure_ascii=False, indent=1).encode("utf-8"))
