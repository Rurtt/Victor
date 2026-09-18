# POSN Camp 2 Mentor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn Jarvis into a competitive-programming mentor for POSN Camp 2 that coaches the user in his own thinking style, using an escalating hint ladder that stops short of code until it is earned.

**Architecture:** A new `mentor.py` holds the ladder policy, the response schema and the prompt assembly; a new `vault.py` reads and writes a second Obsidian vault at `D:\Jarvis\Study`; the already-shipped `memory.py` stores problems, attempts and failure tags in SQLite. Claude runs with no tools and no filesystem access, so every piece of context is gathered in Python and injected into one prompt per turn under a hard character budget.

**Tech Stack:** Python 3.14, standard library only (`sqlite3`, `pathlib`, `json`, `re`, `unittest`), CustomTkinter for the desktop UI, the Claude Code CLI (`claude -p`) as the model transport.

**Spec:** `docs/superpowers/specs/2026-09-17-posn-mentor-design.md`

## Global Constraints

- **Standard library only.** The application uses no third-party packages beyond CustomTkinter and Pillow, which are already installed. Add no dependencies.
- **Claude has no tools.** `claude_brain._request` passes `--safe-mode --tools "" --strict-mcp-config --mcp-config '{"mcpServers":{}}'`. Claude cannot read files. Never write a design that assumes it can.
- **Model output is untrusted.** Every value the model proposes is validated in Python against a fixed enum before it reaches the database or the filesystem. This is the posture `actions.py:validate()` already takes.
- **Mentor mode proposes no PC actions.** `MENTOR_SCHEMA` has no `actions` key. Do not add one.
- **Thai for coaching, C++ and English for code.** User-facing mentor strings are Thai. Code, identifiers and log entries are English.
- **Vault invariants, from `D:\Jarvis\Luk Nong Pong\CLAUDE.md`:** never modify `raw/`; never overwrite `log.md`, append only; always update `index.md` after creating or modifying a page; every page carries `name`, `type`, `tags`, `lang`, `sources`, `date` frontmatter; `date` is `YYYY-MM-DD`; page `type` is one of `source | concept | entity | synthesis | query`; cross-links are `[[kebab-case-slug]]`.
- **Test command:** `python -m unittest discover -s tests` from the `Jarvis` directory. It passes 97 tests as of 2026-09-17. It must pass at the end of every task.
- **This directory is not a git repository.** `D:\Jarvis` is; `Jarvis\` is not. Each task's final step says to commit. If you have not run `git init` here, treat the green full-suite run as the checkpoint instead and move on. Do not run `git init` without asking the user.
- **Known pre-existing noise:** the suite prints `invalid command name … ("after" script)` lines during CustomTkinter teardown — 61 of them. They are not failures. Do not try to fix them as part of this plan.

---

## Already Done

**Step 1 of the spec's build order shipped on 2026-09-17.** `memory.py` exists and is tested by `tests/test_memory.py` (13 tests). `app.py` hydrates `self.history` from it, routes all five append sites through a new `remember()` helper, starts a new chat instead of erasing, and closes the database on exit. Do not redo this.

`memory.py` gives you, and every task below assumes:

```python
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

class MemoryError(RuntimeError): ...

class Memory:
    def __init__(self, base: Path)                  # opens <base>/data/jarvis.db
    def close(self)
    def add_turns(self, items)                      # items: [{"role","text"}]
    def recent_turns(self, limit=16) -> list[dict]  # oldest first
    def total_turns(self) -> int
    def new_chat(self)
    def upsert_problem(self, slug, title, *, topic=None, source=None,
                       status="working") -> int     # returns problem id; keeps rung
    def problem(self, slug) -> dict | None          # full row as a dict
    def set_rung(self, problem_id: int, rung: int)
    def add_attempt(self, problem_id: int, body: str, *, verdict=None) -> int
    def add_failures(self, attempt_id: int, items)  # items: [{"tag","note"}]
    def profile(self, topic: str, limit=5) -> list[tuple[str, int]]
```

---

## File Structure

| File | Status | Responsibility |
|------|--------|----------------|
| `memory.py` | exists, extended in Task 1 | SQLite persistence and the policy enums it validates against |
| `mentor.py` | create, Tasks 1–4 | Ladder policy, response schema, system prompt, prompt assembly and budget |
| `vault.py` | create, Tasks 5–6 | Study-vault frontmatter catalogue, page selection, page render and write |
| `claude_brain.py` | modify, Task 7 | `ask_mentor()` on top of the existing `_request()` |
| `engine.py` | modify, Task 7 | Route a mentor turn to the Claude provider |
| `local_store.py` | modify, Task 8 | Persist the mentor-mode flag in `settings.json` |
| `app.py` | modify, Task 8 | Mentor-mode toggle, mentor turn wiring, note approval |
| `tests/test_mentor.py` | create, Tasks 1–4, 7 | Ladder, schema, budget |
| `tests/test_vault.py` | create, Tasks 5–6 | Catalogue, selection, render, write, invariants |
| `tests/test_ui.py` | extend, Task 8 | Mentor mode end to end through the real widgets |

`mentor.py` and `vault.py` stay separate because they fail differently: a ladder bug produces a bad hint, a vault bug writes to the wrong file. Keeping the filesystem writer in its own module keeps its invariant tests isolated from the prompt work.

---

### Task 1: Ladder policy and the memory queries it needs

**Files:**
- Create: `mentor.py`
- Modify: `memory.py` (append three read methods)
- Test: `tests/test_mentor.py`

**Interfaces:**
- Consumes: `memory.Memory`, `memory.MAX_RUNG`, `memory.MemoryError`
- Produces:
  - `mentor.RUNG_LABELS: tuple[str, ...]` — six Thai labels, index is the rung
  - `mentor.OVERRIDE: str` — the literal `"เปิดเฉลย"`
  - `mentor.label(rung: int) -> str` — `"[ขั้น 3/5: เทคนิค]"`
  - `mentor.is_override(text: str) -> bool`
  - `mentor.allowed_rung(stored: int, proposed: int, *, has_attempt: bool, has_verdict: bool) -> int`
  - `memory.Memory.attempts(problem_id: int) -> list[dict]`
  - `memory.Memory.current_problem() -> dict | None`
  - `memory.Memory.similar_problems(topic: str, tags: list[str], limit: int = 3) -> list[dict]`

- [ ] **Step 1: Write the failing test**

Create `tests/test_mentor.py`:

```python
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import mentor
from memory import Memory


class LadderTests(unittest.TestCase):
    def test_the_model_cannot_promote_itself_more_than_one_rung(self):
        self.assertEqual(
            mentor.allowed_rung(1, 5, has_attempt=True, has_verdict=True), 2)

    def test_rung_one_needs_an_attempt(self):
        self.assertEqual(
            mentor.allowed_rung(0, 1, has_attempt=False, has_verdict=False), 0)
        self.assertEqual(
            mentor.allowed_rung(0, 1, has_attempt=True, has_verdict=False), 1)

    def test_rung_four_needs_a_verdict(self):
        self.assertEqual(
            mentor.allowed_rung(3, 4, has_attempt=True, has_verdict=False), 3)
        self.assertEqual(
            mentor.allowed_rung(3, 4, has_attempt=True, has_verdict=True), 4)

    def test_an_unlock_already_earned_is_never_taken_away(self):
        self.assertEqual(
            mentor.allowed_rung(3, 1, has_attempt=True, has_verdict=True), 3)

    def test_label_names_the_rung_in_thai(self):
        self.assertEqual(mentor.label(3), "[ขั้น 3/5: เทคนิค]")
        self.assertEqual(mentor.label(0), "[ขั้น 0/5: อ่านโจทย์]")

    def test_the_override_phrase_is_recognised_anywhere_in_the_line(self):
        self.assertTrue(mentor.is_override("เปิดเฉลย"))
        self.assertTrue(mentor.is_override("  ยอมแล้ว เปิดเฉลย ให้หน่อย  "))
        self.assertFalse(mentor.is_override("อย่าเพิ่งเปิดนะ"))


