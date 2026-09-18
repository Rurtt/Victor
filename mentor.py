"""Mentor-mode policy: how far Jarvis is allowed to help, and how it says so.

The ladder is enforced here in Python, never in the prompt. The model proposes a
rung; this module decides what it actually gets. That is the same posture
actions.py takes toward proposed PC actions.
"""
from __future__ import annotations

from memory import MAX_RUNG

RUNG_LABELS = ("อ่านโจทย์", "โครงสร้าง", "ขอบเขต", "เทคนิค", "โครงโค้ด", "เฉลย")
OVERRIDE = "เปิดเฉลย"
NEEDS_ATTEMPT = 1   # no hint at all until the user has shown something
NEEDS_VERDICT = 4   # no code shape until the user has actually run something


def label(rung: int) -> str:
    return f"[ขั้น {rung}/{MAX_RUNG}: {RUNG_LABELS[rung]}]"


def is_override(text: str) -> bool:
    return OVERRIDE in (text or "")


def allowed_rung(stored: int, proposed: int, *, has_attempt: bool, has_verdict: bool) -> int:
    """What the model may actually give, given what the user has earned.

    Never more than one rung above where the problem already stands, never below
    it, and never past a gate the user has not met.
    """
    rung = min(max(proposed, stored), stored + 1)
    if rung >= NEEDS_VERDICT and not has_verdict:
        rung = NEEDS_VERDICT - 1
    if rung >= NEEDS_ATTEMPT and not has_attempt:
        rung = 0
    return max(0, min(rung, MAX_RUNG))
