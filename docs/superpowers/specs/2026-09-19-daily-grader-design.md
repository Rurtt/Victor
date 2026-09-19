# Victor daily problems, grader and difficulty ramp — design

Date: 2026-09-19
Status: approved in brainstorming, not yet implemented
Builds on: `2026-09-17-posn-mentor-design.md` (mentor ladder, memory, study vault)

---

## 1. Goal

The mentor exists: hint ladder, failure-tag profile, problem and attempt records.
What Victor lacks is the other two thirds of a practice loop:

- **Question giver.** A fresh set of problems every day, without the user having to
  find them.
- **Grader.** A measured verdict on the user's C++ solution, not a model's opinion.
- **Difficulty ramp.** Start with POSN Camp 1 basics for two to three days, then move to
  Camp-2-ready problems, and keep adjusting to how the user actually performs.

## 2. Decisions taken in brainstorming (2026-09-19)

1. **Problem source is hybrid.** Camp-1 levels use problems generated offline and
   verified mechanically. Camp-2 levels use real past problems from public archives; the
   user submits on the real judge.
2. **Approach A: the Camp-1 bank is built offline, not at runtime.** A generator script
   produces candidates; only problems whose reference and brute-force solutions agree on
   hundreds of random inputs are kept and checked into the repo. Victor at runtime only
   picks, copies and grades. Runtime generation (approach B) is deferred until the bank
   runs out; the verifier written here is reused for it.
   Rejected: letting Claude write expected outputs directly — those are guesses, and the
   grader would call correct code WA.
3. **Ramp is earned, with a floor and a ceiling.** See section 5.
4. **One main problem plus one warm-up per day.**
5. **Solutions live in a folder.** The user codes in their own editor and presses Grade.

## 3. Constraint carried over

`claude_brain.py` runs `claude -p --tools ""`. Nothing in this design asks Claude to read
files, run code or choose problems at runtime. Selection, grading and level changes are
all Python. The only Claude involvement is the existing mentor turn, and the offline
generator script run by the developer.

## 4. Architecture

```
problems/camp1/<slug>/       statement.md, meta.json, tests/NN.in, tests/NN.out
problems/archive.json        Camp-2 real problems (hand-curated)
tools/make_problem.py        offline: generate candidate, verify ref vs brute, write bank entry
grader.py                    compile and run a solution against tests, return verdict
daily.py                     ramp state, daily pick, daily folder writing
app.py                       "Today" card, Grade button, grader worker, date-change check
memory.py                    VERDICTS gains "CE"; helpers for served problems and ramp state
```

### 4.1 Bank formats

`problems/camp1/<slug>/meta.json`:

```json
{"slug": "sum-of-evens", "title": "Sum of Evens", "level": 1,
 "topic": "implementation", "time_limit": 1.0}
```

`topic` must be a member of `memory.TOPICS`; `level` is 1 or 2. Tests are numbered
`01.in`/`01.out` upward, roughly 20 per problem: small cases first, maximum-size last.

`problems/archive.json` is a list of:

```json
{"id": "pith-0042", "title": "Example", "url": "https://example.org/task/0042",
 "level": 3, "topic": "dp", "samples": [{"in": "3\n1 2 3\n", "out": "6\n"}]}
```

`level` is 3 to 5. Every URL is checked live when the file is curated. The statement is
not copied into the repo; the daily `statement.md` holds the title, link and samples.

### 4.2 Levels

| Level | Stage | Content |
|-------|-------|---------|
| 1 | Camp 1 | I/O, loops, conditionals, arrays, simple strings |
| 2 | Camp 1 | sorting, simple math, brute force, prefix sums |
| 3 | Camp 2 entry | binary search, greedy, basic DP, BFS/DFS |
| 4 | Camp 2 | harder DP, Dijkstra, DSU, segment tree basics |
| 5 | Camp 2 | full Camp-2 difficulty |

## 5. Difficulty ramp

State in the `meta` table: `level` (1–5), `camp1_started` (date), `last_daily` (date),
`last_level_change` (date). Dates are `YYYY-MM-DD`.

All rules are evaluated in Python when a verdict is recorded or a new day starts. The
model never sets or proposes a level.

**Camp 1 to Camp 2 (level ≤ 2 → 3).**
- Level 1 → 2 after 3 ACs at level 1.
- Move to level 3 when both hold: at least 2 calendar days since `camp1_started`, and at
  least 5 of the last 6 graded Camp-1 problems are AC.
- Ceiling: on the fourth calendar day, move to level 3 regardless of results. This keeps
  the user's "2–3 days, then Camp 2".

**Inside Camp 2 (levels 3–5).**
- Step up after 3 consecutive solved main problems whose `rung` at solve time was ≤ 2
  (solved with few hints).
- Step down after 2 consecutive give-ups (`เปิดเฉลย`). Never below 3.
- At most one level change per calendar day.

A "graded problem" is a problem with at least one attempt carrying a verdict. Its result
is AC if any attempt is AC; otherwise it is not AC.

Every level change appends to the study vault's `log.md`:

```
## [YYYY-MM-DD] update | Level 3 → 4
Three main problems solved at rung ≤ 2 in a row.
```

## 6. Daily flow

On app start, and when the Today card is refreshed, `daily.ensure_today()` runs:

1. If `last_daily` equals today, do nothing (idempotent).
2. Apply the ceiling rule for today's date.
3. Pick the **main** problem at the current level and the **warm-up** at level − 1
   (level 1 warm-up is another level-1 problem). Candidates exclude every bank id already
   recorded in `problem.source`. Among candidates, prefer the topic most common in the
   user's failure-tag history; otherwise pick at random.