class MemoryQueryTests(unittest.TestCase):
    def test_attempts_and_current_problem(self):
        with tempfile.TemporaryDirectory() as d:
            memory = Memory(Path(d))
            try:
                first = memory.upsert_problem("a-th", "A", topic="dp")
                memory.add_attempt(first, "แนวคิด: ลองทุกกรณี")
                second = memory.upsert_problem("b-th", "B", topic="graph")
                memory.add_attempt(second, "int main(){}", verdict="WA")

                self.assertEqual(len(memory.attempts(first)), 1)
                self.assertIsNone(memory.attempts(first)[0]["verdict"])
                self.assertEqual(memory.attempts(second)[0]["verdict"], "WA")
                # Most recently updated problem that is still being worked on.
                self.assertEqual(memory.current_problem()["slug"], "b-th")
            finally:
                memory.close()

    def test_current_problem_ignores_finished_work(self):
        with tempfile.TemporaryDirectory() as d:
            memory = Memory(Path(d))
            try:
                memory.upsert_problem("a-th", "A", topic="dp")
                memory.upsert_problem("b-th", "B", topic="dp", status="solved")
                self.assertEqual(memory.current_problem()["slug"], "a-th")
            finally:
                memory.close()

    def test_similar_problems_match_topic_or_shared_failure_tag(self):
        with tempfile.TemporaryDirectory() as d:
            memory = Memory(Path(d))
            try:
                dp = memory.upsert_problem("dp-one", "DP one", topic="dp")
                attempt = memory.add_attempt(dp, "code", verdict="WA")
                memory.add_failures(attempt, [{"tag": "wrong-state"}])

                graph = memory.upsert_problem("graph-one", "Graph one", topic="graph")
                attempt = memory.add_attempt(graph, "code", verdict="WA")
                memory.add_failures(attempt, [{"tag": "wrong-state"}])

                memory.upsert_problem("far-away", "Unrelated", topic="geometry")

                found = {p["slug"] for p in
                         memory.similar_problems("dp", ["wrong-state"], limit=5)}
                self.assertEqual(found, {"dp-one", "graph-one"})
            finally:
                memory.close()


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m unittest discover -s tests -p "test_mentor.py"`
Expected: `ModuleNotFoundError: No module named 'mentor'`

- [ ] **Step 3: Add the three read methods to `memory.py`**

Append inside `class Memory`, after `profile`:

```python
    def attempts(self, problem_id: int) -> list[dict]:
        rows = self.db.execute(
            "SELECT * FROM attempt WHERE problem_id = ? ORDER BY id", (problem_id,)).fetchall()
        return [dict(r) for r in rows]

    def current_problem(self) -> dict | None:
        """The problem the user is on: most recently touched and not finished."""
        row = self.db.execute(
            "SELECT * FROM problem WHERE status = 'working'"
            " ORDER BY updated DESC, id DESC LIMIT 1").fetchone()
        return dict(row) if row else None

    def similar_problems(self, topic: str, tags: list[str], limit: int = 3) -> list[dict]:
        """Past problems worth showing beside this one: same topic, or same mistake."""
        placeholders = ",".join("?" * len(tags)) if tags else "NULL"
        rows = self.db.execute(
            "SELECT DISTINCT problem.* FROM problem"
            " LEFT JOIN attempt ON attempt.problem_id = problem.id"
            " LEFT JOIN failure ON failure.attempt_id = attempt.id"
            f" WHERE problem.topic = ? OR failure.tag IN ({placeholders})"
            " ORDER BY problem.updated DESC LIMIT ?",
            (topic, *tags, limit)).fetchall()
        return [dict(r) for r in rows]
```

- [ ] **Step 4: Create `mentor.py` with the ladder policy**

```python
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
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python -m unittest discover -s tests -p "test_mentor.py"`
Expected: 9 tests, `OK`

- [ ] **Step 6: Run the full suite**

Run: `python -m unittest discover -s tests`
Expected: 106 tests, `OK`

- [ ] **Step 7: Commit**

```bash
git add mentor.py memory.py tests/test_mentor.py
git commit -m "feat: mentor ladder policy and the problem queries behind it"
```

---

### Task 2: The mentor response schema and its validator

**Files:**
- Modify: `mentor.py`
- Test: `tests/test_mentor.py`

**Interfaces:**
- Consumes: `memory.TOPICS`, `memory.FAILURE_TAGS`, `memory.STATUSES`, `memory.MAX_RUNG`
- Produces:
  - `mentor.MENTOR_SCHEMA: dict` — the JSON schema handed to `claude -p --json-schema`
  - `mentor.MentorError` — raised on any invalid reply
  - `mentor.MentorReply` — a `NamedTuple` with fields `text: str`, `rung: int`, `problem: dict | None`, `failures: list[dict]`, `note: dict | None`
  - `mentor.decode(data: dict) -> MentorReply`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_mentor.py`, above `if __name__`:

```python
class SchemaTests(unittest.TestCase):
    def good(self, **extra):
        return {"reply": "ลองดูที่ n ก่อน", "rung": 2, **extra}

    def test_a_minimal_reply_decodes(self):
        decoded = mentor.decode(self.good())
        self.assertEqual(decoded.text, "ลองดูที่ n ก่อน")
        self.assertEqual(decoded.rung, 2)
        self.assertIsNone(decoded.problem)
        self.assertEqual(decoded.failures, [])
        self.assertIsNone(decoded.note)

    def test_a_reply_can_never_carry_pc_actions(self):
        self.assertNotIn("actions", mentor.MENTOR_SCHEMA["properties"])
        decoded = mentor.decode(self.good(actions=[{"name": "open_app"}]))
        self.assertFalse(hasattr(decoded, "actions"))

    def test_an_unknown_topic_is_refused(self):
        with self.assertRaises(mentor.MentorError):
            mentor.decode(self.good(problem={"slug": "x", "title": "X",
                                             "topic": "quantum", "status": "working"}))

    def test_an_unknown_failure_tag_is_refused(self):
        with self.assertRaises(mentor.MentorError):
            mentor.decode(self.good(failures=[{"tag": "vibes-were-off"}]))

    def test_an_unknown_page_type_is_refused(self):
        with self.assertRaises(mentor.MentorError):
            mentor.decode(self.good(note={"slug": "s", "type": "blogpost",
                                          "tags": ["dp"], "lang": "th", "body": "x"}))

    def test_a_rung_outside_the_ladder_is_refused(self):
        with self.assertRaises(mentor.MentorError):
            mentor.decode({"reply": "x", "rung": 9})

    def test_a_missing_reply_is_refused(self):
        with self.assertRaises(mentor.MentorError):
            mentor.decode({"rung": 1})

    def test_a_slug_that_looks_like_a_path_is_refused(self):
        with self.assertRaises(mentor.MentorError):
            mentor.decode(self.good(note={"slug": "../escape", "type": "concept",
                                          "tags": ["dp"], "lang": "th", "body": "x"}))

    def test_a_well_formed_note_survives(self):
        decoded = mentor.decode(self.good(note={
            "slug": "monotonic-deque", "type": "concept", "tags": ["dp", "queue"],
            "lang": "both", "body": "คิวที่เก็บค่าเรียงลง"}))
        self.assertEqual(decoded.note["slug"], "monotonic-deque")
        self.assertEqual(decoded.note["type"], "concept")
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m unittest discover -s tests -p "test_mentor.py"`
Expected: FAIL with `AttributeError: module 'mentor' has no attribute 'decode'`

- [ ] **Step 3: Add the schema and the validator to `mentor.py`**

