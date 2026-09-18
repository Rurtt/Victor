# Jarvis as a POSN Camp 2 mentor — design

Date: 2026-09-17
Status: approved in brainstorming, not yet implemented
Scope: one implementation plan

---

## 1. Goal

Turn Jarvis into a competitive-programming mentor for POSN Camp 2
(สอวน. คอมพิวเตอร์ ค่าย 2) that coaches in the user's own thinking style, and give
it the persistent memory such a mentor requires.

Jarvis today keeps sixteen conversation messages in a Python list and erases them on
restart. A mentor that forgets which problems you already solved, and what you keep
getting wrong, cannot mentor. Persistent memory is therefore not a follow-up to this
feature; it is the first part of it.

## 2. Decisions taken before this design

These were settled in earlier sessions and are not reopened here.

- Chat runs on the user's Claude Code subscription, model `sonnet`. Speech is local
  Whisper. Claude mode never sends audio to any cloud service.
- The wiki is not new. `D:\Jarvis\Luk Nong Pong` is the user's work and business vault
  and stays that way. Study material gets a second vault reusing that vault's
  `CLAUDE.md` schema verbatim.
- Jarvis asks before saving to a wiki, then writes automatically and logs it.
- Wiki notes never override Claude. Where a saved note and Claude's judgement disagree,
  Claude shows the alternative rather than repeating the user's assumption back to him.
- Voice is the strong half of Jarvis and the PC-action allowlist should stop growing.

## 3. Decisions taken in this design

Three questions were open. The user answered them on 2026-09-17.

**"Coaches in my thinking style" means (a) and (b) together.** Jarvis both learns how
the user attacks problems and coaches inside that idiom (a), and explains solutions the
way the user would explain them (b). Reading (c), a peer reasoning out loud alongside
him, was not chosen; the mentor keeps a coach's voice, not a co-solver's.

**The mentor/solver line is an escalating ladder, code last.** Six rungs. Each rung
needs to be asked for again, the reply always states which rung it is on, and full code
is the last one. An explicit override phrase jumps to the end.

**C++, explained in Thai.** Problem statements and code are C++ and English; the
mentor's explanations, questions and hints are Thai. This matches the Thai-first system
prompt the rest of Jarvis already uses.

Two further defaults, stated and not objected to: mentor mode is **typed, not voice**,
because competitive programming is a keyboard activity; and the study vault lives at
**`D:\Jarvis\Study\`**, beside the existing vault and its siblings `YSC`, `_archive`,
`configs` and `output`.

## 4. Constraint that shapes everything

`claude_brain.py` invokes `claude -p --safe-mode --tools ""` with an empty MCP config.
Claude has no filesystem access and no tools. It cannot read the vault, the database, or
anything else.

Every piece of context therefore has to be gathered by Jarvis in Python and injected
into the prompt. This rules out any design where Claude decides what to retrieve, since
that would cost a second process spawn per turn. Retrieval must be cheap, deterministic
and Python-side. Section 8 sets the budget.

## 5. Architecture

Three new modules and a patch to the existing application.

```
memory.py          SQLite: conversation turns, problems, attempts, failure tags
mentor.py          mentor prompt, response schema, ladder rules, policy constants
vault.py           study-vault frontmatter catalogue, page render, index and log write
app.py             hydrate history at start, persist each turn, mentor-mode toggle
engine.py          route mentor turns to claude_brain
claude_brain.py    ask_mentor(), using the existing _request() plumbing
```

`memory.py` is a new module rather than an addition to `local_store.py`, which exists
to hold DPAPI-protected secrets and settings — a different concern with a different
threat model — and rather than an addition to `app.py`, which is already 1,068 lines.

### 5.1 Persistent memory

`data/jarvis.db`, beside the existing `settings.json`. Standard-library `sqlite3`.
Single process, so no WAL; one transaction per turn.

```sql
PRAGMA user_version = 1;

