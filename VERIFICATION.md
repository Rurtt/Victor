# Verification — 2026-09-18

(App is Victor, formerly Jarvis — renamed only; no behavior changed.)

## Passed

- 168 automated tests (`python -m unittest discover -s tests`) across the policy
  layer, cloud request handling, speech cancellation, provider routing, the tray
  message loop, the wake-word turn, the mentor ladder and wiki flow, and real Tk
  desktop flows with simulated AI results.
- Conversation history survives a restart, and starting a new chat is not undone
  by one. History lives in `data/jarvis.db`; the sixteen-message cap now governs
  only what is sent to the model.
- The hint ladder is enforced in Python: a model reply proposing rung 5 against a
  stored rung of 1 is clamped to 2 and its text withheld, rung 1 is refused
  without an attempt, and rung 4 is refused until an attempt carries a verdict.
  A problem a reply names starts at rung 0 if new, and a given-up problem stays
  given-up even when a later reply proposes "working" again. Whenever the
  model's proposed rung exceeds what it was actually granted — including a
  turn with no problem attached, where the pre-call ceiling stands in for the
  granted rung — Victor withholds that reply's text outright: only the true
  rung label (when there is one) and a fixed Thai nudge are shown or stored,
  never the over-rung text itself. เปิดเฉลย only overrides when it is the
  entire message, not a substring, so a negation like "อย่าเปิดเฉลยนะ" does not
  record a give-up.
- An attempt is recorded either on the model's own flag, or — read from the
  user's text in Python, never from the model — a verdict word (`AC`/`WA`/`TLE`/
  `RE`) or C++-looking text (`#include` / `int main`, recorded `unsubmitted`).
- Mentor replies cannot carry PC actions; the schema has no actions key. The
  Summarize flow never routes to the mentor, even while Mentor mode is on.
- Wiki writes stay inside `wiki/`, `log.md` is only ever appended to, and `raw/`
  is never written. Saving a note that would replace an existing page warns in
  the dialog first. The vault reader skips a page it cannot decode and notices a
  page edited in place in Obsidian, since each page's own mtime is checked.
- `python app.py` starts clean with no stderr output (measured on the 2026-09-16
  build; not re-measured for this fix wave).
- Measured idle cost on this PC as of the 2026-09-16 build: 0.55 % of one core
  and 59 MB resident, against 2.73 % and 60 MB for the previous build over the
  same 20-second idle window. Not re-measured for this fix wave.
- Claude mode refuses to send audio to any cloud service; the test asserts
  `brain.transcribe` and `brain.synthesize` are never called for a Claude model.
- The tray survives a callback that raises, and its instance guard is reentrant
  within one process and releasable.
- PC proposals remain pending until the approval button is pressed. Cancel and
  Stop invalidate their local tickets; an old reply cannot restore a stopped action.
- AI-supplied shell commands, extra approval fields and unexpected arguments
  are rejected. Summarization responses cannot carry PC actions.
- Text destined for speech is piped as data, not inserted into PowerShell source.
- Python 3.14 with Tk 8.6 is available on this PC. The app uses only standard
  Python libraries and built-in Windows components.
- Windows recognition reports English (US). Windows SAPI reports David and Zira
  voices. A short SAPI synthesis test produced 117,486 audio bytes in memory
  outside the restricted execution sandbox; no microphone was used or audio played.

## Requires your desktop test

- Gemini authentication, model access, actual replies and account quota require
  your API key. No live AI request was made during this build.
- No live Claude request was made either. `claude auth status` reported a
  signed-in Pro subscription, but the `claude -p` call path in `claude_brain.py`
  is exercised only against mocks.
- No live mentor request was made. `claude_brain.ask_mentor` is exercised only
  against mocks, as the chat path already is.
- The study vault at `D:\Jarvis\Study` was created by hand; page writes against a
  real Obsidian vault have not been observed outside temporary directories.
- Mentor turns now use the chat path's worker/generation machinery: only
  `ask_mentor` runs off the Tk thread, and Stop both drops the queued reply
  (no rung recorded) and makes `claude_brain._run` terminate the `claude -p`
  child. Covered by mocked UI tests only; cancelling a real in-flight `claude`
  process from mentor mode has not been observed.
- The style-guide interview from spec §5.6 (Victor drafting the `style-guide`
  page from a first-session interview) was not built. Write that page in
  Obsidian by hand; without it mentor mode still works, just without an
  adapted voice.
