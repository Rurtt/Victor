"""Mentor-mode policy: how far Jarvis is allowed to help, and how it says so.

The ladder is enforced here in Python, never in the prompt. The model proposes a
rung; this module decides what it actually gets. That is the same posture
actions.py takes toward proposed PC actions.
"""
from __future__ import annotations

import re
from typing import NamedTuple

from memory import FAILURE_TAGS, MAX_RUNG, STATUSES, TOPICS

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


PAGE_TYPES = ("source", "concept", "entity", "synthesis", "query")
LANGS = ("en", "th", "both")
SLUG = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
MAX_NOTE_BODY = 20_000

MENTOR_SCHEMA = {
    "type": "object", "required": ["reply", "rung"], "additionalProperties": False,
    "properties": {
        "reply": {"type": "string"},
        "rung": {"type": "integer", "minimum": 0, "maximum": MAX_RUNG},
        "problem": {"type": "object", "additionalProperties": False,
                    "required": ["slug", "title"], "properties": {
                        "slug": {"type": "string"},
                        "title": {"type": "string"},
                        "topic": {"type": "string", "enum": list(TOPICS)},
                        "status": {"type": "string", "enum": list(STATUSES)}}},
        "failures": {"type": "array", "maxItems": 5, "items": {
            "type": "object", "required": ["tag"], "additionalProperties": False,
            "properties": {"tag": {"type": "string", "enum": list(FAILURE_TAGS)},
                           "note": {"type": "string"}}}},
        "note": {"type": "object", "additionalProperties": False,
                 "required": ["slug", "type", "tags", "lang", "body"], "properties": {
                     "slug": {"type": "string"},
                     "type": {"type": "string", "enum": list(PAGE_TYPES)},
                     "tags": {"type": "array", "maxItems": 8,
                              "items": {"type": "string"}},
                     "lang": {"type": "string", "enum": list(LANGS)},
                     "body": {"type": "string"}}}}}


class MentorError(RuntimeError):
    pass


class MentorReply(NamedTuple):
    text: str
    rung: int
    problem: dict | None
    failures: list[dict]
    note: dict | None


def _pick(value, allowed, field):
    if value not in allowed:
        raise MentorError(f"ค่า {field} ไม่อยู่ในรายการที่อนุญาต")
    return value


def _slug(value, field):
    if not isinstance(value, str) or not SLUG.fullmatch(value) or len(value) > 120:
        raise MentorError(f"{field} ต้องเป็น kebab-case")
    return value


def decode(data: dict) -> MentorReply:
    """Validate one model reply. The schema is a request, not a guarantee."""
    if not isinstance(data, dict):
        raise MentorError("รูปแบบคำตอบไม่ถูกต้อง")
    text = data.get("reply")
    if not isinstance(text, str) or not text.strip():
        raise MentorError("คำตอบว่าง")
    rung = data.get("rung")
    if not isinstance(rung, int) or isinstance(rung, bool) or not 0 <= rung <= MAX_RUNG:
        raise MentorError(f"ขั้นต้องอยู่ระหว่าง 0 ถึง {MAX_RUNG}")

    problem = data.get("problem")
    if problem is not None:
        if not isinstance(problem, dict):
            raise MentorError("ข้อมูลโจทย์ไม่ถูกต้อง")
        problem = {"slug": _slug(problem.get("slug"), "slug"),
                   "title": str(problem.get("title", ""))[:200],
                   "topic": (_pick(problem["topic"], TOPICS, "topic")
                             if problem.get("topic") is not None else None),
                   "status": (_pick(problem["status"], STATUSES, "status")
                              if problem.get("status") is not None else "working")}
        if not problem["title"].strip():
            raise MentorError("ชื่อโจทย์ว่าง")

    failures = []
    for item in data.get("failures") or []:
        if not isinstance(item, dict):
            raise MentorError("ข้อมูลข้อผิดพลาดไม่ถูกต้อง")
        failures.append({"tag": _pick(item.get("tag"), FAILURE_TAGS, "tag"),
                         "note": str(item.get("note", ""))[:500] or None})

    note = data.get("note")
    if note is not None:
        if not isinstance(note, dict):
            raise MentorError("ข้อมูลหน้า wiki ไม่ถูกต้อง")
        tags = note.get("tags")
        if not isinstance(tags, list) or not all(isinstance(t, str) for t in tags):
            raise MentorError("tags ต้องเป็นรายการข้อความ")
        body = note.get("body")
        if not isinstance(body, str) or not body.strip() or len(body) > MAX_NOTE_BODY:
            raise MentorError("เนื้อหาหน้า wiki ว่างหรือยาวเกินไป")
        note = {"slug": _slug(note.get("slug"), "slug"),
                "type": _pick(note.get("type"), PAGE_TYPES, "type"),
                "tags": [t[:40] for t in tags[:8]],
                "lang": _pick(note.get("lang"), LANGS, "lang"),
                "body": body}

    # Anything else the model sent — including an "actions" key — is dropped here.
    return MentorReply(text, rung, problem, failures, note)
