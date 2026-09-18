"""Microphone recording (Windows MCI) and WAV playback. Standard library only."""
from __future__ import annotations

import ctypes
import io
import os
from pathlib import Path
import tempfile
import time
import wave
import winsound

ALIAS = "victor_rec"


def _mci(command: str) -> str:
    buf = ctypes.create_unicode_buffer(256)
    err = ctypes.windll.winmm.mciSendStringW(command, buf, 256, None)
    if err:
        msg = ctypes.create_unicode_buffer(256)
        ctypes.windll.winmm.mciGetErrorStringW(err, msg, 256)
        raise OSError("ไมโครโฟนใช้งานไม่ได้: " + (msg.value or str(err)))
    return buf.value


class Recorder:
    """Call from the Tk thread only. Nothing leaves the PC until stop() bytes are sent."""
    def __init__(self):
        self.active = False

    def start(self):
        self.cancel()
        _mci(f"open new type waveaudio alias {ALIAS}")
        try:
            _mci(f"set {ALIAS} bitspersample 16 samplespersec 16000 channels 1 bytespersec 32000 alignment 2")
            _mci(f"record {ALIAS}")
        except OSError:
            _mci(f"close {ALIAS}")
            raise
        self.active = True

    def stop(self) -> bytes:
        if not self.active:
            return b""
        fd, path = tempfile.mkstemp(prefix="victor-", suffix=".wav")
        os.close(fd)
        try:
            _mci(f"stop {ALIAS}")
            _mci(f'save {ALIAS} "{path}"')
            return Path(path).read_bytes()
        finally:
            self.cancel()
            Path(path).unlink(missing_ok=True)

    def cancel(self):
        if self.active:
            try:
                _mci(f"close {ALIAS}")
            except OSError:
                pass
        self.active = False


def pcm_to_wav(pcm: bytes, rate=24000) -> bytes:
    out = io.BytesIO()
    with wave.open(out, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm)
    return out.getvalue()


def play(wav: bytes, cancelled=lambda: False):
    """Blocks the calling worker thread until done or cancelled() turns true.

    Synchronous in-memory PlaySound cannot be interrupted, so play a temp file async."""
    with wave.open(io.BytesIO(wav)) as w:
        seconds = w.getnframes() / w.getframerate()
    fd, path = tempfile.mkstemp(prefix="victor-", suffix=".wav")
    os.close(fd)
    try:
        Path(path).write_bytes(wav)
        winsound.PlaySound(path, winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT)
        end = time.monotonic() + seconds + 0.3
        while time.monotonic() < end and not cancelled():
            time.sleep(0.05)
        if cancelled():
            stop_playback()
    finally:
        Path(path).unlink(missing_ok=True)


def beep():
    """Short acknowledgement that Victor heard its name."""
    winsound.MessageBeep(winsound.MB_OK)


def stop_playback():
    winsound.PlaySound(None, 0)