- `scripts\install-voice.ps1` has never been run end to end. The pinned SHA-256
  values were read from the GitHub and Hugging Face APIs on 2026-09-16; the
  download, extraction and manifest write are untested.
- Real microphone recognition and audible playback need testing with your devices.
- Untested interaction: the wake-word recognizer holds the default microphone
  open while enabled, and the MCI recorder opens the same device when it starts
  recording. Whether Windows shares the device cleanly here has not been checked.
- Tests mock app launches and media commands; they do not send actual keyboard or
  media input. Notes are tested using temporary directories.
- No independent security audit or comprehensive penetration test was performed.

The Windows speech engine denied synthesis inside the tool sandbox, then passed
in the ordinary user environment. Use the supplied launcher from your desktop.

# Verification — 2026-09-19 (daily practice, grader, ramp)

The GUI was not launched for this check: a live Victor may have been running on this
PC, and a real launch of `Start Victor.cmd` writes today's set into `D:\Jarvis\Study`.
Instead the real problem bank and real grader were driven end to end from a script
against a temporary data directory, with no repo or `D:\Jarvis\Study` files touched.

## Scripted check (actual, not mocked)

Ran with the real `bank.py`, `daily.py`, `grader.py` and `memory.Memory`, a temporary
`tempfile.mkdtemp()` directory standing in for the app's data folder, and today's date
(2026-09-19):

1. `bank.load(problems/)` loaded **55 bank entries** with no `BankError`.
2. `daily.ensure_today(m, entries, tmp/daily, today)` on a fresh `Memory` returned
   `[]` (no ramp-change notice — day 1, level 1) and served:
   - warm-up: `camp1/traffic-light-query` (level 1)
   - main: `camp1/caesar-shift-decoder` (level 1)

   `tmp/daily/2026-09-19/warmup/statement.md` and `.../main/` both existed with a
   `sol.cpp` template, matching spec §6 step 4.
3. Read the warm-up's real `statement.md` (a traffic-light color query problem) and
   wrote an actual correct C++ solution (mod-arithmetic on `t mod (R+G+Y)`) into
   `warmup/sol.cpp`. `grader.grade(...)` compiled it with the fallback
   `C:\msys64\ucrt64\bin\g++.exe` and ran all 20 tests:
   **verdict `AC`, detail `AC 20/20`.**
4. Overwrote `warmup/sol.cpp` with a deliberately wrong solution (always prints
   `Red`). Re-graded: **verdict `WA`**, detail:
   ```
   WA on test 1/20
   input:
   4 4 1 3
   25
   19
   30
   ```
   Confirms the failing input is shown for a warm-up (spec §7 "Stop at the first
   failure").
5. Called `daily.ensure_today(...)` again on the same `Memory`/date: returned `[]`
   and `m.daily_rows("2026-09-19")` was byte-for-byte equal to the first call's rows
   — confirms idempotency (spec §6 step 1).

**Verdicts: AC confirmed, WA confirmed (input shown, warm-up), idempotent confirmed.**
`ตรวจ`/mentor-mode grading and the Today card itself were not exercised here since
those are UI-level (`app.py`); the grading call they both delegate to (`grader.grade`)
is the same one exercised above.

## Full test suite

```
python -m unittest discover -s tests
```

**239 tests, OK** (0 failures, 0 errors). No live Victor process held the tray's
instance-guard mutex during this run, so `tests.test_tray` ran clean; when a live
Victor is running, `InstanceGuardTests` in that module is expected to fail on the
mutex-contention case only (environmental, not a regression).

## Pending — run by the user

The brief's six-step live GUI walkthrough was not performed, per the controller
ruling above (risk of a live Victor writing into `D:\Jarvis\Study`). Still to do,
by the user, from the desktop:

1. Run `Start Victor.cmd`. Confirm the sidebar shows TODAY with a warm-up and a
   main problem.
2. Confirm `D:\Jarvis\Study\daily\<today>\main\statement.md` and `sol.cpp` exist
   (Open button).
3. Write a correct solution for the warm-up in `sol.cpp`, press Grade → `AC n/n`,
   card shows AC.
4. Break it (print 0), press Grade → `WA on test k/n` plus the input (warm-up
   only).
5. Turn on mentor mode, type `ตรวจ` → grades the current problem, no Claude call.
6. Close and reopen Victor → no new problems served today, card unchanged.