Add to the imports at the top of `mentor.py`:

```python
import re
from typing import NamedTuple

from memory import FAILURE_TAGS, MAX_RUNG, STATUSES, TOPICS
```

Then append:

```python
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
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m unittest discover -s tests -p "test_mentor.py"`
Expected: 18 tests, `OK`

- [ ] **Step 5: Run the full suite and commit**

Run: `python -m unittest discover -s tests` — expected 115 tests, `OK`

```bash
git add mentor.py tests/test_mentor.py
git commit -m "feat: mentor response schema with no PC actions and strict validation"
```

---

### Task 3: The mentor system prompt

**Files:**
- Modify: `mentor.py`
- Test: `tests/test_mentor.py`

**Interfaces:**
- Consumes: `mentor.OVERRIDE`
- Produces: `mentor.SYSTEM: str`, `mentor.NOTE_FRAME: str`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_mentor.py`:

```python
class SystemPromptTests(unittest.TestCase):
    def test_the_prompt_states_the_rules_python_actually_enforces(self):
        for fragment in ("เปิดเฉลย", "C++", "ขั้น", "POSN"):
            self.assertIn(fragment, mentor.SYSTEM)

    def test_the_prompt_forbids_jumping_the_ladder(self):
        self.assertIn("ทีละขั้น", mentor.SYSTEM)

    def test_the_prompt_tells_the_model_it_has_no_tools(self):
        self.assertIn("ไม่สามารถเปิดไฟล์", mentor.SYSTEM)

    def test_notes_are_framed_as_the_users_assumptions_not_as_truth(self):
        self.assertIn("ไม่ใช่ข้อเท็จจริง", mentor.NOTE_FRAME)
        self.assertIn("ทางเลือกอื่น", mentor.NOTE_FRAME)

    def test_the_prompt_fits_its_slice_of_the_budget(self):
        self.assertLess(len(mentor.SYSTEM) + len(mentor.NOTE_FRAME), 1200)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m unittest discover -s tests -p "test_mentor.py"`
Expected: FAIL with `AttributeError: module 'mentor' has no attribute 'SYSTEM'`

- [ ] **Step 3: Add the prompts to `mentor.py`**

```python
NOTE_FRAME = """บันทึกด้านล่างเป็นของผู้ใช้เอง เป็นสมมติฐานของเขา ไม่ใช่ข้อเท็จจริง
ถ้าความเห็นของคุณต่างจากบันทึก ให้บอกตรง ๆ แล้วเสนอทางเลือกอื่นให้เขาเห็น
อย่าเล่าสมมติฐานของเขากลับไปเฉย ๆ"""

SYSTEM = f"""คุณคือโค้ชโจทย์ POSN ค่าย 2 (สอวน. คอมพิวเตอร์) ของผู้ใช้
อธิบายเป็นภาษาไทย โค้ดและชื่อเทคนิคเป็น C++ กับภาษาอังกฤษตามเดิม

คุณไม่สามารถเปิดไฟล์ ค้นเว็บ หรือสั่งงานคอมพิวเตอร์ได้ ข้อมูลทั้งหมดที่คุณมีอยู่ในพรอมต์นี้แล้ว

ให้คำใบ้ทีละขั้น ห้ามข้ามขั้น ขั้นที่อนุญาตจะระบุมาให้ในแต่ละครั้ง:
0 อ่านโจทย์ — ถามว่าเขาอ่านโจทย์ได้ว่าอย่างไร ยังไม่ใบ้
1 โครงสร้าง — ถามถึงโครงสร้างของปัญหา
2 ขอบเขต — ชี้ที่ขอบเขตของ input ที่กำหนดคลาสของอัลกอริทึม
3 เทคนิค — บอกชื่อเทคนิค
4 โครงโค้ด — pseudocode เท่านั้น ห้ามเป็น C++
5 เฉลย — โค้ด C++ เต็ม พร้อมบอกว่าของเขาพังตรงไหน

ถ้าขั้นที่อนุญาตต่ำกว่าที่เขาขอ ให้ทำตามขั้นที่อนุญาตโดยไม่ต้องบ่น
ถ้าเขาพิมพ์ "{OVERRIDE}" ระบบจะเปิดเฉลยให้เองและบันทึกว่าเขายอมแพ้ คุณไม่ต้องห้าม

ถามกลับมากกว่าบอก ชี้ตัวอย่างแย้งแทนการบอกว่าผิด
ถ้ายังไม่มีข้อมูลว่าเขามักพลาดเรื่องอะไร ให้บอกว่ายังไม่รู้ อย่าเดา

ตอบเป็น JSON: reply คือข้อความถึงเขา, rung คือขั้นที่คุณให้จริง
ถ้ารู้ว่าเป็นโจทย์ไหนให้ใส่ problem, ถ้าเห็นข้อผิดพลาดให้ใส่ failures
ถ้ามีอะไรควรเก็บเข้า wiki ให้ใส่ note แล้วระบบจะถามผู้ใช้ก่อนบันทึก"""
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m unittest discover -s tests -p "test_mentor.py"`
Expected: 23 tests, `OK`

If the budget assertion fails, shorten `SYSTEM` — do not raise the 1,200 limit. The budget in Task 4 depends on it.

- [ ] **Step 5: Run the full suite and commit**

Run: `python -m unittest discover -s tests` — expected 120 tests, `OK`

```bash
git add mentor.py tests/test_mentor.py
git commit -m "feat: mentor system prompt and the untrusted-notes frame"
```

---

### Task 4: Prompt assembly and the injection budget

**Files:**
- Modify: `mentor.py`
- Test: `tests/test_mentor.py`

**Interfaces:**
- Consumes: everything from Tasks 1–3
- Produces:
  - `mentor.BUDGET: dict[str, int]` — the per-slice caps
  - `mentor.render_profile(rows: list[tuple[str, int]]) -> str`
  - `mentor.build_prompt(*, allowed, problem, attempts, profile, similar, style_guide, pages, turns) -> str`

Every argument is plain data, so this function needs no database and no filesystem and is tested directly.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_mentor.py`:

```python
class BudgetTests(unittest.TestCase):
    def oversized(self):
        return {
            "allowed": 3,
            "problem": {"slug": "knapsack-th", "title": "K" * 5000, "topic": "dp",
                        "status": "working", "rung": 2},
            "attempts": [{"body": "x" * 9000, "verdict": "WA"}],
            "profile": [("wrong-state", 4), ("off-by-one", 2)],
            "similar": [{"slug": f"p{n}", "title": "T" * 3000, "topic": "dp"}
                        for n in range(9)],
            "style_guide": "s" * 9000,
            "pages": ["p" * 9000, "q" * 9000, "r" * 9000],
            "turns": [{"role": "user", "text": "t" * 4000} for _ in range(40)],
        }

    def test_every_slice_is_capped_and_the_total_stays_under_the_limit(self):
        prompt = mentor.build_prompt(**self.oversized())
        self.assertLess(len(prompt), 21_000)

    def test_no_slice_is_dropped_entirely_when_everything_is_oversized(self):
        prompt = mentor.build_prompt(**self.oversized())
        for marker in ("knapsack-th", "wrong-state", "sss", "ppp", "ttt"):
            self.assertIn(marker, prompt)

    def test_the_allowed_rung_is_stated_to_the_model(self):
        prompt = mentor.build_prompt(**{**self.oversized(), "allowed": 4})
        self.assertIn("ขั้นที่อนุญาตรอบนี้: 4", prompt)

    def test_an_empty_profile_says_so_rather_than_being_silent(self):
        self.assertIn("ยังไม่มีข้อมูล", mentor.render_profile([]))

    def test_a_profile_ranks_what_the_user_gets_wrong(self):
        rendered = mentor.render_profile([("wrong-state", 4), ("off-by-one", 1)])
        self.assertIn("wrong-state", rendered)
        self.assertIn("4", rendered)

    def test_a_first_session_with_nothing_stored_still_builds_a_prompt(self):
        prompt = mentor.build_prompt(allowed=0, problem=None, attempts=[], profile=[],
                                     similar=[], style_guide="", pages=[], turns=[])
        self.assertIn("ขั้นที่อนุญาตรอบนี้: 0", prompt)
        self.assertIn("ยังไม่มีข้อมูล", prompt)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m unittest discover -s tests -p "test_mentor.py"`