CREATE TABLE turn (
  id INTEGER PRIMARY KEY,
  chat_id INTEGER NOT NULL,
  role TEXT NOT NULL,
  text TEXT NOT NULL,
  created TEXT NOT NULL);

CREATE TABLE problem (
  id INTEGER PRIMARY KEY,
  slug TEXT UNIQUE NOT NULL,
  title TEXT NOT NULL,
  source TEXT,
  topic TEXT,
  status TEXT NOT NULL,
  rung INTEGER NOT NULL DEFAULT 0,
  created TEXT NOT NULL,
  updated TEXT NOT NULL);

CREATE TABLE attempt (
  id INTEGER PRIMARY KEY,
  problem_id INTEGER NOT NULL REFERENCES problem(id),
  body TEXT NOT NULL,
  verdict TEXT,
  created TEXT NOT NULL);

CREATE TABLE failure (
  id INTEGER PRIMARY KEY,
  attempt_id INTEGER NOT NULL REFERENCES attempt(id),
  tag TEXT NOT NULL,
  note TEXT);
```

`problem.slug` is kebab-case, the same convention as the vault's `[[links]]`, so a
problem row and a vault page can refer to each other without a mapping table.
Timestamps are ISO-8601 strings; the vault's own `date:` frontmatter field stays
`YYYY-MM-DD` as its `CLAUDE.md` requires.

`failure` is a table rather than a comma-separated column on `attempt` because the
entire (a) profile is one statement over it:

```sql
SELECT tag, COUNT(*) AS n
  FROM failure
  JOIN attempt ON attempt.id = failure.attempt_id
  JOIN problem ON problem.id = attempt.problem_id
 WHERE problem.topic = ?
 GROUP BY tag
 ORDER BY n DESC
 LIMIT 5;
