"""Bounded offline speech helpers. Public functions run on caller worker threads."""
from __future__ import annotations

from array import array
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import wave

ROOT = Path(__file__).resolve().parent
CLI = ROOT / "runtime/whisper/whisper-cli.exe"
MODEL = ROOT / "models/ggml-small.bin"
MANIFEST = ROOT / "runtime/voice-manifest.json"
POWERSHELL = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32/WindowsPowerShell/v1.0/powershell.exe"
MAX_SECONDS = 60
TRANSCRIBE_TIMEOUT = 240
_verified = {}
_verify_lock = threading.Lock()


class VoiceError(RuntimeError):
    pass


class VoiceCancelled(VoiceError):
    pass


def _verify_runtime():
    """Require the installer-pinned manifest; never download from a voice call."""
    try:
        if MANIFEST.stat().st_size > 100_000:
            raise ValueError("manifest too large")
        files = json.loads(MANIFEST.read_text(encoding="utf-8-sig"))["files"]
        if not isinstance(files, dict) or not files or len(files) > 100:
            raise ValueError("invalid file list")
        required = {CLI.relative_to(ROOT).as_posix(), MODEL.relative_to(ROOT).as_posix()}
        required.update(p.relative_to(ROOT).as_posix() for p in CLI.parent.iterdir()
                        if p.suffix.lower() in (".dll", ".exe"))
        if not required.issubset(files):
            raise ValueError("runtime file missing from manifest")
        with _verify_lock:
            for relative, expected in files.items():
                if not isinstance(expected, str) or len(expected) != 64 or any(c not in "0123456789abcdef" for c in expected.lower()):
                    raise ValueError("invalid SHA-256")
                path = (ROOT / relative).resolve()
                if not path.is_relative_to(ROOT.resolve()):
                    raise ValueError("manifest path outside application")
                before = path.stat()
                key = (str(path), before.st_size, before.st_mtime_ns, expected.lower())
                if _verified.get(str(path)) == key:
                    continue
                with path.open("rb") as stream:
                    digest = hashlib.file_digest(stream, "sha256").hexdigest()
                after = path.stat()
                if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns) or digest != expected.lower():
                    raise ValueError("checksum mismatch: " + relative)
                _verified[str(path)] = key
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise VoiceError("ระบบถอดเสียงในเครื่องยังไม่พร้อม หรือไฟล์ตรวจสอบไม่ตรง: " + str(exc)) from exc


def diagnostic() -> str:
    """Empty means ready; otherwise return a displayable Thai explanation."""
    try:
        _verify_runtime()
    except VoiceError as exc:
        return str(exc)
    return ""


def ready() -> bool:
    return not diagnostic()


def _pcm(wav: bytes) -> bytes:
    if not isinstance(wav, bytes) or len(wav) > MAX_SECONDS * 32000 + 65536:
        raise VoiceError("เสียงต้องเป็น WAV ความยาวไม่เกิน 60 วินาที")
    try:
        with wave.open(io.BytesIO(wav), "rb") as source:
            if (source.getnchannels(), source.getsampwidth(), source.getframerate(), source.getcomptype()) != (1, 2, 16000, "NONE"):
                raise VoiceError("เสียงต้องเป็น PCM 16 kHz โมโน 16 บิต")
            count = source.getnframes()
            if not 1 <= count <= MAX_SECONDS * 16000:
                raise VoiceError("เสียงต้องมีความยาวมากกว่า 0 และไม่เกิน 60 วินาที")
            pcm = source.readframes(count)
            if len(pcm) != count * 2:
                raise VoiceError("ไฟล์เสียงไม่สมบูรณ์")
    except (wave.Error, EOFError) as exc:
        raise VoiceError("รูปแบบไฟล์เสียงไม่ถูกต้อง") from exc
    samples = array("h", pcm)
    if sys.byteorder != "little":
        samples.byteswap()
    if sum(int(x) * int(x) for x in samples) / len(samples) < 100 ** 2:
        raise VoiceError("ไม่ได้ยินเสียงพูด กรุณาพูดอีกครั้ง")
    return pcm


