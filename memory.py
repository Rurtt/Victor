"""Persistent conversation and problem history. Model-proposed values are untrusted.

Jarvis kept sixteen messages in a Python list and lost them on restart. This module
is the disk behind that list: the application still holds a short window in memory
for what it sends to the model, while everything ever said stays here.

The enums below are policy, in the same spirit as actions.RULES: the model selects
from them and never extends them. Every write validates before it touches the
database, so a rejected value leaves nothing behind.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
import sqlite3

ROLES = ("user", "model")
STATUSES = ("working", "solved", "given-up")
VERDICTS = ("AC", "WA", "TLE", "RE", "unsubmitted")
TOPICS = ("dp", "graph", "greedy", "geometry", "math", "string", "data-structure",
          "search", "sorting", "implementation", "number-theory", "tree", "flow",
          "game-theory")
FAILURE_TAGS = ("off-by-one", "wrong-state", "missed-base-case", "overflow",
                "wrong-complexity", "misread-statement", "uninitialised",
                "wrong-greedy", "io-format", "precision", "recursion-depth",
                "edge-case-single", "untested-assumption")
MAX_RUNG = 5
MAX_TEXT = 200_000

SCHEMA = """
CREATE TABLE IF NOT EXISTS turn (
  id INTEGER PRIMARY KEY,
  chat_id INTEGER NOT NULL,
  role TEXT NOT NULL,
  text TEXT NOT NULL,
  created TEXT NOT NULL);

CREATE TABLE IF NOT EXISTS problem (
  id INTEGER PRIMARY KEY,
  slug TEXT UNIQUE NOT NULL,
  title TEXT NOT NULL,
  source TEXT,
  topic TEXT,
  status TEXT NOT NULL,
  rung INTEGER NOT NULL DEFAULT 0,
  created TEXT NOT NULL,
  updated TEXT NOT NULL);

CREATE TABLE IF NOT EXISTS attempt (
  id INTEGER PRIMARY KEY,
  problem_id INTEGER NOT NULL REFERENCES problem(id),
  body TEXT NOT NULL,
  verdict TEXT,
  created TEXT NOT NULL);

CREATE TABLE IF NOT EXISTS failure (
  id INTEGER PRIMARY KEY,
  attempt_id INTEGER NOT NULL REFERENCES attempt(id),
  tag TEXT NOT NULL,
  note TEXT);

CREATE TABLE IF NOT EXISTS meta (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL);