Expected: FAIL with `AttributeError: module 'mentor' has no attribute 'build_prompt'`

- [ ] **Step 3: Add the budget and the assembler to `mentor.py`**

Add `import json` to the imports, then append:

```python
BUDGET = {"style_guide": 1500, "profile": 800, "problem": 2500,
          "similar": 1500, "pages": 1500, "turns": 11_000}


def _cut(text: str, limit: int) -> str:
    text = text or ""
    return text if len(text) <= limit else text[:limit - 1] + "…"


def render_profile(rows) -> str:
    if not rows:
        return "ยังไม่มีข้อมูลว่าเขามักพลาดเรื่องอะไรในหัวข้อนี้"
    return "เขามักพลาดเรื่องนี้ในหัวข้อนี้: " + ", ".join(
        f"{tag} ({n} ครั้ง)" for tag, n in rows)


def build_prompt(*, allowed, problem, attempts, profile, similar,
                 style_guide, pages, turns) -> str:
    """One mentor turn's context, each slice capped independently.

    Claude cannot read any of this for itself; everything it will know is here.
    """
    parts = [f"ขั้นที่อนุญาตรอบนี้: {allowed} ({RUNG_LABELS[allowed]})",
             "ห้ามให้มากกว่าขั้นนี้ แม้ผู้ใช้จะขอ"]

    if style_guide:
        parts.append(NOTE_FRAME)
        parts.append("สไตล์การอธิบายของผู้ใช้:\n" +
                     _cut(style_guide, BUDGET["style_guide"]))

    parts.append(_cut(render_profile(profile), BUDGET["profile"]))

    if problem:
        current = {"slug": problem.get("slug"), "title": problem.get("title"),
                   "topic": problem.get("topic"), "status": problem.get("status"),
                   "rung": problem.get("rung")}
        latest = attempts[-1] if attempts else None
        block = "โจทย์ปัจจุบัน: " + json.dumps(current, ensure_ascii=False)
        if latest:
            block += ("\nสิ่งที่เขาลองล่าสุด (verdict="
                      f"{latest.get('verdict') or 'ยังไม่ได้รัน'}):\n"
                      + (latest.get("body") or ""))
        parts.append(_cut(block, BUDGET["problem"]))
    else:
        parts.append("ยังไม่ได้ระบุว่าเป็นโจทย์ข้อไหน")

    if similar:
        lines = [f"- {p.get('slug')} ({p.get('topic')}): {p.get('title')}"
                 for p in similar[:3]]
        parts.append(_cut("โจทย์เก่าที่ใกล้เคียง:\n" + "\n".join(lines),
                          BUDGET["similar"]))

    if pages:
        joined = "\n\n".join(pages[:2])
        parts.append(_cut("บันทึกจาก wiki ของเขา:\n" + joined, BUDGET["pages"]))

    if turns:
        lines = [f"{t.get('role')}: {t.get('text')}" for t in turns]
        conversation = "\n".join(lines)
        # Keep the newest turns: trim from the front, not the back.
        if len(conversation) > BUDGET["turns"]:
            conversation = "…" + conversation[-(BUDGET["turns"] - 1):]
        parts.append("บทสนทนาก่อนหน้า:\n" + conversation)

    return "\n\n".join(parts)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m unittest discover -s tests -p "test_mentor.py"`
Expected: 29 tests, `OK`

- [ ] **Step 5: Run the full suite and commit**

Run: `python -m unittest discover -s tests` — expected 126 tests, `OK`

```bash
git add mentor.py tests/test_mentor.py
git commit -m "feat: mentor prompt assembly under a hard per-slice budget"
```

---

### Task 5: Study vault, read side

**Files:**
- Create: `vault.py`
- Test: `tests/test_vault.py`
- Create by hand, once: `D:\Jarvis\Study\` with `wiki\`, `raw\assets\`, `index.md`, `log.md`, `CLAUDE.md`

**Interfaces:**
- Consumes: nothing from earlier tasks
- Produces:
  - `vault.VaultError`
  - `vault.Vault(root: Path)`
  - `vault.Vault.catalogue() -> list[dict]` — one dict per page with `slug`, `type`, `tags`, `lang`, `date`, `path`
  - `vault.Vault.page(slug: str) -> str` — full page text, `""` when absent
  - `vault.Vault.select(topic: str, tags: list[str], limit=2, budget=1500) -> list[str]`
  - `vault.Vault.style_guide(budget=1500) -> str`

- [ ] **Step 1: Create the vault on disk**

A one-time manual step, not code. Run in PowerShell:

```powershell
New-Item -ItemType Directory -Force "D:\Jarvis\Study\wiki", "D:\Jarvis\Study\raw\assets"
Copy-Item "D:\Jarvis\Luk Nong Pong\CLAUDE.md" "D:\Jarvis\Study\CLAUDE.md"
Set-Content "D:\Jarvis\Study\index.md" "# Wiki Index`nLast updated: 2026-09-17 | Total pages: 0" -Encoding utf8
Set-Content "D:\Jarvis\Study\log.md" "# Log" -Encoding utf8
```

Then edit `D:\Jarvis\Study\CLAUDE.md` and change exactly two things — the `Vault:` line to `D:\Jarvis\Study\`, and the `Domain:` line to `Study — competitive programming, POSN, CTF`. Change nothing else; the schema is reused verbatim.

- [ ] **Step 2: Write the failing test**

Create `tests/test_vault.py`:

```python
from pathlib import Path
import tempfile
import unittest

from vault import Vault, VaultError

PAGE = """---
name: {slug}
type: {type}
tags: [{tags}]
lang: th
sources: 1
date: 2026-09-17
---

{body}
"""


def build(root: Path, pages):
    (root / "wiki").mkdir(parents=True)
    (root / "raw" / "assets").mkdir(parents=True)
    (root / "index.md").write_text("# Wiki Index", encoding="utf-8")
    (root / "log.md").write_text("# Log", encoding="utf-8")
    for slug, kind, tags, body in pages:
        (root / "wiki" / f"{slug}.md").write_text(
            PAGE.format(slug=slug, type=kind, tags=", ".join(tags), body=body),
            encoding="utf-8")