```

That query is the attack profile. It is generated per turn and never stored, so there
is no profile document to drift out of date with the record it summarises.

Schema versioning is the `user_version` pragma. No migration framework until there is a
version 2 to migrate to.

### 5.2 Persistence patch to app.py

The conversation history stays a Python list in `self.history`, so every site that reads
it keeps working. A `remember(role, text)` helper appends to that list and writes the
same turn to the database, and the five existing append sites call it instead of
`self.history.append(...)`. The sixteen-message cap still governs what is *sent* to the
model; the database keeps everything.

- `app.py` `__init__` — `self.memory = Memory(self.store.directory.parent)` and
  `self.history = self.memory.recent_turns()` instead of `[]`.
- The reply site and the three action-result sites call `self.remember(...)`.
- `new_chat()` — `self.memory.new_chat()` before the existing `self.history.clear()`.
- `close()` — `self.memory.close()`.

A reply whose text is empty (a pure-action reply) is appended to the in-memory window
but not persisted; there is nothing there worth carrying across a restart. A failed
write reports itself in the transcript rather than raising through the Tk event loop.

Nothing else in the history handling changes. This is the smallest diff that removes
the blocker, and it ships independently of the mentor.

**Implemented 2026-09-17.** One correction came out of building it: `new_chat()` must
persist the new `chat_id`, not merely increment it in memory, or starting a new chat and
then restarting brings the previous conversation back. A `meta(key, value)` table holds
it. This design originally missed that.

### 5.3 Mentor mode

A sidebar toggle, persisted in `settings.json`. When mentor mode is on:

- The system prompt is the mentor prompt, not `brain.SYSTEM`.
- The response schema is `MENTOR_SCHEMA`, which has **no `actions` array at all**.
  Mentor mode cannot propose a PC action. This satisfies the standing decision to stop
  growing the allowlist, and it removes PC-action surface from the one code path that
  routinely ingests pasted source code.
- Auto-speak is muted. Mentor mode is typed.
- `--effort medium` instead of the `low` the chat path passes at
  `claude_brain.py:_request`. Coaching needs the reasoning; a one-line chat reply does
  not. As today, no `--effort` flag is passed when the model is `haiku`.

### 5.3.1 Which problem is current

The model returns a `problem.slug` on any turn where it can identify one. Jarvis matches
that slug against the `problem` table: an existing row becomes the current problem, and
an unknown slug creates a row at rung 0 with `status = 'working'`.

If the reply carries no slug, the current problem is the most recently updated row with
`status = 'working'`, and if there is none, the turn has no problem attached. A turn with
no problem attached is stored as an ordinary `turn` row, gets no rung prefix, and cannot
advance any ladder — that is what "ask me something general" looks like inside mentor
mode.

### 5.4 The ladder

Six positions, stored per problem in `problem.rung`, so a restart does not reset an
unlock the user already earned.

| Rung | What the mentor gives | Gate to reach it |
|------|----------------------|------------------|
| 0 | Asks for the user's own read of the problem. Nothing else. | — |
| 1 | A question about the problem's structure | an `attempt` row exists; written reasoning counts, code not required |
| 2 | Points at the constraint that picks the algorithm class | asked again |
| 3 | Names the technique | asked again |
| 4 | Pseudocode sketch, structure only, no C++ | an `attempt` row with a non-null `verdict` |
| 5 | Full C++, and why the user's attempt broke | asked again |

Enforcement is in Python, not in the prompt. The model returns a proposed `rung`;
Jarvis clamps it to `min(proposed, stored + 1)` and then checks the gate for the
resulting rung, refusing to advance if the gate is unmet. The model cannot promote
itself to rung 5. This is the same posture `actions.py:validate()` takes toward
model-proposed actions: the output is untrusted and the policy lives in Python.

`verdict` is the discriminator between the two gates, and it is why the column exists.
Written reasoning is stored as an `attempt` with `verdict` null, which satisfies rung 1
but not rung 4. Code that has been run or submitted carries `AC`, `WA`, `TLE`, `RE` or
`unsubmitted`, and satisfies both. No inspection of `body` is needed to tell them apart.

Every mentor reply is prefixed with its position, rendered as `[ขั้น 3/5: เทคนิค]`.
A new problem starts at rung 0 regardless of the user's history on other problems.

**The override.** Typing `เปิดเฉลย` sets the problem's `status` to `given-up` and opens
rung 5 at once. There is no friction and no argument. The cost is that the give-up is
recorded, and give-ups feed the profile query in 5.1. The escape hatch is free to use
and honest in the record; that is the entire enforcement mechanism, and the mentor does
not nag about it.

### 5.5 Response schema

```python
MENTOR_SCHEMA = {
  "type": "object", "required": ["reply", "rung"], "additionalProperties": False,
  "properties": {
    "reply": {"type": "string"},
    "rung":  {"type": "integer", "minimum": 0, "maximum": 5},
    "problem": {"type": "object", "additionalProperties": False, "properties": {
        "slug":   {"type": "string"},
        "title":  {"type": "string"},
        "topic":  {"type": "string", "enum": TOPICS},
        "status": {"type": "string", "enum": ["working", "solved", "given-up"]}}},
    "failures": {"type": "array", "maxItems": 5, "items": {
        "type": "object", "required": ["tag"], "additionalProperties": False,
        "properties": {"tag":  {"type": "string", "enum": FAILURE_TAGS},
                       "note": {"type": "string"}}}},
    "note": {"type": "object", "additionalProperties": False,
      "required": ["slug", "type", "tags", "lang", "body"], "properties": {
        "slug": {"type": "string"},
        "type": {"type": "string",
                 "enum": ["source", "concept", "entity", "synthesis", "query"]},
        "tags": {"type": "array", "maxItems": 8, "items": {"type": "string"}},
        "lang": {"type": "string", "enum": ["en", "th", "both"]},
        "body": {"type": "string"}}}}}