CREATE INDEX IF NOT EXISTS turn_by_chat ON turn(chat_id, id);
CREATE INDEX IF NOT EXISTS attempt_by_problem ON attempt(problem_id);
CREATE INDEX IF NOT EXISTS failure_by_attempt ON failure(attempt_id);
"""


class MemoryError(RuntimeError):
    pass


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _one_of(value, allowed, label):
    if value not in allowed:
        raise MemoryError(f"{label} ต้องเป็นหนึ่งใน {', '.join(allowed)}")
    return value


def _text(value, label):
    if not isinstance(value, str) or not value.strip():
        raise MemoryError(f"{label} ต้องไม่ว่าง")
    if len(value) > MAX_TEXT:
        raise MemoryError(f"{label} ยาวเกินไป")
    return value


class Memory:
    def __init__(self, base: Path):
        directory = Path(base) / "data"
        directory.mkdir(parents=True, exist_ok=True)
        self.path = directory / "jarvis.db"
        self.db = sqlite3.connect(self.path)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys = ON")
        with self.db:
            self.db.executescript(SCHEMA)
            if not self.db.execute("PRAGMA user_version").fetchone()[0]:
                self.db.execute("PRAGMA user_version = 1")
        # The current chat is stored, not inferred from MAX(chat_id): starting a new
        # chat and then restarting must not bring the previous conversation back.
        stored = self.db.execute("SELECT value FROM meta WHERE key = 'chat_id'").fetchone()
        if stored is None:
            seen = self.db.execute("SELECT MAX(chat_id) FROM turn").fetchone()[0]
            self.chat_id = seen or 1
            self._remember_chat()
        else:
            self.chat_id = int(stored[0])

    def _remember_chat(self):
        with self.db:
            self.db.execute("INSERT INTO meta (key, value) VALUES ('chat_id', ?)"
                            " ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                            (str(self.chat_id),))

    def close(self):
        self.db.close()

    # ---------- conversation ----------

    def add_turns(self, items):
        rows = [(self.chat_id, _one_of(i.get("role"), ROLES, "role"),
                 _text(i.get("text"), "ข้อความ"), _now()) for i in items]
        with self.db:
            self.db.executemany(
                "INSERT INTO turn (chat_id, role, text, created) VALUES (?, ?, ?, ?)", rows)

    def recent_turns(self, limit: int = 16) -> list[dict]:
        """Newest `limit` turns of the current chat, oldest first — app.py's shape."""
        rows = self.db.execute(
            "SELECT role, text FROM turn WHERE chat_id = ? ORDER BY id DESC LIMIT ?",
            (self.chat_id, limit)).fetchall()
        return [{"role": r["role"], "text": r["text"]} for r in reversed(rows)]

    def total_turns(self) -> int:
        return self.db.execute("SELECT COUNT(*) FROM turn").fetchone()[0]

    def new_chat(self):
        """Start a fresh conversation without deleting the previous one."""
        self.chat_id += 1
        self._remember_chat()

    # ---------- problems ----------

    def upsert_problem(self, slug, title, *, topic=None, source=None, status="working") -> int:
        slug, title = _text(slug, "slug"), _text(title, "ชื่อโจทย์")
        _one_of(status, STATUSES, "status")
        if topic is not None:
            _one_of(topic, TOPICS, "topic")
        now = _now()
        with self.db:
            # rung is deliberately absent from the UPDATE: an unlock the user earned
            # survives the model restating the problem's title or topic.
            self.db.execute(
                "INSERT INTO problem (slug, title, source, topic, status, created, updated)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)"
                " ON CONFLICT(slug) DO UPDATE SET title = excluded.title,"
                " source = COALESCE(excluded.source, problem.source),"
                " topic = COALESCE(excluded.topic, problem.topic),"
                " status = excluded.status, updated = excluded.updated",
                (slug, title, source, topic, status, now, now))
        return self.db.execute("SELECT id FROM problem WHERE slug = ?", (slug,)).fetchone()[0]

    def problem(self, slug) -> dict | None:
        row = self.db.execute("SELECT * FROM problem WHERE slug = ?", (slug,)).fetchone()
        return dict(row) if row else None

    def set_rung(self, problem_id: int, rung: int):
        if not isinstance(rung, int) or isinstance(rung, bool) or not 0 <= rung <= MAX_RUNG:
            raise MemoryError(f"ขั้นต้องอยู่ระหว่าง 0 ถึง {MAX_RUNG}")
        with self.db:
            self.db.execute("UPDATE problem SET rung = ?, updated = ? WHERE id = ?",
                            (rung, _now(), problem_id))

    # ---------- attempts and what went wrong ----------

    def add_attempt(self, problem_id: int, body: str, *, verdict=None) -> int:
        body = _text(body, "โค้ดหรือแนวคิด")
        if verdict is not None:
            _one_of(verdict, VERDICTS, "verdict")
        with self.db:
            cursor = self.db.execute(
                "INSERT INTO attempt (problem_id, body, verdict, created) VALUES (?, ?, ?, ?)",
                (problem_id, body, verdict, _now()))
        return cursor.lastrowid

    def add_failures(self, attempt_id: int, items):
        # Validate every tag before writing any, so a bad one leaves no partial record.
        rows = [(attempt_id, _one_of(i.get("tag"), FAILURE_TAGS, "tag"), i.get("note"))
                for i in items]
        with self.db:
            self.db.executemany(
                "INSERT INTO failure (attempt_id, tag, note) VALUES (?, ?, ?)", rows)

    def profile(self, topic: str, limit: int = 5) -> list[tuple[str, int]]:
        """How this user tends to get this topic wrong. Generated, never stored."""
        rows = self.db.execute(
            "SELECT tag, COUNT(*) AS n FROM failure"
            " JOIN attempt ON attempt.id = failure.attempt_id"
            " JOIN problem ON problem.id = attempt.problem_id"
            " WHERE problem.topic = ? GROUP BY tag ORDER BY n DESC, tag LIMIT ?",
            (topic, limit)).fetchall()
        return [(r["tag"], r["n"]) for r in rows]
