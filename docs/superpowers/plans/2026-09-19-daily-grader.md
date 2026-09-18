# Daily Problems, Grader and Difficulty Ramp Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Victor serves one warm-up and one main POSN problem every day, grades the user's C++ locally with a measured verdict, and raises difficulty from Camp 1 to Camp 2 based on results.

**Architecture:** A checked-in problem bank (`problems/`) holds offline-verified Camp-1 problems with tests and a curated list of real Camp-2 archive problems. `bank.py` loads and validates it, `grader.py` compiles and judges `sol.cpp`, `daily.py` owns the ramp rules and the daily pick, and `app.py` shows a Today card with Grade buttons. Nothing at runtime asks Claude to generate, select or grade.

**Tech Stack:** Python 3.11 stdlib (`sqlite3`, `subprocess`, `json`, `random`, `unittest`), CustomTkinter (existing), MSYS2 g++ 15.2 (`C:\msys64\ucrt64\bin\g++.exe`).

**Spec:** `docs/superpowers/specs/2026-09-19-daily-grader-design.md`

## Global Constraints

- Run tests with `python -m unittest discover -s tests` from the `Jarvis/` directory. The suite has 172 tests today; every task ends with the whole suite green.
- No new third-party dependencies.
- Model output never selects a path, a command or a level (spec 7.1).
- Daily folder paths are built only from the date and the fixed names `main` / `warmup` (spec 6, step 4).
- Verdicts are exactly `memory.VERDICTS` = `("AC", "WA", "TLE", "RE", "CE", "unsubmitted")`.
- Levels: 1–2 Camp 1, 3–5 Camp 2 (spec 4.2).
- Compile flags: `-std=c++17 -O2 -static -Wl,--stack,268435456`. `-static` because the MSYS2 runtime DLLs are not on PATH (the user's PATH entry is `C:\msys64\ucrt64\bin.` with a trailing dot), so a dynamically linked `sol.exe` cannot start; the big stack because Windows defaults to 1 MB.
- Tests never write to `D:\Jarvis\Study`. `VictorApp(store=...)` in tests must derive its daily root from the temp store.
- Commits end with `Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>`.
- Work on branch `daily-grader` (already created, spec committed as `8b61949`).

## File Structure

| File | Status | Responsibility |
|------|--------|----------------|
| `memory.py` | modify | `CE` verdict, `daily` table, meta get/set, served sources, weak topics, daily rows |
| `grader.py` | create | find g++, compile, run with time limit, judge → `Result` |
| `bank.py` | create | load and validate `problems/` into `Entry` objects |
| `tools/make_problem.py` | create | offline: ask Claude for a candidate, verify ref vs brute, write bank entry |
| `problems/camp1/<slug>/` | create | generated Camp-1 bank (~20 problems) |
| `problems/archive.json` | create | curated Camp-2 real problems (~30) |
| `daily.py` | create | ramp rules (`next_level`, `update_level`), pick, daily folders, `ensure_today` |
| `app.py` | modify | Today card, Grade button, `ตรวจ`, grade worker, date-change refresh |
| `tests/test_memory.py` | modify | daily-store tests |
| `tests/test_grader.py` | create | verdict tests with tiny C++ fixtures |
| `tests/test_bank.py` | create | loader validation + committed-bank content checks |
| `tests/test_make_problem.py` | create | verifier accepts agreeing, rejects disagreeing |
| `tests/test_daily.py` | create | ramp and daily-serve tests |
| `tests/test_ui.py` | modify | Today card and grade flow in the real app |
| `README.md`, `VERIFICATION.md` | modify | document the feature and the live check |

---

### Task 1: Memory support for the daily set

**Files:**
- Modify: `memory.py` (constants at lines 18–26, `SCHEMA`, new methods at end of `Memory`)
- Test: `tests/test_memory.py`

**Interfaces:**
- Produces:
  - `memory.VERDICTS` includes `"CE"`; `memory.DAILY_ROLES = ("main", "warmup")`
  - `Memory.get_meta(key: str, default: str | None = None) -> str | None`
  - `Memory.set_meta(key: str, value) -> None` (stores `str(value)`)
  - `Memory.served_sources() -> set[str]`
  - `Memory.weak_topics(limit: int = 3) -> list[str]`
  - `Memory.add_daily(day: str, role: str, problem_id: int, level: int) -> None` (replaces an existing `(day, role)`)
  - `Memory.daily_rows(day: str | None = None) -> list[dict]` with keys `day, role, level, problem_id, slug, title, source, status, rung, ac (bool), graded (bool)`, ordered by day, then `warmup` before `main`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_memory.py`:

```python
class DailyStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.memory = Memory(Path(self.temp.name))

    def tearDown(self):
        self.memory.close()
        self.temp.cleanup()

    def test_compile_error_is_a_verdict(self):
        pid = self.memory.upsert_problem("a-plus-b", "A+B")
        self.memory.add_attempt(pid, "int main( {", verdict="CE")
        self.assertEqual(self.memory.attempts(pid)[0]["verdict"], "CE")

    def test_meta_round_trip(self):
        m = self.memory
        self.assertIsNone(m.get_meta("level"))
        self.assertEqual(m.get_meta("level", "1"), "1")
        m.set_meta("level", 3)
        self.assertEqual(m.get_meta("level"), "3")

    def test_daily_rows_report_graded_and_ac(self):
        m = self.memory
        a = m.upsert_problem("sum", "Sum", topic="implementation", source="camp1/sum")
        b = m.upsert_problem("gcd", "GCD", topic="math", source="camp1/gcd")
        m.add_daily("2026-09-20", "main", a, 1)
        m.add_daily("2026-09-20", "warmup", b, 1)
        m.add_attempt(a, "code", verdict="WA")
        m.add_attempt(a, "code", verdict="AC")
        m.add_attempt(b, "just an idea")
        rows = m.daily_rows("2026-09-20")
        self.assertEqual([r["role"] for r in rows], ["warmup", "main"])
        self.assertEqual((rows[1]["ac"], rows[1]["graded"]), (True, True))
        self.assertEqual((rows[0]["ac"], rows[0]["graded"]), (False, False))
        self.assertEqual(rows[1]["source"], "camp1/sum")
        self.assertEqual(m.daily_rows("2026-09-21"), [])
        self.assertEqual(len(m.daily_rows()), 2)

    def test_add_daily_replaces_the_same_day_and_role(self):
        m = self.memory
        a = m.upsert_problem("sum", "Sum", source="camp1/sum")
        m.add_daily("2026-09-20", "main", a, 1)
        m.add_daily("2026-09-20", "main", a, 1)
        self.assertEqual(len(m.daily_rows("2026-09-20")), 1)

    def test_add_daily_rejects_an_unknown_role(self):
        a = self.memory.upsert_problem("sum", "Sum")
        with self.assertRaises(MemoryError):
            self.memory.add_daily("2026-09-20", "bonus", a, 1)

    def test_served_sources_ignore_problems_without_a_source(self):
        m = self.memory
        m.upsert_problem("sum", "Sum", source="camp1/sum")
        m.upsert_problem("chat-problem", "Something from chat")
        self.assertEqual(m.served_sources(), {"camp1/sum"})

    def test_weak_topics_rank_topics_by_failures(self):
        m = self.memory
        dp = m.upsert_problem("knap", "Knap", topic="dp")
        gr = m.upsert_problem("bfs", "BFS", topic="graph")
        m.add_failures(m.add_attempt(dp, "x"), [{"tag": "wrong-state"}, {"tag": "off-by-one"}])
        m.add_failures(m.add_attempt(gr, "y"), [{"tag": "off-by-one"}])
        self.assertEqual(m.weak_topics(), ["dp", "graph"])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m unittest tests.test_memory -v`
Expected: FAIL / ERROR — `CE` rejected by `_one_of`, `AttributeError: 'Memory' object has no attribute 'get_meta'`.

- [ ] **Step 3: Implement**

In `memory.py`, change the constants:

```python
VERDICTS = ("AC", "WA", "TLE", "RE", "CE", "unsubmitted")
DAILY_ROLES = ("main", "warmup")
```

Add to `SCHEMA`, before the `CREATE INDEX` lines:

```sql
CREATE TABLE IF NOT EXISTS daily (
  day TEXT NOT NULL,
  role TEXT NOT NULL,
  problem_id INTEGER NOT NULL REFERENCES problem(id),
  level INTEGER NOT NULL,
  PRIMARY KEY (day, role));
```

`CREATE TABLE IF NOT EXISTS` adds the table to existing databases on the next start; no `user_version` bump is needed because nothing existing changes shape.

Append to the `Memory` class:

```python
    # ---------- meta and the daily set ----------

    def get_meta(self, key: str, default: str | None = None) -> str | None:
        row = self.db.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
        return row[0] if row else default

    def set_meta(self, key: str, value):
        with self.db:
            self.db.execute("INSERT INTO meta (key, value) VALUES (?, ?)"
                            " ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                            (key, str(value)))

    def served_sources(self) -> set[str]:
        """Bank ids already handed out, so the daily pick never repeats one."""
        rows = self.db.execute("SELECT source FROM problem WHERE source IS NOT NULL").fetchall()
        return {r[0] for r in rows}

    def weak_topics(self, limit: int = 3) -> list[str]:
        """Topics ranked by how many failure tags the user has collected in them."""
        rows = self.db.execute(
            "SELECT problem.topic, COUNT(*) AS n FROM failure"
            " JOIN attempt ON attempt.id = failure.attempt_id"
            " JOIN problem ON problem.id = attempt.problem_id"
            " WHERE problem.topic IS NOT NULL"
            " GROUP BY problem.topic ORDER BY n DESC, problem.topic LIMIT ?",
            (limit,)).fetchall()
        return [r[0] for r in rows]

    def add_daily(self, day: str, role: str, problem_id: int, level: int):
        _one_of(role, DAILY_ROLES, "role")
        with self.db:
            # REPLACE: a serve interrupted halfway can simply be run again.
            self.db.execute("INSERT OR REPLACE INTO daily (day, role, problem_id, level)"
                            " VALUES (?, ?, ?, ?)", (day, role, problem_id, level))

    def daily_rows(self, day: str | None = None) -> list[dict]:
        """Served daily problems, oldest first (warm-up before main), with outcomes."""
        where = " WHERE daily.day = ?" if day else ""
        rows = self.db.execute(
            "SELECT daily.day, daily.role, daily.level, problem.id AS problem_id,"
            " problem.slug, problem.title, problem.source, problem.status, problem.rung,"
            " EXISTS(SELECT 1 FROM attempt WHERE attempt.problem_id = problem.id"
            "        AND attempt.verdict = 'AC') AS ac,"
            " EXISTS(SELECT 1 FROM attempt WHERE attempt.problem_id = problem.id"
            "        AND attempt.verdict IS NOT NULL) AS graded"
            " FROM daily JOIN problem ON problem.id = daily.problem_id"
            + where + " ORDER BY daily.day, daily.role DESC",
            (day,) if day else ()).fetchall()
        return [dict(r, ac=bool(r["ac"]), graded=bool(r["graded"])) for r in rows]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m unittest tests.test_memory -v` → PASS.
Run: `python -m unittest discover -s tests` → all green.

- [ ] **Step 5: Commit**

```bash
git add memory.py tests/test_memory.py
git commit -m "feat: store daily problems, meta values and CE verdicts"
```

---

### Task 2: Grader

**Files:**
- Create: `grader.py`
- Test: `tests/test_grader.py`

**Interfaces:**
- Produces:
  - `grader.GraderError(RuntimeError)`
  - `grader.Run(code: int | None, out: str, elapsed: float)` — `code is None` means killed for time
  - `grader.Result(verdict: str, passed: int, total: int, detail: str)`
  - `grader.find_compiler() -> str`
  - `grader.run_program(args: list, stdin_text: str, timeout: float, *, cwd=None, cancelled=lambda: False, merge_stderr=False) -> Run`
  - `grader.compile_source(source: Path, exe: Path, *, cancelled=lambda: False) -> str | None` — `None` on success, else error text
  - `grader.grade(folder: Path, tests, time_limit: float, *, show_input=False, cancelled=lambda: False) -> Result` — `tests` is a sequence of `(input, expected)` where each side is a `str` or a `Path`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_grader.py`:

```python
from pathlib import Path
import tempfile
import unittest

import grader

try:
    grader.find_compiler()
    HAVE_GXX = True
except grader.GraderError:
    HAVE_GXX = False

ECHO_SUM = """#include <bits/stdc++.h>
int main(){long long a,b;std::cin>>a>>b;std::cout<<a+b<<"\\n";}"""
TESTS = [("1 2\n", "3\n"), ("5 5\n", "10\n"), ("7 8\n", "15")]


@unittest.skipUnless(HAVE_GXX, "g++ not found")
class GraderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.folder = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def judge(self, source, tests=TESTS, time_limit=1.0, **kw):
        (self.folder / "sol.cpp").write_text(source, encoding="utf-8")
        return grader.grade(self.folder, tests, time_limit, **kw)

    def test_correct_solution_is_accepted(self):
        result = self.judge(ECHO_SUM)
        self.assertEqual(result, grader.Result("AC", 3, 3, "AC 3/3"))

    def test_first_failing_test_is_reported(self):
        wrong_on_five = ECHO_SUM.replace("a+b", "(a==5?0:a+b)")
        result = self.judge(wrong_on_five)
        self.assertEqual((result.verdict, result.passed), ("WA", 1))
        self.assertTrue(result.detail.startswith("WA on test 2/3"))

    def test_main_problem_hides_the_failing_input(self):
        wrong = ECHO_SUM.replace("a+b", "a-b")
        self.assertNotIn("1 2", self.judge(wrong).detail)
        self.assertIn("1 2", self.judge(wrong, show_input=True).detail)

    def test_infinite_loop_is_time_limit_exceeded(self):
        result = self.judge("int main(){volatile int x=0;while(true){x++;}}", time_limit=0.2)
        self.assertEqual(result.verdict, "TLE")

    def test_nonzero_exit_is_runtime_error(self):
        self.assertEqual(self.judge("int main(){return 1;}").verdict, "RE")

    def test_syntax_error_is_compile_error(self):
        result = self.judge("int main( {")
        self.assertEqual(result.verdict, "CE")
        self.assertTrue(result.detail)

    def test_tests_may_be_files(self):
        given, expected = self.folder / "01.in", self.folder / "01.out"
        given.write_text("2 2\n", encoding="utf-8")
        expected.write_text("4\n", encoding="utf-8")
        self.assertEqual(self.judge(ECHO_SUM, tests=[(given, expected)]).verdict, "AC")

    def test_deep_recursion_does_not_crash(self):
        deep = """#include <bits/stdc++.h>
int f(int n){return n==0?0:1+f(n-1);}
int main(){std::cout<<f(1000000)<<"\\n";}"""
        self.assertEqual(self.judge(deep, tests=[("", "1000000")]).verdict, "AC")

    def test_cancel_stops_grading(self):
        with self.assertRaises(grader.GraderError):
            self.judge(ECHO_SUM, cancelled=lambda: True)


class MissingSourceTests(unittest.TestCase):
    def test_missing_sol_cpp_is_an_error(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(grader.GraderError):
                grader.grade(Path(d), TESTS, 1.0)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m unittest tests.test_grader -v`
Expected: ERROR — `ModuleNotFoundError: No module named 'grader'`.

- [ ] **Step 3: Implement**

Create `grader.py`:

```python
"""Compile and judge the user's C++ locally. Verdicts here are measured, never guessed.

This is the user's own code on the user's own machine, so there is no sandbox
beyond a time limit and a working directory — the same as running it from an
editor (spec 7.1).
"""
from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
from typing import NamedTuple

FALLBACK_GXX = Path(r"C:\msys64\ucrt64\bin\g++.exe")
# -static: the MSYS2 runtime DLLs are not on PATH, so a dynamic sol.exe cannot start.
# Big stack: Windows gives 1 MB, and a recursive DFS at N = 1e5 would die with RE.
FLAGS = ["-std=c++17", "-O2", "-static", "-Wl,--stack,268435456"]
COMPILE_TIMEOUT = 60
MAX_OUTPUT = 64_000_000
MAX_SHOWN_INPUT = 500
_HIDDEN = getattr(subprocess, "CREATE_NO_WINDOW", 0)


class GraderError(RuntimeError):
    pass


class Run(NamedTuple):
    code: int | None  # None when killed for exceeding the time limit
    out: str
    elapsed: float


class Result(NamedTuple):
    verdict: str
    passed: int
    total: int
    detail: str


def find_compiler() -> str:
    found = shutil.which("g++")
    if found:
        return found
    if FALLBACK_GXX.exists():
        return str(FALLBACK_GXX)
    raise GraderError(f"g++ not found on PATH or at {FALLBACK_GXX}")


def run_program(args, stdin_text, timeout, *, cwd=None, cancelled=lambda: False,
                merge_stderr=False) -> Run:
    """Run one process with stdin from memory, output bounded on disk."""
    with tempfile.TemporaryFile() as source, tempfile.TemporaryFile() as out:
        source.write(stdin_text.encode("utf-8"))
        source.seek(0)
        if cancelled():
            raise GraderError("Stopped")
        start = time.monotonic()
        process = subprocess.Popen(
            [str(a) for a in args], stdin=source, stdout=out,
            stderr=subprocess.STDOUT if merge_stderr else subprocess.DEVNULL,
            cwd=cwd, shell=False, creationflags=_HIDDEN)
        try:
            while process.poll() is None:
                if cancelled():
                    raise GraderError("Stopped")
                if time.monotonic() - start > timeout:
                    return Run(None, "", timeout)
                if os.fstat(out.fileno()).st_size > MAX_OUTPUT:
                    return Run(-1, "", time.monotonic() - start)
                time.sleep(0.005)
            elapsed = time.monotonic() - start
            out.seek(0)
            return Run(process.returncode, out.read(MAX_OUTPUT).decode("utf-8", "replace"), elapsed)
        finally:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=5)


def compile_source(source: Path, exe: Path, *, cancelled=lambda: False) -> str | None:
    """None on success, otherwise the first 20 lines of compiler output."""
    run = run_program([find_compiler(), *FLAGS, "-o", exe, source], "", COMPILE_TIMEOUT,
                      cwd=Path(source).parent, cancelled=cancelled, merge_stderr=True)
    if run.code is None:
        return "compile timed out"
    if run.code != 0:
        return "\n".join(run.out.splitlines()[:20]) or "compile failed"
    return None


def _text(value) -> str:
    return value.read_text(encoding="utf-8") if isinstance(value, Path) else value


def grade(folder, tests, time_limit, *, show_input=False, cancelled=lambda: False) -> Result:
    """Compile folder/sol.cpp and run it on each test, stopping at the first failure."""
    folder = Path(folder)
    source = folder / "sol.cpp"
    if not source.exists():
        raise GraderError(f"{source} not found")
    total = len(tests)
    exe = folder / "sol.exe"
    error = compile_source(source, exe, cancelled=cancelled)
    if error:
        return Result("CE", 0, total, error)
    for number, (given, expected) in enumerate(tests, 1):
        data = _text(given)
        run = run_program([exe], data, time_limit * 2, cwd=folder, cancelled=cancelled)
        if run.code is None:
            verdict = "TLE"
        elif run.code != 0:
            verdict = "RE"
        elif run.out.split() != _text(expected).split():
            verdict = "WA"
        else:
            continue
        detail = f"{verdict} on test {number}/{total}"
        if show_input and len(data) <= MAX_SHOWN_INPUT:
            detail += "\ninput:\n" + data
        return Result(verdict, number - 1, total, detail)
    return Result("AC", total, total, f"AC {total}/{total}")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m unittest tests.test_grader -v` → PASS with no skips (g++ is at the fallback path on this machine; if the class is skipped, stop and investigate `find_compiler`).
Run: `python -m unittest discover -s tests` → all green.

- [ ] **Step 5: Commit**

```bash
git add grader.py tests/test_grader.py
git commit -m "feat: local C++ grader with measured verdicts"
```

---

### Task 3: Problem bank loader

**Files:**
- Create: `bank.py`
- Test: `tests/test_bank.py`

**Interfaces:**
- Consumes: `memory.TOPICS`
- Produces:
  - `bank.BankError(ValueError)`
  - `bank.Entry` frozen dataclass: `id: str, slug: str, title: str, level: int, topic: str, time_limit: float, statement: str, tests: tuple, url: str | None = None`. Camp-1 `id` = `"camp1/<slug>"`, tests are `(Path, Path)`; archive `id` = `slug` = the archive id, tests are `(str, str)` samples, `url` set.
  - `bank.load(root: Path) -> list[Entry]`
  - `bank.SLUG` regex, `bank.CAMP1_LEVELS = (1, 2)`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_bank.py`:

```python
import json
from pathlib import Path
import tempfile
import unittest

import bank

ROOT = Path(__file__).resolve().parent.parent


def camp1(root, slug, **meta):
    folder = root / "camp1" / slug
    (folder / "tests").mkdir(parents=True)
    data = {"slug": slug, "title": "Sum", "level": 1, "topic": "implementation",
            "time_limit": 1.0, **meta}
    (folder / "meta.json").write_text(json.dumps(data), encoding="utf-8")
    (folder / "statement.md").write_text("# Sum\n", encoding="utf-8")
    (folder / "tests" / "01.in").write_text("1 2\n", encoding="utf-8")
    (folder / "tests" / "01.out").write_text("3\n", encoding="utf-8")
    return folder


ARCHIVE_ITEM = {"id": "pith-0001", "title": "Example", "url": "https://example.org/t/1",
                "level": 3, "topic": "dp", "samples": [{"in": "3\n", "out": "6\n"}]}


class LoaderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def write_archive(self, items):
        (self.root / "archive.json").write_text(json.dumps(items), encoding="utf-8")

    def test_loads_camp1_and_archive(self):
        camp1(self.root, "sum-two")
        self.write_archive([ARCHIVE_ITEM])
        first, second = bank.load(self.root)
        self.assertEqual((first.id, first.level, first.url), ("camp1/sum-two", 1, None))
        self.assertEqual(first.tests[0][0].name, "01.in")
        self.assertEqual((second.id, second.slug, second.level), ("pith-0001", "pith-0001", 3))
        self.assertEqual(second.tests, (("3\n", "6\n"),))
        self.assertIn("https://example.org/t/1", second.statement)

    def test_empty_root_is_an_empty_bank(self):
        self.assertEqual(bank.load(self.root), [])

    def test_unknown_topic_is_rejected(self):
        camp1(self.root, "sum-two", topic="magic")
        with self.assertRaises(bank.BankError):
            bank.load(self.root)

    def test_camp1_level_must_be_one_or_two(self):
        camp1(self.root, "sum-two", level=3)
        with self.assertRaises(bank.BankError):
            bank.load(self.root)

    def test_boolean_level_is_rejected(self):
        camp1(self.root, "sum-two", level=True)
        with self.assertRaises(bank.BankError):
            bank.load(self.root)

    def test_slug_must_match_folder(self):
        camp1(self.root, "sum-two", slug="other")
        with self.assertRaises(bank.BankError):
            bank.load(self.root)

    def test_input_without_output_is_rejected(self):
        folder = camp1(self.root, "sum-two")
        (folder / "tests" / "02.in").write_text("1 1\n", encoding="utf-8")
        with self.assertRaises(bank.BankError):
            bank.load(self.root)

    def test_archive_needs_https_and_samples(self):
        self.write_archive([dict(ARCHIVE_ITEM, url="http://example.org")])
        with self.assertRaises(bank.BankError):
            bank.load(self.root)
        self.write_archive([dict(ARCHIVE_ITEM, samples=[])])
        with self.assertRaises(bank.BankError):
            bank.load(self.root)

    def test_duplicate_ids_are_rejected(self):
        self.write_archive([ARCHIVE_ITEM, ARCHIVE_ITEM])
        with self.assertRaises(bank.BankError):
            bank.load(self.root)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m unittest tests.test_bank -v`
Expected: ERROR — `ModuleNotFoundError: No module named 'bank'`.

- [ ] **Step 3: Implement**

Create `bank.py`:

```python
"""The problem bank: verified Camp-1 problems in problems/camp1, Camp-2 links in archive.json.

Everything here is repository content, reviewed before commit, but it is still
validated on load so that one bad meta.json is a clear error, not a crash later.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re

from memory import TOPICS

SLUG = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
CAMP1_LEVELS = (1, 2)
ARCHIVE_LEVELS = (3, 4, 5)


class BankError(ValueError):
    pass


@dataclass(frozen=True)
class Entry:
    id: str
    slug: str
    title: str
    level: int
    topic: str
    time_limit: float
    statement: str
    tests: tuple
    url: str | None = None


def _check(entry: Entry, levels) -> Entry:
    name = entry.id or "?"
    if not isinstance(entry.slug, str) or not SLUG.fullmatch(entry.slug) or len(entry.slug) > 120:
        raise BankError(f"{name}: slug must be kebab-case")
    if not entry.title.strip():
        raise BankError(f"{name}: empty title")
    if isinstance(entry.level, bool) or entry.level not in levels:
        raise BankError(f"{name}: level must be one of {levels}")
    if entry.topic not in TOPICS:
        raise BankError(f"{name}: unknown topic {entry.topic!r}")
    limit = entry.time_limit
    if isinstance(limit, bool) or not isinstance(limit, (int, float)) or not 0 < limit <= 10:
        raise BankError(f"{name}: time_limit must be between 0 and 10 seconds")
    if not entry.tests:
        raise BankError(f"{name}: no tests")
    if entry.url is not None and not (isinstance(entry.url, str) and entry.url.startswith("https://")):
        raise BankError(f"{name}: url must start with https://")
    return entry


def _camp1(folder: Path) -> Entry:
    try:
        meta = json.loads((folder / "meta.json").read_text(encoding="utf-8"))
        statement = (folder / "statement.md").read_text(encoding="utf-8")
    except (OSError, ValueError) as exc:
        raise BankError(f"{folder.name}: {exc}") from None
    if not isinstance(meta, dict) or meta.get("slug") != folder.name:
        raise BankError(f"{folder.name}: meta.json slug must match the folder name")
    tests = []
    for given in sorted((folder / "tests").glob("*.in")):
        expected = given.with_suffix(".out")
        if not expected.exists():
            raise BankError(f"{folder.name}: {given.name} has no .out")
        tests.append((given, expected))
    return _check(Entry(id=f"camp1/{folder.name}", slug=folder.name,
                        title=str(meta.get("title", "")), level=meta.get("level"),
                        topic=meta.get("topic"), time_limit=meta.get("time_limit"),
                        statement=statement, tests=tuple(tests)), CAMP1_LEVELS)


def _archive(item) -> Entry:
    if not isinstance(item, dict):
        raise BankError("archive.json: every entry must be an object")
    samples = item.get("samples") or []
    if not all(isinstance(s, dict) and isinstance(s.get("in"), str)
               and isinstance(s.get("out"), str) for s in samples):
        raise BankError(f"{item.get('id')}: samples must be {{in, out}} strings")
    ident, title = str(item.get("id", "")), str(item.get("title", ""))
    lines = [f"# {title}", "",
             f"Level {item.get('level')} · {item.get('topic')} · real judge problem", "",
             f"Full statement and submission: {item.get('url')}", ""]
    for n, sample in enumerate(samples, 1):
        lines += [f"## Sample {n}", "", "Input:", "```", sample["in"].rstrip("\n"), "```",
                  "Output:", "```", sample["out"].rstrip("\n"), "```", ""]
    return _check(Entry(id=ident, slug=ident, title=title, level=item.get("level"),
                        topic=item.get("topic"), time_limit=item.get("time_limit", 1.0),
                        statement="\n".join(lines),
                        tests=tuple((s["in"], s["out"]) for s in samples),
                        url=item.get("url")), ARCHIVE_LEVELS)


def load(root: Path) -> list[Entry]:
    root = Path(root)
    camp1 = root / "camp1"
    entries = [_camp1(d) for d in sorted(camp1.iterdir()) if d.is_dir()] if camp1.is_dir() else []
    archive = root / "archive.json"
    if archive.exists():
        try:
            items = json.loads(archive.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise BankError(f"archive.json: {exc}") from None
        if not isinstance(items, list):
            raise BankError("archive.json must be a list")
        entries += [_archive(i) for i in items]
    for field in ("id", "slug"):
        values = [getattr(e, field) for e in entries]
        if len(values) != len(set(values)):
            raise BankError(f"duplicate {field} in the problem bank")
    return entries
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m unittest tests.test_bank -v` → PASS. Full suite → green.

- [ ] **Step 5: Commit**

```bash
git add bank.py tests/test_bank.py
git commit -m "feat: load and validate the problem bank"
```

---

### Task 4: Offline problem generator and verifier

**Files:**
- Create: `tools/make_problem.py`
- Test: `tests/test_make_problem.py`

**Interfaces:**
- Consumes: `grader.compile_source`, `grader.run_program`, `bank.SLUG`, `bank.CAMP1_LEVELS`, `memory.TOPICS`, `claude_brain._request(model, system, schema, content, cancelled=None, effort="low") -> dict`
- Produces (used only by the developer and its test):
  - `make_problem.Rejected(Exception)`
  - `make_problem.verify(candidate: dict, workdir: Path, *, small=300, large=8, keep_small=12) -> list[tuple[str, str]]`
  - `make_problem.write_entry(bank_root: Path, candidate: dict, level: int, topic: str, tests) -> Path`
  - CLI: `python tools/make_problem.py --level 1 --topic implementation --count 3 [--model sonnet]`

`candidate` keys: `title, slug, statement, reference_cpp, brute_cpp, gen_py, time_limit`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_make_problem.py`:

```python
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import bank  # noqa: E402
import grader  # noqa: E402
import make_problem  # noqa: E402

try:
    grader.find_compiler()
    HAVE_GXX = True
except grader.GraderError:
    HAVE_GXX = False

SUM = """#include <bits/stdc++.h>
int main(){int n;std::cin>>n;long long s=0;for(int i=0;i<n;i++){long long x;std::cin>>x;s+=x;}std::cout<<s<<"\\n";}"""
GEN = """import random, sys
random.seed(int(sys.argv[1]))
n = 3 if sys.argv[2] == "small" else 1000
print(n)
print(*[random.randint(1, 9) for _ in range(n)])
"""


def candidate(**overrides):
    base = {"title": "Sum Them", "slug": "sum-them", "statement": "# Sum Them\n",
            "reference_cpp": SUM, "brute_cpp": SUM, "gen_py": GEN, "time_limit": 1.0}
    return {**base, **overrides}


@unittest.skipUnless(HAVE_GXX, "g++ not found")
class VerifyTests(unittest.TestCase):
    def test_agreeing_solutions_produce_tests(self):
        with tempfile.TemporaryDirectory() as d:
            tests = make_problem.verify(candidate(), Path(d), small=5, large=1, keep_small=3)
        self.assertEqual(len(tests), 4)
        given, expected = tests[0]
        self.assertEqual(int(expected), sum(map(int, given.split()[1:])))

    def test_disagreeing_reference_is_rejected(self):
        wrong = SUM.replace("s+=x", "s+=x*(i>0)")
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(make_problem.Rejected):
                make_problem.verify(candidate(reference_cpp=wrong), Path(d), small=5, large=1)

    def test_reference_that_does_not_compile_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(make_problem.Rejected):
                make_problem.verify(candidate(reference_cpp="int main( {"), Path(d), small=1, large=1)


class WriteEntryTests(unittest.TestCase):
    def test_written_entry_loads_in_the_bank(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            make_problem.write_entry(root, candidate(), 1, "implementation",
                                     [("3\n1 2 3\n", "6\n")])
            (entry,) = bank.load(root)
            self.assertEqual((entry.id, entry.level, len(entry.tests)),
                             ("camp1/sum-them", 1, 1))
            meta = json.loads((root / "camp1" / "sum-them" / "meta.json").read_text("utf-8"))
            self.assertEqual(meta["topic"], "implementation")

    def test_existing_slug_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            make_problem.write_entry(root, candidate(), 1, "implementation", [("1\n5\n", "5\n")])
            with self.assertRaises(make_problem.Rejected):
                make_problem.write_entry(root, candidate(), 1, "implementation", [("1\n5\n", "5\n")])

    def test_bad_slug_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(make_problem.Rejected):
                make_problem.write_entry(Path(d), candidate(slug="../evil"), 1,
                                         "implementation", [("1\n5\n", "5\n")])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m unittest tests.test_make_problem -v`
Expected: ERROR — `ModuleNotFoundError: No module named 'make_problem'`.

- [ ] **Step 3: Implement**

Create `tools/make_problem.py`:

```python
"""Offline Camp-1 bank builder. Run by the developer, never by Victor.

    python tools/make_problem.py --level 1 --topic implementation --count 3

Claude proposes a problem with a reference solution, a brute force and an input
generator. A candidate is kept only if reference and brute force agree on every
small random input and the reference fits the time limit on maximum-size input.
Expected outputs come from the reference, never from Claude's own guesses.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import bank  # noqa: E402
import grader  # noqa: E402
from memory import TOPICS  # noqa: E402

BANK = ROOT / "problems"

SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["title", "slug", "statement", "reference_cpp", "brute_cpp", "gen_py",
                 "time_limit"],
    "properties": {
        "title": {"type": "string"}, "slug": {"type": "string"},
        "statement": {"type": "string"}, "reference_cpp": {"type": "string"},
        "brute_cpp": {"type": "string"}, "gen_py": {"type": "string"},
        "time_limit": {"type": "number"}}}

SYSTEM = """You write original practice problems for POSN (Thai computer olympiad) Camp 1.
Level 1: input/output, loops, conditionals, arrays, simple strings.
Level 2: sorting, simple math, brute force, prefix sums.

Return JSON with:
- title, slug (kebab-case, a-z 0-9 and hyphens only)
- statement: English Markdown with sections Statement, Input, Output, Constraints,
  and at least one Sample (input and output in fenced blocks). Constraints must be exact.
- reference_cpp: the intended C++17 solution; must run within time_limit at maximum constraints.
- brute_cpp: an obviously correct C++17 solution; slow is fine.
- gen_py: a Python 3 script. argv[1] is an integer seed, argv[2] is "small" or "max".
  Seed the random module with argv[1]. "small" prints a tiny valid input the brute force
  can handle instantly; "max" prints a valid input at maximum constraints. Print exactly
  one input and nothing else.
- time_limit: seconds, 1.0 unless the problem needs more.
The answer must be unique for every valid input (no "print any" problems).
Do not copy existing judge problems."""


class Rejected(Exception):
    pass


def _compile(text: str, workdir: Path, name: str) -> Path:
    source, exe = workdir / f"{name}.cpp", workdir / f"{name}.exe"
    source.write_text(text, encoding="utf-8")
    error = grader.compile_source(source, exe)
    if error:
        raise Rejected(f"{name} does not compile:\n{error}")
    return exe


def _input(gen: Path, seed: int, size: str) -> str:
    try:
        done = subprocess.run([sys.executable, str(gen), str(seed), size], capture_output=True,
                              text=True, timeout=20, check=True)
    except (subprocess.SubprocessError, OSError) as exc:
        raise Rejected(f"generator failed on seed {seed} ({size}): {exc}") from None
    return done.stdout


def _output(exe: Path, data: str, timeout: float, what: str) -> tuple[str, float]:
    run = grader.run_program([exe], data, timeout, cwd=exe.parent)
    if run.code is None:
        raise Rejected(f"{what} timed out")
    if run.code != 0:
        raise Rejected(f"{what} exited with {run.code}")
    return run.out, run.elapsed


def verify(candidate: dict, workdir: Path, *, small=300, large=8, keep_small=12):
    workdir = Path(workdir)
    limit = float(candidate["time_limit"])
    reference = _compile(candidate["reference_cpp"], workdir, "reference")
    brute = _compile(candidate["brute_cpp"], workdir, "brute")
    gen = workdir / "gen.py"
    gen.write_text(candidate["gen_py"], encoding="utf-8")
    tests = []
    for seed in range(small):
        data = _input(gen, seed, "small")
        want, _ = _output(brute, data, 10, f"brute force on seed {seed}")
        got, _ = _output(reference, data, limit * 2, f"reference on seed {seed}")
        if want.split() != got.split():
            raise Rejected(f"reference disagrees with brute force on seed {seed}:\n{data[:300]}")
        if seed < keep_small:
            tests.append((data, got))
    for seed in range(large):
        data = _input(gen, 100_000 + seed, "max")
        got, elapsed = _output(reference, data, limit * 2, f"reference on max seed {seed}")
        if elapsed > limit:
            raise Rejected(f"reference took {elapsed:.2f}s on max input, limit {limit}s")
        tests.append((data, got))
    return tests


def write_entry(bank_root: Path, candidate: dict, level: int, topic: str, tests) -> Path:
    slug = candidate.get("slug", "")
    if not isinstance(slug, str) or not bank.SLUG.fullmatch(slug) or len(slug) > 120:
        raise Rejected(f"bad slug {slug!r}")
    target = Path(bank_root) / "camp1" / slug
    if target.exists():
        raise Rejected(f"{slug} already exists in the bank")
    (target / "tests").mkdir(parents=True)
    meta = {"slug": slug, "title": candidate["title"], "level": level, "topic": topic,
            "time_limit": float(candidate["time_limit"])}
    (target / "meta.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    (target / "statement.md").write_text(candidate["statement"], encoding="utf-8")
    for n, (given, expected) in enumerate(tests, 1):
        (target / "tests" / f"{n:02}.in").write_text(given, encoding="utf-8", newline="\n")
        (target / "tests" / f"{n:02}.out").write_text(expected, encoding="utf-8", newline="\n")
    return target


def main():
    from claude_brain import _request  # imported late: tests never need Claude

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--level", type=int, choices=bank.CAMP1_LEVELS, required=True)
    parser.add_argument("--topic", choices=TOPICS, required=True)
    parser.add_argument("--count", type=int, default=1)
    parser.add_argument("--model", default="sonnet")
    args = parser.parse_args()
    for _ in range(args.count):
        camp1 = BANK / "camp1"
        existing = sorted(p.name for p in camp1.glob("*")) if camp1.exists() else []
        ask = (f"Level {args.level}, topic {args.topic}. "
               f"Existing slugs, do not repeat these ideas: {', '.join(existing) or 'none'}.")
        candidate = _request(args.model, SYSTEM, SCHEMA, [{"type": "text", "text": ask}],
                             effort="medium")
        try:
            with tempfile.TemporaryDirectory(prefix="victor-bank-") as workdir:
                tests = verify(candidate, Path(workdir))
            target = write_entry(BANK, candidate, args.level, args.topic, tests)
            print(f"kept     {target}")
        except Rejected as exc:
            print(f"rejected {candidate.get('slug')}: {exc}")


if __name__ == "__main__":
    main()
```

If `_request` hits its 90-second timeout during Task 5, do not change `claude_brain.py`; ask for a shorter statement in `SYSTEM` or retry.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m unittest tests.test_make_problem -v` → PASS. Full suite → green.

- [ ] **Step 5: Commit**

```bash
git add tools/make_problem.py tests/test_make_problem.py
git commit -m "feat: offline problem generator with reference-vs-brute verification"
```

---

### Task 5: Build the Camp-1 bank

**Files:**
- Create: `problems/camp1/<slug>/...` (generated)
- Modify: `tests/test_bank.py` (content check)

**Interfaces:**
- Consumes: `tools/make_problem.py` CLI, `bank.load`
- Produces: at least 10 level-1 and 10 level-2 entries under `problems/camp1/`

- [ ] **Step 1: Write the failing content test**

Append to `tests/test_bank.py`:

```python
class CommittedBankTests(unittest.TestCase):
    def test_camp1_bank_is_large_enough_for_the_first_days(self):
        entries = [e for e in bank.load(ROOT / "problems") if e.url is None]
        by_level = {level: [e for e in entries if e.level == level] for level in (1, 2)}
        self.assertGreaterEqual(len(by_level[1]), 10)
        self.assertGreaterEqual(len(by_level[2]), 10)
        self.assertGreaterEqual(len({e.topic for e in entries}), 4)
        for entry in entries:
            self.assertGreaterEqual(len(entry.tests), 10, entry.id)
```

Run: `python -m unittest tests.test_bank -v` → FAIL (bank empty).

- [ ] **Step 2: Generate level-1 problems**

Run each (about 1–3 minutes per problem; rejections are normal, rerun until the counts are met):

```bash
python tools/make_problem.py --level 1 --topic implementation --count 5
python tools/make_problem.py --level 1 --topic string --count 3
python tools/make_problem.py --level 1 --topic math --count 3
```

- [ ] **Step 3: Generate level-2 problems**

```bash
python tools/make_problem.py --level 2 --topic sorting --count 3
python tools/make_problem.py --level 2 --topic math --count 3
python tools/make_problem.py --level 2 --topic search --count 2
python tools/make_problem.py --level 2 --topic implementation --count 3
```

- [ ] **Step 4: Review every statement by hand**

For each `problems/camp1/*/statement.md`, check and delete the folder if any fails:
- Constraints are stated and match the maximum-size test (compare with the last `tests/NN.in`).
- The sample in the statement matches a correct reading of the problem.
- The answer is unique (no "print any valid answer").
- Level fits the table in spec 4.2; fix `meta.json` `level` rather than deleting if only the level is off.
- It is not a verbatim copy of a known judge problem.

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m unittest tests.test_bank -v` → PASS. Full suite → green.

- [ ] **Step 6: Commit**

```bash
git add problems/camp1 tests/test_bank.py
git commit -m "feat: first verified Camp-1 problem bank"
```

---

### Task 6: Curate the Camp-2 archive

**Files:**
- Create: `problems/archive.json`
- Modify: `tests/test_bank.py`

**Interfaces:**
- Consumes: `bank.load` archive format (spec 4.1): `{"id", "title", "url", "level", "topic", "samples": [{"in", "out"}], "time_limit"?}`
- Produces: at least 30 archive entries, at least 8 at each of levels 3, 4, 5

- [ ] **Step 1: Write the failing content test**

Append to `CommittedBankTests` in `tests/test_bank.py`:

```python
    def test_archive_covers_every_camp2_level(self):
        entries = [e for e in bank.load(ROOT / "problems") if e.url is not None]
        self.assertGreaterEqual(len(entries), 30)
        for level in (3, 4, 5):
            self.assertGreaterEqual(len([e for e in entries if e.level == level]), 8, level)
```

Run → FAIL (no archive).

- [ ] **Step 2: Research and write `problems/archive.json`**

Sources, in order of preference: programming.in.th (POSN/TOI past problems, Thai judge), then the Codeforces problemset (Div. 2 A–D, filtered by tag). For each problem:
- `id`: kebab-case, `<site>-<problem id>` lowercased, e.g. `pith-toi-0042`, `cf-1352c`.
- `level`: 3 = Codeforces ~1200–1500 or TOI easy; 4 = ~1600–1900; 5 = ~2000–2300 or TOI hard.
- `topic`: one of `memory.TOPICS`, from the problem's tags.
- `samples`: copied exactly from the statement, including trailing newlines.
- `url`: open it and confirm it loads the problem (WebFetch). Drop any that fail.

Spread topics: level 3 mostly search/greedy/dp/graph; level 4 dp/graph/data-structure/tree; level 5 dp/graph/data-structure/number-theory.

- [ ] **Step 3: Run tests to verify they pass**

Run: `python -m unittest tests.test_bank -v` → PASS. Full suite → green.

- [ ] **Step 4: Commit**

```bash
git add problems/archive.json tests/test_bank.py
git commit -m "feat: curated Camp-2 archive problems"
```

---

### Task 7: Ramp rules and daily serve

**Files:**
- Create: `daily.py`
- Test: `tests/test_daily.py`

**Interfaces:**
- Consumes: Task 1 `Memory` methods and `memory.DAILY_ROLES`, `bank.Entry`
- Produces:
  - `daily.next_level(level: int, rows: list[dict], *, today: date, camp1_started: date, last_change: date | None) -> tuple[int, str]` — pure; reason is `""` when unchanged
  - `daily.update_level(memory, today: date, log=lambda title, text: None) -> str` — applies `next_level`, stores it, returns a notice or `""`
  - `daily.folder(root: Path, today: date, role: str) -> Path` — `ValueError` on an unknown role
  - `daily.write_folder(root: Path, today: date, role: str, entry) -> Path` — never overwrites `sol.cpp`
  - `daily.ensure_today(memory, entries, root: Path, today: date, *, rng=None, log=lambda title, text: None) -> list[str]`
  - `daily.TEMPLATE` (the `sol.cpp` starter)
- Meta keys: `level`, `camp1_started`, `last_daily`, `last_level_change` (dates `YYYY-MM-DD`)

Rule details the tests pin down (spec 5):
- `days = (today - camp1_started).days`. Day 1 is `days == 0`.
- Ceiling: level ≤ 2 and `days >= 3` → 3, even if the level already changed today.
- Once per day: if `last_change == today`, no other change.
- Level ≤ 2 → 3 when `days >= 2` and at least 5 of the last 6 *graded* rows with level ≤ 2 are AC.
- Level 1 → 2 when at least 3 rows with level 1 are AC.
- Camp 2: consider `main` rows with `level == current` and `day > last_change`. Outcome of a row: `given-up` if status is `given-up`, else `solved` if AC, else not resolved (ignored). Last 3 resolved all `solved` with `rung <= 2` → +1 (max 5). Last 2 resolved both `given-up` → −1 (min 3).

- [ ] **Step 1: Write the failing tests**

Create `tests/test_daily.py`:

```python
from datetime import date, timedelta
from pathlib import Path
import random
import tempfile
import unittest

from bank import Entry
import daily
from memory import Memory

D0 = date(2026, 9, 20)


def row(day, role="main", level=1, ac=False, graded=None, status="working", rung=0):
    return {"day": day.isoformat(), "role": role, "level": level, "ac": ac,
            "graded": ac if graded is None else graded, "status": status, "rung": rung}


def entry(slug, level, topic="implementation"):
    ident = f"camp1/{slug}" if level <= 2 else slug
    return Entry(id=ident, slug=slug, title=slug.title(), level=level, topic=topic,
                 time_limit=1.0, statement=f"# {slug}\n", tests=(("1\n", "1\n"),),
                 url=None if level <= 2 else f"https://example.org/{slug}")


class NextLevelTests(unittest.TestCase):
    def step(self, level, rows, today, last_change=None):
        return daily.next_level(level, rows, today=today, camp1_started=D0,
                                last_change=last_change)

    def test_day_one_with_six_acs_stays_in_camp_one(self):
        rows = [row(D0, ac=True) for _ in range(6)]
        self.assertEqual(self.step(1, rows, D0)[0], 2)
        self.assertEqual(self.step(2, rows, D0, last_change=D0)[0], 2)
        second_day = [row(D0, level=2, ac=True) for _ in range(6)]
        self.assertEqual(self.step(2, second_day, D0 + timedelta(1))[0], 2)

    def test_third_day_with_five_of_six_moves_to_camp_two(self):
        rows = [row(D0, level=2, ac=True) for _ in range(5)] + [row(D0, level=2, graded=True)]
        self.assertEqual(self.step(2, rows, D0 + timedelta(2))[0], 3)

    def test_four_of_six_is_not_enough(self):
        rows = ([row(D0, level=2, ac=True) for _ in range(4)]
                + [row(D0, level=2, graded=True) for _ in range(2)])
        self.assertEqual(self.step(2, rows, D0 + timedelta(2))[0], 2)

    def test_ungraded_rows_do_not_count_against_promotion(self):
        rows = ([row(D0, level=2, ac=True) for _ in range(5)]
                + [row(D0, level=2) for _ in range(3)])
        self.assertEqual(self.step(2, rows, D0 + timedelta(2))[0], 3)

    def test_fourth_day_forces_camp_two(self):
        day4 = D0 + timedelta(3)
        self.assertEqual(self.step(1, [], day4), (3, "Camp 1 ceiling: day 4"))
        self.assertEqual(self.step(2, [], day4, last_change=day4)[0], 3)

    def test_three_low_hint_solves_step_up(self):
        change = D0 + timedelta(3)
        rows = [row(change + timedelta(i + 1), level=3, ac=True, rung=2) for i in range(3)]
        self.assertEqual(self.step(3, rows, change + timedelta(4), last_change=change)[0], 4)

    def test_a_heavily_hinted_solve_blocks_step_up(self):
        change = D0 + timedelta(3)
        rows = [row(change + timedelta(i + 1), level=3, ac=True, rung=r)
                for i, r in enumerate((2, 3, 1))]
        self.assertEqual(self.step(3, rows, change + timedelta(4), last_change=change)[0], 3)

    def test_warmups_do_not_count_toward_camp_two_steps(self):
        change = D0 + timedelta(3)
        rows = [row(change + timedelta(i + 1), role="warmup", level=3, ac=True) for i in range(3)]
        self.assertEqual(self.step(3, rows, change + timedelta(4), last_change=change)[0], 3)

    def test_two_give_ups_step_down_but_never_below_three(self):
        change = D0 + timedelta(5)
        gave_up = [row(change + timedelta(i + 1), level=4, status="given-up") for i in range(2)]
        self.assertEqual(self.step(4, gave_up, change + timedelta(3), last_change=change)[0], 3)
        at_three = [dict(r, level=3) for r in gave_up]
        self.assertEqual(self.step(3, at_three, change + timedelta(3), last_change=change)[0], 3)

    def test_only_one_change_per_day(self):
        today = D0 + timedelta(8)
        rows = [row(D0 + timedelta(4 + i), level=3, ac=True) for i in range(3)]
        self.assertEqual(self.step(3, rows, today, last_change=today)[0], 3)

    def test_problems_from_before_the_last_change_are_ignored(self):
        change = D0 + timedelta(5)
        rows = [row(change - timedelta(i), level=3, ac=True) for i in range(3)]
        self.assertEqual(self.step(3, rows, change + timedelta(1), last_change=change)[0], 3)


class ServeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        base = Path(self.temp.name)
        self.memory = Memory(base)
        self.root = base / "daily"
        self.rng = random.Random(7)

    def tearDown(self):
        self.memory.close()
        self.temp.cleanup()

    def serve(self, entries, today=D0, **kw):
        return daily.ensure_today(self.memory, entries, self.root, today, rng=self.rng, **kw)

    def test_serving_is_idempotent_on_the_same_day(self):
        entries = [entry("a", 1), entry("b", 1), entry("c", 1)]
        self.assertEqual(self.serve(entries), [])
        self.assertEqual(self.serve(entries), [])
        rows = self.memory.daily_rows(D0.isoformat())
        self.assertEqual([r["role"] for r in rows], ["warmup", "main"])
        for role in ("main", "warmup"):
            folder = daily.folder(self.root, D0, role)
            self.assertTrue((folder / "statement.md").exists())
            self.assertEqual((folder / "sol.cpp").read_text(encoding="utf-8"), daily.TEMPLATE)

    def test_a_problem_is_never_served_twice(self):
        entries = [entry(s, 1) for s in ("a", "b", "c", "d")]
        self.serve(entries)
        self.serve(entries, today=D0 + timedelta(1))
        sources = [r["source"] for r in self.memory.daily_rows()]
        self.assertEqual(len(sources), 4)
        self.assertEqual(len(set(sources)), 4)

    def test_warmup_is_one_level_below_main(self):
        self.memory.set_meta("camp1_started", (D0 - timedelta(10)).isoformat())
        self.memory.set_meta("level", 3)
        self.serve([entry("easy", 2), entry("real", 3, topic="dp")])
        rows = {r["role"]: r for r in self.memory.daily_rows(D0.isoformat())}
        self.assertEqual((rows["warmup"]["level"], rows["main"]["level"]), (2, 3))

    def test_exhausted_level_falls_back_with_a_notice(self):
        self.memory.set_meta("camp1_started", (D0 - timedelta(10)).isoformat())
        self.memory.set_meta("level", 3)
        notices = self.serve([entry("easy", 2), entry("hard", 4, topic="dp")])
        rows = {r["role"]: r for r in self.memory.daily_rows(D0.isoformat())}
        self.assertEqual(rows["main"]["level"], 4)
        self.assertTrue(any("level 4" in n for n in notices))

    def test_empty_bank_serves_nothing_and_retries_later(self):
        notices = self.serve([])
        self.assertEqual(self.memory.daily_rows(), [])
        self.assertTrue(notices)
        self.assertIsNone(self.memory.get_meta("last_daily"))

    def test_weak_topic_is_preferred(self):
        weak = self.memory.upsert_problem("old", "Old", topic="string")
        self.memory.add_failures(self.memory.add_attempt(weak, "x"), [{"tag": "off-by-one"}])
        entries = [entry(f"i{n}", 1) for n in range(6)] + [entry("s", 1, topic="string")]
        self.serve(entries)
        served = {r["source"] for r in self.memory.daily_rows(D0.isoformat())}
        self.assertIn("camp1/s", served)

    def test_ceiling_change_is_logged(self):
        self.memory.set_meta("camp1_started", (D0 - timedelta(3)).isoformat())
        logged = []
        notices = self.serve([entry("easy", 2), entry("real", 3, topic="dp")],
                             log=lambda title, text: logged.append(title))
        self.assertEqual(logged, ["Level 1 → 3"])
        self.assertEqual(self.memory.get_meta("level"), "3")
        self.assertTrue(any("Level 1 → 3" in n for n in notices))

    def test_existing_solution_is_never_overwritten(self):
        target = daily.write_folder(self.root, D0, "main", entry("a", 1))
        (target / "sol.cpp").write_text("my work", encoding="utf-8")
        daily.write_folder(self.root, D0, "main", entry("a", 1))
        self.assertEqual((target / "sol.cpp").read_text(encoding="utf-8"), "my work")

    def test_folder_rejects_unknown_roles(self):
        with self.assertRaises(ValueError):
            daily.folder(self.root, D0, "..")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m unittest tests.test_daily -v`
Expected: ERROR — `ModuleNotFoundError: No module named 'daily'`.

- [ ] **Step 3: Implement**

Create `daily.py`:

```python
"""Today's problems and the difficulty ramp. Policy lives here, never in a prompt.

The model never proposes a level. Levels move only on measured results: graded
verdicts, the hint rung reached, and recorded give-ups (spec section 5).
"""
from __future__ import annotations

from datetime import date
from pathlib import Path
import random

from memory import DAILY_ROLES

CAMP1_MAX = 2
FIRST_CAMP2 = 3
MAX_LEVEL = 5
FLOOR_DAYS = 2          # earliest Camp 2 is the third day
CEILING_DAYS = 3        # the fourth day is Camp 2 no matter what
LEVEL2_AFTER = 3        # level-1 ACs before level 2
PROMOTE_WINDOW, PROMOTE_NEED = 6, 5
STEP_UP_STREAK, STEP_UP_MAX_RUNG = 3, 2
STEP_DOWN_STREAK = 2

TEMPLATE = """#include <bits/stdc++.h>
using namespace std;

int main() {
    ios::sync_with_stdio(false);
    cin.tie(nullptr);

    return 0;
}
"""


def next_level(level, rows, *, today, camp1_started, last_change):
    """(new level, reason). Pure: rows come from Memory.daily_rows()."""
    days = (today - camp1_started).days
    if level <= CAMP1_MAX and days >= CEILING_DAYS:
        return FIRST_CAMP2, f"Camp 1 ceiling: day {days + 1}"
    if last_change == today:
        return level, ""
    if level <= CAMP1_MAX:
        graded = [r for r in rows if r["level"] <= CAMP1_MAX and r["graded"]][-PROMOTE_WINDOW:]
        if days >= FLOOR_DAYS and sum(r["ac"] for r in graded) >= PROMOTE_NEED:
            return FIRST_CAMP2, f"{PROMOTE_NEED} of the last {PROMOTE_WINDOW} Camp-1 problems solved"
        if level == 1 and sum(r["ac"] for r in rows if r["level"] == 1) >= LEVEL2_AFTER:
            return 2, f"{LEVEL2_AFTER} level-1 problems solved"
        return level, ""
    since = last_change.isoformat() if last_change else ""
    outcomes = [("given-up" if r["status"] == "given-up" else "solved", r["rung"])
                for r in rows
                if r["role"] == "main" and r["level"] == level and r["day"] > since
                and (r["status"] == "given-up" or r["ac"])]
    tail = outcomes[-STEP_UP_STREAK:]
    if (level < MAX_LEVEL and len(tail) == STEP_UP_STREAK
            and all(o == "solved" and rung <= STEP_UP_MAX_RUNG for o, rung in tail)):
        return level + 1, f"{STEP_UP_STREAK} main problems solved with few hints"
    tail = outcomes[-STEP_DOWN_STREAK:]
    if (level > FIRST_CAMP2 and len(tail) == STEP_DOWN_STREAK
            and all(o == "given-up" for o, _ in tail)):
        return level - 1, f"{STEP_DOWN_STREAK} give-ups in a row"
    return level, ""


def update_level(memory, today, log=lambda title, text: None) -> str:
    level = int(memory.get_meta("level", "1"))
    started = date.fromisoformat(memory.get_meta("camp1_started", today.isoformat()))
    change = memory.get_meta("last_level_change")
    new, reason = next_level(level, memory.daily_rows(), today=today, camp1_started=started,
                             last_change=date.fromisoformat(change) if change else None)
    if new == level:
        return ""
    memory.set_meta("level", new)
    memory.set_meta("last_level_change", today.isoformat())
    title = f"Level {level} → {new}"
    log(title, reason)
    return f"{title}: {reason}"


def folder(root, today, role) -> Path:
    # Built only from the date and a fixed role name; never from bank or model text.
    if role not in DAILY_ROLES:
        raise ValueError(f"unknown daily role {role!r}")
    return Path(root) / today.isoformat() / role


def write_folder(root, today, role, entry) -> Path:
    target = folder(root, today, role)
    target.mkdir(parents=True, exist_ok=True)
    (target / "statement.md").write_text(entry.statement, encoding="utf-8")
    solution = target / "sol.cpp"
    if not solution.exists():
        solution.write_text(TEMPLATE, encoding="utf-8")
    return target


def _pick(entries, level, served, weak, rng, exclude):
    pool = [e for e in entries if e.level == level and e.id not in served and e.id not in exclude]
    for topic in weak:
        preferred = [e for e in pool if e.topic == topic]
        if preferred:
            return rng.choice(preferred)
    return rng.choice(pool) if pool else None


def _pick_near(entries, level, served, weak, rng, exclude=()):
    """The wanted level if it has problems left, else the nearest level that does."""
    # Ties go to the harder level: a Camp-2 student should not fall back into Camp 1.
    for candidate in sorted(range(1, MAX_LEVEL + 1), key=lambda n: (abs(n - level), -n)):
        found = _pick(entries, candidate, served, weak, rng, exclude)
        if found:
            return found
    return None


def ensure_today(memory, entries, root, today, *, rng=None, log=lambda title, text: None):
    """Serve today's warm-up and main exactly once. Returns notices for the transcript."""
    day = today.isoformat()
    if memory.get_meta("last_daily") == day:
        return []
    rng = rng or random.Random()
    if memory.get_meta("camp1_started") is None:
        memory.set_meta("camp1_started", day)
    notices = [n for n in [update_level(memory, today, log)] if n]
    level = int(memory.get_meta("level", "1"))
    served, weak = memory.served_sources(), memory.weak_topics()
    main = _pick_near(entries, level, served, weak, rng)
    if main is None:
        return notices + ["The problem bank is empty. Add problems under problems/."]
    if main.level != level:
        notices.append(f"No level-{level} problems left; today's main is level {main.level}.")
    warmup = _pick_near(entries, max(1, level - 1), served, weak, rng, exclude={main.id})
    picked = [("warmup", warmup), ("main", main)] if warmup else [("main", main)]
    for role, item in picked:  # every folder first, so a disk error leaves no DB rows
        write_folder(root, today, role, item)
    for role, item in picked:
        problem_id = memory.upsert_problem(item.slug, item.title, topic=item.topic, source=item.id)
        memory.add_daily(day, role, problem_id, item.level)
    memory.set_meta("last_daily", day)
    return notices
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m unittest tests.test_daily -v` → PASS. Full suite → green.

- [ ] **Step 5: Commit**

```bash
git add daily.py tests/test_daily.py
git commit -m "feat: difficulty ramp and daily problem serving"
```

---

### Task 8: Today card, Grade button and ตรวจ in the app

**Files:**
- Modify: `app.py` — imports (lines 2–35), `VictorApp.__init__` (line 82 and after the `self.study` block at lines 113–116), `_build` (after the mentor switch, line ~216), `submit` (line ~713), `poll` (line ~800), new methods after `offer_note`
- Test: `tests/test_ui.py`

**Interfaces:**
- Consumes: `bank.load`, `bank.BankError`, `daily.ensure_today`, `daily.update_level`, `daily.folder`, `grader.grade`, `grader.GraderError`, `grader.Result`, `Memory.daily_rows`, `Memory.add_attempt`, `Memory.upsert_problem`, `Memory.current_problem`, `memory.MAX_TEXT`
- Produces:
  - `VictorApp(store=None, daily_root=None)`; attributes `daily_root: Path`, `bank: list[Entry]`, `bank_by_id: dict`, `today_card: CTkFrame`, `today_seen: date`
  - `VictorApp.refresh_today()`, `VictorApp.open_daily(role)`, `VictorApp.start_grade(role, day=None) -> Thread | None`, `VictorApp.finish_grade(row, entry, folder, result)`, `VictorApp.current_daily_role() -> str`, `VictorApp.log_level_change(title, text)`
  - Event kind `"grade"` on `self.events`
  - `app.GRADE_WORD = "ตรวจ"`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_ui.py`:

```python
class DailyCardTests(unittest.TestCase):
    def setUp(self):
        from bank import Entry
        self.temp = tempfile.TemporaryDirectory()
        self.app = VictorApp(store=LocalStore(Path(self.temp.name)))
        self.app.withdraw()
        self.app.study = None
        self.entries = [Entry(id=f"camp1/p{n}", slug=f"p{n}", title=f"P{n}", level=1,
                              topic="implementation", time_limit=1.0, statement="# P\n",
                              tests=(("1\n", "1\n"),)) for n in range(4)]
        self.app.bank = self.entries
        self.app.bank_by_id = {e.id: e for e in self.entries}
        self.app.memory.set_meta("last_daily", "")  # force a fresh serve with this bank
        self.app.refresh_today()

    def tearDown(self):
        self.app.close()
        self.temp.cleanup()

    def today_rows(self):
        from datetime import date
        return {r["role"]: r for r in self.app.memory.daily_rows(date.today().isoformat())}

    def grade(self, role, result):
        with patch("app.grader.grade", return_value=result):
            worker = self.app.start_grade(role)
            worker.join(5)
            self.app.poll()

    def test_daily_folders_live_under_the_test_store_not_the_real_vault(self):
        from datetime import date
        self.assertTrue(str(self.app.daily_root).startswith(self.temp.name))
        self.assertTrue((self.app.daily_root / date.today().isoformat() / "main" / "sol.cpp").exists())

    def test_today_card_lists_both_problems(self):
        import customtkinter as ctk
        texts = " ".join(w.cget("text") for w in self.app.today_card.winfo_children()
                         if isinstance(w, ctk.CTkLabel))
        self.assertIn("main", texts)
        self.assertIn("warmup", texts)

    def test_accepted_solution_is_recorded_and_solves_the_problem(self):
        import grader
        self.grade("main", grader.Result("AC", 1, 1, "AC 1/1"))
        rows = self.today_rows()
        self.assertTrue(rows["main"]["ac"])
        self.assertEqual(rows["main"]["status"], "solved")
        self.assertTrue(any("AC 1/1" in b[1].cget("text") for b in self.app.bubbles))
        self.assertFalse(self.app.busy)

    def test_wrong_answer_is_recorded_without_solving(self):
        import grader
        self.grade("warmup", grader.Result("WA", 0, 1, "WA on test 1/1"))
        rows = self.today_rows()
        self.assertTrue(rows["warmup"]["graded"])
        self.assertFalse(rows["warmup"]["ac"])
        self.assertEqual(rows["warmup"]["status"], "working")

    def test_archive_ac_is_only_a_sample_check(self):
        import grader
        from bank import Entry
        row = self.today_rows()["main"]
        self.app.bank_by_id[row["source"]] = Entry(
            id=row["source"], slug=row["slug"], title=row["title"], level=3, topic="dp",
            time_limit=1.0, statement="#", tests=(("1\n", "1\n"),), url="https://example.org/p")
        self.grade("main", grader.Result("AC", 1, 1, "AC 1/1"))
        self.assertEqual(self.app.memory.attempts(row["problem_id"])[-1]["verdict"], "unsubmitted")
        self.assertTrue(any("https://example.org/p" in b[1].cget("text") for b in self.app.bubbles))

    def test_typing_the_grade_word_in_mentor_mode_grades_instead_of_asking(self):
        import grader
        self.app.mentor_mode = True
        with patch("app.ask_mentor") as ask, \
                patch("app.grader.grade", return_value=grader.Result("AC", 1, 1, "AC 1/1")):
            worker = self.app.submit("ตรวจ")
            worker.join(5)
            self.app.poll()
        ask.assert_not_called()
        self.assertTrue(self.today_rows()["main"]["ac"])

    def test_stop_during_grading_records_nothing(self):
        import grader
        release = threading.Event()
        def slow(*args, **kwargs):
            release.wait(5)
            return grader.Result("AC", 1, 1, "AC 1/1")
        with patch("app.grader.grade", side_effect=slow):
            worker = self.app.start_grade("main")
            self.app.stop()
            release.set()
            worker.join(5)
            self.app.poll()
        for r in self.today_rows().values():
            self.assertFalse(r["graded"])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m unittest tests.test_ui.DailyCardTests -v`
Expected: ERROR — `AttributeError: ... has no attribute 'bank'` / `'refresh_today'`.

- [ ] **Step 3: Implement — imports and constants**

In `app.py`, add `from datetime import date` beside the other stdlib imports, and `import bank`, `import daily`, `import grader` beside the local-module imports. Replace `from memory import Memory, MemoryError` with:

```python
from memory import MAX_TEXT, Memory, MemoryError
```

Below `STUDY_VAULT = ...`:

```python
BANK = BASE / "problems"
GRADE_WORD = "ตรวจ"
```

- [ ] **Step 4: Implement — constructor**

Change the signature to `def __init__(self, store=None, daily_root=None):`. Directly after the `self.study` try/except block, add:

```python
        # Tests pass their own store; they must never write into the real study vault.
        if daily_root is None:
            daily_root = (STUDY_VAULT / "daily" if store is None
                          else self.store.directory.parent / "daily")
        self.daily_root = Path(daily_root)
        self.daily_notices = []
        try:
            self.bank = bank.load(BANK)
        except bank.BankError as exc:
            self.bank = []
            self.daily_notices.append(str(exc))
        self.bank_by_id = {e.id: e for e in self.bank}
        self.today_seen = date.today()
```

After the line in `__init__` that calls `self._build()`, add:

```python
        self.refresh_today()
```

- [ ] **Step 5: Implement — sidebar card**

In `_build`, directly after `if self.mentor_mode: self.mentor_switch.select()`:

```python
        self.today_card = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        self.today_card.pack(fill="x", padx=14, pady=(14, 0))
```

- [ ] **Step 6: Implement — methods**

Add after `offer_note`:

```python
    # ---------- daily problems and grading ----------

    def log_level_change(self, title, text):
        if self.study:
            try:
                self.study.append_log("update", title, text)
            except (VaultError, OSError):
                pass  # ponytail: the level is already stored; the vault line is a courtesy

    def refresh_today(self):
        """Serve today's problems once, then redraw the Today card."""
        today = date.today()
        notices, rows = list(self.daily_notices), []
        self.daily_notices = []
        try:
            notices += daily.ensure_today(self.memory, self.bank, self.daily_root, today,
                                          log=self.log_level_change)
            rows = self.memory.daily_rows(today.isoformat())
        except (MemoryError, sqlite3.Error, OSError) as exc:
            notices.append(str(exc))
        for child in self.today_card.winfo_children():
            child.destroy()
        self.label(self.today_card, "TODAY", T.HINT, T.MUTED).pack(anchor="w")
        for row in rows:
            state = ("AC" if row["ac"] else
                     "given up" if row["status"] == "given-up" else "working")
            self.label(self.today_card, f"{row['role']} · L{row['level']} · {state}\n{row['title']}",
                       T.LABEL, T.TEXT, justify="left", wraplength=180).pack(anchor="w", pady=(6, 2))
            buttons = ctk.CTkFrame(self.today_card, fg_color="transparent")
            buttons.pack(fill="x")
            self.button(buttons, "Open", lambda r=row["role"]: self.open_daily(r),
                        height=28).pack(side="left", expand=True, fill="x", padx=(0, 4))
            self.button(buttons, "Grade", lambda r=row["role"]: self.start_grade(r),
                        height=28).pack(side="left", expand=True, fill="x")
        for notice in notices:
            self.add_message("STATUS", notice)

    def open_daily(self, role):
        path = daily.folder(self.daily_root, date.today(), role)
        if path.exists():
            os.startfile(path)

    def current_daily_role(self):
        """Which of today's problems the mentor is on; main if it is on neither."""
        current = self.memory.current_problem()
        for row in self.memory.daily_rows(date.today().isoformat()):
            if current and row["problem_id"] == current["id"]:
                return row["role"]
        return "main"

    def start_grade(self, role, day=None):
        """Grade one daily solution off the Tk thread. Returns the worker (for tests)."""
        day = day or date.today()
        rows = {r["role"]: r for r in self.memory.daily_rows(day.isoformat())}
        row = rows.get(role)
        entry = self.bank_by_id.get(row["source"]) if row else None
        if entry is None:
            self.add_message("ERROR", "No problem to grade today.")
            return None
        self.silence()
        self.discard_proposals()
        self.generation += 1
        generation = self.generation
        self.busy = True
        self.send_button.configure(state="disabled")
        self.set_status("Grading…", "thinking")
        folder = daily.folder(self.daily_root, day, role)
        # A failing input is itself a hint: only warm-ups show it (spec 7).
        show = role == "warmup" and entry.url is None
        def work():
            try:
                result = grader.grade(folder, entry.tests, entry.time_limit, show_input=show,
                                      cancelled=lambda: generation != self.generation)
                self.events.put(("grade", generation, (row, entry, folder, result)))
            except (grader.GraderError, OSError) as exc:
                self.events.put(("error", generation, str(exc)))
        thread = threading.Thread(target=work, daemon=True)
        thread.start()
        return thread

    def finish_grade(self, row, entry, folder, result):
        """Record the measured verdict, then let the ramp react to it."""
        verdict, text = result.verdict, result.detail
        if entry.url and verdict == "AC":
            # Samples are not the judge: the real verdict comes from the user.
            verdict, text = "unsubmitted", f"samples OK — submit at {entry.url}"
        try:
            body = (folder / "sol.cpp").read_text(encoding="utf-8", errors="replace")[:MAX_TEXT]
            self.memory.add_attempt(row["problem_id"], body if body.strip() else "(empty)",
                                    verdict=verdict)
            if verdict == "AC" and row["status"] != "given-up":
                self.memory.upsert_problem(row["slug"], row["title"], status="solved")
            notice = daily.update_level(self.memory, date.today(), log=self.log_level_change)
        except (MemoryError, sqlite3.Error, OSError) as exc:
            self.add_message("ERROR", str(exc))
            return
        self.add_message("VICTOR", f"{row['title']}: {text}")
        if notice:
            self.add_message("STATUS", notice)
        self.refresh_today()
```

- [ ] **Step 7: Implement — routing**

In `submit`, as the first statements of the method body (before `self.silence()`):

```python
        if self.mentor_mode and not summary and prompt.strip() == GRADE_WORD:
            self.add_message("YOU", prompt)
            return self.start_grade(self.current_daily_role())
```

In `poll`, next to the existing `if kind == "mentor":` branch:

```python
                if kind == "grade":
                    self.finish_grade(*value)
                    continue
```

At the top of `poll`'s body (before the event loop), pick up a date change while Victor stays open overnight:

```python
        if date.today() != self.today_seen:
            self.today_seen = date.today()
            self.refresh_today()
```

- [ ] **Step 8: Run tests to verify they pass**

Run: `python -m unittest tests.test_ui -v` → PASS.
Run: `python -m unittest discover -s tests` → all green. If an existing UI test now fails because `refresh_today` adds a STATUS bubble at startup, make that test's expectation relative (`len(a.bubbles)` before/after) rather than changing the feature.

- [ ] **Step 9: Commit**

```bash
git add app.py tests/test_ui.py
git commit -m "feat: Today card, Grade button and ตรวจ in mentor mode"
```

---

### Task 9: Docs and live verification

**Files:**
- Modify: `README.md`, `VERIFICATION.md`

- [ ] **Step 1: Live check**

1. Run `Start Victor.cmd`. The sidebar shows TODAY with a warm-up and a main problem.
2. Confirm `D:\Jarvis\Study\daily\<today>\main\statement.md` and `sol.cpp` exist (Open button).
3. Write a correct solution for the warm-up in `sol.cpp`, press Grade → `AC n/n`, card shows AC.
4. Break it (print 0), press Grade → `WA on test k/n` plus the input (warm-up only).
5. Turn on mentor mode, type `ตรวจ` → grades the current problem, no Claude call.
6. Close and reopen Victor → no new problems served today, card unchanged.

- [ ] **Step 2: Document**

`README.md`: add a "Daily practice" section — what the card does, where solutions live, the level table from spec 4.2, the ramp rules in one paragraph, `ตรวจ`, and how to grow the bank (`python tools/make_problem.py ...`, editing `problems/archive.json`). Mention that the PATH entry `C:\msys64\ucrt64\bin.` has a trailing dot and that the grader uses the absolute path regardless.

`VERIFICATION.md`: append the six live-check steps above with today's result and the final test count.

- [ ] **Step 3: Commit**

```bash
git add README.md VERIFICATION.md
git commit -m "docs: daily practice, grader and ramp"
```

---

## Self-Review Notes

- Spec coverage: §4.1 formats → Tasks 3, 5, 6; §4.2 levels → Task 7 constants; §5 ramp → Task 7; §6 daily flow and fallbacks → Task 7; §6.1 Today card and `ตรวจ` → Task 8; §7 grader incl. hidden input, archive samples, Stop → Tasks 2 and 8; `CE` → Task 1; §7.1 safety → Global Constraints, `daily.folder`, `write_entry` slug check; §8 generator → Tasks 4–5; §9 tests → each task; §10 build order preserved.
- Refinement of spec §5, pinned by tests: the floor is `days >= 2` (Camp 2 from the third day at the earliest) and the ceiling `days >= 3` (the fourth day), which yields exactly "2–3 days of Camp 1".
- "Rung at solve time" uses the problem's stored rung, which only rises; a hint asked for after solving counts against the streak. Accepted: it errs toward not promoting.
