# Mentor context files

**Problem.** `claude -p --tools ""` means Victor sees only what Python puts in the
prompt. Mentor turns sent the problem slug and the last *graded* `sol.cpp`, never
the statement or live code, so every session began with pasting.

**Decision.** Python re-reads files from disk every mentor turn and adds them as a
budgeted slice of `mentor.build_prompt` (approach A). Rejected: giving Claude a
`Read` tool (slower, more tokens, breaks the gather-in-Python invariant, turns file
text into injection surface with a live tool); a code knowledge graph (CP files are
single 50-200 line files).

- **Auto:** current problem is a daily row -> that day's `statement.md` (3,000
  chars) + `sol.cpp` (6,000 chars).
- **Pinned:** 📎 button, native file dialog, allowlisted text extensions, <=200 KB,
  no NUL bytes. Stays until its chip is clicked or New chat. A pinned file that
  becomes unreadable is unpinned with a warning; the turn still goes out.
- Long files keep head and tail. Files are framed as data, not instructions.
- Files never count as an attempt: `has_attempt`/`has_verdict` still come only
  from the DB and the user's typed text.
- No auto-attach when no problem is identified.

Tests: `tests/test_mentor.py::ContextFileTests`, `tests/test_ui.py::ContextFileAppTests`.