class CatalogueTests(unittest.TestCase):
    def test_the_catalogue_reads_frontmatter_from_every_page(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            build(root, [("monotonic-deque", "concept", ["dp", "queue"], "เนื้อหา"),
                         ("style-guide", "entity", ["meta"], "สไตล์ของผม")])
            entries = {e["slug"]: e for e in Vault(root).catalogue()}
            self.assertEqual(set(entries), {"monotonic-deque", "style-guide"})
            self.assertEqual(entries["monotonic-deque"]["type"], "concept")
            self.assertEqual(entries["monotonic-deque"]["tags"], ["dp", "queue"])
            self.assertEqual(entries["style-guide"]["date"], "2026-09-17")

    def test_a_page_without_frontmatter_is_skipped_not_fatal(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            build(root, [("good", "concept", ["dp"], "ok")])
            (root / "wiki" / "broken.md").write_text("no frontmatter", encoding="utf-8")
            self.assertEqual([e["slug"] for e in Vault(root).catalogue()], ["good"])

    def test_a_missing_vault_reports_itself_rather_than_crashing(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(VaultError):
                Vault(Path(d) / "not-here").catalogue()


class SelectionTests(unittest.TestCase):
    def test_pages_are_selected_by_tag_overlap_and_capped(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            build(root, [("dp-note", "concept", ["dp"], "ก" * 4000),
                         ("graph-note", "concept", ["graph"], "ข" * 4000),
                         ("shared", "concept", ["dp", "graph"], "ค" * 4000)])
            chosen = Vault(root).select("dp", [], limit=2, budget=1500)
            self.assertEqual(len(chosen), 2)
            self.assertLessEqual(sum(len(c) for c in chosen), 1500)
            self.assertTrue(any("dp-note" in c or "shared" in c for c in chosen))
            self.assertFalse(any("graph-note" in c for c in chosen))

    def test_the_style_guide_is_found_by_slug_and_capped(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            build(root, [("style-guide", "entity", ["meta"], "ส" * 4000)])
            guide = Vault(root).style_guide(budget=1500)
            self.assertLessEqual(len(guide), 1500)
            self.assertIn("ส", guide)

    def test_a_missing_style_guide_is_an_empty_string_not_an_error(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            build(root, [("dp-note", "concept", ["dp"], "x")])
            self.assertEqual(Vault(root).style_guide(), "")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `python -m unittest discover -s tests -p "test_vault.py"`
Expected: `ModuleNotFoundError: No module named 'vault'`

- [ ] **Step 4: Create `vault.py`**

```python
"""Read and write a study vault that follows the existing Obsidian schema.

The schema is not ours to invent — it is D:\\Jarvis\\Luk Nong Pong\\CLAUDE.md, reused
verbatim. Page content is the user's own notes: treated as his assumptions, and as
untrusted text when it reaches a prompt. Nothing here ever writes to raw/.
"""
from __future__ import annotations

from pathlib import Path
import re

STYLE_GUIDE = "style-guide"
FRONTMATTER = re.compile(r"\A---\r?\n(.*?)\r?\n---\r?\n", re.DOTALL)
MAX_PAGE = 100_000


class VaultError(RuntimeError):
    pass


def _parse_list(raw: str) -> list[str]:
    inner = raw.strip().strip("[]")
    return [item.strip().strip("'\"") for item in inner.split(",") if item.strip()]


def _frontmatter(text: str) -> dict | None:
    match = FRONTMATTER.match(text)
    if not match:
        return None
    fields = {}
    for line in match.group(1).splitlines():
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        fields[key.strip()] = value.strip()
    if "name" not in fields or "type" not in fields:
        return None
    return {"slug": fields["name"], "type": fields["type"],
            "tags": _parse_list(fields.get("tags", "")),
            "lang": fields.get("lang", "both"), "date": fields.get("date", "")}


class Vault:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.wiki = self.root / "wiki"
        self.log = self.root / "log.md"
        self.index = self.root / "index.md"
        self._cache: list[dict] | None = None
        self._stamp = None

    def catalogue(self) -> list[dict]:
        """Frontmatter only, cached against the directory's mtime."""
        if not self.wiki.is_dir():
            raise VaultError(f"ไม่พบ wiki ที่ {self.wiki}")
        stamp = self.wiki.stat().st_mtime_ns
        if self._cache is not None and stamp == self._stamp:
            return self._cache
        entries = []
        for path in sorted(self.wiki.glob("*.md")):
            try:
                head = path.read_text(encoding="utf-8")[:4000]
            except OSError:
                continue
            fields = _frontmatter(head)
            if fields:
                entries.append({**fields, "path": path})
        self._cache, self._stamp = entries, stamp
        return entries

    def page(self, slug: str) -> str:
        for entry in self.catalogue():
            if entry["slug"] == slug:
                return entry["path"].read_text(encoding="utf-8")[:MAX_PAGE]
        return ""

    def select(self, topic: str, tags, limit: int = 2, budget: int = 1500) -> list[str]:
        """Pages whose tags overlap the current topic. No model call to choose."""
        wanted = {topic, *(tags or [])}
        ranked = sorted(
            (e for e in self.catalogue()
             if e["slug"] != STYLE_GUIDE and wanted & set(e["tags"])),
            key=lambda e: (-len(wanted & set(e["tags"])), e["slug"]))
        chosen, spent = [], 0
        share = budget // max(1, min(limit, len(ranked) or 1))
        for entry in ranked[:limit]:
            text = entry["path"].read_text(encoding="utf-8")[:share]
            if spent + len(text) > budget:
                text = text[:budget - spent]
            if not text:
                break
            chosen.append(text)
            spent += len(text)
        return chosen

    def style_guide(self, budget: int = 1500) -> str:
        return self.page(STYLE_GUIDE)[:budget]
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python -m unittest discover -s tests -p "test_vault.py"`
Expected: 6 tests, `OK`

- [ ] **Step 6: Run the full suite and commit**

Run: `python -m unittest discover -s tests` — expected 132 tests, `OK`

```bash
git add vault.py tests/test_vault.py
git commit -m "feat: study vault frontmatter catalogue and tag-based page selection"
```

---

### Task 6: Study vault, write side

**Files:**
- Modify: `vault.py`
- Test: `tests/test_vault.py`

**Interfaces:**
- Consumes: `vault.Vault` from Task 5, the `note` dict shape from `mentor.decode` in Task 2
- Produces:
  - `vault.Vault.render(note: dict, *, sources: int = 1, today: str | None = None) -> str`
  - `vault.Vault.save(note: dict, summary: str, *, today: str | None = None) -> Path`
  - `vault.Vault.rebuild_index(today: str | None = None)`
  - `vault.Vault.append_log(action: str, title: str, description: str, today: str | None = None)`

`today` is injectable so tests do not depend on the clock. It defaults to `date.today().isoformat()`.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_vault.py`, above `if __name__`:

```python
NOTE = {"slug": "monotonic-deque", "type": "concept", "tags": ["dp", "queue"],
        "lang": "th", "body": "คิวที่เก็บค่าเรียงลง ใช้กับ sliding window"}


class WriteTests(unittest.TestCase):
    def test_a_rendered_page_carries_every_required_frontmatter_field(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            build(root, [])
            page = Vault(root).render(NOTE, today="2026-09-18")
            for field in ("name: monotonic-deque", "type: concept",
                          "tags: [dp, queue]", "lang: th", "sources: 1",
                          "date: 2026-09-18"):
                self.assertIn(field, page)
            self.assertTrue(page.startswith("---\n"))

    def test_saving_writes_the_page_updates_the_index_and_appends_the_log(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            build(root, [("dp-note", "concept", ["dp"], "เก่า")])
            vault = Vault(root)
            written = vault.save(NOTE, "จดเทคนิคจากโจทย์ sliding window")

            self.assertTrue(written.exists())
            self.assertEqual(written.parent, root / "wiki")
            index = (root / "index.md").read_text(encoding="utf-8")
            self.assertIn("[[monotonic-deque]]", index)
            self.assertIn("[[dp-note]]", index)
            log = (root / "log.md").read_text(encoding="utf-8")
            self.assertIn("จดเทคนิคจากโจทย์ sliding window", log)

    def test_the_log_is_only_ever_appended_to(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            build(root, [])
            vault = Vault(root)
            vault.save(NOTE, "ครั้งแรก")
            first = (root / "log.md").read_text(encoding="utf-8")
            vault.save({**NOTE, "slug": "dp-on-trees"}, "ครั้งที่สอง")
            second = (root / "log.md").read_text(encoding="utf-8")
            self.assertTrue(second.startswith(first))
            self.assertIn("ครั้งที่สอง", second)

    def test_a_slug_that_escapes_the_wiki_folder_is_refused(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            build(root, [])
            for bad in ("../escape", "..\\escape", "sub/dir", "C:/Windows/evil"):
                with self.assertRaises(VaultError):
                    Vault(root).save({**NOTE, "slug": bad}, "ไม่ควรเขียน")

    def test_raw_is_never_written(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            build(root, [])
            (root / "raw" / "source.txt").write_text("ของเดิม", encoding="utf-8")
            before = sorted(p.name for p in (root / "raw").rglob("*"))
            Vault(root).save(NOTE, "เขียนหน้าใหม่")
            after = sorted(p.name for p in (root / "raw").rglob("*"))
            self.assertEqual(before, after)
            self.assertEqual((root / "raw" / "source.txt").read_text(encoding="utf-8"),
                             "ของเดิม")

    def test_saving_over_an_existing_page_bumps_its_source_count(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            build(root, [])
            vault = Vault(root)
            vault.save(NOTE, "ครั้งแรก")
            vault.save(NOTE, "ปรับปรุง")
            page = (root / "wiki" / "monotonic-deque.md").read_text(encoding="utf-8")
            self.assertIn("sources: 2", page)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m unittest discover -s tests -p "test_vault.py"`
Expected: FAIL with `AttributeError: 'Vault' object has no attribute 'render'`

- [ ] **Step 3: Add the write side to `vault.py`**

Add `from datetime import date` to the imports, and these constants beside `STYLE_GUIDE`:

```python
SLUG = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
TYPE_ORDER = ("source", "concept", "entity", "synthesis", "query")
TYPE_HEADING = {"source": "Sources", "concept": "Concepts", "entity": "Entities",
                "synthesis": "Syntheses", "query": "Queries"}
```

Then append to `class Vault`:

```python
    def _destination(self, slug: str) -> Path:
        if not isinstance(slug, str) or not SLUG.fullmatch(slug) or len(slug) > 120:
            raise VaultError("slug ต้องเป็น kebab-case และห้ามมีเส้นทางไฟล์")
        path = (self.wiki / f"{slug}.md").resolve()
        if path.parent != self.wiki.resolve():
            raise VaultError("หน้า wiki ต้องอยู่ในโฟลเดอร์ wiki เท่านั้น")
        return path

    def render(self, note: dict, *, sources: int = 1, today: str | None = None) -> str:
        today = today or date.today().isoformat()
        tags = ", ".join(note.get("tags") or [])
        return (f"---\nname: {note['slug']}\ntype: {note['type']}\n"
                f"tags: [{tags}]\nlang: {note['lang']}\nsources: {sources}\n"
                f"date: {today}\n---\n\n{note['body'].strip()}\n")

    def save(self, note: dict, summary: str, *, today: str | None = None) -> Path:
        """Write one page, then refresh index.md and append to log.md.

        The user has already approved this page in the desktop UI; the checks here
        are against a malformed slug, not against the user's intent.
        """
        destination = self._destination(note["slug"])
        existed = destination.exists()
        sources = 1
        if existed:
            previous = destination.read_text(encoding="utf-8")
            match = re.search(r"^sources:\s*(\d+)", previous, re.MULTILINE)
            sources = int(match.group(1)) + 1 if match else 2
        destination.write_text(self.render(note, sources=sources, today=today),
                               encoding="utf-8")
        self._cache = None  # the catalogue is stale now
        self.rebuild_index(today=today)
        self.append_log("update" if existed else "ingest", note["slug"], summary,
                        today=today)
        return destination

    def rebuild_index(self, today: str | None = None):
        today = today or date.today().isoformat()
        entries = self.catalogue()
        lines = [f"# Wiki Index\nLast updated: {today} | Total pages: {len(entries)}\n"]
        for kind in TYPE_ORDER:
            group = [e for e in entries if e["type"] == kind]
            if not group:
                continue
            lines.append(f"## {TYPE_HEADING[kind]} ({len(group)})")
            lines += [f"- [[{e['slug']}]]" for e in group]
            lines.append("")
        self.index.write_text("\n".join(lines), encoding="utf-8")

    def append_log(self, action: str, title: str, description: str,
                   today: str | None = None):
        today = today or date.today().isoformat()
        if action not in ("ingest", "query", "lint", "update"):
            raise VaultError("action ของ log ไม่ถูกต้อง")
        with self.log.open("a", encoding="utf-8") as handle:
            handle.write(f"\n## [{today}] {action} | {title}\n{description}\n")
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m unittest discover -s tests -p "test_vault.py"`
Expected: 12 tests, `OK`

- [ ] **Step 5: Run the full suite and commit**

Run: `python -m unittest discover -s tests` — expected 138 tests, `OK`

```bash
git add vault.py tests/test_vault.py
git commit -m "feat: study vault page write, index rebuild and append-only log"
```

---

### Task 7: Route a mentor turn through Claude

**Files:**
- Modify: `claude_brain.py`
- Modify: `engine.py`
- Test: `tests/test_mentor.py`

**Interfaces:**
- Consumes: `mentor.MENTOR_SCHEMA`, `mentor.SYSTEM`, `mentor.decode`, the existing `claude_brain._request`
- Produces:
  - `claude_brain.ask_mentor(model: str, text: str, *, cancelled=None) -> mentor.MentorReply`
  - `engine.ask_mentor(model: str, text: str, **kwargs) -> mentor.MentorReply`

`engine.ask_mentor` raises `BrainError` for a Gemini model: mentor mode is Claude-only, because the ladder depends on the structured reply this schema produces.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_mentor.py`:

```python
class RoutingTests(unittest.TestCase):
    def test_a_mentor_turn_asks_for_the_mentor_schema_and_higher_effort(self):
        import claude_brain
        captured = {}

        def fake_request(model, system, schema, content, cancelled=None, effort="low"):
            captured.update(model=model, system=system, schema=schema,
                            content=content, effort=effort)
            return {"reply": "ลองดู n ก่อน", "rung": 1}

        with patch.object(claude_brain, "_request", fake_request):
            decoded = claude_brain.ask_mentor("sonnet", "ข้อนี้ทำไงดี")

        self.assertEqual(decoded.text, "ลองดู n ก่อน")
        self.assertEqual(captured["schema"], mentor.MENTOR_SCHEMA)
        self.assertNotIn("actions", captured["schema"]["properties"])
        self.assertIn("POSN", captured["system"])
        self.assertEqual(captured["effort"], "medium")
        self.assertEqual(captured["content"], [{"type": "text", "text": "ข้อนี้ทำไงดี"}])

    def test_a_malformed_mentor_reply_is_refused_not_displayed(self):
        import claude_brain
        with patch.object(claude_brain, "_request",
                          lambda *a, **k: {"reply": "x", "rung": 99}):
            with self.assertRaises(mentor.MentorError):
                claude_brain.ask_mentor("sonnet", "ข้อนี้ทำไงดี")

    def test_mentor_mode_refuses_a_gemini_model(self):
        import engine
        from brain import BrainError
        with self.assertRaises(BrainError):
            engine.ask_mentor("gemini-3.8-flash", "ข้อนี้ทำไงดี")
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m unittest discover -s tests -p "test_mentor.py"`
Expected: FAIL with `AttributeError: module 'claude_brain' has no attribute 'ask_mentor'`

- [ ] **Step 3: Add `ask_mentor` to `claude_brain.py`**

Add `import mentor` to the imports.

Change the `_request` signature from:

```python
def _request(model, system, schema, content, cancelled=None):
```

to:

```python
def _request(model, system, schema, content, cancelled=None, effort="low"):
```

and inside it replace:

```python
        if model != "haiku":
            args += ["--effort", "low"]
```

with:

```python
        if model != "haiku":
            args += ["--effort", effort]
```

Then append to the module:

```python
def ask_mentor(model, text, *, cancelled=None):
    """One coaching turn. Mentor mode has no PC actions and no cloud speech."""
    if not isinstance(text, str) or not text.strip() or len(text) > MAX_INPUT:
        raise BrainError(f"Enter between 1 and {MAX_INPUT:,} characters.")
    # Coaching needs the reasoning a one-line chat reply does not.
    data = _request(model, mentor.SYSTEM, mentor.MENTOR_SCHEMA,
                    [{"type": "text", "text": text}], cancelled, effort="medium")
    return mentor.decode(data)
```

- [ ] **Step 4: Add `ask_mentor` to `engine.py`**

```python
def ask_mentor(model, text, **kwargs):
    """Mentor mode is Claude-only: the ladder needs this structured reply."""
    if provider(model) != "claude":
        raise BrainError("โหมดติวเตอร์ใช้ได้กับโมเดล Claude เท่านั้น เช่น sonnet")
    return claude_brain.ask_mentor(model, text, **kwargs)
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python -m unittest discover -s tests -p "test_mentor.py"`
Expected: 32 tests, `OK`

- [ ] **Step 6: Run the full suite**

Run: `python -m unittest discover -s tests`
Expected: 141 tests, `OK`

`tests/test_claude_brain.py` exercises `_request` indirectly. If a new `effort` parameter breaks one of its assertions, fix the test to expect `--effort low` for the chat path — that behaviour is unchanged and the test is asserting on it.

- [ ] **Step 7: Commit**

```bash
git add claude_brain.py engine.py tests/test_mentor.py
git commit -m "feat: route mentor turns through Claude at medium effort"
```

---

### Task 8: Mentor mode in the desktop application

**Files:**
- Modify: `local_store.py`
- Modify: `app.py`
- Test: `tests/test_ui.py`

**Interfaces:**
- Consumes: everything from Tasks 1–7
- Produces:
  - `local_store.LocalStore.save_settings(model: str, mentor: bool = False)`
  - `JarvisApp.mentor_mode: bool`
  - `JarvisApp.study: vault.Vault | None`
  - `JarvisApp.mentor_turn(prompt: str)`
  - `JarvisApp.offer_note(note: dict)`
  - `JarvisApp.toggle_mentor_mode()`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_ui.py`, above `if __name__`:

```python
class MentorModeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.app = JarvisApp(store=LocalStore(Path(self.temp.name)))
        self.app.withdraw()

    def tearDown(self):
        self.app.close()
        self.temp.cleanup()

    def test_the_ladder_is_clamped_before_anything_is_shown(self):
        import mentor
        a = self.app
        a.mentor_mode = True
        problem = a.memory.upsert_problem("knapsack-th", "Knapsack", topic="dp")
        a.memory.set_rung(problem, 1)
        a.memory.add_attempt(problem, "แนวคิด: ลองทุกกรณี")   # no verdict

        reply = mentor.MentorReply("เฉลยเต็ม ๆ", 5,
                                   {"slug": "knapsack-th", "title": "Knapsack",
                                    "topic": "dp", "status": "working"}, [], None)
        with patch("app.ask_mentor", return_value=reply):
            a.mentor_turn("ขอโค้ดเลย")

        self.assertEqual(a.memory.problem("knapsack-th")["rung"], 2)
        self.assertIn("[ขั้น 2/5", a.bubbles[-1][1].cget("text"))

    def test_the_override_records_a_give_up_and_opens_the_last_rung(self):
        import mentor
        a = self.app
        a.mentor_mode = True
        problem = a.memory.upsert_problem("knapsack-th", "Knapsack", topic="dp")
        a.memory.add_attempt(problem, "int main(){}", verdict="WA")

        reply = mentor.MentorReply("นี่คือเฉลย", 5,
                                   {"slug": "knapsack-th", "title": "Knapsack",
                                    "topic": "dp", "status": "working"}, [], None)
        with patch("app.ask_mentor", return_value=reply):
            a.mentor_turn("เปิดเฉลย")

        row = a.memory.problem("knapsack-th")
        self.assertEqual(row["status"], "given-up")
        self.assertEqual(row["rung"], 5)

    def test_failure_tags_are_stored_and_reach_the_profile(self):
        import mentor
        a = self.app
        a.mentor_mode = True
        problem = a.memory.upsert_problem("knapsack-th", "Knapsack", topic="dp")
        a.memory.add_attempt(problem, "int main(){}", verdict="WA")

        reply = mentor.MentorReply("state ผิด", 1,
                                   {"slug": "knapsack-th", "title": "Knapsack",
                                    "topic": "dp", "status": "working"},
                                   [{"tag": "wrong-state", "note": None}], None)
        with patch("app.ask_mentor", return_value=reply):
            a.mentor_turn("ลองแล้วไม่ผ่าน")

        self.assertEqual(a.memory.profile("dp"), [("wrong-state", 1)])

    def test_a_mentor_turn_never_produces_a_pc_proposal(self):
        import mentor
        a = self.app
        a.mentor_mode = True
        reply = mentor.MentorReply("ลองอ่านโจทย์อีกที", 0, None, [], None)
        with patch("app.ask_mentor", return_value=reply):
            a.mentor_turn("เปิด spotify ให้หน่อย")
        self.assertEqual(a.proposals, [])

    def test_a_model_error_is_shown_and_does_not_break_the_window(self):
        import mentor
        a = self.app
        a.mentor_mode = True
        with patch("app.ask_mentor", side_effect=mentor.MentorError("คำตอบว่าง")):
            a.mentor_turn("ข้อนี้ทำไงดี")
        self.assertIn("คำตอบว่าง", a.bubbles[-1][1].cget("text"))

    def test_mentor_mode_survives_a_restart(self):
        a = self.app
        a.mentor_mode = True
        a.store.save_settings(a.model, mentor=True)
        a.close()
        self.app = JarvisApp(store=LocalStore(Path(self.temp.name)))
        self.app.withdraw()
        self.assertTrue(self.app.mentor_mode)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m unittest tests.test_ui.MentorModeTests`
Expected: FAIL with `AttributeError: 'JarvisApp' object has no attribute 'mentor_turn'`

- [ ] **Step 3: Persist the flag in `local_store.py`**

Replace `save_settings`:

```python
    def save_settings(self, model: str, mentor: bool = False):
        _write_atomic(self.settings_path, json.dumps(
            {"model": model, "language": "th", "mentor": bool(mentor)},
            ensure_ascii=False).encode("utf-8"))
```

`read_settings` needs no change; it already returns the parsed dict.

- [ ] **Step 4: Wire the mentor turn into `app.py`**

Add to the imports:

```python
import mentor
from engine import ask_mentor
from vault import Vault, VaultError
```

Add the module constant beside `BASE`:

```python
STUDY_VAULT = Path(r"D:\Jarvis\Study")
```

In `__init__`, after `self.history = self.memory.recent_turns()`:

```python
        self.mentor_mode = self.store.read_settings().get("mentor") is True
        try:
            self.study = Vault(STUDY_VAULT)
            self.study.catalogue()
        except (VaultError, OSError):
            self.study = None  # mentor mode still works, just without wiki context
```

Add these two methods next to `send`:

```python
    def mentor_turn(self, prompt: str):
        """One coaching turn: gather in Python, ask once, clamp, then store."""
        problem = self.memory.current_problem()
        attempts = self.memory.attempts(problem["id"]) if problem else []
        topic = (problem or {}).get("topic") or ""
        profile = self.memory.profile(topic) if topic else []
        tags = [tag for tag, _ in profile]
        similar = self.memory.similar_problems(topic, tags) if topic else []
        style_guide = self.study.style_guide() if self.study else ""
        pages = self.study.select(topic, tags) if (self.study and topic) else []

        override = mentor.is_override(prompt)
        stored = (problem or {}).get("rung", 0)
        has_attempt = bool(attempts)
        has_verdict = any(a.get("verdict") for a in attempts)
        ceiling = mentor.MAX_RUNG if override else mentor.allowed_rung(
            stored, mentor.MAX_RUNG, has_attempt=has_attempt, has_verdict=has_verdict)

        text = mentor.build_prompt(
            allowed=ceiling, problem=problem, attempts=attempts, profile=profile,
            similar=similar, style_guide=style_guide, pages=pages,
            turns=self.history[-8:])

        try:
            reply = ask_mentor(self.model, text)
        except (BrainError, mentor.MentorError) as exc:
            self.add_message("ERROR", str(exc))
            return

        granted = mentor.MAX_RUNG if override else mentor.allowed_rung(
            stored, reply.rung, has_attempt=has_attempt, has_verdict=has_verdict)

        if reply.problem:
            problem_id = self.memory.upsert_problem(
                reply.problem["slug"], reply.problem["title"],
                topic=reply.problem.get("topic"),
                status="given-up" if override else reply.problem.get("status", "working"))
            self.memory.set_rung(problem_id, granted)
            if reply.failures and attempts:
                self.memory.add_failures(attempts[-1]["id"], reply.failures)

        shown = f"{mentor.label(granted)} {reply.text}"
        self.remember("user", prompt)
        self.remember("model", shown)
        self.history = self.history[-16:]
        self.add_message("JARVIS", shown)
        if reply.note and self.study:
            self.offer_note(reply.note)

    def offer_note(self, note: dict):
        """Ask before writing to the wiki, then write automatically and log it."""
        preview = self.study.render(note)
        if not messagebox.askyesno(
                tr("Save to wiki?"),
                f"{note['slug']} ({note['type']})\n\n{preview[:600]}", parent=self):
            return
        try:
            written = self.study.save(note, note["body"][:120])
            self.add_message("STATUS", tr("Saved to wiki: ") + str(written))
        except (VaultError, OSError) as exc:
            self.add_message("ERROR", tr("Could not save to wiki: ") + str(exc))
```

In `send`, route mentor turns before the existing chat path. Find the line
`history, key, model = list(self.history), self.key, self.model` and insert immediately above it:

```python
        if self.mentor_mode:
            self.busy = False
            self.send_button.configure(state="normal")
            self.mentor_turn(prompt)
            self.set_status("Ready • Microphone off")
            return
```

Add the sidebar toggle where the other sidebar controls are packed:

```python
        self.mentor_switch = ctk.CTkSwitch(
            self.sidebar, text=tr("Mentor mode (POSN)"),
            command=self.toggle_mentor_mode)
        self.mentor_switch.pack(anchor="w", padx=16, pady=(4, 0))
        if self.mentor_mode:
            self.mentor_switch.select()
```

And its handler, beside `toggle_compact`:

```python
    def toggle_mentor_mode(self):
        self.mentor_mode = bool(self.mentor_switch.get())
        if self.mentor_mode:
            self.auto_speak.set(False)  # competitive programming is a typed activity
        try:
            self.store.save_settings(self.model, mentor=self.mentor_mode)
        except StorageError as exc:
            self.add_message("ERROR", str(exc))
```

Finally, find the `self.store.save_settings(new_model)` call in the settings dialog and change it to `self.store.save_settings(new_model, mentor=self.mentor_mode)`, so saving a model does not silently clear the flag.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python -m unittest tests.test_ui.MentorModeTests`
Expected: 6 tests, `OK`

- [ ] **Step 6: Run the full suite**

Run: `python -m unittest discover -s tests`
Expected: 147 tests, `OK`

- [ ] **Step 7: Start the application by hand**

Run: `python app.py`

Confirm: the window opens, the sidebar shows the mentor switch, toggling it and restarting keeps it on, and the status line still reads `Claude Code subscription • sonnet`. Close the window. This is the one check the suite cannot make.

- [ ] **Step 8: Commit**

```bash
git add app.py local_store.py tests/test_ui.py
git commit -m "feat: mentor mode toggle, coaching turn and wiki save approval"
```

---

### Task 9: Update the project documents

**Files:**
- Modify: `README.md`
- Modify: `VERIFICATION.md`

- [ ] **Step 1: Add a mentor-mode section to `README.md`**

Document, in the existing voice of the file: what mentor mode is; the six rungs and their gates; the `เปิดเฉลย` override and that it records a give-up; where the study vault lives; that mentor mode is typed and proposes no PC actions; and that `data/jarvis.db` now holds all conversation history.

- [ ] **Step 2: Update `VERIFICATION.md`**

Change the test count to 147 and add to **Passed**:

```markdown
- Conversation history survives a restart, and starting a new chat is not undone
  by one. History lives in `data/jarvis.db`; the sixteen-message cap now governs
  only what is sent to the model.
- The hint ladder is enforced in Python: a model reply proposing rung 5 against a
  stored rung of 1 is clamped to 2, rung 1 is refused without an attempt, and rung
  4 is refused until an attempt carries a verdict.
- Mentor replies cannot carry PC actions; the schema has no actions key.
- Wiki writes stay inside `wiki/`, `log.md` is only ever appended to, and `raw/`
  is never written.
```

Add to **Requires your desktop test**:

```markdown
- No live mentor request was made. `claude_brain.ask_mentor` is exercised only
  against mocks, as the chat path already is.
- The study vault at `D:\Jarvis\Study` was created by hand; page writes against a
  real Obsidian vault have not been observed outside temporary directories.
```

- [ ] **Step 3: Commit**

```bash
git add README.md VERIFICATION.md
git commit -m "docs: record mentor mode and persistent history"
```

---

## Self-Review

**Spec coverage.** §5.1 memory and §5.2 the persistence patch shipped before this plan. §5.3 mentor mode is Task 8. §5.3.1 which problem is current is `memory.current_problem()` in Task 1 plus the slug handling in Task 8. §5.4 the ladder is Tasks 1 and 8. §5.5 the schema is Task 2. §5.6 reading (b) is `Vault.style_guide` in Task 5, injected in Task 4. §5.7 reading (a) is `render_profile` in Task 4 over `Memory.profile`. §5.8 the never-override frame is `NOTE_FRAME` in Task 3. §6 the vault is Tasks 5 and 6, its layout created by hand in Task 5 Step 1. §6.1 writes are Task 6, with the approval dialog in Task 8. §6.2 the catalogue is Task 5. §7 the data flow is `mentor_turn` in Task 8. §8 the budget is Task 4. §9 the tests are distributed across every task.

**One spec item is deliberately not implemented, and is called out rather than silently dropped.** §5.6 says that on the first mentor session Jarvis interviews the user and drafts the `style-guide` page. No task builds that interview. The feature works without it — an absent style guide yields an empty string and the mentor simply does not adapt its voice — and it is a conversation-design problem better solved after the ladder has met real problems. Write the page by hand in Obsidian to get reading (b) working immediately, or schedule the interview as separate work.

**Placeholder scan.** No "TBD", no "add error handling" without the code, no "similar to Task N". Every code step carries its code.

**Type consistency.** `mentor.allowed_rung(stored, proposed, *, has_attempt, has_verdict)` is called with those keyword names in Task 8. `mentor.MentorReply` fields are `text, rung, problem, failures, note`, and Task 8's mocks construct them positionally in that order. `Vault.select(topic, tags, limit, budget)` and `Vault.style_guide(budget)` match their Task 8 call sites. `Memory.attempts` returns dicts carrying `id` and `verdict`, both of which Task 8 reads. `Vault.save(note, summary)` returns a `Path`, which Task 8 prints. `_request(model, system, schema, content, cancelled=None, effort="low")` keeps its existing positional order, so the two existing call sites in `ask` and `ask_screen` are unaffected.

**Known limitation in Task 8, accepted for a first version.** `mentor_turn` runs inline on the Tk thread, so a mentor turn cannot be stopped mid-flight the way a chat turn can, and the window will freeze for the length of the call. The chat path runs in a worker thread with a generation counter and an event queue. Moving `mentor_turn` onto that same machinery is the obvious next change, and should be done before this is used under time pressure.
