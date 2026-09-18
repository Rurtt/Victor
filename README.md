# Jarvis — your personal assistant, v0.1

A Windows desktop prototype built for this workspace. Chat with Claude or Gemini,
dictate a message, listen to replies, summarize chosen text, and approve a small
set of PC actions. It waits in the system tray and can answer the wake word
"Jarvis" hands-free. This is a new independent implementation; it does not run or
depend on Mark-LIII.

## Start

1. Double-click **Start Jarvis.cmd** in this folder.
2. Open **AI settings** and pick a model.
   - `sonnet`, `haiku` or `opus` use the **Claude Code** you are already signed
     into. No API key. Requests count against your Claude plan.
   - `gemini-…` uses a Gemini API key; paste it into the masked field.
3. Type a message and click **Send**, or press **Ctrl+Enter**.

The default is `sonnet`. Claude mode needs `claude.exe` on your PATH and a
`claude.ai` login — check with `claude auth status`. Jarvis calls it with
`--safe-mode` and no tools, so Claude can only answer and propose actions; every
PC action still needs your click here.

Requires Windows and Python 3.12+ with Tkinter, Pillow (`pip install pillow`, used
for screenshots) and customtkinter 5.2.2 (the interface). **Start Jarvis.cmd**
installs customtkinter automatically the first time. If that fails, run
`py -m pip install customtkinter==5.2.2`, or run `python app.py` in this folder to
see startup errors. Do not run as administrator.

The default model is `gemini-3.8-flash`, listed in Google's model documentation
when this app was built. Change the model ID in settings if your project cannot
access it. Connecting settings does not validate the key; the first message
makes the first API request. A paid API account may incur usage charges.

## Try these

- “Help me plan my afternoon.”
- “Explain this paragraph in simple terms: …”
- “Draft a polite reply to this email: …” (Jarvis drafts; you send.)
- “Open Calculator.”
- “Open https://www.wikipedia.org.”
- “Search the web for beginner guitar lessons.”
- “Save a note: My three priorities tomorrow are …”

**PC actions** in the sidebar lets you try a few actions without an API key.
Every action gets a preview and a separate approval button. The model cannot
provide its own approval. Starting another request or pressing Stop discards
pending proposals. Notes are new `.txt` files inside this folder's `notes/`.
They are never automatically opened or executed.

## Background mode and the wake word

Closing the window hides Jarvis in the system tray instead of quitting. Double-click
the tray icon to bring it back; right-click for **Open**, **Listen once**,
**Wake on/off**, **Stop / mute** and **Exit**. Only **Exit** ends the program.
Starting Jarvis twice just reopens the first copy's window.

The **คำเรียก "Jarvis"** switch turns on wake-word listening. Detection runs
entirely on this PC with the Windows English recognizer — no audio leaves the
machine and no cloud request is made while it waits. Say "Jarvis", wait for the
beep, then speak your command; Jarvis transcribes it locally, sends only the text
to your model, and reads the answer aloud without opening the window. The
hands-free recording window is 7 seconds (`WAKE_SECONDS` in `app.py`).

Idle cost measured on this PC: about **0.55 % of one core and 59 MB**, against
2.7 % before this change. The chat loop now polls at 250 ms when idle and 80 ms
while a request is running.

## Voice

Install the offline Thai speech runtime once — **AI settings → ติดตั้งเสียงไทยในเครื่อง**,
or from PowerShell in this folder:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\install-voice.ps1
```

It downloads whisper.cpp `b5130` (`whisper-bin-x64.zip`, CPU only) and the
`ggml-small` model, **verifies both against SHA-256 values pinned in the script**,
and writes `runtime\voice-manifest.json`. About 500 MB. `local_voice.py` re-checks
every file against that manifest before each transcription and refuses to run on a
mismatch. If you ever change the pinned tag, change its hash in the same edit.

Once installed, Whisper handles dictation offline, and replies are spoken by
Windows. Thai output needs the Thai voice pack (Settings → Time & language →
Speech, `ms-settings:speech`); without it `speak-local.ps1` says so instead of
falling back to English.

The **●** mic button next to Send starts recording (Windows built-in recorder,
no extra software). Click it again when done; it auto-stops at 60 s. The
transcript goes into the message box for you to review before sending.

Without the local runtime, Gemini mode still transcribes and speaks through
Google as before. **Claude mode never sends audio to any cloud service** — it
requires the local runtime and says so if it is missing.

**อ่านคำตอบ** reads the last reply aloud; **อ่านตอบอัตโนมัติ** does it for every
reply. **Stop** or **Esc** cuts it off.

## Window sizes

Drag the window narrower than about 720 px and the sidebar folds into the **☰**
menu; text stays the same size. **⤡** shrinks Jarvis to a small always-on-top
floating window; **⤢** puts it back. Hover any icon button to see its name.
Right-click a message, or click **คัดลอก**, to copy it.

## When Gemini is busy

HTTP 500/502/503/504 mean Google's servers are overloaded, not that your key is
wrong. Jarvis retries up to 3 times (after 2, 4 and 8 seconds, or the wait Google
asks for, at most 10 seconds) and shows "Gemini ไม่ว่าง กำลังลองใหม่" in the chat.
Press **■** or **Esc** to stop waiting. Quota errors (HTTP 429) are not retried,
because retrying uses more quota. If it keeps happening, try again later or pick
another model ID in AI settings.

## Summaries

Click **Summarize text or file**. Paste text, or select a UTF-8 `.txt`, `.md`,
`.csv`, `.json` or `.log` file. Review the text and click **Send to Gemini &
summarize**. Limit: 59,500 characters. For PDF, Word, emails or web pages,
copy and paste the relevant text in this first version.

Summarization cannot propose PC actions: responses containing an action are
rejected by application code. Summary requests exclude earlier chat history.
The resulting summary becomes part of this conversation; the raw document does
not get appended to later chat turns. The source file is not modified.

## Screen control (mouse and keyboard)

Ask in chat, e.g. “เปิด Spotify แล้วกดเล่นเพลง”. Jarvis proposes `control_screen`;
approve it to start. Then, per step:

1. Jarvis hides itself and screenshots the **primary monitor**.
2. The screenshot and your goal go to Gemini, which returns one step:
   click, double click, right click, type one line, scroll, or one allowed key.
3. A dialog shows the step and a red marker on the screenshot.
   **อนุญาตขั้นนี้** runs it; **หยุดงานนี้** or Esc ends the task.

Limits: 25 steps per task, primary monitor only, no Windows key or Win+R,
typed text cannot contain Enter. Text on screen is treated as untrusted.
Jarvis is told never to type passwords or confirm payments/deletions, but
that is an AI instruction, not a guarantee — read each step before approving.
**Every screenshot is sent to Google.** Close private windows first.

## Discord (from your own account)

**Warning:** Discord forbids automating normal user accounts. Your account can
be banned. You chose this; the rules below limit damage, not that risk.

Sidebar → **Discord และกฎการส่ง**. One line per person/channel:
`ชื่อ = https://discord.com/channels/...` (right-click chat → Copy Link).
Saved in `data/discord.json`. Then ask in chat: “ส่ง Discord หา ชื่อ ว่า ...”.