def _terminate(process):
    if process.poll() is None:
        process.terminate()
    try:
        process.wait(timeout=2)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def _run(argv, *, cancelled, timeout, input_bytes=None, cwd=None):
    if cancelled():
        raise VoiceCancelled("ยกเลิกแล้ว")
    # Files avoid an unbounded pipe buffer and pipe-reader deadlock on CLI diagnostics.
    with tempfile.TemporaryFile() as output:
        try:
            environment = {k: v for k, v in os.environ.items()
                           if k.upper() not in ("GGML_BACKEND_PATH", "GGML_BACKEND_DL_PATH")}
            process = subprocess.Popen(argv, shell=False, cwd=cwd or ROOT, env=environment,
                                       stdin=subprocess.PIPE if input_bytes is not None else subprocess.DEVNULL,
                                       stdout=output, stderr=output,
                                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        except OSError as exc:
            raise VoiceError("เริ่มระบบเสียงในเครื่องไม่ได้: " + str(exc)) from exc
        deadline = time.monotonic() + timeout
        try:
            pending_input = input_bytes
            while True:
                if cancelled():
                    raise VoiceCancelled("ยกเลิกแล้ว")
                if time.monotonic() >= deadline:
                    raise VoiceError("ระบบเสียงใช้เวลานานเกินกำหนด กรุณาลองอีกครั้ง")
                try:
                    process.communicate(input=pending_input, timeout=0.1)
                    break
                except subprocess.TimeoutExpired:
                    pending_input = None
            if cancelled():
                raise VoiceCancelled("ยกเลิกแล้ว")
            if process.returncode:
                output.seek(0)
                detail = output.read(4096).decode("utf-8", errors="replace").strip()
                raise VoiceError("ระบบเสียงในเครื่องทำงานไม่สำเร็จ: " + detail)
        finally:
            _terminate(process)


def transcribe(wav: bytes, cancelled=lambda: False) -> str:
    if cancelled():
        raise VoiceCancelled("ยกเลิกแล้ว")
    pcm = _pcm(wav)
    _verify_runtime()
    with tempfile.TemporaryDirectory(prefix="jarvis-voice-") as directory:
        audio = Path(directory) / "command.wav"
        result = Path(directory) / "transcript"
        # Rewrite only validated PCM, dropping arbitrary source metadata/chunks.
        with wave.open(str(audio), "wb") as target:
            target.setnchannels(1)
            target.setsampwidth(2)
            target.setframerate(16000)
            target.writeframes(pcm)
        _run([str(CLI), "-m", str(MODEL), "-f", str(audio), "-l", "th",
              "-t", str(min(4, os.cpu_count() or 1)), "-otxt", "-of", str(result), "-nt", "-ng"],
             cancelled=cancelled, timeout=TRANSCRIBE_TIMEOUT, cwd=CLI.parent)
        try:
            output = result.with_suffix(".txt")
            if output.stat().st_size > 65536:
                raise VoiceError("ผลถอดเสียงยาวเกินกำหนด")
            text = output.read_text(encoding="utf-8-sig").strip()
        except OSError as exc:
            raise VoiceError("ไม่พบผลถอดเสียง") from exc
        if not text:
            raise VoiceError("ไม่ได้ยินเสียงพูด กรุณาพูดอีกครั้ง")
        return text


def _powershell(script):
    return [str(POWERSHELL), "-NoLogo", "-NoProfile", "-NonInteractive",
            "-ExecutionPolicy", "Bypass", "-File", str(ROOT / "scripts" / script)]


def speak(text: str, cancelled=lambda: False):
    if not isinstance(text, str) or not text.strip():
        return
    if len(text) > 8000:
        raise VoiceError("ข้อความอ่านออกเสียงยาวเกินกำหนด")
    _run(_powershell("speak-local.ps1"), cancelled=cancelled, timeout=180,
         input_bytes=text.encode("utf-8"))


class WakeListener:
    """callback(event, detail): 'wake' or 'error', always from the reader thread.

    start/stop are idempotent. Stop terminates and reaps the recognizer, releasing
    its microphone. Callbacks must queue UI work instead of touching Tk widgets.
    """
    def __init__(self, callback):
        self.callback = callback
        self._process = None
        self._thread = None
        self._lock = threading.Lock()

    def start(self):
        with self._lock:
            if self._process is not None and self._process.poll() is None:
                return
            try:
                process = subprocess.Popen(_powershell("wake.ps1"), shell=False, cwd=ROOT,
                                           stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                           stderr=subprocess.STDOUT, text=True, encoding="utf-8",
                                           errors="replace", creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            except OSError as exc:
                detail = "เริ่มการฟัง Jarvis ไม่ได้: " + str(exc)
                threading.Thread(target=self.callback, args=("error", detail), daemon=True).start()
                return
            self._process = process
            self._thread = threading.Thread(target=self._read, args=(process,), daemon=True, name="jarvis-wake")
            self._thread.start()

    def _read(self, process):
        detail = ""
        try:
            for line in iter(process.stdout.readline, ""):
                with self._lock:
                    active = self._process is process
                if not active:
                    break
                if line.strip() == "wake":
                    self.callback("wake", "")
                elif line.startswith("error:"):
                    detail = line[6:].strip()[:2000]
            process.wait()
            with self._lock:
                active = self._process is process
                if active:
                    self._process = None
            if active:
                self.callback("error", detail or "การฟัง Jarvis หยุดทำงาน กรุณาตรวจสอบไมโครโฟนและภาษาอังกฤษของ Windows")
        finally:
            process.stdout.close()

    def stop(self):
        with self._lock:
            process, self._process = self._process, None
            reader = self._thread
        if process is not None:
            _terminate(process)
        if reader is not None and reader is not threading.current_thread():
            reader.join(timeout=3)
