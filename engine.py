"""Chooses the AI and speech provider for one request. The model id is the switch.

Gemini ids keep the HTTPS transport in brain.py; Claude ids run the signed-in
Claude Code subscription in claude_brain.py. Speech prefers the offline runtime
whenever it is installed and still matches its pinned manifest.
"""
from __future__ import annotations

import re

import brain
from brain import BrainError
import claude_brain
import local_voice
import voice

GEMINI = re.compile(r"gemini-[a-zA-Z0-9.-]{1,100}")
CLAUDE = re.compile(r"sonnet|haiku|opus|claude-[a-zA-Z0-9._-]{1,100}")
DEFAULT_MODEL = claude_brain.DEFAULT_MODEL
NO_CLOUD_SPEECH = ("โหมด Claude ไม่ส่งเสียงขึ้นคลาวด์ — ติดตั้งเสียงในเครื่องก่อน "
                   r"(scripts\install-voice.ps1): ")


def provider(model: str) -> str:
    if isinstance(model, str) and GEMINI.fullmatch(model):
        return "gemini"
    if isinstance(model, str) and CLAUDE.fullmatch(model):
        return "claude"
    raise BrainError("เลือกโมเดล: sonnet, haiku, opus หรือ gemini-…")


def valid_model(model: str) -> bool:
    try:
        provider(model)
    except BrainError:
        return False
    return True


def label(model: str) -> str:
    return "Claude" if provider(model) == "claude" else "Gemini"


def needs_key(model: str) -> bool:
    """Claude Code carries its own subscription login, so no key is stored for it."""
    return provider(model) == "gemini"


def _module(model: str):
    return claude_brain if provider(model) == "claude" else brain


def ask(key, model, history, prompt, **kwargs):
    return _module(model).ask(key, model, history, prompt, **kwargs)


def ask_screen(key, model, goal, done_steps, png, **kwargs):
    return _module(model).ask_screen(key, model, goal, done_steps, png, **kwargs)


def local_speech_installed() -> bool:
    """Cheap enough for the UI thread; ready() below hashes hundreds of megabytes."""
    return all(p.is_file() for p in (local_voice.MANIFEST, local_voice.CLI, local_voice.MODEL))


def transcribe(key, model, wav, *, on_retry=None, cancelled=lambda: False) -> str:
    if local_speech_installed():
        try:
            return local_voice.transcribe(wav, cancelled)
        except local_voice.VoiceCancelled:
            raise BrainError("Stopped") from None
        except local_voice.VoiceError as exc:
            raise BrainError(str(exc)) from None
    if needs_key(model):
        return brain.transcribe(key, model, wav, on_retry=on_retry, cancelled=cancelled)
    raise BrainError(NO_CLOUD_SPEECH + local_voice.diagnostic())


def speak(key, model, text, *, on_retry=None, cancelled=lambda: False) -> None:
    """Blocks the calling worker thread until the reply has been read aloud."""
    if local_speech_installed():
        try:
            local_voice.speak(text, cancelled)
            return
        except local_voice.VoiceCancelled:
            raise BrainError("Stopped") from None
        except local_voice.VoiceError as exc:
            raise BrainError(str(exc)) from None
    if needs_key(model):
        pcm = brain.synthesize(key, text, on_retry=on_retry, cancelled=cancelled)
        voice.play(voice.pcm_to_wav(pcm), cancelled=cancelled)
        return
    raise BrainError(NO_CLOUD_SPEECH + local_voice.diagnostic())