4. Write `D:\Jarvis\Study\daily\<YYYY-MM-DD>\main\` and `...\warmup\`, each with
   `statement.md` and a `sol.cpp` template (includes, fast I/O, empty `main`). Paths are
   built only from the date and the fixed names `main`/`warmup`; bank slugs are validated
   with the existing kebab-case regex and never used to build the daily path.
5. Create a `problem` row for each: `slug` = bank slug, `source` = bank id
   (`camp1/<slug>` or the archive id), `topic` from the bank, `status = 'working'`,
   `rung = 0`. The mentor ladder therefore works on today's problems immediately.
6. Set `last_daily`.

If the bank for a level is exhausted, fall back to the nearest level that still has
problems and show one line in the transcript saying so. If nothing is left at all, the
Today card says the bank is empty. Victor never crashes over this.

Unsolved problems from earlier days stay on disk and in the database with status
`working`. There is no penalty; they simply do not count as AC.

### 6.1 Today card

Sidebar card listing today's two problems: title, level, status (working / AC / given up),
and two buttons each: **Open folder** (`os.startfile` on the problem folder) and
**Grade**. Typing `ตรวจ` in mentor mode grades the current problem, which is the same
action.

## 7. Grader

`grader.grade(folder, tests, time_limit, cancelled) -> Result(verdict, passed, total, detail)`.

- **Compiler discovery** at first use: `shutil.which("g++")`, then
  `C:\msys64\ucrt64\bin\g++.exe`. Not found gives a clear message naming both.
  (The user's PATH currently holds `C:\msys64\ucrt64\bin.` with a trailing dot; fixing
  that is recommended but not required.)
- **Compile:** `g++ -std=c++17 -O2 -o sol.exe sol.cpp`, 30 s timeout. Failure gives
  verdict `CE` with the first 20 lines of compiler output.
- **Run:** each test through `subprocess.run` with stdin from the `.in` file, cwd = the
  problem folder, timeout = `2 × time_limit` wall-clock. Timeout gives `TLE`, non-zero
  exit gives `RE`.
- **Compare:** whitespace-separated tokens must match exactly. Mismatch gives `WA`.
- **Stop at the first failure** and report `WA on test 7/20`. The failing input is shown
  only for warm-ups and only when it is ≤ 500 characters; for a main problem, seeing the
  input is itself a hint, so it stays hidden.
- **Archive problems** are graded against their samples only, reported as
  `samples OK — submit at <url>`, and recorded with verdict `unsubmitted`. The real
  verdict comes from the user typing it in chat through the existing `verdict_in` path.
- Runs on a worker thread, same pattern as the mentor turn; Stop kills the running
  compiler or `sol.exe`.

Every grade writes an `attempt` row: `body` = the `sol.cpp` source (capped at
`MAX_TEXT`), `verdict` = the measured result. AC sets the problem to `solved`. Since the
verdict is measured, it can unlock mentor rung 4 honestly.

`memory.VERDICTS` gains `"CE"`.

### 7.1 Safety

The user's own code runs locally with no sandbox beyond the timeout and working
directory, the same as running it from their editor. Bank files are repository content,
reviewed before commit. Model output never selects a path, a command or a level.

## 8. Offline generator

`tools/make_problem.py --level 1 --topic implementation [--count N]`, run by the
developer, not by Victor.

1. Ask Claude (via the existing `claude -p` plumbing) for JSON: `title`, `statement`,
   `reference_cpp`, `brute_cpp`, `gen_py` (reads a seed and a size flag, prints one
   input), `time_limit`.
2. Compile reference and brute.
3. Run 300 small random inputs through both. Any disagreement, crash or timeout rejects
   the candidate.
4. Run the reference on maximum-size inputs; exceeding the time limit rejects it.
5. Write the bank entry with about 12 small and 8 maximum-size tests, expected outputs
   from the reference.
6. The developer reads each statement before committing.

Target for the first bank: about 20 problems across levels 1 and 2 and several topics.

`problems/archive.json` is curated by hand with web research, starting with about 30
problems across levels 3–5.

## 9. Testing

`python -m unittest discover -s tests`, extending the existing suite.

**`tests/test_grader.py`**: tiny C++ fixtures. AC, WA, TLE (infinite loop), RE (non-zero
exit) and CE (syntax error) each yield the right verdict. Stop-at-first-failure reports
the right test number, and main problems hide the failing input. Skipped when no g++ is
found.

**`tests/test_daily.py`**
- `ensure_today` is idempotent on the same date.
- A served problem is never served again.
- Warm-up is level − 1.
- Floor: day 1 with 6 ACs stays in Camp 1.
- Ceiling: day 4 with no ACs moves to level 3.
- Step up after 3 low-rung solves; step down after 2 give-ups; never below 3.
- At most one level change per day.
- An exhausted level falls back instead of raising.

**`tests/test_make_problem.py`**: a reference that disagrees with the brute force is
rejected.

## 10. Build order

1. `grader.py` and `CE` verdict. Useful on its own.
2. `tools/make_problem.py` and the first Camp-1 bank.
3. `problems/archive.json`.
4. `daily.py`: ramp and daily pick.
5. Today card, Grade button and `ตรวจ` in `app.py`.

## 11. Out of scope

- Runtime problem generation (approach B).
- Sandboxing the user's code.
- Voice for the daily card.
- Automatic submission to online judges.
- Scraping judge sites at runtime.