Rules enforced in code: listed names only, 10 messages per hour, one line up to
1,000 characters, no `@everyone`/`@here`, Jarvis opens the chat and checks
Discord is the front window before typing and again before Enter. With
**ส่งทันที** ticked, listed names send without a dialog; unticked, each message
needs approval. Every send appears in the Jarvis chat.

## Access and data handling

- Cloud requests go to Google's fixed HTTPS Gemini API endpoint. Redirects are
  blocked; the API key is in an HTTP header, not the URL.
- The API key stays in memory unless you tick save in AI settings; then it is
  stored in `data/gemini-key.dpapi`, encrypted for your Windows account (DPAPI).
  It is never included in logs, prompts or PC actions. Other software running under your
  Windows account can still potentially inspect process memory.
- Chat is held in memory and cleared on exit or New conversation. Recent chat
  context is sent with follow-up messages (up to 16 entries and a size budget).
  Windows itself may page process memory to disk.
- Google receives your sent messages and selected summary text. Its own retention
  and data-use policies apply independently of this app's memory-only chat.
  Unpaid services may use input/output for improvement and human review, with
  regional exceptions. Review [Google's terms](https://ai.google.dev/gemini-api/terms).
- Screen capture happens only during an approved screen-control task. No clipboard
  watcher, autonomous file browsing, arbitrary code execution, generated shell
  commands, extension loader, startup registration, inbound server or firewall
  changes are implemented.
- Allowed PC actions: open Calculator/Notepad/Explorer, open selected standard
  folders, open an HTTPS website, open a Google search, media keys, save a new note.
- Website validation restricts URL syntax, schemes, ports and obvious local
  targets. It does not inspect website content, verify DNS destinations or sandbox
  the external browser. Only approve websites you want to visit. Search terms go
  to Google when the browser opens the approved search.
- Opening a search does **not** give Jarvis its results. Outside approved screen
  steps and Discord rules, Jarvis cannot operate apps, send messages, delete/move
  files or install software.
- Stop prevents late results from reaching the conversation or becoming actions.
  It cannot recall a cloud request already sent or undo an approved PC action.
- Speech uses fixed bundled PowerShell scripts; spoken text goes through stdin,
  not script interpolation. No PowerShell execution-policy setting is changed.

The approval boundary is designed to reduce accidental AI actions. It is not an
OS sandbox and does not defend against already-malicious software running as your
Windows user. Review the actual action preview. AI replies can still be wrong.

## Verification

Run from this folder:

```powershell
python -m unittest discover -s tests -v
```

76 tests. They check fake approval flags, prohibited commands, URL validation,
single-use approvals, cancellation, note containment, summary action rejection,
HTTP credential handling, late responses, speech cancellation, provider routing
by model ID, the refusal to send audio to the cloud in Claude mode, the tray
message loop and instance guard, the hands-free wake-word turn, and real Tk UI
flows with simulated AI results and mocked PC effects.

Not covered by the suite: a live Claude or Gemini reply, a real microphone
capture, audible playback, and an actual run of `scripts\install-voice.ps1`.
Test those yourself from the desktop session.

## References used during implementation

- [Gemini API reference](https://ai.google.dev/api/generate-content)
- [Gemini model IDs](https://ai.google.dev/gemini-api/docs/models)
- [Windows speech recognition](https://learn.microsoft.com/en-us/dotnet/api/system.speech.recognition.speechrecognitionengine.recognize?view=netframework-4.8.1)
- [Windows SAPI speech synthesis](https://learn.microsoft.com/en-us/previous-versions/windows/desktop/ms723609(v=vs.85))

## Remove

Close Jarvis and delete this folder when you no longer need it. Keep any notes you
want to retain. No service, startup task or system-wide package was installed.