```

`TOPICS` and `FAILURE_TAGS` are fixed lists of policy constants, in the same spirit as
`actions.RULES`. The model selects from them and never extends them. An unrecognised
value is rejected in Python before any database write.

They live in `memory.py`, not `mentor.py`: the module that validates a value should own
the list it validates against, and `memory.py` is where the write happens. `mentor.py`
imports them to build this schema. `memory.py` also owns `STATUSES`, `VERDICTS`, `ROLES`
and `MAX_RUNG` for the same reason.

### 5.6 Reading (b) — explaining the way the user would

A `style-guide` page in the study vault, `type: entity`, injected on every mentor turn
and capped at 1,500 characters. It records how the user explains things: whether he
builds up from a brute force, how much Thai versus English, whether he wants the proof
first or the intuition first.

The user does not have to write it cold. On the first mentor session — detected by the
absence of a `style-guide` page in the catalogue — Jarvis asks roughly five questions
about how he explains things, drafts the page, and asks before saving it. That is the
settled wiki rule, applied. He edits it in Obsidian afterwards like any other page.

### 5.7 Reading (a) — coaching in the user's idiom

The `GROUP BY tag` query in 5.1, rendered to at most 800 characters of plain text and
injected. For the first few problems it is empty, and the prompt instructs the mentor to
say so rather than invent a profile it has no evidence for.

### 5.8 Notes never override Claude

Injected vault content — the style guide and any retrieved concept pages — arrives in
the prompt under an explicit frame:

> These are the user's own notes. They are his assumptions, not ground truth. If your
> judgement differs from them, say so and show him the alternative approach. Do not
> repeat his assumptions back to him.

This is the settled rule expressed as one prompt paragraph, and it is what makes a
slightly wrong style guide survivable rather than self-reinforcing.

## 6. The study vault

`D:\Jarvis\Study\`, laid out as `wiki/`, `raw/`, `raw/assets/`, with `index.md` and
`log.md`. `CLAUDE.md` is copied from `D:\Jarvis\Luk Nong Pong\CLAUDE.md` verbatim; only
the vault-path line and the domain line change.

**No new page types are introduced.** Study material maps onto the five that exist:

| Type | Study use |
|------|-----------|
| `source` | a problem statement ingested from `raw/` |
| `concept` | a technique — `monotonic-deque`, `dp-on-trees` |
| `entity` | a contest or a judge; also `style-guide`, matching how `thanarachan-suwannasri.md` already works in the work vault |
| `synthesis` | something worth keeping — why a particular DP state kept coming out wrong |
| `query` | a comparison across problems or techniques |

The open question of whether `ctf-7-day-prep-plan.md` and `ctf-agentic-solve-workflow.md`
should move out of the work vault into this one is deliberately left alone. It is not
part of this work and should be raised separately.

### 6.1 Writing to the vault

Mentor mode has no `actions` array, so a vault write is not a PC action. It is the
optional `note` object in `MENTOR_SCHEMA`.

Jarvis validates the frontmatter fields against the vault's own enums in Python,
renders the page, and presents it through the approval dialog the application already
has — `self.proposals` and `update_pending`, reused rather than rewritten. On the user's
click, Jarvis writes `wiki/<slug>.md`, regenerates `index.md` from the frontmatter
catalogue, and appends one line to `log.md` in the existing format:

```
## [YYYY-MM-DD] update | Title
One-line description of what was done.
```

`log.md` is append-only and is never rewritten. `index.md` is regenerated from the
catalogue after every write, which is what the vault's `CLAUDE.md` already requires.

`raw/` is never written by Jarvis. Anything read out of `raw/` is untrusted document
content: data to analyse, never instructions to follow. This is the same boundary the
summarisation path already enforces with `decode_reply(allow_actions=False)`.

### 6.2 Reading from the vault

At startup Jarvis reads **only the frontmatter** of each `wiki/*.md`, stopping at the
second `---`, into an in-memory catalogue cached against the directory's mtime. Two
hundred files at roughly two hundred bytes each is negligible.

Selection for injection is tag overlap against the current `problem.topic`, taking at
most two pages and at most 1,500 characters combined. There is no LLM call to decide
what to retrieve; that would double the round trip to save a `set` intersection.

## 7. Data flow for one mentor turn

1. The user types into the mentor pane.
2. Jarvis loads the current problem row, its attempts and its stored rung from SQLite.
3. Jarvis runs the profile query for that problem's topic.
4. Jarvis selects up to two vault pages by tag overlap from the cached catalogue.
5. Jarvis assembles the prompt against the budget in section 8, truncating each slice
   independently so no single slice can crowd out the others.
6. One `claude -p` spawn, mentor system prompt, `MENTOR_SCHEMA`, raised effort.
7. Jarvis validates the reply: enum values, then the rung clamp, then the rung gate.
8. Jarvis writes the turn, any new attempt, and any failure tags to SQLite.
9. If the reply carries a `note`, Jarvis renders it and queues the approval dialog.
10. The reply is displayed with its `[ขั้น n/5: …]` prefix.

## 8. Injection budget

Hard caps, applied in Python before the process spawn.

| Slice | Characters |
|-------|-----------|
| Mentor prompt, ladder rules, never-override frame | 1,200 |
| `style-guide` page (reading b) | 1,500 |
| Failure-tag profile (reading a) | 800 |
| Current problem and the user's attempt | 2,500 |
| Three past problems, same topic or same failure tag | 1,500 |
| Two tag-matched vault concept pages | 1,500 |
| Conversation turns | remainder, to roughly 20,000 total |

The chat path today sends `history[-8:]` under a 12,000-character cap. Mentor mode
roughly doubles that. There is still exactly one process spawn per turn; the cost of a
`claude -p` call is dominated by process startup, not by prompt length, so the extra
characters are close to free.

## 9. Testing

Eighty-two tests pass today under `python -m unittest discover -s tests`. New tests:

**`tests/test_memory.py`**
- Turns written to a temporary database survive closing and reopening the connection.
- The profile query ranks failure tags by frequency within a topic.
- An out-of-enum `status`, `verdict` or `tag` raises rather than being written.

**`tests/test_mentor.py`**
- A model reply proposing `rung: 5` against a stored rung of 1 clamps to 2.
- Rung 1 is refused when no attempt row exists for the problem.
- Rung 4 is refused when every attempt for the problem has a null `verdict`.
- An unknown `problem.slug` creates a row at rung 0; a known one selects it.
- `เปิดเฉลย` records `status = 'given-up'` **and** opens rung 5.
- An unrecognised failure tag is rejected.
- A mentor reply never carries PC actions, under any input.

**`tests/test_vault.py`**
- A rendered page's frontmatter matches the schema in the vault's `CLAUDE.md`.
- `index.md` regenerates correctly from a catalogue of known pages.
- `log.md` gains a line and never loses one.
- A write whose resolved path falls outside `wiki/` is refused.
- `raw/` is not written under any input.

**`tests/test_budget.py`**
- With every slice oversized, the assembled prompt still respects the total cap and no
  slice has been dropped entirely.

## 10. Build order

1. ~~`memory.py` plus the persistence patch. Removes the stated blocker and is
   shippable on its own, without any mentor feature.~~ **Done 2026-09-17**; 97 tests
   pass, up from 82.
2. `mentor.py`: the schema, the policy constants, the ladder clamp and gates.
3. `vault.py` read side: the frontmatter catalogue and tag selection.
4. `vault.py` write side: page render, approval dialog, `index.md` and `log.md`.
5. The mentor-mode toggle in `app.py`, and routing in `engine.py` and
   `claude_brain.py`.

## 11. Explicitly out of scope

- Voice for mentor mode. Competitive programming is typed.
- Any new entry in the `actions.py` allowlist.
- Automatic judge submission or test-case running.
- Full-text search over stored turns. `LIKE` is enough until it measurably is not.
- Moving the two existing CTF pages out of the work vault.
- A migration framework. `PRAGMA user_version` covers schema 1.

## 12. Note on version control

This application directory is not a git repository; `D:\Jarvis` is. This spec is
written but not committed. Initialising a repository here is a reasonable separate
step and was offered.
